"""Spec 0023 (AC3/AC4/AC5/AC6) — benchmark-fit verdict machinery: unit layer.

Pure, no live stack. Pins: the exact two-sided McNemar boundary (the numbers that
justify MIN_DISCORDANT_PAIRS=8), the frozen pre-registered config, the paired
aggregator computing deltas + discordant count FROM retained per-case pairs (not a
difference of aggregate rates), the total Axis-1 verdict with three named INCONCLUSIVE
triggers, the structured representativeness record, and the pre-registered 2×2
composition.
"""

from __future__ import annotations

import dataclasses

import pytest

from harpyja.eval.locate_accuracy import LocateBucket as LB

# ---- AC4: exact two-sided McNemar boundary ---------------------------------


def test_mcnemar_rejects_six_zero_at_alpha05():
    from harpyja.eval.benchmark_fit import mcnemar_exact_p, mcnemar_rejects

    assert mcnemar_exact_p(6, 0) == pytest.approx(0.03125)
    assert mcnemar_rejects(6, 0) is True


def test_mcnemar_does_not_reject_five_zero():
    from harpyja.eval.benchmark_fit import mcnemar_exact_p, mcnemar_rejects

    assert mcnemar_exact_p(5, 0) == pytest.approx(0.0625)
    assert mcnemar_rejects(5, 0) is False


def test_mcnemar_rejects_eight_zero():
    from harpyja.eval.benchmark_fit import mcnemar_exact_p, mcnemar_rejects

    assert mcnemar_exact_p(8, 0) == pytest.approx(0.0078125)
    assert mcnemar_rejects(8, 0) is True


def test_mcnemar_does_not_reject_seven_one():
    from harpyja.eval.benchmark_fit import mcnemar_exact_p, mcnemar_rejects

    assert mcnemar_exact_p(7, 1) == pytest.approx(0.0703125)
    assert mcnemar_rejects(7, 1) is False


def test_mcnemar_symmetric_in_arm_order():
    from harpyja.eval.benchmark_fit import mcnemar_exact_p

    assert mcnemar_exact_p(6, 0) == mcnemar_exact_p(0, 6)
    assert mcnemar_exact_p(7, 1) == mcnemar_exact_p(1, 7)
    # no discordant pairs → cannot reject (p clamped to 1.0).
    assert mcnemar_exact_p(0, 0) == 1.0


# ---- AC4/AC6: frozen pre-registered config ---------------------------------


def test_config_default_is_frozen_preregistered():
    from harpyja.eval.benchmark_fit import PREREGISTERED_CONFIG, BenchmarkFitConfig

    assert isinstance(PREREGISTERED_CONFIG, BenchmarkFitConfig)
    with pytest.raises(dataclasses.FrozenInstanceError):
        PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS = 3  # type: ignore[misc]


def test_config_min_discordant_pairs_is_eight():
    from harpyja.eval.benchmark_fit import PREREGISTERED_CONFIG

    assert PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS == 8


def test_config_delta_empty_band_is_twenty_hundredths():
    from harpyja.eval.benchmark_fit import PREREGISTERED_CONFIG

    assert PREREGISTERED_CONFIG.DELTA_EMPTY_BAND == pytest.approx(0.20)


def test_config_min_n_is_twelve():
    from harpyja.eval.benchmark_fit import PREREGISTERED_CONFIG

    assert PREREGISTERED_CONFIG.min_n == 12


# ---- AC3: paired aggregator from retained pairs ----------------------------


def _rows(pattern):
    """Build PairedRows from a list of (raw_bucket, distilled_bucket) tuples."""
    from harpyja.eval.benchmark_fit import PairedRow

    return [
        PairedRow(case_id=f"c-{i}", raw_bucket=r, distilled_bucket=d)
        for i, (r, d) in enumerate(pattern)
    ]


