"""RED (task 16): artifact-dir resolution + self-ignore + XDG fallback (AC17)."""

import hashlib

import pytest

from harpyja.config.settings import Settings
from harpyja.index.artifacts import (
    ArtifactLocationError,
    repo_cache_key,
    resolve_artifact_dir,
)


def test_artifact_dir_defaults_to_repo_dot_harpyja(tmp_path):
    d = resolve_artifact_dir(tmp_path, Settings(), writable=lambda p: True)
    assert d == tmp_path / ".harpyja"
    assert d.is_dir()


def test_artifact_dir_writes_self_ignore_star(tmp_path):
    d = resolve_artifact_dir(tmp_path, Settings(), writable=lambda p: True)
    assert (d / ".gitignore").read_text(encoding="utf-8").strip() == "*"


def test_artifact_dir_does_not_touch_root_gitignore(tmp_path):
    root_ignore = tmp_path / ".gitignore"
    root_ignore.write_text("original\n", encoding="utf-8")
    resolve_artifact_dir(tmp_path, Settings(), writable=lambda p: True)
    assert root_ignore.read_text(encoding="utf-8") == "original\n"


def test_artifact_dir_falls_back_to_xdg_cache_when_repo_unwritable(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    cache = tmp_path / "xdg"
    cache.mkdir()

    def writable(p):
        return cache in p.parents or p == cache

    d = resolve_artifact_dir(
        repo, Settings(), environ={"XDG_CACHE_HOME": str(cache)}, writable=writable
    )
    assert cache in d.parents
    assert d.name == repo_cache_key(repo)
    assert (cache / "harpyja") in d.parents or d.parent == cache / "harpyja"


def test_artifact_dir_repo_hash_is_realpath_sha256_prefix(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    expected = hashlib.sha256(str(repo.resolve()).encode()).hexdigest()[:16]
    assert repo_cache_key(repo) == expected


def test_artifact_dir_fails_when_neither_writable(tmp_path):
    with pytest.raises(ArtifactLocationError):
        resolve_artifact_dir(
            tmp_path,
            Settings(),
            environ={"XDG_CACHE_HOME": str(tmp_path / "x")},
            writable=lambda p: False,
        )
