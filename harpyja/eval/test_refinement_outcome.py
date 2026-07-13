"""RED (0045 T15, AC7): the total-pure SIX-member refinement verdict.

``decide_refinement_outcome`` maps (frozen config, BEFORE cells, AFTER cells,
named-cell outcomes) to exactly one of six typed members in FROZEN precedence
(worse-first, first-true-wins), recording EVERY true condition. Grid-totality:
every input tuple selects exactly one member and the function never raises.
The four-sided ledger (conversions / regressions / s->wc / fu) plus the
record-only unfired-s->wc cross-check are surfaced per model.
"""

import itertools

from harpyja.eval.refinement_config import PREREGISTERED_REFINEMENT_CONFIG_0045
from harpyja.eval.refinement_outcome import (
    RefinementVerdict,
    decide_refinement_outcome,
)

_CFG = PREREGISTERED_REFINEMENT_CONFIG_0045

# Comparator (0044): s->wc = 5, fu = 1, aggregate net = 2.
_M = ("qwen3:14b", "qwen3:8b", "qwen3.5:4b")


def _cell(bucket, fired=False, fu=False):
    return {
        "bucket": bucket,
        "confidence_fired": fired,
        "submission_outcome": "found-unsubmitted" if fu else "submitted",
    }


def _cells(specs):
    """specs: dict key -> (before_bucket, after_bucket, fired, fu)."""
    before, after = {}, {}
    for key, (bb, ab, fired, fu) in specs.items():
        before[key] = _cell(bb)
        after[key] = _cell(ab, fired=fired, fu=fu)
    return before, after


def _pad(before, after, n=8):
    # Pad with correct->correct cells so the coverage floor (8) is cleared.
    for i in range(n):
        k = f"pad-{i}::qwen3:14b"
        before[k] = _cell("correct")
        after[k] = _cell("correct")
    return before, after


_ALL_CORRECT_NAMED = {"django__django-14315::qwen3:8b": "correct"}


def test_under_powered_when_covered_joined_below_8():
    before, after = _cells({"a::qwen3:14b": ("empty", "correct", False, False)})
    d = decide_refinement_outcome(_CFG, before, after, _ALL_CORRECT_NAMED)
    assert d.verdict == RefinementVerdict.UNDER_POWERED
    assert "under-powered" in d.conditions_true


def test_trades_directions_swc_dropped_fu_rose():
    # s->wc < 5 (improved) but fu > 1 (reopened the (b) direction).
    specs = {
        f"fu{i}::qwen3:14b": ("empty", "empty", False, True) for i in range(2)
    }
    before, after = _cells(specs)
    before, after = _pad(before, after)
    d = decide_refinement_outcome(_CFG, before, after, _ALL_CORRECT_NAMED)
    assert d.verdict == RefinementVerdict.TRADES_DIRECTIONS
    assert d.reopened_direction == "found-but-unsubmitted"


def test_trades_directions_fu_dropped_swc_rose():
    # fu < 1 but s->wc > 5 (reopened the (a) direction).
    specs = {
        f"sw{i}::qwen3:8b": ("empty", "wrong-file", True, False) for i in range(6)
    }
    before, after = _cells(specs)
    before, after = _pad(before, after)
    d = decide_refinement_outcome(_CFG, before, after, _ALL_CORRECT_NAMED)
    assert d.verdict == RefinementVerdict.TRADES_DIRECTIONS
    assert d.reopened_direction == "silence-to-wrong-confidence"


def test_residual_persists_when_django_14315_8b_not_correct():
    before, after = _cells({"x::qwen3:14b": ("empty", "correct", False, False)})
    before, after = _pad(before, after)
    named = {"django__django-14315::qwen3:8b": "wrong-file"}
    d = decide_refinement_outcome(_CFG, before, after, named)
    assert d.verdict == RefinementVerdict.RESIDUAL_PERSISTS
    assert d.residual and "django__django-14315" in d.residual


def test_gate_inert_when_no_benefit():
    # Reproduce 0044 exactly: s->wc == 5, fu == 1, net == 2 (== 0044) → no
    # BENEFIT (nothing strictly improved) → INERT, never CALIBRATED.
    specs = {}
    for i in range(5):
        specs[f"sw{i}::qwen3:8b"] = ("empty", "wrong-file", True, False)
    specs["fu0::qwen3:14b"] = ("empty", "empty", False, True)
    before, after = _cells(specs)
    before, after = _pad(before, after)
    d = decide_refinement_outcome(_CFG, before, after, _ALL_CORRECT_NAMED)
    assert d.verdict == RefinementVerdict.GATE_INERT
    assert "gate-inert" in d.conditions_true


