# Harpyja — Architecture

This document describes how Harpyja is structured, how a request flows through it, and why the major
decisions are what they are. For exact interfaces and data shapes, see [`SPEC.md`](./SPEC.md). For build
sequencing, see [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md).

## 1. Design goals

1. **Precision over recall.** The output is `file:line` citations that an agent can act on directly. A short,
   correct answer beats a long, plausible one.
2. **Cheapest tier that works.** Spend deterministic compute first, a small trained model next, and a
   recursive model only when the query genuinely needs it.
3. **Offline and air-gapped by construction.** No network egress at runtime. Model, search, and parsing are
   all local. Proprietary code never leaves the box.
4. **Small footprint.** Default profile runs a 4B-class quantized model on an 8 GB GPU (CPU fallback).
5. **Agent-agnostic.** Pure MCP. Claude Code and Codex are first-class; anything that speaks MCP works.
6. **Graceful degradation.** Every layer has a fallback. No parser → ripgrep. No model → deterministic tier.
   Escalation failure → return best-effort tier-1 result with a confidence flag.

## 2. Component map

```
┌──────────────────────────────────────────────────────────────────────────┐
│                            MCP Server (FastMCP)                            │
│        stdio  |  streamable HTTP        tools: locate / read / index       │
└───────────────┬──────────────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                              Orchestrator                                  │
│   query classification · tier routing · verification gate · merge/rank     │
└───┬───────────────┬───────────────────┬───────────────────┬───────────────┘
    │               │                   │                   │
    ▼               ▼                   ▼                   ▼
┌────────┐   ┌──────────────┐   ┌───────────────┐   ┌──────────────────┐
│Indexer │   │ Symbol Layer │   │ Tier 1: Scout │   │ Tier 2: Deep     │
│        │   │ (Tree-sitter)│   │ (FastContext- │   │ (dspy.RLM over   │
│manifest│   │  + ripgrep   │   │  style agent) │   │  bounded tools)  │
│ (JSONL)│   │  fallback    │   │               │   │                  │
└────────┘   └──────┬───────┘   └───────┬───────┘   └────────┬─────────┘
                    │                   │                    │
                    └─────────┬─────────┴────────────────────┘
                              ▼
                    ┌───────────────────┐
                    │  Model Gateway    │  OpenAI-compatible
                    │ (llama.cpp/Ollama)│  primary + sub model
                    └───────────────────┘
```

### 2.1 MCP Server
Thin transport boundary built on **FastMCP** (Python MCP SDK). Registers the three tools, validates inputs,
streams progress, and converts internal results into MCP responses. Supports **stdio** (local agents) and
**streamable HTTP** (shared/containerized). Holds no business logic.

### 2.2 Orchestrator (Router)
The brain. For each `locate` call it:
1. **Classifies the query** — point lookup (`where is X`) vs. broad/trace/audit (`how does X flow`, `find all Y`).
2. **Selects a tier plan** based on classification, requested `mode`, and index availability.
3. **Runs Tier 0** (deterministic) to seed candidates when the query references a concrete symbol.
4. **Runs Tier 1 (Scout)** as the default working tier.
5. **Applies the Verification Gate.** Reads cited lines back; scores relevance.
6. **Escalates to Tier 2 (Deep)** only on gate failure, broad classification, or `mode=deep`.
7. **Merges, dedupes, ranks**, and returns the top `max_results` citations with rationales and a confidence flag.

The Orchestrator owns all per-request state so the tiers stay stateless and swappable.

### 2.3 Indexer
Walks the repo (respecting `.gitignore` and a Harpyja ignore file), classifies each file by language, and
writes a **ranked manifest** as JSONL: path, language, size, mtime/hash, and a relevance prior (path
heuristics + size). The manifest is the shared map every tier reads from instead of scanning the tree blind.
Indexing is incremental: unchanged files (by hash) are skipped on refresh.

### 2.4 Symbol Layer (Tier 0)
Two engines behind one interface:
- **AST engine** — Tree-sitter parsers for Go, Rust, Python, JS/TS, C#, Java, C/C++. Extracts symbols
  (functions, methods, classes, types, interfaces) with their line ranges into a **symbol index**, enabling
  exact `definition-of` / `references-to` lookups and structural prefiltering.
- **ripgrep engine** — line-oriented regex search, used directly for unsupported languages and as the
  fallback whenever a parser is missing or a file fails to parse.

The interface always returns the same `CodeSpan` shape, so callers never branch on which engine ran. This is
where **graceful degradation** lives: a parse failure silently downgrades that file to ripgrep.

### 2.5 Tier 1 — Scout
A thin wrapper around **Microsoft FastContext**, used directly as a pinned dependency — Harpyja does not
reimplement it. Scout hands FastContext the natural-language query (plus optional Tier-0 seed spans as hints)
and lets FastContext run its read-only `Read`/`Glob`/`Grep` exploration with parallel tool calls against the
explorer model via the Model Gateway, returning a compact citation block (file paths + line ranges). The
**Scout adapter** exists only to normalize FastContext's `<final_answer>` output into Harpyja's `Citation`
shape and to keep the integration swappable as FastContext evolves.

