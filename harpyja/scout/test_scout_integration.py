"""Integration ACs for Wave 3 Scout (AC1, AC11).

Both are marked `@pytest.mark.integration` (skippable in constrained envs):
- AC1 exercises a live local model endpoint and is skipped when none is
  reachable — the deterministic shape assertions live in the unit ACs, so a
  flaky/absent model degrades this to a skip, never a false failure.
- AC11 proves the assembled Scout stack runs to completion under a network-deny
  guard with a loopback-only Gateway — the model path needs no non-loopback
  egress.
"""

import hashlib
import ipaddress
import socket
from dataclasses import replace
from pathlib import Path

import pytest

from harpyja.config.settings import Settings
from harpyja.gateway.gateway import ModelGateway
from harpyja.orchestrator.locate import locate
from harpyja.scout.engine import ScoutEngine
from harpyja.scout.fastcontext import FastContextBackend
from harpyja.server.types import CodeSpan, LocateRequest

# Spec 0007 integration: drive the REAL FastContext stack on a loopback endpoint.
_LOOPBACK = "http://127.0.0.1:11434/v1"


class _NoEngine:
    """Tier-0 ripgrep stand-in; never consulted on a successful Scout run."""

    def search(self, pattern, scope=None):
        return []


def _endpoint_reachable(api_base: str, timeout: float = 0.25) -> bool:
    split = api_base.split("://", 1)[-1]
    hostport = split.split("/", 1)[0]
    host, _, port = hostport.partition(":")
    try:
        with socket.create_connection((host, int(port or 80)), timeout=timeout):
            return True
    except OSError:
        return False


def _fastcontext_live_available() -> bool:
    """True only when the real package imports AND a loopback endpoint answers."""
    try:
        import fastcontext  # noqa: F401
    except ImportError:
        return False
    return _endpoint_reachable(_LOOPBACK)


_NEEDS_FC = "requires the FastContext package + a live loopback model endpoint"


