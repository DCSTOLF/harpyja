"""The host-terminable execution boundary for the Deep explorer (AC10).

Two facets, deliberately separate so the unit suite stays process-free:

- ``run(target, budget)`` — the **in-process** counter facet. The target (the
  backend's exploration) runs in-process; tool-call / token / depth / sub-query
  bounds are enforced by `DeepBudget` + the host-tool wrappers. A
  `DeepBudgetExceeded` is caught and surfaced as a `truncated_bound`, never a
  `DeepUnavailable`.

- ``run_isolated(worker, args, timeout_ms)`` — the **out-of-band** facet: runs a
  picklable worker in a spawned subprocess the host can **hard-kill**. This is the
  only thing that stops a non-yielding busy loop (`while True: pass`) that touches
  no counter — a same-thread deadline could never fire. On deadline the worker is
  terminated and the run returns ``"wall-clock"``. Spawning a real process, this
  facet's tests are `@pytest.mark.integration`.
"""

from __future__ import annotations

import multiprocessing
from collections.abc import Callable
from typing import Any

from harpyja.config.settings import Settings
from harpyja.deep.budget import DeepBudget, DeepBudgetExceeded
from harpyja.server.types import CodeSpan


def _subprocess_entry(worker: Callable[..., Any], args: tuple, queue) -> None:  # pragma: no cover
    try:
        queue.put(("ok", worker(*args)))
    except BaseException as err:  # noqa: BLE001 - report any child failure to the parent
        queue.put(("err", repr(err)))


class DeepRunner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def run(
        self,
        target: Callable[[], list[CodeSpan]],
        budget: DeepBudget,
    ) -> tuple[list[CodeSpan], str | None]:
        """In-process counter facet: returns (citations, truncated_bound)."""
        try:
            spans = target()
        except DeepBudgetExceeded as err:
            return [], (budget.truncated_bound or str(err))
        return spans, budget.truncated_bound

    def run_isolated(
        self,
        worker: Callable[..., Any],
        args: tuple = (),
        *,
        timeout_ms: int | None = None,
    ) -> tuple[Any, str | None]:
        """Out-of-band facet: hard-kill the worker if it overruns the wall clock."""
        timeout_s = (timeout_ms or self._settings.deep_wall_clock_ms) / 1000.0
        ctx = multiprocessing.get_context("spawn")
        queue = ctx.Queue()
        proc = ctx.Process(target=_subprocess_entry, args=(worker, args, queue))
        proc.start()
        proc.join(timeout_s)
        if proc.is_alive():
            proc.terminate()
            proc.join(1.0)
            if proc.is_alive():
                proc.kill()
                proc.join()
            return None, "wall-clock"
        if queue.empty():
            return None, "wall-clock"
        status, payload = queue.get()
        if status == "err":
            raise RuntimeError(f"deep worker failed: {payload}")
        return payload, None
