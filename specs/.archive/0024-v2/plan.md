---
spec: "0024"
status: planned
strategy: tdd
---

# Plan — 0024 v2 (Scout v2 — native explorer-loop finder)

## Approach

Construction (not measurement): a NEW `ScoutBackend` impl lands under
`harpyja/scout/`, colocated `test_*.py`, behind the UNCHANGED seam. The
orchestrator, gate, matrix, formatter, `engine.py`, `normalize.py`, and the
Locator boundary are untouched — the new backend is injected into `ScoutEngine`
via the same DI slot `FastContextBackend` occupies today.

New modules (each with a colocated test file):

- `harpyja/scout/explorer_tools.py` — `build_explorer_tools(repo_path, settings, *, search_engine)`
  returns EXACTLY the three navigation closures `{grep, glob, read_span}`,
  mirroring `deep/host_tools.build_host_tools`: each `confine_path`-guarded and
  Settings-bounded, read-only. `grep` wraps the SAME `symbols.ripgrep.RipgrepEngine`
  the Deep `search` host tool wraps (invariant B — one bounded rg source of
  truth); `read_span` reuses `server.tools.read_snippet`; `glob`'s path list is
  normalized to file-level `CodeSpan` records (not raw strings).
- `harpyja/scout/context_map.py` — `build_context_map(manifest, query, settings)`
  builds the pre-model filtered tree (no file bytes) from
  `index.manifest.read_manifest` output. The vendor/test/generated exclusion is a
  MAP concern only; tool scope is unaffected.
- `harpyja/scout/submit.py` — the `submit_citations` terminal action + its STRICT
  arg schema (`SubmitCitationsSchemaError` on unknown/extra/diagnosis-shaped
  fields); validates+normalizes via the unchanged `normalize_spans`; no repo-read
  capability.
- `harpyja/scout/explorer_loop.py` — `run_explorer_loop(...)`: the bounded loop
  (one tool call/turn, append raw output, `scout_max_turns` cap, `scout_wall_clock_s`
  ceiling) + the two deterministic self-recovery mechanisms (loop detection,
  citation-preserving truncation). Driven in unit tests by a fake model-call
  callable — no gateway, no network.
- `harpyja/scout/explorer_backend.py` — `ExplorerBackend` implements
  `ScoutBackend.run`; assembles map + tools + submit + loop; calls
  `gateway.assert_local()` ONCE before the loop starts; maps terminal states to
  the four typed `ScoutUnavailable` causes and exposes the degrade-rate field.

Gateway: a NEW `ModelGateway.complete_with_tools(messages, tools, *, transport, resolver, **params)`
returning `{content, tool_calls}` from `choices[0].message`, routing through
`assert_local` BEFORE any transport touch (the single air-gap point) — tested with
an injected fake transport exactly as `complete` is today.

Settings (`harpyja/config/settings.py`) — NEW provisional fields, justified,
flagged for the bake-off (OQ1/OQ3):
- `scout_max_turns=12` — a general (non-fine-tuned) model needs more turns than
  FastContext's old `_DEFAULT_MAX_TURNS=6`; provisional (OQ1).
- `scout_wall_clock_s=300.0` — whole-loop ceiling; the gateway `lm_http_timeout_s=120.0`
  is the per-CALL floor, this stops one slow turn wedging the loop (AC4).
- `scout_loop_repeat_n=2` — consecutive identical no-new-span calls before the
  corrective injection fires (AC5); provisional (OQ3).
- `scout_history_char_cap=60000` — history bloat threshold for truncation (AC5);
  provisional (OQ3).
- `scout_glob_max_paths=400` — glob path bound (parallels `search_max_matches`;
  glob returns file records so it is bounded independently); provisional.

`source_tier=1` note: the terminal spans stay unstamped (`source_tier=0`) out of
`submit_citations`/`normalize_spans`; the `=1` stamp happens UNCHANGED downstream
in `orchestrator/locate.py` via `format_citations(..., source_tier=1)`
(locate.py:167,253 — verified). The new backend does not stamp it — AC6 asserts
the backend output round-trips to `source_tier=1` through the existing
`ScoutEngine`→formatter path.

