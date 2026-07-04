"""AC5/AC8 / D3/D4 — variance rule + lexicographic OQ2 scorer."""

from __future__ import annotations

from harpyja.eval.config import EvalConfig
from harpyja.eval.recommend import (
    OUTCOME_GATE_CONFOUNDED,
    OUTCOME_RECOMMENDED,
    SweepPoint,
    advantage_exceeds_spread,
    rank_sweep,
    recommend_oq2,
)

# ---- D3 variance rule -------------------------------------------------------

def test_recommend_prefers_config_when_advantage_exceeds_spread():
    # candidate clearly lower (better) than incumbent, low noise -> advantage wins.
    candidate = [0.10, 0.12, 0.11]
    incumbent = [0.50, 0.52, 0.51]
    assert advantage_exceeds_spread(candidate, incumbent, higher_is_better=False) is True


def test_recommend_keeps_incumbent_under_noise():
    # candidate mean slightly lower but incumbent spread is large -> within noise.
    candidate = [0.40, 0.41, 0.39]
    incumbent = [0.10, 0.90, 0.50]  # huge spread
    assert advantage_exceeds_spread(candidate, incumbent, higher_is_better=False) is False


def test_advantage_higher_is_better_direction():
    candidate = [0.95, 0.96, 0.94]
    incumbent = [0.50, 0.51, 0.49]
    assert advantage_exceeds_spread(candidate, incumbent, higher_is_better=True) is True


# ---- D4 lexicographic scorer ------------------------------------------------

def _pt(thr, top_n, catch, false_esc, false_runs=None):
    return SweepPoint(
        verify_threshold=thr,
        verify_top_n=top_n,
        catch_rate_mean=catch,
        false_escalation_mean=false_esc,
        false_escalation_runs=tuple(false_runs if false_runs is not None else [false_esc]),
    )


def test_scorer_filters_points_below_catch_rate_bar():
    pts = [
        _pt(0.5, 3, catch=0.80, false_esc=0.01),  # below bar -> excluded
        _pt(0.6, 3, catch=0.92, false_esc=0.20),  # incumbent, clears bar
    ]
    rec = rank_sweep(pts, EvalConfig())
    assert (rec.verify_threshold, rec.verify_top_n) == (0.6, 3)


def test_scorer_minimizes_false_escalation_then_lower_top_n():
    pts = [
        _pt(0.6, 3, catch=0.95, false_esc=0.30, false_runs=[0.30, 0.30, 0.30]),  # incumbent
        _pt(0.7, 5, catch=0.95, false_esc=0.05, false_runs=[0.05, 0.05, 0.05]),  # best false-esc
        _pt(0.7, 3, catch=0.95, false_esc=0.05, false_runs=[0.05, 0.05, 0.05]),  # tie->top_n
    ]
    rec = rank_sweep(pts, EvalConfig())
    # winner beats incumbent clearly (0.30 -> 0.05, no noise) and ties broken to top_n=3
    assert (rec.verify_threshold, rec.verify_top_n) == (0.7, 3)
    assert rec.incumbent_validated is False
    assert rec.advantage_exceeds_variance is True


def test_scorer_deterministic_winner_from_fixed_table():
    pts = [
        _pt(0.5, 5, catch=0.91, false_esc=0.40, false_runs=[0.40, 0.40, 0.40]),
        _pt(0.6, 3, catch=0.93, false_esc=0.35, false_runs=[0.35, 0.35, 0.35]),
        _pt(0.8, 1, catch=0.90, false_esc=0.02, false_runs=[0.02, 0.02, 0.02]),
    ]
    r1 = rank_sweep(pts, EvalConfig())
    r2 = rank_sweep(list(reversed(pts)), EvalConfig())
    assert (r1.verify_threshold, r1.verify_top_n) == (0.8, 1)
    assert (r1.verify_threshold, r1.verify_top_n) == (r2.verify_threshold, r2.verify_top_n)


def test_recommend_marks_incumbent_validated_when_no_alternative_beats_noise():
    pts = [
        _pt(0.6, 3, catch=0.95, false_esc=0.30, false_runs=[0.10, 0.50, 0.30]),  # incumbent, noisy
        _pt(0.7, 3, catch=0.95, false_esc=0.28, false_runs=[0.28, 0.28, 0.28]),  # marginally better
    ]
    rec = rank_sweep(pts, EvalConfig())
    # 0.30 -> 0.28 advantage is within the incumbent's large spread -> keep incumbent
    assert (rec.verify_threshold, rec.verify_top_n) == (0.6, 3)
    assert rec.incumbent_validated is True
    assert rec.advantage_exceeds_variance is False


