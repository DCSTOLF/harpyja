"""Spec 0039 — thinking A/B: frozen config + total pure verdict tests (AC1–AC4)."""

from __future__ import annotations

import dataclasses

import pytest

from harpyja.eval import ac8_pilot, benchmark_fit, think_ab
from harpyja.eval.benchmark_fit import PREREGISTERED_CONFIG
from harpyja.eval.locate_accuracy import LocateBucket
from harpyja.eval.reconcile_probe import load_committed_reconcile_probe_result
from harpyja.eval.terse_dataset import STRATUM_UNDER_POPULATED
from harpyja.eval.think_ab import (
    AB_CONFIG_HASH_0039,
    AB_REPORT_OUTCOMES,
    PREREGISTERED_AB_CONFIG_0039,
    AbVerdict,
    PairRecord,
    ab_config_hash,
    classify_pair_validity,
    decide_ab_report,
    decide_ab_verdict,
)

# ---- AC1: the frozen, hashed, pre-registered decision config -----------------


def test_preregistered_ab_config_0039_pins_all_verdict_shaping_fields():
    cfg = PREREGISTERED_AB_CONFIG_0039
    # Arms: A = shipped default (None, behaviorally ON per 0038), B = off (False).
    # True("high") is a THIRD OBSERVATIONAL arm only — never in the paired verdict.
    assert cfg.arm_a_think is None
    assert cfg.arm_b_think is False
    assert cfg.arm_c_think is True
    assert cfg.arm_c_observational_only is True
    # Statistics.
    assert cfg.alpha == 0.05
    # K policy (OQ1 frozen at plan time): K=2 paired arms, any-success fold,
    # observational arm K=1.
    assert cfg.k_repeats == 2
    assert cfg.k_fold_rule == "any-success"
    assert cfg.observational_k == 1
    # Run-integrity thresholds (the CONFOUNDED predicate inputs).
    assert 0.0 < cfg.invalid_pair_ceiling < 1.0
    assert 0.0 < cfg.degrade_asymmetry_threshold < 1.0
    # Seed schedule (OQ2 frozen): repeat k uses seed S_k for BOTH arms; the
    # honoring claim starts UNVERIFIED until the driver's two-call probe passes.
    assert len(cfg.seed_schedule) == cfg.k_repeats
    assert cfg.seed_honoring == "unverified"
    # The config is frozen — assignment must raise.
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.alpha = 0.5  # type: ignore[misc]


def test_ab_config_pins_model_tag_and_serving_transport():
    # Model identity is PRE-REGISTERED in the hashed config, not resolved at run
    # time (a runtime resolve is a servability check, not a pre-registration) —
    # and it must match the committed 0038 probe evidence exactly.
    cfg = PREREGISTERED_AB_CONFIG_0039
    probe = load_committed_reconcile_probe_result()
    assert cfg.lm_model == "qwen3:14b" == probe["model"]
    assert cfg.serving_transport == "v1-reasoning-effort" == probe["chosen_path"]


def test_ab_config_pins_completion_tokens_factor_b_predicate():
    # Factor (b) of the two-factor distinctness guard has a FROZEN operational
    # form: per-case aggregate of per-turn completion_tokens, direction on >= off,
    # with a minimum delta — never decided at scoring time.
    cfg = PREREGISTERED_AB_CONFIG_0039
    assert cfg.factor_b_scope == "per-case-aggregate"
    assert cfg.factor_b_direction == "on-at-least-off"
    assert cfg.min_on_vs_off_token_delta > 0
    # Factor (b) bites ONLY when the on arm reasoned SUBSTANTIALLY — an easy case
    # where the on arm thought little produces a legitimately small budget delta
    # and must never be invalidated by this factor.
    assert cfg.factor_b_min_on_reasoning_chars > 0


def test_ab_config_conceptual_floor_fixed_at_eight_reuses_benchmark_fit():
    # The conceptual-stratum floor is FIXED at the committed 0023 exact-McNemar
    # floor (8) — the derivation rule is pinned fixed-not-re-derivable (no drop
    # to the arithmetic minimum of 6 after seeing the data).
    cfg = PREREGISTERED_AB_CONFIG_0039
    assert cfg.conceptual_min_discordant == PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS == 8
    assert cfg.floor_derivation == "fixed-not-re-derivable"
    # Stratum verdict eligibility reuses the committed 0023 min_n.
    assert cfg.stratum_min_cases == PREREGISTERED_CONFIG.min_n == 12


