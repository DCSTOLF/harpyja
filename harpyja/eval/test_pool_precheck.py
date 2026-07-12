"""Spec 0040 — pool: frozen 3-model/3-pair pre-check config + preflight enum +
the two per-pair quantities + coverage + the total per-pair verdict."""

from __future__ import annotations

import dataclasses

import pytest

from harpyja.eval.benchmark_fit import PREREGISTERED_CONFIG
from harpyja.eval.locate_accuracy import LocateBucket
from harpyja.eval.pool_precheck import (
    PAIR_VERDICT_ORDER,
    POOL_CONFIG_HASH_0040,
    PREFLIGHT_PRECEDENCE,
    PREREGISTERED_POOL_CONFIG_0040,
    PairCase,
    PairVerdict,
    PreflightObservations,
    PreflightOutcome,
    adjudicate_preflight,
    build_pair_cases,
    coverage_below_minimum,
    decide_pair_verdict,
    decide_pool_fork,
    is_excluding,
    observed_discordance,
    pilot_conceptual_coverage,
    pool_config_hash,
    union_located_ceiling,
)
from harpyja.eval.think_ab_precheck import load_fixture_reachability

_CFG = PREREGISTERED_POOL_CONFIG_0040


def test_preregistered_pool_config_0040_pins_all_verdict_shaping_fields():
    # The three model tags — three sizes, two generations.
    assert _CFG.model_tags == ("qwen3:14b", "qwen3:8b", "qwen3.5:4b")
    # The three named pairwise contrasts.
    assert _CFG.pairs == (
        ("qwen3:14b", "qwen3:8b"),
        ("qwen3:14b", "qwen3.5:4b"),
        ("qwen3:8b", "qwen3.5:4b"),
    )
    # Multiplicity: decided NOW, outcome-blind — per-pair alpha, uncorrected,
    # because each pair answers a distinct standalone decision question.
    assert _CFG.multiplicity_stance == "per-pair-alpha-uncorrected"
    assert "standalone" in _CFG.multiplicity_rationale
    assert _CFG.alpha == 0.05
    # Arm parity: every pilot arm runs the shipped default (thinking on).
    assert _CFG.explorer_think is None
    # Staging fallback pre-declared (OQ3) — never chosen after early results.
    assert _CFG.staging_order == (
        "preflight-all-3-then-pilot-widest-gap-pair-first"
    )
    # Frozen dataclass — a mutable config is not a freeze.
    with pytest.raises(dataclasses.FrozenInstanceError):
        _CFG.alpha = 0.1  # type: ignore[misc]


def test_pool_config_conceptual_floor_reuses_benchmark_fit():
    # The floor is FIXED at the committed 0023 exact-McNemar floor, copied
    # verbatim from the same source 0039 pinned — never a local literal that
    # could be re-derived downward after outcomes are visible.
    assert _CFG.conceptual_min_discordant is PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS
    assert _CFG.floor_derivation == "fixed-not-re-derivable"


def test_pool_config_coverage_minimum_is_the_consuming_arithmetic():
    # MIN_PILOT_CONCEPTUAL_COVERAGE = 8 is DERIVED, not a round guess: the
    # unpiloted conceptual remainder must be strictly smaller than the floor
    # (15 - c < 8  =>  c >= 8), else a verdict could rest on majority-unobserved
    # mass — the vacuity boundary (0 observed + 8 unpiloted >= floor).
    c = _CFG.min_pilot_conceptual_coverage
    assert c == 8
    assert _CFG.full_conceptual_n == 15
    assert _CFG.full_conceptual_n - c < _CFG.conceptual_min_discordant
    # Minimality: one case fewer would sit ON the vacuity boundary.
    assert _CFG.full_conceptual_n - (c - 1) >= _CFG.conceptual_min_discordant
    assert "15 - c < 8" in _CFG.coverage_derivation


