---
spec: "0006"
status: planned
strategy: tdd
---

# Plan — 0006 Wave 4 — Deep (RLM)

## Overview / approach

Wave 4 lands **Tier 2 (Deep)**: a `dspy.RLM` explorer driven through bounded,
read-only host tools inside a host-terminable sandbox, reached only via
`mode=deep`. The `harpyja/deep/` package is empty (only `__init__.py`), so this
plan **mirrors the live `harpyja/scout/` structure** (backend Protocol → engine
behind the shared `Locator` `.search` seam → normalize → injected backend) and
**extends** four existing files (`config/settings.py`, `scout/normalize.py`,
`orchestrator/locate.py`, `server/app.py`). It recreates nothing.

Every unit test is network-/process-/model-free via injected collaborators: a
fake `DeepBackend`, an injected runner, direct host-tool calls, and a
`_BoomDeep` double that raises if touched on a non-deep path. Async (if any) is
driven with `asyncio.run`, never `pytest-asyncio`. The bounds are enforced and
tested at **different seams**: tool-calls (wrapper counter) and tokens (Gateway
counter) are **unit**-testable; wall-clock requires the host-terminable
**subprocess** and is the only `@pytest.mark.integration` mechanism test in the
core. The four genuinely-live ACs (8b, 10a, 11, 12) are `@pytest.mark.integration`
and **skip-not-fail** when `dspy`/`deno`/endpoint are absent.

The wave is sequenced so the Tier-0 floor and `auto` byte-identity are
regression-locked, the Deep machinery is built bottom-up behind its Protocol, and
the **lockstep guard inversion ships in the same change as routing + impl**
(P7) — the suite never holds both the old "no Tier-2 marker" and the new
"Tier-2 marker present" assertions.

## Reconciliation decisions (spec ↔ existing code)

1. **Lockstep inversion (AC2a) is atomic.** `orchestrator/test_locate.py` holds
   two Wave-3 provisional guards — `test_locate_deep_attaches_pending_note` and
   `test_locate_deep_no_tier2_marker` — that assert the *opposite* of what 0006
   ships. They are **deleted and inverted in the same RED step (P7/Step 20)** that
   adds the routing+impl GREEN (Step 21). The suite cannot hold both sides.

2. **`DeepEngine` dual surface.** The engine exposes `.search(query, scope) ->
   list[CodeSpan]` for `Locator` conformance (so the orchestrator/formatter never
   branch on `DeepBackend`, AC1) **and** a richer `run(query, seed) -> (citations,
   truncated_bound | None)` that the orchestrator's deep branch consumes — because
   `deep-truncated:<bound>` is metadata the bare `list[CodeSpan]` `.search`
   contract cannot carry. Both are stated explicitly and both are tested.

3. **`normalize_spans` generalization.** `scout/normalize.py` reads
   `settings.scout_max_citations` / `scout_max_span_lines` **hardcoded**. Deep
   needs the *same* hostile-output clamp with `deep_*` values (AC9). Decision:
   parameterize `normalize_spans` with explicit `max_citations` / `max_span_lines`
   args and keep a **thin Scout-compat wrapper** so every Scout call site stays
   byte-green; Deep calls it with `deep_*`. `source_tier` is **not** carried here
   (CodeSpan has no `source_tier` — Wave-3 reconciliation): the tier is set once
   at the `format_citations` boundary (`source_tier=2` in the deep branch), so
   AC9's clamp is asserted at normalize/engine and AC1's `source_tier==2` at the
   orchestrator.

4. **Bound enforcement is layered & tested at different seams.**
   `deep_max_tool_calls` (wrapper counter) and `deep_token_ceiling` (Gateway
   counter) are **unit**-testable with no process; `deep_wall_clock_ms` requires
   the **host-terminable subprocess** (a same-thread deadline can't fire during a
   synchronous busy loop) and that test is `@pytest.mark.integration`;
   `deep_max_depth` / `deep_max_subqueries` are host-mediated at the spawn seam
   with **recorded residual risk** (if `dspy.RLM` won't expose a hook they become
   cooperative) and are **transitively contained** by the external trio. The
   `deep-truncated:<bound>` note plumbing (given a `truncated_bound`) is
   unit-testable with a fake backend.

