# Architecture

See `ARCHITECTURE.md` (repo root) for the full design and `SPEC.md` for interface contracts. This file is the speccraft-facing summary.

## Layering (packages)

1. `harpyja/server/` — FastMCP app, tool registration, transports (stdio + HTTP). No business logic.
2. `harpyja/orchestrator/` — router, query classifier, verification gate, citation formatter. Owns per-request state.
3. `harpyja/index/` — file walker, ranked JSONL manifest, incremental hashing.
   Live as of Wave 1: `walk`/`ignore` (pathspec, no `git`), `classify`, `prior`,
   `hash`, `manifest` (atomic same-dir temp + `os.replace`, per-file `degraded`
   field as of Wave 2), `artifacts` (in-repo `.harpyja/` or XDG-cache fallback),
   `indexer` (`(mtime,size)` gate + prune + `--rehash`; Wave 2 also extracts
   symbols on the change-of-record gate and forces a full symbol rebuild on a
   cache integrity / engine-identity mismatch).
4. `harpyja/symbols/` — tree-sitter engines + ripgrep engine behind one `CodeSpan`
   interface (Tier 0). Live as of Wave 2: `RipgrepEngine` (literal `--fixed-strings`,
   bounded); `extract` (defs-only by syntactic form → `SymbolRecord` / `ExtractResult`
   for all 10 grammars — Python, Go, Rust, Java, C#, JavaScript, TypeScript, TSX, C,
   C++; minimal closed kind vocabularies, nested **types** extracted with immediate
   `parent` but function-body-local defs dropped); `symbols_io` (byte-reproducible
   `symbols.jsonl` + self-verifying `symbols.meta.json` sidecar; records-first/meta-last
   `os.replace`); `engine_identity` (runtime + a per-grammar slot via `_GRAMMAR_SLOTS`,
   sentinel-safe cache key; `typescript`/`tsx` coupled under one `tree-sitter-typescript`
   version); `symbol_locator` (`SymbolEngine` — exact case-sensitive name + `.`/`::`
   method addressing, behind the `Locator` protocol). Routing is held in lockstep with
   extraction: `classify.KNOWN_LANGUAGES == indexer.SYMBOL_LANGUAGES`
   (`index/test_routing.py`), so a language is never routed ahead of its rules.
   Remaining symbol follow-up: **Wave-2.1 substring/fuzzy matching**.
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
  index → (ripgrep + symbols) → citation formatter behind `harpyja_locate`. As of
  Wave 2 it is symbol-aware: a query naming a symbol surfaces its **definition** above
  its call sites via a formatter definition boost, composed from the ripgrep and
  symbol `Locator`s without branching; a no-symbol-match query degrades byte-identically
  to the Wave-1 ripgrep-only result. `rg` on `PATH` is a hard precondition for
  search/locate only (not `index`); a missing/erroring parser, by contrast, degrades
  gracefully (`grammar-missing` / `parse-error`) — symbols are an enhancement, not a
  precondition. See history.md 2026-06-26.

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
