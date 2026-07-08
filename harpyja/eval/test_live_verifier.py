"""Tests for trajectory-verified live measurement verifier (spec 0031)."""

import pytest
import tempfile
import os
from pathlib import Path

from harpyja.eval.live_verifier import (
    VERIFIER_SCHEMA_VERSION,
    FAILURE_CODES,
    validate_verifier_artifact,
    write_verifier_artifact,
    verify_trajectory,
    VerifierResult,
    verifier_preflight,
)
from harpyja.gateway.gateway import AirGapError


def test_verifier_artifact_schema_is_version_stamped_and_validated():
    """Artifact is version-stamped and validates against required keys."""
    # Complete, valid artifact
    artifact = {
        "schema_version": VERIFIER_SCHEMA_VERSION,
        "requested_model": "qwen3:14b",
        "endpoint": "http://localhost:11434",
        "served_model": "qwen3:14b",
        "configured_endpoint_models": ["qwen3:14b", "qwen3:4b"],
        "tiers_run": [0, 1],
        "model_turns": [],
        "terminal_bucket": "correct",
        "verifier_status": "PASSED",
        "failure_reason": None,
    }

    # Should pass validation
    validate_verifier_artifact(artifact)

    # Dropping any required key should fail
    for key in ["schema_version", "verifier_status"]:
        bad_artifact = {k: v for k, v in artifact.items() if k != key}
        with pytest.raises(ValueError):
            validate_verifier_artifact(bad_artifact)

    # schema_version should equal VERIFIER_SCHEMA_VERSION
    assert artifact["schema_version"] == VERIFIER_SCHEMA_VERSION


