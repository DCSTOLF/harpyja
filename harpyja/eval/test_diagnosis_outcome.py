"""Spec 0043 T14 — the total pure AC6 verdict.

``decide_diagnosis_outcome`` is a TOTAL pure function over the frozen config
and the retained per-case pairs. The power qualification is a returned enum
member (``CLOCK_BOUND_UNDER_POWERED``, gated by the frozen floors), never
prose; bucket movement is BIDIRECTIONAL (conversions AND regressions, net
surfaced) so a single noise flip cannot type ``CLOCK_BOUND_FIXED``; the
per-side ``detector-inconclusive`` counts enter the verdict (identical
detector prevents definition drift, not input-distribution drift).
"""

import itertools

from harpyja.eval.diagnosis_config import PREREGISTERED_DIAGNOSIS_CONFIG_0043
from harpyja.eval.diagnosis_outcome import (
    DiagnosisVerdict,
    decide_diagnosis_outcome,
)

CFG = PREREGISTERED_DIAGNOSIS_CONFIG_0043


def _cells(
    n,
    *,
    fu=0,
    correct=0,
    inconclusive=0,
):
    """Build a BEFORE/AFTER cell dict: `fu` found-unsubmitted (bucket empty),
    `correct` submitted-correct, `inconclusive` detector-inconclusive, the
    rest honest never-found empties."""
    cells = {}
    for i in range(n):
        key = f"case-{i}::qwen3:14b"
        if i < fu:
            cells[key] = {"bucket": "empty", "submission_outcome": "found-unsubmitted"}
        elif i < fu + correct:
            cells[key] = {"bucket": "correct", "submission_outcome": "submitted"}
        elif i < fu + correct + inconclusive:
            cells[key] = {
                "bucket": "empty",
                "submission_outcome": "detector-inconclusive",
            }
        else:
            cells[key] = {"bucket": "empty", "submission_outcome": "never-found"}
    return cells


def _flip(cells, key, bucket, submission):
    out = dict(cells)
    out[key] = {"bucket": bucket, "submission_outcome": submission}
    return out


def test_decide_diagnosis_outcome_grid_totality():
    """Exactly one of the four branches for EVERY grid cell — no input is a
    judgment call."""
    verdicts = set()
    for covered_ok, fu_drops, net in itertools.product(
        [True, False], [True, False], [-1, 0, 1]
    ):
        n = CFG.min_covered_before_cells if covered_ok else 2
        fu_before = CFG.min_before_found_unsubmitted if covered_ok else 1
        before = _cells(n, fu=fu_before, correct=1)
        after = dict(before)
        if fu_drops:
            # one found-unsubmitted cell resolves (bucket unchanged: movement
            # and the fu-drop are independent axes)
            after = _flip(after, "case-0::qwen3:14b", "empty", "submitted")
        if net >= 1:
            after = _flip(after, "case-1::qwen3:14b", "correct", "submitted")
        if net <= -1:
            # the one before-correct cell regresses
            key = f"case-{fu_before}::qwen3:14b"
            after = _flip(after, key, "empty", "never-found")
        outcome = decide_diagnosis_outcome(CFG, before, after)
        assert isinstance(outcome.verdict, DiagnosisVerdict)
        verdicts.add(outcome.verdict)
    assert verdicts == set(DiagnosisVerdict) - {DiagnosisVerdict.NOT_CLOCK_BOUND}


def test_under_powered_gated_by_frozen_floors():
    """Below EITHER frozen floor the verdict is the mechanical UNDER_POWERED
    branch — an enum member, never prose — even when the deltas look great."""
    # Covered subset below the floor:
    before = _cells(CFG.min_covered_before_cells - 1, fu=3, correct=1)
    after = {
        k: {"bucket": "correct", "submission_outcome": "submitted"} for k in before
    }
    outcome = decide_diagnosis_outcome(CFG, before, after)
    assert outcome.verdict is DiagnosisVerdict.CLOCK_BOUND_UNDER_POWERED
    # Found-unsubmitted denominator below its floor (coverage fine):
    before = _cells(CFG.min_covered_before_cells, fu=1, correct=1)
    after = _flip(before, "case-0::qwen3:14b", "correct", "submitted")
    outcome = decide_diagnosis_outcome(CFG, before, after)
    assert outcome.verdict is DiagnosisVerdict.CLOCK_BOUND_UNDER_POWERED
    assert outcome.covered_before == CFG.min_covered_before_cells


def test_bucket_movement_is_bidirectional_net_surfaced():
    """Conversions AND regressions are netted from the retained pairs — one
    conversion cancelled by one regression is net 0, NOT a fix."""
    before = _cells(10, fu=3, correct=2)
    after = _flip(before, "case-0::qwen3:14b", "correct", "submitted")  # conversion
    after = _flip(after, "case-3::qwen3:14b", "empty", "never-found")  # regression
    outcome = decide_diagnosis_outcome(CFG, before, after)
    assert outcome.conversions == 1
    assert outcome.regressions == 1
    assert outcome.net == 0
    assert outcome.verdict is DiagnosisVerdict.CLOCK_BOUND_PERSISTS
    # The single-noise-flip guard: same movement WITHOUT the regression → FIXED.
    after = _flip(before, "case-0::qwen3:14b", "correct", "submitted")
    outcome = decide_diagnosis_outcome(CFG, before, after)
    assert (outcome.conversions, outcome.regressions, outcome.net) == (1, 0, 1)
    assert outcome.verdict is DiagnosisVerdict.CLOCK_BOUND_FIXED


def test_per_side_inconclusive_counts_enter_verdict():
    """BEFORE and AFTER inconclusive counts are reported per side; a large
    asymmetry is a NAMED caveat — the raw delta alone would be
    uninterpretable under input-distribution drift."""
    before = _cells(10, fu=3, correct=1, inconclusive=3)
    after = {
        k: (
            dict(v, submission_outcome="never-found")
            if v["submission_outcome"] == "detector-inconclusive"
            else v
        )
        for k, v in before.items()
    }
    after = _flip(after, "case-0::qwen3:14b", "correct", "submitted")
    outcome = decide_diagnosis_outcome(CFG, before, after)
    assert outcome.inconclusive_before == 3
    assert outcome.inconclusive_after == 0
    assert any("inconclusive" in c for c in outcome.caveats)
    # Balanced inconclusives → no asymmetry caveat.
    outcome2 = decide_diagnosis_outcome(CFG, before, dict(before))
    assert outcome2.inconclusive_before == outcome2.inconclusive_after == 3
    assert not any("inconclusive" in c for c in outcome2.caveats)


def test_not_clock_bound_when_attribution_refutes():
    """ZERO found-unsubmitted cells on adequate coverage refutes the
    hypothesis — the losses are elsewhere; say so and redirect."""
    before = _cells(10, fu=0, correct=2)
    outcome = decide_diagnosis_outcome(CFG, before, dict(before))
    assert outcome.verdict is DiagnosisVerdict.NOT_CLOCK_BOUND
    assert outcome.residual  # the redirect is named, not empty
