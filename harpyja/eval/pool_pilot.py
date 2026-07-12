"""Spec 0040 — the live three-model preflight probe + resumable pilot machinery.

PREFLIGHT (AC3): ``run_model_preflight`` types one model through the committed
enum in ``pool_precheck`` — served → coherent → clean tool_calls →
think-control — against the actual Ollama ``/v1`` path. Serving is
model+version specific (the 0037/0038 lesson): the think-control probe re-runs
the 0038 tiny-cap two-factor discriminator PER MODEL (``reasoning_effort``
proven for ``qwen3:14b`` may differ for a newer generation); an indeterminate
probe adjudicates to THINK_CONTROL_NOOP (conservative, non-excluding).

PILOT (AC4): ``PoolPilotLedger`` is the resumable per ``case::model`` ledger
(the ~100+ min pilot outlasts one invocation — the 0036/0039 posture), keyed
to the FROZEN config hash; ``pool_pilot_preflight`` is the STOP-AND-WARN gate
(a runtime model substitution under the frozen hash would be the post-hoc
steering the freeze prevents). ``run_pool_pilot`` drives ``run_verified_case``
per preflight-passing model x pinned case at ``explorer_think=None`` (arm
parity, pinned in config) — measurement machinery only, no SUT change.
"""

from __future__ import annotations

import dataclasses
import json
import urllib.request
from pathlib import Path
from typing import Any

from harpyja.eval.locate_probe import require_live_stack
from harpyja.eval.pool_precheck import (
    POOL_CONFIG_HASH_0040,
    PREREGISTERED_POOL_CONFIG_0040,
    PoolConfig,
    PreflightObservations,
    PreflightOutcome,
    adjudicate_preflight,
    is_excluding,
)

__all__ = [
    "POOL_PILOT_LEDGER_SCHEMA_VERSION",
    "POOL_PILOT_LEDGER_SCHEMA_VERSION_0041",
    "ModelPreflightResult",
    "PoolPilotLedger",
    "PoolRunError",
    "pool_pilot_preflight",
    "require_live_stack",
    "run_model_preflight",
    "run_pool_pilot",
]

_API_BASE = "http://127.0.0.1:11434"


class PoolRunError(ValueError):
    """A run precondition or ledger that does not conform — loud, never defaulted."""


# ---- the live per-model preflight probe (AC3) ---------------------------------


@dataclasses.dataclass(frozen=True)
class ModelPreflightResult:
    """One model's typed preflight answer plus the raw observations behind it."""

    model: str
    outcome: PreflightOutcome
    observations: PreflightObservations
    think_control_mechanism: str | None
    exclusion_reason: str | None


def _chat(
    model: str,
    body: dict[str, Any],
    *,
    api_base: str,
    timeout_s: float,
) -> dict[str, Any]:
    payload = json.dumps({"model": model, **body}).encode("utf-8")
    req = urllib.request.Request(
        f"{api_base}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read())


def _coherence_probe(
    model: str, *, api_base: str, timeout_s: float
) -> tuple[bool, str | None]:
    """A known-trivial instruction must yield sane content — the 16B-gibberish
    trap produces empties/garbage that would fake "can't localize"."""
    try:
        body = _chat(
            model,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Reply with exactly the single word: READY",
                    }
                ],
                "max_tokens": 1024,
            },
            api_base=api_base,
            timeout_s=timeout_s,
        )
    except Exception as e:  # noqa: BLE001
        return False, f"coherence probe request failed: {e}"
    content = (body["choices"][0]["message"].get("content") or "").strip()
    if "ready" in content.lower():
        return True, None
    return False, f"incoherent reply to a trivial instruction: {content[:120]!r}"


_PROBE_TOOL = {
    "type": "function",
    "function": {
        "name": "grep",
        "description": "Search file contents for a pattern.",
        "parameters": {
            "type": "object",
            "properties": {"pattern": {"type": "string"}},
            "required": ["pattern"],
        },
    },
}


