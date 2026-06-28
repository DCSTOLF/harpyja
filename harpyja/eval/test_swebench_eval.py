"""Spec 0010 — SWE-bench adapter: pure-data layer (AC1, AC2, AC3, AC4).

Stack-free units: patch parsing, schema reconciliation (`_to_eval_case` round-trips
the real `load_dataset`), classification-by-patch-shape, and new-file exclusion.
No network, no live model — the convert/HF coverage (mocked) lives further down.
"""

from __future__ import annotations

import argparse
import json

import pytest

from harpyja.eval.dataset import EvalCase, load_dataset
from harpyja.eval.swebench_eval import (
    POINT_SPAN_MAX_LINES,
    PROVENANCE_NAME,
    RAW_NAME,
    _build_parser,
    _read_jsonl,
    _to_eval_case,
    classify_by_patch_shape,
    cmd_convert,
    is_new_file_only,
    main,
    parse_patch,
    partition_scorable,
)

# --- sample unified diffs ----------------------------------------------------

SINGLE_HUNK = (
    "diff --git a/foo.py b/foo.py\n"
    "--- a/foo.py\n"
    "+++ b/foo.py\n"
    "@@ -10,5 +10,6 @@ def f():\n"
    " ctx\n"
    "-old\n"
    "+new\n"
)

MULTI_HUNK = (
    "--- a/bar.py\n"
    "+++ b/bar.py\n"
    "@@ -5,2 +5,2 @@\n"
    "-a\n+a2\n"
    "@@ -20,3 +20,4 @@\n"
    "-b\n+b2\n"
)

DELETION = (  # whole file deleted: pre-image path is locatable
    "--- a/del.py\n"
    "+++ /dev/null\n"
    "@@ -1,4 +0,0 @@\n"
    "-x\n-y\n-z\n-w\n"
)

NEW_FILE = (  # pre-image is /dev/null: no locatable position
    "--- /dev/null\n"
    "+++ b/new.py\n"
    "@@ -0,0 +1,5 @@\n"
    "+1\n+2\n+3\n+4\n+5\n"
)

PURE_INSERTION_EXISTING = (  # insertion into an existing file (pre-image len 0)
    "--- a/ins.py\n"
    "+++ b/ins.py\n"
    "@@ -10,0 +11,3 @@\n"
    "+p\n+q\n+r\n"
)

MULTI_FILE = (
    "--- a/one.py\n+++ b/one.py\n@@ -1,2 +1,2 @@\n-a\n+a2\n"
    "--- a/two.py\n+++ b/two.py\n@@ -3,2 +3,2 @@\n-b\n+b2\n"
)

BIG_SINGLE_FILE = (  # single file, span far larger than POINT_SPAN_MAX_LINES
    "--- a/big.py\n+++ b/big.py\n@@ -1,80 +1,80 @@\n-a\n+a2\n"
)

NO_TARGETS = "this text is not a unified diff at all\n"


def _instance(patch: str, **over) -> dict:
    base = {
        "instance_id": "proj__proj-1",
        "problem_statement": "the widget throws when frobnicating",
        "repo": "proj/proj",
        "base_commit": "deadbeefcafe1234",
        "patch": patch,
    }
    base.update(over)
    return base


# --- AC1: parse_patch --------------------------------------------------------

def test_parse_patch_single_hunk_preimage_range():
    targets = parse_patch(SINGLE_HUNK)
    assert len(targets) == 1
    assert targets[0].path == "foo.py"
    assert targets[0].is_new_file is False
    assert targets[0].spans == [(10, 14)]  # start=10, length=5 → 10..14


def test_parse_patch_multi_hunk_ranges():
    targets = parse_patch(MULTI_HUNK)
    assert len(targets) == 1
    assert targets[0].path == "bar.py"
    assert targets[0].spans == [(5, 6), (20, 22)]


def test_parse_patch_deletion_locatable_at_preimage_path():
    targets = parse_patch(DELETION)
    assert len(targets) == 1
    assert targets[0].path == "del.py"
    assert targets[0].is_new_file is False
    assert targets[0].spans == [(1, 4)]


def test_parse_patch_all_new_file_flagged_is_new_file_no_spans():
    targets = parse_patch(NEW_FILE)
    assert len(targets) == 1
    assert targets[0].path == "new.py"
    assert targets[0].is_new_file is True
    assert targets[0].spans == []


def test_parse_patch_pure_insertion_in_existing_file_anchored_one_line():
    targets = parse_patch(PURE_INSERTION_EXISTING)
    assert len(targets) == 1
    assert targets[0].path == "ins.py"
    assert targets[0].is_new_file is False
    assert targets[0].spans == [(10, 10)]  # zero-length pre-image → 1-line anchor