def test_pool_config_two_quantities_carry_distinct_epistemic_labels():
    # The headline anti-conflation: the ceiling is a BOUND, the observed
    # discordance is an ESTIMATE — two quantities, two distinct labels.
    assert _CFG.projection_kind == "upper-bound-feasibility"
    assert _CFG.estimate_kind == "point-estimate"
    assert _CFG.projection_kind != _CFG.estimate_kind


def test_pool_config_pinned_pilot_ids_cover_at_least_eight_conceptual():
    # The pinned pilot IDs extend the 0036 first-10 subset (7 conceptual) by
    # the NEXT conceptual case in committed fixture order — no cherry-picking
    # after 0039's per-case results.
    reachability = load_fixture_reachability()
    assert set(_CFG.pilot_case_ids) <= set(reachability)
    conceptual = [
        cid for cid in _CFG.pilot_case_ids if reachability[cid] == "conceptual"
    ]
    assert len(conceptual) >= _CFG.min_pilot_conceptual_coverage
    # The extension case is the first conceptual case beyond the first 10 in
    # fixture order.
    assert "django__django-14315" in _CFG.pilot_case_ids


def test_pool_config_hash_0040_is_stable():
    assert POOL_CONFIG_HASH_0040 == pool_config_hash(_CFG)
    assert len(POOL_CONFIG_HASH_0040) == 64


# ---- preflight enum + precedence + adjudicator (AC2) --------------------------


def test_preflight_outcomes_are_exactly_the_five_committed_values():
    assert {o.value for o in PreflightOutcome} == {
        "preflight-pass",
        "unservable",
        "coherence-fail",
        "tool-call-malformed",
        "think-control-noop",
    }


def test_preflight_precedence_frozen_order():
    # Cheapest / most-fundamental failure first; matches the frozen config.
    assert PREFLIGHT_PRECEDENCE == (
        PreflightOutcome.UNSERVABLE,
        PreflightOutcome.COHERENCE_FAIL,
        PreflightOutcome.TOOL_CALL_MALFORMED,
        PreflightOutcome.THINK_CONTROL_NOOP,
        PreflightOutcome.PREFLIGHT_PASS,
    )
    assert tuple(o.value for o in PREFLIGHT_PRECEDENCE) == _CFG.preflight_precedence


def test_preflight_tiebreak_coherence_and_toolcall_types_coherence_fail():
    # A model failing BOTH coherence and tool-calling adjudicates to
    # COHERENCE_FAIL — the committed tie-break, not implementer choice.
    obs = PreflightObservations(
        served=True, coherent=False, tool_calls_clean=False, think_control="effective"
    )
    assert adjudicate_preflight(obs) is PreflightOutcome.COHERENCE_FAIL


def test_indeterminate_think_probe_maps_to_think_control_noop():
    # A think-control probe whose effect cannot be adjudicated under the
    # tiny-cap discriminator maps to THINK_CONTROL_NOOP — conservative (barred
    # from a thinking-arm), never a stall outside the committed answer space.
    obs = PreflightObservations(
        served=True, coherent=True, tool_calls_clean=True, think_control="indeterminate"
    )
    assert adjudicate_preflight(obs) is PreflightOutcome.THINK_CONTROL_NOOP
    noop = PreflightObservations(
        served=True, coherent=True, tool_calls_clean=True, think_control="noop"
    )
    assert adjudicate_preflight(noop) is PreflightOutcome.THINK_CONTROL_NOOP
    clean = PreflightObservations(
        served=True, coherent=True, tool_calls_clean=True, think_control="effective"
    )
    assert adjudicate_preflight(clean) is PreflightOutcome.PREFLIGHT_PASS


# ---- derived coverage minimum (AC7) -------------------------------------------


def _n_pairs(n: int) -> list[PairCase]:
    return [
        PairCase(
            case_id=f"c{i}",
            bucket_a=LocateBucket.CORRECT,
            bucket_b=LocateBucket.EMPTY,
        )
        for i in range(n)
    ]


