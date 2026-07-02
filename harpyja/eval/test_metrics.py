"""AC2/AC3 — span-hit oracle (D2) and aggregate/gate metrics (D1/D3/D5)."""

from __future__ import annotations

from dataclasses import dataclass

from harpyja.eval.metrics import (
    CaseOutcome,
    escalation_rate,
    gate_catch_rate,
    gate_false_escalation,
    span_hit_primary,
    span_hit_secondary,
    tier01_resolve_rate,
    tier1_correct,
)


@dataclass(frozen=True)
class Span:
    path: str
    start_line: int
    end_line: int


def _outcome(
    *,
    classification="point",
    expected=(("a.py", 10, 20),),
    tier1=(("a.py", 10, 20),),
    final=(("a.py", 10, 20),),
    tiers_run=(0, 1),
):
    return CaseOutcome(
        case_id="c",
        classification=classification,
        expected_spans=tuple(Span(*e) for e in expected),
        tier1_citations=tuple(Span(*t) for t in tier1),
        final_citations=tuple(Span(*f) for f in final),
        tiers_run=tuple(tiers_run),
    )


# ---- AC2: span-hit primary (line-range overlap) ----------------------------

def test_span_hit_primary_overlap_true_on_partial_overlap():
    assert span_hit_primary(Span("a.py", 15, 25), Span("a.py", 10, 20)) is True


def test_span_hit_primary_touching_ranges():
    # end == start counts as overlap (D6).
    assert span_hit_primary(Span("a.py", 20, 30), Span("a.py", 10, 20)) is True


def test_span_hit_primary_false_on_same_file_disjoint():
    assert span_hit_primary(Span("a.py", 30, 40), Span("a.py", 10, 20)) is False


def test_span_hit_primary_false_on_different_file():
    assert span_hit_primary(Span("b.py", 10, 20), Span("a.py", 10, 20)) is False


# ---- AC2: span-hit secondary (file + proximity) ----------------------------

def test_span_hit_secondary_true_within_proximity_window():
    # disjoint by 5 lines, window 50 -> credited.
    assert span_hit_secondary(Span("a.py", 25, 30), Span("a.py", 10, 20), window=50) is True


def test_span_hit_secondary_false_outside_proximity_window():
    assert span_hit_secondary(Span("a.py", 100, 110), Span("a.py", 10, 20), window=50) is False


def test_span_hit_secondary_false_on_different_file():
    assert span_hit_secondary(Span("b.py", 10, 20), Span("a.py", 10, 20), window=50) is False


def test_span_hit_secondary_true_on_overlap():
    # overlap is distance 0 -> always within any window.
    assert span_hit_secondary(Span("a.py", 15, 25), Span("a.py", 10, 20), window=0) is True


# ---- AC3 / D5: tier1 correctness (any citation overlaps any expected, same file) ----

def test_tier1_correctness_any_citation_any_expected_span_same_file():
    cites = (Span("z.py", 1, 2), Span("a.py", 18, 19))
    expected = (Span("a.py", 10, 20), Span("q.py", 5, 6))
    assert tier1_correct(cites, expected) is True


def test_tier1_correct_false_when_no_citation_overlaps():
    cites = (Span("z.py", 1, 2),)
    expected = (Span("a.py", 10, 20),)
    assert tier1_correct(cites, expected) is False


def test_tier1_correct_false_on_empty_citations():
    assert tier1_correct((), (Span("a.py", 10, 20),)) is False


# ---- AC3: escalation rate + tier0/1 resolve rate (over ALL auto cases) ------

def test_escalation_rate_counts_tier2_over_all_auto_cases():
    outcomes = [
        _outcome(tiers_run=(0, 1)),
        _outcome(tiers_run=(0, 1, 2)),
        _outcome(classification="broad", tiers_run=(0, 2)),
        _outcome(tiers_run=(0,)),
    ]
    # 2 of 4 reached Tier-2.
    assert escalation_rate(outcomes) == 0.5


def test_tier01_resolve_rate():
    outcomes = [
        _outcome(tiers_run=(0, 1)),
        _outcome(tiers_run=(0, 1, 2)),
        _outcome(tiers_run=(0,)),
        _outcome(tiers_run=(1,)),
    ]
    # 3 of 4 terminate at tier <= 1.
    assert tier01_resolve_rate(outcomes) == 0.75


# ---- AC3 / D1: gate metrics scoped to the point subset ----------------------

def test_gate_metrics_scoped_to_point_subset_excludes_broad():
    # A broad case that, if counted, would be a wrong-Tier-1 escalation and skew
    # the denominators. It must be excluded entirely (D1).
    outcomes = [
        # point, wrong tier-1 (final/tier1 miss), escalated -> caught
        _outcome(classification="point", tier1=(("b.py", 1, 2),), tiers_run=(0, 1, 2)),
        # broad, would look like wrong+escalated but must be excluded
        _outcome(classification="broad", tier1=(("b.py", 1, 2),), tiers_run=(0, 2)),
    ]
    rate, caught, wrong_total = gate_catch_rate(outcomes)
    assert wrong_total == 1  # broad excluded
    assert caught == 1
    assert rate == 1.0


def test_gate_catch_rate_over_wrong_tier1_denominator():
    outcomes = [
        # wrong + escalated = caught
        _outcome(tier1=(("b.py", 1, 2),), tiers_run=(0, 1, 2)),
        # wrong + NOT escalated = missed
        _outcome(tier1=(("b.py", 1, 2),), tiers_run=(0, 1)),
        # correct tier-1 -> not in this denominator
        _outcome(tier1=(("a.py", 10, 20),), tiers_run=(0, 1)),
    ]
    rate, caught, wrong_total = gate_catch_rate(outcomes)
    assert (caught, wrong_total) == (1, 2)
    assert rate == 0.5


