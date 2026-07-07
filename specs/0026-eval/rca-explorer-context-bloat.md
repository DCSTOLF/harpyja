---
spec: "0026"
kind: rca
date: 2026-07-07
subject: explorer returns `empty` where OpenCode localizes in seconds
root-cause: eager whole-repo context-map injection (spec 0024 build_context_map)
fix-spec: "0027"
---

# RCA — Harpyja explorer degrades to `empty` where OpenCode localizes in seconds

## TL;DR

The Scout explorer, driving a capable model (`Qwen3-16B-A3B`) on the astropy case,
returned `empty` with `turns_used: None` — a **degrade**, not an honest "not found".
The **same model + same llama.cpp server localizes the file and the exact block in a
few seconds inside OpenCode.** Root cause: spec-0024's `build_context_map` prepends a
**flat listing of the entire repository** (~1,221 lines / ~10,181 tokens for astropy)
to the prompt, re-sent every turn. That bloat both slows prefill (~48–68s/turn) and
pushes the model into a generation that does not complete even turn 1 within a 300s
timeout → the gateway raises → `ScoutUnavailable` → floored to `empty`. The eager
whole-repo **push** is the defect; the fix (spec 0027) is **pull** — start near-empty,
discover structure on demand via tools, like OpenCode does.

## Symptom

`_run_scout_case` on `astropy__astropy-12907` (gold: `astropy/modeling/separable.py`
242–248) returned 0 citations, `BUCKET: empty`, `turns_used: None`, across:
- Ollama and llama.cpp serving,
- tight (40s) and generous (300s) HTTP timeouts,
- both pilot subjects and stronger models.

`turns_used: None` is diagnostic: on turn/wall exhaustion the backend sets
`last_turns_used` to the count **before** raising; `None` means the loop **raised an
exception before any submission** (mapped to `MODEL_UNREACHABLE`/`BACKEND_ERROR`), i.e.
the model never completed a usable turn.

## Investigation chain (what was ruled out, in order)

1. **Not the gateway timeout wiring.** `ModelGateway.complete_with_tools` binds the same
   finite per-op timeout as `complete` (spec 0017). Not a missing-timeout bug.
2. **Not model capability.** The 16B localizes this exact case in OpenCode.
3. **Not model speed / not a "dribble".** Plain-chat calls were 0.8–7.5s. Fast model.
4. **Tool-calling support is SERVER-dependent (a real secondary finding).** Ollama
   serves with `--no-jinja --chat-template chatml`, so a *raw HF GGUF* emits **no**
   `tool_calls` there; Ollama-library models and `llama-server --jinja` do. (Matrix
   below.) This blocked the Ollama run of the unsloth 16B outright — but the pilot
   subjects DID tool-call, so it is not the pilot's cause.
5. **The real cause: prompt bloat.** Even on llama.cpp with working tool-calls and a
   300s timeout, turn 1 (a 10,181-token payload) did not return within 300s.

## Measurements

### Tool-calling support (OpenAI `tools` via each server)

| Model | Server | Emits `tool_calls`? | Latency |
|-------|--------|:---:|---|
| `qwen3:8b` | Ollama | ✅ `finish=tool_calls` | 17.7s |
| `hf.co/Qwen/Qwen3-8B-GGUF:latest` (pilot arm A) | Ollama | ✅ | 22.4s |
| `qwen3:4b-instruct` (pilot arm B) | Ollama | ✅ | 3.1s |
| `qwen3-coder:30b` | Ollama | ✅ | 10.3s |
| `hf.co/unsloth/Qwen3-16B-A3B-GGUF:latest` | Ollama (`--no-jinja chatml`) | ❌ `finish=stop`, no call | 8.4s |
| `unsloth/Qwen3-16B-A3B-GGUF:Q4_K_M` | **llama.cpp `--jinja`** | ✅ `finish=tool_calls` | **0.8s** |

Takeaway: the explorer requires an endpoint that surfaces OpenAI `tool_calls`. Same
weights, different server → different tool-calling. (Feeds the 0027 out-of-scope
"tool-call serving preflight" for the bake-off.)

### Context-map size (the defect)

`build_context_map(manifest, query, settings)` for astropy:
- **1,221 lines**, **40,725 chars**, **~10,181 tokens** — a flat listing of every path
  in the repo (from `.github/…` to `licenses/…` to `setup.py`).
- Serialized request body: **42,213 bytes**.
- Re-sent **every turn** and grows as tool outputs accumulate.

### Per-turn latency (llama.cpp, 16B, this hardware)

| Prompt | Latency | Outcome |
|--------|---------|---------|
| Bare tool-call probe (tiny) | **0.8s** | `tool_calls` ✅ |
| ~10K-token context-map + "call grep" (simple) | **48.3s** | `tool_calls` ✅ (mostly prefill) |
| ~16K-token simulated big prompt | **68.6s** | `tool_calls` ✅ |
| **Real explorer turn 1** (map + system frame + 3 tool schemas) | **timed out at 300s** | EXCEPTION → degrade |

