"""`ExplorerBackend` — the native explorer-loop `ScoutBackend` impl (spec 0024).

This replaces the retired FastContext adapter behind the UNCHANGED `ScoutBackend`
seam (`run(query, seed) -> list[CodeSpan]`). It assembles the pre-model context
map, the three read-only navigation tools, and the `submit_citations` terminal
action, then drives a general tool-calling model over them via the loopback
`ModelGateway`.

Air-gap: `gateway.assert_local()` fires ONCE before the loop starts — a
non-loopback endpoint raises `AirGapError` (a floor, never a degrade) and the loop
never begins. In unit tests a fake `model_call` is injected, so the loop is driven
deterministically with no network; the air-gap assertion still runs.

Degradation (turn/wall-clock exhaustion, model unreachable, backend crash) is
mapped to typed `ScoutUnavailable` causes in spec 0024 T17/T18; a well-formed
empty submission is honest-empty and returns ``[]``.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from harpyja.config.settings import Settings
from harpyja.eval.live_verifier import build_trajectory_record
from harpyja.gateway.gateway import AirGapError
from harpyja.index.manifest import ManifestEntry
from harpyja.scout import errors
from harpyja.scout.confirm import confirm_before_submit, derive_submit_disposition
from harpyja.scout.context_map import build_initial_prompt
from harpyja.scout.errors import ScoutUnavailable
from harpyja.scout.explorer_loop import (
    GENERATION_TRUNCATED,
    SUBMITTED,
    TURNS_EXHAUSTED,
    WALLCLOCK_EXHAUSTED,
    run_explorer_loop,
)
from harpyja.scout.explorer_tools import build_explorer_tools
from harpyja.scout.submit import SubmitResult, submit_citations
from harpyja.server.types import CodeSpan
from harpyja.symbols.ripgrep import RipgrepMissingError

# The outcome→cause map for a loop that stopped WITHOUT a citation.
_EXHAUSTION_CAUSE = {
    TURNS_EXHAUSTED: errors.LOOP_TURNS_EXHAUSTED,
    WALLCLOCK_EXHAUSTED: errors.LOOP_WALLCLOCK_EXHAUSTED,
    GENERATION_TRUNCATED: errors.GENERATION_TRUNCATED,  # spec 0028 (AC3)
}


def derive_think_mode(think: bool | None, enable_thinking: bool) -> str:
    """The ONE canonical effective-thinking-mode label (spec 0034).

    Native (`think` explicitly set) wins over the chat-template mechanism so a
    double-set configuration can never produce an ambiguous record.
    """
    if think is True:
        return "native-think-true"
    if think is False:
        return "native-think-false"
    if enable_thinking is False:
        return "chat-template-disabled"
    if enable_thinking is True:
        return "default-omitted"
    return "unknown"


def _tool_schemas() -> list[dict[str, Any]]:
    """Minimal OpenAI function schemas for the five navigation tools + the terminal action."""
    return [
        {
            "type": "function",
            "function": {
                "name": "grep",
                "description": "Ripgrep the repo for a literal pattern.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string"},
                        "scope": {"type": "string"},
                    },
                    "required": ["pattern"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "glob",
                "description": "List repo files matching a glob pattern.",
                "parameters": {
                    "type": "object",
                    "properties": {"pattern": {"type": "string"}},
                    "required": ["pattern"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_span",
                "description": "Read a bounded line range from a repo file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "start": {"type": "integer"},
                        "end": {"type": "integer"},
                    },
                    "required": ["path", "start", "end"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "ls",
                "description": (
                    "List the immediate entries of one repo directory "
                    "(directories end with '/'); defaults to the repo root."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "symbols",
                # Spec 0042 (AC1-desc/AC3): the WHEN-to-use + citation-shaped-output
                # pitch, and `path` OPTIONAL so the repo-wide by-name lookup is
                # reachable before a candidate file is found.
                "description": (
                    "List the symbols (functions, classes, types) defined in a file "
                    "with their exact start/end line spans — the fastest way to turn "
                    "a candidate file into the precise file:line span to cite. Omit "
                    "path and pass name to look a symbol up by name across the repo "
                    "(use when the query's words are not greppable)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "name": {"type": "string"},
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "submit_citations",
                "description": "Submit the final file:line citations and end the search.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "citations": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string"},
                                    "start_line": {"type": "integer"},
                                    "end_line": {"type": "integer"},
                                },
                                "required": ["path"],
                            },
                        }
                    },
                    "required": ["citations"],
                },
            },
        },
    ]


class ExplorerBackend:
    def __init__(
        self,
        *,
        gateway: Any,
        repo_path: str,
        settings: Settings,
        manifest: Sequence[ManifestEntry],
        search_engine: Any,
        symbol_records: Sequence[Any] | None = None,
        model_call: Callable[[list[dict[str, Any]]], Mapping[str, Any]] | None = None,
        clock: Callable[[], float] = time.monotonic,
        max_tokens: int = 2048,
        enable_thinking: bool = True,
        think: bool | None = None,
    ) -> None:
        self._gateway = gateway
        self._repo_path = repo_path
        self._settings = settings
        self._manifest = manifest
        self._search_engine = search_engine
        self._symbol_records = symbol_records or []
        self._model_call = model_call
        self._clock = clock
        # Spec 0028 (AC2) — the per-call generation cap. The finite default lives HERE
        # (the explorer object's own field) so a direct `ExplorerBackend(...)` that
        # bypasses `Settings` is still bounded (DRIFT-GUARD); the wire site feeds it
        # `settings.explorer_max_tokens`. The gateway stays param-driven — the Deep
        # path never carries this cap.
        self._max_tokens = max_tokens
        # Spec 0028 (AC1) — the thinking knob. False ⇒ send
        # chat_template_kwargs={"enable_thinking": False}; True ⇒ omit it.
        self._enable_thinking = enable_thinking
        # Spec 0034 — the native think knob (tri-state). None ⇒ OMIT the param ⇒
        # the outbound request is byte-identical to pre-0034 (observability-only
        # default). True/False are operator opt-in generation control.
        self._think = think
        # Degrade-rate is a first-class reported field (the "every floor reports its
        # rate" convention): a run that raises ScoutUnavailable counts as a degrade;
        # a clean run — including an honest-empty submission — does not.
        self.run_count = 0
        self.degrade_count = 0
        # Spec 0025 (AC3): the per-run turns-USED count (model iterations consumed,
        # NOT the scout_max_turns cap), surfaced so the eval turns diagnostic reads
        # the explorer's native count instead of scraping a FastContext trajectory.
        # None until the first run; populated on submit AND on the exhaustion degrade
        # paths (whichever produced a LoopResult).
        self.last_turns_used: int | None = None
        # Spec 0031 (live): the per-run trajectory artifact (model turns + tool names).
        # None until the first run; captured after a successful run to support
        # trajectory-verified live measurement.
        self.last_trajectory: dict[str, Any] | None = None
        # Spec 0046 (AC3/AC4): the confirm-before-submit facts from the last run.
        # confirmation runs in the SUBMIT PATH (this backend seam), never the loop
        # (which stays confirmation-agnostic — the AC3a separation). Reset per run.
        self.last_confirmation_ran: bool = False
        self.last_confirmation_outcome: str | None = None
        self.last_submit_disposition: str | None = None
        self.last_reactive_triggers: list[str] = []
        # Track the served model from the last response for trajectory capture
        self._last_served_model: str | None = None
        # Spec 0034 — per-turn (reasoning_chars, completion_tokens, finish_reason)
        # accumulator: the ONE seam that sees every response, including a
        # finish="length" final turn that never enters the loop history.
        self._per_turn: list[dict[str, Any]] = []

    @property
    def degrade_rate(self) -> float:
        return self.degrade_count / self.run_count if self.run_count else 0.0

    def _default_model_call(self) -> Callable[[list[dict[str, Any]]], Mapping[str, Any]]:
        schemas = _tool_schemas()

        # Spec 0028 (AC1/AC2) — the explorer's generation-control params, assembled
        # once. `max_tokens` (the anti-runaway cap) is always sent; the thinking knob
        # adds `chat_template_kwargs` ONLY when thinking is disabled (omitted → on).
        params: dict[str, Any] = {"max_tokens": self._max_tokens}
        if not self._enable_thinking:
            params["chat_template_kwargs"] = {"enable_thinking": False}
        # Spec 0038 (reconciliation): the tri-state knob rides ONLY when
        # explicitly set — None omits everything and the request stays
        # byte-identical (the surviving 0034 pin). True/False route through the
        # PROBE-PROVEN honoring mechanism on this same /v1 transport:
        # `reasoning_effort` ("high" ⇒ thinking on, "none" ⇒ genuinely off at
        # generation level). The 0034 top-level `think` field is GONE — Ollama's
        # /v1 layer silently drops it (0037's committed no-op finding); a dead
        # field pretending to be a knob is the exact hole 0037 caught.
        # Evidence: specs/0038-reconciliation/probes/probe_result.json
        # (outcome=v1-variant, two-factor verdict).
        if self._think is not None:
            params["reasoning_effort"] = "high" if self._think else "none"

        def call(messages: list[dict[str, Any]]) -> Mapping[str, Any]:
            return self._gateway.complete_with_tools(messages, schemas, **params)

        return call

    def run(self, query: str, seed: list[CodeSpan]) -> list[CodeSpan]:
        # Air-gap FIRST — a non-loopback endpoint raises AirGapError before any
        # model I/O and the loop never starts (a floor, never a degrade — so this
        # is deliberately OUTSIDE the run/degrade accounting below).
        self._gateway.assert_local()

        self.run_count += 1
        self.last_turns_used = None  # reset per run
        self._last_served_model = None  # reset per run
        self._per_turn = []  # reset per run (spec 0034)
        # Spec 0046: reset the confirm-before-submit facts per run.
        self.last_confirmation_ran = False
        self.last_confirmation_outcome = None
        self.last_submit_disposition = None
        self.last_reactive_triggers = []
        try:
            return self._run_loop(query)
        except ScoutUnavailable:
            self.degrade_count += 1
            raise

    def _run_loop(self, query: str) -> list[CodeSpan]:
        # spec 0027: the eager whole-repo context map is REMOVED (push → pull). The
        # initial prompt is minimal (query + tool-usage framing, no repo listing); the
        # model discovers layout on demand via ls/glob/grep/symbols. `context_map` is still the
        # loop's initial-message param — now carrying the minimal prompt, not a repo map.
        context_map = build_initial_prompt(query)
        tools = build_explorer_tools(
            self._repo_path,
            self._settings,
            search_engine=self._search_engine,
            symbol_records=self._symbol_records,
            manifest=self._manifest,
        )

        # Spec 0046 (AC3): confirm-before-submit rides the SUBMIT PATH. The
        # interceptor reuses the EXISTING host-side read_span (no new registered
        # tool) to check the candidate span carries the query's intent; the
        # outcome (PASS / FAIL / CONFIRM_ERROR / NO_CANDIDATE) is stashed and, on
        # FAIL/CONFIRM_ERROR, the citation is still emitted (flagged), never
        # silenced. Gating the OUTPUT, not the ACTION.
        read_span_fn = tools["read_span"]
        confirmation: dict[str, Any] = {"ran": False, "outcome": None, "has_candidate": False}
        # Spec 0046 (Option A): the reactive + confirm levers are gated by ONE
        # explorer-scoped flag. Baseline arm (off): pure 0044 — no confirmation
        # runs (confirmation_outcome stays None => flagged-wrong-emitted == 0).
        reactive_confirm = bool(getattr(self._settings, "explorer_reactive_confirm", False))

        def submit(citations: Sequence[Mapping[str, Any]]) -> SubmitResult:
            res = submit_citations(citations, self._repo_path, self._settings)
            candidate = res.spans[0] if res.spans else None
            confirmation["has_candidate"] = candidate is not None
            if reactive_confirm and candidate is not None:
                confirmation["ran"] = True
                confirmation["outcome"] = confirm_before_submit(query, candidate, read_span_fn)
            return res

        # Spec 0046 (AC2): the reactive policy's hit-in-comment trigger reads
        # source text host-side via the same read_span (gold-blind: source, not
        # gold); one-line reads.
        def line_reader(path: str, line: int) -> str | None:
            try:
                r = read_span_fn(path, line, line)
            except Exception:
                return None
            return r.get("content") if isinstance(r, dict) else None

        model_call = self._model_call or self._default_model_call()

        # Spec 0031 (live): wrap any model_call to track served_model for trajectory
        # capture. This works for both injected and default calls.
        def wrapped_model_call(messages: list[dict[str, Any]]) -> Mapping[str, Any]:
            response = model_call(messages)
            self._last_served_model = response.get("model")
            reasoning = response.get("reasoning")
            self._per_turn.append({
                "reasoning_chars": len(reasoning) if reasoning is not None else None,
                "completion_tokens": response.get("completion_tokens"),
                "finish_reason": response.get("finish_reason"),
            })
            return response

        try:
            result = run_explorer_loop(
                model_call=wrapped_model_call,
                tools=tools,
                submit=submit,
                context_map=context_map,
                settings=self._settings,
                clock=self._clock,
                line_reader=line_reader,
                reactive_enabled=reactive_confirm,
            )
        except (RipgrepMissingError, AirGapError):
            raise  # Tier-0 / air-gap floors — never a degrade
        except ScoutUnavailable:
            raise  # already typed
        except OSError as err:
            # A transport/OS failure reaching the local endpoint.
            raise ScoutUnavailable(errors.MODEL_UNREACHABLE) from err
        except Exception as err:  # noqa: BLE001 - any loop/model crash → typed degrade
            raise ScoutUnavailable(errors.BACKEND_ERROR) from err

        # Record the native turns-USED count on every terminal path that produced a
        # LoopResult (submit and both exhaustion outcomes) — before any degrade raise,
        # so the migrated 0022 measurement survives exhausted runs too.
        self.last_turns_used = result.turns_used

        # Spec 0046 (AC3/AC4): finalize the confirm-before-submit facts. The
        # submit_disposition is derived from the reactive triggers (loop) + the
        # confirmation outcome (submit seam) + whether a candidate was submitted,
        # so a null is attributable across all five shapes.
        _outcome = confirmation["outcome"]
        self.last_confirmation_ran = confirmation["ran"]
        self.last_confirmation_outcome = str(_outcome) if _outcome is not None else None
        self.last_reactive_triggers = list(result.reactive_triggers_fired)
        self.last_submit_disposition = derive_submit_disposition(
            result.reactive_triggers_fired,
            _outcome,
            has_candidate=confirmation["has_candidate"],
        )

        # Spec 0031 (live): capture trajectory after the loop (before any degrade raise)
        # for trajectory-verified live measurement. The trajectory carries model_turns,
        # tool_names_invoked, and served_model; the harness will merge in tiers_run,
        # requested_model, and terminal_bucket.
        self.last_trajectory = build_trajectory_record(
            result.history,
            result.turns_used,
            served_model=self._last_served_model,
            endpoint=self._gateway.api_base,
            citations_submitted=result.citations_submitted,
            citations_surviving=result.citations_surviving,
            per_turn=list(self._per_turn),
            think_mode=derive_think_mode(self._think, self._enable_thinking),
            # Spec 0038: the explorer's ONE transport — /v1 chat/completions via
            # ModelGateway.complete_with_tools (the reconciled reasoning_effort
            # mechanism rides this same path; no per-value transport split).
            serving_transport="v1-chat-completions",
            # Spec 0044: the confidence-conditioned nudge facts from the loop.
            confidence_fired=result.confidence_fired,
            confidence_triggering_signal=result.confidence_triggering_signal,
            confidence_firing_turn=result.confidence_firing_turn,
            confidence_firing_spans=result.confidence_firing_spans,
            # Spec 0046: the reactive triggers (loop) + confirm-before-submit
            # facts (submit seam) — SUT-recorded, gold-blind.
            reactive_triggers_fired=result.reactive_triggers_fired,
            confirmation_ran=self.last_confirmation_ran,
            confirmation_outcome=self.last_confirmation_outcome,
            submit_disposition=self.last_submit_disposition,
        )

        if result.outcome == SUBMITTED:
            # Honest-empty (a well-formed empty submission) returns [] — NOT a degrade.
            return result.spans or []
        # Loop stopped with no citation → typed degrade to the Tier-0 floor.
        raise ScoutUnavailable(_EXHAUSTION_CAUSE[result.outcome])
