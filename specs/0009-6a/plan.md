---
spec: "0009-6a"
status: planned
strategy: tdd
---

# Plan — 0009-6a Wave 6a — Eval harness + OQ2 calibration

A NEW measurement-only package `harpyja/eval/`. INVARIANT: it observes the system
under test through the real `harpyja.orchestrator.locate.locate(...)` seam and never
modifies tier/gate/matrix behavior. It emits a recommendation (OQ2 trade-off table +
recommended `(verify_threshold, verify_top_n)`); it does NOT flip any `Settings`
default (follow-up spec).

## Module split

| Module | Responsibility | ACs |
|--------|----------------|-----|
| `harpyja/eval/dataset.py` | `EvalCase` dataclass, fixture loader, typed `DatasetError` | AC1 |
| `harpyja/eval/metrics.py` | D2 span-hit oracle (primary line-overlap + secondary proximity); D3 single oracle; aggregate metrics (escalation, Tier-0/1 resolve, gate catch / false-escalation scoped to point subset) | AC2, AC3 |
| `harpyja/eval/config.py` | `EvalConfig` dataclass (K, proximity-window, N-floor, catch-rate bar); `aggregate_runs` mean+spread | AC5 (part), AC6 (part) |
| `harpyja/eval/report.py` | Pinned JSON schema, serialize, `validate_report`, artifact-dir-outside-repo guard | AC4, AC7 |
| `harpyja/eval/runner.py` | Drives `locate(...)` auto path (injected fakes for unit, live build for integration); assembles per-case events + aggregate into a report | AC4, AC7 |
| `harpyja/eval/recommend.py` | Variance rule (`prefer`), lexicographic OQ2 scorer (`rank_sweep`), N-floor caveat | AC5, AC8 |
| `harpyja/eval/sweep.py` | Enumerate `verify_threshold` × `verify_top_n` grid via `dataclasses.replace`, K runs/point, per-point mean+spread | AC6, AC8 |
| `harpyja/eval/fixtures/` | Vendored OSS legacy repo at pinned rev + hand-labeled `seed.jsonl` (D1) | AC7, AC8 |

Tests live NEXT TO each module: `harpyja/eval/test_dataset.py`,
`test_metrics.py`, `test_config.py`, `test_report.py`, `test_runner.py`,
`test_recommend.py`, `test_sweep.py`, and `test_eval_integration.py`
(`@pytest.mark.integration`, skip-not-fail).

## Design decisions (folded-in review refinements)

**K placement — `EvalConfig`, NOT `Settings`.** K (repeated-run count) is eval-only and
inert to every tier/gate/matrix branch. The only `Settings` fields the sweep overrides
are `verify_threshold` / `verify_top_n` — those are *real* SUT fields built via
`dataclasses.replace` and read by `locate`/`gate`. K is orthogonal: it is a loop count
the runner consumes, never a `replace` dimension `locate` reads. Putting it in the
production frozen `Settings` is a coupling smell with no compensating uniformity benefit
(K and threshold/top_n do not compose in one `replace` that the SUT consults — only the
latter two reach the SUT). So K, the proximity-window, the N-floor, and the catch-rate
bar live on a dedicated `EvalConfig` dataclass in `harpyja/eval/config.py`.
**Reconciliation flag (non-blocking):** the spec body's line "additive eval-only
`Settings` field carrying K" should be reconciled to "eval-only `EvalConfig`" in a later
doc pass. Does not block the plan.

**D1 (gate-metric denominator scope).** `gate_catch_rate` and `gate_false_escalation`
are computed ONLY over the gate-eligible (point-query) subset, selected by the fixture's
`classification == "point"` label. Broad queries route straight to Deep per the 0008
matrix and are EXCLUDED from both gate denominators. `escalation_rate`
("% auto queries reaching Tier-2") is a SEPARATE aggregate over ALL auto cases (both
paths) and must never be conflated. Baked into the metric function signatures (they take
the case's classification) and asserted by
`test_gate_metrics_scoped_to_point_subset_excludes_broad`.

**D2 (zero-denominator sentinel).** Undefined metric → JSON `null` plus a sibling count
field carrying the denominator (`gate_catch_rate: null`, `wrong_tier1_count: 0`). AC7
"all metrics populated" is satisfied by an explicit-null-with-count (a populated field,
not an omitted one). Fixture authoring constraint: the seed set MUST contain >= 1
wrong-Tier-1 AND >= 1 correct-Tier-1 *point* case so the live denominators are non-zero;
asserted by `test_eval_all_metrics_populated_or_explicit_null_with_count`. (Interacts
with D1: the point sub-population sizes must still clear the N-floor.)

**D3 (variance rule — pinned).** Spread statistic = population standard deviation
(`statistics.pstdev`) over the K runs. The recommendation helper prefers candidate A over
the incumbent B for a metric iff `mean(A) - mean(B) > pstdev(B)` — advantage strictly
exceeds the **incumbent's** spread (conservative; a single statistic, fully
deterministic). Single-run K=1 → spread = 0. Implemented in
`recommend.prefer(...)`; asserted by `test_recommend_prefers_config_when_advantage_exceeds_spread`
and `test_recommend_keeps_incumbent_under_noise`.