### 2.6 Tier 2 — Deep
A Recursive Language Model (`dspy.RLM`). Instead of loading source into the prompt, the repo manifest and a
set of **bounded host tools** live in a sandboxed REPL; the model writes code, searches, partitions, and
spawns recursive sub-queries, pulling only the spans it needs into token space. This adopts the megacode
approach — reimplemented, language-agnostic, and not vendored. Host tools exposed to the RLM:

- `list_manifest(filter)` — read the ranked manifest.
- `search(pattern, scope)` — ripgrep-backed regex search with bounds.
- `symbols(path)` — Tier-0 symbol index for a file (AST when available).
- `read_span(path, start, end)` — bounded snippet read.

Tools are **read-only and bounded** (max lines, max matches, max files) so a runaway query can't exhaust
memory or the model's budget.

### 2.7 Verification Gate
The cheap insurance that makes `auto` trustworthy. After Tier 1 returns, the gate reads the actual cited
lines and scores them against the query — by a small LLM judge call and/or embedding similarity, whichever
the profile enables. Below threshold → escalate. This catches the dangerous case of a confident-but-wrong
citation, which is worse than no citation because the agent will trust it.

### 2.8 Model Gateway
A single abstraction over the local OpenAI-compatible endpoint (llama.cpp's `llama-server` or Ollama). Holds
the base URL, the **primary** model (Scout + RLM driver) and an optional smaller **sub** model (RLM
sub-queries, verification judge). Centralizing this means every tier is endpoint-agnostic and the air-gap
guarantee is enforced in one place.

### 2.9 Citation Formatter
Normalizes heterogeneous tier outputs into one ranked, deduplicated citation list. Merges overlapping spans,
attaches a one-line rationale and a `source_tier`, and clamps to `max_results`.

## 3. Request lifecycle (`harpyja_locate`)

```
locate(query, repo, mode=auto)
   │
   ├─ ensure index (build if missing/stale) ........................ Indexer
   ├─ classify(query) → {point | broad}; budget = profile + mode ... Orchestrator
   │
   ├─ if point & symbol-like:
   │      seed = Tier0.symbol_lookup(query) ........................ Symbol Layer
   │
   ├─ candidates = Tier1.scout(query, seed) ........................ Scout
   │
   ├─ score = VerificationGate.check(candidates, query)
   │      pass  → results = candidates
   │      fail  → escalate
   │
   ├─ if escalate or classify==broad or mode==deep:
   │      results = Tier2.deep(query, manifest, candidates) ........ Deep
   │
   └─ return Formatter.rank(results)[:max_results] ................. Citation Formatter
```

`mode=fast` stops after Tier 1 regardless of the gate (returns with a low-confidence flag if it would have
escalated). `mode=deep` skips straight to Tier 2 after the Tier-0 seed.

## 4. Cross-cutting decisions

**Concurrency / thread-safety.** `dspy.RLM` is not thread-safe with a custom interpreter, so the Deep tier
constructs a **fresh RLM instance per request** (default per-call interpreter). The MCP server handles
concurrent agents by isolating each request; no tier holds mutable shared state beyond the read-only index.

**Air-gap enforcement.** The Model Gateway is the only outbound caller and it points at localhost. Indexer,
Symbol Layer, and ripgrep are filesystem-only. Deno/Pyodide for the RLM sandbox is installed once and runs
offline. A startup check can assert no non-loopback endpoints are configured.

**Footprint.** One 4B-class quantized model serves both Scout and the RLM driver; the optional sub/judge
model can be the same model or a smaller one. Tier 0 carries most point-lookup load with zero model cost,
keeping the GPU free for genuinely hard queries.

**Failure posture.** Model down → Harpyja still answers from Tier 0 (deterministic) with a flag. Parser
missing → ripgrep. RLM sandbox unavailable → return Tier-1 best-effort. Harpyja prefers a degraded honest
answer over a hard failure.

**Statelessness & swappability.** Tiers are adapters behind stable interfaces (`Locator` protocol). The Scout
engine, the Deep engine, the judge, and the model backend can each be replaced independently. This matters
because FastContext is new and moving.

## 5. What lives where (packages)

```
harpyja/
  server/        FastMCP app, tool registration, transports
  orchestrator/  router, query classifier, verification gate, formatter
  index/         file walker, manifest, incremental hashing
  symbols/       tree-sitter engines, ripgrep engine, CodeSpan interface
  scout/         FastContext-style adapter (Tier 1)
  deep/          dspy.RLM driver + bounded host tools (Tier 2)
  gateway/       model gateway (llama.cpp / Ollama)
  config/        settings load/merge, profiles
  cli.py         serve / index / locate / read entrypoints
```

See [`SPEC.md`](./SPEC.md) for the interface contracts each package must satisfy.
