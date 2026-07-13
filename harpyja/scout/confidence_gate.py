"""Spec 0044 — the gold-blind confidence gate (AC1).

The pre-registered confidence definition, signal (a) SOLELY: a symbols-derived
exact span. A `symbols` tool result QUALIFIES iff ALL of:

- **clean** — no 0035 marker of either shape: a bare marker string (the
  REPLACEMENT result) or a marker riding ahead of real spans (the 0042
  ANNOTATION shape) disqualifies the result;
- **bounded** — 1..``CONFIDENCE_MAX_QUALIFYING_SPANS`` spans: an
  exact-definition lookup is confidence, a multi-hundred-entry repo-wide
  substring batch (up to ``scout_symbols_repo_max_entries``) is a candidate
  list, and firing on it would reintroduce submit-before-verify through the
  gate itself;
- **exact-span-shaped** — every carried span has explicit start/end lines
  (citation-shaped by construction; a file-level span is not "exact").

File-local (``path``-scoped) and repo-wide (``name``-only) results are judged
by the SAME three conditions — the span-count bound excludes the repo-wide
blast radius, not the call route.

GOLD-BLIND by construction: this module lives in ``scout/``, sees only a tool
result, and imports nothing from ``eval/`` (ast-pinned). The postflight
fired-on-wrong-span attribution — which DOES need gold — lives on the eval
side and reuses ``metrics.span_hit_kind`` by identity.

The nudge text is SUT surface exactly as the 0043 unconditional sentence was:
the frozen template names ALL qualifying spans (never implying a single
certain target) and is byte-pinned by the frozen 0044 config.
"""

from __future__ import annotations

from typing import Any

from harpyja.scout.confidence_signals import spans_overlap_line
from harpyja.server.types import CodeSpan

# The frozen span-count bound (mirrored as data in the frozen 0044 config).
CONFIDENCE_MAX_QUALIFYING_SPANS = 5

# The triggering-signal label recorded in trajectory artifacts (AC3/AC4).
CONFIDENCE_SIGNAL = "symbols-exact-span"

# The frozen nudge template — multi-span wording: the message names the
# evidence without steering toward an arbitrary first span.
CONFIDENCE_NUDGE_TEMPLATE = (
    "Your symbols result contains the exact span(s): {spans}. "
    "If one of these spans answers the query, call submit_citations with it now."
)


def qualifying_symbols_spans(result: Any) -> list[CodeSpan]:
    """The pre-registered qualifying projection over one raw `symbols` result.

    Returns the qualifying spans (the gate fires) or ``[]`` (no fire). Total
    over every result shape the tool can produce: bare marker string
    (REPLACEMENT), marker-annotated list (ANNOTATION), empty list, over-bound
    batch, non-exact (line-less) spans.
    """
    if not isinstance(result, list):
        return []
    if not 1 <= len(result) <= CONFIDENCE_MAX_QUALIFYING_SPANS:
        return []
    spans: list[CodeSpan] = []
    for item in result:
        if not isinstance(item, CodeSpan):
            return []  # a marker string (ANNOTATION) or foreign shape — not clean
        if item.start_line is None or item.end_line is None:
            return []  # file-level is not "exact"
        spans.append(item)
    return spans


def _exact(span: Any) -> bool:
    return (
        isinstance(span, CodeSpan)
        and span.start_line is not None
        and span.end_line is not None
    )


def _is_corroborated(
    candidate: CodeSpan,
    prior_spans: list[tuple[str, CodeSpan]],
    result_tool: str,
) -> bool:
    """A candidate span is corroborated iff an earlier DIFFERENT-tool span
    line-overlaps it (convergence) OR a prior grep hit lies inside it
    (containment). Same-tool repetition is NOT corroboration.

    Overlap routes through the gold-free ``spans_overlap_line`` (shared by
    identity with the eval-side oracle's "line" grade — one definition)."""
    for tool_name, prior in prior_spans:
        if not _exact(prior) or tool_name == result_tool:
            continue
        if spans_overlap_line(candidate, prior):
            return True
        if (
            tool_name == "grep"
            and prior.path == candidate.path
            and candidate.start_line <= prior.start_line
            and prior.end_line <= candidate.end_line
        ):
            return True
    return False


def qualifying_confidence_spans(
    result: Any,
    prior_spans: list[tuple[str, CodeSpan]] | None = None,
    result_tool: str = "symbols",
) -> list[CodeSpan]:
    """Spec 0045 REFINED gate (require-corroboration, AC3).

    Fires (returns the qualifying spans) only on CORROBORATED exact spans — a
    bare uncorroborated bounded symbols span (the 0044 weak singleton) no longer
    fires. Corroboration credits convergence (a different-tool line overlap) and
    grep-inside-symbol containment against ``prior_spans`` (the earlier
    tool-result spans, in order). An over-bound batch is admitted only for its
    corroborated members, and the corroborated set is itself bounded so a
    candidate list cannot return through the gate.

    Gold-blind: consumes only the trajectory (this result + prior spans).
    """
    prior_spans = prior_spans or []
    if not isinstance(result, list) or not result:
        return []
    # Clean-only: a marker string (REPLACEMENT/ANNOTATION) disqualifies.
    if any(not isinstance(item, CodeSpan) for item in result):
        return []
    corroborated = [
        span
        for span in result
        if _exact(span) and _is_corroborated(span, prior_spans, result_tool)
    ]
    if not 1 <= len(corroborated) <= CONFIDENCE_MAX_QUALIFYING_SPANS:
        return []
    return corroborated


def build_confidence_nudge(spans: list[CodeSpan]) -> dict[str, Any]:
    """The ONE bounded, model-visible nudge message (role `user`), built from
    the frozen template over ALL qualifying spans."""
    rendered = ", ".join(f"{s.path}:{s.start_line}-{s.end_line}" for s in spans)
    return {"role": "user", "content": CONFIDENCE_NUDGE_TEMPLATE.format(spans=rendered)}
