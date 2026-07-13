"""Spec 0043 — the gated diagnosis re-measurement machinery (AC5).

Re-measures the FROZEN 0042 pilot cells (consumed from
``PREREGISTERED_DIAGNOSIS_CONFIG_0043``, never re-selected) through
``run_gated_pool_pilot`` — the 0041 exclusive-endpoint hard gate, proof
``0041/pilot/2`` in the ledger, keyed by ``DIAGNOSIS_CONFIG_HASH_0043`` —
under the T13 lever (the submit-early prompt nudge; the ONLY deliberate SUT
delta vs the 0042 run, same 10-turn/240s/300s knobs from the frozen config).

Per clean cell the ledger records the ``submission_outcome`` fact from the
trajectory-VERIFIED artifact (the 0043/1 schema field — computed by
``run_verified_case`` via the ONE detector). ``build_diagnosis_run_summary``
joins the AFTER ledger against the BEFORE covered subset — the committed T9
attribution table, which is exactly the set of 0042 cells whose full
trajectory survived in machine-local ``eval_work`` — using the IDENTICAL
detector version on both sides, and returns the total pure AC6 verdict with
per-side ``detector-inconclusive`` counts and bidirectional net movement.
"""

from __future__ import annotations

import dataclasses
import json
import time
import urllib.request
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from harpyja.eval.adoption_run import load_pinned_adoption_cases
from harpyja.eval.diagnosis_config import (
    DIAGNOSIS_CONFIG_HASH_0043,
    PREREGISTERED_DIAGNOSIS_CONFIG_0043,
)
from harpyja.eval.diagnosis_outcome import decide_diagnosis_outcome
from harpyja.eval.gate_run import run_gated_pool_pilot
from harpyja.eval.live_verifier import extract_tool_names
from harpyja.eval.pool_pilot import (
    POOL_PILOT_LEDGER_SCHEMA_VERSION_0041,
    PoolPilotLedger,
    PoolRunError,
    _cell_needs_run,
    _evict_other_models,
)
from harpyja.eval.pool_precheck import PREREGISTERED_POOL_CONFIG_0040
from harpyja.eval.submission_gap import DETECTOR_VERSION

_API_BASE = "http://127.0.0.1:11434"

DIAGNOSIS_CELL_ARTIFACT_SCHEMA_VERSION = "0043/diagnosis-cell/1"
DIAGNOSIS_RUN_SUMMARY_SCHEMA_VERSION = "0043/diagnosis-summary/1"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


_DEFAULT_ATTRIBUTION = (
    "specs/0043-diagnosis/attribution/attribution_table.json",
    "specs/.archive/0043-diagnosis/attribution/attribution_table.json",
)


class _DiagnosisBudgetExhausted(Exception):
    pass


def diagnosis_coverage_models(include_optional: Sequence[str] = ()) -> tuple[str, ...]:
    """Coverage consumed from the frozen config; ``include_optional`` can only
    ENABLE tags already frozen as optional — never introduce new ones."""
    cfg = PREREGISTERED_DIAGNOSIS_CONFIG_0043
    unknown = [m for m in include_optional if m not in cfg.optional_models]
    if unknown:
        raise PoolRunError(
            f"models {unknown} are not in the frozen optional coverage "
            f"{list(cfg.optional_models)} — coverage is consumed from "
            "PREREGISTERED_DIAGNOSIS_CONFIG_0043, never re-selected"
        )
    included = set(include_optional)
    return cfg.required_models + tuple(
        m for m in cfg.optional_models if m in included
    )


