"""spec 0036 — pure pilot aggregation glue (AC4/AC5 degrade posture).

Maps per-case, per-arm outcomes to signal-bearing `PilotPair`s and applies the
`decide_ac8` gate under the 0036 pre-registered config. A typed environment
degrade on EITHER arm excludes the case from the pairs (it is not a capability
observation) and records it BY CAUSE — never counted clean, never silent.
Pure, no live I/O.
"""

from __future__ import annotations

from harpyja.eval.ac8_pilot import (
    AC8_CONFIG_HASH_0036,
    PREREGISTERED_AC8_CONFIG_0036,
    Ac8Outcome,
)
from harpyja.eval.locate_accuracy import LocateBucket
from harpyja.eval.pilot_runner import (
    PilotCaseOutcome,
    build_pilot_pairs,
    gate_report,
)


def _clean(cid: str, a: LocateBucket, b: LocateBucket) -> PilotCaseOutcome:
    return PilotCaseOutcome(case_id=cid, bucket_a=a, bucket_b=b)


def test_pilot_runner_builds_pairs_and_decides_under_0036_config():
    # 10 clean cases, 3 signal flips → projected 9 ≥ 8 → PROCEED; the report cites
    # the 0036 config hash (the freeze the artifact must reference).
    outcomes = [
        _clean("c0", LocateBucket.CORRECT, LocateBucket.EMPTY),  # signal
        _clean("c1", LocateBucket.RIGHT_FILE_WRONG_SPAN, LocateBucket.WRONG_FILE),  # signal
        _clean("c2", LocateBucket.EMPTY, LocateBucket.CORRECT),  # signal
        _clean("c3", LocateBucket.EMPTY, LocateBucket.WRONG_FILE),  # noise flip
        _clean("c4", LocateBucket.CORRECT, LocateBucket.CORRECT),  # concordant
        _clean("c5", LocateBucket.EMPTY, LocateBucket.EMPTY),
        _clean("c6", LocateBucket.WRONG_FILE, LocateBucket.WRONG_FILE),
        _clean("c7", LocateBucket.EMPTY, LocateBucket.EMPTY),
        _clean("c8", LocateBucket.WRONG_FILE, LocateBucket.EMPTY),  # noise flip
        _clean("c9", LocateBucket.EMPTY, LocateBucket.EMPTY),
    ]
    pairs, excluded = build_pilot_pairs(outcomes)
    assert len(pairs) == 10 and excluded == {}
    report = gate_report(outcomes)
    assert report["outcome"] is Ac8Outcome.PROCEED
    assert report["config_hash"] == AC8_CONFIG_HASH_0036
    assert report["pairs_run"] == 10
    assert report["signal_discordant"] == 3
    assert report["excluded"] == {}


def test_pilot_runner_excludes_and_records_degrades():
    # A typed degrade on either arm excludes the case (recorded by cause) — it is
    # NOT a pair, NOT counted clean, and the gate runs on the remaining pairs only.
    outcomes = [
        _clean("c0", LocateBucket.CORRECT, LocateBucket.EMPTY),  # signal
        PilotCaseOutcome(
            case_id="c1",
            bucket_a=None,
            bucket_b=LocateBucket.EMPTY,
            degrade_a="model-unreachable",
        ),
        PilotCaseOutcome(
            case_id="c2",
            bucket_a=LocateBucket.CORRECT,
            bucket_b=None,
            degrade_b="scout-unavailable",
        ),
        _clean("c3", LocateBucket.EMPTY, LocateBucket.EMPTY),
    ]
    pairs, excluded = build_pilot_pairs(outcomes)
    assert [p.case_id for p in pairs] == ["c0", "c3"]
    assert excluded == {
        "c1": "arm_a: model-unreachable",
        "c2": "arm_b: scout-unavailable",
    }
    report = gate_report(outcomes)
    assert report["pairs_run"] == 2
    assert report["excluded"] == excluded
    # 1 signal / 2 pairs → projected 15 ≥ 8 under the frozen thresholds → PROCEED —
    # but the exclusions stay visible in the report, never silently absorbed.
    assert report["outcome"] is Ac8Outcome.PROCEED
    assert report["config"] == PREREGISTERED_AC8_CONFIG_0036


def test_pilot_runner_degraded_case_requires_cause():
    # A missing bucket with NO recorded cause is a contract violation — the runner
    # raises loudly rather than fabricating an exclusion reason.
    import pytest

    bad = PilotCaseOutcome(case_id="c0", bucket_a=None, bucket_b=LocateBucket.EMPTY)
    with pytest.raises(ValueError):
        build_pilot_pairs([bad])