def test_rank_sweep_no_point_clears_bar_records_honestly():
    pts = [_pt(0.6, 3, catch=0.50, false_esc=0.10)]
    rec = rank_sweep(pts, EvalConfig())
    assert rec.incumbent_validated is False
    assert "bar" in rec.rationale.lower()


# ---- Spec 0019 D2/AC9: gate-confounded typed null ---------------------------

def _clean_grid():
    # A grid where rank_sweep would happily pick a clean winner.
    return [
        _pt(0.6, 3, catch=0.95, false_esc=0.30, false_runs=[0.30, 0.30, 0.30]),
        _pt(0.7, 3, catch=0.95, false_esc=0.05, false_runs=[0.05, 0.05, 0.05]),
    ]


def test_gate_confounded_below_ceiling_defers_to_rank_sweep():
    # Measured instruct false-escalation <= ceiling: the judge is trustworthy
    # enough to calibrate over, so recommend_oq2 returns exactly rank_sweep's pick.
    cfg = EvalConfig()  # ceiling 0.20
    pts = _clean_grid()
    rec = recommend_oq2(pts, measured_false_escalation=0.10, eval_config=cfg)
    clean = rank_sweep(pts, cfg)
    assert rec.outcome == OUTCOME_RECOMMENDED
    assert rec.gate_false_escalation_measured is None
    assert (rec.verify_threshold, rec.verify_top_n) == (
        clean.verify_threshold,
        clean.verify_top_n,
    )


def test_gate_confounded_above_ceiling_emits_typed_null():
    # Measured > ceiling: DO NOT calibrate verify_threshold over a still-broken
    # judge — emit the gate-confounded typed null instead of a clean pick.
    cfg = EvalConfig()
    rec = recommend_oq2(_clean_grid(), measured_false_escalation=0.35, eval_config=cfg)
    assert rec.outcome == OUTCOME_GATE_CONFOUNDED
    assert rec.incumbent_validated is False
    assert rec.advantage_exceeds_variance is False


def test_gate_confounded_carries_measured_rate():
    cfg = EvalConfig()
    rec = recommend_oq2(_clean_grid(), measured_false_escalation=0.42, eval_config=cfg)
    assert rec.outcome == OUTCOME_GATE_CONFOUNDED
    assert rec.gate_false_escalation_measured == 0.42
    assert "gate-confounded" in rec.rationale.lower()


def test_gate_confounded_exactly_at_ceiling_is_not_confounded():
    # Boundary: == ceiling is NOT confounded (strict `>`), so it defers to rank_sweep.
    cfg = EvalConfig()  # ceiling 0.20
    rec = recommend_oq2(_clean_grid(), measured_false_escalation=0.20, eval_config=cfg)
    assert rec.outcome == OUTCOME_RECOMMENDED


def test_recommend_oq2_none_measured_defers_to_rank_sweep():
    # No G2 measurement available (e.g. zero correct-Tier-1 point cases) -> not
    # confounded by absence; defer to the clean recommender.
    cfg = EvalConfig()
    pts = _clean_grid()
    rec = recommend_oq2(pts, measured_false_escalation=None, eval_config=cfg)
    assert rec.outcome == OUTCOME_RECOMMENDED
    assert (rec.verify_threshold, rec.verify_top_n) == (0.7, 3)


# ---- Spec 0020 (T1/P1): the NOT_SEPARABLE discriminator is reachable on the -------
# ---- byte-frozen Recommendation, distinct from a variance-beating flip ------------
#
# classify_g3_outcome (0020) must tell a no-survivor null from a variance-beating
# flip. Both carry outcome=="recommended" AND incumbent_validated=False, so
# incumbent_validated alone cannot discriminate. This LOCK proves the pair
# (incumbent_validated, advantage_exceeds_variance) does, WITHOUT touching the
# dispatcher: no-survivor is the UNIQUE (False, False) combo.

