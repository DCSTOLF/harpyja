---
id: "0007"
title: "FastContext"
status: closed
created: 2026-06-27
authors: [claude]
packages: [harpyja/scout, harpyja/gateway, harpyja/config]
related-specs: ["0005", "0006"]
---

# Spec 0007 — FastContext

## Why

Wave 3 shipped Scout behind a `ScoutBackend` Protocol + `FastContextBackend`
adapter that takes an **injected** client — but no real default client exists,
so Scout's live acceptance criterion
(`test_scout_fast_returns_tier1_citations_live`) only ever **skips**. Tier 1 is
structurally present but never actually runs a model end-to-end.

FastContext is real and installable (`microsoft/fastcontext` via a pinned `git`
install; the `fastcontext` CLI is already on PATH; the `FastContext-1.0-4B-RL`
fine-tune runs in Ollama on loopback). This spec supplies the real backend so
Scout runs end-to-end and the suite's **last skip becomes a genuine pass** —
exactly as Wave 4 did for Deep.

Ref: `FASTCONTEXT_INSTALL.md` (repo root — currently untracked; **commit it**
as part of this wave so the spec's primary reference is durable, or fold its
load-bearing facts inline); history.md 2026-06-27 (Wave 3/4 backend + air-gap
patterns).

### Invariant (load-bearing)

Scout drives the **real FastContext agent** — Microsoft's own Read/Glob/Grep
exploration loop, constructed via `make_fastcontext_agent` — **not** `dspy.RLM`.
That distinct engine is what keeps Tier 1 structurally separate from Tier 2.
Preserve it: do **not** route Scout through Deep's machinery.

### Verified against source (resolves both former open questions)

Confirmed against `/Users/daniel.stolf/Development/fastcontext` @ commit
`1522d6d6b5e040e817b468e12826662aa069a8b0`
(`src/fastcontext/agent/{agent_factory,agent,llm}.py`):

- `make_fastcontext_agent(trajectory_file, work_dir, **kwargs)` — `**kwargs`
  feeds only `system_prompt`; there is **no `model` / `base_url` / `api_key`
  parameter**. It reads `FC_MODEL` / `FC_BASE_URL` / `FC_API_KEY` /
  `FC_MAX_TOKENS` / `FC_TEMPERATURE` from `os.environ` at construction and
  raises `RuntimeError` on a missing `FC_MODEL` / `FC_BASE_URL` or a missing
  `rg`.
- `agent.run(prompt, max_turns=4, verbose=False, citation=False)` — matches the
  call shape; we pass `citation=True` and an explicit `max_turns`.
- **No config-file / per-call config seam exists.** Per-instance config is only
  reachable by constructing `LLM(model=…, base_url=…, …)` + `Agent(llm=…)`
  directly — i.e. **bypassing the factory** (considered and deferred; see
  Deviations).
- **`FC_REASONING_EFFORT` is read lazily inside `LLM.acall` on every model
  call** (`llm.py:77`), not at construction — so its env-sensitive window spans
  the **entire `agent.run()`**, which sets the lock scope below.
- Dependency pin: `git+https` install at SHA `1522d6d6…` — verified to install
  and import cleanly. The `third_party/mini-swe-agent` submodule is **vestigial**
  (not referenced by the package source or `pyproject.toml`), so a plain
  `git+https` install — which does not init submodules — works; no local clone
  required.

## What

Supply a default client for `FastContextBackend` behind the **unchanged**
`ScoutBackend` seam (unit tests keep driving fakes). One client, two paths.

### Backend client — two paths

- **Path A (primary, in-process):**
  `make_fastcontext_agent(work_dir=<repo>, trajectory_file=<temp OUTSIDE repo>)`
  → `await agent.run(prompt, max_turns=<n>, citation=True)` inside the tool
  handler. **Lazy import** — no top-level `import fastcontext` (mirrors
  `RlmBackend`). The `ScoutBackend` Protocol stays synchronous
  (`run(query, seed) -> list[CodeSpan]`); the adapter bridges the awaitable
  `agent.run(...)` to it via `asyncio.run(...)` (no `pytest-asyncio`, per
  conventions).
- **Path B (fallback, demoted — retained behind the injected runner):** when
  the package isn't importable, drive the `fastcontext` CLI as a subprocess
  (`cwd=repo`, `--traj <temp>`, `--citation`, timeout, parse `<final_answer>`)
  via an **injected runner**. Path B is the no-package CLI escape **and** the
  concurrency-clean path (env scoped to the child); it is not deleted.

### Dependency

Pinned `git` install at SHA `1522d6d6b5e040e817b468e12826662aa069a8b0`
(`uv add "git+https://github.com/microsoft/fastcontext@1522d6d6b5e040e817b468e12826662aa069a8b0"`);
no PyPI. This is **portable** (no machine-specific path) and was verified to
resolve, install, and import. The `third_party/mini-swe-agent` submodule is
vestigial (unreferenced by the package), so a plain `git+https` install needs no
submodule init. `requires-python >=3.12` already holds.

