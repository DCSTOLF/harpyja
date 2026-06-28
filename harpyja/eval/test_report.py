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
