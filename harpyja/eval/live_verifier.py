"""Postflight verifier for trajectory-verified live measurement (spec 0031)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from harpyja.eval.report import atomic_write_json

VERIFIER_SCHEMA_VERSION = "0031/1"

# Six enumerated failure reasons (when facts cannot be proven)
FAILURE_CODES = frozenset([
    "model-unknown",
    "model-mismatch",
    "model-not-invoked",
    "tool-names-unextractable",
    "terminal-bucket-missing",
    "artifact-incomplete",
])

# Failure precedence (deterministic order when multiple facts unprovable)
FAILURE_PRECEDENCE = [
    "artifact-incomplete",
    "model-unknown",
    "model-mismatch",
    "model-not-invoked",
    "tool-names-unextractable",
    "terminal-bucket-missing",
]


class VerificationError(Exception):
    """Raised when a measurement cannot be verified."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Verification failed: {reason}")


@dataclass
class VerifierResult:
    """Result of postflight verification."""
    status: str  # "PASSED" or "FAILED"
    failure_reason: str | None  # One of FAILURE_CODES if FAILED, else None
    model_identity: str | None = None
    model_invoked: bool | None = None
    tool_names_invoked: list[str] | None = None
    terminal_bucket: str | None = None
    served_model: str | None = None
    endpoint: str | None = None
    timestamp: str | None = None
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "schema_version": VERIFIER_SCHEMA_VERSION,
            "status": self.status,
            "failure_reason": self.failure_reason,
            "model_identity": self.model_identity,
            "model_invoked": self.model_invoked,
            "tool_names_invoked": self.tool_names_invoked,
            "terminal_bucket": self.terminal_bucket,
            "served_model": self.served_model,
            "endpoint": self.endpoint,
            "timestamp": self.timestamp,
            "verifier_status": self.status,
            "details": self.details or {},
        }


def validate_verifier_artifact(artifact: Mapping[str, Any]) -> None:
    """Validate verifier artifact against schema."""
    required_keys = {
        "schema_version",
        "verifier_status",
        "requested_model",
        "endpoint",
        "tiers_run",
        "model_turns",
    }

    missing = required_keys - set(artifact.keys())
    if missing:
        raise ValueError(f"Artifact missing required keys: {missing}")

    if artifact.get("schema_version") != VERIFIER_SCHEMA_VERSION:
        raise ValueError(
            f"Schema version mismatch: expected {VERIFIER_SCHEMA_VERSION}, "
            f"got {artifact.get('schema_version')}"
        )

    if artifact.get("verifier_status") not in ("PASSED", "FAILED"):
        raise ValueError(
            f"Invalid verifier_status: {artifact.get('verifier_status')}"
        )


def write_verifier_artifact(
    artifact: Mapping[str, Any],
    out_path: str | Path,
    repo_path: str | Path,
) -> Path:
    """Write verifier artifact atomically outside the repo."""
    out_dir = Path(out_path).parent
    return atomic_write_json(
        dict(artifact),
        out_dir=out_dir,
        repo_path=repo_path,
        filename=Path(out_path).name,
    )


