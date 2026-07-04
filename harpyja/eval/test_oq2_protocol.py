"""Spec 0020 — the sequential G0→G1→G2→G3 stop-and-report protocol driver.

Fully unit-testable with injected fakes (no live models). Covers: G0 preflight
stop-before-provision (AC1/AC3), G1 three sub-checks classed by cause (AC4/AC12),
G2 first-class metrics + A/B + over-ceiling-no-abort (AC5), G3 → classify +
descriptive-only-under-confound (AC9/AC11), end-to-end ledger + verdict-before-
next-gate ordering (AC1/AC2/AC12), and the no-default-flip guard (AC10).
"""

from __future__ import annotations

from harpyja.config.settings import Settings
from harpyja.eval.config import EvalConfig
from harpyja.eval.oq2_classify import (
    DEGRADED_DOMINATED,
    GATE_CONFOUNDED,
    NOT_SEPARABLE,
    RECOMMENDATION,
)
from harpyja.eval.oq2_ledger import LEDGER_SCHEMA_VERSION, validate_gate_ledger
from harpyja.eval.oq2_protocol import (
    G1Result,
    G2Result,
    G3Result,
    ProvisionInfo,
    run_oq2_protocol,
)
from harpyja.eval.recommend import (
    OUTCOME_GATE_CONFOUNDED,
    OUTCOME_RECOMMENDED,
    Recommendation,
)

# ---- fakes ------------------------------------------------------------------

def _settings():
    return Settings()


def _served_payload(settings):
    return {"models": [{"name": settings.scout_model}, {"name": settings.lm_model}]}


def _provenance_base():
    return {
        "sut_git_sha": "deadbeef",
        "model_tags": ["scout", "deep"],
        "grid": {"thresholds": [0.5, 0.6, 0.7], "top_ns": [1, 3, 5]},
    }


def _provision_ok(effective_n=12):
    return lambda: ProvisionInfo(fixture_subset_id="swebench-verified-n12", effective_n=effective_n)


def _rec(*, outcome=OUTCOME_RECOMMENDED, incumbent_validated=False, advantage=True, measured=None):
    return Recommendation(
        verify_threshold=0.7, verify_top_n=3, catch_rate_bar=0.90,
        advantage_exceeds_variance=advantage, incumbent_validated=incumbent_validated,
        rationale="", outcome=outcome, gate_false_escalation_measured=measured,
    )


def _g1_pass():
    return lambda s, c: G1Result(
        completed=True, degrade_dominant=False, correct_citation_false_rejected=False,
        measured={"scout_degrade_rate": 0.0, "deep_degrade_rate": 0.0, "gate_score": 0.85},
    )


def _g2_clean():
    return lambda s, c: G2Result(
        instruct_false_escalation=0.10, finder_false_escalation=0.25, catch_rate=0.92,
    )


def _g3_clean():
    def run_g3(s, c, *, descriptive_only):
        run_g3.descriptive_only = descriptive_only
        return G3Result(
            recommendation=_rec(),
            aggregate={"degraded_dominated": False},
            descriptive={"span_hit_rate_primary": 0.6, "escalation_rate": 0.3},
        )
    run_g3.descriptive_only = None
    return run_g3


def _run(**overrides):
    """Drive the protocol with all-passing fakes unless overridden."""
    settings = overrides.pop("settings", _settings())
    kwargs = dict(
        settings=settings,
        eval_config=EvalConfig(),
        tags_payload=_served_payload(settings),
        provenance_base=_provenance_base(),
        provision=_provision_ok(),
        run_g1=_g1_pass(),
        run_g2=_g2_clean(),
        run_g3=_g3_clean(),
    )
    kwargs.update(overrides)
    return run_oq2_protocol(**kwargs)


# ---- G0 (AC1/AC3) -----------------------------------------------------------

def test_protocol_g0_missing_model_stops_before_provision():
    provision_called = []
    settings = _settings()
    payload = {"models": [{"name": settings.scout_model}]}  # lm_model missing
    res = _run(
        settings=settings, tags_payload=payload,
        provision=lambda: provision_called.append(True),
    )
    assert res.disposition == "hold"
    assert res.outcome == "BLOCKED"
    assert provision_called == []  # stopped BEFORE provisioning
    assert [g.gate for g in res.gates] == ["G0"]
    assert settings.lm_model in res.gates[0].detail["missing"]


def test_protocol_g0_pass_records_verdict_then_enters_g1():
    g1_called = []
    def g1(s, c):
        g1_called.append(True)
        return _g1_pass()(s, c)
    res = _run(run_g1=g1)
    assert g1_called == [True]
    assert res.gates[0].gate == "G0"
    assert res.gates[0].status == "pass"


