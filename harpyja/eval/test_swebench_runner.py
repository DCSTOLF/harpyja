"""Spec 0010 — the per-case-repo driver (AC5, AC6, AC7, AC8, AC11).

Each case carries its OWN repo (a SWE-bench worktree) and its own injected stack.
The driver pools per-case outcomes into the unchanged metrics + additive report,
overrides routing to the patch-shape label through the `LocateStack.classifier`
seam (D-route), and records the production-classifier agreement. No live model.
"""

from __future__ import annotations

import time

from harpyja.config.settings import Settings
from harpyja.eval.config import EvalConfig
from harpyja.eval.dataset import EvalCase, ExpectedSpan
from harpyja.eval.report import validate_report
from harpyja.eval.runner import LocateStack
from harpyja.eval.swebench_eval import PROTOCOL, run_swebench
from harpyja.orchestrator.gate import GateOutcome
from harpyja.server.types import CodeSpan

_ART = None  # tmp artifact dir so locate's manifest read returns [] (set per test)


class FakeEngine:
    def __init__(self, spans=()):
        self._spans = list(spans)

    def search(self, pattern, scope=None):
        return list(self._spans)


class FakeScout:
    def __init__(self, spans=(), delay=0.0):
        self._spans = list(spans)
        self._delay = delay

    def search(self, query, scope=None):
        if self._delay:
            time.sleep(self._delay)
        return list(self._spans)


class FakeDeep:
    def __init__(self, spans=()):
        self._spans = list(spans)

    def run(self, query):
        return list(self._spans), None

    def search(self, pattern, scope=None):
        return list(self._spans)


class FakeGate:
    def __init__(self, passed):
        self._passed = passed

    def verify(self, query, citations, *, repo_path, settings):
        return GateOutcome(
            passed=self._passed, score=1.0 if self._passed else 0.0,
            scored_count=len(citations), dropped_count=0, failed=False,
        )


def _span(path, a, b):
    return CodeSpan(path=path, start_line=a, end_line=b)


def _stack(*, scout_spans=(), deep_spans=(), gate_passed=True,
           seed_spans=(("a.py", 1, 1),), scout_delay=0.0):
    return LocateStack(
        engine=FakeEngine([_span(*s) for s in seed_spans]),
        symbol_engine=FakeEngine([]),
        scout_engine=FakeScout([_span(*s) for s in scout_spans], delay=scout_delay),
        deep_engine=FakeDeep([_span(*s) for s in deep_spans]),
        gate=FakeGate(gate_passed),
        indexer=lambda *a, **k: None,
        resolve_dir=lambda repo, settings: _ART,
        index_ready=True,
    )


class _Factory:
    """A stack_factory that returns a pre-built stack per repo and records calls."""

    def __init__(self, by_repo):
        self.by_repo = by_repo
        self.repos = []

    def __call__(self, settings, repo):
        self.repos.append(repo)
        return self.by_repo[repo]


def _cfg():
    return EvalConfig()


def _settings():
    return Settings()


def _setart(tmp_path):
    global _ART
    _ART = tmp_path / "art"
    _ART.mkdir(exist_ok=True)


# --- AC6: per-case-repo driver ----------------------------------------------

def test_driver_pools_two_distinct_repo_cases_into_schema(tmp_path):
    _setart(tmp_path)
    cases = [
        EvalCase("p1", "where retry", "/repoA", (ExpectedSpan("net.py", 10, 20),), "point"),
        EvalCase("b1", "how it fits", "/repoB", (ExpectedSpan("main.py", 1, 50),), "broad"),
    ]
    factory = _Factory({
        "/repoA": _stack(scout_spans=[("net.py", 12, 18)], gate_passed=True),
        "/repoB": _stack(deep_spans=[("main.py", 5, 9)]),
    })
    report = run_swebench(
        cases, _settings(), _cfg(), stack_factory=factory,
        out_dir=tmp_path / "out", write=True,
        production_classifier=lambda q: "point",
    )
    assert factory.repos == ["/repoA", "/repoB"]  # each case used its own repo
    assert len(report["cases"]) == 2
    validate_report(report)