def test_gate_inert_even_when_both_costs_rose_and_net_not_improved():
    # s->wc > 5 AND fu > 1 (both rose) AND net not improved → no BENEFIT,
    # not trade-shaped (both directions worse) → INERT (the recorded caveat).
    specs = {}
    for i in range(6):
        specs[f"sw{i}::qwen3:8b"] = ("empty", "wrong-file", True, False)
    for i in range(2):
        specs[f"fu{i}::qwen3:14b"] = ("empty", "empty", False, True)
    before, after = _cells(specs)
    before, after = _pad(before, after)
    d = decide_refinement_outcome(_CFG, before, after, _ALL_CORRECT_NAMED)
    assert d.verdict == RefinementVerdict.GATE_INERT
    # The risen classes are recorded as data.
    assert d.swc_total > 5 and d.fu_total > 1


def test_gate_calibrated_requires_all_conjuncts():
    # s->wc drops to 0, fu 0, net >= 0, no model negative, residual correct.
    specs = {"conv::qwen3:14b": ("empty", "correct", False, False)}
    before, after = _cells(specs)
    before, after = _pad(before, after)
    d = decide_refinement_outcome(_CFG, before, after, _ALL_CORRECT_NAMED)
    assert d.verdict == RefinementVerdict.GATE_CALIBRATED
    assert d.swc_total == 0 and d.fu_total == 0
    assert d.benefit is True


def test_gate_calibrated_reachable_at_bucket_net_zero_head_to_head_regression():
    # net 0 on the bucket axis (a head-to-head regression vs 0044's +2), but
    # s->wc dropped → BENEFIT → CALIBRATED. The head-to-head net is recorded.
    specs = {}  # no conversions, no regressions → bucket net 0
    before, after = _cells(specs)
    before, after = _pad(before, after)
    d = decide_refinement_outcome(_CFG, before, after, _ALL_CORRECT_NAMED)
    assert d.verdict == RefinementVerdict.GATE_CALIBRATED
    assert d.aggregate_net == 0
    assert d.head_to_head_net_delta == 0 - 2  # vs 0044's +2


def test_miscalibration_remains_terminal_else_names_failed_conjunct():
    # Benefit holds (s->wc dropped) and residual correct and not trade-shaped,
    # but a model is net-negative → a CALIBRATED conjunct fails → the terminal
    # else, naming the failed conjunct.
    specs = {"reg::qwen3:8b": ("correct", "wrong-file", False, False)}
    before, after = _cells(specs)
    before, after = _pad(before, after)
    d = decide_refinement_outcome(_CFG, before, after, _ALL_CORRECT_NAMED)
    assert d.verdict == RefinementVerdict.MISCALIBRATION_REMAINS
    assert d.failed_conjunct


def test_all_true_conditions_recorded():
    specs = {f"sw{i}::qwen3:8b": ("empty", "wrong-file", True, False) for i in range(6)}
    for i in range(2):
        specs[f"fu{i}::qwen3:14b"] = ("empty", "empty", False, True)
    before, after = _cells(specs)
    before, after = _pad(before, after)
    d = decide_refinement_outcome(_CFG, before, after, _ALL_CORRECT_NAMED)
    assert isinstance(d.conditions_true, tuple)
    assert d.verdict.name in _CFG.verdict_precedence


def test_grid_totality_every_tuple_types_exactly_one_member():
    # Cartesian sweep: for every combination of (swc, fu, net-sign, residual,
    # benefit-ish) the function returns exactly one member and never raises.
    for swc_n, fu_n, conv_n, reg_n, residual_ok in itertools.product(
        (0, 5, 6), (0, 1, 2), (0, 1), (0, 1), (True, False)
    ):
        specs = {}
        for i in range(swc_n):
            specs[f"sw{i}::qwen3:8b"] = ("empty", "wrong-file", True, False)
        for i in range(fu_n):
            specs[f"fu{i}::qwen3:14b"] = ("empty", "empty", False, True)
        for i in range(conv_n):
            specs[f"cv{i}::qwen3:14b"] = ("empty", "correct", False, False)
        for i in range(reg_n):
            specs[f"rg{i}::qwen3.5:4b"] = ("correct", "wrong-file", False, False)
        before, after = _cells(specs)
        before, after = _pad(before, after)
        named = {
            "django__django-14315::qwen3:8b": "correct" if residual_ok else "wrong-file"
        }
        d = decide_refinement_outcome(_CFG, before, after, named)
        assert isinstance(d.verdict, RefinementVerdict)
