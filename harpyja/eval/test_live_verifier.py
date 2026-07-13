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
        # Spec 0043: presence-required on a CURRENT artifact (same-change
        # amendment — this fixture tracks VERIFIER_SCHEMA_VERSION).
        "submission_outcome": "never-found",
        # Spec 0044: the confidence facts, presence-required on a CURRENT
        # artifact (same-change amendment — non-firing run shape).
        "confidence_fired": False,
        "confidence_triggering_signal": None,
        "confidence_firing_turn": None,
        "confidence_firing_spans": None,
        # Spec 0045: silence->wrong-confidence, presence-required on a CURRENT
        # artifact (same-change amendment — None on a correct/no-submit run).
        "silence_to_wrong_confidence": None,
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


# --- Spec 0031 (live): Proof of clean execution (AC6) ---


def test_artifact_empty_bucket_not_masked_has_model_turns_and_tier1():
    """Prove empty bucket is honest (not masked error) by checking trajectory evidence.

    To prove a result (empty bucket or otherwise) is not a masked error:
    1. No degradation markers in trajectory
    2. Model made multiple turns (explorer actually ran, not error after turn 1)
    3. Tier 1 is in tiers_run (explorer loop executed)
    4. Terminal turn completes (not cut short)
    """
    from harpyja.eval.live_verifier import build_trajectory_record

    # Simulate a clean run that found no matches (empty bucket) but actually explored
    model_turns = [
        {"role": "user", "content": "find X"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "ls"}}]},
        {"role": "tool", "content": "[...]", "tool_call_id": "call_1"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "grep"}}]},
        {"role": "tool", "content": "[]", "tool_call_id": "call_2"},  # empty grep result
        {"role": "assistant", "content": "Calling submit", "tool_calls": [{"function": {"name": "submit_citations"}}]},
    ]

    traj = {
        "schema_version": VERIFIER_SCHEMA_VERSION,
        "requested_model": "qwen3:14b",
        "endpoint": "http://localhost:11434",
        "served_model": "qwen3:14b",
        "configured_endpoint_models": ["qwen3:14b"],
        "tiers_run": [0, 1],  # Tier 1 (explorer) ran
        "model_turns": model_turns,
        "terminal_bucket": "empty",
    }

    # Verify passes (all facts present)
    result = verify_trajectory(traj)
    assert result.status == "PASSED"

    # Proof it's not masked: check trajectory evidence
    assert 1 in traj["tiers_run"], "Tier 1 must be in tiers_run to prove explorer ran"

    # Count model turns (assistant responses) to prove exploration actually happened
    assistant_turns = [t for t in model_turns if isinstance(t, dict) and t.get("role") == "assistant"]
    assert len(assistant_turns) >= 2, "Must have multiple model turns to prove not a single-turn error"

    # Verify no degradation markers in trajectory
    for turn in model_turns:
        if isinstance(turn, dict) and isinstance(turn.get("content"), str):
            assert "tool-call-degraded" not in turn["content"], "Degradation marker found"

    print("✓ Empty bucket is CLEAN: Tier 1 ran, multiple model turns, no degradations")


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


# --- Spec 0032 (trajectory-parser): dedup pins + divergence closure ---

from harpyja.eval import live_verifier as _lv  # noqa: E402
from harpyja.eval.live_verifier import (  # noqa: E402
    FAILURE_PRECEDENCE,
    build_trajectory_record,
    extract_tool_names,
)


def _multitool_history() -> list[dict]:
    """A well-formed multi-tool history (every name present)."""
    return [
        {"role": "assistant", "content": "",
         "tool_calls": [{"function": {"name": "ls"}}]},
        {"role": "assistant", "content": "",
         "tool_calls": [{"function": {"name": "grep"}},
                        {"function": {"name": "symbols"}}]},
        {"role": "assistant", "content": "",
         "tool_calls": [{"function": {"name": "grep"}},  # repeat → deduped
                        {"function": {"name": "submit_citations"}}]},
    ]


def _nameless_history() -> list[dict]:
    """A history whose tool_call lacks function.name (the T20 divergent input)."""
    return [
        {"role": "assistant", "content": "",
         "tool_calls": [{"function": {"name": "ls"}}]},
        {"role": "assistant", "content": "",
         "tool_calls": [{"function": {}}]},  # nameless
    ]


# T1 — characterization pins (AC3/AC5/AC6): green pre-cutover, must survive it.


def test_build_trajectory_record_valid_multitool_names_preserved():
    """AC3: valid multi-tool history parses to the same ordered-unique name list."""
    record = build_trajectory_record(_multitool_history(), 3)

    assert record["tool_names_invoked"] == ["ls", "grep", "symbols", "submit_citations"]
    # Post-cutover the sentinel is present-and-None on success; pre-cutover the
    # key is absent — .get() pins both as "no failure".
    assert record.get("tool_names_failure") is None


def test_verifier_schema_version_and_failure_codes_frozen():
    """AC5: schema version, the six codes, and their precedence are byte-frozen."""
    # 0031/1 -> ... -> 0044/1 -> 0045/1: spec 0045 additive bump
    # (silence->wrong-confidence), reconciled here (same-change amendment).
    assert VERIFIER_SCHEMA_VERSION == "0045/1"
    assert FAILURE_CODES == frozenset([
        "model-unknown",
        "model-mismatch",
        "model-not-invoked",
        "tool-names-unextractable",
        "terminal-bucket-missing",
        "artifact-incomplete",
    ])
    assert FAILURE_PRECEDENCE == [
        "artifact-incomplete",
        "model-unknown",
        "model-mismatch",
        "model-not-invoked",
        "tool-names-unextractable",
        "terminal-bucket-missing",
    ]


