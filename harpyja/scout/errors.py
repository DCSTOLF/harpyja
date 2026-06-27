"""Scout failure taxonomy.

`ScoutUnavailable` is the one *degradable* failure: the model path could not be
reached or the backend failed, so the orchestrator falls back to Tier 0 with a
confidence flag. It carries a **stable** ``cause`` identifier so distinct causes
get distinct caller-visible notes (conventions: distinct failure causes →
distinct notes).

Two failures are deliberately NOT modelled here because they must NOT degrade:
- `RipgrepMissingError` — a Tier-0 hard precondition is absent; it propagates
  loudly (the degradation floor).
- `AirGapError` — a non-loopback endpoint is a floor violation, not a degrade.
"""

from __future__ import annotations

# Stable cause identifiers used to build `scout-degraded:<cause>` notes.
CONNECTION_REFUSED = "connection-refused"
NO_ENDPOINT_CONFIGURED = "no-endpoint-configured"
BACKEND_ERROR = "backend-error"
# Spec 0007 — the default-client install/discovery causes. `fastcontext-missing`
# is terminal only when no CLI fallback is wired; `cli-missing` when the package
# is absent AND `fastcontext` is not on PATH (the four-way split stays distinct).
FASTCONTEXT_MISSING = "fastcontext-missing"
CLI_MISSING = "cli-missing"


class ScoutUnavailable(RuntimeError):
    """Scout could not produce an answer; the caller should degrade to Tier 0."""

    def __init__(self, cause: str) -> None:
        super().__init__(f"scout unavailable: {cause}")
        self.cause = cause
