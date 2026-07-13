"""Spec 0045 — the gated live re-measurement + four-sided summary (AC5, T20).

Mirrors the 0044 submission runner (mirror-not-share for the FROZEN verdict/config;
the generic cell + ledger machinery is reused BY IMPORT from ``submission_run``).
``run_refinement_cells`` refuses without ``live=True`` and STOPs on either a
SUT-hash OR a config-hash drift (the dual-hash gate) — coverage is consumed from
the frozen config, never re-selected; the ledger is keyed by
``REFINEMENT_CONFIG_HASH_0045``. ``build_refinement_run_summary`` joins the
config-pinned BEFORE baseline with the AFTER ledger into the FOUR-SIDED ledger
(conversions / regressions / s->wc / fu) + NET per model, head-to-head vs 0044,
and the total-pure ``decide_refinement_outcome`` verdict.
"""

from __future__ import annotations

import json
import time
import urllib.request
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from harpyja.eval.adoption_run import load_pinned_adoption_cases
from harpyja.eval.gate_run import run_gated_pool_pilot
from harpyja.eval.pool_pilot import (
    PoolPilotLedger,
    PoolRunError,
    _evict_other_models,
)
from harpyja.eval.pool_precheck import PREREGISTERED_POOL_CONFIG_0040
from harpyja.eval.refinement_config import (
    PREREGISTERED_REFINEMENT_CONFIG_0045,
    REFINEMENT_CONFIG_HASH_0045,
    compute_sut_hash,
)
from harpyja.eval.refinement_outcome import decide_refinement_outcome
from harpyja.eval.submission_run import (
    _live_verified_case_runner,
    _write_submission_artifact,
    build_submission_cell_artifact,
    load_baseline_cells,
)

REFINEMENT_RUN_SUMMARY_SCHEMA_VERSION = "0045/refinement-summary/1"
# WITHOUT /v1 — the /api/tags preflight uses this base; the reused
# _live_verified_case_runner appends /v1 for the OpenAI-compatible endpoint.
_API_BASE = "http://127.0.0.1:11434"

_CFG = PREREGISTERED_REFINEMENT_CONFIG_0045


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


class _RefinementBudgetExhausted(Exception):
    pass


def refinement_coverage_models(
    include_optional: Sequence[str] = (),
) -> tuple[str, ...]:
    """Coverage consumed from the frozen 0045 config; ``include_optional`` can
    only ENABLE tags already frozen as optional — never a new one."""
    unknown = [m for m in include_optional if m not in _CFG.optional_models]
    if unknown:
        raise PoolRunError(
            f"models {unknown} are not in the frozen optional coverage "
            f"{list(_CFG.optional_models)} — coverage is consumed from "
            "PREREGISTERED_REFINEMENT_CONFIG_0045, never re-selected"
        )
    included = set(include_optional)
    return _CFG.required_models + tuple(
        m for m in _CFG.optional_models if m in included
    )


