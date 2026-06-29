"""Eval metrics (AC2, AC3).

One overlap oracle, reused everywhere (D3/D5): `_any_primary_overlap` is the
single notion of "a citation set is correct for these expected spans." Span-hit
accuracy, gate catch-rate, and gate false-escalation all route through it — there
is no second definition of correctness that could drift.

Metric domains (D1):
- `escalation_rate` / `tier01_resolve_rate` range over **all** auto cases.
- `gate_catch_rate` / `gate_false_escalation` range over the **point-query
  subset only** — broad queries bypass the gate (straight to Deep per the 0008
  matrix) and are excluded from both gate denominators.

Tier-1 correctness is judged against the **Tier-1 (Scout) citations**, captured by
the runner independently of escalation — when the gate escalates, the final
citations are Tier-2's and cannot reveal whether Tier-1 was wrong. So a
`CaseOutcome` carries both `tier1_citations` (gate oracle) and `final_citations`
(accuracy).

Zero-denominator (D2): a gate metric over an empty population returns
`(None, 0, 0)` — an explicit null with its (zero) counts, never a silent 0.0.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


class Span(Protocol):
    """Anything with a repo-relative path and an inclusive line range."""

    path: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class CaseOutcome:
    """The per-case observation the metric layer consumes.

    `tier1_citations` are Scout's (Tier-1) output captured independently of
    escalation; `final_citations` are what the auto path ultimately returned.
    """

    case_id: str
    classification: str
    expected_spans: tuple[Span, ...]
    tier1_citations: tuple[Span, ...]
    final_citations: tuple[Span, ...]
    tiers_run: tuple[int, ...]


# ---- the single overlap oracle (D3/D5) -------------------------------------

def span_hit_kind(cited: Span, expected: Span) -> str | None:
    """Classify the overlap of one cited span against one expected span.

    Returns ``"line"`` (same file + overlapping line ranges, D6), ``"file"`` (same
    file but the cited span is **file-level** — line-less, spec 0011 — so it is a
    coarse path-only match), or ``None`` (no match). The file-level branch is taken
    **before** the line arithmetic, so a ``None`` cited line never reaches it. A
    file-level (path-only) hit is recorded **distinctly** and is never a line hit.
    """
    if cited.path != expected.path:
        return None
    if cited.start_line is None or cited.end_line is None:
        return "file"  # path-only (coarse) match — honest precision in measurement
    if cited.start_line <= expected.end_line and expected.start_line <= cited.end_line:
        return "line"
    return None


def span_hit_primary(cited: Span, expected: Span) -> bool:
    """Same file and overlapping ranges, OR a file-level path-only match (D6).

    The one oracle, routed through :func:`span_hit_kind` so a second definition of
    "hit" cannot drift; a coarse file-level hit still counts as a localization.
    """
    return span_hit_kind(cited, expected) is not None


def span_hit_secondary(cited: Span, expected: Span, window: int) -> bool:
    """Same file and within `window` lines (looser; overlap is distance 0).

    Spec 0011: a file-level (line-less) cited span is guarded **before** the line
    arithmetic — same-file is a path-only match (distance 0, within any window).
    """
    if cited.path != expected.path:
        return False
    if cited.start_line is None or cited.end_line is None:
        return True  # path-only proximity match (no line distance to compute)
    gap = max(expected.start_line - cited.end_line, cited.start_line - expected.end_line, 0)
    return gap <= window


def _any_primary_overlap(cited: Sequence[Span], expected: Sequence[Span]) -> bool:
    """D5: ANY cited span overlaps ANY expected span in the same file."""
    return any(span_hit_primary(c, e) for c in cited for e in expected)


def _any_secondary(cited: Sequence[Span], expected: Sequence[Span], window: int) -> bool:
    return any(span_hit_secondary(c, e, window) for c in cited for e in expected)


def tier1_correct(citations: Sequence[Span], expected: Sequence[Span]) -> bool:
    """Whether Tier-1's answer is correct: the D5 any/any primary oracle."""
    return _any_primary_overlap(citations, expected)


# ---- case-level accuracy ----------------------------------------------------

def case_span_hit_primary(outcome: CaseOutcome) -> bool:
    """Did the final answer hit (primary overlap) — the locate-accuracy oracle."""
    return _any_primary_overlap(outcome.final_citations, outcome.expected_spans)


def case_span_hit_secondary(outcome: CaseOutcome, window: int) -> bool:
    return _any_secondary(outcome.final_citations, outcome.expected_spans, window)


# ---- aggregate metrics over ALL auto cases ---------------------------------

def _escalated(outcome: CaseOutcome) -> bool:
    return 2 in outcome.tiers_run


def escalation_rate(outcomes: Sequence[CaseOutcome]) -> float:
    """% of auto queries reaching Tier-2 (all cases, both paths)."""
    if not outcomes:
        return 0.0
    return sum(1 for o in outcomes if _escalated(o)) / len(outcomes)


def tier01_resolve_rate(outcomes: Sequence[CaseOutcome]) -> float:
    """% of auto queries terminating at tier <= 1 (no Deep)."""
    if not outcomes:
        return 0.0
    return sum(1 for o in outcomes if o.tiers_run and max(o.tiers_run) <= 1) / len(outcomes)


def span_hit_rate_primary(outcomes: Sequence[CaseOutcome]) -> float:
    if not outcomes:
        return 0.0
    return sum(1 for o in outcomes if case_span_hit_primary(o)) / len(outcomes)


def span_hit_rate_secondary(outcomes: Sequence[CaseOutcome], window: int) -> float:
    if not outcomes:
        return 0.0
    return sum(1 for o in outcomes if case_span_hit_secondary(o, window)) / len(outcomes)


# ---- gate metrics over the POINT subset only (D1) --------------------------

def _point(outcomes: Sequence[CaseOutcome]) -> list[CaseOutcome]:
    return [o for o in outcomes if o.classification == "point"]


def gate_catch_rate(outcomes: Sequence[CaseOutcome]) -> tuple[float | None, int, int]:
    """Over wrong-Tier-1 *point* cases: fraction that escalated to Tier-2.

    Returns `(rate|None, caught, wrong_total)`; `None` with zero counts when no
    wrong-Tier-1 point case exists (D2).
    """
    wrong = [
        o for o in _point(outcomes)
        if not _any_primary_overlap(o.tier1_citations, o.expected_spans)
    ]
    caught = sum(1 for o in wrong if _escalated(o))
    if not wrong:
        return None, 0, 0
    return caught / len(wrong), caught, len(wrong)


def gate_false_escalation(outcomes: Sequence[CaseOutcome]) -> tuple[float | None, int, int]:
    """Over correct-Tier-1 *point* cases: fraction wrongly escalated to Tier-2.

    Returns `(rate|None, false_escalated, correct_total)`; `None` with zero counts
    when no correct-Tier-1 point case exists (D2).
    """
    correct = [
        o for o in _point(outcomes)
        if _any_primary_overlap(o.tier1_citations, o.expected_spans)
    ]
    false_esc = sum(1 for o in correct if _escalated(o))
    if not correct:
        return None, 0, 0
    return false_esc / len(correct), false_esc, len(correct)
