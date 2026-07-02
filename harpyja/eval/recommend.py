"""OQ2 recommendation — variance rule (D3) + lexicographic scorer (D4).

The recommendation is the deliverable of this wave (B1): a recommended
`(verify_threshold, verify_top_n)`, NOT a `Settings` default flip. The incumbent
`(0.6, 3)` is only displaced by a sweep point whose advantage **exceeds run-to-run
variance** (D3); otherwise the incumbent is recorded as *validated*, not guessed.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass

# The provisional incumbent from spec 0008 (verify_threshold, verify_top_n).
INCUMBENT = (0.6, 3)

# Spec 0019 (D2): OQ2 outcome identifiers. A clean run yields a `recommended`
# recommendation (validate-or-flip the incumbent); a run whose measured
# instruct-judge false-escalation exceeds the ceiling yields the `gate-confounded`
# typed null — calibrating verify_threshold over a still-broken judge is refused.
OUTCOME_RECOMMENDED = "recommended"
OUTCOME_GATE_CONFOUNDED = "gate-confounded"


@dataclass(frozen=True)
class SweepPoint:
    """One grid point's aggregated result over K runs."""

    verify_threshold: float
    verify_top_n: int
    catch_rate_mean: float | None
    false_escalation_mean: float
    false_escalation_runs: tuple[float, ...]


@dataclass(frozen=True)
class Recommendation:
    verify_threshold: float
    verify_top_n: int
    catch_rate_bar: float
    advantage_exceeds_variance: bool
    incumbent_validated: bool
    rationale: str
    # Spec 0019 (D2): additive, appended last-with-defaults so every existing
    # construction stays valid. `outcome` is OUTCOME_RECOMMENDED for a clean pick
    # and OUTCOME_GATE_CONFOUNDED when the gate itself is too unreliable to
    # calibrate over; `gate_false_escalation_measured` carries the measured rate on
    # a confounded outcome (None otherwise).
    outcome: str = OUTCOME_RECOMMENDED
    gate_false_escalation_measured: float | None = None


def advantage_exceeds_spread(
    candidate_runs: Sequence[float],
    incumbent_runs: Sequence[float],
    *,
    higher_is_better: bool,
) -> bool:
    """D3: candidate's mean advantage strictly exceeds the incumbent's spread.

    Spread = population standard deviation (`pstdev`) of the incumbent's K runs
    (conservative — a noisy incumbent is hard to displace). K=1 → spread 0.
    """
    if not candidate_runs or not incumbent_runs:
        return False
    cand = statistics.mean(candidate_runs)
    inc = statistics.mean(incumbent_runs)
    advantage = (cand - inc) if higher_is_better else (inc - cand)
    return advantage > statistics.pstdev(incumbent_runs)


def _lex_key(p: SweepPoint) -> tuple[float, int, float]:
    # D4: minimize false-escalation, tie-break lower top_n, then lower threshold.
    return (p.false_escalation_mean, p.verify_top_n, p.verify_threshold)


def _find_incumbent(points: Sequence[SweepPoint]) -> SweepPoint | None:
    for p in points:
        if (p.verify_threshold, p.verify_top_n) == INCUMBENT:
            return p
    return None


