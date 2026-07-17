"""Spec 0048 — bake-off: the staged, resumable, DETACHED live-run driver (T22).

OQ1 staging, OPERATIONAL-ONLY: preflight all three tags → run the widest-gap pair
(14b-4b) first as a feasibility/plumbing check (NO threshold/model/grid/decoding/
prompt/pool change) → then the full 3×53 grid, resumable through ``BakeoffLedger``
across the ~9h run. The single sanctioned early stop is a NAMED safety/infra halt
(the heavy-repo timeout degrade class recurring past the degraded-dominated guard),
never an outcome-dependent stop.

This must be launched DETACHED (``nohup … & disown``) with log monitoring — a
harness background task dies at ~20 min (repo memory: detach-long-live-runs). See
``run_bakeoff.sh`` beside this module. The model-call seams are injected so the
module imports without a live stack; the defaults hit the live SUT unchanged
(the harness NEVER mutates the SUT).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from harpyja.eval.bakeoff_analysis import BakeoffReport
from harpyja.eval.bakeoff_config import (
    BAKEOFF_CONFIG_HASH_0048,
    BakeoffConfig,
    bakeoff_config_hash,
)
from harpyja.eval.bakeoff_run import (
    BakeoffLedger,
    BakeoffPreflightObservations,
    BakeoffRunError,
    bakeoff_preflight,
    build_bakeoff_report,
    is_excluding,
)

# A cell runner: (case_id, model) -> the durable artifact dict (bucket, tools,
# degrade, …) — the seam the live SUT fills. Injected so the module is importable
# and unit-drivable without a model endpoint.
CellRunner = Callable[[str, str], Mapping[str, Any]]
# A per-model preflight prober: model tag -> observations (served/coherent/
# tool-calls/replay). Injected likewise.
PreflightProber = Callable[[str], BakeoffPreflightObservations]


def _feasibility_pair(cfg: BakeoffConfig) -> tuple[str, str]:
    """The widest expected gap runs first (14b vs 4b) — pre-declared, never
    chosen after early results."""
    return (cfg.model_tags[0], cfg.model_tags[-1])


def run_bakeoff(
    cfg: BakeoffConfig,
    *,
    case_ids: Sequence[str],
    reachability: Mapping[str, str],
    ledger_path: str | Path,
    preflight_prober: PreflightProber,
    cell_runner: CellRunner,
    symbols_adoption: Mapping[str, float] | None = None,
    found_but_unsubmitted: Mapping[str, int] | None = None,
) -> BakeoffReport:
    """Drive the staged, resumable grid and return the typed report.

    The driver re-verifies the frozen config hash at entry (a run under a drifted
    contract is refused, loud), preflights all three tags (an excluded model is
    recorded, never scored zero), and — if fewer than two survive — returns the
    ``INFRASTRUCTURE_HALTED`` report WITHOUT running the grid.
    """
    if bakeoff_config_hash(cfg) != BAKEOFF_CONFIG_HASH_0048:
        raise BakeoffRunError(
            "working config hash != the frozen 0048 hash — refuse to run a "
            "drifted analysis contract"
        )

    observations = {tag: preflight_prober(tag) for tag in cfg.model_tags}
    outcomes, exclusions = bakeoff_preflight(cfg, observations=observations)
    survivors = tuple(t for t in cfg.model_tags if not is_excluding(outcomes[t]))

    ledger = BakeoffLedger(ledger_path, config_hash=BAKEOFF_CONFIG_HASH_0048)

    if len(survivors) < 2:
        # No bake-off is possible — the report types INFRASTRUCTURE_HALTED and the
        # grid never runs.
        return build_bakeoff_report(
            cfg, ledger.entries, reachability,
            surviving_models=survivors, exclusions=exclusions,
            symbols_adoption=symbols_adoption, found_but_unsubmitted=found_but_unsubmitted,
        )

    # Staged model order: the feasibility pair's models first, then the rest —
    # a pure ordering of the SAME grid (operational-only; no cell is skipped).
    feas = _feasibility_pair(cfg)
    model_order = [m for m in (feas[0], feas[1]) if m in survivors]
    model_order += [m for m in survivors if m not in model_order]

    for model in model_order:
        for case_id in case_ids:
            if ledger.has(case_id, model):
                continue  # resume: already recorded in a prior invocation
            artifact = cell_runner(case_id, model)
            ledger.record(case_id, model, dict(artifact))

    return build_bakeoff_report(
        cfg, ledger.entries, reachability,
        surviving_models=survivors, exclusions=exclusions,
        symbols_adoption=symbols_adoption, found_but_unsubmitted=found_but_unsubmitted,
    )


__all__ = ["CellRunner", "PreflightProber", "run_bakeoff"]