5. **Degradation reuses `_locate_scout`.** `DeepUnavailable(<cause>)` → Scout
   best-effort by **calling the existing `_locate_scout` path** and **prepending**
   a stable `deep-degraded:<cause>` note. `tiers_run` is whatever Scout returns:
   `[0,1]` on Scout success, `[0]` on double-degrade carrying **both**
   `deep-degraded:<cause>` and `scout-degraded:<cause>` (AC5). The deep branch
   **never** degrades on weak/zero citations (AC5/5a — that's an honest Tier-2
   result); only typed `DeepUnavailable` degrades. `RipgrepMissingError` (seed,
   runs first) and `AirGapError` propagate as the floor (AC6).

6. **`_DEEP_PENDING` is deleted.** Removing `"deep"` from `_SCOUT_MODES` (→
   `{"fast"}`) drops the provisional deep→Scout note and the deep handling inside
   `_degrade` (which becomes Scout-only).

7. **Path confinement reuses `server/tools.confine_path`.** The host tools reuse
   the existing `confine_path(repo_path, path)` guard (symlink-aware
   `relative_to(repo_root)` check) rather than re-implementing it; over-budget
   requests reuse the existing `read_snippet` / `RipgrepEngine` / `read_manifest`
   clamps.

8. **Deep is not cached.** Model-backed/non-deterministic; **no** engine-identity
   or cache slot, exactly like Scout. No cache-slot lockstep test; the lockstep
   invariant is the Tier-2-marker inversion (AC2a).

## Test-first sequence

### Phase 1 — Settings + `normalize_spans` generalization

#### Step 1 — Deep budget settings (RED)
- Add to `harpyja/config/test_settings.py`:
  - `test_settings_deep_defaults` — `deep_seed_top_n==5`, `deep_max_citations==20`,
    `deep_max_span_lines==200`, `deep_max_depth==3`, `deep_max_subqueries==8`,
    `deep_max_tool_calls==200`, `deep_token_ceiling==32000`, `deep_wall_clock_ms==60000`.
  - `test_settings_deep_loads_from_toml` — toml keys override, coerced to int.
  - `test_settings_deep_loads_from_env` — `HARPYJA_DEEP_*` env overrides toml.
- Fails: the `deep_*` fields don't exist on `Settings`. [AC: budgets behind AC10]

#### Step 2 — append Deep fields to `Settings` (GREEN)
- Edit `harpyja/config/settings.py`: append (last, with defaults) the eight
  `deep_*` fields. `_coerce` already handles `int`.
- Step-1 tests pass; existing settings tests untouched. [AC10]

#### Step 3 — generalize `normalize_spans` to explicit budgets (RED)
- Add to `harpyja/scout/test_scout_normalize.py`:
  - `test_normalize_spans_honors_explicit_deep_budgets` — calling `normalize_spans`
    with explicit `max_citations`/`max_span_lines` set to the `deep_*` values
    clamps count and per-span line range to *those* values (not the Scout ones).
- Fails: `normalize_spans(raw, repo_root, settings)` only reads `scout_*`
  hardcoded; it has no explicit-budget parameters. [AC9]

#### Step 4 — parameterize `normalize_spans` + Scout-compat wrapper (GREEN)
- Edit `harpyja/scout/normalize.py`: change the core to
  `normalize_spans(raw, repo_root, *, max_citations, max_span_lines)`; keep a
  thin `normalize_spans_for_scout(raw, repo_root, settings)` (or a defaulted
  overload) that forwards `settings.scout_*`. Update `scout/engine.py`'s call
  site to the wrapper.
- Step-3 test passes; **all existing Scout normalize + engine tests stay green
  (byte-identical clamp for `scout_*`)**. [AC9]

### Phase 2 — Deep errors / backend / budget

#### Step 5 — `DeepUnavailable` stable causes (RED)
- Add `harpyja/deep/test_deep.py`:
  - `test_deep_unavailable_carries_stable_cause` — `DeepUnavailable("rlm-down").cause
    == "rlm-down"`; the three cause constants are `{sandbox-absent, rlm-down,
    backend-error}`; preserves the wrapped cause via `raise ... from err`.
- Fails: `harpyja/deep/errors.py` does not exist. [AC5, AC5a]