def test_verify_result_field_by_field_stable_on_valid_trajectory():
    """AC6 (hermetic half): field-by-field VerifierResult golden on a valid trajectory.

    This is the granularity the bake-off depends on — not just PASSED + bucket.
    """
    got = verify_trajectory(_traj()).to_dict()
    got.pop("timestamp")

    assert got == {
        # 0045 additive bump (silence->wrong-confidence) — same-change amendment.
        "schema_version": "0045/1",
        "status": "PASSED",
        "failure_reason": None,
        "model_identity": "served_present_and_matching",
        "model_invoked": True,
        "tool_names_invoked": ["grep", "symbols"],
        "terminal_bucket": "correct",
        "served_model": "qwen3:14b",
        "endpoint": "http://localhost:11434",
        "verifier_status": "PASSED",
        "details": {"method": "served_model_match"},
    }


# T2 — divergence closure (AC1/AC2/AC4): RED until the cutover.


def test_build_trajectory_record_delegates_to_canonical_extract_tool_names(monkeypatch):
    """AC1: the builder calls the module-level extract_tool_names symbol.

    Import-identity proof: only a call through the canonical symbol can observe
    the monkeypatch — an inline copy would silently ignore it.
    """
    monkeypatch.setattr(
        _lv, "extract_tool_names", lambda traj: (["__SENTINEL__"], True, None)
    )
    record = build_trajectory_record(_multitool_history(), 3)

    assert record["tool_names_invoked"] == ["__SENTINEL__"]


def test_build_trajectory_record_nameless_tool_call_returns_typed_failure_without_raising():
    """AC2/AC4: a nameless tool_call is a typed, non-raising failure — never a skip.

    The failure surfaces as DATA (tool_names_failure) because the builder is
    called live by ExplorerBackend and must not change loop control flow.
    """
    record = build_trajectory_record(_nameless_history(), 2)  # must not raise

    assert record["tool_names_failure"] == "tool-names-unextractable"
    # Strict-wins: no partial list that silently dropped the nameless call.
    assert record["tool_names_invoked"] == []


def test_nameless_tool_call_yields_identical_typed_outcome_in_both_paths():
    """AC2: verify path and builder produce the SAME typed outcome on the same input."""
    nameless = _nameless_history()

    verify_outcome = verify_trajectory(_traj(model_turns=nameless)).failure_reason
    build_outcome = build_trajectory_record(nameless, 2)["tool_names_failure"]

    assert verify_outcome == build_outcome == "tool-names-unextractable"


def test_extract_tool_names_is_strict_on_nameless_calls():
    """AC4: the canonical parser itself returns ([], False, code) — no partial list."""
    names, proven, reason = extract_tool_names({"model_turns": _nameless_history()})

    assert names == []
    assert proven is False
    assert reason == "tool-names-unextractable"


def test_verifier_artifact_0031_shape_pin():
    """PIN (0033 T1): a literal 0031/1 artifact (no citation-count fields) validates.

    This is the legacy shape the 0033 version gate must keep accepting after the
    schema bump — written against the LITERAL version string, not the constant.
    """
    artifact = {
        "schema_version": "0031/1",
        "requested_model": "qwen3:14b",
        "endpoint": "http://localhost:11434",
        "served_model": "qwen3:14b",
        "configured_endpoint_models": ["qwen3:14b"],
        "tiers_run": [0, 1],
        "model_turns": [],
        "terminal_bucket": "correct",
        "verifier_status": "PASSED",
        "failure_reason": None,
    }
    validate_verifier_artifact(artifact)  # must not raise, today and post-0033


def test_single_tool_name_parser_definition_by_symbol_audit():
    """AC8 consumer audit: exactly ONE tool-name parser definition exists.

    build_trajectory_record no longer carries an inline copy — its source calls
    the canonical extract_tool_names and contains no second seen-set name loop.
    A source/symbol assertion, not a point-in-time grep.
    """
    import inspect

    builder_src = inspect.getsource(build_trajectory_record)
    assert "extract_tool_names(" in builder_src
    assert "seen = set()" not in builder_src  # the deleted inline-parse signature

    # The canonical parser is the module-level symbol both paths resolve.
    assert _lv.extract_tool_names is extract_tool_names
    verify_src = inspect.getsource(verify_trajectory)
    assert "extract_tool_names(" in verify_src


# --- Spec 0033: citation counts on the trajectory record + schema 0033/1 (AC5) ---


def test_build_trajectory_record_carries_citation_counts():
    """AC5: the record carries the submit-seam counts as data."""
    record = build_trajectory_record(
        _multitool_history(), 3, citations_submitted=1, citations_surviving=0
    )
    assert record["citations_submitted"] == 1
    assert record["citations_surviving"] == 0


def test_found_then_dropped_distinct_from_honest_empty_in_artifact():
    """AC5: (1, 0) found-then-dropped is structurally distinguishable from
    (0, 0) honest-empty in the trajectory record — this class can't hide in
    'empty' again."""
    dropped = build_trajectory_record(
        _multitool_history(), 3, citations_submitted=1, citations_surviving=0
    )
    empty = build_trajectory_record(
        _multitool_history(), 3, citations_submitted=0, citations_surviving=0
    )
    assert (dropped["citations_submitted"], dropped["citations_surviving"]) == (1, 0)
    assert (empty["citations_submitted"], empty["citations_surviving"]) == (0, 0)
    assert dropped["citations_submitted"] != empty["citations_submitted"]