def test_ab_config_hash_0039_is_stable():
    assert AB_CONFIG_HASH_0039 == ab_config_hash(PREREGISTERED_AB_CONFIG_0039)
    assert len(AB_CONFIG_HASH_0039) == 64  # sha256 hex


# ---- AC1/AC2: total pure verdict over the full outcome grid ------------------


def _pair(
    cid: str,
    on: LocateBucket | None,
    off: LocateBucket | None,
    *,
    reachability: str = "conceptual",
    reasoning_on: int = 900,
    reasoning_off: int = 0,
    tokens_on: int = 1500,
    tokens_off: int = 400,
    degrade_on: str | None = None,
    degrade_off: str | None = None,
) -> PairRecord:
    return PairRecord(
        case_id=cid,
        reachability=reachability,
        bucket_on=on,
        bucket_off=off,
        reasoning_chars_on=reasoning_on,
        reasoning_chars_off=reasoning_off,
        completion_tokens_on=tokens_on,
        completion_tokens_off=tokens_off,
        degrade_on=degrade_on,
        degrade_off=degrade_off,
    )


def _helping_flips(n: int) -> list[PairRecord]:
    # off missed, on located — the flip that favors thinking-on.
    return [_pair(f"h{i}", LocateBucket.CORRECT, LocateBucket.EMPTY) for i in range(n)]


def _hurting_flips(n: int) -> list[PairRecord]:
    return [_pair(f"x{i}", LocateBucket.EMPTY, LocateBucket.CORRECT) for i in range(n)]


def test_decide_ab_verdict_full_outcome_grid_every_member_reachable():
    cfg = PREREGISTERED_AB_CONFIG_0039
    # THINKING_HELPS: 9/0 discordant favoring on (exact p = 2/512 < 0.05).
    assert decide_ab_verdict(_helping_flips(9), cfg).verdict is AbVerdict.THINKING_HELPS
    # THINKING_HURTS: the mirror — the enum is direction-complete.
    assert decide_ab_verdict(_hurting_flips(9), cfg).verdict is AbVerdict.THINKING_HURTS
    # NO_EFFECT: floor met (8 discordant) but balanced 4/4 → p = 1.0.
    balanced = _helping_flips(4) + _hurting_flips(4)
    assert decide_ab_verdict(balanced, cfg).verdict is AbVerdict.NO_EFFECT
    # UNDER_POWERED: only 3 signal-bearing discordant pairs, under the floor of 8.
    assert decide_ab_verdict(_helping_flips(3), cfg).verdict is AbVerdict.UNDER_POWERED
    # CONFOUNDED: heavy one-sided on-arm typed degrades above the frozen threshold.
    degraded = _helping_flips(9) + [
        _pair(f"d{i}", None, LocateBucket.EMPTY, degrade_on="generation-truncated")
        for i in range(6)
    ]
    assert decide_ab_verdict(degraded, cfg).verdict is AbVerdict.CONFOUNDED


def test_confounded_checked_first():
    # BOTH confounded and would-be-significant → CONFOUNDED wins; a confounded
    # run never emits a statistical verdict.
    cfg = PREREGISTERED_AB_CONFIG_0039
    records = _helping_flips(10) + [
        _pair(f"d{i}", None, LocateBucket.EMPTY, degrade_on="wall-clock")
        for i in range(7)
    ]
    result = decide_ab_verdict(records, cfg)
    assert result.verdict is AbVerdict.CONFOUNDED
    assert result.confound_reasons  # the cause is recorded, never silent


def test_under_floor_null_is_under_powered_not_no_effect():
    cfg = PREREGISTERED_AB_CONFIG_0039
    # 3 discordant, balanced-ish (2/1): under-floor null → UNDER_POWERED, never
    # NO_EFFECT and never a forced directional result.
    records = _helping_flips(2) + _hurting_flips(1) + [
        _pair(f"c{i}", LocateBucket.CORRECT, LocateBucket.CORRECT) for i in range(5)
    ]
    result = decide_ab_verdict(records, cfg)
    assert result.verdict is AbVerdict.UNDER_POWERED
    assert result.signal_discordant == 3


