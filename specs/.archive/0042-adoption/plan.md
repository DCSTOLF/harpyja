---
spec: "0042"
status: planned
strategy: tdd
---

# Plan — 0042 adoption

Date: 2026-07-12

Symbols-tool adoption: fix all four stacked defects (stale prompt, when-less
description, result-shape penalty, positioning gap), freeze the measurement
predicate, re-measure through the 0041-gated driver, type the outcome.

## Plan-time decisions (do not re-open)

- **OQ1 — repo-wide lookup shape: optional `path` on the existing `symbols`
  tool. NO new `find_symbol` tool.** Rationale: a 4–14B weights the enumerated
  menu heavily; a sixth tool is menu bloat for a small model, and the spec's
  own lean is optional-path. CONSEQUENCE: tool count stays **5**; both hard-count
  tests (`test_build_explorer_tools_returns_exactly_five_navigation_tools`,
  `test_tool_schemas_match_the_built_tool_surface_single_source`) and the
  conventions prose stay at 5 — **AC4 is a no-op VERIFY, not a change**. Because
  name-presence alone cannot prove the repo-wide capability is *advertised*, the
  AC1 drift guard additionally asserts the repo-wide when-to-use text is present
  in the prompt, UNCONDITIONALLY (spec AC1, folded post-quorum).

- **OQ2 — output clamp + ranking.** Repo-wide lookup is clamped by a NEW distinct
  knob `scout_symbols_repo_max_entries` (default 200), separate from the
  file-local `scout_symbols_max_entries=400` — a common name's blast radius across
  a repo differs from one file's symbol list. Ranking is PINNED: exact-name >
  prefix > substring, ties broken deterministically by path lexicographic then
  (start_line). Ranking pinned by a unit test, never arbitrary truncation.

- **OQ3 — when-to-use placement: BOTH the schema description AND the initial
  prompt, with the prompt carrying the *when*.** Small models under-read the
  schema description and over-weight the enumerated prompt list, so the adoption
  pitch lands in the prompt; the description carries the citation-shaped-output
  and exact-span pitch for the models that do read it.

## Risk notes

- **Byte-frozen request-param pin survival (HIGH — must not regress).**
  `test_explorer_backend.py::test_explorer_byte_identical_pin_survives_0041` and
  the sibling pin (`test_explorer_backend.py:609`) both assert the outbound
  `params == {"max_tokens": 2048}` at `explorer_think=None`. This spec DOES change
  the SUT surface (prompt text, tool schemas, tool result shape), UNLIKE
  0040/0041 hygiene-only work — but every one of those changes rides
  `complete_with_tools(messages, schemas, **params)` via the `messages` and
  `schemas` args, NEVER `params`. `_default_model_call`'s `params` assembly
  (`explorer_backend.py:239–253`) must be left byte-identical. Mitigation: those
  two pin tests stay in the suite and are asserted green after T2 and T6; no task
  touches the `params` dict.

- **`build_initial_prompt` token-budget bound.** The prompt grows (it now names 5
  tools + terminal + when-to-use text), but
  `test_explorer_backend.py::test_turn1_payload_bounded_and_repo_size_independent`
  caps turn-1 at ~2000 tokens and requires repo-size independence. The new prompt
  is still a small constant with no manifest term — mitigation: keep it terse;
  the bound test stays green in T2.

- **0035 convention extension blast radius (MEDIUM).** Two marker semantics now
  coexist: the 0035 REPLACEMENT shape (bare marker string, no spans exist) and
  the NEW ANNOTATION shape (`[marker, *CodeSpans]`, marker first, spans exist).
  Mitigation (codex round-2 tasking constraint): the `conventions.md` 0035
  amendment lands in the SAME task (T4) as the result-shape change and every
  consumer/schema test, so old and new marker semantics never conflict
  mid-implementation. The positioning absent-index case (T6) deliberately uses the
  REPLACEMENT shape (no spans to annotate); the file-local degraded case (T4) uses
  the ANNOTATION shape — the two are pinned distinct.

- **Integration wall-clock (MEDIUM).** The re-run over the 11 pinned 0040 cases x
  models is ~100+ min and outlasts one invocation. Mitigation: model coverage is
  pinned pre-run in the frozen config (14b at minimum), the driver runs through
  `run_gated_pool_pilot` on the resumable `PoolPilotLedger`, and it is
  STOP-AND-WARN (non-zero exit on missing/contended live infra, never a silent
  skip). Integration TESTS are `@pytest.mark.integration` (deselected by
  `addopts = ["-m", "not integration"]`) and skip-not-fail; closure rests on the
  committed AC6 artifacts, not the test.

