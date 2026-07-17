"""Spec 0048 — bake-off: the pure analysis core (AC3 / AC4-pure / AC5-pure).

Every frozen decision rule of the Analysis contract is fixture-pinned here:
per-pair discordance from per-case buckets (identity-reusing the ONE committed
oracles), the four mutually-distinct coverage/closeness outcomes on ABSOLUTE-count
predicates, exact-McNemar + Holm step-down with family m=3 FIXED, per-repo
leave-one/two-out concentration, the typed assembly, and the reachability split.
"""

from __future__ import annotations

import pytest

from harpyja.eval import ac8_pilot, bakeoff_analysis, think_ab
from harpyja.eval.bakeoff_analysis import (
    BakeoffOutcome,
    BakeoffPairCase,
    BakeoffReport,
    ModelExclusion,
    PairOutcome,
    PairResult,
    assemble_bakeoff,
    decide_pair_outcome,
    discordant_counts,
    holm_adjusted_pvalues,
    holm_rejections,
    lexical_descriptive_stats,
    per_repo_bc_distribution,
    repo_concentrated,
    split_by_reachability,
)
from harpyja.eval.bakeoff_config import PREREGISTERED_BAKEOFF_CONFIG_0048
from harpyja.eval.benchmark_fit import mcnemar_exact_p
from harpyja.eval.locate_accuracy import LocateBucket

_CFG = PREREGISTERED_BAKEOFF_CONFIG_0048
C = LocateBucket.CORRECT  # located
E = LocateBucket.EMPTY  # not located
W = LocateBucket.WRONG_FILE  # not located


def _case(case_id: str, repo: str, a: LocateBucket, b: LocateBucket) -> BakeoffPairCase:
    return BakeoffPairCase(case_id=case_id, repo=repo, bucket_a=a, bucket_b=b)


# ---- T3: per-pair discordance b+c from per-case buckets ----------------------


def test_discordant_counts_uses_is_signal_discordant_by_identity():
    # The ONE committed oracles — re-exported by identity, never re-derived.
    assert bakeoff_analysis.is_signal_discordant is ac8_pilot.is_signal_discordant
    assert bakeoff_analysis.located_via_oracle is think_ab.located_via_oracle


def test_discordant_counts_b_and_c_from_per_case_buckets():
    cases = [
        _case("r__r-1", "r__r", C, E),  # a-located only -> b
        _case("r__r-2", "r__r", C, W),  # a-located only -> b
        _case("r__r-3", "r__r", E, C),  # b-located only -> c
        _case("r__r-4", "r__r", C, C),  # concordant located -> neither
        _case("r__r-5", "r__r", E, W),  # concordant not-located -> neither
    ]
    b, c = discordant_counts(cases)
    assert (b, c) == (2, 1)
    assert b + c == 3  # == count of signal-discordant rows


def test_discordant_counts_not_marginal_counts():
    # Equal marginal locate-counts, different b+c: marginals cannot recover it.
    overlap = [_case(f"o-{i}", "o", C, C) for i in range(5)]  # both locate 5, b+c=0
    disjoint = [_case(f"d-{i}", "d", C, E) for i in range(5)] + [
        _case(f"d-{i}", "d", E, C) for i in range(5, 10)
    ]  # a locates 5, b locates 5 (same marginals) but b+c=10
    assert discordant_counts(overlap)[0] + discordant_counts(overlap)[1] == 0
    assert discordant_counts(disjoint)[0] + discordant_counts(disjoint)[1] == 10


# ---- T5: the four coverage/closeness outcomes --------------------------------


def _pair_cases(n_b: int, n_c: int, n_concordant: int, repo: str = "r") -> list:
    """n_b a-only + n_c b-only + n_concordant both-located rows."""
    rows = []
    k = 0
    for _ in range(n_b):
        rows.append(_case(f"{repo}-{k}", repo, C, E))
        k += 1
    for _ in range(n_c):
        rows.append(_case(f"{repo}-{k}", repo, E, C))
        k += 1
    for _ in range(n_concordant):
        rows.append(_case(f"{repo}-{k}", repo, C, C))
        k += 1
    return rows


