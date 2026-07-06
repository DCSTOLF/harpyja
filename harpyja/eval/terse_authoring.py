"""spec 0026 AC2 layer (b) — OFFLINE two-model blind-authoring tool.

A one-time OPERATOR/DEV activity (same out-of-air-gap posture as `swebench_eval`'s
`convert`/`provision`): author and verifier are INJECTED callables (separately-invoked
model contexts via the operator's cross-model tooling), NEVER the product
`ModelGateway`. For each raw case the tool builds an author prompt from the issue
intent with the gold span WITHHELD, invokes the author for a terse query, invokes the
verifier separately for a semantic-leak verdict, records loud authoring provenance,
and routes a `leaky` verdict to drop (never a silent keep). It emits terse `EvalCase`s
+ an `AuthoringArtifact` — it does NOT touch Harpyja runtime.
"""

from __future__ import annotations

from collections.abc import Callable

from harpyja.eval.authoring_provenance import (
    AUTHORING_SCHEMA_VERSION,
    AuthoringArtifact,
    AuthoringRecord,
    assert_author_input_blind,
    sha256_text,
    validate_authoring_record,
)
from harpyja.eval.dataset import DATASET_SCHEMA_VERSION, EvalCase, ExpectedSpan

Invoke = Callable[[str], str]

_QUERY_PROVENANCE = "model-authored-blind"
_CLASSIFICATION_PROVENANCE = "hand-labeled-by-intent"


def _author_prompt(issue: str) -> str:
    return (
        "You are given a software issue description. Write a SHORT, natural terse "
        "query (one sentence) capturing what a developer would ask to locate the "
        "relevant code. Do NOT invent file paths or line numbers.\n\n"
        f"Issue:\n{issue}\n"
    )


def _verifier_prompt(query: str, issue: str, spans: tuple[ExpectedSpan, ...]) -> str:
    paths = ", ".join(sp.path for sp in spans)
    return (
        "Does the following terse query semantically ENCODE the gold answer location "
        "(reuse its file path / identifiers / structure) rather than describe the "
        "issue intent? Answer 'leaky' or 'clean'.\n\n"
        f"Query: {query}\nGold location: {paths}\nIssue: {issue}\n"
    )


def _parse_spans(raw_case: dict) -> tuple[ExpectedSpan, ...]:
    return tuple(
        ExpectedSpan(path=s["path"], start_line=s["start_line"], end_line=s["end_line"])
        for s in raw_case["expected_spans"]
    )


def author_terse_case(
    raw_case: dict,
    *,
    author_invoke: Invoke,
    verifier_invoke: Invoke,
    author_model: str,
    verifier_model: str,
    classification: str = "point",
) -> tuple[EvalCase | None, AuthoringRecord]:
    """Author one terse case under the blind protocol. Returns `(EvalCase | None,
    AuthoringRecord)` — the case is `None` when the verifier flags a leak (dropped)."""
    issue = str(raw_case["query"])
    spans = _parse_spans(raw_case)

    author_input = _author_prompt(issue)
    # Build a preliminary record just to run the operational blindness assertion on
    # the author input BEFORE invoking the author (fail loud if the issue itself would
    # hand the author the gold path).
    probe = validate_authoring_record(
        {
            "case_id": raw_case["case_id"],
            "author_model": author_model,
            "verifier_model": verifier_model,
            "author_input": author_input,
            "author_input_hash": sha256_text(author_input),
            "verifier_input_hash": sha256_text(""),
            "verifier_verdict": "clean",
            "outcome": "kept",
        }
    )
    assert_author_input_blind(probe, spans)  # pin (2), end-to-end

    query = author_invoke(author_input).strip()
    verifier_input = _verifier_prompt(query, issue, spans)
    verdict = verifier_invoke(verifier_input).strip().lower()
    verdict = "leaky" if verdict == "leaky" else "clean"
    outcome = "kept" if verdict == "clean" else "dropped"

    record = AuthoringRecord(
        case_id=raw_case["case_id"],
        author_model=author_model,
        verifier_model=verifier_model,
        author_input=author_input,
        author_input_hash=sha256_text(author_input),
        verifier_input_hash=sha256_text(verifier_input),
        verifier_verdict=verdict,
        outcome=outcome,
    )

    if outcome != "kept":
        return None, record

    case = EvalCase(
        case_id=raw_case["case_id"],
        query=query,
        repo=str(raw_case["repo"]),
        expected_spans=(),  # joined at load time from the pinned raw fixture
        classification=classification,
        schema_version=DATASET_SCHEMA_VERSION,
        query_provenance=_QUERY_PROVENANCE,
        gold_withheld=True,
        classification_provenance=_CLASSIFICATION_PROVENANCE,
    )
    return case, record


def author_terse_set(
    raw_cases: list[dict],
    *,
    author_invoke: Invoke,
    verifier_invoke: Invoke,
    author_model: str,
    verifier_model: str,
) -> tuple[list[EvalCase], AuthoringArtifact]:
    """Author a whole set; aggregate leaky/dropped counts (provenance-of-a-null)."""
    cases: list[EvalCase] = []
    records: list[AuthoringRecord] = []
    leaky = 0
    dropped = 0
    for raw in raw_cases:
        case, record = author_terse_case(
            raw,
            author_invoke=author_invoke,
            verifier_invoke=verifier_invoke,
            author_model=author_model,
            verifier_model=verifier_model,
        )
        records.append(record)
        if record.verifier_verdict == "leaky":
            leaky += 1
        if record.outcome == "dropped":
            dropped += 1
        if case is not None:
            cases.append(case)
    artifact = AuthoringArtifact(
        schema_version=AUTHORING_SCHEMA_VERSION,
        records=tuple(records),
        leaky_count=leaky,
        dropped_count=dropped,
    )
    return cases, artifact
