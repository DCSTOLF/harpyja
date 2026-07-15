"""Spec 0046 (AC5/AC6) — the two-arm gated re-measurement machinery.

Both arms run the FROZEN 33 cells (consumed from PREREGISTERED_REACTIVE_CONFIG_0046,
never re-selected) through ``run_gated_pool_pilot`` — the 0041 exclusive-endpoint
hard gate, proof ``0041/pilot/2`` in the ledger. The ONLY difference between the
arms is the ``explorer_reactive_confirm`` flag: BASELINE (off = pure 0044) vs NEW
(on = reactive-suppression + confirm partition).

Startup verifies the working-tree SUT hash against the COMMITTED config
(``expected_sut_hash``): a drifted SUT is a typed STOP before any cell runs.

``build_reactive_run_summary`` checks the BASELINE arm's aggregate NET (vs the
committed pre-nudge table, computed by the driver) against the frozen sanity band
— outside => BASELINE_DRIFT_STOP (a sanity check on SUT reproduction, NOT a
pass/fail gate on the new lever) — then measures the NEW arm head-to-head vs the
BASELINE arm through the total-pure five-sided verdict.

Mirror-not-share vs ``submission_run`` (spec 0044): that module is a frozen
historical pin; this is its 0046 two-arm sibling.
"""

from __future__ import annotations

import dataclasses
import json
import time
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from harpyja.eval.adoption_run import load_pinned_adoption_cases
from harpyja.eval.gate_run import run_gated_pool_pilot
from harpyja.eval.pool_pilot import (
    PoolPilotLedger,
    PoolRunError,
    _cell_needs_run,
    _evict_other_models,
)
from harpyja.eval.pool_precheck import PREREGISTERED_POOL_CONFIG_0040
from harpyja.eval.reactive_config import (
    PREREGISTERED_REACTIVE_CONFIG_0046,
    REACTIVE_CONFIG_HASH_0046,
    compute_sut_hash,
)
from harpyja.eval.reactive_outcome import ReactiveVerdict, decide_reactive_outcome

_API_BASE = "http://127.0.0.1:11434"
REACTIVE_RUN_SUMMARY_SCHEMA_VERSION = "0046/reactive-summary/1"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


class _ReactiveBudgetExhausted(Exception):
    pass


def reactive_arm_flag(arm: str) -> bool:
    """Map an arm name to the explorer_reactive_confirm flag (baseline off, new on)."""
    if arm not in ("baseline", "new"):
        raise PoolRunError(f"unknown arm {arm!r}; expected 'baseline' or 'new'")
    return arm == "new"


def reactive_coverage_models(include_optional: Sequence[str] = ()) -> tuple[str, ...]:
    cfg = PREREGISTERED_REACTIVE_CONFIG_0046
    unknown = [m for m in include_optional if m not in cfg.optional_models]
    if unknown:
        raise PoolRunError(
            f"models {unknown} are not in the frozen optional coverage "
            f"{list(cfg.optional_models)} — coverage is consumed from the frozen config"
        )
    included = set(include_optional)
    return cfg.required_models + tuple(m for m in cfg.optional_models if m in included)


def _live_verified_case_runner(
    *, arm: str, api_base: str, out_dir: Path
) -> Callable[[dict[str, Any], str], tuple[dict[str, Any], str | None]]:
    """The real per-cell runner: ``run_verified_case`` under the frozen knobs, with
    ``explorer_reactive_confirm`` set by the ARM (the ONLY deliberate delta)."""
    from harpyja.config.settings import Settings
    from harpyja.eval.live_verifier import run_verified_case
    from harpyja.gateway.gateway import ModelGateway

    cfg = PREREGISTERED_REACTIVE_CONFIG_0046
    flag = reactive_arm_flag(arm)
    worktrees = _repo_root() / "eval_work" / "worktrees"

    def runner(case: dict[str, Any], model: str) -> tuple[dict[str, Any], str | None]:
        settings = dataclasses.replace(
            Settings(),
            lm_api_base=f"{api_base}/v1",
            lm_model=model,
            explorer_think=cfg.explorer_think,
            explorer_reactive_confirm=flag,
            scout_max_turns=cfg.scout_max_turns,
            scout_wall_clock_s=cfg.scout_wall_clock_s,
            lm_http_timeout_s=cfg.lm_http_timeout_s,
        )
        gateway = ModelGateway(api_base=settings.lm_api_base, model=settings.lm_model)
        model_dir = out_dir / arm / model.replace(":", "_").replace(".", "_")
        _result, artifact_path = run_verified_case(
            case_name=case["case_id"], settings=settings, gateway=gateway,
            gold_span=case["gold"], out_dir=model_dir,
            repo_path=str(worktrees / case["case_id"]), query=case["query"],
        )
        artifact = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
        return artifact, str(artifact_path)

    return runner


