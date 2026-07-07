"""RED (task 4): layered settings precedence.

AC6 — resolution order is defaults < harpyja.toml < HARPYJA_* env < per-request.
"""

import pytest

from harpyja.config.settings import (
    Settings,
    UnsupportedVerifyMethod,
    load_settings,
    resolve_settings,
)


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


# --- Spec 0007: Scout FastContext model + FC_* params (AC3) ---
# Spec 0016: scout default flipped to the served dstolf Q8 RL tag (B1 fix) — the
# old mitkox RL-Q4 tag was not served by Ollama → HTTP 404 on every Scout call.
_FC_GGUF = "hf.co/dstolf/FastContext-1.0-4B-RL-Q8_0-GGUF:latest"

# The old, unserved default — must no longer be a live field default (spec 0016 AC6).
_OLD_UNSERVED_SCOUT = "hf.co/mitkox/FastContext-1.0-4B-RL-Q4_K_M-GGUF:latest"


def test_settings_scout_model_default():
    s = Settings()
    assert s.scout_model == _FC_GGUF
    # Scout's fine-tune is distinct from Deep's driver model.
    assert s.scout_model != s.lm_model


def test_settings_lm_model_default():
    # Spec 0016 (AC2 / D2): the Deep default flipped from the llama.cpp placeholder
    # "local" to a served Ollama tag. No prior test pinned this value.
    s = Settings()
    assert s.lm_model == "hf.co/Qwen/Qwen3-8B-GGUF:latest"


def test_settings_defaults_drop_unserved_tags():
    # Spec 0016/0025 (AC6): drift guard by FIELD-DEFAULT INTROSPECTION, never a text
    # grep — so docstrings, comments, and historical fixtures cannot trip a false
    # positive. The property the guard ENFORCES is "no field default names an
    # UNSERVED/unobtainable tag" — NOT "no default is FastContext-branded" (which would
    # contradict the kept, served `scout_model` gate baseline below).
    import dataclasses

    default_values = {
        f.name: (f.default_factory() if f.default is dataclasses.MISSING else f.default)
        for f in dataclasses.fields(Settings)
    }
    assert _OLD_UNSERVED_SCOUT not in default_values.values()
    assert default_values["scout_model"] == _FC_GGUF  # served → allowed
    assert default_values["lm_model"] != "local"


def test_scout_model_preserved_as_served_gate_baseline():
    # Spec 0025 (AC6): the FastContext BACKEND is removed, but `scout_model` is a
    # SEPARATE consumer — the Verification Gate A/B baseline (verify_method=
    # "scout_model", spec 0018). Its default is a FastContext-lineage tag, but a SERVED
    # one, so the baseline still resolves. It is scoped OUT of the FC-removal: the
    # cutover must not sweep it away with the FC_* plumbing.
    import dataclasses

    from harpyja.config.settings import _VERIFY_METHODS

    field_names = {f.name for f in dataclasses.fields(Settings)}
    assert "scout_model" in field_names  # NOT removed by the FC cleanup
    assert Settings().scout_model == _FC_GGUF  # served default retained
    assert "scout_model" in _VERIFY_METHODS  # still a live gate baseline


# Spec 0025: the FC-only Scout knobs (scout_max_tokens/scout_temperature/
# scout_reasoning_effort) were removed with the FastContext adapter — their absence is
# pinned by test_fastcontext_absent.test_fc_only_scout_settings_fields_removed.


def test_settings_scout_model_precedence(tmp_path, monkeypatch):
    monkeypatch.delenv("HARPYJA_SCOUT_MODEL", raising=False)
    toml = _write_toml(tmp_path / "harpyja.toml", 'scout_model = "from-toml"\n')
    # toml beats default
    base = load_settings(config_path=toml, repo_path=tmp_path)
    assert base.scout_model == "from-toml"
    # env beats toml
    monkeypatch.setenv("HARPYJA_SCOUT_MODEL", "from-env")
    env_base = load_settings(config_path=toml, repo_path=tmp_path)
    assert env_base.scout_model == "from-env"
    # per-request override beats env
    resolved = resolve_settings(env_base, {"scout_model": "from-request"})
    assert resolved.scout_model == "from-request"
    assert env_base.scout_model == "from-env"  # base not mutated


# --- Wave 4: Deep (Tier 2) budgets (AC10) ---


def test_settings_deep_defaults():
    s = Settings()
    assert s.deep_seed_top_n == 5
    assert s.deep_max_citations == 20
    assert s.deep_max_span_lines == 200
    assert s.deep_max_depth == 3
    assert s.deep_max_subqueries == 8
    assert s.deep_max_tool_calls == 200
    assert s.deep_token_ceiling == 32000
    assert s.deep_wall_clock_ms == 60000


