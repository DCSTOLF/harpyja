---
spec: "0027"
status: planned
strategy: tdd
---

# Plan — 0027 harness (remove eager context-map; on-demand structure discovery)

The steps are ordered along the data path: `Settings` field → `ls` tool + count-convention
amendment → backend map-removal + bounded-payload → four-state cause-taxonomy report
plumbing → `turns_used` retirement sweep → truncation guard → live astropy+django proof +
evidence artifact → doc-correction verification. Every GREEN is preceded by a RED. Each
step is tagged `[unit]` / `[integration]` / `[build]`. Verify each unit/build step with
`uv run pytest -m "not integration"`; integration steps run under the live 16B stack and
are `skip-not-fail`.

## Test-first sequence

### Step 1 — `scout_ls_max_entries` Settings field (RED) [unit]
- Add to `harpyja/config/test_settings.py`:
  - `test_scout_ls_max_entries_default_is_a_finite_positive_bound` — asserts `Settings().scout_ls_max_entries` exists, is an `int`, and is a finite positive clamp (mirrors the `scout_glob_max_paths` bound).
  - `test_scout_ls_max_entries_present_in_settings_fields` — via `dataclasses.fields(Settings)` (the field-default introspection drift-guard pattern), asserts the new field is a declared frozen-dataclass field with a default (not injected ad hoc).
- Tests fail: `Settings` has no `scout_ls_max_entries` attribute yet → `AttributeError` / field absent.

### Step 2 — Add `scout_ls_max_entries` to `Settings` (GREEN) [build]
- Implement in `harpyja/config/settings.py`: append `scout_ls_max_entries: int = 200` (or similar finite bound) LAST among the scout fields, with a comment naming it as the `ls`/tree tool output clamp (parallel to `scout_glob_max_paths`). Frozen dataclass, additive-last.
- All step-1 tests pass.

### Step 3 — `ls` tool + exact-four-tool reconciliation (RED) [unit]
- Amend `harpyja/scout/test_explorer_tools.py`:
  - Rename/replace `test_build_explorer_tools_returns_exactly_three_navigation_tools` → `test_build_explorer_tools_returns_exactly_four_navigation_tools` — asserts `set(tools) == {"grep","glob","read_span","ls"}` and `len(tools) == 4`.
  - `test_ls_lists_a_single_directory_only` — `ls("subdir")` returns the immediate entries of one directory (files AND dirs, so layout is discoverable — the affordance `glob` lacks); it does NOT recurse into a depth-N subtree (Decision 1: single-directory listing).
  - `test_ls_is_read_only` — the returned callable performs no write/mutation; output is `CodeSpan`/text shape (a listing normalizes to file-level `CodeSpan` records, consistent with `glob`).
  - `test_ls_path_outside_repo_rejected` — a hostile `../` / absolute out-of-repo path is rejected via `confine_path` (same boundary as `grep`/`glob`/`read_span`).
  - `test_ls_clamps_to_scout_ls_max_entries` — an over-budget directory listing is clamped to `settings.scout_ls_max_entries`.
- Amend `harpyja/scout/test_explorer_backend.py`:
  - Update `test_tool_schemas_match_the_built_tool_surface_single_source` — the schema-drift set-equality now expects `ls` on BOTH sides (`schema_names == tool_names | {SUBMIT_TOOL}` with `ls` present in `_tool_schemas()` and `build_explorer_tools`).
- Tests fail: `build_explorer_tools` returns only three keys (no `ls`); `_tool_schemas()` advertises no `ls`; the count assertion still says three.

### Step 4 — Implement `ls` tool + amend the exact-count convention (GREEN) [build]
- Implement in `harpyja/scout/explorer_tools.py`: add a fourth closure `ls(path=".")` — `confine_path`-guarded single-directory listing, normalized to file-level `CodeSpan` records, clamped by `settings.scout_ls_max_entries`; return `{"grep","glob","read_span","ls"}`. Update the module docstring ("EXACTLY three" → "EXACTLY four", naming `ls` as the layout-discovery affordance `glob` lacks).
- Implement in `harpyja/scout/explorer_backend.py`: add the `ls` function schema to `_tool_schemas()`.
- Amend `.speccraft/conventions.md`: the exact-tool-count convention text `build_explorer_tools returns EXACTLY {grep, glob, read_span}` → `EXACTLY {grep, glob, read_span, ls}`, with a one-line rationale (a DELIBERATE, reconciled affordance change — the layout-discovery gap `glob` leaves, NOT silent weak-model tool creep — the very guard the convention exists for).
- All step-3 tests pass. (AC3)