def test_protocol_fixtures_absent_is_blocked_hold():
    res = _run(provision=lambda: None)  # provision yields no fixtures
    assert res.disposition == "hold"
    assert res.outcome == "BLOCKED"
    assert res.gates[0].gate == "G0"  # G0 passed, provision then blocked


# ---- G1 (AC4/AC12) ----------------------------------------------------------

def test_protocol_g1_environment_noncompletion_is_blocked_hold():
    sweep_called = []
    def g1(s, c):
        return G1Result(completed=False, environment_failure=True)
    def g2(s, c):
        sweep_called.append(True)
    res = _run(run_g1=g1, run_g2=g2)
    assert res.disposition == "hold"
    assert res.outcome == "BLOCKED"
    assert sweep_called == []
    assert res.gates[-1].gate == "G1"
    assert res.gates[-1].detail["cause"] == "environment"


def test_protocol_g1_completed_but_degrade_dominant_is_stop_smoke():
    def g1(s, c):
        return G1Result(completed=True, degrade_dominant=True,
                        measured={"scout_degrade_rate": 0.7})
    res = _run(run_g1=g1)
    assert res.disposition == "close"
    assert res.outcome == "STOP:SMOKE"
    assert res.gates[-1].detail["measured"]["scout_degrade_rate"] == 0.7


def test_protocol_g1_completed_but_false_rejects_citation_is_stop_smoke():
    def g1(s, c):
        return G1Result(completed=True, correct_citation_false_rejected=True,
                        measured={"gate_score": 0.1})
    res = _run(run_g1=g1)
    assert res.disposition == "close"
    assert res.outcome == "STOP:SMOKE"


def test_protocol_g1_all_three_subchecks_pass_enters_g2():
    g2_called = []
    def g2(s, c):
        g2_called.append(True)
        return _g2_clean()(s, c)
    res = _run(run_g2=g2)
    assert g2_called == [True]
    g1_verdict = next(g for g in res.gates if g.gate == "G1")
    assert g1_verdict.status == "pass"


# ---- G2 (AC5) ---------------------------------------------------------------

def test_protocol_g2_captures_false_escalation_and_catch_rate():
    res = _run()
    g2 = next(g for g in res.gates if g.gate == "G2")
    assert g2.detail["gate_false_escalation_instruct"] == 0.10
    assert g2.detail["catch_rate"] == 0.92


def test_protocol_g2_records_instruct_vs_finder_ab_flag():
    # finder (0.05) beats instruct (0.30) -> OQ-A flag set (does not re-decide the judge).
    def g2(s, c):
        return G2Result(instruct_false_escalation=0.30,
                        finder_false_escalation=0.05, catch_rate=0.9)
    res = _run(run_g2=g2, run_g3=_g3_clean())
    g2v = next(g for g in res.gates if g.gate == "G2")
    assert g2v.detail["gate_false_escalation_instruct"] == 0.30
    assert g2v.detail["gate_false_escalation_scout"] == 0.05
    assert g2v.detail["finder_beats_instruct"] is True


def test_protocol_g2_under_ceiling_routes_clean_g3():
    g3 = _g3_clean()
    _run(run_g3=g3)  # instruct 0.10 <= ceiling 0.20
    assert g3.descriptive_only is False  # full sweep, not descriptive-only


def test_protocol_g2_over_ceiling_does_not_abort_routes_descriptive_g3():
    def over(s, c):
        return G2Result(instruct_false_escalation=0.35,
                        finder_false_escalation=0.25, catch_rate=0.9)
    def g3(s, c, *, descriptive_only):
        g3.descriptive_only = descriptive_only
        return G3Result(
            recommendation=_rec(outcome=OUTCOME_GATE_CONFOUNDED, measured=0.35),
            aggregate={"degraded_dominated": False},
            descriptive={"span_hit_rate_primary": 0.5},
        )
    g3.descriptive_only = None
    res = _run(run_g2=over, run_g3=g3)
    assert g3.descriptive_only is True  # routed to descriptive-only, did NOT abort
    assert res.disposition == "close"
    assert res.outcome == GATE_CONFOUNDED


# ---- G3 (AC9/AC11) ----------------------------------------------------------

def test_protocol_g3_clean_runs_full_sweep_then_classifies():
    res = _run()  # clean -> recommended flip, N=12 < n_floor
    assert res.outcome == RECOMMENDATION
    assert res.g3.label == RECOMMENDATION
    assert res.g3.indicative_only is True  # N=12 < 30


