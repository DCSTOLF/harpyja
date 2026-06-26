# Architecture

See `ARCHITECTURE.md` (repo root) for the full design and `SPEC.md` for interface contracts. This file is the speccraft-facing summary.

## Layering (packages)

1. `harpyja/server/` — FastMCP app, tool registration, transports (stdio + HTTP). No business logic.
2. `harpyja/orchestrator/` — router, query classifier, verification gate, citation formatter. Owns per-request state.
3. `harpyja/index/` — file walker, ranked JSONL manifest, incremental hashing.
   Live as of Wave 1: `walk`/`ignore` (pathspec, no `git`), `classify`, `prior`,
   `hash`, `manifest` (atomic same-dir temp + `os.replace`), `artifacts`
   (in-repo `.harpyja/` or XDG-cache fallback), `indexer` (`(mtime,size)` gate
   + prune + `--rehash`).
4. `harpyja/symbols/` — tree-sitter engines + ripgrep engine behind one `CodeSpan`
   interface (Tier 0). Live as of Wave 1: `RipgrepEngine` (literal `--fixed-strings`,
   bounded); tree-sitter engines are Wave 2.
5. `harpyja/scout/` — FastContext adapter (Tier 1).
6. `harpyja/deep/` — `dspy.RLM` driver + bounded read-only host tools (Tier 2).
7. `harpyja/gateway/` — Model Gateway over the local OpenAI-compatible endpoint. Only outbound caller.
8. `harpyja/config/` — settings load/merge, profiles.

Tiers are adapters behind stable interfaces (`Locator` protocol) and stay stateless/swappable — the Scout engine, Deep engine, judge, and model backend can each be replaced independently.

## Key decisions

- Cheapest-tier-that-works escalation (Tier 0 → 1 → 2), gated by a read-back Verification Gate — see ARCHITECTURE.md §2.2 / §2.7.
- Fresh `dspy.RLM` instance per request (RLM is not thread-safe with a custom interpreter) — ARCHITECTURE.md §4.
- Air-gap enforced in one helper, `gateway.assert_local` (loopback = `127.0.0.0/8`
  / `::1` / `localhost`), reused for both the outbound model endpoint and the
  inbound HTTP bind; all other layers are filesystem-only — ARCHITECTURE.md §4.
- Tier 0 (deterministic, model-free) is the floor every later tier is additive on:
  index → ripgrep → citation formatter behind `harpyja_locate`. `rg` on `PATH` is a
  hard precondition for search/locate only (not `index`); when absent, locate fails
  loudly (`RipgrepMissingError`) rather than returning a silent empty result — see
  history.md 2026-06-26.

## Boundaries

- Inbound: MCP only (`locate` / `read` / `index`) over stdio or streamable HTTP.
  The HTTP listener binds loopback only by default (`DEFAULT_HTTP_HOST =
  127.0.0.1`); a non-loopback bind requires an explicit `--allow-remote-bind`
  opt-out and is gated by the same `gateway.assert_local` check as the outbound
  endpoint. As of Wave 1, `harpyja_locate` (Tier-0, real retrieval),
  `harpyja_index`, and `harpyja_read` are registered; the Wave 0 `locate_stub` is removed.
- Outbound: local model endpoint via the Model Gateway (llama.cpp / Ollama), localhost only.
- Filesystem: read-only access to the target repo's **source**; manifest + symbol
  index are derived artifacts written to `<repo>/.harpyja/` (self-ignoring) or, when
  the repo is unwritable, `${XDG_CACHE_HOME:-~/.cache}/harpyja/<repo-hash>/`.