def test_driver_writes_outside_every_case_repo(tmp_path):
    _setart(tmp_path)
    # out_dir inside a case repo must be refused.
    repo = tmp_path / "repoA"
    repo.mkdir()
    cases = [EvalCase("p1", "q", str(repo), (ExpectedSpan("a.py", 1, 2),), "point")]
    factory = _Factory({str(repo): _stack(scout_spans=[("a.py", 1, 2)])})
    raised = False
    try:
        run_swebench(
            cases, _settings(), _cfg(), stack_factory=factory,
            out_dir=repo / "inside", write=True,
            production_classifier=lambda q: "point",
        )
    except ValueError:
        raised = True
    assert raised


def test_driver_every_gate_metric_present(tmp_path):
    _setart(tmp_path)
    # only a broad case → empty point subset → gate metrics null-with-count (D2)
    cases = [EvalCase("b1", "q", "/repoB", (ExpectedSpan("m.py", 1, 9),), "broad")]
    factory = _Factory({"/repoB": _stack(deep_spans=[("m.py", 1, 9)])})
    report = run_swebench(
        cases, _settings(), _cfg(), stack_factory=factory,
        production_classifier=lambda q: "broad",
    )
    agg = report["aggregate"]
    assert agg["gate_catch_rate"] is None and agg["wrong_tier1_count"] == 0
    assert agg["gate_false_escalation"] is None and agg["correct_tier1_count"] == 0


# --- AC5 / D-route: routing override + agreement -----------------------------

def test_driver_override_forces_point_so_gate_runs(tmp_path):
    _setart(tmp_path)
    # production text classifier says "broad", but patch-shape is "point": the
    # driver injects "point" via the classifier seam so the gate fires.
    cases = [EvalCase("p1", "broad-sounding prose", "/r", (ExpectedSpan("n.py", 10, 20),), "point")]
    factory = _Factory({"/r": _stack(scout_spans=[("n.py", 12, 18)], gate_passed=True)})
    report = run_swebench(
        cases, _settings(), _cfg(), stack_factory=factory,
        production_classifier=lambda q: "broad",
    )
    case = report["cases"][0]
    assert 1 in case["tiers_run"]                 # routed point → Scout/gate ran
    assert case["production_gate_ran"] is True


def test_driver_records_both_labels_and_agreement(tmp_path):
    _setart(tmp_path)
    cases = [
        EvalCase("p1", "q1", "/r1", (ExpectedSpan("a.py", 1, 5),), "point"),
        EvalCase("p2", "q2", "/r2", (ExpectedSpan("b.py", 1, 5),), "point"),
    ]
    factory = _Factory({
        "/r1": _stack(scout_spans=[("a.py", 1, 5)], gate_passed=True),
        "/r2": _stack(scout_spans=[("b.py", 1, 5)], gate_passed=True),
    })
    # production agrees on p1 (point), disagrees on p2 (broad) → agreement 0.5
    labels = {"q1": "point", "q2": "broad"}
    report = run_swebench(
        cases, _settings(), _cfg(), stack_factory=factory,
        production_classifier=lambda q: labels[q],
    )
    by = {c["case_id"]: c for c in report["cases"]}
    assert by["p1"]["patch_shape_label"] == "point"
    assert by["p1"]["production_classifier_label"] == "point"
    assert by["p2"]["production_classifier_label"] == "broad"
    assert report["aggregate"]["classifier_agreement_rate"] == 0.5


