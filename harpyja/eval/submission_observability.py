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
from harpyja.eval.submission_gap import _parse_tool_content
from harpyja.server.types import CodeSpan


def _tool_spans_in_order(
    trajectory: Mapping[str, Any],
) -> list[tuple[int, str, CodeSpan]]:
    """(position, tool_name, span) for every decodable tool-result span, in
    trajectory order. Tool names are attributed via the tool_call_id map from
    the assistant messages' tool_calls."""
    id_to_name: dict[str, str] = {}
    out: list[tuple[int, str, CodeSpan]] = []
    pos = 0
    for turn in trajectory.get("model_turns", []):
        if turn.get("role") == "assistant":
            for call in turn.get("tool_calls") or []:
                name = (call.get("function") or {}).get("name")
                call_id = call.get("id")
                if call_id and name:
                    id_to_name[call_id] = name
            continue
        if turn.get("role") != "tool":
            continue
        name = id_to_name.get(turn.get("tool_call_id", ""))
        if name is None:
            continue
        spans, _decodable = _parse_tool_content(turn.get("content"))
        for span in spans:
            out.append((pos, name, span))
        pos += 1
    return out


def grep_hits_inside_symbol_spans(trajectory: Mapping[str, Any]) -> int:
    """(b): count grep spans contained in an EARLIER symbols span (same file)."""
    spans = _tool_spans_in_order(trajectory)
    count = 0
    for pos, name, grep_span in spans:
        if name != "grep":
            continue
        if grep_span.start_line is None or grep_span.end_line is None:
            continue
        for sym_pos, sym_name, sym_span in spans:
            if sym_name != "symbols" or sym_pos >= pos:
                continue
            if (
                sym_span.path == grep_span.path
                and sym_span.start_line is not None
                and sym_span.end_line is not None
                and sym_span.start_line <= grep_span.start_line
                and grep_span.end_line <= sym_span.end_line
            ):
                count += 1
                break
    return count


def convergent_evidence(trajectory: Mapping[str, Any]) -> bool:
    """(c): ≥2 distinct tools returned overlapping spans on the same file —
    overlap judged through the ONE oracle's "line" grade."""
    spans = _tool_spans_in_order(trajectory)
    for _pos_a, name_a, span_a in spans:
        if span_a.start_line is None or span_a.end_line is None:
            continue
        for _pos_b, name_b, span_b in spans:
            if name_b == name_a:
                continue
            if span_b.start_line is None or span_b.end_line is None:
                continue
            if span_hit_kind(span_a, span_b) == "line":
                return True
    return False


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
