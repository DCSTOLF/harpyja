"""Spec 0025 (T14/T15, AC9): the retracted FastContext dependency is not declared.

An executable guard that the packaging metadata no longer references the retracted
`fastcontext` git dependency — so a clean `uv sync` from scratch cannot pull it back
in. Reads the real `pyproject.toml`, never a snapshot.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

_PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _pyproject() -> dict:
    with open(_PYPROJECT, "rb") as fh:
        return tomllib.load(fh)


def test_pyproject_declares_no_fastcontext_dependency():
    data = _pyproject()
    deps = data["project"]["dependencies"]
    assert not any("fastcontext" in d for d in deps), deps


def test_pyproject_has_no_fastcontext_uv_source():
    data = _pyproject()
    sources = data.get("tool", {}).get("uv", {}).get("sources", {})
    assert "fastcontext" not in sources, sources
