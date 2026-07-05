"""Spec 0022 (AC4/AC5/AC6) — the Scout-only locate probe.

An ADDITIVE eval-side driver (the SUT in `harpyja/scout/` + `harpyja/orchestrator/`
is frozen). It runs Scout in ISOLATION — `scout_engine.search` only, NO gate, judge,
or Deep (the 0021 ladder was inert anyway, and Scout is the cost driver) — then
projects each case through the frozen-oracle taxonomy (`locate_accuracy`) to
regenerate the distribution from scratch (NOT inheriting 0021's contaminated counts).

Turns-used honesty (AC5): Scout does not surface turns on `search`'s return nor on
`ScoutTally`, and the client unlinks its trajectory JSONL before any caller sees it.
We recover it through the PUBLIC `agent_factory` injection seam
(`build_scout_engine(..., agent_factory=…)`, Path A): `counting_agent_factory` wraps
the REAL `make_fastcontext_agent`, and inside `run()` counts the trajectory steps
BEFORE the frozen client's cleanup fires. The count is a labeled estimate
(`turns_used_source == "trajectory"`) read from FastContext's trajectory *format*;
Path B (CLI) and unwired runs are honestly `"unavailable"` — never a fabricated
counter.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from harpyja.eval.dataset import EvalCase
from harpyja.eval.locate_accuracy import (
    ClassifiedCase,
    LocateBucket,
    LocateDistribution,
    classify_case,
    normalize_citations,
    score_distribution,
)

# ---- stratification (AC4): repo × gold-patch span-size band -----------------

# Named span-size bands over the largest gold span in a case (line count, inclusive).
SPAN_SIZE_BANDS: tuple[tuple[str, int], ...] = (("small", 10), ("medium", 50))
_LARGE_BAND = "large"


def _repo_key(case: EvalCase) -> str:
    """The repo identity for stratification — the SWE-bench `owner__repo` prefix of the
    case-id (stable even when every case is repointed at one live checkout path)."""
    return case.case_id.rsplit("-", 1)[0] if "-" in case.case_id else case.case_id


def span_size_band(case: EvalCase) -> str:
    """Bucket a case by its largest gold span's line count into a named band."""
    largest = max((s.end_line - s.start_line + 1 for s in case.expected_spans), default=0)
    for name, ceiling in SPAN_SIZE_BANDS:
        if largest <= ceiling:
            return name
    return _LARGE_BAND


def stratify_cases(cases: Sequence[EvalCase]) -> dict[tuple[str, str], list[EvalCase]]:
    """Group cases by (repo, span-size band) so a cheap subset generalizes to the 38."""
    strata: dict[tuple[str, str], list[EvalCase]] = {}
    for case in cases:
        strata.setdefault((_repo_key(case), span_size_band(case)), []).append(case)
    return strata


# ---- turns-used (AC5): trajectory step-count via the agent_factory seam ------

def count_turns(trajectory_path: str) -> int | None:
    """Count agent steps in a FastContext trajectory JSONL (one record per turn).

    Returns the number of JSON-object records; ``None`` if the file is absent or any
    record is malformed — a labeled gap, never a guessed number. The one-record-per-
    turn rule is FastContext's trajectory format assumption, validated live and stated
    in findings.
    """
    try:
        with open(trajectory_path, encoding="utf-8") as fh:
            lines = [ln for ln in fh if ln.strip()]
    except OSError:
        return None
    turns = 0
    for ln in lines:
        try:
            json.loads(ln)
        except json.JSONDecodeError:
            return None
        turns += 1
    return turns


AgentFactory = Callable[..., Any]


def counting_agent_factory(
    turns_sink: list[int], *, inner_factory: AgentFactory | None = None
) -> AgentFactory:
    """A `build_scout_engine(agent_factory=…)` factory that wraps the REAL agent and
    records turns-used from the trajectory BEFORE the frozen client cleans it up.

    ``inner_factory`` defaults to the real ``make_fastcontext_agent`` (lazy-imported);
    tests inject a stub. The wrapper measures real behavior — it only observes.
    """

    def _factory(*, work_dir: str, trajectory_file: str) -> Any:
        if inner_factory is None:
            from fastcontext.agent.agent_factory import make_fastcontext_agent

            inner = make_fastcontext_agent(work_dir=work_dir, trajectory_file=trajectory_file)
        else:
            inner = inner_factory(work_dir=work_dir, trajectory_file=trajectory_file)
        return _CountingAgent(inner, trajectory_file, turns_sink)

    return _factory


