"""RED (0046 T15/T16, AC7): the total-pure five-sided verdict.

``decide_reactive_outcome`` maps (frozen config, BASELINE cells, NEW cells) to
exactly one of THREE typed members (under an UNDER_POWERED guard), in FROZEN
precedence, recording every true condition. DISSOLVES_TRADE is REFUTABLE — the
new counted side ``flagged-wrong-emitted`` can rise, so the lever CAN worsen the
verdict; a pure s->wc->flagged relabel breaches the CEILING (which sits below
baseline s->wc), and NEW wrong mass breaches the SUM.
"""

from __future__ import annotations

import dataclasses
import itertools

from harpyja.eval.reactive_config import PREREGISTERED_REACTIVE_CONFIG_0046 as CFG
from harpyja.eval.reactive_outcome import (
    ReactiveVerdict,
    decide_reactive_outcome,
    reactive_verdict_from_flags,
)

# The power floors are exercised by test_under_powered_guard_fires_below_floor;
# the verdict-logic tests use a floor-relaxed config so small fixtures reach the
# real branches (the floors are a guard, not the logic under test here).
CFG_L = dataclasses.replace(CFG, min_covered_baseline_cells=1, min_baseline_swc=0)


def _swc(model, i, *, confirmation="PASS"):
    # a fired wrong-submitted cell (s->wc when PASS, flagged-wrong-emitted on FAIL)
    return (f"c{i}::{model}", {
        "terminal_bucket": "wrong-file", "confidence_fired": True,
        "confirmation_outcome": confirmation, "confirmation_ran": True,
        "submission_outcome": "submitted", "submit_disposition": (
            "confirmed-then-submitted" if confirmation == "PASS" else "confirm-failed-flagged"),
    })


def _fu(model, i):
    return (f"c{i}::{model}", {
        "terminal_bucket": "no-citation", "confidence_fired": False,
        "confirmation_outcome": None, "confirmation_ran": False,
        "submission_outcome": "found-unsubmitted", "submit_disposition": "no-candidate",
    })


def _correct(model, i, *, disposition="never-triggered"):
    return (f"c{i}::{model}", {
        "terminal_bucket": "correct", "confidence_fired": False,
        "confirmation_outcome": "PASS", "confirmation_ran": True,
        "submission_outcome": "submitted", "submit_disposition": disposition,
    })


def _pad(cells, model, start, n):
    # pad with correct cells so power floors clear
    for i in range(start, start + n):
        k, v = _correct(model, i)
        cells[k] = v


def _base_new(baseline_pairs, new_pairs):
    m = "qwen3:8b"
    baseline = dict(baseline_pairs)
    new = dict(new_pairs)
    _pad(baseline, m, 100, 10)
    _pad(new, m, 100, 10)
    return baseline, new


# --- precedence flag grid-totality --------------------------------------------


def test_grid_totality_every_flag_tuple_types_exactly_one_member():
    for under, trades, dissolves in itertools.product([True, False], repeat=3):
        v = reactive_verdict_from_flags(under, trades, dissolves)
        assert isinstance(v, ReactiveVerdict)


def test_precedence_first_true_wins():
    assert reactive_verdict_from_flags(True, True, True) == ReactiveVerdict.UNDER_POWERED
    assert reactive_verdict_from_flags(False, True, True) == ReactiveVerdict.TRADES_AGAIN
    assert reactive_verdict_from_flags(False, False, True) == ReactiveVerdict.DISSOLVES_TRADE
    assert reactive_verdict_from_flags(False, False, False) == ReactiveVerdict.NO_EFFECT


# --- the three members over cells ---------------------------------------------


def test_dissolves_trade_when_fu_falls_and_nothing_reopens():
    # baseline: 3 s->wc + 3 fu; new: 3 s->wc (PASS, no flags) + 1 fu -> fu fell,
    # no new wrong mass, fwe=0.
    baseline, new = _base_new(
        [_swc("qwen3:8b", i) for i in range(3)] + [_fu("qwen3:8b", 10 + i) for i in range(3)],
        [_swc("qwen3:8b", i) for i in range(3)] + [_fu("qwen3:8b", 10)],
    )
    # pad new fu-cells that are no longer fu with correct (conversions ok)
    d = decide_reactive_outcome(CFG_L, baseline, new)
    assert d.verdict == ReactiveVerdict.DISSOLVES_TRADE
    assert d.fu_baseline == 3 and d.fu_new == 1


def test_trades_again_when_fu_rises():
    baseline, new = _base_new(
        [_fu("qwen3:8b", 10 + i) for i in range(2)],
        [_fu("qwen3:8b", 10 + i) for i in range(5)],
    )
    d = decide_reactive_outcome(CFG_L, baseline, new)
    assert d.verdict == ReactiveVerdict.TRADES_AGAIN
    assert "found-but-unsubmitted" in d.reopened


def test_flag_everything_breaches_ceiling_not_a_dissolve():
    # baseline: 4 s->wc; new: relabel ALL into flagged-wrong-emitted (sum flat,
    # but fwe == baseline_swc > ceiling=floor(0.5*4)=2) -> TRADES_AGAIN on fwe.
    baseline, new = _base_new(
        [_swc("qwen3:8b", i) for i in range(4)],
        [_swc("qwen3:8b", i, confirmation="FAIL") for i in range(4)],
    )
    d = decide_reactive_outcome(CFG_L, baseline, new)
    assert d.verdict == ReactiveVerdict.TRADES_AGAIN
    assert "flagged-wrong-emitted" in d.reopened
    assert d.flagged_wrong_emitted_new == 4 and d.ceiling == 2


