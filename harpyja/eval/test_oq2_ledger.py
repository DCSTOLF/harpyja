"""Spec 0020 (T5, AC2) — the gate-ledger: a NEW pinned artifact (`0020/1`).

Distinct from the sweep report `0014/1`. Records each gate's verdict + measured
sub-values + close/hold cause + the G3 label with all D/G/S booleans + run
provenance, written outside any target repo via the shared `atomic_write_json`.
"""

from __future__ import annotations

import json

import pytest

from harpyja.eval.oq2_classify import GATE_CONFOUNDED, RECOMMENDATION, G3Classification
from harpyja.eval.oq2_ledger import (
    LEDGER_SCHEMA_VERSION,
    LedgerSchemaError,
    build_gate_ledger,
    validate_gate_ledger,
    write_gate_ledger,
)


def _provenance():
    return {
        "sut_git_sha": "deadbeef",
        "eval_config": {"k_runs": 5, "n_floor": 30, "gate_false_escalation_ceiling": 0.20},
        "fixture_subset_id": "swebench-verified-n12",
        "model_tags": ["hf.co/dstolf/FastContext-1.0-4B-RL-Q8_0-GGUF:latest", "qwen3-coder:30b"],
        "grid": {"thresholds": [0.5, 0.6, 0.7], "top_ns": [1, 3, 5]},
    }


def _g3(label=RECOMMENDATION, *, no_survivor=False, indicative_only=True):
    return G3Classification(
        label=label,
        degraded_dominated=False,
        gate_confounded=label == GATE_CONFOUNDED,
        no_survivor=no_survivor,
        indicative_only=indicative_only,
    )


def _gates():
    return [
        {"gate": "G0", "status": "pass", "pulled": ["a", "b"]},
        {"gate": "G1", "status": "pass",
         "subchecks": {"completed": True, "degrade_dominant": False, "false_rejected": False}},
        {"gate": "G2", "status": "pass",
         "gate_false_escalation_instruct": 0.10, "gate_false_escalation_scout": 0.25,
         "catch_rate": 0.92},
        {"gate": "G3", "status": "complete", "label": RECOMMENDATION},
    ]


def test_gate_ledger_schema_version_is_0020_1():
    from harpyja.eval.report import SCHEMA_VERSION as REPORT_VERSION

    assert LEDGER_SCHEMA_VERSION == "0020/1"
    assert LEDGER_SCHEMA_VERSION != REPORT_VERSION  # a distinct artifact, not the report


def test_build_gate_ledger_has_all_gate_and_provenance_fields():
    led = build_gate_ledger(
        disposition="close", outcome=RECOMMENDATION,
        gates=_gates(), g3=_g3(), provenance=_provenance(),
    )
    validate_gate_ledger(led)  # must not raise
    assert led["ledger_version"] == "0020/1"
    assert led["disposition"] == "close"
    assert led["outcome"] == RECOMMENDATION
    # per-gate measured values are carried through
    assert led["gates"][2]["gate_false_escalation_instruct"] == 0.10
    assert led["gates"][2]["gate_false_escalation_scout"] == 0.25
    # g3 block: label + all booleans
    assert led["g3"]["label"] == RECOMMENDATION
    assert led["g3"]["no_survivor"] is False
    assert led["g3"]["indicative_only"] is True
    # provenance: all five fields
    for f in ("sut_git_sha", "eval_config", "fixture_subset_id", "model_tags", "grid"):
        assert f in led["provenance"]


def test_validate_gate_ledger_loud_on_missing_field():
    led = build_gate_ledger(
        disposition="close", outcome=RECOMMENDATION,
        gates=_gates(), g3=_g3(), provenance=_provenance(),
    )
    del led["provenance"]["sut_git_sha"]
    with pytest.raises(LedgerSchemaError):
        validate_gate_ledger(led)


def test_validate_gate_ledger_loud_on_wrong_version():
    led = build_gate_ledger(
        disposition="close", outcome=RECOMMENDATION,
        gates=_gates(), g3=_g3(), provenance=_provenance(),
    )
    led["ledger_version"] = "9999/9"
    with pytest.raises(LedgerSchemaError):
        validate_gate_ledger(led)


def test_validate_gate_ledger_g3_booleans_optional_under_gate_confound():
    # Under GATE_CONFOUNDED, no_survivor is recorded n/a (None) — validation still passes
    # (guards the phantom-NOT_SEPARABLE avoidance at the schema layer).
    led = build_gate_ledger(
        disposition="close", outcome=GATE_CONFOUNDED,
        gates=[{"gate": "G0", "status": "pass"},
               {"gate": "G3", "status": "complete", "label": GATE_CONFOUNDED}],
        g3=G3Classification(
            label=GATE_CONFOUNDED, degraded_dominated=False, gate_confounded=True,
            no_survivor=None, indicative_only=False,
        ),
        provenance=_provenance(),
    )
    validate_gate_ledger(led)
    assert led["g3"]["no_survivor"] is None


def test_validate_gate_ledger_accepts_null_g3_for_early_stop():
    # A G0 BLOCKED or STOP:SMOKE never reaches G3 -> g3 is None, ledger still valid.
    led = build_gate_ledger(
        disposition="hold", outcome="BLOCKED",
        gates=[{"gate": "G0", "status": "blocked", "missing_tag": "qwen3-coder:30b"}],
        g3=None, provenance=_provenance(),
    )
    validate_gate_ledger(led)
    assert led["g3"] is None


def test_validate_gate_ledger_loud_on_gate_missing_status():
    led = build_gate_ledger(
        disposition="hold", outcome="BLOCKED",
        gates=[{"gate": "G0"}], g3=None, provenance=_provenance(),
    )
    with pytest.raises(LedgerSchemaError):
        validate_gate_ledger(led)


def test_write_gate_ledger_refuses_inside_repo(tmp_path):
    led = build_gate_ledger(
        disposition="close", outcome=RECOMMENDATION,
        gates=_gates(), g3=_g3(), provenance=_provenance(),
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(ValueError, match="inside the indexed repo"):
        write_gate_ledger(led, out_dir=repo / "sub", repo_path=repo)


def test_write_gate_ledger_writes_valid_json_outside_repo(tmp_path):
    led = build_gate_ledger(
        disposition="close", outcome=RECOMMENDATION,
        gates=_gates(), g3=_g3(), provenance=_provenance(),
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    out = tmp_path / "artifacts"
    path = write_gate_ledger(led, out_dir=out, repo_path=repo)
    assert path.name == "gate_ledger.json"
    loaded = json.loads(path.read_text())
    validate_gate_ledger(loaded)
    assert loaded["ledger_version"] == "0020/1"
