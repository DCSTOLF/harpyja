"""Spec 0046 (AC7) — the total-pure five-sided verdict.

``decide_reactive_outcome`` maps (frozen config, BASELINE cells, NEW cells) to
exactly one typed member, under a FROZEN precedence (first-true-wins), recording
every true condition. The predicate is FIVE-sided (conversions, regressions,
s->wc, found-but-unsubmitted, flagged-wrong-emitted). ``s->wc`` and
``flagged-wrong-emitted`` PARTITION the fired-wrong-submitted mass by confirmation
outcome; their SUM is the conserved baseline quantity, so a drop in one that
merely relocates to the other is visible (the de-attribution guard). The CEILING
(a relabel-tolerance fraction < 1 of baseline s->wc) blocks a pure relabel; the
SUM conjunct blocks NEW wrong mass — they do DIFFERENT work.

4b reconciliation (wired to ``submit_disposition``, never prose): the CONFIRM
lever adds no turn, but the REACTIVE lever spends explore turns/bytes and 4b's
binding constraint IS tool-output bytes/prefill. So a 4b net-negative on a
``triggered-and-explored`` cell is an inert-with-cost null (excused); only a 4b
net-negative on a NO-trigger cell counts as trades-again.

Pilot-N SIGNAL, not an inferential claim.
"""

from __future__ import annotations

import dataclasses
import enum
from collections import Counter
from collections.abc import Mapping
from typing import Any

from harpyja.eval.reactive_config import ReactiveConfig
from harpyja.eval.reactive_observability import reactive_side_of


class ReactiveVerdict(enum.Enum):
    UNDER_POWERED = "under-powered"
    TRADES_AGAIN = "trades-again"
    DISSOLVES_TRADE = "dissolves-trade"
    NO_EFFECT = "no-effect"


@dataclasses.dataclass(frozen=True)
class ReactiveDecision:
    verdict: ReactiveVerdict
    covered_baseline: int
    baseline_swc: int
    swc_new: int
    flagged_wrong_emitted_new: int
    ceiling: int
    fu_baseline: int
    fu_new: int
    conversions: int
    regressions: int
    net: int
    per_model: tuple[dict[str, Any], ...]
    conditions_true: tuple[str, ...]
    reopened: tuple[str, ...]
    residual: str | None


def reactive_verdict_from_flags(
    under_powered: bool, trades_again: bool, dissolves: bool
) -> ReactiveVerdict:
    """The frozen precedence, first-true-wins (total over the 8 flag tuples)."""
    if under_powered:
        return ReactiveVerdict.UNDER_POWERED
    if trades_again:
        return ReactiveVerdict.TRADES_AGAIN
    if dissolves:
        return ReactiveVerdict.DISSOLVES_TRADE
    return ReactiveVerdict.NO_EFFECT


def _model_of(key: str) -> str:
    return key.split("::", 1)[1] if "::" in key else key


def _sides(cells: Mapping[str, Mapping[str, Any]]) -> Counter:
    return Counter(reactive_side_of(v, []) for v in cells.values())