### Step 5 — Backend map-removal + bounded, repo-size-independent turn-1 payload (RED) [unit]
- Amend `harpyja/scout/test_explorer_backend.py`:
  - `test_run_loop_injects_no_whole_repo_listing` — drive `_backend(...)` with a scripted `model_call` that captures the FIRST `messages` payload; assert no repo-manifest listing is present (no map record content) and the payload is a small constant.
  - `test_turn1_payload_under_token_bound_small_and_large_manifest` — run the backend twice, once with a SMALL synthetic `manifest` and once with a LARGE synthetic manifest (hundreds/thousands of entries); assert BOTH turn-1 payloads clear `len(payload)//4 <= 2000` tokens (`<= ~8000` chars) AND are within a small delta of each other (repo-size independence — the map is built in `_run_loop`, not `run_explorer_loop`, so this MUST be asserted at the backend level).
- Tests fail: `_run_loop` still calls `build_context_map(self._manifest, ...)`, so the large manifest injects a repo-sized turn-1 prompt that blows the bound and diverges from the small case.

### Step 6 — Cut over to `context_map=""` (GREEN) [build]
- Implement in `harpyja/scout/explorer_backend.py`: in `_run_loop`, stop calling `build_context_map`; pass `context_map=""` to `run_explorer_loop` (the DECIDED cutover — zero repo content satisfies the full-removal invariant; `_Session` record-0 stays a contentless placeholder, keeping `_refresh_index().insert(1,…)` valid). Remove the now-unused `build_context_map` import. (Leave `context_map.py` module in place — the backend simply stops calling it; deleting record 0 is optional cleanup and NOT load-bearing.)
- All step-5 tests pass; the existing backend/loop tests still pass (loop signature unchanged). (AC1, AC2)

### Step 7 — Four-state cause taxonomy: per-cause degrade counts in the report layer (RED) [unit]
- Amend `harpyja/eval/test_runner.py`:
  - `test_aggregate_reports_per_cause_scout_degrade_counts` — build runs whose `notes` carry each of the four native-loop causes (`scout-degraded:model-unreachable`, `:backend-error`, `:loop-turns-exhausted`, `:loop-wallclock-exhausted`); assert the aggregate carries a SEPARATE count per cause, and that they sum consistently with the existing collapsed `scout_degrade_count` (the collapsed field is retained; per-cause is additive attribution).
  - `test_per_cause_counts_distinguish_wallclock_from_honest_empty` — a `loop-wallclock-exhausted` degrade and a low-turn honest-empty (`SUBMITTED`, no note) land in DISTINCT buckets — proving the discriminant is `ScoutUnavailable.cause` / `LoopResult.outcome`, NOT `turns_used` arithmetic.
- Amend `harpyja/eval/test_report.py`:
  - `test_report_schema_version_is_0027` — replaces `test_report_schema_version_is_0026`; asserts `SCHEMA_VERSION == "0027/1"`.
  - `test_per_cause_degrade_fields_default_via_aggregate_defaults` — a legacy/omitted-field aggregate block still passes `validate_report` because the new per-cause fields are in `_AGGREGATE_DEFAULTS` (additive-last-with-defaults).
- Tests fail: `runner.aggregate_outcomes` emits only the collapsed `scout_degrade_count`; `SCHEMA_VERSION` is `"0026/1"`; the per-cause fields are absent from `_AGGREGATE_DEFAULTS` / the validator field set.

### Step 8 — Per-cause degrade plumbing + SCHEMA_VERSION bump (GREEN) [build]
- Implement in `harpyja/eval/runner.py`: add a cause-extracting helper (parse the `<cause>` token out of a `scout-degraded:<cause>` note, tolerant of the `+no-matches` suffix) and emit per-cause counts for the four native-loop causes alongside the retained collapsed `scout_degrade_count`. `_is_scout_degraded` stays the union predicate feeding `degraded_dominated` (unchanged dominance semantics).
- Implement in `harpyja/eval/report.py`: append the per-cause fields LAST in the aggregate field list AND in `_AGGREGATE_DEFAULTS` (default 0), with a comment noting `LOOP_WALLCLOCK_EXHAUSTED` is the PRE-EXISTING spec-0024 between-turns ceiling merely surfaced per-cause (not new scope); bump `SCHEMA_VERSION` `"0026/1"` → `"0027/1"`.
- All step-7 tests pass. (AC4)

