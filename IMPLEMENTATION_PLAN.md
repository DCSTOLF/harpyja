# Harpyja — Implementation Plan (Wave-Based)

Harpyja is built in **waves**. Each wave is independently shippable and testable: the product is useful at
the end of every wave, and each wave only depends on the ones before it. This lets you stop at any point with
a working locator and add capability without rework.

Contracts referenced here are defined in [`SPEC.md`](./SPEC.md); structure in
[`ARCHITECTURE.md`](./ARCHITECTURE.md).

```
Wave 0 ─ Foundations ─▶ Wave 1 ─ Deterministic core ─▶ Wave 2 ─ AST/symbols
                                                           │
        Wave 5 ─ Router+Gate ◀─ Wave 4 ─ Deep (RLM) ◀─ Wave 3 ─ Scout
                    │
                    ▶ Wave 6 ─ Hardening & release
```

Legend for each wave: **Goal** · **Deliverables** · **Acceptance** · **Risks**.

---

## Wave 0 — Foundations

**Goal.** A skeleton MCP server that Claude Code and Codex can register and call, returning a trivial result.
Prove the end-to-end loop before any retrieval logic exists.

**Deliverables**
- `uv`/`pyproject.toml` packaging, Python 3.12, lint (ruff) + test (pytest) wiring.
- Package skeleton per the Architecture layout (`server/`, `orchestrator/`, `index/`, `symbols/`, `scout/`,
  `deep/`, `gateway/`, `config/`, `cli.py`).
- `config/` settings: profile defaults → `harpyja.toml` → `HARPYJA_*` env → request. `harpyja doctor`.
- FastMCP server with `serve --stdio` and `serve --http`; registers `harpyja_locate` returning a stub.
- `ModelGateway` with `assert_local()` (no real calls yet).
- Registration docs verified against **Claude Code** (`.mcp.json`) and **Codex** (`config.toml`).

**Acceptance**
- Both agents list `harpyja_locate` and receive the stub response over stdio.
- `harpyja doctor` reports presence/absence of `rg`, `deno`, the model endpoint, and air-gap status.

**Risks.** MCP registration quirks differ slightly between Claude Code and Codex — pin both configs early.

---

## Wave 1 — Deterministic core (Indexer + ripgrep)

**Goal.** A genuinely useful locator with **no model at all**: index a repo and answer point lookups via
ripgrep. This is the floor Harpyja degrades to forever after.

**Deliverables**
- **Indexer:** gitignore-aware walker, language classification, ranked **manifest** JSONL with `prior`
  heuristic, incremental hashing. `harpyja_index` tool + CLI.
- **RipgrepEngine:** bounded regex search returning `CodeSpan`s; `search_max_files`/`search_max_matches`.
- **`harpyja_read`:** bounded snippet reads with path confinement.
- **Citation Formatter:** dedupe, merge overlapping spans, rank by `prior` + match density.
- Orchestrator v0: `mode` ignored; everything routes to ripgrep. Returns real citations.

**Acceptance**
- `locate` on a known string/symbol returns correct `file:line` with zero model calls.
- Re-indexing an unchanged repo skips unchanged files (hash check).
- Path-traversal attempts are rejected.

**Risks.** Manifest ranking quality — keep the `prior` simple and transparent; tune later with real repos.

---

## Wave 2 — AST / Tree-sitter symbol layer

**Goal.** Structural understanding for the nine target languages, with **graceful degradation** to Wave 1's
ripgrep whenever parsing isn't available.

**Deliverables**
- Tree-sitter integration (py-tree-sitter + grammar pack) for **Go, Rust, Python, JS, TS, C#, Java, C, C++**.
- **Symbol index** JSONL: definitions with kinds and spans; `symbols(path)` and `lookup(name, scope)`.
- `SymbolEngine` interface with the **non-raising degradation contract**: parse failure → ripgrep, path
  recorded in `degraded`.
- Per-language toggles in `[languages]` config.
- `harpyja_index` now reports `symbols_indexed` and `degraded`.

**Acceptance**
- Definition lookup for a known symbol in each language resolves to the correct span via AST.
- Forcing a parser failure still returns ripgrep citations and lists the file in `degraded`.
- A file in an unsupported language is searchable (ripgrep) and never errors.

**Risks.** Grammar/version drift across languages; pin grammar versions and cover each language in CI.

---

## Wave 3 — Tier 1: Scout

**Goal.** Add the fast trained explorer as the default working tier, behind a swappable adapter.

**Deliverables**
- **Model Gateway** live against **llama.cpp** and **Ollama** (OpenAI-compatible); primary/sub model config.
- **ScoutAdapter** wrapping **Microsoft FastContext** directly (pinned git dependency, not reimplemented):
  construct the FastContext agent, query in, its parallel read-only `Read`/`Glob`/`Grep` exploration runs,
  `<final_answer>` block out, parsed to `Citation`s. Seed spans from Tier 0 passed as hints. `scout_max_turns` bound.
- Orchestrator routes `mode=fast`/default point queries through Tier 0 → Tier 1.
- Adapter isolates the explorer's wire format so the engine can be replaced.

**Acceptance**
- `locate` returns Scout citations on the default profile against a mid-size repo within the turn budget.
- With the model endpoint down, Harpyja falls back to Tier 0 and flags `confidence: low` (no hard failure).
- Swapping the model in config requires no code change.

