---
spec: "0001"
closed: 2026-06-26
---

# Changelog — 0001 Wave 0 — Foundations

## What shipped vs spec

Wave 0 delivers the full agent↔server skeleton with no retrieval, exactly as
scoped: packaging, the eight-subpackage layout + `cli.py`, layered config,
the gateway air-gap shell, a stub-returning FastMCP server over stdio and HTTP,
`doctor`, and registration recipes. All 12 acceptance criteria are covered;
all 21 tasks shipped.

- **Packaging (AC1):** `pyproject.toml` — `requires-python = ">=3.12"`,
  hatchling build, ruff `E/F/I/UP/B` (line-length 100, `target-version py312`),
  pytest with `testpaths=["harpyja"]`, `python_files=test_*.py`,
  `python_functions=test_*`, and an `integration` marker. Console script
  `harpyja = harpyja.cli:main`.
- **Skeleton (AC2):** `harpyja/{server,orchestrator,index,symbols,scout,deep,
  gateway,config}/` + `cli.py`, all importable (parametrized import test).
- **Config (AC6, AC7):** `config/settings.py` — frozen `Settings` dataclass;
  precedence defaults < `harpyja.toml` < `HARPYJA_*` env < per-request override
  (`load_settings` builds the first three; `resolve_settings` applies the
  per-request layer via `dataclasses.replace`). Toml keys mirror field names;
  values are type-coerced. `config/discovery.py` — `discover_config_path`
  (explicit `--config` > cwd > repo-root).
- **Gateway / air-gap (AC8):** `gateway/gateway.py` — `ModelGateway` dataclass +
  `assert_local(endpoint, allow_remote, resolver)`. Loopback = `127.0.0.0/8`,
  `::1`, or literal `localhost`; IP and `localhost` short-circuit with no DNS;
  hostnames use an **injectable resolver**; non-loopback raises `AirGapError`
  unless `allow_remote`. No live model calls.
- **Server (AC3, AC4, AC5, AC9):** `server/types.py` (CodeSpan/Citation/
  LocateRequest/LocateResult per SPEC §2.1), `server/tools.py`
  (`locate_stub` → empty `LocateResult`, `confidence="low"`, notes
  "wave-0 stub: no retrieval"), `server/app.py` (`build_app()` registers
  `harpyja_locate`; `run_stdio`; `run_http` with `DEFAULT_HTTP_HOST=127.0.0.1`
  loopback-only inbound bind), `server/logging_config.py`
  (`configure_logging` — single stderr handler, drops any stdout handler for
  stdio framing safety).
- **CLI (AC3, AC4):** `cli.py` argparse — `serve` (`--stdio` default / `--http`,
  `--host` default `127.0.0.1`, `--port`, `--allow-remote-bind` opt-out
  enforced via `assert_local`, `--config`) and `doctor`.
- **Doctor (AC10):** `config/doctor.py` — `run_doctor(settings, which)` reports
  `rg`/`deno` presence (injectable `which`), endpoint URL, and static air-gap
  status via `assert_local`; no live endpoint call. `format_report` renders it.
- **Registration recipes (AC11, AC12):** `docs/registration/{mcp.json,
  codex-config.toml,README.md}`.

## AC coverage

| AC | Status | Where |
|----|--------|-------|
| 1 install + ruff + pytest exit 0 | covered | `pyproject.toml`, gate |
| 2 eight subpackages + cli importable | covered | `test_package_skeleton.py` |
| 3 `serve --stdio` handshake + lists tool | covered | `test_stdio_hygiene.py` (integration) |
| 4 `serve --http` loopback bind + lists tool | covered + live-verified | `test_app.py`, lsof/curl |
| 5 `harpyja_locate` returns schema-valid empty stub | covered | `test_locate_tool.py` |
| 6 precedence defaults<toml<env<request | covered (a + b) | `test_settings.py` |
| 7 toml discovery order | covered | `test_discovery.py` |
| 8 `assert_local` loopback pass / remote raise / no network | covered | `test_gateway.py` |
| 9 stdout clean, logs to stderr | covered | `test_stdio_hygiene.py` |
| 10 `doctor` reports rg/deno/endpoint/air-gap, no live call | covered | `test_doctor.py` |
| 11 Claude Code `.mcp.json` round-trip | manual + automated proxy | `docs/registration/`, integration test |
| 12 Codex `config.toml` round-trip | manual + automated proxy | `docs/registration/`, integration test |

## Deviations from spec

- **AC4 additionally live-verified:** HTTP server confirmed bound to `127.0.0.1`
  via `lsof` and returned `406` to a plain `curl` (beyond the spec's bind
  assertion).
- **AC11/12 remain manual** (documented in `docs/registration/`), with
  `server/test_stdio_hygiene.py` — a real-subprocess stdio MCP round-trip — as
  an automated proxy.
- **Dev interpreter was Python 3.14** (satisfies `requires-python >= 3.12`);
  CI/target floor remains 3.12.

## Test / lint status

- 60 tests pass (59 unit + 1 integration `test_stdio_hygiene.py`).
- `ruff check` clean.
- TDD throughout: every RED task preceded its GREEN (see `tasks.md`).

## Files touched

- `pyproject.toml`, `README.md`
- `harpyja/cli.py`, `harpyja/__init__.py`
- `harpyja/server/{__init__.py,app.py,tools.py,types.py,logging_config.py}`
- `harpyja/server/{test_app.py,test_locate_tool.py,test_stdio_hygiene.py}`
- `harpyja/config/{__init__.py,settings.py,discovery.py,doctor.py}`
- `harpyja/config/{test_settings.py,test_discovery.py}`
- `harpyja/gateway/{__init__.py,gateway.py,test_gateway.py}`
- `harpyja/{orchestrator,index,symbols,scout,deep}/__init__.py`
- `harpyja/{test_package_skeleton.py,test_cli.py,test_doctor.py}`
- `docs/registration/{mcp.json,codex-config.toml,README.md}`
