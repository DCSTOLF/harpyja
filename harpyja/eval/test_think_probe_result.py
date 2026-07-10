"""Spec 0037 — probe-result contract: the typed think-probe outcome is pinned.

The probe (specs/0037-explorer-think-knob/probes/run_probes.sh) answers ONE
question — which request param actually toggles thinking on this Ollama /v1
path — and its answer is a TYPED outcome committed as probes/probe_result.json.
These tests pin the outcome space (total, per the 0023 named-outcome
discipline), the validator's loud reject path, and the committed evidence file
itself, so the claimed outcome can never drift from the recorded evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harpyja.eval.think_probe import (
    PROBE_OUTCOMES,
    PROBE_RESULT_SCHEMA_VERSION,
    ProbeResultError,
    load_probe_result,
    validate_probe_result,
)

_HARPYJA_ROOT = Path(__file__).resolve().parents[2]
COMMITTED_PROBE_RESULT = (
    _HARPYJA_ROOT / "specs" / ".archive" / "0037-explorer-think-knob"
    / "probes" / "probe_result.json"
)

_ARM_KEYS = {"completion_tokens", "finish_reason", "content_present", "think_in_content"}
_ARMS = {"think_true", "think_false", "omitted"}


def _valid_result() -> dict:
    arm = {
        "completion_tokens": 20,
        "finish_reason": "length",
        "content_present": False,
        "think_in_content": False,
    }
    return {
        "schema_version": PROBE_RESULT_SCHEMA_VERSION,
        "model": "qwen3:14b",
        "endpoint": "http://localhost:11434/v1/chat/completions",
        "outcome": "native-think-effective",
        "arms": {name: dict(arm) for name in _ARMS},
    }


def test_probe_outcomes_are_the_three_typed_values() -> None:
    """The outcome space is TOTAL: exactly the three typed values, nothing else."""
    assert PROBE_OUTCOMES == frozenset(
        {"native-think-effective", "chat-template-effective", "no-op"}
    )


def test_validate_probe_result_accepts_a_conforming_result() -> None:
    validate_probe_result(_valid_result())


def test_validate_probe_result_rejects_unknown_outcome() -> None:
    bad = _valid_result()
    bad["outcome"] = "thinking-off"
    with pytest.raises(ProbeResultError):
        validate_probe_result(bad)


def test_validate_probe_result_rejects_missing_arm_block() -> None:
    bad = _valid_result()
    del bad["arms"]["think_false"]
    with pytest.raises(ProbeResultError):
        validate_probe_result(bad)


def test_validate_probe_result_rejects_missing_arm_key() -> None:
    bad = _valid_result()
    del bad["arms"]["think_true"]["completion_tokens"]
    with pytest.raises(ProbeResultError):
        validate_probe_result(bad)


def test_validate_probe_result_rejects_unknown_schema_version() -> None:
    bad = _valid_result()
    bad["schema_version"] = "9999/1"
    with pytest.raises(ProbeResultError):
        validate_probe_result(bad)


def test_committed_probe_result_loads_and_validates() -> None:
    """The COMMITTED evidence file exists and carries the claimed typed outcome.

    This is the drift-pin: the spec's claim about which param toggles thinking
    cannot exist without the recorded probe evidence backing it.
    """
    result = load_probe_result(COMMITTED_PROBE_RESULT)
    assert result["schema_version"] == PROBE_RESULT_SCHEMA_VERSION
    assert result["model"] == "qwen3:14b"
    endpoint = result["endpoint"]
    assert endpoint.startswith(("http://localhost", "http://127.0.0.1"))
    assert "/v1/" in endpoint
    assert result["outcome"] in PROBE_OUTCOMES
    assert set(result["arms"]) == _ARMS
    for arm in result["arms"].values():
        assert _ARM_KEYS <= set(arm)


def test_load_probe_result_rejects_invalid_json_shape(tmp_path: Path) -> None:
    p = tmp_path / "probe_result.json"
    p.write_text(json.dumps({"outcome": "no-op"}), encoding="utf-8")
    with pytest.raises(ProbeResultError):
        load_probe_result(p)