def _cell_from_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "terminal_bucket": artifact.get("terminal_bucket"),
        "submission_outcome": artifact.get("submission_outcome"),
        "confidence_fired": artifact.get("confidence_fired"),
        "confirmation_outcome": artifact.get("confirmation_outcome"),
        "confirmation_ran": artifact.get("confirmation_ran"),
        "submit_disposition": artifact.get("submit_disposition"),
        "reactive_triggers_fired": artifact.get("reactive_triggers_fired"),
    }


def run_reactive_cells(
    *,
    arm: str,
    ledger_path: str | Path,
    artifact_dir: str | Path,
    include_optional: Sequence[str] = (),
    live: bool = False,
    budget_s: float | None = None,
    api_base: str = _API_BASE,
    verifier_out_dir: str | Path | None = None,
    verified_case_runner: Callable[
        [dict[str, Any], str], tuple[dict[str, Any], str | None]
    ] | None = None,
    ps_reader: Callable[[str], list[str]] | None = None,
    now: Callable[[], str] | None = None,
    resolver: Callable[[str], list[str]] | None = None,
    expected_sut_hash: str | None = None,
) -> dict[str, Any]:
    """Run ONE arm's cells through the 0041 gate. No parameter re-selects cases or
    models — pinned coverage is consumed from the frozen config."""
    if not live:
        raise PoolRunError(
            "run_reactive_cells is a live operator entrypoint — pass live=True from "
            "the committed driver (specs/0046-submission/reactive_run/run_reactive.py)"
        )
    flag = reactive_arm_flag(arm)
    if expected_sut_hash is not None:
        actual = compute_sut_hash()
        if actual != expected_sut_hash:
            raise PoolRunError(
                f"working-tree SUT hash {actual} != committed SUT hash "
                f"{expected_sut_hash} — the SUT drifted after the freeze; STOP "
                "(no cells ran), re-freeze or restore the surface"
            )
    models = reactive_coverage_models(include_optional)
    ledger_path = Path(ledger_path)
    artifact_dir = Path(artifact_dir)
    cases = load_pinned_adoption_cases()
    config_hash = f"{REACTIVE_CONFIG_HASH_0046}::{arm}"

    runner = verified_case_runner
    if runner is None:
        try:
            with urllib.request.urlopen(f"{api_base}/api/tags", timeout=10) as r:
                served = [m["name"] for m in json.loads(r.read())["models"]]
        except OSError as e:
            raise PoolRunError(
                f"live endpoint {api_base} unreachable ({e}) — STOP; no cells ran"
            ) from e
        missing = [m for m in models if m not in served]
        if missing:
            raise PoolRunError(f"frozen coverage models not served: {missing} — STOP")
        out_dir = (
            Path(verifier_out_dir)
            if verifier_out_dir is not None
            else _repo_root() / "eval_work" / "live_artifacts" / "reactive_0046"
        )
        runner = _live_verified_case_runner(arm=arm, api_base=api_base, out_dir=out_dir)

    started = time.monotonic()
    real_mode = verified_case_runner is None
    block_state: dict[str, str | None] = {"model": None}

    def run_cell(case: dict[str, Any], model: str) -> dict[str, Any]:
        if budget_s is not None and time.monotonic() - started > budget_s:
            raise _ReactiveBudgetExhausted()
        if real_mode and block_state["model"] != model:
            _evict_other_models(model, api_base=api_base)
            block_state["model"] = model
        try:
            artifact, artifact_path = runner(case, model)
        except ValueError as e:
            return {"terminal_bucket": None, "degrade": f"no-trajectory: {e}", "arm": arm}
        if artifact.get("verifier_status") != "PASSED":
            return {
                "terminal_bucket": None,
                "degrade": f"verifier:{artifact.get('failure_reason')}",
                "artifact": str(artifact_path) if artifact_path else None,
                "arm": arm,
            }
        cell = _cell_from_artifact(artifact)
        cell["degrade"] = None
        cell["artifact"] = str(artifact_path) if artifact_path else None
        cell["arm"] = arm
        return cell

    status = "completed"
    gate_result: dict[str, Any] = {}
    try:
        gate_result = run_gated_pool_pilot(
            PREREGISTERED_POOL_CONFIG_0040,
            ledger_path=ledger_path, pilot_models=list(models), cases=cases,
            run_cell=run_cell, api_base=api_base, ps_reader=ps_reader, now=now,
            resolver=resolver, config_hash=config_hash, live=True,
        )
    except _ReactiveBudgetExhausted:
        status = "in-progress"

    entries = json.loads(ledger_path.read_text(encoding="utf-8")).get("entries", {})
    remaining = [
        f"{case['case_id']}::{model}"
        for model in models for case in cases
        if _cell_needs_run(entries.get(f"{case['case_id']}::{model}"), clean_gate_since=True)
    ]
    return {
        "status": status, "arm": arm, "flag": flag, "config_hash": config_hash,
        "ledger_path": str(ledger_path), "models": list(models),
        "cells_remaining": remaining, "checks_recorded": gate_result.get("checks_recorded"),
    }


