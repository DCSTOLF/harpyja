"""Spec 0043 — the FROZEN attribution-to-lever decision table (AC4, stage 1).

Stage 1 of the two-stage freeze: this table is frozen + hashed + committed
BEFORE any attribution number is computed or seen, so the lever choice is a
mechanical function of the numbers — never steered post-hoc toward a
convenient fix (the 0023/0026/0039/0040/0042 discipline applied to lever
selection). Stage 2 (``diagnosis_config``) freezes the SELECTED lever after
this table has picked it, before any live spend.

The frozen ranking rule (spec OQ1): the model dawdling AFTER locating names
the ``messages``-only submit-early prompt nudge — the cheapest lever, no
budget cost — and it outranks everything else. A wall-clock raise is the
LAST-resort lever (it multiplies bake-off wall-clock across models × cases)
and carries its "cheaper levers insufficient" rationale requirement AS DATA.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping, Sequence
from statistics import median
from typing import Any


@dataclasses.dataclass(frozen=True)
class LeverTable:
    """The frozen decision table: thresholds + the committed ranking rule."""

    table_id: str = "0043/lever-table/1"
    # Signal thresholds — derive_signals reads THESE (no second tuning spot).
    # Dawdle: median assistant turns spent AFTER the gold span was already in a
    # tool result, among located-but-unsubmitted cases.
    dawdle_min_turns: int = 2
    # Per-turn cost: mean reasoning chars/turn (0040 measured ~14.7k for
    # 14b/8b vs 3.9k for 4b; 10k marks the heavy-reasoning regime).
    reasoning_chars_high_per_turn: int = 10_000
    # Wall-clock dominance: fraction of non-submitted cases whose terminal
    # cause is the loop's own wall-clock expiry.
    wall_clock_dominant_fraction: float = 0.5
    # The committed ranking (highest priority first) — dawdle-after-locate
    # names the cheapest lever regardless of what else is high.
    ranking: tuple[str, ...] = (
        "after_locate_dawdle_high -> submit-early-prompt-nudge",
        "per_turn_cost_high -> cheaper-navigation-output-clamp",
        "wall_clock_expiry_dominant -> bounded-wall-clock-raise",
        "default -> submit-early-prompt-nudge",
    )


FROZEN_LEVER_TABLE_0043 = LeverTable()


def lever_table_hash(table: LeverTable) -> str:
    """The 0039/0040/0042 freeze shape: sha256 over the sorted-JSON asdict."""
    payload = json.dumps(dataclasses.asdict(table), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


LEVER_TABLE_HASH_0043 = lever_table_hash(FROZEN_LEVER_TABLE_0043)


@dataclasses.dataclass(frozen=True)
class LeverSignals:
    """The attribution-signal space the table is total over."""

    after_locate_dawdle_high: bool
    per_turn_cost_high: bool
    wall_clock_expiry_dominant: bool


@dataclasses.dataclass(frozen=True)
class LeverDecision:
    """The selected lever; a wall-clock raise carries its rationale
    requirement as data (auditable, not prose)."""

    lever: str
    requires_rationale: bool
    rationale_requirement: str | None


def derive_signals(records: Sequence[Mapping[str, Any]]) -> LeverSignals:
    """Signals derive mechanically from per-case attribution records via the
    frozen table's own thresholds."""
    t = FROZEN_LEVER_TABLE_0043

    dawdles = [
        r["turns_after_locate"]
        for r in records
        if r.get("turns_to_locate") is not None
        and r.get("terminal_cause") != "submitted"
    ]
    dawdle_high = bool(dawdles) and median(dawdles) >= t.dawdle_min_turns

    chars = [
        c
        for r in records
        for c in (r.get("reasoning_chars_per_turn") or [])
        if c is not None
    ]
    cost_high = bool(chars) and (sum(chars) / len(chars)) >= t.reasoning_chars_high_per_turn

    unsubmitted = [r for r in records if r.get("terminal_cause") != "submitted"]
    wall_dominant = bool(unsubmitted) and (
        sum(1 for r in unsubmitted if r.get("terminal_cause") == "wall-clock")
        / len(unsubmitted)
        >= t.wall_clock_dominant_fraction
    )

    return LeverSignals(
        after_locate_dawdle_high=dawdle_high,
        per_turn_cost_high=cost_high,
        wall_clock_expiry_dominant=wall_dominant,
    )


def select_lever(signals: LeverSignals) -> LeverDecision:
    """TOTAL over the signal space — exactly one lever per cell, in the frozen
    ranking order. No cell is a judgment call."""
    if signals.after_locate_dawdle_high:
        return LeverDecision(
            lever="submit-early-prompt-nudge",
            requires_rationale=False,
            rationale_requirement=None,
        )
    if signals.per_turn_cost_high:
        return LeverDecision(
            lever="cheaper-navigation-output-clamp",
            requires_rationale=False,
            rationale_requirement=None,
        )
    if signals.wall_clock_expiry_dominant:
        return LeverDecision(
            lever="bounded-wall-clock-raise",
            requires_rationale=True,
            rationale_requirement=(
                "a wall-clock raise alone requires a recorded rationale for why "
                "cheaper levers (prompt nudge, navigation clamp) were insufficient"
            ),
        )
    # Nothing high: the cheapest lever is the presumptive default (no budget
    # cost, byte-frozen params untouched).
    return LeverDecision(
        lever="submit-early-prompt-nudge",
        requires_rationale=False,
        rationale_requirement=None,
    )
