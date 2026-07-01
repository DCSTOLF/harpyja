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
import re
import socket
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError

from harpyja.config.settings import Settings
from harpyja.gateway.gateway import ModelGateway
from harpyja.server.types import Citation

logger = logging.getLogger(__name__)

# A judge scores how well a cited span answers the query, on a normalized [0,1].
Judge = Callable[[str, str], float]


class ScoreParseError(ValueError):
    """The judge reply did not conform to a bare [0,1] score (spec 0018 / D2).

    Raised by a judge when :func:`_parse_score` returns ``None`` so the gate's
    existing ``except`` degrades (``failed=True``) instead of the judge fabricating
    a score from noise (the 0015/B2 harm — a line number clamped to ``1.0`` or a
    chatty reply misread). :meth:`VerificationGate.verify` names this cause with a
    distinct WARNING (D4), separable from a timeout (0017) or a read-back failure.
    """


# Spec 0018 (B2 fix / D2): a *conforming* judge reply is a bare score in [0,1] —
# an optional case-insensitive `Score:` label and a single trailing period tolerated,
# but nothing else (no prose, no line numbers). Anchored + single-match so a reply
# like "…at line 219…" or "0, because…" cannot smuggle a number past the parse.
_SCORE_RE = re.compile(
    r"^\s*(?:score\s*:\s*)?(\d+(?:\.\d*)?|\.\d+)\s*\.?\s*$",
    re.IGNORECASE,
)


@dataclass
class GateOutcome:
    passed: bool
    score: float
    scored_count: int
    dropped_count: int
    failed: bool
    # Spec 0011: a third state, distinct from passed/failed. Set to "no-line-range"
    # when a file-level (line-less) citation reached the gate — it has no lines to
    # read back, so it is NOT scored and NOT a verified pass; the orchestrator maps
    # this to the stable `gate-skipped:no-line-range` marker. Additive (last).
    skipped_reason: str | None = None


def _read_cited_lines(repo_path: str, citation: Citation) -> str:
    """Read the cited span back from disk (1-indexed, inclusive)."""
    path = Path(repo_path) / citation.path
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(citation.start_line - 1, 0)
    end = citation.end_line
    return "\n".join(lines[start:end])


