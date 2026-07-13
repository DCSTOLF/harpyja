"""Postflight verifier for trajectory-verified live measurement (spec 0031)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from harpyja.eval.report import atomic_write_json
from harpyja.eval.submission_gap import DETECTOR_VERSION as _DETECTOR_VERSION

VERIFIER_SCHEMA_VERSION = "0045/1"

# Spec 0033 (+0034, +0038, +0043, +0044): the version GATE (0026
# DATASET_SCHEMA_VERSION pattern) — a legacy 0031/1 artifact (no citation-count
# fields) still validates; an unknown version fails loud. The 0033/1, 0034/1,
# and 0038/1 additions are all OPTIONAL fields (citations counts;
# per_turn/think_mode; serving_transport), so no legacy artifact is invalidated
# by any bump. The 0043/1 field (submission_outcome) is REQUIRED-present on a
# 0043/1+ artifact (value may be None when no gold was available). The 0044/1
# fields (confidence_fired / triggering signal / firing turn / firing spans)
# are REQUIRED-present on a 0044/1 artifact (False/None on a non-firing run) —
# an attributable null must not be silently omittable from a current artifact.
_KNOWN_VERIFIER_SCHEMA_VERSIONS = frozenset(
    {"0031/1", "0033/1", "0034/1", "0038/1", "0043/1", "0044/1", "0045/1"}
)

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


_SUBMITTED_NOT_CORRECT_BUCKETS = frozenset({"wrong-file", "right-file-wrong-span"})


def classify_silence_to_wrong_confidence(
    terminal_bucket: str | None, fired: bool
) -> bool | None:
    """Spec 0045: the AFTER-side ingredient of silence->wrong-confidence.

    ``True`` iff the gate ``fired`` AND the run submitted a not-correct span
    (bucket in {wrong-file, right-file-wrong-span}). ``None`` when no bucket was
    derivable (no gold). Called with ``fired`` inverted for the record-only
    unfired cross-check. The BEFORE-empty half of the s->wc predicate is joined
    at ledger time (never here — this is the per-cell projection).
    """
    if terminal_bucket is None:
        return None
    return fired and terminal_bucket in _SUBMITTED_NOT_CORRECT_BUCKETS


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

    # Spec 0043: the loss-class field is presence-required on a 0043/1+ artifact
    # (legacy versions predate it and stay valid — additive, never breaking).
    if artifact.get("schema_version") in ("0043/1", "0044/1", "0045/1"):
        required_keys = required_keys | {"submission_outcome"}

    # Spec 0044: the confidence facts are presence-required on a CURRENT
    # artifact — a null must be attributable (never-fired / fired-but-ignored /
    # fired-on-wrong-span), so the firing facts cannot be silently omitted.
    # The record-only observability fields (b)/(c) + the null label ride the
    # WRITTEN artifact only (eval-side postflight) and are presence-required
    # there too, so the next spec's gate choice has its data on every artifact.
    if artifact.get("schema_version") in ("0044/1", "0045/1"):
        required_keys = required_keys | {
            "confidence_fired",
            "confidence_triggering_signal",
            "confidence_firing_turn",
            "confidence_firing_spans",
        }
        if "case" in artifact:
            # A run_verified_case-assembled artifact (never a bare record).
            required_keys = required_keys | {
                "grep_hits_inside_symbol_spans",
                "convergent_evidence",
                "confidence_null",
            }

    # Spec 0045: silence->wrong-confidence is a first-class counted fact,
    # presence-required on a 0045/1 artifact (bare record AND written; value may
    # be None when no gold). The record-only unfired cross-check rides the
    # WRITTEN artifact only (eval-side postflight), presence-required there.
    if artifact.get("schema_version") == "0045/1":
        required_keys = required_keys | {"silence_to_wrong_confidence"}
        if "case" in artifact:
            required_keys = required_keys | {"unfired_silence_to_wrong_confidence"}

    missing = required_keys - set(artifact.keys())
    if missing:
        raise ValueError(f"Artifact missing required keys: {missing}")

    if artifact.get("schema_version") not in _KNOWN_VERIFIER_SCHEMA_VERSIONS:
        raise ValueError(
            f"Unknown schema version: expected one of "
            f"{sorted(_KNOWN_VERIFIER_SCHEMA_VERSIONS)}, "
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
    citations_submitted: int | None = None,
    citations_surviving: int | None = None,
    per_turn: list[dict[str, Any]] | None = None,
    think_mode: str | None = None,
    serving_transport: str | None = None,
    submission_outcome: str | None = None,
    confidence_fired: bool = False,
    confidence_triggering_signal: str | None = None,
    confidence_firing_turn: int | None = None,
    confidence_firing_spans: list[dict[str, Any]] | None = None,
    silence_to_wrong_confidence: bool | None = None,
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
    # Tool names come from the ONE canonical parser (spec 0032): the strict
    # extract_tool_names the verify path uses. A nameless tool_call is a typed
    # failure carried as DATA (tool_names_failure) — never raised, because this
    # builder runs live inside ExplorerBackend's loop; never a silent skip.
    tool_names, _proven, tool_names_failure = extract_tool_names(
        {"model_turns": history}
    )

    record = {
        "schema_version": VERIFIER_SCHEMA_VERSION,
        "model_turns": history,
        "tool_names_invoked": tool_names,
        "tool_names_failure": tool_names_failure,
        "served_model": served_model,
        "endpoint": endpoint,
        "turns_used": turns_used,
        # Spec 0033: the submit-seam counts — found-then-dropped (1, 0) is
        # structurally distinguishable from honest-empty (0, 0).
        "citations_submitted": citations_submitted,
        "citations_surviving": citations_surviving,
        # Spec 0034: per-turn (reasoning_chars, completion_tokens, finish_reason)
        # from the backend accumulator. NOTE the deliberate length SKEW vs
        # model_turns: a finish="length" final turn never enters the history but
        # DOES get a per_turn entry — consumers must not zip the lists positionally.
        "per_turn": per_turn or [],
        "think_mode": think_mode,
        # Spec 0038: the endpoint-mechanism identity the run was served through
        # (e.g. "v1-chat-completions"), so the four-facts invariant is checkable
        # per-transport. Present-and-None when unknown — never fabricated.
        "serving_transport": serving_transport,
        # Spec 0043: the found-but-unsubmitted loss class as data. The builder
        # runs live without gold spans, so the value arrives from the caller
        # (present-and-None when no gold was available — never fabricated);
        # detector_version rides along only when an outcome was computed.
        "submission_outcome": submission_outcome,
        "detector_version": (
            _DETECTOR_VERSION if submission_outcome is not None else None
        ),
        # Spec 0044: the confidence-conditioned nudge facts — whether the
        # evidence gate fired, which signal, on which turn, and the triggering
        # spans (plain dicts). SUT-recorded, gold-blind; the eval-side
        # wrong-span attribution judges the spans against gold postflight.
        "confidence_fired": confidence_fired,
        "confidence_triggering_signal": confidence_triggering_signal,
        "confidence_firing_turn": confidence_firing_turn,
        "confidence_firing_spans": confidence_firing_spans,
        # Spec 0045: the AFTER-side ingredient of silence->wrong-confidence
        # (fired ∧ submitted-but-not-correct). Gold-dependent, so present-and-None
        # on the live builder (the bucket arrives from the verify seam) — mirrors
        # the 0043 submission_outcome threading.
        "silence_to_wrong_confidence": silence_to_wrong_confidence,
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
    requested_model: str,
    tags_payload: dict[str, Any],
    *,
    resolver: Any = None,
) -> None:
    """Pre-flight checks for AC6 live verification.

    Asserts the endpoint is loopback-only, then verifies the requested model
    is present in the /api/tags payload. Raises AirGapError or ValueError on failure.

    Args:
        endpoint: The gateway API base URL
        requested_model: The model name to verify
        tags_payload: The /api/tags response payload
        resolver: Optional hostname resolver (for testing)

    Raises:
        AirGapError: If endpoint is not localhost
        ValueError: If requested model is not in the tags payload
    """
    from harpyja.gateway.gateway import assert_local

    # Air-gap first: assert the endpoint is loopback-only
    assert_local(endpoint, resolver=resolver)

    # Extract served model names from tags payload
    served_models = {m.get("name") for m in (tags_payload or {}).get("models", [])}

    # Check if requested model is present
    if requested_model not in served_models:
        raise ValueError(
            f"Requested model {requested_model!r} not found in served models: "
            f"{sorted(served_models)}"
        )


def probe_reasoning_default(gateway: Any) -> bool:
    """Spec 0034 (AC5 precondition): does THIS served model emit `reasoning` by
    default (no `think` param)?

    One call through the sanctioned gateway seam (air-gap asserted inside
    `complete_with_tools` before any I/O). Instance-relative by design — the
    default-thinking finding is about this endpoint + model, not a universal.
    """
    probe_tools = [{
        "type": "function",
        "function": {"name": "noop", "description": "no-op probe tool",
                     "parameters": {"type": "object", "properties": {}}},
    }]
    resp = gateway.complete_with_tools(
        [{"role": "user", "content": "Reply with the single word: ok"}],
        probe_tools,
        max_tokens=256,
    )
    reasoning = resp.get("reasoning")
    return bool(reasoning)


def run_verified_case(
    case_name: str,
    settings: Any,
    gateway: Any,  # ModelGateway
    gold_span: dict[str, Any],
    out_dir: Path,
    repo_path: str | None = None,
    query: str | None = None,
) -> tuple[VerifierResult, Path]:
    """Run a verified case through the explorer and produce a verifier artifact.

    Constructs an ExplorerBackend, runs the explorer loop, captures the trajectory,
    derives terminal_bucket from gold_span, verifies, and writes the artifact.

    Args:
        case_name: The case identifier (e.g., "astropy__astropy-12907")
        settings: Settings object with lm_model, lm_endpoint, etc.
        gateway: ModelGateway instance
        gold_span: Gold span (dict with file, start_line, end_line)
        out_dir: Output directory for artifact
        repo_path: Worktree path (if None, will be looked up from fixture)
        query: Query text (if None, will be looked up from fixture)

    Returns:
        (VerifierResult, artifact_path) tuple
    """
    from datetime import datetime
    from harpyja.index.manifest import read_manifest
    from harpyja.symbols.engine_identity import engine_identity
    from harpyja.symbols.ripgrep import RipgrepEngine
    from harpyja.symbols.symbols_io import load_symbols_or_none
    from harpyja.scout.explorer_backend import ExplorerBackend
    from harpyja.eval.locate_accuracy import classify_case, normalize_citations
    from harpyja.scout.errors import ScoutUnavailable
    from harpyja.server.types import CodeSpan
    import json

    # Load case data from test fixture if not provided
    if repo_path is None or query is None:
        # Use the test-harness fixture
        from harpyja.eval.test_harness_live import _CASES, _worktree
        if case_name not in _CASES:
            raise ValueError(f"Case {case_name} not in fixture")
        gold_tuple, query_text = _CASES[case_name]
        if query is None:
            query = query_text
        if repo_path is None:
            repo_path = _worktree(case_name)
            if repo_path is None:
                raise ValueError(f"Case {case_name} worktree not found")

    # Build the explorer stack
    art_dir = Path(repo_path) / ".harpyja"
    manifest = read_manifest(art_dir) or []
    symbol_records = load_symbols_or_none(art_dir, engine_identity()) or []

    ripgrep = None
    try:
        from harpyja.symbols.ripgrep import RipgrepEngine
        ripgrep = RipgrepEngine(settings)
    except Exception:
        pass

    backend = ExplorerBackend(
        gateway=gateway,
        repo_path=repo_path,
        settings=settings,
        manifest=manifest,
        search_engine=ripgrep,
        symbol_records=symbol_records,
        max_tokens=settings.explorer_max_tokens,
        enable_thinking=settings.explorer_enable_thinking,
        think=settings.explorer_think,
    )

    # Run the explorer loop. A typed degrade is captured OUTSIDE the except
    # block's variable lifetime (spec 0033) so the no-trajectory raise below can
    # NAME the cause and chain it — never the 0031 cause-less ValueError.
    degrade: ScoutUnavailable | None = None
    try:
        citations = backend.run(query, [])  # empty seed
    except ScoutUnavailable as e:
        # Explorer degraded — record the typed cause; trajectory may still exist.
        citations = []
        degrade = e

    # Capture trajectory
    last_trajectory = backend.last_trajectory
    if last_trajectory is None:
        cause = degrade.cause if degrade is not None else "unknown"
        raise ValueError(
            f"Explorer did not capture trajectory (scout cause: {cause})"
        ) from degrade

    # Derive terminal_bucket from locate_accuracy
    gold_span_obj = CodeSpan(
        path=gold_span.get("file"),
        start_line=gold_span.get("start_line"),
        end_line=gold_span.get("end_line"),
    )
    normalized = normalize_citations(citations, None)
    terminal_bucket, _ = classify_case(
        normalized.effective,
        (gold_span_obj,),
        window=50
    )

    # Build full trajectory for verification
    traj = {
        "schema_version": VERIFIER_SCHEMA_VERSION,
        "requested_model": settings.lm_model,
        "endpoint": settings.lm_api_base,
        "served_model": last_trajectory.get("served_model"),
        "configured_endpoint_models": [settings.lm_model],
        "tiers_run": [0, 1],  # explorer always runs Tier 0+1
        "model_turns": last_trajectory.get("model_turns", []),
        "terminal_bucket": terminal_bucket.value if terminal_bucket else None,
    }

    # Verify the trajectory
    result = verify_trajectory(traj)

    # Spec 0043: type the found-but-unsubmitted loss class from the trajectory
    # + gold via the ONE detector (submission_gap), so the fact is durable in
    # the written artifact — distinct from never-found, countable per run.
    from harpyja.eval.submission_gap import classify_submission

    submission_outcome = classify_submission(
        {
            "model_turns": traj["model_turns"],
            "citations_submitted": last_trajectory.get("citations_submitted"),
            "citations_surviving": last_trajectory.get("citations_surviving"),
        },
        (gold_span_obj,),
    )

    # Spec 0044: the record-only observability fields (b)/(c) and the
    # attributable-null label — EVAL-SIDE POSTFLIGHT over the persisted
    # trajectory (the SUT never sees gold; the gate never sees these).
    from harpyja.eval.submission_observability import (
        classify_confidence_null,
        convergent_evidence,
        grep_hits_inside_symbol_spans,
    )

    confidence_null = classify_confidence_null(
        {
            "confidence_fired": last_trajectory.get("confidence_fired", False),
            "confidence_firing_spans": last_trajectory.get(
                "confidence_firing_spans"
            ),
            "terminal_bucket": traj["terminal_bucket"],
        },
        (gold_span_obj,),
    )

    # Spec 0045: the silence->wrong-confidence fact (AFTER side) + the
    # record-only unfired cross-check, computed from the gold-derived bucket.
    _fired = last_trajectory.get("confidence_fired", False)
    silence_to_wrong_confidence = classify_silence_to_wrong_confidence(
        traj["terminal_bucket"], _fired
    )
    unfired_silence_to_wrong_confidence = classify_silence_to_wrong_confidence(
        traj["terminal_bucket"], not _fired
    )

    # Build and write artifact
    artifact = {
        "schema_version": VERIFIER_SCHEMA_VERSION,
        "requested_model": settings.lm_model,
        "endpoint": settings.lm_api_base,
        "served_model": traj["served_model"],
        "configured_endpoint_models": [settings.lm_model],
        "tiers_run": traj["tiers_run"],
        "model_turns": traj["model_turns"],
        "terminal_bucket": traj["terminal_bucket"],
        "verifier_status": result.status,
        "failure_reason": result.failure_reason,
        # Spec 0033: the submit-seam counts are DURABLE — found-then-dropped
        # (submitted>0, surviving=0) is distinguishable in the persisted artifact.
        "citations_submitted": last_trajectory.get("citations_submitted"),
        "citations_surviving": last_trajectory.get("citations_surviving"),
        # Spec 0034: per-turn reasoning observability — durable in the artifact.
        "per_turn": last_trajectory.get("per_turn", []),
        "think_mode": last_trajectory.get("think_mode"),
        # Spec 0038: the transport identity the run was served through — durable,
        # so the four-facts invariant is checkable per-transport.
        "serving_transport": last_trajectory.get("serving_transport"),
        # Spec 0043: the loss class as data in the SECOND (hand-assembled) seam
        # — the 0033/0034/0038 dual-seam rule, written-JSON test-pinned.
        "submission_outcome": submission_outcome.value,
        "detector_version": _DETECTOR_VERSION,
        # Spec 0044: the confidence facts in the SECOND seam too (the dual-seam
        # checklist's 4th application, written-JSON test-pinned).
        "confidence_fired": last_trajectory.get("confidence_fired", False),
        "confidence_triggering_signal": last_trajectory.get(
            "confidence_triggering_signal"
        ),
        "confidence_firing_turn": last_trajectory.get("confidence_firing_turn"),
        "confidence_firing_spans": last_trajectory.get("confidence_firing_spans"),
        # Spec 0044: the record-only fields (b)/(c) + the attributable null —
        # eval-side postflight, never gating, durable for the next spec's
        # gate choice.
        "grep_hits_inside_symbol_spans": grep_hits_inside_symbol_spans(
            {"model_turns": traj["model_turns"]}
        ),
        "convergent_evidence": convergent_evidence(
            {"model_turns": traj["model_turns"]}
        ),
        "confidence_null": confidence_null,
        # Spec 0045: silence->wrong-confidence in the SECOND seam too (the
        # dual-seam checklist's 5th application, written-JSON test-pinned) + the
        # record-only unfired cross-check (the fired-conditioning loophole).
        "silence_to_wrong_confidence": silence_to_wrong_confidence,
        "unfired_silence_to_wrong_confidence": unfired_silence_to_wrong_confidence,
        "timestamp": datetime.utcnow().isoformat(),
        "case": case_name,
    }

    out_path = (out_dir / f"{case_name}_verifier_artifact.json").resolve()
    write_verifier_artifact(artifact, out_path, repo_path)

    return result, out_path