def _tool_call_probe(
    model: str, *, api_base: str, timeout_s: float
) -> tuple[bool, str | None]:
    """One forced tool turn must come back as clean tool_calls: id present,
    the committed name, arguments parsing as a JSON object."""
    try:
        body = _chat(
            model,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Use the grep tool to search for 'foo'.",
                    }
                ],
                "tools": [_PROBE_TOOL],
                "max_tokens": 1024,
            },
            api_base=api_base,
            timeout_s=timeout_s,
        )
    except Exception as e:  # noqa: BLE001
        return False, f"tool-call probe request failed: {e}"
    calls = body["choices"][0]["message"].get("tool_calls") or []
    if not calls:
        return False, "no tool_calls in a forced tool turn"
    for call in calls:
        if not call.get("id"):
            return False, "tool_call missing id"
        fn = call.get("function") or {}
        if fn.get("name") != "grep":
            return False, f"unexpected tool name: {fn.get('name')!r}"
        try:
            args = json.loads(fn.get("arguments") or "")
        except (TypeError, ValueError):
            return False, f"tool_call arguments not JSON: {fn.get('arguments')!r}"
        if not isinstance(args, dict):
            return False, "tool_call arguments not a JSON object"
    return True, None


def _think_arm(
    model: str, effort: str | None, *, api_base: str, timeout_s: float
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "messages": [{"role": "user", "content": "What is 17 * 23?"}],
        "max_tokens": 60,
    }
    if effort is not None:
        body["reasoning_effort"] = effort
    resp = _chat(model, body, api_base=api_base, timeout_s=timeout_s)
    choice = resp["choices"][0]
    message = choice["message"]
    content = message.get("content") or ""
    return {
        "content": content,
        "finish": choice.get("finish_reason"),
        "reasoning_chars": len(message.get("reasoning") or ""),
        "think_leak": "<think>" in content,
    }


def _think_control_probe(
    model: str, *, api_base: str, timeout_s: float
) -> str:
    """The 0038 tiny-cap two-factor discriminator, per model: "effective" iff
    the off arm genuinely stops generating reasoning while the on arm thinks;
    "noop" iff both arms think regardless; "indeterminate" otherwise (which
    the adjudicator conservatively maps to THINK_CONTROL_NOOP)."""
    try:
        off = _think_arm(model, "none", api_base=api_base, timeout_s=timeout_s)
        on = _think_arm(model, "high", api_base=api_base, timeout_s=timeout_s)
    except Exception:  # noqa: BLE001
        return "indeterminate"
    off_is_off = (
        off["reasoning_chars"] == 0
        and not off["think_leak"]
        and (bool(off["content"].strip()) or off["finish"] != "length")
    )
    on_is_on = on["reasoning_chars"] > 0 or (
        on["finish"] == "length" and not on["content"].strip()
    )
    off_is_on = off["reasoning_chars"] > 0 or (
        off["finish"] == "length" and not off["content"].strip()
    )
    if off_is_off and on_is_on:
        return "effective"
    if off_is_on and on_is_on:
        return "noop"
    return "indeterminate"


def run_model_preflight(
    model: str,
    *,
    served_tags: set[str],
    api_base: str = _API_BASE,
    timeout_s: float = 300.0,
) -> ModelPreflightResult:
    """Type one model through the committed preflight enum, in the frozen
    precedence order — later probes are skipped once an earlier one fails
    (their facts default to the failing shape, recorded in observations)."""
    served = model in served_tags
    coherent, reason = False, f"model tag {model!r} not served"
    tool_calls_clean = False
    think_control = "indeterminate"
    if served:
        coherent, reason = _coherence_probe(
            model, api_base=api_base, timeout_s=timeout_s
        )
        if coherent:
            tool_calls_clean, reason = _tool_call_probe(
                model, api_base=api_base, timeout_s=timeout_s
            )
            if tool_calls_clean:
                think_control = _think_control_probe(
                    model, api_base=api_base, timeout_s=timeout_s
                )

    obs = PreflightObservations(
        served=served,
        coherent=coherent,
        tool_calls_clean=tool_calls_clean,
        think_control=think_control,
    )
    outcome = adjudicate_preflight(obs)
    return ModelPreflightResult(
        model=model,
        outcome=outcome,
        observations=obs,
        think_control_mechanism=(
            "reasoning-effort" if think_control == "effective" else None
        ),
        exclusion_reason=reason if is_excluding(outcome) else None,
    )


# ---- resumable pilot ledger + STOP-AND-WARN preflight (AC4) --------------------

POOL_PILOT_LEDGER_SCHEMA_VERSION = "0040/pilot/1"

# Spec 0041 (AC3): the run-level exclusivity proof rides the ledger under a
# NEW version — version-gated per the 0026/0036 pattern: the new version
# REQUIRES the record, legacy 0040/pilot/1 artifacts validate unchanged.
POOL_PILOT_LEDGER_SCHEMA_VERSION_0041 = "0041/pilot/2"