def test_pair_outcome_under_powered_below_coverage_floor():
    cases = _pair_cases(20, 0, 0)  # eligible N = 20 < 36, big discordance anyway
    res = decide_pair_outcome(
        _CFG, ("qwen3:14b", "qwen3:8b"), cases,
        dropped_total=10, dropped_degrade=2, rejected=True,
    )
    assert res.outcome is PairOutcome.PAIR_UNDER_POWERED


def test_pair_outcome_degraded_dominated_flag_partitions_by_cause():
    cases = _pair_cases(10, 0, 10)  # eligible N = 20 < 36
    dominated = decide_pair_outcome(
        _CFG, ("qwen3:14b", "qwen3:8b"), cases,
        dropped_total=10, dropped_degrade=6, rejected=False,  # 6/10 > 0.5
    )
    not_dominated = decide_pair_outcome(
        _CFG, ("qwen3:14b", "qwen3:8b"), cases,
        dropped_total=10, dropped_degrade=5, rejected=False,  # 5/10 == 0.5, not >
    )
    assert dominated.outcome is PairOutcome.PAIR_UNDER_POWERED
    assert dominated.degraded_dominated is True
    assert not_dominated.degraded_dominated is False


def test_pair_outcome_models_too_close_when_discordance_below_floor():
    # eligible N = 40 >= 36, b+c = 7 < 8
    cases = _pair_cases(4, 3, 33)
    res = decide_pair_outcome(
        _CFG, ("qwen3:8b", "qwen3.5:4b"), cases,
        dropped_total=0, dropped_degrade=0, rejected=False,
    )
    assert res.outcome is PairOutcome.PAIR_MODELS_TOO_CLOSE
    # descriptive, NOT a powered-equivalence claim
    assert res.winner is None


def test_pair_outcome_no_difference_when_holm_not_reject():
    cases = _pair_cases(5, 4, 30)  # eligible N = 39 >= 36, b+c = 9 >= 8
    res = decide_pair_outcome(
        _CFG, ("qwen3:14b", "qwen3:8b"), cases,
        dropped_total=0, dropped_degrade=0, rejected=False,
    )
    assert res.outcome is PairOutcome.PAIR_NO_DIFFERENCE
    assert res.winner is None


def test_pair_outcome_separates_when_holm_rejects():
    cases = _pair_cases(8, 0, 30)  # eligible N = 38 >= 36, b+c = 8, b>c
    res = decide_pair_outcome(
        _CFG, ("qwen3:14b", "qwen3:8b"), cases,
        dropped_total=0, dropped_degrade=0, rejected=True,
    )
    assert res.outcome is PairOutcome.PAIR_SEPARATES
    assert res.winner == "qwen3:14b"  # sign(b - c) > 0 -> model_a


def test_pair_outcome_predicates_are_mutually_distinct():
    # grid over (N<36 / N>=36) x (b+c <8 / >=8) x (reject / not) -> exactly one member
    seen = set()
    for eligible_big in (False, True):
        concordant = 33 if eligible_big else 5
        for bc_big in (False, True):
            n_b = 8 if bc_big else 3
            cases = _pair_cases(n_b, 0, concordant)
            for rejected in (False, True):
                res = decide_pair_outcome(
                    _CFG, ("qwen3:14b", "qwen3:8b"), cases,
                    dropped_total=0, dropped_degrade=0, rejected=rejected,
                )
                assert isinstance(res.outcome, PairOutcome)
                seen.add(res.outcome)
    # coverage dominates: every N<36 config is UNDER_POWERED regardless
    assert PairOutcome.PAIR_UNDER_POWERED in seen
    assert PairOutcome.PAIR_MODELS_TOO_CLOSE in seen
    assert PairOutcome.PAIR_NO_DIFFERENCE in seen
    assert PairOutcome.PAIR_SEPARATES in seen


