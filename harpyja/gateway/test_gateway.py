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
