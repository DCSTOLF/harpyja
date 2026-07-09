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
                "description": "List the symbols (functions, classes, types, etc.) defined in a file.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
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
        # Track the served model from the last response for trajectory capture
        self._last_served_model: str | None = None

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

        def submit(citations: Sequence[Mapping[str, Any]]) -> SubmitResult:
            return submit_citations(citations, self._repo_path, self._settings)

        model_call = self._model_call or self._default_model_call()

        # Spec 0031 (live): wrap any model_call to track served_model for trajectory
        # capture. This works for both injected and default calls.
        def wrapped_model_call(messages: list[dict[str, Any]]) -> Mapping[str, Any]:
            response = model_call(messages)
            self._last_served_model = response.get("model")
            return response

        try:
            result = run_explorer_loop(
                model_call=wrapped_model_call,
                tools=tools,
                submit=submit,
                context_map=context_map,
                settings=self._settings,
                clock=self._clock,
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
        )

        if result.outcome == SUBMITTED:
            # Honest-empty (a well-formed empty submission) returns [] — NOT a degrade.
            return result.spans or []
        # Loop stopped with no citation → typed degrade to the Tier-0 floor.
        raise ScoutUnavailable(_EXHAUSTION_CAUSE[result.outcome])
