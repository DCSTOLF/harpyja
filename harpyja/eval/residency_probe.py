"""Spec 0041 — the driver-scoped bounded-residency probe (AC4/AC7).

The dev Ollama pins every touched model resident (server-side ``keep_alive=-1``
— the 0040 memory-squeeze half of the contamination). The candidate fix is a
DRIVER-side native-API touch with a bounded ``keep_alive`` after each block —
never a field on the SUT's ``/v1`` request body (the production gateway is not
the seam; the 0034/0038 byte-identical pin survives verbatim).

Sent ≠ honored (the 0037 ``/v1``-drops-the-field lesson): whether the touch
actually RE-BOUNDS a pinned model is an empirical question answered by this
probe, judged ONLY from observed ``/api/ps`` ``expires_at`` movement. The typed
outcome — ``touch-rebounds`` (bounded touch honored → the driver bounds
residency per block, eviction stays defense-in-depth) or ``touch-ignored``
(eviction remains the only residency control, recorded) — commits as a
spec-local ``0041/residency-probe/1`` artifact; wiring is conditional on it
via a loud-FAIL tripwire (fails on drift, never skips — the 0038 posture).
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any

RESIDENCY_PROBE_SCHEMA_VERSION = "0041/residency-probe/1"

_KNOWN_SCHEMA_VERSIONS = frozenset({RESIDENCY_PROBE_SCHEMA_VERSION})

RESIDENCY_PROBE_OUTCOMES = frozenset({"touch-rebounds", "touch-ignored"})

# A re-bound expiry must land within the bound plus slack — movement to yet
# another far-future value is NOT honoring.
_REBOUND_SLACK_FACTOR = 2.0

_REQUIRED_KEYS = frozenset(
    {
        "schema_version",
        "endpoint",
        "model",
        "keep_alive_bound_s",
        "touched_at",
        "expires_at_before",
        "expires_at_after",
        "outcome",
    }
)


class ResidencyProbeError(ValueError):
    """A probe result that does not conform — loud, never defaulted."""


def judge_residency_outcome(
    *,
    expires_at_before: str,
    expires_at_after: str,
    touched_at: str,
    keep_alive_bound_s: float,
) -> str:
    """Type the outcome from OBSERVED ``expires_at`` movement only.

    ``touch-rebounds`` iff the expiry MOVED and landed in the bounded
    near-future window after the touch (bound × slack); anything else —
    unchanged, or moved to another far-future pin — is ``touch-ignored``.
    """
    if expires_at_after == expires_at_before:
        return "touch-ignored"
    touched = _dt.datetime.fromisoformat(touched_at)
    after = _dt.datetime.fromisoformat(expires_at_after)
    window_s = keep_alive_bound_s * _REBOUND_SLACK_FACTOR
    if _dt.timedelta(0) <= after - touched <= _dt.timedelta(seconds=window_s):
        return "touch-rebounds"
    return "touch-ignored"


def validate_residency_probe_result(obj: dict[str, Any]) -> None:
    """Loudly reject any non-conforming probe result — including one whose
    recorded outcome contradicts its own expires_at evidence."""
    version = obj.get("schema_version")
    if version not in _KNOWN_SCHEMA_VERSIONS:
        raise ResidencyProbeError(
            f"unknown residency-probe schema_version: {version!r}"
        )
    missing = _REQUIRED_KEYS - set(obj)
    if missing:
        raise ResidencyProbeError(f"probe result missing keys: {sorted(missing)}")
    outcome = obj.get("outcome")
    if outcome not in RESIDENCY_PROBE_OUTCOMES:
        raise ResidencyProbeError(
            f"outcome {outcome!r} not in the typed outcome set "
            f"{sorted(RESIDENCY_PROBE_OUTCOMES)}"
        )
    rejudged = judge_residency_outcome(
        expires_at_before=obj["expires_at_before"],
        expires_at_after=obj["expires_at_after"],
        touched_at=obj["touched_at"],
        keep_alive_bound_s=obj["keep_alive_bound_s"],
    )
    if rejudged != outcome:
        raise ResidencyProbeError(
            f"recorded outcome {outcome!r} contradicts the expires_at evidence "
            f"(re-judges to {rejudged!r}) — the artifact is not self-consistent"
        )


def load_residency_probe_result(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise ResidencyProbeError(f"residency probe result not found: {p}")
    obj = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ResidencyProbeError(
            f"probe result must be a JSON object, got {type(obj).__name__}"
        )
    validate_residency_probe_result(obj)
    return obj


def load_committed_residency_probe_result() -> dict[str, Any]:
    """Load THE committed 0041 probe result — archive-first per the
    evidence-path convention (pins target ``specs/.archive/`` from authoring;
    the live path is the explicit fallback while the spec is unarchived)."""
    root = Path(__file__).resolve().parents[2]
    archived = (
        root / "specs" / ".archive" / "0041-gates"
        / "residency_probe" / "probe_result.json"
    )
    live = root / "specs" / "0041-gates" / "residency_probe" / "probe_result.json"
    return load_residency_probe_result(archived if archived.is_file() else live)


def run_residency_probe(
    *,
    api_base: str = "http://127.0.0.1:11434",
    model: str | None = None,
    keep_alive_bound_s: float = 300,
    resolver: Any = None,
) -> dict[str, Any]:
    """The live probe procedure (AC7): one bounded-``keep_alive`` native touch
    against a resident model, judged ONLY from ``/api/ps`` ``expires_at``
    movement. Loopback-asserted first (the 0019 rule). Returns a validated
    ``0041/residency-probe/1`` result — the caller (the committed operator
    driver) persists it."""
    import urllib.request

    from harpyja.gateway.gateway import assert_local

    assert_local(api_base, resolver=resolver)

    def _ps() -> dict[str, str]:
        with urllib.request.urlopen(f"{api_base}/api/ps", timeout=10) as r:  # noqa: S310
            return {
                m["name"]: m.get("expires_at", "")
                for m in json.loads(r.read())["models"]
            }

    residents = _ps()
    if model is None:
        if not residents:
            raise ResidencyProbeError(
                "no resident model to probe — load one (or pass model=) so the "
                "touch has a pinned expiry to move"
            )
        model = next(iter(residents))
    if model not in residents:
        raise ResidencyProbeError(
            f"model {model!r} is not resident — the probe judges expires_at "
            "MOVEMENT and needs a pinned before-state (load the model first)"
        )
    expires_before = residents[model]
    touched_at = _dt.datetime.now(_dt.UTC).isoformat()
    payload = json.dumps({"model": model, "keep_alive": keep_alive_bound_s}).encode(
        "utf-8"
    )
    req = urllib.request.Request(
        f"{api_base}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120):  # noqa: S310
        pass
    expires_after = _ps().get(model, "")
    result = {
        "schema_version": RESIDENCY_PROBE_SCHEMA_VERSION,
        "endpoint": api_base,
        "model": model,
        "keep_alive_bound_s": keep_alive_bound_s,
        "touched_at": touched_at,
        "expires_at_before": expires_before,
        "expires_at_after": expires_after,
        "outcome": judge_residency_outcome(
            expires_at_before=expires_before,
            expires_at_after=expires_after,
            touched_at=touched_at,
            keep_alive_bound_s=keep_alive_bound_s,
        ),
    }
    validate_residency_probe_result(result)
    return result


def assert_residency_wiring_matches_committed_outcome(
    *, touch_enabled: bool, committed: dict[str, Any]
) -> None:
    """The loud-FAIL tripwire: the driver's touch-enabled state must agree
    with the committed probe outcome — fails on drift, never skips."""
    validate_residency_probe_result(committed)
    honored = committed["outcome"] == "touch-rebounds"
    if touch_enabled != honored:
        raise ResidencyProbeError(
            "wiring↔evidence drift: driver touch_enabled="
            f"{touch_enabled} but the committed probe outcome is "
            f"{committed['outcome']!r} — reconcile the wiring with the "
            "recorded evidence (never wire a mechanism the evidence does not back)"
        )
