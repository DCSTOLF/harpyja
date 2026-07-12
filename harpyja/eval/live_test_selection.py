"""Spec 0041 (AC6) — the enforced executable consumer of the live opt-in.

A deselect default whose opt-in path exists only as documentation rots into a
live suite that never runs (the spec's own OQ3 risk). This module IS the named
consumer: it mechanically proves, via ``pytest --collect-only`` over the real
committed config, that (a) the opt-in selection (``-m integration``) reaches a
non-zero live suite and (b) the DEFAULT selection contains zero live-marked
tests. The operator drivers call it in preflight; a unit test pins it.

The documented opt-in invocation::

    uv run pytest -m integration            # the live suite (skip-not-fail)
    HARPYJA_REQUIRE_LIVE_STACK=1 uv run pytest -m integration   # strict
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

__all__ = ["LiveSelectionError", "assert_live_optin_selection"]


class LiveSelectionError(RuntimeError):
    """The committed test-selection config violates the AC6 contract."""


def _collect_ids(root: Path, *extra: str) -> list[str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", *extra],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    # Exit 5 = nothing collected (a legitimate zero); anything past 5 is a
    # config/usage failure and must be loud.
    if proc.returncode not in (0, 5):
        raise LiveSelectionError(
            f"pytest --collect-only failed (exit {proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return [
        line.strip()
        for line in proc.stdout.splitlines()
        if "::" in line and not line.startswith(("=", "<"))
    ]


def assert_live_optin_selection(root: str | Path) -> dict[str, int]:
    """Prove both directions of the AC6 contract against the real config.

    Raises :class:`LiveSelectionError` if the opt-in selection is EMPTY (the
    live suite has rotted out of reach) or if any live-marked test appears in
    the DEFAULT selection (the 0040 accident is reachable again).
    """
    root = Path(root)
    default_ids = set(_collect_ids(root))
    optin_ids = set(_collect_ids(root, "-m", "integration"))
    if not optin_ids:
        raise LiveSelectionError(
            "opt-in selection (-m integration) collects ZERO live tests — "
            "the live suite is unreachable; a gate that hides the live tests "
            "forever is its own failure"
        )
    live_in_default = sorted(default_ids & optin_ids)
    if live_in_default:
        raise LiveSelectionError(
            "live-marked tests are reachable by the DEFAULT invocation "
            f"(the 0040 accident): {live_in_default[:5]}"
        )
    return {
        "default": len(default_ids),
        "optin": len(optin_ids),
        "live_in_default": 0,
    }
