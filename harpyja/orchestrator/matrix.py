"""Planning matrix — the single source of truth for routing (spec 0008, AC3).

`plan_ladder(mode, classification, index_ready)` returns the **planned tier
ladder** for a request. The ladder executes that sequence; for `auto`, the
Verification Gate decides whether the trailing Tier-2 step actually runs, so the
realized `tiers_run` is a prefix of the planned ladder.

`index_ready` false means the manifest/symbol index is not built, so the Tier-0
**seed** is skipped and the model tier runs query-only — the planned sequence
drops its leading `0`. A not-ready index is a routing variant, not a floor
failure.

The escalation-trigger rules in the orchestrator are *derived from* this table;
on any apparent conflict, the table wins.
"""

from __future__ import annotations

from harpyja.orchestrator.classify import Classification
from harpyja.server.types import Mode

# (mode, classification) -> planned ladder when the index IS ready (seed present).
# The index_ready=False variant is this ladder with a leading 0 removed.
_SEEDED_LADDER: dict[tuple[Mode, Classification], list[int]] = {
    ("auto", "point"): [0, 1, 2],
    ("auto", "broad"): [0, 2],
    ("fast", "point"): [0, 1],
    ("fast", "broad"): [0, 1],  # fast wins over broad: ceiling is Tier-1
    ("deep", "point"): [0, 2],  # deep ignores classification
    ("deep", "broad"): [0, 2],
}


def plan_ladder(mode: Mode, classification: Classification, index_ready: bool) -> list[int]:
    """Return the planned tier ladder for one (mode, classification, index_ready)."""
    ladder = _SEEDED_LADDER[(mode, classification)]
    if index_ready:
        return list(ladder)
    # No index → no Tier-0 seed; drop the leading 0, run the model tier query-only.
    return [tier for tier in ladder if tier != 0]
