"""The Scout backend boundary (Tier 1).

`ScoutBackend` is the narrow, swappable seam between Harpyja and whatever runs
the exploratory model loop (FastContext is the first impl). Keeping it a Protocol
means tests inject a fake with no live model, and the FastContext package/version
question stays isolated behind this one interface.
"""

from __future__ import annotations

from typing import Protocol

from harpyja.server.types import CodeSpan


class ScoutBackend(Protocol):
    """Run an exploratory query and return candidate spans.

    `seed` are Tier-0 hint spans; the backend may use them to start warm. The
    return value is untrusted and is normalized by the caller before use.
    """

    def run(self, query: str, seed: list[CodeSpan]) -> list[CodeSpan]: ...
