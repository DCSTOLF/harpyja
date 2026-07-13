"""Spec 0045 — trajectory-only confidence signals (gold-blind, scout-side).

Moved here from ``eval/submission_observability.py`` (spec 0044) so the refined
confidence gate (spec 0045) can CONSUME them without importing eval/ — the gate
is gold-blind by construction. These functions see only a persisted trajectory
(tool-result spans in order); none takes gold. ``eval/submission_observability``
now imports them BACK by identity (one definition, no drift); the gold-needing
``classify_confidence_null`` stays eval-side.

- ``spans_overlap_line`` — the gold-free span-overlap primitive: same file, both
  spans line-shaped, inclusive ranges intersect. It AGREES with eval's
  ``metrics.span_hit_kind`` "line" grade on tool-vs-tool spans (pinned in
  test_confidence_signals) so ONE overlap definition survives without a
  scout->eval edge.
- (b) ``grep_hits_inside_symbol_spans`` — grep spans lying WITHIN an
  earlier-returned symbols span (same file, containment, ordered).
- (c) ``convergent_evidence`` — >=2 DISTINCT tools returned line-overlapping
  spans on one file.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from typing import Any

from harpyja.server.types import CodeSpan

# The canonical CodeSpan-field allowlist + tool-content parser (spec 0043,
# moved here so BOTH the gold-blind scout side and the eval side share ONE
# definition; ``eval/submission_gap`` re-exports these by identity).
_CODESPAN_FIELDS = {"path", "start_line", "end_line", "symbol", "language", "kind"}


def _parse_tool_content(content: Any) -> tuple[list[CodeSpan], bool]:
    """Parse one tool-role message's stringified content.

    Returns ``(spans, decodable)``. A non-list string is the 0035 marker shape —
    no spans, decodable. A list-shaped string that fails exact parsing is
    undecodable (``([], False)``) — the caller types it, never drops it.
    """
    if not isinstance(content, str):
        return [], False
    text = content.strip()
    if not text.startswith("["):
        return [], True
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        return [], False
    if not isinstance(tree.body, ast.List):
        return [], False
    spans: list[CodeSpan] = []
    for node in tree.body.elts:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            continue  # 0042 ANNOTATION marker riding ahead of real spans
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "CodeSpan"
        ):
            return [], False
        try:
            kwargs = {
                kw.arg: ast.literal_eval(kw.value)
                for kw in node.keywords
                if kw.arg in _CODESPAN_FIELDS
            }
            spans.append(CodeSpan(**kwargs))
        except (ValueError, SyntaxError, TypeError):
            return [], False
    return spans, True


def spans_overlap_line(a: CodeSpan, b: CodeSpan) -> bool:
    """Gold-free "line" overlap: same file, both line-shaped, ranges intersect.

    Matches the eval single-oracle ``span_hit_kind(...) == "line"`` branch for
    two spans that both carry lines — pinned in test_confidence_signals.
    """
    if a.path != b.path:
        return False
    if a.start_line is None or a.end_line is None:
        return False
    if b.start_line is None or b.end_line is None:
        return False
    return a.start_line <= b.end_line and b.start_line <= a.end_line


def tool_spans_in_order(
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
    spans = tool_spans_in_order(trajectory)
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
    """(c): >=2 distinct tools returned line-overlapping spans on the same
    file — overlap judged through the gold-free ``spans_overlap_line``."""
    spans = tool_spans_in_order(trajectory)
    for _pos_a, name_a, span_a in spans:
        for _pos_b, name_b, span_b in spans:
            if name_b == name_a:
                continue
            if spans_overlap_line(span_a, span_b):
                return True
    return False
