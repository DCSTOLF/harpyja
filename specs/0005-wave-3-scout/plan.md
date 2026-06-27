---
spec: "0005"
status: planned
strategy: tdd
---

# Plan — 0005 Wave 3 — Scout

## Overview / approach

Wave 3 lands Tier 1 (Scout) and the Model Gateway request path. The package dirs
already hold real Wave 0/1/2 code, so this plan **extends** existing files and
adds the empty `harpyja/scout/` package — it does not recreate anything.

The whole wave is driven test-first with **injected collaborators** so every unit
test is network-free: a fake `resolver` (already in use), an injected HTTP
`transport` on the Gateway request path, a fake `ScoutBackend`, and a
failing-if-called Gateway double on the offline paths. Async (if any backend is
async) is driven from sync tests with `asyncio.run`, never `pytest-asyncio`.
The two `[integration]` ACs (AC1, AC11) are marked `@pytest.mark.integration`.

The work is sequenced so each tier of behavior is RED-locked before it is built,
and the `auto` path is regression-locked **byte-identical** before any routing is
added.

## Reconciliation decisions (spec ↔ existing code)

1. **`degraded` confidence.** `server/types.py` `Confidence` is
   `Literal["high","medium","low"]` with no `"degraded"`. The spec's degrade
   states 2/3 set `confidence = degraded`. Decision: **additively add
   `"degraded"`** to the `Confidence` Literal (Phase 1). Breaks nothing; existing
   values keep their meaning.

2. **`NonLoopbackEndpointError` → reuse `AirGapError`.** The spec names a typed
   air-gap error `NonLoopbackEndpointError`. The air-gap is enforced in **one
   place** (`gateway.assert_local`) per guardrails, and it already raises
   `AirGapError(ValueError)`. Decision: **do NOT introduce a new error type** —
   the Gateway request path reuses `AirGapError`. The spec's "stable, typed,
   actionable error that names the offending host, not a degrade note" intent is
   satisfied by `AirGapError` (the message already names the rejected endpoint).
   This is the single-air-gap-helper guardrail, made explicit.

3. **`source_tier` threading.** `CodeSpan` has no `source_tier` field; only
   `Citation` does, and `format.py` **hardcodes `source_tier=0`** on every
   Citation. Decision: add a `source_tier: int = 0` parameter to
   `format_citations`; the Scout path passes `source_tier=1`, the `auto`/Tier-0
   path keeps the default `0`. Normalization (`scout/normalize.py`) therefore
   works in `CodeSpan` space and does **not** carry the tier — the tier is set
   once, at the formatter boundary. AC1's "citations carry `source_tier=1`" is
   asserted both at the formatter and at the `locate(mode=fast)` boundary.

4. **Seed-helper factoring.** Tier-0 seeding (symbol + ripgrep composition) is
   needed by both `auto` and the Scout path (under `mode=fast` the caller skipped
   `auto`, so Scout must self-seed). Decision: factor a small `_tier0_seed(...)`
   helper in `locate.py` that returns the composed `list[CodeSpan]`; the `auto`
   branch and the `ScoutEngine`'s self-seed both call it. The `auto` branch must
   stay **byte-identical** (AC2 compares the serialized `LocateResult` incl.
   notes), so the refactor (T27) lands only after the byte-identical lock (T19)
   is green and is re-run against it.

5. **Scout is not cached.** Scout output is model-backed/non-deterministic and
   carries **no engine-identity / cache slot** (spec + conventions). No
   lockstep cache-slot test is required for Scout; the `mode=deep` lockstep guard
   (AC8) instead asserts the absence of any Tier-2 marker.

## Test-first sequence

### Phase 1 — types, settings, Gateway request path

#### Step 1 — `degraded` confidence value (RED)
- Add to `harpyja/server/test_types.py`:
  - `test_confidence_includes_degraded` — asserts `"degraded" in get_args(Confidence)`.
- Fails: the Literal has no `"degraded"` member yet. [AC5]

#### Step 2 — add `degraded` to the Literal (GREEN)
- Edit `harpyja/server/types.py`: `Confidence = Literal["high","medium","low","degraded"]`.
- Step-1 test passes. [AC5]