def test_settings_deep_loads_from_toml(tmp_path, monkeypatch):
    for k in (
        "DEEP_SEED_TOP_N",
        "DEEP_MAX_DEPTH",
        "DEEP_WALL_CLOCK_MS",
    ):
        monkeypatch.delenv(f"HARPYJA_{k}", raising=False)
    toml = _write_toml(
        tmp_path / "harpyja.toml",
        "deep_max_depth = 2\ndeep_max_subqueries = 4\ndeep_wall_clock_ms = 5000\n",
    )
    s = load_settings(config_path=toml, repo_path=tmp_path)
    assert s.deep_max_depth == 2
    assert s.deep_max_subqueries == 4
    assert s.deep_wall_clock_ms == 5000
    assert isinstance(s.deep_max_depth, int)


def test_settings_deep_loads_from_env(tmp_path, monkeypatch):
    toml = _write_toml(tmp_path / "harpyja.toml", "deep_max_tool_calls = 50\n")
    monkeypatch.setenv("HARPYJA_DEEP_MAX_TOOL_CALLS", "111")
    s = load_settings(config_path=toml, repo_path=tmp_path)
    assert s.deep_max_tool_calls == 111  # env beats toml


# --- Spec 0008 (Wave 5): Verification Gate settings (AC13) ---


def test_settings_has_verify_defaults():
    s = Settings()
    # Spec 0018 (B2 fix / D1): the gate judge default flips from the OOD finder
    # `scout_model` to the served instruct model — `verify_method` now selects it.
    assert s.verify_method == "instruct_model"
    assert s.verify_threshold == 0.6
    assert s.verify_top_n == 3
    # Defaults appended last keep the float typed as a float.
    assert isinstance(s.verify_threshold, float)


def test_settings_verify_method_default_is_instruct_model():
    # Spec 0018 AC2: the DEFAULT flip is asserted via dataclass-field introspection
    # (not a source grep), so this guards drift rather than matching a string in a file.
    from dataclasses import fields

    field = next(f for f in fields(Settings) if f.name == "verify_method")
    assert field.default == "instruct_model"


def test_verify_method_instruct_model_loads_clean():
    # Spec 0018 AC1: the new instruct-model judge value constructs without error.
    s = Settings(verify_method="instruct_model")
    assert s.verify_method == "instruct_model"


def test_verify_methods_membership_is_scout_and_instruct():
    # Spec 0018 AC1 / D3: `verify_method` finally selects a judge; both the retained
    # finder method and the new instruct method are accepted (nothing else).
    from harpyja.config.settings import _VERIFY_METHODS

    assert _VERIFY_METHODS == frozenset({"scout_model", "instruct_model"})


def test_verify_threshold_coerces_float_from_toml(tmp_path, monkeypatch):
    monkeypatch.delenv("HARPYJA_VERIFY_THRESHOLD", raising=False)
    toml = _write_toml(tmp_path / "harpyja.toml", "verify_threshold = 0.8\n")
    s = load_settings(config_path=toml, repo_path=tmp_path)
    assert s.verify_threshold == 0.8
    assert isinstance(s.verify_threshold, float)


def test_verify_threshold_coerces_float_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HARPYJA_VERIFY_THRESHOLD", "0.42")
    s = load_settings(config_path=None, repo_path=tmp_path)
    assert s.verify_threshold == 0.42
    assert isinstance(s.verify_threshold, float)


def test_verify_method_scout_model_loads_clean():
    # The one shipping value constructs without error.
    s = Settings(verify_method="scout_model")
    assert s.verify_method == "scout_model"


def test_verify_method_rejects_unsupported_value_at_load(tmp_path, monkeypatch):
    # AC13 / no-false-capability: an accepted-but-inert backend must reject loudly,
    # never silently fall through to scout_model.
    monkeypatch.setenv("HARPYJA_VERIFY_METHOD", "embedding")
    with pytest.raises(UnsupportedVerifyMethod) as exc:
        load_settings(config_path=None, repo_path=tmp_path)
    msg = str(exc.value)
    assert "verify_method" in msg
    assert "scout_model" in msg  # names the accepted set


def test_verify_method_arbitrary_value_rejected():
    for bad in ("model_judge", "embedding", "totally-made-up"):
        with pytest.raises(UnsupportedVerifyMethod):
            Settings(verify_method=bad)


def test_verify_method_rejected_on_per_request_override(tmp_path, monkeypatch):
    monkeypatch.delenv("HARPYJA_VERIFY_METHOD", raising=False)
    base = load_settings(config_path=None, repo_path=tmp_path)
    with pytest.raises(UnsupportedVerifyMethod):
        resolve_settings(base, {"verify_method": "model_judge"})


# --- Spec 0017 (B3): gateway HTTP timeout (AC1 / D1 / D2) ---