# ---- T7: exact McNemar identity + Holm step-down (m=3 FIXED) ------------------

P1 = ("qwen3:14b", "qwen3:8b")
P2 = ("qwen3:14b", "qwen3.5:4b")
P3 = ("qwen3:8b", "qwen3.5:4b")
_TIE_ORDER = _CFG.pairs


def test_mcnemar_reused_by_identity():
    assert bakeoff_analysis.mcnemar_exact_p is mcnemar_exact_p


def test_holm_step_down_rejects_ascending_family_m3():
    raw = {P1: 0.004, P2: 0.03, P3: 0.5}
    rej = holm_rejections(raw, alpha=0.05, m=3, tie_order=_TIE_ORDER)
    # rank1 0.004 <= 0.05/3=0.0167 -> reject; rank2 0.03 > 0.05/2=0.025 -> STOP
    assert rej[P1] is True
    assert rej[P2] is False
    assert rej[P3] is False


def test_holm_adjusted_pvalue_is_running_max():
    raw = {P1: 0.004, P2: 0.03, P3: 0.5}
    adj = holm_adjusted_pvalues(raw, m=3, tie_order=_TIE_ORDER)
    assert adj[P1] == pytest.approx(0.012)  # 3 * 0.004
    assert adj[P2] == pytest.approx(0.06)  # max(0.012, 2 * 0.03)
    assert adj[P3] == pytest.approx(0.5)  # max(0.06, 1 * 0.5)


def test_holm_family_size_fixed_at_three_when_fewer_pairs_reach_test():
    # Only TWO pairs reach McNemar, but m stays 3 (anti-steering): the smallest
    # uses divisor 3 (threshold 0.0167), not divisor 2 (0.025).
    raw = {P1: 0.02, P2: 0.5}
    rej = holm_rejections(raw, alpha=0.05, m=3, tie_order=_TIE_ORDER)
    assert rej[P1] is False  # 0.02 > 0.05/3; would be True under m=2
    rej_m2 = holm_rejections(raw, alpha=0.05, m=2, tie_order=_TIE_ORDER)
    assert rej_m2[P1] is True  # confirms m=3 is what suppressed it


def test_holm_ties_broken_by_fixed_pair_order():
    raw = {P3: 0.02, P1: 0.02, P2: 0.02}  # all tied, insertion order scrambled
    adj = holm_adjusted_pvalues(raw, m=3, tie_order=_TIE_ORDER)
    # deterministic regardless of dict order: rank multipliers 3,2,1 by tie_order
    assert adj[P1] == pytest.approx(0.06)  # rank1 -> 3*0.02
    assert adj[P2] == pytest.approx(0.06)  # rank2 -> max(0.06, 2*0.02=0.04)
    assert adj[P3] == pytest.approx(0.06)  # rank3 -> max(0.06, 1*0.02)


def test_holm_boundary_p_equal_alpha_rejects():
    raw = {P1: 0.01, P2: 0.02, P3: 0.05}
    rej = holm_rejections(raw, alpha=0.05, m=3, tie_order=_TIE_ORDER)
    # rank3 threshold 0.05/1 = 0.05, p == 0.05 -> reject under the `<=` convention
    assert rej[P3] is True


# ---- T9: per-repo leave-one/leave-two-out concentration ----------------------


def test_repo_concentrated_when_leave_one_out_flips_direction():
    # base: c>b (sign -). Drop repoC -> b>c (sign +): a flip, staying above floor.
    cases = (
        _pair_cases(5, 0, 0, repo="A")  # b += 5
        + _pair_cases(0, 4, 0, repo="B")  # c += 4
        + _pair_cases(0, 4, 0, repo="C")  # c += 4
    )
    b, c = discordant_counts(cases)
    assert (b, c) == (5, 8) and b + c >= 8
    assert repo_concentrated(cases, alpha=0.05, floor=8) is True


