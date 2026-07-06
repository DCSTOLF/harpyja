"""AC1 — dataset loader parses the fixture format; rejects malformed cases loudly."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harpyja.eval.dataset import (
    DATASET_SCHEMA_VERSION,
    DatasetError,
    EvalCase,
    load_dataset,
)


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


_VALID_ROW = {
    "case_id": "c1",
    "query": "where is the retry backoff computed",
    "repo": "fixtures/legacy",
    "expected_spans": [{"path": "net/retry.py", "start_line": 10, "end_line": 20}],
    "classification": "point",
}


def test_load_dataset_parses_valid_fixture(tmp_path):
    f = _write_jsonl(
        tmp_path / "seed.jsonl",
        [
            _VALID_ROW,
            {
                "case_id": "c2",
                "query": "how does auth flow work end to end",
                "repo": "fixtures/legacy",
                "expected_spans": [
                    {"path": "auth/login.py", "start_line": 5, "end_line": 9},
                    {"path": "auth/session.py", "start_line": 40, "end_line": 60},
                ],
                "classification": "broad",
            },
        ],
    )
    cases = load_dataset(f)
    assert len(cases) == 2
    assert all(isinstance(c, EvalCase) for c in cases)
    c1 = cases[0]
    assert c1.case_id == "c1"
    assert c1.query.startswith("where is")
    assert c1.classification == "point"
    assert c1.expected_spans[0].path == "net/retry.py"
    assert c1.expected_spans[0].start_line == 10
    assert c1.expected_spans[0].end_line == 20
    assert len(cases[1].expected_spans) == 2


def test_load_dataset_rejects_missing_expected_span(tmp_path):
    bad = {k: v for k, v in _VALID_ROW.items() if k != "expected_spans"}
    f = _write_jsonl(tmp_path / "bad.jsonl", [bad])
    with pytest.raises(DatasetError):
        load_dataset(f)


def test_load_dataset_rejects_empty_expected_spans(tmp_path):
    bad = {**_VALID_ROW, "expected_spans": []}
    f = _write_jsonl(tmp_path / "bad.jsonl", [bad])
    with pytest.raises(DatasetError):
        load_dataset(f)


def test_load_dataset_rejects_unknown_classification_label(tmp_path):
    bad = {**_VALID_ROW, "classification": "fuzzy"}
    f = _write_jsonl(tmp_path / "bad.jsonl", [bad])
    with pytest.raises(DatasetError):
        load_dataset(f)


def test_load_dataset_raises_typed_error_never_silent_skip(tmp_path):
    # One good row, one malformed (bad JSON). A silent skip would yield 1 case;
    # the contract is a loud raise, never a dropped row.
    f = tmp_path / "mixed.jsonl"
    f.write_text(json.dumps(_VALID_ROW) + "\n" + "{not json}\n", encoding="utf-8")
    with pytest.raises(DatasetError):
        load_dataset(f)


def test_load_dataset_rejects_non_integer_line(tmp_path):
    bad = {
        **_VALID_ROW,
        "expected_spans": [{"path": "a.py", "start_line": "x", "end_line": 20}],
    }
    f = _write_jsonl(tmp_path / "bad.jsonl", [bad])
    with pytest.raises(DatasetError):
        load_dataset(f)


def test_load_dataset_rejects_inverted_line_range(tmp_path):
    bad = {
        **_VALID_ROW,
        "expected_spans": [{"path": "a.py", "start_line": 30, "end_line": 10}],
    }
    f = _write_jsonl(tmp_path / "bad.jsonl", [bad])
    with pytest.raises(DatasetError):
        load_dataset(f)


# --- spec 0026: schema-version-gated terse guard fields (AC3/AC5) ---------------

# A terse-schema (0026) row: tagged with schema_version, carries the guard fields,
# and OMITS expected_spans (they are joined by case_id from the pinned raw fixture).
_TERSE_ROW = {
    "schema_version": DATASET_SCHEMA_VERSION,
    "case_id": "astropy__astropy-12907",
    "query": "nested compound models report wrong separability",
    "repo": "astropy/astropy",
    "classification": "point",
    "gold_withheld": True,
    "query_provenance": "model-authored-blind",
    "classification_provenance": "hand-labeled-by-intent",
}


def test_dataset_schema_version_constant_exists():
    # A NEW constant is introduced (there is none today); it is not report.SCHEMA_VERSION.
    assert DATASET_SCHEMA_VERSION == "0026/1"


def test_parse_case_terse_schema_requires_guard_fields(tmp_path):
    bad = {k: v for k, v in _TERSE_ROW.items() if k != "query_provenance"}
    f = _write_jsonl(tmp_path / "terse.jsonl", [bad])
    with pytest.raises(DatasetError):
        load_dataset(f)


def test_parse_case_terse_schema_requires_gold_withheld(tmp_path):
    bad = {k: v for k, v in _TERSE_ROW.items() if k != "gold_withheld"}
    f = _write_jsonl(tmp_path / "terse.jsonl", [bad])
    with pytest.raises(DatasetError):
        load_dataset(f)


def test_parse_case_terse_schema_omits_spans_ok(tmp_path):
    # A terse row with NO expected_spans loads (spans are joined later); the guard
    # fields come back populated, expected_spans defaults empty.
    f = _write_jsonl(tmp_path / "terse.jsonl", [_TERSE_ROW])
    cases = load_dataset(f)
    assert len(cases) == 1
    c = cases[0]
    assert c.schema_version == DATASET_SCHEMA_VERSION
    assert c.expected_spans == ()
    assert c.gold_withheld is True
    assert c.query_provenance == "model-authored-blind"
    assert c.classification_provenance == "hand-labeled-by-intent"


def test_legacy_row_without_version_still_requires_spans(tmp_path):
    # The gate is version-scoped: a LEGACY row (no schema_version) with no spans
    # still raises — only terse-schema rows may omit spans.
    bad = {k: v for k, v in _VALID_ROW.items() if k != "expected_spans"}
    f = _write_jsonl(tmp_path / "legacy.jsonl", [bad])
    with pytest.raises(DatasetError):
        load_dataset(f)


def test_parse_case_legacy_no_version_tag_loads_with_defaults(tmp_path):
    # An existing seed/legacy row loads unchanged; the new guard fields read back
    # as their defaults (additive last-with-defaults, backward-compat).
    f = _write_jsonl(tmp_path / "legacy.jsonl", [_VALID_ROW])
    cases = load_dataset(f)
    c = cases[0]
    assert c.case_id == "c1"
    assert c.schema_version is None
    assert c.gold_withheld is False
    assert c.query_provenance is None
    assert c.leaked_tokens == ()
    assert c.classification_provenance is None
    assert c.label_provenance is None