def test_settings_has_http_timeout_default():
    # AC1 / D1: a finite, positive float default — never None. The bound must exist
    # out of the box so the gateway's urlopen can never hang forever.
    import dataclasses
    import math

    s = Settings()
    assert s.lm_http_timeout_s == 120.0
    assert isinstance(s.lm_http_timeout_s, float)
    assert s.lm_http_timeout_s > 0
    assert math.isfinite(s.lm_http_timeout_s)
    # Field-default introspection: the declared default is not None.
    default_values = {
        f.name: (f.default_factory() if f.default is dataclasses.MISSING else f.default)
        for f in dataclasses.fields(Settings)
    }
    assert default_values["lm_http_timeout_s"] is not None


def test_http_timeout_coerces_float_from_toml(tmp_path, monkeypatch):
    monkeypatch.delenv("HARPYJA_LM_HTTP_TIMEOUT_S", raising=False)
    toml = _write_toml(tmp_path / "harpyja.toml", "lm_http_timeout_s = 5.0\n")
    s = load_settings(config_path=toml, repo_path=tmp_path)
    assert s.lm_http_timeout_s == 5.0
    assert isinstance(s.lm_http_timeout_s, float)


def test_http_timeout_coerces_float_from_env_beats_toml(tmp_path, monkeypatch):
    # AC1 / D2: env > toml; no per-request layer is exercised here, and the loaded
    # base is a fresh frozen instance (never mutated in place).
    toml = _write_toml(tmp_path / "harpyja.toml", "lm_http_timeout_s = 10.0\n")
    monkeypatch.setenv("HARPYJA_LM_HTTP_TIMEOUT_S", "2.5")
    s = load_settings(config_path=toml, repo_path=tmp_path)
    assert s.lm_http_timeout_s == 2.5
    assert isinstance(s.lm_http_timeout_s, float)


# --- Spec 0024 (v2 explorer loop): new Scout loop budgets (T1/T2, AC4/AC5/AC2) ---


def test_scout_loop_budgets_present_with_provisional_defaults():
    # The explorer loop's turn/time/self-recovery/glob budgets are first-class
    # Settings fields (provisional, flagged for the bake-off — OQ1/OQ3).
    s = Settings()
    assert s.scout_max_turns == 12
    assert s.scout_wall_clock_s == 300.0
    assert s.scout_loop_repeat_n == 2
    assert s.scout_history_char_cap == 60000
    assert s.scout_glob_max_paths == 400


def test_scout_ls_max_entries_default_is_finite_positive_bound():
    # spec 0027: the `ls`/tree tool's output clamp — a first-class Settings field
    # (parallel to scout_glob_max_paths for glob), finite + positive.
    s = Settings()
    assert isinstance(s.scout_ls_max_entries, int)
    assert s.scout_ls_max_entries > 0
    assert s.scout_ls_max_entries == 200


def test_scout_ls_max_entries_is_declared_settings_field():
    # Field-default introspection (drift guard): the clamp is a declared frozen-dataclass
    # field, not an ad-hoc attribute.
    import dataclasses

    names = {f.name for f in dataclasses.fields(Settings)}
    assert "scout_ls_max_entries" in names


def test_scout_ls_max_entries_coerces_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HARPYJA_SCOUT_LS_MAX_ENTRIES", "150")
    s = load_settings(repo_path=tmp_path)
    assert s.scout_ls_max_entries == 150
    assert isinstance(s.scout_ls_max_entries, int)


def test_scout_wall_clock_exceeds_per_call_http_timeout():
    # The whole-loop wall-clock ceiling must sit strictly ABOVE the per-call HTTP
    # timeout floor — turns and time are distinct budgets (AC4). A single slow call
    # (bounded by lm_http_timeout_s) must be able to complete before the loop ceiling.
    s = Settings()
    assert s.scout_wall_clock_s > s.lm_http_timeout_s


def test_scout_loop_budgets_coerce_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HARPYJA_SCOUT_MAX_TURNS", "20")
    monkeypatch.setenv("HARPYJA_SCOUT_WALL_CLOCK_S", "450.5")
    monkeypatch.setenv("HARPYJA_SCOUT_LOOP_REPEAT_N", "3")
    monkeypatch.setenv("HARPYJA_SCOUT_HISTORY_CHAR_CAP", "80000")
    monkeypatch.setenv("HARPYJA_SCOUT_GLOB_MAX_PATHS", "250")
    s = load_settings(repo_path=tmp_path)
    assert s.scout_max_turns == 20
    assert isinstance(s.scout_max_turns, int)
    assert s.scout_wall_clock_s == 450.5
    assert isinstance(s.scout_wall_clock_s, float)
    assert s.scout_loop_repeat_n == 3
    assert s.scout_history_char_cap == 80000
    assert s.scout_glob_max_paths == 250