def verify_trajectory(trajectory: dict[str, Any]) -> VerifierResult:
    """Verify a captured trajectory against the four facts.

    Checks in precedence order:
    1. artifact-incomplete: required fields missing
    2. model-unknown: model identity not provable (served_model absent, fallback fails)
    3. model-mismatch: served_model present but != requested_model
    4. model-not-invoked: 1 not in tiers_run or no model_turns
    5. tool-names-unextractable: tool_calls present but lacking parseable names
    6. terminal-bucket-missing: terminal_bucket missing or invalid

    Returns PASSED only when all four facts are provable.
    """
    required_keys = {
        "schema_version",
        "requested_model",
        "endpoint",
        "tiers_run",
        "model_turns",
    }

    # Check completeness first
    missing = required_keys - set(trajectory.keys())
    if missing:
        return VerifierResult(
            status="FAILED",
            failure_reason="artifact-incomplete",
            details={"missing_keys": list(missing)},
        )

    # Try to extract each fact, following precedence order
    model_identity, identity_proven, identity_reason = extract_model_identity(trajectory)
    identity_details = {}

    # Record if identity was proven via fallback
    if identity_proven and trajectory.get("served_model") is None:
        identity_details["method"] = "configured_endpoint_models_fallback"
        identity_details["configured_models"] = trajectory.get("configured_endpoint_models", [])
    elif identity_proven and trajectory.get("served_model"):
        identity_details["method"] = "served_model_match"

    if not identity_proven:
        return VerifierResult(
            status="FAILED",
            failure_reason=identity_reason or "model-unknown",
            model_identity=model_identity,
            served_model=trajectory.get("served_model"),
            endpoint=trajectory.get("endpoint"),
            details={"identity_details": identity_reason},
        )

    model_invoked, invoked_proven, invoked_reason = extract_model_invoked(trajectory)
    if not invoked_proven:
        return VerifierResult(
            status="FAILED",
            failure_reason=invoked_reason or "model-not-invoked",
            model_identity=model_identity,
            model_invoked=model_invoked,
            served_model=trajectory.get("served_model"),
            endpoint=trajectory.get("endpoint"),
        )

    tool_names, tools_proven, tools_reason = extract_tool_names(trajectory)
    if not tools_proven:
        return VerifierResult(
            status="FAILED",
            failure_reason=tools_reason or "tool-names-unextractable",
            model_identity=model_identity,
            model_invoked=model_invoked,
            tool_names_invoked=tool_names,
            served_model=trajectory.get("served_model"),
            endpoint=trajectory.get("endpoint"),
        )

    terminal_bucket, bucket_proven, bucket_reason = extract_terminal_bucket(trajectory)
    if not bucket_proven:
        return VerifierResult(
            status="FAILED",
            failure_reason=bucket_reason or "terminal-bucket-missing",
            model_identity=model_identity,
            model_invoked=model_invoked,
            tool_names_invoked=tool_names,
            served_model=trajectory.get("served_model"),
            endpoint=trajectory.get("endpoint"),
        )

    # All facts proven
    return VerifierResult(
        status="PASSED",
        failure_reason=None,
        model_identity=model_identity,
        model_invoked=model_invoked,
        tool_names_invoked=tool_names,
        terminal_bucket=terminal_bucket,
        served_model=trajectory.get("served_model"),
        endpoint=trajectory.get("endpoint"),
        details=identity_details if identity_details else None,
    )


def extract_model_identity(
    trajectory: dict[str, Any],
) -> tuple[str | None, bool, str | None]:
    """Extract model identity fact from trajectory.

    Returns (model_identity_str, is_proven, failure_reason).

    OQ1 three branches:
    (a) served_model present and == requested_model → identity PROVEN
    (b) served_model present and != requested_model → model-mismatch FAILURE
    (c) served_model absent → fallback to configured_endpoint_models:
        - if requested in list → identity PROVEN via fallback
        - if list empty/lacks requested → model-unknown FAILURE
    """
    served_model = trajectory.get("served_model")
    requested_model = trajectory.get("requested_model")
    configured_models = trajectory.get("configured_endpoint_models", [])

    # Branch (a): served present and matches
    if served_model and served_model == requested_model:
        return ("served_present_and_matching", True, None)

    # Branch (b): served present but mismatches
    if served_model and served_model != requested_model:
        return (None, False, "model-mismatch")

    # Branch (c): served absent, try fallback
    if not served_model:
        if requested_model in configured_models:
            return ("fallback_from_configured_list", True, None)
        else:
            return (None, False, "model-unknown")

    return (None, False, "model-unknown")


