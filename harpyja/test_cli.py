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
    cli.main(["serve", "--http", "--host", "0.0.0.0", "--port", "9000", "--allow-remote-bind"])
    assert captured["http"] == [("0.0.0.0", 9000)]


# --- Wave 1: index / locate / read subcommands (task 47) ---


class _FakeIndexResult:
    def to_dict(self):
        return {
            "files_indexed": 1,
            "symbols_indexed": 0,
            "languages": {},
            "elapsed_ms": 0,
            "degraded": [],
        }


def test_cli_index_invokes_indexer_with_repo(monkeypatch, tmp_path):
    seen = {}

    def fake_index(repo, settings, *, rehash=False, **kw):
        seen["repo"], seen["rehash"] = str(repo), rehash
        return _FakeIndexResult()

    monkeypatch.setattr(cli, "index_repo", fake_index)
    rc = cli.main(["index", "--repo", str(tmp_path)])
    assert rc == 0
    assert seen["repo"] == str(tmp_path)
    assert seen["rehash"] is False


def test_cli_index_rehash_flag_passed(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(
        cli,
        "index_repo",
        lambda repo, settings, *, rehash=False, **kw: (
            seen.update(rehash=rehash) or _FakeIndexResult()
        ),
    )
    cli.main(["index", "--repo", str(tmp_path), "--rehash"])
    assert seen["rehash"] is True


def test_cli_index_prints_summary(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "index_repo", lambda *a, **k: _FakeIndexResult())
    cli.main(["index", "--repo", str(tmp_path)])
    assert "files_indexed" in capsys.readouterr().out


def test_cli_locate_passes_query_mode_maxresults_langhint(monkeypatch, tmp_path):
    seen = {}

    def fake_locate(req, settings, *, engine, **kw):
        seen["req"] = req
        from harpyja.server.types import LocateResult

        return LocateResult(citations=[], confidence="low", tiers_run=[0], notes="")

    monkeypatch.setattr(cli, "locate", fake_locate)
    cli.main(
        [
            "locate",
            "--repo",
            str(tmp_path),
            "--query",
            "find me",
            "--mode",
            "deep",
            "--max-results",
            "3",
            "--language-hint",
            "go",
        ]
    )
    req = seen["req"]
    assert req.query == "find me"
    assert req.mode == "deep"
    assert req.max_results == 3
    assert req.language_hint == "go"
    assert req.repo_path == str(tmp_path)


def test_cli_read_passes_path_start_end(monkeypatch, tmp_path):
    seen = {}

    def fake_read(repo, path, start, end, settings):
        seen.update(repo=str(repo), path=path, start=start, end=end)
        return {
            "path": path,
            "start": start,
            "end": end,
            "language": None,
            "content": "",
            "truncated": False,
        }

    monkeypatch.setattr(cli, "read_snippet", fake_read)
    cli.main(["read", "--repo", str(tmp_path), "--path", "a.py", "--start", "2", "--end", "5"])
    assert (seen["path"], seen["start"], seen["end"]) == ("a.py", 2, 5)


def test_cli_locate_rg_missing_prints_actionable_error(monkeypatch, tmp_path, capsys):
    from harpyja.symbols.ripgrep import RipgrepMissingError

    def boom(*a, **k):
        raise RipgrepMissingError("ripgrep (rg) is required for search but was not found")

    monkeypatch.setattr(cli, "locate", boom)
    rc = cli.main(["locate", "--repo", str(tmp_path), "--query", "q"])
    assert rc != 0  # non-zero exit, not a crash
    err = capsys.readouterr().err
    assert "ripgrep" in err.lower()
