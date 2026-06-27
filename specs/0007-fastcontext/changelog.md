---
spec: "0007"
closed: 2026-06-27
---

# Changelog — 0007 FastContext

## What shipped vs spec

- Supplied the real **default client** for the already-shipped `FastContextBackend`
  seam (Wave 3 left it injected-only). Scout (Tier 1) now runs the real Microsoft
  FastContext agent (`make_fastcontext_agent` — its own Read/Glob/Grep loop, **not**
  `dspy.RLM`) end-to-end, and the Wave-3 live AC flips skip → genuine pass.
- The `ScoutBackend` / `ScoutEngine` / `Locator` / formatter seams are **unchanged**;
  new code is confined to `harpyja/scout/` plus an additive `Settings` field group
  and two new `errors.py` causes — exactly the blast radius the spec promised.
- **Path A (primary, in-process):** lazy-import `make_fastcontext_agent`, build a
  fresh agent (`work_dir=<repo>`, `trajectory_file=<temp OUTSIDE repo>`),
  `await agent.run(..., citation=True)` bridged onto a **dedicated loop-free worker
  thread** (`_run_coro_on_worker_thread`) so the synchronous `ScoutBackend` seam is
  safe even when the MCP handler is already on an event loop.
- **Path B (fallback):** injected CLI runner, `FC_*` scoped to the child via `env=`
  (parent `os.environ` never mutated).
- The full six-key `FC_*` → `Settings` mapping landed (`FC_MODEL←scout_model`,
  `FC_BASE_URL←lm_api_base`, `FC_API_KEY` constant `"ollama"` dummy,
  `FC_MAX_TOKENS`/`FC_TEMPERATURE`/`FC_REASONING_EFFORT`).
- Air-gap: single `gateway.assert_local` on the resolved `FC_BASE_URL` **before**
  agent construction (Path A) and **before** subprocess spawn (Path B); on Path A the
  lock is held across assert → env-set → construct → full run, closing the TOCTOU
  window. FastContext owns its own model client (the `rlm.py` precedent, not the
  `scout/tools.py` whitelist) — proven by a network-deny integration test.
- Read-only: `trajectory_file` resolves OUTSIDE the repo; a no-repo-writes
  integration test (content-hash manifest excluding `.harpyja/`) proves the scanned
  repo is byte-unchanged; the residual in-process write risk is recorded
  (assumption-verified-by-test, symmetric to network-deny).
- Four-way degrade cause taxonomy: added `fastcontext-missing` / `cli-missing` to the
  existing `connection-refused` / `no-endpoint-configured` / `backend-error`. A
  deterministic Path-A → Path-B state machine makes `fastcontext-missing` terminal
  **only** when the CLI runner is unwired.
- Scout stays **not cached** (model-backed, like Deep); `mode=auto` is unchanged and
  model-free; `mode=fast` → Scout.

## Deviations

- **AC3 relaxed (conditional, not absolute) — verified against FastContext source
  @ SHA `1522d6d6b5e040e817b468e12826662aa069a8b0`.** `make_fastcontext_agent` is
  **env-only** (no `model`/`base_url` params; reads `FC_*` from `os.environ`;
  `FC_REASONING_EFFORT` is read **lazily per model call** at `llm.py:77`). With no
  config-file seam, `FC_*` are injected via process env **under a module-level
  `threading.Lock` (`_SCOUT_ENV_LOCK`)** — NOT an `asyncio.Lock` (each call runs on
  its own worker thread/loop, so only a thread lock serializes cross-thread
  `os.environ` writes). The lock is held across the **entire `agent.run()`** (the lazy
  reasoning-effort read), set-then-restore with per-key unset-vs-empty preservation.
  This **serializes Scout** — accepted for the single-GPU profile (concurrent Scout
  calls already contend for the one 4B model). Scout-only; Deep's "config from
  `Settings`, not ambient env" is untouched.
- **Considered and deferred:** per-instance constructor injection (`LLM(...)` +
  `Agent(llm=...)`, bypassing the factory) would avoid the lock for
  `model`/`base_url` but couples to FastContext internals and breaks the
  `make_fastcontext_agent` invariant. Revisit only if the lock is a measured
  bottleneck.
