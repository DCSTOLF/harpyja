"""Spec 0020 (D1/D2/D3) — the G3 outcome projection.

`classify_g3_outcome` is a pure function that sits ABOVE the byte-frozen 0019
`recommend_oq2` dispatcher (which emits only two strings, `recommended` /
`gate-confounded`) and adds the two reliability labels — `DEGRADED_DOMINATED` and
`NOT_SEPARABLE` — that the operator protocol reports. Keeping it here (not in
`recommend.py`) is what keeps the dispatcher un-perturbed (measurement-not-construction).

Precedence (D3): **DEGRADED_DOMINATED > GATE_CONFOUNDED > NOT_SEPARABLE >
RECOMMENDATION**. A degraded-dominated run means the tiers did not run, so the
false-escalation reading is itself untrustworthy — a broken apparatus invalidates the
reading before it is interpreted, hence degrade wins first. All true blocking
conditions are recorded on the result, not only the winning label.

The no-survivor signal `S` is derived from the byte-frozen `Recommendation` WITHOUT
touching the dispatcher: the no-survivor branch is the unique state with
`incumbent_validated is False AND advantage_exceeds_variance is False` (a
variance-beating flip carries `advantage_exceeds_variance is True`; a validated
incumbent carries `incumbent_validated is True`). `S` is computed ONLY when
`rank_sweep` actually ran (`outcome != "gate-confounded"`); under the gate-confound
short-circuit it is left n/a (`None`), so a phantom `NOT_SEPARABLE` is never booked
alongside `GATE_CONFOUNDED` in the ledger.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from harpyja.eval.recommend import OUTCOME_GATE_CONFOUNDED, Recommendation

# The four G3 outcome labels (UPPER_SNAKE display identifiers; the frozen dispatcher
# keeps its own two wire strings).
RECOMMENDATION = "RECOMMENDATION"
GATE_CONFOUNDED = "GATE_CONFOUNDED"
DEGRADED_DOMINATED = "DEGRADED_DOMINATED"
NOT_SEPARABLE = "NOT_SEPARABLE"


@dataclass(frozen=True)
class G3Classification:
    """One G3 verdict: the winning label + every true blocking condition.

    `no_survivor` is `None` under the gate-confound short-circuit (rank_sweep never
    ran), `True`/`False` otherwise. `indicative_only` is a sub-flag on `RECOMMENDATION`
    only (effective-N below the N-floor makes the pick deltas-only); it is always
    `False` on a typed null.
    """

    label: str
    degraded_dominated: bool
    gate_confounded: bool
    no_survivor: bool | None
    indicative_only: bool


def classify_g3_outcome(
    recommendation: Recommendation,
    aggregate: Mapping[str, object],
    eval_config,
) -> G3Classification:
    """Project the frozen recommendation + run aggregate to one G3 label (D3 order)."""
    degraded = bool(aggregate["degraded_dominated"])
    gate_confounded = recommendation.outcome == OUTCOME_GATE_CONFOUNDED

    # S — the no-survivor signal — is only meaningful when rank_sweep ran. Under the
    # gate-confound short-circuit the dispatcher never inspects the grid, so leave it
    # n/a (None) rather than reading the placeholder fields as a real no-survivor.
    if gate_confounded:
        no_survivor: bool | None = None
    else:
        no_survivor = (
            recommendation.incumbent_validated is False
            and recommendation.advantage_exceeds_variance is False
        )

    # Precedence D > G > S > default.
    if degraded:
        label = DEGRADED_DOMINATED
    elif gate_confounded:
        label = GATE_CONFOUNDED
    elif no_survivor:
        label = NOT_SEPARABLE
    else:
        label = RECOMMENDATION

    indicative_only = (
        label == RECOMMENDATION and int(aggregate["effective_n"]) < eval_config.n_floor
    )

    return G3Classification(
        label=label,
        degraded_dominated=degraded,
        gate_confounded=gate_confounded,
        no_survivor=no_survivor,
        indicative_only=indicative_only,
    )
