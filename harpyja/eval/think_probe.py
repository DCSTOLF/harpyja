"""Spec 0037 — think-probe result contract (typed outcome + loud validator).

The live probe (specs/0037-explorer-think-knob/probes/run_probes.sh) determines
which request param actually toggles thinking on the dev Ollama /v1 path. Its
answer is committed as probes/probe_result.json with exactly ONE of the three
typed outcomes below — a TOTAL outcome space (the 0023 named-outcome
discipline): the expected hypothesis (native `think`), the rival mechanism
(`chat_template_kwargs`), or a no-op. Downstream ACs are conditional on
``native-think-effective``; the other two outcomes are recorded, A/B-blocking
findings — never a silent re-point.

This is a spec-local artifact schema (``0037/1``), deliberately NOT part of the
verifier schema set (``0034/1``) — it adds no persisted verifier field.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROBE_OUTCOMES = frozenset(
    {"native-think-effective", "chat-template-effective", "no-op"}
)

PROBE_RESULT_SCHEMA_VERSION = "0037/1"

_KNOWN_SCHEMA_VERSIONS = frozenset({PROBE_RESULT_SCHEMA_VERSION})

_REQUIRED_ARMS = frozenset({"think_true", "think_false", "omitted"})

_REQUIRED_ARM_KEYS = frozenset(
    {"completion_tokens", "finish_reason", "content_present", "think_in_content"}
)


class ProbeResultError(ValueError):
    """A probe_result.json that does not conform to the 0037/1 contract."""


def validate_probe_result(obj: dict[str, Any]) -> None:
    """Loudly reject any non-conforming probe result — no silent defaults."""
    version = obj.get("schema_version")
    if version not in _KNOWN_SCHEMA_VERSIONS:
        raise ProbeResultError(f"unknown probe-result schema_version: {version!r}")
    if not obj.get("model"):
        raise ProbeResultError("probe result missing 'model'")
    if not obj.get("endpoint"):
        raise ProbeResultError("probe result missing 'endpoint'")
    outcome = obj.get("outcome")
    if outcome not in PROBE_OUTCOMES:
        raise ProbeResultError(
            f"outcome {outcome!r} not in the typed outcome set {sorted(PROBE_OUTCOMES)}"
        )
    arms = obj.get("arms")
    if not isinstance(arms, dict) or set(arms) != _REQUIRED_ARMS:
        raise ProbeResultError(
            f"probe result must carry exactly the arms {sorted(_REQUIRED_ARMS)}, "
            f"got {sorted(arms) if isinstance(arms, dict) else arms!r}"
        )
    for name, arm in arms.items():
        if not isinstance(arm, dict) or not _REQUIRED_ARM_KEYS <= set(arm):
            missing = _REQUIRED_ARM_KEYS - set(arm if isinstance(arm, dict) else ())
            raise ProbeResultError(f"arm {name!r} missing keys: {sorted(missing)}")


def load_probe_result(path: str | Path) -> dict[str, Any]:
    """Read, validate, and return the committed probe result."""
    p = Path(path)
    if not p.is_file():
        raise ProbeResultError(f"probe result not found: {p}")
    obj = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ProbeResultError(f"probe result must be a JSON object, got {type(obj).__name__}")
    validate_probe_result(obj)
    return obj
