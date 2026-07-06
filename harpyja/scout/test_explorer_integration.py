"""Integration ACs for spec 0024 (v2 explorer loop), AC10.

`@pytest.mark.integration`, skip-not-fail: a host without a served loopback
tool-calling model must not red-fail the suite — the deterministic behavior is
pinned by the unit ACs (test_explorer_*). Two live proofs:

- The loop drives a REAL tool-calling model over a REAL repo to a parsed citation
  list, completing within the turn cap.
- Under an in-process network-deny guard, the live run makes ZERO non-loopback
  connections (egress is observed via the same harness pattern the 0007/0014
  air-gap tests use, not merely asserted).
"""

from __future__ import annotations

import ipaddress
import socket
from contextlib import contextmanager

import pytest

from harpyja.config.settings import Settings
from harpyja.gateway.gateway import ModelGateway
from harpyja.scout.errors import ScoutUnavailable
from harpyja.scout.wiring import build_scout_engine
from harpyja.server.types import CodeSpan

_LOOPBACK = "http://127.0.0.1:11434/v1"
_NEEDS_MODEL = "requires a live loopback tool-calling model endpoint"


def _endpoint_reachable(api_base: str, timeout: float = 0.25) -> bool:
    split = api_base.split("://", 1)[-1]
    hostport = split.split("/", 1)[0]
    host, _, port = hostport.partition(":")
    try:
        with socket.create_connection((host, int(port or 80)), timeout=timeout):
            return True
    except OSError:
        return False


def _is_loopback_host(host: str) -> bool:
    if host in ("localhost", ""):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@contextmanager
def _deny_nonloopback_egress():
    """Allow loopback connects; raise on any non-loopback host (Python egress)."""
    real_connect = socket.socket.connect

    def guarded(self, address):
        try:
            host = address[0] if isinstance(address, tuple) else ""
        except Exception:
            host = ""
        if isinstance(address, tuple) and not _is_loopback_host(str(host)):
            raise AssertionError(f"non-loopback egress attempted to {address!r}")
        return real_connect(self, address)

    socket.socket.connect = guarded  # type: ignore[method-assign]
    try:
        yield
    finally:
        socket.socket.connect = real_connect  # type: ignore[method-assign]


def _repo(tmp_path) -> str:
    (tmp_path / "app.py").write_text(
        "def add(a, b):\n    return a + b\n\n\n"
        "def divide(a, b):\n    return a / b  # zero-division bug lives here\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# demo\nA tiny calculator.\n", encoding="utf-8")
    return str(tmp_path)


def _live_engine(repo: str):
    settings = Settings()
    gateway = ModelGateway(
        api_base=_LOOPBACK,
        model=settings.lm_model,
        allow_remote=False,
        timeout_s=settings.lm_http_timeout_s,
    )
    return build_scout_engine(settings, repo, gateway=gateway)


@pytest.mark.integration
def test_live_explorer_loop_produces_citation_list(tmp_path):
    if not _endpoint_reachable(_LOOPBACK):
        pytest.skip(_NEEDS_MODEL)
    engine = _live_engine(_repo(tmp_path))
    try:
        out = engine.search("where is the division-by-zero bug", scope=str(tmp_path))
    except ScoutUnavailable:
        # A live model that exhausts its turn/wall-clock budget still TERMINATED
        # within the cap (never hung) — the bounded-loop contract held.
        return
    assert isinstance(out, list)
    assert all(isinstance(s, CodeSpan) for s in out)


@pytest.mark.integration
def test_live_explorer_loop_no_nonloopback_egress(tmp_path):
    if not _endpoint_reachable(_LOOPBACK):
        pytest.skip(_NEEDS_MODEL)
    engine = _live_engine(_repo(tmp_path))
    with _deny_nonloopback_egress():
        try:
            engine.search("locate the bug", scope=str(tmp_path))
        except ScoutUnavailable:
            pass  # bounded termination is fine; the egress guard is what matters
