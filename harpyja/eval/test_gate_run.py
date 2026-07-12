"""Spec 0041 — the gated live-run driver (AC1, AC2) + reload-churn attribution (AC8).

``run_gated_pool_pilot`` wraps the pilot loop in the exclusive-endpoint gate:
start check + a re-check BEFORE EACH model block, every check recorded into the
``0041/pilot/2`` ledger's exclusivity proof. Contention → the typed stop
``exclusive-endpoint-contended`` — refuse, don't warn; no bypass exists.
"""

from __future__ import annotations

import inspect
import json

import pytest

from harpyja.eval.exclusivity_gate import ExclusiveEndpointContended
from harpyja.eval.gate_run import run_gated_pool_pilot
from harpyja.eval.pool_precheck import (
    POOL_CONFIG_HASH_0040,
    PREREGISTERED_POOL_CONFIG_0040,
)

_CFG = PREREGISTERED_POOL_CONFIG_0040
_API = "http://127.0.0.1:11434"
_CASES = [{"case_id": "c1"}, {"case_id": "c2"}]


def _clean_entry(case: dict, model: str) -> dict:
    return {"bucket": "correct", "degrade": None, "attempts": 1}


class _ScheduledPs:
    """A fake /api/ps whose Nth call returns the Nth resident list."""

    def __init__(self, schedule: list[list[str]]):
        self.schedule = list(schedule)
        self.calls = 0

    def __call__(self, api_base: str) -> list[str]:
        residents = self.schedule[min(self.calls, len(self.schedule) - 1)]
        self.calls += 1
        return residents


def test_gated_run_refuses_to_start_on_contended_endpoint_zero_cells(tmp_path):
    ledger_path = tmp_path / "ledger.json"
    executed: list[tuple[str, str]] = []

    def run_cell(case: dict, model: str) -> dict:
        executed.append((case["case_id"], model))
        return _clean_entry(case, model)

    with pytest.raises(ExclusiveEndpointContended) as exc:
        run_gated_pool_pilot(
            _CFG,
            ledger_path=ledger_path,
            pilot_models=list(_CFG.model_tags),
            cases=_CASES,
            run_cell=run_cell,
            ps_reader=_ScheduledPs([["mistral:7b"]]),
            api_base=_API,
            live=True,
        )
    assert exc.value.stop_id == "exclusive-endpoint-contended"
    assert executed == []  # zero cells executed
    # The refusal itself is auditable: the ledger carries the failed check
    # and zero entries.
    obj = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert obj["schema_version"] == "0041/pilot/2"
    assert obj["entries"] == {}
    failed = obj["exclusivity"]["checks"][-1]
    assert failed["clean"] is False
    assert failed["foreign"] == ["mistral:7b"]
    assert failed["timestamp"]


def test_gated_run_has_no_bypass_or_force_parameter():
    """The gate is not a lever (the 0039 run_ab_paired precedent): the only
    sanctioned unblock is changing the environment."""
    params = set(inspect.signature(run_gated_pool_pilot).parameters)
    forbidden = {"force", "bypass", "allow_contended", "skip_gate", "ignore_contention"}
    assert params & forbidden == set()


def test_gated_run_mid_run_contention_stops_before_block_and_types_boundary_suspect(
    tmp_path,
):
    """The AC2 worked example, outcome-blind on a flipping fake: clean before
    blocks 1 and 2, foreign before block 3 → block 3 never runs, block 2's
    cells (all since the last clean check) are suspect, block 1's stay valid
    under their own recorded clean checks."""
    ledger_path = tmp_path / "ledger.json"
    m1, m2, m3 = _CFG.model_tags
    executed: list[tuple[str, str]] = []

    def run_cell(case: dict, model: str) -> dict:
        executed.append((case["case_id"], model))
        return _clean_entry(case, model)

    # Checks fire: start, pre-block m1, pre-block m2, pre-block m3 (foreign).
    ps = _ScheduledPs([[], [], [], ["llama3:8b"]])

    with pytest.raises(ExclusiveEndpointContended):
        run_gated_pool_pilot(
            _CFG,
            ledger_path=ledger_path,
            pilot_models=[m1, m2, m3],
            cases=_CASES,
            run_cell=run_cell,
            ps_reader=ps,
            api_base=_API,
            live=True,
        )

    # Block 3 never ran.
    assert (c := [m for _, m in executed]) and m3 not in c
    obj = json.loads(ledger_path.read_text(encoding="utf-8"))
    entries = obj["entries"]
    # Block 1's cells remain valid (no suspect marker)...
    for case in _CASES:
        assert entries[f"{case['case_id']}::{m1}"].get("status") is None
    # ...block 2's cells — all since the last clean check — are suspect,
    # their original observations retained (invalidated, not erased).
    for case in _CASES:
        cell = entries[f"{case['case_id']}::{m2}"]
        assert cell["status"] == "suspect"
        assert cell["bucket"] == "correct"
    # No block-3 cells exist.
    assert not any(key.endswith(f"::{m3}") for key in entries)
    # The contamination boundary is recorded: the last check is the failed
    # one, with its timestamp and the foreign tag.
    checks = obj["exclusivity"]["checks"]
    assert [c["clean"] for c in checks] == [True, True, True, False]
    assert checks[-1]["foreign"] == ["llama3:8b"]
    assert checks[-1]["timestamp"]