Reused seams (verified, unchanged): `scout.engine.ScoutEngine.search`
(backend slot); `scout.normalize.normalize_spans` / `normalize_spans_with_tally`;
`symbols.ripgrep.RipgrepEngine` (+ `RipgrepMissingError` floor);
`server.tools.confine_path` / `read_snippet`; `index.manifest.read_manifest`;
`gateway.ModelGateway.assert_local`; `scout.errors.ScoutUnavailable`;
`gateway.AirGapError` (never degrades). Every GREEN preceded by RED. Sequenced so
the loop is fully driven by FAKES end-to-end (Steps 1–14) before the live gateway
method (Step 9) is exercised against a real endpoint only at integration
(Step 15).

## Test-first sequence

### Step 1 — New Settings budgets (RED)  [AC4/AC5/AC2]
- Add to `harpyja/config/test_settings.py`:
  - `test_scout_loop_budgets_present_with_provisional_defaults` — `scout_max_turns`,
    `scout_wall_clock_s`, `scout_loop_repeat_n`, `scout_history_char_cap`,
    `scout_glob_max_paths` exist with the justified defaults.
  - `test_scout_wall_clock_exceeds_per_call_http_timeout` — `scout_wall_clock_s`
    (whole-loop ceiling) is strictly greater than `lm_http_timeout_s` (per-call
    floor), so turns and time are distinct budgets.
- Tests fail: fields not yet declared.

### Step 2 — Add Settings fields (GREEN)  [AC4/AC5/AC2]
- Add the five fields to `harpyja/config/settings.py` with docstring
  justifications and the OQ1/OQ3 provisional-flag comments.
- Step-1 tests pass.

### Step 3 — Three navigation tools: bounded, confined, read-only (RED)  [AC2]
- Add `harpyja/scout/test_explorer_tools.py`:
  - `test_build_explorer_tools_returns_exactly_three_navigation_tools` — the dict
    keys are EXACTLY `{grep, glob, read_span}`; nothing mutating, no `submit_citations`.
  - `test_grep_wraps_shared_ripgrep_engine` — `grep` delegates to the injected
    `RipgrepEngine` (the same engine the Deep `search` host tool wraps), not a
    second rg surface.
  - `test_grep_clamps_to_search_max_matches` — over-budget match set clamped.
  - `test_glob_normalizes_paths_to_file_level_codespans` — `glob` returns
    file-level `CodeSpan` records (`is_file_level`), not raw path strings.
  - `test_glob_clamps_to_scout_glob_max_paths` — glob path list bounded.
  - `test_read_span_reuses_read_snippet_and_bounds_lines` — `read_span` reuses
    `read_snippet`, clamped by `tool_max_lines`/`tool_max_chars`.
  - `test_grep_scope_outside_repo_rejected` — an out-of-repo `scope` raises
    `PathConfinementError` (hostile input).
  - `test_read_span_path_outside_repo_rejected` — `../` traversal rejected.
  - `test_glob_pattern_escaping_repo_yields_no_out_of_repo_paths` — glob cannot
    surface a path outside the repo.
- Tests fail: `explorer_tools` module / `build_explorer_tools` do not exist.

### Step 4 — Implement `build_explorer_tools` (GREEN)  [AC2]
- Implement `harpyja/scout/explorer_tools.py` mirroring `build_host_tools`: three
  `confine_path`-guarded, Settings-bounded closures; `grep` wraps the injected
  `RipgrepEngine`; `glob` normalizes to file-level `CodeSpan`s clamped by
  `scout_glob_max_paths`; `read_span` wraps `read_snippet`.
- Step-3 tests pass.

