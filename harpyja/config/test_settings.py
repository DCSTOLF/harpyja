"""RED (task 4): layered settings precedence.

AC6 — resolution order is defaults < harpyja.toml < HARPYJA_* env < per-request.
"""

from harpyja.config.settings import Settings, load_settings, resolve_settings


def _write_toml(path, body):
    path.write_text(body, encoding="utf-8")
    return path


def test_load_settings_defaults_when_no_sources(tmp_path, monkeypatch):
    monkeypatch.delenv("HARPYJA_LM_API_BASE", raising=False)
    settings = load_settings(config_path=None, repo_path=tmp_path)
    assert settings == Settings()  # pristine defaults
    assert settings.lm_api_base == Settings().lm_api_base


def test_load_settings_env_overrides_toml(tmp_path, monkeypatch):
    toml = _write_toml(
        tmp_path / "harpyja.toml",
        'lm_api_base = "http://127.0.0.1:9999/v1"\n',
    )
    monkeypatch.setenv("HARPYJA_LM_API_BASE", "http://127.0.0.1:8000/v1")
    settings = load_settings(config_path=toml, repo_path=tmp_path)
    assert settings.lm_api_base == "http://127.0.0.1:8000/v1"


def test_load_settings_toml_used_when_no_env(tmp_path, monkeypatch):
    toml = _write_toml(
        tmp_path / "harpyja.toml",
        'lm_api_base = "http://127.0.0.1:9999/v1"\n',
    )
    monkeypatch.delenv("HARPYJA_LM_API_BASE", raising=False)
    settings = load_settings(config_path=toml, repo_path=tmp_path)
    assert settings.lm_api_base == "http://127.0.0.1:9999/v1"


def test_resolve_settings_request_override_beats_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HARPYJA_LM_API_BASE", "http://127.0.0.1:8000/v1")
    base = load_settings(config_path=None, repo_path=tmp_path)
    resolved = resolve_settings(base, {"lm_api_base": "http://127.0.0.1:7000/v1"})
    assert resolved.lm_api_base == "http://127.0.0.1:7000/v1"
    # base is not mutated by the override
    assert base.lm_api_base == "http://127.0.0.1:8000/v1"


def test_resolve_settings_none_override_is_noop(tmp_path, monkeypatch):
    monkeypatch.delenv("HARPYJA_LM_API_BASE", raising=False)
    base = load_settings(config_path=None, repo_path=tmp_path)
    assert resolve_settings(base, None) == base
