"""RED (0044 T14, AC5/AC8): the total pure verdict.

``decide_submission_outcome`` maps (frozen config, BEFORE cells, AFTER cells)
to exactly ONE of FIVE typed members under a FROZEN precedence (first match
wins), with every true condition recorded alongside the winner:

1. UNDER_POWERED   — coverage/fu floors CONSUMED (never dormant config);
2. NEVER_FIRES     — beneficiary (14b) firings <= the numeric threshold;
                     an 8b zero-firing rate NEVER triggers it;
3. STILL_TRADES_OFF — any model net-negative OR aggregate net < 0;
4. NUDGE_INERT     — fired but bought nothing (conversions=0, no fu drop) —
                     the inert-lever hole closed at the VERDICT level;
5. CONDITIONED_NUDGE_SHIPS — net >= 0 AND no model negative AND a BENEFIT
                     conjunct (conversions >= 1 OR fu_after < fu_before).

Grid-totality: every input returns an enum member, never raises (the
0020/0023/0043 discipline).
"""

import itertools

from harpyja.eval.submission_config import PREREGISTERED_SUBMISSION_CONFIG_0044
from harpyja.eval.submission_outcome import (
    SubmissionVerdict,
    decide_submission_outcome,
)

_CFG = PREREGISTERED_SUBMISSION_CONFIG_0044
M14, M8, M4 = "qwen3:14b", "qwen3:8b", "qwen3.5:4b"


def _cell(bucket, outcome=None, fired=False):
    return {"bucket": bucket, "submission_outcome": outcome,
            "confidence_fired": fired}


def _before(n_per_model=4, fu_keys=()):
    """A BEFORE grid clearing both floors by default: 12 cells, fu on demand."""
    cells = {}
    for m in (M14, M8, M4):
        for i in range(1, n_per_model + 1):
            key = f"c{i}::{m}"
            cells[key] = _cell("correct" if i == 1 else "empty")
    for key in fu_keys:
        cells[key] = _cell("empty", outcome="found-unsubmitted")
    return cells


_FU3 = (f"c2::{M14}", f"c3::{M14}", f"c2::{M8}")


def _after_from(before, buckets=None, fired=(), fu_keys=()):
    after = {}
    for key, cell in before.items():
        after[key] = _cell(
            (buckets or {}).get(key, cell["bucket"]),
            outcome="found-unsubmitted" if key in fu_keys else None,
            fired=key in fired,
        )
    return after


def test_under_powered_when_coverage_below_floor():
    before = {k: v for i, (k, v) in enumerate(
        sorted(_before(fu_keys=_FU3).items())) if i < 5}  # < 8 covered
    after = _after_from(before, fired={f"c2::{M14}"})
    decision = decide_submission_outcome(_CFG, before, after)
    assert decision.verdict is SubmissionVerdict.UNDER_POWERED
    assert "under-powered" in decision.conditions_true


def test_under_powered_when_fu_floor_unmet():
    # The fu floor is re-checked as a baseline-identity guard: adequate
    # coverage but fu_before < 3 is still UNDER_POWERED, never vacuous-drop.
    before = _before(fu_keys=_FU3[:2])  # fu_before = 2
    after = _after_from(before, fired={f"c2::{M14}"})
    decision = decide_submission_outcome(_CFG, before, after)
    assert decision.verdict is SubmissionVerdict.UNDER_POWERED
    assert decision.fu_before == 2


def test_never_fires_keyed_to_beneficiary_only():
    before = _before(fu_keys=_FU3)
    # Nothing fired anywhere: NEVER_FIRES (keyed to 14b).
    after = _after_from(before)
    decision = decide_submission_outcome(_CFG, before, after)
    assert decision.verdict is SubmissionVerdict.NEVER_FIRES
    # 8b zero-firing with 14b firing does NOT trigger the label — 8b's
    # pre-registered success criterion is regressions=0 at ANY firing rate.
    after2 = _after_from(
        before,
        buckets={f"c2::{M14}": "correct"},
        fired={f"c2::{M14}"},
        fu_keys=(f"c3::{M14}", f"c2::{M8}"),
    )
    decision2 = decide_submission_outcome(_CFG, before, after2)
    assert decision2.verdict is not SubmissionVerdict.NEVER_FIRES
    assert decision2.verdict is SubmissionVerdict.CONDITIONED_NUDGE_SHIPS


def test_still_trades_off_on_any_negative_model_net():
    # 14b converts 2, 8b regresses 1: aggregate net +1 but 8b net −1 —
    # an aggregate win that hides an 8b regression is NOT a ship.
    before = _before(fu_keys=_FU3)
    after = _after_from(
        before,
        buckets={
            f"c2::{M14}": "correct",
            f"c3::{M14}": "correct",
            f"c1::{M8}": "wrong-file",  # was correct → regression
        },
        fired={f"c2::{M14}", f"c3::{M14}", f"c1::{M8}"},
    )
    decision = decide_submission_outcome(_CFG, before, after)
    assert decision.verdict is SubmissionVerdict.STILL_TRADES_OFF
    assert decision.net == 1
    per_model = {r["model"]: r for r in decision.per_model}
    assert per_model[M8]["net"] == -1
    assert per_model[M14]["net"] == 2