### Step 5 — Context map from manifest; map-filter ≠ tool-scope (RED)  [AC3]
- Add `harpyja/scout/test_context_map.py`:
  - `test_context_map_built_from_manifest_no_file_bytes` — the map is a filtered
    tree derived from `ManifestEntry`s; no file contents are read (assert no
    `read_snippet`/open on repo files pre-loop).
  - `test_context_map_injected_with_query` — the query text appears in the
    assembled map/prompt payload.
  - `test_context_map_excludes_vendor_test_generated_from_display` — excluded
    entries are absent from the rendered map.
  - `test_excluded_file_still_reachable_via_tools` — a test/vendor file dropped
    from the MAP still resolves through `grep`/`glob`/`read_span` (map-filter is a
    display concern, never a search-confinement one).
- Tests fail: `context_map` module does not exist.

### Step 6 — Implement `build_context_map` (GREEN)  [AC3]
- Implement `harpyja/scout/context_map.py`: render a compact filtered tree from
  `read_manifest` output (no bytes), inject the query; the exclusion applies to
  the rendered map only.
- Step-5 tests pass.

### Step 7 — `submit_citations` terminal action: strict schema + normalize (RED)  [AC6]
- Add `harpyja/scout/test_submit_citations.py`:
  - `test_submit_citations_returns_normalized_codespans` — well-formed structured
    args → `normalize_spans` output (confined, clamped).
  - `test_submit_citations_drops_out_of_repo_nonexistent_over_budget_malformed` —
    each bad ref dropped, never propagated.
  - `test_submit_citations_strict_schema_rejects_unknown_field` — an extra/unknown
    arg raises `SubmitCitationsSchemaError`.
  - `test_submit_citations_diagnosis_shaped_field_fails_schema` — a
    `root_cause`/`fix`/`explanation`-style field fails schema (the enforceable
    locator-not-diagnoser guard).
  - `test_submit_citations_has_no_repo_read_capability` — the action exposes no
    read/grep/glob surface; it only validates+normalizes refs.
  - `test_submit_citations_empty_is_honest_empty_not_error` — an empty
    well-formed submission returns `[]` without raising.
  - `test_submit_citations_spans_reach_source_tier_1_via_engine_path` — the
    returned spans, run through the unchanged `ScoutEngine`→`format_citations`
    path, become `source_tier=1` citations (the backend does not stamp it).
- Tests fail: `submit` module / `submit_citations` / `SubmitCitationsSchemaError`
  do not exist.

### Step 8 — Implement `submit_citations` + strict schema (GREEN)  [AC6]
- Implement `harpyja/scout/submit.py`: a strict arg validator (frozen allowed
  field set; unknown/extra → `SubmitCitationsSchemaError`), mapping validated refs
  to raw `CodeSpan`s and returning `normalize_spans(...)` output; no repo-read
  closure attached.
- Step-7 tests pass.

### Step 9 — Gateway tool-calling method, air-gap-first (RED)  [AC7]
- Add to `harpyja/gateway/test_gateway.py`:
  - `test_complete_with_tools_returns_content_and_tool_calls` — with a fake
    transport returning `choices[0].message.tool_calls`, the method yields
    `{content, tool_calls}`.
  - `test_complete_with_tools_posts_tools_and_tool_choice` — the payload carries
    `tools=`/`tool_choice=`.
  - `test_complete_with_tools_asserts_local_before_transport` — a non-loopback
    `api_base` raises `AirGapError` and the fake transport is NEVER called.
- Tests fail: `complete_with_tools` does not exist.

### Step 10 — Implement `complete_with_tools` (GREEN)  [AC7]
- Add `ModelGateway.complete_with_tools`: `assert_local` first, then POST via the
  injectable transport (default bound to `timeout_s`), returning `content` +
  `tool_calls` from `choices[0].message`. Gateway stays the only outbound caller.
- Step-9 tests pass.