def test_legacy_0031_artifact_still_validates_post_bump():
    """AC5: after the 0033/1 bump, a literal 0031/1 artifact (no count fields)
    still validates via the version gate — additive, never a breaking bump."""
    artifact = {
        "schema_version": "0031/1",
        "requested_model": "qwen3:14b",
        "endpoint": "http://localhost:11434",
        "served_model": "qwen3:14b",
        "configured_endpoint_models": ["qwen3:14b"],
        "tiers_run": [0, 1],
        "model_turns": [],
        "terminal_bucket": "correct",
        "verifier_status": "PASSED",
        "failure_reason": None,
    }
    validate_verifier_artifact(artifact)
    # And the NEW version validates too (the gate accepts exactly the known set).
    artifact_new = dict(artifact, schema_version="0033/1",
                        citations_submitted=1, citations_surviving=0)
    validate_verifier_artifact(artifact_new)
    # An unknown version still fails loud.
    with pytest.raises(ValueError):
        validate_verifier_artifact(dict(artifact, schema_version="9999/9"))


def test_fc_citation_dropped_count_and_report_schema_untouched():
    """AC5: the eval-report schema is byte-untouched by this spec — the per-case
    counts live on the VERIFIER artifact, not the report."""
    from harpyja.eval import report as _report

    assert _report.SCHEMA_VERSION == "0028/1"  # not bumped by 0033
    assert "fc_citation_dropped_count" in _report._AGGREGATE_DEFAULTS
    assert "citations_submitted" not in _report._AGGREGATE_DEFAULTS
    assert "citations_surviving" not in _report._AGGREGATE_DEFAULTS


# --- Spec 0033: run_verified_case names + chains the typed degrade cause (AC6) ---


def test_run_verified_case_names_and_chains_degrade_cause(tmp_path, monkeypatch):
    """AC6: an explorer degrade BEFORE trajectory capture raises a ValueError that
    NAMES the typed ScoutUnavailable cause and chains it as __cause__ — never the
    0031 cause-less 'Explorer did not capture trajectory'."""
    import harpyja.scout.explorer_backend as _eb
    from harpyja.config.settings import Settings as _Settings
    from harpyja.eval.live_verifier import run_verified_case
    from harpyja.scout import errors as _serrors
    from harpyja.scout.errors import ScoutUnavailable

    class _DegradingBackend:
        def __init__(self, **kwargs):
            self.last_trajectory = None

        def run(self, query, seed):
            raise ScoutUnavailable(_serrors.MODEL_UNREACHABLE)

    monkeypatch.setattr(_eb, "ExplorerBackend", _DegradingBackend)
    (tmp_path / ".harpyja").mkdir()

    with pytest.raises(ValueError) as ei:
        run_verified_case(
            case_name="fake-case",
            settings=_Settings(),
            gateway=object(),
            gold_span={"file": "a.py", "start_line": 1, "end_line": 2},
            out_dir=tmp_path,
            repo_path=str(tmp_path),
            query="find it",
        )
    assert _serrors.MODEL_UNREACHABLE in str(ei.value)  # the cause is NAMED
    assert isinstance(ei.value.__cause__, ScoutUnavailable)  # and CHAINED


def test_run_verified_case_artifact_carries_citation_counts(tmp_path, monkeypatch):
    """AC5 (persisted-artifact half): the counts reach the WRITTEN artifact JSON,
    not only the in-memory trajectory record — found-then-dropped is durable."""
    import json as _json

    import harpyja.scout.explorer_backend as _eb
    from harpyja.config.settings import Settings as _Settings
    from harpyja.eval.live_verifier import run_verified_case

    class _SubmittingBackend:
        def __init__(self, **kwargs):
            self.last_trajectory = None

        def run(self, query, seed):
            self.last_trajectory = {
                "schema_version": VERIFIER_SCHEMA_VERSION,
                "model_turns": [
                    {"role": "assistant", "content": "",
                     "tool_calls": [{"function": {"name": "grep"}}]},
                ],
                "tool_names_invoked": ["grep"],
                "tool_names_failure": None,
                "served_model": "qwen3:14b",
                "endpoint": "http://127.0.0.1:11434/v1",
                "turns_used": 1,
                "citations_submitted": 1,
                "citations_surviving": 0,  # found-then-dropped
            }
            return []

    monkeypatch.setattr(_eb, "ExplorerBackend", _SubmittingBackend)
    (tmp_path / "repo" / ".harpyja").mkdir(parents=True)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    _result, artifact_path = run_verified_case(
        case_name="fake-case",
        settings=_Settings(),
        gateway=object(),
        gold_span={"file": "a.py", "start_line": 1, "end_line": 2},
        out_dir=out_dir,
        repo_path=str(tmp_path / "repo"),
        query="find it",
    )
    artifact = _json.loads(Path(artifact_path).read_text())
    assert artifact["citations_submitted"] == 1
    assert artifact["citations_surviving"] == 0


# --- Spec 0034: per-turn reasoning observability (AC2/AC4/AC5) ---


def test_valid_fixture_verify_outcome_pinned():
    """PIN (0034 T1): outcome tuple over the valid fixture — the AC4 baseline.

    Outcome-EQUALITY is the contract (status, failure_reason, four facts);
    artifact-byte identity is explicitly NOT claimed (to_dict stamps the
    current schema version).
    """
    r = verify_trajectory(_traj())
    assert (
        r.status, r.failure_reason, r.model_identity, r.model_invoked,
        r.tool_names_invoked, r.terminal_bucket,
    ) == ("PASSED", None, "served_present_and_matching", True,
          ["grep", "symbols"], "correct")


def test_build_trajectory_record_carries_per_turn():
    """AC2: a per_turn list lands verbatim under the record's per_turn key."""
    pt = [{"reasoning_chars": 51, "completion_tokens": 20, "finish_reason": "length"}]
    record = build_trajectory_record(_multitool_history(), 1, per_turn=pt)
    assert record["per_turn"] == pt


