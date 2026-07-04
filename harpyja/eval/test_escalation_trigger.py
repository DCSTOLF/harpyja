"""Spec 0021 (AC2) — the escalation-trigger truth table.

`classify_escalation` is a pure eval-side helper that maps a case's
(tier1_correct, gate_rejected, deep_available) plus the PLANNED ladder to
(will_escalate, wrong_citation_fate). It does NOT re-derive routing: every ladder
input here is produced by CALLING `harpyja.orchestrator.matrix.plan_ladder` — the
single source of truth (spec 0008 / conventions) — so the fate is deterministic,
not inferred from 0020 tribal knowledge.

The four fates form the MECE `wrong_citation_fate` axis of the AC4 finding:
GATE_FALSE_ACCEPTANCE | NO_ESCALATION_PATH | DEEP_DEGRADED_OR_UNAVAILABLE |
NOT_APPLICABLE.
"""

from __future__ import annotations

from harpyja.eval.escalation import WrongCitationFate, classify_escalation
from harpyja.orchestrator.matrix import plan_ladder


def test_classify_escalation_wrong_tier1_deep_available_escalates():
    # auto/point ladder has Tier-2 -> a wrong Tier-1 the gate rejects, with Deep up,
    # escalates. Fate NOT_APPLICABLE (escalation is the healthy path here).
    ladder = plan_ladder("auto", "point", True)
    assert ladder == [0, 1, 2]
    will, fate = classify_escalation(
        tier1_correct=False, gate_rejected=True, deep_available=True, ladder=ladder
    )
    assert will is True
    assert fate is WrongCitationFate.NOT_APPLICABLE


def test_classify_escalation_honest_empty_does_not_escalate():
    # FROZEN-SUT FACT (locate.py:161-165 _honest_empty): an empty Tier-1 is gate-
    # SKIPPED ("nothing to score") and terminates at [0,1] — it NEVER escalates,
    # even with Tier-2 on the ladder. This is escalation-by-design-absent, so its
    # fate is NO_ESCALATION_PATH, NOT an escalation. (Corrects the planner's
    # assumption that honest-empty escalates.)
    ladder = plan_ladder("auto", "point", True)
    will, fate = classify_escalation(
        tier1_empty=True, tier1_correct=False, gate_rejected=True,
        deep_available=True, ladder=ladder,
    )
    assert will is False
    assert fate is WrongCitationFate.NO_ESCALATION_PATH


def test_classify_escalation_gate_accept_no_escalation():
    # Wrong Tier-1 but the gate ACCEPTED it -> no escalation despite Tier-2 on-ladder.
    # This is the gate false-acceptance fate (mirror of G2's false-escalation target).
    ladder = plan_ladder("auto", "point", True)
    will, fate = classify_escalation(
        tier1_correct=False, gate_rejected=False, deep_available=True, ladder=ladder
    )
    assert will is False
    assert fate is WrongCitationFate.GATE_FALSE_ACCEPTANCE


def test_classify_escalation_deep_degraded_suppresses_escalation():
    # Gate rejected the wrong Tier-1, Tier-2 is on-ladder, but Deep is unavailable
    # (deep-degraded:<cause> / OOM) -> escalation honestly suppressed.
    ladder = plan_ladder("auto", "point", True)
    will, fate = classify_escalation(
        tier1_correct=False, gate_rejected=True, deep_available=False, ladder=ladder
    )
    assert will is False
    assert fate is WrongCitationFate.DEEP_DEGRADED_OR_UNAVAILABLE


def test_classify_escalation_no_tier2_on_ladder_is_no_path():
    # fast/point ladder is [0,1] (no Tier-2) -> a wrong Tier-1 cannot escalate by
    # design: NO_ESCALATION_PATH, regardless of gate/deep state.
    ladder = plan_ladder("fast", "point", True)
    assert 2 not in ladder
    will, fate = classify_escalation(
        tier1_correct=False, gate_rejected=True, deep_available=True, ladder=ladder
    )
    assert will is False
    assert fate is WrongCitationFate.NO_ESCALATION_PATH


def test_classify_escalation_correct_tier1_not_applicable():
    # A correct Tier-1 the gate accepts is not a wrong-citation case at all.
    ladder = plan_ladder("auto", "point", True)
    will, fate = classify_escalation(
        tier1_correct=True, gate_rejected=False, deep_available=True, ladder=ladder
    )
    assert will is False
    assert fate is WrongCitationFate.NOT_APPLICABLE


def test_classify_escalation_ladder_sourced_from_plan_ladder():
    # Regression guard against duplicating the routing matrix: the ladders this suite
    # feeds classify_escalation are exactly what plan_ladder returns.
    assert plan_ladder("auto", "point", True) == [0, 1, 2]
    assert plan_ladder("fast", "point", True) == [0, 1]
