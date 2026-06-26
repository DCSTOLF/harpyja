"""RED (task 12): FastMCP app construction, tool registration, loopback default.

AC3/AC4 — build_app registers harpyja_locate and a call returns the schema-valid
stub; the HTTP runner defaults its bind host to loopback (127.0.0.1).
"""

import asyncio

import pytest
from fastmcp import Client

from harpyja.server.app import build_app, run_http
from harpyja.server.types import CodeSpan


def _run(coro):
    return asyncio.run(coro)


class _FakeEngine:
    def __init__(self, spans):
        self._spans = spans

    def search(self, pattern, scope=None):
        return list(self._spans)


def _write(root, rel, content="needle\n"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def test_build_app_registers_harpyja_locate():
    app = build_app()

    async def go():
        async with Client(app) as client:
            tools = await client.list_tools()
            return [t.name for t in tools]

    assert "harpyja_locate" in _run(go())


def test_build_app_registers_harpyja_index_and_read():
    app = build_app()

    async def go():
        async with Client(app) as client:
            return {t.name for t in await client.list_tools()}

    names = _run(go())
    assert {"harpyja_index", "harpyja_read", "harpyja_locate"} <= names


def test_build_app_index_tool_returns_summary_shape(tmp_path):
    _write(tmp_path, "a.py")
    app = build_app()

    async def go():
        async with Client(app) as client:
            return await client.call_tool("harpyja_index", {"repo_path": str(tmp_path)})

    data = _run(go()).data
    assert set(data.keys()) == {
        "files_indexed",
        "symbols_indexed",
        "languages",
        "elapsed_ms",
        "degraded",
    }
    assert data["symbols_indexed"] == 0


def test_build_app_read_tool_returns_snippet_shape(tmp_path):
    _write(tmp_path, "a.py", "l1\nl2\nl3\n")
    app = build_app()

    async def go():
        async with Client(app) as client:
            return await client.call_tool(
                "harpyja_read",
                {"repo_path": str(tmp_path), "path": "a.py", "start": 1, "end": 2},
            )

    data = _run(go()).data
    assert set(data.keys()) == {"path", "start", "end", "language", "content", "truncated"}


def test_build_app_locate_tool_runs_tier0(tmp_path):
    _write(tmp_path, "a.py", "needle\n")
    app = build_app(engine_factory=lambda s: _FakeEngine([CodeSpan("a.py", 1, 1)]))

    async def go():
        async with Client(app) as client:
            return await client.call_tool(
                "harpyja_locate", {"query": "needle", "repo_path": str(tmp_path)}
            )

    data = _run(go()).data
    assert data["tiers_run"] == [0]
    assert data["citations"][0]["path"] == "a.py"


def test_build_app_locate_reports_rg_missing_actionably(tmp_path):
    _write(tmp_path, "a.py")
    app = build_app(which=lambda _name: None)  # rg absent

    async def go_locate():
        async with Client(app) as client:
            return await client.call_tool(
                "harpyja_locate", {"query": "q", "repo_path": str(tmp_path)}
            )

    with pytest.raises(Exception):  # noqa: B017 - FastMCP wraps tool errors
        _run(go_locate())

    # index does NOT need rg — it still succeeds.
    async def go_index():
        async with Client(app) as client:
            return await client.call_tool("harpyja_index", {"repo_path": str(tmp_path)})

    assert _run(go_index()).data["files_indexed"] >= 1


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


# --- Wave 2: real symbol surfacing + symbol-aware locate (AC3, AC9, AC10, AC14, AC16) ---


def test_build_app_index_surfaces_real_symbols_indexed(tmp_path):
    _write(tmp_path, "a.py", "def foo():\n    pass\n")
    app = build_app()

    async def go():
        async with Client(app) as client:
            return await client.call_tool("harpyja_index", {"repo_path": str(tmp_path)})

    assert _run(go()).data["symbols_indexed"] == 1


def test_build_app_index_surfaces_degraded_array(tmp_path):
    _write(tmp_path, "broken.py", "def bad(:\n    pass\n")
    app = build_app()

    async def go():
        async with Client(app) as client:
            return await client.call_tool("harpyja_index", {"repo_path": str(tmp_path)})

    assert any("parse-error" in d for d in _run(go()).data["degraded"])


def test_build_app_locate_promotes_definition_above_call_site(tmp_path):
    _write(tmp_path, "a.py", "def foo():\n    pass\nfoo()\n")
    app = build_app(engine_factory=lambda s: _FakeEngine([CodeSpan("a.py", 3, 3)]))

    async def go():
        async with Client(app) as client:
            return await client.call_tool(
                "harpyja_locate", {"query": "foo", "repo_path": str(tmp_path)}
            )

    top = _run(go()).data["citations"][0]
    assert top["symbol"] == "foo"
    assert top["kind"] == "function"


def test_build_app_locate_note_reflects_wave2_symbol_tier(tmp_path):
    _write(tmp_path, "a.py", "x = 1\n")
    app = build_app(engine_factory=lambda s: _FakeEngine([]))

    async def go():
        async with Client(app) as client:
            return await client.call_tool(
                "harpyja_locate", {"query": "x", "repo_path": str(tmp_path)}
            )

    assert _run(go()).data["notes"].startswith("Wave 2:")