def rank_sweep(points: Sequence[SweepPoint], eval_config) -> Recommendation:
    """Pick a recommended grid point per D4 + the D3 variance gate vs the incumbent."""
    bar = eval_config.catch_rate_bar
    survivors = [p for p in points if p.catch_rate_mean is not None and p.catch_rate_mean >= bar]

    if not survivors:
        thr, top_n = INCUMBENT
        return Recommendation(
            verify_threshold=thr,
            verify_top_n=top_n,
            catch_rate_bar=bar,
            advantage_exceeds_variance=False,
            incumbent_validated=False,
            rationale=f"no grid point cleared the catch-rate bar ({bar}); incumbent not validated",
        )

    winner = min(survivors, key=_lex_key)
    incumbent = _find_incumbent(survivors)

    if incumbent is not None and (winner.verify_threshold, winner.verify_top_n) == INCUMBENT:
        return Recommendation(
            verify_threshold=incumbent.verify_threshold,
            verify_top_n=incumbent.verify_top_n,
            catch_rate_bar=bar,
            advantage_exceeds_variance=False,
            incumbent_validated=True,
            rationale="incumbent (0.6, 3) is the best surviving point; validated",
        )

    if incumbent is not None:
        beats_noise = advantage_exceeds_spread(
            winner.false_escalation_runs,
            incumbent.false_escalation_runs,
            higher_is_better=False,
        )
        if not beats_noise:
            return Recommendation(
                verify_threshold=incumbent.verify_threshold,
                verify_top_n=incumbent.verify_top_n,
                catch_rate_bar=bar,
                advantage_exceeds_variance=False,
                incumbent_validated=True,
                rationale=(
                    "best alternative's advantage is within the incumbent's run-to-run "
                    "variance; incumbent (0.6, 3) validated, not flipped"
                ),
            )
        return Recommendation(
            verify_threshold=winner.verify_threshold,
            verify_top_n=winner.verify_top_n,
            catch_rate_bar=bar,
            advantage_exceeds_variance=True,
            incumbent_validated=False,
            rationale="alternative beats incumbent beyond run-to-run variance",
        )

    # Incumbent did not clear the bar; recommend the winner outright.
    return Recommendation(
        verify_threshold=winner.verify_threshold,
        verify_top_n=winner.verify_top_n,
        catch_rate_bar=bar,
        advantage_exceeds_variance=True,
        incumbent_validated=False,
        rationale="incumbent did not clear the catch-rate bar; recommending best survivor",
    )


def gate_confounded_recommendation(measured_rate: float, eval_config) -> Recommendation:
    """Spec 0019 (D2): the `gate-confounded` typed null.

    Emitted when the measured instruct-judge false-escalation rate exceeds
    `eval_config.gate_false_escalation_ceiling`: the gate rejects correct citations
    often enough that any `verify_threshold` tuned over this score distribution
    would calibrate a still-broken gate. We refuse the pick and report the confound,
    carrying the measured rate. `verify_threshold`/`verify_top_n` mirror the
    incumbent purely as a placeholder — `outcome` is the load-bearing field.
    """
    thr, top_n = INCUMBENT
    return Recommendation(
        verify_threshold=thr,
        verify_top_n=top_n,
        catch_rate_bar=eval_config.catch_rate_bar,
        advantage_exceeds_variance=False,
        incumbent_validated=False,
        rationale=(
            f"gate-confounded: instruct-judge false-escalation {measured_rate:.3f} "
            f"exceeds the ceiling {eval_config.gate_false_escalation_ceiling}; a "
            "threshold tuned over this distribution would calibrate a still-broken "
            "gate — OQ2 withheld pending a gate-accuracy fix"
        ),
        outcome=OUTCOME_GATE_CONFOUNDED,
        gate_false_escalation_measured=measured_rate,
    )


def recommend_oq2(
    points: Sequence[SweepPoint],
    measured_false_escalation: float | None,
    eval_config,
) -> Recommendation:
    """Spec 0019 (D2): gate-confound dispatcher wrapping the D3/D4 recommender.

    If G2 measured a material instruct-judge false-escalation rate — strictly
    greater than `gate_false_escalation_ceiling` — emit the `gate-confounded` typed
    null instead of calibrating over it. Otherwise (rate `None`, i.e. unmeasured, or
    at/below the ceiling) defer to `rank_sweep`. Boundary `== ceiling` is NOT
    confounded (strict `>`).
    """
    if (
        measured_false_escalation is not None
        and measured_false_escalation > eval_config.gate_false_escalation_ceiling
    ):
        return gate_confounded_recommendation(measured_false_escalation, eval_config)
    return rank_sweep(points, eval_config)