### Step 11 — Bounded loop: one call/turn, turn cap, wall-clock ceiling (RED)  [AC4]
- Add `harpyja/scout/test_explorer_loop.py` (fake model-call callable + fake tools,
  no gateway):
  - `test_loop_executes_one_tool_call_per_turn_and_appends_output` — each turn
    dispatches exactly one tool call and appends its raw output to history.
  - `test_loop_terminates_on_submit_citations` — a `submit_citations` call ends
    the loop and returns its spans.
  - `test_non_terminating_fake_killed_by_turn_cap` — a fake that never submits is
    stopped at `scout_max_turns` (never hangs).
  - `test_wall_clock_ceiling_terminates_when_turns_would_not` — with an injected
    clock, a slow/hung turn trips `scout_wall_clock_s` before the turn cap would
    (no wedge).
  - `test_unknown_tool_name_is_rejected_not_dispatched` — a call to a tool outside
    the whitelist is refused, not executed.
- Tests fail: `explorer_loop` module / `run_explorer_loop` do not exist.

### Step 12 — Implement `run_explorer_loop` (GREEN)  [AC4]
- Implement `harpyja/scout/explorer_loop.py`: the turn loop with an injected
  model-call callable, an injected monotonic clock, a whitelist dispatch table,
  history append, and the `scout_max_turns`/`scout_wall_clock_s` terminations;
  terminal states surfaced to the caller (submit / turns-exhausted /
  wall-clock-exhausted).
- Step-11 tests pass.

### Step 13 — Self-recovery: loop detection + citation-preserving truncation (RED)  [AC5]
- Add to `harpyja/scout/test_explorer_loop.py`:
  - `test_exact_repeat_no_new_span_triggers_corrective_injection` — an exact
    `(tool_name, normalized_args)` repeat for `scout_loop_repeat_n` consecutive
    no-new-span turns injects the corrective note.
  - `test_distinct_args_do_not_trigger_loop_detection` — differing normalized args
    do not trip the detector (no false positive).
  - `test_history_past_char_cap_triggers_truncation` — history exceeding
    `scout_history_char_cap` fires truncation.
  - `test_truncation_drops_only_stale_navigational_chatter` — repeated calls /
    superseded listings are what gets dropped.
  - `test_truncation_preserves_citable_observation_dropped_span_index_reinjected`
    — PRESERVATION (the negative): a final citation depending on a `read_span`/
    `grep` hit OLDER than the bloat threshold STILL resolves after truncation
    (the dropped-span compact index is re-injected); truncation NEVER converts a
    real find into honest-empty.
- Tests fail: recovery hooks not yet in the loop.

### Step 14 — Implement self-recovery (GREEN)  [AC5]
- Add to `explorer_loop.py`: normalized-args equality tracking with the
  consecutive-no-new-span counter → corrective injection; a char-cap truncator
  that drops only stale navigational chatter and re-injects a compact dropped-span
  index for any capped `read_span`/`grep` observation whose location could still
  be cited.
- Step-13 tests pass.

### Step 15 — `ExplorerBackend`: seam + DI + air-gap-before-loop (RED)  [AC1/AC7]
- Add `harpyja/scout/test_explorer_backend.py`:
  - `test_explorer_backend_satisfies_scoutbackend_run` — `.run(query, seed)`
    returns `list[CodeSpan]`; structurally a `ScoutBackend`.
  - `test_explorer_backend_injected_into_scout_engine` — injected into
    `ScoutEngine` via the existing slot; `search` round-trips through the
    unchanged `normalize_spans_with_tally`.
  - `test_fakes_drive_loop_deterministically_to_citations` — a scripted fake
    model-call drives map→tools→submit to a deterministic citation list.
  - `test_assert_local_called_once_before_loop_starts` — `gateway.assert_local()`
    runs before ANY model I/O; a non-loopback endpoint raises `AirGapError` and
    the loop never starts (no model call, no tool call).
- Tests fail: `explorer_backend` module / `ExplorerBackend` do not exist.

### Step 16 — Implement `ExplorerBackend` (GREEN)  [AC1/AC7]
- Implement `harpyja/scout/explorer_backend.py`: assemble `build_context_map` +
  `build_explorer_tools` + `submit_citations` + `run_explorer_loop` over
  `gateway.complete_with_tools`; call `gateway.assert_local()` once up front;
  return the terminal spans.
- Step-15 tests pass.