def test_paired_aggregate_delta_empty_from_pairs():
    from harpyja.eval.benchmark_fit import aggregate_paired

    # 3 improved (raw EMPTY → distilled CORRECT), 1 concordant-CORRECT, 1 concordant-EMPTY.
    rows = _rows(
        [(LB.EMPTY, LB.CORRECT)] * 3
        + [(LB.CORRECT, LB.CORRECT)]
        + [(LB.EMPTY, LB.EMPTY)]
    )
    agg = aggregate_paired(rows)
    # raw_empty=4, distilled_empty=1 → paired within-case delta = (4-1)/5.
    assert agg.delta_empty == pytest.approx(0.6)
    assert agg.n == 5


def test_paired_aggregate_delta_file_accuracy_from_pairs():
    from harpyja.eval.benchmark_fit import aggregate_paired

    rows = _rows(
        [(LB.EMPTY, LB.CORRECT)] * 3
        + [(LB.CORRECT, LB.CORRECT)]
        + [(LB.EMPTY, LB.EMPTY)]
    )
    agg = aggregate_paired(rows)
    # file-found = {CORRECT, RIGHT_FILE_WRONG_SPAN}. raw_file=1, distilled_file=4.
    assert agg.delta_file_accuracy == pytest.approx(0.6)


def test_paired_aggregate_discordant_count_from_pairs():
    from harpyja.eval.benchmark_fit import aggregate_paired

    # 3 improved (b), 2 worsened (c: raw not-empty → distilled EMPTY), 1 concordant.
    rows = _rows(
        [(LB.EMPTY, LB.CORRECT)] * 3
        + [(LB.CORRECT, LB.EMPTY)] * 2
        + [(LB.CORRECT, LB.CORRECT)]
    )
    agg = aggregate_paired(rows)
    assert agg.discordant_b == 3
    assert agg.discordant_c == 2
    assert agg.discordant_pairs == 5


# ---- AC4: total Axis-1 verdict + named INCONCLUSIVE triggers ---------------


def _agg_for(pattern):
    from harpyja.eval.benchmark_fit import aggregate_paired

    return aggregate_paired(_rows(pattern))


def test_decide_axis1_query_shape_when_delta_power_and_reject():
    from harpyja.eval.benchmark_fit import Axis1Verdict, decide_axis1

    # 8 improved (b=8, c=0) + 6 concordant-CORRECT → delta_empty≈0.57, McNemar 8/0 rejects.
    agg = _agg_for([(LB.EMPTY, LB.CORRECT)] * 8 + [(LB.CORRECT, LB.CORRECT)] * 6)
    verdict, reason = decide_axis1(agg, usable_n=14)
    assert verdict is Axis1Verdict.QUERY_SHAPE
    assert reason is None


def test_decide_axis1_capability_when_flat_and_power():
    from harpyja.eval.benchmark_fit import Axis1Verdict, decide_axis1

    # 4 improved + 4 worsened (discordant=8, delta_empty=0) + 6 concordant → flat, powered.
    agg = _agg_for(
        [(LB.EMPTY, LB.CORRECT)] * 4
        + [(LB.CORRECT, LB.EMPTY)] * 4
        + [(LB.CORRECT, LB.CORRECT)] * 6
    )
    verdict, reason = decide_axis1(agg, usable_n=14)
    assert verdict is Axis1Verdict.CAPABILITY
    assert reason is None


def test_decide_axis1_inconclusive_insufficient_power_low_discordant():
    from harpyja.eval.benchmark_fit import Axis1Verdict, InconclusiveReason, decide_axis1

    agg = _agg_for([(LB.EMPTY, LB.CORRECT)] * 2 + [(LB.CORRECT, LB.CORRECT)] * 10)
    verdict, reason = decide_axis1(agg, usable_n=12)
    assert verdict is Axis1Verdict.INCONCLUSIVE
    assert reason is InconclusiveReason.INSUFFICIENT_POWER