**D4 (sweep ranking / cost function — pinned).** `rank_sweep` is a deterministic
lexicographic scorer:
1. Keep only grid points whose mean `gate_catch_rate >= catch_rate_bar`
   (provisional 0.90).
2. Among survivors, minimize mean `gate_false_escalation`.
3. Tie-break: lower `verify_top_n` (cost).
4. Tie-break: lower `verify_threshold` (deterministic final order).
The incumbent `(0.6, 3)` is only displaced by a survivor whose advantage exceeds variance
per D3; otherwise the incumbent is recorded as **validated**, not guessed. The fixed input
table always yields the same winner (`test_scorer_deterministic_winner_from_fixed_table`).

**D5 (multi-citation reduction).** A Tier-1 result is **correct** iff ANY evaluated
citation overlaps ANY expected span in the SAME file (the D2 primary line-overlap oracle).
This single oracle is reused by span-hit, catch-rate, AND false-escalation — there is no
second notion of correctness. Asserted by
`test_tier1_correctness_any_citation_any_expected_span_same_file` and
`test_gate_metrics_use_same_oracle_as_span_hit`.

**D6 (pinned provisional magnitudes).** `N_FLOOR = 30` cases; `PROXIMITY_WINDOW_LINES = 50`;
`CATCH_RATE_BAR = 0.90`. All three are provisional `EvalConfig` defaults (marked
tunable-once-N-grows, parity with the existing 0.90 bar). Touching ranges
(`a.end == b.start`) count as a primary overlap — pinned in the metric docstring and a
boundary test.

**D7 (pinned report schema — enumerated top-level fields).**
- `schema_version: str`
- `run_metadata`: `{ repo_revision, seed_n, n_floor, indicative_only: bool, mode,
  k_runs, settings_snapshot: {verify_method, verify_threshold, verify_top_n}, timestamp,
  artifact_dir }`
- `cases`: list of per-case events, each
  `{ case_id, query, classification ("point"|"broad"), expected_spans,
  citations: [{path, start_line, end_line, source_tier, score}], tiers_run,
  terminal_tier, escalated_to_deep (2 in tiers_run), gate_eligible (classification ==
  "point"), gate_triggered, tier1_correct (bool|null per D3/D5), span_hit_primary,
  span_hit_secondary, notes }`
- `aggregate`: `{ span_hit_rate_primary, span_hit_rate_secondary, escalation_rate,
  tier01_resolve_rate, gate_catch_rate (float|null), caught_count, wrong_tier1_count,
  gate_false_escalation (float|null), false_escalated_count, correct_tier1_count,
  per_tier_latency_ms, per_tier_model_calls }`
- Multi-run / sweep reports wrap each aggregate metric as `{mean, spread}`; sweep adds
  `sweep: [ {verify_threshold, verify_top_n, aggregate(mean+spread)} ]` and
  `recommendation: { verify_threshold, verify_top_n, catch_rate_bar, advantage_exceeds_variance,
  incumbent_validated, rationale }`.

## Test-first sequence

### Step 1 — Dataset loader (RED) — AC1
- Add `harpyja/eval/test_dataset.py`:
  - `test_load_dataset_parses_valid_fixture` — a well-formed fixture yields `EvalCase`
    objects with `query`, `repo`, `expected_spans` (file+line range), `classification`.
  - `test_load_dataset_rejects_missing_expected_span` — typed `DatasetError`.
  - `test_load_dataset_rejects_unknown_classification_label` — only `point`/`broad`.
  - `test_load_dataset_raises_typed_error_never_silent_skip` — a malformed row raises;
    no case is silently dropped (count assertion + exception type).
- Tests fail: `harpyja/eval/dataset.py` does not exist.

### Step 2 — Dataset loader (GREEN) — AC1
- Implement `harpyja/eval/dataset.py`: `EvalCase` (frozen dataclass, fully annotated),
  `ExpectedSpan`, `DatasetError`, `load_dataset(path) -> list[EvalCase]` that parses the
  JSONL fixture and raises `DatasetError` on any malformed/missing field (never skips).
