---
id: "0001"
title: "Wave 0 — Foundations"
status: closed
created: 2026-06-26
authors: [claude]
packages: ["harpyja"]
related-specs: []
---

# Spec 0001 — Wave 0 — Foundations

## Why

Everything in Harpyja (Waves 1–6) sits on top of a working agent↔server loop, a
package skeleton, layered config, and a gateway shell. Wave 0 proves that loop
end-to-end *before* any retrieval logic exists, so the riskiest integration
surface — MCP registration, which differs subtly between Claude Code and Codex —
is pinned early rather than discovered late. The product is intentionally
useless at retrieval here; its only job is to register, handshake, and return a
contract-valid stub. Getting the skeleton, packaging, and config precedence
right now is what lets later waves be purely additive.

## What

A skeleton MCP server, its packaging, and its config/gateway shells.

- **Packaging:** `uv` / `pyproject.toml` with `requires-python = ">=3.12"`, and
  `ruff` (lint) and `pytest` (test) wired and passing on the skeleton.
- **Package skeleton** per the Architecture layout: `harpyja/{server, orchestrator,
  index, symbols, scout, deep, gateway, config}/` plus `harpyja/cli.py`.
- **Config subsystem:** layered settings with precedence
  profile defaults → `harpyja.toml` → `HARPYJA_*` env → per-request override
  (lowest to highest). `harpyja.toml` is discovered in order: an explicit
  `--config <path>`, else `harpyja.toml` in the current working directory, else
  the repo root.
- **FastMCP server:** `harpyja serve --stdio` **and** `harpyja serve --http`,
  both registering `harpyja_locate`, which returns a **schema-valid empty**
  result — empty `citations` list + a `confidence` flag — per the
  `LocateResult` shape in `SPEC.md §2.1`. No retrieval.
  - **Inbound air-gap:** `--http` binds **loopback only** (`127.0.0.1`) by
    default; binding any non-loopback interface requires an explicit opt-out.
  - **stdio hygiene:** the stdio transport keeps **stdout clean** — all logs go
    to stderr — so MCP framing is never corrupted.
- **`ModelGateway` shell** with `assert_local()` — enforces a loopback-only
  endpoint. **Loopback** is defined as `127.0.0.0/8` or `::1` (or a host that
  resolves only to those); every other address is rejected unless an explicit
  `allow_remote` opt-out is set. No live model calls in this wave.
- **`harpyja doctor`:** presence checks for `rg` and `deno` on `PATH` and the
  configured model-endpoint URL, plus a **static air-gap assertion** that runs
  the same `assert_local()` loopback check on the configured endpoint. It does
  **not** make a live call to the endpoint (deferred to Wave 3).
- **Registration recipes:** verified `.mcp.json` (Claude Code) and
  `config.toml` (Codex) snippets.

## Acceptance criteria

1. `uv sync` (or `pip install -e .`) installs the package on Python 3.12;
   `ruff check` and `pytest` both exit 0 on the skeleton.
2. All eight subpackages (`server`, `orchestrator`, `index`, `symbols`,
   `scout`, `deep`, `gateway`, `config`) and `cli.py` are importable.
3. `harpyja serve --stdio` starts a FastMCP server that completes the MCP
   handshake and lists `harpyja_locate` in its tool list.
4. `harpyja serve --http --port <p>` starts the server over streamable HTTP,
   binds to loopback (`127.0.0.1`) by default, and lists `harpyja_locate` in its
   tool list.
5. Calling `harpyja_locate` with any arguments returns a response matching the
   `LocateResult` shape in `SPEC.md §2.1` — an empty `citations` list plus a
   `confidence` flag (`high|medium|low`) — raising no exception and running no
   retrieval.
6. Config resolves with precedence profile defaults < `harpyja.toml` <
   `HARPYJA_*` env < per-request override. Verified at two levels: (a) an env
   `HARPYJA_LM_API_BASE` overrides the `harpyja.toml` value, and (b) a
   per-request value overrides the env value in the resolved settings.
7. `harpyja.toml` is discovered per the documented order — explicit
   `--config <path>` wins over a cwd `harpyja.toml`, which wins over the
   repo-root file.
8. `ModelGateway.assert_local()` passes for `127.0.0.0/8` and `::1` endpoints
   and raises for any non-loopback endpoint (e.g. `0.0.0.0`, a routable IP, or a
   non-loopback host) unless `allow_remote` is set — making no network call.
9. The stdio transport writes nothing to stdout except MCP protocol frames; all
   logs go to stderr (a logged `serve --stdio` session still completes the
   handshake and a `harpyja_locate` call cleanly).
10. `harpyja doctor` reports presence/absence of `rg` and `deno` on `PATH`, the
    configured model-endpoint URL, and air-gap status (pass/fail via the same
    loopback check as AC8), **without** making a live call to the endpoint.
11. _(manual integration check)_ From **Claude Code** (`.mcp.json`): the server
    launches, completes the MCP handshake, `harpyja_locate` appears in the tool
    list, and a call returns the schema-valid stub over stdio.
12. _(manual integration check)_ From **Codex** (`config.toml`), independently:
    the server launches, completes the MCP handshake, `harpyja_locate` appears
    in the tool list, and a call returns the schema-valid stub over stdio.

## Out of scope

- Any real retrieval, indexing, manifest, symbol, or ripgrep logic (Wave 1+).
- A working `ModelGateway` request path or any live model call (Wave 3).
- Verification gate, query classifier, escalation, and real ranking (Wave 5).
- Live model-endpoint probing inside `doctor` (Wave 3).
- Deno/Pyodide sandbox bootstrap for the Deep tier (Wave 4).
- `harpyja_read` and `harpyja_index` beyond stub registration, if registered at
  all (Wave 1).

## Open questions

_none_
