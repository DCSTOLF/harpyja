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


# --- spec 0036 AC7/OQ3: full-set target + conceptual-stratum reportability -------


def _tagged_case(cid: str, repo: str, reachability: str) -> EvalCase:
    return EvalCase(
        case_id=cid,
        query="q",
        repo=repo,
        expected_spans=(ExpectedSpan(path="a.py", start_line=1, end_line=2),),
        classification="point",
        schema_version="0036/1",
        gold_withheld=True,
        query_provenance="model-authored-blind",
        classification_provenance="hand-labeled-by-intent",
        reachability=reachability,
        reachability_provenance="mechanical",
        concept_patch_relation="same",
    )


def test_full_set_meets_frozen_full_n_target():
    # The static min_n=12 floor is NOT the representative-set size gate: the full
    # set must ALSO clear the governing frozen config's full_n_target (30).
    from harpyja.eval.ac8_pilot import PREREGISTERED_AC8_CONFIG
    from harpyja.eval.terse_dataset import meets_full_n_target

    repos = ["x/a", "x/b", "x/c"]
    thirty = [_tagged_case(f"c{i}", repos[i % 3], "lexical") for i in range(30)]
    twelve = [_tagged_case(f"c{i}", repos[i % 3], "lexical") for i in range(12)]
    assert meets_full_n_target(_ds(thirty), PREREGISTERED_AC8_CONFIG) is True
    assert meets_full_n_target(_ds(twelve), PREREGISTERED_AC8_CONFIG) is False


def test_conceptual_stratum_reportability_floor():
    # OQ3's PRE-DECLARED floor: the conceptual stratum must hold >= 5 cases for the
    # axis to be reported as a split; below that it is UNDER_POPULATED — a typed
    # finding, never a silent merge into the aggregate.
    from harpyja.eval.terse_dataset import (
        STRATUM_REPORTABLE,
        STRATUM_UNDER_POPULATED,
        conceptual_stratum_report,
    )

    repos = ["x/a", "x/b", "x/c"]

    def _mix(conceptual_n: int, total: int) -> list[EvalCase]:
        return [
            _tagged_case(
                f"c{i}", repos[i % 3], "conceptual" if i < conceptual_n else "lexical"
            )
            for i in range(total)
        ]

    lex_n, con_n, status = conceptual_stratum_report(_ds(_mix(5, 30)))
    assert (lex_n, con_n, status) == (25, 5, STRATUM_REPORTABLE)

    lex_n, con_n, status = conceptual_stratum_report(_ds(_mix(4, 30)))
    assert (lex_n, con_n, status) == (26, 4, STRATUM_UNDER_POPULATED)


def test_committed_pilot_fixture_is_tagged_and_stratum_reported():
    # spec 0036: the COMMITTED fixture (the real pilot set) loads through the loud
    # loader with every case tagged; the pilot-sized conceptual-stratum report is
    # computed and PRINTED (its status is a typed finding either way — an
    # UNDER_POPULATED pilot stratum is honest data, not a test failure). The
    # min_n=12 static floor is the FULL set's gate, deliberately not asserted here.
    from harpyja.eval.terse_dataset import conceptual_stratum_report

    ds = load_terse_dataset(
        Path(__file__).parent / "fixtures" / "swebench_verified.terse.jsonl", _RAW, _PROV
    )
    assert ds.cases, "committed fixture joined to zero cases"
    assert all(c.reachability in {"lexical", "conceptual"} for c in ds.cases)
    lex_n, con_n, status = conceptual_stratum_report(ds, pilot_sized=True)
    assert lex_n + con_n == len(ds.cases)  # every case carries the tag
    print(
        f"\n[0036 pilot stratum] lexical={lex_n} conceptual={con_n} status={status}"
    )


def test_committed_full_set_report_matches_computed_truth():
    # spec 0036 T20/T21: the committed full_set_report.json must EQUAL what the
    # helpers compute from the committed fixture — the recorded claim can never
    # drift from the data (no-false-capability). The static floor must pass; the
    # frozen full_n_target status is recorded HONESTLY (the 50-case raw pool
    # exhausted below 30 — a finding, not a hidden shortfall), and the
    # representative-at-frozen-target claim is NOT made while it reads false.
    from harpyja.eval.ac8_pilot import PREREGISTERED_AC8_CONFIG_0036
    from harpyja.eval.terse_dataset import conceptual_stratum_report, meets_full_n_target

    report_path = (
        Path(__file__).resolve().parents[2]
        / "specs" / "0036-terse-query" / "full_set_report.json"
    )
    assert report_path.exists(), "full_set_report.json not committed"
    report = json.loads(report_path.read_text())

    ds = load_terse_dataset(
        Path(__file__).parent / "fixtures" / "swebench_verified.terse.jsonl", _RAW, _PROV
    )
    floor = validate_terse_set_floor(ds)
    lex_n, con_n, status = conceptual_stratum_report(ds)
    target_met = meets_full_n_target(ds, PREREGISTERED_AC8_CONFIG_0036)

    assert report["usable_n"] == floor.usable_n == len(ds.cases)
    assert report["num_repos"] == floor.num_repos
    assert report["floor_ok"] == floor.ok is True
    assert report["lexical_n"] == lex_n
    assert report["conceptual_n"] == con_n
    assert report["stratum_status"] == status
    assert report["full_n_target"] == PREREGISTERED_AC8_CONFIG_0036.full_n_target
    assert report["meets_full_n_target"] == target_met
    assert (
        report["representative_at_frozen_target"] is target_met
    ), "the representativeness claim must track the computed target status exactly"


def test_conceptual_stratum_pilot_floor_is_two():
    # The pilot-sized floor (>= 2) — pre-declared alongside the full-set floor.
    from harpyja.eval.terse_dataset import (
        STRATUM_REPORTABLE,
        STRATUM_UNDER_POPULATED,
        conceptual_stratum_report,
    )

    repos = ["x/a", "x/b"]
    pilot = [
        _tagged_case(f"c{i}", repos[i % 2], "conceptual" if i < 2 else "lexical")
        for i in range(10)
    ]
    _, con_n, status = conceptual_stratum_report(_ds(pilot), pilot_sized=True)
    assert (con_n, status) == (2, STRATUM_REPORTABLE)

    thin = [
        _tagged_case(f"c{i}", repos[i % 2], "conceptual" if i < 1 else "lexical")
        for i in range(10)
    ]
    _, con_n, status = conceptual_stratum_report(_ds(thin), pilot_sized=True)
    assert (con_n, status) == (1, STRATUM_UNDER_POPULATED)
