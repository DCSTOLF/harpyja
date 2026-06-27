"""The Deep backend boundary (Tier 2).

`DeepBackend` is the narrow, swappable seam between Harpyja and whatever runs the
recursive explorer loop (`dspy.RLM` is the first impl). Keeping it a Protocol
means tests inject a fake with no live model/sandbox, and the dspy/Deno
package question stays isolated behind this one interface.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from harpyja.server.types import CodeSpan


@runtime_checkable
class DeepBackend(Protocol):
    """Run a recursive exploration and return candidate spans.

    `seed` are Tier-0 hint spans; `tools` is the exact bounded host-tool
    whitelist the backend may call. The return value is untrusted and is
    normalized by the caller before use.
    """

    def run(
        self,
        query: str,
        seed: list[CodeSpan],
        tools: Mapping[str, Any],
    ) -> list[CodeSpan]: ...
