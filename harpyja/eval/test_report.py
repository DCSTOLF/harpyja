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


# --- spec 0014: Deep-degrade visibility — schema 0012/1 → 0013/1 (P6) ---------


def test_report_schema_version_is_0025():
    # spec 0025 bumps 0014/1 -> 0025/1: the fc_citation_recovered_* fields are retired
    # to always-zero (suffix recovery removed). The bump records that the measured
    # thing changed; the fields stay for schema stability (retire-to-zero, not remove).
    assert SCHEMA_VERSION == "0025/1"


def test_recovered_citation_fields_retired_to_zero_with_defaults():
    # Spec 0025 (AC7): the recovered_* fields default to 0 and a real run never
    # populates them non-zero (the runner hardcodes 0). The shape-tally fields stay.
    from harpyja.eval.report import _AGGREGATE_DEFAULTS

    assert _AGGREGATE_DEFAULTS["fc_citation_recovered_spanned_count"] == 0
    assert _AGGREGATE_DEFAULTS["fc_citation_recovered_filelevel_count"] == 0
    # the shape-tally fields remain first-class defaults (still describe the explorer).
    for k in (
        "fc_citation_spanned_count",
        "fc_citation_filelevel_count",
        "fc_citation_dropped_count",
    ):
        assert k in _AGGREGATE_DEFAULTS


def test_deep_degrade_fields_present_with_defaults():
    # A legacy aggregate (no deep fields) gets the "not computed" defaults injected,
    # mirroring the scout twins: count 0, rate null — never an omitted key, never 0.0.
    rep = build_report(_run_metadata(), [_case()], _aggregate())
    validate_report(rep)  # must not raise — deep fields are in the pinned schema
    assert rep["aggregate"]["deep_degrade_count"] == 0
    assert rep["aggregate"]["deep_degrade_rate"] is None


def test_0012_and_0013_aggregate_shapes_both_validate():
    # Old-shape block omitting the deep fields AND a fully-populated new-shape block
    # both pass the SINGLE loud validator (centralized _AGGREGATE_DEFAULTS).
    legacy = build_report(_run_metadata(), [_case()], _aggregate())
    validate_report(legacy)
    populated = build_report(
        _run_metadata(),
        [_case()],
        _aggregate(deep_degrade_count=2, deep_degrade_rate=0.5),
    )
    validate_report(populated)
    assert populated["aggregate"]["deep_degrade_count"] == 2
    assert populated["aggregate"]["deep_degrade_rate"] == 0.5


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


# --- Spec 0011 (citation-shape): degrade-visibility fields + null cited lines ---


def test_report_schema_version_bumped_past_0011():
    # spec 0011 set 0011/1; later specs bump additively past it (current exact pin
    # is asserted in test_report_schema_version_is_0013).
    assert SCHEMA_VERSION != "0011/1"


def test_new_degrade_fields_present_with_defaults():
    # AC16: the new aggregate + run-metadata fields appear via the centralized
    # defaults even when a block omits them, and the report validates.
    rep = build_report(_run_metadata(), [_case()], _aggregate())
    agg = rep["aggregate"]
    for f in (
        "scout_degrade_count",
        "scout_degrade_rate",
        "degraded_dominated",
        "reliability_notes",
        "fc_citation_spanned_count",
        "fc_citation_filelevel_count",
        "fc_citation_dropped_count",
    ):
        assert f in agg, f
    assert "degraded_dominated_threshold" in rep["run_metadata"]
    validate_report(rep)  # no raise


def test_pre_0011_and_0011_shapes_both_validate():
    # AC16: a block omitting the new fields (filled by defaults) AND a fully
    # populated 0011 block both pass the one loud validator.
    minimal = build_report(_run_metadata(), [_case()], _aggregate())
    full = build_report(
        _run_metadata(degraded_dominated_threshold=0.5),
        [_case()],
        _aggregate(
            scout_degrade_count=3,
            scout_degrade_rate=0.25,
            degraded_dominated=False,
            reliability_notes=["indicative-only"],
            fc_citation_spanned_count=4,
            fc_citation_filelevel_count=2,
            fc_citation_dropped_count=1,
        ),
    )
    validate_report(minimal)
    validate_report(full)


# --- Spec 0012 (path-prefix): recovered_* shape-split counters ---


def test_report_schema_version_bumped_past_0012():
    # spec 0012 set 0012/1; spec 0014 bumps additively past it (asserted == 0013/1
    # in test_report_schema_version_is_0013).
    assert SCHEMA_VERSION != "0012/1"


def test_recovered_fields_present_with_defaults():
    # AC4: the two recovered counts appear via the centralized defaults even when a
    # block omits them, and the report validates.
    rep = build_report(_run_metadata(), [_case()], _aggregate())
    agg = rep["aggregate"]
    for f in ("fc_citation_recovered_spanned_count", "fc_citation_recovered_filelevel_count"):
        assert f in agg and agg[f] == 0, f
    validate_report(rep)  # no raise