def make_scout_model_judge(gateway: ModelGateway, settings: Settings) -> Judge:
    """Retained non-default judge (spec 0018 / D3, D5): rate span relevance with the
    OOD finder `scout_model`.

    Kept behind `verify_method="scout_model"` as the finder-vs-instruct A/B baseline;
    `make_instruct_judge` (over `lm_model`) is the default. Routes through the single
    outbound caller (`ModelGateway.complete`) and shares the strict
    :func:`_score_or_raise` so a non-conforming reply degrades identically (AC13) —
    never the old fabricating parse. Unit tests inject a fake judge instead of a model.
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
        return _score_or_raise(reply)

    return judge


def make_instruct_judge(gateway: ModelGateway, settings: Settings) -> Judge:
    """Default judge (spec 0018 / D1): rate span relevance with the instruct `lm_model`.

    Replaces the OOD `scout_model` finder (which false-rejected correct citations —
    0015/B2) with `settings.lm_model`, a served instruction-following model that is
    in-distribution for "rate 0.0–1.0". The prompt demands a **bare** number so the
    strict :func:`_parse_score` can enforce it; a non-conforming reply raises
    :class:`ScoreParseError` so the gate degrades rather than fabricating a score.
    Routes through the single outbound caller (`ModelGateway.complete`), which
    `assert_local`s before any egress — the air-gap is inherited, not re-implemented.
    """

    def judge(query: str, cited_text: str) -> float:
        messages = [
            {
                "role": "system",
                "content": (
                    "You rate how well a code span answers a search query, on a scale "
                    "from 0.0 to 1.0 (0 = irrelevant, 1 = exactly answers it). "
                    "Reply with only the number — no words, no explanation."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Query: {query}\n\nCited span:\n{cited_text}\n\n"
                    "Score (only a number between 0 and 1):"
                ),
            },
        ]
        reply = gateway.complete(messages, model=settings.lm_model, temperature=0)
        return _score_or_raise(reply)

    return judge


def _score_or_raise(reply: str) -> float:
    """Strict-parse ``reply`` to a [0,1] score, or raise :class:`ScoreParseError`.

    Shared by both judge factories (spec 0018 / AC13) so a non-conforming reply
    degrades identically — never a fabricated score — whichever judge is selected.
    """
    score = _parse_score(reply)
    if score is None:
        raise ScoreParseError(f"non-conforming judge reply (not a bare [0,1] score): {reply!r}")
    return score


# Spec 0018 (D3): `verify_method` selects the judge factory. Co-located with the
# factories (not in wiring) so the production builder and the `verify()` fallback
# share one source of truth. `verify_method` is validated at Settings load, so a
# lookup miss here would be an internal invariant break, not user input.
_JUDGE_FACTORIES: dict[str, Callable[[ModelGateway, Settings], Judge]] = {
    "scout_model": make_scout_model_judge,
    "instruct_model": make_instruct_judge,
}


def select_judge(gateway: ModelGateway, settings: Settings) -> Judge:
    """Build the judge for `settings.verify_method` (default `instruct_model`)."""
    return _JUDGE_FACTORIES[settings.verify_method](gateway, settings)


def _parse_score(reply: str) -> float | None:
    """Parse a strict [0,1] score from a judge reply, or ``None`` if non-conforming.

    Spec 0018 (B2 fix / D2): the old parser grabbed the *first number anywhere* and
    clamped, so a line number ("…at line 219…") became a fabricated ``1.0`` pass and
    prose smuggled arbitrary scores. This is strict: the whole reply must be a bare
    score in ``[0,1]`` (an optional ``Score:`` label and a single trailing period
    tolerated). Anything else — an out-of-range number, a line number, prose after the
    number, or no number — returns ``None`` so the caller degrades instead of
    fabricating (prefer escalate-on-ambiguity over reject; the 0015 harm was false
    rejection).
    """
    match = _SCORE_RE.match(reply)
    if not match:
        return None
    value = float(match.group(1))
    if 0.0 <= value <= 1.0:
        return value
    return None


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

        # Spec 0011: a file-level (line-less) citation has no lines to read back —
        # detect it BEFORE any read-back (which would crash on `None` lines) and
        # treat it as not-verifiable, not a verified pass. Only lined citations are
        # scored; the marker records that a coarse span was present.
        lined = [c for c in top if not c.is_file_level]
        skipped_reason = "no-line-range" if any(c.is_file_level for c in top) else None

        judge = self._judge or select_judge(self.gateway, settings)
        scores: list[float] = []
        try:
            for citation in lined:
                cited_text = _read_cited_lines(repo_path, citation)
                scores.append(judge(query, cited_text))
        except Exception as err:
            # The gate cannot vouch — never raise, never silently pass. The degrade
            # cause is named distinctly so operators can separate them (the 0014
            # typed-degrade visibility convention); each failure logs EXACTLY ONE
            # WARNING (no double-emit). No schema change — log only.
            # Spec 0018 (B2 / D4): a non-conforming judge reply (ScoreParseError) —
            # checked FIRST because it is a ValueError and would otherwise fall through
            # to the generic branch.
            if isinstance(err, ScoreParseError):
                logger.warning("verification gate score parse non-conforming: %r", err)
            # Spec 0017 (B3 / D4): a stalled-model timeout.
            elif isinstance(err, (TimeoutError, socket.timeout, URLError)):
                logger.warning("verification gate judge timed out: %r", err, exc_info=True)
            else:
                logger.warning("verification gate scoring failed", exc_info=True)
            return GateOutcome(
                passed=False,
                score=0.0,
                scored_count=len(scores),
                dropped_count=dropped,
                failed=True,
                skipped_reason=skipped_reason,
            )

        # Aggregate: the best cited span carries the verdict — one strongly
        # relevant citation is enough for a locate answer to be trustworthy. A
        # pure file-level top scores nothing → passed=False (not-verifiable).
        score = max(scores) if scores else 0.0
        return GateOutcome(
            passed=score >= settings.verify_threshold,
            score=score,
            scored_count=len(lined),
            dropped_count=dropped,
            failed=False,
            skipped_reason=skipped_reason,
        )