_KNOWN_LEDGER_SCHEMA_VERSIONS = frozenset(
    {POOL_PILOT_LEDGER_SCHEMA_VERSION, POOL_PILOT_LEDGER_SCHEMA_VERSION_0041}
)


class PoolPilotLedger:
    """Resumable per-cell (case x model) pilot ledger, atomically persisted,
    keyed to the FROZEN 0040 config hash (a ledger written under a different
    config is not resumable — loud, never merged). With ``exclusivity`` (the
    0041 run-level proof) it persists at ``0041/pilot/2``, which REQUIRES a
    conforming record; without, it writes/reads ``0040/pilot/1`` unchanged."""

    def __init__(
        self,
        path: str | Path,
        *,
        config_hash: str = POOL_CONFIG_HASH_0040,
        exclusivity: dict[str, Any] | None = None,
    ):
        self._path = Path(path)
        self._config_hash = config_hash
        self._exclusivity: dict[str, Any] | None = None
        if self._path.is_file():
            obj = json.loads(self._path.read_text(encoding="utf-8"))
            version = obj.get("schema_version")
            if version not in _KNOWN_LEDGER_SCHEMA_VERSIONS:
                raise PoolRunError(f"unknown pool-ledger schema_version: {version!r}")
            if obj.get("config_hash") != config_hash:
                raise PoolRunError(
                    "ledger was written under a different frozen config "
                    f"({obj.get('config_hash')!r} != {config_hash!r}) — not resumable"
                )
            if version == POOL_PILOT_LEDGER_SCHEMA_VERSION_0041:
                # The new version is not a valid measurement without the proof.
                self._exclusivity = self._validated_exclusivity(
                    obj.get("exclusivity")
                )
            self._entries: dict[str, dict[str, Any]] = dict(obj.get("entries", {}))
            if exclusivity is not None:
                self.set_exclusivity(exclusivity)
        else:
            self._entries = {}
            if exclusivity is not None:
                self._exclusivity = self._validated_exclusivity(exclusivity)
            self._flush()

    @staticmethod
    def _validated_exclusivity(record: Any) -> dict[str, Any]:
        from harpyja.eval.exclusivity_gate import (
            ExclusivityError,
            validate_exclusivity_record,
        )

        if not isinstance(record, dict):
            raise PoolRunError(
                f"a {POOL_PILOT_LEDGER_SCHEMA_VERSION_0041} ledger requires the "
                "exclusivity proof record — a run artifact lacking it is not a "
                "valid measurement"
            )
        try:
            validate_exclusivity_record(record)
        except ExclusivityError as e:
            raise PoolRunError(f"non-conforming exclusivity record: {e}") from e
        return dict(record)

    @property
    def exclusivity(self) -> dict[str, Any] | None:
        return dict(self._exclusivity) if self._exclusivity is not None else None

    def set_exclusivity(self, record: dict[str, Any]) -> None:
        """Replace the exclusivity record (e.g. a per-block check appended)
        and re-persist — validated, never defaulted."""
        self._exclusivity = self._validated_exclusivity(record)
        self._flush()

    @staticmethod
    def _key(case_id: str, model: str) -> str:
        return f"{case_id}::{model}"

    def has(self, case_id: str, model: str) -> bool:
        return self._key(case_id, model) in self._entries

    def get(self, case_id: str, model: str) -> dict[str, Any] | None:
        return self._entries.get(self._key(case_id, model))

    def record(self, case_id: str, model: str, entry: dict[str, Any]) -> None:
        self._entries[self._key(case_id, model)] = entry
        self._flush()

    @property
    def entries(self) -> dict[str, dict[str, Any]]:
        return dict(self._entries)

    def _flush(self) -> None:
        payload: dict[str, Any] = {
            "schema_version": (
                POOL_PILOT_LEDGER_SCHEMA_VERSION_0041
                if self._exclusivity is not None
                else POOL_PILOT_LEDGER_SCHEMA_VERSION
            ),
            "config_hash": self._config_hash,
            "entries": self._entries,
        }
        if self._exclusivity is not None:
            payload["exclusivity"] = self._exclusivity
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        tmp.replace(self._path)


_MAX_CELL_ATTEMPTS = 2  # one bounded re-run per typed degrade (0036 posture)