#### Step 3 — Scout budget settings (RED)
- Add to `harpyja/config/test_settings.py`:
  - `test_settings_scout_defaults` — `scout_seed_top_n==5`, `scout_max_citations==20`, `scout_max_span_lines==200`.
  - `test_settings_scout_loads_from_toml` — toml keys override the defaults, coerced to int.
  - `test_settings_scout_loads_from_env` — `HARPYJA_SCOUT_*` env overrides toml.
- Fails: fields don't exist on `Settings`. [AC3, AC7]

#### Step 4 — add Scout fields to `Settings` (GREEN)
- Edit `harpyja/config/settings.py`: append (last, with defaults) `scout_seed_top_n: int = 5`, `scout_max_citations: int = 20`, `scout_max_span_lines: int = 200`. `_coerce` already handles int.
- Step-3 tests pass. [AC3, AC7]

#### Step 5 — Gateway request path (RED)
- Add to `harpyja/gateway/test_gateway.py`:
  - `test_gateway_complete_calls_injected_transport_for_loopback` — `ModelGateway(api_base="http://127.0.0.1:11434/v1").complete(...)` with an injected fake transport returns the parsed completion and records exactly one call.
  - `test_gateway_complete_asserts_local_before_send` — a `8.8.8.8` endpoint raises `AirGapError` and the injected transport is **never** called.
  - `test_gateway_complete_rejects_resolved_non_loopback` — a hostname endpoint whose injected `resolver` returns a routable IP raises `AirGapError` before the transport is touched (resolution-time air-gap on the request path).
- Fails: `ModelGateway` has no request method (file comment: "No request path yet"). [AC4]

