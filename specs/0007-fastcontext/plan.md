---
spec: "0007"
status: planned
strategy: tdd
---

# Plan — 0007 FastContext

Supply the real **default client** for the already-shipped `FastContextBackend`
seam so Scout (Tier 1) runs `make_fastcontext_agent` end-to-end and the Wave-3
live AC flips skip → pass. The `ScoutBackend` / `ScoutEngine` / `Locator` /
formatter seams stay **unchanged**; all new code lands in `harpyja/scout/`
(plus one additive `Settings` field group and two new `errors.py` causes).

## Carry-forward decisions resolved (load-bearing — these shape the tests)

These are settled here, not left open. Tests below assert them.

- **D1 — Async bridge + lock primitive.** The default in-process client runs the
  awaitable `agent.run(...)` via `asyncio.run(...)` on a **dedicated loop-free
  worker thread** (`_run_coro_on_worker_thread`), so it is safe even when the MCP
  tool handler is already on a running event loop (`asyncio.run` from inside a
  running loop raises). Concurrent Scout calls land on different OS threads, each
  spinning its own loop, so the single-flight primitive is a **module-level
  `threading.Lock`** (`_SCOUT_ENV_LOCK`), NOT an `asyncio.Lock`. Scope: module-level
  singleton, Scout-only — never leaks to Deep.
- **D2 — `FC_*` env injection under the lock, set-then-restore.** Path A sets the
  managed `FC_*` keys in `os.environ` **only while holding `_SCOUT_ENV_LOCK`**,
  via a `try/finally` that snapshots each key's prior value and restores it
  (`del` if it was unset, re-assign if it was empty `""` — the unset-vs-empty
  distinction is preserved per key). The lock is held across the **entire**
  `agent.run()` (not just construction), because `FC_REASONING_EFFORT` is
  lazy-read per model call at `llm.py:77`. Path B never mutates parent env: it
  scopes `FC_*` to the child via `subprocess env=`.
- **D3 — Full `FC_*` → `Settings` mapping** (all set unconditionally; `FC_API_KEY`
  is a constant dummy because Ollama needs none):

  | env var               | source                          | set when      |
  |-----------------------|---------------------------------|---------------|
  | `FC_MODEL`            | `settings.scout_model`          | unconditional |
  | `FC_BASE_URL`         | `settings.lm_api_base`          | unconditional |
  | `FC_API_KEY`          | constant `"ollama"` (dummy)     | unconditional |
  | `FC_MAX_TOKENS`       | `settings.scout_max_tokens`     | unconditional |
  | `FC_TEMPERATURE`      | `settings.scout_temperature`    | unconditional |
  | `FC_REASONING_EFFORT` | `settings.scout_reasoning_effort` | unconditional |

  `scout_model` (default the Ollama GGUF) is distinct from `lm_model` (Deep). All
  six Scout fields are additive — appended **last** in `Settings` with defaults,
  inheriting the standard precedence (defaults < `harpyja.toml` < `HARPYJA_*` env
  < per-request) via the existing `_from_toml` / `_from_env` machinery.

