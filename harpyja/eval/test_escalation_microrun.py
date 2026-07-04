"""Spec 0021 (AC3) — the instrumented ≤2-case escalation micro-run.

Two layers:
- Pure-unit tests for the additive instrumentation (`_wrap_timed`) and the result
  builder (`build_micro_result`) — deterministic, no live stack. These pin that the
  micro-run reproduces `escalation_rate` from `tiers_run` and attributes wall-clock
  per tier, labeling the split an ESTIMATE (the per-tier granularity does not exist
  in any persisted 0020 dump — see findings.md Feasibility).
- One `@pytest.mark.integration`, skip-not-fail end-to-end run that drives ≤2 real
  cases through the wrapped live stack when served models + fixtures are present.
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass

import pytest

from harpyja.eval.config import EvalConfig
from harpyja.eval.escalation_microrun import (
    MicroRunResult,
    _wrap_timed,
    build_micro_result,
    run_escalation_microrun,
)
from harpyja.eval.metrics import CaseOutcome
from harpyja.eval.runner import CaseRun, build_live_stack
from harpyja.eval.test_eval_integration import (
    _NEEDS_STACK,
    _live_stack_available,
    _settings_live,
)
from harpyja.eval.test_swebench_integration import _LEGACY, _live_cases


@dataclass
class Span:
    path: str
    start_line: int
    end_line: int


def _outcome(*, tiers_run):
    return CaseOutcome(
        case_id="c",
        classification="point",
        expected_spans=(Span("a.py", 10, 20),),
        tier1_citations=(),
        final_citations=(),
        tiers_run=tuple(tiers_run),
    )


def _run(*, tiers_run, latency_ms=100.0, notes=None):
    return CaseRun(
        event={"notes": notes},
        outcome=_outcome(tiers_run=tiers_run),
        terminal_tier=max(tiers_run) if tiers_run else None,
        latency_ms=latency_ms,
    )


# ---- instrumentation: additive timing wrapper ------------------------------

class _Fake:
    def search(self, pattern, scope=None):
        time.sleep(0.002)
        return [pattern]


def test_wrap_timed_accumulates_into_slot_and_preserves_return():
    timer = {"scout": 0.0}
    fake = _Fake()
    unwrap = _wrap_timed(fake, "search", timer, "scout")
    assert fake.search("q", scope="/repo") == ["q"]  # return preserved
    assert timer["scout"] > 0.0  # wall-clock accumulated
    unwrap()
    # after unwrap the method is the original (no further accumulation)
    before = timer["scout"]
    fake.search("q")
    assert timer["scout"] == before


def test_wrap_timed_noop_on_missing_method_or_none():
    timer = {"deep": 0.0}
    # None collaborator (Deep not wired) -> safe no-op, unwrap callable.
    assert _wrap_timed(None, "search", timer, "deep")() is None
    # object lacking the method -> no-op.
    assert _wrap_timed(object(), "search", timer, "deep")() is None
    assert timer["deep"] == 0.0


# ---- result builder: reproduces escalation_rate from tiers_run -------------

def test_build_micro_result_reproduces_escalation_rate_from_tiers_run():
    runs = [_run(tiers_run=(0, 1)), _run(tiers_run=(0, 1, 2))]
    timer = {"scout": 30.0, "judge": 12.0, "deep": 58.0}
    res = build_micro_result(runs, timer, total_wall_ms=100.0)
    assert isinstance(res, MicroRunResult)
    assert res.n_cases == 2
    assert res.escalation_rate == 0.5  # 1 of 2 reached Tier-2, derived from tiers_run
    assert res.per_tier_wall_ms == {"scout": 30.0, "judge": 12.0, "deep": 58.0}
    assert res.per_tier_label == "estimate"  # never presented as recorded
    assert res.total_wall_ms == 100.0


def test_build_micro_result_zero_rate_when_no_tier2():
    runs = [_run(tiers_run=(0, 1)), _run(tiers_run=(0,))]
    res = build_micro_result(runs, {"scout": 1.0, "judge": 0.0, "deep": 0.0}, total_wall_ms=5.0)
    assert res.escalation_rate == 0.0


def test_build_micro_result_flags_deep_degraded():
    runs = [_run(tiers_run=(0, 1), notes="scout ok; deep-degraded:oom")]
    res = build_micro_result(runs, {"scout": 1.0, "judge": 0.0, "deep": 0.0}, total_wall_ms=5.0)
    assert res.deep_degraded is True


# ---- integration: live ≤2-case instrumented micro-run (skip-not-fail) ------

@pytest.mark.integration
def test_escalation_microrun_reproduces_rate_with_per_tier_timing(tmp_path):
    if not _live_stack_available():
        pytest.skip(_NEEDS_STACK)
    repo = str(tmp_path / "legacy")
    shutil.copytree(_LEGACY, repo)
    stack = build_live_stack(_settings_live(), repo)
    res = run_escalation_microrun(
        _live_cases(repo, cap=2), _settings_live(), EvalConfig(k_runs=1),
        stack=stack, repo_path=repo, cap=2,
    )
    assert isinstance(res, MicroRunResult)
    assert 0 < res.n_cases <= 2
    assert 0.0 <= res.escalation_rate <= 1.0
    assert set(res.per_tier_wall_ms) == {"scout", "judge", "deep"}
    assert res.per_tier_label == "estimate"
    assert res.total_wall_ms > 0.0
