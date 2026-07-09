"""spec 0036 — pure pilot aggregation glue (AC4, AC5 degrade posture).

Maps per-case, per-arm pilot outcomes to `PilotPair`s and applies the frozen
`decide_ac8` gate under `PREREGISTERED_AC8_CONFIG_0036`. Degrade posture: a
typed environment degrade on EITHER arm is not a capability observation — the
case is EXCLUDED from the pairs and RECORDED by cause (never counted clean,
never silently absorbed); the gate runs on the remaining pairs and the report
keeps the exclusions visible beside the verdict and the config hash it ran
under. Pure, no live I/O — the live runner feeds it buckets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from harpyja.eval.ac8_pilot import (
    AC8_CONFIG_HASH_0036,
    PREREGISTERED_AC8_CONFIG_0036,
    Ac8PilotConfig,
    PilotPair,
    config_hash,
    decide_from_pairs,
    signal_bearing_discordant,
)
from harpyja.eval.locate_accuracy import LocateBucket


@dataclass(frozen=True)
class PilotCaseOutcome:
    """One pilot case's two-arm result: a bucket per arm, or a typed degrade
    cause where an arm never produced a capability observation."""

    case_id: str
    bucket_a: LocateBucket | None
    bucket_b: LocateBucket | None
    degrade_a: str | None = None
    degrade_b: str | None = None


def build_pilot_pairs(
    outcomes: list[PilotCaseOutcome],
) -> tuple[list[PilotPair], dict[str, str]]:
    """Split outcomes into scoreable `PilotPair`s and recorded exclusions.

    A case missing an arm's bucket MUST carry that arm's degrade cause — a
    bucket-less arm with no cause is a contract violation, raised loudly (a
    fabricated exclusion reason would mask what actually happened).
    """
    pairs: list[PilotPair] = []
    excluded: dict[str, str] = {}
    for o in outcomes:
        causes: list[str] = []
        if o.bucket_a is None:
            if not o.degrade_a:
                raise ValueError(
                    f"pilot case {o.case_id!r}: arm A has no bucket and no degrade cause"
                )
            causes.append(f"arm_a: {o.degrade_a}")
        if o.bucket_b is None:
            if not o.degrade_b:
                raise ValueError(
                    f"pilot case {o.case_id!r}: arm B has no bucket and no degrade cause"
                )
            causes.append(f"arm_b: {o.degrade_b}")
        if causes:
            excluded[o.case_id] = "; ".join(causes)
            continue
        pairs.append(
            PilotPair(case_id=o.case_id, bucket_a=o.bucket_a, bucket_b=o.bucket_b)
        )
    return pairs, excluded


def gate_report(
    outcomes: list[PilotCaseOutcome],
    cfg: Ac8PilotConfig = PREREGISTERED_AC8_CONFIG_0036,
) -> dict[str, Any]:
    """Apply the frozen gate and return the citable report: verdict, the config
    (and its hash — the freeze the pilot artifact must reference), the pair and
    signal counts, and the recorded exclusions."""
    pairs, excluded = build_pilot_pairs(outcomes)
    return {
        "outcome": decide_from_pairs(pairs, cfg),
        "config": cfg,
        "config_hash": AC8_CONFIG_HASH_0036 if cfg is PREREGISTERED_AC8_CONFIG_0036 else config_hash(cfg),
        "pairs_run": len(pairs),
        "signal_discordant": signal_bearing_discordant(pairs),
        "excluded": excluded,
    }
