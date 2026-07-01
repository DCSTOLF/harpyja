# Harpyja

> ## ⚠️ Experimental — not production-ready
>
> **This project is entirely experimental.** It is a research/work-in-progress prototype: APIs,
> schemas, defaults, and behavior change without notice; the documented hardware footprint is **not
> validated** (see the caveat below); and real-data evaluation is ongoing and `indicative_only`. Do not
> depend on it for anything you can't afford to have break. Use at your own risk.

**A precision code-retrieval MCP server for coding agents working in large, legacy, and air-gapped codebases.**

Harpyja is a [Model Context Protocol](https://modelcontextprotocol.io) server with one job: given a
natural-language query, find the **exact files and line ranges** a coding agent needs across millions of
lines of code — without the agent burning its own context window on blind searches.

It is named after *Harpia harpyja*, the harpy eagle: an apex hunter that locks onto a target in dense
canopy and does not miss.

```
agent ──"where is the retry/backoff logic for the payment gateway?"──▶ Harpyja
                                                                          │
                                       ┌──────────────────────────────────┘
                                       ▼
                          Tier 0  deterministic (AST + ripgrep)
                          Tier 1  Scout      (fast trained explorer)
                          Tier 2  Deep        (recursive LM, on escalation)
                                                                          │
agent ◀──  src/billing/gateway.py:212-241  ◀──────────────────────────────┘
           tests/test_gateway.py:88-103
```

---

## Why

Coding agents are good at *editing* code and bad at *finding* it in repositories that are too big to fit
in context. The usual failure mode is the agent spending half its context window grepping around, then
reasoning over a polluted history. This is worse in the codebases that need it most: decades of patched
proprietary code, no surviving institutional knowledge, no clean README, and nothing that ever entered an
LLM's training set.

Harpyja externalizes retrieval into a dedicated subsystem that does it cheaply and precisely, then hands
back compact citations. Not every problem needs a million-token context window. Sometimes you need a small,
brutally specialized subsystem that does one thing extremely well.

## What it is (and isn't)

- **It is** a read-only locator. It returns `file:line` citations and short rationales.
- **It is not** an editor, a RAG chatbot, or a code generator. It never modifies your repository.
- **It runs offline.** Everything — model, search, parsing — stays on the local machine. No telemetry,
  no external calls. Suitable for fully air-gapped environments and proprietary code that must stay proprietary.
- **It fits a modest box.** The default profile targets an 8 GB local GPU using a 4B-class quantized model.

  > ⚠️ **The 8 GB / Q4 footprint is not currently validated (2026-06, specs 0010–0012).** The
  > *recommended* `FastContext-1.0-4B-RL-Q4_K_M` community model is **non-functional on real
  > repositories** — it emits a `<final_answer>` on the toy fixture but **never converges on real
  > codebases** (empty output: the classic "passes tests, fails in production"). The only Scout config
  > validated on real repos is the **Q8 conversion** (~2× the memory of Q4, ~5 GB resident),
  > which **OOMs `mode=auto` on a 16 GB machine** (co-loading Scout + the Deep model + the Deno/Pyodide
  > sandbox). **The documented hardware floor needs re-characterizing for the Q8 working config**; until
  > then treat "8 GB / 4B" as the *aspirational* target, not a validated minimum.
  >
  > **Defaults (spec 0016 / B1 fix):** the default `scout_model` is the *served* Q8 tag
  > `hf.co/dstolf/FastContext-1.0-4B-RL-Q8_0-GGUF:latest` (the old recommended-Q4 tag was not
  > served by Ollama → HTTP 404 on every call). The default Deep model (`lm_model`) is provisionally
  > `hf.co/Qwen/Qwen3-8B-GGUF:latest` ("for now"). Override either from the eval CLI with
  > `--scout-model` / `--deep-model` (`run`/`sweep`), or via `harpyja.toml` / `HARPYJA_*`.

## How it works

Harpyja is a three-tier locator with cost-based escalation:

| Tier | Engine | Role | Speed |
|------|--------|------|-------|
| **0** | Tree-sitter symbol index + ripgrep | Deterministic prefilter and exact-symbol lookups | instant |
| **1** | **Scout** — a thin wrapper around Microsoft **FastContext** (read-only `Read`/`Glob`/`Grep` exploration) | The default. Handles most "where is X" queries | fast |
| **2** | **Deep** — a Recursive Language Model (`dspy.RLM`) over bounded host tools | Escalation path for broad/trace/audit queries | slower, thorough |

The **Orchestrator** runs the cheapest tier that can answer, verifies the result by reading the cited lines
back, and only escalates when verification fails or the query shape demands it. See
[`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full design and [`SPEC.md`](./SPEC.md) for the contracts.

Tier 1 **uses Microsoft [FastContext](https://github.com/DCSTOLF/fastcontext) directly** — Harpyja wraps it
as a pinned dependency, not a reimplementation. Tier 2 **reimplements the `dspy.RLM` approach** demonstrated by
[megacode](https://github.com/mitkox/megacode), which serves only as reference and inspiration (not a
dependency). Around both, Harpyja adds the language-agnostic indexing, symbol layer, routing, verification,
and MCP surface that turn them into a reusable locator.

## MCP tools

Harpyja exposes a deliberately tiny surface:

- **`harpyja_locate(query, repo_path, mode="auto", max_results=8)`** → ranked `file:line` citations with rationales.
- **`harpyja_read(path, start, end)`** → a bounded code snippet (for remote/air-gapped repos the agent can't read directly).
- **`harpyja_index(repo_path, refresh=false)`** → build/refresh the manifest and symbol index ahead of time.

`mode` is one of `auto | fast | deep`. In `auto`, the Orchestrator decides which tiers to run.

## Supported languages (symbol layer)

Tree-sitter symbol extraction ships for **Go, Rust, Python, JavaScript/TypeScript, C#, Java, and C/C++**.
Any other language — or a file that fails to parse — **degrades gracefully to ripgrep**, so Harpyja never
goes blind on an unknown file type.

## Requirements

- Python **3.12+**
- [`ripgrep`](https://github.com/BurntSushi/ripgrep) (`rg`) on `PATH`
- [Deno](https://deno.land) (the `dspy.RLM` sandbox runs on Deno/Pyodide WASM — installed once, runs locally)
- A local OpenAI-compatible model endpoint: **llama.cpp** (`llama-server`) **or Ollama**
- Optional: a CUDA/Metal GPU (the default profile *targets* 8 GB; see the validation caveat above —
  the real-repo-working Q8 Scout config is ~5 GB resident and `mode=auto` co-loads the Deep model + WASM
  sandbox on top, so 8 GB is not a validated minimum yet)

## Install

```bash
git clone <your-fork>/harpyja
cd harpyja
uv sync            # or: pip install -e .
```

## Serve a model (pick one)

**Ollama**

```bash
ollama serve
ollama pull <4b-instruct-model>
export HARPYJA_LM_API_BASE="http://localhost:11434/v1"
export HARPYJA_LM_MODEL="<4b-instruct-model>"
```

**llama.cpp**

```bash
llama-server -m ./models/<model>.gguf --port 8000 --ctx-size 8192
export HARPYJA_LM_API_BASE="http://localhost:8000/v1"
export HARPYJA_LM_MODEL="local"
```

## Wire it into your agent

**Claude Code** (`.mcp.json` in your project, or `claude mcp add`):

```json
{
  "mcpServers": {
    "harpyja": {
      "command": "uv",
      "args": ["run", "harpyja", "serve", "--stdio"],
      "env": { "HARPYJA_LM_API_BASE": "http://localhost:11434/v1" }
    }
  }
}
```

**Codex** (`~/.codex/config.toml`):

```toml
[mcp_servers.harpyja]
command = "uv"
args = ["run", "harpyja", "serve", "--stdio"]
env = { HARPYJA_LM_API_BASE = "http://localhost:11434/v1" }
```

Both speak MCP over stdio. Harpyja also supports streamable HTTP (`harpyja serve --http --port 9000`) for
shared or containerized deployments.

## Quick start

```bash
# One-time (optional) index for faster first query
uv run harpyja index --repo ~/dev/legacy-monolith

# Ask from the CLI (same path the MCP tool uses)
uv run harpyja locate --repo ~/dev/legacy-monolith \
  --query "where do we validate inbound webhook signatures?" \
  --mode auto
```

Then, inside Claude Code or Codex, just ask naturally — the agent will call `harpyja_locate` on its own.

## Configuration

Settings load from `harpyja.toml` (project root) with environment-variable overrides
(`HARPYJA_*`). See [`SPEC.md`](./SPEC.md#configuration) for the full table. Common knobs: model endpoints,
escalation thresholds, per-tier token budgets, language toggles, search bounds, and the outbound model-call
timeout (`lm_http_timeout_s`, default 120 s — bounds each Gateway HTTP call so a stalled local endpoint
degrades instead of hanging).

## Project status

Early. The tiers are designed to land incrementally — see [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md).
Harpyja stays useful at every wave: even Wave 1 (deterministic AST + ripgrep, no model) is a working locator.

> **Note:** FastContext is a very new research release and its API/weights may shift. Harpyja pins versions
> and isolates the integration behind an adapter so the Scout tier can be swapped without touching the rest.

## License

MIT. Builds on MIT/permissively-licensed upstreams (FastContext, DSPy, tree-sitter, ripgrep).
