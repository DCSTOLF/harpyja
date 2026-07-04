"""Spec 0021 (AC3) — the instrumented ≤2-case escalation micro-run.

An ADDITIVE eval-side wrapper (the SUT in `harpyja/orchestrator/` is frozen). It
drives ≤2 real cases through the existing `run_case` path with the live stack's
collaborators wrapped for wall-clock accounting, then:

- reproduces `escalation_rate` from the collected `tiers_run` (the metric is
  derived — this run confirms it live rather than trusting a persisted number), and
- attributes wall-clock to Scout / judge (gate) / Deep, LABELED an ``estimate``.

Honesty (findings.md Feasibility): the per-tier split is a sample estimate — the
frozen runner exposes only whole-case `latency_ms`, and no persisted 0020 dump
carries per-tier granularity. The recorded total (`total_wall_ms`) is real; the
split is the estimate. The wrapper attributes time at the eval boundary by timing
the collaborators' public entry points (`scout_engine.search`, `gate.verify`,
`deep_engine.search`) — it never edits orchestrator internals.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from harpyja.eval.config import EvalConfig
from harpyja.eval.metrics import escalation_rate
from harpyja.eval.runner import CaseRun, _is_deep_degraded, run_case

# The public entry point on each collaborator, mapped to its timing slot. Timing
# the same `scout_engine.search` the gate-oracle capture and `locate` both call is
# intentional — all Scout exploration lands in the "scout" slot (the suspected sink).
_TIER_SEAMS: tuple[tuple[str, str, str], ...] = (
    ("scout_engine", "search", "scout"),
    ("gate", "verify", "judge"),
    ("deep_engine", "search", "deep"),
)


@dataclass(frozen=True)
class MicroRunResult:
    """The outcome of an instrumented micro-run.

    `per_tier_wall_ms` is a labeled ESTIMATE (`per_tier_label == "estimate"`);
    `total_wall_ms` is the real recorded wall-clock for the driven cases.
    """

    n_cases: int
    escalation_rate: float
    per_tier_wall_ms: dict[str, float]
    per_tier_label: str
    total_wall_ms: float
    tiers_run: list[tuple[int, ...]]
    deep_degraded: bool


def _wrap_timed(obj: object | None, method_name: str, timer: dict, slot: str) -> Callable[[], None]:
    """Additively wrap ``obj.method_name`` to accumulate wall-clock into ``timer[slot]``.

    Returns an ``unwrap()`` that restores the original method. A ``None`` collaborator
    (tier not wired) or a missing method is a safe no-op — the micro-run stays honest
    when a tier never ran rather than fabricating a slot.
    """
    if obj is None or not callable(getattr(obj, method_name, None)):
        return lambda: None
    original = getattr(obj, method_name)

    def timed(*args, **kwargs):
        t0 = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            timer[slot] += (time.perf_counter() - t0) * 1000.0

    setattr(obj, method_name, timed)

    def unwrap() -> None:
        setattr(obj, method_name, original)

    return unwrap


def build_micro_result(
    runs: Sequence[CaseRun], timer: dict, *, total_wall_ms: float
) -> MicroRunResult:
    """Assemble the result from driven `CaseRun`s + the per-tier timer (pure)."""
    outcomes = [r.outcome for r in runs]
    return MicroRunResult(
        n_cases=len(runs),
        escalation_rate=escalation_rate(outcomes),
        per_tier_wall_ms={
            "scout": timer.get("scout", 0.0),
            "judge": timer.get("judge", 0.0),
            "deep": timer.get("deep", 0.0),
        },
        per_tier_label="estimate",
        total_wall_ms=total_wall_ms,
        tiers_run=[o.tiers_run for o in outcomes],
        deep_degraded=any(_is_deep_degraded(r.event.get("notes")) for r in runs),
    )


def run_escalation_microrun(
    cases,
    settings,
    eval_config: EvalConfig,
    *,
    stack,
    repo_path: str,
    cap: int = 2,
) -> MicroRunResult:
    """Drive ≤`cap` cases through the wrapped live stack; return the instrumented result.

    Collaborators are wrapped for timing, restored in a ``finally`` so the stack is
    left as found even if a case raises.
    """
    cases = list(cases)[:cap]
    timer = {"scout": 0.0, "judge": 0.0, "deep": 0.0}
    unwraps = [
        _wrap_timed(getattr(stack, attr, None), method, timer, slot)
        for attr, method, slot in _TIER_SEAMS
    ]
    runs: list[CaseRun] = []
    t0 = time.perf_counter()
    try:
        for case in cases:
            runs.append(
                run_case(case, settings, eval_config, repo_path=repo_path, stack=stack)
            )
    finally:
        for unwrap in unwraps:
            unwrap()
    total_wall_ms = (time.perf_counter() - t0) * 1000.0
    return build_micro_result(runs, timer, total_wall_ms=total_wall_ms)
