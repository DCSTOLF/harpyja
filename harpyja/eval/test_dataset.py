"""AC1 — dataset loader parses the fixture format; rejects malformed cases loudly."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harpyja.eval.dataset import DatasetError, EvalCase, load_dataset


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