def test_pilot_conceptual_coverage_counts_both_buckets_present():
    # Coverage counts the retained pairs — conceptual cases where BOTH models
    # produced a clean bucket (build_pair_cases already drops the rest).
    assert pilot_conceptual_coverage(_n_pairs(7)) == 7
    assert pilot_conceptual_coverage([]) == 0


def test_insufficient_pilot_evidence_fires_at_c_equals_seven():
    # The 0036 first-10 subset alone: 7 conceptual — the unpiloted remainder
    # (15-7=8) could clear the floor on its own → the predicate fires.
    assert coverage_below_minimum(_n_pairs(7), _CFG)


def test_insufficient_pilot_evidence_does_not_fire_at_c_equals_eight():
    # At c=8 the remainder (7) is strictly below the floor — extrapolation
    # admissible, never a shaky FEASIBLE below the boundary.
    assert not coverage_below_minimum(_n_pairs(8), _CFG)


# ---- the TWO per-pair quantities from per-case pairs (AC5) --------------------


def _pairs(spec: dict[str, tuple[str, str]]) -> list[PairCase]:
    return [
        PairCase(case_id=cid, bucket_a=LocateBucket(a), bucket_b=LocateBucket(b))
        for cid, (a, b) in spec.items()
    ]


# 8 piloted conceptual pairs: A locates c1..c6 (6), B locates c1..c5 (5) —
# B's located set is a SUBSET of A's: union-located 6, signal-discordant 1 (c6).
_SUBSET_SCENARIO = {
    "c1": ("correct", "correct"),
    "c2": ("correct", "right-file-wrong-span"),
    "c3": ("right-file-wrong-span", "correct"),
    "c4": ("correct", "correct"),
    "c5": ("right-file-wrong-span", "right-file-wrong-span"),
    "c6": ("correct", "empty"),
    "c7": ("empty", "wrong-file"),
    "c8": ("wrong-file", "empty"),
}

# IDENTICAL marginals (A=6, B=5) but minimally-overlapping located sets:
# A locates c1..c6, B locates c4..c8: union-located 8, signal-discordant 5.
_DISJOINT_SCENARIO = {
    "c1": ("correct", "empty"),
    "c2": ("correct", "wrong-file"),
    "c3": ("correct", "empty"),
    "c4": ("correct", "correct"),
    "c5": ("right-file-wrong-span", "right-file-wrong-span"),
    "c6": ("correct", "correct"),
    "c7": ("empty", "right-file-wrong-span"),
    "c8": ("wrong-file", "correct"),
}


def test_union_located_ceiling_and_observed_discordance_from_per_case_pairs():
    pairs = _pairs(_SUBSET_SCENARIO)
    # Union-located 6 of 8 piloted → ceiling round(15 * 6/8) = 11 (a BOUND:
    # every union-located case assumed discordant).
    assert union_located_ceiling(pairs, full_conceptual_n=15) == 11
    # Observed signal-discordance 1 of 8 → estimate round(15 * 1/8) = 2.
    assert observed_discordance(pairs, full_conceptual_n=15) == 2
    # Degenerate: no pairs → both quantities 0, never a division error.
    assert union_located_ceiling([], full_conceptual_n=15) == 0
    assert observed_discordance([], full_conceptual_n=15) == 0


def test_observed_discordance_reuses_committed_is_signal_discordant_oracle():
    # One-oracle reuse, identity-asserted (the 0032 pattern): the located
    # predicate and the discordance predicate are THE committed ones — never a
    # re-derived local rule that could drift.
    from harpyja.eval import ac8_pilot, pool_precheck, think_ab

    assert pool_precheck.is_signal_discordant is ac8_pilot.is_signal_discordant
    assert pool_precheck.located_via_oracle is think_ab.located_via_oracle


