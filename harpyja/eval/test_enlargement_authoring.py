"""Spec 0047 — enlargement authoring/tagging orchestration (unit; fakes only).

Blind-ineligibility filtering (issue names the gold path → author can't be blind),
extended-authoring-artifact assembly with a byte-identical drift-guard on the existing
36 records + an additive blind_ineligible_count, deterministic reachability tagging,
enlarged-terse assembly with the existing-19 drift-guard, the loud-rejection guard on
an untagged enlarged row, and the 20-case audit sample. No live model calls: the
author/verifier arms are injected fakes (the driver wires Claude + Codex on the host).
"""

from __future__ import annotations

import json

import pytest

from harpyja.eval import enlargement_authoring as ea
from harpyja.eval.authoring_provenance import validate_authoring_artifact
from harpyja.eval.dataset import DatasetError, load_dataset


def _raw(cid: str, repo: str, *, gold_path: str = "src/mod.py", issue: str | None = None) -> dict:
    return {
        "case_id": cid,
        "query": issue if issue is not None else f"users report a crash when frobnicating {cid}",
        "repo": repo,
        "expected_spans": [{"path": gold_path, "start_line": 10, "end_line": 20}],
        "base_commit": "deadbeef",
    }


# ---- blind-ineligibility (issue names gold path) -------------------------------


def test_is_blind_ineligible_when_issue_names_gold_path():
    ineligible = _raw("a__a-1", "a/a", issue="the bug is in src/mod.py around line 12")
    eligible = _raw("b__b-2", "b/b", issue="the separability matrix is wrong for nested models")
    assert ea.is_blind_ineligible(ineligible) is True
    assert ea.is_blind_ineligible(eligible) is False


# ---- Step 13 (T12): blind authoring + attrition counted, not silently dropped --


def _author(_inp: str) -> str:
    return "Where is the code that computes the thing?"


def _verifier_clean(_inp: str) -> str:
    return "clean"


def _verifier_leaky(_inp: str) -> str:
    return "leaky"


def test_author_enlarged_set_counts_blind_ineligible_separately():
    raws = [
        _raw("a__a-1", "a/a", issue="crash in src/mod.py"),  # blind-ineligible
        _raw("b__b-2", "b/b", issue="wrong result for nested models"),  # eligible
    ]
    cases, artifact, ineligible_ids = ea.author_enlarged_set(
        raws,
        author_invoke=_author,
        verifier_invoke=_verifier_clean,
        author_model="claude",
        verifier_model="codex",
    )
    assert ineligible_ids == ("a__a-1",)
    assert [c.case_id for c in cases] == ["b__b-2"]
    assert artifact.leaky_count == 0


def test_author_enlarged_set_records_leaky_drop():
    raws = [_raw("b__b-2", "b/b", issue="wrong result for nested models")]
    cases, artifact, ineligible_ids = ea.author_enlarged_set(
        raws,
        author_invoke=_author,
        verifier_invoke=_verifier_leaky,
        author_model="claude",
        verifier_model="codex",
    )
    assert cases == []
    assert artifact.leaky_count == 1
    assert artifact.dropped_count == 1
    assert ineligible_ids == ()


# ---- Step 13 (T12): extended artifact appends, existing byte-identical ----------


def _existing_artifact_payload() -> dict:
    inp = "You are given a software issue description...\n\nIssue:\nold\n"
    from harpyja.eval.authoring_provenance import sha256_text

    return {
        "schema_version": "0026/1",
        "leaky_count": 5,
        "dropped_count": 5,
        "records": [
            {
                "case_id": "old__old-1",
                "author_model": "claude",
                "verifier_model": "codex",
                "author_input": inp,
                "author_input_hash": sha256_text(inp),
                "verifier_input_hash": sha256_text("v"),
                "verifier_verdict": "clean",
                "outcome": "kept",
            }
        ],
    }


def test_assemble_enlarged_authoring_preserves_existing_and_adds_counts():
    existing = _existing_artifact_payload()
    raws = [_raw("b__b-2", "b/b", issue="wrong result for nested models")]
    _cases, new_artifact, _ineligible = ea.author_enlarged_set(
        raws, author_invoke=_author, verifier_invoke=_verifier_clean,
        author_model="claude", verifier_model="codex",
    )
    merged = ea.assemble_enlarged_authoring_artifact(
        existing, new_artifact, blind_ineligible_count=3
    )
    # existing record preserved byte-identical (prefix), counts aggregated
    assert merged["records"][0] == existing["records"][0]
    assert merged["leaky_count"] == existing["leaky_count"] + new_artifact.leaky_count
    assert merged["dropped_count"] == existing["dropped_count"] + new_artifact.dropped_count
    assert merged["blind_ineligible_count"] == 3
    # still validates loud at 0026/1 (additive key tolerated)
    validate_authoring_artifact(merged)