def test_ceiling_and_sum_do_different_work():
    # A partial relabel within the ceiling keeps the sum flat AND fwe<=ceiling ->
    # NOT a trade on those axes.
    baseline, new = _base_new(
        [_swc("qwen3:8b", i) for i in range(4)],
        [_swc("qwen3:8b", 0, confirmation="FAIL")] + [_swc("qwen3:8b", i) for i in range(1, 4)],
    )
    d = decide_reactive_outcome(CFG_L, baseline, new)
    # fwe=1 <= ceiling 2; sum=4 == baseline 4 (not risen) -> no fu change -> NO_EFFECT
    assert d.verdict == ReactiveVerdict.NO_EFFECT
    assert d.flagged_wrong_emitted_new == 1


def test_4b_triggered_and_explored_net_negative_is_inert_with_cost_null():
    m = "qwen3.5:4b"
    baseline = {**dict([_correct(m, 0), _correct(m, 1)])}
    new = {**dict([
        (f"c0::{m}", {"terminal_bucket": "wrong-file", "confidence_fired": False,
                      "confirmation_outcome": "PASS", "confirmation_ran": True,
                      "submission_outcome": "submitted",
                      "submit_disposition": "triggered-and-explored"}),
        _correct(m, 1),
    ])}
    _pad(baseline, "qwen3:8b", 100, 10)
    _pad(new, "qwen3:8b", 100, 10)
    d = decide_reactive_outcome(CFG_L, baseline, new)
    # 4b net -1 but the regression is triggered-and-explored (reactive-explore
    # bytes) -> excused, not a counting net-negative.
    assert d.verdict != ReactiveVerdict.TRADES_AGAIN or "qwen3.5:4b-net" not in d.reopened


def test_4b_no_trigger_net_negative_is_trades_again():
    m = "qwen3.5:4b"
    baseline = {**dict([_correct(m, 0)])}
    new = {f"c0::{m}": {"terminal_bucket": "wrong-file", "confidence_fired": False,
                        "confirmation_outcome": "PASS", "confirmation_ran": True,
                        "submission_outcome": "submitted",
                        "submit_disposition": "never-triggered"}}
    _pad(baseline, "qwen3:8b", 100, 10)
    _pad(new, "qwen3:8b", 100, 10)
    d = decide_reactive_outcome(CFG_L, baseline, new)
    assert d.verdict == ReactiveVerdict.TRADES_AGAIN
    assert any("4b" in r or "qwen3.5" in r for r in d.reopened)


def test_under_powered_guard_fires_below_floor():
    baseline = dict([_swc("qwen3:8b", 0)])  # only 1 cell -> below floor 8
    new = dict([_swc("qwen3:8b", 0)])
    d = decide_reactive_outcome(CFG, baseline, new)
    assert d.verdict == ReactiveVerdict.UNDER_POWERED


def test_all_true_conditions_recorded():
    baseline, new = _base_new(
        [_fu("qwen3:8b", 10 + i) for i in range(2)],
        [_fu("qwen3:8b", 10 + i) for i in range(5)],
    )
    d = decide_reactive_outcome(CFG_L, baseline, new)
    assert "trades-again" in d.conditions_true


def test_config_fraction_frozen_and_verdict_is_dataclass():
    assert 0 < CFG.flagged_wrong_emitted_ceiling_fraction < 1
    d = decide_reactive_outcome(CFG, dict([_swc("qwen3:8b", 0)]), dict([_swc("qwen3:8b", 0)]))
    assert dataclasses.is_dataclass(d)


# --- Spec 0046 (T22, AC7): the predicate freeze (committed BEFORE any number) --
def test_committed_predicate_matches_computed_truth():
    """The frozen five-sided predicate artifact matches the in-code truth: the
    counted sides, the verdict members + precedence, and the ceiling fraction.
    Committed pre-baseline so the predicate cannot be reshaped after the numbers."""
    import hashlib
    import json
    from pathlib import Path

    from harpyja.eval.reactive_observability import REACTIVE_SIDES

    # Evidence-path convention: specs/.archive first, live specs/ fallback.
    root = Path(__file__).resolve().parents[2]
    rel = "predicate_freeze/five_sided_predicate.json"
    archived = root / "specs" / ".archive" / "0046-submission" / rel
    live = root / "specs" / "0046-submission" / rel
    path = archived if archived.is_file() else live
    committed = json.loads(path.read_text())

    assert committed["counted_sides"] == sorted(REACTIVE_SIDES)
    assert committed["verdict_members"] == [m.value for m in ReactiveVerdict]
    assert committed["verdict_precedence"] == list(CFG.verdict_precedence)
    assert (
        committed["flagged_wrong_emitted_ceiling_fraction"]
        == CFG.flagged_wrong_emitted_ceiling_fraction
    )
    assert committed["baseline_band"] == list(CFG.baseline_band)
    # the frozen digest is a valid sha256 over the payload (minus the hash field).
    frozen = committed["predicate_hash"]
    recomputed = {k: v for k, v in committed.items() if k != "predicate_hash"}
    payload = json.dumps(recomputed, sort_keys=True).encode("utf-8")
    assert hashlib.sha256(payload).hexdigest() == frozen
    assert len(frozen) == 64
