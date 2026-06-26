"""Harpyja CLI entrypoints.

Wave 0 ships two subcommands:
- ``serve`` — run the MCP server over stdio (default) or streamable HTTP. HTTP
  binds loopback (127.0.0.1) by default; a non-loopback bind requires the
  explicit ``--allow-remote-bind`` opt-out (inbound air-gap, AC3/AC4).
- ``doctor`` — environment preflight (AC10).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from harpyja.config.settings import load_settings
from harpyja.gateway.gateway import AirGapError, assert_local
from harpyja.index.indexer import index_repo
from harpyja.orchestrator.locate import locate
from harpyja.server.app import (
    DEFAULT_HTTP_HOST,
    DEFAULT_HTTP_PORT,
    build_app,
    run_http,
    run_stdio,
)
from harpyja.server.tools import read_snippet
from harpyja.server.types import LocateRequest
from harpyja.symbols.ripgrep import RipgrepEngine, RipgrepMissingError


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harpyja")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="run the MCP server")
    transport = serve.add_mutually_exclusive_group()
    transport.add_argument("--stdio", action="store_true", help="serve over stdio (default)")
    transport.add_argument("--http", action="store_true", help="serve over streamable HTTP")
    serve.add_argument("--host", default=DEFAULT_HTTP_HOST, help="HTTP bind host")
    serve.add_argument("--port", type=int, default=DEFAULT_HTTP_PORT, help="HTTP bind port")
    serve.add_argument(
        "--allow-remote-bind",
        action="store_true",
        help="permit a non-loopback HTTP bind host (opt-out of the inbound air-gap)",
    )
    serve.add_argument("--config", default=None, help="path to harpyja.toml")

    doctor = sub.add_parser("doctor", help="environment preflight")
    doctor.add_argument("--config", default=None, help="path to harpyja.toml")

    index = sub.add_parser("index", help="build/refresh the repo manifest")
    index.add_argument("--repo", default=".", help="repo path to index")
    index.add_argument(
        "--rehash", action="store_true", help="re-hash every file (ignore the mtime/size gate)"
    )
    index.add_argument("--config", default=None, help="path to harpyja.toml")

    loc = sub.add_parser("locate", help="find file:line citations for a query")
    loc.add_argument("--query", required=True, help="natural-language query")
    loc.add_argument("--repo", default=".", help="repo path to search")
    loc.add_argument("--mode", default="auto", help="auto | fast | deep")
    loc.add_argument("--max-results", type=int, default=8, dest="max_results")
    loc.add_argument("--language-hint", default=None, dest="language_hint")
    loc.add_argument("--config", default=None, help="path to harpyja.toml")

    read = sub.add_parser("read", help="read a bounded code snippet")
    read.add_argument("--repo", default=".", help="repo path (confinement root)")
    read.add_argument("--path", required=True, help="repo-relative file path")
    read.add_argument("--start", type=int, required=True, help="1-indexed start line")
    read.add_argument("--end", type=int, required=True, help="inclusive end line")
    read.add_argument("--config", default=None, help="path to harpyja.toml")

    return parser


def _cmd_serve(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    app = build_app()
    if args.http:
        if not args.allow_remote_bind:
            try:
                assert_local(args.host)
            except AirGapError:
                parser.error(
                    f"refusing to bind HTTP to non-loopback host {args.host!r}; "
                    f"pass --allow-remote-bind to override"
                )
        run_http(app, host=args.host, port=args.port)
    else:
        run_stdio(app)
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    # Imported lazily so `serve` has no doctor dependency.
    from harpyja.config.doctor import format_report, run_doctor
    from harpyja.config.settings import load_settings

    settings = load_settings(config_path=args.config)
    report = run_doctor(settings)
    print(format_report(report))
    return 0


def _cmd_index(args: argparse.Namespace) -> int:
    settings = load_settings(config_path=args.config)
    result = index_repo(args.repo, settings, rehash=args.rehash)
    print(json.dumps(result.to_dict()))
    return 0


def _cmd_locate(args: argparse.Namespace) -> int:
    settings = load_settings(config_path=args.config)
    engine = RipgrepEngine(settings)
    req = LocateRequest(
        query=args.query,
        repo_path=args.repo,
        mode=args.mode,
        max_results=args.max_results,
        language_hint=args.language_hint,
    )
    try:
        result = locate(req, settings, engine=engine)
    except RipgrepMissingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(asdict(result)))
    return 0


def _cmd_read(args: argparse.Namespace) -> int:
    settings = load_settings(config_path=args.config)
    out = read_snippet(args.repo, args.path, args.start, args.end, settings)
    print(json.dumps(out))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "serve":
        return _cmd_serve(args, parser)
    if args.command == "doctor":
        return _cmd_doctor(args)
    if args.command == "index":
        return _cmd_index(args)
    if args.command == "locate":
        return _cmd_locate(args)
    if args.command == "read":
        return _cmd_read(args)
    parser.error(f"unknown command: {args.command}")  # pragma: no cover
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