The isolated 10K-token prompt finishes in 48s because it is a trivial ask; the **real**
explorer turn — same map **plus** the verbose system prompt and 3 detailed tool schemas
— pushes the model (Qwen3, thinking-enabled) into a generation that **does not complete
turn 1 in 300s**. So there are two compounding costs, both from an oversized unfocused
prompt: (a) ~10K-token prefill, (b) runaway generation.

### Explorer runs (all degraded — none an honest localization attempt)

| Serving | Timeout | Elapsed | Result | `turns_used` |
|---------|---------|---------|--------|-------------|
| Ollama 16B (no tool_calls) | 90s | 117.5s | empty | None |
| Ollama `qwen3-coder:30b` (tool-calls ✅) | 40s | 71.8s | empty | None |
| llama.cpp 16B | 60s | 60.6s | empty (TimeoutError) | None |
| llama.cpp 16B, generous | 300s | turn-1 timed out at 300s | empty | None |

Every run degraded (`turns_used: None`) — the loop raised before any submission. Not one
was an honest localization measurement.

### The original "wedge"

Before bounding budgets, the FIRST live run (Ollama, `hf.co/Qwen/Qwen3-8B-GGUF`, SUT
default budgets 12 turns / 300s wall / 120s per-read) ran **60+ minutes at 0% CPU** on
`psf__requests-1142`: a slow local generation on the bloated prompt outlasted the
per-socket-op timeout (spec 0017's noted caveat — it is not a total-request deadline),
and neither the per-op timeout nor `scout_wall_clock_s` preempts an in-flight read.

## The OpenCode comparison (the variable)

| | Harpyja explorer | OpenCode |
|---|---|---|
| Initial context | **Whole-repo file tree dumped up front** (~10K tokens for astropy) | Near-empty; system prompt + task |
| Repo structure | Pushed eagerly, every turn, growing | **Discovered on demand** (`ls`/`glob`/`grep`) |
| Per-turn prompt | Large and growing | Small; only what the model chose to read |
| Result on astropy | 48–68s/turn → timeout/degrade → `empty` | Localizes file + block in seconds |

Same model, same llama.cpp server, same case: OpenCode succeeds in seconds; Harpyja
degrades. The one variable is that Harpyja front-loads the entire repo map and a heavy
tool/system frame, so the model never gets to *do* the task. A "simple" locator
out-prompts a full coding agent.

## Impact — the 0026 pilot finding is timeout-confounded

The all-`empty` results this defect produces are indistinguishable at the taxonomy level
from "the finder cannot localize" — both surface as an empty citation set. The recorded
finding that ran through THIS harness is therefore **capability-mute, not a
capability-finding**:

- **0026 pilot `UNDER_POWERED_STOP`** — ran on `ExplorerBackend` (the sole Scout backend
  post-0024/0025) with `lm_http_timeout_s=40`, far below the true ~48–68s/turn cost, so
  runs degraded on timeout/error, not on localization. It measured the harness, not the
  candidates.

**Scope — this does NOT reach 0020–0023 (a correction of this RCA's own first draft).**
`build_context_map` and `ExplorerBackend` are **net-new in spec 0024** (module docstrings:
"spec 0024, AC3"; both first committed in `7c94ef2`, "native explorer-loop Scout backend
replaces FastContext"). Specs **0020–0023 (2026-07-04/05) ran BEFORE 0024**, on the
retired FastContext client (`harpyja/scout/client.py`) — which **never called
`build_context_map` because it did not exist yet.** So their `RETRIEVAL_FUNDAMENTAL` /
near-zero-localization characterization **cannot be confounded by this eager-map defect.**
They measured a backend that has since been removed (0025); this RCA does not bear on them
either way. (Whether FastContext had its OWN prompt-construction problems is a separate,
un-investigated question — not claimed here.) An earlier draft of this section wrongly
listed 0020–0023 as "likewise confounded"; **that overreach is retracted** — an
inaccurate correction is worse than none. Only **0026** is confounded by this defect.

The FastContext **dependency removal (0024/0025) stands independently** — that model was
retracted/unobtainable; a sourcing decision, not a capability claim. What is unproven
until re-run is the 0026 CAPABILITY characterization that these candidates "can't
localize."

## Fix (spec 0027-harness)

Remove the eager whole-repo context-map entirely (push → pull); add a cheap on-demand
`ls`/tree tool so a blind start does not swing into aimless search; keep the cutover
minimal (no gate/matrix/`submit_citations`/tool-boundary change); make the three empties
(timeout-degrade / turn-exhaustion / honest-empty) distinguishable so a re-emptied
astropy is diagnosable; and validate on astropy as the OpenCode-parity proof. Then the
0026 pilot is re-run on the fixed explorer (with a timeout above real per-turn cost and a
tool-call serving preflight) — only then is its verdict a signal about candidates rather
than about the harness.

## Reproduction pointers

- Validation model/server: `unsloth/Qwen3-16B-A3B-GGUF:Q4_K_M` on `llama-server --jinja`,
  `127.0.0.1:8131/v1`, 65536 context.
- Context-map size: `harpyja.scout.context_map.build_context_map(manifest, query,
  settings)` over the astropy worktree.
- Degrade path: `harpyja/scout/explorer_backend.py::_run_loop` (`turns_used` set before
  the exhaustion raise; `None` ⇒ pre-submission exception).