def test_0011_and_0012_aggregate_shapes_both_validate():
    # AC4: a legacy 0011-shaped aggregate (recovered fields absent → defaulted) AND a
    # fully populated 0012 block both pass the one loud validator.
    legacy = build_report(_run_metadata(), [_case()], _aggregate())
    full = build_report(
        _run_metadata(degraded_dominated_threshold=0.5),
        [_case()],
        _aggregate(
            fc_citation_spanned_count=4,
            fc_citation_filelevel_count=2,
            fc_citation_dropped_count=1,
            fc_citation_recovered_spanned_count=2,
            fc_citation_recovered_filelevel_count=3,
        ),
    )
    validate_report(legacy)
    validate_report(full)
    assert full["aggregate"]["fc_citation_recovered_filelevel_count"] == 3


def test_validate_report_tolerates_null_cited_lines():
    # AC19: a file-level cited span serializes its line fields as JSON null; the
    # one loud validator accepts it (gold expected_spans stay int-only).
    case = _case(
        citations=[{"path": "a.py", "start_line": None, "end_line": None, "source_tier": 1}]
    )
    rep = build_report(_run_metadata(), [case], _aggregate())
    validate_report(rep)  # no raise
    # round-trips through JSON as null
    assert json.loads(json.dumps(rep))["cases"][0]["citations"][0]["start_line"] is None


# --- Spec 0019 (OQ2 re-run): gate-confound outcome + ceiling + instruct/scout A/B ---


def test_gate_confound_and_ceiling_fields_present_with_defaults():
    # AC5/AC6/D2: the new run-metadata ceiling + aggregate gate-confound and A/B twins
    # appear via the centralized defaults even when a block omits them.
    rep = build_report(_run_metadata(), [_case()], _aggregate())
    assert "gate_false_escalation_ceiling" in rep["run_metadata"]
    assert rep["run_metadata"]["gate_false_escalation_ceiling"] is None
    agg = rep["aggregate"]
    for f in (
        "gate_confounded",
        "gate_confounded_measured_rate",
        "gate_false_escalation_instruct",
        "gate_false_escalation_instruct_count",
        "gate_false_escalation_instruct_total",
        "gate_false_escalation_scout",
        "gate_false_escalation_scout_count",
        "gate_false_escalation_scout_total",
    ):
        assert f in agg, f
    # null-with-zero-count defaults: rates null, counts 0, flag False
    assert agg["gate_confounded"] is False
    assert agg["gate_confounded_measured_rate"] is None
    assert agg["gate_false_escalation_instruct"] is None
    assert agg["gate_false_escalation_instruct_count"] == 0
    assert agg["gate_false_escalation_scout_total"] == 0
    validate_report(rep)  # no raise


def test_validate_report_accepts_gate_confound_and_ab_fields():
    # A fully-populated 0019 block validates.
    rm = _run_metadata(gate_false_escalation_ceiling=0.20)
    agg = _aggregate(
        gate_confounded=True,
        gate_confounded_measured_rate=0.42,
        gate_false_escalation_instruct=0.42,
        gate_false_escalation_instruct_count=5,
        gate_false_escalation_instruct_total=12,
        gate_false_escalation_scout=0.75,
        gate_false_escalation_scout_count=9,
        gate_false_escalation_scout_total=12,
    )
    rep = build_report(rm, [_case()], agg)
    validate_report(rep)  # no raise
    assert rep["run_metadata"]["gate_false_escalation_ceiling"] == 0.20
    assert rep["aggregate"]["gate_confounded"] is True
    assert rep["aggregate"]["gate_false_escalation_scout"] == 0.75


def test_0013_and_0019_aggregate_shapes_both_validate():
    # A legacy 0013-shaped block (new fields absent → defaulted) AND a fully populated
    # 0019 block both pass the one loud validator.
    legacy = build_report(_run_metadata(), [_case()], _aggregate())
    full = build_report(
        _run_metadata(gate_false_escalation_ceiling=0.20),
        [_case()],
        _aggregate(
            gate_confounded=False,
            gate_false_escalation_instruct=0.10,
            gate_false_escalation_instruct_count=1,
            gate_false_escalation_instruct_total=10,
        ),
    )
    validate_report(legacy)
    validate_report(full)


def test_gate_confound_fields_have_single_anti_drift_source():
    # T8 anti-drift: the gate-confound aggregate field set is declared ONCE
    # (_GATE_CONFOUND_AGG_FIELDS) and every name is both enumerated in the required
    # tuple and default-populated — so adding a name without a default is caught here,
    # not by a half-populated report reading as complete.
    from harpyja.eval.report import (
        _AGGREGATE_DEFAULTS,
        _AGGREGATE_FIELDS,
        _GATE_CONFOUND_AGG_FIELDS,
    )

    for name in _GATE_CONFOUND_AGG_FIELDS:
        assert name in _AGGREGATE_FIELDS, f"{name} missing from _AGGREGATE_FIELDS"
        assert name in _AGGREGATE_DEFAULTS, f"{name} missing a default"


def test_report_round_trip_gate_confounded():
    # AC9: the gate-confounded outcome + measured rate survive a JSON round-trip and
    # re-validate (the typed null is durable in the artifact, not just in memory).
    rm = _run_metadata(gate_false_escalation_ceiling=0.20)
    agg = _aggregate(gate_confounded=True, gate_confounded_measured_rate=0.35)
    rep = build_report(rm, [_case()], agg)
    reloaded = json.loads(json.dumps(rep))
    validate_report(reloaded)  # no raise
    assert reloaded["aggregate"]["gate_confounded"] is True
    assert reloaded["aggregate"]["gate_confounded_measured_rate"] == 0.35