def test_build_trajectory_record_carries_think_mode():
    """AC2: think_mode lands on the record."""
    record = build_trajectory_record(_multitool_history(), 1, think_mode="default-omitted")
    assert record["think_mode"] == "default-omitted"


def test_build_trajectory_record_per_turn_defaults_when_omitted():
    """AC2: legacy callers unbroken — omitted params default safely."""
    record = build_trajectory_record(_multitool_history(), 1)
    assert record["per_turn"] == []
    assert record.get("think_mode") is None


def test_record_discriminates_reasoning_truncated_from_content_truncated_and_clean():
    """AC2: probe A's reasoning-first shape is distinguishable IN THE RECORD from a
    content-truncated turn AND a clean turn."""
    reasoning_trunc = {"reasoning_chars": 51, "completion_tokens": 20,
                       "finish_reason": "length"}
    content_trunc = {"reasoning_chars": 0, "completion_tokens": 20,
                     "finish_reason": "length"}
    clean = {"reasoning_chars": 2833, "completion_tokens": 642,
             "finish_reason": "tool_calls"}
    record = build_trajectory_record(
        _multitool_history(), 3, per_turn=[reasoning_trunc, content_trunc, clean]
    )
    shapes = [(t["finish_reason"], t["reasoning_chars"] and t["reasoning_chars"] > 0)
              for t in record["per_turn"]]
    assert shapes == [("length", True), ("length", 0), ("tool_calls", True)]
    assert len(set(map(str, record["per_turn"]))) == 3  # three distinct shapes


def test_schema_version_is_0034_1():
    """AC2: 0033/1 -> 0034/1 — spec 0034 additive bump (per_turn/think_mode).
    Amended by spec 0038 (serving_transport), spec 0043 (submission_outcome),
    and spec 0044 (confidence facts) and spec 0045 (silence->wrong-confidence;
    same-change reconciliation): the CURRENT version is 0045/1; 0034/1 and
    0038/1 stay known legacy versions."""
    assert VERIFIER_SCHEMA_VERSION == "0045/1"


def test_legacy_0031_and_0033_artifacts_still_validate():
    """AC2: the version gate accepts BOTH legacy versions with no reasoning fields."""
    base = {
        "requested_model": "qwen3:14b",
        "endpoint": "http://localhost:11434",
        "served_model": "qwen3:14b",
        "configured_endpoint_models": ["qwen3:14b"],
        "tiers_run": [0, 1],
        "model_turns": [],
        "terminal_bucket": "correct",
        "verifier_status": "PASSED",
        "failure_reason": None,
    }
    validate_verifier_artifact(dict(base, schema_version="0031/1"))
    validate_verifier_artifact(dict(base, schema_version="0033/1",
                                    citations_submitted=1, citations_surviving=1))
    with pytest.raises(ValueError):
        validate_verifier_artifact(dict(base, schema_version="9999/9"))


def test_0034_artifact_reasoning_fields_optional():
    """AC2: a 0034/1 artifact WITHOUT per_turn/think_mode still validates — a
    non-reasoning model legitimately produces none (defaulted, never rejected)."""
    artifact = {
        "schema_version": "0034/1",
        "requested_model": "m",
        "endpoint": "http://localhost:11434",
        "served_model": "m",
        "configured_endpoint_models": ["m"],
        "tiers_run": [0, 1],
        "model_turns": [],
        "terminal_bucket": "empty",
        "verifier_status": "PASSED",
        "failure_reason": None,
    }
    validate_verifier_artifact(artifact)


def test_written_artifact_carries_per_turn_and_think_mode(tmp_path, monkeypatch):
    """AC2 (the 0033 written-JSON lesson): the fields survive run_verified_case's
    HAND-ASSEMBLED artifact — asserted against the written JSON, not the record."""
    import json as _json

    import harpyja.scout.explorer_backend as _eb
    from harpyja.config.settings import Settings as _Settings
    from harpyja.eval.live_verifier import run_verified_case

    per_turn = [{"reasoning_chars": 51, "completion_tokens": 20,
                 "finish_reason": "length"}]

    class _StubBackend:
        def __init__(self, **kwargs):
            self.last_trajectory = None

        def run(self, query, seed):
            self.last_trajectory = {
                "schema_version": VERIFIER_SCHEMA_VERSION,
                "model_turns": [
                    {"role": "assistant", "content": "",
                     "tool_calls": [{"function": {"name": "grep"}}]},
                ],
                "tool_names_invoked": ["grep"],
                "tool_names_failure": None,
                "served_model": "qwen3:14b",
                "endpoint": "http://127.0.0.1:11434/v1",
                "turns_used": 1,
                "citations_submitted": 0,
                "citations_surviving": 0,
                "per_turn": per_turn,
                "think_mode": "default-omitted",
                # Spec 0038: the transport identity must survive assembly too.
                "serving_transport": "v1-chat-completions",
            }
            return []

    monkeypatch.setattr(_eb, "ExplorerBackend", _StubBackend)
    (tmp_path / "repo" / ".harpyja").mkdir(parents=True)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    _res, artifact_path = run_verified_case(
        case_name="fake-case", settings=_Settings(), gateway=object(),
        gold_span={"file": "a.py", "start_line": 1, "end_line": 2},
        out_dir=out_dir, repo_path=str(tmp_path / "repo"), query="find it",
    )
    artifact = _json.loads(Path(artifact_path).read_text())
    assert artifact["per_turn"] == per_turn
    assert artifact["think_mode"] == "default-omitted"
    # Spec 0038: serving_transport is durable in the WRITTEN artifact (the 0033
    # written-JSON lesson — the record alone proves nothing).
    assert artifact["serving_transport"] == "v1-chat-completions"


