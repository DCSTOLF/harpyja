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


# --- spec 0010: run_case `mode` seam (AC7) -----------------------------------

class _FakeResult:
    citations = ()
    tiers_run = (0,)
    notes = None


def test_run_case_accepts_mode_and_threads_into_locate_request(monkeypatch):
    from harpyja.eval import runner as R

    captured = {}

    def fake_locate(req, settings, **kw):
        captured["mode"] = req.mode
        return _FakeResult()

    monkeypatch.setattr("harpyja.orchestrator.locate.locate", fake_locate)
    case = EvalCase("c", "q", "repo", (ExpectedSpan("a.py", 1, 2),), "broad")
    stack = LocateStack(engine=FakeEngine([]))
    R.run_case(case, _make_settings(), EvalConfig(), repo_path="repo", stack=stack, mode="fast")
    assert captured["mode"] == "fast"


def test_run_case_defaults_to_auto(monkeypatch):
    from harpyja.eval import runner as R

    captured = {}

    def fake_locate(req, settings, **kw):
        captured["mode"] = req.mode
        return _FakeResult()

    monkeypatch.setattr("harpyja.orchestrator.locate.locate", fake_locate)
    case = EvalCase("c", "q", "repo", (ExpectedSpan("a.py", 1, 2),), "broad")
    stack = LocateStack(engine=FakeEngine([]))
    R.run_case(case, _make_settings(), EvalConfig(), repo_path="repo", stack=stack)
    assert captured["mode"] == "auto"


def test_run_dataset_forwards_mode_to_run_case(monkeypatch, tmp_path):
    from harpyja.eval import runner as R

    modes = []

    def fake_locate(req, settings, **kw):
        modes.append(req.mode)
        return _FakeResult()

    monkeypatch.setattr("harpyja.orchestrator.locate.locate", fake_locate)
    cases = [EvalCase("b1", "q", "repo", (ExpectedSpan("m.py", 1, 9),), "broad")]
    stack = LocateStack(engine=FakeEngine([]))
    R.run_dataset(
        cases, _make_settings(), EvalConfig(),
        repo_path="repo", stack=stack, mode="fast",
    )
    assert modes == ["fast"]


# --- Spec 0011 (citation-shape): degrade visibility + shape counts (AC14/17/19) ---

from harpyja.config.settings import Settings  # noqa: E402
from harpyja.scout import errors as _scout_errors  # noqa: E402
from harpyja.scout.engine import ScoutTally  # noqa: E402
from harpyja.scout.errors import ScoutUnavailable  # noqa: E402


class _RaisingScout:
    def search(self, query, scope=None):
        raise ScoutUnavailable(_scout_errors.BACKEND_ERROR)


class _TallyScout:
    """Returns preset spans and exposes a fixed last_tally (the carrier seam)."""

    def __init__(self, spans, tally):
        self._spans = list(spans)
        self._tally = tally
        self.last_tally = None

    def search(self, query, scope=None):
        self.last_tally = self._tally
        return list(self._spans)


def _degrade_stack(scout, art):
    return LocateStack(
        engine=FakeEngine([]),
        symbol_engine=FakeEngine([]),
        scout_engine=scout,
        deep_engine=None,
        gate=FakeGate(True),
        indexer=lambda *a, **k: None,
        resolve_dir=lambda repo, settings: art,
        index_ready=True,
    )


def _point(case_id="p", path="a.py"):
    return EvalCase(case_id, "where is x", "repo", (ExpectedSpan(path, 1, 2),), "point")


def test_runner_reports_scout_degrade_count_and_rate(tmp_path):
    # AC14: a scout-degraded case is counted; rate = count / cases_attempted.
    art = tmp_path / "art"
    art.mkdir()
    stack = _degrade_stack(_RaisingScout(), art)
    rep = run_dataset(
        [_point("p1"), _point("p2")], Settings(), EvalConfig(),
        repo_path=str(tmp_path / "repo"), stack=stack,
    )
    agg = rep["aggregate"]
    assert agg["scout_degrade_count"] == 2
    assert agg["scout_degrade_rate"] == 1.0


def test_runner_degrade_rate_null_with_zero_denominator(tmp_path):
    # AC14: zero cases → explicit null paired with the (zero) count, never 0.0.
    art = tmp_path / "art"
    art.mkdir()
    stack = _degrade_stack(_RaisingScout(), art)
    rep = run_dataset([], Settings(), EvalConfig(), repo_path=str(tmp_path / "repo"), stack=stack)
    agg = rep["aggregate"]
    assert agg["scout_degrade_rate"] is None
    assert agg["scout_degrade_count"] == 0


# --- Spec 0014 (P8): Deep-degrade visibility — twin of the scout machinery ---

from harpyja.deep.errors import PARSE_ERROR as _DEEP_PARSE_ERROR  # noqa: E402
from harpyja.deep.errors import DeepUnavailable as _DeepUnavailable  # noqa: E402


class _UnavailableDeep:
    def __init__(self, cause):
        self.cause = cause

    def run(self, query):
        raise _DeepUnavailable(self.cause)


