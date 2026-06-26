"""RED (task 10): `.gitignore` + `ignore_globs` matching via pathspec (AC4).

Honors negation, directory-only rules, anchored vs floating globs, `**`, and
nested per-directory `.gitignore` files — all without invoking `git`.
"""

import subprocess

from harpyja.index.ignore import build_ignore


def _write(root, rel, content=""):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def test_ignore_anchored_vs_floating_globs(tmp_path):
    _write(tmp_path, ".gitignore", "/rootonly\nanylevel\n")
    m = build_ignore(tmp_path)
    assert m.is_ignored("rootonly", is_dir=False) is True
    assert m.is_ignored("sub/rootonly", is_dir=False) is False  # anchored to root
    assert m.is_ignored("anylevel", is_dir=False) is True
    assert m.is_ignored("sub/anylevel", is_dir=False) is True  # floating


def test_ignore_directory_only_rule(tmp_path):
    _write(tmp_path, ".gitignore", "logs/\n")
    m = build_ignore(tmp_path)
    assert m.is_ignored("logs", is_dir=True) is True
    assert m.is_ignored("logs", is_dir=False) is False  # a *file* named logs is kept
    assert m.is_ignored("logs/app.txt", is_dir=False) is True


def test_ignore_double_star_glob(tmp_path):
    _write(tmp_path, ".gitignore", "**/tmp/**\n")
    m = build_ignore(tmp_path)
    assert m.is_ignored("a/tmp/b.txt", is_dir=False) is True


def test_ignore_negation_reinclude(tmp_path):
    _write(tmp_path, ".gitignore", "*.log\n!keep.log\n")
    m = build_ignore(tmp_path)
    assert m.is_ignored("a.log", is_dir=False) is True
    assert m.is_ignored("keep.log", is_dir=False) is False


def test_ignore_nested_per_directory_gitignore(tmp_path):
    _write(tmp_path, "sub/.gitignore", "secret.txt\n")
    m = build_ignore(tmp_path)
    assert m.is_ignored("sub/secret.txt", is_dir=False) is True
    assert m.is_ignored("secret.txt", is_dir=False) is False  # root not affected


def test_ignore_globs_apply_in_addition(tmp_path):
    m = build_ignore(tmp_path, extra_globs=("*.min.js",))
    assert m.is_ignored("a.min.js", is_dir=False) is True


def test_ignore_no_git_invocation(tmp_path, monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("git was invoked")

    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.setattr(subprocess, "Popen", _boom)
    _write(tmp_path, ".gitignore", "*.log\n")
    m = build_ignore(tmp_path)
    assert m.is_ignored("x.log", is_dir=False) is True
