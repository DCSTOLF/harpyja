"""Eval runner (AC4, AC7).

Drives the **real** `harpyja.orchestrator.locate.locate(...)` auto path per case
and assembles a pinned-schema report. The harness is measurement-only: it injects
collaborators (tier engines, gate, indexer/resolver) but never alters routing.

Tier-1 correctness (the gate oracle) is captured by calling `scout_engine`
directly for point cases — when the gate escalates, the final citations are
Tier-2's and cannot reveal whether Tier-1 was wrong. This is an honest extra Scout
call on point cases (a known harness cost), kept out of the broad path (which has
no gate, D1).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from harpyja.config.settings import Settings
from harpyja.eval import metrics as M
from harpyja.eval.config import EvalConfig
from harpyja.eval.dataset import EvalCase
from harpyja.eval.report import build_report, write_report
from harpyja.orchestrator.classify import classify_query
from harpyja.scout.errors import ScoutUnavailable
from harpyja.server.types import LocateRequest


@dataclass(frozen=True)
class LocateStack:
    """The injected collaborators forwarded to `locate(...)`.

    Defaults mirror `locate`'s real production seams; unit tests override with
    fakes. `index_ready` is forwarded so a test can force the Tier-0 seed on.
    """

    engine: object
    scout_engine: object | None = None
    deep_engine: object | None = None
    gate: object | None = None
    symbol_engine: object | None = None
    classifier: Callable = classify_query
    indexer: Callable | None = None
    resolve_dir: Callable | None = None
    index_ready: bool | None = None
    # Optional per-tier model-call counts (None = unknown; honest rather than a
    # false zero on a live run with no counter wired).
    model_calls: Mapping[int, int] | None = None


@dataclass
class CaseRun:
    """One driven case: its per-case report event + the metric `CaseOutcome`."""

    event: dict
    outcome: M.CaseOutcome
    terminal_tier: int | None
    latency_ms: float


def _span_dict(s) -> dict:
    return {"path": s.path, "start_line": s.start_line, "end_line": s.end_line}


def _citation_dict(c) -> dict:
    return {
        "path": c.path,
        "start_line": c.start_line,
        "end_line": c.end_line,
        "source_tier": getattr(c, "source_tier", 0),
        "score": getattr(c, "score", 0.0),
    }


def _locate(req: LocateRequest, settings: Settings, stack: LocateStack):
    from harpyja.orchestrator.locate import locate

    kwargs: dict = {
        "engine": stack.engine,
        "scout_engine": stack.scout_engine,
        "deep_engine": stack.deep_engine,
        "gate": stack.gate,
        "symbol_engine": stack.symbol_engine,
        "classifier": stack.classifier,
        "index_ready": stack.index_ready,
    }
    if stack.indexer is not None:
        kwargs["indexer"] = stack.indexer
    if stack.resolve_dir is not None:
        kwargs["resolve_dir"] = stack.resolve_dir
    return locate(req, settings, **kwargs)


def build_live_stack(settings: Settings, repo: str) -> LocateStack:
    """Assemble a `LocateStack` from the real production tier factories (AC7/AC8).

    Mirrors `orchestrator/test_locate_integration.py`'s `_build`: the same
    `build_scout_engine` / `build_deep_engine` / `build_verification_gate` the live
    `mode=auto` path uses, plus the Tier-0 `RipgrepEngine`. `index_ready` is left
    `None` so `locate` derives it from the freshly built manifest.
    """
    from harpyja.deep.wiring import build_deep_engine
    from harpyja.orchestrator.wiring import build_verification_gate
    from harpyja.scout.wiring import build_scout_engine
    from harpyja.symbols.ripgrep import RipgrepEngine

    return LocateStack(
        engine=RipgrepEngine(settings),
        scout_engine=build_scout_engine(settings, repo),
        deep_engine=build_deep_engine(settings, repo),
        gate=build_verification_gate(settings, repo),
    )


def run_case(
    case: EvalCase,
    settings: Settings,
    eval_config: EvalConfig,
    *,
    repo_path: str,
    stack: LocateStack,
    mode: str = "auto",
) -> CaseRun:
    """Drive one case through the real `locate` path; build its event + outcome.

    `mode` defaults to `"auto"` (the OQ2 path); `"fast"` gives the Scout-terminal
    Tier-1 line for the fast-vs-auto comparison (AC7).
    """
    req = LocateRequest(
        query=case.query,
        repo_path=repo_path,
        mode=mode,
        max_results=settings.max_results,
    )

    gate_eligible = case.classification == "point"
    tier1_spans: tuple = ()
    if gate_eligible and stack.scout_engine is not None:
        try:
            tier1_spans = tuple(stack.scout_engine.search(case.query, scope=repo_path))
        except ScoutUnavailable:
            tier1_spans = ()

    t0 = time.perf_counter()
    result = _locate(req, settings, stack)
    latency_ms = (time.perf_counter() - t0) * 1000.0

    outcome = M.CaseOutcome(
        case_id=case.case_id,
        classification=case.classification,
        expected_spans=case.expected_spans,
        tier1_citations=tier1_spans,
        final_citations=tuple(result.citations),
        tiers_run=tuple(result.tiers_run),
    )

    terminal_tier = max(result.tiers_run) if result.tiers_run else None
    tier1_ok = M.tier1_correct(tier1_spans, case.expected_spans) if gate_eligible else None
    gate_triggered = gate_eligible and stack.gate is not None and bool(tier1_spans)

    event = {
        "case_id": case.case_id,
        "query": case.query,
        "classification": case.classification,
        "expected_spans": [_span_dict(s) for s in case.expected_spans],
        "citations": [_citation_dict(c) for c in result.citations],
        "tiers_run": list(result.tiers_run),
        "terminal_tier": terminal_tier,
        "escalated_to_deep": 2 in result.tiers_run,
        "gate_eligible": gate_eligible,
        "gate_triggered": gate_triggered,
        "tier1_correct": tier1_ok,
        "span_hit_primary": M.case_span_hit_primary(outcome),
        "span_hit_secondary": M.case_span_hit_secondary(
            outcome, eval_config.proximity_window_lines
        ),
        "notes": result.notes,
    }
    return CaseRun(event=event, outcome=outcome, terminal_tier=terminal_tier, latency_ms=latency_ms)


def aggregate_outcomes(
    runs: Sequence[CaseRun],
    eval_config: EvalConfig,
    *,
    model_calls: Mapping[int, int] | None = None,
) -> dict:
    """Build the D7 aggregate block from a set of driven cases."""
    outcomes = [r.outcome for r in runs]
    catch_rate, caught, wrong_total = M.gate_catch_rate(outcomes)
    false_esc_rate, false_esc, correct_total = M.gate_false_escalation(outcomes)

    per_tier_latency: dict[str, float] = {}
    for r in runs:
        if r.terminal_tier is None:
            continue
        key = str(r.terminal_tier)
        per_tier_latency[key] = per_tier_latency.get(key, 0.0) + r.latency_ms

    return {
        "span_hit_rate_primary": M.span_hit_rate_primary(outcomes),
        "span_hit_rate_secondary": M.span_hit_rate_secondary(
            outcomes, eval_config.proximity_window_lines
        ),
        "escalation_rate": M.escalation_rate(outcomes),
        "tier01_resolve_rate": M.tier01_resolve_rate(outcomes),
        "gate_catch_rate": catch_rate,
        "caught_count": caught,
        "wrong_tier1_count": wrong_total,
        "gate_false_escalation": false_esc_rate,
        "false_escalated_count": false_esc,
        "correct_tier1_count": correct_total,
        "per_tier_latency_ms": per_tier_latency,
        "per_tier_model_calls": (dict(model_calls) if model_calls is not None else None),
    }


def run_dataset(
    cases: Sequence[EvalCase],
    settings: Settings,
    eval_config: EvalConfig,
    *,
    repo_path: str,
    stack: LocateStack,
    out_dir=None,
    write: bool = False,
    repo_revision: str = "unknown",
    timestamp: str = "1970-01-01T00:00:00Z",
    mode: str = "auto",
) -> dict:
    """Run every case through the auto path; assemble (and optionally write) a report."""
    runs = [
        run_case(c, settings, eval_config, repo_path=repo_path, stack=stack, mode=mode)
        for c in cases
    ]
    aggregate = aggregate_outcomes(runs, eval_config, model_calls=stack.model_calls)

    seed_n = len(cases)
    run_metadata = {
        "repo_revision": repo_revision,
        "seed_n": seed_n,
        "n_floor": eval_config.n_floor,
        "indicative_only": seed_n < eval_config.n_floor,
        "mode": mode,
        "k_runs": 1,
        "settings_snapshot": {
            "verify_method": settings.verify_method,
            "verify_threshold": settings.verify_threshold,
            "verify_top_n": settings.verify_top_n,
        },
        "timestamp": timestamp,
        "artifact_dir": str(out_dir) if out_dir is not None else None,
    }

    report = build_report(run_metadata, [r.event for r in runs], aggregate)
    if write:
        if out_dir is None:
            raise ValueError("write=True requires out_dir")
        write_report(report, out_dir=out_dir, repo_path=repo_path)
    return report
