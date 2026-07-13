"""Spec 0045 — the total-pure SIX-member refinement verdict (AC7, T16).

``decide_refinement_outcome`` is total and pure over (frozen config, BEFORE
cells, AFTER cells, named-cell outcomes). It computes the FOUR-SIDED ledger
(conversions / regressions / silence->wrong-confidence / found-but-unsubmitted)
per model, then selects exactly one member of a FROZEN worse-first precedence
(first-true-wins), recording EVERY true condition alongside the winner. A
record-only unfired-s->wc cross-check is surfaced beside s->wc (the
fired-conditioning loophole). Pilot-N SIGNAL, not an inferential claim.
"""

from __future__ import annotations

import dataclasses
import enum
from collections.abc import Mapping
from typing import Any

_SUBMITTED_NOT_CORRECT = frozenset({"wrong-file", "right-file-wrong-span"})


class RefinementVerdict(enum.Enum):
    UNDER_POWERED = "under-powered"
    TRADES_DIRECTIONS = "trades-directions"
    RESIDUAL_PERSISTS = "residual-persists"
    GATE_INERT = "gate-inert"
    GATE_CALIBRATED = "gate-calibrated"
    MISCALIBRATION_REMAINS = "miscalibration-remains"


@dataclasses.dataclass(frozen=True)
class RefinementDecision:
    verdict: RefinementVerdict
    per_model: tuple[dict[str, Any], ...]
    covered_joined: int
    conversions: int
    regressions: int
    aggregate_net: int
    swc_total: int
    unfired_swc_total: int
    fu_total: int
    benefit: bool
    head_to_head_net_delta: int
    conditions_true: tuple[str, ...]
    reopened_direction: str | None
    residual: str | None
    failed_conjunct: str | None


def _model_of(key: str) -> str:
    return key.split("::", 1)[1] if "::" in key else key


def decide_refinement_outcome(
    config: Any,
    before_cells: Mapping[str, Mapping[str, Any]],
    after_cells: Mapping[str, Mapping[str, Any]],
    named_cells: Mapping[str, str],
) -> RefinementDecision:
    joined = sorted(set(before_cells) & set(after_cells))
    covered_joined = len(joined)

    models = sorted({_model_of(k) for k in joined})
    per_model: list[dict[str, Any]] = []
    conversions = regressions = 0
    swc_total = unfired_swc_total = 0
    any_model_negative = False
    for model in models:
        keys = [k for k in joined if _model_of(k) == model]
        m_conv = sum(
            1 for k in keys
            if before_cells[k].get("bucket") != "correct"
            and after_cells[k].get("bucket") == "correct"
        )
        m_reg = sum(
            1 for k in keys
            if before_cells[k].get("bucket") == "correct"
            and after_cells[k].get("bucket") != "correct"
        )
        m_swc = sum(1 for k in keys if _is_swc(before_cells[k], after_cells[k], True))
        m_unfired = sum(
            1 for k in keys if _is_swc(before_cells[k], after_cells[k], False)
        )
        m_net = m_conv - m_reg
        any_model_negative = any_model_negative or m_net < 0
        conversions += m_conv
        regressions += m_reg
        swc_total += m_swc
        unfired_swc_total += m_unfired
        per_model.append({
            "model": model, "conversions": m_conv, "regressions": m_reg,
            "net": m_net, "silence_to_wrong_confidence": m_swc,
            "unfired_silence_to_wrong_confidence": m_unfired,
        })

    fu_total = sum(
        1 for k in joined
        if after_cells[k].get("submission_outcome") == "found-unsubmitted"
    )
    aggregate_net = conversions - regressions

    swc_0044 = config.comparator_swc_total
    fu_0044 = config.comparator_fu_after
    net_0044 = sum(v for _m, v in config.comparator_net_by_model)
    head_to_head_net_delta = aggregate_net - net_0044

    # Conditions — every one evaluated and recorded; precedence picks the label.
    under_powered = (
        covered_joined < config.min_covered_joined_cells
        or config.comparator_swc_total < config.min_comparator_swc
    )
    swc_dropped_fu_rose = swc_total < swc_0044 and fu_total > fu_0044
    fu_dropped_swc_rose = fu_total < fu_0044 and swc_total > swc_0044
    trades = swc_dropped_fu_rose or fu_dropped_swc_rose
    residual_ok = named_cells.get(config.residual_cell) == "correct"
    residual_persists = not residual_ok
    benefit = (
        swc_total < swc_0044 or fu_total < fu_0044 or aggregate_net > net_0044
    )
    gate_inert = not benefit
    calibrated = (
        aggregate_net >= 0
        and not any_model_negative
        and swc_total <= swc_0044
        and fu_total <= fu_0044
        and benefit
    )

    conditions_true = tuple(
        name for name, val in (
            ("under-powered", under_powered),
            ("trades-directions", trades),
            ("residual-persists", residual_persists),
            ("gate-inert", gate_inert),
            ("gate-calibrated", calibrated),
        ) if val
    )

    reopened_direction: str | None = None
    residual: str | None = None
    failed_conjunct: str | None = None

    if under_powered:
        verdict = RefinementVerdict.UNDER_POWERED
    elif trades:
        verdict = RefinementVerdict.TRADES_DIRECTIONS
        reopened_direction = (
            "found-but-unsubmitted" if swc_dropped_fu_rose
            else "silence-to-wrong-confidence"
        )
    elif residual_persists:
        verdict = RefinementVerdict.RESIDUAL_PERSISTS
        residual = (
            f"{config.residual_cell} is "
            f"{named_cells.get(config.residual_cell, 'absent')} (not correct); "
            "evidence needed: an 8b run where its verification time is preserved "
            "(the named 0043+0044 casualty)"
        )
    elif gate_inert:
        verdict = RefinementVerdict.GATE_INERT
    elif calibrated:
        verdict = RefinementVerdict.GATE_CALIBRATED
    else:
        verdict = RefinementVerdict.MISCALIBRATION_REMAINS
        if aggregate_net < 0:
            failed_conjunct = "aggregate-net-negative"
        elif any_model_negative:
            failed_conjunct = "model-net-negative"
        elif swc_total > swc_0044:
            failed_conjunct = "silence-to-wrong-confidence-rose"
        elif fu_total > fu_0044:
            failed_conjunct = "found-but-unsubmitted-rose"
        else:
            failed_conjunct = "benefit-absent"

    return RefinementDecision(
        verdict=verdict,
        per_model=tuple(per_model),
        covered_joined=covered_joined,
        conversions=conversions,
        regressions=regressions,
        aggregate_net=aggregate_net,
        swc_total=swc_total,
        unfired_swc_total=unfired_swc_total,
        fu_total=fu_total,
        benefit=benefit,
        head_to_head_net_delta=head_to_head_net_delta,
        conditions_true=conditions_true,
        reopened_direction=reopened_direction,
        residual=residual,
        failed_conjunct=failed_conjunct,
    )


def _is_swc(
    before: Mapping[str, Any], after: Mapping[str, Any], fired: bool
) -> bool:
    """s->wc (ledger): BEFORE empty ∧ AFTER submitted-not-correct ∧ fired==fired."""
    return (
        before.get("bucket") == "empty"
        and after.get("bucket") in _SUBMITTED_NOT_CORRECT
        and bool(after.get("confidence_fired")) == fired
    )