def test_recommend_no_survivor_is_unique_false_false_combo():
    # No grid point clears the catch-rate bar -> the honest "no defensible pick" null.
    rec = rank_sweep([_pt(0.6, 3, catch=0.50, false_esc=0.10)], EvalConfig())
    assert rec.outcome == OUTCOME_RECOMMENDED  # only two strings exist
    assert rec.incumbent_validated is False
    assert rec.advantage_exceeds_variance is False  # <-- the no-survivor signature


def test_recommend_variance_beating_flip_sets_advantage_true():
    # A clearly-better alternative beyond the incumbent's variance -> a flip, which is
    # NOT the no-survivor combo (advantage_exceeds_variance is True).
    pts = [
        _pt(0.6, 3, catch=0.95, false_esc=0.30, false_runs=[0.30, 0.30, 0.30]),
        _pt(0.7, 3, catch=0.95, false_esc=0.05, false_runs=[0.05, 0.05, 0.05]),
    ]
    rec = rank_sweep(pts, EvalConfig())
    assert (rec.verify_threshold, rec.verify_top_n) == (0.7, 3)
    assert rec.incumbent_validated is False
    assert rec.advantage_exceeds_variance is True  # distinguishes flip from no-survivor


def test_recommend_validated_incumbent_sets_incumbent_validated_true():
    # Best alternative within the incumbent's variance -> validated incumbent
    # (a RECOMMENDATION of (0.6,3)), the third distinct field combo.
    pts = [
        _pt(0.6, 3, catch=0.95, false_esc=0.30, false_runs=[0.10, 0.50, 0.30]),
        _pt(0.7, 3, catch=0.95, false_esc=0.28, false_runs=[0.28, 0.28, 0.28]),
    ]
    rec = rank_sweep(pts, EvalConfig())
    assert rec.incumbent_validated is True
    assert rec.advantage_exceeds_variance is False


# ---- Spec 0020 (T2/P2): byte-frozen recommend_oq2 behavior snapshot ---------------
#
# A fixed input->output field table. Any future edit to recommend_oq2 / rank_sweep
# that changes their behavior breaks this lock (the concretely-observable
# "byte-unchanged dispatcher" guard the 0020 review asked for — a behavior snapshot,
# not a source grep).

def _fields(rec):
    return (
        rec.verify_threshold,
        rec.verify_top_n,
        rec.catch_rate_bar,
        rec.advantage_exceeds_variance,
        rec.incumbent_validated,
        rec.outcome,
        rec.gate_false_escalation_measured,
    )


def test_recommend_oq2_behavior_snapshot_is_frozen():
    cfg = EvalConfig()  # catch_rate_bar 0.90, ceiling 0.20
    no_survivor = [_pt(0.6, 3, catch=0.50, false_esc=0.10)]
    validated = [
        _pt(0.6, 3, catch=0.95, false_esc=0.30, false_runs=[0.10, 0.50, 0.30]),
        _pt(0.7, 3, catch=0.95, false_esc=0.28, false_runs=[0.28, 0.28, 0.28]),
    ]
    flip = [
        _pt(0.6, 3, catch=0.95, false_esc=0.30, false_runs=[0.30, 0.30, 0.30]),
        _pt(0.7, 3, catch=0.95, false_esc=0.05, false_runs=[0.05, 0.05, 0.05]),
    ]
    # (points, measured_false_escalation) -> exact Recommendation field tuple
    assert _fields(recommend_oq2(no_survivor, None, cfg)) == (
        0.6, 3, 0.90, False, False, OUTCOME_RECOMMENDED, None,
    )
    assert _fields(recommend_oq2(validated, None, cfg)) == (
        0.6, 3, 0.90, False, True, OUTCOME_RECOMMENDED, None,
    )
    assert _fields(recommend_oq2(flip, None, cfg)) == (
        0.7, 3, 0.90, True, False, OUTCOME_RECOMMENDED, None,
    )
    # over-ceiling -> gate-confounded typed null (placeholder incumbent + measured rate)
    assert _fields(recommend_oq2(flip, 0.35, cfg)) == (
        0.6, 3, 0.90, False, False, OUTCOME_GATE_CONFOUNDED, 0.35,
    )
    # at/below ceiling -> defers to rank_sweep (same as the clean flip)
    assert _fields(recommend_oq2(flip, 0.10, cfg)) == (
        0.7, 3, 0.90, True, False, OUTCOME_RECOMMENDED, None,
    )
