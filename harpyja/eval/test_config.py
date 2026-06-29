"""AC5 (part) / D6 — EvalConfig provisional constants + repeated-run aggregation."""

from __future__ import annotations

import dataclasses

from harpyja.config.settings import Settings
from harpyja.eval.config import EvalConfig, aggregate_runs


def test_eval_config_defaults_pin_provisional_constants():
    cfg = EvalConfig()
    assert cfg.k_runs >= 1
    assert cfg.proximity_window_lines == 50
    assert cfg.n_floor == 30
    assert cfg.catch_rate_bar == 0.90


def test_eval_config_has_degraded_dominated_threshold_default():
    # Spec 0011 (AC15): the degraded-dominated threshold is an eval-only knob,
    # provisional 0.5 (a majority of cases degraded ⇒ the run characterizes the
    # degrade floor, not the SUT). The disjointness test above guards it from
    # leaking into production Settings.
    assert EvalConfig().degraded_dominated_threshold == 0.5


def test_eval_config_is_frozen():
    cfg = EvalConfig()
    try:
        cfg.k_runs = 99  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("EvalConfig must be frozen")


def test_eval_config_is_independent_of_settings():
    # K-placement guard: eval knobs must never leak into the frozen SUT Settings.
    eval_fields = {f.name for f in dataclasses.fields(EvalConfig)}
    settings_fields = {f.name for f in dataclasses.fields(Settings)}
    assert eval_fields.isdisjoint(settings_fields)


def test_aggregate_runs_mean_and_spread_pstdev():
    import statistics

    values = [0.4, 0.6, 0.8]
    agg = aggregate_runs(values)
    assert abs(agg["mean"] - statistics.mean(values)) < 1e-9
    assert abs(agg["spread"] - statistics.pstdev(values)) < 1e-9


def test_aggregate_runs_single_run_zero_spread():
    agg = aggregate_runs([0.7])
    assert agg["mean"] == 0.7
    assert agg["spread"] == 0.0


def test_aggregate_runs_empty_is_null_with_zero_spread():
    agg = aggregate_runs([])
    assert agg["mean"] is None
    assert agg["spread"] == 0.0