def test_marginal_counts_trap_yields_different_verdicts():
    # IDENTICAL marginal locate-counts (6 vs 5) — different per-case overlap:
    # marginals cannot recover union-located or discordance; per-case pairs can.
    subset = _pairs(_SUBSET_SCENARIO)
    disjoint = _pairs(_DISJOINT_SCENARIO)
    assert union_located_ceiling(subset, full_conceptual_n=15) == 11
    assert union_located_ceiling(disjoint, full_conceptual_n=15) == 15
    assert observed_discordance(subset, full_conceptual_n=15) == 2
    assert observed_discordance(disjoint, full_conceptual_n=15) == 9


def test_ceiling_is_not_vacuous_and_distinct_from_observed_discordance():
    # The ceiling is neither trivially full-N (not vacuous) nor equal to the
    # observed-discordance estimate — two genuinely distinct quantities on a
    # fixture where the models locate overlapping-but-discordant sets.
    pairs = _pairs(_SUBSET_SCENARIO)
    ceiling = union_located_ceiling(pairs, full_conceptual_n=15)
    observed = observed_discordance(pairs, full_conceptual_n=15)
    assert ceiling < 15
    assert observed < ceiling


def test_build_pair_cases_joins_ledger_entries_on_conceptual_stratum():
    entries = {
        "x::m-a": {"bucket": "correct", "degrade": None},
        "x::m-b": {"bucket": "empty", "degrade": None},
        "y::m-a": {"bucket": "correct", "degrade": None},
        "y::m-b": {"bucket": "correct", "degrade": None},
        # lexical case — excluded from the conceptual stratum.
        "lex::m-a": {"bucket": "correct", "degrade": None},
        "lex::m-b": {"bucket": "correct", "degrade": None},
        # degraded cell — not a capability observation; the case drops.
        "z::m-a": {"bucket": None, "degrade": "verifier:timeout"},
        "z::m-b": {"bucket": "correct", "degrade": None},
        # only one arm present — no pair.
        "w::m-a": {"bucket": "correct", "degrade": None},
    }
    reachability = {"x": "conceptual", "y": "conceptual", "z": "conceptual",
                    "w": "conceptual", "lex": "lexical"}
    pairs = build_pair_cases(entries, "m-a", "m-b", reachability)
    assert {p.case_id for p in pairs} == {"x", "y"}
    by_id = {p.case_id: p for p in pairs}
    assert by_id["x"].bucket_a is LocateBucket.CORRECT
    assert by_id["x"].bucket_b is LocateBucket.EMPTY


def test_preflight_asymmetry_noop_nonexcluding_others_excluding():
    # DELIBERATE asymmetry (load-bearing — never "fix" into symmetry):
    # THINK_CONTROL_NOOP still bakes off (default-on), only barred from a
    # future thinking-arm; the other three failures EXCLUDE.
    assert not is_excluding(PreflightOutcome.THINK_CONTROL_NOOP)
    assert not is_excluding(PreflightOutcome.PREFLIGHT_PASS)
    assert is_excluding(PreflightOutcome.UNSERVABLE)
    assert is_excluding(PreflightOutcome.COHERENCE_FAIL)
    assert is_excluding(PreflightOutcome.TOOL_CALL_MALFORMED)


# ---- total per-pair verdict + frozen predicate order + fork (AC6) --------------

_PASS = PreflightOutcome.PREFLIGHT_PASS


def _uniform_pairs(n: int, a: str, b: str) -> list[PairCase]:
    return [
        PairCase(case_id=f"c{i}", bucket_a=LocateBucket(a), bucket_b=LocateBucket(b))
        for i in range(n)
    ]


