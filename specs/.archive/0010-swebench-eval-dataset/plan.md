---
spec: "0010"
status: planned
strategy: tdd
---

# Plan — 0010 SWE-bench Verified eval dataset

Python 3.12 / pytest. Tests live next to the package as `test_*.py`; async driven by
`asyncio.run`, never pytest-asyncio. `@pytest.mark.integration` = skip-not-fail.
Every GREEN is preceded by a RED. Production seams are grounded in the real code:
`EvalCase` (5 frozen fields, `dataset.py:44`), `LocateStack.classifier` seam
(`runner.py:43`, forwarded verbatim into `locate`), `run_case` hardcoded
`mode="auto"` (`runner.py:128`), the single-repo `run_dataset` (`runner.py:214`),
the pinned `validate_report` / `SCHEMA_VERSION="0009-6a/1"` (`report.py:24`), the one
overlap oracle `_any_primary_overlap` (`metrics.py:72`), `aggregate_outcomes`
(`runner.py:178`), `atomic_write_json` outside-repo guard (`report.py:129`), and the
sweep grid via `dataclasses.replace` (`sweep.py:60`).

New production surface this wave:
- `harpyja/eval/swebench_eval.py` (NEW) — `parse_patch` / `FileTarget`, `_to_eval_case`,
  patch-shape classification + threshold constant, new-file flagging, `convert` /
  `provision` / `prune`, the **per-case-repo driver** (own `repo_path` + own
  `LocateStack` with the D-route classifier injected, pooling into the unchanged
  `metrics` + `aggregate_outcomes`), and the `run` / `sweep` CLI subcommands.
- `harpyja/eval/runner.py` — thread a `mode` param into `run_case` (AC7 seam).
- `harpyja/eval/report.py` — additive durable fields, `SCHEMA_VERSION` bump; both the
  0009-6a single-run shape and the new multi-repo shape still validate.
- Root `Makefile` (NEW), `.gitignore`, `pyproject.toml` (`uv add datasets`).

New test files (rationale):
- `harpyja/eval/test_swebench_eval.py` — pure/stack-free units: `parse_patch`,
  `_to_eval_case` round-trip, classification, new-file, convert (mocked HF), CLI
  missing-fixture, Makefile recipe inspection.
- `harpyja/eval/test_swebench_runner.py` — the per-case-repo **driver** units
  (multi-repo pooling, D-route override + agreement, `mode=fast` block, durable
  metadata/provenance, per-case timeout + sample cap) — kept separate from the
  pure-data units because they inject fake stacks and exercise the driver.
- `harpyja/eval/test_swebench_integration.py` — AC10/AC11 + a live `convert` smoke,
  all `@pytest.mark.integration`, skip-not-fail.
Extend in place: `test_report.py` (additive schema, AC8), `test_runner.py`
(`run_case` mode seam, AC7).

## Test-first sequence

### Phase 0 — Plumbing

#### Step 1 — datasets dep + ignores (plumbing, verifiable)
- `uv add datasets` (HuggingFace, used by `convert` only — dev-time, off the
  `locate()` path, out of the air-gap guarantee per R8).
- `.gitignore`: add `eval_work/` and `swebench_verified.resolved.jsonl`; keep
  `swebench_verified.raw.jsonl` **tracked**.
- Verify: `uv run python -c "import datasets"` succeeds; `git check-ignore` reports
  `eval_work/` and the resolved fixture ignored, raw fixture not ignored.

### Phase 1 — Report schema (additive, foundation for the driver)

#### Step 2 — Additive durable report fields (RED) — AC8
- Extend `harpyja/eval/test_report.py`:
  - `test_report_schema_version_bumped` — `SCHEMA_VERSION` is no longer `"0009-6a/1"`.
  - `test_report_legacy_single_run_shape_still_validates` — a `build_report` from the
    0009-6a three blocks (no new fields supplied) still passes `validate_report`
    (new fields default-populated, appended-last).
  - `test_report_multi_repo_shape_validates` — a report carrying the new
    metadata/aggregate/case fields validates.
  - `test_report_requires_new_durable_metadata_fields` — `validate_report` rejects a
    report missing `protocol`, `new_file_only_excluded_count`,
    `malformed_skipped_count`, `classifier_agreement_rate`, `span_inflation_tolerance`,
    `contamination_caveat`, `dataset_provenance`.
  - `test_report_requires_per_case_production_gate_ran` — a case missing
    `production_gate_ran` is rejected.
