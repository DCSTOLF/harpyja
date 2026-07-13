"""Spec 0043 — the total pure AC6 verdict.

``decide_diagnosis_outcome`` maps (frozen config, retained per-case pairs) to
exactly one of four typed branches, in frozen precedence order:

1. ``CLOCK_BOUND_UNDER_POWERED`` — the covered BEFORE subset is below its
   frozen floor: too few surviving trajectories to see anything.
2. ``NOT_CLOCK_BOUND`` — adequate coverage and ZERO found-unsubmitted BEFORE
   cells: the attribution refutes the hypothesis (the loss class does not
   exist on the covered evidence); the losses are elsewhere — say so and
   redirect.
3. ``CLOCK_BOUND_UNDER_POWERED`` — the loss class exists but its denominator
   is below the frozen floor (a drop over 1–2 cells cannot type a fix).
4. ``CLOCK_BOUND_FIXED`` — found-unsubmitted drops AND net movement is
   positive (conversions minus regressions, BIDIRECTIONAL — a single noise
   flip over a net-zero re-run cannot type FIXED).
5. ``CLOCK_BOUND_PERSISTS`` — everything else; the residual is named.

The power qualification is a RETURNED ENUM MEMBER, never prose (the round-2
review fix); per-side ``detector-inconclusive`` counts ride the outcome and a
large asymmetry is a named caveat — the identical-detector rule prevents
definition drift, not input-distribution drift. Pilot-N SIGNAL, not an
inferential claim.
"""

from __future__ import annotations

import dataclasses
import enum
from collections.abc import Mapping
from typing import Any

from harpyja.eval.diagnosis_config import DiagnosisConfig

# A BEFORE/AFTER detector-inconclusive gap at or above this is a named caveat.
INCONCLUSIVE_ASYMMETRY_MIN = 2


class DiagnosisVerdict(enum.Enum):
    CLOCK_BOUND_FIXED = "clock-bound-fixed"
    CLOCK_BOUND_UNDER_POWERED = "clock-bound-under-powered"
    CLOCK_BOUND_PERSISTS = "clock-bound-persists"
    NOT_CLOCK_BOUND = "not-clock-bound"


@dataclasses.dataclass(frozen=True)
class DiagnosisOutcome:
    verdict: DiagnosisVerdict
    covered_before: int
    fu_before: int
    fu_after: int
    inconclusive_before: int
    inconclusive_after: int
    conversions: int
    regressions: int
    net: int
    caveats: tuple[str, ...]
    residual: str | None


def _count(cells: Mapping[str, Mapping[str, Any]], outcome: str) -> int:
    return sum(1 for v in cells.values() if v.get("submission_outcome") == outcome)


def decide_diagnosis_outcome(
    config: DiagnosisConfig,
    before_cells: Mapping[str, Mapping[str, Any]],
    after_cells: Mapping[str, Mapping[str, Any]],
) -> DiagnosisOutcome:
    """Total and pure: every input reaches exactly one typed branch."""
    covered_before = len(before_cells)
    paired = sorted(set(before_cells) & set(after_cells))

    fu_before = _count(before_cells, "found-unsubmitted")
    fu_after = _count(after_cells, "found-unsubmitted")
    inconclusive_before = _count(before_cells, "detector-inconclusive")
    inconclusive_after = _count(after_cells, "detector-inconclusive")

    conversions = sum(
        1
        for k in paired
        if after_cells[k].get("bucket") == "correct"
        and before_cells[k].get("bucket") != "correct"
    )
    regressions = sum(
        1
        for k in paired
        if before_cells[k].get("bucket") == "correct"
        and after_cells[k].get("bucket") != "correct"
    )
    net = conversions - regressions

    caveats: list[str] = []
    if abs(inconclusive_before - inconclusive_after) >= INCONCLUSIVE_ASYMMETRY_MIN:
        caveats.append(
            "detector-inconclusive asymmetry across sides "
            f"({inconclusive_before} BEFORE vs {inconclusive_after} AFTER) — "
            "the raw found-unsubmitted delta is qualified by input-distribution "
            "drift, not detector drift"
        )

    verdict: DiagnosisVerdict
    residual: str | None = None
    if covered_before < config.min_covered_before_cells:
        verdict = DiagnosisVerdict.CLOCK_BOUND_UNDER_POWERED
        residual = (
            f"covered BEFORE subset {covered_before} < frozen floor "
            f"{config.min_covered_before_cells}"
        )
    elif fu_before == 0:
        verdict = DiagnosisVerdict.NOT_CLOCK_BOUND
        residual = (
            "zero found-unsubmitted cells on adequate coverage — the loss "
            "class does not exist on the covered evidence; the losses are "
            "elsewhere (redirect: wrong-span/never-found classes)"
        )
    elif fu_before < config.min_before_found_unsubmitted:
        verdict = DiagnosisVerdict.CLOCK_BOUND_UNDER_POWERED
        residual = (
            f"found-unsubmitted denominator {fu_before} < frozen floor "
            f"{config.min_before_found_unsubmitted}"
        )
    elif fu_after < fu_before and net > 0:
        verdict = DiagnosisVerdict.CLOCK_BOUND_FIXED
    else:
        verdict = DiagnosisVerdict.CLOCK_BOUND_PERSISTS
        residual = (
            f"found-unsubmitted {fu_before} -> {fu_after}; net movement {net} "
            f"({conversions} conversions, {regressions} regressions) — the fix "
            "is insufficient on this evidence"
        )

    return DiagnosisOutcome(
        verdict=verdict,
        covered_before=covered_before,
        fu_before=fu_before,
        fu_after=fu_after,
        inconclusive_before=inconclusive_before,
        inconclusive_after=inconclusive_after,
        conversions=conversions,
        regressions=regressions,
        net=net,
        caveats=tuple(caveats),
        residual=residual,
    )