def test_verify_trajectory_outcome_equality_over_valid_fixtures():
    """AC4: outcome-EQUALITY over the valid fixture set, post-0034-bump.

    Byte-identity is explicitly DISCLAIMED — VerifierResult.to_dict() stamps the
    CURRENT schema version, so re-serialized artifacts differ by design. What
    must hold is the outcome tuple + the frozen codes.
    """
    r = verify_trajectory(_traj())
    assert (
        r.status, r.failure_reason, r.model_identity, r.model_invoked,
        r.tool_names_invoked, r.terminal_bucket,
    ) == ("PASSED", None, "served_present_and_matching", True,
          ["grep", "symbols"], "correct")
    # Four-facts contract + six failure codes untouched by 0034.
    assert len(FAILURE_CODES) == 6
    assert FAILURE_PRECEDENCE[0] == "artifact-incomplete"
    # A failing trajectory still fails identically.
    bad = verify_trajectory(_traj(served_model="wrong"))
    assert (bad.status, bad.failure_reason) == ("FAILED", "model-mismatch")


# --- Spec 0038: reconciliation — serving_transport + four-facts-survive + enum audit ---


def test_trajectory_records_serving_transport():
    """AC6 (0038): build_trajectory_record persists the serving transport
    (endpoint-mechanism identity) as an ADDITIVE optional field, so the
    four-facts invariant is checkable per-transport rather than assumed."""
    record = build_trajectory_record(
        _multitool_history(), 3, serving_transport="v1-reasoning-effort"
    )
    assert record["serving_transport"] == "v1-reasoning-effort"
    # Omitted → present-and-None (the think_mode posture): never fabricated.
    record = build_trajectory_record(_multitool_history(), 3)
    assert record["serving_transport"] is None


def test_legacy_artifacts_without_serving_transport_still_validate():
    """AC6 (0038): the version GATE — a legacy 0034/1 artifact (no
    serving_transport) still validates; 0038/1 is a known version; an unknown
    version still fails loud."""
    legacy = {
        "schema_version": "0034/1",
        "verifier_status": "PASSED",
        "requested_model": "qwen3:14b",
        "endpoint": "http://localhost:11434",
        "tiers_run": [1],
        "model_turns": [],
    }
    validate_verifier_artifact(legacy)  # no raise
    current = dict(legacy, schema_version="0038/1")
    validate_verifier_artifact(current)  # no raise
    with pytest.raises(ValueError):
        validate_verifier_artifact(dict(legacy, schema_version="9999/1"))


def test_four_facts_survive_reconciled_trajectory():
    """AC6 (0038): the verifier's four facts remain provable on a trajectory
    produced through the reconciled path (serving_transport recorded)."""
    traj = _traj(serving_transport="v1-reasoning-effort")
    result = verify_trajectory(traj)
    assert result.status == "PASSED"
    assert result.model_identity is not None
    assert result.model_invoked is True
    assert result.tool_names_invoked == ["grep", "symbols"]
    assert result.terminal_bucket == "correct"


def test_derive_think_mode_disambiguates_post_switch():
    """AC6 (0038): the 0034 enum audit — with the knob now routed through the
    honoring mechanism (reasoning_effort on /v1), the existing labels still
    disambiguate the tri-state: three distinct values, native wins over the
    chat-template knob, no new label needed. The labels name the OPERATOR
    INTENT (native think on/off/default); the transport mechanism they ride is
    recorded separately in serving_transport."""
    from harpyja.scout.explorer_backend import derive_think_mode

    labels = {
        derive_think_mode(True, True),
        derive_think_mode(False, True),
        derive_think_mode(None, True),
    }
    assert labels == {"native-think-true", "native-think-false", "default-omitted"}
    assert derive_think_mode(False, False) == "native-think-false"  # native wins


# --- Spec 0043: found-but-unsubmitted on the artifact, dual-seam (AC2) ---


def test_build_trajectory_record_carries_submission_outcome():
    """AC2 (seam 1): the builder carries the typed submission outcome + the
    detector version as data; omitted → present-and-None (additive default,
    legacy callers unbroken)."""
    record = build_trajectory_record(
        _multitool_history(), 3, submission_outcome="found-unsubmitted"
    )
    assert record["submission_outcome"] == "found-unsubmitted"
    from harpyja.eval.submission_gap import DETECTOR_VERSION

    assert record["detector_version"] == DETECTOR_VERSION

    defaulted = build_trajectory_record(_multitool_history(), 3)
    assert defaulted["submission_outcome"] is None
    assert defaulted["detector_version"] is None


def test_run_verified_case_written_artifact_carries_submission_outcome(
    tmp_path, monkeypatch
):
    """AC2 (seam 2, the 0033/0034/0038 dual-seam written-JSON pin): the
    hand-assembled run_verified_case artifact ALSO carries the field — computed
    from the trajectory + gold via the ONE detector, durable in the JSON."""
    import json as _json

    import harpyja.scout.explorer_backend as _eb
    from harpyja.config.settings import Settings as _Settings
    from harpyja.eval.live_verifier import run_verified_case
    from harpyja.eval.submission_gap import DETECTOR_VERSION

    class _FoundNotSubmittedBackend:
        def __init__(self, **kwargs):
            self.last_trajectory = None

        def run(self, query, seed):
            self.last_trajectory = {
                "schema_version": VERIFIER_SCHEMA_VERSION,
                "model_turns": [
                    {"role": "assistant", "content": "",
                     "tool_calls": [{"function": {"name": "grep"}}]},
                    {"role": "tool", "content":
                     "[CodeSpan(path='a.py', start_line=1, end_line=2, "
                     "symbol=None, language=None, kind=None)]"},
                ],
                "tool_names_invoked": ["grep"],
                "tool_names_failure": None,
                "served_model": "qwen3:14b",
                "endpoint": "http://127.0.0.1:11434/v1",
                "turns_used": 1,
                "citations_submitted": 0,
                "citations_surviving": 0,
            }
            return []

    monkeypatch.setattr(_eb, "ExplorerBackend", _FoundNotSubmittedBackend)
    (tmp_path / "repo" / ".harpyja").mkdir(parents=True)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    _result, artifact_path = run_verified_case(
        case_name="fake-case",
        settings=_Settings(),
        gateway=object(),
        gold_span={"file": "a.py", "start_line": 1, "end_line": 2},
        out_dir=out_dir,
        repo_path=str(tmp_path / "repo"),
        query="find it",
    )
    artifact = _json.loads(Path(artifact_path).read_text())
    # The gold span sat in a TOOL RESULT and was never submitted — the loss
    # class is countable in the durable artifact, distinct from never-found.
    assert artifact["submission_outcome"] == "found-unsubmitted"
    assert artifact["detector_version"] == DETECTOR_VERSION


