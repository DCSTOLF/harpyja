"""Spec 0041 — residency-probe contract tests (AC4).

Sent ≠ honored (the 0037 lesson applied to this spec's own knob): whether a
bounded ``keep_alive`` native touch actually re-bounds a model pinned at
``keep_alive=-1`` is judged ONLY from observed ``/api/ps`` ``expires_at``
movement — never from the request that was sent. The typed outcome commits as
a spec-local, schema-versioned artifact; the wiring is conditional on it and a
loud-FAIL tripwire pins wiring↔evidence consistency (fails, never skips).
"""

from __future__ import annotations

import pytest

from harpyja.eval.residency_probe import (
    RESIDENCY_PROBE_OUTCOMES,
    RESIDENCY_PROBE_SCHEMA_VERSION,
    ResidencyProbeError,
    assert_residency_wiring_matches_committed_outcome,
    judge_residency_outcome,
    load_committed_residency_probe_result,
    validate_residency_probe_result,
)


def test_residency_probe_outcomes_are_the_two_typed_values():
    assert RESIDENCY_PROBE_OUTCOMES == frozenset({"touch-rebounds", "touch-ignored"})


def test_residency_probe_schema_version_is_0041_residency_probe_1():
    assert RESIDENCY_PROBE_SCHEMA_VERSION == "0041/residency-probe/1"


def test_judge_residency_outcome_reads_only_expires_at_movement():
    touched = "2026-07-11T12:00:00+00:00"
    pinned_far = "2292-01-01T00:00:00+00:00"  # keep_alive=-1 far-future pin
    # expires_at moved to a bounded near-future after the touch → the server
    # HONORED the bounded keep_alive.
    assert (
        judge_residency_outcome(
            expires_at_before=pinned_far,
            expires_at_after="2026-07-11T12:05:00+00:00",
            touched_at=touched,
            keep_alive_bound_s=300,
        )
        == "touch-rebounds"
    )
    # expires_at unchanged (still the far-future pin) → the touch was IGNORED,
    # no matter what the sent request carried.
    assert (
        judge_residency_outcome(
            expires_at_before=pinned_far,
            expires_at_after=pinned_far,
            touched_at=touched,
            keep_alive_bound_s=300,
        )
        == "touch-ignored"
    )
    # Movement to ANOTHER far-future value is not a re-bound either — the
    # honoring claim requires the bounded near-future.
    assert (
        judge_residency_outcome(
            expires_at_before=pinned_far,
            expires_at_after="2293-01-01T00:00:00+00:00",
            touched_at=touched,
            keep_alive_bound_s=300,
        )
        == "touch-ignored"
    )


def test_judge_residency_outcome_parses_ollama_nanosecond_timestamps():
    """Ollama emits RFC3339 with nanosecond precision and 'Z'/offset suffixes —
    the judge must parse the wire format, not a pre-cleaned one."""
    assert (
        judge_residency_outcome(
            expires_at_before="0001-01-01T00:00:00Z",  # keep_alive=-1 pin shape
            expires_at_after="2026-07-11T12:04:59.123456789-03:00",
            touched_at="2026-07-11T12:00:00.987654321-03:00",
            keep_alive_bound_s=300,
        )
        == "touch-rebounds"
    )


def _result(outcome: str = "touch-rebounds") -> dict:
    return {
        "schema_version": RESIDENCY_PROBE_SCHEMA_VERSION,
        "endpoint": "http://127.0.0.1:11434",
        "model": "qwen3:14b",
        "keep_alive_bound_s": 300,
        "touched_at": "2026-07-11T12:00:00+00:00",
        "expires_at_before": "2292-01-01T00:00:00+00:00",
        "expires_at_after": "2026-07-11T12:05:00+00:00",
        "outcome": outcome,
    }


def test_validate_residency_probe_result_rejects_missing_expires_at_evidence():
    validate_residency_probe_result(_result())  # conforming passes
    with pytest.raises(ResidencyProbeError):
        validate_residency_probe_result(
            {k: v for k, v in _result().items() if k != "expires_at_before"}
        )
    with pytest.raises(ResidencyProbeError):
        validate_residency_probe_result(
            {k: v for k, v in _result().items() if k != "expires_at_after"}
        )
    with pytest.raises(ResidencyProbeError):
        validate_residency_probe_result({**_result(), "outcome": "honored"})
    with pytest.raises(ResidencyProbeError):
        validate_residency_probe_result(
            {**_result(), "schema_version": "0038/1"}
        )
    # The recorded outcome must MATCH what the evidence re-judges to — an
    # artifact whose outcome contradicts its own expires_at facts is invalid.
    with pytest.raises(ResidencyProbeError):
        validate_residency_probe_result({**_result(), "outcome": "touch-ignored"})


def test_assert_residency_wiring_matches_committed_outcome_fails_loud_on_drift():
    rebounds = _result("touch-rebounds")
    # Wiring agrees with evidence → passes.
    assert_residency_wiring_matches_committed_outcome(
        touch_enabled=True, committed=rebounds
    )
    assert_residency_wiring_matches_committed_outcome(
        touch_enabled=False,
        committed={
            **_result("touch-ignored"),
            "expires_at_after": "2292-01-01T00:00:00+00:00",
        },
    )
    # Drift FAILS loudly — never skips (the 0038 posture).
    with pytest.raises(ResidencyProbeError, match="drift"):
        assert_residency_wiring_matches_committed_outcome(
            touch_enabled=False, committed=rebounds
        )
    with pytest.raises(ResidencyProbeError, match="drift"):
        assert_residency_wiring_matches_committed_outcome(
            touch_enabled=True,
            committed={
                **_result("touch-ignored"),
                "expires_at_after": "2292-01-01T00:00:00+00:00",
            },
        )


def test_committed_residency_probe_loads_and_validates():
    """Archive-first resolver over THE committed artifact. Until the live
    probe (AC7) commits it, absence skips; once committed this validates it
    forever (and the T18 integration test is the enforced live consumer)."""
    try:
        result = load_committed_residency_probe_result()
    except ResidencyProbeError as e:
        if "not found" in str(e):
            pytest.skip("residency probe not yet run (AC7 live step)")
        raise
    assert result["outcome"] in RESIDENCY_PROBE_OUTCOMES