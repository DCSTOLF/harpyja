"""Deep (Tier 2) failure taxonomy.

`DeepUnavailable` is the one *degradable* failure: the RLM/sandbox could not run,
so the orchestrator falls back to **Scout best-effort** (Tier 1) with a confidence
flag. It carries a **stable** ``cause`` so distinct causes get distinct
caller-visible notes (`deep-degraded:<cause>`).

Deliberately NOT modelled as `DeepUnavailable`:
- a **budget truncation** (depth/sub-queries/tool-calls/tokens/wall-clock) — that
  is an honest, bounded Tier-2 result carrying a `deep-truncated:<bound>` note,
  not a degrade (treating it as one would be an ungated escalation);
- `RipgrepMissingError` (Tier-0 seed precondition) and `AirGapError` (non-loopback
  endpoint) — those propagate loudly as the degradation floor.
"""

from __future__ import annotations

# Stable cause identifiers used to build `deep-degraded:<cause>` notes.
SANDBOX_ABSENT = "sandbox-absent"
RLM_DOWN = "rlm-down"
BACKEND_ERROR = "backend-error"
# A *named, narrow-caught* parse failure at the dspy adapter seam earns its own
# cause (spec 0014): we can name and pin this exception class against source, so
# it is distinct from the BACKEND_ERROR catch-all, which still absorbs every
# *unforeseen* backend exception. Sibling, not a replacement.
PARSE_ERROR = "parse-error"


class DeepUnavailable(RuntimeError):
    """Tier 2 could not produce an answer; the caller should degrade to Scout."""

    def __init__(self, cause: str) -> None:
        super().__init__(f"deep unavailable: {cause}")
        self.cause = cause