def test_parse_patch_unparseable_returns_no_targets():
    # parse_patch never raises across the set; an unparseable patch yields no
    # targets, which convert counts as a loud skip (tested at the convert layer).
    assert parse_patch(NO_TARGETS) == []


# --- AC2: _to_eval_case round-trips the REAL loader --------------------------

def test_to_eval_case_roundtrips_through_load_dataset(tmp_path):
    inst = _instance(SINGLE_HUNK)
    rec = _to_eval_case(inst, parse_patch(inst["patch"]))
    fixture = tmp_path / "one.jsonl"
    fixture.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    cases = load_dataset(fixture)  # must NOT raise DatasetError
    assert len(cases) == 1
    assert isinstance(cases[0], EvalCase)


def test_to_eval_case_emits_case_id_and_expected_spans_list_of_objects():
    inst = _instance(SINGLE_HUNK)
    rec = _to_eval_case(inst, parse_patch(inst["patch"]))
    assert rec["case_id"] == "proj__proj-1"
    assert "id" not in rec  # the upload's wrong key is gone
    assert isinstance(rec["expected_spans"], list)
    assert rec["expected_spans"][0] == {
        "path": "foo.py",
        "start_line": 10,
        "end_line": 14,
    }


def test_to_eval_case_classification_in_point_broad():
    rec = _to_eval_case(_instance(SINGLE_HUNK), parse_patch(SINGLE_HUNK))
    assert rec["classification"] in {"point", "broad"}


def test_base_commit_in_raw_read_by_read_jsonl_but_absent_from_eval_case(tmp_path):
    inst = _instance(SINGLE_HUNK)
    rec = _to_eval_case(inst, parse_patch(inst["patch"]))
    assert rec["base_commit"] == "deadbeefcafe1234"  # lives in the RAW record
    fixture = tmp_path / "one.jsonl"
    fixture.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    # provision reads base_commit from the raw dict directly …
    raw = _read_jsonl(fixture)
    assert raw[0]["base_commit"] == "deadbeefcafe1234"
    # … while load_dataset ignores the extra key (EvalCase has no such field).
    case = load_dataset(fixture)[0]
    assert not hasattr(case, "base_commit")


# --- AC3: classification by patch shape --------------------------------------

def test_classify_single_file_small_span_is_point():
    assert classify_by_patch_shape(parse_patch(SINGLE_HUNK)) == "point"


def test_classify_multi_file_is_broad():
    assert classify_by_patch_shape(parse_patch(MULTI_FILE)) == "broad"


def test_classify_single_file_over_threshold_span_is_broad():
    assert classify_by_patch_shape(parse_patch(BIG_SINGLE_FILE)) == "broad"


def test_point_span_threshold_constant_boundary():
    at = parse_patch(f"--- a/b.py\n+++ b/b.py\n@@ -1,{POINT_SPAN_MAX_LINES} +1,1 @@\n-x\n")
    over = parse_patch(
        f"--- a/b.py\n+++ b/b.py\n@@ -1,{POINT_SPAN_MAX_LINES + 1} +1,1 @@\n-x\n"
    )
    assert classify_by_patch_shape(at) == "point"   # exactly at the bar
    assert classify_by_patch_shape(over) == "broad"  # one line past it


# --- AC4: new-file exclusion -------------------------------------------------

def test_all_new_file_instance_flagged_new_file_only():
    rec = _to_eval_case(_instance(NEW_FILE), parse_patch(NEW_FILE))
    assert rec["new_file_only"] is True
    assert rec["expected_spans"] == []  # nothing locatable


def test_mixed_targets_not_new_file_only():
    assert is_new_file_only(parse_patch(DELETION)) is False


def test_partition_scorable_excludes_new_file_only_and_counts_it():
    rows = [
        _to_eval_case(_instance(SINGLE_HUNK, instance_id="a"), parse_patch(SINGLE_HUNK)),
        _to_eval_case(_instance(NEW_FILE, instance_id="b"), parse_patch(NEW_FILE)),
    ]
    scorable, excluded = partition_scorable(rows)
    assert [r["case_id"] for r in scorable] == ["a"]
    assert excluded == 1  # surfaced count, never a silent zero


# --- AC8: convert over MOCKED HuggingFace (no network) + provenance ----------

class _FakeDS:
    """Stand-in for a HuggingFace dataset split: iterable rows + a fingerprint."""

    _fingerprint = "fp-abc123"

    def __init__(self, rows):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)


def _fake_instances():
    return [
        _instance(SINGLE_HUNK, instance_id="a__a-1", repo="a/a", base_commit="c1"),
        _instance(NEW_FILE, instance_id="b__b-2", repo="b/b", base_commit="c2"),
        _instance(NO_TARGETS, instance_id="c__c-3", repo="c/c", base_commit="c3"),
    ]


