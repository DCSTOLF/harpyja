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
from harpyja.gateway.gateway import AirGapError
from harpyja.index.manifest import ManifestEntry
from harpyja.scout import errors
from harpyja.scout.context_map import build_context_map
from harpyja.scout.errors import ScoutUnavailable
from harpyja.scout.explorer_loop import (
    SUBMITTED,
    TURNS_EXHAUSTED,
    WALLCLOCK_EXHAUSTED,
    run_explorer_loop,
)
from harpyja.scout.explorer_tools import build_explorer_tools
from harpyja.scout.submit import submit_citations
from harpyja.server.types import CodeSpan
from harpyja.symbols.ripgrep import RipgrepMissingError

# The outcome→cause map for a loop that stopped WITHOUT a citation.
_EXHAUSTION_CAUSE = {
    TURNS_EXHAUSTED: errors.LOOP_TURNS_EXHAUSTED,
    WALLCLOCK_EXHAUSTED: errors.LOOP_WALLCLOCK_EXHAUSTED,
}


def _tool_schemas() -> list[dict[str, Any]]:
    """Minimal OpenAI function schemas for the three tools + the terminal action."""
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
        model_call: Callable[[list[dict[str, Any]]], Mapping[str, Any]] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._gateway = gateway
        self._repo_path = repo_path
        self._settings = settings
        self._manifest = manifest
        self._search_engine = search_engine
        self._model_call = model_call
        self._clock = clock
        # Degrade-rate is a first-class reported field (the "every floor reports its
        # rate" convention): a run that raises ScoutUnavailable counts as a degrade;
        # a clean run — including an honest-empty submission — does not.
        self.run_count = 0
        self.degrade_count = 0

    @property
    def degrade_rate(self) -> float:
        return self.degrade_count / self.run_count if self.run_count else 0.0

    def _default_model_call(self) -> Callable[[list[dict[str, Any]]], Mapping[str, Any]]:
        schemas = _tool_schemas()

        def call(messages: list[dict[str, Any]]) -> Mapping[str, Any]:
            return self._gateway.complete_with_tools(messages, schemas)

        return call

    def run(self, query: str, seed: list[CodeSpan]) -> list[CodeSpan]:
        # Air-gap FIRST — a non-loopback endpoint raises AirGapError before any
        # model I/O and the loop never starts (a floor, never a degrade — so this
        # is deliberately OUTSIDE the run/degrade accounting below).
        self._gateway.assert_local()

        self.run_count += 1
        try:
            return self._run_loop(query)
        except ScoutUnavailable:
            self.degrade_count += 1
            raise

    def _run_loop(self, query: str) -> list[CodeSpan]:
        context_map = build_context_map(self._manifest, query, self._settings)
        tools = build_explorer_tools(
            self._repo_path, self._settings, search_engine=self._search_engine
        )

        def submit(citations: Sequence[Mapping[str, Any]]) -> list[CodeSpan]:
            return submit_citations(citations, self._repo_path, self._settings)

        model_call = self._model_call or self._default_model_call()
        try:
            result = run_explorer_loop(
                model_call=model_call,
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

        if result.outcome == SUBMITTED:
            # Honest-empty (a well-formed empty submission) returns [] — NOT a degrade.
            return result.spans or []
        # Loop stopped with no citation → typed degrade to the Tier-0 floor.
        raise ScoutUnavailable(_EXHAUSTION_CAUSE[result.outcome])
