"""RED (task 8): the air-gap guarantee lives in ModelGateway.assert_local.

AC8 — 127.0.0.0/8 and ::1 pass; everything else raises unless allow_remote; the
check makes no network call. Hostname resolution is injected (never live DNS).
"""

import socket

import pytest

from harpyja.gateway.gateway import AirGapError, ModelGateway, assert_local


@pytest.mark.parametrize("ip", ["127.0.0.1", "127.0.0.5", "127.255.255.254"])
def test_assert_local_accepts_ipv4_loopback_range(ip):
    assert_local(f"http://{ip}:8000/v1")  # must not raise


@pytest.mark.parametrize("endpoint", ["::1", "http://[::1]:8080"])
def test_assert_local_accepts_ipv6_loopback(endpoint):
    assert_local(endpoint)  # must not raise


def test_assert_local_accepts_localhost_hostname():
    # 'localhost' is canonically loopback; no resolver call needed.
    assert_local("http://localhost:11434/v1", resolver=_forbidden_resolver)


def test_assert_local_rejects_unspecified_zero():
    with pytest.raises(AirGapError):
        assert_local("http://0.0.0.0:8000")


@pytest.mark.parametrize("ip", ["10.0.0.5", "8.8.8.8"])
def test_assert_local_rejects_routable_ip(ip):
    with pytest.raises(AirGapError):
        assert_local(f"http://{ip}:8000/v1")


def test_assert_local_rejects_non_loopback_host():
    resolver = lambda host: ["93.184.216.34"]  # noqa: E731 - test stub
    with pytest.raises(AirGapError):
        assert_local("http://example.com:8000", resolver=resolver)


def test_assert_local_accepts_host_resolving_only_to_loopback():
    resolver = lambda host: ["127.0.0.1"]  # noqa: E731 - test stub
    assert_local("http://my-local-box:8000", resolver=resolver)  # must not raise


def test_assert_local_allow_remote_opt_out_bypasses_check():
    assert_local("http://8.8.8.8:8000", allow_remote=True)  # must not raise


def test_assert_local_makes_no_network_call(monkeypatch):
    called = {"n": 0}

    def _boom(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("network call attempted during assert_local")

    monkeypatch.setattr(socket, "getaddrinfo", _boom)
    assert_local("http://127.0.0.1:8000/v1")  # loopback IP: no resolution
    assert called["n"] == 0


def test_modelgateway_assert_local_delegates():
    gw = ModelGateway(api_base="http://127.0.0.1:11434/v1")
    gw.assert_local()  # must not raise for a loopback endpoint


def test_modelgateway_assert_local_raises_for_remote():
    gw = ModelGateway(api_base="http://8.8.8.8:11434/v1")
    with pytest.raises(AirGapError):
        gw.assert_local()


def _forbidden_resolver(host):
    raise AssertionError(f"resolver should not be called for {host!r}")


# --- Wave 3: Gateway request path (AC4) ---


def test_gateway_complete_calls_injected_transport_for_loopback():
    calls = []

    def transport(url, payload):
        calls.append((url, payload))
        return {"choices": [{"message": {"content": "hello"}}]}

    gw = ModelGateway(api_base="http://127.0.0.1:11434/v1")
    out = gw.complete([{"role": "user", "content": "hi"}], transport=transport)
    assert out == "hello"
    assert len(calls) == 1
    url, payload = calls[0]
    assert url.startswith("http://127.0.0.1:11434/v1")
    assert payload["model"] == "local"


def test_gateway_complete_asserts_local_before_send():
    def transport(url, payload):  # pragma: no cover - must never run
        raise AssertionError("transport called for a non-loopback endpoint")

    gw = ModelGateway(api_base="http://8.8.8.8:11434/v1")
    with pytest.raises(AirGapError):
        gw.complete([{"role": "user", "content": "hi"}], transport=transport)


def test_gateway_complete_rejects_resolved_non_loopback():
    def transport(url, payload):  # pragma: no cover - must never run
        raise AssertionError("transport called before air-gap rejection")

    resolver = lambda host: ["93.184.216.34"]  # noqa: E731 - test stub
    gw = ModelGateway(api_base="http://example.com:11434/v1")
    with pytest.raises(AirGapError):
        gw.complete(
            [{"role": "user", "content": "hi"}],
            transport=transport,
            resolver=resolver,
        )


# --- Spec 0024 (v2 explorer loop): tool-calling completion (T9/T10, AC7) ---

_TOOLS = [{"type": "function", "function": {"name": "grep", "parameters": {}}}]


def test_complete_with_tools_returns_content_and_tool_calls():
    tool_calls = [
        {
            "id": "c1",
            "type": "function",
            "function": {"name": "grep", "arguments": '{"pattern": "x"}'},
        }
    ]

    def transport(url, payload):
        return {"choices": [{"message": {"content": "", "tool_calls": tool_calls}}]}

    gw = ModelGateway(api_base="http://127.0.0.1:11434/v1")
    out = gw.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS, transport=transport)
    assert out["tool_calls"] == tool_calls
    assert out["content"] == ""


