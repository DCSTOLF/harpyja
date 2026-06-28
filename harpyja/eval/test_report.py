"""AC4/AC7 / D7 — pinned report schema, validation, artifact-outside-repo guard."""

from __future__ import annotations

import json

import pytest

from harpyja.eval.report import (
    SCHEMA_VERSION,
    ReportSchemaError,
    build_report,
    validate_report,
    write_report,
)


def _run_metadata(**over):
    base = {
        "repo_revision": "abc123",
        "seed_n": 2,
        "n_floor": 30,
        "indicative_only": True,
        "mode": "auto",
        "k_runs": 1,
        "settings_snapshot": {
            "verify_method": "scout_model",
            "verify_threshold": 0.6,
            "verify_top_n": 3,
        },
        "timestamp": "2026-06-28T00:00:00Z",
        "artifact_dir": "/tmp/out",
    }
    base.update(over)
    return base


def _case(**over):
    base = {
        "case_id": "c1",
        "query": "where is X",
        "classification": "point",
        "expected_spans": [{"path": "a.py", "start_line": 10, "end_line": 20}],
        "citations": [
            {"path": "a.py", "start_line": 12, "end_line": 18, "source_tier": 1, "score": 0.9}
        ],
        "tiers_run": [0, 1],
        "terminal_tier": 1,
        "escalated_to_deep": False,
        "gate_eligible": True,
        "gate_triggered": True,
        "tier1_correct": True,
        "span_hit_primary": True,
        "span_hit_secondary": True,
        "notes": None,
    }
    base.update(over)
    return base


def _aggregate(**over):
    base = {
        "span_hit_rate_primary": 1.0,
        "span_hit_rate_secondary": 1.0,
        "escalation_rate": 0.0,
        "tier01_resolve_rate": 1.0,
        "gate_catch_rate": None,
        "caught_count": 0,
        "wrong_tier1_count": 0,
        "gate_false_escalation": 0.0,
        "false_escalated_count": 0,
        "correct_tier1_count": 1,
        "per_tier_latency_ms": {"0": 1.0, "1": 5.0},
        "per_tier_model_calls": {"0": 0, "1": 1},
    }
    base.update(over)
    return base


def test_report_top_level_fields_present():
    rep = build_report(_run_metadata(), [_case()], _aggregate())
    assert rep["schema_version"] == SCHEMA_VERSION
    for key in ("schema_version", "run_metadata", "cases", "aggregate"):
        assert key in rep


def test_report_conforms_to_pinned_schema():
    rep = build_report(_run_metadata(), [_case()], _aggregate())
    validate_report(rep)  # must not raise


def test_validate_report_rejects_missing_top_level_field():
    rep = build_report(_run_metadata(), [_case()], _aggregate())
    del rep["aggregate"]
    with pytest.raises(ReportSchemaError):
        validate_report(rep)


def test_validate_report_rejects_missing_aggregate_field():
    agg = _aggregate()
    del agg["escalation_rate"]
    rep = build_report(_run_metadata(), [_case()], agg)
    with pytest.raises(ReportSchemaError):
        validate_report(rep)


def test_validate_report_rejects_missing_case_field():
    case = _case()
    del case["tiers_run"]
    rep = build_report(_run_metadata(), [case], _aggregate())
    with pytest.raises(ReportSchemaError):
        validate_report(rep)


def test_report_undefined_metric_serialized_as_null_with_count():
    rep = build_report(
        _run_metadata(),
        [_case()],
        _aggregate(gate_catch_rate=None, wrong_tier1_count=0),
    )
    s = json.dumps(rep)
    back = json.loads(s)
    assert back["aggregate"]["gate_catch_rate"] is None
    assert back["aggregate"]["wrong_tier1_count"] == 0


def test_artifact_dir_must_be_outside_indexed_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    inside = repo / ".harpyja" / "eval"
    rep = build_report(_run_metadata(), [_case()], _aggregate())
    with pytest.raises(ValueError):
        write_report(rep, out_dir=inside, repo_path=repo)