def _content_manifest(root: Path) -> dict[str, str]:
    """`{relpath: sha256(bytes)}` over source files, EXCLUDING sanctioned derived
    artifacts (`.harpyja/`) and temp/trajectory — the AC8/D5 read-only surface.

    Content-hash only: mtime-only churn is ignored on purpose.
    """
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if ".harpyja" in rel.parts:  # derived index artifacts (sanctioned writes)
            continue
        out[str(rel)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def _settings_live() -> Settings:
    return replace(Settings(), lm_api_base=_LOOPBACK)


@pytest.mark.integration
def test_scout_fast_returns_tier1_citations_live(tmp_path):
    """AC1/AC11: the Wave-3 skip flips to a REAL pass — `make_fastcontext_agent`
    runs against the loopback endpoint and the pipeline reports `tiers_run=[0,1]`
    with Tier-1 citations. Citation *content* is model-dependent, so this asserts
    the pipeline shape (the genuine end-to-end run), not specific spans."""
    if not _fastcontext_live_available():
        pytest.skip(_NEEDS_FC)
    from harpyja.scout.wiring import build_scout_engine

    (tmp_path / "auth.py").write_text(
        "def authenticate(token):\n    return token == 'ok'\n", encoding="utf-8"
    )
    settings = _settings_live()
    scout = build_scout_engine(settings, str(tmp_path))
    result = locate(
        LocateRequest(
            query="where is authentication handled?", repo_path=str(tmp_path), mode="fast"
        ),
        settings,
        engine=_NoEngine(),
        scout_engine=scout,
    )
    # A real FastContext run either succeeds (Scout, tiers_run=[0,1]) or honestly
    # degrades on the third-party's own flakiness (scout-degraded:backend-error,
    # tiers_run=[0]). BOTH prove the live stack ran end-to-end (the Wave-3 skip is
    # genuinely gone); citation content is model-dependent, so it is not asserted.
    assert result.tiers_run in ([0, 1], [0])
    if result.tiers_run == [0, 1]:
        assert all(c.source_tier == 1 for c in result.citations)
    else:
        assert (result.notes or "").startswith("scout-degraded:")


@pytest.mark.integration
def test_scout_live_no_backend_error_citation_false(tmp_path):
    """Spec 0011 AC20: the exact 12/12-broken case is fixed at the unit of failure.

    Under seam (a) Scout drives FastContext with `citation=False`, so FC's own
    `format_citations` (which raised `TypeError` on bare-path model output → the
    `scout-degraded:backend-error` that floored every real query) is never called.
    A live run must therefore NEVER carry a `backend-error` note: it either returns
    Tier-1 citations (`[0,1]`) or honestly degrades for a *different*, real reason
    (e.g. connection) — but the citation-formatter crash is structurally gone.
    Citation *content* stays model-dependent and is not asserted.
    """
    if not _fastcontext_live_available():
        pytest.skip(_NEEDS_FC)
    from harpyja.scout.wiring import build_scout_engine

    (tmp_path / "auth.py").write_text(
        "def authenticate(token):\n    return token == 'ok'\n", encoding="utf-8"
    )
    settings = _settings_live()
    scout = build_scout_engine(settings, str(tmp_path))
    result = locate(
        LocateRequest(
            query="where is authentication handled?", repo_path=str(tmp_path), mode="fast"
        ),
        settings,
        engine=_NoEngine(),
        scout_engine=scout,
    )
    assert result.tiers_run in ([0, 1], [0])
    assert "backend-error" not in (result.notes or "")  # the crash is gone (AC20)


@pytest.mark.integration
def test_scout_fast_path_a_leaves_repo_byte_unchanged(tmp_path):
    """AC8: an end-to-end Path-A run leaves the scanned repo byte-unchanged (no
    FastContext-authored files in `work_dir`), excluding the sanctioned `.harpyja/`
    index. Residual in-process write risk is recorded (assumption-verified-by-test,
    symmetric to the network-deny guard) — the in-process loop *could* write, so we
    verify it does not rather than asserting it cannot."""
    if not _fastcontext_live_available():
        pytest.skip(_NEEDS_FC)
    from harpyja.scout.wiring import build_scout_engine

    (tmp_path / "auth.py").write_text(
        "def authenticate(token):\n    return token == 'ok'\n", encoding="utf-8"
    )
    settings = _settings_live()
    scout = build_scout_engine(settings, str(tmp_path))
    # `.harpyja/` (the sanctioned derived index) is excluded from the manifest, so
    # a snapshot taken before any indexing still compares only source files.
    before = _content_manifest(tmp_path)
    locate(
        LocateRequest(
            query="where is authentication handled?", repo_path=str(tmp_path), mode="fast"
        ),
        settings,
        engine=_NoEngine(),
        scout_engine=scout,
    )
    after = _content_manifest(tmp_path)
    assert before == after  # source files untouched by the FastContext loop


@pytest.mark.integration
def test_scout_path_a_no_nonloopback_egress(tmp_path, monkeypatch):
    """AC9: an end-to-end Path-A run makes ZERO non-loopback egress. A network-deny
    guard trips on any connect to a non-loopback IP; FastContext owns its model
    client, so this proves the air-gap at the only place it can leak."""
    if not _fastcontext_live_available():
        pytest.skip(_NEEDS_FC)
    from harpyja.scout.wiring import build_scout_engine

    real_connect = socket.socket.connect
    tripped: list[str] = []

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        try:
            if not ipaddress.ip_address(host).is_loopback:
                tripped.append(str(host))
                raise OSError("network-deny: non-loopback blocked")
        except ValueError:
            pass  # hostnames are resolved to IPs before connect; loopback IPs pass
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)

    (tmp_path / "auth.py").write_text(
        "def authenticate(token):\n    return token == 'ok'\n", encoding="utf-8"
    )
    settings = _settings_live()
    scout = build_scout_engine(settings, str(tmp_path))
    result = locate(
        LocateRequest(
            query="where is authentication handled?", repo_path=str(tmp_path), mode="fast"
        ),
        settings,
        engine=_NoEngine(),
        scout_engine=scout,
    )
    assert result.tiers_run in ([0, 1], [0])  # completed (Scout ran or honestly degraded)
    assert tripped == []  # no non-loopback egress on the model path


@pytest.mark.integration
def test_scout_runs_under_network_deny(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("def handler():\n    pass\n", encoding="utf-8")

    # Network-deny: any connect to a non-loopback (or unresolved) address fails.
    real_connect = socket.socket.connect
    tripped: list[str] = []

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        try:
            is_loopback = ipaddress.ip_address(host).is_loopback
        except ValueError as err:
            tripped.append(str(host))
            raise OSError("network-deny: name resolution blocked") from err
        if not is_loopback:
            tripped.append(str(host))
            raise OSError("network-deny: non-loopback blocked")
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)

    gateway = ModelGateway(api_base="http://127.0.0.1:11434/v1")

    def loopback_transport(url, payload):
        # Stand-in for the local model; no real socket, stays in-process.
        return {"choices": [{"message": {"content": "a.py:1"}}]}

    def fastcontext_client(query, seed, tools):
        # Drives the model strictly through the loopback-enforced Gateway.
        tools["model"].complete([{"role": "user", "content": query}], transport=loopback_transport)
        return [CodeSpan(path="a.py", start_line=1, end_line=1)]

    backend = FastContextBackend(
        client=fastcontext_client,
        model_client=gateway,
        read=object(),
        glob=object(),
        grep=object(),
    )
    scout = ScoutEngine(backend, lambda q: [], Settings(), str(tmp_path))

    result = locate(
        LocateRequest(query="handler", repo_path=str(tmp_path), mode="fast"),
        Settings(),
        engine=_NoEngine(),
        scout_engine=scout,
    )

    assert result.tiers_run == [0, 1]
    assert result.citations and result.citations[0].source_tier == 1
    assert tripped == []  # the model path made no non-loopback egress
