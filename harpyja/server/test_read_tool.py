"""RED (task 28/30): bounded read + clamp + path confinement (AC15, AC16)."""

import sys

import pytest

from harpyja.config.settings import Settings
from harpyja.server.tools import PathConfinementError, read_snippet


def _write(root, rel, content):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def test_read_returns_spec_shape(tmp_path):
    _write(tmp_path, "a.py", "l1\nl2\nl3\n")
    out = read_snippet(tmp_path, "a.py", 1, 2, Settings())
    assert set(out.keys()) == {"path", "start", "end", "language", "content", "truncated"}
    assert out["language"] == "python"


def test_read_one_indexed_inclusive_range(tmp_path):
    _write(tmp_path, "a.txt", "line1\nline2\nline3\nline4\n")
    out = read_snippet(tmp_path, "a.txt", 2, 3, Settings())
    assert "line2" in out["content"] and "line3" in out["content"]
    assert "line1" not in out["content"] and "line4" not in out["content"]
    assert out["start"] == 2 and out["end"] == 3
    assert out["truncated"] is False


def test_read_clamps_tool_max_lines_sets_truncated(tmp_path):
    _write(tmp_path, "a.txt", "".join(f"l{i}\n" for i in range(1, 11)))
    out = read_snippet(tmp_path, "a.txt", 1, 10, Settings(tool_max_lines=2))
    assert out["end"] == 2  # clamped to the line bound
    assert out["truncated"] is True


def test_read_clamps_tool_max_chars_sets_truncated(tmp_path):
    _write(tmp_path, "a.txt", "abcdefghij\nklmnopqrst\n")
    out = read_snippet(tmp_path, "a.txt", 1, 2, Settings(tool_max_chars=5))
    assert len(out["content"]) <= 5
    assert out["truncated"] is True


def test_read_not_truncated_when_within_bounds(tmp_path):
    _write(tmp_path, "a.txt", "l1\nl2\nl3\n")
    out = read_snippet(tmp_path, "a.txt", 1, 3, Settings())
    assert out["truncated"] is False


def test_read_rejects_parent_traversal(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (tmp_path / "secret.txt").write_text("top secret\n", encoding="utf-8")
    with pytest.raises(PathConfinementError):
        read_snippet(repo, "../secret.txt", 1, 1, Settings())


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privilege on Windows")
def test_read_rejects_in_repo_symlink_escaping_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret\n", encoding="utf-8")
    (repo / "link.txt").symlink_to(outside)
    with pytest.raises(PathConfinementError):
        read_snippet(repo, "link.txt", 1, 1, Settings())
