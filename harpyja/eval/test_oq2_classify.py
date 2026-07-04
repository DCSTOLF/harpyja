"""Spec 0020 (T3/P3, AC6/AC7/AC8) — the G3 outcome projection truth table.

`classify_g3_outcome` is a pure function ABOVE the byte-frozen `recommend_oq2`
dispatcher. It maps (recommendation, aggregate, eval_config) to exactly one of four
labels by the total order D > G > S > default, records ALL true blocking conditions
(not just the winner), and never computes the no-survivor (S) boolean under the
gate-confound short-circuit (which would book a phantom NOT_SEPARABLE).
"""

from __future__ import annotations

from harpyja.eval.config import EvalConfig
from harpyja.eval.oq2_classify import (
    DEGRADED_DOMINATED,
    GATE_CONFOUNDED,
    NOT_SEPARABLE,
    RECOMMENDATION,
    classify_g3_outcome,
)
from harpyja.eval.recommend import (
    OUTCOME_GATE_CONFOUNDED,
    OUTCOME_RECOMMENDED,
    Recommendation,
)


def _rec(*, outcome=OUTCOME_RECOMMENDED, incumbent_validated=False, advantage=False,
         measured=None):
    return Recommendation(
        verify_threshold=0.6,
        verify_top_n=3,
        catch_rate_bar=0.90,
        advantage_exceeds_variance=advantage,
        incumbent_validated=incumbent_validated,
        rationale="",
        outcome=outcome,
        gate_false_escalation_measured=measured,
    )


def _agg(*, degraded_dominated=False, effective_n=12):
    return {"degraded_dominated": degraded_dominated, "effective_n": effective_n}


# ---- precedence D > G > S > default -----------------------------------------

def test_classify_g3_outcome_degraded_dominated_wins():
    # D=T with a plain recommended rec (so S would be computable) -> DEGRADED_DOMINATED.
    c = classify_g3_outcome(_rec(advantage=True), _agg(degraded_dominated=True), EvalConfig())
    assert c.label == DEGRADED_DOMINATED
    assert c.degraded_dominated is True


def test_classify_g3_outcome_gate_confounded_when_not_degraded():
    # D=F, G=T -> GATE_CONFOUNDED; S is n/a (rank_sweep never ran) -> None, no phantom.
    c = classify_g3_outcome(
        _rec(outcome=OUTCOME_GATE_CONFOUNDED, measured=0.35), _agg(), EvalConfig()
    )
    assert c.label == GATE_CONFOUNDED
    assert c.gate_confounded is True
    assert c.no_survivor is None


def test_classify_g3_outcome_not_separable_no_survivor():
    # D=F, G=F, S=T (the no-survivor field combo) -> NOT_SEPARABLE.
    c = classify_g3_outcome(
        _rec(incumbent_validated=False, advantage=False), _agg(), EvalConfig()
    )
    assert c.label == NOT_SEPARABLE
    assert c.no_survivor is True


def test_classify_g3_outcome_recommendation_validated_incumbent():
    # D=F, G=F, S=F (validated incumbent) -> RECOMMENDATION (D2: within-variance is
    # NOT NOT_SEPARABLE).
    c = classify_g3_outcome(
        _rec(incumbent_validated=True, advantage=False), _agg(effective_n=30), EvalConfig()
    )
    assert c.label == RECOMMENDATION
    assert c.no_survivor is False


def test_classify_g3_outcome_recommendation_variance_beating_flip():
    # D=F, G=F, S=F (flip) -> RECOMMENDATION.
    c = classify_g3_outcome(
        _rec(incumbent_validated=False, advantage=True), _agg(effective_n=30), EvalConfig()
    )
    assert c.label == RECOMMENDATION
    assert c.no_survivor is False


# ---- record ALL true conditions (AC7) ---------------------------------------

def test_classify_g3_outcome_both_degraded_and_gate_confounded_records_both():
    # D=T and G=T -> label DEGRADED_DOMINATED (precedence), but BOTH booleans recorded.
    c = classify_g3_outcome(
        _rec(outcome=OUTCOME_GATE_CONFOUNDED, measured=0.4),
        _agg(degraded_dominated=True),
        EvalConfig(),
    )
    assert c.label == DEGRADED_DOMINATED
    assert c.degraded_dominated is True
    assert c.gate_confounded is True
    assert c.no_survivor is None  # still n/a — gate-confounded short-circuit


# ---- indicative_only sub-flag on RECOMMENDATION only (AC8) -------------------

def test_classify_g3_outcome_indicative_only_below_n_floor():
    # RECOMMENDATION with effective_N (12) < n_floor (30) -> indicative_only True.
    c = classify_g3_outcome(_rec(advantage=True), _agg(effective_n=12), EvalConfig())
    assert c.label == RECOMMENDATION
    assert c.indicative_only is True


def test_classify_g3_outcome_not_indicative_at_or_above_n_floor():
    # effective_N == n_floor (30) -> indicative_only False.
    c = classify_g3_outcome(_rec(advantage=True), _agg(effective_n=30), EvalConfig())
    assert c.label == RECOMMENDATION
    assert c.indicative_only is False


def test_classify_g3_outcome_indicative_only_false_for_typed_nulls():
    # indicative_only is a RECOMMENDATION sub-flag only — never set on a typed null.
    c = classify_g3_outcome(
        _rec(outcome=OUTCOME_GATE_CONFOUNDED, measured=0.9), _agg(effective_n=12), EvalConfig()
    )
    assert c.label == GATE_CONFOUNDED
    assert c.indicative_only is False