def test_still_trades_off_on_negative_aggregate():
    before = _before(fu_keys=_FU3)
    after = _after_from(
        before,
        buckets={f"c1::{M14}": "empty"},  # was correct → regression
        fired={f"c1::{M14}", f"c2::{M14}"},
    )
    decision = decide_submission_outcome(_CFG, before, after)
    assert decision.verdict is SubmissionVerdict.STILL_TRADES_OFF
    assert decision.net == -1


def test_nudge_inert_when_fired_but_no_benefit():
    # The inert-lever hole: fired, ignored, nothing moved — net 0 with zero
    # conversions and no fu drop must NOT type a ship.
    before = _before(fu_keys=_FU3)
    after = _after_from(
        before,
        fired={f"c2::{M14}", f"c2::{M8}"},
        fu_keys=_FU3,  # fu_after == fu_before == 3
    )
    decision = decide_submission_outcome(_CFG, before, after)
    assert decision.verdict is SubmissionVerdict.NUDGE_INERT
    assert decision.conversions == 0
    assert decision.fu_after == decision.fu_before == 3


def test_ships_requires_benefit_conjunct():
    # Conversion + fu drop + no regressions anywhere → SHIPS.
    before = _before(fu_keys=_FU3)
    after = _after_from(
        before,
        buckets={f"c2::{M14}": "correct"},
        fired={f"c2::{M14}"},
        fu_keys=(f"c3::{M14}", f"c2::{M8}"),  # fu 3 → 2
    )
    decision = decide_submission_outcome(_CFG, before, after)
    assert decision.verdict is SubmissionVerdict.CONDITIONED_NUDGE_SHIPS
    assert decision.conversions == 1
    assert decision.regressions == 0
    # A pure fu-drop with zero conversions is ALSO benefit (net 0, fu 3→2).
    after2 = _after_from(
        before,
        buckets={},
        fired={f"c2::{M14}"},
        fu_keys=(f"c3::{M14}", f"c2::{M8}"),
    )
    decision2 = decide_submission_outcome(_CFG, before, after2)
    assert decision2.verdict is SubmissionVerdict.CONDITIONED_NUDGE_SHIPS


def test_precedence_first_match_wins():
    # Under-powered AND net-negative types UNDER_POWERED (frozen order), with
    # the trades-off condition still RECORDED among the true conditions.
    before = {f"c1::{M14}": _cell("correct"), f"c2::{M14}": _cell("empty")}
    after = _after_from(before, buckets={f"c1::{M14}": "empty"})
    decision = decide_submission_outcome(_CFG, before, after)
    assert decision.verdict is SubmissionVerdict.UNDER_POWERED
    assert "under-powered" in decision.conditions_true
    assert "still-trades-off" in decision.conditions_true


def test_all_true_conditions_recorded():
    # A zero-firing inert run records BOTH never-fires and nudge-inert; the
    # frozen precedence picks NEVER_FIRES.
    before = _before(fu_keys=_FU3)
    after = _after_from(before, fu_keys=_FU3)
    decision = decide_submission_outcome(_CFG, before, after)
    assert decision.verdict is SubmissionVerdict.NEVER_FIRES
    assert "never-fires" in decision.conditions_true
    assert "nudge-inert" in decision.conditions_true


def test_per_model_firing_rates_reported():
    before = _before(fu_keys=_FU3)
    after = _after_from(
        before,
        buckets={f"c2::{M14}": "correct"},
        fired={f"c2::{M14}", f"c3::{M14}", f"c1::{M8}", f"c2::{M8}"},
        fu_keys=(f"c2::{M8}",),
    )
    decision = decide_submission_outcome(_CFG, before, after)
    per_model = {r["model"]: r for r in decision.per_model}
    assert per_model[M14]["firings"] == 2
    assert per_model[M14]["firing_rate"] == 0.5  # 2 of 4 cells
    assert per_model[M8]["firings"] == 2
    assert per_model[M4]["firings"] == 0
    assert per_model[M4]["firing_rate"] == 0.0


def test_grid_totality_every_input_types():
    # Cartesian sweep: coverage {below, at}, 14b firing {0, >0}, per-model net
    # movement {regression, none, conversion}, fu_after {drop, hold} — every
    # combination returns an enum member, never raises.
    for coverage_ok, fires_14b, movement, fu_drop in itertools.product(
        (False, True), (False, True),
        ("regress-8b", "none", "convert-14b"), (False, True),
    ):
        before = _before(fu_keys=_FU3)
        if not coverage_ok:
            before = dict(sorted(before.items())[:4])
        buckets = {}
        if movement == "regress-8b" and f"c1::{M8}" in before:
            buckets[f"c1::{M8}"] = "wrong-file"
        if movement == "convert-14b" and f"c2::{M14}" in before:
            buckets[f"c2::{M14}"] = "correct"
        fired = {f"c2::{M14}"} if fires_14b else set()
        fu_after = () if fu_drop else tuple(k for k in _FU3 if k in before)
        after = _after_from(before, buckets=buckets, fired=fired, fu_keys=fu_after)
        decision = decide_submission_outcome(_CFG, before, after)
        assert isinstance(decision.verdict, SubmissionVerdict)
        assert isinstance(decision.conditions_true, tuple)