def test_decide_axis1_inconclusive_insufficient_power_low_usable_n():
    from harpyja.eval.benchmark_fit import Axis1Verdict, InconclusiveReason, decide_axis1

    agg = _agg_for([(LB.EMPTY, LB.CORRECT)] * 8)  # discordant=8 but usable_n small
    verdict, reason = decide_axis1(agg, usable_n=5)
    assert verdict is Axis1Verdict.INCONCLUSIVE
    assert reason is InconclusiveReason.INSUFFICIENT_POWER


def test_decide_axis1_inconclusive_insufficient_power_mcnemar_fails():
    from harpyja.eval.benchmark_fit import Axis1Verdict, InconclusiveReason, decide_axis1

    # 6 improved + 2 worsened (discordant=8, delta_empty=(6-2)/14≈0.29 ≥ band) but
    # McNemar 6/2 p≈0.289 does NOT reject → materially positive yet underpowered.
    agg = _agg_for(
        [(LB.EMPTY, LB.CORRECT)] * 6
        + [(LB.CORRECT, LB.EMPTY)] * 2
        + [(LB.CORRECT, LB.CORRECT)] * 6
    )
    verdict, reason = decide_axis1(agg, usable_n=14)
    assert verdict is Axis1Verdict.INCONCLUSIVE
    assert reason is InconclusiveReason.INSUFFICIENT_POWER


def test_decide_axis1_inconclusive_distiller_arm_disagreement():
    from harpyja.eval.benchmark_fit import Axis1Verdict, InconclusiveReason, decide_axis1

    # Powered, mechanical delta positive, but the LLM sensitivity arm moved the other way.
    agg = _agg_for([(LB.EMPTY, LB.CORRECT)] * 8 + [(LB.CORRECT, LB.CORRECT)] * 6)
    verdict, reason = decide_axis1(agg, usable_n=14, llm_delta_empty=-0.3)
    assert verdict is Axis1Verdict.INCONCLUSIVE
    assert reason is InconclusiveReason.DISTILLER_ARM_DISAGREEMENT


def test_decide_axis1_inconclusive_axis_signal_disagreement():
    from harpyja.eval.benchmark_fit import Axis1Verdict, InconclusiveReason, decide_axis1

    # delta_empty > 0 (distilling cuts empties) but delta_file_accuracy < 0 (distilling
    # loses the file): the two signals disagree.
    agg = _agg_for(
        [(LB.EMPTY, LB.WRONG_FILE)] * 8  # empties down, file not gained
        + [(LB.RIGHT_FILE_WRONG_SPAN, LB.WRONG_FILE)] * 6  # file lost, empty unchanged
    )
    assert agg.delta_empty > 0
    assert agg.delta_file_accuracy < 0
    verdict, reason = decide_axis1(agg, usable_n=14)
    assert verdict is Axis1Verdict.INCONCLUSIVE
    assert reason is InconclusiveReason.AXIS_SIGNAL_DISAGREEMENT


def test_decide_axis1_is_total_over_grid():
    from harpyja.eval.benchmark_fit import Axis1Verdict, decide_axis1

    patterns = [
        [],
        [(LB.EMPTY, LB.CORRECT)],
        [(LB.EMPTY, LB.CORRECT)] * 8 + [(LB.CORRECT, LB.CORRECT)] * 6,
        [(LB.CORRECT, LB.EMPTY)] * 4 + [(LB.EMPTY, LB.CORRECT)] * 4,
    ]
    for pattern in patterns:
        for usable_n in (0, 5, 12, 20):
            for llm in (None, -0.5, 0.5):
                verdict, reason = decide_axis1(
                    _agg_for(pattern), usable_n=usable_n, llm_delta_empty=llm
                )
                assert isinstance(verdict, Axis1Verdict)
                if verdict is Axis1Verdict.INCONCLUSIVE:
                    assert reason is not None
                else:
                    assert reason is None


# ---- AC5: structured representativeness record -----------------------------


