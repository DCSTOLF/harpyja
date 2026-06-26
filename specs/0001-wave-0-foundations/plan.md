---
id: "0001"
title: "Wave 0 — Foundations"
spec: specs/0001-wave-0-foundations/spec.md
created: 2026-06-26
---

# Plan 0001 — Wave 0 — Foundations

Test-first (RED→GREEN→REFACTOR) plan. Every GREEN step is preceded by a failing
RED test. Greenfield: no `harpyja/` package, no `pyproject.toml`, no tests yet —
so step 1 (RED) legitimately fails at collection time and step 2 drives the
skeleton into existence.

Conventions: Python 3.12, pytest, ruff, `uv`/`pyproject.toml`. Test files are
`test_*.py` co-located with the package under test (no top-level `tests/` root);
test functions `test_<subject>_<scenario>`; logs to stderr, stdout clean on the
stdio transport.

## Group A — Packaging & lint/test bootstrap (AC1, AC2)

1. **RED — Failing import test for package skeleton**
   - Test: `harpyja/test_package_skeleton.py` → `test_subpackages_importable_all_eight`, `test_cli_module_importable`
   - Asserts `importlib.import_module` succeeds for `harpyja.{server,orchestrator,index,symbols,scout,deep,gateway,config}` and `harpyja.cli`.
   - AC: 2. Automatable.

2. **GREEN — Create `pyproject.toml` + package skeleton**
   - Prod: `pyproject.toml` (`requires-python = ">=3.12"`, `[project]` name `harpyja`, deps `fastmcp`/`mcp`, `[tool.ruff]`, `[tool.pytest.ini_options]` with `python_files = test_*.py` + `testpaths`/`norecursedirs` so co-located tests are collected); `harpyja/__init__.py`; `harpyja/{server,orchestrator,index,symbols,scout,deep,gateway,config}/__init__.py`; `harpyja/cli.py` stub.
   - AC: 1, 2. Automatable.

3. **REFACTOR — Lint/test gate green**
   - Run `ruff check` and `pytest`; fix skeleton lint nits. No new test.
   - AC: 1. Automatable (gate). _Delegate: codex._

## Group B — Config subsystem (AC6, AC7)

4. **RED — Config precedence test**
   - Test: `harpyja/config/test_settings.py` → `test_load_settings_env_overrides_toml`, `test_resolve_settings_request_override_beats_env`, `test_load_settings_defaults_when_no_sources`
   - Asserts defaults < `harpyja.toml` < `HARPYJA_*` env < per-request override.
   - AC: 6. Automatable.

5. **GREEN — Implement layered settings merge**
   - Prod: `harpyja/config/settings.py` — `Settings` dataclass + `load_settings(config_path=None, repo_path=None)` + `resolve_settings(base, request_override=None)`.
   - AC: 6. Automatable.

6. **RED — `harpyja.toml` discovery-order test**
   - Test: `harpyja/config/test_discovery.py` → `test_discover_config_explicit_path_wins`, `test_discover_config_cwd_beats_repo_root`, `test_discover_config_repo_root_fallback`, `test_discover_config_none_when_absent`
   - Uses `tmp_path` + `monkeypatch.chdir`.
   - AC: 7. Automatable.

7. **GREEN — Implement config discovery**
   - Prod: `harpyja/config/discovery.py` — `discover_config_path(explicit=None, cwd=None, repo_root=None)` (explicit > cwd > repo-root); wire into `load_settings`.
   - AC: 7. Automatable.

## Group C — ModelGateway air-gap (AC8)

8. **RED — `assert_local` test**
   - Test: `harpyja/gateway/test_gateway.py` → `test_assert_local_accepts_ipv4_loopback_range` (param `127.0.0.1`/`127.0.0.5`/`127.255.255.254`), `test_assert_local_accepts_ipv6_loopback` (`::1`, `http://[::1]:8080`), `test_assert_local_accepts_localhost_hostname`, `test_assert_local_rejects_unspecified_zero` (`0.0.0.0`), `test_assert_local_rejects_routable_ip` (`10.0.0.5`, `8.8.8.8`), `test_assert_local_rejects_non_loopback_host`, `test_assert_local_allow_remote_opt_out_bypasses_check`, `test_assert_local_makes_no_network_call`
   - Host resolution mocked — never a live DNS/socket call.
   - AC: 8. Automatable.

9. **GREEN — Implement ModelGateway shell + assert_local**
   - Prod: `harpyja/gateway/gateway.py` — `ModelGateway` shell (NO request path, NO live calls) + `assert_local(endpoint, allow_remote=False, resolver=...)`; `127.0.0.0/8` + `::1` loopback, injectable resolver, raises on non-loopback unless `allow_remote`.
   - AC: 8. Automatable.

## Group D — Locate result shape & stub tool (AC5)

10. **RED — LocateResult shapes + stub builder test**
    - Test: `harpyja/server/test_locate_tool.py` → `test_locate_stub_returns_empty_citations`, `test_locate_stub_confidence_is_low`, `test_locate_stub_tiers_run_empty_and_notes`, `test_locate_stub_accepts_arbitrary_args_no_exception`, `test_locateresult_shape_matches_spec_fields`
    - Stub returns `LocateResult(citations=[], confidence="low", tiers_run=[], notes="wave-0 stub: no retrieval")`; field names match SPEC §2.1 verbatim.
    - AC: 5. Automatable.

