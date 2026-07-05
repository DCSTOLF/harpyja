"""Spec 0022 (AC4/AC5/AC6) — Scout-only locate probe: unit layer.

Deterministic, no live stack. Pins: case stratification (repo × gold-span-size band),
per-case `last_tally` reset, distribution assembly, the honest turns-used capture
(`count_turns` from a trajectory fixture + `counting_agent_factory` reading it before
cleanup, labeled `trajectory` vs `unavailable`), the reformulation-probe empty-rate
delta with probe cases held OUT of the baseline, and the `require_live_stack` gate.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from harpyja.eval.dataset import EvalCase, ExpectedSpan
from harpyja.eval.locate_accuracy import LocateBucket
from harpyja.scout.engine import ScoutTally
from harpyja.server.types import CodeSpan


def _case(case_id: str, *, spans, query: str = "where is the retry logic?") -> EvalCase:
    return EvalCase(
        case_id=case_id,
        query=query,
        repo="/repo",
        expected_spans=tuple(ExpectedSpan(*s) for s in spans),
        classification="point",
    )


class _FakeScout:
    """A scout_engine stand-in: scripted (spans, tally) per search; tracks last_tally
    at each search entry so we can prove the probe resets it per case."""

    def __init__(self, script):
        self._script = list(script)
        self._i = 0
        self.last_tally: ScoutTally | None = None
        self.seen_at_entry: list[ScoutTally | None] = []
        self.queries: list[str] = []

    def search(self, pattern, scope=None):
        self.seen_at_entry.append(self.last_tally)
        self.queries.append(pattern)
        spans, tally = self._script[self._i]
        self._i += 1
        self.last_tally = tally
        return list(spans)


@dataclass
class _FakeStack:
    scout_engine: object


# ---- AC4: stratification ---------------------------------------------------

def test_stratify_cases_by_repo_and_span_size_band():
    from harpyja.eval.locate_probe import stratify_cases

    cases = [
        _case("astropy__astropy-1", spans=[("a.py", 10, 12)]),      # small
        _case("astropy__astropy-2", spans=[("b.py", 1, 200)]),      # large
        _case("flask__flask-3", spans=[("c.py", 5, 9)]),            # small, other repo
    ]
    strata = stratify_cases(cases)
    # keyed by (repo, band); the two astropy cases split across size bands.
    keys = set(strata.keys())
    assert ("astropy__astropy", "small") in keys
    assert ("astropy__astropy", "large") in keys
    assert ("flask__flask", "small") in keys
    # every case placed exactly once.
    assert sum(len(v) for v in strata.values()) == 3


# ---- AC4: probe drives Scout-only, resets tally, builds distribution --------

def test_run_locate_probe_resets_last_tally_per_case():
    from harpyja.eval.locate_probe import run_locate_probe

    scout = _FakeScout(
        [
            ([CodeSpan("a.py", 10, 12)], ScoutTally(spanned=1)),
            ([CodeSpan("b.py", 1, 2)], ScoutTally(spanned=1)),
        ]
    )
    cases = [_case("r-1", spans=[("a.py", 10, 20)]), _case("r-2", spans=[("b.py", 5, 9)])]
    run_locate_probe(cases, stack=_FakeStack(scout), repo_path="/repo", window=50)
    # a stale tally from case 1 must never be visible at case 2's search entry.
    assert scout.seen_at_entry == [None, None]


def test_run_locate_probe_collects_citations_tally_and_builds_distribution():
    from harpyja.eval.locate_probe import run_locate_probe

    scout = _FakeScout(
        [
            ([CodeSpan("a.py", 110, 115)], ScoutTally(spanned=1)),         # CORRECT
            ([CodeSpan("a.py", None, None)], ScoutTally(filelevel=1)),     # RFWS (path-only)
            ([], ScoutTally(dropped=2)),                                   # EMPTY (dropped)
        ]
    )
    cases = [
        _case("r-1", spans=[("a.py", 100, 120)]),
        _case("r-2", spans=[("a.py", 100, 120)]),
        _case("r-3", spans=[("a.py", 100, 120)]),
    ]
    res = run_locate_probe(cases, stack=_FakeStack(scout), repo_path="/repo", window=50)
    d = res.distribution
    assert d.n == 3
    assert d.counts[LocateBucket.CORRECT] == 1
    assert d.counts[LocateBucket.RIGHT_FILE_WRONG_SPAN] == 1
    assert d.counts[LocateBucket.EMPTY] == 1
    assert d.normalization_dropped_total == 2
    # per-case rows are auditable (AC8 seed).
    assert len(res.rows) == 3
    assert res.rows[0].case_id == "r-1" and res.rows[0].bucket is LocateBucket.CORRECT


def test_run_locate_probe_turns_unavailable_without_sink():
    from harpyja.eval.locate_probe import run_locate_probe

    scout = _FakeScout([([CodeSpan("a.py", 1, 2)], ScoutTally())])
    res = run_locate_probe(
        [_case("r-1", spans=[("a.py", 1, 2)])],
        stack=_FakeStack(scout), repo_path="/repo", window=50,
    )
    assert res.turns_used is None
    assert res.turns_used_source == "unavailable"


def test_run_locate_probe_turns_from_sink_labeled_trajectory():
    from harpyja.eval.locate_probe import run_locate_probe

    scout = _FakeScout(
        [([CodeSpan("a.py", 1, 2)], ScoutTally()), ([CodeSpan("b.py", 1, 2)], ScoutTally())]
    )
    sink: list[int] = [3, 5]  # as if a counting_agent_factory appended per case
    cases = [_case("r-1", spans=[("a.py", 1, 2)]), _case("r-2", spans=[("b.py", 1, 2)])]
    res = run_locate_probe(
        cases, stack=_FakeStack(scout), repo_path="/repo", window=50, turns_sink=sink
    )
    assert res.turns_used == (3, 5)
    assert res.turns_used_source == "trajectory"


# ---- AC5: honest turns-used capture ----------------------------------------

def test_count_turns_from_trajectory_counts_steps(tmp_path):
    from harpyja.eval.locate_probe import count_turns

    traj = tmp_path / "t.jsonl"
    traj.write_text('{"step": 1}\n{"step": 2}\n{"step": 3}\n\n')  # blank line ignored
    assert count_turns(str(traj)) == 3


def test_count_turns_none_on_absent_or_malformed(tmp_path):
    from harpyja.eval.locate_probe import count_turns

    assert count_turns(str(tmp_path / "nope.jsonl")) is None
    bad = tmp_path / "bad.jsonl"
    bad.write_text("{not json\n")
    assert count_turns(str(bad)) is None


def test_counting_agent_factory_wraps_real_and_reads_trajectory_before_cleanup(tmp_path):
    from harpyja.eval.locate_probe import counting_agent_factory

    traj = tmp_path / "traj.jsonl"

    class _StubInner:
        async def run(self, prompt, max_turns=4, citation=False):
            # the REAL agent would write its trajectory here during the run.
            traj.write_text('{"step": 1}\n{"step": 2}\n')
            return "answer-spans"

    def _stub_inner_factory(*, work_dir, trajectory_file):
        return _StubInner()

    sink: list[int] = []
    factory = counting_agent_factory(sink, inner_factory=_stub_inner_factory)
    agent = factory(work_dir=str(tmp_path), trajectory_file=str(traj))
    answer = asyncio.run(agent.run("q", max_turns=4, citation=False))
    # inner's return is preserved AND the turn count was read from the trajectory.
    assert answer == "answer-spans"
    assert sink == [2]


def test_turns_used_source_labels_trajectory_vs_unavailable(tmp_path):
    # When the trajectory is missing/unreadable, the wrapper records nothing rather
    # than fabricating a count (0021 honesty).
    from harpyja.eval.locate_probe import counting_agent_factory

    class _StubInnerNoTraj:
        async def run(self, prompt, max_turns=4, citation=False):
            return "ans"  # writes NO trajectory

    def _factory(*, work_dir, trajectory_file):
        return _StubInnerNoTraj()

    sink: list[int] = []
    factory = counting_agent_factory(sink, inner_factory=_factory)
    agent = factory(work_dir=str(tmp_path), trajectory_file=str(tmp_path / "absent.jsonl"))
    asyncio.run(agent.run("q"))
    assert sink == []  # no fabricated turn count


# ---- AC6: reformulation probe (labeled non-primary) ------------------------

def test_reformulation_probe_records_empty_rate_delta():
    from harpyja.eval.locate_probe import run_reformulation_probe

    # raw query → empty; distilled query → a citation. So distilling cuts empty-rate.
    scout = _FakeScout(
        [
            ([], ScoutTally()),                          # case1 raw → EMPTY
            ([CodeSpan("a.py", 100, 120)], ScoutTally()),  # case1 distilled → CORRECT
        ]
    )
    cases = [_case("r-1", spans=[("a.py", 100, 120)])]
    res = run_reformulation_probe(
        cases, stack=_FakeStack(scout), repo_path="/repo", window=50,
        distill=lambda q: "retry logic",
    )
    assert res.raw_empty_rate == 1.0
    assert res.distilled_empty_rate == 0.0
    assert res.delta_empty == 1.0


def test_reformulation_probe_cases_excluded_from_baseline():
    from harpyja.eval.locate_probe import run_locate_probe, run_reformulation_probe

    # The baseline run and the probe run are separate calls over separate case lists;
    # the probe returns its own object and never mutates a baseline distribution.
    baseline_scout = _FakeScout([([CodeSpan("a.py", 110, 115)], ScoutTally())])
    baseline = run_locate_probe(
        [_case("b-1", spans=[("a.py", 100, 120)])],
        stack=_FakeStack(baseline_scout), repo_path="/repo", window=50,
    )
    probe_scout = _FakeScout([([], ScoutTally()), ([], ScoutTally())])
    probe = run_reformulation_probe(
        [_case("p-1", spans=[("a.py", 100, 120)])],
        stack=_FakeStack(probe_scout), repo_path="/repo", window=50, distill=lambda q: "x",
    )
    # baseline distribution is untouched by the probe (still its single CORRECT case).
    assert baseline.distribution.n == 1
    assert baseline.distribution.counts[LocateBucket.CORRECT] == 1
    assert not hasattr(probe, "distribution")  # probe is not a baseline distribution


# ---- fail posture: require_live_stack --------------------------------------

def test_require_live_stack_proceeds_when_available():
    from harpyja.eval.locate_probe import require_live_stack

    assert require_live_stack(True, env={}) == "proceed"


def test_require_live_stack_skips_when_env_unset():
    from harpyja.eval.locate_probe import require_live_stack

    assert require_live_stack(False, env={}) == "skip"


def test_require_live_stack_fails_when_env_set():
    from harpyja.eval.locate_probe import require_live_stack

    assert require_live_stack(False, env={"HARPYJA_REQUIRE_LIVE_STACK": "1"}) == "fail"


def test_scout_stack_available_is_scout_scoped_not_deep():
    # Scout-only availability must NOT depend on Deno (Tier-2). An unreachable endpoint
    # → False regardless of Deno; and the result is always a bool.
    from harpyja.eval.locate_probe import scout_stack_available

    # a definitely-dead port → not reachable → False (proves it probes the endpoint,
    # not Deno). Port 9 (discard) is not served locally under test.
    assert scout_stack_available(endpoint="http://127.0.0.1:9/v1") is False
    assert isinstance(scout_stack_available(endpoint="http://127.0.0.1:9/v1"), bool)


# ---- Spec 0023 (AC8): raw-arm provenance precondition ----------------------

_RAW_ISSUE = (
    "The retry backoff handler intermittently drops the final attempt when the queue "
    "drains under load and the worker pool is saturated during a sudden burst of jobs.\n\n"
    "Steps to reproduce: enqueue many jobs, saturate the workers, and observe that the "
    "last retry is silently skipped instead of being scheduled after the backoff delay."
)


def _raw_case(case_id: str, *, spans) -> EvalCase:
    return _case(case_id, spans=spans, query=_RAW_ISSUE)


def test_is_raw_issue_true_for_multiparagraph_body():
    from harpyja.eval.locate_probe import is_raw_issue

    assert is_raw_issue(_RAW_ISSUE) is True


def test_is_raw_issue_false_for_short_single_line():
    from harpyja.eval.locate_probe import is_raw_issue

    assert is_raw_issue("where is the retry logic?") is False


def test_is_raw_issue_false_for_blank():
    from harpyja.eval.locate_probe import is_raw_issue

    assert is_raw_issue("   \n  ") is False


# ---- Spec 0023 (AC3/AC7/AC8): paired reformulation probe -------------------


def test_paired_probe_emits_per_case_rows():
    from harpyja.eval.locate_probe import run_paired_reformulation_probe

    # Two raw cases; scout is called twice per usable case (raw arm, distilled arm).
    scout = _FakeScout(
        [
            ([], ScoutTally()),                            # c1 raw → EMPTY
            ([CodeSpan("a.py", 100, 120)], ScoutTally()),  # c1 distilled → CORRECT
            ([], ScoutTally()),                            # c2 raw → EMPTY
            ([CodeSpan("b.py", 100, 120)], ScoutTally()),  # c2 distilled → CORRECT
        ]
    )
    cases = [
        _raw_case("r-1", spans=[("a.py", 100, 120)]),
        _raw_case("r-2", spans=[("b.py", 100, 120)]),
    ]
    res = run_paired_reformulation_probe(
        cases, stack=_FakeStack(scout), repo_path="/repo", window=50
    )
    assert res.usable_n == 2
    assert len(res.paired_rows) == 2
    assert res.paired_rows[0].raw_bucket is LocateBucket.EMPTY
    assert res.paired_rows[0].distilled_bucket is LocateBucket.CORRECT


def test_paired_probe_delta_file_accuracy_paired():
    from harpyja.eval.locate_probe import run_paired_reformulation_probe

    scout = _FakeScout(
        [
            ([], ScoutTally()),                            # raw → EMPTY (no file)
            ([CodeSpan("a.py", 100, 120)], ScoutTally()),  # distilled → CORRECT (file found)
        ]
    )
    res = run_paired_reformulation_probe(
        [_raw_case("r-1", spans=[("a.py", 100, 120)])],
        stack=_FakeStack(scout), repo_path="/repo", window=50,
    )
    # distillation found the file where raw did not → positive paired file-accuracy delta.
    assert res.delta_file_accuracy == 1.0
    assert res.delta_empty == 1.0


def test_paired_probe_discordant_count_recorded():
    from harpyja.eval.locate_probe import run_paired_reformulation_probe

    scout = _FakeScout(
        [([], ScoutTally()), ([CodeSpan("a.py", 100, 120)], ScoutTally())]
    )
    res = run_paired_reformulation_probe(
        [_raw_case("r-1", spans=[("a.py", 100, 120)])],
        stack=_FakeStack(scout), repo_path="/repo", window=50,
    )
    assert res.discordant_pairs == 1


def test_paired_probe_excludes_non_raw_from_usable_n():
    from harpyja.eval.locate_probe import run_paired_reformulation_probe

    # One raw case (2 scout calls) + one terse case (excluded, 0 scout calls).
    scout = _FakeScout(
        [([], ScoutTally()), ([CodeSpan("a.py", 100, 120)], ScoutTally())]
    )
    cases = [
        _raw_case("raw-1", spans=[("a.py", 100, 120)]),
        _case("terse-1", spans=[("b.py", 1, 2)], query="fix the bug"),
    ]
    res = run_paired_reformulation_probe(
        cases, stack=_FakeStack(scout), repo_path="/repo", window=50
    )
    assert res.usable_n == 1
    assert "terse-1" in res.excluded_case_ids


def test_paired_probe_usable_n_below_min_n_marks_inconclusive():
    from harpyja.eval.benchmark_fit import (
        PREREGISTERED_CONFIG,
        Axis1Verdict,
        InconclusiveReason,
        aggregate_paired,
        decide_axis1,
    )
    from harpyja.eval.locate_probe import run_paired_reformulation_probe

    scout = _FakeScout(
        [([], ScoutTally()), ([CodeSpan("a.py", 100, 120)], ScoutTally())]
    )
    res = run_paired_reformulation_probe(
        [_raw_case("r-1", spans=[("a.py", 100, 120)])],
        stack=_FakeStack(scout), repo_path="/repo", window=50,
    )
    assert res.usable_n < PREREGISTERED_CONFIG.min_n
    verdict, reason = decide_axis1(
        aggregate_paired(res.paired_rows), usable_n=res.usable_n
    )
    assert verdict is Axis1Verdict.INCONCLUSIVE
    assert reason is InconclusiveReason.INSUFFICIENT_POWER


# ---- Spec 0023 (AC7): extend, don't break the 0022 seam --------------------


def test_reformulation_result_additive_fields_default():
    from harpyja.eval.locate_probe import ReformulationResult

    # The 0022 constructor shape still works; new fields default (no per-case pairs).
    r = ReformulationResult(
        n=1, raw_empty_rate=1.0, distilled_empty_rate=0.0, delta_empty=1.0
    )
    assert r.paired_rows == ()
    assert r.delta_file_accuracy == 0.0
    assert r.discordant_pairs == 0
    assert r.llm_delta_empty is None
    assert r.usable_n == 0
    assert r.excluded_case_ids == ()


def test_run_reformulation_probe_unchanged():
    from harpyja.eval.locate_probe import run_reformulation_probe

    scout = _FakeScout(
        [([], ScoutTally()), ([CodeSpan("a.py", 100, 120)], ScoutTally())]
    )
    res = run_reformulation_probe(
        [_case("r-1", spans=[("a.py", 100, 120)])],
        stack=_FakeStack(scout), repo_path="/repo", window=50, distill=lambda q: "retry",
    )
    # the legacy aggregate-rate contract is intact.
    assert res.raw_empty_rate == 1.0
    assert res.distilled_empty_rate == 0.0
    assert res.delta_empty == 1.0
