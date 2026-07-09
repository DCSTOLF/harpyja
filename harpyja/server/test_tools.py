"""Pins for server/tools.py path confinement (spec 0035 AC4)."""

import pytest

from harpyja.server.tools import PathConfinementError, confine_path


def test_confine_path_nonexistent_in_repo_path_resolves_without_raising(tmp_path):
    """PIN (0035): confine_path resolves NON-STRICT — a nonexistent in-repo path
    passes confinement without raising. The 0035 scope-marker branches depend on
    this contract (the wrapper's exists() guard, not confine_path, detects
    absence); a future strict/exists change here must fail this pin loudly."""
    out = confine_path(str(tmp_path), "does/not/exist")
    assert out == (tmp_path / "does" / "not" / "exist").resolve()


def test_confine_path_still_rejects_escape(tmp_path):
    """The confinement half is untouched: a repo-escaping path raises."""
    with pytest.raises(PathConfinementError):
        confine_path(str(tmp_path), "../outside")
