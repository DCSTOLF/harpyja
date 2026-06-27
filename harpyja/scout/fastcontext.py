"""`FastContextBackend` — the first `ScoutBackend` impl (Microsoft FastContext).

The FastContext package + version is the sole open question for this wave, so it
is reached only through an **injected** ``client`` callable — there is no
top-level hard import that could break the suite if the dependency is absent or
its API moves. The backend's job is narrow: assemble the local-only tool
whitelist and delegate, returning the client's `<final_answer>` spans for the
caller to normalize.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from harpyja.scout.tools import build_tool_whitelist
from harpyja.server.types import CodeSpan

# A FastContext client takes (query, seed, tools) and returns candidate spans.
FastContextClient = Callable[[str, list[CodeSpan], dict[str, Any]], list[CodeSpan]]


class FastContextBackend:
    def __init__(
        self,
        *,
        client: FastContextClient,
        model_client: Any,
        read: Any,
        glob: Any,
        grep: Any,
    ) -> None:
        self._client = client
        self._tools = build_tool_whitelist(model_client, read=read, glob=glob, grep=grep)

    def run(self, query: str, seed: list[CodeSpan]) -> list[CodeSpan]:
        return self._client(query, seed, self._tools)
