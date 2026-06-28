"""AC4 — runner drives the real `locate` auto path via injected fakes; assembles
a schema-conforming report without a live model; writes artifacts outside the repo."""

from __future__ import annotations

from harpyja.eval.config import EvalConfig
from harpyja.eval.dataset import EvalCase, ExpectedSpan
from harpyja.eval.report import validate_report
from harpyja.eval.runner import LocateStack, run_dataset
from harpyja.orchestrator.gate import GateOutcome
from harpyja.server.types import CodeSpan


class FakeEngine:
    """Tier-0 / symbol fake; returns a fixed span list regardless of query."""

    def __init__(self, spans=()):
        self._spans = list(spans)

    def search(self, pattern, scope=None):
        return list(self._spans)


class FakeScout:
    def __init__(self, spans=()):
        self._spans = list(spans)

    def search(self, query, scope=None):
        return list(self._spans)


class FakeDeep:
    def __init__(self, spans=()):
        self._spans = list(spans)

    def run(self, query):
        return list(self._spans), None

    def search(self, pattern, scope=None):
        return list(self._spans)


class FakeGate:
    """Deterministic gate: pass/fail is fixed (no model, no disk read-back)."""

    def __init__(self, passed):
        self._passed = passed

    def verify(self, query, citations, *, repo_path, settings):
        return GateOutcome(
            passed=self._passed, score=1.0 if self._passed else 0.0,
            scored_count=len(citations), dropped_count=0, failed=False,
        )


def _span(path, a, b):
    return CodeSpan(path=path, start_line=a, end_line=b)


def _stack(*, scout_spans, deep_spans, gate_passed, seed_spans=(("a.py", 1, 1),)):
    return LocateStack(
        engine=FakeEngine([_span(*s) for s in seed_spans]),
        symbol_engine=FakeEngine([]),
        scout_engine=FakeScout([_span(*s) for s in scout_spans]),
        deep_engine=FakeDeep([_span(*s) for s in deep_spans]),
        gate=FakeGate(gate_passed),
        indexer=lambda *a, **k: None,
        resolve_dir=lambda repo, settings: _ARTDIR,
        index_ready=True,
    )


# a stable empty artifact dir so locate's read_manifest returns [] (set per-test).
_ARTDIR = None


def _cases():
    return [
        # point, scout hits expected, gate passes -> tiers [0,1], no escalation
        EvalCase("p_ok", "where is retry", "repo", (ExpectedSpan("net.py", 10, 20),), "point"),
        # point, scout misses, gate fails -> escalate to deep which hits -> [0,1,2]
        EvalCase("p_esc", "where is auth", "repo", (ExpectedSpan("auth.py", 5, 9),), "point"),
        # broad -> straight to deep [0,2]; excluded from gate metrics
        EvalCase("b1", "how does it all fit", "repo", (ExpectedSpan("main.py", 1, 50),), "broad"),
    ]


def _make_settings():
    from harpyja.config.settings import Settings

    return Settings()


def _run(tmp_path):
    global _ARTDIR
    art = tmp_path / "art"
    art.mkdir()
    _ARTDIR = art
    settings = _make_settings()
    cfg = EvalConfig()
    out = tmp_path / "eval-out"
    cases = _cases()
    # Per-case stack: point-ok hits, point-esc misses+deep-hits, broad deep-hits.
    # The runner takes ONE stack; we drive different behaviour through the fakes
    # by giving scout/deep span sets that match each case's expected location.
    stack = _stack(
        scout_spans=[("net.py", 12, 18)],   # hits p_ok expected; misses others
        deep_spans=[("auth.py", 5, 9)],     # hits p_esc + (broad uses deep too)
        gate_passed=False,                  # force escalation on point misses
    )
    return run_dataset(
        cases, settings, cfg,
        repo_path=str(tmp_path / "repo"),
        stack=stack, out_dir=out, write=True, repo_revision="testrev",
    ), out


def test_runner_drives_auto_path_with_injected_fakes(tmp_path):
    report, _ = _run(tmp_path)
    assert len(report["cases"]) == 3
    by_id = {c["case_id"]: c for c in report["cases"]}
    # broad routed straight to Deep
    assert by_id["b1"]["tiers_run"] == [0, 2]
    assert by_id["b1"]["escalated_to_deep"] is True
    assert by_id["b1"]["gate_eligible"] is False


def test_runner_assembles_report_without_live_model(tmp_path):
    report, _ = _run(tmp_path)
    assert report["aggregate"]["span_hit_rate_primary"] >= 0.0
    assert "escalation_rate" in report["aggregate"]


def test_runner_report_conforms_to_schema(tmp_path):
    report, _ = _run(tmp_path)
    validate_report(report)


def test_runner_writes_artifacts_outside_repo(tmp_path):
    _, out = _run(tmp_path)
    written = out / "report.json"
    assert written.exists()
    repo = tmp_path / "repo"
    assert repo.resolve() not in out.resolve().parents and out.resolve() != repo.resolve()


def test_runner_per_case_records_gate_decision_fields(tmp_path):
    report, _ = _run(tmp_path)
    by_id = {c["case_id"]: c for c in report["cases"]}
    # point case where scout hit and gate failed: gate-eligible, escalated
    p_esc = by_id["p_esc"]
    assert p_esc["gate_eligible"] is True
    assert p_esc["escalated_to_deep"] is True
    assert p_esc["tiers_run"] == [0, 1, 2]
    assert p_esc["terminal_tier"] == 2
    # tier1_correct is a bool for a point case (scout missed auth.py -> False)
    assert p_esc["tier1_correct"] is False
    # broad case: tier1_correct is None (no Tier-1 to judge)
    assert by_id["b1"]["tier1_correct"] is None
