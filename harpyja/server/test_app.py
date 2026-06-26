"""RED (task 12): FastMCP app construction, tool registration, loopback default.

AC3/AC4 — build_app registers harpyja_locate and a call returns the schema-valid
stub; the HTTP runner defaults its bind host to loopback (127.0.0.1).
"""

import asyncio

from fastmcp import Client

from harpyja.server.app import build_app, run_http


def _run(coro):
    return asyncio.run(coro)


def test_build_app_registers_harpyja_locate():
    app = build_app()

    async def go():
        async with Client(app) as client:
            tools = await client.list_tools()
            return [t.name for t in tools]

    assert "harpyja_locate" in _run(go())


def test_build_app_locate_tool_call_returns_stub():
    app = build_app()

    async def go():
        async with Client(app) as client:
            return await client.call_tool(
                "harpyja_locate", {"query": "q", "repo_path": "/repo"}
            )

    result = _run(go())
    data = result.data
    assert data["citations"] == []
    assert data["confidence"] == "low"
    assert data["tiers_run"] == []
    assert data["notes"] == "wave-0 stub: no retrieval"


def test_run_http_defaults_to_loopback_host():
    captured = {}

    class _FakeApp:
        def run(self, **kwargs):
            captured.update(kwargs)

    run_http(_FakeApp(), port=9000)
    assert captured.get("host") == "127.0.0.1"
    assert captured.get("port") == 9000
    assert captured.get("transport") == "http"


def test_run_http_allows_explicit_host_opt_out():
    captured = {}

    class _FakeApp:
        def run(self, **kwargs):
            captured.update(kwargs)

    run_http(_FakeApp(), host="0.0.0.0", port=9000)
    assert captured.get("host") == "0.0.0.0"
