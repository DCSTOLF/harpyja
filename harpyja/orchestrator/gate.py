"""Verification Gate (spec 0008, AC10/AC11).

The gate reads the cited lines back from disk and scores their relevance to the
query, then decides `passed = score >= verify_threshold`. It is the signal that
governs Tier-1 → Tier-2 escalation in `mode=auto`.

Design notes:
- **Bounded top-N.** Only the top `verify_top_n` ranked citations are scored — a
  generative `scout_model` judge over an unbounded set would put a
  result-set-sized model cost on the hot path. The dropped count is logged so a
  bounded scan is never indistinguishable from a full one (no-silent-truncation).
- **Air-gap (one helper, belt-and-suspenders).** The gate is in-house orchestrator
  code, so its judge call routes through `ModelGateway.complete()` (the only
  outbound caller, which already air-gaps at resolution time). The gate
  *additionally* calls `gateway.assert_local()` **before** the judge as an explicit
  pre-check — still the one helper, no parallel air-gap type. A non-loopback
  endpoint is a loud `AirGapError` floor, never a degrade, and the judge is never
  called.
- **Scoring failure never blocks.** If the judge (or a cited-line read-back) raises,
  the gate maps it to `GateOutcome.failed=True` and `passed=False` — it never lets
  the exception escape and never silently passes. The orchestrator treats a failed
  gate as a gate-fail for routing (escalates in `auto` if a tier remains) and
  attaches the stable `gate-scoring-failed` flag.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from harpyja.config.settings import Settings
from harpyja.gateway.gateway import ModelGateway
from harpyja.server.types import Citation

logger = logging.getLogger(__name__)

# A judge scores how well a cited span answers the query, on a normalized [0,1].
Judge = Callable[[str, str], float]


@dataclass
class GateOutcome:
    passed: bool
    score: float
    scored_count: int
    dropped_count: int
    failed: bool


def _read_cited_lines(repo_path: str, citation: Citation) -> str:
    """Read the cited span back from disk (1-indexed, inclusive)."""
    path = Path(repo_path) / citation.path
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(citation.start_line - 1, 0)
    end = citation.end_line
    return "\n".join(lines[start:end])


def make_scout_model_judge(gateway: ModelGateway, settings: Settings) -> Judge:
    """Default judge: reuse the loaded `scout_model` to rate span relevance (OQ1).

    Routes through the single outbound caller (`ModelGateway.complete`) and parses
    a normalized [0,1] score from the reply. Kept tiny; unit tests inject a fake
    judge instead of reaching a model.
    """

    def judge(query: str, cited_text: str) -> float:
        messages = [
            {
                "role": "system",
                "content": (
                    "You score how well a code span answers a search query. "
                    "Reply with a single number between 0 and 1."
                ),
            },
            {"role": "user", "content": f"Query: {query}\n\nCited span:\n{cited_text}\n\nScore:"},
        ]
        reply = gateway.complete(messages, model=settings.scout_model, temperature=0)
        return _parse_score(reply)

    return judge


def _parse_score(reply: str) -> float:
    """Pull the first float out of a model reply; clamp to [0,1]."""
    import re

    match = re.search(r"[0-9]*\.?[0-9]+", reply)
    if not match:
        return 0.0
    return max(0.0, min(1.0, float(match.group())))


class VerificationGate:
    def __init__(self, gateway: ModelGateway, judge: Judge | None = None) -> None:
        self.gateway = gateway
        self._judge = judge

    def verify(
        self,
        query: str,
        citations: list[Citation],
        *,
        repo_path: str,
        settings: Settings,
    ) -> GateOutcome:
        # Air-gap floor first — before any judge work. A non-loopback endpoint
        # raises AirGapError and nothing is scored.
        self.gateway.assert_local()

        top = citations[: settings.verify_top_n]
        dropped = len(citations) - len(top)
        if dropped > 0:
            logger.info(
                "verification gate scoring top %d of %d citations (%d dropped)",
                len(top),
                len(citations),
                dropped,
            )

        judge = self._judge or make_scout_model_judge(self.gateway, settings)
        scores: list[float] = []
        try:
            for citation in top:
                cited_text = _read_cited_lines(repo_path, citation)
                scores.append(judge(query, cited_text))
        except Exception:
            # The gate cannot vouch — never raise, never silently pass.
            logger.warning("verification gate scoring failed", exc_info=True)
            return GateOutcome(
                passed=False,
                score=0.0,
                scored_count=len(scores),
                dropped_count=dropped,
                failed=True,
            )

        # Aggregate: the best cited span carries the verdict — one strongly
        # relevant citation is enough for a locate answer to be trustworthy.
        score = max(scores) if scores else 0.0
        return GateOutcome(
            passed=score >= settings.verify_threshold,
            score=score,
            scored_count=len(top),
            dropped_count=dropped,
            failed=False,
        )