def run_refinement_cells(
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
    expected_sut_hash: str | None = None,
    expected_config_hash: str | None = None,
) -> dict[str, Any]:
    """The gated 0045 re-measurement loop. The DUAL-HASH gate STOPs on either a
    SUT-hash OR a config-hash drift after the stage-2 freeze."""
    if not live:
        raise PoolRunError(
            "run_refinement_cells is a live operator entrypoint — pass "
            "live=True from the committed driver "
            "(specs/0045-refinement/refinement_run/run_refinement.py)"
        )
    if expected_sut_hash is not None:
        actual = compute_sut_hash()
        if actual != expected_sut_hash:
            raise PoolRunError(
                f"working-tree SUT hash {actual} != committed SUT hash "
                f"{expected_sut_hash} — the SUT drifted after the stage-2 "
                "freeze; STOP (no cells ran)"
            )
    if expected_config_hash is not None and (
        expected_config_hash != REFINEMENT_CONFIG_HASH_0045
    ):
        raise PoolRunError(
            f"committed config hash {expected_config_hash} != in-code "
            f"{REFINEMENT_CONFIG_HASH_0045} — the frozen config drifted; STOP "
            "(no cells ran)"
        )

    models = refinement_coverage_models(include_optional)
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
            else _repo_root() / "eval_work" / "live_artifacts" / "refinement_0045"
        )
        runner = _live_verified_case_runner(api_base=api_base, out_dir=out_dir)

    started = time.monotonic()
    real_mode = verified_case_runner is None
    block_state: dict[str, str | None] = {"model": None}

    def run_cell(case: dict[str, Any], model: str) -> dict[str, Any]:
        if budget_s is not None and time.monotonic() - started > budget_s:
            raise _RefinementBudgetExhausted()
        if real_mode and block_state["model"] != model:
            _evict_other_models(model, api_base=api_base)
            block_state["model"] = model
        try:
            artifact, artifact_path = runner(case, model)
        except ValueError as e:
            return {"bucket": None, "degrade": f"no-trajectory: {e}",
                    "artifact": None, "confidence_fired": None,
                    "silence_to_wrong_confidence": None}
        if artifact.get("verifier_status") != "PASSED":
            return {"bucket": None, "degrade": f"verifier:{artifact.get('failure_reason')}",
                    "artifact": str(artifact_path) if artifact_path else None,
                    "confidence_fired": None, "silence_to_wrong_confidence": None}
        cell = build_submission_cell_artifact(
            case_id=case["case_id"], model=model, verifier_artifact=artifact,
            verifier_artifact_path=artifact_path, ledger_path=ledger_path,
        )
        # Spec 0045: carry the s->wc fact from the verifier artifact.
        cell["silence_to_wrong_confidence"] = artifact.get(
            "silence_to_wrong_confidence"
        )
        cell["unfired_silence_to_wrong_confidence"] = artifact.get(
            "unfired_silence_to_wrong_confidence"
        )
        out_path = _write_submission_artifact(
            artifact_dir, case["case_id"], model, cell
        )
        return {
            "bucket": cell["terminal_bucket"], "degrade": None,
            "artifact": str(out_path),
            "verifier_artifact": cell["verifier_artifact"],
            "submission_outcome": cell["submission_outcome"],
            "confidence_fired": cell["confidence_fired"],
            "confidence_null": cell["confidence_null"],
            "silence_to_wrong_confidence": cell["silence_to_wrong_confidence"],
            "unfired_silence_to_wrong_confidence": cell[
                "unfired_silence_to_wrong_confidence"
            ],
        }

    status = "completed"
    gate_result: dict[str, Any] = {}
    try:
        gate_result = run_gated_pool_pilot(
            PREREGISTERED_POOL_CONFIG_0040,
            ledger_path=ledger_path, pilot_models=list(models), cases=cases,
            run_cell=run_cell, api_base=api_base, ps_reader=ps_reader, now=now,
            resolver=resolver, config_hash=REFINEMENT_CONFIG_HASH_0045, live=True,
        )
    except _RefinementBudgetExhausted:
        status = "in-progress"

    return {
        "status": status,
        "config_hash": REFINEMENT_CONFIG_HASH_0045,
        "ledger_path": str(ledger_path),
        "models": list(models),
        "checks_recorded": gate_result.get("checks_recorded"),
    }


def build_refinement_run_summary(
    ledger_path: str | Path,
    baseline_table_path: str | Path | None = None,
) -> dict[str, Any]:
    """AC5: BEFORE (config-pinned committed baseline) vs AFTER (this ledger;
    suspect + degraded cells excluded), IDENTICAL detector, the FOUR-SIDED
    ledger per model + head-to-head vs 0044, and the total-pure verdict."""
    ledger = PoolPilotLedger(ledger_path, config_hash=REFINEMENT_CONFIG_HASH_0045)
    if ledger.exclusivity is None:
        raise PoolRunError(
            "refinement ledger lacks the 0041/pilot/2 exclusivity proof — not "
            "a valid measurement"
        )
    before = load_baseline_cells(baseline_table_path)
    after = {
        key: {
            "bucket": cell.get("bucket"),
            "submission_outcome": cell.get("submission_outcome"),
            "confidence_fired": cell.get("confidence_fired"),
            "silence_to_wrong_confidence": cell.get("silence_to_wrong_confidence"),
        }
        for key, cell in ledger.entries.items()
        if cell.get("status") != "suspect" and cell.get("degrade") is None
    }
    named_cells = {
        key: cell.get("bucket")
        for key, cell in after.items()
    }
    decision = decide_refinement_outcome(_CFG, before, after, named_cells)
    net_0044 = sum(v for _m, v in _CFG.comparator_net_by_model)
    return {
        "schema_version": REFINEMENT_RUN_SUMMARY_SCHEMA_VERSION,
        "config_hash": REFINEMENT_CONFIG_HASH_0045,
        "ledger": str(Path(ledger_path)),
        "verdict": decision.verdict.name,
        "conditions_true": list(decision.conditions_true),
        "reopened_direction": decision.reopened_direction,
        "residual": decision.residual,
        "failed_conjunct": decision.failed_conjunct,
        "ledger_four_sided": {
            "per_model": list(decision.per_model),
            "conversions": decision.conversions,
            "regressions": decision.regressions,
            "aggregate_net": decision.aggregate_net,
            "swc_total": decision.swc_total,
            "unfired_swc_total": decision.unfired_swc_total,
            "fu_total": decision.fu_total,
            "covered_joined": decision.covered_joined,
        },
        "head_to_head": {
            "comparator_net": net_0044,
            "net_delta_vs_0044": decision.head_to_head_net_delta,
            "comparator_swc": _CFG.comparator_swc_total,
            "comparator_fu": _CFG.comparator_fu_after,
        },
    }
