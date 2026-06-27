"""RED (task 4): layered settings precedence.

AC6 — resolution order is defaults < harpyja.toml < HARPYJA_* env < per-request.
"""

from harpyja.config.settings import Settings, load_settings, resolve_settings


def test_settings_has_wave1_default_fields():
    s = Settings()
    assert s.ignore_globs == ()
    assert s.follow_symlinks is False
    assert s.search_max_files == 4000
    assert s.search_max_matches == 400
    assert s.rg_chunk_size == 512
    assert s.tool_max_lines == 400
    assert s.tool_max_chars == 20000
    assert s.manifest_page == 200
    assert s.cache_dir is None


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


def test_coerce_ignore_globs_from_toml_list(tmp_path, monkeypatch):
    toml = _write_toml(
        tmp_path / "harpyja.toml",
        'ignore_globs = ["**/dist/**", "*.min.js"]\n',
    )
    monkeypatch.delenv("HARPYJA_IGNORE_GLOBS", raising=False)
    s = load_settings(config_path=toml, repo_path=tmp_path)
    assert s.ignore_globs == ("**/dist/**", "*.min.js")
    assert isinstance(s.ignore_globs, tuple)


def test_coerce_ignore_globs_from_env_csv(tmp_path, monkeypatch):
    monkeypatch.setenv("HARPYJA_IGNORE_GLOBS", "a/**, b/**")
    s = load_settings(config_path=None, repo_path=tmp_path)
    assert s.ignore_globs == ("a/**", "b/**")


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


# --- Wave 3: Scout budgets (AC3, AC7) ---


def test_settings_scout_defaults():
    s = Settings()
    assert s.scout_seed_top_n == 5
    assert s.scout_max_citations == 20
    assert s.scout_max_span_lines == 200


def test_settings_scout_loads_from_toml(tmp_path, monkeypatch):
    for k in ("SCOUT_SEED_TOP_N", "SCOUT_MAX_CITATIONS", "SCOUT_MAX_SPAN_LINES"):
        monkeypatch.delenv(f"HARPYJA_{k}", raising=False)
    toml = _write_toml(
        tmp_path / "harpyja.toml",
        "scout_seed_top_n = 3\nscout_max_citations = 12\nscout_max_span_lines = 80\n",
    )
    s = load_settings(config_path=toml, repo_path=tmp_path)
    assert s.scout_seed_top_n == 3
    assert s.scout_max_citations == 12
    assert s.scout_max_span_lines == 80
    # Coerced to int, not left as raw strings.
    assert isinstance(s.scout_seed_top_n, int)


def test_settings_scout_loads_from_env(tmp_path, monkeypatch):
    toml = _write_toml(tmp_path / "harpyja.toml", "scout_seed_top_n = 3\n")
    monkeypatch.setenv("HARPYJA_SCOUT_SEED_TOP_N", "7")
    s = load_settings(config_path=toml, repo_path=tmp_path)
    assert s.scout_seed_top_n == 7  # env beats toml
