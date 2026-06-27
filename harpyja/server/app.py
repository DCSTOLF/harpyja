"""FastMCP application: registers the tools and exposes the transports.

Wave 1 registers all three tools — `harpyja_index`, `harpyja_read`,
`harpyja_locate` — with `harpyja_locate` backed by the Tier-0 orchestrator. The
search engine is built per-request from an injectable factory so `which`/engine
can be stubbed in tests; `harpyja_index` and `harpyja_read` never need ripgrep.
`run_http` binds loopback (127.0.0.1) by default (inbound air-gap).
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from fastmcp import FastMCP

from harpyja.config.settings import Settings, load_settings
from harpyja.index.indexer import index_repo
from harpyja.orchestrator.locate import locate
from harpyja.server.tools import read_snippet
from harpyja.server.types import LocateRequest, Mode
from harpyja.symbols.ripgrep import RipgrepEngine

DEFAULT_HTTP_HOST = "127.0.0.1"
DEFAULT_HTTP_PORT = 9000


def build_app(
    settings: Settings | None = None,
    *,
    which: Callable[[str], str | None] = shutil.which,
    engine_factory: Callable[[Settings], Any] | None = None,
    scout_factory: Callable[[Settings, str], Any] | None = None,
) -> FastMCP:
    """Construct the FastMCP app with Harpyja's three tools registered.

    `scout_factory(settings, repo_path)` builds the Tier-1 Scout engine for a
    request; it is only consulted for `mode in {fast, deep}`, so a default
    (`None`) keeps `auto` deterministic and free of any model/Gateway call.
    """
    settings = settings if settings is not None else load_settings()
    if engine_factory is None:

        def engine_factory(s: Settings) -> Any:
            return RipgrepEngine(s, which=which)

    app = FastMCP(name="harpyja")

    @app.tool(name="harpyja_index")
    def harpyja_index(repo_path: str, refresh: bool = False) -> dict[str, Any]:
        """Build/refresh the manifest for a repo. No ripgrep required."""
        return index_repo(repo_path, settings, rehash=refresh).to_dict()

    @app.tool(name="harpyja_read")
    def harpyja_read(repo_path: str, path: str, start: int, end: int) -> dict[str, Any]:
        """Return a bounded, path-confined code snippet."""
        return read_snippet(repo_path, path, start, end, settings)

    @app.tool(name="harpyja_locate")
    def harpyja_locate(
        query: str,
        repo_path: str,
        mode: Mode = "auto",
        max_results: int = 8,
        language_hint: str | None = None,
    ) -> dict[str, Any]:
        """Find files/lines relevant to a query (Tier 0: deterministic ripgrep)."""
        req = LocateRequest(
            query=query,
            repo_path=repo_path,
            mode=mode,
            max_results=max_results,
            language_hint=language_hint,
        )
        scout_engine = scout_factory(settings, repo_path) if scout_factory else None
        result = locate(
            req, settings, engine=engine_factory(settings), scout_engine=scout_engine
        )
        return asdict(result)

    return app


def run_stdio(app: FastMCP) -> None:
    """Serve over stdio (local agents)."""
    app.run(transport="stdio")


def run_http(
    app: FastMCP,
    host: str = DEFAULT_HTTP_HOST,
    port: int = DEFAULT_HTTP_PORT,
) -> None:
    """Serve over streamable HTTP, bound to loopback by default."""
    app.run(transport="http", host=host, port=port)
