"""Per-request explorer-loop budget meter (AC10).

Per-call host-tool clamps are not enough: the RLM is a code-writing loop that can
recurse and fan out. `DeepBudget` bounds the loop itself — tool-calls, tokens,
recursion depth, and sub-query fan-out — and records which bound fired so the
result can carry a stable `deep-truncated:<bound>` note.

These four are the *counter* facet (pure-Python, no process). The fifth bound,
wall-clock, is enforced by the host-terminable runner (see ``deep/runner.py``);
the runner sets ``truncated_bound = "wall-clock"`` on this meter when it fires.
"""

from __future__ import annotations

from harpyja.config.settings import Settings


class DeepBudgetExceeded(RuntimeError):
    """A host tool refused a call because a counter bound is exhausted.

    Not a `DeepUnavailable` — the runner catches this as a truncation signal and
    returns the citations gathered so far with a `deep-truncated:<bound>` note.
    """


class DeepBudget:
    def __init__(self, settings: Settings) -> None:
        self._max_tool_calls = settings.deep_max_tool_calls
        self._max_tokens = settings.deep_token_ceiling
        self._max_depth = settings.deep_max_depth
        self._max_subqueries = settings.deep_max_subqueries

        self._tool_calls = 0
        self._tokens = 0
        self._depth = 0
        self._subqueries = 0
        self.truncated_bound: str | None = None

    def _trip(self, bound: str) -> bool:
        # First bound to fire wins; record it and refuse the charge.
        if self.truncated_bound is None:
            self.truncated_bound = bound
        return False

    def charge_tool_call(self) -> bool:
        if self._tool_calls + 1 > self._max_tool_calls:
            return self._trip("tool-calls")
        self._tool_calls += 1
        return True

    def charge_tokens(self, n: int) -> bool:
        if self._tokens + n > self._max_tokens:
            return self._trip("tokens")
        self._tokens += n
        return True

    def enter_subquery(self) -> bool:
        if self._subqueries + 1 > self._max_subqueries:
            return self._trip("subqueries")
        if self._depth + 1 > self._max_depth:
            return self._trip("depth")
        self._subqueries += 1
        self._depth += 1
        return True

    def exit_subquery(self) -> None:
        if self._depth > 0:
            self._depth -= 1