#### Step 6 — implement the Gateway request path (GREEN)
- Edit `harpyja/gateway/gateway.py`: add `ModelGateway.complete(...)` (OpenAI-compatible chat/completions) that (1) calls `self.assert_local(resolver=resolver)` **before any I/O**, then (2) invokes an **injected** `transport`/client (default a thin stdlib client over the loopback endpoint). Reuse `AirGapError` (no new error type — see reconciliation #2).
- Step-5 tests pass; existing `test_gateway.py` air-gap tests still pass. [AC4]

### Phase 2 — Scout normalization + formatter tier threading

#### Step 7 — normalize hostile `<final_answer>` output (RED)
- Add `harpyja/scout/test_scout_normalize.py`:
  - `test_normalize_drops_path_outside_repo_root`
  - `test_normalize_drops_nonexistent_file`
  - `test_normalize_drops_inverted_line_range`
  - `test_normalize_drops_out_of_range_line`
  - `test_normalize_dedupes_duplicate_spans`
  - `test_normalize_clamps_over_max_citations` (> `scout_max_citations`)
  - `test_normalize_clamps_span_over_max_lines` (span > `scout_max_span_lines` clamped to first N lines)
- Fails: `scout/normalize.py` does not exist. [AC7]

#### Step 8 — implement `normalize_spans` (GREEN)
- Add `harpyja/scout/normalize.py`: `normalize_spans(raw, repo_root, settings) -> list[CodeSpan]` — drops paths outside `repo_root`, drops nonexistent files, drops inverted/out-of-range ranges, dedups identical spans, clamps to `min(scout_max_citations, ...)` count and clamps each span to `scout_max_span_lines`. Works in `CodeSpan` space (no `source_tier` here — see reconciliation #3).
- Step-7 tests pass. [AC7]

#### Step 9 — formatter `source_tier` threading (RED)
- Add to `harpyja/orchestrator/test_formatter.py`:
  - `test_format_citations_threads_source_tier_one` — `format_citations(..., source_tier=1)` yields citations with `source_tier==1`.
  - `test_format_citations_defaults_source_tier_zero` — default call still yields `source_tier==0`.
- Fails: `format_citations` has no `source_tier` parameter (it hardcodes `0`). [AC1]

#### Step 10 — add `source_tier` param to `format_citations` (GREEN)
- Edit `harpyja/orchestrator/format.py`: add `source_tier: int = 0` param; use it in the `Citation(...)` construction instead of the hardcoded `0`.
- Step-9 tests pass; existing formatter tests still pass (default `0`). [AC1]

### Phase 3 — Scout backend + engine (self-seed)

#### Step 11 — ScoutEngine self-seeds before backend, passes top-N hints (RED)
- Add `harpyja/scout/test_scout.py`:
  - `test_scout_engine_seeds_before_backend` — a fake backend records the order; the seed callable is invoked before `backend.run`.
  - `test_scout_engine_passes_top_n_hints` — exactly `scout_seed_top_n` seed spans (in formatter rank order) reach the fake backend.
  - `test_scout_engine_seed_precondition_error_propagates` — a seed callable raising `RipgrepMissingError` propagates and the backend is **never** called (ordering → state 4).
- Fails: `scout/engine.py` / `scout/backend.py` don't exist. [AC3, AC5, AC6]

#### Step 12 — implement `ScoutBackend` Protocol + `ScoutEngine` (GREEN)
- Add `harpyja/scout/backend.py`: `ScoutBackend` Protocol — `run(query, seed: list[CodeSpan]) -> list[CodeSpan]`.
- Add `harpyja/scout/engine.py`: `ScoutEngine` exposes `.search(pattern, scope=None)` (the shared `Locator`/`_Engine` seam), constructed with `(backend, seed_fn, settings, repo_root)`. `.search` calls `seed_fn(query)` **first**, slices top-`scout_seed_top_n`, then `backend.run`. Seed errors propagate (no try/except around `seed_fn`).
- Step-11 tests pass. [AC3, AC6]

#### Step 13 — ScoutEngine normalizes backend output (RED)
- Add to `harpyja/scout/test_scout.py`:
  - `test_scout_engine_normalizes_hostile_output` — a fake backend returns out-of-budget / out-of-root spans; the engine returns only normalized, in-budget `CodeSpan`s.
- Fails: `ScoutEngine.search` returns backend output un-normalized. [AC7]

#### Step 14 — wire `normalize_spans` into `ScoutEngine` (GREEN)
- Edit `harpyja/scout/engine.py`: pass `backend.run(...)` output through `normalize_spans(raw, repo_root, settings)` before returning.
- Step-13 test passes. [AC7]

#### Step 15 — exact tool whitelist handed to FastContext (RED)
- Add to `harpyja/scout/test_scout.py`:
  - `test_build_tool_whitelist_exact_set` — positive equality: the tool object graph equals `{Read wrapper, Glob wrapper, Grep wrapper, Gateway model client}` and nothing else (no raw `base_url`, no env-derived endpoint, no HTTP client/session).
- Fails: `scout/tools.py` does not exist. [AC10]

#### Step 16 — implement `build_tool_whitelist` (GREEN)
- Add `harpyja/scout/tools.py`: `build_tool_whitelist(gateway_client, read, glob, grep) -> Mapping` returning exactly the four entries.
- Step-15 test passes. [AC10]

#### Step 17 — FastContext backend delegates to an injected client (RED)
- Add to `harpyja/scout/test_scout.py`:
  - `test_fastcontext_backend_delegates_to_injected_client` — `FastContextBackend(run via an injected fake fastcontext client).run(query, seed)` forwards query + seed hints + the tool whitelist to the injected client and returns its `<final_answer>`-shaped spans, with **no live model**.
- Fails: `scout/fastcontext.py` does not exist. [AC6, AC10]

#### Step 18 — implement `FastContextBackend` behind the Protocol (GREEN)
- Add `harpyja/scout/fastcontext.py`: `FastContextBackend` implementing `ScoutBackend`, taking an **injected** FastContext client/runner (the actual package+version is the sole Open Question; the Protocol + injected client de-risk its absence — no top-level hard import that blocks the suite). It assembles the tool whitelist via `build_tool_whitelist` and delegates.
- Step-17 test passes. [AC6]

### Phase 4 — orchestrator mode routing + degradation

#### Step 19 — `auto` byte-identical + zero Gateway calls (RED, regression lock)
- Add to `harpyja/orchestrator/test_locate.py`:
  - `test_locate_auto_byte_identical_to_wave2` — `mode=auto` serialized `LocateResult` (citations + confidence + tiers_run + notes) equals the current Wave-2 output over the same fixture.
  - `test_locate_auto_makes_zero_gateway_calls` — a Gateway double that raises if called is passed in; `mode=auto` never calls it.
- Fails: `locate` does not yet accept the scout/gateway DI params (TypeError). [AC2, AC9]

#### Step 20 — add Scout/Gateway DI params to `locate`, `auto` untouched (GREEN)
- Edit `harpyja/orchestrator/locate.py`: add injected params `scout_engine: _Engine | None = None` and a gateway double pass-through (same DI style as `engine`/`symbol_engine`). The `auto` branch is **unchanged** (still `tiers_run=[0]`, same notes incl. `_MODE_NO_EFFECT`).
- Step-19 tests pass. [AC2, AC9]

#### Step 21 — `mode=fast` routes to Scout (RED)
- Add to `harpyja/orchestrator/test_locate.py`:
  - `test_locate_fast_routes_to_scout` — with a fake scout engine returning spans, citations come from Scout.
  - `test_locate_fast_tiers_run_includes_one` — `tiers_run == [0, 1]`.
  - `test_locate_fast_citations_source_tier_one` — Scout citations carry `source_tier == 1`.
- Fails: no `fast` branch; `mode` is still ignored (`_MODE_NO_EFFECT`). [AC1, AC3, AC6]

#### Step 22 — implement the `fast` Scout branch (GREEN)
- Edit `harpyja/orchestrator/locate.py`: when `mode in {"fast","deep"}`, run the Scout path — seed via the shared Tier-0 lookup, call `scout_engine.search`, `format_citations(..., source_tier=1)`, `tiers_run=[0,1]`. Leave `auto` byte-identical.
- Step-21 tests pass; Step-19 lock still green. [AC1, AC3, AC6]

#### Step 23 — four degradation states + distinct notes (RED)
- Add to `harpyja/orchestrator/test_locate.py`:
  - `test_locate_degraded_connection_refused` — Gateway refused + Tier-0 has results → `confidence=="degraded"`, `tiers_run==[0]`, note `scout-degraded:connection-refused`.
  - `test_locate_degraded_no_endpoint_configured` — note `scout-degraded:no-endpoint-configured`.
  - `test_locate_degraded_backend_error` — FastContext raised → note `scout-degraded:backend-error`.
  - `test_locate_degraded_empty_tier0_no_matches_suffix` — Gateway down + Tier-0 honestly empty → empty citations, distinct note suffixed `+no-matches`.
  - `test_locate_seed_precondition_error_propagates` — `rg` missing **and** model down → `RipgrepMissingError` propagates (not swallowed, not empty); state 4 wins by seed-before-backend ordering.
  - `test_locate_non_loopback_raises_airgap` — a resolved non-loopback endpoint raises `AirGapError`, **not** a degrade note.
- Fails: the Scout branch has no degradation handling. [AC5]

#### Step 24 — implement degradation handling (GREEN)
- Edit `harpyja/orchestrator/locate.py`: in the Scout branch, run the seed first (its `RipgrepMissingError` propagates). Wrap the backend/gateway call: on connection-refused / no-endpoint / backend-error, fall back to the **already-computed** Tier-0 seed citations with `confidence="degraded"`, `tiers_run=[0]`, and the matching stable note (`+no-matches` suffix when the seed is empty). Let `AirGapError` propagate (floor, not a note). Preserve cause with `raise ... from err` where re-raising.
- Step-23 tests pass. [AC5]

#### Step 25 — `mode=deep` lockstep guard (RED)
- Add to `harpyja/orchestrator/test_locate.py`:
  - `test_locate_deep_attaches_pending_note` — `mode=deep` routes to Scout and the notes contain a `Deep pending` marker.
  - `test_locate_deep_no_tier2_marker` — `2 not in tiers_run`, and the result exposes no Tier-2 identity/cache key (`fast` and `deep` behaviorally identical this wave).
- Fails: `deep` produces no pending note / not distinguished. [AC8]

#### Step 26 — implement `deep` provisional routing (GREEN)
- Edit `harpyja/orchestrator/locate.py`: `deep` == `fast` plus a stable `Deep pending` note; never adds `2` to `tiers_run` and creates no Tier-2 marker.
- Step-25 tests pass. [AC8]

#### Step 27 — Refactor: extract `_tier0_seed` (REFACTOR)
- Edit `harpyja/orchestrator/locate.py`: factor the symbol + ripgrep composition into `_tier0_seed(...)` called by both the `auto` branch and the Scout self-seed. Removes duplication introduced by Step 22.
- All tests still pass, including the Step-19 byte-identical lock. [AC2, AC3]

### Phase 5 — server wiring

#### Step 28 — `build_app` Scout/Gateway wiring (RED)
- Add to `harpyja/server/test_app.py`:
  - `test_build_app_auto_zero_gateway_calls` — `harpyja_locate(mode="auto")` end-to-end makes zero Gateway calls (Gateway double that fails if called).
  - `test_build_app_fast_uses_scout_engine` — `harpyja_locate(mode="fast")` constructs/injects the Scout engine (backed by a `ModelGateway`) into `locate`.
- Fails: `build_app` has no scout/gateway factory. [AC2, AC9]

#### Step 29 — wire Scout factory into `build_app` (GREEN)
- Edit `harpyja/server/app.py`: add a `scout_factory` / gateway wiring param (same injectable style as `engine_factory`); pass the constructed `scout_engine` into `locate`. `auto` stays gateway-free.
- Step-28 tests pass. [AC2, AC9]

### Phase 6 — integration ACs

#### Step 30 — AC1 live Scout (RED → green on assembled stack, integration)
- Add `harpyja/scout/test_scout_integration.py`:
  - `test_scout_fast_returns_tier1_citations_live` — `@pytest.mark.integration`, pinned fixture repo + query known to resolve; asserts `1 in tiers_run` and citations carry `source_tier==1`; a conceptual query that yields nothing from Tier-0 returns non-empty Scout citations. Skips (not fails) if the live endpoint is unreachable.
- Green once Phases 1–5 are assembled and an endpoint is available. [AC1]

#### Step 31 — AC11 network-deny (RED → green on assembled stack, integration)
- Add to `harpyja/scout/test_scout_integration.py`:
  - `test_scout_runs_under_network_deny` — `@pytest.mark.integration`, runs Scout to completion under a network-deny environment with a loopback-only Gateway endpoint, proving the model path needs no non-loopback egress.
- Green on the assembled stack under the network-deny env. [AC11]

## Delegation

- Steps 5–6 (Gateway request path) → keep in this thread; tightly coupled to the
  existing `assert_local` seam and `AirGapError` reuse.
- Steps 11–18 (Scout engine/backend/tools) → could delegate to a Python-focused
  implementer; isolated behind the `ScoutBackend` Protocol so the FastContext
  Open Question never blocks the suite.
- Steps 30–31 (integration) → run by whoever owns the live endpoint / network-deny
  CI lane.

## Risk

- **FastContext package + version unknown (sole Open Question).** Mitigation: all
  unit behavior runs against a fake `ScoutBackend`; `FastContextBackend` takes an
  injected client with no top-level hard import, so its absence cannot break the
  suite (Steps 12, 17–18).
- **`auto` byte-identical regression.** Mitigation: the byte-identical + zero-Gateway
  lock (Step 19) lands **before** any routing/refactor, and the `_tier0_seed`
  refactor (Step 27) is validated against it.
- **Degrade-state collapse (phantom "nothing found").** Mitigation: seed-before-backend
  ordering makes state 4 win by construction (Step 11 propagation test, Step 23
  ordering test); state 3 carries a distinct `+no-matches` note.
- **In-process FastContext egress side-channel.** Honest limit per spec: tool
  injection can't stop a third party opening its own socket. Mitigation: exact
  tool whitelist (Step 15) + network-deny integration test (Step 31); WASM/process
  sandbox tracked as a follow-up (out of scope).
- **AC1 model flakiness.** Mitigation: pinned fixture repo+query; deterministic
  shape assertions live in unit ACs; live test degrades to skip, not false failure.

## AC-coverage matrix

| AC | Type | Steps (RED/GREEN) |
|----|------|-------------------|
| AC1  | integration + unit shape | 9/10, 21/22, 30 |
| AC2  | unit | 19/20, 27, 28/29 |
| AC3  | unit | 3/4, 11/12, 21/22 |
| AC4  | unit | 5/6 (+ existing `test_gateway.py`) |
| AC5  | unit | 1/2, 11 (propagate), 23/24 |
| AC6  | unit | 11/12, 17/18, 21/22 |
| AC7  | unit | 7/8, 13/14 |
| AC8  | unit | 25/26 |
| AC9  | unit | 19/20, 28/29 |
| AC10 | unit | 15/16, 17 |
| AC11 | integration | 31 |