def _convert_args(out_dir):
    return argparse.Namespace(
        out_dir=str(out_dir), sample=0, per_repo=None, seed=0, verbose=False
    )


def test_convert_with_mocked_hf_emits_raw_jsonl(tmp_path, monkeypatch):
    import datasets

    monkeypatch.setattr(datasets, "load_dataset", lambda name, split: _FakeDS(_fake_instances()))
    cmd_convert(_convert_args(tmp_path))
    rows = _read_jsonl(tmp_path / RAW_NAME)
    ids = {r["case_id"] for r in rows}
    assert {"a__a-1", "b__b-2"} <= ids
    assert "c__c-3" not in ids  # no parseable targets → skipped, not written


def test_convert_records_provenance_and_counts(tmp_path, monkeypatch):
    import datasets

    monkeypatch.setattr(datasets, "load_dataset", lambda name, split: _FakeDS(_fake_instances()))
    cmd_convert(_convert_args(tmp_path))
    prov = json.loads((tmp_path / PROVENANCE_NAME).read_text(encoding="utf-8"))
    assert prov["hf_dataset_id"] == "princeton-nlp/SWE-bench_Verified"
    assert prov["hf_split"] == "test"
    assert prov["hf_revision"] == "fp-abc123"
    assert len(prov["raw_fixture_sha256"]) == 64
    assert set(prov["sample_case_ids"]) == {"a__a-1", "b__b-2"}
    assert prov["malformed_skipped_count"] == 1       # c had no targets
    assert prov["new_file_only_excluded_count"] == 1  # b is new_file_only


# --- AC9: run / sweep CLI subcommands + missing-fixture guard ----------------

def test_run_subcommand_parses():
    args = _build_parser().parse_args(["run", "--fixtures", "x", "--out-dir", "y"])
    assert args.cmd == "run"


def test_settings_from_args_applies_model_overrides():
    from harpyja.eval.swebench_eval import _settings_from_args

    args = _build_parser().parse_args([
        "run", "--lm-model", "qwen2.5-coder:3b",
        "--lm-api-base", "http://127.0.0.1:11434/v1", "--deep-max-subqueries", "1",
    ])
    s = _settings_from_args(args)
    assert s.lm_model == "qwen2.5-coder:3b"
    assert s.lm_api_base == "http://127.0.0.1:11434/v1"
    assert s.deep_max_subqueries == 1


def test_settings_from_args_defaults_unchanged_without_flags():
    from harpyja.config.settings import Settings
    from harpyja.eval.swebench_eval import _settings_from_args

    args = _build_parser().parse_args(["run", "--fixtures", "x"])
    assert _settings_from_args(args).lm_model == Settings().lm_model


def test_sweep_subcommand_parses():
    args = _build_parser().parse_args(["sweep", "--fixtures", "x", "--out-dir", "y"])
    assert args.cmd == "sweep"


def test_run_missing_resolved_fixture_exits_nonzero_actionable(tmp_path):
    with pytest.raises(SystemExit) as ei:
        main(["run", "--fixtures", str(tmp_path), "--out-dir", str(tmp_path / "out")])
    assert ei.value.code != 0
    assert "provision" in str(ei.value.code).lower()


def test_sweep_missing_resolved_fixture_exits_nonzero_actionable(tmp_path):
    with pytest.raises(SystemExit) as ei:
        main(["sweep", "--fixtures", str(tmp_path), "--out-dir", str(tmp_path / "out")])
    assert ei.value.code != 0
    assert "provision" in str(ei.value.code).lower()


# --- AC9: root Makefile targets (reconciled to the real subcommands) ---------

def _repo_root():
    from pathlib import Path

    return Path(__file__).resolve().parents[2]


def _makefile_text():
    return (_repo_root() / "Makefile").read_text(encoding="utf-8")


def _make_expand(target):
    """Expand a target's recipe via `make -n` (resolves the $(EVAL) variable)."""
    import subprocess

    out = subprocess.run(
        ["make", "-n", target], cwd=_repo_root(), capture_output=True, text=True
    )
    return out.stdout


def test_makefile_run_target_invokes_swebench_eval_run():
    assert "swebench_eval run" in _make_expand("swebench-run")


def test_makefile_sweep_target_invokes_swebench_eval_sweep():
    assert "swebench_eval sweep" in _make_expand("swebench-sweep")


def test_makefile_does_not_reference_runner_fixture_placeholder():
    # the upload's nonexistent CLI must be gone after reconciliation
    assert "harpyja.eval.runner --fixture" not in _makefile_text()
    assert "harpyja.eval.sweep --fixture" not in _makefile_text()