def test_gated_run_writes_full_exclusivity_log_at_0041_pilot_2(tmp_path):
    ledger_path = tmp_path / "ledger.json"
    models = list(_CFG.model_tags)

    result = run_gated_pool_pilot(
        _CFG,
        ledger_path=ledger_path,
        pilot_models=models,
        cases=_CASES,
        run_cell=_clean_entry,
        ps_reader=_ScheduledPs([[]]),
        api_base=_API,
        live=True,
    )
    assert result["status"] == "completed"
    obj = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert obj["schema_version"] == "0041/pilot/2"
    assert obj["config_hash"] == POOL_CONFIG_HASH_0040
    record = obj["exclusivity"]
    # Every check recorded — start + one per block — each with timestamp.
    assert len(record["checks"]) == 1 + len(models)
    assert all(c["timestamp"] and c["clean"] for c in record["checks"])
    assert record["exclusivity_check_kind"] == "start-plus-per-block"
    assert record["model_set"] == list(_CFG.model_tags)
    assert record["unseeable_residuals"] == [
        "intra-block-window",
        "same-tag-contention",
    ]
    # All cells ran and recorded.
    assert len(obj["entries"]) == len(models) * len(_CASES)


def test_attribute_reload_churn_requires_new_degrade_and_expires_at_reset_marker():
    """AC8 operationalized — attribution is a checkable condition, never a
    close-time judgment call: churn-attributable iff NEW vs the committed 0040
    clean-run profile AND carrying the observed-reload marker."""
    from harpyja.eval.gate_run import attribute_reload_churn

    clean_0040_profile = {
        "django__django-11099::qwen3.5:4b": "model-unreachable",
    }
    this_run = {
        # Already in the clean profile → a standing constraint, not churn.
        "django__django-11099::qwen3.5:4b": "model-unreachable",
        # New AND marked with an observed expires_at reset → churn-attributable.
        "astropy__astropy-12907::qwen3:14b": "model-unreachable",
        # New but NO reload marker → unattributed, never assumed.
        "sympy__sympy-13480::qwen3:8b": "verifier:timeout",
    }
    markers = {"astropy__astropy-12907::qwen3:14b"}
    assert attribute_reload_churn(this_run, clean_0040_profile, markers) == {
        "astropy__astropy-12907::qwen3:14b": "model-unreachable"
    }
    # No degrades → nothing attributable.
    assert attribute_reload_churn({}, clean_0040_profile, markers) == {}
    # A marker alone (degrade in the clean profile) does not attribute.
    assert (
        attribute_reload_churn(
            {"django__django-11099::qwen3.5:4b": "model-unreachable"},
            clean_0040_profile,
            {"django__django-11099::qwen3.5:4b"},
        )
        == {}
    )


def test_clean_0040_degrade_profile_loads_the_committed_ledger():
    """AC8's comparison basis: the per-cell typed-degrade profile of the
    committed 0040 CLEAN run (run-2; the archived run-1 is the contaminated
    one and must never be the baseline)."""
    from harpyja.eval.gate_run import clean_0040_degrade_profile

    profile = clean_0040_degrade_profile()
    assert set(profile) == {
        "astropy__astropy-12907::qwen3.5:4b",
        "matplotlib__matplotlib-21568::qwen3:14b",
        "pylint-dev__pylint-7080::qwen3.5:4b",
        "pytest-dev__pytest-10081::qwen3:8b",
        "sympy__sympy-16792::qwen3.5:4b",
    }
    assert all(profile.values())  # every entry is a TYPED degrade cause


def test_gated_run_refuses_without_live_flag(tmp_path):
    from harpyja.eval.pool_pilot import PoolRunError

    with pytest.raises(PoolRunError, match="live=True"):
        run_gated_pool_pilot(
            _CFG,
            ledger_path=tmp_path / "ledger.json",
            pilot_models=list(_CFG.model_tags),
            cases=_CASES,
            run_cell=_clean_entry,
            ps_reader=_ScheduledPs([[]]),
            api_base=_API,
        )