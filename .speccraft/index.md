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

- 2026-06-27 — **Wave 4 Deep (Tier 2) shipped — dspy.RLM + sandbox** (specs/0006-wave-4-deep-rlm/): `mode=deep`→Tier 2 (`tiers_run=[0,2]`, `source_tier=2`); `auto`/`fast` unchanged. **Layered explorer-loop bounds** — externally-enforced tool-calls/tokens/`deep_wall_clock_ms` (the latter a hard-kill via an out-of-band host-terminable subprocess; a same-thread deadline can't preempt a WASM busy loop) are load-bearing; host-mediated depth/subqueries carry recorded residual risk, transitively contained by the trio. **Typed-failure-only degrade** to Scout (`deep-degraded:<cause>`); weak/zero output stays an honest Tier-2 result (no ungated escalation); budget truncation → stable non-degrade `deep-truncated:<bound>`. **RlmBackend air-gap deviation**: `dspy.RLM` owns its own LM, so air-gap is `gateway.assert_local` on the endpoint **before** building the LM, proven by a network-deny test. Sandbox isolation (ambient FS + non-loopback egress denied) verified-by-test, residual risk recorded; `DeepEngine` dual surface (`.search` Locator + `run()→(citations,truncated_bound)`); lockstep guard inverted atomically; Deep **not cached**. Verified live (dspy 3.2.1 + Deno 2.9 + Ollama + rg 15.1). Open: Verification Gate + auto-escalation (Wave 5); FastContext package (Scout); Wave-2.1 substring/fuzzy.
- 2026-06-27 — **Wave 3 Scout (Tier 1) + Model Gateway request path shipped** (specs/0005-wave-3-scout/): first model-backed tier, explicit-opt-in (`mode=auto` byte-identical to Wave 2 with **zero** Gateway calls; `mode=fast`→Scout). **Four-state degradation floor** (model-down→Tier-0 `degraded`+`scout-degraded:<cause>` note; Tier-0-honestly-empty→`+no-matches`; `rg`-missing→`RipgrepMissingError` propagates loudly; non-loopback→`AirGapError` floor) with **seed-before-backend ordering** making the loud case win by construction. `ModelGateway.complete()` asserts resolution-time air-gap (reused Wave-0 `assert_local`/`AirGapError`) before an injected transport. `ScoutBackend` Protocol + `FastContextBackend` (injected client, no hard import) keep FastContext swappable; Scout is **not cached**.
- 2026-06-26 — **Wave 2 symbol layer completed (all 10 grammars)** (specs/0004-symbol-layer-remaining-grammars/): added Rust, Java, C#, JS, TS, TSX, C, C++ behind the **unchanged** `SymbolEngine`/`Locator`/formatter (AC15 by construction); **no-silent-coverage lockstep invariant** `classify.KNOWN_LANGUAGES == indexer.SYMBOL_LANGUAGES` (`index/test_routing.py`) — routing + identity slot + extraction ship together (fixed a latent Wave-1 silent-zero violation); `.h`→C is a **scoped** guarantee (degrade only on ERROR/MISSING — tree-sitter-c tolerates a bare `class {}`); `engine_identity` per-grammar `_GRAMMAR_SLOTS` with `typescript`/`tsx` coupled. Sole open follow-up: **Wave-2.1 substring/fuzzy matching**.