def test_pair_verdict_total_over_five_member_enum_every_member_reachable():
    # MODEL_EXCLUDED: a preflight-excluded member — before any arithmetic.
    r = decide_pair_verdict(
        _CFG, [], preflight_a=PreflightOutcome.COHERENCE_FAIL, preflight_b=_PASS
    )
    assert r.verdict is PairVerdict.PAIR_NOT_EVALUATED_MODEL_EXCLUDED
    # INSUFFICIENT: 7 retained pairs — under the derived coverage minimum.
    r = decide_pair_verdict(
        _CFG, _uniform_pairs(7, "correct", "empty"), preflight_a=_PASS, preflight_b=_PASS
    )
    assert r.verdict is PairVerdict.INSUFFICIENT_PILOT_EVIDENCE
    # UNDER_POWERED: neither model locates anything — ceiling 0 < floor 8.
    r = decide_pair_verdict(
        _CFG, _uniform_pairs(8, "empty", "wrong-file"), preflight_a=_PASS, preflight_b=_PASS
    )
    assert r.verdict is PairVerdict.PAIR_UNDER_POWERED
    # TOO_CLOSE: both locate the SAME cases — ceiling 15 clears, discordance 0.
    r = decide_pair_verdict(
        _CFG, _uniform_pairs(8, "correct", "correct"), preflight_a=_PASS, preflight_b=_PASS
    )
    assert r.verdict is PairVerdict.PAIR_MODELS_TOO_CLOSE
    # FEASIBLE: fully discordant — ceiling 15 and observed 15 both clear.
    r = decide_pair_verdict(
        _CFG, _uniform_pairs(8, "correct", "empty"), preflight_a=_PASS, preflight_b=_PASS
    )
    assert r.verdict is PairVerdict.PAIR_FEASIBLE
    # The result carries the floor by REUSE, plus both epistemic labels.
    assert r.floor is PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS
    assert r.projection_kind == "upper-bound-feasibility"
    assert r.estimate_kind == "point-estimate"


def test_pair_verdict_predicate_order_frozen():
    # The enum's value order IS the frozen config's predicate order.
    assert tuple(v.value for v in PAIR_VERDICT_ORDER) == _CFG.pair_verdict_order
    # An input satisfying MULTIPLE predicates resolves to the EARLIEST:
    # excluded model + insufficient coverage → MODEL_EXCLUDED.
    r = decide_pair_verdict(
        _CFG,
        _uniform_pairs(7, "empty", "empty"),
        preflight_a=PreflightOutcome.UNSERVABLE,
        preflight_b=_PASS,
    )
    assert r.verdict is PairVerdict.PAIR_NOT_EVALUATED_MODEL_EXCLUDED
    # insufficient coverage + would-be under-powered → INSUFFICIENT.
    r = decide_pair_verdict(
        _CFG, _uniform_pairs(7, "empty", "empty"), preflight_a=_PASS, preflight_b=_PASS
    )
    assert r.verdict is PairVerdict.INSUFFICIENT_PILOT_EVIDENCE
    # ceiling < floor wins over the closeness estimate (both under floor):
    # UNDER_POWERED, never TOO_CLOSE.
    r = decide_pair_verdict(
        _CFG, _uniform_pairs(8, "empty", "empty"), preflight_a=_PASS, preflight_b=_PASS
    )
    assert r.verdict is PairVerdict.PAIR_UNDER_POWERED
    # THINK_CONTROL_NOOP is NON-excluding — the pair still evaluates.
    r = decide_pair_verdict(
        _CFG,
        _uniform_pairs(8, "correct", "empty"),
        preflight_a=PreflightOutcome.THINK_CONTROL_NOOP,
        preflight_b=_PASS,
    )
    assert r.verdict is PairVerdict.PAIR_FEASIBLE


def test_too_close_distinct_from_under_powered_when_ceiling_clears_discordance_zero():
    # The distinct reportable finding: under-powered-because-IDENTICAL
    # (ceiling clears, models agree) vs under-powered-because-few-cases
    # (ceiling cannot reach the floor). Same "no bake-off signal", different
    # typed cause.
    identical = decide_pair_verdict(
        _CFG, _uniform_pairs(8, "correct", "correct"), preflight_a=_PASS, preflight_b=_PASS
    )
    nobody = decide_pair_verdict(
        _CFG, _uniform_pairs(8, "empty", "empty"), preflight_a=_PASS, preflight_b=_PASS
    )
    assert identical.verdict is PairVerdict.PAIR_MODELS_TOO_CLOSE
    assert nobody.verdict is PairVerdict.PAIR_UNDER_POWERED
    assert identical.ceiling >= identical.floor > identical.observed
    assert nobody.ceiling < nobody.floor


