"""Spec 0040 — AC8: the committed fork claim artifact (loader + emitter).

The fork is the spec's product: per pair, PAIR_FEASIBLE (the bake-off may run
on it now) vs UNDER_POWERED / TOO_CLOSE / INSUFFICIENT / MODEL_EXCLUDED (pool
enlargement — which also unblocks the 0039 thinking A/B). The committed
``pool_fork.json`` is test-pinned to ``decide_pool_fork``'s computed truth
over the committed pilot ledger + preflight result (the 0039 claim-pin
pattern): the claim cannot exist without the recorded evidence backing it.

No live bake-off compute is spent here; a FEASIBLE verdict is upper-bound
honesty — "possible to clear the floor", proven only by the bake-off's own run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harpyja.eval.pool_precheck import (
    POOL_CONFIG_HASH_0040,
    PREREGISTERED_POOL_CONFIG_0040,
    PairVerdict,
    PairVerdictResult,
    PoolConfig,
    PreflightOutcome,
    decide_pool_fork,
)

POOL_FORK_SCHEMA_VERSION = "0040/fork/1"

_BAKEOFF_NEXT_STEP = (
    "PAIR_FEASIBLE: the bake-off may run on this pair now — feasibility is an "
    "upper bound, proven only by the bake-off's own powered run"
)

_ENLARGEMENT_NEXT_STEP = (
    "pool enlargement — the named 0036 audited convert step (which also "
    "unblocks the 0039 thinking A/B re-check)"
)


class PoolForkError(ValueError):
    """A fork artifact that does not conform — loud, never defaulted."""


def build_pool_fork_artifact(
    fork: dict[str, PairVerdictResult]
) -> dict[str, Any]:
    """Serialize decide_pool_fork's results VERBATIM — same verdicts, same
    quantities, both epistemic-kind labels — plus the typed next step."""
    pairs: dict[str, Any] = {}
    for name, result in fork.items():
        pairs[name] = {
            "verdict": result.verdict.value,
            "coverage": result.coverage,
            "ceiling": result.ceiling,
            "observed": result.observed,
            "floor": result.floor,
            "projection_kind": result.projection_kind,
            "estimate_kind": result.estimate_kind,
            "preflight_a": result.preflight_a.value,
            "preflight_b": result.preflight_b.value,
            "next_step": (
                _BAKEOFF_NEXT_STEP
                if result.verdict is PairVerdict.PAIR_FEASIBLE
                else _ENLARGEMENT_NEXT_STEP
            ),
        }
    return {
        "schema_version": POOL_FORK_SCHEMA_VERSION,
        "config_hash": POOL_CONFIG_HASH_0040,
        "pairs": pairs,
    }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def committed_pool_fork_path() -> Path:
    """THE committed 0040 fork — archive-first (the 79f7bf2 convention)."""
    root = _repo_root()
    archived = root / "specs" / ".archive" / "0040-pool" / "pool_fork.json"
    live = root / "specs" / "0040-pool" / "pool_fork.json"
    return archived if archived.is_file() else live


def load_committed_pool_fork() -> dict[str, Any]:
    path = committed_pool_fork_path()
    if not path.is_file():
        raise PoolForkError(f"committed 0040 fork not found: {path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("schema_version") != POOL_FORK_SCHEMA_VERSION:
        raise PoolForkError(
            f"unknown pool-fork schema_version: {obj.get('schema_version')!r}"
        )
    if not isinstance(obj.get("pairs"), dict):
        raise PoolForkError("fork artifact missing 'pairs'")
    return obj


def _committed_pilot_ledger_path() -> Path:
    root = _repo_root()
    archived = (
        root / "specs" / ".archive" / "0040-pool" / "pilot" / "pilot_results.json"
    )
    live = root / "specs" / "0040-pool" / "pilot" / "pilot_results.json"
    return archived if archived.is_file() else live


def recompute_pool_fork(
    cfg: PoolConfig = PREREGISTERED_POOL_CONFIG_0040,
) -> dict[str, PairVerdictResult]:
    """The computed truth: decide_pool_fork over the COMMITTED pilot ledger +
    preflight result — what the committed artifact is pinned against."""
    from harpyja.eval.pool_preflight_result import (
        load_committed_pool_preflight_result,
    )
    from harpyja.eval.think_ab_precheck import load_fixture_reachability

    ledger_path = _committed_pilot_ledger_path()
    if not ledger_path.is_file():
        raise PoolForkError(f"committed 0040 pilot ledger not found: {ledger_path}")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    if ledger.get("config_hash") != POOL_CONFIG_HASH_0040:
        raise PoolForkError("pilot ledger cites a different frozen config hash")
    preflight = load_committed_pool_preflight_result()
    preflight_by_model = {
        tag: PreflightOutcome(record["outcome"])
        for tag, record in preflight["models"].items()
    }
    reachability = load_fixture_reachability()
    return decide_pool_fork(
        cfg,
        ledger["entries"],
        reachability,
        preflight_by_model=preflight_by_model,
    )


def emit_pool_fork(out_path: str | Path | None = None) -> Path:
    """Emit the committed fork from the committed evidence (the operator's
    thin emit step, run once the pilot ledger is complete)."""
    fork = recompute_pool_fork()
    artifact = build_pool_fork_artifact(fork)
    path = (
        Path(out_path)
        if out_path is not None
        else _repo_root() / "specs" / "0040-pool" / "pool_fork.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path
