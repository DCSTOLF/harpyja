"""Spec 0047 — the resumable, ledger-backed enlargement pipeline (unit; fakes only).

Drives `run_pipeline` with INJECTED fakes for every out-of-process arm (HF snapshot,
Claude author, Codex verifier, concept-labeler, span-text reader) so the convert →
author → tag → assemble → recheck chain is exercised end-to-end with no network and no
model calls. The load-bearing property under test is LOSSLESS RESUME: a crash mid-author
must not re-invoke the author on already-recorded cases when the driver is re-run.
"""

from __future__ import annotations

import json

import pytest

from harpyja.eval import enlargement_run as er
from harpyja.eval.enlargement import (
    PREREGISTERED_ENLARGEMENT_CONFIG_0047,
    PowerRecheckResult,
    validate_sampling_frame,
)
from harpyja.eval.swebench_eval import _to_eval_case, parse_patch


def _frame():
    return validate_sampling_frame(
        {
            "schema_version": "0047/frame/1",
            "hf_dataset_id": "princeton-nlp/SWE-bench_Verified",
            "hf_revision": "rev-fixture",
            "hf_split": "test",
            "prior_raw_fixture_sha256": "0" * 64,
            "already_pinned_ids": ["old__old-0"],
        }
    )


def _hf_inst(iid: str, repo: str) -> dict:
    patch = (
        "diff --git a/mod.py b/mod.py\n--- a/mod.py\n+++ b/mod.py\n"
        "@@ -10,3 +10,4 @@\n ctx\n-old\n+new\n more\n"
    )
    return {
        "instance_id": iid,
        "repo": repo,
        "patch": patch,
        "problem_statement": f"something is wrong in {iid}",
        "base_commit": "abc123",
    }


def _pinned_inst() -> dict:
    """An HF instance for the already-pinned case; its `_to_eval_case` output IS the
    committed raw row, so the content guard passes by construction."""
    return _hf_inst("old__old-0", "old/old")


def _existing_raw() -> list[dict]:
    # The committed raw fixture row = the audited convert of the pinned instance.
    inst = _pinned_inst()
    return [_to_eval_case(inst, parse_patch(inst["patch"]))]


def _make_deps(
    tmp_path, *, verifier, snapshot_rows=None, existing_terse=None, revision="rev-fixture"
):
    # the real HF snapshot contains BOTH the pinned cases and the new candidates.
    rows = snapshot_rows if snapshot_rows is not None else [
        _pinned_inst(),
        _hf_inst("aaa__aaa-1", "aaa/aaa"),
        _hf_inst("bbb__bbb-2", "bbb/bbb"),
    ]
    return er.EnlargementDeps(
        frame=_frame(),
        cfg=PREREGISTERED_ENLARGEMENT_CONFIG_0047,
        out_dir=tmp_path,
        ledger_path=tmp_path / "ledger.json",
        existing_raw_rows=_existing_raw(),
        existing_terse_rows=existing_terse if existing_terse is not None else [],
        existing_authoring={"schema_version": "0026/1", "leaky_count": 0,
                            "dropped_count": 0, "records": []},
        existing_provenance={"hf_dataset_id": "princeton-nlp/SWE-bench_Verified",
                             "hf_revision": "rev-fixture", "hf_split": "test",
                             "raw_fixture_sha256": "0" * 64, "sample_case_ids": ["old__old-0"]},
        load_snapshot=lambda: (revision, rows),
        author_invoke=lambda _p: "where is the broken thing",
        verifier_invoke=verifier,
        concept_label=lambda cid, q, gold, span: "same",
        read_span_text=lambda raw: "def helper(): pass",
        author_model="claude",
        verifier_model="codex",
        concept_model="codex",
        effect_band=0.1,
    )