- **Deep sibling out of scope.** `harpyja/deep/host_tools.py`'s `symbols` host
  tool is DELIBERATELY unchanged (spec Out-of-scope). Its nested/own result shape
  is not reconciled here. Plan note only; T4 asserts nothing in `deep/host_tools.py`
  changes (a one-line divergence pin, optional).

## `_spans_of` finding (verified against source)

Read `explorer_loop.py:85–110`. For a `list` result, `_spans_of` already does
`getattr(item, "path", None)`; a marker STRING has no `.path` → skipped, and
`CodeSpan` entries are counted. The current `symbols` dict `{"symbols": [...],
"degraded": bool}` is a `Mapping` with no top-level `"path"` key → yields ZERO
spans (the structural penalty the Why describes). So the fix is the `symbols`
RETURN TYPE (dict → list), and `_spans_of` needs **no code change** — but the
new behaviour (marker skipped, CodeSpans counted, marker stays model-visible via
`session.add`→`str(result)`) is regression-PINNED in T3. Do not "simplify"
`_spans_of` to `isinstance(item, CodeSpan)`-only without keeping the degraded
ripgrep-fallback CodeSpans counted.

## Test-first sequence

### Step 1 — Prompt drift-guard + when-to-use (RED) [AC1]
- Add to `harpyja/scout/test_context_map.py`:
  - `test_build_initial_prompt_names_every_registered_tool` — asserts each name
    in `explorer_backend._tool_schemas()` (the SAME single source
    `test_tool_schemas_match_the_built_tool_surface_single_source` uses) appears
    as a substring of `build_initial_prompt("q")`: `{grep, glob, read_span, ls,
    symbols}` + terminal `submit_citations`.
  - `test_build_initial_prompt_documents_symbols_repo_wide_when` — asserts the
    prompt carries the repo-wide symbol-lookup when-to-use text (e.g. a
    "look up a symbol by name across the repo" phrasing), not just the bare name.
  - `test_build_initial_prompt_marks_submit_citations_terminal` — asserts
    `submit_citations` is described as the terminal action, distinct from
    navigation.
- Add to `harpyja/scout/test_explorer_backend.py`:
  - `test_initial_prompt_binds_to_registered_tool_surface_single_source` — the
    structural drift guard: derives the set from `_tool_schemas()` and fails if
    any registered tool name is absent from `build_initial_prompt`. This is the
    guard that would have caught the 0030 stale prompt.
- Tests fail: `context_map.py:55–60` enumerates only "ls, glob, and grep" —
  `symbols`, `read_span`, `submit_citations`, and the repo-wide when-text are all
  absent.

### Step 2 — Rewrite `build_initial_prompt` (GREEN) [AC1]
- Rewrite `build_initial_prompt` in `harpyja/scout/context_map.py` to name all
  five navigation tools + the terminal `submit_citations` (documented as
  terminal), and state WHEN to use `symbols` — including the repo-wide
  by-name lookup pitch aimed at candidate-file → precise-span.
- Keep it a small constant (no manifest term) so the ~2000-token bound and
  repo-size-independence tests stay green.
- Step-1 tests pass.
- VERIFY (no change): `test_explorer_byte_identical_pin_survives_0041` and the
  sibling `params == {"max_tokens": 2048}` pin stay green — prompt text rides
  `messages`, never `params`.

### Step 3 — Result-shape + `_spans_of` consumer tests (RED) [AC2]
- Rewrite the dict-shape `symbols` tests in
  `harpyja/scout/test_explorer_tools.py` (currently `test_symbols_*`,
  lines ~177–504) to the new shape:
  - `test_symbols_clean_returns_bare_codespan_list` — clean file → `list[CodeSpan]`
    (no `{"symbols": ..., "degraded": ...}` dict), like every other nav tool.
  - `test_symbols_degraded_prepends_marker_then_codespans` — degraded file →
    `[marker_str, *CodeSpans]`, marker FIRST; the marker is a stable identifier
    (e.g. `symbols-degraded-index: '<path>'`, cause-taxonomy shape), the spans are
    the ripgrep fallback CodeSpans.
  - `test_symbols_result_shape_no_longer_nested_dict` — regression pin against the
    0/28-era nested-dict shape (asserts result is not a `Mapping`).