def test_production_label_captured_not_the_injected_override(tmp_path):
    _setart(tmp_path)
    # The override would make every label "point"; agreement must reflect the
    # PRODUCTION classifier (here "broad"), not the injected one.
    cases = [EvalCase("p1", "q", "/r", (ExpectedSpan("a.py", 1, 5),), "point")]
    factory = _Factory({"/r": _stack(scout_spans=[("a.py", 1, 5)], gate_passed=True)})
    report = run_swebench(
        cases, _settings(), _cfg(), stack_factory=factory,
        production_classifier=lambda q: "broad",
    )
    assert report["cases"][0]["production_classifier_label"] == "broad"
    assert report["aggregate"]["classifier_agreement_rate"] == 0.0


def test_without_override_point_case_would_route_broad(tmp_path):
    # Documents what the intervention changes: with the production label injected
    # as the classifier, a "broad"-classified point case bypasses the gate.
    _setart(tmp_path)
    from dataclasses import replace

    from harpyja.eval.runner import run_case
    base = _stack(scout_spans=[("n.py", 12, 18)], deep_spans=[("n.py", 12, 18)], gate_passed=True)
    bypass = replace(base, classifier=lambda *a, **k: "broad")
    case = EvalCase("p1", "q", "/r", (ExpectedSpan("n.py", 10, 20),), "point")
    run = run_case(case, _settings(), _cfg(), repo_path="/r", stack=bypass)
    assert run.event["tiers_run"] == [0, 2]  # straight to Deep; gate bypassed


def test_production_gate_ran_distinct_from_gate_triggered_in_fast(tmp_path):
    _setart(tmp_path)
    # fast mode: the harness Scout probe sees spans (gate_triggered True) but the
    # production gate is informational, so production_gate_ran is False — distinct.
    cases = [EvalCase("p1", "q", "/r", (ExpectedSpan("n.py", 10, 20),), "point")]
    factory = _Factory({"/r": _stack(scout_spans=[("n.py", 12, 18)], gate_passed=True)})
    report = run_swebench(
        cases, _settings(), _cfg(), stack_factory=factory, mode="fast",
        production_classifier=lambda q: "point",
    )
    case = report["cases"][0]
    assert case["gate_triggered"] is True          # harness-observed
    assert case["production_gate_ran"] is False     # SUT-observed (fast → informational)


# --- AC7: fast-vs-auto driver block ------------------------------------------

def test_driver_fast_mode_no_case_escalates(tmp_path):
    _setart(tmp_path)
    cases = [
        EvalCase("p1", "q1", "/r1", (ExpectedSpan("a.py", 1, 5),), "point"),
        EvalCase("b1", "q2", "/r2", (ExpectedSpan("b.py", 1, 5),), "broad"),
    ]
    factory = _Factory({
        "/r1": _stack(scout_spans=[("a.py", 1, 5)], gate_passed=False),  # would escalate in auto
        "/r2": _stack(scout_spans=[("b.py", 1, 5)], gate_passed=False),
    })
    report = run_swebench(
        cases, _settings(), _cfg(), stack_factory=factory, mode="fast",
        production_classifier=lambda q: "point",
    )
    validate_report(report)
    assert report["run_metadata"]["mode"] == "fast"
    assert all(c["escalated_to_deep"] is False for c in report["cases"])


# --- AC8: durable metadata + provenance --------------------------------------

def test_report_carries_durable_metadata_and_provenance(tmp_path):
    _setart(tmp_path)
    provenance = {
        "hf_dataset_id": "princeton-nlp/SWE-bench_Verified",
        "hf_split": "test",
        "hf_revision": "fp-1",
        "raw_fixture_sha256": "a" * 64,
        "sample_case_ids": ["p1"],
    }
    cases = [EvalCase("p1", "q", "/r", (ExpectedSpan("a.py", 1, 5),), "point")]
    factory = _Factory({"/r": _stack(scout_spans=[("a.py", 1, 5)], gate_passed=True)})
    report = run_swebench(
        cases, _settings(), _cfg(), stack_factory=factory,
        production_classifier=lambda q: "point",
        provenance=provenance, new_file_only_excluded_count=3, malformed_skipped_count=2,
    )
    rm = report["run_metadata"]
    assert rm["protocol"] == PROTOCOL
    assert rm["dataset_provenance"]["hf_split"] == "test"
    assert rm["span_inflation_tolerance"] == 3
    assert isinstance(rm["contamination_caveat"], str) and rm["contamination_caveat"]
    assert rm["new_file_only_excluded_count"] == 3
    assert rm["malformed_skipped_count"] == 2