#### Step 6 — implement `deep/errors.py` (GREEN)
- Add `harpyja/deep/errors.py`: `DeepUnavailable(RuntimeError)` with `.cause` and
  stable constants `SANDBOX_ABSENT="sandbox-absent"`, `RLM_DOWN="rlm-down"`,
  `BACKEND_ERROR="backend-error"` (mirror `scout/errors.py`). A budget truncation
  is documented as **not** a `DeepUnavailable`.
- Step-5 test passes. [AC5, AC5a]

#### Step 7 — `DeepBackend` Protocol (RED)
- Add to `harpyja/deep/test_deep.py`:
  - `test_deep_backend_protocol_accepts_fake` — a fake exposing
    `run(query, seed, tools) -> list[CodeSpan]` is a structural `DeepBackend`;
    injected with no live model/sandbox (same DI seam as `scout_engine`).
- Fails: `harpyja/deep/backend.py` does not exist. [AC4]

#### Step 8 — implement `DeepBackend` Protocol (GREEN)
- Add `harpyja/deep/backend.py`: `DeepBackend` Protocol —
  `run(query: str, seed: list[CodeSpan], tools: Mapping) -> list[CodeSpan]`
  (mirror `scout/backend.py`; output untrusted, normalized by the caller).
- Step-7 test passes. [AC4]

#### Step 9 — `DeepBudget` meter (RED)
- Add to `harpyja/deep/test_deep.py`:
  - `test_budget_tool_calls_stops_after_max` — past `deep_max_tool_calls` the meter
    reports exhausted and records `truncated_bound == "tool-calls"`.
  - `test_budget_token_ceiling_blocks_completion` — past `deep_token_ceiling` the
    meter refuses further token spend, `truncated_bound == "tokens"`.
  - `test_budget_depth_subqueries_cap_at_spawn_seam` — depth/subquery counters cap
    at `deep_max_depth` / `deep_max_subqueries`, `truncated_bound in {"depth",
    "subqueries"}`.
  - `test_budget_truncated_bound_none_when_unexhausted` — no bound fired → `None`.
- Fails: `harpyja/deep/budget.py` does not exist. [AC10]

#### Step 10 — implement `DeepBudget` (GREEN)
- Add `harpyja/deep/budget.py`: a pure-Python per-request meter tracking
  tool_calls / tokens / depth / subqueries / wall-clock against the `deep_max_*`
  caps, exposing `charge_*`/`can_*` predicates and a `truncated_bound: str | None`.
  Externally-enforced counters are unit-testable with no process.
- Step-9 tests pass. [AC10]

### Phase 3 — Host tools (confinement + clamps + read-only + whitelist)

#### Step 11 — bounded read-only host tools (RED)
- Add `harpyja/deep/test_host_tools.py`:
  - `test_read_span_rejects_path_outside_repo` — a `../` / absolute path is rejected.
  - `test_read_span_clamps_over_budget_lines_chars` — request beyond
    `tool_max_lines`/`tool_max_chars` is clamped, not honored.
  - `test_search_confines_scope_to_repo_root` — a scope outside the repo is rejected.
  - `test_search_clamps_max_matches_and_files` — bounded by `search_max_matches` /
    `search_max_files`.
  - `test_symbols_rejects_path_outside_repo` — `path` outside the repo is rejected.
  - `test_list_manifest_bounded_by_manifest_page` — page-bounded by `manifest_page`.
  - `test_host_tools_surface_is_read_only` — the tool dict exposes **no** write/
    edit/delete operation (asserted on the surface).
  - `test_host_tools_whitelist_exact_equality` — **positive equality**:
    `set(build_host_tools(...).keys()) == {"list_manifest","search","symbols",
    "read_span"}` and nothing else (deno-less backstop for AC8a).
- Fails: `harpyja/deep/host_tools.py` does not exist. [AC7, AC8, AC8a]

#### Step 12 — implement `build_host_tools` (GREEN)
- Add `harpyja/deep/host_tools.py`: `build_host_tools(repo_path, settings, engine,
  symbol_engine, budget) -> dict` exposing **exactly**
  `{list_manifest, search, symbols, read_span}`, each a thin wrapper over existing
  machinery — `list_manifest`→`read_manifest` (page-bounded), `search`→
  `RipgrepEngine` (scope-confined, `search_max_*`-bounded), `symbols`→symbol index
  for one confined file, `read_span`→`read_snippet` (`tool_max_*`-bounded). Reuse
  `server/tools.confine_path` for confinement; each wrapper consults `budget`
  (stop dispatching past `deep_max_tool_calls`). No mutating op exists.
