"""Spec 0043 — the found-but-unsubmitted detector (AC2).

A run where the model's tool results CONTAINED a gold-overlapping span but it
never reached ``submit_citations`` must be distinguishable from a run that
never found it — today both collapse into "empty"/RFWS, the degrade-masks-
outcome class. The detector is a PURE PROJECTION over one persisted trajectory:

- Gold overlap routes through the ONE existing oracle — ``metrics.span_hit_kind``
  imported BY IDENTITY (never a second overlap definition); only a ``"line"``
  hit counts, so a path-only (file-level) span is honestly NOT a find.
- The submit side routes through the EXISTING 0033 ``citations_submitted`` /
  ``citations_surviving`` counts (one-counter-reuse) — never re-parsed from
  history; ``(>0, 0)`` is the 0033 found-then-dropped shape.
- Tool results in persisted history are STRINGIFIED ``CodeSpan`` reprs, so the
  parse is exact Python-expression parsing (``ast``), not regex. A list-shaped
  tool message that cannot be decoded is the DISTINCT typed outcome
  ``DETECTOR_INCONCLUSIVE`` — never silently folded into ``NEVER_FOUND`` (that
  would reintroduce, one level down, the collapse this module exists to kill).
  A bare non-list string is the KNOWN 0035 marker shape: parseable-as-no-spans.
- A PROVEN hit dominates an undecodable sibling message: found is found.
"""

from __future__ import annotations

import ast
import enum
from collections.abc import Mapping, Sequence
from typing import Any

from harpyja.eval.metrics import Span, span_hit_kind
from harpyja.server.types import CodeSpan

# Cited by the frozen PREREGISTERED_DIAGNOSIS_CONFIG_0043 so the BEFORE
# (retroactive, offline) and AFTER (live) sides provably ran ONE detector.
DETECTOR_VERSION = "0043/1"


class SubmissionOutcome(enum.Enum):
    """The total typed-outcome enum over the AC2 fixture matrix."""

    FOUND_UNSUBMITTED = "found-unsubmitted"
    SUBMITTED = "submitted"
    SUBMITTED_THEN_DROPPED = "submitted-then-dropped"
    NEVER_FOUND = "never-found"
    DETECTOR_INCONCLUSIVE = "detector-inconclusive"


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
        # Bare marker string (0035 REPLACEMENT shape) — a known no-span result.
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
            # 0042 ANNOTATION shape: a marker string riding ahead of real spans.
            continue
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


def _tool_observed_spans(
    trajectory: Mapping[str, Any],
) -> tuple[list[CodeSpan], bool]:
    """All spans observed in TOOL-role messages, plus an any-undecodable flag."""
    spans: list[CodeSpan] = []
    any_undecodable = False
    for turn in trajectory.get("model_turns", []):
        if turn.get("role") != "tool":
            continue
        parsed, decodable = _parse_tool_content(turn.get("content"))
        if not decodable:
            any_undecodable = True
        spans.extend(parsed)
    return spans, any_undecodable


def classify_submission(
    trajectory: Mapping[str, Any], expected: Sequence[Span]
) -> SubmissionOutcome:
    """Type one persisted trajectory's submission outcome (total, pure).

    Precedence: the 0033 counts decide the submit side first (they are recorded
    facts, no parsing); only an unsubmitted run is classified from its
    tool-observed spans, where a proven line-overlap hit dominates an
    undecodable sibling message.
    """
    surviving = trajectory.get("citations_surviving")
    submitted = trajectory.get("citations_submitted")
    if isinstance(surviving, int) and surviving > 0:
        return SubmissionOutcome.SUBMITTED
    if isinstance(submitted, int) and submitted > 0:
        return SubmissionOutcome.SUBMITTED_THEN_DROPPED

    spans, any_undecodable = _tool_observed_spans(trajectory)
    found = any(
        span_hit_kind(span, exp) == "line" for span in spans for exp in expected
    )
    if found:
        return SubmissionOutcome.FOUND_UNSUBMITTED
    if any_undecodable:
        return SubmissionOutcome.DETECTOR_INCONCLUSIVE
    return SubmissionOutcome.NEVER_FOUND
