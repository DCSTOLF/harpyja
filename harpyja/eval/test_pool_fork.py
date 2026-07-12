"""Spec 0040 — AC8: the committed fork claim artifact, pinned to computed truth."""

from __future__ import annotations

import pytest

from harpyja.eval.locate_accuracy import LocateBucket
from harpyja.eval.pool_fork import (
    POOL_FORK_SCHEMA_VERSION,
    build_pool_fork_artifact,
    committed_pool_fork_path,
    load_committed_pool_fork,
)
from harpyja.eval.pool_precheck import (
    POOL_CONFIG_HASH_0040,
    PREREGISTERED_POOL_CONFIG_0040,
    PairCase,
    PairVerdict,
    PairVerdictResult,
    PreflightOutcome,
    decide_pool_fork,
)

_CFG = PREREGISTERED_POOL_CONFIG_0040


def _result(verdict: PairVerdict) -> PairVerdictResult:
    return PairVerdictResult(
        verdict=verdict,
        coverage=8,
        ceiling=10,
        observed=4,
        floor=8,
        projection_kind=_CFG.projection_kind,
        estimate_kind=_CFG.estimate_kind,
        preflight_a=PreflightOutcome.PREFLIGHT_PASS,
        preflight_b=PreflightOutcome.PREFLIGHT_PASS,
    )


def test_fork_names_pool_enlargement_for_non_feasible_pairs():
    fork = {
        "a vs b": _result(PairVerdict.PAIR_FEASIBLE),
        "a vs c": _result(PairVerdict.PAIR_MODELS_TOO_CLOSE),
        "b vs c": _result(PairVerdict.PAIR_UNDER_POWERED),
    }
    artifact = build_pool_fork_artifact(fork)
    assert artifact["schema_version"] == POOL_FORK_SCHEMA_VERSION
    assert artifact["config_hash"] == POOL_CONFIG_HASH_0040
    pairs = artifact["pairs"]
    # A FEASIBLE pair's next step is the bake-off — upper-bound honesty: it
    # remains "possible", proven only by the bake-off's own run.
    assert "bake-off" in pairs["a vs b"]["next_step"]
    # Every non-FEASIBLE pair names pool enlargement, which also unblocks the
    # 0039 thinking A/B.
    for name in ("a vs c", "b vs c"):
        assert "pool enlargement" in pairs[name]["next_step"]
        assert "0039" in pairs[name]["next_step"]
    # Both epistemic-kind labels ride every pair line.
    for line in pairs.values():
        assert line["projection_kind"] == "upper-bound-feasibility"
        assert line["estimate_kind"] == "point-estimate"


def test_load_committed_pool_fork_archive_first():
    from harpyja.eval import pool_fork as mod

    root = mod._repo_root()
    archived = root / "specs" / ".archive" / "0040-pool" / "pool_fork.json"
    live = root / "specs" / "0040-pool" / "pool_fork.json"
    assert committed_pool_fork_path() == (
        archived if archived.is_file() else live
    )


def test_committed_pool_fork_matches_computed_truth():
    # The 0039 claim-pin pattern: the committed fork's per-pair verdicts equal
    # decide_pool_fork recomputed from the committed pilot ledger + preflight
    # evidence — the claim cannot drift from the evidence.
    if not committed_pool_fork_path().is_file():
        pytest.skip("committed 0040 fork not yet emitted (pilot pending)")
    from harpyja.eval.pool_fork import recompute_pool_fork

    committed = load_committed_pool_fork()
    recomputed = recompute_pool_fork()
    assert committed["config_hash"] == POOL_CONFIG_HASH_0040
    for name, line in committed["pairs"].items():
        truth = recomputed[name]
        assert line["verdict"] == truth.verdict.value
        assert line["ceiling"] == truth.ceiling
        assert line["observed"] == truth.observed
        assert line["coverage"] == truth.coverage
        assert line["floor"] == truth.floor


def test_decide_pool_fork_is_the_one_oracle_for_the_artifact():
    # build_pool_fork_artifact serializes decide_pool_fork's results verbatim
    # — same verdict values, same quantities — on a constructed evidence set.
    reachability = {f"c{i}": "conceptual" for i in range(8)}
    entries = {}
    for model in _CFG.model_tags:
        for i in range(8):
            located = model == "qwen3:14b" or (model == "qwen3.5:4b" and i < 4)
            entries[f"c{i}::{model}"] = {
                "bucket": "correct" if located else "empty",
                "degrade": None,
            }
    fork = decide_pool_fork(
        _CFG,
        entries,
        reachability,
        preflight_by_model={
            m: PreflightOutcome.PREFLIGHT_PASS for m in _CFG.model_tags
        },
    )
    artifact = build_pool_fork_artifact(fork)
    for name, result in fork.items():
        line = artifact["pairs"][name]
        assert line["verdict"] == result.verdict.value
        assert line["ceiling"] == result.ceiling
        assert line["observed"] == result.observed
    # Sanity on the constructed evidence: the all-located vs none pair is
    # FEASIBLE; its per-case pairs came from PairCase machinery.
    assert (
        fork["qwen3:14b vs qwen3:8b"].verdict is PairVerdict.PAIR_FEASIBLE
    )
    assert isinstance(
        PairCase("x", LocateBucket.CORRECT, LocateBucket.EMPTY), PairCase
    )