### Model selection (distinct from Deep)

Scout uses the FastContext fine-tune, **distinct** from Deep's driver. `FC_MODEL`
maps from a **Scout-specific** setting (`scout_model`, default the Ollama GGUF),
**not** the shared `lm_model`. `scout_model` is a **new** `Settings` field,
added per the additive-field convention (appended last, with a default) and
inheriting the standard precedence: defaults < `harpyja.toml` < `HARPYJA_*` env
< per-request override.

### Config injection — AC3 relaxed *conditionally* (not absolutely)

The original AC3 forbade **any** per-call mutation of process-global
`os.environ`. Source verification shows the factory is **env-only** with no
config-file seam, so that absolute ban is relaxed to a conditional one that
still stops the race AC3 existed to prevent:

- **Preferred (if a per-call config-file / direct-param seam existed):** inject
  `FC_*` with no shared-state mutation. **Verified absent** — so this branch
  does not apply here.
- **Landed branch — process env under a Scout single-flight lock:** set `FC_*`
  in the process environment, but **only while holding a Scout single-flight
  lock**, and hold that lock across the **entire `agent.run()`** (not just
  construction), because `FC_REASONING_EFFORT` is read lazily on every model
  call. This serializes Scout. A flat "OS env is fine, no lock" is rejected:
  it silently ships the very cross-request race AC3 existed to stop.

The serialization cost is **accepted**: on the local single-GPU profile, Scout
calls already contend for the one 4B model, so a single-flight lock is not a
real throughput regression (recorded in Deviations).

**Scope — relaxation is Scout-only and must not leak to Deep.** This
env-injection latitude is confined to the FastContext adapter
(`harpyja/scout/`). Tier 2 (`harpyja/deep/`) keeps "config from `Settings`, not
ambient env" unchanged; nothing here touches Deep's wiring.

### Air-gap (single helper) — non-negotiable, ordering untouched

`gateway.assert_local` on the **resolved** `FC_BASE_URL` fires **before the
agent is constructed (Path A) and before the subprocess is spawned (Path B)** —
FastContext owns its own LLM client (`AsyncOpenAI` inside `LLM`), the
"third-party owns its model client" honest-limit. Still **one** air-gap helper,
never a parallel check. Config relaxation changes nothing about the egress
guarantee. Prove zero non-loopback egress with a network-deny test (the Wave-4
pattern).

### Read-only — assumption verified by test (symmetric to the air-gap)

`trajectory_file` resolves **outside** the scanned repo (a temp path per call).
But FastContext's in-process loop has full Read/Glob/Grep filesystem reach into
`work_dir=<repo>`; per conventions, third-party in-process behavior is "an
assumption verified by test, never an asserted guarantee." So, symmetric to the
air-gap's network-deny test, a **no-repo-writes integration test** proves an
end-to-end Path-A run leaves the scanned repo byte-unchanged (no
FastContext-authored cache/state/lock files), and the residual in-process write
risk is **recorded** (no false-capability claim).

### Normalization

FastContext `<final_answer>` → `CodeSpan` via the **existing** `normalize_spans`
(shared with Deep), `source_tier=1`, repo-confined + clamped; out-of-repo /
nonexistent / over-budget refs are dropped.

### Degradation — four distinct causes, never collapsed

Package + CLI absent **OR** endpoint down → `ScoutUnavailable` → the existing
four-state Tier-0 floor (`scout-degraded:<cause>`); **no new branch**. The cause
is one of **four distinct, stable identifiers** (never one collapsed note, per
the cause-distinctness convention):

- `fastcontext-missing` — package not importable (Path A unavailable).
- `cli-missing` — Path A unavailable **and** no `fastcontext` on PATH.
- `connection-refused` — endpoint configured but down.
- `backend-error` — agent/CLI ran but failed in a typed infra way.