- Tests fail: `SCHEMA_VERSION` unchanged and the new field names are absent from
  `_RUN_METADATA_FIELDS` / `_CASE_FIELDS` / `_AGGREGATE_FIELDS`.

#### Step 3 — Bump + append schema fields with defaults (GREEN) — AC8
- `harpyja/eval/report.py`: bump `SCHEMA_VERSION` (e.g. `"0010/1"`); append-last to the
  field tuples: run_metadata `protocol`, `new_file_only_excluded_count`,
  `malformed_skipped_count`, `classifier_agreement_rate`, `span_inflation_tolerance`,
  `contamination_caveat`, `dataset_provenance` (object: `hf_dataset_id`, `hf_split`,
  `hf_revision`, `raw_fixture_sha256`, `sample_case_ids`); case `production_gate_ran`,
  `patch_shape_label`, `production_classifier_label`; aggregate
  `classifier_agreement_rate`. `build_report` injects schema-stable **defaults**
  (`"standalone-localization"` protocol, `0` counts, `None` rate, prose caveat) when a
  block omits them, so the 0009-6a path stays valid.
- All Step-2 tests pass.

### Phase 2 — Patch parsing + schema reconciliation (pure functions, no stack)

#### Step 4 — `parse_patch` pre-image oracle (RED) — AC1
- Add `harpyja/eval/test_swebench_eval.py`:
  - `test_parse_patch_single_hunk_preimage_range`
  - `test_parse_patch_multi_hunk_ranges`
  - `test_parse_patch_deletion_locatable_at_preimage_path` (`+++ /dev/null` → scored at `--- a/…`)
  - `test_parse_patch_all_new_file_flagged_is_new_file_no_spans` (`--- /dev/null` → `is_new_file`, no spans)
  - `test_parse_patch_pure_insertion_in_existing_file_anchored_one_line` (pre-image len 0 → concrete 1-line span, D-protocol/R6)
  - `test_parse_patch_malformed_skipped_loudly_with_counted_reason` (skips at instance level, never aborts the set)
- Tests fail: `swebench_eval` / `parse_patch` / `FileTarget` do not exist (ImportError).

#### Step 5 — Port `parse_patch` + `FileTarget` (GREEN) — AC1
- `harpyja/eval/swebench_eval.py`: port the upload's working `parse_patch` /
  `FileTarget` (pre-image hunk ranges; `is_new_file` for `--- /dev/null`; one-line
  anchor for zero-length insertion-in-existing-file); malformed text returns a counted
  skip-reason, never raises across the set.
- All Step-4 tests pass.

#### Step 6 — `_to_eval_case` round-trip + `base_commit` (RED) — AC2
- `test_swebench_eval.py`:
  - `test_to_eval_case_roundtrips_through_load_dataset` (no `DatasetError`)
  - `test_to_eval_case_emits_case_id_and_expected_spans_list_of_objects`
  - `test_to_eval_case_classification_in_point_broad`
  - `test_base_commit_present_in_raw_record_and_ignored_by_load_dataset`
  - `test_provision_reads_base_commit_from_raw_dict_not_eval_case`
- Tests fail: the uploaded `_to_eval_case` emits `id` / `expected`(dict) /
  `base_commit` / `language` / `new_file_only` — `load_dataset` raises `DatasetError`,
  and there is no `provision` reading `base_commit` from the raw dict.

#### Step 7 — Reconcile `_to_eval_case` + `provision` base_commit read (GREEN) — AC2
- `swebench_eval.py`: `_to_eval_case` emits the real `EvalCase` shape (`case_id`,
  `expected_spans` list-of-`{path,start_line,end_line}`, `classification ∈ {point,broad}`);
  `base_commit`/`language`/`new_file_only` live only in the **raw** record. `provision`
  reads `base_commit` via `_read_jsonl` directly (never through `load_dataset`),
  rewrites `repo` to the worktree at `base_commit`.
