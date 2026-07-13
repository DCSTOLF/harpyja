"""Spec 0043 T7 — the FROZEN attribution-to-lever decision table (AC4, stage 1).

The table is frozen + hashed + committed BEFORE any attribution number is
computed or seen — the fix choice is mechanical over the numbers, never
steered post-hoc. A wall-clock raise is a last-resort lever that carries its
"cheaper levers insufficient" rationale requirement AS DATA.
"""

import itertools

from harpyja.eval.lever_table import (
    FROZEN_LEVER_TABLE_0043,
    LEVER_TABLE_HASH_0043,
    LeverSignals,
    derive_signals,
    lever_table_hash,
    select_lever,
)


def test_lever_table_hash_is_stable():
    """The 0039/0040/0042 freeze shape: the committed constant IS the hash of
    the frozen table — any table edit breaks this pin loudly."""
    assert LEVER_TABLE_HASH_0043 == lever_table_hash(FROZEN_LEVER_TABLE_0043)
    assert len(LEVER_TABLE_HASH_0043) == 64  # sha256 hex


def test_lever_table_selection_is_total():
    """Exactly one lever for EVERY cell of the signal space — no gap, no
    overlap, no judgment call left open."""
    levers = set()
    for dawdle, cost, wall in itertools.product([False, True], repeat=3):
        decision = select_lever(LeverSignals(
            after_locate_dawdle_high=dawdle,
            per_turn_cost_high=cost,
            wall_clock_expiry_dominant=wall,
        ))
        assert decision.lever in {
            "submit-early-prompt-nudge",
            "cheaper-navigation-output-clamp",
            "bounded-wall-clock-raise",
        }
        levers.add(decision.lever)
    assert "submit-early-prompt-nudge" in levers  # the cheap lever is reachable


def test_submit_early_nudge_is_presumptive_first_rank_when_dawdle_after_locate():
    """The frozen ranking rule (OQ1): the model dawdling AFTER locating names
    the messages-only submit-early nudge — the cheapest lever, never a
    wall-clock raise — regardless of what else is high."""
    for cost, wall in itertools.product([False, True], repeat=2):
        decision = select_lever(LeverSignals(
            after_locate_dawdle_high=True,
            per_turn_cost_high=cost,
            wall_clock_expiry_dominant=wall,
        ))
        assert decision.lever == "submit-early-prompt-nudge"
        assert decision.requires_rationale is False


def test_wall_clock_raise_requires_recorded_rationale_flag():
    """A raise of the ceiling alone carries the 'cheaper levers insufficient'
    rationale requirement AS DATA (auditable, not prose)."""
    decision = select_lever(LeverSignals(
        after_locate_dawdle_high=False,
        per_turn_cost_high=False,
        wall_clock_expiry_dominant=True,
    ))
    assert decision.lever == "bounded-wall-clock-raise"
    assert decision.requires_rationale is True
    assert "cheaper" in decision.rationale_requirement


def test_derive_signals_uses_frozen_thresholds():
    """Signals derive mechanically from per-case attribution records via the
    table's OWN frozen thresholds — no second place to tune them."""
    t = FROZEN_LEVER_TABLE_0043
    dawdling = [
        {"turns_to_locate": 3, "turns_after_locate": t.dawdle_min_turns,
         "reasoning_chars_per_turn": [100], "terminal_cause": "wall-clock"},
        {"turns_to_locate": 2, "turns_after_locate": t.dawdle_min_turns + 1,
         "reasoning_chars_per_turn": [200], "terminal_cause": "wall-clock"},
    ]
    signals = derive_signals(dawdling)
    assert signals.after_locate_dawdle_high is True
    assert signals.per_turn_cost_high is False
    assert signals.wall_clock_expiry_dominant is True

    quick_submit = [
        {"turns_to_locate": 3, "turns_after_locate": 0,
         "reasoning_chars_per_turn": [t.reasoning_chars_high_per_turn + 1],
         "terminal_cause": "submitted"},
    ]
    signals = derive_signals(quick_submit)
    assert signals.after_locate_dawdle_high is False
    assert signals.per_turn_cost_high is True
    assert signals.wall_clock_expiry_dominant is False