A missing `FC_BASE_URL` maps to the existing `no-endpoint-configured` cause; a
missing `rg` surfaces as the loud `RipgrepMissingError` **floor** (not a Scout
degrade cause — `make_fastcontext_agent` itself requires `rg`). `ScoutUnavailable`
is raised **only** for typed infra failure — never for weak / zero /
low-confidence citations (those stay an honest Tier-1 result). Foreign
exceptions (the factory's `RuntimeError`) are wrapped preserving the cause
(`raise … from err`).

## Acceptance criteria

`[unit]` = fakes / injected, no model. `[integration]` =
`@pytest.mark.integration`, skip-not-fail.

1. **[integration]** FastContext present → Scout `mode=fast` runs
   `make_fastcontext_agent` against the loopback endpoint; returns
   `tiers_run=[0,1]`, citations `source_tier=1`.
2. **[unit]** `assert_local(resolved FC_BASE_URL)` is called **before** the
   agent is constructed (Path A) **and before** the subprocess runner is
   invoked (Path B); a non-loopback URL → `AirGapError`, with the agent **never
   constructed** and the runner **never invoked**.
3. **[unit]** `FC_*` derives from `Settings` (`scout_model` / `lm_api_base`),
   not ambient env; precedence respected (defaults < `harpyja.toml` <
   `HARPYJA_*` < per-request). Path A sets `FC_*` in process env **only under a
   Scout single-flight lock held across the full `agent.run()`** — no unlocked
   or torn per-call mutation; Path B scopes env to the **child** process (no
   parent-env mutation).
4. **[unit] Concurrency / no cross-contamination.** Two parallel Scout calls
   with **different `scout_model`** each observe their own `FC_MODEL` (and other
   `FC_*`) with zero cross-contamination — driven via the injected factory /
   runner, no real model. This is the test that proves the chosen mechanism
   (not the env ban itself).
5. **[unit]** FastContext `<final_answer>` → confined, clamped `CodeSpan`
   (`source_tier=1`) via `normalize_spans`; out-of-repo / nonexistent /
   over-budget refs dropped.
6. **[unit]** Path B: package not importable but `fastcontext` on PATH →
   subprocess driven (`cwd=repo`, `--traj <temp>`, `--citation`, timeout, block
   parsed) via an **injected runner**; no real process spawned.
7. **[unit]** `trajectory_file` resolves **outside** the scanned repo.
8. **[integration] Read-only.** An end-to-end Path-A run leaves the scanned repo
   **byte-unchanged** (no FastContext-authored files in `work_dir`); residual
   in-process write risk recorded (assumption-verified-by-test, symmetric to
   AC9).
9. **[integration]** network-deny: end-to-end on a loopback-only endpoint, zero
   non-loopback egress.
10. **[unit]** package + CLI absent / endpoint down → `ScoutUnavailable` with
    the **four distinct causes** (`fastcontext-missing` / `cli-missing` /
    `connection-refused` / `backend-error`, never collapsed) → the existing
    four-state Tier-0 fallback; `rg`-missing surfaces as the `RipgrepMissingError`
    floor; **not** raised for weak / empty citations (those stay an honest
    Tier-1 result).
11. **[integration]** the Wave-3 Scout live AC flips skip → real pass when
    FastContext is present; skip-not-fail otherwise.

## Deviations (record in the changelog at close, not the diff)

- **AC3 relaxed (conditional, not absolute):** Path A primary; no config-file
  seam exists in FastContext, so `FC_*` are injected via process env **under a
  Scout single-flight lock spanning the full `agent.run()`** (`FC_REASONING_EFFORT`
  is read lazily per call). The lock **serializes Scout** — accepted for the
  local single-GPU profile, where concurrent Scout calls already contend for the
  one model. Path B remains the concurrency-clean fallback (env scoped to the
  child).
- **Considered and deferred:** per-instance constructor injection
  (`LLM(model=…, base_url=…)` + `Agent(llm=…)`, bypassing `make_fastcontext_agent`)
  would avoid the lock for `model`/`base_url` but **bypasses Microsoft's own
  factory** and couples to FastContext internals — deferred to keep the
  `make_fastcontext_agent` invariant. Revisit if the lock's serialization
  becomes a measured bottleneck.
- **AC10 broadened during implementation (graceful-degradation guardrail):** a
  live run surfaced that FastContext's *own* `get_final_answer` /
  `format_citations` can raise (e.g. `TypeError`) on malformed model output —
  the read-only confinement worked (it blocked the model's attempt to read
  `/harpyja` outside `work_dir`), but the third-party post-processing then
  crashed. The client now maps **any** unexpected backend exception (not just
  `RuntimeError`/`OSError`) to `ScoutUnavailable(backend-error)` so Scout
  degrades to the Tier-0 floor rather than letting a raw exception escape —
  honoring "no model → Tier 0". Floors (`RipgrepMissingError` / `AirGapError`)
  and the Path-B import signal still propagate; honest-empty (a clean run with
  no parseable citation) still returns `[]`, never a raise. Covered by
  `test_client_unexpected_backend_exception_maps_backend_error`, and the live
  integration ACs accept either a Tier-1 success (`[0,1]`) or an honest
  `scout-degraded:backend-error` (`[0]`) — both prove the real stack ran.

## Out of scope

- Verification Gate + Tier-0→1→2 auto-escalation (Wave 5).
- Any change to the `ScoutEngine` / `Locator` seam or the formatter.
- Deep / Tier 2 — including any change to Deep's "config from `Settings`, not
  ambient env" posture (the AC3 relaxation is **Scout-only**).
- Wave-2.1 substring / fuzzy matching.

This is a **new spec** — it does **not** reopen closed 0005.

## Open questions

_Both former open questions are resolved under "Verified against source":_

1. **SHA to pin** — `1522d6d6b5e040e817b468e12826662aa069a8b0`, installed via a
   portable `git+https` pin (the `third_party/mini-swe-agent` submodule is
   vestigial, so no submodule init / local clone is needed).
2. **Config-injection seam** — `make_fastcontext_agent` is **env-only** (no
   `model`/`base_url` params, no config-file seam); `FC_REASONING_EFFORT` is
   lazy-read per call → landed on env-under-single-flight-lock spanning the full
   run.