- Step-11 tests pass. [AC7, AC8, AC8a]

### Phase 4 — Host-terminable runner + wall-clock

#### Step 13 — runner contract (counter facet, unit) (RED)
- Add to `harpyja/deep/test_deep.py`:
  - `test_runner_invokes_target_and_returns_spans` — the runner executes an
    injected target and returns its `list[CodeSpan]` (in-process facet).
  - `test_runner_surfaces_truncated_bound_from_budget` — when the target hits a
    counter bound, the runner returns the gathered spans **and** the
    `truncated_bound`, never raising `DeepUnavailable`.
- Fails: `harpyja/deep/runner.py` does not exist. [AC10]

#### Step 14 — implement `DeepRunner` (GREEN)
- Add `harpyja/deep/runner.py`: the host-terminable out-of-band execution boundary.
  Counter bounds (tool-calls/tokens/depth/subqueries) flow through the in-process
  facet (testable with no subprocess); `deep_wall_clock_ms` is enforced by **hard
  termination** of an out-of-band worker (subprocess the host can kill) — never
  cooperative cancellation. Designed so the same boundary later hosts the real
  RLM/Deno sandbox.
- Step-13 tests pass. [AC10]

#### Step 15 — wall-clock hard-kills a non-yielding busy loop (RED → integration)
- Add `harpyja/deep/test_deep_integration.py`:
  - `test_runner_hard_kills_nonyielding_busy_loop_on_wall_clock` —
    `@pytest.mark.integration`; spawns a **real subprocess** running a genuine
    `while True: pass` (not a cooperative `sleep`); the host deadline kills it and
    the run returns `deep-truncated:wall-clock` with gathered citations and **no**
    `DeepUnavailable`. The harness itself must not hang.
- Green once the Step-14 runner subprocess kill is assembled. [AC10 wall-clock]

### Phase 5 — `DeepEngine` (seed + normalize + dual surface)

#### Step 16 — DeepEngine self-seed, dual surface, typed-only failure (RED)
- Add to `harpyja/deep/test_deep.py`:
  - `test_deep_engine_seeds_before_backend` — the seed callable runs before
    `backend.run` (order recorded by a fake).
  - `test_deep_engine_passes_top_n_seed_hints` — exactly `deep_seed_top_n` seed
    spans (rank order) reach the fake backend as hints.
  - `test_deep_engine_seed_precondition_error_propagates` — a seed
    `RipgrepMissingError` propagates and the backend is **never** called.
  - `test_deep_engine_search_returns_normalized_codespans` — the `.search` Locator
    seam returns hostile-clamped `CodeSpan`s (deep budgets via the generalized
    `normalize_spans`).
  - `test_deep_engine_run_returns_citations_and_truncated_bound` — `run()` returns
    `(spans, truncated_bound)`; with a fake backend reporting a bound, the tuple
    carries it.
  - `test_deep_engine_raises_deep_unavailable_on_typed_infra_failure` — a backend
    raising a typed infra failure surfaces `DeepUnavailable(<cause>)`.
  - `test_deep_engine_weak_or_zero_output_not_unavailable` — a backend returning
    zero/weak citations returns an honest result and does **not** raise (AC5a, no
    ungated escalation).
- Fails: `harpyja/deep/engine.py` does not exist. [AC1, AC3, AC4, AC5, AC5a, AC9]

#### Step 17 — implement `DeepEngine` (GREEN)
- Add `harpyja/deep/engine.py`: `DeepEngine(backend, seed_fn, runner, settings,
  repo_root)`. Self-seeds Tier-0 (`seed_fn`) **before** the backend (floor
  ordering; seed errors propagate); runs the backend via the runner with a
  `DeepBudget` and the host-tool whitelist; normalizes output via
  `normalize_spans(..., max_citations=deep_max_citations,
  max_span_lines=deep_max_span_lines)`. Exposes `.search(query, scope) ->
  list[CodeSpan]` (Locator) **and** `run(query, seed) -> (spans, truncated_bound)`.
  Raises `DeepUnavailable` **only** for typed infra failure.
