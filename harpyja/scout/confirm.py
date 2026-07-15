"""Spec 0046 (AC3) — confirm-before-submit (gold-blind, scout-side).

Gate the OUTPUT, not the ACTION. Before a citation is emitted, a host-side
interceptor reads the candidate span and applies a CONCRETE, DETERMINISTIC
lexical/symbolic predicate — never a model judgment, never gold. This module is
SEPARATE from the reactive policy / confidence gate by construction: those
modules must not import it (AC3a), so confirmation can never throttle the
firing/exploration decision (the 0045 collapse is structurally impossible).

Outcomes:

- ``PASS``          — a query key identifier appears in the span text OR matches
  the span's symbol name → emit the citation clean.
- ``FAIL``          — key identifier(s) extractable but absent from the span →
  emit WITH a confidence flag (degraded honest citation), never silence.
- ``CONFIRM_ERROR`` — the predicate cannot decide (no extractable identifier, a
  line-less candidate, or an unreadable/empty span) → could-not-vouch → emit
  WITH a flag, same route as FAIL, distinct recorded cause. NEVER a guessed
  PASS/FAIL.
- ``NO_CANDIDATE``  — nothing was submitted → honest-empty, nothing to intercept.

The query key-identifier extraction is mechanical and reads the QUERY only.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from enum import StrEnum
from typing import Any

from harpyja.server.types import CodeSpan

# A host-side span reader: (path, start, end) -> a dict carrying "content"
# (reuses the existing read_span implementation — no new registered tool).
SpanReader = Callable[[str, int, int], "dict[str, Any]"]

# The minimum identifier length credited as a key identifier (drops "in"/"of"
# noise; keeps real symbol names). A pinned floor, not a free knob.
KEY_ID_MIN_LEN = 3

# An identifier-shaped token, with dotted paths (``mod.sub``) kept WHOLE.
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
# Backtick / single / double quote delimited spans (preferred when present).
_QUOTED = re.compile(r"[`\"']([^`\"']+)[`\"']")


class ConfirmationOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    CONFIRM_ERROR = "CONFIRM_ERROR"
    NO_CANDIDATE = "NO_CANDIDATE"


def _idents_in(text: str) -> list[str]:
    out: list[str] = []
    for m in _IDENT.finditer(text):
        tok = m.group(0)
        if len(tok.replace(".", "")) >= KEY_ID_MIN_LEN and tok not in out:
            out.append(tok)
    return out


def extract_query_key_identifiers(query: str) -> list[str]:
    """The query's key identifier(s), extracted mechanically from the QUERY only.

    Prefers backtick/quote-delimited tokens when the query contains them
    (the user pointed at a symbol); otherwise every identifier-shaped token at
    or above the length floor, dotted paths kept whole. Never reads gold.
    """
    if not query:
        return []
    quoted = _QUOTED.findall(query)
    if quoted:
        toks: list[str] = []
        for q in quoted:
            for tok in _idents_in(q):
                if tok not in toks:
                    toks.append(tok)
        if toks:
            return toks
    return _idents_in(query)


def confirm_before_submit(
    query: str,
    candidate: CodeSpan | None,
    read_span: SpanReader,
) -> ConfirmationOutcome:
    """Confirm the candidate span carries the query's intent (deterministic).

    Reuses the host-side ``read_span`` (no new registered tool). Total over:
    no candidate, a line-less candidate, an unreadable/empty span, no extractable
    identifier, and the PASS/FAIL decision.
    """
    if candidate is None:
        return ConfirmationOutcome.NO_CANDIDATE
    if candidate.start_line is None or candidate.end_line is None:
        return ConfirmationOutcome.CONFIRM_ERROR
    key_ids = extract_query_key_identifiers(query)
    if not key_ids:
        return ConfirmationOutcome.CONFIRM_ERROR
    try:
        result = read_span(candidate.path, candidate.start_line, candidate.end_line)
    except Exception:
        return ConfirmationOutcome.CONFIRM_ERROR
    text = result.get("content", "") if isinstance(result, dict) else ""
    if not text:
        return ConfirmationOutcome.CONFIRM_ERROR
    hay = text.lower()
    sym = (candidate.symbol or "").lower()
    for kid in key_ids:
        k = kid.lower()
        if k in hay or (sym and k == sym):
            return ConfirmationOutcome.PASS
    return ConfirmationOutcome.FAIL


def derive_submit_disposition(
    triggers_fired: list[str],
    confirmation_outcome: ConfirmationOutcome | None,
    *,
    has_candidate: bool,
) -> str:
    """Derive the attributable submit shape (total over the five shapes).

    A null is attributable across: ``no-candidate`` / ``confirm-failed-flagged``
    / ``triggered-and-explored`` / ``confirmed-then-submitted`` / ``never-triggered``.
    """
    if not has_candidate:
        return "no-candidate"
    if confirmation_outcome in (
        ConfirmationOutcome.FAIL,
        ConfirmationOutcome.CONFIRM_ERROR,
    ):
        return "confirm-failed-flagged"
    if triggers_fired:
        return "triggered-and-explored"
    if confirmation_outcome is ConfirmationOutcome.PASS:
        return "confirmed-then-submitted"
    return "never-triggered"
