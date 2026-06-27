# Harpyja

A read-only, offline MCP server that turns a natural-language query into exact `file:line` citations across large/legacy/air-gapped codebases.

## Stack

- Python 3.12+
- FastMCP (MCP server; stdio + streamable HTTP)
- Tree-sitter (symbol layer: Go, Rust, Python, JS/TS, C#, Java, C/C++) + ripgrep fallback
- Microsoft FastContext (Tier 1 "Scout", pinned dependency)
- DSPy `dspy.RLM` over Deno/Pyodide WASM sandbox (Tier 2 "Deep")
- Local OpenAI-compatible model endpoint: llama.cpp (`llama-server`) or Ollama (4B-class quantized, 8 GB GPU profile)
- `uv` for env/deps

## Architecture in one paragraph

A FastMCP server exposes three tools (`locate` / `read` / `index`) and holds no business logic. The Orchestrator classifies each query, then runs the cheapest tier that can answer: Tier 0 (deterministic tree-sitter symbols + ripgrep), Tier 1 (Scout, a FastContext adapter), and Tier 2 (Deep, a `dspy.RLM` over bounded read-only host tools). A Verification Gate reads cited lines back and escalates on failure; a Citation Formatter merges, ranks, and clamps results. The Model Gateway is the single outbound abstraction, pointed only at localhost — the one place the air-gap guarantee is enforced. Every layer has a fallback so retrieval never goes blind.

## Hard rules (see guardrails.md)

- No network egress at runtime — model/search/parsing stay local; only the Model Gateway calls out, and only to localhost.
- Read-only — Harpyja returns citations and never edits, writes, or generates code in the target repo.
- Always degrade gracefully — no parser → ripgrep; no model → Tier 0; escalation fails → best-effort Tier 1 with a confidence flag.

## Where to look

- MCP server / transports: `harpyja/server/`
- Routing, classifier, verification gate, formatter: `harpyja/orchestrator/`
- File walker / manifest / hashing: `harpyja/index/`
- Tree-sitter + ripgrep engines (`CodeSpan`): `harpyja/symbols/`
- Tier 1 Scout (FastContext adapter): `harpyja/scout/`
- Tier 2 Deep (`dspy.RLM` + host tools): `harpyja/deep/`
- Model Gateway (llama.cpp / Ollama): `harpyja/gateway/`
- Settings / profiles: `harpyja/config/`
- CLI entrypoints (serve/index/locate/read): `harpyja/cli.py`

## Active spec

none

## Recent decisions (last 3)

- 2026-06-26 — **Wave 2 symbol layer completed (all 10 grammars)** (specs/0004-symbol-layer-remaining-grammars/): added Rust, Java, C#, JS, TS, TSX, C, C++ behind the **unchanged** `SymbolEngine`/`Locator`/formatter (AC15 by construction); **no-silent-coverage lockstep invariant** `classify.KNOWN_LANGUAGES == indexer.SYMBOL_LANGUAGES` (`index/test_routing.py`) — routing + identity slot + extraction ship together (fixed a latent Wave-1 silent-zero violation); `.h`→C is a **scoped** guarantee (degrade only on ERROR/MISSING — tree-sitter-c tolerates a bare `class {}`); `engine_identity` per-grammar `_GRAMMAR_SLOTS` with `typescript`/`tsx` coupled. Sole open follow-up: **Wave-2.1 substring/fuzzy matching**.
- 2026-06-26 — **Wave 2 symbol layer shipped** (specs/0003-wave-2-symbol-layer/): Tier-0 tree-sitter symbol layer (Python + Go, defs-only); byte-reproducible `symbols.jsonl` + self-verifying `symbols.meta.json` sidecar (engine-identity + sha256 content-digest → rebuild on any mismatch, records-first/meta-last); per-file `degraded` persisted on the manifest (total-in-index); `SymbolEngine` behind the `Locator` protocol (exact + `.`/`::` method addressing, substring deferred to Wave 2.1); formatter definition boost; air-gap audited.
- 2026-06-26 — **Wave 1 deterministic core shipped** (specs/0002-wave-1-deterministic-core/): model-free Tier-0 locator (index → ripgrep → formatter); `.gitignore` via `pathspec` (no git); two-level `(mtime,size)` incremental gate + prune + `--rehash`; `rg` hard precondition for search/locate only; `.harpyja/` derived artifacts + XDG fallback; literal-by-default search; honest hard-fail over silent empty.