# --- AC11: runtime budget (per-case timeout + sample cap) --------------------

def test_driver_honors_sample_cap(tmp_path):
    _setart(tmp_path)
    cases = [
        EvalCase(f"c{i}", "q", f"/r{i}", (ExpectedSpan("a.py", 1, 5),), "broad")
        for i in range(5)
    ]
    factory = _Factory({f"/r{i}": _stack(deep_spans=[("a.py", 1, 5)]) for i in range(5)})
    report = run_swebench(
        cases, _settings(), _cfg(), stack_factory=factory, sample_cap=2,
        production_classifier=lambda q: "broad",
    )
    assert len(report["cases"]) == 2
    assert report["run_metadata"]["seed_n"] == 2


def test_driver_per_case_timeout_counted_skip(tmp_path):
    _setart(tmp_path)
    # a point case whose Scout probe sleeps past the timeout → counted skip, not a
    # hung run and not a silent zero.
    cases = [EvalCase("slow", "q", "/r", (ExpectedSpan("a.py", 1, 5),), "point")]
    factory = _Factory({"/r": _stack(scout_spans=[("a.py", 1, 5)], scout_delay=0.3)})
    report = run_swebench(
        cases, _settings(), _cfg(), stack_factory=factory, per_case_timeout=0.01,
        production_classifier=lambda q: "point",
    )
    assert report["cases"] == []  # the slow case was skipped, not scored
    assert report["run_metadata"]["timed_out_count"] == 1


# --- AC11: OQ2 sweep logic (deterministic; complements the live integration) -

def _sweep(tmp_path, *, prod_label, k_runs=2):
    from harpyja.eval.config import EvalConfig
    from harpyja.eval.swebench_eval import run_swebench_sweep

    _setart(tmp_path)
    cases = [EvalCase("p1", "q", "/r", (ExpectedSpan("a.py", 1, 5),), "point")]
    factory = _Factory({"/r": _stack(scout_spans=[("a.py", 1, 5)], gate_passed=True)})
    return run_swebench_sweep(
        cases, _settings(), EvalConfig(k_runs=k_runs), stack_factory=factory,
        thresholds=(0.5, 0.6), top_ns=(3,),
        production_classifier=lambda q: prod_label,
    )


def test_swebench_sweep_enumerates_grid_and_recommends(tmp_path):
    report = _sweep(tmp_path, prod_label="point")
    assert len(report["sweep"]) == 2  # 2 thresholds × 1 top_n
    rec = report["recommendation"]
    assert rec["verify_threshold"] in (0.5, 0.6)
    assert rec["verify_top_n"] == 3


def test_swebench_sweep_low_agreement_flags_deltas_only(tmp_path):
    rec = _sweep(tmp_path, prod_label="broad")["recommendation"]
    assert rec["classifier_agreement_rate"] == 0.0
    assert rec["oq2_low_confidence"] is True
    assert rec["oq2_basis"] == "deltas-only"


def test_swebench_sweep_high_agreement_is_calibration(tmp_path):
    rec = _sweep(tmp_path, prod_label="point")["recommendation"]
    assert rec["classifier_agreement_rate"] == 1.0
    assert rec["oq2_low_confidence"] is False
    assert rec["oq2_basis"] == "calibration"


def test_swebench_sweep_does_not_mutate_base_settings(tmp_path):
    base = _settings()
    before = (base.verify_threshold, base.verify_top_n)
    _sweep(tmp_path, prod_label="point")
    assert (base.verify_threshold, base.verify_top_n) == before  # replace-only