def _deep_degrade_stack(deep, scout, art):
    return LocateStack(
        engine=FakeEngine([]),
        symbol_engine=FakeEngine([]),
        scout_engine=scout,
        deep_engine=deep,
        gate=FakeGate(True),
        indexer=lambda *a, **k: None,
        resolve_dir=lambda repo, settings: art,
        index_ready=True,
    )


def test_runner_reports_deep_degrade_count_and_rate(tmp_path):
    # AC6: a deep-degraded case is counted; rate = count / cases_attempted (mode=deep,
    # Deep floors to a healthy Scout best-effort).
    art = tmp_path / "art"
    art.mkdir()
    scout = _TallyScout([_span("a.py", 1, 2)], ScoutTally())
    stack = _deep_degrade_stack(_UnavailableDeep(_DEEP_PARSE_ERROR), scout, art)
    rep = run_dataset(
        [_point("p1"), _point("p2")], Settings(), EvalConfig(),
        repo_path=str(tmp_path / "repo"), stack=stack, mode="deep",
    )
    agg = rep["aggregate"]
    assert agg["deep_degrade_count"] == 2
    assert agg["deep_degrade_rate"] == 1.0


def test_runner_deep_degrade_rate_null_with_zero_denominator(tmp_path):
    # AC10: zero cases → explicit null paired with the (zero) count, never 0.0.
    art = tmp_path / "art"
    art.mkdir()
    stack = _deep_degrade_stack(
        _UnavailableDeep(_DEEP_PARSE_ERROR), _TallyScout([], ScoutTally()), art
    )
    rep = run_dataset(
        [], Settings(), EvalConfig(), repo_path=str(tmp_path / "repo"), stack=stack, mode="deep"
    )
    agg = rep["aggregate"]
    assert agg["deep_degrade_rate"] is None
    assert agg["deep_degrade_count"] == 0


def test_degrade_note_predicates_share_one_membership_check():
    # Refactor guard (P12): scout/deep predicates are spelled once via a shared
    # prefix membership helper, and a None/empty notes string is not degraded.
    from harpyja.eval.runner import _has_degrade_note, _is_deep_degraded, _is_scout_degraded

    assert _is_scout_degraded("scout-degraded:backend-error;x") is True
    assert _is_deep_degraded("deep-degraded:parse-error") is True
    assert _is_scout_degraded("deep-degraded:parse-error") is False
    assert _is_deep_degraded(None) is False
    assert _has_degrade_note("deep-degraded:parse-error", "deep-degraded") is True
    assert _has_degrade_note("", "scout-degraded") is False


def test_runner_degraded_dominated_counts_case_once_when_both_degrade(tmp_path):
    # AC11: a case whose notes carry BOTH scout-degraded and deep-degraded is a
    # single degraded case for degraded_dominated (union, not sum), while the per-tier
    # rates stay separately attributed.
    art = tmp_path / "art"
    art.mkdir()
    stack = _deep_degrade_stack(_UnavailableDeep(_DEEP_PARSE_ERROR), _RaisingScout(), art)
    rep = run_dataset(
        [_point("p1")], Settings(), EvalConfig(degraded_dominated_threshold=0.5),
        repo_path=str(tmp_path / "repo"), stack=stack, mode="deep",
    )
    agg = rep["aggregate"]
    assert agg["scout_degrade_count"] == 1  # attributed separately
    assert agg["deep_degrade_count"] == 1  # attributed separately
    # 1 case, both tiers floored → combined per-case degraded rate = 1/1 = 1.0 > 0.5,
    # counted ONCE (a sum would be 2/1 = 2.0, still > .5, but the count must be 1).
    assert agg["degraded_dominated"] is True


def test_runner_aggregates_fc_citation_shape_counts(tmp_path):
    # AC17 (aggregate): the per-case ScoutTally carrier is summed into the report.
    art = tmp_path / "art"
    art.mkdir()
    scout = _TallyScout([_span("a.py", 1, 2)], ScoutTally(spanned=2, filelevel=1, dropped=3))
    stack = _degrade_stack(scout, art)
    rep = run_dataset(
        [_point()], Settings(), EvalConfig(), repo_path=str(tmp_path / "repo"), stack=stack
    )
    agg = rep["aggregate"]
    assert agg["fc_citation_spanned_count"] == 2
    assert agg["fc_citation_filelevel_count"] == 1
    assert agg["fc_citation_dropped_count"] == 3


def test_runner_retires_recovered_counts_to_zero(tmp_path):
    # Spec 0025 (AC7): suffix recovery is removed, so the recovered_* report fields are
    # RETIRED to always-zero — the runner no longer sources them from the ScoutTally.
    # Even a tally carrying (stale, hypothetical) non-zero recovered counts emits 0,
    # proving the retirement is independent of the tally. The shape-tally fields
    # (spanned/filelevel/dropped) STAY populated (asserted above).
    art = tmp_path / "art"
    art.mkdir()
    scout = _TallyScout(
        [_span("a.py", 1, 2)],
        ScoutTally(spanned=1, recovered_spanned=2, recovered_filelevel=3),
    )
    stack = _degrade_stack(scout, art)
    rep = run_dataset(
        [_point()], Settings(), EvalConfig(), repo_path=str(tmp_path / "repo"), stack=stack
    )
    agg = rep["aggregate"]
    assert agg["fc_citation_recovered_spanned_count"] == 0
    assert agg["fc_citation_recovered_filelevel_count"] == 0


