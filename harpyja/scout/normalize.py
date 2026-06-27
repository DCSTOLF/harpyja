"""Normalize untrusted Scout backend output into safe `CodeSpan`s (AC7).

The backend's `<final_answer>` is untrusted. Each raw span is validated against
the repo root and the line bounds of the named file, deduped, and clamped to the
Scout budgets. Anything that can't be made valid is dropped — never propagated.
"""

from __future__ import annotations

from pathlib import Path

from harpyja.config.settings import Settings
from harpyja.server.types import CodeSpan


def _line_count(path: Path) -> int:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return sum(1 for _ in fh)


def normalize_spans(
    raw: list[CodeSpan],
    repo_root: str,
    *,
    max_citations: int,
    max_span_lines: int,
) -> list[CodeSpan]:
    """Drop/clamp hostile spans; return at most ``max_citations`` of them.

    The budgets are explicit so both tiers reuse this one clamp: Scout calls it
    via :func:`normalize_spans_for_scout` with the ``scout_*`` budgets; Deep
    (Tier 2) calls it with the ``deep_*`` budgets.
    """
    root = Path(repo_root).resolve()
    seen: set[tuple[str, int, int]] = set()
    out: list[CodeSpan] = []

    for span in raw:
        # Path must resolve to a real file *inside* the repo root.
        resolved = (root / span.path).resolve()
        try:
            rel = resolved.relative_to(root)
        except ValueError:
            continue  # outside the repo (absolute path or `..` traversal)
        if not resolved.is_file():
            continue

        # Line range must be 1-based, non-inverted, and within the file.
        if span.start_line < 1 or span.end_line < span.start_line:
            continue
        n_lines = _line_count(resolved)
        if span.start_line > n_lines:
            continue

        end = min(span.end_line, n_lines)
        # Clamp an over-long span to the first max_span_lines lines.
        end = min(end, span.start_line + max_span_lines - 1)

        key = (str(rel), span.start_line, end)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            CodeSpan(
                path=str(rel),
                start_line=span.start_line,
                end_line=end,
                symbol=span.symbol,
                language=span.language,
                kind=span.kind,
            )
        )
        if len(out) >= max_citations:
            break

    return out


def normalize_spans_for_scout(
    raw: list[CodeSpan],
    repo_root: str,
    settings: Settings,
) -> list[CodeSpan]:
    """Scout-budget wrapper over :func:`normalize_spans` (byte-identical clamp)."""
    return normalize_spans(
        raw,
        repo_root,
        max_citations=settings.scout_max_citations,
        max_span_lines=settings.scout_max_span_lines,
    )
