"""The bounded explorer loop (spec 0024, AC4/AC5).

A general tool-calling model is driven over the three read-only navigation tools
to a terminal `submit_citations` action. The loop is model-agnostic and, in unit
tests, driven by a fake model-call callable (no gateway, no network).

Termination is doubly bounded (turns ≠ time for a general model):
- ``scout_max_turns`` — the turn cap; a non-terminating model is killed here and
  never hangs.
- ``scout_wall_clock_s`` — the whole-loop wall-clock ceiling (via an injectable
  monotonic clock); one slow/hung turn cannot wedge the loop.

Self-recovery keeps a stuck/verbose model from wedging or flooding context:
- **Loop detection** — an exact ``(tool_name, normalized_args)`` call repeated for
  ``scout_loop_repeat_n`` consecutive turns WITHOUT adding a new span injects a
  corrective note.
- **Citation-preserving truncation** — when history exceeds
  ``scout_history_char_cap``, the oldest bulky navigational observations are
  dropped, but their locations are re-injected as a compact index. The binding
  invariant: truncation drops only stale chatter and NEVER converts a real find
  into honest-empty — a location once observed stays citable.

Messages sent to the model carry ONLY OpenAI-valid keys; the loop's bookkeeping
(spans per observation, record kind) is held in a parallel `records` list, so no
private field ever crosses the gateway.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from harpyja.gateway.gateway import AirGapError
from harpyja.scout.confidence_gate import (
    CONFIDENCE_SIGNAL,
    build_confidence_nudge,
    qualifying_symbols_spans,
)
from harpyja.scout.submit import SubmitResult
from harpyja.server.types import CodeSpan
from harpyja.symbols.ripgrep import RipgrepMissingError

# Terminal outcomes.
SUBMITTED = "submitted"
TURNS_EXHAUSTED = "turns-exhausted"
WALLCLOCK_EXHAUSTED = "wallclock-exhausted"
# Spec 0028 (AC3): the model's generation hit the max_tokens cap (finish=length) —
# a truncated turn, mapped downstream to the `generation-truncated` degrade cause.
GENERATION_TRUNCATED = "generation-truncated"

SUBMIT_TOOL = "submit_citations"

_INDEX_PREFIX = "Previously observed locations (evidence retained): "
_CORRECTIVE = (
    "That tool call was unproductive — repeated with no new results. "
    "Try a different query, tool, or scope."
)

ModelCall = Callable[[list[dict[str, Any]]], Mapping[str, Any]]
Clock = Callable[[], float]


@dataclass
class LoopResult:
    outcome: str
    spans: list[CodeSpan] | None
    turns_used: int
    history: list[dict[str, Any]] = field(default_factory=list)
    # Spec 0033: the submit seam's submitted-vs-surviving counts, threaded so a
    # found-then-dropped submission (1, 0) never reads as honest-empty (0, 0).
    # None on non-submit terminals (exhaustion/truncation — nothing was submitted).
    citations_submitted: int | None = None
    citations_surviving: int | None = None
    # Spec 0044: the confidence-conditioned nudge facts (AC3) — whether the
    # evidence gate fired, which signal, on which turn, and the triggering
    # spans (as plain dicts, so the eval-side wrong-span attribution can judge
    # them against gold via the ONE oracle without re-parsing history).
    confidence_fired: bool = False
    confidence_triggering_signal: str | None = None
    confidence_firing_turn: int | None = None
    confidence_firing_spans: list[dict[str, Any]] | None = None


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


def _spans_of(result: Any) -> list[CodeSpan]:
    """Extract the citable locations a tool result carries (grep/glob list, read dict)."""
    spans: list[CodeSpan] = []
    if isinstance(result, list):
        for item in result:
            path = getattr(item, "path", None)
            if path is None:
                continue
            spans.append(
                item
                if isinstance(item, CodeSpan)
                else CodeSpan(
                    path=path,
                    start_line=getattr(item, "start_line", None),
                    end_line=getattr(item, "end_line", None),
                )
            )
    elif isinstance(result, Mapping) and result.get("path"):
        spans.append(
            CodeSpan(
                path=result["path"],
                start_line=result.get("start"),
                end_line=result.get("end"),
            )
        )
    return spans


def _loc_key(s: CodeSpan) -> tuple[str, int | None, int | None]:
    return (s.path, s.start_line, s.end_line)


def _loc_str(s: CodeSpan) -> str:
    return f"{s.path}:{s.start_line}" if s.start_line is not None else s.path


def _answer_tool_call(
    call: Mapping[str, Any],
    tools: Mapping[str, Callable[..., Any]],
    submit: Callable[[Sequence[Mapping[str, Any]]], SubmitResult],
    session: _Session,
    settings: Any,
) -> LoopResult | None:
    """Answer a single tool call. Returns a LoopResult if terminal (submit_citations),
    else None to continue to the next call in the batch."""
    fn = call.get("function", {})
    name = fn.get("name")
    args = _parse_arguments(fn.get("arguments"))
    call_id = call.get("id", "")

    if name == SUBMIT_TOOL:
        res = submit(args.get("citations", []))
        return LoopResult(  # type: ignore
            SUBMITTED,
            res.spans,
            None,
            session.messages(),
            citations_submitted=res.submitted,
            citations_surviving=res.surviving,
        )

    if name not in tools:
        session.add(
            {
                "role": "tool",
                "tool_call_id": call_id,
                "content": f"error: unknown tool {name!r}; "
                f"available: {sorted(tools)} or {SUBMIT_TOOL}",
            },
            "control",
        )
        return None

    try:
        result = tools[name](**args)
    except (RipgrepMissingError, AirGapError):
        # Floor exceptions (Tier-0 / air-gap) are never degraded; they propagate
        # to the backend as-is for tier-0 floor handling.
        raise
    except Exception as e:
        # Per-call degrade (spec 0029, AC2): tool failure recorded with stable marker;
        # batch continues to the next call instead of aborting the turn.
        session.add(
            {
                "role": "tool",
                "tool_call_id": call_id,
                "content": f"tool-call-degraded:execution-error: {type(e).__name__}: {str(e)}",
            },
            "control",
        )
        return None

    spans = _spans_of(result)
    session.add(
        {"role": "tool", "tool_call_id": call_id, "content": str(result)},
        "tool",
        spans=spans,
    )

    # Spec 0044 (the live operating point): the confidence gate watches RAW
    # symbols results only. A qualifying result is STASHED here and injected
    # strictly POST-BATCH by run_explorer_loop (0029: never interleave a message
    # inside an answer-all-N batch). Fires at most once per case.
    # NOTE: spec 0045's REFINED require-corroboration ranking
    # (`qualifying_confidence_spans`) was measured and typed TRADES_DIRECTIONS
    # (it cut silence->wrong-confidence 5->1 but reopened found-but-unsubmitted
    # 1->8), so it is RETIRED — the loop is restored to 0044's gate (net +2).
    if (
        name == "symbols"
        and not session.confidence_fired
        and session.pending_confidence is None
    ):
        qualifying = qualifying_symbols_spans(result)
        if qualifying:
            session.pending_confidence = qualifying

    # Loop detection: an exact repeat with no new span for N consecutive turns.
    session.note_navigation(name, args, spans)
    if session.repeat >= settings.scout_loop_repeat_n:
        session.add({"role": "user", "content": _CORRECTIVE}, "control")
        session.repeat = 0

    return None


class _Session:
    """Mutable loop bookkeeping kept OUT of the wire messages."""

    def __init__(self, context_map: str) -> None:
        self.records: list[dict[str, Any]] = [
            {"msg": {"role": "user", "content": context_map}, "kind": "map"}
        ]
        self.seen: set[tuple[str, int | None, int | None]] = set()
        self.last_key: str | None = None
        self.repeat = 0
        self.dropped: list[CodeSpan] = []
        self.index_pos: int | None = None
        # Spec 0044: confidence-nudge state — a qualifying symbols result is
        # stashed mid-batch and injected post-batch; fired-at-most-once.
        self.pending_confidence: list[CodeSpan] | None = None
        self.confidence_fired = False
        self.confidence_firing_turn: int | None = None
        self.confidence_spans: list[CodeSpan] | None = None

    def messages(self) -> list[dict[str, Any]]:
        return [r["msg"] for r in self.records]

    def add(self, msg: dict[str, Any], kind: str, **extra: Any) -> None:
        self.records.append({"msg": msg, "kind": kind, **extra})

    def _total_chars(self) -> int:
        # Skip in-flight tombstones: maybe_truncate re-reads the total between
        # drops, and with ≥2 droppable observations a None is present mid-pass.
        return sum(
            len(str(r["msg"].get("content", "")))
            for r in self.records
            if r is not None
        )

    def note_navigation(self, name: str, args: dict[str, Any], spans: list[CodeSpan]) -> None:
        """Update loop-detection state; the caller reads ``self.repeat``.

        A repeat is an exact ``(tool_name, normalized_args)`` match to the previous
        navigation call that produced NO new span; anything else resets the run.
        """
        new = [s for s in spans if _loc_key(s) not in self.seen]
        for s in spans:
            self.seen.add(_loc_key(s))
        key = f"{name}:{json.dumps(args, sort_keys=True)}"
        if key == self.last_key and not new:
            self.repeat += 1
        else:
            self.repeat = 1
            self.last_key = key

    def maybe_truncate(self, cap: int) -> None:
        if self._total_chars() <= cap:
            return
        # Drop the OLDEST 'tool' observations (stale navigational chatter), never the
        # most recent one and never the map/index/control records.
        tool_positions = [i for i, r in enumerate(self.records) if r["kind"] == "tool"]
        droppable = tool_positions[:-1]  # keep the newest observation
        for pos in droppable:
            if self._total_chars() <= cap:
                break
            rec = self.records[pos]
            self.dropped.extend(rec.get("spans", []))
            self.records[pos] = None  # tombstone; compacted below
        self.records = [r for r in self.records if r is not None]
        if self.dropped:
            self._refresh_index()

    def _refresh_index(self) -> None:
        # A single compact index of every dropped location, re-injected right after
        # the map so a truncated-but-citable observation is never lost.
        seen_locs: list[str] = []
        for s in self.dropped:
            loc = _loc_str(s)
            if loc not in seen_locs:
                seen_locs.append(loc)
        content = _INDEX_PREFIX + ", ".join(seen_locs)
        for r in self.records:
            if r["kind"] == "index":
                r["msg"]["content"] = content
                return
        self.records.insert(1, {"msg": {"role": "user", "content": content}, "kind": "index"})


def _stamp_confidence(result: LoopResult, session: _Session) -> LoopResult:
    """Thread the 0044 confidence facts onto a terminal LoopResult."""
    result.confidence_fired = session.confidence_fired
    if session.confidence_fired:
        result.confidence_triggering_signal = CONFIDENCE_SIGNAL
        result.confidence_firing_turn = session.confidence_firing_turn
        result.confidence_firing_spans = [
            {"path": s.path, "start_line": s.start_line, "end_line": s.end_line}
            for s in session.confidence_spans or []
        ]
    return result


def run_explorer_loop(
    *,
    model_call: ModelCall,
    tools: Mapping[str, Callable[..., Any]],
    submit: Callable[[Sequence[Mapping[str, Any]]], SubmitResult],
    context_map: str,
    settings: Any,
    clock: Clock = time.monotonic,
) -> LoopResult:
    """Drive the bounded loop to a terminal citation list (or a bounded stop)."""
    session = _Session(context_map)
    start = clock()
    turns_used = 0

    for _ in range(settings.scout_max_turns):
        if clock() - start >= settings.scout_wall_clock_s:
            return _stamp_confidence(
                LoopResult(WALLCLOCK_EXHAUSTED, None, turns_used, session.messages()),
                session,
            )

        turns_used += 1
        response = model_call(session.messages())
        # Spec 0028 (AC3): a max_tokens-capped generation (finish=length) is a
        # truncation, NEVER the success path — even if a syntactically valid
        # tool_call rode along, its args may be silently incomplete. Bail before any
        # tool dispatch so a truncated turn degrades instead of being mis-read.
        if response.get("finish_reason") == "length":
            return _stamp_confidence(
                LoopResult(GENERATION_TRUNCATED, None, turns_used, session.messages()),
                session,
            )
        session.add(
            {
                "role": "assistant",
                "content": response.get("content") or "",
                "tool_calls": list(response.get("tool_calls") or []),
            },
            "assistant",
        )

        tool_calls = response.get("tool_calls") or []
        if not tool_calls:
            session.add({"role": "user", "content": "Call one of the available tools."}, "control")
            continue

        # spec 0029: iterate ALL tool_calls (N parallel calls) in order, answering each.
        # Terminal (submit_citations) at any position returns immediately.
        # Per-call degrade: tool failure recorded with stable marker; batch continues.
        for call in tool_calls:
            result = _answer_tool_call(call, tools, submit, session, settings)
            if result is not None:
                # Terminal (submit_citations) was encountered; return immediately.
                result.turns_used = turns_used
                return _stamp_confidence(result, session)

        # Spec 0044: the confidence-conditioned nudge, injected strictly at the
        # POST-BATCH boundary (0029: every tool_call_id above is answered; a
        # message inside the batch would be a malformed conversation). Evidence-
        # gated ONLY — no turn/time fallback — and fired at most once per case.
        # The record kind "confidence-nudge" is never tombstoned by
        # maybe_truncate (which drops only bulky "tool" observations) and never
        # enters note_navigation, so loop-detection and turn accounting are
        # untouched.
        if session.pending_confidence and not session.confidence_fired:
            session.add(
                build_confidence_nudge(session.pending_confidence),
                "confidence-nudge",
            )
            session.confidence_fired = True
            session.confidence_firing_turn = turns_used
            session.confidence_spans = session.pending_confidence
            session.pending_confidence = None

        # Context management: citation-preserving truncation past the bloat cap.
        session.maybe_truncate(settings.scout_history_char_cap)

    return _stamp_confidence(
        LoopResult(TURNS_EXHAUSTED, None, turns_used, session.messages()), session
    )
