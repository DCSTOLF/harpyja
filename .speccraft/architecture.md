# Architecture

See `ARCHITECTURE.md` (repo root) for the full design and `SPEC.md` for interface contracts. This file is the speccraft-facing summary.

## Layering (packages)

1. `harpyja/server/` — FastMCP app, tool registration, transports (stdio + HTTP). No business logic.
2. `harpyja/orchestrator/` — router, query classifier, verification gate, citation formatter. Owns per-request state.
3. `harpyja/index/` — file walker, ranked JSONL manifest, incremental hashing.
4. `harpyja/symbols/` — tree-sitter engines + ripgrep engine behind one `CodeSpan` interface (Tier 0).
5. `harpyja/scout/` — FastContext adapter (Tier 1).
6. `harpyja/deep/` — `dspy.RLM` driver + bounded read-only host tools (Tier 2).
7. `harpyja/gateway/` — Model Gateway over the local OpenAI-compatible endpoint. Only outbound caller.
8. `harpyja/config/` — settings load/merge, profiles.

Tiers are adapters behind stable interfaces (`Locator` protocol) and stay stateless/swappable — the Scout engine, Deep engine, judge, and model backend can each be replaced independently.

## Key decisions

- Cheapest-tier-that-works escalation (Tier 0 → 1 → 2), gated by a read-back Verification Gate — see ARCHITECTURE.md §2.2 / §2.7.
- Fresh `dspy.RLM` instance per request (RLM is not thread-safe with a custom interpreter) — ARCHITECTURE.md §4.
- Air-gap enforced in the Model Gateway alone; all other layers are filesystem-only — ARCHITECTURE.md §4.

## Boundaries

- Inbound: MCP only (`locate` / `read` / `index`) over stdio or streamable HTTP.
- Outbound: local model endpoint via the Model Gateway (llama.cpp / Ollama), localhost only.
- Filesystem: read-only access to the target repo; manifest + symbol index are derived artifacts.