def test_verdict_predicates_non_overlapping_and_total():
    # Sweep a grid of (helping, hurting, concordant, on-degraded) counts: every
    # input maps to exactly one enum member, no path raises, no silent default.
    cfg = PREREGISTERED_AB_CONFIG_0039
    for b in range(0, 10, 3):
        for c in range(0, 10, 3):
            for conc in (0, 4):
                for deg in (0, 3, 8):
                    records = (
                        _helping_flips(b)
                        + _hurting_flips(c)
                        + [
                            _pair(f"c{i}", LocateBucket.CORRECT, LocateBucket.CORRECT)
                            for i in range(conc)
                        ]
                        + [
                            _pair(f"d{i}", None, LocateBucket.EMPTY, degrade_on="x")
                            for i in range(deg)
                        ]
                    )
                    result = decide_ab_verdict(records, cfg)
                    assert isinstance(result.verdict, AbVerdict)


def test_signal_discordance_reuses_committed_0026_oracle():
    # The localizes-bucket set routes through the committed 0026 oracle
    # (CORRECT + RIGHT_FILE_WRONG_SPAN = located), never a re-derived local rule.
    assert think_ab.is_signal_discordant is ac8_pilot.is_signal_discordant
    cfg = PREREGISTERED_AB_CONFIG_0039
    records = [
        # right-file-wrong-span counts as LOCATED → this flip is signal-bearing.
        _pair("s1", LocateBucket.RIGHT_FILE_WRONG_SPAN, LocateBucket.EMPTY),
        # empty↔wrong-file: both NOT located → concordant noise, not a flip.
        _pair("n1", LocateBucket.WRONG_FILE, LocateBucket.EMPTY),
    ]
    result = decide_ab_verdict(records, cfg)
    assert result.signal_discordant == 1


# ---- AC4: reachability split + unified total report taxonomy -----------------


def _mixed_set() -> list[PairRecord]:
    # 15 conceptual (9 helping flips + 6 concordant) + 4 lexical concordant —
    # mirroring the 0036 sample shape.
    conceptual = _helping_flips(9) + [
        _pair(f"cc{i}", LocateBucket.CORRECT, LocateBucket.CORRECT) for i in range(6)
    ]
    lexical = [
        _pair(
            f"lx{i}",
            LocateBucket.CORRECT,
            LocateBucket.CORRECT,
            reachability="lexical",
        )
        for i in range(4)
    ]
    return conceptual + lexical


def test_reachability_split_conceptual_gets_own_floor_and_verdict_line():
    cfg = PREREGISTERED_AB_CONFIG_0039
    report = decide_ab_report(_mixed_set(), cfg)
    conceptual = report.strata["conceptual"]
    assert conceptual.n == 15
    assert conceptual.status == "verdicted"
    assert conceptual.result is not None
    assert conceptual.result.verdict is AbVerdict.THINKING_HELPS
    # The conceptual stratum is verdicted against ITS OWN committed floor.
    assert conceptual.floor == cfg.conceptual_min_discordant == 8


def test_lexical_stratum_typed_stratum_under_populated():
    cfg = PREREGISTERED_AB_CONFIG_0039
    report = decide_ab_report(_mixed_set(), cfg)
    lexical = report.strata["lexical"]
    # N=4 is below any declared floor: the line is TYPED under-populated —
    # described (its N is visible) but never verdicted, never implied comparable.
    assert lexical.n == 4
    assert lexical.status == STRATUM_UNDER_POPULATED
    assert lexical.result is None


def test_ab_report_unifies_verdict_precheck_and_stratum_shapes():
    # ONE total outcome taxonomy: the FIVE verdict members (direction-complete)
    # plus the pre-check stop plus the stratum under-populated line — 7 typed
    # outcomes, no stringly ad-hoc extras.
    assert len(AbVerdict) == 5
    assert AB_REPORT_OUTCOMES == frozenset(v.value for v in AbVerdict) | {
        "under-powered-stop",
        STRATUM_UNDER_POPULATED,
    }
    # A pre-check stop produces the same report shape with the typed headline.
    cfg = PREREGISTERED_AB_CONFIG_0039
    stopped = decide_ab_report([], cfg, precheck_stop=True)
    assert stopped.headline == "under-powered-stop"
    assert stopped.strata == {}


def test_whole_set_average_not_the_headline():
    cfg = PREREGISTERED_AB_CONFIG_0039
    report = decide_ab_report(_mixed_set(), cfg)
    # The headline is the conceptual-stratum line — the hypothesis and the
    # majority — never a whole-set average (RETRIEVAL_FUNDAMENTAL confound).
    assert report.headline.startswith("conceptual:")
    field_names = {f.name for f in dataclasses.fields(report)}
    assert not any("accuracy" in name or "average" in name for name in field_names)


# ---- AC3: two-factor arm-distinctness guard (deliberately asymmetric) --------


