"""`DeepEngine` — Tier 2 behind the shared `Locator` seam, plus a richer `run`.

Like `ScoutEngine`, the engine is **self-seeding**: every call runs its own
lightweight Tier-0 lookup (`seed_fn`) **before** the backend, so a seed
precondition failure (`RipgrepMissingError`) propagates loudly as the floor and
the backend is never reached. Backend output is untrusted and normalized to the
`deep_*` budgets.

Two surfaces:
- `.search(query, scope) -> list[CodeSpan]` — the `Locator` seam, so the
  orchestrator/formatter never branch on `DeepBackend`.
- `run(query) -> (citations, truncated_bound | None)` — the orchestrator's deep
  branch needs the truncation bound, which the bare `list[CodeSpan]` `.search`
  contract cannot carry. A truncation is an honest bounded result, **not** a
  `DeepUnavailable` (which propagates for the caller to degrade to Scout).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from harpyja.config.settings import Settings
from harpyja.deep.backend import DeepBackend
from harpyja.deep.budget import DeepBudget
from harpyja.deep.runner import DeepRunner
from harpyja.scout.normalize import normalize_spans
from harpyja.server.types import CodeSpan

SeedFn = Callable[[str], list[CodeSpan]]
MakeTools = Callable[[DeepBudget], Mapping[str, Any]]


class DeepEngine:
    def __init__(
        self,
        backend: DeepBackend,
        seed_fn: SeedFn,
        runner: DeepRunner,
        settings: Settings,
        repo_root: str,
        *,
        make_tools: MakeTools,
    ) -> None:
        self._backend = backend
        self._seed_fn = seed_fn
        self._runner = runner
        self._settings = settings
        self._repo_root = repo_root
        self._make_tools = make_tools

    def run(self, query: str) -> tuple[list[CodeSpan], str | None]:
        # Seed FIRST — its precondition errors must propagate before the backend.
        seed = self._seed_fn(query)
        hints = seed[: self._settings.deep_seed_top_n]

        budget = DeepBudget(self._settings)
        tools = self._make_tools(budget)

        def target() -> list[CodeSpan]:
            # DeepUnavailable / AirGapError propagate through the runner untouched;
            # only DeepBudgetExceeded is caught and surfaced as a truncation.
            return self._backend.run(query, hints, tools)

        raw, truncated = self._runner.run(target, budget)
        citations = normalize_spans(
            raw,
            self._repo_root,
            max_citations=self._settings.deep_max_citations,
            max_span_lines=self._settings.deep_max_span_lines,
        )
        return citations, truncated

    def search(self, pattern: str, scope: str | None = None) -> list[CodeSpan]:
        return self.run(pattern)[0]
