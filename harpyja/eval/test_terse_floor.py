"""spec 0026 AC3/AC4 — classification-by-intent provenance, labeled excluded-count
(known-correct-span-only, never a silent drop), and the size/pairing floor citing the
committed benchmark_fit constants across multiple repos."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from harpyja.eval.benchmark_fit import PREREGISTERED_CONFIG
from harpyja.eval.dataset import DATASET_SCHEMA_VERSION, EvalCase, ExpectedSpan
from harpyja.eval.terse_dataset import (
    TerseDataset,
    load_terse_dataset,
    validate_terse_set_floor,
)

_FIX = Path(__file__).parent / "fixtures"
_RAW = _FIX / "swebench_verified.raw.jsonl"
_PROV = _FIX / "swebench_verified.provenance.json"


def _terse_row(case_id="astropy__astropy-12907", **over) -> dict:
    row = {
        "schema_version": DATASET_SCHEMA_VERSION,
        "case_id": case_id,
        "query": "nested compound models report wrong separability",
        "repo": "astropy/astropy",
        "classification": "point",
        "gold_withheld": True,
        "query_provenance": "model-authored-blind",
    }
    row.update(over)
    return row


def _case(cid: str, repo: str) -> EvalCase:
    return EvalCase(
        case_id=cid,
        query="q",
        repo=repo,
        expected_spans=(ExpectedSpan(path="a.py", start_line=1, end_line=2),),
        classification="point",
        schema_version=DATASET_SCHEMA_VERSION,
        gold_withheld=True,
        query_provenance="model-authored-blind",
        classification_provenance="hand-labeled-by-intent",
    )


def _ds(cases: list[EvalCase]) -> TerseDataset:
    return TerseDataset(cases=cases, join_meta={}, excluded_count=0, excluded_case_ids=())


def test_classification_provenance_is_hand_labeled_by_intent(tmp_path):
    # Even when the terse row omits it, the join stamps the intent-label provenance.
    terse = tmp_path / "terse.jsonl"
    terse.write_text(json.dumps(_terse_row()) + "\n", encoding="utf-8")
    ds = load_terse_dataset(terse, _RAW, _PROV)
    assert ds.cases[0].classification_provenance == "hand-labeled-by-intent"


def test_excluded_count_is_labeled_field_not_silent_drop(tmp_path):
    # Build a tiny raw fixture with one span-less case (no locatable target) and one
    # good case; a matching provenance pin. The span-less case is EXCLUDED and counted.
    raw = tmp_path / "raw.jsonl"
    good = {
        "case_id": "good__1",
        "query": "issue text one",
        "repo": "x/y",
        "expected_spans": [{"path": "a.py", "start_line": 1, "end_line": 2}],
        "base_commit": "c0",
    }
    empty = {
        "case_id": "empty__1",
        "query": "issue text two",
        "repo": "x/y",
        "expected_spans": [],
        "base_commit": "c1",
    }
    raw.write_text(json.dumps(good) + "\n" + json.dumps(empty) + "\n", encoding="utf-8")
    prov = tmp_path / "prov.json"
    sha = hashlib.sha256(raw.read_bytes()).hexdigest()
    prov.write_text(json.dumps({"raw_fixture_sha256": sha}), encoding="utf-8")

    terse = tmp_path / "terse.jsonl"
    terse.write_text(
        json.dumps(_terse_row(case_id="good__1", repo="x/y"))
        + "\n"
        + json.dumps(_terse_row(case_id="empty__1", repo="x/y"))
        + "\n",
        encoding="utf-8",
    )
    ds = load_terse_dataset(terse, raw, prov)
    assert len(ds.cases) == 1 and ds.cases[0].case_id == "good__1"
    assert ds.excluded_count == 1
    assert "empty__1" in ds.excluded_case_ids


def test_terse_floor_cites_committed_constants():
    cases = [_case(f"c{i}", repo=["x/a", "x/b", "x/c"][i % 3]) for i in range(12)]
    result = validate_terse_set_floor(_ds(cases))
    assert result.min_n == PREREGISTERED_CONFIG.min_n == 12
    assert result.discordant_floor == PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS == 8
    assert result.ok


def test_terse_floor_fails_below_min_n():
    cases = [_case(f"c{i}", repo=["x/a", "x/b"][i % 2]) for i in range(11)]
    result = validate_terse_set_floor(_ds(cases))
    assert not result.ok
    assert result.usable_n == 11


def test_terse_floor_requires_multiple_repos():
    single = [_case(f"c{i}", repo="only/repo") for i in range(12)]
    assert not validate_terse_set_floor(_ds(single)).ok

    multi = [_case(f"c{i}", repo=["x/a", "x/b", "x/c"][i % 3]) for i in range(12)]
    assert validate_terse_set_floor(_ds(multi)).ok
