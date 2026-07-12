"""Spec 0040 — AC4 unit: the resumable pilot ledger + STOP-AND-WARN preflight."""

from __future__ import annotations

import json

import pytest

from harpyja.eval.locate_probe import require_live_stack
from harpyja.eval.pool_pilot import (
    POOL_PILOT_LEDGER_SCHEMA_VERSION,
    PoolPilotLedger,
    PoolRunError,
    pool_pilot_preflight,
    run_pool_pilot,
)
from harpyja.eval.pool_precheck import (
    POOL_CONFIG_HASH_0040,
    PREREGISTERED_POOL_CONFIG_0040,
)

_CFG = PREREGISTERED_POOL_CONFIG_0040


def test_pool_pilot_ledger_resumes_completed_cells(tmp_path):
    path = tmp_path / "pilot_results.json"
    ledger = PoolPilotLedger(path, config_hash=POOL_CONFIG_HASH_0040)
    ledger.record("c1", "qwen3:14b", {"bucket": "correct", "degrade": None})
    # A fresh instance over the same path resumes the completed cell.
    resumed = PoolPilotLedger(path, config_hash=POOL_CONFIG_HASH_0040)
    assert resumed.has("c1", "qwen3:14b")
    assert not resumed.has("c1", "qwen3:8b")
    assert resumed.get("c1", "qwen3:14b")["bucket"] == "correct"
    # The persisted shape is the version-stamped, hash-pinned envelope.
    obj = json.loads(path.read_text(encoding="utf-8"))
    assert obj["schema_version"] == POOL_PILOT_LEDGER_SCHEMA_VERSION
    assert obj["config_hash"] == POOL_CONFIG_HASH_0040
    assert "c1::qwen3:14b" in obj["entries"]


def test_pool_pilot_ledger_schema_validates_loud(tmp_path):
    path = tmp_path / "pilot_results.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "9999/1",
                "config_hash": POOL_CONFIG_HASH_0040,
                "entries": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(PoolRunError, match="schema_version"):
        PoolPilotLedger(path, config_hash=POOL_CONFIG_HASH_0040)
    # A ledger written under a DIFFERENT frozen config is not resumable.
    path.write_text(
        json.dumps(
            {
                "schema_version": POOL_PILOT_LEDGER_SCHEMA_VERSION,
                "config_hash": "b" * 64,
                "entries": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(PoolRunError, match="different frozen config"):
        PoolPilotLedger(path, config_hash=POOL_CONFIG_HASH_0040)


def test_pool_pilot_preflight_stops_when_model_tag_unserved():
    with pytest.raises(PoolRunError, match="not served"):
        pool_pilot_preflight(
            _CFG,
            served_tags=["qwen3:14b"],
            pilot_models=["qwen3:14b", "qwen3:8b"],
        )
    # A model outside the pre-registered tag set STOPs even if served —
    # substitution under the frozen hash is the steering the freeze prevents.
    with pytest.raises(PoolRunError, match="not in the pre-registered"):
        pool_pilot_preflight(
            _CFG,
            served_tags=["qwen3-coder:30b"],
            pilot_models=["qwen3-coder:30b"],
        )
    ok = pool_pilot_preflight(
        _CFG,
        served_tags=list(_CFG.model_tags),
        pilot_models=list(_CFG.model_tags),
    )
    assert ok["models_served"] is True
    assert ok["explorer_think"] is None  # arm parity rides the frozen config


def test_cell_needs_run_bounded_retry_for_typed_degrades():
    from harpyja.eval.pool_pilot import _cell_needs_run

    # Absent cell → run.
    assert _cell_needs_run(None)
    # Clean bucket → NEVER re-run (re-running clean observations because an
    # outcome looks wrong would be post-hoc steering).
    assert not _cell_needs_run({"bucket": "empty", "degrade": None, "attempts": 1})
    # Typed degrade with attempts left → ONE bounded re-run (0036 posture).
    assert _cell_needs_run(
        {"bucket": None, "degrade": "no-trajectory: x", "attempts": 1}
    )
    # Degrade at the attempt cap → recorded-by-cause, excluded, never silent.
    assert not _cell_needs_run(
        {"bucket": None, "degrade": "no-trajectory: x", "attempts": 2}
    )
    # Legacy cell without attempts counts as one attempt.
    assert _cell_needs_run({"bucket": None, "degrade": "verifier:x"})


def test_run_pool_pilot_refuses_without_live_flag(tmp_path):
    # The live loop is an operator entrypoint — never fired implicitly.
    with pytest.raises(PoolRunError, match="live=True"):
        run_pool_pilot(
            _CFG,
            out_dir=tmp_path / "artifacts",
            ledger_path=tmp_path / "ledger.json",
            pilot_models=list(_CFG.model_tags),
        )


def test_strict_run_skip_is_hard_fail():
    # Without the strict env an unavailable stack skips; under
    # HARPYJA_REQUIRE_LIVE_STACK the same condition is a hard FAIL.
    assert require_live_stack(False, env={}) == "skip"
    assert (
        require_live_stack(False, env={"HARPYJA_REQUIRE_LIVE_STACK": "1"}) == "fail"
    )