def decide_reactive_outcome(
    config: ReactiveConfig,
    baseline_cells: Mapping[str, Mapping[str, Any]],
    new_cells: Mapping[str, Mapping[str, Any]],
) -> ReactiveDecision:
    base_sides = _sides(baseline_cells)
    new_sides = _sides(new_cells)
    # Baseline arm runs the reverted gate with NO confirmation, so baseline
    # flagged-wrong-emitted == 0 by construction; baseline s->wc IS the whole
    # fired-wrong-submitted mass.
    baseline_swc = base_sides["s->wc"] + base_sides["flagged-wrong-emitted"]
    fu_baseline = base_sides["fu"]
    swc_new = new_sides["s->wc"]
    fwe_new = new_sides["flagged-wrong-emitted"]
    fu_new = new_sides["fu"]
    sum_new = swc_new + fwe_new

    ceiling = config.flagged_wrong_emitted_ceiling
    if ceiling is None:
        ceiling = int(config.flagged_wrong_emitted_ceiling_fraction * baseline_swc)

    # Per-model conversions/regressions (bucket deltas) + the 4b reconciliation.
    paired = sorted(set(baseline_cells) & set(new_cells))
    models = sorted({_model_of(k) for k in baseline_cells} | {_model_of(k) for k in new_cells})
    per_model: list[dict[str, Any]] = []
    conversions = regressions = 0
    any_unexcused_negative = False
    unexcused_models: list[str] = []
    for model in models:
        m_paired = [k for k in paired if _model_of(k) == model]
        m_conv = sum(
            1 for k in m_paired
            if new_cells[k].get("terminal_bucket") == "correct"
            and baseline_cells[k].get("terminal_bucket") != "correct"
        )
        m_regressed = [
            k for k in m_paired
            if baseline_cells[k].get("terminal_bucket") == "correct"
            and new_cells[k].get("terminal_bucket") != "correct"
        ]
        m_reg = len(m_regressed)
        m_net = m_conv - m_reg
        conversions += m_conv
        regressions += m_reg
        # A regression on a triggered-and-explored cell of the inert model is an
        # inert-with-cost null (reactive-explore bytes) — excused. Any other
        # net-negative counts.
        m_no_trigger_reg = sum(
            1 for k in m_regressed
            if new_cells[k].get("submit_disposition") != "triggered-and-explored"
        )
        if m_net < 0:
            if model == config.inert_model and m_no_trigger_reg == 0:
                pass  # excused: all regressions are triggered-and-explored
            else:
                any_unexcused_negative = True
                unexcused_models.append(model)
        per_model.append({
            "model": model, "conversions": m_conv, "regressions": m_reg,
            "net": m_net, "no_trigger_regressions": m_no_trigger_reg,
        })
    net = conversions - regressions

    covered_baseline = len(baseline_cells)
    under_powered = (
        covered_baseline < config.min_covered_baseline_cells
        or baseline_swc < config.min_baseline_swc
    )

    # Directions the lever can err in (each a first-class counted side).
    fu_fell = fu_new < fu_baseline
    fu_rose = fu_new > fu_baseline
    swc_rose = swc_new > baseline_swc
    sum_rose = sum_new > baseline_swc
    fwe_over_ceiling = fwe_new > ceiling

    reopened: list[str] = []
    if fu_rose:
        reopened.append("found-but-unsubmitted")
    if sum_rose or swc_rose:
        reopened.append("silence-to-wrong-confidence")
    if fwe_over_ceiling:
        reopened.append("flagged-wrong-emitted")
    for m in unexcused_models:
        reopened.append(f"{m}-net-negative")

    trades_again = bool(reopened)
    dissolves = (
        fu_fell and not sum_rose and not swc_rose
        and not fwe_over_ceiling and not any_unexcused_negative
    )

    conditions_true = tuple(
        name for name, value in (
            ("under-powered", under_powered),
            ("trades-again", trades_again),
            ("dissolves-trade", dissolves),
            ("no-effect", not (under_powered or trades_again or dissolves)),
        ) if value
    )

    verdict = reactive_verdict_from_flags(under_powered, trades_again, dissolves)
    residual: str | None = None
    if verdict is ReactiveVerdict.UNDER_POWERED:
        residual = (
            f"covered baseline {covered_baseline} (floor "
            f"{config.min_covered_baseline_cells}) / baseline s->wc {baseline_swc} "
            f"(floor {config.min_baseline_swc})"
        )
    elif verdict is ReactiveVerdict.TRADES_AGAIN:
        residual = f"reopened: {reopened}"

    return ReactiveDecision(
        verdict=verdict,
        covered_baseline=covered_baseline,
        baseline_swc=baseline_swc,
        swc_new=swc_new,
        flagged_wrong_emitted_new=fwe_new,
        ceiling=ceiling,
        fu_baseline=fu_baseline,
        fu_new=fu_new,
        conversions=conversions,
        regressions=regressions,
        net=net,
        per_model=tuple(per_model),
        conditions_true=conditions_true,
        reopened=tuple(reopened),
        residual=residual,
    )