- All Step-1 tests pass.

### Step 3 — Span-hit oracle (RED) — AC2
- Add `harpyja/eval/test_metrics.py`:
  - `test_span_hit_primary_overlap_true_on_partial_overlap`
  - `test_span_hit_primary_touching_ranges` — `end == start` counts as overlap (D6).
  - `test_span_hit_primary_false_on_same_file_disjoint`
  - `test_span_hit_primary_false_on_different_file`
  - `test_span_hit_secondary_true_within_proximity_window` — within `PROXIMITY_WINDOW_LINES`.
  - `test_span_hit_secondary_false_outside_proximity_window`
  - `test_span_hit_secondary_false_on_different_file`
- Tests fail: `harpyja/eval/metrics.py` does not exist.

### Step 4 — Span-hit oracle (GREEN) — AC2
- Implement `harpyja/eval/metrics.py`: `span_hit_primary(cited, expected) -> bool`
  (same-file line-range overlap, touching = overlap) and
  `span_hit_secondary(cited, expected, window) -> bool` (same file within proximity
  window). The proximity window is passed in (sourced from `EvalConfig` in Step 8).
- All Step-3 tests pass.

### Step 5 — Aggregate + gate metrics (RED) — AC3, D1, D2, D5
- Extend `harpyja/eval/test_metrics.py`:
  - `test_escalation_rate_counts_tier2_over_all_auto_cases` — `2 in tiers_run`, ALL cases.
  - `test_tier01_resolve_rate`
  - `test_gate_metrics_scoped_to_point_subset_excludes_broad` — broad cases excluded
    from both gate denominators (D1).
  - `test_gate_catch_rate_over_wrong_tier1_denominator`
  - `test_gate_false_escalation_rate_over_correct_tier1_denominator`
  - `test_gate_metrics_use_same_oracle_as_span_hit` — catch-rate & false-escalation call
    the SAME overlap oracle as span-hit (D3-spec / D5).
  - `test_tier1_correctness_any_citation_any_expected_span_same_file` — any/any reduction (D5).
  - `test_gate_catch_rate_null_with_count_on_zero_denominator` — `None` + count (D2).
  - `test_gate_false_escalation_null_with_count_on_zero_denominator`
- Tests fail: aggregate/gate functions not implemented.

### Step 6 — Aggregate + gate metrics (GREEN) — AC3
- Extend `harpyja/eval/metrics.py`: `tier1_correct(case) -> bool|None` (D5 any/any over
  same oracle), `escalation_rate(cases)`, `tier01_resolve_rate(cases)`,
  `gate_catch_rate(point_cases) -> (value|None, caught, wrong_total)`,
  `gate_false_escalation(point_cases) -> (value|None, false_escalated, correct_total)`.
  Gate functions filter to `classification == "point"`; broad excluded. Null-with-count
  sentinel on zero denominator.
- All Step-5 tests pass.

### Step 7 — EvalConfig + repeated-run aggregation (RED) — AC5 (part)
- Add `harpyja/eval/test_config.py`:
  - `test_eval_config_defaults_pin_provisional_constants` — `K`, `PROXIMITY_WINDOW_LINES=50`,
    `N_FLOOR=30`, `CATCH_RATE_BAR=0.90` (D6).
  - `test_eval_config_is_independent_of_settings` — `EvalConfig` field names disjoint from
    `Settings` field names (K-placement guard: eval knobs never leak into the frozen SUT config).
  - `test_aggregate_runs_mean_and_spread_pstdev` — K run-values → `{mean, spread=pstdev}`.
  - `test_aggregate_runs_single_run_zero_spread` — K=1 → spread 0.
- Tests fail: `harpyja/eval/config.py` does not exist.

### Step 8 — EvalConfig + repeated-run aggregation (GREEN) — AC5 (part)
- Implement `harpyja/eval/config.py`: frozen `EvalConfig` (K, proximity_window, n_floor,
  catch_rate_bar) and `aggregate_runs(values) -> {mean, spread}` (`statistics.mean` /
  `pstdev`). Wire Step-4 secondary metric to read `proximity_window` from `EvalConfig`.
- All Step-7 tests pass.

### Step 9 — Report schema (RED) — AC4, AC7, D7
- Add `harpyja/eval/test_report.py`:
  - `test_report_top_level_fields_present` — `schema_version`, `run_metadata`, `cases`,
    `aggregate` (D7).
  - `test_report_conforms_to_pinned_schema` — `validate_report` accepts a well-formed report.
  - `test_validate_report_rejects_missing_field` — typed error on a dropped field.
  - `test_report_undefined_metric_serialized_as_null_with_count` — D2 sentinel round-trips.
  - `test_artifact_dir_must_be_outside_indexed_repo` — guard raises when output dir is
    inside `repo_path` (read-only guardrail).
