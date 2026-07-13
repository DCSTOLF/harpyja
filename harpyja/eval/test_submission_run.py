"""RED (0044 T17, AC6): the gated submission re-measurement machinery.

``run_submission_cells`` consumes the FROZEN ``PREREGISTERED_SUBMISSION_CONFIG_0044``
coverage (the pinned 0042 pilot cells — never re-selected), VERIFIES the
working-tree SUT hash against the committed config at startup (a drifted SUT
is a typed STOP before any cell runs), routes the whole run through
``run_gated_pool_pilot`` (live=True required; ``0041/pilot/2`` exclusivity
proof, keyed by ``SUBMISSION_CONFIG_HASH_0044``), and per clean cell records
the submission_outcome AND the confidence facts from the trajectory-VERIFIED
artifact. ``build_submission_run_summary`` joins BEFORE (the config-pinned
committed baseline, sha256-verified) against AFTER (this ledger, suspect and
degraded cells excluded) and returns the total pure AC8 verdict as data.

All fakes here — no network (the test_diagnosis_run idioms).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harpyja.eval import submission_gap
from harpyja.eval.pool_pilot import PoolRunError
from harpyja.eval.submission_config import (
    PREREGISTERED_SUBMISSION_CONFIG_0044,
    SUBMISSION_CONFIG_HASH_0044,
    compute_sut_hash,
)
from harpyja.eval.submission_run import (
    build_submission_run_summary,
    load_baseline_cells,
    run_submission_cells,
)

_CFG = PREREGISTERED_SUBMISSION_CONFIG_0044
_REPO_ROOT = Path(__file__).resolve().parents[2]
_BASELINE = _REPO_ROOT / _CFG.baseline_table_path


def _fake_verifier_artifact(
    case_id: str,
    model: str,
    *,
    bucket: str = "correct",
    submission_outcome: str = "submitted",
    verifier_status: str = "PASSED",
    failure_reason: str | None = None,
    confidence_fired: bool = True,
) -> dict:
    return {
        "schema_version": "0044/1",
        "requested_model": model,
        "endpoint": "http://127.0.0.1:11434/v1",
        "served_model": model,
        "configured_endpoint_models": [model],
        "tiers_run": [0, 1],
        "model_turns": [
            {
                "role": "assistant",
                "tool_calls": [
                    {"id": "t1", "function": {"name": "symbols", "arguments": "{}"}},
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
        "confidence_fired": confidence_fired,
        "confidence_triggering_signal": (
            "symbols-exact-span" if confidence_fired else None
        ),
        "confidence_firing_turn": 1 if confidence_fired else None,
        "confidence_firing_spans": (
            [{"path": "a.py", "start_line": 1, "end_line": 2}]
            if confidence_fired
            else None
        ),
        "grep_hits_inside_symbol_spans": 0,
        "convergent_evidence": False,
        "confidence_null": None,
        "case": case_id,
    }


def _passing_runner(case: dict, model: str) -> tuple[dict, str | None]:
    return _fake_verifier_artifact(case["case_id"], model), None


def _run(tmp_path: Path, **kw):
    kw.setdefault("verified_case_runner", _passing_runner)
    kw.setdefault("ps_reader", lambda api_base: [])
    kw.setdefault("live", True)
    return run_submission_cells(
        ledger_path=tmp_path / "submission_results.json",
        artifact_dir=tmp_path / "artifacts",
        **kw,
    )


def test_run_refuses_without_live(tmp_path):
    """The 0040/0041/0042/0043 posture: live=True only from the committed driver."""
    with pytest.raises(PoolRunError, match="live=True"):
        run_submission_cells(
            ledger_path=tmp_path / "submission_results.json",
            artifact_dir=tmp_path / "artifacts",
            verified_case_runner=_passing_runner,
            ps_reader=lambda api_base: [],
        )
    assert not (tmp_path / "submission_results.json").exists()


def test_coverage_models_consumed_from_frozen_config(tmp_path):
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


def test_ledger_keyed_by_submission_config_hash_and_carries_confidence(tmp_path):
    result = _run(tmp_path)
    assert result["status"] == "completed"
    assert result["cells_remaining"] == []
    assert result["config_hash"] == SUBMISSION_CONFIG_HASH_0044
    obj = json.loads(
        (tmp_path / "submission_results.json").read_text(encoding="utf-8")
    )
    assert obj["config_hash"] == SUBMISSION_CONFIG_HASH_0044
    case_id = _CFG.pilot_case_ids[0]
    model = _CFG.required_models[0]
    cell = obj["entries"][f"{case_id}::{model}"]
    assert cell["bucket"] == "correct"
    assert cell["submission_outcome"] == "submitted"
    # The confidence facts ride the ledger cell — the firing rate is
    # computable from the run's own record.
    assert cell["confidence_fired"] is True
    assert cell["confidence_triggering_signal"] == "symbols-exact-span"
    assert cell["confidence_firing_turn"] == 1
    assert cell["confidence_null"] is None


def test_startup_verifies_sut_hash_against_frozen_config(tmp_path):
    # A drifted SUT is a typed STOP before any cell runs (the committed config
    # names the POST-lever surface; the driver passes its recorded hash here).
    with pytest.raises(PoolRunError, match="SUT hash"):
        _run(tmp_path, expected_sut_hash="0" * 64)
    assert not (tmp_path / "submission_results.json").exists()
    # The matching hash runs clean.
    result = _run(tmp_path, expected_sut_hash=compute_sut_hash())
    assert result["status"] == "completed"


def test_summary_joins_before_committed_table_vs_after_ledger(tmp_path):
    before = load_baseline_cells()
    table = json.loads(_BASELINE.read_text(encoding="utf-8"))
    adoption_rows = [c for c in table["cases"] if c["run"] == _CFG.baseline_run]
    assert set(before) == {f"{c['case']}::{c['model']}" for c in adoption_rows}

    _run(tmp_path)
    summary = build_submission_run_summary(tmp_path / "submission_results.json")
    assert summary["config_hash"] == SUBMISSION_CONFIG_HASH_0044
    assert summary["detector_version"] == submission_gap.DETECTOR_VERSION
    assert sorted(summary["covered_before_cells"]) == sorted(before)
    assert summary["covered_before"] == len(before)
    assert summary["found_unsubmitted_before"] == 6  # the frozen baseline fact
    # The five-member verdict as data, all true conditions recorded.
    assert summary["verdict"] in {
        "under-powered",
        "never-fires",
        "still-trades-off",
        "nudge-inert",
        "conditioned-nudge-ships",
    }
    assert {"conversions", "regressions", "net", "conditions_true"} <= set(summary)
    # Per-model reporting: net AND firing rate per model — an aggregate win
    # that hides an 8b regression is not a ship.
    per_model = {r["model"]: r for r in summary["per_model"]}
    for model in _CFG.required_models:
        assert {"net", "conversions", "regressions", "firings",
                "firing_rate"} <= set(per_model[model])


def test_summary_excludes_suspect_and_degraded_cells(tmp_path):
    bad_case = _CFG.pilot_case_ids[0]

    def runner(case: dict, model: str) -> tuple[dict, str | None]:
        if case["case_id"] == bad_case:
            return _fake_verifier_artifact(
                case["case_id"], model,
                verifier_status="FAILED", failure_reason="model-unknown",
            ), None
        return _passing_runner(case, model)

    _run(tmp_path, verified_case_runner=runner)
    summary = build_submission_run_summary(tmp_path / "submission_results.json")
    model = _CFG.required_models[0]
    assert f"{bad_case}::{model}" not in summary["covered_after_cells"]


def test_identical_detector_both_sides(tmp_path):
    table = json.loads(_BASELINE.read_text(encoding="utf-8"))
    assert table["detector_version"] == submission_gap.DETECTOR_VERSION
    assert _CFG.detector_version == submission_gap.DETECTOR_VERSION
    _run(tmp_path)
    summary = build_submission_run_summary(tmp_path / "submission_results.json")
    assert summary["detector_version"] == submission_gap.DETECTOR_VERSION


def test_load_baseline_cells_verifies_sha256(tmp_path):
    # The baseline-identity guard bites at runtime too: a table whose bytes
    # do not match the frozen sha256 is refused.
    tampered = tmp_path / "tampered.json"
    table = json.loads(_BASELINE.read_text(encoding="utf-8"))
    table["cases"] = table["cases"][:1]
    tampered.write_text(json.dumps(table), encoding="utf-8")
    with pytest.raises(PoolRunError, match="sha256"):
        load_baseline_cells(tampered)


def test_committed_submission_config_matches_computed_truth():
    """T21 (stage-2 freeze pin): the COMMITTED config artifact names exactly
    the in-code frozen 0044 config.

    Spec 0045 note: 0045 evolved the pinned SUT surface (``confidence_gate.py``,
    ``explorer_loop.py``) for the refined gate, so the LIVE ``compute_sut_hash()``
    no longer equals 0044's frozen ``sut_hash`` — the 0044 freeze is now
    HISTORICAL. This test therefore guards the committed artifact's INTERNAL
    CONSISTENCY (its stored ``config_hash`` recomputes from its own config dict)
    and that every field EXCEPT the now-evolved ``sut_hash`` still matches the
    in-code config. 0045's own frozen config pins the current SUT (T13/T14/T23)."""
    import dataclasses
    import hashlib

    committed_path = (
        _REPO_ROOT / "specs" / "0044-submission" / "submission_config"
        / "submission_config.json"
    )
    archived_path = (
        _REPO_ROOT / "specs" / ".archive" / "0044-submission"
        / "submission_config" / "submission_config.json"
    )
    path = archived_path if archived_path.is_file() else committed_path
    assert path.is_file(), (
        "stage-2 freeze artifact missing — commit submission_config.json "
        "BEFORE any live call (T21)"
    )
    committed = json.loads(path.read_text(encoding="utf-8"))
    assert committed["schema_version"] == "0044/submission-config/1"
    # Internal consistency: config_hash recomputes from the committed config
    # dict (json.dumps of tuples and lists is identical — the frozen payload).
    recomputed = hashlib.sha256(
        json.dumps(committed["config"], sort_keys=True).encode("utf-8")
    ).hexdigest()
    assert committed["config_hash"] == recomputed
    # Every field except the 0045-evolved sut_hash still matches the in-code
    # config (the drift guard remains live for all non-SUT fields).
    expected = json.loads(json.dumps(dataclasses.asdict(_CFG), default=list))
    got = dict(committed["config"])
    expected.pop("sut_hash")
    got.pop("sut_hash")
    assert got == expected
    # The frozen 0044 sut_hash is a valid digest and now DIFFERS from live
    # (0045 evolved the SUT) — the historical freeze, made explicit.
    assert len(committed["config"]["sut_hash"]) == 64
    assert committed["config"]["sut_hash"] != compute_sut_hash()
