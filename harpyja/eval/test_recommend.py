"""AC5/AC8 / D3/D4 — variance rule + lexicographic OQ2 scorer."""

from __future__ import annotations

from harpyja.eval.config import EvalConfig
from harpyja.eval.recommend import (
    SweepPoint,
    advantage_exceeds_spread,
    rank_sweep,
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
