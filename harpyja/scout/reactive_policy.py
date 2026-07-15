"""Spec 0046 (AC2) — the reactive submission policy (gold-blind, scout-side).

Default to submitting the best span in hand; keep exploring ONLY on a NAMED
DISCONFIRMING trigger. Predicting span quality up front is the hard problem;
noticing that something CONTRADICTS the candidate is the easy one.

The three triggers are pre-registered and mechanically fixturable. All are
gold-blind — they read tool results and (for ``hit-in-comment``) source text
through an injected reader, never the gold answer. This module lives in
``scout/`` and imports nothing from ``eval/`` (ast-pinned in the test).

Placement: this decides "submit vs keep exploring" — it never extends the loop
budget. A triggered explore is still bounded by the existing ``scout_max_turns``
/ ``scout_wall_clock_s`` ceilings (0043's dawdle is bounded, not reopened).

Separation (AC3a): this module must NOT reference the confirm interceptor
(``harpyja.scout.confirm`` / ``ConfirmationOutcome`` / the disposition
derivation) — confirmation gates the OUTPUT, never the firing/exploration
decision, so the 0045 collapse is structurally impossible.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from typing import Any

from harpyja.scout.confidence_signals import tool_spans_in_order

# The closed, frozen trigger set; ORDER is the stable reporting order the
# set-valued result preserves.
REACTIVE_TRIGGERS_ORDER: tuple[str, ...] = (
    "symbols-empty",
    "hit-in-comment",
    "tool-disagreement",
)
REACTIVE_TRIGGERS = frozenset(REACTIVE_TRIGGERS_ORDER)

# A host-side line reader: (path, 1-based line) -> the source line text, or None
# when unreadable. Injected (reuses read_span host-side) — never touches gold.
LineReader = Callable[[str, int], "str | None"]

# Per-language whole-line-comment tokens for the ripgrep-fallback comment rule.
_LINE_COMMENT_TOKENS: dict[str, tuple[str, ...]] = {
    ".py": ("#",),
    ".rb": ("#",),
    ".sh": ("#",),
    ".go": ("//",),
    ".rs": ("//",),
    ".js": ("//",),
    ".jsx": ("//",),
    ".ts": ("//",),
    ".tsx": ("//",),
    ".c": ("//",),
    ".h": ("//",),
    ".cc": ("//",),
    ".cpp": ("//",),
    ".hpp": ("//",),
    ".cs": ("//",),
    ".java": ("//",),
}
_DOCSTRING_MARKERS = ('"""', "'''")


def _normalize_path(path: str) -> str:
    """Canonical form for cross-tool file-identity comparison (gold-free)."""
    return os.path.normpath(path.strip())


def _first_span_path(spans: list[tuple[int, str, Any]], tool: str) -> str | None:
    for _pos, name, span in spans:
        if name == tool and span.path:
            return span.path
    return None


def _symbols_returned_empty(trajectory: Mapping[str, Any]) -> bool:
    """A ``symbols`` call returned no spans (empty list or the 0035 marker).

    Detected from the raw turns: a tool result attributed to a ``symbols`` call
    whose parsed content carries zero spans (``[]`` or a bare marker string).
    """
    from harpyja.scout.confidence_signals import _parse_tool_content

    id_to_name: dict[str, str] = {}
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
        if id_to_name.get(turn.get("tool_call_id", "")) != "symbols":
            continue
        spans, _decodable = _parse_tool_content(turn.get("content"))
        if not spans:
            return True
    return False


def _is_comment_line(text: str, path: str) -> bool:
    """Deterministic whole-line comment / docstring-boundary rule (ripgrep
    fallback). A hit inside executable code is NOT a comment even if a comment
    shares the line — without a match column we only credit WHOLE-line comments
    and docstring-quote lines, never a trailing comment on a code line."""
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.startswith(_DOCSTRING_MARKERS):
        return True
    ext = os.path.splitext(path)[1].lower()
    for token in _LINE_COMMENT_TOKENS.get(ext, ()):
        if stripped.startswith(token):
            return True
    return False


def _grep_hit_in_comment(
    spans: list[tuple[int, str, Any]], line_reader: LineReader | None
) -> bool:
    if line_reader is None:
        return False
    for _pos, name, span in spans:
        if name != "grep" or span.start_line is None or not span.path:
            continue
        text = line_reader(span.path, span.start_line)
        if text is not None and _is_comment_line(text, span.path):
            return True
    return False


def _tool_disagreement(spans: list[tuple[int, str, Any]]) -> bool:
    grep_path = _first_span_path(spans, "grep")
    symbols_path = _first_span_path(spans, "symbols")
    if grep_path is None or symbols_path is None:
        return False
    return _normalize_path(grep_path) != _normalize_path(symbols_path)


def fired_triggers(
    trajectory: Mapping[str, Any],
    *,
    line_reader: LineReader | None = None,
) -> list[str]:
    """The set of disconfirming triggers that fired, in stable declaration order.

    Gold-blind: consumes only the trajectory's tool results (+ source text via
    ``line_reader`` for ``hit-in-comment``). An empty list means "nothing
    contradicts the candidate" — the reactive default is submit-best.
    """
    spans = tool_spans_in_order(trajectory)
    fired: dict[str, bool] = {
        "symbols-empty": _symbols_returned_empty(trajectory),
        "hit-in-comment": _grep_hit_in_comment(spans, line_reader),
        "tool-disagreement": _tool_disagreement(spans),
    }
    return [t for t in REACTIVE_TRIGGERS_ORDER if fired[t]]


def should_keep_exploring(
    trajectory: Mapping[str, Any],
    *,
    line_reader: LineReader | None = None,
) -> bool:
    """Keep exploring iff at least one NAMED trigger fired. No trigger -> submit
    the best span in hand (the reactive default). This decision never extends
    the loop budget; termination stays with the existing turn/wall-clock caps."""
    return bool(fired_triggers(trajectory, line_reader=line_reader))
