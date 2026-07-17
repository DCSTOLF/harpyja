"""Spec 0048 — bake-off: the pure analysis core.

Turns per model+case buckets into per-pair verdicts and the assembled bake-off
outcome, under the FROZEN ``bakeoff_config`` contract. Pure — no I/O, no SUT
import beyond the frozen taxonomy. The discordance / located / exact-McNemar
oracles are the ONE committed set (``ac8_pilot`` / ``think_ab`` / ``benchmark_fit``),
re-exported BY IDENTITY and never re-derived (the one-oracle-reuse rule).
"""

from __future__ import annotations

import dataclasses
import enum
import itertools
from collections.abc import Mapping, Sequence
from typing import Any

# The ONE committed oracles — imported by identity (asserted by test).
from harpyja.eval.ac8_pilot import is_signal_discordant
from harpyja.eval.bakeoff_config import BakeoffConfig
from harpyja.eval.benchmark_fit import mcnemar_exact_p
from harpyja.eval.locate_accuracy import LocateBucket
from harpyja.eval.think_ab import located_via_oracle

__all__ = [
    "BakeoffOutcome",
    "BakeoffPairCase",
    "BakeoffReport",
    "ModelExclusion",
    "PairOutcome",
    "PairResult",
    "assemble_bakeoff",
    "decide_pair_outcome",
    "discordant_counts",
    "holm_adjusted_pvalues",
    "holm_rejections",
    "is_signal_discordant",
    "lexical_descriptive_stats",
    "located_via_oracle",
    "mcnemar_exact_p",
    "per_repo_bc_distribution",
    "repo_concentrated",
    "split_by_reachability",
]


# ---- per-case rows + discordance (b, c) --------------------------------------


@dataclasses.dataclass(frozen=True)
class BakeoffPairCase:
    """One conceptual case's cross-model bucket pair, retaining its repo (for the
    per-repo concentration guard). Marginal locate-counts cannot recover ``b+c``."""

    case_id: str
    repo: str
    bucket_a: LocateBucket
    bucket_b: LocateBucket


def discordant_counts(pair_cases: Sequence[BakeoffPairCase]) -> tuple[int, int]:
    """``(b, c)`` from per-case buckets: ``b`` = model_a located & model_b not;
    ``c`` = model_b located & model_a not. ``b + c`` = the signal-discordant count
    (``is_signal_discordant`` by construction), NEVER marginal locate-counts."""
    b = c = 0
    for case in pair_cases:
        a_loc = located_via_oracle(case.bucket_a)
        b_loc = located_via_oracle(case.bucket_b)
        if a_loc and not b_loc:
            b += 1
        elif b_loc and not a_loc:
            c += 1
    return b, c


# ---- exact McNemar + Holm–Bonferroni (family m FIXED) ------------------------


def _ranked(raw_p: Mapping[Any, float], tie_order: Sequence[Any]) -> list[Any]:
    """Ascending by p, ties broken by position in ``tie_order`` (deterministic)."""
    order_index = {k: i for i, k in enumerate(tie_order)}
    return sorted(raw_p, key=lambda k: (raw_p[k], order_index.get(k, len(tie_order))))


def holm_adjusted_pvalues(
    raw_p: Mapping[Any, float], *, m: int, tie_order: Sequence[Any]
) -> dict[Any, float]:
    """Holm-adjusted p per key: ``min(1, running-max over j<=i of (m - j + 1)·p(j))``.
    ``m`` is the FIXED family size (never the number of keys present)."""
    ranked = _ranked(raw_p, tie_order)
    adjusted: dict[Any, float] = {}
    running = 0.0
    for i, key in enumerate(ranked, start=1):
        running = max(running, (m - i + 1) * raw_p[key])
        adjusted[key] = min(1.0, running)
    return adjusted


def holm_rejections(
    raw_p: Mapping[Any, float], *, alpha: float, m: int, tie_order: Sequence[Any]
) -> dict[Any, bool]:
    """Holm step-down rejections under the ``p <= alpha`` convention: reject the
    ranked hypotheses up to (not including) the first whose adjusted p exceeds
    ``alpha``. ``m`` FIXED."""
    ranked = _ranked(raw_p, tie_order)
    adjusted = holm_adjusted_pvalues(raw_p, m=m, tie_order=tie_order)
    rejections: dict[Any, bool] = {}
    still_rejecting = True
    for key in ranked:
        if still_rejecting and adjusted[key] <= alpha:
            rejections[key] = True
        else:
            still_rejecting = False
            rejections[key] = False
    return rejections


# ---- per-pair outcome --------------------------------------------------------


class PairOutcome(enum.Enum):
    """The committed per-pair answer space — total, on ABSOLUTE-count predicates
    (no denominator enters; the floor is an absolute 8)."""

    PAIR_UNDER_POWERED = "pair-under-powered"
    PAIR_MODELS_TOO_CLOSE = "pair-models-too-close"
    PAIR_NO_DIFFERENCE = "pair-no-difference"
    PAIR_SEPARATES = "pair-separates"


