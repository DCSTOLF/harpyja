"""RED (0045 T19, AC5): the gated live re-measurement machinery.

``run_refinement_cells`` refuses without ``live=True``, consumes coverage from
the frozen config (never re-selects), keys its ledger by
``REFINEMENT_CONFIG_HASH_0045``, and STOPs on EITHER a SUT-hash OR a config-hash
drift (the dual-hash gate). ``build_refinement_run_summary`` joins the BEFORE
baseline with the AFTER ledger into the FOUR-SIDED ledger (conversions /
regressions / s->wc / fu) + NET per model, head-to-head vs 0044, feeding the
total-pure ``decide_refinement_outcome``.
"""

import json
from pathlib import Path

import pytest

from harpyja.eval.refinement_config import (
    PREREGISTERED_REFINEMENT_CONFIG_0045 as _CFG,
)
from harpyja.eval.refinement_config import (
    REFINEMENT_CONFIG_HASH_0045,
    compute_sut_hash,
)
from harpyja.eval.refinement_outcome import RefinementVerdict
from harpyja.eval.refinement_run import (
    build_refinement_run_summary,
    refinement_coverage_models,
    run_refinement_cells,
)


def test_run_refuses_without_live(tmp_path):
    with pytest.raises(Exception, match="live"):
        run_refinement_cells(
            ledger_path=tmp_path / "l.json", artifact_dir=tmp_path / "a",
            live=False,
        )


def test_coverage_models_consumed_from_frozen_config():
    models = refinement_coverage_models()
    assert models[0] == _CFG.required_models[0]
    # Optional models only when explicitly included — never re-selected.
    assert set(refinement_coverage_models(("qwen3:8b",))) >= {_CFG.required_models[0]}


def test_startup_stops_on_sut_hash_drift(tmp_path):
    with pytest.raises(Exception, match="SUT"):
        run_refinement_cells(
            ledger_path=tmp_path / "l.json", artifact_dir=tmp_path / "a",
            live=True, expected_sut_hash="deadbeef" * 8,
            verified_case_runner=lambda case, model: ({}, None),
        )


def test_startup_stops_on_config_hash_drift(tmp_path):
    with pytest.raises(Exception, match="config"):
        run_refinement_cells(
            ledger_path=tmp_path / "l.json", artifact_dir=tmp_path / "a",
            live=True, expected_sut_hash=compute_sut_hash(),
            expected_config_hash="deadbeef" * 8,
            verified_case_runner=lambda case, model: ({}, None),
        )


_ROOT = Path(__file__).resolve().parents[2]
_VALID_EXCLUSIVITY = json.loads(
    (_ROOT / "specs/.archive/0044-submission/submission_run"
     "/submission_results.json").read_text(encoding="utf-8")
)["exclusivity"]


def _ledger(tmp_path, entries, exclusivity=_VALID_EXCLUSIVITY):
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps({
        "schema_version": "0041/pilot/2",
        "config_hash": REFINEMENT_CONFIG_HASH_0045,
        "exclusivity": exclusivity,
        "entries": entries,
    }), encoding="utf-8")
    return path


def _entry(bucket, fired=False, fu=False, swc=None):
    return {
        "status": "clean",
        "degrade": None,
        "bucket": bucket,
        "confidence_fired": fired,
        "submission_outcome": "found-unsubmitted" if fu else "submitted",
        "silence_to_wrong_confidence": swc,
    }


def test_four_sided_ledger_per_model_and_head_to_head(tmp_path, monkeypatch):
    # A minimal AFTER ledger: one 8b empty->wrong-file FIRED (s->wc), one 14b
    # conversion; the BEFORE baseline is the config-pinned committed table.
    entries = {
        "django__django-13516::qwen3:8b": _entry("wrong-file", fired=True),
        "astropy__astropy-12907::qwen3:14b": _entry("correct"),
    }
    ledger_path = _ledger(tmp_path, entries)
    summary = build_refinement_run_summary(ledger_path)
    assert summary["config_hash"] == REFINEMENT_CONFIG_HASH_0045
    ledger = summary["ledger_four_sided"]
    assert set(ledger) >= {"per_model", "aggregate_net", "swc_total", "fu_total"}
    # Head-to-head vs 0044's pinned aggregate net (2).
    assert summary["head_to_head"]["comparator_net"] == 2
    assert summary["verdict"] in {m.name for m in RefinementVerdict}


def test_summary_requires_exclusivity_proof(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "schema_version": "0041/pilot/2",
        "config_hash": REFINEMENT_CONFIG_HASH_0045, "entries": {},
    }), encoding="utf-8")
    with pytest.raises(Exception, match="exclusivity"):
        build_refinement_run_summary(bad)


def test_summary_feeds_decide_refinement_outcome(tmp_path):
    # Degrade/suspect cells excluded from the join; a clean empty->correct 14b
    # cell converts.
    entries = {
        "astropy__astropy-12907::qwen3:14b": _entry("correct"),
        "bad::qwen3:8b": {"status": "suspect", "degrade": None, "bucket": "correct"},
    }
    ledger_path = _ledger(tmp_path, entries)
    summary = build_refinement_run_summary(ledger_path)
    assert "verdict" in summary and "conditions_true" in summary
    # The record-only unfired-s->wc cross-check is surfaced beside s->wc.
    assert "unfired_swc_total" in summary["ledger_four_sided"]
