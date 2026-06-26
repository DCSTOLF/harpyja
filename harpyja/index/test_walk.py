"""RED (task 12): the indexer walk (AC4, AC6a)."""

import sys

import pytest

from harpyja.index.ignore import build_ignore
from harpyja.index.walk import walk


def _write(root, rel, content="x"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def test_walk_yields_non_ignored_files(tmp_path):
    _write(tmp_path, ".gitignore", "*.log\n")
    _write(tmp_path, "a.py")
    _write(tmp_path, "sub/b.py")
    _write(tmp_path, "noise.log")
    found = set(walk(tmp_path, build_ignore(tmp_path)))
    # .gitignore is itself a real, non-ignored file and is indexed; noise.log is not.
    assert found == {".gitignore", "a.py", "sub/b.py"}
    assert "noise.log" not in found


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privilege on Windows")
def test_walk_skips_symlinks_when_follow_false(tmp_path):
    _write(tmp_path, "real.py")
    (tmp_path / "link.py").symlink_to(tmp_path / "real.py")
    (tmp_path / "realdir").mkdir()
    _write(tmp_path, "realdir/c.py")
    (tmp_path / "linkdir").symlink_to(tmp_path / "realdir", target_is_directory=True)
    found = set(walk(tmp_path, build_ignore(tmp_path), follow_symlinks=False))
    assert found == {"real.py", "realdir/c.py"}
    assert not any(p.startswith("linkdir") or p == "link.py" for p in found)


def test_walk_descends_unignored_dirs_only(tmp_path):
    _write(tmp_path, ".gitignore", "node_modules/\n")
    _write(tmp_path, "node_modules/pkg/x.js")
    _write(tmp_path, "src/y.py")
    found = set(walk(tmp_path, build_ignore(tmp_path)))
    assert found == {".gitignore", "src/y.py"}
    assert not any(p.startswith("node_modules") for p in found)
