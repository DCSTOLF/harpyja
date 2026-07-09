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

None

## Recent decisions (last 3)

- 2026-07-09 — **Spec 0035 (grep-scope-markers) SHIPPED the honest-affordance SUT fix before the eval set — MECHANICALLY PROVEN, behavioral effect UNMEASURED BY DESIGN. Three explorer/Deep wrappers now separate three states that all collapsed to a silent `[]`: a searchable-but-empty scope stays plain `[]` (honest-empty, never blurred); an UNSEARCHABLE (nonexistent) scope returns a typed, model/RLM-visible, non-terminal marker STRING (`grep-scope-not-found` / `ls-path-not-found` / `search-scope-not-found`, `<id>: '<scope>'`) fired BEFORE delegation (a nonexistent cwd crashes the engine's subprocess); an existing FILE scope DELEGATES to the one `RipgrepEngine` for REAL repo-relative matches — the `grep` `is_dir()` redirect guard DELETED, converging explorer `grep` == Deep `search` == one engine contract (the 0033 astropy right-file grep is now a POSITIVE fixture, not a redirect). The review round DISCOVERED a distinct, worse defect than the spec's claimed silent-`[]`: Deep's nonexistent scope was an UNCAUGHT `FileNotFoundError` (no typed catch on `host_tools.search`/`RlmBackend.run`) — a graceful-degradation guardrail violation, FIXED here at guardrail altitude (`_charge()` still first). The marker-return route (NOT a raise) is deliberate twice: the 0029 catch would mislabel a navigation mistake with a `tool-call-degraded:execution-error:` prefix AND skip `note_navigation`, defeating loop detection — the marker string needs ZERO `explorer_loop.py` changes. AC6 LIVE was NOT-EXERCISED (honestly): the run's model used only valid scopes (bucket wrong-file, clean terminal submit), the 0023 NOT-EXERCISED fallback printed — but the harness fix proved itself IN THE SAME RUN: the verifier artifact PERSISTED durably at `eval_work/live_artifacts/bad_scope_marker/20260709T183038Z-20622/`, the FIRST live run answerable later without a re-run. Whether markers/delegation change model behavior or bucket distributions is the EVAL SET's paired measurement — "works mechanically" must NEVER blur into "the fix works." Instrument+affordance stack 0031→0032→0033→0034→0035 COMPLETE; the eval set is the named next spec. 13/13 tasks, all 8 ACs MET at stated strength, 1193 units, ruff 36 = baseline (zero-new)** (specs/0035-grep-scope-markers/)
- 2026-07-09 — **Spec 0034 (reasoning-observability) CLOSED the 0031–0033 measurement blind spot: the reasoning `qwen3:14b` on THIS Ollama generates by default — silently DROPPED by the gateway and eating the `explorer_max_tokens=2048` cap since 0028 — is now surfaced ADDITIVELY (`ModelGateway.complete_with_tools` returns `reasoning` + `usage.completion_tokens`; absent→None, present-empty→""/None) and recorded per-turn in the DURABLE trajectory artifact via a NEW backend accumulator (the DECIDED seam: `wrapped_model_call` grew from the `_last_served_model` last-write scalar into a per-turn `{reasoning_chars, completion_tokens, finish_reason}` list, reset per run, threaded into `build_trajectory_record` AND `run_verified_case`'s written artifact — the ONLY seam that sees the finish="length" FINAL turn that never enters `model_turns`, so a truncated-by-reasoning turn is distinguishable IN THE RECORD from content-truncated and clean). One canonical `derive_think_mode` enum (native wins on double-set); `VERIFIER_SCHEMA_VERSION 0033/1→0034/1` behind the gate, reasoning fields OPTIONAL, legacy 0031/1+0033/1 still validate. The knob `Settings.explorer_think: bool | None = None` is tri-state DEFAULT-OMIT ⇒ outbound request BYTE-IDENTICAL to pre-0034 (pinned on the request body: params=={"max_tokens":2048}); coexists with `explorer_enable_thinking`. AC5 EXERCISED LIVE (qwen3:14b/Ollama, precondition-probed): per-turn reasoning_chars=[2086,794,1325,2676,1260,1328,1795] — ~11K chars/run of previously invisible reasoning now durable. Instrument stack 0031→0032→0033→0034 COMPLETE for the eval set; spec 0035 (silent-`[]` grep markers) filed as the next SUT fix BEFORE the eval set. 23/23 tasks, all 6 ACs MET, 1175 units, ruff 34 = baseline (zero-new)** (specs/0034-reasoning-observability/)
- 2026-07-09 — **Spec 0033 (scoped-grep-paths) CLOSED the 0032 measurement-integrity blocker: scoped grep now returns REPO-RELATIVE paths, fixed at the ONE `RipgrepEngine` seam (`search(repo_root=)`, mechanism-b parse-side re-prefix — the `rg` invocation byte-identical for directory scopes so AC1's ordering/ignore-file pin holds trivially; the FILE-scope `symbols` degraded-fallback runs from the parent dir with the filename as an rg arg, net-fixing a pre-existing NotADirectoryError crash), the fix INHERITED by every engine consumer (explorer `grep`, Deep `search`, `symbols` fallback all supply `repo_root=repo_path` as DATA — never a per-caller re-prefix); found-then-dropped is now a first-class recorded fact — `submit_citations` returns `SubmitResult(spans, submitted, surviving)` threaded LoopResult→backend→`build_trajectory_record`→PERSISTED artifact, `VERIFIER_SCHEMA_VERSION 0031/1→0033/1` behind a version GATE so legacy artifacts still validate; the drop CLOSED LIVE on real astropy (submitted=1, surviving=1). ADJACENT think-experiment (post-impl, N=2) delivered a first-ever right-file + first-ever `symbols` invocation on astropy — PROOF-OF-MECHANISM (the 0030 tool-chain works when engaged) with the CAUSAL CLAIM WITHHELD (both tested knobs measured inert, verdict: variance, not "thinking helps"), and surfaced the HIDDEN-VARIABLE finding that qwen3:14b THINKS BY DEFAULT and the gateway has silently DROPPED `reasoning` + eaten the 2048 cap since 0028 → every 0031–0033 baseline is measured-under-invisible-truncation-risk. 15/15 tasks, all 8 ACs MET, 1140 units, ruff 34 vs 36 (net -2)** (specs/0033-scoped-grep-paths/)
