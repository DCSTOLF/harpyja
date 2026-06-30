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

# Spec 0012: a recovered suffix must carry at least this many segments — a bare
# basename (1 segment) is never recovered (the specificity floor).
MIN_TAIL_SEGMENTS = 2


def _line_count(path: Path) -> int:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return sum(1 for _ in fh)


def _recover_suffix(
    cited_path: str, file_set: frozenset[str], top_level: frozenset[str]
) -> str | None:
    """Spec 0012: recover an out-of-repo cited path by its longest unique suffix.

    The model hallucinates a leading root (e.g. ``/pallets/flask/...``) onto an
    otherwise-real repo path. For ``k`` from the full length down to
    ``MIN_TAIL_SEGMENTS``, take the last ``k`` segments as ``tail`` and match it
    against the manifest ``file_set`` (segment-aligned: ``p == tail`` or ``p`` ends
    with ``"/" + tail``). Recovery requires (a) the tail's **head** is a known
    top-level manifest entry — a fabricated mid-tree suffix is rejected — and (b)
    **exactly one** match at the longest such ``k``. Ambiguous (>1) → drop, never a
    silent pick and never a fall-back to a shorter, less specific tail. Returns the
    repo-relative manifest path, or ``None`` to drop. No filesystem access here; the
    caller re-validates the returned path with repo-confine + ``is_file``.
    """
    if not file_set:
        return None
    segs = [s for s in cited_path.replace("\\", "/").split("/") if s not in ("", ".", "..")]
    for k in range(len(segs), MIN_TAIL_SEGMENTS - 1, -1):
        tail_segs = segs[len(segs) - k :]
        if tail_segs[0] not in top_level:
            continue  # leading-segment guard: tail must be anchored at a top-level entry
        tail = "/".join(tail_segs)
        matches = [p for p in file_set if p == tail or p.endswith("/" + tail)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return None  # ambiguous at the most specific tail → honest drop
    return None


def normalize_spans_with_tally(
    raw: list[CodeSpan],
    repo_root: str,
    *,
    max_citations: int,
    max_span_lines: int,
    file_set: frozenset[str] | None = None,
    recovered_paths_out: list[str] | None = None,
) -> tuple[list[CodeSpan], int, int, int]:
    """Drop/clamp hostile spans; return ``(spans, dropped, rec_spanned, rec_filelevel)``.

    Spec 0011: a **file-level** span (``is_file_level``, both lines ``None``) is a
    bare-path citation carrying no honest line range. It skips the line-range
    validation/clamp but still passes repo-confine + ``is_file`` + dedup, and is
    returned **carrying ``None`` lines** (no fabricated range). A **spanned** span
    (both ints) keeps the prior behavior byte-for-byte, so Tier-2/Deep — which only
    ever emits lined spans — is unaffected. A **half-``None``** span (one line set,
    one absent) is not a sanctioned shape and is dropped (AC23).

    Spec 0012: when a path does not resolve to a real in-repo file, attempt bounded
    suffix recovery against ``file_set`` (the indexed manifest's repo-relative paths)
    **before** dropping — see :func:`_recover_suffix`. A recovered path re-enters the
    normal repo-confine + ``is_file`` (+ clamp) validation, so recovery composes with,
    never bypasses, 0011's checks. ``file_set`` absent/empty ⇒ no recovery (graceful
    degrade to the 0011 drop). ``recovered_spanned`` / ``recovered_filelevel`` count
    the kept-by-recovery refs by shape (the file-level kind skips the gate read-back,
    so the two are tracked separately).

    Every ref discarded by a validation gate is **counted** (``dropped``, no silent
    coverage) and logged; dedup-skips and the ``max_citations`` budget cut are not
    drops.
    """
    root = Path(repo_root).resolve()
    top_level = frozenset(p.split("/")[0] for p in file_set) if file_set else frozenset()
    seen: set[tuple[str, int | None, int | None]] = set()
    out: list[CodeSpan] = []
    dropped = 0
    recovered_spanned = 0
    recovered_filelevel = 0

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
            in_repo = resolved.is_file()
        except ValueError:
            in_repo = False

        recovered = False
        if not in_repo:
            # Spec 0012: try suffix recovery before dropping.
            rec = _recover_suffix(span.path, file_set or frozenset(), top_level)
            if rec is None:
                dropped += 1
                logger.info("scout normalize dropped unrecoverable out-of-repo ref: %s", span.path)
                continue
            resolved = (root / rec).resolve()
            try:
                rel = resolved.relative_to(root)
            except ValueError:
                dropped += 1
                continue
            if not resolved.is_file():  # defensive: stale manifest entry
                dropped += 1
                logger.info("scout normalize dropped stale recovered ref: %s", rec)
                continue
            recovered = True
            logger.info("scout normalize recovered %s -> %s", span.path, rec)

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
            if recovered:
                recovered_filelevel += 1
                if recovered_paths_out is not None:
                    recovered_paths_out.append(str(rel))
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
            if recovered:
                recovered_spanned += 1
        if len(out) >= max_citations:
            break

    return out, dropped, recovered_spanned, recovered_filelevel


def normalize_spans(
    raw: list[CodeSpan],
    repo_root: str,
    *,
    max_citations: int,
    max_span_lines: int,
    file_set: frozenset[str] | None = None,
) -> list[CodeSpan]:
    """Spans-only view of :func:`normalize_spans_with_tally` (legacy callers).

    The budgets are explicit so both tiers reuse this one clamp: Scout calls it
    via :func:`normalize_spans_for_scout` with the ``scout_*`` budgets; Deep
    (Tier 2) calls it with the ``deep_*`` budgets.
    """
    spans, _dropped, _rs, _rf = normalize_spans_with_tally(
        raw, repo_root, max_citations=max_citations, max_span_lines=max_span_lines,
        file_set=file_set,
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