- All Step-6 tests pass.

#### Step 8 — Classification by patch shape + threshold constant (RED) — AC3
- `test_swebench_eval.py`:
  - `test_classify_single_file_small_span_is_point`
  - `test_classify_multi_file_is_broad`
  - `test_classify_single_file_over_threshold_span_is_broad`
  - `test_point_span_threshold_constant_boundary` (asserts the named constant at its boundary)
- Tests fail: no patch-shape classifier / named threshold constant exists.

#### Step 9 — Patch-shape classifier (GREEN) — AC3, D-class
- `swebench_eval.py`: named constant (e.g. `POINT_SPAN_MAX_LINES`, provisional);
  rule (frozen): single-file ∧ total pre-image span ≤ constant ⇒ `"point"`, else
  `"broad"`. Wired into `_to_eval_case`.
- All Step-8 tests pass.

#### Step 10 — New-file exclusion (RED) — AC4, D-newfile
- `test_swebench_eval.py`:
  - `test_all_new_file_instance_flagged_new_file_only`
  - `test_new_file_only_excluded_from_score_population` (exclusion helper drops it from scoring)
  - `test_new_file_only_count_is_durable_not_silent_zero`
- Tests fail: no `new_file_only` flag / no exclusion helper.

#### Step 11 — New-file flag + exclusion helper (GREEN) — AC4
- `swebench_eval.py`: flag `new_file_only` at convert (all targets `--- /dev/null`);
  an exclusion helper drops `new_file_only` cases from the scored population and
  returns the excluded count for the durable `new_file_only_excluded_count` field
  (no-false-capability: excluded, never a silent zero).
- All Step-10 tests pass.

### Phase 3 — convert / provision (networked dev-time tools)

#### Step 12 — `convert` over mocked HF + provenance (RED) — AC8 provenance
- `test_swebench_eval.py`:
  - `test_convert_with_mocked_hf_emits_raw_jsonl` (monkeypatch `datasets.load_dataset`; no network)
  - `test_convert_records_provenance_hf_id_split_revision`
  - `test_convert_records_raw_fixture_sha256_and_sample_case_ids`
  - `test_convert_counts_malformed_skipped_instances`
- Tests fail: `convert` (reconciled to the new schema) + provenance capture absent.

#### Step 13 — `convert` implementation (GREEN) — AC8 provenance
- `swebench_eval.py`: `convert` reads HF (lazy `import datasets`, dev-time, off the
  air-gap path), runs `parse_patch` + `_to_eval_case`, writes portable
  `swebench_verified.raw.jsonl`, and emits a provenance record (HF id/split/revision,
  sha256 over the raw bytes + record count, selected sample case-ids) + the
  malformed-skipped count for the report.
- All Step-12 tests pass.

### Phase 4 — `mode=fast` seam

#### Step 14 — `run_case` accepts `mode` (RED) — AC7 seam, R3
- Extend `harpyja/eval/test_runner.py`:
  - `test_run_case_accepts_mode_param`
  - `test_run_case_threads_mode_into_locate_request` (a `mode="fast"` run builds a
    `LocateRequest(mode="fast")`, asserted via a fake engine capturing the request)
- Tests fail: `run_case` hardcodes `mode="auto"` (`runner.py:128`) — no `mode` kwarg.

#### Step 15 — Thread `mode` through `run_case` (GREEN) — AC7 seam
- `harpyja/eval/runner.py`: add `mode: str = "auto"` to `run_case`, use it in the
  `LocateRequest`; `run_dataset` forwards its `mode` to `run_case` (today it only
  reaches metadata).
- All Step-14 tests pass; existing `run_dataset` tests unchanged.

### Phase 5 — Per-case-repo driver

