"""`RlmBackend` — the first `DeepBackend` impl (`dspy.RLM`).

`dspy.RLM` runs a sandboxed Deno/Pyodide REPL and owns its own `dspy.LM`
(litellm) for the explorer loop and sub-LLM calls — it does **not** accept a
caller-supplied model function. So the air-gap is enforced by asserting the
configured endpoint is loopback **before** the LM is constructed (the single
`gateway.assert_local` helper), and proven by the network-deny integration test;
`dspy`/litellm opening its own connection to a loopback endpoint is the
"third-party in-process code" case the conventions cover.

There is **no top-level `import dspy`**: the default factory imports it lazily, so
the module (and the unit suite) load cleanly when `dspy` is absent. A **fresh**
RLM is built per request (not thread-safe with a custom interpreter).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

from harpyja.config.settings import Settings
from harpyja.gateway.gateway import assert_local as _assert_local
from harpyja.server.types import CodeSpan

# Builds a fresh RLM driver from (settings, tools); the result is callable as
# ``rlm(query=...)`` and exposes ``.answer`` (dspy Prediction).
RlmFactory = Callable[[Settings, Mapping[str, Any]], Any]
AssertLocal = Callable[..., None]

# Lenient `path:line` / `path:start-end` extraction from the model's free text.
_CITATION = re.compile(r"([\w./\-]+\.[A-Za-z0-9_]+):(\d+)(?:-(\d+))?")


def parse_citations(text: str) -> list[CodeSpan]:
    """Extract `path:line` / `path:start-end` refs into raw CodeSpans.

    Output is untrusted (a weak model emits noise) and is confined/validated by
    the caller's `normalize_spans`; a parse that finds nothing yields an empty,
    honest Tier-2 result rather than an error.
    """
    spans: list[CodeSpan] = []
    for path, start, end in _CITATION.findall(text or ""):
        s = int(start)
        spans.append(CodeSpan(path=path, start_line=s, end_line=int(end) if end else s))
    return spans


def _default_rlm_factory(settings: Settings, tools: Mapping[str, Any]) -> Any:  # pragma: no cover
    import dspy

    lm = dspy.LM(
        f"openai/{settings.lm_model}",
        api_base=settings.lm_api_base,
        api_key="ollama",
        max_tokens=settings.deep_token_ceiling,
    )
    rlm = dspy.RLM(
        "query -> answer",
        tools=list(tools.values()),
        max_iterations=max(1, settings.deep_max_subqueries),
        max_llm_calls=max(1, settings.deep_max_subqueries * 2),
        sub_lm=lm,
        verbose=False,
    )
    rlm.set_lm(lm)
    return rlm


class RlmBackend:
    def __init__(
        self,
        settings: Settings,
        *,
        rlm_factory: RlmFactory | None = None,
        assert_local: AssertLocal | None = None,
    ) -> None:
        self._settings = settings
        self._rlm_factory = rlm_factory or _default_rlm_factory
        self._assert_local = assert_local or _assert_local

    def run(
        self,
        query: str,
        seed: list[CodeSpan],
        tools: Mapping[str, Any],
    ) -> list[CodeSpan]:
        # Single air-gap helper: the endpoint must resolve loopback BEFORE the LM
        # (and any litellm connection) is constructed. A non-loopback endpoint
        # raises AirGapError here and the RLM is never built.
        self._assert_local(self._settings.lm_api_base, allow_remote=self._settings.allow_remote)

        rlm = self._rlm_factory(self._settings, tools)  # fresh instance per request
        prediction = rlm(query=_compose_prompt(query, seed))
        return parse_citations(getattr(prediction, "answer", "") or "")


def _compose_prompt(query: str, seed: list[CodeSpan]) -> str:
    if not seed:
        return query
    hints = ", ".join(f"{s.path}:{s.start_line}" for s in seed)
    return f"{query}\n\nTier-0 seed hints (starting points): {hints}"