- Add to `harpyja/scout/test_explorer_loop.py`:
  - `test_spans_of_counts_symbols_codespans_into_seen_accounting` — a `symbols`
    result `[marker, CodeSpan(...)]` makes `_spans_of` yield the CodeSpan and the
    location enters `session.seen` / loop-detection new-span accounting (the exact
    property the nested dict defeated).
  - `test_spans_of_ignores_symbols_marker_string` — the marker element yields no
    span (only `CodeSpan` entries count).
  - `test_symbols_degraded_marker_stays_model_visible` — `str(result)` in the tool
    message keeps the marker visible (never-a-silent-downgrade), i.e. loop
    stringification preserves 0030's contract.
- Tests fail: `explorer_tools.py:128–165` returns the nested dict; the shape and
  span-accounting assertions fail against it.

### Step 4 — Result-shape widening + 0035 amendment IN LOCKSTEP (GREEN) [AC2]
- Change `symbols` in `harpyja/scout/explorer_tools.py` to return
  `list[CodeSpan]` (clean) / `[marker, *CodeSpans]` (degraded, marker first); the
  `degraded: bool` dict field is GONE.
- Confirm `_spans_of` (`explorer_loop.py:85–110`) needs no code change; the T3
  loop tests pin its behaviour.
- **Amend `.speccraft/conventions.md` in THIS SAME task** (the 0035 marker
  convention bullet at line 75): record the SECOND, distinct marker case —
  "successful-but-degraded ANNOTATION" (`[marker, *CodeSpans]`, marker first,
  spans real, marker never counts as a span) alongside the existing
  "unsearchable-scope REPLACEMENT" (bare marker string, no spans). Cite spec 0042
  AC2.
- All Step-3 tests pass; the byte-frozen pin stays green (result shape rides tool
  output, not `params`).
- Plan note / optional pin: assert `deep/host_tools.py` `symbols` is untouched
  (deliberate divergence — Out of scope).

### Step 5 — Positioning: repo-wide lookup + schema (RED) [AC3, AC1-desc]
- Add to `harpyja/scout/test_explorer_tools.py`:
  - `test_symbols_repo_wide_lookup_by_name_no_path` — `symbols(name="separability_matrix")`
    (no `path`) returns matching Tier-0 records with exact spans from across the
    repo; read-only, repo-confined.
  - `test_symbols_repo_wide_ranking_exact_prefix_substring` — PINS ranking
    exact-name > prefix > substring, ties by path lexicographic (then start_line).
  - `test_symbols_repo_wide_clamped_by_repo_max_entries` — clamped by the new
    `scout_symbols_repo_max_entries` knob (distinct from `scout_symbols_max_entries`).
  - `test_symbols_repo_wide_hostile_input_rejected` — hostile/oversized name input
    rejected/bounded.
  - `test_symbols_repo_wide_absent_tier0_returns_replacement_marker` — absent OR
    degraded Tier-0 records → a TYPED marker in the 0035 REPLACEMENT shape (bare
    marker string, e.g. `symbols-index-unavailable: '<name>'`), never a silent
    `[]` indistinguishable from "no such symbol".
- Add to `harpyja/scout/test_explorer_backend.py`:
  - `test_symbols_schema_path_optional` — `_tool_schemas()` `symbols` no longer
    lists `path` in `required` (so repo-wide is reachable).
  - `test_symbols_schema_description_states_when_and_spans` — the description
    carries the when-to-use and the exact start/end-span (citation-shaped-output)
    pitch.
- Add to `harpyja/config/test_settings.py`:
  - `test_scout_symbols_repo_max_entries_default` — the new knob exists with the
    pinned default.
- Tests fail: `symbols(path)` requires `path` (`explorer_tools.py:128`); the
  schema marks `path` required (`explorer_backend.py:139`) with a when-less
  description; the knob does not exist.

### Step 6 — Positioning implementation + AC4 no-op verify (GREEN) [AC3, AC1-desc, AC4]
- Make `path` optional on `symbols` in `harpyja/scout/explorer_tools.py`: with a
  `name` (no path) → repo-wide lookup over `symbol_records`, ranked
  exact>prefix>substring (ties path-lexicographic), clamped by
  `scout_symbols_repo_max_entries`; absent/degraded index → 0035 REPLACEMENT
  marker string.
- Add `scout_symbols_repo_max_entries: int = 200` to
  `harpyja/config/settings.py` (additive-last on the scout budgets); thread it
  through `build_explorer_tools`.
