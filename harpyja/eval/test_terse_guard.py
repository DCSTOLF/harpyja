"""spec 0026 AC2 layer (a) / AC5 — the near-vacuous token-subset tripwire (a query
containing gold-span-only code identifiers absent from the source issue is flagged),
recomputed against the JOINED source issue; plus loud guard rejection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harpyja.eval.dataset import DATASET_SCHEMA_VERSION, DatasetError, load_dataset
from harpyja.eval.terse_dataset import compute_leaked_tokens, load_terse_dataset

_FIX = Path(__file__).parent / "fixtures"
_RAW = _FIX / "swebench_verified.raw.jsonl"
_PROV = _FIX / "swebench_verified.provenance.json"
_CASE = "astropy__astropy-12907"


def _terse_row(**over) -> dict:
    row = {
        "schema_version": DATASET_SCHEMA_VERSION,
        "case_id": _CASE,
        "query": "nested compound models report the wrong separability matrix",
        "repo": "astropy/astropy",
        "classification": "point",
        "gold_withheld": True,
        "query_provenance": "model-authored-blind",
        "classification_provenance": "hand-labeled-by-intent",
    }
    row.update(over)
    return row


def _write(path: Path, rows: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def test_token_subset_flag_flags_gold_only_identifier():
    # A code-like identifier present in the query but absent from the issue → flagged.
    leaked = compute_leaked_tokens("call format_datetime to fix it", "the date is wrong")
    assert "format_datetime" in leaked


def test_token_subset_flag_ignores_natural_english_subset():
    # A natural terse query drawn from the issue → no code-like leaked tokens (the
    # near-vacuous property the spec acknowledges).
    leaked = compute_leaked_tokens(
        "the date formatting is wrong", "the date formatting is wrong here"
    )
    assert leaked == ()


def test_token_flag_recomputes_against_joined_source_issue(tmp_path):
    # A code-like identifier absent from the joined astropy issue is flagged; any
    # `leaked_tokens` stored in the terse row is IGNORED (recomputed, never trusted).
    row = _terse_row(
        query="why does _calculate_separability_zz break for nested models",
        leaked_tokens=["totally_fake_stored_value"],
    )
    terse = _write(tmp_path / "terse.jsonl", [row])
    ds = load_terse_dataset(terse, _RAW, _PROV)
    leaked = ds.cases[0].leaked_tokens
    assert "_calculate_separability_zz" in leaked
    assert "totally_fake_stored_value" not in leaked


def test_clean_natural_query_has_no_leaked_tokens(tmp_path):
    terse = _write(tmp_path / "terse.jsonl", [_terse_row()])
    ds = load_terse_dataset(terse, _RAW, _PROV)
    assert ds.cases[0].leaked_tokens == ()


def test_loud_loader_rejects_terse_case_missing_guard_field(tmp_path):
    bad = {k: v for k, v in _terse_row().items() if k != "query_provenance"}
    terse = _write(tmp_path / "terse.jsonl", [bad])
    with pytest.raises(DatasetError):
        load_terse_dataset(terse, _RAW, _PROV)


def test_legacy_and_terse_cases_load_together(tmp_path):
    # AC5 both directions in one loud loader call: a terse case (guard enforced) and a
    # legacy case (no version tag, guard defaulted) both load.
    legacy = {
        "case_id": "legacy1",
        "query": "where is retry backoff",
        "repo": "fixtures/legacy",
        "expected_spans": [{"path": "net/retry.py", "start_line": 1, "end_line": 4}],
        "classification": "point",
    }
    f = _write(tmp_path / "mixed.jsonl", [legacy, _terse_row()])
    cases = load_dataset(f)
    assert len(cases) == 2
    assert cases[0].schema_version is None and cases[0].gold_withheld is False
    assert cases[1].schema_version == DATASET_SCHEMA_VERSION and cases[1].gold_withheld is True
