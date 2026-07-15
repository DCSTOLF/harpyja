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

from harpyja.server.types import CodeSpan

# Spec 0046 (AC1): the 0045 require-corroboration LEVER is RETIRED — recorded as
# a measured regression, not a silent deletion. On the 0045 live run, gating the
# ACTION on corroboration collapsed firing to 3/33 and drove found-but-unsubmitted
# from 1 -> 8 (net -1, typed TRADES_DIRECTIONS): the evidence belonged in the
# OUTPUT path (confirm-before-submit), not the firing condition. The 0044 gate
# below (`qualifying_symbols_spans`) is the restored, wired firing condition; the
# gold-blind overlap primitive (`spans_overlap_line`) is RETAINED in
# `confidence_signals` for the reactive triggers / confirm interceptor.
CORROBORATION_RETIRED_RATIONALE = (
    "0045's require-corroboration-to-fire is retired as a measured regression "
    "(firing collapsed 3/33, found-but-unsubmitted 1 -> 8, net -1, "
    "TRADES_DIRECTIONS): it gated the ACTION when the evidence belonged in the "
    "OUTPUT path. The 0044 firing condition (qualifying_symbols_spans) is restored."
)

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


def build_confidence_nudge(spans: list[CodeSpan]) -> dict[str, Any]:
    """The ONE bounded, model-visible nudge message (role `user`), built from
    the frozen template over ALL qualifying spans."""
    rendered = ", ".join(f"{s.path}:{s.start_line}-{s.end_line}" for s in spans)
    return {"role": "user", "content": CONFIDENCE_NUDGE_TEMPLATE.format(spans=rendered)}