- Update `_tool_schemas()` `symbols` in `harpyja/scout/explorer_backend.py`: drop
  `path` from `required`, add the when-to-use + exact-span description.
- **AC4 VERIFY (no-op):** run
  `test_build_explorer_tools_returns_exactly_five_navigation_tools` and
  `test_tool_schemas_match_the_built_tool_surface_single_source` — both stay green
  at 5; the conventions prose stays at 5 (no edit). Record in the task that AC4 is
  discharged as a verification, per the OQ1 decision.
- Step-5 tests pass; byte-frozen pin stays green.

### Step 7 — REFACTOR (optional)
- Extract the two `symbols` marker constructions (annotation vs replacement) into
  named helpers/constants in `explorer_tools.py` so the two 0035 shapes are
  single-sourced. All tests still pass.

### Step 8 — Frozen measurement config tests (RED) [AC5]
- Add `harpyja/eval/test_adoption_precheck.py`:
  - `test_adoption_config_hash_is_stable` — `ADOPTION_CONFIG_HASH_0042 ==
    adoption_config_hash(PREREGISTERED_ADOPTION_CONFIG_0042)` (the 0039/0040
    `dataclasses.asdict`→sha256 shape).
  - `test_decide_adoption_outcome_grid_totality` — over the full cross of
    {adoption_count == 0, > 0} x {rfws_denominator < / >= MIN_RFWS_DENOMINATOR} x
    {conversions, regressions, net}, `decide_adoption_outcome` returns exactly one
    of the four typed outcomes for EVERY cell (total pure function, no gap/overlap).
  - `test_adoption_boundary_still_not_adopted_iff_zero_clean_cell_symbols` —
    STILL_NOT_ADOPTED iff clean-cell `symbols` invocations == 0.
  - `test_conversion_predicate_is_bidirectional_from_paired_buckets` — computed
    from retained per-case pairs (0040-ledger bucket vs re-run bucket), retaining
    BOTH RFWS→exact conversions AND exact→RFWS regressions, with the net surfaced;
    a single noise flip over a net-negative re-run does NOT type CONVERTS
    unqualified. Asserts it is NEVER computed from marginal counts.
  - `test_under_powered_gated_by_min_rfws_denominator` — a no-conversion result
    below the power floor types ADOPTED_UNDER_POWERED, not ADOPTED_NO_CONVERSION.
  - `test_partial_model_coverage_uses_per_model_denominator` — a 14b-only run is
    typed against 14b's own clean-cell universe, never the pooled 0/28 baseline;
    the pinned model coverage is asserted.
- Tests fail: `harpyja/eval/adoption_precheck.py` does not exist.

### Step 9 — Frozen config + decider (GREEN) [AC5]
- Add `harpyja/eval/adoption_precheck.py` (following `pool_precheck.py` /
  `think_ab.py`): frozen `@dataclass(frozen=True) AdoptionConfig` with
  `PREREGISTERED_ADOPTION_CONFIG_0042` pinning the adoption boundary, the RFWS
  denominator definition (committed 0040 clean cells bucketed RFWS per model), the
  bidirectional per-case paired-bucket conversion predicate, `MIN_RFWS_DENOMINATOR`,
  the pinned model coverage (14b minimum) and partial-coverage per-model
  denominators; `adoption_config_hash` + `ADOPTION_CONFIG_HASH_0042`; a total pure
  `decide_adoption_outcome(...)` returning ADOPTED_AND_CONVERTS /
  ADOPTED_NO_CONVERSION / ADOPTED_UNDER_POWERED / STILL_NOT_ADOPTED. Reuse the
  committed `LocateBucket` / `located_via_oracle` oracles (identity, not
  re-derived).
- Write the discoverable frozen-config artifact under
  `specs/0042-adoption/` (the hash committed, per AC5 / 0039/0040 shape) — BEFORE
  any live call.
- Step-8 tests pass.

### Step 10 — Operator driver tests (RED) [AC6]
- Add `harpyja/eval/test_adoption_run.py` (unit, fakes):
  - `test_adoption_run_cell_emits_trajectory_verified_artifact` — the driver's
    `run_cell` produces a per-case artifact carrying model identity, tools invoked
    INCLUDING the per-case `symbols` invocation count, terminal bucket, and the
    `0041/pilot/2` exclusivity proof.
  - `test_adoption_run_refuses_without_live` — routing through
    `run_gated_pool_pilot(..., live=False)` refuses loudly (the 0040/0041 posture).
  - `test_adoption_run_consumes_pinned_0040_cases` — the pinned 0040 case set is
    consumed, not re-selected.