- **D4 — Deterministic fallback state machine + terminal causes.** On Path A the
  client lazy-imports the factory:
  - import OK → run Path A.
  - import fails **and** a CLI runner is wired (not `None`) **and** `fastcontext`
    is on `PATH` (via injected `which`) → run Path B.
  - import fails **and** CLI runner wired but `fastcontext` **not** on `PATH` →
    `ScoutUnavailable("cli-missing")`.
  - import fails **and** CLI runner is unwired (`None` / intentionally disabled) →
    `ScoutUnavailable("fastcontext-missing")` (this is the **only** path on which
    `fastcontext-missing` is terminal, making AC10's test unambiguous).
  - run reaches the endpoint but it is down → `ScoutUnavailable("connection-refused")`.
  - factory `RuntimeError` naming a missing `FC_BASE_URL` → `ScoutUnavailable("no-endpoint-configured")`.
  - any other typed infra failure from factory/agent/CLI → `ScoutUnavailable("backend-error")`,
    wrapped `raise ... from err`.
  - factory's `RipgrepMissingError` (missing `rg`) → **propagates as the floor**,
    never a Scout degrade cause.
  - weak / zero / low-confidence citations → honest **empty** Tier-1 result, never
    a raise.
- **D5 — Read-only assertion surface (AC8).** Snapshot the scanned repo as a
  manifest of `{relpath: sha256(bytes)}` over **non-ignored** files, **excluding**
  sanctioned derived artifacts: `.harpyja/` (and the XDG cache fallback dir),
  files matching the repo's ignore set, and any per-call temp/`trajectory_file`
  (which already resolves outside the repo). Compare content hashes only
  (mtime-only churn ignored). Assert byte-unchanged; record residual in-process
  write risk (symmetric to AC9's network-deny), no false-capability claim.
- **D6 — Air-gap before construct/spawn + TOCTOU close.** `assert_local(resolved
  FC_BASE_URL)` fires **before** the agent is constructed (Path A) **and before**
  the subprocess is spawned (Path B), through the **single** `gateway.assert_local`
  helper (never a parallel check). On Path A the lock is held across
  `assert_local` → env-set → construction → full run, closing the TOCTOU window.
- **D7 — Install portability.** Dependency is the local clone at SHA
  `1522d6d6b5e040e817b468e12826662aa069a8b0` via `uv add --editable <path>`. The
  absolute personal path is **non-portable**; recorded as an explicit Deviation
  (alongside the AC3 relaxation). CI/docs must reference the submodule-or-skip
  pattern, never `/Users/daniel.stolf/...`; vendoring as a git submodule is noted
  as the portable alternative (deferred — local-path editable kept for this wave).
- **D8 — `FASTCONTEXT_INSTALL.md`** is committed in this wave (currently untracked)
  as the spec's durable primary reference.

## Module map (new / touched)

- `harpyja/config/settings.py` — add `scout_model`, `scout_max_tokens`,
  `scout_temperature`, `scout_reasoning_effort` (additive, appended last).
- `harpyja/scout/errors.py` — add `FASTCONTEXT_MISSING = "fastcontext-missing"`,
  `CLI_MISSING = "cli-missing"`.
- `harpyja/scout/client.py` — **NEW.** `DefaultFastContextClient` (the real
  `FastContextClient`), the `FC_*` mapping + `_managed_fc_env` set-then-restore
  context manager, `_run_coro_on_worker_thread`, `_SCOUT_ENV_LOCK`, the Path A/B
  state machine, and `parse_final_answer` (`<final_answer>` → raw `CodeSpan`s).
- `harpyja/scout/wiring.py` — **NEW.** `build_scout_engine(settings, repo_path)`
  (the production `scout_factory`, mirrors `deep/wiring.py`): wires the default
  client into `FastContextBackend` + a Tier-0 `seed_fn` + `ScoutEngine`.
- `harpyja/scout/test_fastcontext_client.py` — **NEW** unit tests (AC2,3,4,5,6,7,10).
- `harpyja/config/test_settings.py` — extend (scout field defaults + precedence).
- `harpyja/scout/test_scout_integration.py` — extend (AC1, AC8, AC9, AC11).

## Test-first sequence

### Step 1 — Commit reference + dependency (setup, no test)
- Commit `FASTCONTEXT_INSTALL.md` (D8) so the spec's primary reference is durable.
- Add the FastContext dependency to `pyproject.toml` via local-path editable
  install at the pinned SHA (D7); initialize `third_party/mini-swe-agent` in the
  clone first. Record the absolute-path non-portability as an explicit Deviation;
  do not hardcode the personal path in CI.
- No behavior change — the suite still loads (lazy import only).

### Step 2 — Scout `Settings` fields (RED)
- Extend `harpyja/config/test_settings.py`:
  - `test_settings_scout_model_default` — `Settings().scout_model` equals the
    Ollama GGUF default `"hf.co/mitkox/FastContext-1.0-4B-RL-Q4_K_M-GGUF:latest"`,
    distinct from `lm_model`.
  - `test_settings_scout_fc_param_defaults` — `scout_max_tokens` / `scout_temperature`
    / `scout_reasoning_effort` defaults (`1024` / `"0"` / `"none"`).
  - `test_settings_scout_model_precedence` — `harpyja.toml` < `HARPYJA_SCOUT_MODEL`
    env < per-request override, via `load_settings` + `resolve_settings`.
- Tests fail: the fields do not exist on `Settings`.

### Step 3 — Scout `Settings` fields (GREEN)
- Append `scout_model`, `scout_max_tokens`, `scout_temperature`,
  `scout_reasoning_effort` (with defaults) **last** in the `Settings` dataclass.
- Step-2 tests pass; existing byte-reproducibility holds (additive-last convention).

### Step 4 — New degrade causes (RED)
- Add to `harpyja/scout/test_fastcontext_client.py`:
  - `test_scout_error_causes_are_distinct_identifiers` — imports
    `FASTCONTEXT_MISSING` / `CLI_MISSING` and asserts they equal
    `"fastcontext-missing"` / `"cli-missing"` and differ from the existing three.
- Tests fail: the constants are not defined in `errors.py`.

### Step 5 — New degrade causes (GREEN)
- Add `FASTCONTEXT_MISSING = "fastcontext-missing"` and `CLI_MISSING = "cli-missing"`
  to `harpyja/scout/errors.py`.
- Step-4 test passes.

### Step 6 — `FC_*` mapping + set-then-restore env guard (RED)
- Add to `test_fastcontext_client.py`:
  - `test_fc_env_maps_from_settings` — `_fc_env_from_settings(settings)` yields the
    full D3 table (`FC_MODEL←scout_model`, `FC_BASE_URL←lm_api_base`,
    `FC_API_KEY=="ollama"`, `FC_MAX_TOKENS`/`FC_TEMPERATURE`/`FC_REASONING_EFFORT`).
  - `test_fc_env_set_then_restore_preserves_unset` — a managed key absent before
    `_managed_fc_env` is absent again after.
  - `test_fc_env_set_then_restore_preserves_empty` — a managed key set to `""`
    before is restored to `""` (not deleted) after — unset-vs-empty preserved.
  - `test_fc_env_restored_on_exception` — values restored even when the guarded
    body raises.
- Tests fail: `harpyja/scout/client.py` / the helpers do not exist.

### Step 7 — `FC_*` mapping + env guard (GREEN)
- Create `harpyja/scout/client.py` with `_fc_env_from_settings` and the
  `_managed_fc_env` `contextmanager` (snapshot → set → `try/finally` restore,
  per-key unset-vs-empty).
- Step-6 tests pass.

### Step 8 — Path A in-process client: air-gap, trajectory, worker-thread bridge (RED)
- Add to `test_fastcontext_client.py` (driving an **injected fake** `agent_factory`
  whose fake agent exposes an `async run(...)`; no real package, no real model):
  - `test_client_asserts_local_before_agent_constructed` — a non-loopback
    `lm_api_base` raises `AirGapError` and the fake factory is **never called**
    (AC2, Path A).
  - `test_client_trajectory_file_outside_repo` — the fake factory captures
    `trajectory_file` + `work_dir`; assert `work_dir == repo` and
    `trajectory_file` resolves **outside** the repo (AC7).
  - `test_client_runs_agent_and_parses_final_answer` — fake `agent.run` returns a
    `<final_answer>` block with `path:line` refs; client returns the raw
    `CodeSpan`s via `parse_final_answer` (AC5 parse half; normalize half already
    covered by `test_scout.py` / `test_scout_normalize.py`).
  - `test_client_bridges_awaitable_from_running_loop` — invoke the client from
    **inside** an `asyncio.run(...)` context; it still returns (proves the
    loop-free worker thread, D1), where a naive `asyncio.run` would raise.
- Tests fail: `DefaultFastContextClient` / `parse_final_answer` /
  `_run_coro_on_worker_thread` not implemented.

### Step 9 — Path A in-process client (GREEN)
- Implement `DefaultFastContextClient.__call__(query, seed, tools)`:
  `assert_local(resolved FC_BASE_URL)` → build agent via the (lazy-imported or
  injected) factory with `work_dir=repo`, `trajectory_file=<temp outside repo>` →
  `_run_coro_on_worker_thread(agent.run(prompt, max_turns=n, citation=True))` →
  `parse_final_answer`. Lazy import only (mirrors `RlmBackend`).
- Step-8 tests pass.

### Step 10 — Single-flight lock + concurrency (RED)
- Add to `test_fastcontext_client.py`:
  - `test_client_holds_lock_across_full_agent_run` — the fake agent records
    `lock.locked()` **at construction AND at a simulated model-call boundary**
    inside `run` (the lazy `FC_REASONING_EFFORT` window); assert held at both
    (AC3 lock-span, review item f).
  - `test_parallel_scout_calls_no_fc_model_cross_contamination` — two threads with
    **different** `scout_model`, each fake factory records the `FC_MODEL` it
    observed at construction; assert each call saw its own value, zero crossover
    (AC4). Proves a `threading.Lock` serializes cross-thread `os.environ` writes.
- Tests fail: no lock; env not yet injected under the lock across the run.

### Step 11 — Single-flight lock + env injection under lock (GREEN)
- Add module-level `_SCOUT_ENV_LOCK = threading.Lock()`. Acquire it, then within
  it: `assert_local` → `_managed_fc_env(...)` → construct → `_run_coro_on_worker_thread`
  → restore (D2/D6). Lock spans the full run.
- Step-10 tests pass; Step-8/9 tests still pass.

### Step 12 — Path B CLI runner fallback (RED)
- Add to `test_fastcontext_client.py` (inject an `agent_factory` that raises
  `ImportError`, a fake `cli_runner`, and a fake `which`):
  - `test_client_path_b_drives_injected_runner` — runner is invoked with
    `cwd=repo`, `--traj <temp outside repo>`, `--citation`, a timeout; its
    `<final_answer>` is parsed (AC6); no real process spawned.
  - `test_client_path_b_asserts_local_before_spawn` — non-loopback URL →
    `AirGapError` and the runner is **never** invoked (AC2, Path B).
  - `test_client_path_b_env_scoped_to_child` — runner receives an `env` dict
    carrying `FC_*`; `os.environ` is **not** mutated (D2, Path B).
- Tests fail: Path B branch not implemented.

### Step 13 — Path B CLI runner fallback (GREEN)
- Implement the Path B branch behind the injected `cli_runner` (+ injected `which`,
  defaulting to `shutil.which`): `assert_local` → invoke runner with child `env=`
  (no parent mutation) → `parse_final_answer`.
- Step-12 tests pass.

### Step 14 — Fallback state machine + four distinct causes (RED)
- Add to `test_fastcontext_client.py`:
  - `test_client_fastcontext_missing_when_runner_unwired` — import fails,
    `cli_runner=None` → `ScoutUnavailable` with cause `fastcontext-missing` (D4
    terminal; AC10).
  - `test_client_cli_missing_when_binary_absent` — import fails, runner wired but
    `which("fastcontext")` is `None` → cause `cli-missing` (AC10).
  - `test_client_connection_refused_maps_cause` — fake `agent.run` raises a
    connection error → cause `connection-refused` (AC10).
  - `test_client_missing_fc_base_url_maps_no_endpoint` — factory raises
    `RuntimeError` naming `FC_BASE_URL` → cause `no-endpoint-configured` (D4).
  - `test_client_backend_error_wraps_runtimeerror` — factory raises a generic
    `RuntimeError` → cause `backend-error`, `__cause__` preserved (`raise ... from`).
  - `test_client_missing_rg_propagates_floor` — factory raises
    `RipgrepMissingError` → it **propagates** (not `ScoutUnavailable`) (AC10 floor).
  - `test_client_weak_citations_stay_honest_empty` — `agent.run` returns no
    parseable citation → client returns `[]`, no raise (AC10 honesty rule).
- Tests fail: the state machine / cause mapping not implemented.

### Step 15 — Fallback state machine + causes (GREEN)
- Implement the D4 import/PATH branch logic and the run-time exception → cause
  mapping (preserving `RipgrepMissingError` / `AirGapError` as the floor;
  wrap foreign exceptions `raise ... from err`).
- Step-14 tests pass.

### Step 16 — Production wiring factory (RED)
- Add `harpyja/scout/test_scout_wiring.py`:
  - `test_build_scout_engine_wires_default_client` — `build_scout_engine(settings,
    repo)` (with an injected factory to avoid the real import) returns a
    `ScoutEngine` whose backend delegates to a `DefaultFastContextClient` and whose
    `seed_fn` is the Tier-0 (symbol + ripgrep) composition; no model touched.
- Tests fail: `harpyja/scout/wiring.py` does not exist.

### Step 17 — Production wiring factory (GREEN)
- Create `harpyja/scout/wiring.py::build_scout_engine` (mirrors `deep/wiring.py`):
  resolve artifacts, build `RipgrepEngine` + `SymbolEngine` seed, `FastContextBackend`
  with the default client + loopback Gateway model client + bounded read/glob/grep,
  wrap in `ScoutEngine`. Suitable as the server `scout_factory`.
- Step-16 test passes. (Server already accepts a `scout_factory`; no seam change.)

### Step 18 — Integration: read-only, network-deny Path A, live flip (RED)
- Extend `harpyja/scout/test_scout_integration.py` (all `@pytest.mark.integration`,
  skip-not-fail when endpoint/package absent):
  - `test_scout_fast_path_a_leaves_repo_byte_unchanged` — end-to-end Path A run;
    D5 content-hash manifest before/after over non-ignored files excluding
    `.harpyja/` + temp/trajectory; assert byte-unchanged; comment records residual
    in-process write risk (AC8).
  - `test_scout_path_a_no_nonloopback_egress` — Wave-4 network-deny guard around an
    end-to-end Path A run; assert zero non-loopback connects (AC9).
  - Flip `test_scout_fast_returns_tier1_citations_live` — when FastContext imports
    and the loopback endpoint is reachable, assert a real `tiers_run=[0,1]` with
    `source_tier=1` citations; otherwise `skip` (AC1, AC11).
- Tests fail (or skip) before the client/wiring exist.

### Step 19 — Integration green (GREEN)
- With Steps 1–17 landed, the three integration tests pass when the environment is
  present and skip-not-fail otherwise. Wire `scout_factory=build_scout_engine` in
  the server assembly path if not already.

### Step 20 — Refactor (optional)
- Factor the shared `<final_answer>` / `path:line` citation parsing if it
  meaningfully duplicates `deep/rlm.py::parse_citations` (extract a small shared
  helper) — keep Tier-1 and Tier-2 otherwise structurally distinct.
- Tighten the `_managed_fc_env` per-key snapshot/restore for readability.
- All tests still pass.

## Acceptance-criteria → step map

| AC | kind | step(s) |
|----|------|---------|
| AC1  | integration | 18, 19 |
| AC2  | unit | 8 (Path A), 12 (Path B) |
| AC3  | unit | 6, 7, 10, 11 (mapping/precedence in 2/3) |
| AC4  | unit | 10, 11 |
| AC5  | unit | 8 (parse) + existing `test_scout(_normalize).py` (normalize) |
| AC6  | unit | 12, 13 |
| AC7  | unit | 8 |
| AC8  | integration | 18, 19 |
| AC9  | integration | 18, 19 |
| AC10 | unit | 4, 5, 14, 15 |
| AC11 | integration | 18, 19 |

## Delegation

- Steps 2–17 (unit RED/GREEN, settings, client, wiring) → `tdd-implementer`
  (reason: pure pytest + injection, deterministic, network-free; the core of the
  wave).
- Steps 8–15 (async worker-thread bridge, `threading.Lock` env single-flight,
  fallback state machine) → keep with a careful implementer; review item (a)/(c)
  concurrency correctness is the highest-risk surface and benefits from focused
  attention.
- Step 18–19 (integration: read-only manifest, network-deny, live flip) → delegate
  to the agent strongest on the existing `deep/test_deep_integration.py` patterns
  (reason: reuses the Wave-4 network-deny + assumption-verified-by-test scaffolding).

## Risk

- **`asyncio.run` from a running MCP loop** → mitigation: D1 worker-thread bridge
  proven by `test_client_bridges_awaitable_from_running_loop` (invoked from inside
  an event loop).
- **`asyncio.Lock` would silently fail to serialize cross-thread `os.environ`** →
  mitigation: `threading.Lock` named in D1, proven by the parallel-threads AC4 test
  (not a coroutine test).
- **Leaked `FC_*` env for other in-process readers** → mitigation: D2 set-then-restore
  with unset-vs-empty preservation, proven by Step-6 tests; residual staleness is
  harmless for Scout (every call re-sets all keys) and recorded.
- **`fastcontext-missing` unreachable as a terminal cause** → mitigation: D4 makes
  it terminal exactly when the CLI runner is unwired (`None`), tested in Step 14.
- **AC8 byte-unchanged ambiguity** → mitigation: D5 explicit exclusion list
  (`.harpyja/`, ignored, temp/trajectory) + content-hash-only comparison.
- **In-process Read/Glob/Grep can still write/egress (honest limit)** → mitigation:
  assumption-verified-by-test (AC8 read-only, AC9 network-deny) with residual risk
  recorded — never an asserted guarantee.
- **Local-path absolute install non-portable in CI** → mitigation: D7 records it as
  an explicit Deviation; submodule vendoring noted as the portable follow-up; CI
  must not reference the personal path.