### Step 9 — Retire `turns_used` as a why-did-it-end signal (RED→guard) [unit]
- Add `harpyja/scout/test_turns_used_not_a_diagnostic.py` (or extend `test_explorer_backend.py`):
  - `test_no_turns_used_based_outcome_inference_in_scout_and_eval` — an EXECUTABLE guard (grep-sweep-as-test over `harpyja/scout` + `harpyja/eval` source): assert no `turns_used`/`last_turns_used` appears in a comparison that infers run outcome/degrade-kind (e.g. `turns_used == cap`, `turns_used is None` used as a why-did-it-end discriminant). The only sanctioned uses are the migrated 0022 turns-CONSUMED measurement (`LoopResult.turns_used`, `last_turns_used`, `locate_probe` recording) — assert those specific measurement sites are the sole matches.
  - `test_backend_exhaustion_cause_derives_from_loopresult_outcome_not_turns` — pin that the backend maps the terminal degrade cause off `result.outcome` (`_EXHAUSTION_CAUSE[result.outcome]`), independent of `result.turns_used` (e.g. a WALLCLOCK_EXHAUSTED with a sub-cap `turns_used` still yields `LOOP_WALLCLOCK_EXHAUSTED`).
- Tests may PASS immediately (the current code already routes on `outcome`) — that is the intended guard outcome; if the sweep finds any `turns_used`-based inference, remove it in the paired GREEN before the guard goes green. (AC8)

### Step 10 — Truncation still fires + citation-preserving with the map absent (RED) [unit]
- Amend `harpyja/scout/test_explorer_loop.py`:
  - `test_truncation_still_fires_past_cap_with_empty_context_map` — run `run_explorer_loop(..., context_map="")` with enough tool output to exceed `scout_history_char_cap`; assert `maybe_truncate` still tombstones stale `kind=="tool"` records (the mechanism is unchanged; onset merely shifts later without the ~40K map term).
  - `test_empty_map_truncation_preserves_older_citable_observation` — the 0024 preservation negative with `context_map=""`: a final citation depending on an observation OLDER than the truncation threshold STILL resolves after truncation runs (never converted to honest-empty).
- Tests fail if written against a build where the empty-map path regressed truncation; they pin the invariant holds with no map record content. (AC9)

### Step 11 — Refactor (optional) [build]
- If the per-cause cause-token parsing (Step 8) duplicates the `scout-degraded:<cause>` spelling that `orchestrator/locate.py` and `_has_degrade_note` already own, centralize the cause-suffix extraction in ONE helper the runner reads (mirroring `_has_degrade_note`), so the note format has a single parse authority.
- All tests still pass.

### Step 12 — Live astropy + django localization proof, N=10, no timeout/backend degrade (RED→integration) [integration]
- Add to `harpyja/eval/test_locate_probe.py` (or a sibling `test_harness_live.py`), all `@pytest.mark.integration`, skip-not-fail via `scout_stack_available` / `require_live_stack`:
  - `test_astropy_12907_localizes_without_degrade_within_10_turns` — case `astropy__astropy-12907` (worktree `eval_work/worktrees/astropy__astropy-12907`; gold `astropy/modeling/separable.py` 242–248), hand-authored terse query; assert bucket ∈ `{right-file-wrong-span, correct}` (via `classify_case`), `turns_used <= 10`, and the terminal outcome is NOT `MODEL_UNREACHABLE`/`BACKEND_ERROR`.
  - `test_django_12774_localizes_without_degrade_within_10_turns` — case `django__django-12774` (2,611 `.py`; gold `django/db/models/query.py` 689–695), hand-authored terse query; same assertions.
- Tests fail (or skip where the live stack is absent): they require the map-removal + `ls` tool to be live on the served 16B `--jinja` stack at `127.0.0.1:8131/v1`.
- **DELEGATED** — the two live 16B runs execute on the operator/served stack, not in CI.

