"""Spec 0047 — enlargement authoring/tagging orchestration (operator-side, offline).

Reuses 0036's two-model blind protocol (``terse_authoring.author_terse_set``) and the
loud authoring-provenance sidecar VERBATIM; adds only the enlargement-scale
orchestration the audited convert needs:

- ``is_blind_ineligible`` / ``author_enlarged_set`` — pre-filter cases whose issue text
  NAMES the gold path (the author input cannot be made blind) so blind-ineligibility is
  COUNTED, never a silent drop, exactly as 0036 predicted (14/50 were ineligible).
- ``assemble_enlarged_authoring_artifact`` — append the new records to the committed 36,
  proving the existing prefix byte-identical (drift-guard) and carrying an ADDITIVE
  ``blind_ineligible_count`` (legacy 0026/1 validates unchanged).
- ``tag_enlarged_row`` — build a loud-loadable ``0036/1`` terse row: reachability is the
  DETERMINISTIC ``classify_reachability`` (mechanical); concept-vs-patch is a model
  hand-label (gold-visible) recorded with its own provenance.
- ``assemble_enlarged_terse`` / ``audit_sample`` — assemble the enlarged fixture with the
  existing-19 drift-guard, and emit a deterministic 20-case sample for operator audit.

NON-PRODUCT: the author/verifier arms are INJECTED callables (the driver wires Claude +
Codex via the operator's cross-model CLI tooling) — never the product ModelGateway.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Callable

from harpyja.eval.authoring_provenance import (
    AuthoringArtifact,
    validate_authoring_artifact,
)
from harpyja.eval.terse_authoring import author_terse_set
from harpyja.eval.terse_reachability import MECHANICAL, classify_reachability

Invoke = Callable[[str], str]

_QUERY_PROVENANCE = "model-authored-blind"
_CLASSIFICATION_PROVENANCE = "hand-labeled-by-intent"
_TERSE_SCHEMA_0036 = "0036/1"


class EnlargementAuthoringError(ValueError):
    """A drift-guard / dup-guard fired, or an assembled artifact is malformed — loud."""


# ---- blind-ineligibility (the 0036 attrition class) ---------------------------


def is_blind_ineligible(raw_case: dict) -> bool:
    """True iff the issue text NAMES a gold-span path — the author input cannot be made
    blind, so the case is ineligible for the blind protocol (counted, never authored)."""
    issue = str(raw_case.get("query", ""))
    for span in raw_case.get("expected_spans", []):
        path = span.get("path") if isinstance(span, dict) else None
        if path and path in issue:
            return True
    return False


def author_enlarged_set(
    raw_cases: list[dict],
    *,
    author_invoke: Invoke,
    verifier_invoke: Invoke,
    author_model: str,
    verifier_model: str,
) -> tuple[list, AuthoringArtifact, tuple[str, ...]]:
    """Author the enlarged set under the blind protocol, pre-filtering the
    blind-ineligible cases and returning their ids so the count is DATA, not a silent
    drop. Delegates the kept cases to 0036's ``author_terse_set`` verbatim."""
    eligible: list[dict] = []
    ineligible_ids: list[str] = []
    for raw in raw_cases:
        if is_blind_ineligible(raw):
            ineligible_ids.append(raw["case_id"])
        else:
            eligible.append(raw)
    cases, artifact = author_terse_set(
        eligible,
        author_invoke=author_invoke,
        verifier_invoke=verifier_invoke,
        author_model=author_model,
        verifier_model=verifier_model,
    )
    return cases, artifact, tuple(ineligible_ids)


# ---- extended authoring artifact (append; existing byte-identical) ------------


def _record_payload(r) -> dict:
    return {
        "case_id": r.case_id,
        "author_model": r.author_model,
        "verifier_model": r.verifier_model,
        "author_input": r.author_input,
        "author_input_hash": r.author_input_hash,
        "verifier_input_hash": r.verifier_input_hash,
        "verifier_verdict": r.verifier_verdict,
        "outcome": r.outcome,
    }


def _record_sha(rec: dict) -> str:
    return hashlib.sha256(json.dumps(rec, sort_keys=True).encode("utf-8")).hexdigest()


