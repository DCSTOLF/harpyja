"""FastMCP application: registers the tools and exposes the transports.

Wave 0 registers only `harpyja_locate` (returning the stub). `run_stdio` and
`run_http` are thin wrappers over FastMCP's transports so the CLI and tests can
drive them; `run_http` binds loopback (127.0.0.1) by default to keep the
air-gap intact on the inbound side (AC4).
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastmcp import FastMCP

from harpyja.server.tools import locate_stub
from harpyja.server.types import Mode

DEFAULT_HTTP_HOST = "127.0.0.1"
DEFAULT_HTTP_PORT = 9000


def build_app() -> FastMCP:
    """Construct the FastMCP app with Harpyja's tools registered."""
    app = FastMCP(name="harpyja")

    @app.tool(name="harpyja_locate")
    def harpyja_locate(
        query: str,
        repo_path: str,
        mode: Mode = "auto",
        max_results: int = 8,
        language_hint: str | None = None,
    ) -> dict[str, Any]:
        """Find files/lines relevant to a query. Wave 0: returns an empty stub."""
        result = locate_stub(
            query=query,
            repo_path=repo_path,
            mode=mode,
            max_results=max_results,
            language_hint=language_hint,
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
