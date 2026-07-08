"""The four bounded, read-only host tools — the RLM's entire world (AC7/8/8a).

Each is a thin wrapper over existing Tier-0 machinery (manifest reader,
`RipgrepEngine`, the symbol index, `read_snippet`), bounded by the existing
`Settings` caps, and confined to the repo root via `server.tools.confine_path` —
because the RLM that calls these is untrusted code. `build_host_tools` returns
**exactly** `{list_manifest, search, symbols, read_span}` and nothing mutating.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from harpyja.config.settings import Settings
from harpyja.deep.budget import DeepBudget, DeepBudgetExceeded
from harpyja.index.manifest import ManifestEntry
from harpyja.server.tools import confine_path, read_snippet
from harpyja.server.types import CodeSpan
from harpyja.symbols.extract import SymbolRecord
from harpyja.symbols.symbols_io import record_to_codespan


class _Search:  # structural: anything with .search(pattern, scope)
    def search(self, pattern: str, scope: str | None = None) -> list[CodeSpan]: ...


def build_host_tools(
    repo_path: str,
    settings: Settings,
    *,
    search_engine: _Search,
    symbol_records: Sequence[SymbolRecord],
    manifest: Sequence[ManifestEntry],
    budget: DeepBudget,
) -> dict[str, Callable[..., Any]]:
    """Build the exact four-tool whitelist for one Deep request."""

    def _charge() -> None:
        if not budget.charge_tool_call():
            raise DeepBudgetExceeded(budget.truncated_bound or "tool-calls")

    def list_manifest(filter: str | None = None) -> list[dict[str, Any]]:
        _charge()
        entries = manifest
        if filter:
            entries = [e for e in entries if filter in e.path]
        return [
            {"path": e.path, "language": e.language, "prior": e.prior}
            for e in entries[: settings.manifest_page]
        ]

    def search(pattern: str, scope: str | None = None) -> list[CodeSpan]:
        _charge()
        scoped = str(confine_path(repo_path, scope)) if scope else repo_path
        spans = search_engine.search(pattern, scope=scoped)
        return spans[: settings.search_max_matches]  # defensive bound on untrusted loop

    def symbols(path: str) -> list[CodeSpan]:
        _charge()
        confine_path(repo_path, path)  # rejects a path outside the repo root
        return [record_to_codespan(r) for r in symbol_records if r.path == path]

    def read_span(path: str, start: int, end: int) -> dict[str, Any]:
        _charge()
        return read_snippet(repo_path, path, start, end, settings)

    return {
        "list_manifest": list_manifest,
        "search": search,
        "symbols": symbols,
        "read_span": read_span,
    }
