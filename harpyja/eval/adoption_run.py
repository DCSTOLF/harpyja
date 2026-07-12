"""Spec 0042 — the gated adoption re-measurement machinery (AC6).

``run_adoption_cells`` re-measures symbols adoption on the COMMITTED 0040
pinned pilot case set (consumed from ``PREREGISTERED_ADOPTION_CONFIG_0042``,
never re-selected) through ``run_gated_pool_pilot`` — the 0041 exclusive-
endpoint gate (start + per-block checks, no bypass), with the ``0041/pilot/2``
exclusivity proof riding a resumable ``PoolPilotLedger`` keyed by
``ADOPTION_CONFIG_HASH_0042``.

Postures inherited by identity (never re-derived):

- ``live=False`` refuses loudly — the committed driver
  (``specs/0042-adoption/adoption_run/run_adoption.py``) is the only
  ``live=True`` caller (the 0040 ``run_pool_pilot`` posture).
- Resume via ``_cell_needs_run``: clean cells NEVER re-run (re-running a
  clean observation because its outcome looks wrong would be post-hoc
  steering); typed degrades get ONE bounded re-run; suspect cells re-run only
  after a subsequent clean gate check.
- Model coverage is pinned pre-run: ``required_models`` are mandatory,
  ``optional_models`` recorded-if-run — "wall-clock allows" can never shrink
  the measurement below required, and no unpinned tag can enter.

Per clean cell the machinery emits a trajectory-VERIFIED adoption artifact
(``build_adoption_cell_artifact``): built ONLY from a verifier-PASSED
``run_verified_case`` artifact (the verifier seam, never self-reported),
carrying requested + served model identity, the tools invoked INCLUDING the
per-case ``symbols`` invocation count (derived from the trajectory's
tool_calls), the terminal bucket, the citation counts, and the run's
exclusivity-proof reference.
"""

from __future__ import annotations

import dataclasses
import json
import time
import urllib.request
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from harpyja.eval.adoption_precheck import (
    ADOPTION_CONFIG_HASH_0042,
    PREREGISTERED_ADOPTION_CONFIG_0042,
    build_adoption_cells,
    decide_adoption_outcome,
    load_committed_0040_pilot_ledger,
)
from harpyja.eval.gate_run import run_gated_pool_pilot
from harpyja.eval.live_verifier import extract_tool_names
from harpyja.eval.pool_pilot import (
    POOL_PILOT_LEDGER_SCHEMA_VERSION_0041,
    PoolPilotLedger,
    PoolRunError,
    _cell_needs_run,
    _evict_other_models,
    pool_pilot_preflight,
)
from harpyja.eval.pool_precheck import PREREGISTERED_POOL_CONFIG_0040

__all__ = [
    "ADOPTION_CELL_ARTIFACT_SCHEMA_VERSION",
    "ADOPTION_RUN_SUMMARY_SCHEMA_VERSION",
    "adoption_coverage_models",
    "build_adoption_cell_artifact",
    "build_adoption_run_summary",
    "load_pinned_adoption_cases",
    "run_adoption_cells",
]

_API_BASE = "http://127.0.0.1:11434"

ADOPTION_CELL_ARTIFACT_SCHEMA_VERSION = "0042/adoption-cell/1"
ADOPTION_RUN_SUMMARY_SCHEMA_VERSION = "0042/adoption-run-summary/1"