11. **GREEN — Implement result dataclasses + stub locate handler**
    - Prod: `harpyja/server/types.py` (`CodeSpan`, `Citation(CodeSpan)`, `LocateRequest`, `LocateResult` per SPEC §2.1); `harpyja/server/tools.py` (`locate_stub(...) -> LocateResult`).
    - AC: 5. Automatable.

## Group E — FastMCP server, transports, registration (AC3, AC4, AC9)

12. **RED — App construction + tool registration test**
    - Test: `harpyja/server/test_app.py` → `test_build_app_registers_harpyja_locate`, `test_build_app_locate_tool_call_returns_stub`, `test_build_app_http_defaults_to_loopback_host`
    - In-memory FastMCP client / registry introspection — no process spawn.
    - AC: 3, 4. Automatable.

13. **GREEN — Implement FastMCP app + register harpyja_locate**
    - Prod: `harpyja/server/app.py` — `build_app()` registers `harpyja_locate` (`query` req, `repo_path` req, `mode="auto"`, `max_results=8`, `language_hint=None`) → `locate_stub`; `run_stdio(app)`, `run_http(app, host="127.0.0.1", port=...)`.
    - AC: 3, 4. Automatable.

14. **RED — stdio stdout-hygiene / stderr-logging test**
    - Test: `harpyja/server/test_stdio_hygiene.py` → `test_configure_logging_uses_stderr_handler`, `test_configure_logging_no_stdout_handler`, `test_stdio_session_stdout_only_mcp_frames`
    - Subprocess portion `@pytest.mark.integration` (skippable); handler-config assertions always run.
    - AC: 9. Automatable.

15. **GREEN — Implement stderr-only logging config**
    - Prod: `harpyja/server/logging_config.py` — `configure_logging()` installs a stderr `StreamHandler`, no stdout handler; called before stdio transport starts.
    - AC: 9. Automatable.

## Group F — CLI: serve + doctor (AC3, AC4, AC10)

16. **RED — CLI serve wiring test**
    - Test: `harpyja/test_cli.py` → `test_cli_serve_stdio_invokes_stdio_transport`, `test_cli_serve_http_binds_loopback_by_default`, `test_cli_serve_http_port_passed_through`, `test_cli_serve_http_non_loopback_requires_opt_out`
    - Monkeypatch `run_stdio`/`run_http` — no real server starts.
    - AC: 3, 4. Automatable.

17. **GREEN — Implement CLI `serve`**
    - Prod: `harpyja/cli.py` — `serve` subcommand (`--stdio`, `--http`, `--host` default `127.0.0.1`, `--port`, `--allow-remote-bind`) → `build_app` + runners; `[project.scripts] harpyja = "harpyja.cli:main"`.
    - AC: 3, 4. Automatable.

18. **RED — `harpyja doctor` test**
    - Test: `harpyja/test_doctor.py` → `test_doctor_reports_rg_presence`, `test_doctor_reports_deno_presence`, `test_doctor_reports_rg_absent`, `test_doctor_reports_endpoint_url`, `test_doctor_air_gap_pass_for_loopback_endpoint`, `test_doctor_air_gap_fail_for_remote_endpoint`, `test_doctor_makes_no_endpoint_call`
    - Monkeypatch `shutil.which`, patch `assert_local`, assert no HTTP client call.
    - AC: 10. Automatable.

19. **GREEN — Implement `harpyja doctor`**
    - Prod: `harpyja/cli.py` (`doctor` subcommand) + `harpyja/config/doctor.py` (`run_doctor(settings) -> DoctorReport`): `shutil.which("rg")`/`which("deno")`, endpoint URL from settings, `assert_local` for air-gap status — no network call.
    - AC: 10. Automatable.

## Group G — Registration recipes (AC11, AC12) — MANUAL

20. **MANUAL — Add verified registration recipes**
    - Prod: `docs/registration/.mcp.json` (Claude Code), `docs/registration/codex-config.toml` (Codex), `docs/registration/README.md` (manual verification steps).
    - Manual verify per AC11/12: launch from each host → handshake → `harpyja_locate` listed → stub over stdio. **Not pytest-automatable.**
    - AC: 11, 12. Manual.

21. **REFACTOR — Final gate**
    - Run full `ruff check` + `pytest` (with/without `integration` marker); consolidate shared fixtures into a `conftest.py` next to `harpyja/`.
    - AC: 1 (regression gate). Automatable. _Delegate: codex._

## Risks & mitigations

- **FastMCP introspection / in-memory client API may differ** → in step 12 use FastMCP's in-memory client if available, else assert against the registered-tool map; keep transport runners thin and monkeypatchable.
- **stdout-purity hard to assert without a real session** → split AC9 into always-on handler-config assertions + a `@pytest.mark.integration` subprocess test, skipped where the event loop can't run.
- **pytest collecting co-located `test_*.py` (no `tests/` root)** → set `python_files`/`testpaths`/`norecursedirs` explicitly in `[tool.pytest.ini_options]` in step 2.
