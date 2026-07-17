"""Spec 0049 (AC5/AC6) — the K-draw replay proof + typed outcome (unit).

The bucket taxonomy is REUSED BY IDENTITY from ``locate_accuracy.LocateBucket``
(no oracle change); this module adds only the ≥3-draw orchestration, per-cell
reproduce/flip verdicts across all three greedy tags, the global typed outcome,
and the drift-pinned artifact schema. Pure: draws are pre-classified buckets.
"""

from __future__ import annotations

import pytest

from harpyja.eval.bakeoff_config import BakeoffConfig
from harpyja.eval.exclusivity_gate import build_exclusivity_record
from harpyja.eval.greedy_replay import (
    GREEDY_REPLAY_ARTIFACT_KEYS,
    GreedyServingOutcome,
    ReplayCell,
    build_greedy_replay_artifact,
    greedy_replay_proof,
)
from harpyja.eval.locate_accuracy import LocateBucket

_CFG = BakeoffConfig()
E = LocateBucket.EMPTY
C = LocateBucket.CORRECT
R = LocateBucket.RIGHT_FILE_WRONG_SPAN


def _cell(tag, case_id, draws, repo="astropy"):
    return ReplayCell(tag=tag, case_id=case_id, repo=repo, draws=tuple(draws))


def test_greedy_replay_proof_requires_at_least_three_draws_per_cell():
    cells = [_cell("qwen3-14b-greedy", "astropy-12907", [E, E])]  # only 2 draws
    with pytest.raises(ValueError):
        greedy_replay_proof(cells)


def test_greedy_replay_proof_cell_reproduces_when_all_draws_identical_bucket():
    cells = [_cell("qwen3-14b-greedy", "astropy-12907", [R, R, R])]
    result = greedy_replay_proof(cells)
    assert result["cells"][0]["verdict"] == "reproduce"


def test_greedy_replay_proof_cell_flips_on_within_cell_bucket_divergence():
    cells = [_cell("qwen3-14b-greedy", "astropy-12907", [E, R, E])]
    result = greedy_replay_proof(cells)
    assert result["cells"][0]["verdict"] == "flip"
    # The offender is NAMED (tag + case).
    assert ("qwen3-14b-greedy", "astropy-12907") in result["flips"]


def test_greedy_replay_proof_keys_on_bucket_not_tool_path():
    # 0048 saw 9-vs-6 tool paths within the SAME empty bucket — the proof sees only
    # buckets, so identical buckets reproduce regardless of trajectory length.
    cells = [_cell("qwen3-14b-greedy", "pytest-5495", [E, E, E])]
    assert greedy_replay_proof(cells)["cells"][0]["verdict"] == "reproduce"


def test_greedy_replay_proof_reuses_locate_bucket_taxonomy_by_identity():
    # A draw that is not a LocateBucket is rejected — the taxonomy is the oracle.
    cells = [_cell("qwen3-14b-greedy", "astropy-12907", ["empty", "empty", "empty"])]
    with pytest.raises(TypeError):
        greedy_replay_proof(cells)


def test_greedy_serving_outcome_reproducible_requires_every_cell():
    cells = [
        _cell("qwen3-14b-greedy", "astropy-12907", [R, R, R]),
        _cell("qwen3-8b-greedy", "astropy-12907", [E, E, E]),
        _cell("qwen3.5-4b-greedy", "pytest-5495", [C, C, C], repo="pytest"),
    ]
    result = greedy_replay_proof(cells)
    assert result["outcome"] is GreedyServingOutcome.GREEDY_REPRODUCIBLE
    assert result["flips"] == []


def test_greedy_serving_outcome_any_flip_forces_residual_nondeterminism():
    # Two tags reproduce; ONE cell flips → global RESIDUAL_NONDETERMINISM (no
    # per-tag cherry-pick of a reproducible subset), naming the offender.
    cells = [
        _cell("qwen3-14b-greedy", "astropy-12907", [R, R, R]),
        _cell("qwen3-8b-greedy", "pytest-5495", [E, C, E], repo="pytest"),
        _cell("qwen3.5-4b-greedy", "pytest-5495", [C, C, C], repo="pytest"),
    ]
    result = greedy_replay_proof(cells)
    assert result["outcome"] is GreedyServingOutcome.RESIDUAL_NONDETERMINISM
    assert result["flips"] == [("qwen3-8b-greedy", "pytest-5495")]


def _valid_exclusivity():
    return build_exclusivity_record(
        checks=[{"timestamp": "2026-07-17T00:00:00Z", "clean": True}],
        model_set=["qwen3-14b-greedy"],
    )


def test_greedy_replay_artifact_schema_carries_committed_fingerprint_and_exclusivity():
    art = build_greedy_replay_artifact(
        _CFG,
        tag="qwen3-14b-greedy",
        case_id="astropy-12907",
        repo="astropy",
        buckets=[R, R, R],
        verdict="reproduce",
        exclusivity_record=_valid_exclusivity(),
    )
    # Chain of custody: the committed fingerprint is embedded from the config.
    assert art["committed_fingerprint"] == dict(_CFG.served_variant_fingerprints)[
        "qwen3-14b-greedy"
    ]
    assert art["buckets"] == ["right-file-wrong-span"] * 3
    assert art["exclusivity"]["exclusivity_check_kind"] == "start-plus-per-block"


def test_greedy_replay_artifact_is_drift_pinned():
    art = build_greedy_replay_artifact(
        _CFG,
        tag="qwen3-8b-greedy",
        case_id="pytest-5495",
        repo="pytest",
        buckets=[E, E, E],
        verdict="reproduce",
        exclusivity_record=_valid_exclusivity(),
    )
    assert set(art) == set(GREEDY_REPLAY_ARTIFACT_KEYS)
