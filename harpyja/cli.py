"""Harpyja CLI entrypoints.

Wave 0 ships two subcommands:
- ``serve`` — run the MCP server over stdio (default) or streamable HTTP. HTTP
  binds loopback (127.0.0.1) by default; a non-loopback bind requires the
  explicit ``--allow-remote-bind`` opt-out (inbound air-gap, AC3/AC4).
- ``doctor`` — environment preflight (AC10).
"""

from __future__ import annotations

import argparse
import sys

from harpyja.gateway.gateway import AirGapError, assert_local
from harpyja.server.app import (
    DEFAULT_HTTP_HOST,
    DEFAULT_HTTP_PORT,
    build_app,
    run_http,
    run_stdio,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harpyja")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="run the MCP server")
    transport = serve.add_mutually_exclusive_group()
    transport.add_argument(
        "--stdio", action="store_true", help="serve over stdio (default)"
    )
    transport.add_argument(
        "--http", action="store_true", help="serve over streamable HTTP"
    )
    serve.add_argument("--host", default=DEFAULT_HTTP_HOST, help="HTTP bind host")
    serve.add_argument(
        "--port", type=int, default=DEFAULT_HTTP_PORT, help="HTTP bind port"
    )
    serve.add_argument(
        "--allow-remote-bind",
        action="store_true",
        help="permit a non-loopback HTTP bind host (opt-out of the inbound air-gap)",
    )
    serve.add_argument("--config", default=None, help="path to harpyja.toml")

    doctor = sub.add_parser("doctor", help="environment preflight")
    doctor.add_argument("--config", default=None, help="path to harpyja.toml")

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


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "serve":
        return _cmd_serve(args, parser)
    if args.command == "doctor":
        return _cmd_doctor(args)
    parser.error(f"unknown command: {args.command}")  # pragma: no cover
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