def test_assemble_enlarged_authoring_rejects_existing_record_drift():
    existing = _existing_artifact_payload()
    tampered = json.loads(json.dumps(existing))
    tampered["records"][0]["outcome"] = "dropped"  # mutate a committed record
    raws = [_raw("b__b-2", "b/b", issue="wrong result for nested models")]
    _cases, new_artifact, _i = ea.author_enlarged_set(
        raws, author_invoke=_author, verifier_invoke=_verifier_clean,
        author_model="claude", verifier_model="codex",
    )
    with pytest.raises(ea.EnlargementAuthoringError, match="drift"):
        ea.assemble_enlarged_authoring_artifact(
            existing, new_artifact, blind_ineligible_count=0,
            baseline_records=tampered["records"],
        )


# ---- Step 15 (T14/T15): deterministic tagging + loud rejection -----------------


def test_tag_enlarged_row_is_deterministic_reachability():
    case = ea._FakeCase(
        case_id="c__c-3", query="where is separability_matrix computed",
        repo="c/c", classification="point",
    )
    lexical = ea.tag_enlarged_row(
        case, span_text="def separability_matrix(): ...", concept_label="same",
    )
    conceptual = ea.tag_enlarged_row(
        case, span_text="def unrelated_helper(): ...", concept_label="divergent",
        concept_span={"path": "c/c/x.py", "start_line": 1, "end_line": 2},
        concept_span_provenance="hand-labeled-concept-span",
    )
    assert lexical["reachability"] == "lexical"
    assert lexical["reachability_provenance"] == "mechanical"
    assert conceptual["reachability"] == "conceptual"
    assert conceptual["concept_patch_relation"] == "divergent"
    assert conceptual["concept_span"]["path"] == "c/c/x.py"


def test_enlarged_terse_row_missing_tag_is_rejected_loudly(tmp_path):
    row = {
        "case_id": "c__c-3", "query": "q", "repo": "c/c", "classification": "point",
        "schema_version": "0036/1", "gold_withheld": True,
        "query_provenance": "model-authored-blind",
        # reachability + concept_patch_relation MISSING
    }
    p = tmp_path / "terse.jsonl"
    p.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(DatasetError, match="reachability"):
        load_dataset(p)


def test_assemble_enlarged_terse_preserves_existing_nineteen():
    existing = [
        {"case_id": "old__old-1", "query": "q", "repo": "o/o", "classification": "point",
         "schema_version": "0036/1", "gold_withheld": True,
         "query_provenance": "model-authored-blind", "reachability": "conceptual",
         "reachability_provenance": "mechanical", "concept_patch_relation": "same"},
    ]
    new_rows = [
        {"case_id": "new__new-2", "query": "q2", "repo": "n/n", "classification": "point",
         "schema_version": "0036/1", "gold_withheld": True,
         "query_provenance": "model-authored-blind", "reachability": "lexical",
         "reachability_provenance": "mechanical", "concept_patch_relation": "same"},
    ]
    merged = ea.assemble_enlarged_terse(existing, new_rows)
    assert existing[0] in merged
    assert [r["case_id"] for r in merged] == ["new__new-2", "old__old-1"]


def test_assemble_enlarged_terse_rejects_duplicate_case_id():
    existing = [{"case_id": "dup__dup-1", "query": "q", "repo": "o/o",
                 "classification": "point", "schema_version": "0036/1",
                 "gold_withheld": True, "query_provenance": "model-authored-blind",
                 "reachability": "conceptual", "reachability_provenance": "mechanical",
                 "concept_patch_relation": "same"}]
    dup = [dict(existing[0])]
    with pytest.raises(ea.EnlargementAuthoringError, match="duplicate"):
        ea.assemble_enlarged_terse(existing, dup)


def test_audit_sample_is_deterministic_and_capped():
    rows = [
        {"case_id": f"r__r-{i:03d}", "repo": f"repo{i % 5}"} for i in range(130)
    ]
    s1 = ea.audit_sample(rows, n=20)
    s2 = ea.audit_sample(list(reversed(rows)), n=20)
    assert len(s1) == 20
    assert [r["case_id"] for r in s1] == [r["case_id"] for r in s2]  # deterministic