def load_before_cells(
    attribution_table_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    """The BEFORE covered subset: the committed T9 attribution table's
    adoption_0042 rows — exactly the cells whose full trajectory survived in
    ``eval_work`` (BEFORE is computable ONLY for these; the caller NAMES the
    subset in the artifact, never silently narrows)."""
    if attribution_table_path is None:
        root = _repo_root()
        for rel in _DEFAULT_ATTRIBUTION:
            if (root / rel).is_file():
                attribution_table_path = root / rel
                break
        else:
            raise PoolRunError(
                "committed attribution table not found — the BEFORE side of "
                "the comparison is the T9 committed evidence"
            )
    table = json.loads(Path(attribution_table_path).read_text(encoding="utf-8"))
    if table.get("detector_version") != DETECTOR_VERSION:
        raise PoolRunError(
            "attribution table detector_version "
            f"{table.get('detector_version')!r} != {DETECTOR_VERSION!r} — the "
            "BEFORE/AFTER comparison requires the IDENTICAL detector"
        )
    return {
        f"{row['case']}::{row['model']}": {
            "bucket": row.get("bucket"),
            "submission_outcome": row.get("submission_outcome"),
        }
        for row in table.get("cases", [])
        if row.get("run") == "adoption_0042"
    }


def build_diagnosis_cell_artifact(
    *,
    case_id: str,
    model: str,
    verifier_artifact: dict[str, Any],
    verifier_artifact_path: str | Path | None,
    ledger_path: str | Path,
) -> dict[str, Any]:
    """The per-cell durable artifact, built ONLY from a verifier-PASSED
    trajectory, carrying the 0043 loss-class fact as data."""
    if verifier_artifact.get("verifier_status") != "PASSED":
        raise PoolRunError(
            "diagnosis cell artifacts are built only from verifier-PASSED "
            "trajectories — a failed verification is a typed degrade in the "
            "ledger, never an artifact"
        )
    turns = verifier_artifact.get("model_turns") or []
    tool_names, _proven, _failure = extract_tool_names({"model_turns": turns})
    return {
        "schema_version": DIAGNOSIS_CELL_ARTIFACT_SCHEMA_VERSION,
        "case_id": case_id,
        "model": model,
        "requested_model": verifier_artifact.get("requested_model"),
        "served_model": verifier_artifact.get("served_model"),
        "endpoint": verifier_artifact.get("endpoint"),
        "verifier_status": "PASSED",
        "verifier_schema_version": verifier_artifact.get("schema_version"),
        "verifier_artifact": (
            str(verifier_artifact_path) if verifier_artifact_path else None
        ),
        "tool_names_invoked": tool_names,
        "terminal_bucket": verifier_artifact.get("terminal_bucket"),
        "citations_submitted": verifier_artifact.get("citations_submitted"),
        "citations_surviving": verifier_artifact.get("citations_surviving"),
        # The 0043 loss-class fact, from the verified trajectory's own field.
        "submission_outcome": verifier_artifact.get("submission_outcome"),
        "detector_version": verifier_artifact.get("detector_version"),
        "exclusivity_proof_ref": {
            "ledger": str(ledger_path),
            "ledger_schema_version": POOL_PILOT_LEDGER_SCHEMA_VERSION_0041,
            "config_hash": DIAGNOSIS_CONFIG_HASH_0043,
        },
    }


def _write_diagnosis_artifact(
    artifact_dir: Path, case_id: str, model: str, artifact: dict[str, Any]
) -> Path:
    slug = model.replace(":", "_").replace(".", "_")
    path = artifact_dir / f"{case_id}__{slug}.diagnosis.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    tmp.replace(path)
    return path


def _live_verified_case_runner(
    *, api_base: str, out_dir: Path
) -> Callable[[dict[str, Any], str], tuple[dict[str, Any], str | None]]:
    """The real per-cell runner: ``run_verified_case`` under the frozen run
    knobs — the T13 lever (prompt) is the only deliberate SUT delta vs 0042."""
    from harpyja.config.settings import Settings
    from harpyja.eval.live_verifier import run_verified_case
    from harpyja.gateway.gateway import ModelGateway

    cfg = PREREGISTERED_DIAGNOSIS_CONFIG_0043
    worktrees = _repo_root() / "eval_work" / "worktrees"

    def runner(case: dict[str, Any], model: str) -> tuple[dict[str, Any], str | None]:
        settings = dataclasses.replace(
            Settings(),
            lm_api_base=f"{api_base}/v1",
            lm_model=model,
            explorer_think=cfg.explorer_think,
            scout_max_turns=cfg.scout_max_turns,
            scout_wall_clock_s=cfg.scout_wall_clock_s,
            lm_http_timeout_s=cfg.lm_http_timeout_s,
        )
        gateway = ModelGateway(api_base=settings.lm_api_base, model=settings.lm_model)
        model_dir = out_dir / model.replace(":", "_").replace(".", "_")
        _result, artifact_path = run_verified_case(
            case_name=case["case_id"],
            settings=settings,
            gateway=gateway,
            gold_span=case["gold"],
            out_dir=model_dir,
            repo_path=str(worktrees / case["case_id"]),
            query=case["query"],
        )
        artifact = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
        return artifact, str(artifact_path)

    return runner


def run_diagnosis_cells(
    *,
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
) -> dict[str, Any]:
    """The gated diagnosis re-measurement loop. No parameter re-selects cases
    or models — pinned coverage is consumed from the frozen config."""
    if not live:
        raise PoolRunError(
            "run_diagnosis_cells is a live operator entrypoint — pass live=True "
            "from the committed driver "
            "(specs/0043-diagnosis/diagnosis_run/run_diagnosis.py)"
        )
    models = diagnosis_coverage_models(include_optional)
    ledger_path = Path(ledger_path)
    artifact_dir = Path(artifact_dir)
    cases = load_pinned_adoption_cases()

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
            raise PoolRunError(
                f"frozen coverage models not served: {missing} — STOP; no cells ran"
            )
        out_dir = (
            Path(verifier_out_dir)
            if verifier_out_dir is not None
            else _repo_root() / "eval_work" / "live_artifacts" / "diagnosis_0043"
        )
        runner = _live_verified_case_runner(api_base=api_base, out_dir=out_dir)

    attempts_map: dict[str, int] = {}
    if ledger_path.is_file():
        prior_entries = json.loads(ledger_path.read_text(encoding="utf-8")).get(
            "entries", {}
        )
        attempts_map = {
            key: int(cell.get("attempts") or 1)
            for key, cell in prior_entries.items()
        }

    started = time.monotonic()
    real_mode = verified_case_runner is None
    block_state: dict[str, str | None] = {"model": None}

    def run_cell(case: dict[str, Any], model: str) -> dict[str, Any]:
        if budget_s is not None and time.monotonic() - started > budget_s:
            raise _DiagnosisBudgetExhausted()
        if real_mode and block_state["model"] != model:
            _evict_other_models(model, api_base=api_base)
            block_state["model"] = model
        key = f"{case['case_id']}::{model}"
        attempts = attempts_map.get(key, 0) + 1
        attempts_map[key] = attempts
        try:
            artifact, artifact_path = runner(case, model)
        except ValueError as e:
            return {
                "bucket": None,
                "degrade": f"no-trajectory: {e}",
                "artifact": None,
                "attempts": attempts,
                "submission_outcome": None,
            }
        if artifact.get("verifier_status") != "PASSED":
            return {
                "bucket": None,
                "degrade": f"verifier:{artifact.get('failure_reason')}",
                "artifact": str(artifact_path) if artifact_path else None,
                "attempts": attempts,
                "submission_outcome": None,
            }
        cell_artifact = build_diagnosis_cell_artifact(
            case_id=case["case_id"],
            model=model,
            verifier_artifact=artifact,
            verifier_artifact_path=artifact_path,
            ledger_path=ledger_path,
        )
        out_path = _write_diagnosis_artifact(
            artifact_dir, case["case_id"], model, cell_artifact
        )
        return {
            "bucket": cell_artifact["terminal_bucket"],
            "degrade": None,
            "artifact": str(out_path),
            "verifier_artifact": cell_artifact["verifier_artifact"],
            "attempts": attempts,
            "submission_outcome": cell_artifact["submission_outcome"],
            "detector_version": cell_artifact["detector_version"],
            "citations_submitted": cell_artifact["citations_submitted"],
            "citations_surviving": cell_artifact["citations_surviving"],
        }

    status = "completed"
    gate_result: dict[str, Any] = {}
    try:
        gate_result = run_gated_pool_pilot(
            PREREGISTERED_POOL_CONFIG_0040,
            ledger_path=ledger_path,
            pilot_models=list(models),
            cases=cases,
            run_cell=run_cell,
            api_base=api_base,
            ps_reader=ps_reader,
            now=now,
            resolver=resolver,
            config_hash=DIAGNOSIS_CONFIG_HASH_0043,
            live=True,
        )
    except _DiagnosisBudgetExhausted:
        status = "in-progress"
    # ExclusiveEndpointContended propagates — the typed stop belongs to the
    # driver (exit 2); the refusal proof is already in the ledger.

    entries = json.loads(ledger_path.read_text(encoding="utf-8")).get("entries", {})
    remaining = [
        f"{case['case_id']}::{model}"
        for model in models
        for case in cases
        if _cell_needs_run(
            entries.get(f"{case['case_id']}::{model}"), clean_gate_since=True
        )
    ]
    return {
        "status": status,
        "config_hash": DIAGNOSIS_CONFIG_HASH_0043,
        "ledger_path": str(ledger_path),
        "models": list(models),
        "cells_remaining": remaining,
        "checks_recorded": gate_result.get("checks_recorded"),
    }


def build_diagnosis_run_summary(
    ledger_path: str | Path,
    attribution_table_path: str | Path | None = None,
) -> dict[str, Any]:
    """The AC5 machine-readable comparison: BEFORE (committed covered subset)
    vs AFTER (this ledger), IDENTICAL detector both sides, per-side
    inconclusive counts, bidirectional net movement, and the total pure AC6
    verdict as data. Suspect cells are excluded from the join."""
    cfg = PREREGISTERED_DIAGNOSIS_CONFIG_0043
    ledger = PoolPilotLedger(ledger_path, config_hash=DIAGNOSIS_CONFIG_HASH_0043)
    if ledger.exclusivity is None:
        raise PoolRunError(
            "diagnosis ledger lacks the 0041/pilot/2 exclusivity proof — not a "
            "valid measurement"
        )
    before = load_before_cells(attribution_table_path)
    after = {
        key: {
            "bucket": cell.get("bucket"),
            "submission_outcome": cell.get("submission_outcome"),
        }
        for key, cell in ledger.entries.items()
        if cell.get("status") != "suspect" and cell.get("degrade") is None
    }
    outcome = decide_diagnosis_outcome(cfg, before, after)
    return {
        "schema_version": DIAGNOSIS_RUN_SUMMARY_SCHEMA_VERSION,
        "config_hash": DIAGNOSIS_CONFIG_HASH_0043,
        "ledger": str(Path(ledger_path)),
        "detector_version": DETECTOR_VERSION,
        # The covered BEFORE subset is NAMED — BEFORE is computable only for
        # cells whose full trajectory survived in eval_work.
        "covered_before_cells": sorted(before),
        "covered_before": outcome.covered_before,
        "found_unsubmitted_before": outcome.fu_before,
        "found_unsubmitted_after": outcome.fu_after,
        "inconclusive_before": outcome.inconclusive_before,
        "inconclusive_after": outcome.inconclusive_after,
        "conversions": outcome.conversions,
        "regressions": outcome.regressions,
        "net": outcome.net,
        "caveats": list(outcome.caveats),
        "residual": outcome.residual,
        "verdict": outcome.verdict.value,
    }
