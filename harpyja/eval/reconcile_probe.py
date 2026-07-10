"""Spec 0038 — reconcile-probe result contract (typed outcome + loud validator).

The live probe (specs/0038-reconciliation/probes/run_probes.sh) determines
which transport path genuinely honors the explorer think toggle on the dev
Ollama, by the 0034/0037 two-factor generation test (tiny-cap discriminator +
completion_tokens cross-check + <think> leak scan) across ALL THREE arms
(think:true / think:false / omitted — native default OBSERVED, never inferred).
Its answer is committed as probes/probe_result.json with exactly ONE of the
three typed outcomes below — a TOTAL outcome space (the 0023 named-outcome
discipline): the probe-proven leading candidate (native /api/chat), a /v1
variant not ruled out by 0037, or still-blocked (no path honors it — a typed
STILL_BLOCKED close, never a forced pass).

The shape splits path from evidence — ``chosen_path`` / ``outcome`` /
``usage_mapping`` / ``migration_cost`` / per-arm observed facts — so future
drift can distinguish endpoint failure from adapter failure. ``usage_mapping``
pins the native source of ``completion_tokens`` (proof-bearing: AC1/AC3 token
deltas cite it); ``migration_cost`` scopes the endpoint-migration cost
(tool_call_id presence for the 0029 answer-all-N protocol, usage/reasoning
field names) BEFORE wiring, not after.

This is a spec-local artifact schema (``0038/1``), deliberately NOT a reuse of
``0037/1`` and NOT part of the verifier schema set — it adds no persisted
verifier field on its own.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RECONCILE_PROBE_OUTCOMES = frozenset({"native-api-chat", "v1-variant", "still-blocked"})

RECONCILE_PROBE_SCHEMA_VERSION = "0038/1"

_KNOWN_SCHEMA_VERSIONS = frozenset({RECONCILE_PROBE_SCHEMA_VERSION})

_REQUIRED_ARMS = frozenset({"think_true", "think_false", "omitted"})

_REQUIRED_ARM_KEYS = frozenset(
    {
        "content_present",
        "finish_reason",
        "completion_tokens",
        "reasoning_chars",
        "think_in_content",
    }
)

_REQUIRED_MIGRATION_COST_KEYS = frozenset(
    {"tool_call_id_present", "usage_field_name", "reasoning_field_name"}
)


class ReconcileProbeError(ValueError):
    """A probe_result.json that does not conform to the 0038/1 contract."""


def validate_reconcile_probe_result(obj: dict[str, Any]) -> None:
    """Loudly reject any non-conforming probe result — no silent defaults."""
    version = obj.get("schema_version")
    if version not in _KNOWN_SCHEMA_VERSIONS:
        raise ReconcileProbeError(
            f"unknown reconcile-probe schema_version: {version!r}"
        )
    if not obj.get("model"):
        raise ReconcileProbeError("probe result missing 'model'")
    if not obj.get("endpoint"):
        raise ReconcileProbeError("probe result missing 'endpoint'")
    if not obj.get("chosen_path"):
        raise ReconcileProbeError("probe result missing 'chosen_path'")
    outcome = obj.get("outcome")
    if outcome not in RECONCILE_PROBE_OUTCOMES:
        raise ReconcileProbeError(
            f"outcome {outcome!r} not in the typed outcome set "
            f"{sorted(RECONCILE_PROBE_OUTCOMES)}"
        )
    usage_mapping = obj.get("usage_mapping")
    if not isinstance(usage_mapping, dict) or "completion_tokens" not in usage_mapping:
        raise ReconcileProbeError(
            "probe result must carry 'usage_mapping' with a 'completion_tokens' source"
        )
    migration_cost = obj.get("migration_cost")
    if not isinstance(migration_cost, dict) or not (
        _REQUIRED_MIGRATION_COST_KEYS <= set(migration_cost)
    ):
        missing = _REQUIRED_MIGRATION_COST_KEYS - set(
            migration_cost if isinstance(migration_cost, dict) else ()
        )
        raise ReconcileProbeError(f"migration_cost missing keys: {sorted(missing)}")
    arms = obj.get("arms")
    if not isinstance(arms, dict) or set(arms) != _REQUIRED_ARMS:
        raise ReconcileProbeError(
            f"probe result must carry exactly the arms {sorted(_REQUIRED_ARMS)}, "
            f"got {sorted(arms) if isinstance(arms, dict) else arms!r}"
        )
    for name, arm in arms.items():
        if not isinstance(arm, dict) or not _REQUIRED_ARM_KEYS <= set(arm):
            missing = _REQUIRED_ARM_KEYS - set(arm if isinstance(arm, dict) else ())
            raise ReconcileProbeError(f"arm {name!r} missing keys: {sorted(missing)}")


def load_reconcile_probe_result(path: str | Path) -> dict[str, Any]:
    """Read, validate, and return the committed probe result."""
    p = Path(path)
    if not p.is_file():
        raise ReconcileProbeError(f"probe result not found: {p}")
    obj = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ReconcileProbeError(
            f"probe result must be a JSON object, got {type(obj).__name__}"
        )
    validate_reconcile_probe_result(obj)
    return obj


def load_committed_reconcile_probe_result() -> dict[str, Any]:
    """Load THE committed 0038 probe result — the one canonical resolver.

    Per the evidence-path convention the canonical location is
    ``specs/.archive/0038-reconciliation/probes/probe_result.json`` (pins
    target the archived path from authoring; the close flow relocates the spec
    dir there at zero conflicts); while the spec is live and unarchived the
    live path is resolved explicitly as the fallback — never a bare
    ``specs/0038-reconciliation/`` alone.
    """
    root = Path(__file__).resolve().parents[2]
    archived = (
        root / "specs" / ".archive" / "0038-reconciliation"
        / "probes" / "probe_result.json"
    )
    live = root / "specs" / "0038-reconciliation" / "probes" / "probe_result.json"
    return load_reconcile_probe_result(archived if archived.is_file() else live)
