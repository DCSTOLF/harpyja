"""Spec 0046 (AC4b/c/d) — the five-sided reactive accounting (eval-side).

Mirror-not-share vs ``submission_observability`` (spec 0044): the 0044 module is
a frozen historical pin; this is its 0046 sibling. Every per-cell outcome lands
in exactly ONE counted side (grid-total). ``s->wc`` and ``flagged-wrong-emitted``
PARTITION the fired-wrong-submitted mass by confirmation outcome, so their SUM is
the conserved 0045 quantity — a drop in one that merely relocates to the other is
visible (the de-attribution guard). The flag-rate diagnostic and the record-only
``unfired_confirm_found_but_unsubmitted`` cross-check ride BESIDE the counted
sides, never in the verdict.

Reuses ``metrics.span_hit_kind`` BY IDENTITY (one-oracle) and the 0045
``classify_silence_to_wrong_confidence`` BY IDENTITY (the conserved sum — a
single definition of the fired-wrong-submitted mass, no drift).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from harpyja.eval.live_verifier import classify_silence_to_wrong_confidence
from harpyja.eval.metrics import Span, span_hit_kind

__all__ = [
    "REACTIVE_SIDES",
    "classify_reactive_side",
    "classify_silence_to_wrong_confidence",
    "flag_rate",
    "reactive_side_of",
    "span_hit_kind",
    "unfired_confirm_found_but_unsubmitted",
]

# The six counted sides every per-cell outcome maps into.
REACTIVE_SIDES = frozenset(
    {"located", "s->wc", "flagged-wrong-emitted", "regression-or-miss", "fu", "honest-empty"}
)

# A wrong-but-submitted terminal bucket (a citation went out, not correct).
_SUBMITTED_WRONG_BUCKETS = frozenset({"wrong-file", "right-file-wrong-span"})
# Confirmation outcomes that emit a FLAGGED citation (the FAIL route).
_FLAG_OUTCOMES = frozenset({"FAIL", "CONFIRM_ERROR"})
# The 0043 submission-gap label for "found the gold, never submitted it".
_FOUND_UNSUBMITTED = "found-unsubmitted"


def classify_reactive_side(
    *,
    correct: bool,
    has_candidate: bool,
    swc_eligible: bool,
    confirmation: str | None,
    gold_in_tool_result: bool = False,
) -> str:
    """The truth-table side for one cell (total, pure).

    Counted by CORRECTNESS x s->wc-eligibility; the confirmation flag changes the
    side ONLY inside the s->wc-eligible-wrong partition (splitting s->wc from
    flagged-wrong-emitted), and is otherwise a diagnostic mark that never creates
    a new correctness side.
    """
    if not has_candidate:
        return "fu" if gold_in_tool_result else "honest-empty"
    if correct:
        return "located"  # flagged-but-correct still located
    if swc_eligible:
        if confirmation in _FLAG_OUTCOMES:
            return "flagged-wrong-emitted"
        return "s->wc"
    return "regression-or-miss"  # not-eligible wrong; a flag is diagnostic only


def reactive_side_of(trajectory: Mapping[str, Any], expected: Sequence[Span]) -> str:
    """Derive a cell's counted side from its persisted trajectory + gold.

    ``swc_eligible`` uses the gate-fired half here; the before-empty ("silence->")
    half is joined at ledger time (the 0045 posture). ``expected`` is accepted so
    a future finer eligibility check can route through ``span_hit_kind`` by
    identity without changing the seam.
    """
    bucket = trajectory.get("terminal_bucket")
    correct = bucket == "correct"
    submitted_wrong = bucket in _SUBMITTED_WRONG_BUCKETS
    has_candidate = correct or submitted_wrong
    swc_eligible = bool(trajectory.get("confidence_fired")) and submitted_wrong
    gold_in_tool = trajectory.get("submission_outcome") == _FOUND_UNSUBMITTED
    return classify_reactive_side(
        correct=correct,
        has_candidate=has_candidate,
        swc_eligible=swc_eligible,
        confirmation=trajectory.get("confirmation_outcome"),
        gold_in_tool_result=gold_in_tool,
    )


def flag_rate(cells: Sequence[Mapping[str, Any]]) -> float:
    """Record-only diagnostic: the fraction of CONFIRMED cells whose citation was
    flagged (confirmation FAIL/CONFIRM_ERROR). 0.0 when no cell was confirmed."""
    confirmed = [c for c in cells if c.get("confirmation_ran")]
    if not confirmed:
        return 0.0
    flagged = sum(1 for c in confirmed if c.get("confirmation_outcome") in _FLAG_OUTCOMES)
    return flagged / len(confirmed)


def unfired_confirm_found_but_unsubmitted(cells: Sequence[Mapping[str, Any]]) -> int:
    """Record-only, UNCONDITIONED cross-check (the 0045 conditioned-cost rule):
    count found-but-unsubmitted cells where confirmation did NOT run. Expected
    ~0 by construction (emit-with-flag never blocks) — PROVES emit-with-flag
    manufactures no fu rather than assuming it."""
    return sum(
        1
        for c in cells
        if c.get("submission_outcome") == _FOUND_UNSUBMITTED and not c.get("confirmation_ran")
    )
