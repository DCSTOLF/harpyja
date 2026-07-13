"""Spec 0043 T16 — the gated diagnosis re-measurement machinery (AC5).

``run_diagnosis_cells`` consumes the FROZEN ``PREREGISTERED_DIAGNOSIS_CONFIG_0043``
coverage (the pinned 0042 pilot cells — never re-selected), routes the whole
run through ``run_gated_pool_pilot`` (live=True required; ``0041/pilot/2``
exclusivity proof, keyed by ``DIAGNOSIS_CONFIG_HASH_0043``), and per clean
cell records the ``submission_outcome`` fact from the trajectory-VERIFIED
artifact. ``build_diagnosis_run_summary`` computes the BEFORE (committed T9
covered subset) vs AFTER comparison with the IDENTICAL detector version and
the total pure AC6 verdict.

All fakes here — no network (the test_adoption_run idioms).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harpyja.eval import submission_gap
from harpyja.eval.diagnosis_config import (
    DIAGNOSIS_CONFIG_HASH_0043,
    PREREGISTERED_DIAGNOSIS_CONFIG_0043,
)
from harpyja.eval.diagnosis_run import (
    build_diagnosis_run_summary,
    load_before_cells,
    run_diagnosis_cells,
)
from harpyja.eval.pool_pilot import PoolRunError

_CFG = PREREGISTERED_DIAGNOSIS_CONFIG_0043
_REPO_ROOT = Path(__file__).resolve().parents[2]
# Evidence-path convention: specs/.archive first, live specs/ fallback.
_ATTRIBUTION_ARCHIVED = (
    _REPO_ROOT
    / "specs/.archive/0043-diagnosis/attribution/attribution_table.json"
)
_ATTRIBUTION_LIVE = (
    _REPO_ROOT / "specs/0043-diagnosis/attribution/attribution_table.json"
)
_ATTRIBUTION = (
    _ATTRIBUTION_ARCHIVED if _ATTRIBUTION_ARCHIVED.is_file() else _ATTRIBUTION_LIVE
)


def _fake_verifier_artifact(
    case_id: str,
    model: str,
    *,
    bucket: str = "correct",
    submission_outcome: str = "submitted",
    verifier_status: str = "PASSED",
    failure_reason: str | None = None,
) -> dict:
    return {
        "schema_version": "0043/1",
        "requested_model": model,
        "endpoint": "http://127.0.0.1:11434/v1",
        "served_model": model,
        "configured_endpoint_models": [model],
        "tiers_run": [0, 1],
        "model_turns": [
            {
                "role": "assistant",
                "tool_calls": [
                    {"id": "t1", "function": {"name": "grep", "arguments": "{}"}},
                    {
                        "id": "t2",
                        "function": {"name": "submit_citations", "arguments": "{}"},
                    },
                ],
            },
        ],
        "terminal_bucket": bucket,
        "verifier_status": verifier_status,
        "failure_reason": failure_reason,
        "citations_submitted": 1,
        "citations_surviving": 1,
        "submission_outcome": submission_outcome,
        "detector_version": submission_gap.DETECTOR_VERSION,
        "case": case_id,
    }


def _passing_runner(case: dict, model: str) -> tuple[dict, str | None]:
    return _fake_verifier_artifact(case["case_id"], model), None


def _run(tmp_path: Path, **kw):
    kw.setdefault("verified_case_runner", _passing_runner)
    kw.setdefault("ps_reader", lambda api_base: [])
    kw.setdefault("live", True)
    return run_diagnosis_cells(
        ledger_path=tmp_path / "diagnosis_results.json",
        artifact_dir=tmp_path / "artifacts",
        **kw,
    )


def test_diagnosis_run_cell_emits_trajectory_verified_artifact(tmp_path):
    result = _run(tmp_path)
    assert result["status"] == "completed"
    assert result["cells_remaining"] == []

    case_id = _CFG.pilot_case_ids[0]
    model = _CFG.required_models[0]
    slug = model.replace(":", "_").replace(".", "_")
    art_path = tmp_path / "artifacts" / f"{case_id}__{slug}.diagnosis.json"
    assert art_path.is_file()
    art = json.loads(art_path.read_text(encoding="utf-8"))
    assert art["requested_model"] == model
    assert art["served_model"] == model
    assert art["verifier_status"] == "PASSED"
    assert art["terminal_bucket"] == "correct"
    # The loss-class fact rides the per-cell artifact AND the ledger cell.
    assert art["submission_outcome"] == "submitted"
    assert art["detector_version"] == submission_gap.DETECTOR_VERSION
    ref = art["exclusivity_proof_ref"]
    assert ref["ledger"] == str(tmp_path / "diagnosis_results.json")
    assert ref["ledger_schema_version"] == "0041/pilot/2"
    assert ref["config_hash"] == DIAGNOSIS_CONFIG_HASH_0043
    obj = json.loads(
        (tmp_path / "diagnosis_results.json").read_text(encoding="utf-8")
    )
    assert obj["config_hash"] == DIAGNOSIS_CONFIG_HASH_0043
    cell = obj["entries"][f"{case_id}::{model}"]
    assert cell["bucket"] == "correct"
    assert cell["submission_outcome"] == "submitted"


def test_diagnosis_run_refuses_without_live(tmp_path):
    """The 0040/0041/0042 posture: live=True only from the committed driver."""
    with pytest.raises(PoolRunError, match="live=True"):
        run_diagnosis_cells(
            ledger_path=tmp_path / "diagnosis_results.json",
            artifact_dir=tmp_path / "artifacts",
            verified_case_runner=_passing_runner,
            ps_reader=lambda api_base: [],
        )
    assert not (tmp_path / "diagnosis_results.json").exists()


def test_diagnosis_run_consumes_pinned_0042_cells(tmp_path):
    """Cells == the frozen config's pilot_case_ids x coverage models — no
    re-selection parameter exists; include_optional only ENABLES frozen tags."""
    seen: set[tuple[str, str]] = set()

    def runner(case: dict, model: str) -> tuple[dict, str | None]:
        seen.add((case["case_id"], model))
        return _passing_runner(case, model)

    _run(tmp_path, verified_case_runner=runner)
    assert seen == {
        (cid, m) for cid in _CFG.pilot_case_ids for m in _CFG.required_models
    }

    with pytest.raises(PoolRunError, match="frozen"):
        _run(tmp_path, include_optional=["some-other-model:1b"])


def test_before_covered_subset_named_in_artifact(tmp_path):
    """BEFORE is computable only for cells whose full trajectory survived in
    eval_work — the committed T9 table IS that covered subset, and the summary
    NAMES it (never silently narrows)."""
    before = load_before_cells()
    # The committed table's adoption rows: 31 clean cells on this machine.
    table = json.loads(_ATTRIBUTION.read_text())
    adoption_rows = [c for c in table["cases"] if c["run"] == "adoption_0042"]
    assert set(before) == {
        f"{c['case']}::{c['model']}" for c in adoption_rows
    }
    for v in before.values():
        assert set(v) >= {"bucket", "submission_outcome"}

    _run(tmp_path)
    summary = build_diagnosis_run_summary(tmp_path / "diagnosis_results.json")
    assert sorted(summary["covered_before_cells"]) == sorted(before)
    assert summary["covered_before"] == len(before)
    assert summary["found_unsubmitted_before"] == sum(
        1 for v in before.values()
        if v["submission_outcome"] == "found-unsubmitted"
    )
    # The verdict is the total pure AC6 function's output, as data.
    assert summary["verdict"] in {
        "clock-bound-fixed",
        "clock-bound-under-powered",
        "clock-bound-persists",
        "not-clock-bound",
    }
    assert "inconclusive_before" in summary
    assert "inconclusive_after" in summary
    assert {"conversions", "regressions", "net"} <= set(summary)


def test_identical_detector_both_sides(tmp_path):
    """One detector version across the comparison: the committed BEFORE table,
    the frozen config, and the AFTER summary all carry the SAME version."""
    table = json.loads(_ATTRIBUTION.read_text())
    assert table["detector_version"] == submission_gap.DETECTOR_VERSION
    assert _CFG.detector_version == submission_gap.DETECTOR_VERSION
    _run(tmp_path)
    summary = build_diagnosis_run_summary(tmp_path / "diagnosis_results.json")
    assert summary["detector_version"] == submission_gap.DETECTOR_VERSION
