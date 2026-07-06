"""spec 0026 AC1 — terse cases JOIN their spans by case_id from the sha256-pinned
raw fixture; the pin is asserted BEFORE the join and no span is second-transcribed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harpyja.eval.dataset import DATASET_SCHEMA_VERSION, DatasetError
from harpyja.eval.terse_dataset import load_terse_dataset

_FIX = Path(__file__).parent / "fixtures"
_RAW = _FIX / "swebench_verified.raw.jsonl"
_PROV = _FIX / "swebench_verified.provenance.json"

# A real case in the committed pinned raw fixture (verified span:
# astropy/modeling/separable.py 242-248).
_CASE = "astropy__astropy-12907"


def _terse_row(case_id: str, **over) -> dict:
    row = {
        "schema_version": DATASET_SCHEMA_VERSION,
        "case_id": case_id,
        "query": "nested compound models report the wrong separability matrix",
        "repo": "astropy/astropy",
        "classification": "point",
        "gold_withheld": True,
        "query_provenance": "model-authored-blind",
        "classification_provenance": "hand-labeled-by-intent",
    }
    row.update(over)
    return row


def _write_terse(path: Path, rows: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def test_terse_load_asserts_raw_pin_before_join(tmp_path):
    # A tampered raw fixture (bytes no longer match provenance sha) must raise BEFORE
    # any join, even though the referenced case_id would otherwise resolve.
    tampered = tmp_path / "swebench_verified.raw.jsonl"
    tampered.write_bytes(_RAW.read_bytes() + b" ")  # one byte → sha mismatch
    terse = _write_terse(tmp_path / "terse.jsonl", [_terse_row(_CASE)])
    with pytest.raises(DatasetError):
        load_terse_dataset(terse, tampered, _PROV)


def test_terse_case_joins_spans_from_raw_by_case_id(tmp_path):
    terse = _write_terse(tmp_path / "terse.jsonl", [_terse_row(_CASE)])
    # The terse file itself carries NO expected_spans (no second transcription).
    assert all("expected_spans" not in r for r in [_terse_row(_CASE)])
    ds = load_terse_dataset(terse, _RAW, _PROV)
    assert len(ds.cases) == 1
    c = ds.cases[0]
    assert c.case_id == _CASE
    assert c.expected_spans  # populated by the join
    assert c.expected_spans[0].path == "astropy/modeling/separable.py"
    assert c.expected_spans[0].start_line == 242
    assert c.expected_spans[0].end_line == 248


def test_terse_join_exposes_base_commit_and_source_issue(tmp_path):
    terse = _write_terse(tmp_path / "terse.jsonl", [_terse_row(_CASE)])
    ds = load_terse_dataset(terse, _RAW, _PROV)
    meta = ds.join_meta[_CASE]
    assert meta.base_commit == "d16bfe05a744909de4b27f5875fe0d4ed41ce607"
    # source issue = the raw `query` (the SWE-bench problem_statement)
    assert "separability_matrix" in meta.source_issue
    # base_commit is NOT promoted onto EvalCase (review B2 — stays a raw-record key)
    assert not hasattr(ds.cases[0], "base_commit")


def test_terse_case_id_absent_in_raw_raises(tmp_path):
    terse = _write_terse(tmp_path / "terse.jsonl", [_terse_row("nonexistent__case-999")])
    with pytest.raises(DatasetError):
        load_terse_dataset(terse, _RAW, _PROV)


def test_terse_label_provenance_is_patch_derived_at_convert(tmp_path):
    terse = _write_terse(tmp_path / "terse.jsonl", [_terse_row(_CASE)])
    ds = load_terse_dataset(terse, _RAW, _PROV)
    assert ds.cases[0].label_provenance == "patch-derived-at-convert"