### Step 17 — Typed degradation + degrade-rate field (RED)  [AC8/AC9]
- Add to `harpyja/scout/test_explorer_backend.py`:
  - `test_model_unreachable_raises_distinct_cause` — a transport connection
    failure → `ScoutUnavailable` with the connection cause.
  - `test_turn_exhausted_empty_raises_distinct_cause` — turns exhausted with no
    citation → `ScoutUnavailable(LOOP_TURNS_EXHAUSTED)`.
  - `test_wall_clock_exhausted_empty_raises_distinct_cause` — ceiling tripped with
    no citation → `ScoutUnavailable(LOOP_WALLCLOCK_EXHAUSTED)`.
  - `test_backend_raise_maps_to_backend_error_cause` — an internal loop crash →
    `ScoutUnavailable(BACKEND_ERROR)`.
  - `test_all_four_causes_are_distinct_stable_ids` — the four cause ids are
    pairwise distinct.
  - `test_well_formed_empty_submit_is_honest_empty_not_unavailable` — an empty
    well-formed `submit_citations` returns `[]` and does NOT raise (honest-empty).
  - `test_airgap_error_never_mapped_to_scout_unavailable` — `AirGapError` (and
    `RipgrepMissingError`) propagate as floors, never degrade.
  - `test_degrade_rate_is_first_class_reported_field` — the backend/engine exposes
    a degrade-rate/degrade-count field per the standing convention.
- Tests fail: new cause constants / degrade-rate field not present.

### Step 18 — Implement typed causes + degrade-rate (GREEN)  [AC8/AC9]
- Add `LOOP_TURNS_EXHAUSTED`, `LOOP_WALLCLOCK_EXHAUSTED`, `MODEL_UNREACHABLE`
  cause constants to `harpyja/scout/errors.py` (reuse `CONNECTION_REFUSED`/
  `BACKEND_ERROR`/`NO_ENDPOINT_CONFIGURED` where they already fit); map each
  terminal state in `ExplorerBackend` to its distinct cause; keep `AirGapError`/
  `RipgrepMissingError` propagating; expose the degrade-rate counter as a
  first-class reported field.
- Step-17 tests pass.

### Step 19 — Wire `ExplorerBackend` into the production factory (RED)  [AC1]
- Add to `harpyja/scout/test_scout_wiring.py`:
  - `test_build_scout_engine_wires_explorer_backend` — `build_scout_engine`
    assembles a `ScoutEngine` whose backend is `ExplorerBackend` over the loopback
    `ModelGateway`, the shared `RipgrepEngine`, the manifest map, and the
    Settings budgets — no model touched (fake model-call injected).
  - `test_build_scout_engine_threads_new_loop_budgets` — `scout_max_turns` /
    `scout_wall_clock_s` from Settings reach the loop.
- Tests fail (when the wiring still constructs `FastContextBackend`): the swap is
  not done.

### Step 20 — Swap the factory to `ExplorerBackend` (GREEN)  [AC1]
- Update `harpyja/scout/wiring.py` `build_scout_engine` to construct
  `ExplorerBackend` (loopback gateway + shared `RipgrepEngine` + context map +
  explorer tools) in the DI slot; the FastContext adapter code is NOT deleted here
  (out-of-scope cleanup spec). Keep the `seed_fn` and `file_set` threading
  unchanged.
- Step-19 tests pass; existing wiring tests still green (or updated in lockstep to
  the new backend type).

### Step 21 — Refactor: factor the tool-dispatch table (REFACTOR)
- Extract the whitelist dispatch shared by `run_explorer_loop` and
  `ExplorerBackend` into one helper (single source of the name→closure mapping,
  including the `submit_citations` terminal branch); pin with
  `test_tool_dispatch_table_is_single_source` in `test_explorer_loop.py`. All
  tests still pass. (If no real duplication emerges, no-op this honestly and say
  so.)