- Step-16 tests pass. [AC1, AC3, AC4, AC5, AC5a, AC9]

### Phase 6 — `RlmBackend` (injected, no hard import)

#### Step 18 — RlmBackend delegates to an injected runner via the Gateway (RED)
- Add to `harpyja/deep/test_deep.py`:
  - `test_rlm_backend_delegates_to_injected_runner` — `RlmBackend` with an injected
    runner/`dspy` stand-in forwards query + seed hints + the four-tool whitelist
    and returns its spans, with **no live model/sandbox** and **no top-level
    `import dspy`** (the module imports cleanly when `dspy` is absent).
  - `test_rlm_backend_fresh_instance_per_request` — two `run` calls construct two
    distinct RLM instances (not thread-safe with a custom interpreter).
  - `test_rlm_backend_drives_model_through_gateway_complete` — model I/O goes only
    through `gateway.complete` (single air-gap helper, AC6).
- Fails: `harpyja/deep/rlm.py` does not exist. [AC4, AC6]

#### Step 19 — implement `RlmBackend` (GREEN)
- Add `harpyja/deep/rlm.py`: `RlmBackend` implementing `DeepBackend` via an
  **injected** runner — **no** top-level `import dspy` (mirror
  `scout/fastcontext.py`); constructs a **fresh** `dspy.RLM` per request; drives
  the explorer model strictly through `gateway.complete`; sandbox isolation lives
  at this boundary.
- Step-18 tests pass; the suite still imports with `dspy`/`deno` absent. [AC4, AC6]

### Phase 7 — Orchestrator deep routing + degradation + LOCKSTEP INVERSION

#### Step 20 — invert the lockstep guard + lock the deep branch (RED)
- Edit `harpyja/orchestrator/test_locate.py`:
  - **DELETE** `test_locate_deep_attaches_pending_note` and
    `test_locate_deep_no_tier2_marker` (they assert the inverse of 0006 — AC2a).
  - Add Deep doubles mirroring the Scout ones: `_FakeDeep` (records hints; can
    report a `truncated_bound`), `_UnavailableDeep(cause)`, `_BoomDeep` (raises if
    consulted).
  - Add:
    - `test_locate_deep_emits_tier2_marker_when_wired` — `mode=deep` with an
      injected `deep_engine` → `tiers_run == [0, 2]`, citations `source_tier == 2`.
      [AC1, AC2a]
    - `test_locate_deep_passes_top_n_seed_hints_to_backend` — the deep path seeds
      Tier-0 and hands `deep_seed_top_n` hints to the backend. [AC3]
    - `test_locate_deep_seed_rg_missing_propagates_backend_never_called` —
      `RipgrepMissingError` from the seed propagates; the backend is never called.
      [AC3, AC6]
    - `test_locate_deep_unavailable_degrades_to_scout` — `DeepUnavailable(cause)` →
      Scout best-effort, note **prepended** `deep-degraded:<cause>`,
      `tiers_run == [0, 1]` on Scout success. [AC5]
    - `test_locate_deep_double_degrade_carries_both_notes` — Deep down + model also
      down → `tiers_run == [0]`, notes carry **both** `deep-degraded:<cause>` and
      `scout-degraded:<cause>`. [AC5]
    - `test_locate_deep_distinct_cause_notes` — the three causes yield distinct
      `deep-degraded:<cause>` notes. [AC5]
    - `test_locate_deep_weak_or_zero_citations_stay_tier2` — a successful Deep run
      returning zero/weak citations → `tiers_run == [0, 2]`, **no** fallback.
      [AC5, AC5a]
    - `test_locate_deep_airgap_propagates` — `AirGapError` propagates, **not** a
      degrade note. [AC6]
    - `test_locate_deep_truncated_note_plumbed` — a backend reporting a
      `truncated_bound` → result carries `deep-truncated:<bound>`, **not** a
      `DeepUnavailable`. [AC10]
    - `test_locate_auto_makes_zero_deep_calls` — `_BoomDeep` injected; `mode=auto`
      stays byte-identical and never touches Deep. [AC2, AC13]
    - `test_locate_fast_makes_zero_deep_calls` — `mode=fast` still routes to Scout
      and never touches `_BoomDeep`. [AC2, AC13]