def test_representativeness_record_is_structured():
    from harpyja.eval.benchmark_fit import RepresentativenessRecord

    rec = RepresentativenessRecord(
        query_shape="verbose-issue-prose",
        repo_type="documented-oss",
        documentation_density="high",
        codebase_age="modern",
        target_proxy_validity="strong",
    )
    for field in (
        "query_shape",
        "repo_type",
        "documentation_density",
        "codebase_age",
        "target_proxy_validity",
    ):
        assert hasattr(rec, field)


def test_representative_false_when_low_doc_and_weak_proxy():
    from harpyja.eval.benchmark_fit import RepresentativenessRecord, is_representative

    rec = RepresentativenessRecord(
        query_shape="verbose-issue-prose",
        repo_type="documented-oss",
        documentation_density="low",
        codebase_age="modern",
        target_proxy_validity="weak",
    )
    assert is_representative(rec) is False


def test_representative_true_when_only_documentation_low():
    from harpyja.eval.benchmark_fit import RepresentativenessRecord, is_representative

    rec = RepresentativenessRecord(
        query_shape="verbose-issue-prose",
        repo_type="documented-oss",
        documentation_density="low",
        codebase_age="modern",
        target_proxy_validity="strong",
    )
    assert is_representative(rec) is True


def test_representative_true_when_only_weak_proxy():
    from harpyja.eval.benchmark_fit import RepresentativenessRecord, is_representative

    rec = RepresentativenessRecord(
        query_shape="verbose-issue-prose",
        repo_type="documented-oss",
        documentation_density="high",
        codebase_age="modern",
        target_proxy_validity="weak",
    )
    assert is_representative(rec) is True


# ---- AC6: pre-registered 2×2 composition -----------------------------------


def test_compose_verdict_query_shape_representative_adds_layer():
    from harpyja.eval.benchmark_fit import (
        Axis1Verdict,
        NextSpec,
        compose_verdict,
    )

    v = compose_verdict(Axis1Verdict.QUERY_SHAPE, representative=True)
    assert v.next_spec is NextSpec.ADD_REFORMULATION_LAYER


def test_compose_verdict_query_shape_unrepresentative_builds_benchmark():
    from harpyja.eval.benchmark_fit import (
        Axis1Verdict,
        NextSpec,
        compose_verdict,
    )

    v = compose_verdict(Axis1Verdict.QUERY_SHAPE, representative=False)
    assert v.next_spec is NextSpec.BUILD_TERSE_QUERY_BENCHMARK


def test_compose_verdict_capability_representative_routes_n38():
    from harpyja.eval.benchmark_fit import (
        Axis1Verdict,
        NextSpec,
        compose_verdict,
    )

    v = compose_verdict(Axis1Verdict.CAPABILITY, representative=True)
    assert v.next_spec is NextSpec.N38_PLUS_FINDER_CAPABILITY


def test_compose_verdict_capability_unrepresentative_retires_swebench():
    from harpyja.eval.benchmark_fit import (
        Axis1Verdict,
        NextSpec,
        compose_verdict,
    )

    v = compose_verdict(Axis1Verdict.CAPABILITY, representative=False)
    assert v.next_spec is NextSpec.RETIRE_SWEBENCH


def test_compose_verdict_inconclusive_axis1_holds():
    from harpyja.eval.benchmark_fit import (
        Axis1Verdict,
        NextSpec,
        compose_verdict,
    )

    for rep in (True, False):
        v = compose_verdict(Axis1Verdict.INCONCLUSIVE, representative=rep)
        assert v.next_spec is NextSpec.HOLD_INCONCLUSIVE


def test_compose_verdict_is_total_over_axes():
    from harpyja.eval.benchmark_fit import (
        Axis1Verdict,
        BenchmarkFitVerdict,
        compose_verdict,
    )

    for axis1 in Axis1Verdict:
        for rep in (True, False):
            v = compose_verdict(axis1, representative=rep)
            assert isinstance(v, BenchmarkFitVerdict)
            assert v.axis1 is axis1
            assert v.representative is rep