def test_complete_with_tools_surfaces_finish_reason():
    # spec 0028 AC0: finish_reason lives on the CHOICE object, not the message.
    def transport(url, payload):
        return {"choices": [{"finish_reason": "tool_calls", "message": {"content": ""}}]}

    gw = ModelGateway(api_base="http://127.0.0.1:11434/v1")
    out = gw.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS, transport=transport)
    assert out["finish_reason"] == "tool_calls"


def test_complete_with_tools_finish_reason_defaults_unknown_when_absent():
    # spec 0028 AC0: an absent finish_reason defaults to the exact sentinel "unknown".
    def transport(url, payload):
        return {"choices": [{"message": {"content": "done"}}]}

    gw = ModelGateway(api_base="http://127.0.0.1:11434/v1")
    out = gw.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS, transport=transport)
    assert out["finish_reason"] == "unknown"


def test_complete_with_tools_finish_reason_is_additive_backward_compatible():
    # spec 0028 AC0: the new key is additive — the two existing keys are unchanged,
    # and a legacy response (no finish_reason) still yields the "unknown" sentinel.
    tool_calls = [{"id": "c1", "type": "function", "function": {"name": "grep"}}]

    def transport(url, payload):
        return {"choices": [{"message": {"content": "hi", "tool_calls": tool_calls}}]}

    gw = ModelGateway(api_base="http://127.0.0.1:11434/v1")
    out = gw.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS, transport=transport)
    assert out["content"] == "hi"
    assert out["tool_calls"] == tool_calls
    assert out["finish_reason"] == "unknown"


def test_complete_with_tools_handles_message_without_tool_calls():
    def transport(url, payload):
        return {"choices": [{"message": {"content": "done"}}]}

    gw = ModelGateway(api_base="http://127.0.0.1:11434/v1")
    out = gw.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS, transport=transport)
    assert out["content"] == "done"
    assert out["tool_calls"] == []


def test_complete_with_tools_posts_tools_in_payload():
    calls = []

    def transport(url, payload):
        calls.append(payload)
        return {"choices": [{"message": {"content": "ok"}}]}

    gw = ModelGateway(api_base="http://127.0.0.1:11434/v1")
    gw.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS, transport=transport)
    assert calls[0]["tools"] == _TOOLS


def test_complete_with_tools_asserts_local_before_transport():
    def transport(url, payload):  # pragma: no cover - must never run
        raise AssertionError("transport called for a non-loopback endpoint")

    gw = ModelGateway(api_base="http://8.8.8.8:11434/v1")
    with pytest.raises(AirGapError):
        gw.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS, transport=transport)


# --- Spec 0017 (B3): gateway HTTP timeout (AC2, AC3, AC7) ---

import json  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402

from harpyja.gateway import gateway as _gateway_mod  # noqa: E402


class _FakeResp:
    """Minimal context-manager stand-in for a urlopen response."""

    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


def test_modelgateway_timeout_s_dataclass_default_is_finite():
    # AC2: a bare ModelGateway (no timeout arg, no Settings) is still hang-bounded —
    # the dataclass field default is a finite positive float, never None.
    gw = ModelGateway(api_base="http://127.0.0.1:11434/v1")
    assert gw.timeout_s is not None
    assert isinstance(gw.timeout_s, float)
    assert gw.timeout_s > 0
    import math

    assert math.isfinite(gw.timeout_s)


def test_default_transport_passes_timeout_to_urlopen(monkeypatch):
    # AC3 (load-bearing): the configured timeout is really threaded to the blocking
    # socket op, not dropped. Monkeypatch urlopen to capture the kwarg.
    captured = {}

    def _fake_urlopen(req, timeout=None):
        captured["timeout"] = timeout
        body = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
        return _FakeResp(body)

    monkeypatch.setattr(_gateway_mod, "urlopen", _fake_urlopen)
    gw = ModelGateway(api_base="http://127.0.0.1:11434/v1", timeout_s=3.5)
    out = gw.complete([{"role": "user", "content": "hi"}])  # default transport
    assert out == "ok"
    assert captured["timeout"] is not None
    assert captured["timeout"] > 0
    assert captured["timeout"] == 3.5