class _CountingAgent:
    """Delegates to the real agent, then reads the trajectory turn count into a sink."""

    def __init__(self, inner: Any, trajectory_file: str, turns_sink: list[int]) -> None:
        self._inner = inner
        self._trajectory_file = trajectory_file
        self._turns_sink = turns_sink

    async def run(self, prompt: str, *args: Any, **kwargs: Any) -> Any:
        answer = await self._inner.run(prompt, *args, **kwargs)
        turns = count_turns(self._trajectory_file)
        if turns is not None:
            self._turns_sink.append(turns)
        return answer


# ---- live Scout-only stack (AC4/AC5) ---------------------------------------

@dataclass(frozen=True)
class ScoutOnlyStack:
    """A minimal stack carrying ONLY Scout — no gate/judge/Deep is wired, by design."""

    scout_engine: Any


def build_scout_only_stack(settings, repo_path: str, *, turns_sink: list[int] | None = None):
    """Build a Scout-ONLY stack via the public `build_scout_engine` seam.

    When ``turns_sink`` is given, a `counting_agent_factory` is injected so turns-used
    is recovered from the trajectory (Path A). No gate/judge/Deep is constructed — the
    probe measures Scout in isolation. Additive: no SUT change.
    """
    from harpyja.scout.wiring import build_scout_engine

    agent_factory = counting_agent_factory(turns_sink) if turns_sink is not None else None
    scout_engine = build_scout_engine(settings, repo_path, agent_factory=agent_factory)
    return ScoutOnlyStack(scout_engine=scout_engine)


# ---- the Scout-only probe (AC4) --------------------------------------------

@dataclass(frozen=True)
class CaseRow:
    """One auditable per-case row (AC8)."""

    case_id: str
    bucket: LocateBucket
    within_window: bool
    path_only_right_file: bool
    n_citations: int
    normalization_dropped: int


@dataclass(frozen=True)
class ProbeResult:
    """The regenerated Scout-only distribution + auditable rows + turns-used."""

    distribution: LocateDistribution
    rows: tuple[CaseRow, ...]
    turns_used: tuple[int, ...] | None
    turns_used_source: str
    recovered_spanned_total: int
    recovered_filelevel_total: int


def _run_scout_case(scout_engine: Any, case: EvalCase, repo_path: str):
    """Drive ONE case through Scout only (reset tally first, mirror the runner)."""
    if hasattr(scout_engine, "last_tally"):
        scout_engine.last_tally = None
    spans = scout_engine.search(case.query, scope=repo_path)
    tally = getattr(scout_engine, "last_tally", None)
    return normalize_citations(spans, tally)


def run_locate_probe(
    cases: Sequence[EvalCase],
    *,
    stack: Any,
    repo_path: str,
    window: int,
    turns_sink: list[int] | None = None,
) -> ProbeResult:
    """Drive `cases` through Scout in isolation and regenerate the distribution.

    No gate/judge/Deep is touched. `turns_sink` (populated by a wired
    `counting_agent_factory`) supplies turns-used; absent/empty → `"unavailable"`.
    """
    scout_engine = stack.scout_engine
    rows: list[CaseRow] = []
    classified: list[ClassifiedCase] = []
    rec_spanned = 0
    rec_filelevel = 0
    for case in cases:
        norm = _run_scout_case(scout_engine, case, repo_path)
        bucket, flags = classify_case(norm.effective, case.expected_spans, window=window)
        classified.append((bucket, flags, norm.normalization_dropped))
        rec_spanned += norm.recovered_spanned
        rec_filelevel += norm.recovered_filelevel
        rows.append(
            CaseRow(
                case_id=case.case_id,
                bucket=bucket,
                within_window=flags.within_window,
                path_only_right_file=flags.path_only_right_file,
                n_citations=len(norm.effective),
                normalization_dropped=norm.normalization_dropped,
            )
        )
    turns_used, source = _resolve_turns(turns_sink)
    return ProbeResult(
        distribution=score_distribution(classified),
        rows=tuple(rows),
        turns_used=turns_used,
        turns_used_source=source,
        recovered_spanned_total=rec_spanned,
        recovered_filelevel_total=rec_filelevel,
    )