- Tests fail: `harpyja/eval/report.py` does not exist.

### Step 10 — Report schema (GREEN) — AC4, AC7
- Implement `harpyja/eval/report.py`: the D7 schema (constants for field names),
  `build_report(...)`, `validate_report(report)`, `write_report(report, out_dir,
  repo_path)` (atomic same-dir temp + `os.replace`; raises if `out_dir` is within
  `repo_path`, mirroring the FastContext `trajectory_file` precedent).
- All Step-9 tests pass.

### Step 11 — Runner over fakes (RED) — AC4
- Add `harpyja/eval/test_runner.py`:
  - `test_runner_drives_auto_path_with_injected_fakes` — calls
    `locate(req, settings, engine=fake, scout_engine=fake, deep_engine=fake, gate=fake, ...)`
    for each case; no live model.
  - `test_runner_assembles_report_without_live_model` — produces a report dict.
  - `test_runner_report_conforms_to_schema` — `validate_report` passes on runner output.
  - `test_runner_writes_artifacts_outside_repo` — artifacts land outside the indexed repo.
  - `test_runner_per_case_records_gate_decision_fields` — per-case `gate_eligible`,
    `gate_triggered`, `tier1_correct`, `escalated_to_deep`, `terminal_tier` populated
    from `LocateResult.tiers_run` / notes.
- Tests fail: `harpyja/eval/runner.py` does not exist.

### Step 12 — Runner over fakes (GREEN) — AC4
- Implement `harpyja/eval/runner.py`: `run_case(case, settings, *, engine, scout_engine,
  deep_engine, gate, ...) -> CaseEvent` (drives the real `locate`, derives
  `escalated_to_deep = 2 in tiers_run`, `terminal_tier = max(tiers_run)`, span-hit +
  D5 `tier1_correct`), and `run_dataset(cases, settings, eval_config, *, fakes, out_dir,
  repo_path) -> report`. Aggregates via `metrics.*` and writes via `report.write_report`.
- All Step-11 tests pass.

### Step 13 — Recommendation helper + OQ2 scorer (RED) — AC5, AC8, D3, D4
- Add `harpyja/eval/test_recommend.py`:
  - `test_recommend_prefers_config_when_advantage_exceeds_spread` — clear-signal fixture (D3).
  - `test_recommend_keeps_incumbent_under_noise` — high-variance fixture: advantage within
    spread → incumbent kept (D3).
  - `test_scorer_filters_points_below_catch_rate_bar` — D4 step 1.
  - `test_scorer_minimizes_false_escalation_then_lower_top_n` — D4 steps 2-3.
  - `test_scorer_deterministic_winner_from_fixed_table` — same table → same winner (D4).
  - `test_recommend_marks_incumbent_validated_when_no_alternative_beats_noise` — records
    `(0.6,3)` validated, not guessed.
- Tests fail: `harpyja/eval/recommend.py` does not exist.

### Step 14 — Recommendation helper + OQ2 scorer (GREEN) — AC5, AC8
- Implement `harpyja/eval/recommend.py`: `prefer(candidate, incumbent, metric) -> bool`
  (D3 `mean(A)-mean(B) > pstdev(B)`), `rank_sweep(points, eval_config) ->
  Recommendation` (D4 lexicographic scorer + variance gate vs incumbent `(0.6,3)`, sets
  `incumbent_validated`).
- All Step-13 tests pass.

### Step 15 — Sweep grid (RED) — AC6
- Add `harpyja/eval/test_sweep.py`:
  - `test_sweep_enumerates_threshold_top_n_grid` — full Cartesian product of the two axes.
  - `test_sweep_builds_each_point_via_dataclasses_replace` — each point is
    `dataclasses.replace(settings, verify_threshold=..., verify_top_n=...)` (asserted).
  - `test_sweep_does_not_mutate_settings` — base `Settings` instance unchanged after sweep.
  - `test_sweep_aggregates_per_point_mean_and_spread_over_k` — K runs/point → mean+spread.
- Tests fail: `harpyja/eval/sweep.py` does not exist.

### Step 16 — Sweep grid (GREEN) — AC6
- Implement `harpyja/eval/sweep.py`: `run_sweep(cases, base_settings, eval_config,
  thresholds, top_ns, *, fakes, out_dir, repo_path) -> sweep_report`. Builds each point
  via `dataclasses.replace`, runs `runner.run_dataset` K times, aggregates per point via
  `config.aggregate_runs`, and calls `recommend.rank_sweep`.