@dataclasses.dataclass(frozen=True)
class PairResult:
    pair: tuple[str, str]
    b: int
    c: int
    eligible_n: int
    dropped_total: int
    dropped_degrade: int
    degraded_dominated: bool
    raw_p: float | None
    adjusted_p: float | None
    rejected: bool
    outcome: PairOutcome
    winner: str | None
    repo_concentrated: bool


def _is_degraded_dominated(cfg: BakeoffConfig, dropped_total: int, dropped_degrade: int) -> bool:
    if dropped_total <= 0:
        return False
    return (dropped_degrade / dropped_total) > cfg.degraded_dominated_threshold


def decide_pair_outcome(
    cfg: BakeoffConfig,
    pair: tuple[str, str],
    pair_cases: Sequence[BakeoffPairCase],
    *,
    dropped_total: int,
    dropped_degrade: int,
    rejected: bool,
    raw_p: float | None = None,
    adjusted_p: float | None = None,
) -> PairResult:
    """Total per-pair verdict in the frozen predicate order: coverage → too-close
    → no-difference → separates. ``rejected`` is the Holm decision computed across
    the whole family (a pair below the discordance floor never reaches the test)."""
    eligible_n = len(pair_cases)
    b, c = discordant_counts(pair_cases)
    degraded_dominated = _is_degraded_dominated(cfg, dropped_total, dropped_degrade)

    def _result(outcome: PairOutcome, winner: str | None) -> PairResult:
        return PairResult(
            pair=pair, b=b, c=c, eligible_n=eligible_n, dropped_total=dropped_total,
            dropped_degrade=dropped_degrade, degraded_dominated=degraded_dominated,
            raw_p=raw_p, adjusted_p=adjusted_p, rejected=rejected, outcome=outcome,
            winner=winner, repo_concentrated=repo_concentrated(
                pair_cases, alpha=cfg.alpha, floor=cfg.conceptual_min_discordant
            ),
        )

    if eligible_n < cfg.coverage_floor:
        return _result(PairOutcome.PAIR_UNDER_POWERED, None)
    if (b + c) < cfg.conceptual_min_discordant:
        return _result(PairOutcome.PAIR_MODELS_TOO_CLOSE, None)
    if rejected:
        winner = pair[0] if b > c else pair[1]
        return _result(PairOutcome.PAIR_SEPARATES, winner)
    return _result(PairOutcome.PAIR_NO_DIFFERENCE, None)


# ---- per-repo concentration --------------------------------------------------


def _sign(x: int) -> int:
    return (x > 0) - (x < 0)


def per_repo_bc_distribution(pair_cases: Sequence[BakeoffPairCase]) -> dict[str, int]:
    """Per-repo signed discordance ``b_r - c_r`` — the distribution reported
    alongside a separating verdict."""
    dist: dict[str, int] = {}
    for case in pair_cases:
        a_loc = located_via_oracle(case.bucket_a)
        b_loc = located_via_oracle(case.bucket_b)
        delta = (1 if a_loc and not b_loc else 0) - (1 if b_loc and not a_loc else 0)
        dist[case.repo] = dist.get(case.repo, 0) + delta
    return dist


def repo_concentrated(
    pair_cases: Sequence[BakeoffPairCase], *, alpha: float, floor: int
) -> bool:
    """True when dropping ANY single repo — or ANY two repos — flips the McNemar
    direction (``sign(b - c)``) or drops ``b + c`` below ``floor`` (the ≤8/repo
    overfit guard, operationalized as leave-one-out AND leave-two-out)."""
    repos = sorted({case.repo for case in pair_cases})
    base_b, base_c = discordant_counts(pair_cases)
    base_sign = _sign(base_b - base_c)
    for k in (1, 2):
        for dropped in itertools.combinations(repos, k):
            kept = [c for c in pair_cases if c.repo not in dropped]
            b, c = discordant_counts(kept)
            if (b + c) < floor:
                return True
            if base_sign != 0 and _sign(b - c) == -base_sign:
                return True
    return False


# ---- assembly of the three pairwise verdicts ---------------------------------


class BakeoffOutcome(enum.Enum):
    RANKING = "ranking"
    INTRANSITIVE = "intransitive"
    PARTIAL = "partial"
    NO_SEPARATION = "no-separation"
    INFRASTRUCTURE_HALTED = "infrastructure-halted"


@dataclasses.dataclass(frozen=True)
class ModelExclusion:
    tag: str
    reason: str


@dataclasses.dataclass(frozen=True)
class BakeoffReport:
    outcome: BakeoffOutcome
    ranking: tuple[str, ...] | None
    conceptual_pair_results: tuple[PairResult, ...]
    lexical_stats: Mapping[str, Any]
    exclusions: tuple[ModelExclusion, ...]
    per_repo_distribution: Mapping[str, Mapping[str, int]]
    # 0042/0043 threads, per model — reported beside the verdict, never in it.
    symbols_adoption: Mapping[str, float] = dataclasses.field(default_factory=dict)
    found_but_unsubmitted: Mapping[str, int] = dataclasses.field(default_factory=dict)


