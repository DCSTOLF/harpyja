"""Spec 0044 — eval-side postflight observability + the attributable null (AC4).

The demoted confidence signals are RECORD-ONLY fields — computed here,
POSTFLIGHT, over the persisted trajectory (never in the loop: the SUT delta
stays predicate + injection only) and NEVER gating:

- (b) ``grep_hits_inside_symbol_spans`` — grep spans lying WITHIN a
  previously-returned symbols span (same file, line-interval containment,
  ordered: the symbols evidence must precede the grep hit);
- (c) ``convergent_evidence`` — ≥2 DISTINCT tools returned spans on one file
  whose line intervals overlap (non-empty intersection, judged through the ONE
  oracle's "line" grade).

These fields exist so the NEXT spec can choose a better gate from measured
data instead of intuition.

``classify_confidence_null`` attributes a null result: ``never-fired`` /
``fired-but-ignored`` / ``fired-on-wrong-span`` (``None`` on a correct case —
there is no null to attribute). The wrong-span judgment routes through
``metrics.span_hit_kind`` imported BY IDENTITY (one-oracle-reuse; only a
``"line"`` hit counts — a path-only overlap is honestly NOT a gold hit, the
0043 detector posture). Span parsing reuses the 0043 detector's exact
Python-expression parser — never a second parser that could drift.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from harpyja.eval.metrics import Span, span_hit_kind

# (b)/(c) + the trajectory scanner MOVED to scout (gold-blind) so the 0045
# refined gate consumes the SAME definitions; imported BACK by identity here —
# one definition, no drift (spec 0045 §Invariants "ONE definition per signal").
# The gold-NEEDING ``classify_confidence_null`` stays eval-side (below).
from harpyja.scout.confidence_signals import (
    convergent_evidence,
    grep_hits_inside_symbol_spans,
    tool_spans_in_order,
)
from harpyja.server.types import CodeSpan

# Legacy private alias kept for any in-repo importer of the pre-0045 name.
_tool_spans_in_order = tool_spans_in_order

__all__ = [
    "classify_confidence_null",
    "convergent_evidence",
    "grep_hits_inside_symbol_spans",
    "tool_spans_in_order",
]


def classify_confidence_null(
    trajectory: Mapping[str, Any], expected: Sequence[Span]
) -> str | None:
    """Attribute a null (total, pure): never-fired / fired-but-ignored /
    fired-on-wrong-span; ``None`` on a correct case."""
    if trajectory.get("terminal_bucket") == "correct":
        return None
    if not trajectory.get("confidence_fired"):
        return "never-fired"
    firing = [
        CodeSpan(
            path=s.get("path"),
            start_line=s.get("start_line"),
            end_line=s.get("end_line"),
        )
        for s in trajectory.get("confidence_firing_spans") or []
    ]
    hit = any(
        span_hit_kind(span, exp) == "line" for span in firing for exp in expected
    )
    return "fired-but-ignored" if hit else "fired-on-wrong-span"