- Fails: `locate` has no `deep_engine` param / no deep branch; `_DEEP_PENDING`
  still present; the deleted guards' inverse is now asserted. [AC1, AC2, AC2a,
  AC3, AC5, AC5a, AC6, AC10, AC13]

#### Step 21 — implement deep routing + degradation, delete `_DEEP_PENDING` (GREEN)
- Edit `harpyja/orchestrator/locate.py`:
  - Remove `"deep"` from `_SCOUT_MODES` (→ `{"fast"}`); **delete** `_DEEP_PENDING`
    and all its uses (the provisional deep→Scout note and the `deep` handling in
    `_degrade`, which becomes Scout-only).
  - Add a `deep_engine: _Engine | None = None` DI param; add
    `if req.mode == "deep": return _locate_deep(...)`.
  - Implement `_locate_deep(...)` mirroring `_locate_scout`: self-seed Tier-0
    (top `deep_seed_top_n`); if `deep_engine is None` degrade honestly; else call
    `deep_engine.run(query, seed)`; on `DeepUnavailable` degrade by **calling
    `_locate_scout(...)`** and **prepending** `deep-degraded:<cause>` (so
    `tiers_run` is Scout's `[0,1]`/`[0]` per AC5); on success build
    `LocateResult(citations source_tier=2, tiers_run=[0,2], notes=<deep-truncated:
    bound if any>)`. `RipgrepMissingError` (seed) and `AirGapError` propagate;
    **never** degrade on weak/zero citations. Preserve cause with `raise ... from
    err` where re-raising.
- Step-20 tests pass; all Wave-1/2/3 `test_locate.py` tests still green. [AC1,
  AC2, AC2a, AC3, AC5, AC5a, AC6, AC10, AC13]

### Phase 8 — Server wiring

#### Step 22 — `build_app` Deep wiring (RED)
- Add to `harpyja/server/test_app.py`:
  - `test_build_app_deep_uses_deep_engine` — `harpyja_locate(mode="deep")` with an
    injected `deep_factory` constructs/injects the `deep_engine` into `locate`
    (result carries `2 in tiers_run`).
  - `test_build_app_auto_makes_zero_deep_calls` — a `_BoomDeep` factory; `mode=auto`
    never calls it.
  - `test_build_app_fast_makes_zero_deep_calls` — `mode=fast` (Scout) never calls
    the `_BoomDeep` factory.
- Fails: `build_app` has no `deep_factory` param. [AC2, AC13]

#### Step 23 — wire `deep_factory` into `build_app` (GREEN)
- Edit `harpyja/server/app.py`: add a `deep_factory: Callable[[Settings, str],
  Any] | None = None` param (same style as `scout_factory`); inject
  `deep_engine = deep_factory(settings, repo_path) if deep_factory else None` into
  `locate`. `auto`/`fast` make zero Deep calls.
- Step-22 tests pass; existing `test_app.py` (auto zero-gateway, fast→Scout) stay
  green. [AC2, AC13]

### Phase 9 — Integration ACs (skip-not-fail)

#### Step 24 — live sandbox / runaway / network-deny / end-to-end (RED → integration)
- Add to `harpyja/deep/test_deep_integration.py` (all `@pytest.mark.integration`,
  skip-not-fail when `dspy`/`deno`/endpoint absent):
  - `test_deep_sandbox_exposes_only_four_tools` — in the **real** sandbox an
    in-sandbox `open()` of a path **outside** the repo, an `open()` of a path
    **inside** the repo (would bypass `read_span`'s clamps — a fifth unbounded
    capability), and a raw `socket` / `import socket` attempt **all fail**; the
    residual runtime-change risk + verification method are recorded. [AC8b]
  - `test_deep_real_runaway_terminates_with_truncated_note` — a real RLM/sandbox
    driven to recurse/spin without bound is halted by the host (wall-clock /
    tool-call / token deadline) and returns a `deep-truncated:<bound>` result.
    [AC10a]
  - `test_deep_runs_under_network_deny_loopback_only` — Deep runs to completion
    under a network-deny environment with a loopback-only Gateway; the model path
    needs no non-loopback egress and the sandbox runs offline. [AC12]
  - `test_deep_end_to_end_live` — `mode=deep` end-to-end against a live RLM +
    sandbox + endpoint. [AC11]
- Green on the assembled stack where `dspy`/`deno`/endpoint are available. [AC8b,
  AC10a, AC11, AC12]

## Delegation

- **Steps 1–4 (settings + `normalize_spans` generalization)** → keep in this
  thread; tightly coupled to the existing Scout clamp and its byte-green call
  sites.
- **Steps 5–17 (deep errors/backend/budget/host-tools/runner/engine)** → could
  delegate to a Python-focused implementer; fully isolated behind the
  `DeepBackend` Protocol + injected runner + fake backend, so the dspy/Deno open
  question never blocks the unit suite.
- **Steps 18–19 (`RlmBackend`)** → keep with whoever owns the dspy/Deno
  provisioning spike; the injected-runner / no-hard-import seam de-risks it.
- **Steps 20–21 (orchestrator + lockstep inversion)** → keep in this thread; the
  guard inversion must land atomically with routing+impl.
- **Step 15 + Step 24 (integration)** → run by whoever owns the live endpoint /
  Deno sandbox / network-deny CI lane.

## Risk

- **dspy package/version + Deno/Pyodide provisioning is the sole open question.**
  Mitigation: all unit behavior runs against a fake `DeepBackend` and an injected
  runner; `RlmBackend` has **no top-level `import dspy`** (Step 19), so its
  absence cannot break the suite; the live wiring is confined to the
  skip-not-fail integration ACs (Steps 15, 24).
- **Out-of-band, host-terminable execution mechanism.** `deep_wall_clock_ms` is
  only realizable if the backend runs in a preemptible context (subprocess/worker
  the host can hard-kill) — a same-thread deadline can't fire during a synchronous
  WASM busy loop. Mitigation: the runner (Step 14) splits the **counter facet**
  (unit-testable, no process) from the **wall-clock facet** (subprocess hard-kill,
  integration Step 15 exercising a genuine non-yielding loop without hanging the
  harness). Depth/subqueries carry **recorded residual risk** and are transitively
  contained by the external trio.
- **Lockstep inversion ordering (AC2a).** Mitigation: the two Wave-3 guards are
  **deleted+inverted in the same RED (Step 20)** that precedes the routing+impl
  GREEN (Step 21) — the suite is never able to hold both the old "no Tier-2
  marker" and the new "Tier-2 marker present" assertions.
- **`auto`/`fast` byte-identity + zero Deep calls.** Mitigation: `_BoomDeep`
  doubles at both the orchestrator (Step 20) and server (Step 22) seams; the
  Wave-2/3 `test_locate.py` and `test_app.py` invariants are re-run after Step 21
  / Step 23.
- **Ungated escalation smuggled in as a "weak result" degrade.** Mitigation:
  explicit tests that zero/weak Deep citations stay an honest Tier-2 result
  (Steps 16, 20) and that only typed `DeepUnavailable` degrades (Steps 16, 20).
- **Silent truncation (false-capability claim).** Mitigation: the
  `deep-truncated:<bound>` note is unit-plumbed with a fake backend (Step 20) and
  proven against real bounds in integration (Steps 15, 24).

## AC-coverage matrix

| AC  | Type        | Steps (RED/GREEN) |
|-----|-------------|-------------------|
| AC1  | unit        | 16/17, 20/21 |
| AC2  | unit        | 20/21, 22/23 |
| AC2a | unit        | 20/21 (delete+invert) |
| AC3  | unit        | 16/17, 20/21 |
| AC4  | unit        | 7/8, 16/17, 18/19 |
| AC5  | unit        | 5/6, 16/17, 20/21 |
| AC5a | unit        | 5/6, 16/17, 20/21 |
| AC6  | unit        | 18/19, 20/21 (+ existing `gateway.assert_local`) |
| AC7  | unit        | 11/12 |
| AC8  | unit        | 11/12 |
| AC8a | unit        | 11/12 (positive equality) |
| AC8b | integration | 24 |
| AC9  | unit        | 3/4, 16/17 |
| AC10 | unit + integ| 9/10, 13/14, 20/21 (note) ; 15 (wall-clock) |
| AC10a| integration | 24 |
| AC11 | integration | 24 |
| AC12 | integration | 24 |
| AC13 | unit        | 20/21, 22/23 |
