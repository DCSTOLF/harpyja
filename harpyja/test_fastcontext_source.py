"""RED (spec 0013): the FastContext dependency must be sourced from the DCSTOLF
fork at the unchanged pinned rev.

Drives AC1/AC3/AC4 — a metadata-assertion test that parses `pyproject.toml` and
scans `uv.lock` + the install/source docs, asserting the git source moved from
`microsoft/fastcontext` to `DCSTOLF/fastcontext` while the pinned commit is
byte-identical. This file lives next to the package under test per repo
conventions (no top-level tests/ root).
"""

import tomllib
from pathlib import Path

EXPECTED_URL = "https://github.com/DCSTOLF/fastcontext"
EXPECTED_REV = "1522d6d6b5e040e817b468e12826662aa069a8b0"
LEGACY_HOST = "github.com/microsoft/fastcontext"

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(name):
    return (_REPO_ROOT / name).read_text(encoding="utf-8")


def _fastcontext_source():
    data = tomllib.loads(_read("pyproject.toml"))
    return data["tool"]["uv"]["sources"]["fastcontext"]


def test_pyproject_fastcontext_git_source_is_dcstolf_fork():
    assert _fastcontext_source()["git"] == EXPECTED_URL


def test_pyproject_fastcontext_rev_is_unchanged_pin():
    assert _fastcontext_source()["rev"] == EXPECTED_REV


def test_pyproject_has_no_microsoft_fastcontext_url():
    assert LEGACY_HOST not in _read("pyproject.toml")


def test_uv_lock_resolves_fastcontext_from_dcstolf_fork():
    lock = _read("uv.lock")
    assert EXPECTED_URL in lock
    assert LEGACY_HOST not in lock
    assert EXPECTED_REV in lock


def test_docs_have_no_microsoft_fastcontext_url():
    for doc in ("README.md", "FASTCONTEXT_INSTALL.md"):
        assert LEGACY_HOST not in _read(doc), doc