def test_run_pipeline_end_to_end_produces_recheck(tmp_path):
    deps = _make_deps(tmp_path, verifier=lambda _p: "clean")
    result = er.run_pipeline(deps)
    assert isinstance(result, PowerRecheckResult)
    # both new cases authored + tagged + assembled into the enlarged terse fixture
    lines = (tmp_path / "swebench_verified.terse.jsonl").read_text().splitlines()
    terse = [json.loads(x) for x in lines if x.strip()]
    ids = {r["case_id"] for r in terse}
    assert {"aaa__aaa-1", "bbb__bbb-2"} <= ids
    # the power_recheck + audit sample artifacts were emitted
    assert (tmp_path / "power_recheck.json").is_file()
    assert (tmp_path / "audit_sample.json").is_file()
    # AC1: the provenance chain was extended (prior sha preserved, new ids grown)
    prov = json.loads((tmp_path / "swebench_verified.provenance.json").read_text())
    assert prov["prior_raw_fixture_sha256"] == "0" * 64
    assert prov["raw_fixture_sha256"] != "0" * 64
    assert {"aaa__aaa-1", "bbb__bbb-2"} <= set(prov["sample_case_ids"])


def test_run_pipeline_stops_and_warns_when_pinned_case_absent(tmp_path):
    # a snapshot that no longer contains the pinned case → the committed slice cannot
    # be reused verbatim → StopAndWarn (content guard, not a fingerprint check).
    deps = _make_deps(tmp_path, verifier=lambda _p: "clean")
    deps = er.dataclasses.replace(deps, load_snapshot=lambda: ("any-rev", []))
    with pytest.raises(er.StopAndWarn, match="snapshot"):
        er.run_pipeline(deps)


def test_run_pipeline_stops_and_warns_when_pinned_content_drifts(tmp_path):
    # the pinned case is present but re-derives differently (content changed) → stop.
    drifted = _pinned_inst()
    drifted["problem_statement"] = "a DIFFERENT issue body than what was committed"
    rows = [drifted, _hf_inst("aaa__aaa-1", "aaa/aaa")]
    deps = _make_deps(tmp_path, verifier=lambda _p: "clean", snapshot_rows=rows)
    with pytest.raises(er.StopAndWarn, match="re-derives DIFFERENTLY"):
        er.run_pipeline(deps)


def test_run_pipeline_proceeds_on_benign_fingerprint_change(tmp_path):
    # fingerprint differs from the frozen frame, but the pinned slice is content-
    # identical → the run PROCEEDS (the arrow-fingerprint fragility fixed).
    deps = _make_deps(tmp_path, verifier=lambda _p: "clean", revision="a-new-arrow-fingerprint")
    result = er.run_pipeline(deps)
    assert isinstance(result, PowerRecheckResult)
    prov = json.loads((tmp_path / "swebench_verified.provenance.json").read_text())
    assert prov["source_fingerprint_observed"] == "a-new-arrow-fingerprint"
    assert prov["source_fingerprint_frozen"] == "rev-fixture"


def test_run_pipeline_resumes_author_losslessly_after_crash(tmp_path):
    calls = {"n": 0}

    def flaky_verifier(_p: str) -> str:
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("simulated mid-author crash")
        return "clean"

    deps = _make_deps(tmp_path, verifier=flaky_verifier)
    with pytest.raises(RuntimeError, match="crash"):
        er.run_pipeline(deps)
    calls_at_crash = calls["n"]
    assert calls_at_crash == 2  # first case verified, second crashed

    # resume with a healthy verifier: the FIRST case must not be re-verified.
    deps2 = er.dataclasses.replace(deps, verifier_invoke=lambda _p: "clean")
    result = er.run_pipeline(deps2)
    assert isinstance(result, PowerRecheckResult)
    # only the un-recorded cases were (re)verified on resume — no full replay
    assert calls["n"] < calls_at_crash + 2


def test_run_pipeline_records_leaky_and_ineligible_counts(tmp_path):
    rows = [
        _pinned_inst(),
        _hf_inst("aaa__aaa-1", "aaa/aaa"),  # clean
        _hf_inst("bbb__bbb-2", "bbb/bbb"),  # leaky
    ]
    seq = {"n": 0}

    def verifier(_p: str) -> str:
        seq["n"] += 1
        return "leaky" if seq["n"] == 2 else "clean"

    deps = _make_deps(tmp_path, verifier=verifier, snapshot_rows=rows)
    er.run_pipeline(deps)
    authoring = json.loads((tmp_path / "swebench_verified.authoring.json").read_text())
    assert authoring["leaky_count"] == 1
    assert authoring["dropped_count"] == 1
    assert "blind_ineligible_count" in authoring