def test_verifier_schema_version_bumped_and_legacy_still_validates():
    """AC2: 0038/1 -> 0043/1 -> 0044/1 -> 0045/1 additive bumps; every legacy
    version still passes the gate; unknown versions still fail loud."""
    from harpyja.eval.live_verifier import _KNOWN_VERIFIER_SCHEMA_VERSIONS

    assert VERIFIER_SCHEMA_VERSION == "0045/1"
    assert "0044/1" in _KNOWN_VERIFIER_SCHEMA_VERSIONS
    assert "0043/1" in _KNOWN_VERIFIER_SCHEMA_VERSIONS
    assert "0038/1" in _KNOWN_VERIFIER_SCHEMA_VERSIONS

    legacy = {
        "schema_version": "0038/1",
        "requested_model": "qwen3:14b",
        "endpoint": "http://localhost:11434",
        "served_model": "qwen3:14b",
        "configured_endpoint_models": ["qwen3:14b"],
        "tiers_run": [0, 1],
        "model_turns": [],
        "terminal_bucket": "correct",
        "verifier_status": "PASSED",
        "failure_reason": None,
        "serving_transport": "v1-chat-completions",
    }
    validate_verifier_artifact(legacy)  # no submission_outcome — still valid
    with pytest.raises(ValueError):
        validate_verifier_artifact(dict(legacy, schema_version="9999/9"))


def test_validate_verifier_artifact_requires_submission_outcome():
    """AC2: the 0043/1 required key set includes the new field — a CURRENT
    artifact cannot silently omit the loss-class fact (presence-required; a
    None value is legitimate when no gold was available to the builder)."""
    artifact = {
        "schema_version": "0043/1",
        "requested_model": "qwen3:14b",
        "endpoint": "http://localhost:11434",
        "served_model": "qwen3:14b",
        "configured_endpoint_models": ["qwen3:14b"],
        "tiers_run": [0, 1],
        "model_turns": [],
        "terminal_bucket": "correct",
        "verifier_status": "PASSED",
        "failure_reason": None,
    }
    with pytest.raises(ValueError):
        validate_verifier_artifact(artifact)  # 0043/1 without the field: loud
    validate_verifier_artifact(
        dict(artifact, submission_outcome="never-found",
             detector_version="0043/1")
    )
    validate_verifier_artifact(
        dict(artifact, submission_outcome=None, detector_version=None)
    )


# --- Spec 0044: confidence-conditioned nudge facts on the artifact, dual-seam (AC4) ---


def test_verifier_schema_version_is_0044_1():
    """AC4/0045 AC2: 0044/1 -> 0045/1 additive bump (silence->wrong-confidence);
    every legacy version still passes the gate; unknown versions fail loud."""
    from harpyja.eval.live_verifier import _KNOWN_VERIFIER_SCHEMA_VERSIONS

    assert VERIFIER_SCHEMA_VERSION == "0045/1"
    for legacy_version in ("0031/1", "0033/1", "0034/1", "0038/1", "0043/1", "0044/1"):
        assert legacy_version in _KNOWN_VERIFIER_SCHEMA_VERSIONS
    assert "0045/1" in _KNOWN_VERIFIER_SCHEMA_VERSIONS


def test_build_trajectory_record_carries_confidence_fields():
    """AC4 (seam 1): the builder carries fired/signal/turn/spans as data;
    omitted -> present-and-None/False (additive default, legacy callers
    unbroken)."""
    record = build_trajectory_record(
        _multitool_history(), 3,
        confidence_fired=True,
        confidence_triggering_signal="symbols-exact-span",
        confidence_firing_turn=2,
        confidence_firing_spans=[{"path": "a.py", "start_line": 1, "end_line": 2}],
    )
    assert record["confidence_fired"] is True
    assert record["confidence_triggering_signal"] == "symbols-exact-span"
    assert record["confidence_firing_turn"] == 2
    assert record["confidence_firing_spans"] == [
        {"path": "a.py", "start_line": 1, "end_line": 2}
    ]
    defaulted = build_trajectory_record(_multitool_history(), 3)
    assert defaulted["confidence_fired"] is False
    assert defaulted["confidence_triggering_signal"] is None
    assert defaulted["confidence_firing_turn"] is None
    assert defaulted["confidence_firing_spans"] is None