def test_repo_concentrated_when_leave_two_out_drops_below_floor():
    # 5 repos x 2 a-only: b=10. No single drop < 8; dropping two -> 6 < 8.
    cases = []
    for r in range(5):
        cases += _pair_cases(2, 0, 0, repo=f"R{r}")
    assert discordant_counts(cases) == (10, 0)
    assert repo_concentrated(cases, alpha=0.05, floor=8) is True


def test_repo_not_concentrated_when_robust_to_all_drops():
    cases = []
    for r in range(8):
        cases += _pair_cases(2, 0, 0, repo=f"R{r}")  # b=16
    assert repo_concentrated(cases, alpha=0.05, floor=8) is False
    dist = per_repo_bc_distribution(cases)
    assert dist == {f"R{r}": 2 for r in range(8)}  # signed (b-c) per repo


# ---- T11: typed assembly of the pairwise verdicts ----------------------------


def _sep(pair, winner) -> PairResult:
    return PairResult(
        pair=pair, b=8, c=0, eligible_n=40, dropped_total=0, dropped_degrade=0,
        degraded_dominated=False, raw_p=0.008, adjusted_p=0.024, rejected=True,
        outcome=PairOutcome.PAIR_SEPARATES, winner=winner, repo_concentrated=False,
    )


def _nonsep(pair, outcome=PairOutcome.PAIR_NO_DIFFERENCE) -> PairResult:
    return PairResult(
        pair=pair, b=5, c=4, eligible_n=40, dropped_total=0, dropped_degrade=0,
        degraded_dominated=False, raw_p=1.0, adjusted_p=1.0, rejected=False,
        outcome=outcome, winner=None, repo_concentrated=False,
    )


_ALL = ("qwen3:14b", "qwen3:8b", "qwen3.5:4b")


def test_assembly_infrastructure_halted_when_fewer_than_two_survive():
    rep = assemble_bakeoff(
        {}, surviving_models=("qwen3:14b",),
        exclusions=(ModelExclusion("qwen3:8b", "unservable"),
                    ModelExclusion("qwen3.5:4b", "replay-fail")),
    )
    assert rep.outcome is BakeoffOutcome.INFRASTRUCTURE_HALTED
    assert len(rep.exclusions) == 2


def test_assembly_partial_when_exactly_two_survive():
    results = {P1: _sep(P1, "qwen3:14b")}
    rep = assemble_bakeoff(
        results, surviving_models=("qwen3:14b", "qwen3:8b"),
        exclusions=(ModelExclusion("qwen3.5:4b", "coherence-fail"),),
    )
    assert rep.outcome is BakeoffOutcome.PARTIAL
    assert rep.ranking is None  # a two-model bake-off never ranks all three


def test_assembly_ranking_when_edges_form_total_order():
    results = {
        P1: _sep(P1, "qwen3:14b"),
        P2: _sep(P2, "qwen3:14b"),
        P3: _sep(P3, "qwen3:8b"),
    }
    rep = assemble_bakeoff(results, surviving_models=_ALL, exclusions=())
    assert rep.outcome is BakeoffOutcome.RANKING
    assert rep.ranking == ("qwen3:14b", "qwen3:8b", "qwen3.5:4b")


def test_assembly_intransitive_when_edges_form_cycle():
    results = {
        P1: _sep(P1, "qwen3:14b"),  # 14b > 8b
        P3: _sep(P3, "qwen3:8b"),  # 8b > 4b
        P2: _sep(P2, "qwen3.5:4b"),  # 4b > 14b  -> cycle, out-degrees {1,1,1}
    }
    rep = assemble_bakeoff(results, surviving_models=_ALL, exclusions=())
    assert rep.outcome is BakeoffOutcome.INTRANSITIVE
    assert rep.ranking is None


