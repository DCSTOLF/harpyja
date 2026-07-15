"""RED (0046 T19/T20, AC5/AC6): the two-arm gated re-measurement machinery.

Both arms run on the CURRENT SUT, distinguished ONLY by the
``explorer_reactive_confirm`` flag: BASELINE (off = pure 0044) vs NEW (on =
reactive-suppression + confirm partition). The baseline arm's aggregate NET vs
the committed pre-nudge table is checked against the frozen sanity band [1,3]
(else BASELINE_DRIFT_STOP); the NEW arm is measured head-to-head vs the BASELINE
arm (not vs 0044's history).
"""

from __future__ import annotations

import pytest

from harpyja.eval.pool_pilot import PoolRunError
from harpyja.eval.reactive_config import REACTIVE_CONFIG_HASH_0046
from harpyja.eval.reactive_outcome import ReactiveVerdict
from harpyja.eval.reactive_run import (
    build_reactive_run_summary,
    reactive_arm_flag,
    run_reactive_cells,
)


def test_run_refuses_without_live():
    with pytest.raises(PoolRunError):
        run_reactive_cells(arm="baseline", ledger_path="x", artifact_dir="y", live=False)


def test_arm_flag_maps_baseline_off_new_on():
    assert reactive_arm_flag("baseline") is False
    assert reactive_arm_flag("new") is True


def test_startup_stops_on_sut_hash_drift():
    with pytest.raises(PoolRunError):
        run_reactive_cells(
            arm="new", ledger_path="x", artifact_dir="y", live=True,
            verified_case_runner=lambda case, model: ({}, None),
            expected_sut_hash="deadbeef" * 8,  # != working-tree hash -> STOP
        )


# --- summary: band check + head-to-head verdict -------------------------------


def _cell(bucket, *, fired=False, confirmation=None, submission="submitted",
          confirmation_ran=False, disposition="never-triggered"):
    return {
        "terminal_bucket": bucket, "confidence_fired": fired,
        "confirmation_outcome": confirmation, "confirmation_ran": confirmation_ran,
        "submission_outcome": submission, "submit_disposition": disposition,
        "status": "clean", "degrade": None,
    }


def _mk(cells):
    return {"entries": cells, "exclusivity": {"proof": "0041/pilot/2"}}


def test_summary_new_vs_baseline_head_to_head(monkeypatch):
    # baseline: 3 s->wc + 3 fu; new: 3 s->wc + 1 fu -> fu fell, nothing reopens.
    base = {}
    new = {}
    for i in range(3):
        base[f"c{i}::qwen3:8b"] = _cell("wrong-file", fired=True)
        new[f"c{i}::qwen3:8b"] = _cell("wrong-file", fired=True, confirmation="PASS",
                                       confirmation_ran=True)
    for i in range(3):
        base[f"f{i}::qwen3:8b"] = _cell("no-citation", submission="found-unsubmitted")
    new["f0::qwen3:8b"] = _cell("no-citation", submission="found-unsubmitted")
    for i in range(1, 3):
        new[f"f{i}::qwen3:8b"] = _cell("correct")
    # pad to clear floors
    for i in range(10):
        base[f"p{i}::qwen3:8b"] = _cell("correct")
        new[f"p{i}::qwen3:8b"] = _cell("correct")

    summary = build_reactive_run_summary(
        baseline_cells=base, new_cells=new, baseline_net=2,  # in band [1,3]
    )
    assert summary["baseline_drift_stop"] is False
    assert summary["verdict"] == ReactiveVerdict.DISSOLVES_TRADE.value
    assert summary["fu_baseline"] == 3 and summary["fu_new"] == 1
    assert summary["config_hash"] == REACTIVE_CONFIG_HASH_0046
    # five sides reported
    for k in ("swc_new", "flagged_wrong_emitted_new", "conversions", "regressions"):
        assert k in summary


def test_summary_baseline_drift_stop_when_out_of_band():
    base = {f"p{i}::qwen3:8b": _cell("correct") for i in range(12)}
    new = dict(base)
    summary = build_reactive_run_summary(baseline_cells=base, new_cells=new, baseline_net=9)
    assert summary["baseline_drift_stop"] is True
    assert summary["verdict"] == "BASELINE_DRIFT_STOP"


def test_summary_new_arm_flag_everything_trades_again():
    base, new = {}, {}
    for i in range(4):
        base[f"c{i}::qwen3:8b"] = _cell("wrong-file", fired=True)
        new[f"c{i}::qwen3:8b"] = _cell("wrong-file", fired=True, confirmation="FAIL",
                                       confirmation_ran=True, disposition="confirm-failed-flagged")
    for i in range(10):
        base[f"p{i}::qwen3:8b"] = _cell("correct")
        new[f"p{i}::qwen3:8b"] = _cell("correct")
    summary = build_reactive_run_summary(baseline_cells=base, new_cells=new, baseline_net=2)
    assert summary["verdict"] == ReactiveVerdict.TRADES_AGAIN.value
    assert "flagged-wrong-emitted" in summary["reopened"]
