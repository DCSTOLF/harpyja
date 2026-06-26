"""RED (task 16): CLI `serve` wiring.

AC3/AC4 — `serve --stdio` drives the stdio transport; `serve --http` drives the
HTTP transport bound to loopback by default; a non-loopback bind needs an
explicit opt-out. Transport runners are monkeypatched so no server starts.
"""

import pytest

import harpyja.cli as cli


@pytest.fixture
def captured(monkeypatch):
    calls = {"stdio": 0, "http": []}

    def fake_stdio(app):
        calls["stdio"] += 1

    def fake_http(app, host, port):
        calls["http"].append((host, port))

    monkeypatch.setattr(cli, "run_stdio", fake_stdio)
    monkeypatch.setattr(cli, "run_http", fake_http)
    monkeypatch.setattr(cli, "build_app", lambda: object())
    return calls


def test_cli_serve_stdio_invokes_stdio_transport(captured):
    rc = cli.main(["serve", "--stdio"])
    assert rc == 0
    assert captured["stdio"] == 1
    assert captured["http"] == []


def test_cli_serve_defaults_to_stdio(captured):
    cli.main(["serve"])
    assert captured["stdio"] == 1


def test_cli_serve_http_binds_loopback_by_default(captured):
    cli.main(["serve", "--http", "--port", "9000"])
    assert captured["http"] == [("127.0.0.1", 9000)]


def test_cli_serve_http_port_passed_through(captured):
    cli.main(["serve", "--http", "--port", "12345"])
    assert captured["http"] == [("127.0.0.1", 12345)]


def test_cli_serve_http_non_loopback_requires_opt_out(captured):
    with pytest.raises(SystemExit):
        cli.main(["serve", "--http", "--host", "0.0.0.0", "--port", "9000"])
    assert captured["http"] == []  # never started


def test_cli_serve_http_non_loopback_with_opt_out_allowed(captured):
    cli.main(
        ["serve", "--http", "--host", "0.0.0.0", "--port", "9000", "--allow-remote-bind"]
    )
    assert captured["http"] == [("0.0.0.0", 9000)]
