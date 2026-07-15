"""RED (0046 T13/T14, AC4b/c/d): the five-sided reactive accounting.

Every per-cell outcome lands in exactly ONE counted side; no error direction is
left uncounted. ``s->wc`` and ``flagged-wrong-emitted`` PARTITION the
fired-wrong-submitted mass by confirmation outcome, so their SUM is conserved
(the de-attribution guard). The flag-rate diagnostic and the record-only
``unfired_confirm_found_but_unsubmitted`` cross-check ride BESIDE the counted
sides, never in the verdict.
"""

from __future__ import annotations

import itertools

from harpyja.eval.reactive_observability import (
    REACTIVE_SIDES,
    classify_reactive_side,
    flag_rate,
    reactive_side_of,
    unfired_confirm_found_but_unsubmitted,
)

# --- grid-totality of the truth-table classifier ------------------------------


def test_every_input_tuple_maps_to_exactly_one_side():
    for correct, has_candidate, swc_eligible, confirmation, gold in itertools.product(
        [True, False], [True, False], [True, False],
        [None, "PASS", "FAIL", "CONFIRM_ERROR"], [True, False],
    ):
        side = classify_reactive_side(
            correct=correct, has_candidate=has_candidate,
            swc_eligible=swc_eligible, confirmation=confirmation,
            gold_in_tool_result=gold,
        )
        assert side in REACTIVE_SIDES


def test_correct_is_located_regardless_of_flag():
    # A flagged-but-correct citation is still located (flag rides the diagnostic
    # axis only; it never becomes a regression).
    assert classify_reactive_side(
        correct=True, has_candidate=True, swc_eligible=False,
        confirmation="FAIL", gold_in_tool_result=False) == "located"


def test_eligible_wrong_pass_is_swc():
    assert classify_reactive_side(
        correct=False, has_candidate=True, swc_eligible=True,
        confirmation="PASS", gold_in_tool_result=False) == "s->wc"


def test_eligible_wrong_fail_is_flagged_wrong_emitted():
    for conf in ("FAIL", "CONFIRM_ERROR"):
        assert classify_reactive_side(
            correct=False, has_candidate=True, swc_eligible=True,
            confirmation=conf, gold_in_tool_result=False) == "flagged-wrong-emitted"


def test_not_eligible_wrong_fail_is_regression_or_miss_not_flagged_wrong():
    # The partition BOUNDARY: a NOT-eligible wrong span that FAILs confirmation
    # is counted by CORRECTNESS as regression/miss — its flag is diagnostic
    # only, NEVER flagged-wrong-emitted (which is s->wc-eligible-wrong by def).
    assert classify_reactive_side(
        correct=False, has_candidate=True, swc_eligible=False,
        confirmation="FAIL", gold_in_tool_result=False) == "regression-or-miss"


def test_no_candidate_splits_fu_vs_honest_empty_by_gold():
    assert classify_reactive_side(
        correct=False, has_candidate=False, swc_eligible=False,
        confirmation=None, gold_in_tool_result=True) == "fu"
    assert classify_reactive_side(
        correct=False, has_candidate=False, swc_eligible=False,
        confirmation=None, gold_in_tool_result=False) == "honest-empty"


# --- per-trajectory adapter ---------------------------------------------------


def _traj(bucket, *, fired=False, confirmation=None, submission="never-found",
          confirmation_ran=False):
    return {
        "terminal_bucket": bucket,
        "confidence_fired": fired,
        "confirmation_outcome": confirmation,
        "confirmation_ran": confirmation_ran,
        "submission_outcome": submission,
    }


def test_reactive_side_of_swc_and_flagged_partition_the_wrong_fired_mass():
    swc = _traj("wrong-file", fired=True, confirmation="PASS", confirmation_ran=True)
    fwe = _traj("wrong-file", fired=True, confirmation="FAIL", confirmation_ran=True)
    assert reactive_side_of(swc, []) == "s->wc"
    assert reactive_side_of(fwe, []) == "flagged-wrong-emitted"


def test_reactive_side_of_correct_is_located():
    assert reactive_side_of(_traj("correct", fired=True, confirmation="PASS"), []) == "located"


def test_reactive_side_of_found_unsubmitted_is_fu():
    t = _traj("no-citation", submission="found-unsubmitted")
    assert reactive_side_of(t, []) == "fu"


# --- flag-rate diagnostic + unfired confirm fu cross-check --------------------


def test_flag_rate_is_flagged_fraction_of_confirmed_cells():
    cells = [
        _traj("correct", confirmation="PASS", confirmation_ran=True),
        _traj("wrong-file", fired=True, confirmation="FAIL", confirmation_ran=True),
        _traj("wrong-file", fired=True, confirmation="CONFIRM_ERROR", confirmation_ran=True),
        _traj("no-citation", confirmation=None, confirmation_ran=False),  # not counted
    ]
    # 2 flagged of 3 confirmed = 2/3
    assert flag_rate(cells) == 2 / 3


def test_unfired_confirm_found_but_unsubmitted_counts_only_unfired_confirm():
    cells = [
        _traj("no-citation", submission="found-unsubmitted", confirmation_ran=False),  # counted
        _traj("no-citation", submission="found-unsubmitted", confirmation_ran=True),   # confirm ran
        _traj("wrong-file", submission="submitted", confirmation_ran=False),           # not fu
    ]
    assert unfired_confirm_found_but_unsubmitted(cells) == 1


def test_accounting_reuses_span_hit_kind_by_identity():
    import harpyja.eval.metrics as metrics
    import harpyja.eval.reactive_observability as ro

    assert ro.span_hit_kind is metrics.span_hit_kind