#### Step 16 — Driver pools ≥2 distinct-repo cases (RED) — AC6
- Add `harpyja/eval/test_swebench_runner.py`:
  - `test_driver_drives_two_cases_each_distinct_repo_path` (each case's `repo` used as `repo_path`)
  - `test_driver_builds_own_stack_per_case` (a stack-factory hook is invoked per case)
  - `test_driver_pools_into_pinned_schema_report` (`validate_report` passes)
  - `test_driver_every_gate_metric_populated_or_null_with_count` (empty point subset ⇒ null-with-count, D2)
  - `test_driver_writes_artifacts_outside_every_case_repo` (`atomic_write_json` refuses inside any case repo)
- Tests fail: the multi-repo driver does not exist.

#### Step 17 — Per-case-repo driver (GREEN) — AC6
- `swebench_eval.py`: a driver (e.g. `run_swebench(cases, settings, eval_config, *,
  stack_factory, out_dir, mode="auto", ...)`) that, per case, uses `case.repo` as
  `repo_path`, builds its **own** `LocateStack` via `stack_factory` (real
  `build_live_stack`, or fakes in tests), drives `run_case`, and pools the
  `CaseOutcome`s through the unchanged `aggregate_outcomes` + the additive report.
  Writes via `atomic_write_json` to an out-of-tree dir.
- All Step-16 tests pass.

#### Step 18 — D-route override + agreement (RED) — AC5, D-route, B1
- `test_swebench_runner.py`:
  - `test_driver_injects_classifier_overriding_routing_to_point` (fake `classify_query`
    returns `"broad"`; the injected classifier forces `point`; gate fires)
  - `test_production_label_captured_before_override_installed` (agreement never reads
    the injected label — codex's self-observation guard)
  - `test_per_case_records_both_patch_shape_and_production_labels`
  - `test_aggregate_reports_classifier_agreement_rate`
  - `test_gate_fired_asserted_from_production_gate_ran_not_scout_probe`
    (`production_gate_ran` derived from `result.tiers_run` / `result.notes`)
  - `test_without_override_same_case_routes_broad_and_bypasses_gate`
- Tests fail: no classifier injection / agreement capture / `production_gate_ran`.

#### Step 19 — Inject classifier + record agreement (GREEN) — AC5, D-route
- `swebench_eval.py`: per case, first capture the **production** label
  `classify_query(query)`, *then* build the stack with
  `LocateStack(classifier=lambda *_: case.classification)`; record both labels per case
  and the SUT-observed `production_gate_ran` (from `result.tiers_run`/`notes`, kept
  distinct from the harness Scout-probe `gate_triggered`); aggregate the
  classifier-agreement rate.
- All Step-18 tests pass.

#### Step 20 — fast-vs-auto driver block (RED) — AC7 driver
- `test_swebench_runner.py`:
  - `test_driver_fast_mode_report_schema_conforming`
  - `test_driver_fast_mode_no_case_escalates_to_deep` (`escalated_to_deep is False` for all)
  - `test_driver_fast_block_distinct_from_auto_block`
- Tests fail: the driver does not yet pass `mode` into `run_case` / emit a `fast` block.

#### Step 21 — Driver `mode=fast` block (GREEN) — AC7
- `swebench_eval.py`: driver threads `mode` (default `auto`) into `run_case`; a
  `mode="fast"` run emits a Scout-terminal block (gate informational, never escalates)
  distinct from the `auto` block.
- All Step-20 tests pass.

#### Step 22 — Durable metadata + provenance populated (RED) — AC8, R2
- `test_swebench_runner.py`:
  - `test_report_carries_protocol_identity` (`standalone-localization`, no-harness/patch/test-exec)
  - `test_report_carries_new_file_only_excluded_count`
  - `test_report_carries_malformed_skipped_count`
  - `test_report_carries_classifier_agreement_rate`
  - `test_report_carries_span_inflation_tolerance` (D-protocol upward bias, R5)
  - `test_report_carries_contamination_caveat`
  - `test_report_carries_dataset_provenance` (HF id/split/revision, raw sha256, sample ids)
  - `test_per_case_production_gate_ran_distinct_from_gate_triggered`
- Tests fail: the driver leaves the (schema-accepted) fields at defaults; provenance is
  not threaded from `convert`/raw fixture into the report.

#### Step 23 — Populate metadata + provenance (GREEN) — AC8
- `swebench_eval.py`: thread provenance (from the resolved fixture sidecar /
  `_read_jsonl`), the new-file excluded count, malformed-skipped count, agreement rate,
  the span-inflation tolerance constant, and the contamination caveat into the report
  run_metadata; per-case `production_gate_ran`.
- All Step-22 tests pass.

#### Step 24 — Per-case timeout + sample cap (RED) — AC11 budget, R7
- `test_swebench_runner.py`:
  - `test_driver_honors_sample_cap` (caps the number of cases driven)
  - `test_driver_per_case_timeout_skips_loudly_with_count` (a slow fake stack is
    timed out and surfaced as a counted skip, never a hung run / silent zero)
- Tests fail: no timeout / cap in the driver.

#### Step 25 — Budget enforcement (GREEN) — AC11 budget
- `swebench_eval.py`: per-case wall-clock timeout + sample cap; timed-out cases are a
  counted, surfaced skip. (Bounds the N≥30 × grid × K runtime documented in AC11.)
- All Step-24 tests pass.

#### Step 26 — Refactor: one aggregate/metadata assembly (REFACTOR)
- Extract the additive run_metadata + aggregate assembly shared by
  `runner.run_dataset`, `sweep.run_sweep`, and the new driver into one helper so the
  durable fields cannot drift between the single-repo and multi-repo report families.
- All tests still pass.

### Phase 6 — CLI + Makefile

#### Step 27 — `run` / `sweep` CLI, missing fixture (RED) — AC9 unit, R1
- `test_swebench_eval.py`:
  - `test_run_subcommand_parses`
  - `test_sweep_subcommand_parses`
  - `test_run_missing_resolved_fixture_exits_nonzero_actionable`
  - `test_sweep_missing_resolved_fixture_exits_nonzero_actionable`
- Tests fail: no argparse entrypoint / subcommands.

#### Step 28 — argparse subcommands (GREEN) — AC9
- `swebench_eval.py`: `__main__` argparse with `convert` / `provision` / `prune` /
  `run` / `sweep`; `run`/`sweep` load the resolved fixture and, when it is absent, exit
  non-zero with an actionable message (run `make swebench-provision`). `run`/`sweep`
  build per-case stacks via `build_live_stack`.
- All Step-27 tests pass.

#### Step 29 — Makefile targets (RED) — AC9
- `test_swebench_eval.py`:
  - `test_makefile_run_target_invokes_swebench_eval_run`
  - `test_makefile_sweep_target_invokes_swebench_eval_sweep`
  - `test_makefile_does_not_reference_runner_fixture_placeholder`
    (the upload's `python -m harpyja.eval.runner --fixture …` must be gone)
- Tests fail: no root `Makefile`.

#### Step 30 — Create root Makefile (GREEN) — AC9
- Create root `Makefile` from the upload's `Makefile.swebench` targets, reconciled to
  call `python -m harpyja.eval.swebench_eval run|sweep` (and `convert`/`provision`/
  `prune`); a `swebench-full` target gated behind the sample passing (out of scope of
  the gating run).
- All Step-29 tests pass.

### Phase 7 — Integration (skip-not-fail)

#### Step 31 — AC10 live e2e + zero non-loopback egress (RED) — AC10
- Add `harpyja/eval/test_swebench_integration.py` (`@pytest.mark.integration`):
  - `test_swebench_e2e_live_auto_schema_conforming` (≥1 resolved case; reuse
    `_live_stack_available` pattern; skip if resolved fixture or stack absent)
  - `test_swebench_run_zero_nonloopback_egress` (reuse the `_deny_nonloopback_egress`
    contextmanager from `test_eval_integration.py`)
- Tests skip in constrained envs; with a live stack they exercise the driver via
  `build_live_stack`. Fail (when run live) until the run stage is fully wired.

#### Step 32 — Wire the live `auto` run path (GREEN) — AC10
- Ensure `run` drives each resolved case through real `build_live_stack` + the driver,
  fully offline; report validates; egress stays loopback-only.
- Step-31 tests pass (or skip).

#### Step 33 — AC11 live OQ2 sweep at scale (RED) — AC11
- `test_swebench_integration.py` (`@pytest.mark.integration`):
  - `test_swebench_oq2_sweep_tradeoff_table_and_recommendation` (mean + spread per grid point)
  - `test_swebench_sweep_indicative_only_false_when_n_ge_floor`
  - `test_swebench_sweep_asserts_no_settings_default_mutated`
    (mirror `test_sweep_does_not_mutate_settings`; `dataclasses.replace` only)
  - `test_swebench_sweep_honors_per_case_timeout_and_sample_cap` (runtime budget, R7)
  - `test_swebench_oq2_low_agreement_flags_deltas_only` (agreement-rate floor guard, round-2)
- Tests skip without a live stack; fail (live) until the multi-repo sweep is wired.

#### Step 34 — Wire the multi-repo sweep (GREEN) — AC11
- `swebench_eval.py` `sweep`: grid `threshold × top_n`, K runs/point over the resolved
  sample via the per-case-repo driver (each point via `dataclasses.replace`, never
  mutation), pooled into `recommend.rank_sweep`; honor the per-case timeout + sample
  cap; flag the OQ2 result **low-confidence (deltas-only)** below the agreement floor.
- Step-33 tests pass (or skip).

#### Step 35 — Live `convert` smoke (RED→GREEN) — AC8 / network
- `test_swebench_integration.py`: `test_convert_live_hf_smoke` (`@pytest.mark.integration`,
  skip without network / `datasets`) — `convert` over a tiny real HF slice emits the
  raw fixture + provenance. The unit coverage is the mocked Step-12 test; this is the
  networked counterpart. No further prod change beyond Step-13.

## Delegation

- Steps 4–13 (pure parsing / schema reconciliation / convert) → delegate to a
  `general-purpose` implementer: self-contained, fully unit-testable, no live stack.
- Steps 16–25 (the per-case-repo driver, D-route, fast block, budget) → keep with the
  eval-harness owner: load-bearing seam against `runner.py` / `metrics.py` /
  `report.py` invariants (one-oracle reuse, read-only writes, recommend-only).
- Steps 31–35 (integration) → delegate execution to an environment with the live stack
  (FastContext + dspy + Deno + rg + loopback endpoint + a provisioned sample); they
  skip elsewhere, so they gate locally only where the stack exists.

## Risk

- **Contamination (R4):** SWE-bench is public; absolute accuracy is not a
  generalization claim. → mitigation: lead with relative sweep-deltas / fast-vs-auto
  deltas; carry the contamination caveat as a durable report field; agreement-rate
  floor flags low-confidence runs (Step 22/34).
- **D-route honesty (B1):** the injected classifier is an evaluation *intervention*,
  not pure observation. → mitigation: capture the production label **before** the
  override (Step 18/19), record both labels + aggregate agreement, and gate the OQ2
  recommendation behind the agreement floor.
- **Schema dual-shape drift (AC8):** new fields could break the 0009-6a report. →
  mitigation: append-last-with-defaults + Step-2 tests that **both** families validate;
  Step-26 refactor centralizes assembly so the two cannot diverge.
- **AC11 runtime (N≥30 × grid × K, plausibly hours; 0009-6a was 5 cases = 634s):** →
  mitigation: per-case wall-clock timeout + sample cap unit-tested (Step 24/25),
  documented wall-clock budget, full-500 run opt-in only after the sample passes.
- **Network for `convert` (R8):** HF reach breaks offline CI. → mitigation: mocked HF
  unit (Step 12) is the gate; the live smoke (Step 35) is integration-gated; `convert`
  is explicitly out of the runtime air-gap guarantee (dev-time, off `locate()`).
- **Read-only on per-case repos:** the driver writes one report pooled across many
  worktrees. → mitigation: `atomic_write_json` refuses inside *any* case repo
  (Step 16), artifacts pooled out-of-tree.