def test_run_verified_case_written_artifact_carries_confidence_fields(
    tmp_path, monkeypatch
):
    """AC4 (seam 2, the 0033/0034/0038/0043 dual-seam written-JSON pin — 4th
    application): run_verified_case's HAND-ASSEMBLED artifact carries the
    confidence facts from the backend trajectory, asserted against the written
    JSON, not the record."""
    import json as _json

    import harpyja.scout.explorer_backend as _eb
    from harpyja.config.settings import Settings as _Settings
    from harpyja.eval.live_verifier import run_verified_case

    class _FiredBackend:
        def __init__(self, **kwargs):
            self.last_trajectory = None

        def run(self, query, seed):
            self.last_trajectory = {
                "schema_version": VERIFIER_SCHEMA_VERSION,
                "model_turns": [
                    {"role": "assistant", "content": "",
                     "tool_calls": [{"function": {"name": "symbols"}}]},
                ],
                "tool_names_invoked": ["symbols"],
                "tool_names_failure": None,
                "served_model": "qwen3:14b",
                "endpoint": "http://127.0.0.1:11434/v1",
                "turns_used": 1,
                "citations_submitted": 0,
                "citations_surviving": 0,
                "confidence_fired": True,
                "confidence_triggering_signal": "symbols-exact-span",
                "confidence_firing_turn": 1,
                "confidence_firing_spans": [
                    {"path": "a.py", "start_line": 1, "end_line": 2}
                ],
            }
            return []

    monkeypatch.setattr(_eb, "ExplorerBackend", _FiredBackend)
    (tmp_path / "repo" / ".harpyja").mkdir(parents=True)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    _res, artifact_path = run_verified_case(
        case_name="fake-case", settings=_Settings(), gateway=object(),
        gold_span={"file": "a.py", "start_line": 1, "end_line": 2},
        out_dir=out_dir, repo_path=str(tmp_path / "repo"), query="find it",
    )
    artifact = _json.loads(Path(artifact_path).read_text())
    assert artifact["confidence_fired"] is True
    assert artifact["confidence_triggering_signal"] == "symbols-exact-span"
    assert artifact["confidence_firing_turn"] == 1
    assert artifact["confidence_firing_spans"] == [
        {"path": "a.py", "start_line": 1, "end_line": 2}
    ]


def test_validate_verifier_artifact_requires_confidence_fields_on_0044():
    """AC4: the 0044/1 required key set includes the confidence facts — a
    CURRENT artifact cannot silently omit them (presence-required; None/False
    values are legitimate on a non-firing run). Legacy 0043/1 artifacts (no
    confidence fields) still validate unchanged."""
    base = {
        "schema_version": "0044/1",
        "requested_model": "qwen3:14b",
        "endpoint": "http://localhost:11434",
        "served_model": "qwen3:14b",
        "configured_endpoint_models": ["qwen3:14b"],
        "tiers_run": [0, 1],
        "model_turns": [],
        "terminal_bucket": "correct",
        "verifier_status": "PASSED",
        "failure_reason": None,
        "submission_outcome": "never-found",
        "detector_version": "0043/1",
    }
    with pytest.raises(ValueError):
        validate_verifier_artifact(base)  # 0044/1 without confidence facts: loud
    validate_verifier_artifact(dict(
        base,
        confidence_fired=False,
        confidence_triggering_signal=None,
        confidence_firing_turn=None,
        confidence_firing_spans=None,
    ))
    # Legacy 0043/1 still validates with neither field set beyond its own gate.
    legacy = dict(base, schema_version="0043/1")
    validate_verifier_artifact(legacy)


def test_run_verified_case_written_artifact_carries_observability_fields(
    tmp_path, monkeypatch
):
    """AC4 (seam 2 extension): the record-only fields (b)/(c) and the
    attributable-null label are computed EVAL-SIDE POSTFLIGHT and are durable
    in the written JSON — presence-required on a 0044/1 artifact."""
    import json as _json

    import harpyja.scout.explorer_backend as _eb
    from harpyja.config.settings import Settings as _Settings
    from harpyja.eval.live_verifier import run_verified_case

    class _WrongSpanFiredBackend:
        def __init__(self, **kwargs):
            self.last_trajectory = None

        def run(self, query, seed):
            self.last_trajectory = {
                "schema_version": VERIFIER_SCHEMA_VERSION,
                "model_turns": [
                    {"role": "assistant", "content": "",
                     "tool_calls": [
                         {"id": "s1", "function": {"name": "symbols"}}]},
                    {"role": "tool", "tool_call_id": "s1", "content":
                     "[CodeSpan(path='other.py', start_line=5, end_line=9, "
                     "symbol=None, language=None, kind=None)]"},
                    {"role": "assistant", "content": "",
                     "tool_calls": [{"id": "g1", "function": {"name": "grep"}}]},
                    {"role": "tool", "tool_call_id": "g1", "content":
                     "[CodeSpan(path='other.py', start_line=6, end_line=6, "
                     "symbol=None, language=None, kind=None)]"},
                ],
                "tool_names_invoked": ["symbols", "grep"],
                "tool_names_failure": None,
                "served_model": "qwen3:14b",
                "endpoint": "http://127.0.0.1:11434/v1",
                "turns_used": 2,
                "citations_submitted": 0,
                "citations_surviving": 0,
                "confidence_fired": True,
                "confidence_triggering_signal": "symbols-exact-span",
                "confidence_firing_turn": 1,
                "confidence_firing_spans": [
                    {"path": "other.py", "start_line": 5, "end_line": 9}
                ],
            }
            return []

    monkeypatch.setattr(_eb, "ExplorerBackend", _WrongSpanFiredBackend)
    (tmp_path / "repo" / ".harpyja").mkdir(parents=True)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    _res, artifact_path = run_verified_case(
        case_name="fake-case", settings=_Settings(), gateway=object(),
        gold_span={"file": "a.py", "start_line": 1, "end_line": 2},
        out_dir=out_dir, repo_path=str(tmp_path / "repo"), query="find it",
    )
    artifact = _json.loads(Path(artifact_path).read_text())
    # (b): the grep hit at other.py:6 lies inside the earlier symbols span 5-9.
    assert artifact["grep_hits_inside_symbol_spans"] == 1
    # (c): two distinct tools overlap on other.py.
    assert artifact["convergent_evidence"] is True
    # The null is attributable: fired on a span that does NOT line-hit gold.
    assert artifact["confidence_null"] == "fired-on-wrong-span"
    validate_verifier_artifact(artifact)