def _evict_other_models(current: str, *, api_base: str = _API_BASE) -> list[str]:
    """Best-effort eviction of every loaded model except ``current`` before a
    model block fires. The dev Ollama pins models with keep_alive=-1
    (expires_at far-future); a 14b block running against 14+ GB of co-pinned
    residents thrashes the 32 GB box — wall-clock expiries fake "empty" and
    HTTP timeouts fake "model-unreachable" (run-integrity, the 0040 lesson)."""
    evicted: list[str] = []
    try:
        with urllib.request.urlopen(f"{api_base}/api/ps", timeout=10) as r:
            loaded = [m["name"] for m in json.loads(r.read())["models"]]
    except Exception:  # noqa: BLE001
        return evicted
    for name in loaded:
        if name == current:
            continue
        try:
            payload = json.dumps({"model": name, "keep_alive": 0}).encode("utf-8")
            req = urllib.request.Request(
                f"{api_base}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30):
                pass
            evicted.append(name)
        except Exception:  # noqa: BLE001
            continue
    return evicted


def _cell_needs_run(
    cell: dict[str, Any] | None, *, clean_gate_since: bool = False
) -> bool:
    """Resume predicate: absent → run; clean bucket → NEVER re-run (re-running
    a clean observation because its outcome looks wrong would be post-hoc
    steering); typed degrade → ONE bounded re-run, then recorded-by-cause;
    suspect (spec 0041 — invalidated outcome-blind at a contamination
    boundary) → re-runnable ONLY after a subsequent clean gate check."""
    if cell is None:
        return True
    if cell.get("status") == "suspect":
        return clean_gate_since
    if cell.get("degrade") is None:
        return False
    return cell.get("attempts", 1) < _MAX_CELL_ATTEMPTS


def pool_pilot_preflight(
    cfg: PoolConfig, *, served_tags: list[str], pilot_models: list[str]
) -> dict[str, Any]:
    """STOP-AND-WARN before any pilot cell fires: every model entering the
    pilot must be a pinned tag AND served — a runtime substitution under the
    frozen hash would be exactly the post-hoc steering the freeze prevents."""
    unpinned = [m for m in pilot_models if m not in cfg.model_tags]
    if unpinned:
        raise PoolRunError(
            f"models {unpinned} are not in the pre-registered tag set "
            f"{list(cfg.model_tags)} — STOP; do not substitute under the frozen hash"
        )
    missing = [m for m in pilot_models if m not in served_tags]
    if missing:
        raise PoolRunError(
            f"pre-registered model tags {missing} are not served "
            f"(served: {served_tags}) — STOP; do not substitute a model under "
            f"the frozen config hash"
        )
    return {
        "models_served": True,
        "pilot_models": list(pilot_models),
        "explorer_think": cfg.explorer_think,
    }


def run_pool_pilot(
    cfg: PoolConfig = PREREGISTERED_POOL_CONFIG_0040,
    *,
    out_dir: str | Path,
    ledger_path: str | Path,
    pilot_models: list[str],
    live: bool = False,
    budget_s: float | None = None,
) -> dict[str, Any]:
    """The live pilot loop: per preflight-passing model x pinned case through
    ``run_verified_case`` at ``explorer_think=None`` (arm parity), resumable
    via ``PoolPilotLedger``. ``live=False`` refuses loudly — the committed
    operator driver is the only caller that passes ``live=True``. A ``budget_s``
    stops cleanly between cells with status "in-progress" (the driver maps it
    to exit 3 — re-invoke to resume)."""
    if not live:
        raise PoolRunError(
            "run_pool_pilot is a live operator entrypoint — pass live=True "
            "from the committed driver (specs/0040-pool/pilot/run_pilot.py)"
        )
    return _run_pool_pilot_live(
        cfg, out_dir=Path(out_dir), ledger_path=Path(ledger_path),
        pilot_models=pilot_models, budget_s=budget_s,
    )


def _run_pool_pilot_live(
    cfg: PoolConfig,
    *,
    out_dir: Path,
    ledger_path: Path,
    pilot_models: list[str],
    budget_s: float | None = None,
) -> dict[str, Any]:
    import dataclasses as _dc
    import time as _time

    from harpyja.config.settings import Settings
    from harpyja.eval.live_verifier import run_verified_case
    from harpyja.eval.think_ab_precheck import _repo_root, load_fixture_reachability
    from harpyja.gateway.gateway import ModelGateway

    started = _time.monotonic()

    root = _repo_root()
    fixtures = root / "harpyja" / "eval" / "fixtures"
    worktrees = root / "eval_work" / "worktrees"

    with urllib.request.urlopen(f"{_API_BASE}/api/tags", timeout=10) as r:
        served = [m["name"] for m in json.loads(r.read())["models"]]
    preflight = pool_pilot_preflight(
        cfg, served_tags=served, pilot_models=pilot_models
    )

    reachability = load_fixture_reachability()
    raw_index: dict[str, dict[str, Any]] = {}
    for line in (fixtures / "swebench_verified.raw.jsonl").read_text(
        encoding="utf-8"
    ).splitlines():
        if line.strip():
            row = json.loads(line)
            raw_index[row["case_id"]] = row
    cases: list[dict[str, Any]] = []
    for line in (fixtures / "swebench_verified.terse.jsonl").read_text(
        encoding="utf-8"
    ).splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row["case_id"] not in cfg.pilot_case_ids:
            continue
        gold = raw_index[row["case_id"]]["expected_spans"][0]
        cases.append(
            {
                "case_id": row["case_id"],
                "query": row["query"],
                "gold": {
                    "file": gold["path"],
                    "start_line": gold["start_line"],
                    "end_line": gold["end_line"],
                },
            }
        )

    ledger = PoolPilotLedger(ledger_path, config_hash=POOL_CONFIG_HASH_0040)
    locate_counts: dict[str, int] = {}

    # Model-major order (all cases on one model before the next) to minimize
    # model swaps — the 0036 arm-major posture.
    for model in pilot_models:
        if any(_cell_needs_run(ledger.get(c["case_id"], model)) for c in cases):
            _evict_other_models(model)
        for case in cases:
            prior = ledger.get(case["case_id"], model)
            if not _cell_needs_run(prior):
                continue
            attempts = (prior.get("attempts", 1) if prior else 0) + 1
            if budget_s is not None and _time.monotonic() - started > budget_s:
                remaining = sum(
                    1
                    for m in pilot_models
                    for c in cases
                    if _cell_needs_run(ledger.get(c["case_id"], m))
                )
                return {
                    "status": "in-progress",
                    "config_hash": POOL_CONFIG_HASH_0040,
                    "preflight": preflight,
                    "cells_remaining": remaining,
                    "ledger_path": str(ledger_path),
                }
            settings = _dc.replace(
                Settings(),
                lm_api_base=f"{_API_BASE}/v1",
                lm_model=model,
                explorer_think=cfg.explorer_think,
                scout_max_turns=10,
                scout_wall_clock_s=240.0,
                lm_http_timeout_s=300.0,
            )
            gateway = ModelGateway(
                api_base=settings.lm_api_base, model=settings.lm_model
            )
            model_dir = out_dir / model.replace(":", "_").replace(".", "_")
            try:
                result, artifact_path = run_verified_case(
                    case_name=case["case_id"],
                    settings=settings,
                    gateway=gateway,
                    gold_span=case["gold"],
                    out_dir=model_dir,
                    repo_path=str(worktrees / case["case_id"]),
                    query=case["query"],
                )
            except ValueError as e:
                ledger.record(
                    case["case_id"],
                    model,
                    {
                        "bucket": None,
                        "degrade": f"no-trajectory: {e}",
                        "artifact": None,
                        "attempts": attempts,
                    },
                )
                continue
            artifact = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
            if result.status != "PASSED":
                entry: dict[str, Any] = {
                    "bucket": None,
                    "degrade": f"verifier:{result.failure_reason}",
                    "artifact": str(artifact_path),
                    "attempts": attempts,
                }
            else:
                per_turn = artifact.get("per_turn") or []
                entry = {
                    "bucket": artifact["terminal_bucket"],
                    "degrade": None,
                    "artifact": str(artifact_path),
                    "attempts": attempts,
                    "reasoning_chars": sum(
                        t.get("reasoning_chars") or 0 for t in per_turn
                    ),
                    "completion_tokens": sum(
                        t.get("completion_tokens") or 0 for t in per_turn
                    ),
                    "tools": artifact.get("tool_names", []),
                    "think_mode": artifact.get("think_mode"),
                    "serving_transport": artifact.get("serving_transport"),
                }
            ledger.record(case["case_id"], model, entry)

    from harpyja.eval.locate_accuracy import LocateBucket
    from harpyja.eval.think_ab import located_via_oracle

    for model in pilot_models:
        locate_counts[model] = sum(
            1
            for case in cases
            if reachability.get(case["case_id"]) == "conceptual"
            and (cell := ledger.get(case["case_id"], model)) is not None
            and cell.get("bucket")
            and located_via_oracle(LocateBucket(cell["bucket"]))
        )

    return {
        "status": "completed",
        "config_hash": POOL_CONFIG_HASH_0040,
        "preflight": preflight,
        "conceptual_locate_counts": locate_counts,
        "ledger_path": str(ledger_path),
    }