def test_assembly_partial_when_some_separate_some_not():
    results = {
        P1: _sep(P1, "qwen3:14b"),
        P2: _nonsep(P2, PairOutcome.PAIR_MODELS_TOO_CLOSE),
        P3: _nonsep(P3, PairOutcome.PAIR_NO_DIFFERENCE),
    }
    rep = assemble_bakeoff(results, surviving_models=_ALL, exclusions=())
    assert rep.outcome is BakeoffOutcome.PARTIAL


def test_assembly_no_separation_when_no_pair_separates():
    results = {
        P1: _nonsep(P1),
        P2: _nonsep(P2, PairOutcome.PAIR_MODELS_TOO_CLOSE),
        P3: _nonsep(P3, PairOutcome.PAIR_UNDER_POWERED),
    }
    rep = assemble_bakeoff(results, surviving_models=_ALL, exclusions=())
    assert rep.outcome is BakeoffOutcome.NO_SEPARATION


def test_bakeoff_outcome_enum_is_total_over_grid():
    # every survivor count x edge config lands exactly one member, never None
    for survivors in ((), ("a",), ("a", "b"), _ALL):
        rep = assemble_bakeoff({}, surviving_models=survivors, exclusions=())
        assert isinstance(rep.outcome, BakeoffOutcome)


# ---- T13: reachability split is first-class ----------------------------------


def _entries(spec):
    """spec: {case_id: {model: bucket_or_'degrade'}} -> ledger-shaped entries."""
    out = {}
    for case_id, per_model in spec.items():
        for model, val in per_model.items():
            if val == "degrade":
                out[f"{case_id}::{model}"] = {"degrade": "generation-truncated"}
            else:
                out[f"{case_id}::{model}"] = {"bucket": val.value}
    return out


def test_split_by_reachability_conceptual_carries_verdict():
    reach = {"django__django-1": "conceptual", "flask__flask-2": "lexical"}
    entries = _entries({
        "django__django-1": {"qwen3:14b": C, "qwen3:8b": E},
        "flask__flask-2": {"qwen3:14b": C, "qwen3:8b": E},
    })
    cases, dropped_total, dropped_degrade = split_by_reachability(
        entries, reach, "qwen3:14b", "qwen3:8b"
    )
    assert [c.case_id for c in cases] == ["django__django-1"]  # conceptual only
    assert cases[0].repo == "django__django"
    assert (dropped_total, dropped_degrade) == (0, 0)


def test_split_by_reachability_counts_dropped_and_degrade():
    reach = {"a__a-1": "conceptual", "a__a-2": "conceptual", "a__a-3": "conceptual"}
    entries = _entries({
        "a__a-1": {"qwen3:14b": C, "qwen3:8b": E},  # clean pair
        "a__a-2": {"qwen3:14b": "degrade", "qwen3:8b": C},  # degrade drop
        "a__a-3": {"qwen3:14b": C},  # missing model_b -> plain drop
    })
    cases, dropped_total, dropped_degrade = split_by_reachability(
        entries, reach, "qwen3:14b", "qwen3:8b"
    )
    assert len(cases) == 1
    assert dropped_total == 2
    assert dropped_degrade == 1


def test_lexical_yields_descriptive_stats_only():
    reach = {"x__x-1": "lexical", "x__x-2": "lexical", "y__y-3": "conceptual"}
    entries = _entries({
        "x__x-1": {"qwen3:14b": C},
        "x__x-2": {"qwen3:14b": E},
        "y__y-3": {"qwen3:14b": C},
    })
    stats = lexical_descriptive_stats(entries, reach, "qwen3:14b")
    assert stats == {"found": 1, "not_found": 1, "total": 2}  # lexical only
    assert not isinstance(stats, PairResult)  # NEVER a verdict


def test_no_whole_pool_average_headline():
    # The report shape exposes per-stratum lines and NO pooled/averaged headline.
    fields = {f.name for f in __import__("dataclasses").fields(BakeoffReport)}
    assert "lexical_stats" in fields
    assert not any("average" in n or "pooled" in n or "whole_pool" in n for n in fields)
