"""spec 0026 AC2 — the load-bearing authoring provenance is carried in a LOUD-VALIDATED
sidecar shape (never prose), and pin (2)'s blindness is an operational assertion (the
recorded author input contains none of the joined gold-span content)."""

from __future__ import annotations

import hashlib

import pytest

from harpyja.eval.authoring_provenance import (
    AUTHORING_SCHEMA_VERSION,
    AuthoringError,
    assert_author_input_blind,
    validate_authoring_artifact,
    validate_authoring_record,
)
from harpyja.eval.dataset import ExpectedSpan


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


_AUTHOR_INPUT = (
    "Issue intent: nested compound models report the wrong separability matrix. "
    "Author a terse query capturing the user's ask. (Gold location withheld.)"
)


def _rec(**over) -> dict:
    r = {
        "case_id": "astropy__astropy-12907",
        "author_model": "hf.co/Qwen/Qwen3-8B-GGUF:latest",
        "verifier_model": "qwen3:4b-instruct",
        "author_input": _AUTHOR_INPUT,
        "author_input_hash": _sha(_AUTHOR_INPUT),
        "verifier_input_hash": _sha("verifier sees query + issue"),
        "verifier_verdict": "clean",
        "outcome": "kept",
    }
    r.update(over)
    return r


_SPANS = (ExpectedSpan(path="astropy/modeling/separable.py", start_line=242, end_line=248),)


@pytest.mark.parametrize(
    "missing",
    [
        "author_model",
        "verifier_model",
        "author_input_hash",
        "verifier_input_hash",
        "verifier_verdict",
        "outcome",
    ],
)
def test_authoring_record_requires_all_fields(missing):
    bad = {k: v for k, v in _rec().items() if k != missing}
    with pytest.raises(AuthoringError):
        validate_authoring_record(bad)


def test_authoring_verdict_enum_validated():
    with pytest.raises(AuthoringError):
        validate_authoring_record(_rec(verifier_verdict="maybe"))


def test_authoring_outcome_enum_validated():
    with pytest.raises(AuthoringError):
        validate_authoring_record(_rec(outcome="shipped"))


def test_authoring_hash_consistency_enforced():
    with pytest.raises(AuthoringError):
        validate_authoring_record(_rec(author_input_hash="deadbeef"))


def test_pin2_author_input_excludes_joined_span_content():
    # A clean author input (no gold path) passes; one containing the gold span path fails.
    validate_authoring_record(_rec())  # sanity
    assert_author_input_blind(validate_authoring_record(_rec()), _SPANS)  # no raise

    leaked_input = _AUTHOR_INPUT + " see astropy/modeling/separable.py"
    leaky = _rec(author_input=leaked_input, author_input_hash=_sha(leaked_input))
    with pytest.raises(AuthoringError):
        assert_author_input_blind(validate_authoring_record(leaky), _SPANS)


def test_authoring_aggregate_counts_present_and_schema_versioned():
    artifact = {
        "schema_version": AUTHORING_SCHEMA_VERSION,
        "records": [_rec()],
        "leaky_count": 0,
        "dropped_count": 0,
    }
    parsed = validate_authoring_artifact(artifact)
    assert parsed.schema_version == AUTHORING_SCHEMA_VERSION
    assert parsed.leaky_count == 0 and parsed.dropped_count == 0
    assert len(parsed.records) == 1


def test_authoring_artifact_rejects_missing_counts():
    artifact = {
        "schema_version": AUTHORING_SCHEMA_VERSION,
        "records": [_rec()],
        # leaky_count / dropped_count omitted → provenance-of-a-null violation
    }
    with pytest.raises(AuthoringError):
        validate_authoring_artifact(artifact)
