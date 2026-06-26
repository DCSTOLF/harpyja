"""Citation formatter (AC14, AC11).

Turns raw `CodeSpan` matches into a ranked, deduplicated `Citation` list:
1. dedupe identical spans,
2. merge overlapping or adjacent same-file spans,
3. rank by `prior` then match density (number of raw spans merged in),
4. break ties stably on `(path, start_line)`,
5. clamp to `max_results`.
"""

from __future__ import annotations

from collections.abc import Callable

from harpyja.server.types import Citation, CodeSpan

PriorOf = Callable[[str], float]


def _merge_same_file(spans: list[CodeSpan]) -> list[tuple[CodeSpan, int]]:
    """Merge overlapping/adjacent spans within one file. Returns (span, density)."""
    ordered = sorted(spans, key=lambda s: (s.start_line, s.end_line))
    merged: list[tuple[int, int, int]] = []  # (start, end, density)
    for s in ordered:
        if merged and s.start_line <= merged[-1][1] + 1:  # overlap or adjacency
            start, end, density = merged[-1]
            merged[-1] = (start, max(end, s.end_line), density + 1)
        else:
            merged.append((s.start_line, s.end_line, 1))
    path = ordered[0].path
    return [
        (CodeSpan(path=path, start_line=st, end_line=en), density) for st, en, density in merged
    ]


def format_citations(
    spans: list[CodeSpan],
    prior_of: PriorOf,
    max_results: int,
) -> list[Citation]:
    # Dedupe identical spans.
    unique = {(s.path, s.start_line, s.end_line): s for s in spans}.values()

    by_path: dict[str, list[CodeSpan]] = {}
    for s in unique:
        by_path.setdefault(s.path, []).append(s)

    merged: list[tuple[CodeSpan, int]] = []
    for path_spans in by_path.values():
        merged.extend(_merge_same_file(path_spans))

    # Rank: prior desc, density desc, then stable (path, start_line).
    merged.sort(
        key=lambda sd: (
            -prior_of(sd[0].path),
            -sd[1],
            sd[0].path,
            sd[0].start_line,
        )
    )

    citations = [
        Citation(
            path=span.path,
            start_line=span.start_line,
            end_line=span.end_line,
            source_tier=0,
            score=prior_of(span.path),
        )
        for span, _density in merged
    ]
    return citations[:max_results]