def _fork_entries(
    buckets_by_model: dict[str, dict[str, str]]
) -> dict[str, dict[str, object]]:
    entries: dict[str, dict[str, object]] = {}
    for model, buckets in buckets_by_model.items():
        for cid, bucket in buckets.items():
            entries[f"{cid}::{model}"] = {"bucket": bucket, "degrade": None}
    return entries


def test_model_excluded_voids_every_pair_containing_it_including_14b():
    cases = {f"c{i}": "correct" for i in range(8)}
    entries = _fork_entries(
        {"qwen3:14b": cases, "qwen3:8b": cases, "qwen3.5:4b": cases}
    )
    reachability = {f"c{i}": "conceptual" for i in range(8)}
    # 8b excluded → both pairs containing 8b void; 14b-4b still evaluates.
    fork = decide_pool_fork(
        _CFG,
        entries,
        reachability,
        preflight_by_model={
            "qwen3:14b": _PASS,
            "qwen3:8b": PreflightOutcome.TOOL_CALL_MALFORMED,
            "qwen3.5:4b": _PASS,
        },
    )
    assert (
        fork["qwen3:14b vs qwen3:8b"].verdict
        is PairVerdict.PAIR_NOT_EVALUATED_MODEL_EXCLUDED
    )
    assert (
        fork["qwen3:8b vs qwen3.5:4b"].verdict
        is PairVerdict.PAIR_NOT_EVALUATED_MODEL_EXCLUDED
    )
    assert (
        fork["qwen3:14b vs qwen3.5:4b"].verdict
        is not PairVerdict.PAIR_NOT_EVALUATED_MODEL_EXCLUDED
    )
    # 14b (the re-confirmed anchor) failing voids ALL THREE pairs — a
    # harness-integrity signal, not just a membership fact.
    fork = decide_pool_fork(
        _CFG,
        entries,
        reachability,
        preflight_by_model={
            "qwen3:14b": PreflightOutcome.COHERENCE_FAIL,
            "qwen3:8b": _PASS,
            "qwen3.5:4b": _PASS,
        },
    )
    assert all(
        r.verdict is PairVerdict.PAIR_NOT_EVALUATED_MODEL_EXCLUDED
        for r in fork.values()
    )


def test_decide_pool_fork_types_all_three_pairs():
    reachability = {f"c{i}": "conceptual" for i in range(8)}
    entries = _fork_entries(
        {
            # 14b locates everything; 8b nothing; 4b the first four.
            "qwen3:14b": {f"c{i}": "correct" for i in range(8)},
            "qwen3:8b": {f"c{i}": "empty" for i in range(8)},
            "qwen3.5:4b": {
                f"c{i}": ("right-file-wrong-span" if i < 4 else "wrong-file")
                for i in range(8)
            },
        }
    )
    fork = decide_pool_fork(
        _CFG,
        entries,
        reachability,
        preflight_by_model={m: _PASS for m in _CFG.model_tags},
    )
    assert set(fork) == {
        "qwen3:14b vs qwen3:8b",
        "qwen3:14b vs qwen3.5:4b",
        "qwen3:8b vs qwen3.5:4b",
    }
    assert all(isinstance(r.verdict, PairVerdict) for r in fork.values())
    # 14b vs 8b: union 8 → ceiling 15; discordance 8 → observed 15 → FEASIBLE.
    assert fork["qwen3:14b vs qwen3:8b"].verdict is PairVerdict.PAIR_FEASIBLE
    # 8b vs 4b: union 4 → ceiling 8 (>= floor); discordance 4 → observed 8 →
    # FEASIBLE at the exact boundary.
    assert fork["qwen3:8b vs qwen3.5:4b"].verdict is PairVerdict.PAIR_FEASIBLE