### Step 13 — Live turn-1 payload measurement + committed evidence artifact (GREEN→integration) [integration]
- Extend the Step-12 integration path to record, per case: turn-1 payload size (chars + `len//4` tokens), per-turn latency, turns used, terminal `LoopResult.outcome` / `ScoutUnavailable.cause`, and the localization bucket.
- Assert LIVE the turn-1 payload dropped from the ~10,181-token regression to the AC1 bound (`<= 2000` tokens) and per-turn latency is no longer map-prefill-dominated.
- Write a committed evidence artifact `specs/0027-harness/operator-run-findings.md` (mirroring the operator-run-findings pattern) capturing the per-case measurements — the durable "AC5 is the whole spec" proof, not a transient skip-not-fail run.
- **DELEGATED** — produced from the live runs. (AC5, AC6)

### Step 14 — AC7 doc-correction consistency verification (build/guard) [build]
- Verify (do NOT re-litigate) that the 0026-only scoping already landed in `0fdcb57` is consistent across the three surfaces: this spec's AC7, `specs/0026-eval/rca-explorer-context-bloat.md` Impact, and `specs/0026-eval/operator-run-findings.md` correction note — the record states 0026 ran through `ExplorerBackend`/the eager map (timeout-confounded) and 0020–0023 ran on the RETIRED FastContext backend (never called `build_context_map`, so this RCA does NOT bear on them — moot, NOT "confounded").
- If any surface drifted, correct it to match; otherwise assert consistency and move on. (AC7)

## Delegation

- Step 12 (live astropy + django localization) → delegate to the **operator/live-16B run** (reason: requires the served llama.cpp `--jinja` 16B stack at `127.0.0.1:8131/v1` + the SWE-bench worktrees under `eval_work/worktrees/`; `skip-not-fail` in CI, `require_live_stack` for the deliverable run — matches the operator-run pattern, not a unit harness).
- Step 13 (live payload measurement + committed evidence artifact) → same **operator/live-16B run** (reason: the durable AC5/AC6 proof is a measurement over the live stack; the artifact is the deliverable).
- All other steps (1–11, 14) → **tdd-implementer** in-repo under `uv run pytest -m "not integration"` (pure unit/build, deterministic fakes, no network).

## Risk

- **Blind-start swing (the opposite failure the `ls` tool guards):** removing the map could send the model into aimless `grep`/`glob`/`ls` that exhausts N=10 turns or the wall-clock ceiling → a NEW `LOOP_TURNS_EXHAUSTED`/`LOOP_WALLCLOCK_EXHAUSTED` degrade. → Mitigation: AC4's per-cause taxonomy (Step 8) NAMES this outcome distinctly from a timeout/backend degrade, so a genuine blind-start exhaustion is diagnosable and — per Decision 2 — triggers a minimal-orientation FOLLOW-UP that must re-run AC5/AC6 fresh; it is not pre-scaffolded here.
- **`context_map=""` leaves a contentless `_Session` record 0:** a future reader could mistake the empty record for a live map term. → Mitigation: Step 5's `test_run_loop_injects_no_whole_repo_listing` pins zero repo content; the optional record-0 deletion is explicitly deferred as non-load-bearing.
- **Live proof unreproducible / stack unavailable:** `skip-not-fail` could let the load-bearing AC5 silently skip. → Mitigation: the committed evidence artifact (Step 13) + `require_live_stack` convert the deliverable run into a hard fail-loud on skip, so the "whole spec" proof is durable, not a transient green-by-skip.
- **Per-cause note parsing drift:** parsing `<cause>` out of `scout-degraded:<cause>` could drift from `orchestrator/locate.py`'s note spelling (and the `+no-matches` suffix). → Mitigation: Step 11 centralizes the cause-suffix extraction in one helper alongside `_has_degrade_note`, single parse authority.
- **AC7 correction inaccuracy (worse than none):** an over-broad correction that re-implicates 0020–0023 would re-introduce the exact error `0fdcb57` fixed. → Mitigation: Step 14 is verify-consistency-only against the fixed commit, scoped to 0026, grounded in the 0024-introduced-the-map timeline.
