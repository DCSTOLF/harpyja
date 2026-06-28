"""Query classifier — point vs broad (spec 0008, AC2).

A `point` query targets a specific symbol / file / location; a `broad` query asks
to trace, audit, or survey behavior across the repo. The classification picks the
matrix row (point → cheap Tier-0/1 ladder; broad → straight to Deep).

This wave ships a **heuristic** only. `classify_query` is the pluggable seam: a
`Classifier = Callable[[str], Classification]` that a model classifier can replace
later without touching the planning matrix or the ACs. Ambiguous → `point` by
design — the cheap path is the default, and the gate/ladder escalate on a real
signal rather than over-classifying up front.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Literal

Classification = Literal["point", "broad"]
Classifier = Callable[[str], Classification]

# Lexical signals that a query wants a survey/trace rather than one location.
# Matched as whole words/phrases, case-insensitively.
_BROAD_TRIGGERS = (
    "trace",
    "audit",
    "overall",
    "architecture",
    "lifecycle",
    "end-to-end",
    "end to end",
    "everywhere",
    "all the",
    "every ",
    "across",
    "flow through",
    "walk through",
    "pipeline",
    "how does",
    "data flow",
)


def classify_query(query: str) -> Classification:
    """Classify a query as `point` or `broad`; ambiguous → `point`."""
    text = query.strip().lower()
    if not text:
        return "point"
    for trigger in _BROAD_TRIGGERS:
        if trigger.endswith(" "):
            # Trailing-space triggers (e.g. "every ") match a word boundary start.
            if re.search(rf"\b{re.escape(trigger.strip())}\b", text):
                return "broad"
        elif trigger in text:
            return "broad"
    return "point"