- All Step-15 tests pass.

### Step 17 — Refactor: single-oracle + report-assembly dedup (REFACTOR)
- Extract the shared overlap oracle so span-hit, catch-rate, and false-escalation call
  exactly one function (defends D3/D5 against drift). Collapse per-case event assembly
  duplicated between `runner.run_case` and the sweep path into one helper.
- All unit tests still pass.

### Step 18 — Live end-to-end (RED) — AC7
- Add `harpyja/eval/test_eval_integration.py` (`@pytest.mark.integration`, skip-not-fail,
  mirroring `orchestrator/test_locate_integration.py` stack-availability guard):
  - `test_eval_end_to_end_live_seed_set_schema_conforming` — seed set through the live
    stack (`build_scout_engine` / `build_deep_engine` / `build_verification_gate`);
    `validate_report` passes.
  - `test_eval_all_metrics_populated_or_explicit_null_with_count` — every aggregate field
    present (value or null-with-count); seed set has >= 1 wrong- and >= 1 correct-Tier-1
    point case (D2 constraint).
  - `test_eval_air_gap_no_nonloopback_egress` — network-deny-style assertion: zero
    non-loopback egress during the run.
- Tests fail (or skip without the stack): no seed fixture, no live-build runner helper.

### Step 19 — Live end-to-end (GREEN) — AC7
- Add `harpyja/eval/fixtures/` — vendored OSS legacy repo at a pinned revision +
  hand-labeled `seed.jsonl` (D1), satisfying the D2 both-populations constraint and a
  documented "add a case" path. Add `runner.build_live_fakes(settings, repo)` (thin
  wrapper over the three `build_*` factories). Ensure `run_dataset` populates every D7
  aggregate field.
- Step-18 tests pass when the live stack is present; skip otherwise.

### Step 20 — Live OQ2 sweep (RED) — AC8
- Extend `harpyja/eval/test_eval_integration.py`:
  - `test_oq2_sweep_live_produces_recommendation` — live sweep over the seed set, K
    runs/point; trade-off table (mean+spread per point) backs a recommended
    `(verify_threshold, verify_top_n)`.
  - `test_oq2_sweep_applies_n_floor_caveat_below_floor` — when `seed_n < N_FLOOR`, the
    report's `run_metadata.indicative_only` is `True` and the recommendation carries the
    caveat (deterministic via the pinned `N_FLOOR=30`).
- Tests fail (or skip): live sweep entrypoint + N-floor caveat not yet wired.

### Step 21 — Live OQ2 sweep (GREEN) — AC8
- Wire `sweep.run_sweep` into a thin `eval` entrypoint that runs the live OQ2 grid,
  emits the trade-off table + recommendation, and sets `indicative_only` /
  N-floor caveat from `EvalConfig.n_floor`. Record the recommendation, table (with
  spread), catch-rate bar, and N caveat as the changelog deliverable — DO NOT edit any
  `Settings` default (B1).
- Step-20 tests pass when the live stack is present; skip otherwise.

## Delegation

- Step 19 (vendored OSS repo + hand-labeled spans) → delegate fixture curation to a
  dataset-curation pass (reason: hand-labeling expected spans on a real legacy tree is
  label-authoring work, separable from harness code; the harness contract is already
  pinned by the unit ACs).
- Steps 18-21 (integration) → delegate live runs to an operator with the full stack
  (FastContext + dspy + Deno + rg + loopback endpoint with the Deep driver model), since
  unit ACs pin every deterministic shape and integration is skip-not-fail elsewhere.

## Risk

- Live model non-determinism could make the recommendation flap → mitigation: the D3
  variance gate (advantage > incumbent spread) and K repeated runs; a within-noise result
  records the incumbent `(0.6,3)` as validated rather than flipping.
- Two implementers diverging on gate denominators or correctness → mitigation: D1 point-only
  scoping and the D3/D5 single-oracle are baked into function signatures and asserted by
  `test_gate_metrics_scoped_to_point_subset_excludes_broad` and
  `test_gate_metrics_use_same_oracle_as_span_hit`.
- Small seed N → mitigation: pinned `N_FLOOR=30`, `indicative_only` flag, and AC8 caveat
  branch; the both-populations fixture constraint keeps gate denominators non-zero.
- Harness accidentally writing into an indexed repo → mitigation: `write_report` raises
  when the output dir is inside `repo_path`; asserted in unit and integration.
- INVARIANT drift (harness mutating SUT) → mitigation: K lives on `EvalConfig` not
  `Settings`; sweep builds points via `dataclasses.replace` only; `test_sweep_does_not_mutate_settings`.