def _resolve_turns(turns_sink: list[int] | None) -> tuple[tuple[int, ...] | None, str]:
    if turns_sink:
        return tuple(turns_sink), "trajectory"
    return None, "unavailable"


# ---- the reformulation probe (AC6, labeled non-primary) --------------------

@dataclass(frozen=True)
class ReformulationResult:
    """Raw-vs-distilled empty-rate delta over the probe cases (held OUT of baseline)."""

    n: int
    raw_empty_rate: float
    distilled_empty_rate: float
    delta_empty: float


def _empty_rate(cases, scout_engine, repo_path, window, *, query_of) -> float:
    empties = 0
    for case in cases:
        if hasattr(scout_engine, "last_tally"):
            scout_engine.last_tally = None
        spans = scout_engine.search(query_of(case), scope=repo_path)
        tally = getattr(scout_engine, "last_tally", None)
        norm = normalize_citations(spans, tally)
        bucket, _ = classify_case(norm.effective, case.expected_spans, window=window)
        if bucket is LocateBucket.EMPTY:
            empties += 1
    return empties / len(cases) if cases else 0.0


def run_reformulation_probe(
    cases: Sequence[EvalCase],
    *,
    stack: Any,
    repo_path: str,
    window: int,
    distill: Callable[[str], str],
) -> ReformulationResult:
    """Compare Scout empty-rate on raw issue text vs a distilled one-line query.

    A DISCRIMINATOR probe (BENCHMARK_UNREPRESENTATIVE vs RETRIEVAL_FUNDAMENTAL), not a
    baseline: its cases never enter `run_locate_probe`'s distribution.
    """
    scout_engine = stack.scout_engine
    raw = _empty_rate(cases, scout_engine, repo_path, window, query_of=lambda c: c.query)
    distilled = _empty_rate(
        cases, scout_engine, repo_path, window, query_of=lambda c: distill(c.query)
    )
    return ReformulationResult(
        n=len(cases),
        raw_empty_rate=raw,
        distilled_empty_rate=distilled,
        delta_empty=raw - distilled,
    )


# ---- fail posture: the strict live-stack gate ------------------------------

def _truthy(value: str | None) -> bool:
    return bool(value) and value.strip().lower() not in ("", "0", "false", "no")


def _endpoint_reachable(api_base: str, timeout: float = 0.25) -> bool:
    hostport = api_base.split("://", 1)[-1].split("/", 1)[0]
    host, _, port = hostport.partition(":")
    try:
        with socket.create_connection((host or "127.0.0.1", int(port or 80)), timeout=timeout):
            return True
    except OSError:
        return False


def scout_stack_available(settings: Any = None, *, endpoint: str | None = None) -> bool:
    """Scout-ONLY availability — NARROWER than the Deep-oriented `_live_stack_available`.

    A Scout probe needs only: `fastcontext` importable, `rg` on PATH, and a reachable
    loopback endpoint serving the Scout model. It does NOT need Deno or the Deep driver
    model (those are Tier-2). Reusing the Deep gate would FALSE-skip a Scout-capable
    host (the exact over-gating found on the 0022 live run: Deno absent, Scout served).
    """
    try:
        import fastcontext  # noqa: F401
    except ImportError:
        return False
    if shutil.which("rg") is None:
        return False
    base = endpoint or (getattr(settings, "lm_api_base", None) if settings else None)
    return _endpoint_reachable(base or "http://127.0.0.1:11434/v1")


def require_live_stack(available: bool, *, env: Mapping[str, str] | None = None) -> str:
    """Decide how an integration test should react to stack availability.

    Returns ``"proceed"`` when the stack is up; otherwise ``"fail"`` when
    ``HARPYJA_REQUIRE_LIVE_STACK`` is truthy (the intentional closure run must NOT go
    green by skipping) or ``"skip"`` when unset (CI-safe on a stackless host). Kept
    pytest-free so it is unit-testable; the caller maps the string to skip/fail.
    """
    if available:
        return "proceed"
    environ = os.environ if env is None else env
    return "fail" if _truthy(environ.get("HARPYJA_REQUIRE_LIVE_STACK")) else "skip"
