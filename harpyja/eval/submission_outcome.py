"""Spec 0044 — the total pure AC8 verdict.

``decide_submission_outcome`` maps (frozen config, BEFORE cells, AFTER cells)
to exactly one of FIVE typed members, in FROZEN precedence order (first match
wins), and records EVERY true condition alongside the winner — overlapping
conditions are a total order, never a partition argument at close time (the
0020/0023 discipline):

1. ``UNDER_POWERED`` — the covered BEFORE subset is below its frozen floor,
   OR the BEFORE found-unsubmitted denominator is (the fu floor is cleared
   statically by the frozen baseline's fu_before = 6, but re-checked here as
   a guard against a baseline-identity error). Power failure is a RETURNED
   ENUM MEMBER, never prose — the floors the config carries are CONSUMED.
2. ``NEVER_FIRES`` — the beneficiary model's firings are at or below the
   numeric config threshold. Keyed to the PRE-REGISTERED beneficiary (14b)
   ONLY: an 8b zero-firing rate never triggers it (8b's pre-registered
   success criterion is regressions = 0 at ANY firing rate).
3. ``STILL_TRADES_OFF`` — any model's net is negative OR the aggregate net is
   negative: an aggregate win that hides an 8b regression is not a ship.
4. ``NUDGE_INERT`` — the nudge bought nothing: zero conversions AND no
   found-unsubmitted drop. The inert-lever hole closed at the VERDICT level —
   a fired-but-ignored net-0 run must not type a ship (round-2 claude-p).
5. ``CONDITIONED_NUDGE_SHIPS`` — aggregate net >= 0 AND no model net-negative
   AND a BENEFIT conjunct holds (conversions >= 1 OR fu_after < fu_before) —
   the 0043 predicate was two-conjunct and this spec keeps both sides.

Pilot-N SIGNAL, not an inferential claim.
"""

from __future__ import annotations

import dataclasses
import enum
from collections.abc import Mapping
from typing import Any

from harpyja.eval.submission_config import SubmissionConfig


class SubmissionVerdict(enum.Enum):
    UNDER_POWERED = "under-powered"
    NEVER_FIRES = "never-fires"
    STILL_TRADES_OFF = "still-trades-off"
    NUDGE_INERT = "nudge-inert"
    CONDITIONED_NUDGE_SHIPS = "conditioned-nudge-ships"


@dataclasses.dataclass(frozen=True)
class SubmissionDecision:
    verdict: SubmissionVerdict
    covered_before: int
    fu_before: int
    fu_after: int
    conversions: int
    regressions: int
    net: int
    per_model: tuple[dict[str, Any], ...]
    conditions_true: tuple[str, ...]
    residual: str | None


def _model_of(key: str) -> str:
    return key.split("::", 1)[1] if "::" in key else key


def _count_fu(cells: Mapping[str, Mapping[str, Any]]) -> int:
    return sum(
        1
        for v in cells.values()
        if v.get("submission_outcome") == "found-unsubmitted"
    )


def decide_submission_outcome(
    config: SubmissionConfig,
    before_cells: Mapping[str, Mapping[str, Any]],
    after_cells: Mapping[str, Mapping[str, Any]],
) -> SubmissionDecision:
    """Total and pure: every input reaches exactly one typed member, and every
    true condition is recorded."""
    covered_before = len(before_cells)
    paired = sorted(set(before_cells) & set(after_cells))
    fu_before = _count_fu(before_cells)
    fu_after = _count_fu(after_cells)

    models = sorted(
        {_model_of(k) for k in before_cells} | {_model_of(k) for k in after_cells}
    )
    per_model: list[dict[str, Any]] = []
    any_model_negative = False
    conversions = 0
    regressions = 0
    beneficiary_firings = 0
    for model in models:
        m_paired = [k for k in paired if _model_of(k) == model]
        m_conversions = sum(
            1
            for k in m_paired
            if after_cells[k].get("bucket") == "correct"
            and before_cells[k].get("bucket") != "correct"
        )
        m_regressions = sum(
            1
            for k in m_paired
            if before_cells[k].get("bucket") == "correct"
            and after_cells[k].get("bucket") != "correct"
        )
        m_after = [k for k in after_cells if _model_of(k) == model]
        m_firings = sum(
            1 for k in m_after if after_cells[k].get("confidence_fired")
        )
        m_net = m_conversions - m_regressions
        if m_net < 0:
            any_model_negative = True
        conversions += m_conversions
        regressions += m_regressions
        if model == config.beneficiary_model:
            beneficiary_firings = m_firings
        per_model.append({
            "model": model,
            "cells": len(m_after),
            "conversions": m_conversions,
            "regressions": m_regressions,
            "net": m_net,
            "firings": m_firings,
            "firing_rate": (m_firings / len(m_after)) if m_after else 0.0,
        })
    net = conversions - regressions

    # Every condition, evaluated independently and RECORDED — the frozen
    # precedence below picks the label; overlaps are data, not argument.
    under_powered = (
        covered_before < config.min_covered_before_cells
        or fu_before < config.min_before_found_unsubmitted
    )
    never_fires = (
        beneficiary_firings <= config.never_fires_max_beneficiary_firings
    )
    still_trades_off = any_model_negative or net < 0
    benefit = conversions >= 1 or fu_after < fu_before
    nudge_inert = conversions == 0 and fu_after >= fu_before
    ships = net >= 0 and not any_model_negative and benefit

    conditions_true = tuple(
        name
        for name, value in (
            ("under-powered", under_powered),
            ("never-fires", never_fires),
            ("still-trades-off", still_trades_off),
            ("nudge-inert", nudge_inert),
            ("conditioned-nudge-ships", ships),
        )
        if value
    )

    verdict: SubmissionVerdict
    residual: str | None = None
    if under_powered:
        verdict = SubmissionVerdict.UNDER_POWERED
        residual = (
            f"covered BEFORE subset {covered_before} (floor "
            f"{config.min_covered_before_cells}) / found-unsubmitted "
            f"denominator {fu_before} (floor "
            f"{config.min_before_found_unsubmitted})"
        )
    elif never_fires:
        verdict = SubmissionVerdict.NEVER_FIRES
        residual = (
            f"beneficiary {config.beneficiary_model} fired on "
            f"{beneficiary_firings} cells (threshold "
            f"{config.never_fires_max_beneficiary_firings}) — the confidence "
            "bar is too strict for the model the lever exists to rescue; "
            "per-model firing rates reported alongside"
        )
    elif still_trades_off:
        verdict = SubmissionVerdict.STILL_TRADES_OFF
        negative = [r["model"] for r in per_model if r["net"] < 0]
        residual = (
            f"net {net} ({conversions} conversions, {regressions} "
            f"regressions); net-negative models: {negative or 'none'} — "
            "conversions bought with regressions again"
        )
    elif nudge_inert:
        verdict = SubmissionVerdict.NUDGE_INERT
        residual = (
            f"the nudge fired but bought nothing: 0 conversions, "
            f"found-unsubmitted {fu_before} -> {fu_after} (no drop) — "
            "fired-but-ignored is the residual; see the per-case "
            "attributable-null fields"
        )
    else:
        verdict = SubmissionVerdict.CONDITIONED_NUDGE_SHIPS

    return SubmissionDecision(
        verdict=verdict,
        covered_before=covered_before,
        fu_before=fu_before,
        fu_after=fu_after,
        conversions=conversions,
        regressions=regressions,
        net=net,
        per_model=tuple(per_model),
        conditions_true=conditions_true,
        residual=residual,
    )
