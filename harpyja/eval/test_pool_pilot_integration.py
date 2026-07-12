"""Spec 0040 — AC4 integration: the committed three-model pilot evidence.

The multi-hour pilot runs through the committed operator driver
(specs/0040-pool/pilot/run_pilot.py — STOP-AND-WARN, resumable, exit 3 while
work remains); this test pins the COMMITTED ledger it produces: every pinned
case x preflight-passing model cell present, each either a verifier-clean
bucket or a typed degrade cause (never a silent hole), at arm parity
``explorer_think=None``. Skip-not-fail while the ledger is absent/incomplete;
strict under HARPYJA_REQUIRE_LIVE_STACK.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harpyja.eval.locate_accuracy import LocateBucket
from harpyja.eval.locate_probe import require_live_stack
from harpyja.eval.pool_pilot import POOL_PILOT_LEDGER_SCHEMA_VERSION
from harpyja.eval.pool_precheck import (
    POOL_CONFIG_HASH_0040,
    PREREGISTERED_POOL_CONFIG_0040,
)

_CFG = PREREGISTERED_POOL_CONFIG_0040


def _committed_ledger_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    archived = (
        root / "specs" / ".archive" / "0040-pool" / "pilot" / "pilot_results.json"
    )
    live = root / "specs" / "0040-pool" / "pilot" / "pilot_results.json"
    return archived if archived.is_file() else live


@pytest.mark.integration
def test_three_model_pilot_emits_verifier_clean_artifacts_at_default_think():
    path = _committed_ledger_path()
    if not path.is_file():
        if require_live_stack(False) == "fail":
            pytest.fail(
                "committed 0040 pilot ledger absent (HARPYJA_REQUIRE_LIVE_STACK "
                "set) — run specs/0040-pool/pilot/run_pilot.py to completion"
            )
        pytest.skip("committed 0040 pilot ledger not yet produced — run the driver")

    obj = json.loads(path.read_text(encoding="utf-8"))
    assert obj["schema_version"] == POOL_PILOT_LEDGER_SCHEMA_VERSION
    assert obj["config_hash"] == POOL_CONFIG_HASH_0040
    entries = obj["entries"]

    expected = {
        f"{cid}::{model}"
        for cid in _CFG.pilot_case_ids
        for model in _CFG.model_tags
    }
    missing = expected - set(entries)
    if missing:
        if require_live_stack(False) == "fail":
            pytest.fail(f"pilot ledger incomplete: {len(missing)} cells missing")
        pytest.skip(f"pilot in progress: {len(missing)}/{len(expected)} cells remain")

    for key in expected:
        cell = entries[key]
        # Every cell is a verifier-clean bucket or a TYPED degrade — never a
        # silent hole, never both.
        if cell["degrade"] is None:
            assert LocateBucket(cell["bucket"])  # valid taxonomy value
            # Arm parity: the recorded think_mode is the shipped default
            # (explorer_think=None ⇒ reasoning_effort omitted ⇒ default-on).
            assert cell.get("think_mode") == "default-omitted"
            # Endpoint-mechanism identity recorded per transport (0038).
            assert cell.get("serving_transport")
            assert cell.get("artifact")
        else:
            assert cell["bucket"] is None
