"""Spec 0038 — reconcile-probe result contract: the typed honoring-path outcome is pinned.

The probe (specs/0038-reconciliation/probes/run_probes.sh) answers ONE question
— which transport path genuinely honors the think toggle on this Ollama, by the
two-factor generation test — and its answer is a TYPED outcome committed as
probes/probe_result.json. These tests pin the outcome space (total, per the
0023 named-outcome discipline), the split path-vs-evidence shape (so future
drift can distinguish endpoint failure from adapter failure), the validator's
loud reject path, and the committed evidence file itself, so the claimed
outcome can never drift from the recorded evidence.

Path pin per the evidence-path convention: the canonical target is
specs/.archive/0038-reconciliation/ (pins target the archived location from
authoring); while the spec is live and unarchived, BOTH locations are resolved
explicitly — never a bare specs/0038-reconciliation/ alone.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harpyja.eval.reconcile_probe import (
    RECONCILE_PROBE_OUTCOMES,
    RECONCILE_PROBE_SCHEMA_VERSION,
    ReconcileProbeError,
    load_committed_reconcile_probe_result,
    load_reconcile_probe_result,
    validate_reconcile_probe_result,
)

_ARMS = {"think_true", "think_false", "omitted"}
_ARM_KEYS = {
    "content_present",
    "finish_reason",
    "completion_tokens",
    "reasoning_chars",
    "think_in_content",
}
_MIGRATION_COST_KEYS = {
    "tool_call_id_present",
    "usage_field_name",
    "reasoning_field_name",
}


def _valid_result() -> dict:
    arm = {
        "content_present": True,
        "finish_reason": "stop",
        "completion_tokens": 4,
        "reasoning_chars": 0,
        "think_in_content": False,
    }
    return {
        "schema_version": RECONCILE_PROBE_SCHEMA_VERSION,
        "model": "qwen3:14b",
        "endpoint": "http://localhost:11434/api/chat",
        "chosen_path": "/api/chat",
        "outcome": "native-api-chat",
        "usage_mapping": {"completion_tokens": "eval_count"},
        "migration_cost": {
            "tool_call_id_present": False,
            "usage_field_name": "eval_count",
            "reasoning_field_name": "message.thinking",
        },
        "arms": {name: dict(arm) for name in _ARMS},
    }


def test_reconcile_probe_outcomes_are_the_three_typed_values() -> None:
    """The outcome space is TOTAL: exactly the three typed values, nothing else.

    A new 0038-local set — deliberately NOT a reuse of 0037's mechanism enum:
    0037 answered "which mechanism", this probe answers "which path" plus the
    typed STILL_BLOCKED terminal.
    """
    assert RECONCILE_PROBE_OUTCOMES == frozenset(
        {"native-api-chat", "v1-variant", "still-blocked"}
    )


def test_reconcile_probe_schema_version_is_0038_1() -> None:
    """Own spec-local schema — not 0037/1, not the verifier schema set."""
    assert RECONCILE_PROBE_SCHEMA_VERSION == "0038/1"


def test_validate_reconcile_probe_result_accepts_a_conforming_result() -> None:
    validate_reconcile_probe_result(_valid_result())


def test_validate_rejects_unknown_outcome() -> None:
    bad = _valid_result()
    bad["outcome"] = "no-op"  # a 0037 outcome, not in the 0038 set
    with pytest.raises(ReconcileProbeError):
        validate_reconcile_probe_result(bad)


def test_validate_rejects_missing_usage_mapping() -> None:
    bad = _valid_result()
    del bad["usage_mapping"]
    with pytest.raises(ReconcileProbeError):
        validate_reconcile_probe_result(bad)


def test_validate_rejects_missing_migration_cost() -> None:
    bad = _valid_result()
    del bad["migration_cost"]
    with pytest.raises(ReconcileProbeError):
        validate_reconcile_probe_result(bad)


def test_validate_rejects_missing_migration_cost_key() -> None:
    bad = _valid_result()
    del bad["migration_cost"]["tool_call_id_present"]
    with pytest.raises(ReconcileProbeError):
        validate_reconcile_probe_result(bad)


def test_validate_rejects_missing_chosen_path() -> None:
    bad = _valid_result()
    del bad["chosen_path"]
    with pytest.raises(ReconcileProbeError):
        validate_reconcile_probe_result(bad)


def test_validate_rejects_missing_arm_block() -> None:
    bad = _valid_result()
    del bad["arms"]["think_false"]
    with pytest.raises(ReconcileProbeError):
        validate_reconcile_probe_result(bad)


def test_validate_rejects_missing_arm_key() -> None:
    bad = _valid_result()
    del bad["arms"]["omitted"]["reasoning_chars"]
    with pytest.raises(ReconcileProbeError):
        validate_reconcile_probe_result(bad)


def test_validate_rejects_unknown_schema_version() -> None:
    bad = _valid_result()
    bad["schema_version"] = "0037/1"
    with pytest.raises(ReconcileProbeError):
        validate_reconcile_probe_result(bad)


def test_committed_reconcile_probe_loads_and_validates() -> None:
    """The COMMITTED evidence file exists and carries the claimed typed outcome.

    This is the drift-pin: the spec's claim about which path honors the think
    toggle cannot exist without the recorded probe evidence backing it.
    """
    result = load_committed_reconcile_probe_result()
    assert result["schema_version"] == RECONCILE_PROBE_SCHEMA_VERSION
    assert result["model"] == "qwen3:14b"
    endpoint = result["endpoint"]
    assert endpoint.startswith(("http://localhost", "http://127.0.0.1"))
    assert result["outcome"] in RECONCILE_PROBE_OUTCOMES
    assert result["chosen_path"]
    assert "completion_tokens" in result["usage_mapping"]
    assert _MIGRATION_COST_KEYS <= set(result["migration_cost"])
    assert set(result["arms"]) == _ARMS
    for arm in result["arms"].values():
        assert _ARM_KEYS <= set(arm)


def test_load_reconcile_probe_result_rejects_invalid_json_shape(tmp_path: Path) -> None:
    p = tmp_path / "probe_result.json"
    p.write_text(json.dumps({"outcome": "still-blocked"}), encoding="utf-8")
    with pytest.raises(ReconcileProbeError):
        load_reconcile_probe_result(p)