def test_verifier_artifact_writes_outside_repo_atomically():
    """Artifact writes outside repo; raises if out-dir is inside repo_path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write outside repo should succeed
        artifact = {
            "schema_version": VERIFIER_SCHEMA_VERSION,
            "requested_model": "test-model",
            "endpoint": "http://localhost:11434",
            "served_model": "test-model",
            "configured_endpoint_models": ["test-model"],
            "tiers_run": [1],
            "model_turns": [],
            "terminal_bucket": "correct",
            "verifier_status": "PASSED",
            "failure_reason": None,
        }
        repo_path = "/Users/daniel.stolf/development/harpyja"
        out_path = Path(tmpdir) / "artifact.json"

        # Should succeed with outside path
        write_verifier_artifact(artifact, out_path, repo_path)
        assert out_path.exists()

        # Should raise if out-dir is inside repo
        bad_out_path = Path(repo_path) / ".harpyja" / "artifact.json"
        with pytest.raises(ValueError):
            write_verifier_artifact(artifact, bad_out_path, repo_path)


def _traj(**overrides) -> dict:
    """Build a complete, valid trajectory fixture."""
    trajectory = {
        "schema_version": VERIFIER_SCHEMA_VERSION,
        "requested_model": "qwen3:14b",
        "endpoint": "http://localhost:11434",
        "served_model": "qwen3:14b",
        "configured_endpoint_models": ["qwen3:14b", "qwen3:4b"],
        "tiers_run": [0, 1],
        "model_turns": [
            {
                "role": "assistant",
                "content": "I'll help you search for that.",
                "tool_calls": [{"function": {"name": "grep"}}],
            },
            {
                "role": "assistant",
                "content": "Found the symbol.",
                "tool_calls": [{"function": {"name": "symbols"}}],
            },
        ],
        "terminal_bucket": "correct",
    }
    trajectory.update(overrides)
    return trajectory


def test_verify_extracts_four_facts_from_valid_trajectory():
    """Complete valid trajectory passes verification with all four facts populated."""
    traj = _traj()
    result = verify_trajectory(traj)

    assert result.status == "PASSED"
    assert result.failure_reason is None
    assert result.model_identity is not None
    assert result.model_invoked is not None
    assert result.tool_names_invoked is not None
    assert result.terminal_bucket is not None


def test_verify_missing_required_field_fails_artifact_incomplete():
    """Dropping a required top-level field triggers artifact-incomplete failure."""
    traj = _traj()
    del traj["model_turns"]  # Remove a required field
    result = verify_trajectory(traj)

    assert result.status == "FAILED"
    assert result.failure_reason == "artifact-incomplete"


def test_verify_model_identity_matching_passes():
    """served_model == requested_model proves identity."""
    traj = _traj(served_model="qwen3:14b", requested_model="qwen3:14b")
    result = verify_trajectory(traj)

    assert result.status == "PASSED"
    assert result.model_identity is not None


def test_verify_model_identity_mismatch_fails_model_mismatch():
    """served_model != requested_model fails with model-mismatch."""
    traj = _traj(served_model="qwen3:4b", requested_model="qwen3:14b")
    result = verify_trajectory(traj)

    assert result.status == "FAILED"
    assert result.failure_reason == "model-mismatch"


def test_verify_model_identity_absent_resolves_via_configured_fallback():
    """served_model absent but requested in configured list passes via fallback."""
    traj = _traj(
        served_model=None,
        requested_model="qwen3:14b",
        configured_endpoint_models=["qwen3:14b", "qwen3:4b"],
    )
    result = verify_trajectory(traj)

    assert result.status == "PASSED"
    assert result.model_identity is not None
    # Details should record the fallback source
    assert result.details is not None
    assert "fallback" in str(result.details).lower() or "configured" in str(result.details).lower()


def test_verify_model_identity_absent_and_unlisted_fails_model_unknown():
    """served_model absent and requested not in configured list fails model-unknown."""
    # Case 1: empty configured list
    traj = _traj(
        served_model=None,
        requested_model="qwen3:14b",
        configured_endpoint_models=[],
    )
    result = verify_trajectory(traj)

    assert result.status == "FAILED"
    assert result.failure_reason == "model-unknown"

    # Case 2: requested not in configured list
    traj = _traj(
        served_model=None,
        requested_model="llama:70b",
        configured_endpoint_models=["qwen3:14b", "qwen3:4b"],
    )
    result = verify_trajectory(traj)

    assert result.status == "FAILED"
    assert result.failure_reason == "model-unknown"


def test_verify_model_invoked_tier0_only_fails_model_not_invoked():
    """Tier-0 only (no Tier-1) with empty model_turns fails model-not-invoked."""
    traj = _traj(tiers_run=[0], model_turns=[])
    result = verify_trajectory(traj)

    assert result.status == "FAILED"
    assert result.failure_reason == "model-not-invoked"


def test_verify_model_invoked_requires_tier1_and_a_model_turn():
    """Tier-1 claimed but no model_turns still fails model-not-invoked."""
    traj = _traj(tiers_run=[0, 1], model_turns=[])
    result = verify_trajectory(traj)

    assert result.status == "FAILED"
    assert result.failure_reason == "model-not-invoked"


def test_verify_tool_names_lists_invoked_tools_by_name():
    """Tool names are extracted in order-unique from model_turns."""
    traj = _traj(
        model_turns=[
            {
                "role": "assistant",
                "content": "Searching...",
                "tool_calls": [{"function": {"name": "grep"}}],
            },
            {
                "role": "assistant",
                "content": "Found the symbol.",
                "tool_calls": [{"function": {"name": "symbols"}}],
            },
        ]
    )
    result = verify_trajectory(traj)

    assert result.status == "PASSED"
    assert result.tool_names_invoked == ["grep", "symbols"]


def test_verify_symbols_present_vs_absent_is_distinguishable():
    """Symbols presence/absence is clearly distinguished in results."""
    # Traj with symbols
    traj_with_symbols = _traj(
        model_turns=[
            {
                "role": "assistant",
                "content": "Using symbols tool.",
                "tool_calls": [{"function": {"name": "symbols"}}],
            },
        ]
    )
    result_with = verify_trajectory(traj_with_symbols)

    # Traj without symbols
    traj_without_symbols = _traj(
        model_turns=[
            {
                "role": "assistant",
                "content": "Using grep.",
                "tool_calls": [{"function": {"name": "grep"}}],
            },
        ]
    )
    result_without = verify_trajectory(traj_without_symbols)

    assert result_with.status == "PASSED"
    assert result_without.status == "PASSED"
    assert "symbols" in result_with.tool_names_invoked
    assert "symbols" not in result_without.tool_names_invoked


def test_verify_tool_calls_without_names_fail_tool_names_unextractable():
    """Tool calls lacking function.name cause tool-names-unextractable failure."""
    traj = _traj(
        model_turns=[
            {
                "role": "assistant",
                "content": "Invalid call.",
                "tool_calls": [{"function": {}}],  # No 'name' key
            },
        ]
    )
    result = verify_trajectory(traj)

    assert result.status == "FAILED"
    assert result.failure_reason == "tool-names-unextractable"


def test_verify_terminal_bucket_present_passes():
    """terminal_bucket present with valid value carries through to result."""
    for bucket_value in ["correct", "right-file-wrong-span", "wrong-file", "empty"]:
        traj = _traj(terminal_bucket=bucket_value)
        result = verify_trajectory(traj)

        assert result.status == "PASSED"
        assert result.terminal_bucket == bucket_value


def test_verify_terminal_bucket_missing_fails_terminal_bucket_missing():
    """terminal_bucket absent or None triggers terminal-bucket-missing failure."""
    # Case 1: absent
    traj = _traj()
    del traj["terminal_bucket"]
    result = verify_trajectory(traj)

    assert result.status == "FAILED"
    assert result.failure_reason == "terminal-bucket-missing"

    # Case 2: None
    traj = _traj(terminal_bucket=None)
    result = verify_trajectory(traj)

    assert result.status == "FAILED"
    assert result.failure_reason == "terminal-bucket-missing"


def test_verify_status_is_exactly_passed_or_failed():
    """Status is exactly PASSED or FAILED; failure_reason is consistent."""
    # PASSED case
    traj = _traj()
    result = verify_trajectory(traj)

    assert result.status in {"PASSED", "FAILED"}
    assert result.status == "PASSED"
    assert result.failure_reason is None

    # FAILED case
    traj = _traj(served_model="wrong", requested_model="qwen3:14b")
    result = verify_trajectory(traj)

    assert result.status == "FAILED"
    assert result.failure_reason is not None
    assert result.failure_reason in FAILURE_CODES


def test_verify_failure_precedence_is_deterministic():
    """Precedence is deterministic: artifact-incomplete wins over other failures."""
    # Scenario: missing required field + also model mismatch
    # Should fail with artifact-incomplete (higher precedence)
    traj = _traj(served_model="wrong", requested_model="qwen3:14b")
    del traj["model_turns"]  # Missing required field
    result = verify_trajectory(traj)

    assert result.status == "FAILED"
    assert result.failure_reason == "artifact-incomplete"  # Not model-mismatch


@pytest.mark.parametrize("failure_code", sorted(FAILURE_CODES))
def test_verify_all_six_failure_codes_reachable(failure_code):
    """Each of the six failure codes is reachable by some fixture."""
    fixtures = {
        "artifact-incomplete": lambda: (
            _traj(),
            lambda t: t.pop("model_turns", None),  # Remove required field
        ),
        "model-unknown": lambda: (
            _traj(served_model=None, configured_endpoint_models=[]),
            lambda t: None,  # No modification needed
        ),
        "model-mismatch": lambda: (
            _traj(served_model="wrong", requested_model="qwen3:14b"),
            lambda t: None,
        ),
        "model-not-invoked": lambda: (
            _traj(tiers_run=[0], model_turns=[]),
            lambda t: None,
        ),
        "tool-names-unextractable": lambda: (
            _traj(
                model_turns=[
                    {
                        "role": "assistant",
                        "content": "Bad call.",
                        "tool_calls": [{"function": {}}],  # Missing 'name'
                    },
                ]
            ),
            lambda t: None,
        ),
        "terminal-bucket-missing": lambda: (
            _traj(terminal_bucket=None),
            lambda t: None,
        ),
    }

    traj_builder, modifier = fixtures[failure_code]()
    traj = traj_builder
    modifier(traj)
    result = verify_trajectory(traj)

    assert result.status == "FAILED"
    assert result.failure_reason == failure_code, (
        f"Expected {failure_code} but got {result.failure_reason}"
    )


# --- Spec 0031 (live): Verifier preflight (T21/T22, AC6) ---


def test_verifier_preflight_passes_when_model_present():
    """verifier_preflight passes when model is in /api/tags payload."""
    endpoint = "http://127.0.0.1:11434/v1"
    requested_model = "qwen3:14b"
    tags_payload = {
        "models": [
            {"name": "qwen3:14b"},
            {"name": "qwen3:4b"},
        ]
    }

    # Should not raise
    verifier_preflight(endpoint, requested_model, tags_payload)


def test_verifier_preflight_fails_when_model_absent():
    """verifier_preflight raises PreflightError when model not in tags."""
    endpoint = "http://127.0.0.1:11434/v1"
    requested_model = "llama:70b"
    tags_payload = {
        "models": [
            {"name": "qwen3:14b"},
            {"name": "qwen3:4b"},
        ]
    }

    with pytest.raises(ValueError) as exc_info:
        verifier_preflight(endpoint, requested_model, tags_payload)
    assert "llama:70b" in str(exc_info.value) or "missing" in str(exc_info.value).lower()


def test_verifier_preflight_rejects_non_localhost_endpoint():
    """verifier_preflight rejects non-localhost endpoints before probing."""
    endpoint = "http://8.8.8.8:11434/v1"
    requested_model = "qwen3:14b"
    tags_payload = {"models": [{"name": "qwen3:14b"}]}

    with pytest.raises(AirGapError):
        verifier_preflight(endpoint, requested_model, tags_payload)
