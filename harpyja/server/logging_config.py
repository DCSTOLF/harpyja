"""Logging configuration that keeps stdout clean for the stdio transport.

On the stdio MCP transport, stdout carries JSON-RPC frames — any stray write
corrupts the protocol. So all logging goes to **stderr** and we ensure no
handler targets stdout (AC9). Call :func:`configure_logging` before serving.
"""

from __future__ import annotations

import logging
import sys

_DEFAULT_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    """Install a single stderr handler on the root logger; drop stdout ones."""
    root = logging.getLogger()

    # Remove any pre-existing handler that writes to stdout.
    for handler in root.handlers[:]:
        if isinstance(handler, logging.StreamHandler) and handler.stream is sys.stdout:
            root.removeHandler(handler)

    # Add a stderr handler if one isn't already present.
    has_stderr = any(
        isinstance(h, logging.StreamHandler) and h.stream is sys.stderr for h in root.handlers
    )
    if not has_stderr:
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
        root.addHandler(handler)

    root.setLevel(level)
