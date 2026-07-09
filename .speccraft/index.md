# Harpyja

A read-only, offline MCP server that turns a natural-language query into exact `file:line` citations across large/legacy/air-gapped codebases.

## Stack

- Python 3.12+
- FastMCP (MCP server; stdio + streamable HTTP)
- Tree-sitter (symbol layer: Go, Rust, Python, JS/TS, C#, Java, C/C++) + ripgrep fallback
- Tier 1 "Scout": native explorer loop (a general OpenAI-compatible tool-calling model over five read-only tools `{grep,glob,read_span,ls,symbols}`) — as of spec 0024 (+`ls` spec 0027, +`symbols` spec 0030); FastContext is FULLY REMOVED as of spec 0025 (no external finder dependency; the explorer is the sole Scout backend, running on `lm_model`)
- DSPy `dspy.RLM` over Deno/Pyodide WASM sandbox (Tier 2 "Deep")
- Local OpenAI-compatible model endpoint: llama.cpp (`llama-server`) or Ollama. As of spec 0025 the default `lm_model` (`hf.co/Qwen/Qwen3-8B-GGUF:latest`) serves BOTH the Scout explorer loop and Deep; any OpenAI-compatible tool-calling model is swappable. ⚠️ **8 GB footprint NOT validated**: an 8B-class model co-loaded with Deep + the Deno/Pyodide sandbox under `mode=auto` exceeds a small GPU — treat "8 GB" as aspirational, not a validated minimum
- `uv` for env/deps

## Architecture in one paragraph

A FastMCP server exposes three tools (`locate` / `read` / `index`) and holds no business logic. The Orchestrator classifies each query, then runs the cheapest tier that can answer: Tier 0 (deterministic tree-sitter symbols + ripgrep), Tier 1 (Scout, a native tool-calling explorer loop), and Tier 2 (Deep, a `dspy.RLM` over bounded read-only host tools). A Verification Gate reads cited lines back and escalates on failure; a Citation Formatter merges, ranks, and clamps results. The Model Gateway is the single outbound abstraction, pointed only at localhost — the one place the air-gap guarantee is enforced. Every layer has a fallback so retrieval never goes blind.

## Hard rules (see guardrails.md)

- No network egress at runtime — model/search/parsing stay local; only the Model Gateway calls out, and only to localhost.
- Read-only — Harpyja returns citations and never edits, writes, or generates code in the target repo.
- Always degrade gracefully — no parser → ripgrep; no model → Tier 0; escalation fails → best-effort Tier 1 with a confidence flag.

## Where to look

- MCP server / transports: `harpyja/server/`
- Routing, classifier, verification gate, formatter: `harpyja/orchestrator/`
- File walker / manifest / hashing: `harpyja/index/`
- Tree-sitter + ripgrep engines (`CodeSpan`): `harpyja/symbols/`
- Tier 1 Scout (native explorer loop; FastContext fully removed as of spec 0025): `harpyja/scout/`
- Tier 2 Deep (`dspy.RLM` + host tools): `harpyja/deep/`
- Model Gateway (llama.cpp / Ollama): `harpyja/gateway/`
- Settings / profiles: `harpyja/config/`
- CLI entrypoints (serve/index/locate/read): `harpyja/cli.py`

## Active spec

specs/0034-reasoning-observability/

## Recent decisions (last 3)

- 2026-07-09 — **Spec 0033 (scoped-grep-paths) CLOSED the 0032 measurement-integrity blocker: scoped grep now returns REPO-RELATIVE paths, fixed at the ONE `RipgrepEngine` seam (`search(repo_root=)`, mechanism-b parse-side re-prefix — the `rg` invocation byte-identical for directory scopes so AC1's ordering/ignore-file pin holds trivially; the FILE-scope `symbols` degraded-fallback runs from the parent dir with the filename as an rg arg, net-fixing a pre-existing NotADirectoryError crash), the fix INHERITED by every engine consumer (explorer `grep`, Deep `search`, `symbols` fallback all supply `repo_root=repo_path` as DATA — never a per-caller re-prefix); found-then-dropped is now a first-class recorded fact — `submit_citations` returns `SubmitResult(spans, submitted, surviving)` threaded LoopResult→backend→`build_trajectory_record`→PERSISTED artifact, `VERIFIER_SCHEMA_VERSION 0031/1→0033/1` behind a version GATE so legacy artifacts still validate; the drop CLOSED LIVE on real astropy (submitted=1, surviving=1). ADJACENT think-experiment (post-impl, N=2) delivered a first-ever right-file + first-ever `symbols` invocation on astropy — PROOF-OF-MECHANISM (the 0030 tool-chain works when engaged) with the CAUSAL CLAIM WITHHELD (both tested knobs measured inert, verdict: variance, not "thinking helps"), and surfaced the HIDDEN-VARIABLE finding that qwen3:14b THINKS BY DEFAULT and the gateway has silently DROPPED `reasoning` + eaten the 2048 cap since 0028 → every 0031–0033 baseline is measured-under-invisible-truncation-risk. 15/15 tasks, all 8 ACs MET, 1140 units, ruff 34 vs 36 (net -2)** (specs/0033-scoped-grep-paths/)
- 2026-07-08 — **Spec 0032 (trajectory-parser) CLOSED the 0031 T20 blocker: dedup'd the tool-call-name parser to ONE strict source of truth — `build_trajectory_record` no longer carries its inline silent-skip parse, it delegates to the canonical `extract_tool_names`, and the strict `tool-names-unextractable` failure now surfaces on the LIVE path as DATA (a NON-RAISING additive `tool_names_failure: str | None` record key, `tool_names_invoked=[]` on a nameless call, never a partial list) so ExplorerBackend's mid-loop control flow is byte-unchanged. OQ2 audited twice: tool-names was the SOLE duplicated parse (identity/tiers_run/bucket each single-sourced) — no parallel spec needed, locked by an `inspect.getsource` symbol-audit test. AC6 RE-VERIFIED LIVE on Ollama qwen3:14b: astropy EXACT field-by-field match to the 0031 reference (PASSED/empty/[ls,grep,submit_citations]/symbols-not-invoked), django PASSED/correct (cite 693 inside gold 689–695, genuine ground-truth overlap; first live confirmation of the 0029 answer-all-N fix). 6/6 tasks, 1111 units, ruff zero-new. BUT the instrument doing its job surfaced a NAMED NEXT BLOCKER — a scoped-grep path-shape defect that FLIPS a measured bucket: astropy's "empty" matches 0031 at the fact level but by a DIFFERENT mechanism (found-then-dropped, not found-nothing), because scoped grep returns scope-relative paths that fail repo-confine at normalization** (specs/0032-trajectory-parser/)
- 2026-07-08 — **Spec 0031 (live) built the trajectory-verified live-measurement INSTRUMENT — a pure read-only postflight verifier (`live_verifier.py`) that proves the FOUR FACTS a valid live run must show (model identity / model invoked / tools-called-by-name / terminal bucket) or FAILS with exactly one of SIX enumerated, fixed-precedence codes; plus the read-only capture seams that make those facts recoverable (gateway surfaces `response['model']`; `ExplorerBackend.last_trajectory` via `build_trajectory_record`); plus the 0029 committed-test reconciliation (`_MODEL_OVERRIDE_REASON`) and the "trajectory-verified measurement" convention binding all future live specs. VERIFIER + SEAMS UNIT-COMPLETE (26 verifier tests + gateway/backend seam tests, AC1–AC5/AC7), but AC6 proof-of-instrument is a HOLD: `run_verified_case` shipped a STUB and the 0030 astropy/django live re-run (the symbols-invocation resolution) is the operator's deliverable, gated by `verifier_preflight`, skip-clean on an absent stack.** (specs/0031-live/)