- Add `specs/0042-adoption/adoption_run/test_run_adoption_integration.py`:
  - `test_adoption_closure_run_smoke` — `@pytest.mark.integration`, skip-not-fail
    under the opt-in default; asserts the driver STOPS-AND-WARNS (non-zero exit) on
    missing live infra rather than silently passing.
- Tests fail: the driver `specs/0042-adoption/adoption_run/run_adoption.py` does
  not exist.

### Step 11 — STOP-AND-WARN operator driver (GREEN) [AC6]
- Add `specs/0042-adoption/adoption_run/run_adoption.py` (the
  0040/0041 committed-driver shape, cf. `specs/.archive/0041-gates/gate/run_gate.py`):
  runs the re-measure through `run_gated_pool_pilot(live=True)` on the committed
  0040 pinned pilot cases with the `0041/pilot/2` exclusivity proof in every
  artifact; a `run_cell` that invokes `run_verified_case` under the fixed SUT and
  records per-case trajectory-verified artifacts (model identity, tools incl.
  `symbols` count, terminal bucket, exclusivity proof); STOP-AND-WARN (non-zero
  exit on contended/missing live infra). Resumable via `PoolPilotLedger`;
  model coverage read from the frozen AC5 config (14b minimum).
- Step-10 tests pass (integration test skips by default).

### Step 12 — LIVE MEASUREMENT (operator run, LAST) [AC6]
- After ALL four fixes (T1–T6) + the frozen config committed (T9), run
  `specs/0042-adoption/adoption_run/run_adoption.py` against the live stack.
  Commit the durable per-case artifacts (or a versioned aggregate derived from
  them) under `specs/0042-adoption/`. This is an operator run, not a test task;
  the frozen hash was committed BEFORE this call.

### Step 13 — Typed-outcome record (doc, closes) [AC7]
- Write the AC7 outcome doc under `specs/0042-adoption/`: the typed outcome
  DECIDED by `decide_adoption_outcome` (AC5 frozen config) over the AC6 artifacts —
  ADOPTED_AND_CONVERTS ("observed ≥N conversion signal at pilot N with the net
  flip count — a signal, NOT an inferential claim; the 0023/0026 ≥8-discordant-pairs
  floor is what a claim would need") / ADOPTED_NO_CONVERSION / ADOPTED_UNDER_POWERED
  / STILL_NOT_ADOPTED. The record states: 0030's lift-refutation was
  measured-on-an-unusable-tool; the 0/28 baseline was measured under the
  stale-prompt/nested-shape condition (delta is fix-vs-defect, not
  tool-vs-no-tool); and the accepted all-four-fixes-at-once attribution confound.

## Delegation

- T1–T7 (Scout surface: prompt, tool schemas, result shape, positioning,
  conventions) → keep in-thread / general implementer: tightly coupled edits
  across `context_map.py` / `explorer_backend.py` / `explorer_tools.py` /
  `explorer_loop.py` / `conventions.md` with a lockstep constraint (T4) that a
  handoff would fracture.
- T8–T9 (frozen config + total decider) → delegate to an eval/statistics-strong
  agent (reason: grid-totality + bidirectional paired-bucket predicate mirror the
  0039/0040 `pool_precheck` / `think_ab` freeze work).
- T10–T13 (gated driver + live run + doc) → delegate to the eval-harness/operator
  agent that owns the 0040/0041 committed drivers (reason: `run_gated_pool_pilot`,
  `PoolPilotLedger`, `0041/pilot/2` exclusivity proof, STOP-AND-WARN precedent).

## Risk register (summary)

- Byte-frozen `params == {"max_tokens": 2048}` pin → mitigation: never touch
  `_default_model_call` params; assert the two pin tests green after T2, T6.
- 0035 two-marker blast radius → mitigation: convention amendment + all
  consumer/schema tests land together in T4; replacement vs annotation pinned
  distinct (T4 vs T6).
- Integration wall-clock ~100+ min → mitigation: model coverage pinned in frozen
  config (14b min), resumable ledger, STOP-AND-WARN driver, skip-not-fail tests.
- Prompt token bound → mitigation: keep prompt a terse constant; bound test green
  in T2.
- Deep sibling divergence → mitigation: assert `deep/host_tools.py` unchanged
  (T4 note/pin).