def test_runner_serializes_file_level_citation_lines_as_null(tmp_path):
    # AC19: a file-level cited span serializes start/end as JSON null and the
    # assembled report passes the one loud validator.
    art = tmp_path / "art"
    art.mkdir()
    scout = _TallyScout([CodeSpan("a.py", None, None)], ScoutTally(filelevel=1))
    stack = _degrade_stack(scout, art)
    rep = run_dataset(
        [_point()], Settings(), EvalConfig(), repo_path=str(tmp_path / "repo"), stack=stack
    )
    validate_report(rep)
    cited = rep["cases"][0]["citations"]
    assert cited and cited[0]["start_line"] is None and cited[0]["end_line"] is None


# --- spec 0027 (AC4): per-cause scout-degrade counts (cause taxonomy, not turns_used) ---


class _RaisingScoutCause:
    def __init__(self, cause):
        self._cause = cause

    def search(self, query, scope=None):
        raise ScoutUnavailable(self._cause)


class _EmptyScout:
    def search(self, query, scope=None):
        return []  # honest-empty — NOT a degrade (no scout-degraded note)


def test_scout_degrade_cause_extracts_the_typed_cause():
    from harpyja.eval.runner import _scout_degrade_cause

    assert (
        _scout_degrade_cause("scout-degraded:loop-wallclock-exhausted")
        == "loop-wallclock-exhausted"
    )
    # tolerant of the +no-matches suffix and trailing notes
    assert (
        _scout_degrade_cause("scout-degraded:model-unreachable+no-matches")
        == "model-unreachable"
    )
    assert _scout_degrade_cause("scout-degraded:backend-error;x") == "backend-error"
    assert _scout_degrade_cause("deep-degraded:parse-error") is None
    assert _scout_degrade_cause(None) is None


def test_aggregate_reports_per_cause_scout_degrade_counts(tmp_path):
    art = tmp_path / "art"
    art.mkdir()
    stack = _degrade_stack(_RaisingScoutCause(_scout_errors.LOOP_WALLCLOCK_EXHAUSTED), art)
    rep = run_dataset(
        [_point("p1"), _point("p2")], Settings(), EvalConfig(),
        repo_path=str(tmp_path / "repo"), stack=stack,
    )
    agg = rep["aggregate"]
    assert agg["scout_degrade_loop_wallclock_exhausted_count"] == 2
    assert agg["scout_degrade_model_unreachable_count"] == 0
    assert agg["scout_degrade_backend_error_count"] == 0
    assert agg["scout_degrade_loop_turns_exhausted_count"] == 0
    # per-cause counts sum consistently with the retained collapsed count.
    assert agg["scout_degrade_count"] == 2


def test_per_cause_distinguishes_wallclock_from_honest_empty(tmp_path):
    # honest-empty (scout returns []) → NO degrade, zero everywhere.
    a1 = tmp_path / "a1"
    a1.mkdir()
    rep_e = run_dataset(
        [_point("p1")], Settings(), EvalConfig(),
        repo_path=str(tmp_path / "r1"), stack=_degrade_stack(_EmptyScout(), a1),
    )
    assert rep_e["aggregate"]["scout_degrade_count"] == 0
    assert rep_e["aggregate"]["scout_degrade_loop_wallclock_exhausted_count"] == 0
    # wallclock-exhaustion degrade → a DISTINCT bucket (discriminant is the cause,
    # not turns_used, which would be a sub-cap int indistinguishable from honest-empty).
    a2 = tmp_path / "a2"
    a2.mkdir()
    rep_w = run_dataset(
        [_point("p1")], Settings(), EvalConfig(),
        repo_path=str(tmp_path / "r2"),
        stack=_degrade_stack(_RaisingScoutCause(_scout_errors.LOOP_WALLCLOCK_EXHAUSTED), a2),
    )
    assert rep_w["aggregate"]["scout_degrade_loop_wallclock_exhausted_count"] == 1


def test_generation_truncated_note_increments_distinct_count(tmp_path):
    # spec 0028 AC3: a `scout-degraded:generation-truncated` note is counted in its
    # OWN additive field, distinct from model-unreachable and the loop-exhaustion causes.
    art = tmp_path / "art"
    art.mkdir()
    stack = _degrade_stack(_RaisingScoutCause(_scout_errors.GENERATION_TRUNCATED), art)
    rep = run_dataset(
        [_point("p1"), _point("p2")], Settings(), EvalConfig(),
        repo_path=str(tmp_path / "repo"), stack=stack,
    )
    agg = rep["aggregate"]
    assert agg["scout_degrade_generation_truncated_count"] == 2
    assert agg["scout_degrade_model_unreachable_count"] == 0
    assert agg["scout_degrade_count"] == 2