### Step 22 — Live tool-calling model over a real repo (RED, integration, skip-not-fail)  [AC10]
- Add `harpyja/scout/test_explorer_integration.py`, reusing the
  `_deny_nonloopback_egress` harness pattern from
  `harpyja/eval/test_eval_integration.py` and the 0007/0014 air-gap gating:
  - `@pytest.mark.integration test_live_explorer_loop_produces_citation_list` —
    a real tool-calling model over a real repo returns a parsed citation list,
    within `scout_max_turns`; skip (not fail) when no local stack is served.
  - `@pytest.mark.integration test_live_explorer_loop_no_nonloopback_egress` —
    under `_deny_nonloopback_egress()` the live run makes ZERO non-loopback
    connections (egress observed, not merely asserted).
- Tests fail (when a stack is present) until the live entry is wired; otherwise
  skip.

### Step 23 — Wire the live integration entry (GREEN, integration)  [AC10]
- Finish the live path: the integration test builds the real loopback stack via
  `build_scout_engine` and drives one real query; no SUT change beyond the
  factory. Passes when a served tool-calling model is available; skips otherwise.

## AC mapping

- AC1 → Steps 15–16 (backend + DI), 19–20 (factory wiring)
- AC2 → Steps 3–4
- AC3 → Steps 5–6
- AC4 → Steps 11–12
- AC5 → Steps 13–14
- AC6 → Steps 7–8
- AC7 → Steps 9–10 (gateway), 15–16 (assert_local before loop)
- AC8 → Steps 17–18
- AC9 → Steps 17–18 (degrade-rate field)
- AC10 → Steps 22–23
- Settings (OQ1/OQ3 provisional budgets) → Steps 1–2

## Delegation

- Steps 1–21 (pure/faked unit TDD — tools, map, submit, loop, backend, wiring; no
  live model) → keep in-thread. Strength match: deterministic RED→GREEN with
  injected fakes, no external stack.
- Steps 22–23 (live tool-calling model over a real repo + network-deny egress
  assertion) → delegate to an integration runner with a served local
  OpenAI-compatible tool-calling endpoint (per repo memory: local Ollama on the
  32 GB dev host). Reason: needs a live loopback endpoint the unit thread must
  never depend on; `@pytest.mark.integration` skip-not-fail keeps CI green when
  absent.

## Risk

- General model needs more turns than the FastContext default (OQ1) → mitigation:
  `scout_max_turns` is a justified provisional Settings field flagged for the
  bake-off; the loop is model-agnostic and the value is a one-line tune, not a
  code fork.
- Tool-suite creep to "help" a weak model → mitigation: EXACTLY three navigation
  tools asserted (`test_build_explorer_tools_returns_exactly_three_navigation_tools`);
  a weak-model result is a finding, not a bug (spec load-bearing invariant).
- Truncation silently eating a citable observation → mitigation: AC5 preservation
  test proves the negative (dropped-span index re-injected; a find older than the
  bloat threshold still resolves); truncation drops only stale chatter.
- Diagnosis leaking through the terminal parse (locator-not-diagnoser) →
  mitigation: STRICT `submit_citations` schema rejects unknown/diagnosis-shaped
  fields (`test_submit_citations_diagnosis_shaped_field_fails_schema`), an
  enforceable guard not a soft check.
- A second, subtly-different grep surface → mitigation: `grep` wraps the SAME
  `RipgrepEngine` the Deep `search` host tool wraps (invariant B), pinned by
  `test_grep_wraps_shared_ripgrep_engine`.
- A slow/hung single turn wedging the loop → mitigation: the whole-loop
  `scout_wall_clock_s` ceiling is distinct from and above the per-call
  `lm_http_timeout_s` floor, asserted by
  `test_wall_clock_ceiling_terminates_when_turns_would_not`.
- Air-gap regression (a new outbound path) → mitigation: `assert_local` before the
  loop starts AND inside `complete_with_tools`; the gateway stays the only
  outbound caller; AC10 observes zero non-loopback egress via the shared
  `_deny_nonloopback_egress` harness.
- FastContext entanglement in one diff → mitigation: the adapter code is left in
  place (out-of-scope cleanup spec); only the factory DI slot is swapped, so the
  two changes are not entangled.