**Risks.** FastContext is new; its API/weights may shift. Pin it as a git dependency and keep the integration
entirely inside `scout/` so a moving upstream is contained. If FastContext can't run (e.g. model endpoint
down or sandbox missing), Harpyja degrades to Tier 0 — it does **not** reimplement the explorer.

---

## Wave 4 — Tier 2: Deep (RLM)

**Goal.** Add the recursive escalation engine, adopting the megacode *approach* (reimplemented, not vendored),
generalized across languages.

**Deliverables**
- **DeepLocator** constructing a **fresh `dspy.RLM` per call** (thread-safety).
- **Bounded host tools** in the sandbox: `list_manifest`, `search`, `symbols`, `read_span` — all read-only and
  bounded per SPEC.
- RLM driver prompt that emits the standard `CodeSpan` citation JSON; budgets `rlm_max_iterations`,
  `rlm_max_llm_calls`, `rlm_max_output_chars`.
- Deno/Pyodide sandbox bootstrap + `doctor` check; skip-Tier-2-gracefully path when sandbox absent.

**Acceptance**
- A broad "trace how X flows across the system" query returns coherent multi-file citations.
- Host tools cannot read outside the repo or exceed configured bounds.
- Concurrent Deep calls don't interfere (fresh instance per request verified).
- Missing Deno → Tier 2 skipped, best Tier 1/0 result returned with a flag.

**Risks.** RLM latency/cost on small local models; expose budgets and the `fast-local` profile. Sandbox setup
friction on air-gapped hosts — document the one-time Deno install.

---

## Wave 5 — Router & Verification Gate (the `auto` brain)

**Goal.** Make `mode=auto` real: classify queries, run the cheapest tier, verify, and escalate only when needed.

**Deliverables**
- **Query classifier** (`point` vs `broad`) per the SPEC heuristics; pluggable for a model-based version later.
- **Planning matrix** wired: mode × classification × index-readiness → tier sequence.
- **VerificationGate**: `judge` / `embedding` / `both`; reads cited lines, scores, sets `passed`.
- Escalation policy: empty result, gate fail, or broad classification → Tier 2. `fast` never escalates;
  `deep` skips to Tier 2.
- `confidence` derivation (high/medium/low) and `tiers_run` reporting.

**Acceptance**
- Point query resolved by Tier 0/1 does **not** invoke Tier 2 (cost stays low).
- An injected wrong Tier-1 citation scores below threshold and triggers escalation.
- Broad queries route straight to Deep; `fast` mode returns without escalating and flags low confidence when
  the gate would have failed.

**Risks.** Classifier false-negatives sending broad queries down the cheap path — bias ambiguous cases toward
escalation in `auto`; measure on a labeled query set.

---

## Wave 6 — Hardening & release

**Goal.** Make Harpyja dependable, measurable, and shippable for air-gapped enterprise use.

**Deliverables**
- **Air-gap validation:** integration test asserting zero non-loopback egress across a full `auto` run;
  `assert_local()` enforced at startup.
- **Concurrency soak:** N parallel `locate` calls; verify isolation and no shared mutable state.
- **Benchmark harness:** SWE-bench-style locate accuracy + token/latency per tier; track escalation rate and
  Tier-0 hit rate (the cost lever). Compare `fast` vs `auto` vs `deep`.
- **Observability:** structured per-tier timing/score logs under `.harpyja/` (opt-in), redaction note.
- **Packaging:** versioned release, pinned upstreams (FastContext, DSPy, grammars), `doctor` as a preflight.
- **Docs:** troubleshooting, profile tuning for 8 GB GPUs, per-agent setup recipes.

**Acceptance**
- Full air-gapped run on a proprietary-style repo with no network: passes.
- Benchmark report shows the escalation rate is sane (most point queries resolved below Tier 2) and accuracy
  meets the target on the eval set.
- Tagged release installable via `uv`/`pip`; `doctor` green on a clean air-gapped host.

**Risks.** Benchmark repos for legacy/air-gapped scenarios are scarce — assemble a representative internal set
early (Wave 1+) so tuning isn't blocked at the end.

---

## Dependency summary

| Wave | Depends on | Unlocks |
|------|-----------|---------|
| 0 Foundations | — | agent integration, config, gateway shell |
| 1 Deterministic core | 0 | working model-free locator |
| 2 AST/symbols | 1 | structural lookups + degradation |
| 3 Scout | 1, 2 | fast default tier |
| 4 Deep | 1, 2 | recursive escalation engine |
| 5 Router + Gate | 3, 4 | real `auto` mode |
| 6 Hardening | 5 | release-ready, benchmarked |

## Sequencing notes

- **Waves 3 and 4 are parallelizable** once Wave 2 lands — Scout and Deep share only the Model Gateway and
  the Symbol/ripgrep layer, both stable by then.
- **Ship early.** Wave 1 alone is a deployable deterministic locator; Wave 2 makes it good; the model tiers
  are additive. Don't block a usable release on the RLM tier.
- **Keep adapters thin.** The Scout and Deep engines sit behind the `Locator` protocol so either can be
  replaced as the FastContext and RLM ecosystems move.