def test_off_arm_reasoning_excludes_and_records_pair():
    # An off arm showing reasoning = the knob failed = instrument defect: the
    # pair is EXCLUDED-AND-RECORDED with its cause, never silently dropped and
    # never counted.
    cfg = PREREGISTERED_AB_CONFIG_0039
    bad = _pair("bad1", LocateBucket.CORRECT, LocateBucket.EMPTY, reasoning_off=700)
    result = decide_ab_verdict(_helping_flips(9) + [bad], cfg)
    assert ("bad1", "invalid:off-arm-reasoning-present") in result.excluded
    assert result.pairs_counted == 9  # the invalid pair is not counted


def test_factor_b_completion_tokens_predicate_per_case_aggregate():
    cfg = PREREGISTERED_AB_CONFIG_0039
    # Hidden-thinking signature: the on arm reasoned SUBSTANTIALLY yet the off
    # arm burned an indistinguishable completion budget → invalid via factor (b).
    hidden = _pair(
        "hid1",
        LocateBucket.CORRECT,
        LocateBucket.EMPTY,
        reasoning_on=2000,
        tokens_on=1500,
        tokens_off=1490,
    )
    valid, reason = classify_pair_validity(hidden, cfg)
    assert not valid and reason == "factor-b-budget-indistinct"
    # Easy case: the on arm genuinely reasoned but only a little — the small
    # budget delta is legitimate and must NOT be invalidated (factor-b misfire
    # guard).
    easy = _pair(
        "easy1",
        LocateBucket.CORRECT,
        LocateBucket.CORRECT,
        reasoning_on=100,
        tokens_on=430,
        tokens_off=400,
    )
    valid, reason = classify_pair_validity(easy, cfg)
    assert valid and reason is None


def test_on_arm_no_reasoning_pair_kept_asymmetry():
    # An on arm with zero reasoning is LEGITIMATE shipped-None behavior — the
    # pair is KEPT; excluding it would bias the sample toward cases where
    # thinking fired. (Do not "fix" the guard into symmetry.)
    cfg = PREREGISTERED_AB_CONFIG_0039
    quiet = _pair(
        "q1",
        LocateBucket.CORRECT,
        LocateBucket.CORRECT,
        reasoning_on=0,
        tokens_on=400,
        tokens_off=400,
    )
    valid, reason = classify_pair_validity(quiet, cfg)
    assert valid and reason is None


def test_invalid_pair_rate_above_ceiling_yields_confounded():
    cfg = PREREGISTERED_AB_CONFIG_0039
    # 9 clean helping flips + 4 off-arm-reasoning defects: 4/13 ≈ 0.31 > 0.20
    # ceiling → CONFOUNDED, even though the clean flips would be significant.
    defects = [
        _pair(f"bad{i}", LocateBucket.CORRECT, LocateBucket.EMPTY, reasoning_off=500)
        for i in range(4)
    ]
    result = decide_ab_verdict(_helping_flips(9) + defects, cfg)
    assert result.verdict is AbVerdict.CONFOUNDED
    assert any("invalid-pair-rate" in r for r in result.confound_reasons)


def test_exclusions_never_silently_attrit_n():
    cfg = PREREGISTERED_AB_CONFIG_0039
    records = _helping_flips(9) + [
        _pair("deg1", None, LocateBucket.EMPTY, degrade_on="wall-clock"),
        _pair("bad1", LocateBucket.CORRECT, LocateBucket.EMPTY, reasoning_off=300),
    ]
    result = decide_ab_verdict(records, cfg)
    causes = dict(result.excluded)
    assert causes["deg1"] == "degrade:on:wall-clock"
    assert causes["bad1"] == "invalid:off-arm-reasoning-present"
    assert result.pairs_total == 11 and result.pairs_counted == 9


def test_mcnemar_reuses_benchmark_fit_exact_test():
    # Significance is the committed 0023 exact test, direction-split on (b, c).
    assert think_ab.mcnemar_rejects is benchmark_fit.mcnemar_rejects
    cfg = PREREGISTERED_AB_CONFIG_0039
    helps = decide_ab_verdict(_helping_flips(8), cfg)
    assert helps.verdict is AbVerdict.THINKING_HELPS
    assert helps.discordant_b == 8 and helps.discordant_c == 0
    hurts = decide_ab_verdict(_hurting_flips(8), cfg)
    assert hurts.verdict is AbVerdict.THINKING_HURTS
    assert hurts.discordant_b == 0 and hurts.discordant_c == 8
