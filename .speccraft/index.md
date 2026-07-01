# Harpyja

A read-only, offline MCP server that turns a natural-language query into exact `file:line` citations across large/legacy/air-gapped codebases.

## Stack

- Python 3.12+
- FastMCP (MCP server; stdio + streamable HTTP)
- Tree-sitter (symbol layer: Go, Rust, Python, JS/TS, C#, Java, C/C++) + ripgrep fallback
- Microsoft FastContext (Tier 1 "Scout", pinned dependency)
- DSPy `dspy.RLM` over Deno/Pyodide WASM sandbox (Tier 2 "Deep")
- Local OpenAI-compatible model endpoint: llama.cpp (`llama-server`) or Ollama (4B-class quantized, 8 GB GPU profile — ⚠️ **8 GB / Q4 floor NOT validated**: the recommended Q4_K_M Scout model is non-functional on real repos; the working config is Q8 (~2× memory, OOMs auto on 16 GB) — re-characterize the floor, see ARCHITECTURE.md "Footprint")
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

- 2026-07-01 — **Spec 0017 (gateway_http_timeout) shipped — the B3 fix from 0015** (specs/0017-gateway-http-timeout/): closed **B3** (0015 `live-run-findings.md`) as a pure reliability/plumbing fix — the Model Gateway's outbound `urlopen(req)` had **no timeout** (default `None` → block forever), so a stalled/torn-down local Ollama connection wedged the whole `mode=auto` run indefinitely (2.5 h at 0% CPU, `caffeinate` on) — why no full OQ2 sweep ever finished. Six durable points. **(1)** *A call that can hang forever can never degrade* — the fix is to make the un-raisable **raisable**, NOT add a new degrade path: the gate ALREADY wraps the judge in `except Exception → GateOutcome(failed=True)`, but it never fired because an un-timed-out `urlopen` raises nothing; a finite `urlopen(req, timeout=timeout_s)` lets the *existing* catch fire. **(2)** The finite floor lives on the **constructed object's own field default** (`ModelGateway.timeout_s: float = 120.0`, AC2), not only `Settings.lm_http_timeout_s` (AC1) — else direct/unwired constructions fall back to unbounded `None`. **(3)** Seam-preserving (D3): bound via `functools.partial(_default_transport, timeout_s=…)` **only when `transport is None`**; the injectable `Transport` signature is untouched. **(4)** Timeout-degrade **visibility** (D4) extends the 0014 convention to the gate as a **LOG signal** (distinct timeout-naming WARNING on `TimeoutError`/`socket.timeout`/`URLError`), NOT a schema field. **(5)** Per-socket-op, not total-deadline honesty; default `120.0 s` decoupled from `deep_wall_clock_ms` (D1), no per-request layer (D2); air-gap `assert_local`-first preserved (AC9). **(6)** Both wiring sites thread `timeout_s=settings.lm_http_timeout_s` — `orchestrator/wiring.py` (hang path) + `scout/wiring.py` (defense-in-depth). **725 unit pass** (+14), ruff clean; +1 integration. Load-bearing proof **AC7**: a deterministic loopback accept-then-withhold-bytes server raises in **<1 s** (real stall bounded, not a fake); AC11 live-Ollama smoke passed (6.15 s, skip-not-fail, NOT the stall proof). B1(0016)+B3(0017) fixed; **B2** (gate false-escalation) + **OQ2 re-run** still open; also total-deadline defense, Deep dspy/litellm timeout, retry/backoff, Wave-2.1 substring/fuzzy.
- 2026-07-01 — **Spec 0016 (scout_model) shipped — the B1 serving/plumbing fix from 0015** (specs/0016-scout-model/): closed **B1** (0015 `live-run-findings.md` D1) as a pure serving/plumbing fix — two `Settings` default VALUES flip to served Ollama tags + two CLI override flags, no tier/classifier/citation/gate-algorithm change. **(1)** `scout_model` flips from the UNSERVED `mitkox/…RL-Q4_K_M` (HTTP 404 every call → fully-degraded run for a non-model reason) to the served `hf.co/dstolf/FastContext-1.0-4B-RL-Q8_0-GGUF:latest`; `lm_model` flips from the llama.cpp placeholder `"local"` to the served `hf.co/Qwen/Qwen3-8B-GGUF:latest` — an unserved default is an infra defect, not a config preference (no-false-capability applied to model tags). **(2)** Stated cross-subsystem coupling: `verify_method="scout_model"` means `scout_model` also backs the Verification Gate, so the flip changes *which served model the gate calls* (broken→served plumbing) — DISTINCT from the still-open **B2** gate-*judging-logic* problem. **(3)** The `lm_model` flip is intentionally GLOBAL (D2 — hits MCP `mode=auto`, not just eval CLI); the llama.cpp regression (`"local"` benign there, Ollama Qwen tag won't resolve) is named + accepted, mitigated by unchanged override precedence; Qwen default provisional ("for now"). **(4)** `run`/`sweep` gain `--scout-model` (the missing escape hatch) + canonical `--deep-model`; `--lm-model` kept as a DEPRECATED alias on a distinct argparse dest, reconciled in `_settings_from_args` (`deep = args.deep_model or args.lm_model`) so canonical wins regardless of CLI order (D1); frozen-`replace` base-not-mutated preserved. **711 unit pass**, ruff clean; +11 unit (AC6 field-default **introspection** drift guard — never a grep; both-orders D1 test; `--help` introspection) +1 integration `/api/tags` **positive**-membership three-way skip-not-fail guard (AC7) — validated live (Q8 default IS served). Follow-ups carried: **B2** (gate false-escalation), **B3** (gateway `urlopen` no-timeout), the **OQ2 re-run** (fresh spec after B1/B2/B3), permanent Deep model, Q8 footprint floor, Wave-2.1 substring/fuzzy.
- 2026-07-01 — **Spec 0015 (OQ2) CLOSED — run FAILED; implementation reverted, one bug fix (B0) salvaged** (specs/0015-oq2/): the live `mode=auto` 12-repo OQ2 sweep could not complete. AC1 partially proven (3-case smoke runs to completion, no crash — 0014 Deep fix holds) but the full N=50 run never finished. Three blockers surfaced (→ new specs): **B1** default `scout_model` is an unserved model (`mitkox/…RL-Q4_K_M` → HTTP 404) with no `--scout-model` CLI override; **B2** the verification gate reuses the FastContext citation-*finder* model as a relevance *judge* → rejects CORRECT citations (astropy-12907 cited the right file, got `gate-low-confidence`; `_parse_score` grabs the first number in the reply) — this IS the AC4 gate-false-escalation phenomenon; **B3** the model gateway `urlopen` has no HTTP timeout → a stalled/torn-down Ollama connection wedges the run indefinitely (2.5 h, 0% CPU, `caffeinate` on) — the reason no full run completed. **Salvaged:** B0 provision worktree-path fix (`cmd_provision` `Path(args.work_dir).resolve()`) + regression test — a relative `--work-dir` made `git worktree add` create trees under the clone while the fixture recorded a divergent `wt.resolve()` → every path 404'd. All OQ2 measurement machinery (typed-outcome enum, per-point degrade gate, schema bump `0013/1→0014/1`, sweep provenance, `run_oq2_sweep`) was **reverted to HEAD** — not worth carrying un-exercised. Verified-not-bugs (don't re-chase): `parse_final_answer`, suffix-recovery wiring. Findings in `live-run-findings.md` + `changelog.md` seed the B1/B2/B3 fix specs; a fresh spec re-attempts OQ2 once the stack runs to completion. **700 unit pass** after revert, ruff clean.
