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

- 2026-06-27 — **Wave 5 Verification Gate + Tier-0→1→2 auto-escalation shipped — `mode=auto` now climbs** (specs/0008-wave-5-verification-gate/): the Wave-0 "`auto` byte-identical / zero model calls" lock is **deliberately retired** and replaced by an explicit AC1 contract — removed in **lockstep** (`_MODE_NO_EFFECT` + the matching lock tests in `orchestrator/test_locate.py` AND `server/test_app.py` deleted in the same change). New orchestrator path: `classify.py` (heuristic point/broad, ambiguous→point, pluggable `Classifier` seam) → `matrix.py` (`plan_ladder` = the 12-row planning matrix, the **single source of truth** that `_locate_auto` genuinely drives off — a T17 refactor caught it re-deriving routing and rewired it) → seed → Scout → **`gate.py` `VerificationGate`** → Deep. **OQ1 resolved: the gate reuses `scout_model` as the relevance judge**, routed through `ModelGateway.complete()` (the one outbound caller — **not** a parallel client) with `gateway.assert_local` before the judge as belt-and-suspenders; scoring failure → `GateOutcome.failed`, **never raises and never silently passes**. **OQ3 resolved: bounded top-N** (`verify_top_n=3`, dropped count logged) — the enabler that keeps a generative judge affordable on the hot path. Three additive `Settings` fields (`verify_method`/`verify_threshold`/`verify_top_n`); **`verify_method` rejects unshipped values loudly** via `__post_init__`→`UnsupportedVerifyMethod` (no-false-capability). Empty-case **three-way split**: typed-unavailable→degrade (`"degraded"` UNCHANGED, no climb) / honest-empty→`gate-skipped:scout-empty` seed return (no climb) / malformed≡gate-can't-score→escalate. `fast` = cost ceiling (informational gate → `gate-low-confidence`, never escalates). Confidence keyed on **terminal-tier + flags** so honest-empty never reads as `high`. Stable flag ids: `gate-low-confidence` / `gate-scoring-failed` / `gate-skipped:scout-empty`. `build_verification_gate` is the production `gate_factory`; gate **not cached**. Verified **live** (513 passed / 0 skipped, ruff clean): FastContext Scout + `scout_model` gate judge + Deep `qwen2.5-coder:3b` over Deno — a point query resolved cheap (no Tier-2), a broad query climbed to Tier-2. Open: OQ2 `verify_threshold` tuning vs eval repo; Wave-2.1 substring/fuzzy.
- 2026-06-27 — **Scout Tier-1 real default client shipped — FastContext agent** (specs/0007-fastcontext/): supplied the **real default client** for the already-shipped `FastContextBackend` seam (Wave 3 left it injected-only), so Scout drives the real Microsoft FastContext agent (`make_fastcontext_agent` — its own Read/Glob/Grep loop, **not** `dspy.RLM`) end-to-end and the Wave-3 live AC flips skip → genuine pass; seams (`ScoutBackend`/`ScoutEngine`/`Locator`/formatter) **unchanged**. `client.py::DefaultFastContextClient` — **Path A** (in-process: lazy `make_fastcontext_agent`, `trajectory_file` OUTSIDE repo, `await agent.run(..., citation=True)` bridged onto a **loop-free worker thread** so it's safe under a running MCP loop) + **Path B** (injected CLI runner, `FC_*` scoped to the child via `env=`). **AC3 relaxed conditionally (source-verified @ SHA `1522d6d6…`):** the factory is env-only and reads `FC_REASONING_EFFORT` lazily per call, so `FC_*` are injected via process env **under a module-level `threading.Lock` (not `asyncio.Lock`)** held across the **full run**, set-then-restore with unset-vs-empty — serializes Scout (accepted for single-GPU); Scout-only, never Deep. Single `gateway.assert_local` before construct/spawn (TOCTOU closed by the lock); third-party owns its model client (`rlm.py` precedent, whitelist vestigial) — network-deny test. Read-only proven by a no-repo-writes test (confinement blocked the model reading `/harpyja`). **Four-way cause taxonomy** (`fastcontext-missing`/`cli-missing` added) + deterministic Path-A→B state machine; **AC10 broadened live**: a third-party post-processing crash (FastContext's own `format_citations` `TypeError`) maps to `backend-error` → Tier-0 degrade, never a raw escape. `wiring.py::build_scout_engine` is the production `scout_factory`. Scout **not cached**. Verified live (~42s, suite **442 passed / 0 skipped**, ruff clean). Shipped as a **portable `git`-rev pin** at the SHA (the plan's local-path editable install was tested and corrected — the `third_party/mini-swe-agent` submodule is vestigial, so `git+https` installs cleanly). Open: Verification Gate + auto-escalation (Wave 5); Wave-2.1 substring/fuzzy.
- 2026-06-27 — **Wave 4 Deep (Tier 2) shipped — dspy.RLM + sandbox** (specs/0006-wave-4-deep-rlm/): `mode=deep`→Tier 2 (`tiers_run=[0,2]`, `source_tier=2`); `auto`/`fast` unchanged. **Layered explorer-loop bounds** — externally-enforced tool-calls/tokens/`deep_wall_clock_ms` (the latter a hard-kill via an out-of-band host-terminable subprocess; a same-thread deadline can't preempt a WASM busy loop) are load-bearing; host-mediated depth/subqueries carry recorded residual risk, transitively contained by the trio. **Typed-failure-only degrade** to Scout (`deep-degraded:<cause>`); weak/zero output stays an honest Tier-2 result (no ungated escalation); budget truncation → stable non-degrade `deep-truncated:<bound>`. **RlmBackend air-gap deviation**: `dspy.RLM` owns its own LM, so air-gap is `gateway.assert_local` on the endpoint **before** building the LM, proven by a network-deny test. Sandbox isolation (ambient FS + non-loopback egress denied) verified-by-test, residual risk recorded; `DeepEngine` dual surface (`.search` Locator + `run()→(citations,truncated_bound)`); lockstep guard inverted atomically; Deep **not cached**. Verified live (dspy 3.2.1 + Deno 2.9 + Ollama + rg 15.1). Open: Verification Gate + auto-escalation (Wave 5); FastContext package (Scout); Wave-2.1 substring/fuzzy.