def _clean(cells: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        k: dict(v) for k, v in cells.items()
        if v.get("status") != "suspect" and v.get("degrade") is None
    }


def build_reactive_run_summary(
    *,
    baseline_cells: Mapping[str, Mapping[str, Any]] | None = None,
    new_cells: Mapping[str, Mapping[str, Any]] | None = None,
    baseline_net: int,
    baseline_ledger_path: str | Path | None = None,
    new_ledger_path: str | Path | None = None,
) -> dict[str, Any]:
    """The AC5/AC6 comparison: the BASELINE arm's NET vs the committed pre-nudge
    table (``baseline_net``, computed by the driver) is band-checked; then the NEW
    arm is measured head-to-head vs the BASELINE arm through the five-sided verdict.
    Cells may be passed directly (unit) or loaded from the two arm ledgers (live)."""
    cfg = PREREGISTERED_REACTIVE_CONFIG_0046
    if baseline_cells is None:
        baseline_cells = _load_ledger_cells(baseline_ledger_path, "baseline")
    if new_cells is None:
        new_cells = _load_ledger_cells(new_ledger_path, "new")
    base = _clean(baseline_cells)
    new = _clean(new_cells)

    lo, hi = cfg.baseline_band
    baseline_drift_stop = not (lo <= baseline_net <= hi)
    summary: dict[str, Any] = {
        "schema_version": REACTIVE_RUN_SUMMARY_SCHEMA_VERSION,
        "config_hash": REACTIVE_CONFIG_HASH_0046,
        "baseline_net": baseline_net,
        "baseline_band": list(cfg.baseline_band),
        "baseline_drift_stop": baseline_drift_stop,
        "covered_baseline_cells": sorted(base),
        "covered_new_cells": sorted(new),
    }
    if baseline_drift_stop:
        summary["verdict"] = "BASELINE_DRIFT_STOP"
        summary["residual"] = (
            f"baseline arm NET {baseline_net} outside the sanity band "
            f"{cfg.baseline_band} — the current SUT does not reproduce the 0044 "
            "operating point; STOP before typing the new-arm verdict"
        )
        return summary

    decision = decide_reactive_outcome(cfg, base, new)
    summary.update({
        "verdict": decision.verdict.value,
        "baseline_swc": decision.baseline_swc,
        "swc_new": decision.swc_new,
        "flagged_wrong_emitted_new": decision.flagged_wrong_emitted_new,
        "swc_plus_fwe_new": decision.swc_new + decision.flagged_wrong_emitted_new,
        "ceiling": decision.ceiling,
        "fu_baseline": decision.fu_baseline,
        "fu_new": decision.fu_new,
        "conversions": decision.conversions,
        "regressions": decision.regressions,
        "net": decision.net,
        "per_model": list(decision.per_model),
        "conditions_true": list(decision.conditions_true),
        "reopened": list(decision.reopened),
        "residual": decision.residual,
        "dissolves": decision.verdict is ReactiveVerdict.DISSOLVES_TRADE,
    })
    return summary


def _load_ledger_cells(ledger_path: str | Path | None, arm: str) -> dict[str, dict[str, Any]]:
    if ledger_path is None:
        raise PoolRunError(f"the {arm} arm needs cells or a ledger path")
    ledger = PoolPilotLedger(ledger_path, config_hash=f"{REACTIVE_CONFIG_HASH_0046}::{arm}")
    if ledger.exclusivity is None:
        raise PoolRunError(
            f"{arm} ledger lacks the 0041/pilot/2 exclusivity proof — not a valid measurement"
        )
    return {key: dict(cell) for key, cell in ledger.entries.items()}