- **AC10 broadened during implementation (live-discovered graceful-degradation
  guardrail).** A live run surfaced that FastContext's **own**
  `get_final_answer` / `format_citations` can raise (e.g. `TypeError`) on malformed
  model output — the read-only confinement worked (it blocked the model's attempt to
  read `/harpyja` outside `work_dir`), but the third-party post-processing then
  crashed. The client now maps **any** unexpected backend exception (not just
  `RuntimeError`/`OSError`) → `ScoutUnavailable(backend-error)`, so Scout degrades to
  the Tier-0 floor rather than letting a raw exception escape ("no model → Tier 0").
  Floors (`RipgrepMissingError` / `AirGapError`) and the Path-B `ImportError` signal
  still propagate; honest-empty (a clean run with no parseable citation) still returns
  `[]`, never a raise. Covered by
  `test_client_unexpected_backend_exception_maps_backend_error`; the live ACs accept
  either Tier-1 success (`[0,1]`) or an honest `scout-degraded:backend-error` (`[0]`)
  — both prove the real stack ran.
- **Install: portable `git` pin (deviation resolved).** The plan provisionally chose
  a local-path editable install and flagged its absolute path as non-portable for CI.
  On review this was tested and corrected: `uv add
  "git+https://github.com/microsoft/fastcontext@1522d6d6…"` resolves, installs, and
  imports cleanly — the `third_party/mini-swe-agent` submodule is **vestigial**
  (unreferenced by the package source / `pyproject.toml`), so the submodule-skipping
  `git+https` install works. Shipped as the portable `git`-rev pin; the
  non-portability deviation no longer applies.

## Files touched

- `harpyja/scout/client.py` (new) — `DefaultFastContextClient`, the `FC_*` mapping,
  `_managed_fc_env` set-then-restore guard, `_run_coro_on_worker_thread`,
  `_SCOUT_ENV_LOCK`, the Path-A/B state machine, `parse_final_answer`.
- `harpyja/scout/wiring.py` (new) — `build_scout_engine` (production `scout_factory`).
- `harpyja/scout/errors.py` — added `FASTCONTEXT_MISSING` / `CLI_MISSING`.
- `harpyja/config/settings.py` — added `scout_model`, `scout_max_tokens`,
  `scout_temperature`, `scout_reasoning_effort` (additive, appended last).
- `harpyja/scout/test_fastcontext_client.py` (new), `harpyja/scout/test_scout_wiring.py`
  (new), `harpyja/scout/test_scout_integration.py` (extended),
  `harpyja/config/test_settings.py` (extended).
- `pyproject.toml` / `uv.lock` — FastContext `git`-rev dependency (pinned SHA).
- `FASTCONTEXT_INSTALL.md` (committed — the spec's durable primary reference).

## Verification status

- Full suite **442 passed / 0 skipped**, ruff clean.
- Live run CONFIRMED end-to-end (~42s): FastContext's confinement blocked the model
  reading `/harpyja` outside `work_dir`; the Wave-3 live AC flipped skip → genuine
  pass (accepting either `[0,1]` success or honest `scout-degraded:backend-error`).

## ADR proposed for history.md

2026-06-27 — Scout Tier-1 real default client shipped (FastContext agent, env-under-
threading-lock, live-discovered degrade broadening). See the prepended entry in
`.speccraft/history.md`.

## Conventions proposed

- Extended the "third-party owns its own model client" bullet to cover the
  **off-loop env-config** case: when a third party reads config from `os.environ` and
  is bridged onto a worker thread, the single-flight primitive is a `threading.Lock`
  (not `asyncio.Lock`), the env guard is set-then-restore with per-key unset-vs-empty
  preservation, and the lock spans the full off-loop call when the config is read
  lazily.
- New bullet: a **third-party post-processing crash** (the backend's own
  formatter/parser raising on malformed model output) is infra failure → map **any**
  unexpected backend exception to the typed degrade cause; never let a raw exception
  escape the tier. Floors still propagate; honest-empty still returns `[]`.
