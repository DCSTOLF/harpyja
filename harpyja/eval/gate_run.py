"""Spec 0041 — the gated pilot-run driver (AC1, AC2) + reload-churn attribution (AC8).

``run_gated_pool_pilot`` wraps a pilot loop in the exclusive-endpoint gate:
one check BEFORE the run and one BEFORE EACH model block, every check recorded
into the ledger's ``0041/exclusivity/1`` proof (persisted at ``0041/pilot/2``).
A failed check is the typed stop ``exclusive-endpoint-contended`` — refuse,
don't warn; there is NO bypass/force parameter (asserted by signature
introspection, the 0039 ``run_ab_paired`` precedent); the only sanctioned
unblock is changing the environment.

Boundary discipline (AC2, outcome-blind): a failed per-block re-check stops
BEFORE that block and types every cell recorded since the last clean check as
``suspect`` — original observations retained (invalidated, never erased), at
boundary granularity, never per-suspicious-cell. Suspect cells become
re-runnable only after a subsequent clean gate check (the third
``_cell_needs_run`` branch).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from harpyja.eval.exclusivity_gate import (
    ExclusiveEndpointContended,
    build_exclusivity_record,
    check_exclusive_endpoint,
)
from harpyja.eval.pool_pilot import (
    PoolPilotLedger,
    PoolRunError,
    _cell_needs_run,
)
from harpyja.eval.pool_precheck import (
    POOL_CONFIG_HASH_0040,
    PREREGISTERED_POOL_CONFIG_0040,
    PoolConfig,
)

__all__ = ["attribute_reload_churn", "run_gated_pool_pilot"]

_API_BASE = "http://127.0.0.1:11434"


def run_gated_pool_pilot(
    cfg: PoolConfig = PREREGISTERED_POOL_CONFIG_0040,
    *,
    ledger_path: str | Path,
    pilot_models: Sequence[str],
    cases: Sequence[dict[str, Any]],
    run_cell: Callable[[dict[str, Any], str], dict[str, Any]],
    api_base: str = _API_BASE,
    ps_reader: Callable[[str], list[str]] | None = None,
    now: Callable[[], str] | None = None,
    resolver: Callable[[str], list[str]] | None = None,
    config_hash: str = POOL_CONFIG_HASH_0040,
    live: bool = False,
) -> dict[str, Any]:
    """Gate-wrapped pilot loop. ``live=False`` refuses loudly (the 0040
    posture — the committed operator driver is the only ``live=True`` caller).
    The foreign predicate runs against the FROZEN ``cfg.model_tags``."""
    if not live:
        raise PoolRunError(
            "run_gated_pool_pilot is a live operator entrypoint — pass "
            "live=True from the committed driver (specs/0041-gates/gate/run_gate.py)"
        )
    ledger_path = Path(ledger_path)
    checks: list[dict[str, Any]] = []

    def _record(exclusivity_ledger: PoolPilotLedger | None) -> PoolPilotLedger:
        record = build_exclusivity_record(
            checks=checks, model_set=cfg.model_tags
        )
        if exclusivity_ledger is None:
            return PoolPilotLedger(
                ledger_path, config_hash=config_hash, exclusivity=record
            )
        exclusivity_ledger.set_exclusivity(record)
        return exclusivity_ledger

    def _gate(label: str, ledger: PoolPilotLedger | None) -> PoolPilotLedger:
        try:
            checks.append(
                check_exclusive_endpoint(
                    api_base,
                    cfg.model_tags,
                    label=label,
                    ps_reader=ps_reader,
                    resolver=resolver,
                    now=now,
                )
            )
        except ExclusiveEndpointContended as exc:
            checks.append(exc.as_failed_check())
            _record(ledger)
            raise
        return _record(ledger)

    ledger = _gate("start", None)

    cells_since_clean: list[tuple[str, str]] = []
    for model in pilot_models:
        try:
            ledger = _gate(f"pre-block:{model}", ledger)
        except ExclusiveEndpointContended:
            # Contamination boundary: everything since the last clean check is
            # suspect — outcome-blind, observations retained, never erased.
            for case_id, m in cells_since_clean:
                cell = ledger.get(case_id, m)
                if cell is not None:
                    ledger.record(
                        case_id, m, {**cell, "status": "suspect"}
                    )
            raise
        # A clean gate check just passed — suspect cells become re-runnable.
        cells_since_clean = []
        for case in cases:
            prior = ledger.get(case["case_id"], model)
            if not _cell_needs_run(prior, clean_gate_since=True):
                continue
            entry = run_cell(case, model)
            ledger.record(case["case_id"], model, entry)
            cells_since_clean.append((case["case_id"], model))

    return {
        "status": "completed",
        "config_hash": config_hash,
        "ledger_path": str(ledger_path),
        "checks_recorded": len(checks),
    }


def clean_0040_degrade_profile() -> dict[str, str]:
    """The AC8 comparison basis: per-cell typed degrades of THE committed 0040
    CLEAN pilot run (run-2), archive-first per the evidence-path convention.
    Never the archived ``pilot_results.run1-contaminated.json``."""
    import json

    root = Path(__file__).resolve().parents[2]
    archived = (
        root / "specs" / ".archive" / "0040-pool" / "pilot" / "pilot_results.json"
    )
    live = root / "specs" / "0040-pool" / "pilot" / "pilot_results.json"
    path = archived if archived.is_file() else live
    if not path.is_file():
        raise PoolRunError(f"committed 0040 clean pilot ledger not found: {path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    return {
        cell: entry["degrade"]
        for cell, entry in obj["entries"].items()
        if entry.get("degrade")
    }


def attribute_reload_churn(
    this_run_degrades: dict[str, str],
    clean_0040_profile: dict[str, str],
    reload_markers: set[str] | frozenset[str],
) -> dict[str, str]:
    """AC8's operationalized attribution — never a close-time judgment call.

    A cell's typed degrade counts as reload-churn-attributable ONLY when BOTH:
    it is NEW relative to the committed 0040 clean-run degrade profile on the
    shared pinned cases, AND an observed-reload marker (an ``expires_at``
    reset since the previous cell) was recorded for it. A degrade already in
    the clean profile is a standing constraint, not churn; a new degrade
    without a marker is unattributed (typed, reported, never assumed)."""
    return {
        cell: degrade
        for cell, degrade in this_run_degrades.items()
        if cell not in clean_0040_profile and cell in reload_markers
    }