def assemble_enlarged_authoring_artifact(
    existing_payload: dict,
    new_artifact: AuthoringArtifact,
    *,
    blind_ineligible_count: int,
    baseline_records: list[dict] | None = None,
) -> dict:
    """Append the new authoring records to the committed artifact, aggregate the
    leaky/dropped counts, and add the ADDITIVE ``blind_ineligible_count``.

    Drift-guard: the existing records prefix must be byte-identical to
    ``baseline_records`` (defaults to ``existing_payload['records']``) — a mutated
    committed record raises. Validates loud at ``0026/1`` (additive key tolerated)."""
    existing_records = list(existing_payload.get("records", []))
    baseline = baseline_records if baseline_records is not None else existing_records
    if len(baseline) != len(existing_records):
        raise EnlargementAuthoringError(
            "authoring drift: baseline record count "
            f"{len(baseline)} != existing {len(existing_records)}"
        )
    for i, (base, cur) in enumerate(zip(baseline, existing_records, strict=True)):
        if _record_sha(base) != _record_sha(cur):
            raise EnlargementAuthoringError(
                f"authoring drift: committed record {i} changed "
                f"({cur.get('case_id')!r}) — refusing to enlarge a mutated artifact"
            )
    merged = {
        "schema_version": existing_payload.get("schema_version", "0026/1"),
        "leaky_count": existing_payload.get("leaky_count", 0) + new_artifact.leaky_count,
        "dropped_count": existing_payload.get("dropped_count", 0)
        + new_artifact.dropped_count,
        "blind_ineligible_count": existing_payload.get("blind_ineligible_count", 0)
        + blind_ineligible_count,
        "records": existing_records + [_record_payload(r) for r in new_artifact.records],
    }
    validate_authoring_artifact(merged)
    return merged


# ---- tagging (reachability mechanical + concept-vs-patch hand-label) ----------


@dataclasses.dataclass(frozen=True)
class _FakeCase:
    """A minimal EvalCase stand-in for unit tests (the real driver passes EvalCase)."""

    case_id: str
    query: str
    repo: str
    classification: str


def tag_enlarged_row(
    case,
    *,
    span_text: str,
    concept_label: str,
    concept_span: dict | None = None,
    concept_span_provenance: str | None = None,
) -> dict:
    """Build a loud-loadable ``0036/1`` terse row for one kept, authored case.

    Reachability is DETERMINISTIC (``classify_reachability`` over the query's own
    code-like vocabulary vs the gold span text; provenance ``mechanical``).
    ``concept_label`` (``same`` | ``divergent``) is a model hand-label made with gold
    VISIBLE — recorded with ``hand-labeled`` provenance; a ``divergent`` row must carry
    a concept span."""
    reachability = classify_reachability(case.query, span_text)
    row: dict = {
        "case_id": case.case_id,
        "query": case.query,
        "repo": case.repo,
        "classification": case.classification,
        "schema_version": _TERSE_SCHEMA_0036,
        "gold_withheld": True,
        "query_provenance": _QUERY_PROVENANCE,
        "classification_provenance": _CLASSIFICATION_PROVENANCE,
        "reachability": reachability,
        "reachability_provenance": MECHANICAL,
        "concept_patch_relation": concept_label,
    }
    if concept_label == "divergent":
        if concept_span is None or not concept_span_provenance:
            raise EnlargementAuthoringError(
                f"divergent case {case.case_id!r} requires a concept span + provenance"
            )
        row["concept_span"] = concept_span
        row["concept_span_provenance"] = concept_span_provenance
    return row


def assemble_enlarged_terse(existing_rows: list[dict], new_rows: list[dict]) -> list[dict]:
    """Append new terse rows to the committed 19, rejecting duplicate case_ids loudly;
    the existing rows are reused verbatim and the output is sorted by case_id."""
    seen = {r["case_id"] for r in existing_rows}
    merged = list(existing_rows)
    for row in new_rows:
        cid = row["case_id"]
        if cid in seen:
            raise EnlargementAuthoringError(f"duplicate case_id on terse append: {cid!r}")
        seen.add(cid)
        merged.append(row)
    merged.sort(key=lambda r: r["case_id"])
    return merged


def audit_sample(rows: list[dict], n: int = 20) -> list[dict]:
    """A deterministic, evenly-spread sample of ``n`` rows (sorted by case_id, strided)
    for the operator to spot-check — not the whole enlarged set."""
    ordered = sorted(rows, key=lambda r: r["case_id"])
    if len(ordered) <= n:
        return ordered
    stride = len(ordered) / n
    return [ordered[int(i * stride)] for i in range(n)]