def test_gateway_complete_raises_on_silent_server_within_bound():
    # AC7 (load-bearing): a real loopback endpoint that accepts then withholds all
    # bytes must make complete() RAISE within a small bound, not hang forever.
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    accepted = []

    def _accept_and_stall():
        try:
            conn, _ = listener.accept()
            accepted.append(conn)  # hold it open, send nothing
        except OSError:
            pass

    t = threading.Thread(target=_accept_and_stall, daemon=True)
    t.start()
    try:
        gw = ModelGateway(api_base=f"http://127.0.0.1:{port}/v1", timeout_s=0.25)
        start = time.monotonic()
        with pytest.raises((TimeoutError, socket.timeout, OSError)):
            gw.complete([{"role": "user", "content": "hi"}])
        elapsed = time.monotonic() - start
        assert elapsed < 1.0  # bounded — a regression that drops timeout would hang
    finally:
        listener.close()
        for conn in accepted:
            conn.close()


# --- Spec 0017 (B3): preservation locks (AC4, AC8, AC9) ---


def test_gateway_complete_uses_injected_transport_unchanged():
    # AC8 / D3: an explicit two-arg Transport (no **kwargs) is used VERBATIM — the
    # timeout partial binds only when transport is None. Fails if the partial were
    # bound unconditionally (a strict two-arg fake would then get an unexpected
    # timeout_s kwarg and raise TypeError).
    seen = []

    def transport(url, payload):  # strictly two positional args
        seen.append((url, payload))
        return {"choices": [{"message": {"content": "verbatim"}}]}

    gw = ModelGateway(api_base="http://127.0.0.1:11434/v1", timeout_s=3.0)
    out = gw.complete([{"role": "user", "content": "hi"}], transport=transport)
    assert out == "verbatim"
    assert len(seen) == 1  # called with exactly (url, payload), no timeout leaked


def test_gateway_complete_propagates_transport_timeout():
    # AC4: a raised timeout PROPAGATES out of complete() — the gateway neither
    # catches nor converts it, so a caller's degrade handler can see it. Distinct
    # from AC3 (supplied); this proves "not swallowed". The fake makes the test
    # itself non-hanging.
    def transport(url, payload):
        raise TimeoutError("simulated read timeout")

    gw = ModelGateway(api_base="http://127.0.0.1:11434/v1")
    with pytest.raises(TimeoutError):
        gw.complete([{"role": "user", "content": "hi"}], transport=transport)


def test_gateway_complete_default_transport_never_called_for_remote(monkeypatch):
    # AC9: the assert-local floor runs BEFORE egress even on the default-transport
    # path — a non-loopback api_base raises AirGapError and the timeout-bearing
    # urlopen is never invoked.
    def _boom(*args, **kwargs):
        raise AssertionError("urlopen called for a non-loopback endpoint")

    monkeypatch.setattr(_gateway_mod, "urlopen", _boom)
    gw = ModelGateway(api_base="http://8.8.8.8:11434/v1")  # no injected transport
    with pytest.raises(AirGapError):
        gw.complete([{"role": "user", "content": "hi"}])


# --- Spec 0017 (B3): optional live happy-path smoke (AC11) ---


@pytest.mark.integration
def test_gateway_complete_live_ollama_under_timeout():
    """AC11: against a reachable local Ollama, a real complete() returns well under
    the configured timeout and never hangs. Skip-not-fail — this documents the happy
    path only; it is NOT the stall proof (AC7 is) and must not be read as validating
    the fix against a real stall."""
    from urllib.parse import urlsplit

    from harpyja.config.settings import Settings

    settings = Settings()
    parts = urlsplit(settings.lm_api_base)
    host, port = parts.hostname or "127.0.0.1", parts.port or 11434
    if not _socket_reachable(host, port, timeout=1.0):
        pytest.skip(f"no local model endpoint reachable at {host}:{port}")

    gw = ModelGateway(
        api_base=settings.lm_api_base,
        model=settings.scout_model,
        timeout_s=settings.lm_http_timeout_s,
    )
    start = time.monotonic()
    try:
        out = gw.complete([{"role": "user", "content": "Reply with the word ok."}])
    except Exception as err:  # a missing model / HTTP error is not a timeout regression
        pytest.skip(f"endpoint reachable but complete() errored (not a stall): {err!r}")
    elapsed = time.monotonic() - start
    assert isinstance(out, str)
    assert elapsed < settings.lm_http_timeout_s  # returned inside the bound, no hang


def _socket_reachable(host, port, timeout=1.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