def assemble_bakeoff(
    pair_results: Mapping[tuple[str, str], PairResult],
    *,
    surviving_models: Sequence[str],
    exclusions: Sequence[ModelExclusion],
    lexical_stats: Mapping[str, Any] | None = None,
    per_repo_distribution: Mapping[str, Mapping[str, int]] | None = None,
    symbols_adoption: Mapping[str, float] | None = None,
    found_but_unsubmitted: Mapping[str, int] | None = None,
) -> BakeoffReport:
    """Total assembly in the frozen survivorship order: <2 → HALTED; ==2 → PARTIAL
    (never ranks all three); ==3 → total order / cycle / mixed / none."""
    results = tuple(pair_results.values())

    def _report(outcome: BakeoffOutcome, ranking: tuple[str, ...] | None) -> BakeoffReport:
        return BakeoffReport(
            outcome=outcome, ranking=ranking, conceptual_pair_results=results,
            lexical_stats=lexical_stats or {}, exclusions=tuple(exclusions),
            per_repo_distribution=per_repo_distribution or {},
            symbols_adoption=symbols_adoption or {},
            found_but_unsubmitted=found_but_unsubmitted or {},
        )

    if len(surviving_models) < 2:
        return _report(BakeoffOutcome.INFRASTRUCTURE_HALTED, None)
    if len(surviving_models) == 2:
        return _report(BakeoffOutcome.PARTIAL, None)

    separating = [r for r in results if r.outcome is PairOutcome.PAIR_SEPARATES]
    if not separating:
        return _report(BakeoffOutcome.NO_SEPARATION, None)
    if len(separating) < 3:
        return _report(BakeoffOutcome.PARTIAL, None)

    # Three separating edges over three nodes: transitive (out-degrees {2,1,0}) or
    # a 3-cycle (out-degrees {1,1,1}).
    out_degree: dict[str, int] = {m: 0 for m in surviving_models}
    for r in separating:
        assert r.winner is not None
        out_degree[r.winner] = out_degree.get(r.winner, 0) + 1
    if sorted(out_degree.values()) == [0, 1, 2]:
        ranking = tuple(sorted(out_degree, key=lambda m: out_degree[m], reverse=True))
        return _report(BakeoffOutcome.RANKING, ranking)
    return _report(BakeoffOutcome.INTRANSITIVE, None)


# ---- reachability split ------------------------------------------------------


def _repo_of(case_id: str) -> str:
    """SWE-bench id ``<org>__<repo>-<number>`` → ``<org>__<repo>``."""
    return case_id.rsplit("-", 1)[0]


def split_by_reachability(
    entries: Mapping[str, Mapping[str, Any]],
    reachability: Mapping[str, str],
    model_a: str,
    model_b: str,
) -> tuple[list[BakeoffPairCase], int, int]:
    """Complete-case paired conceptual join, retaining repo and counting drops.

    A conceptual case forms a pair only when BOTH models carry a CLEAN bucket; a
    typed degrade or missing/empty cell drops the case (counted), a degrade-caused
    drop additionally counted for the degraded-dominated partition."""
    cases: list[BakeoffPairCase] = []
    dropped_total = 0
    dropped_degrade = 0
    for case_id, tag in reachability.items():
        if tag != "conceptual":
            continue
        cell_a = entries.get(f"{case_id}::{model_a}")
        cell_b = entries.get(f"{case_id}::{model_b}")
        if not cell_a or not cell_b:
            dropped_total += 1
            if (cell_a or {}).get("degrade") or (cell_b or {}).get("degrade"):
                dropped_degrade += 1
            continue
        if cell_a.get("degrade") or cell_b.get("degrade"):
            dropped_total += 1
            dropped_degrade += 1
            continue
        if not cell_a.get("bucket") or not cell_b.get("bucket"):
            dropped_total += 1
            continue
        repo = str(cell_a.get("repo") or _repo_of(case_id))
        cases.append(
            BakeoffPairCase(
                case_id=case_id, repo=repo,
                bucket_a=LocateBucket(cell_a["bucket"]),
                bucket_b=LocateBucket(cell_b["bucket"]),
            )
        )
    return cases, dropped_total, dropped_degrade


def lexical_descriptive_stats(
    entries: Mapping[str, Mapping[str, Any]],
    reachability: Mapping[str, str],
    model: str,
) -> dict[str, int]:
    """Per-model raw found/not-found counts over the LEXICAL stratum — DESCRIPTIVE
    statistics only, NEVER an inferential pairwise verdict."""
    found = not_found = 0
    for case_id, tag in reachability.items():
        if tag != "lexical":
            continue
        cell = entries.get(f"{case_id}::{model}")
        if not cell or cell.get("degrade") or not cell.get("bucket"):
            continue
        if located_via_oracle(LocateBucket(cell["bucket"])):
            found += 1
        else:
            not_found += 1
    return {"found": found, "not_found": not_found, "total": found + not_found}