def extract_model_invoked(trajectory: dict[str, Any]) -> tuple[bool | None, bool, str | None]:
    """Extract model-invoked fact from trajectory.

    Returns (model_invoked_bool, is_proven, failure_reason).

    Proves: 1 in tiers_run AND len(model_turns) >= 1
    This catches Tier-0 short-circuit cases.
    """
    tiers_run = trajectory.get("tiers_run", [])
    model_turns = trajectory.get("model_turns", [])

    if 1 in tiers_run and len(model_turns) >= 1:
        return (True, True, None)
    return (False, False, "model-not-invoked")


def extract_tool_names(trajectory: dict[str, Any]) -> tuple[list[str], bool, str | None]:
    """Extract tool names fact from trajectory.

    Returns (tool_names_list, is_proven, failure_reason).

    Plain name parse: collect ordered-unique function.name from all tool_calls.
    """
    model_turns = trajectory.get("model_turns", [])
    tool_names = []
    seen = set()

    for turn in model_turns:
        tool_calls = turn.get("tool_calls", [])
        for call in tool_calls:
            # Try to extract function.name
            name = call.get("function", {}).get("name")
            if not name:
                # Tool call without parseable name
                return ([], False, "tool-names-unextractable")
            if name not in seen:
                tool_names.append(name)
                seen.add(name)

    return (tool_names, True, None)


def extract_terminal_bucket(trajectory: dict[str, Any]) -> tuple[str | None, bool, str | None]:
    """Extract terminal bucket fact from trajectory.

    Returns (bucket_label, is_proven, failure_reason).

    Minimal: any present terminal_bucket is valid (T12 will validate against LocateBucket).
    """
    bucket = trajectory.get("terminal_bucket")

    if bucket is not None:
        return (bucket, True, None)
    return (None, False, "terminal-bucket-missing")


def build_trajectory_record(
    history: list[dict[str, Any]],
    turns_used: int,
    *,
    served_model: str | None = None,
    endpoint: str | None = None,
    requested_model: str | None = None,
    configured_endpoint_models: list[str] | None = None,
    terminal_bucket: str | None = None,
) -> dict[str, Any]:
    """Build trajectory artifact record from captured explorer loop data.

    This captures the essential trajectory data:
    - model_turns: the conversation history from the loop
    - tool_names_invoked: ordered-unique tool names extracted from tool_calls
    - served_model: the model reported by the endpoint (or None)
    - endpoint: the gateway endpoint URL
    - Plus optional fields for full assembly by the harness

    Args:
        history: The loop's message history (list of turn dicts with tool_calls)
        turns_used: The number of model turns consumed
        served_model: The model name from the gateway response
        endpoint: The gateway endpoint URL
        requested_model: The requested model name (optional, for assembly)
        configured_endpoint_models: List of models available at endpoint (optional)
        terminal_bucket: The outcome classification (optional, from locate_accuracy)

    Returns:
        A partial trajectory dict ready for verification or assembly
    """
    # Extract tool names from history using the shared parser logic
    tool_names = []
    seen = set()

    for turn in history:
        tool_calls = turn.get("tool_calls", [])
        for call in tool_calls:
            name = call.get("function", {}).get("name")
            if name and name not in seen:
                tool_names.append(name)
                seen.add(name)

    record = {
        "schema_version": VERIFIER_SCHEMA_VERSION,
        "model_turns": history,
        "tool_names_invoked": tool_names,
        "served_model": served_model,
        "endpoint": endpoint,
        "turns_used": turns_used,
    }

    # Add optional fields if provided
    if requested_model is not None:
        record["requested_model"] = requested_model
    if configured_endpoint_models is not None:
        record["configured_endpoint_models"] = configured_endpoint_models
    if terminal_bucket is not None:
        record["terminal_bucket"] = terminal_bucket

    return record


def verifier_preflight(
    endpoint: str,
    repo_path: str,
) -> tuple[bool, str]:
    """Pre-flight checks for AC6 live verification.

    Returns (passed, reason) where reason explains any skip/failure.
    """
    raise NotImplementedError("verifier_preflight not yet implemented")
