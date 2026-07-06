"""spec 0026 AC2 — loud-validated authoring-provenance sidecar for the terse set.

The two-model blind-authoring protocol's load-bearing proof is carried in a validated
shape, NEVER prose: one record per authored case (which models authored/verified it,
the input hashes, the verifier verdict, the kept/reauthored/dropped outcome) plus the
aggregate leaky/dropped counts (provenance-of-a-null). Pin (2)'s blindness is an
OPERATIONAL assertion here: `assert_author_input_blind` proves the recorded author
input contains none of the joined gold-span content — the concrete
"is-the-skip-actually-skipping" check, not a bare attestation.

This is OPERATOR/DEV audit metadata produced OFFLINE (out of Harpyja runtime); it is
NOT read by the dataset loader or the AC6 scoring path — hence a sidecar keyed by
`case_id`, not `EvalCase` fields.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from harpyja.eval.dataset import ExpectedSpan
from harpyja.eval.report import atomic_write_json

AUTHORING_SCHEMA_VERSION = "0026/1"

VERDICTS = frozenset({"clean", "leaky"})
OUTCOMES = frozenset({"kept", "reauthored", "dropped"})

_RECORD_REQUIRED = (
    "case_id",
    "author_model",
    "verifier_model",
    "author_input",
    "author_input_hash",
    "verifier_input_hash",
    "verifier_verdict",
    "outcome",
)


class AuthoringError(Exception):
    """An authoring-provenance record or artifact was malformed — raised loudly so a
    missing load-bearing field is never a silent passenger."""


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AuthoringRecord:
    case_id: str
    author_model: str
    verifier_model: str
    author_input: str
    author_input_hash: str
    verifier_input_hash: str
    verifier_verdict: str
    outcome: str


@dataclass(frozen=True)
class AuthoringArtifact:
    schema_version: str
    records: tuple[AuthoringRecord, ...]
    leaky_count: int
    dropped_count: int


def validate_authoring_record(raw: dict) -> AuthoringRecord:
    if not isinstance(raw, dict):
        raise AuthoringError(f"authoring record must be an object, got {type(raw).__name__}")
    for key in _RECORD_REQUIRED:
        if key not in raw:
            raise AuthoringError(f"authoring record missing required field {key!r}")
    for key in _RECORD_REQUIRED:
        if not isinstance(raw[key], str) or not raw[key]:
            raise AuthoringError(f"authoring record field {key!r} must be a non-empty string")
    if raw["verifier_verdict"] not in VERDICTS:
        raise AuthoringError(
            f"verifier_verdict={raw['verifier_verdict']!r} not in {sorted(VERDICTS)}"
        )
    if raw["outcome"] not in OUTCOMES:
        raise AuthoringError(f"outcome={raw['outcome']!r} not in {sorted(OUTCOMES)}")
    if sha256_text(raw["author_input"]) != raw["author_input_hash"]:
        raise AuthoringError(
            f"author_input_hash does not match sha256(author_input) for {raw['case_id']!r}"
        )
    return AuthoringRecord(
        case_id=raw["case_id"],
        author_model=raw["author_model"],
        verifier_model=raw["verifier_model"],
        author_input=raw["author_input"],
        author_input_hash=raw["author_input_hash"],
        verifier_input_hash=raw["verifier_input_hash"],
        verifier_verdict=raw["verifier_verdict"],
        outcome=raw["outcome"],
    )


def assert_author_input_blind(
    record: AuthoringRecord, expected_spans: tuple[ExpectedSpan, ...]
) -> None:
    """Pin (2): the recorded author input must contain NONE of the joined gold-span
    content (the file path or its `path:line` citation form). A violation means the
    authoring context was not actually blind — raise loudly."""
    text = record.author_input
    for sp in expected_spans:
        if sp.path in text:
            raise AuthoringError(
                f"pin(2) blindness violated for {record.case_id!r}: author input "
                f"contains gold-span path {sp.path!r}"
            )
        for cite in (f"{sp.path}:{sp.start_line}", f"{sp.path}:{sp.start_line}-{sp.end_line}"):
            if cite in text:
                raise AuthoringError(
                    f"pin(2) blindness violated for {record.case_id!r}: author input "
                    f"contains gold-span citation {cite!r}"
                )


def validate_authoring_artifact(raw: dict) -> AuthoringArtifact:
    if not isinstance(raw, dict):
        raise AuthoringError("authoring artifact must be an object")
    if raw.get("schema_version") != AUTHORING_SCHEMA_VERSION:
        raise AuthoringError(
            f"authoring artifact schema_version must be {AUTHORING_SCHEMA_VERSION!r}"
        )
    records_raw = raw.get("records")
    if not isinstance(records_raw, list):
        raise AuthoringError("authoring artifact 'records' must be a list")
    for key in ("leaky_count", "dropped_count"):
        if key not in raw or not isinstance(raw[key], int) or isinstance(raw[key], bool):
            raise AuthoringError(f"authoring artifact missing integer aggregate {key!r}")
    records = tuple(validate_authoring_record(r) for r in records_raw)
    return AuthoringArtifact(
        schema_version=AUTHORING_SCHEMA_VERSION,
        records=records,
        leaky_count=raw["leaky_count"],
        dropped_count=raw["dropped_count"],
    )


def write_authoring_artifact(
    artifact: AuthoringArtifact, *, out_dir: str | Path, repo_path: str | Path
) -> Path:
    """Persist the artifact via the shared outside-repo atomic writer."""
    payload = {
        "schema_version": artifact.schema_version,
        "leaky_count": artifact.leaky_count,
        "dropped_count": artifact.dropped_count,
        "records": [
            {
                "case_id": r.case_id,
                "author_model": r.author_model,
                "verifier_model": r.verifier_model,
                "author_input": r.author_input,
                "author_input_hash": r.author_input_hash,
                "verifier_input_hash": r.verifier_input_hash,
                "verifier_verdict": r.verifier_verdict,
                "outcome": r.outcome,
            }
            for r in artifact.records
        ],
    }
    return atomic_write_json(
        payload,
        out_dir=out_dir,
        repo_path=repo_path,
        filename="swebench_verified.authoring.json",
    )