class _AdoptionBudgetExhausted(Exception):
    """Internal typed budget stop — the run resumes on the next invocation."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def adoption_coverage_models(
    include_optional: Sequence[str] = (),
) -> tuple[str, ...]:
    """The run's model coverage, CONSUMED from the frozen 0042 config:
    required models always; optional models only when explicitly included —
    and only from the frozen optional tuple, never a free-form tag."""
    cfg = PREREGISTERED_ADOPTION_CONFIG_0042
    unknown = [m for m in include_optional if m not in cfg.optional_models]
    if unknown:
        raise PoolRunError(
            f"models {unknown} are not in the frozen optional coverage "
            f"{list(cfg.optional_models)} — coverage is consumed from "
            "PREREGISTERED_ADOPTION_CONFIG_0042, never re-selected"
        )
    included = set(include_optional)
    return cfg.required_models + tuple(
        m for m in cfg.optional_models if m in included
    )


def load_pinned_adoption_cases(root: Path | None = None) -> list[dict[str, Any]]:
    """The committed 0040 pinned pilot cases (query + gold span), in the
    frozen ``pilot_case_ids`` order — consumed from the fixtures the 0040
    pilot ran on, never re-selected."""
    cfg = PREREGISTERED_ADOPTION_CONFIG_0042
    fixtures = (root or _repo_root()) / "harpyja" / "eval" / "fixtures"
    raw_index: dict[str, dict[str, Any]] = {}
    for line in (fixtures / "swebench_verified.raw.jsonl").read_text(
        encoding="utf-8"
    ).splitlines():
        if line.strip():
            row = json.loads(line)
            raw_index[row["case_id"]] = row
    by_id: dict[str, dict[str, Any]] = {}
    for line in (fixtures / "swebench_verified.terse.jsonl").read_text(
        encoding="utf-8"
    ).splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row["case_id"] not in cfg.pilot_case_ids:
            continue
        gold = raw_index[row["case_id"]]["expected_spans"][0]
        by_id[row["case_id"]] = {
            "case_id": row["case_id"],
            "query": row["query"],
            "gold": {
                "file": gold["path"],
                "start_line": gold["start_line"],
                "end_line": gold["end_line"],
            },
        }
    missing = [cid for cid in cfg.pilot_case_ids if cid not in by_id]
    if missing:
        raise PoolRunError(
            f"pinned pilot cases missing from the committed fixtures: {missing}"
        )
    return [by_id[cid] for cid in cfg.pilot_case_ids]


def build_adoption_cell_artifact(
    *,
    case_id: str,
    model: str,
    verifier_artifact: dict[str, Any],
    verifier_artifact_path: str | Path | None,
    ledger_path: str | Path,
) -> dict[str, Any]:
    """The per-cell durable AC6 artifact, built ONLY from a verifier-PASSED
    trajectory. Tool facts are DERIVED from the trajectory's tool_calls via
    the one canonical parser (``extract_tool_names``) — never accepted
    self-reported."""
    if verifier_artifact.get("verifier_status") != "PASSED":
        raise PoolRunError(
            "adoption cell artifacts are built only from verifier-PASSED "
            "trajectories — a failed verification is a typed degrade in the "
            "ledger, never an artifact"
        )
    turns = verifier_artifact.get("model_turns") or []
    invocations = [
        name
        for turn in turns
        for call in (turn.get("tool_calls") or [])
        if (name := (call.get("function") or {}).get("name"))
    ]
    tool_names, _proven, _failure = extract_tool_names({"model_turns": turns})
    return {
        "schema_version": ADOPTION_CELL_ARTIFACT_SCHEMA_VERSION,
        "case_id": case_id,
        "model": model,
        # Model identity — requested AND served, from the verified trajectory.
        "requested_model": verifier_artifact.get("requested_model"),
        "served_model": verifier_artifact.get("served_model"),
        "endpoint": verifier_artifact.get("endpoint"),
        "verifier_status": "PASSED",
        "verifier_schema_version": verifier_artifact.get("schema_version"),
        "verifier_artifact": (
            str(verifier_artifact_path) if verifier_artifact_path else None
        ),
        # Tools invoked — incl. the per-case symbols invocation COUNT.
        "tool_names_invoked": tool_names,
        "tool_invocations": invocations,
        "symbols_invocations": sum(1 for n in invocations if n == "symbols"),
        "terminal_bucket": verifier_artifact.get("terminal_bucket"),
        "citations_submitted": verifier_artifact.get("citations_submitted"),
        "citations_surviving": verifier_artifact.get("citations_surviving"),
        # The run's exclusivity proof lives on the ledger (it grows per-block
        # check by check) — the artifact carries the typed REFERENCE.
        "exclusivity_proof_ref": {
            "ledger": str(ledger_path),
            "ledger_schema_version": POOL_PILOT_LEDGER_SCHEMA_VERSION_0041,
            "config_hash": ADOPTION_CONFIG_HASH_0042,
        },
    }


def _write_adoption_artifact(
    artifact_dir: Path, case_id: str, model: str, artifact: dict[str, Any]
) -> Path:
    slug = model.replace(":", "_").replace(".", "_")
    path = artifact_dir / f"{case_id}__{slug}.adoption.json"
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
    """The real per-cell runner: ``run_verified_case`` under the fixed SUT
    (the 0040 ``_run_pool_pilot_live`` settings shape, arm parity via the
    frozen 0040 ``explorer_think``)."""
    from harpyja.config.settings import Settings
    from harpyja.eval.live_verifier import run_verified_case
    from harpyja.gateway.gateway import ModelGateway

    worktrees = _repo_root() / "eval_work" / "worktrees"
    explorer_think = PREREGISTERED_POOL_CONFIG_0040.explorer_think

    def runner(case: dict[str, Any], model: str) -> tuple[dict[str, Any], str | None]:
        settings = dataclasses.replace(
            Settings(),
            lm_api_base=f"{api_base}/v1",
            lm_model=model,
            explorer_think=explorer_think,
            scout_max_turns=10,
            scout_wall_clock_s=240.0,
            lm_http_timeout_s=300.0,
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


def run_adoption_cells(
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
    """The gated adoption re-measurement loop (see module docstring). There
    is deliberately NO parameter to re-select cases or models — the pinned
    coverage is consumed from the frozen config; ``include_optional`` can
    only ENABLE tags already frozen as optional."""
    if not live:
        raise PoolRunError(
            "run_adoption_cells is a live operator entrypoint — pass live=True "
            "from the committed driver "
            "(specs/0042-adoption/adoption_run/run_adoption.py)"
        )
    models = adoption_coverage_models(include_optional)
    ledger_path = Path(ledger_path)
    artifact_dir = Path(artifact_dir)
    cases = load_pinned_adoption_cases()

    runner = verified_case_runner
    if runner is None:
        # Real live mode: STOP-AND-WARN serving preflight first (the 0040
        # posture — a substitution/absence under the frozen hash is a stop,
        # and an unreachable endpoint is a typed stop, never a traceback).
        try:
            with urllib.request.urlopen(f"{api_base}/api/tags", timeout=10) as r:
                served = [m["name"] for m in json.loads(r.read())["models"]]
        except OSError as e:
            raise PoolRunError(
                f"live endpoint {api_base} unreachable ({e}) — STOP; no cells ran"
            ) from e
        pool_pilot_preflight(
            PREREGISTERED_POOL_CONFIG_0040,
            served_tags=served,
            pilot_models=list(models),
        )
        out_dir = (
            Path(verifier_out_dir)
            if verifier_out_dir is not None
            else _repo_root() / "eval_work" / "live_artifacts" / "adoption_0042"
        )
        runner = _live_verified_case_runner(api_base=api_base, out_dir=out_dir)

    # Prior attempts ride the resumable ledger (read-only pre-scan; the gate
    # owns the live ledger instance).
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
            raise _AdoptionBudgetExhausted()
        if real_mode and block_state["model"] != model:
            # Entering a model block with work to do: evict co-residents
            # (the 0040 run-integrity lesson; defense-in-depth under 0041).
            _evict_other_models(model, api_base=api_base)
            block_state["model"] = model
        key = f"{case['case_id']}::{model}"
        attempts = attempts_map.get(key, 0) + 1
        attempts_map[key] = attempts
        try:
            artifact, artifact_path = runner(case, model)
        except ValueError as e:
            # run_verified_case's no-trajectory raise — a typed degrade.
            return {
                "bucket": None,
                "degrade": f"no-trajectory: {e}",
                "artifact": None,
                "attempts": attempts,
                "symbols_invocations": 0,
            }
        if artifact.get("verifier_status") != "PASSED":
            return {
                "bucket": None,
                "degrade": f"verifier:{artifact.get('failure_reason')}",
                "artifact": str(artifact_path) if artifact_path else None,
                "attempts": attempts,
                "symbols_invocations": 0,
            }
        cell_artifact = build_adoption_cell_artifact(
            case_id=case["case_id"],
            model=model,
            verifier_artifact=artifact,
            verifier_artifact_path=artifact_path,
            ledger_path=ledger_path,
        )
        out_path = _write_adoption_artifact(
            artifact_dir, case["case_id"], model, cell_artifact
        )
        return {
            "bucket": cell_artifact["terminal_bucket"],
            "degrade": None,
            "artifact": str(out_path),
            "verifier_artifact": cell_artifact["verifier_artifact"],
            "attempts": attempts,
            "symbols_invocations": cell_artifact["symbols_invocations"],
            "tools": cell_artifact["tool_names_invoked"],
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
            config_hash=ADOPTION_CONFIG_HASH_0042,
            live=True,
        )
    except _AdoptionBudgetExhausted:
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
        "config_hash": ADOPTION_CONFIG_HASH_0042,
        "ledger_path": str(ledger_path),
        "models": list(models),
        "cells_remaining": remaining,
        "checks_recorded": gate_result.get("checks_recorded"),
    }


def build_adoption_run_summary(ledger_path: str | Path) -> dict[str, Any]:
    """The machine-readable run summary: joins the run ledger against THE
    committed 0040 baseline via the FROZEN T9 machinery
    (``build_adoption_cells`` + ``decide_adoption_outcome`` — identity, never
    re-derived). The decision here is PROVISIONAL over the current ledger
    state; the AC7 typed-outcome record (T13) re-derives it from the frozen
    decider over the final committed artifacts. Suspect cells (invalidated at
    a contamination boundary) are excluded from the measurement join."""
    ledger = PoolPilotLedger(ledger_path, config_hash=ADOPTION_CONFIG_HASH_0042)
    if ledger.exclusivity is None:
        raise PoolRunError(
            "adoption ledger lacks the 0041/pilot/2 exclusivity proof — not a "
            "valid measurement"
        )
    entries = ledger.entries
    measured = {
        key: cell
        for key, cell in entries.items()
        if cell.get("status") != "suspect"
    }
    baseline = load_committed_0040_pilot_ledger()["entries"]
    models = sorted({key.partition("::")[2] for key in measured})
    cells = build_adoption_cells(baseline, measured, models)
    decision = decide_adoption_outcome(PREREGISTERED_ADOPTION_CONFIG_0042, cells)
    decision_dict = dataclasses.asdict(decision)
    decision_dict["outcome"] = decision.outcome.value
    return {
        "schema_version": ADOPTION_RUN_SUMMARY_SCHEMA_VERSION,
        "config_hash": ADOPTION_CONFIG_HASH_0042,
        "ledger": str(Path(ledger_path)),
        "models_run": models,
        "cells_recorded": len(entries),
        "cells_clean": sum(
            1
            for cell in measured.values()
            if cell.get("degrade") is None and cell.get("bucket")
        ),
        "cells_degraded": sum(1 for cell in measured.values() if cell.get("degrade")),
        "cells_suspect": len(entries) - len(measured),
        "decision": decision_dict,
    }