def test_protocol_g3_degraded_dominated_typed_null():
    def g3(s, c, *, descriptive_only):
        return G3Result(recommendation=_rec(), aggregate={"degraded_dominated": True})
    res = _run(run_g3=g3)
    assert res.outcome == DEGRADED_DOMINATED
    assert res.g3.degraded_dominated is True


def test_protocol_g3_not_separable_typed_null():
    def g3(s, c, *, descriptive_only):
        return G3Result(
            recommendation=_rec(incumbent_validated=False, advantage=False),
            aggregate={"degraded_dominated": False},
        )
    res = _run(run_g3=g3)
    assert res.outcome == NOT_SEPARABLE
    assert res.g3.no_survivor is True


def test_protocol_g3_never_forces_a_pick_on_typed_null():
    def g3(s, c, *, descriptive_only):
        return G3Result(
            recommendation=_rec(outcome=OUTCOME_GATE_CONFOUNDED, measured=0.4),
            aggregate={"degraded_dominated": False},
        )
    def g2(s, c):
        return G2Result(0.4, 0.3, 0.9)
    res = _run(run_g2=g2, run_g3=g3)
    assert res.outcome == GATE_CONFOUNDED
    assert res.g3.label == GATE_CONFOUNDED  # a typed null, not a manufactured (thr,top_n)


# ---- end-to-end ledger + ordering (AC1/AC2/AC12) ----------------------------

def test_protocol_emits_ledger_version_0020_1():
    res = _run()
    validate_gate_ledger(res.ledger)
    assert res.ledger["ledger_version"] == LEDGER_SCHEMA_VERSION
    assert res.ledger["g3"]["label"] == RECOMMENDATION
    assert res.ledger["provenance"]["fixture_subset_id"] == "swebench-verified-n12"


def test_protocol_records_each_verdict_before_next_gate():
    timeline = []
    def g1(s, c):
        timeline.append("call:g1")
        return _g1_pass()(s, c)
    def g2(s, c):
        timeline.append("call:g2")
        return _g2_clean()(s, c)
    def g3(s, c, *, descriptive_only):
        timeline.append("call:g3")
        return _g3_clean()(s, c, descriptive_only=descriptive_only)
    _run(run_g1=g1, run_g2=g2, run_g3=g3,
         verdict_sink=lambda v: timeline.append(f"verdict:{v.gate}"))
    # each gate's verdict is committed before the next gate's collaborator runs
    assert timeline.index("verdict:G0") < timeline.index("call:g1")
    assert timeline.index("verdict:G1") < timeline.index("call:g2")
    assert timeline.index("verdict:G2") < timeline.index("call:g3")


def test_protocol_g0_blocked_ledger_has_no_g1_g2_g3_verdicts():
    settings = _settings()
    payload = {"models": [{"name": settings.scout_model}]}  # lm_model missing
    res = _run(settings=settings, tags_payload=payload)
    validate_gate_ledger(res.ledger)
    assert res.ledger["g3"] is None
    assert [g["gate"] for g in res.ledger["gates"]] == ["G0"]
    # a hold names the fix (remediation command + the missing tags)
    assert "missing" in res.ledger["gates"][0]
    assert res.ledger["gates"][0]["remediation"]


def test_protocol_g1_stop_smoke_is_a_close_not_a_hold():
    def g1(s, c):
        return G1Result(completed=True, degrade_dominant=True)
    res = _run(run_g1=g1)
    assert res.ledger["disposition"] == "close"
    assert res.ledger["outcome"] == "STOP:SMOKE"


# ---- no-default-flip guard (AC10) — LOCK ------------------------------------

def test_protocol_recommendation_does_not_flip_settings_defaults():
    import dataclasses

    before = {
        f.name: f.default
        for f in dataclasses.fields(Settings)
        if f.name in ("verify_threshold", "verify_top_n", "verify_method")
    }
    res = _run()  # a RECOMMENDATION run
    assert res.outcome == RECOMMENDATION
    after = {
        f.name: f.default
        for f in dataclasses.fields(Settings)
        if f.name in ("verify_threshold", "verify_top_n", "verify_method")
    }
    assert before == after == {
        "verify_threshold": 0.6, "verify_top_n": 3, "verify_method": "instruct_model",
    }


def test_protocol_write_emits_ledger_file(tmp_path):
    import json

    repo = tmp_path / "repo"
    repo.mkdir()
    out = tmp_path / "artifacts"
    res = _run(out_dir=out, repo_path=repo, write=True)
    written = out / "gate_ledger.json"
    assert written.exists()
    validate_gate_ledger(json.loads(written.read_text()))
    assert res.ledger["outcome"] == RECOMMENDATION
