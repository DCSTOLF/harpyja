"""Spec 0048 — bake-off: driver smoke tests (T22 scaffolding).

The live grid is an OPERATOR run (``run_bakeoff.sh``); these tests exercise the
driver's control flow with injected seams — config-hash refusal, the
fewer-than-two-survivors halt (grid never runs), and resumability — WITHOUT a
model endpoint.
"""

from __future__ import annotations

import dataclasses

import pytest

from harpyja.eval.bakeoff_analysis import BakeoffOutcome
from harpyja.eval.bakeoff_config import PREREGISTERED_BAKEOFF_CONFIG_0048
from harpyja.eval.bakeoff_driver import run_bakeoff
from harpyja.eval.bakeoff_run import BakeoffPreflightObservations, BakeoffRunError

pytestmark = pytest.mark.integration

_CFG = PREREGISTERED_BAKEOFF_CONFIG_0048


def _passing(_tag):
    return BakeoffPreflightObservations(True, True, True, "reproducible")


def _cell(bucket="correct"):
    return lambda case_id, model: {"bucket": bucket}


def test_run_bakeoff_refuses_drifted_config(tmp_path):
    drifted = dataclasses.replace(_CFG, coverage_floor=35)
    with pytest.raises(BakeoffRunError):
        run_bakeoff(
            drifted, case_ids=["a__a-1"], reachability={"a__a-1": "conceptual"},
            ledger_path=tmp_path / "l.json", preflight_prober=_passing, cell_runner=_cell(),
        )


def test_run_bakeoff_halts_without_two_survivors_and_skips_grid(tmp_path):
    calls: list[tuple[str, str]] = []

    def counting_cell(case_id, model):
        calls.append((case_id, model))
        return {"bucket": "correct"}

    def only_14b_serves(tag):
        served = tag == "qwen3:14b"
        return BakeoffPreflightObservations(served, True, True, "reproducible")

    rep = run_bakeoff(
        _CFG, case_ids=["a__a-1"], reachability={"a__a-1": "conceptual"},
        ledger_path=tmp_path / "l.json", preflight_prober=only_14b_serves,
        cell_runner=counting_cell,
    )
    assert rep.outcome is BakeoffOutcome.INFRASTRUCTURE_HALTED
    assert calls == []  # grid never ran
    assert {e.tag for e in rep.exclusions} == {"qwen3:8b", "qwen3.5:4b"}


def test_run_bakeoff_resumes_recorded_cells(tmp_path):
    ledger = tmp_path / "l.json"
    calls: list[tuple[str, str]] = []

    def counting_cell(case_id, model):
        calls.append((case_id, model))
        return {"bucket": "correct"}

    cases = ["a__a-1", "a__a-2"]
    reach = {c: "conceptual" for c in cases}
    run_bakeoff(_CFG, case_ids=cases, reachability=reach, ledger_path=ledger,
                preflight_prober=_passing, cell_runner=counting_cell)
    first_pass = len(calls)
    assert first_pass == 3 * len(cases)  # 3 survivors x 2 cases

    # a second invocation resumes — no cell re-runs
    run_bakeoff(_CFG, case_ids=cases, reachability=reach, ledger_path=ledger,
                preflight_prober=_passing, cell_runner=counting_cell)
    assert len(calls) == first_pass  # nothing re-ran