# --- Spec 0045 (T11/T12, AC2): silence->wrong-confidence first-class fact ----
# The invisible cost the 0044 bucket ledger could not see — an empty->wrong-file
# submission under a FIRED gate — becomes a first-class counted fact, additive
# bump 0044/1 -> 0045/1, threaded through BOTH seams. A record-only
# unfired-s->wc cross-check rides the written artifact (the fired-conditioning
# loophole: distinguish "cost eliminated" from "cost de-attributed").

def _fired_wrong_file_backend(fired: bool):
    """A backend that returns a WRONG-FILE citation; gate fired or not."""
    import harpyja.scout.explorer_backend as _eb
    from harpyja.server.types import CodeSpan

    class _B:
        def __init__(self, **kwargs):
            self.last_trajectory = None

        def run(self, query, seed):
            self.last_trajectory = {
                "schema_version": VERIFIER_SCHEMA_VERSION,
                "model_turns": [
                    {"role": "assistant", "content": "",
                     "tool_calls": [{"id": "s1", "function": {"name": "symbols"}}]},
                    {"role": "tool", "tool_call_id": "s1", "content":
                     "[CodeSpan(path='wrong.py', start_line=5, end_line=9, "
                     "symbol=None, language=None, kind=None)]"},
                ],
                "tool_names_invoked": ["symbols"],
                "tool_names_failure": None,
                "served_model": "qwen3:8b",
                "endpoint": "http://127.0.0.1:11434/v1",
                "turns_used": 1,
                "citations_submitted": 1,
                "citations_surviving": 1,
                "confidence_fired": fired,
                "confidence_triggering_signal": "symbols-exact-span" if fired else None,
                "confidence_firing_turn": 1 if fired else None,
                "confidence_firing_spans": (
                    [{"path": "wrong.py", "start_line": 5, "end_line": 9}]
                    if fired else None
                ),
            }
            return [CodeSpan(path="wrong.py", start_line=5, end_line=9)]

    return _eb, _B


def _run_swc_case(tmp_path, monkeypatch, fired: bool):
    import json as _json

    from harpyja.config.settings import Settings as _Settings
    from harpyja.eval.live_verifier import run_verified_case

    _eb, backend_cls = _fired_wrong_file_backend(fired)
    monkeypatch.setattr(_eb, "ExplorerBackend", backend_cls)
    (tmp_path / "repo" / ".harpyja").mkdir(parents=True)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    _res, artifact_path = run_verified_case(
        case_name="swc-case", settings=_Settings(), gateway=object(),
        gold_span={"file": "gold.py", "start_line": 1, "end_line": 2},
        out_dir=out_dir, repo_path=str(tmp_path / "repo"), query="find it",
    )
    return _json.loads(Path(artifact_path).read_text())


def test_written_artifact_carries_silence_to_wrong_confidence(tmp_path, monkeypatch):
    # FIRED gate + wrong-file submission → silence->wrong-confidence True; the
    # record-only unfired line is False (it WAS fired).
    artifact = _run_swc_case(tmp_path, monkeypatch, fired=True)
    assert artifact["terminal_bucket"] == "wrong-file"
    assert artifact["silence_to_wrong_confidence"] is True
    assert artifact["unfired_silence_to_wrong_confidence"] is False
    validate_verifier_artifact(artifact)


def test_written_artifact_carries_unfired_swc_record_only(tmp_path, monkeypatch):
    # NOT fired + wrong-file submission → the record-only unfired cross-check is
    # True while the gate-attributed s->wc is False (cost de-attributed, not
    # eliminated — the fired-conditioning loophole made visible).
    artifact = _run_swc_case(tmp_path, monkeypatch, fired=False)
    assert artifact["terminal_bucket"] == "wrong-file"
    assert artifact["silence_to_wrong_confidence"] is False
    assert artifact["unfired_silence_to_wrong_confidence"] is True
    validate_verifier_artifact(artifact)


def test_verifier_schema_version_is_0045_1():
    from harpyja.eval.live_verifier import _KNOWN_VERIFIER_SCHEMA_VERSIONS

    assert VERIFIER_SCHEMA_VERSION == "0045/1"
    # Every legacy version — including 0044/1 — still validates (additive).
    for legacy in ("0031/1", "0033/1", "0034/1", "0038/1", "0043/1", "0044/1"):
        assert legacy in _KNOWN_VERIFIER_SCHEMA_VERSIONS


def test_swc_presence_required_on_0045_1():
    # A 0045/1 written artifact missing silence_to_wrong_confidence fails loud.
    base = {
        "schema_version": "0045/1",
        "verifier_status": "passed",
        "requested_model": "qwen3:8b",
        "endpoint": "http://127.0.0.1:11434/v1",
        "tiers_run": [0, 1],
        "model_turns": [],
        "submission_outcome": None,
        "confidence_fired": False,
        "confidence_triggering_signal": None,
        "confidence_firing_turn": None,
        "confidence_firing_spans": None,
        "grep_hits_inside_symbol_spans": 0,
        "convergent_evidence": False,
        "confidence_null": None,
        "unfired_silence_to_wrong_confidence": None,
        "case": "x",
    }
    with pytest.raises(ValueError, match="silence_to_wrong_confidence"):
        validate_verifier_artifact(base)