def test_gate_false_escalation_rate_over_correct_tier1_denominator():
    outcomes = [
        # correct + escalated = false escalation
        _outcome(tier1=(("a.py", 10, 20),), tiers_run=(0, 1, 2)),
        # correct + not escalated = good stop
        _outcome(tier1=(("a.py", 10, 20),), tiers_run=(0, 1)),
        # correct + not escalated = good stop
        _outcome(tier1=(("a.py", 12, 18),), tiers_run=(0, 1)),
        # wrong tier-1 -> not in this denominator
        _outcome(tier1=(("b.py", 1, 2),), tiers_run=(0, 1, 2)),
    ]
    rate, false_esc, correct_total = gate_false_escalation(outcomes)
    assert (false_esc, correct_total) == (1, 3)
    assert abs(rate - 1 / 3) < 1e-9


# ---- AC3: same oracle (D3/D5) ----------------------------------------------

def test_gate_metrics_use_same_oracle_as_span_hit():
    import harpyja.eval.metrics as m

    calls: list[str] = []
    original = m._any_primary_overlap

    def spy(cites, expected):
        calls.append("oracle")
        return original(cites, expected)

    m._any_primary_overlap = spy  # type: ignore[assignment]
    try:
        outcome = _outcome(tier1=(("a.py", 10, 20),), tiers_run=(0, 1))
        gate_catch_rate([outcome])
        gate_false_escalation([outcome])
        tier1_correct(outcome.tier1_citations, outcome.expected_spans)
    finally:
        m._any_primary_overlap = original  # type: ignore[assignment]
    # all three correctness judgments route through the one oracle.
    assert calls.count("oracle") >= 3


# ---- AC3 / D2: zero-denominator -> null-with-count --------------------------

def test_gate_catch_rate_null_with_count_on_zero_denominator():
    # every point case has a correct Tier-1 -> no wrong-Tier-1 cases.
    outcomes = [_outcome(tier1=(("a.py", 10, 20),), tiers_run=(0, 1))]
    rate, caught, wrong_total = gate_catch_rate(outcomes)
    assert rate is None
    assert (caught, wrong_total) == (0, 0)


def test_gate_false_escalation_null_with_count_on_zero_denominator():
    # every point case has a wrong Tier-1 -> no correct-Tier-1 cases.
    outcomes = [_outcome(tier1=(("b.py", 1, 2),), tiers_run=(0, 1, 2))]
    rate, false_esc, correct_total = gate_false_escalation(outcomes)
    assert rate is None
    assert (false_esc, correct_total) == (0, 0)


# ---- Spec 0019 (AC5): one oracle governs BOTH gate denominators -------------

def test_gate_denominator_membership_flips_with_the_single_oracle():
    # A case's Tier-1 correctness (the ONE overlap oracle) decides which gate
    # denominator it lands in — correct -> false-escalation population; wrong ->
    # catch-rate population. The two are mutually exclusive and both defined by the
    # same oracle, so a locate-accuracy flip must move the case between them.
    correct = _outcome(tier1=(("a.py", 10, 20),), tiers_run=(0, 1))  # overlaps expected
    assert tier1_correct(correct.tier1_citations, correct.expected_spans) is True
    _, _, fe_total = gate_false_escalation([correct])
    _, _, cr_total = gate_catch_rate([correct])
    assert (fe_total, cr_total) == (1, 0)  # in false-esc denom, not catch-rate

    wrong = _outcome(tier1=(("b.py", 1, 2),), tiers_run=(0, 1, 2))  # misses expected
    assert tier1_correct(wrong.tier1_citations, wrong.expected_spans) is False
    _, _, fe_total_w = gate_false_escalation([wrong])
    _, _, cr_total_w = gate_catch_rate([wrong])
    assert (fe_total_w, cr_total_w) == (0, 1)  # flipped: catch-rate denom, not false-esc


# --- Spec 0011 (citation-shape): file-level (line-less) path-only overlap (AC18) ---


@dataclass(frozen=True)
class _FileLevelSpan:
    path: str
    start_line: int | None = None
    end_line: int | None = None


def test_span_hit_path_only_for_file_level_citation():
    # AC18: a file-level (line-less) citation in the same file as an expected span
    # scores a PATH-ONLY match — counted as a hit, recorded distinctly from a line
    # match, never a line hit.
    from harpyja.eval.metrics import span_hit_kind

    cited = _FileLevelSpan("a.py")  # None lines
    expected = Span("a.py", 10, 20)
    assert span_hit_primary(cited, expected) is True
    assert span_hit_kind(cited, expected) == "file"
    # a real line-overlap is a DISTINCT kind
    assert span_hit_kind(Span("a.py", 12, 14), expected) == "line"
    # different file → no match
    assert span_hit_kind(_FileLevelSpan("other.py"), expected) is None


def test_span_hit_file_level_branch_before_line_arithmetic():
    # AC18: the path-only branch is taken BEFORE the line comparison, so a None
    # cited line never reaches the arithmetic (no crash).
    cited = _FileLevelSpan("a.py")
    expected = Span("a.py", 1, 5)
    # would raise TypeError (None <= int) if the branch were not taken first
    assert span_hit_primary(cited, expected) is True