def test_write_report_outside_repo_succeeds(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    out = tmp_path / "eval-out"
    rep = build_report(_run_metadata(), [_case()], _aggregate())
    written = write_report(rep, out_dir=out, repo_path=repo)
    assert written.exists()
    back = json.loads(written.read_text(encoding="utf-8"))
    validate_report(back)


# --- spec 0010: additive durable fields + multi-repo shape (AC8) -------------

# The SWE-bench-specific run_metadata block (populated by the per-case-repo
# driver). For the 0009-6a single-run path these are absent and build_report
# injects schema-stable defaults (null/0) so the legacy shape still validates.
_NEW_RUN_METADATA = {
    "protocol": "standalone-localization",
    "dataset_provenance": {
        "hf_dataset_id": "princeton-nlp/SWE-bench_Verified",
        "hf_split": "test",
        "hf_revision": "deadbeefcafe",
        "raw_fixture_sha256": "0" * 64,
        "sample_case_ids": ["django__django-1", "astropy__astropy-2"],
    },
    "span_inflation_tolerance": 3,
    "contamination_caveat": "SWE-bench is public; treat as a relative instrument.",
    "new_file_only_excluded_count": 1,
    "malformed_skipped_count": 2,
}


def test_report_schema_version_bumped():
    # The schema is additively extended this wave, so the version must move off
    # the 0009-6a string.
    assert SCHEMA_VERSION != "0009-6a/1"


def test_report_legacy_single_run_shape_still_validates():
    # 0009-6a three blocks with NO spec-0010 fields: build_report fills defaults
    # so the legacy single-run report still conforms.
    rep = build_report(_run_metadata(), [_case()], _aggregate())
    validate_report(rep)
    assert rep["run_metadata"]["protocol"] is None
    assert rep["run_metadata"]["new_file_only_excluded_count"] == 0
    assert rep["run_metadata"]["dataset_provenance"] is None
    assert rep["cases"][0]["production_gate_ran"] is None
    assert rep["aggregate"]["classifier_agreement_rate"] is None


def test_report_multi_repo_shape_validates():
    rm = _run_metadata(**_NEW_RUN_METADATA)
    case = _case(
        production_gate_ran=True,
        patch_shape_label="point",
        production_classifier_label="broad",
    )
    agg = _aggregate(classifier_agreement_rate=0.5)
    rep = build_report(rm, [case], agg)
    validate_report(rep)
    assert rep["run_metadata"]["protocol"] == "standalone-localization"
    assert rep["run_metadata"]["dataset_provenance"]["hf_split"] == "test"
    assert rep["aggregate"]["classifier_agreement_rate"] == 0.5
    assert rep["cases"][0]["production_gate_ran"] is True


def test_validate_report_rejects_missing_new_metadata_field():
    rep = build_report(_run_metadata(**_NEW_RUN_METADATA), [_case()], _aggregate())
    del rep["run_metadata"]["protocol"]
    with pytest.raises(ReportSchemaError):
        validate_report(rep)


def test_validate_report_rejects_missing_provenance():
    rep = build_report(_run_metadata(**_NEW_RUN_METADATA), [_case()], _aggregate())
    del rep["run_metadata"]["dataset_provenance"]
    with pytest.raises(ReportSchemaError):
        validate_report(rep)


def test_validate_report_rejects_case_missing_production_gate_ran():
    rep = build_report(_run_metadata(), [_case()], _aggregate())
    del rep["cases"][0]["production_gate_ran"]
    with pytest.raises(ReportSchemaError):
        validate_report(rep)


def test_validate_report_rejects_aggregate_missing_agreement_rate():
    rep = build_report(_run_metadata(), [_case()], _aggregate())
    del rep["aggregate"]["classifier_agreement_rate"]
    with pytest.raises(ReportSchemaError):
        validate_report(rep)
