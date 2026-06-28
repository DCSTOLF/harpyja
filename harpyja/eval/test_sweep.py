"""AC6 — sweep enumerates threshold × top_n grid via dataclasses.replace, K runs/point."""

from __future__ import annotations

import dataclasses

from harpyja.config.settings import Settings
from harpyja.eval.config import EvalConfig
from harpyja.eval.dataset import EvalCase, ExpectedSpan
from harpyja.eval.runner import LocateStack
from harpyja.eval.sweep import run_sweep
from harpyja.orchestrator.gate import GateOutcome
from harpyja.server.types import CodeSpan


class FakeEngine:
    def __init__(self, spans=()):
        self._spans = [CodeSpan(*s) for s in spans]

    def search(self, pattern, scope=None):
        return list(self._spans)


class FakeScout:
    def __init__(self, spans=()):
        self._spans = [CodeSpan(*s) for s in spans]

    def search(self, query, scope=None):
        return list(self._spans)


class FakeDeep:
    def __init__(self, spans=()):
        self._spans = [CodeSpan(*s) for s in spans]

    def run(self, query):
        return list(self._spans), None

    def search(self, pattern, scope=None):
        return list(self._spans)


class ThresholdGate:
    """Threshold-sensitive fake: pass iff a fixed score clears settings.verify_threshold."""

    def __init__(self, score):
        self._score = score

    def verify(self, query, citations, *, repo_path, settings):
        passed = self._score >= settings.verify_threshold
        return GateOutcome(passed=passed, score=self._score, scored_count=len(citations),
                           dropped_count=0, failed=False)


def _stack(tmp_path):
    art = tmp_path / "art"
    art.mkdir(exist_ok=True)
    return LocateStack(
        engine=FakeEngine([("a.py", 1, 1)]),
        symbol_engine=FakeEngine([]),
        scout_engine=FakeScout([("net.py", 12, 18)]),
        deep_engine=FakeDeep([("net.py", 10, 20)]),
        gate=ThresholdGate(score=0.65),
        indexer=lambda *a, **k: None,
        resolve_dir=lambda repo, settings: art,
        index_ready=True,
    )


def _cases():
    return [
        EvalCase("p1", "where is retry", "repo", (ExpectedSpan("net.py", 10, 20),), "point"),
        EvalCase("p2", "where is the other", "repo", (ExpectedSpan("zzz.py", 1, 2),), "point"),
    ]


def _kwargs(tmp_path):
    return dict(
        cases=_cases(),
        base_settings=Settings(),
        eval_config=EvalConfig(k_runs=3),
        thresholds=[0.5, 0.6, 0.7],
        top_ns=[3, 5],
        repo_path=str(tmp_path / "repo"),
        stack=_stack(tmp_path),
    )


def test_sweep_enumerates_threshold_top_n_grid(tmp_path):
    rep = run_sweep(**_kwargs(tmp_path))
    assert len(rep["sweep"]) == 3 * 2
    seen = {(p["verify_threshold"], p["verify_top_n"]) for p in rep["sweep"]}
    assert seen == {(t, n) for t in [0.5, 0.6, 0.7] for n in [3, 5]}


def test_sweep_builds_each_point_via_dataclasses_replace(tmp_path, monkeypatch):
    import harpyja.eval.sweep as sweep_mod

    calls: list[tuple] = []
    real_replace = dataclasses.replace

    def spy_replace(obj, **changes):
        if isinstance(obj, Settings):
            calls.append((changes.get("verify_threshold"), changes.get("verify_top_n")))
        return real_replace(obj, **changes)

    monkeypatch.setattr(sweep_mod, "replace", spy_replace)
    run_sweep(**_kwargs(tmp_path))
    # one replace per grid point, with the right axis values.
    assert set(calls) == {(t, n) for t in [0.5, 0.6, 0.7] for n in [3, 5]}


def test_sweep_does_not_mutate_settings(tmp_path):
    kwargs = _kwargs(tmp_path)
    base = kwargs["base_settings"]
    run_sweep(**kwargs)
    assert base.verify_threshold == 0.6
    assert base.verify_top_n == 3


def test_sweep_aggregates_per_point_mean_and_spread_over_k(tmp_path):
    rep = run_sweep(**_kwargs(tmp_path))
    point = rep["sweep"][0]
    agg = point["aggregate"]
    # each wrapped metric carries mean + spread; deterministic fakes -> spread 0.
    assert "escalation_rate" in agg
    assert "mean" in agg["escalation_rate"] and "spread" in agg["escalation_rate"]
    assert agg["escalation_rate"]["spread"] == 0.0


def test_sweep_emits_recommendation(tmp_path):
    rep = run_sweep(**_kwargs(tmp_path))
    rec = rep["recommendation"]
    assert "verify_threshold" in rec and "verify_top_n" in rec
    assert "incumbent_validated" in rec
