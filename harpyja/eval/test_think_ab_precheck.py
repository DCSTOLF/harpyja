"""Spec 0039 — AC5: the upper-bound feasibility pre-check that GATES the live run."""

from __future__ import annotations

from harpyja.eval.ac8_pilot import AC8_CONFIG_HASH_0036
from harpyja.eval.think_ab import PRECHECK_STOP, PREREGISTERED_AB_CONFIG_0039
from harpyja.eval.think_ab_precheck import (
    PRECHECK_PROJECTION_KIND,
    ab_power_precheck,
    committed_pilot_ledger_path,
    load_committed_pilot_ledger,
    run_precheck,
)

_CFG = PREREGISTERED_AB_CONFIG_0039


def _fake_ledger(buckets: dict[str, str], model: str = _CFG.lm_model) -> dict:
    return {
        "config_hash": "f" * 64,
        "entries": {
            f"{cid}::{model}": {"bucket": bucket, "degrade": None, "attempts": 1}
            for cid, bucket in buckets.items()
        },
    }


def test_ab_power_precheck_upper_bound_feasibility_from_0036_ledger():
    # 7 piloted conceptual cases, 4 located by the pinned arm → rate 4/7 →
    # projected UPPER BOUND over the 15-case stratum = round(15*4/7) = 9 >= 8
    # → PROCEED. The projection is LABELED an upper-bound feasibility check:
    # the pilot measured cross-MODEL discordance, which BOUNDS but cannot
    # estimate within-model think-flip rates (every located case is assumed to
    # flip — a same-model contrast flips far fewer).
    ledger = _fake_ledger(
        {
            "a": "correct",
            "b": "right-file-wrong-span",
            "c": "right-file-wrong-span",
            "d": "right-file-wrong-span",
            "e": "empty",
            "f": "wrong-file",
            "g": "empty",
        }
    )
    reachability = {cid: "conceptual" for cid in "abcdefg"}
    outcome = ab_power_precheck(
        ledger, reachability, _CFG, full_conceptual_n=15
    )
    assert outcome.projection_kind == PRECHECK_PROJECTION_KIND == "upper-bound-feasibility"
    assert outcome.piloted_conceptual_n == 7
    assert outcome.located_conceptual == 4
    assert outcome.projected_upper_bound == 9
    assert outcome.floor == 8
    assert outcome.outcome == "proceed"


def test_precheck_under_powered_stop_gates_live_run():
    # 1/7 located → projected upper bound round(15/7) = 2 < 8 → the typed stop.
    # The stop is the run's honest deliverable and names the 0036
    # pool-enlargement carry-forward as the next step.
    ledger = _fake_ledger(
        {c: ("correct" if c == "a" else "empty") for c in "abcdefg"}
    )
    reachability = {cid: "conceptual" for cid in "abcdefg"}
    outcome = ab_power_precheck(ledger, reachability, _CFG, full_conceptual_n=15)
    assert outcome.outcome == PRECHECK_STOP
    assert "pool" in outcome.next_step and "0036" in outcome.next_step


def test_precheck_projects_on_arm_degrade_asymmetry():
    ledger = _fake_ledger({c: "correct" for c in "abcdefgh"})
    reachability = {cid: "conceptual" for cid in "abcdefgh"}
    # A projected on-arm truncation fraction above the frozen threshold is a
    # predictable CONFOUNDED — surfaced for free BEFORE wall-clock is spent.
    warned = ab_power_precheck(
        ledger,
        reachability,
        _CFG,
        full_conceptual_n=15,
        on_arm_truncation_fraction=0.5,
    )
    assert warned.degrade_warning is not None
    assert "truncation" in warned.degrade_warning
    # Absent per-turn evidence the warning says so honestly — never silent.
    unknown = ab_power_precheck(ledger, reachability, _CFG, full_conceptual_n=15)
    assert unknown.degrade_warning is not None
    assert "unavailable" in unknown.degrade_warning


def test_precheck_loads_committed_ledger_archive_first():
    # The committed evidence path resolves specs/.archive first (the 79f7bf2
    # evidence-path convention) and the ledger cites the 0036 config hash.
    path = committed_pilot_ledger_path()
    assert ".archive" in str(path)
    ledger = load_committed_pilot_ledger()
    assert ledger["config_hash"] == AC8_CONFIG_HASH_0036


def test_precheck_projects_only_first_10_of_19_conceptual_subset():
    # THE REAL COMMITTED EVIDENCE: the pilot covered only the first 10 of 19
    # cases → the projectable conceptual subset is 7 (< 15); the 14b arm
    # located 3 of them → projected upper bound round(15*3/7) = 6 < 8 → the
    # pre-check fires UNDER_POWERED_STOP. This is the spec's honest arithmetic,
    # test-pinned to the committed truth.
    outcome = run_precheck(_CFG)
    assert outcome.piloted_conceptual_n == 7
    assert outcome.full_conceptual_n == 15
    assert outcome.located_conceptual == 3
    assert outcome.projected_upper_bound == 6
    assert outcome.outcome == PRECHECK_STOP
