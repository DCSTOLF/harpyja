"""Spec 0041 — AC8 integration: the live gate passes-and-records / stops-typed.

Skip-not-fail without a live stack; strict under HARPYJA_REQUIRE_LIVE_STACK.
The contended case fabricates NO traffic: it narrows the frozen model set so
an already-resident tag becomes foreign — the endpoint is never touched.
"""

from __future__ import annotations

import dataclasses
import json
import urllib.request

import pytest

from harpyja.eval.exclusivity_gate import ExclusiveEndpointContended
from harpyja.eval.gate_run import (
    attribute_reload_churn,
    clean_0040_degrade_profile,
    run_gated_pool_pilot,
)
from harpyja.eval.locate_probe import require_live_stack
from harpyja.eval.pool_precheck import PREREGISTERED_POOL_CONFIG_0040

_CFG = PREREGISTERED_POOL_CONFIG_0040
_API = "http://127.0.0.1:11434"


def _residents() -> list[str] | None:
    try:
        with urllib.request.urlopen(f"{_API}/api/ps", timeout=5) as r:
            return [m["name"] for m in json.loads(r.read())["models"]]
    except Exception:  # noqa: BLE001
        return None


def _skip_or_fail_unreachable() -> None:
    if require_live_stack(False) == "fail":
        pytest.fail("Ollama unreachable (HARPYJA_REQUIRE_LIVE_STACK set)")
    pytest.skip("Ollama unreachable — live gate run skipped, not faked")


@pytest.mark.integration
def test_gate_run_on_exclusive_endpoint_records_proof(tmp_path):
    residents = _residents()
    if residents is None:
        _skip_or_fail_unreachable()
    foreign = [t for t in residents if t not in _CFG.model_tags]
    if foreign:
        pytest.skip(
            f"endpoint currently contended ({foreign}) — the exclusive-pass "
            "leg needs an exclusive endpoint; see the contended-stop test"
        )
    ledger_path = tmp_path / "gate_proof.json"
    result = run_gated_pool_pilot(
        _CFG,
        ledger_path=ledger_path,
        pilot_models=list(_CFG.model_tags),
        cases=[],
        run_cell=lambda case, model: pytest.fail("gate-proof pass runs no cells"),
        api_base=_API,
        live=True,
    )
    assert result["status"] == "completed"
    obj = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert obj["schema_version"] == "0041/pilot/2"
    checks = obj["exclusivity"]["checks"]
    assert len(checks) == 1 + len(_CFG.model_tags)  # start + one per block
    assert all(c["clean"] and c["timestamp"] for c in checks)
    assert obj["exclusivity"]["exclusivity_check_kind"] == "start-plus-per-block"


@pytest.mark.integration
def test_gate_run_on_contended_endpoint_stops_typed(tmp_path):
    residents = _residents()
    if residents is None:
        _skip_or_fail_unreachable()
    if not residents:
        pytest.skip(
            "no resident model — cannot deem the endpoint contended without "
            "touching it (this test fabricates no traffic)"
        )
    # Narrow the frozen set so a real resident is foreign to THIS run —
    # a genuine contended endpoint from the run's perspective, zero traffic.
    narrowed = dataclasses.replace(
        _CFG, model_tags=tuple(t for t in _CFG.model_tags if t not in residents)
        or ("no-such-model:0b",)
    )
    ledger_path = tmp_path / "gate_proof.json"
    executed: list[str] = []
    with pytest.raises(ExclusiveEndpointContended) as exc:
        run_gated_pool_pilot(
            narrowed,
            ledger_path=ledger_path,
            pilot_models=list(narrowed.model_tags),
            cases=[{"case_id": "c1"}],
            run_cell=lambda case, model: executed.append(model),
            api_base=_API,
            live=True,
        )
    assert exc.value.stop_id == "exclusive-endpoint-contended"
    assert executed == []  # zero cells
    obj = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert obj["entries"] == {}
    assert obj["exclusivity"]["checks"][-1]["clean"] is False


@pytest.mark.integration
def test_reload_churn_attribution_against_0040_clean_profile():
    """The AC8 attribution inputs are computable from committed evidence: the
    0040 CLEAN-run degrade profile is the comparison basis, and attribution
    is the pinned two-condition predicate — never a judgment call."""
    profile = clean_0040_degrade_profile()
    assert len(profile) == 5  # the 0040 findings: 5 persistent heavy-repo degrades
    # A run with no new degrades attributes nothing; a profile-known degrade
    # never counts as churn even when marked.
    assert attribute_reload_churn({}, profile, set()) == {}
    known = next(iter(profile))
    assert attribute_reload_churn({known: profile[known]}, profile, {known}) == {}