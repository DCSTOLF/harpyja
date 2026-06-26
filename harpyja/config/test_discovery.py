"""RED (task 6): harpyja.toml discovery order.

AC7 — explicit --config wins over a cwd harpyja.toml, which wins over the
repo-root file; None when no file exists anywhere.
"""

from harpyja.config.discovery import discover_config_path


def test_discover_config_explicit_path_wins(tmp_path, monkeypatch):
    cwd = tmp_path / "cwd"
    root = tmp_path / "root"
    cwd.mkdir()
    root.mkdir()
    (cwd / "harpyja.toml").write_text("", encoding="utf-8")
    (root / "harpyja.toml").write_text("", encoding="utf-8")
    explicit = tmp_path / "custom.toml"
    explicit.write_text("", encoding="utf-8")

    found = discover_config_path(explicit=explicit, cwd=cwd, repo_root=root)
    assert found == explicit


def test_discover_config_cwd_beats_repo_root(tmp_path):
    cwd = tmp_path / "cwd"
    root = tmp_path / "root"
    cwd.mkdir()
    root.mkdir()
    (cwd / "harpyja.toml").write_text("", encoding="utf-8")
    (root / "harpyja.toml").write_text("", encoding="utf-8")

    found = discover_config_path(explicit=None, cwd=cwd, repo_root=root)
    assert found == cwd / "harpyja.toml"


def test_discover_config_repo_root_fallback(tmp_path):
    cwd = tmp_path / "cwd"
    root = tmp_path / "root"
    cwd.mkdir()
    root.mkdir()
    (root / "harpyja.toml").write_text("", encoding="utf-8")  # only repo root has one

    found = discover_config_path(explicit=None, cwd=cwd, repo_root=root)
    assert found == root / "harpyja.toml"


def test_discover_config_none_when_absent(tmp_path):
    cwd = tmp_path / "cwd"
    root = tmp_path / "root"
    cwd.mkdir()
    root.mkdir()

    assert discover_config_path(explicit=None, cwd=cwd, repo_root=root) is None
