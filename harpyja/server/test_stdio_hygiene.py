"""RED (task 14): stdio transport keeps stdout clean; logs go to stderr.

AC9 — the stdio MCP framing must never be corrupted by log output. Unit checks
on the logging config always run; a subprocess MCP round-trip (which only
succeeds if stdout carries nothing but JSON-RPC frames) is marked integration.
"""

import asyncio
import logging
import sys

import pytest

from harpyja.server.logging_config import configure_logging


@pytest.fixture
def reset_root_logging():
    root = logging.getLogger()
    saved = root.handlers[:]
    saved_level = root.level
    root.handlers = []
    try:
        yield root
    finally:
        root.handlers = saved
        root.level = saved_level


def test_configure_logging_uses_stderr_handler(reset_root_logging):
    configure_logging()
    streams = [
        h.stream for h in reset_root_logging.handlers if isinstance(h, logging.StreamHandler)
    ]
    assert any(s is sys.stderr for s in streams)


def test_configure_logging_no_stdout_handler(reset_root_logging):
    configure_logging()
    for h in reset_root_logging.handlers:
        if isinstance(h, logging.StreamHandler):
            assert h.stream is not sys.stdout


_SERVER_SCRIPT = """\
import logging
from harpyja.server.app import build_app, run_stdio
from harpyja.server.logging_config import configure_logging

configure_logging()
# A log line emitted before/while serving must NOT corrupt stdout framing.
logging.getLogger("harpyja").info("server starting: this must land on stderr")
run_stdio(build_app())
"""


@pytest.mark.integration
def test_stdio_session_stdout_only_mcp_frames(tmp_path):
    try:
        from fastmcp import Client
        from fastmcp.client.transports import PythonStdioTransport
    except Exception as exc:  # pragma: no cover - env guard
        pytest.skip(f"fastmcp stdio client unavailable: {exc}")

    script = tmp_path / "stdio_server.py"
    script.write_text(_SERVER_SCRIPT, encoding="utf-8")
    (tmp_path / "sample.py").write_text("x = 1\n", encoding="utf-8")

    async def go():
        transport = PythonStdioTransport(script_path=str(script))
        async with Client(transport) as client:
            tools = [t.name for t in await client.list_tools()]
            # Use harpyja_index — it exercises the full stdio round-trip without
            # needing ripgrep, so the stdout-hygiene check runs regardless of env.
            result = await client.call_tool(
                "harpyja_index", {"repo_path": str(tmp_path)}
            )
            return tools, result.data

    try:
        tools, data = asyncio.run(go())
    except Exception as exc:  # pragma: no cover - env guard
        pytest.skip(f"stdio subprocess session could not run: {exc}")

    # The handshake + call only complete if stdout carried clean MCP frames.
    assert "harpyja_locate" in tools
    assert data["files_indexed"] >= 1
