"""Normalize untrusted Scout backend output into safe `CodeSpan`s (AC7).

The backend's `<final_answer>` is untrusted. Each raw span is validated against
the repo root and the line bounds of the named file, deduped, and clamped to the
Scout budgets. Anything that can't be made valid is dropped — never propagated.
"""

from __future__ import annotations

import logging
from pathlib import Path

from harpyja.config.settings import Settings
from harpyja.server.types import CodeSpan

logger = logging.getLogger(__name__)


def _line_count(path: Path) -> int:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return sum(1 for _ in fh)


def normalize_spans_with_tally(
    raw: list[CodeSpan],
    repo_root: str,
    *,
    max_citations: int,
    max_span_lines: int,
) -> tuple[list[CodeSpan], int]:
    """Drop/clamp hostile spans; return ``(spans, dropped_count)``.

    Spec 0011: a **file-level** span (``is_file_level``, both lines ``None``) is a
    bare-path citation carrying no honest line range. It skips the line-range
    validation/clamp but still passes repo-confine + ``is_file`` + dedup, and is
    returned **carrying ``None`` lines** (no fabricated range). A **spanned** span
    (both ints) keeps the prior behavior byte-for-byte, so Tier-2/Deep — which only
    ever emits lined spans — is unaffected. A **half-``None``** span (one line set,
    one absent) is not a sanctioned shape and is dropped (AC23).

    Every ref discarded by a validation gate is **counted** (``dropped_count``, no
    silent coverage) and logged; dedup-skips and the ``max_citations`` budget cut
    are not drops.
    """
    root = Path(repo_root).resolve()
    seen: set[tuple[str, int | None, int | None]] = set()
    out: list[CodeSpan] = []
    dropped = 0

    for span in raw:
        # Half-None is not a sanctioned shape (file-level is both-None) — AC23.
        if (span.start_line is None) != (span.end_line is None):
            dropped += 1
            logger.info("scout normalize dropped half-None span: %s", span.path)
            continue

        # Path must resolve to a real file *inside* the repo root.
        resolved = (root / span.path).resolve()
        try:
            rel = resolved.relative_to(root)
        except ValueError:
            dropped += 1
            logger.info("scout normalize dropped out-of-repo ref: %s", span.path)
            continue  # outside the repo (absolute path or `..` traversal)
        if not resolved.is_file():
            dropped += 1
            logger.info("scout normalize dropped nonexistent ref: %s", span.path)
            continue

        if span.is_file_level:
            # File-level: no line range to validate/clamp — repo-confine + is_file
            # (above) + dedup only. Carried with None lines (honest precision).
            key = (str(rel), None, None)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                CodeSpan(
                    path=str(rel),
                    start_line=None,
                    end_line=None,
                    symbol=span.symbol,
                    language=span.language,
                    kind=span.kind,
                )
            )
        else:
            # Line range must be 1-based, non-inverted, and within the file.
            if span.start_line < 1 or span.end_line < span.start_line:
                dropped += 1
                logger.info("scout normalize dropped invalid line range: %s", span.path)
                continue
            n_lines = _line_count(resolved)
            if span.start_line > n_lines:
                dropped += 1
                logger.info("scout normalize dropped out-of-range line: %s", span.path)
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

    return out, dropped


def normalize_spans(
    raw: list[CodeSpan],
    repo_root: str,
    *,
    max_citations: int,
    max_span_lines: int,
) -> list[CodeSpan]:
    """Spans-only view of :func:`normalize_spans_with_tally` (legacy callers).

    The budgets are explicit so both tiers reuse this one clamp: Scout calls it
    via :func:`normalize_spans_for_scout` with the ``scout_*`` budgets; Deep
    (Tier 2) calls it with the ``deep_*`` budgets.
    """
    spans, _ = normalize_spans_with_tally(
        raw, repo_root, max_citations=max_citations, max_span_lines=max_span_lines
    )
    return spans


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
