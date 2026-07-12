"""Spec 0040 — pool preflight result contract (typed outcomes + loud validator).

The live preflight (specs/0040-pool/preflight/run_preflight.sh) probes ALL
THREE pinned models — ``qwen3:14b`` re-confirmed, not assumed from 0039 —
for coherence, clean ``/v1`` tool_calls, and think-control mechanism, and
commits one artifact carrying exactly one committed ``PreflightOutcome`` per
model (the 0023/0037 total-answer-space discipline; the enum and its
precedence live in ``pool_precheck``).

The shape records the raw observations next to the typed outcome, plus the
per-model ``think_control_mechanism`` (the 0037/0038 lesson: serving is
model+version specific — ``reasoning_effort`` proven for 14b may differ for a
newer generation; probed, never assumed). The excluding/non-excluding
ASYMMETRY is enforced at validation: an EXCLUDING outcome must carry its
recorded ``exclusion_reason`` (never a silent removal), a non-excluding one
must not (a reason on a kept model would misread as an exclusion).

This is a spec-local artifact schema (``0040/preflight/1``) — NOT part of the
verifier schema set; it adds no persisted verifier field.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harpyja.eval.pool_precheck import (
    PREREGISTERED_POOL_CONFIG_0040,
    PreflightOutcome,
    is_excluding,
)

POOL_PREFLIGHT_SCHEMA_VERSION = "0040/preflight/1"

_KNOWN_SCHEMA_VERSIONS = frozenset({POOL_PREFLIGHT_SCHEMA_VERSION})

_REQUIRED_MODEL_KEYS = frozenset(
    {
        "outcome",
        "served",
        "coherent",
        "tool_calls_clean",
        "think_control",
        "think_control_mechanism",
        "exclusion_reason",
    }
)

_OUTCOME_VALUES = frozenset(o.value for o in PreflightOutcome)


class PoolPreflightError(ValueError):
    """A preflight result that does not conform — loud, never defaulted."""


def validate_pool_preflight_result(obj: dict[str, Any]) -> None:
    """Loudly reject any non-conforming preflight result — no silent defaults."""
    version = obj.get("schema_version")
    if version not in _KNOWN_SCHEMA_VERSIONS:
        raise PoolPreflightError(
            f"unknown pool-preflight schema_version: {version!r}"
        )
    if not obj.get("endpoint"):
        raise PoolPreflightError("preflight result missing 'endpoint'")
    if not obj.get("config_hash"):
        raise PoolPreflightError("preflight result missing 'config_hash'")
    models = obj.get("models")
    expected = set(PREREGISTERED_POOL_CONFIG_0040.model_tags)
    if not isinstance(models, dict) or set(models) != expected:
        raise PoolPreflightError(
            f"preflight result must carry exactly the three pinned models "
            f"{sorted(expected)}, got "
            f"{sorted(models) if isinstance(models, dict) else models!r}"
        )
    for tag, record in models.items():
        if not isinstance(record, dict) or not _REQUIRED_MODEL_KEYS <= set(record):
            missing = _REQUIRED_MODEL_KEYS - set(
                record if isinstance(record, dict) else ()
            )
            raise PoolPreflightError(f"model {tag!r} missing keys: {sorted(missing)}")
        outcome = record["outcome"]
        if outcome not in _OUTCOME_VALUES:
            raise PoolPreflightError(
                f"model {tag!r} outcome {outcome!r} not in the typed outcome "
                f"set {sorted(_OUTCOME_VALUES)}"
            )
        excluding = is_excluding(PreflightOutcome(outcome))
        if excluding and not record["exclusion_reason"]:
            raise PoolPreflightError(
                f"model {tag!r} has EXCLUDING outcome {outcome!r} but no "
                f"recorded exclusion_reason — exclusion is never silent"
            )
        if not excluding and record["exclusion_reason"]:
            raise PoolPreflightError(
                f"model {tag!r} has non-excluding outcome {outcome!r} but "
                f"carries an exclusion_reason — a reason on a kept model "
                f"would misread as an exclusion"
            )


def load_pool_preflight_result(path: str | Path) -> dict[str, Any]:
    """Read, validate, and return a committed preflight result."""
    p = Path(path)
    if not p.is_file():
        raise PoolPreflightError(f"preflight result not found: {p}")
    obj = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise PoolPreflightError(
            f"preflight result must be a JSON object, got {type(obj).__name__}"
        )
    validate_pool_preflight_result(obj)
    return obj


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def committed_pool_preflight_path() -> Path:
    """THE committed 0040 preflight result — archive-first (the 79f7bf2
    convention: pins target ``specs/.archive`` from authoring; the live spec
    dir is the explicit fallback while unarchived)."""
    root = _repo_root()
    archived = (
        root / "specs" / ".archive" / "0040-pool" / "preflight"
        / "preflight_result.json"
    )
    live = root / "specs" / "0040-pool" / "preflight" / "preflight_result.json"
    return archived if archived.is_file() else live


def load_committed_pool_preflight_result() -> dict[str, Any]:
    return load_pool_preflight_result(committed_pool_preflight_path())
