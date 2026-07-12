"""Spec 0041 (AC6) — safe-by-default test invocation, with an enforced consumer.

The 0040 run-1 contamination was a plain ``pytest -q`` firing LIVE integration
tests at the measurement endpoint. The default invocation must DESELECT
live-marked tests (opt-in, not opt-out) — and the opt-in path has a MECHANICAL
executable consumer (``assert_live_optin_selection``), so the live suite can
never silently rot into never-running.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_addopts_deselects_integration_by_default():
    cfg = tomllib.loads(
        (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    addopts = cfg["tool"]["pytest"]["ini_options"].get("addopts", [])
    joined = " ".join(addopts) if isinstance(addopts, list) else str(addopts)
    assert "-m" in joined and "not integration" in joined, (
        "the committed default invocation must deselect live integration "
        f"tests (marker-based) — addopts is {addopts!r}"
    )


def test_marker_deselect_collects_zero_integration_and_optin_collects_them(
    tmp_path,
):
    """The mechanism itself, mechanically: under the deselect default a
    live-marked test is NOT collected; under the documented opt-in it is."""
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\n'
        'addopts = ["-m", "not integration"]\n'
        'markers = ["integration: live"]\n',
        encoding="utf-8",
    )
    (tmp_path / "test_sample.py").write_text(
        "import pytest\n\n"
        "@pytest.mark.integration\n"
        "def test_live():\n    pass\n\n"
        "def test_unit():\n    pass\n",
        encoding="utf-8",
    )

    def collect(*extra: str) -> str:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", *extra],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.stdout

    default = collect()
    assert "test_unit" in default and "test_live" not in default
    optin = collect("-m", "integration")
    assert "test_live" in optin and "test_unit" not in optin


def test_assert_live_optin_selection_is_the_enforced_consumer():
    """The named executable consumer over the REAL repo config: non-zero
    live-marked tests under the opt-in, zero of them in the default
    selection — a mechanical assertion, not documentation."""
    from harpyja.eval.live_test_selection import assert_live_optin_selection

    counts = assert_live_optin_selection(_REPO_ROOT)
    assert counts["optin"] > 0  # the live suite exists and is reachable
    assert counts["live_in_default"] == 0  # and the default cannot fire it