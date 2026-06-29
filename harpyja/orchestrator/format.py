"""Citation formatter (AC14, AC11; Wave 2: AC10, AC12).

Turns raw `CodeSpan` matches into a ranked, deduplicated `Citation` list:
1. dedupe identical spans (including symbol identity, so co-located defs survive),
2. merge overlapping or adjacent same-file spans,
3. rank by `prior`, then a **definition boost** (a span carrying a `symbol` — a
   definition — ranks above raw text hits of equal prior, D10/D11), then match
   density (number of raw spans merged in),
4. break ties with the stable total order `(path, start_line, end_line, kind, name)`,
5. clamp to `max_results`.

The boost is a **placeholder** weight: it is layered on top of `prior` + density and
MUST preserve "definition above call site" for the same token (D12). With no
definition spans present, the ranking reduces exactly to the Wave-1 order.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from harpyja.server.types import Citation, CodeSpan

PriorOf = Callable[[str], float]


@dataclass
class _Merged:
    path: str
    start_line: int | None  # None ⇒ file-level (spec 0011)
    end_line: int | None
    density: int
    is_def: bool
    symbol: str | None
    kind: str | None


def _merge_same_file(spans: list[CodeSpan]) -> list[_Merged]:
    """Within one file: keep each definition span as a distinct citation, and merge
    overlapping/adjacent **raw text** spans among themselves (Wave-1 behavior).

    A definition is a precise, individually-citable range — merging it away (e.g. a
    method span absorbed into its enclosing class span) would lose the very symbol
    the query promoted, so definitions are never merged.

    Spec 0011: a **file-level** (line-less) span has no range to order or merge
    against, so it is **never** adjacency-merged into a lined span — it survives as
    its own coarse citation carrying ``None`` lines. The line-merge runs only over
    lined text spans, so a ``None`` line never reaches the arithmetic.
    """
    out: list[_Merged] = [
        _Merged(s.path, s.start_line, s.end_line, 1, True, s.symbol, s.kind)
        for s in spans
        if s.symbol is not None
    ]
    # File-level spans: distinct, never merged (no line range to merge on).
    out.extend(
        _Merged(s.path, None, None, 1, False, None, None)
        for s in spans
        if s.symbol is None and s.is_file_level
    )

    texts = sorted(
        (s for s in spans if s.symbol is None and not s.is_file_level),
        key=lambda s: (s.start_line, s.end_line),
    )
    merged_texts: list[_Merged] = []
    for s in texts:
        if merged_texts and s.start_line <= merged_texts[-1].end_line + 1:  # overlap/adjacency
            m = merged_texts[-1]
            m.end_line = max(m.end_line, s.end_line)
            m.density += 1
        else:
            merged_texts.append(_Merged(s.path, s.start_line, s.end_line, 1, False, None, None))
    out.extend(merged_texts)
    return out


def format_citations(
    spans: list[CodeSpan],
    prior_of: PriorOf,
    max_results: int,
    source_tier: int = 0,
) -> list[Citation]:
    # Dedupe identical spans — keyed on symbol identity too, so co-located distinct
    # definitions (e.g. `A = 1; B = 2`) are not collapsed.
    unique: dict[tuple, CodeSpan] = {}
    for s in spans:
        unique.setdefault((s.path, s.start_line, s.end_line, s.symbol, s.kind), s)

    by_path: dict[str, list[CodeSpan]] = {}
    for s in unique.values():
        by_path.setdefault(s.path, []).append(s)

    merged: list[_Merged] = []
    for path_spans in by_path.values():
        merged.extend(_merge_same_file(path_spans))

    # Rank: prior desc, then definition boost, then density desc, then a stable
    # total order. The boost (0 for defs, 1 otherwise) sits between prior and
    # density so a definition outranks a denser call-site cluster of equal prior.
    # Stable order is None-safe: a file-level (line-less) span sorts AFTER lined
    # spans of the same path (coarser precision last), never compared int-vs-None.
    merged.sort(
        key=lambda m: (
            -prior_of(m.path),
            0 if m.is_def else 1,
            -m.density,
            m.path,
            m.start_line is None,
            m.start_line or 0,
            m.end_line or 0,
            m.kind or "",
            m.symbol or "",
        )
    )

    citations = [
        Citation(
            path=m.path,
            start_line=m.start_line,
            end_line=m.end_line,
            symbol=m.symbol,
            kind=m.kind,
            source_tier=source_tier,
            score=prior_of(m.path),
        )
        for m in merged
    ]
    return citations[:max_results]
