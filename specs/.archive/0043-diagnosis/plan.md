---
spec: "0043"
status: planned
strategy: tdd
---

# Plan — 0043 diagnosis

Date: 2026-07-12

Submission-gap diagnosis: attribute where the per-case budget goes from the
persisted `eval_work` trajectories (no new model compute), add a first-class
found-but-unsubmitted detector, attribute the 4b heavy-repo degrade inversion,
select a lever by a FROZEN decision table, freeze the re-measurement config,
implement the lever preserving the byte-frozen SUT pins, re-measure the 0042
pilot cells on the 0041-gated endpoint, and type the outcome.

## Plan-time decisions (do not re-open)

- **New modules land flat in `harpyja/eval/` with sibling `test_*.py`** (the
  0040/0041/0042 precedent). Chosen names:
  - `submission_gap.py` — the AC2 found-but-unsubmitted detector (pure projection
    over one persisted trajectory) + its `SubmissionOutcome` enum + `DETECTOR_VERSION`.
  - `clock_attribution.py` — the AC1 budget attributor + the AC3 4b-inversion
    attributor (both pure over persisted trajectories) + the committed
    derived-table serialization pinned to artifact filenames + content hashes.
  - `lever_table.py` — the AC4 stage-1 FROZEN attribution-to-lever decision table
    (hashed, committed BEFORE any attribution number is computed).
  - `diagnosis_config.py` — the AC5 stage-2 `PREREGISTERED_DIAGNOSIS_CONFIG_0043`
    (hashed, committed AFTER lever selection, BEFORE live spend).
  - `diagnosis_outcome.py` — the AC6 total pure `decide_diagnosis_outcome`
    4-branch verdict.
  - The live driver goes at `specs/0043-diagnosis/diagnosis_run/run_diagnosis.py`
    (specs/ is NOT on the pytest path — 0041/0042 precedent); its integration
    smoke lives in `harpyja/eval/test_diagnosis_run_integration.py` so the suite
    collects it (the `test_adoption_run_integration.py` / `test_gate_run_integration.py`
    precedent — the plan's "specs/ smoke" is realized in-package for collection).

- **One overlap oracle, reused (NOT re-defined).** The detector tests gold overlap
  through `harpyja/eval/metrics.py::span_hit_kind` (the SAME oracle the
  `LocateBucket` machinery uses) — a parsed `CodeSpan` counts as a hit only when
  `span_hit_kind` returns `"line"`; a `"file"` (path-only, no gold LINE overlap)
  or `None` is NOT a hit. The AC2 fixture's path-only row therefore types
  `never-found` by the oracle's line-overlap predicate, never by a second
  definition. `test_submission_gap_reuses_metrics_line_overlap_oracle` pins the
  reuse (mirrors `test_gate_metrics_use_same_oracle_as_span_hit`).

- **One submit-counter, reused (NOT re-parsed).** `submitted` vs
  `submitted-then-dropped` is decided from the EXISTING 0033
  `citations_submitted` / `citations_surviving` counts carried on the trajectory
  (`(>0, 0)` ⇒ dropped), NEVER re-derived from history parsing. Pinned by
  `test_submitted_then_dropped_routes_through_0033_counts_not_history`.

- **The two-stage freeze is sequenced in the task order and is load-bearing:**
  stage 1 (`lever_table.py` + committed artifact, T7–T8) lands BEFORE the offline
  attribution NUMBERS are computed/seen (T9); stage 2
  (`PREREGISTERED_DIAGNOSIS_CONFIG_0043`, T10–T11) lands AFTER the frozen table has
  mechanically selected the lever from the committed attribution but BEFORE any
  live spend (T16–T18). No task computes an attribution number before T9; no task
  spends live compute before T11.

- **Byte-frozen SUT pin survives (the 0034/0038/0042 standing pin).** Whatever
  lever T13 lands, the outbound `params == {"max_tokens": 2048}` at
  `explorer_think=None` stays byte-identical: a prompt nudge rides `messages`, a
  ceiling/turn-cap change is a deliberate named `Settings` change that never
  touches `_default_model_call`'s `params` assembly. The two pin tests
  (`test_explorer_backend.py` `params==2048` at `explorer_think=None`, and the
  0042 prompt↔surface drift guard) are asserted green after T13.

## Test-first sequence

### Step 1 — found-but-unsubmitted detector (RED) [AC2]
- Add `harpyja/eval/test_submission_gap.py`:
  - `test_submission_outcome_enum_is_total_over_fixture_matrix` — the 6-row
    fixture matrix, each row pinned to its enum value: tool-result hit →
    `FOUND_UNSUBMITTED`; submitted hit → `SUBMITTED`; submitted-then-dropped →
    `SUBMITTED_THEN_DROPPED`; path-only (file-level, no gold line overlap) →
    `NEVER_FOUND`; never-found → `NEVER_FOUND`; unparseable tool message →
    `DETECTOR_INCONCLUSIVE`. Asserts the enum has EXACTLY these 5 members.
  - `test_detector_parses_stringified_codespan_reprs_from_tool_role_messages` —
    a gold-overlapping `CodeSpan` repr inside a tool-role message is recovered and
    tested for overlap.
  - `test_submission_gap_reuses_metrics_line_overlap_oracle` — the reuse pin:
    the detector routes gold overlap through `metrics.span_hit_kind`, and a
    path-only span (`span_hit_kind=="file"`) is NOT counted as found.
  - `test_submitted_then_dropped_routes_through_0033_counts_not_history` —
    `SUBMITTED_THEN_DROPPED` is decided from `citations_submitted`/`citations_surviving`
    `(>0,0)`, never re-parsed from history.
  - `test_unparseable_tool_message_is_inconclusive_never_never_found` — an
    undecodable tool message yields `DETECTOR_INCONCLUSIVE`, never silently folded
    into `NEVER_FOUND`.
  - `test_detector_version_constant_present` — `DETECTOR_VERSION` exists (pinned so
    the config can cite it).
- Tests fail: `harpyja/eval/submission_gap.py` does not exist.

### Step 2 — detector implementation (GREEN) [AC2]
- Add `harpyja/eval/submission_gap.py`: `SubmissionOutcome` (5-member enum),
  `DETECTOR_VERSION`, and a total pure `classify_submission(trajectory) ->
  SubmissionOutcome` that parses stringified `CodeSpan` reprs out of tool-role
  messages, tests gold overlap via `metrics.span_hit_kind` (line-overlap only),
  and reads the 0033 `citations_submitted`/`citations_surviving` counts for the
  submitted / submitted-then-dropped split. An undecodable tool message →
  `DETECTOR_INCONCLUSIVE`.
- Step-1 tests pass.

### Step 3 — dual-seam schema bump (RED) [AC2]
- Add to `harpyja/eval/test_live_verifier.py`:
  - `test_build_trajectory_record_carries_submission_outcome` — the
    `build_trajectory_record` seam emits the additive `submission_outcome` (+
    `detector_version`) field.
  - `test_run_verified_case_written_artifact_carries_submission_outcome` — the
    SECOND, hand-assembled `run_verified_case` written-JSON artifact ALSO carries
    the field (the 0033/0034/0038 dual-seam written-JSON pin — both seams, one
    test file).
  - `test_verifier_schema_version_bumped_and_legacy_still_validates` —
    `VERIFIER_SCHEMA_VERSION == "0043/1"`, added to
    `_KNOWN_VERIFIER_SCHEMA_VERSIONS`, and a legacy `0038/1` artifact still
    validates (additive-last-with-default).
  - `test_validate_verifier_artifact_requires_submission_outcome` — the required
    key set includes the new field for a `0043/1` artifact.
- Tests fail: both seams and `validate_verifier_artifact` predate the field;
  `VERIFIER_SCHEMA_VERSION` is `"0038/1"`.

### Step 4 — thread the field through BOTH seams (GREEN) [AC2]
- In `harpyja/eval/live_verifier.py`: bump `VERIFIER_SCHEMA_VERSION → "0043/1"`
  (add to `_KNOWN_VERIFIER_SCHEMA_VERSIONS`); thread `submission_outcome`
  (computed via `submission_gap.classify_submission`) + `detector_version`
  through `build_trajectory_record` AND `run_verified_case`'s hand-assembled dict;
  add both keys additively to `validate_verifier_artifact`.
- Step-3 tests pass; legacy artifacts still validate.

### Step 5 — attribution + 4b-inversion machinery (RED) [AC1, AC3]
- Add `harpyja/eval/test_clock_attribution.py`:
  - `test_attribution_asserts_per_artifact_existence_first` — a missing trajectory
    yields the typed `trajectory-missing` degrade for that cell, never a silent
    skip.
  - `test_per_case_attribution_fields` — per case: turns-to-locate,
    turns-after-locate, reasoning-chars/turn, completion-tokens/turn, tool-call
    count, finish_reason, terminal cause (wall-clock / HTTP timeout / turn cap /
    submitted). Reported per model.
  - `test_attribution_never_zips_per_turn_and_model_turns` — a `finish_reason=length`
    final `per_turn` entry with no matching history turn does NOT crash and is not
    positionally aligned (the length-skew pin).
  - `test_case_timing_is_estimate_grade_labeled` — case-level timing is derived as
    successive verifier-artifact timestamp deltas within a sequential run block and
    is LABELED an estimate (0021); NO latency field is read (there is none).
  - `test_no_measured_latency_field_anywhere` — the attributor never claims a
    per-turn or per-case measured latency.
  - `test_4b_inversion_attributor_names_cause_or_unattributable` — the inversion
    attributor consumes the named discriminating evidence (turn counts vs
    tool-result byte sizes vs prompt-growth/prefill vs ledger-degrade timing) and
    returns either a named cause OR `UNATTRIBUTABLE_NEEDS_INSTRUMENTED_RERUN` WITH
    the specific missing measurement named (falsifiable, not a default escape).
  - `test_derived_table_pins_source_artifact_filenames_and_hashes` — the committed
    derived-attribution-table serialization carries each source artifact's filename
    + content sha256 (so the finding survives after `eval_work` evaporates).
- Tests fail: `harpyja/eval/clock_attribution.py` does not exist.

### Step 6 — attribution + 4b-inversion machinery (GREEN) [AC1, AC3]
- Add `harpyja/eval/clock_attribution.py`: existence-asserting per-cell loader
  (typed `trajectory-missing` degrade), the per-case attributor over one
  persisted trajectory (never zipping `per_turn`/`model_turns`), estimate-grade
  case-timing from timestamp deltas (labeled), the 4b-inversion attributor over
  the named discriminating evidence with the falsifiable
  `UNATTRIBUTABLE_NEEDS_INSTRUMENTED_RERUN` out, and the committed derived-table
  serializer pinned to source filenames + sha256.
- Step-5 tests pass. (No live compute — pure over fixtures.)
- REFACTOR (optional, evaluate at GREEN): if the per-turn field extraction
  duplicates `submission_gap`'s tool-role parsing, extract a shared reader; else
  record evaluate-and-decline (0042-T7 precedent).

### Step 7 — FROZEN attribution-to-lever table (RED) [AC4, stage 1]
- Add `harpyja/eval/test_lever_table.py`:
  - `test_lever_table_hash_is_stable` — `LEVER_TABLE_HASH_0043 ==
    lever_table_hash(FROZEN_LEVER_TABLE_0043)` (the 0039/0040/0042
    `dataclasses.asdict`→sha256 shape).
  - `test_lever_table_selection_is_total` — over the declared attribution-signal
    space (after-locate-turns high; per-turn token cost high; hard wall-clock
    expiry with low post-hit dawdle) `select_lever` returns exactly one lever for
    EVERY cell (total, no gap/overlap).
  - `test_submit_early_nudge_is_presumptive_first_rank_when_dawdle_after_locate` —
    the frozen ranking rule: dawdle-after-locate → the `messages`-only submit-early
    nudge (cheapest, presumptive rank-1), NOT a wall-clock raise.
  - `test_wall_clock_raise_requires_recorded_rationale_flag` — a wall-clock/turn-cap
    lever carries the "cheaper levers insufficient" rationale requirement AS DATA.
- Tests fail: `harpyja/eval/lever_table.py` does not exist.

### Step 8 — lever table impl + COMMIT (GREEN) [AC4, stage 1]
- Add `harpyja/eval/lever_table.py`: frozen `FROZEN_LEVER_TABLE_0043`,
  `lever_table_hash`, `LEVER_TABLE_HASH_0043`, total `select_lever(...)`.
- Write the discoverable frozen-table artifact (values + hash) under
  `specs/0043-diagnosis/lever_table/lever_table.json` — **BEFORE any attribution
  number is computed** (stage-1 freeze; this task must land before T9).
- Step-7 tests pass.

### Step 9 — OFFLINE attribution run + committed derived table (operator) [AC1, AC3]
- Run `clock_attribution` over the persisted
  `eval_work/live_artifacts/{pilot_0040,adoption_0042}/<model>/<case>_verifier_artifact.json`
  (verified present on this dev machine). Commit the derived attribution table
  (per-model, per-case) pinned to source artifact filenames + content hashes under
  `specs/0043-diagnosis/attribution/attribution_table.json`, and the 4b-inversion
  finding (named cause OR `UNATTRIBUTABLE_NEEDS_INSTRUMENTED_RERUN` + the missing
  measurement). This is an OFFLINE operator step (no model compute), AFTER the T8
  lever freeze — so the numbers are computed only after the choosing rule is
  frozen.

### Step 10 — PREREGISTERED_DIAGNOSIS_CONFIG_0043 (RED) [AC5, stage 2]
- Add `harpyja/eval/test_diagnosis_config.py`:
  - `test_diagnosis_config_hash_is_stable` — `DIAGNOSIS_CONFIG_HASH_0043 ==
    diagnosis_config_hash(PREREGISTERED_DIAGNOSIS_CONFIG_0043)`.
  - `test_config_pins_0042_pilot_cells` — cells = the 0042 pilot cell set (consumed,
    not re-selected).
  - `test_config_pins_sut_hash_gate_proof_and_counted_buckets` — `sut_hash` (pins
    the post-0042 symbols surface), `gate_proof_version == "0041/exclusivity/1"`,
    and the exact counted buckets are present.
  - `test_config_detector_version_matches_submission_gap` — `detector_version ==
    submission_gap.DETECTOR_VERSION` (identical detector both sides).
  - `test_config_has_min_covered_before_cells_floor` — `MIN_COVERED_BEFORE_CELLS`
    is a named frozen field (the 0042 `MIN_RFWS_DENOMINATOR` pattern).
  - `test_config_names_selected_lever_from_frozen_table` — the lever(s)-under-test
    field equals `lever_table.select_lever(...)` over the committed T9 attribution
    (mechanical, not chosen by hand).
- Tests fail: `harpyja/eval/diagnosis_config.py` does not exist.

### Step 11 — config freeze + COMMIT (GREEN) [AC5, stage 2]
- Add `harpyja/eval/diagnosis_config.py`: frozen
  `PREREGISTERED_DIAGNOSIS_CONFIG_0043` (cells, `sut_hash`, `gate_proof_version`,
  counted buckets, `detector_version`, lever(s)-under-test, `MIN_COVERED_BEFORE_CELLS`),
  `diagnosis_config_hash`, `DIAGNOSIS_CONFIG_HASH_0043`.
- Write the discoverable frozen-config artifact under
  `specs/0043-diagnosis/diagnosis_config/diagnosis_config.json` — AFTER the T9
  lever selection, **BEFORE any live spend** (stage-2 freeze).
- Step-10 tests pass.

### Step 12 — lever implementation (RED) [AC4, FIX]
- Add tests for the lever the T9 table selected (the presumptive first-rank is the
  `messages`-borne submit-early nudge):
  - If a prompt nudge: add to `harpyja/scout/test_context_map.py` /
    `test_explorer_backend.py` — `test_submit_early_nudge_present_in_prompt` and
    `test_params_pin_survives_submit_early_nudge` (outbound `params ==
    {"max_tokens": 2048}` at `explorer_think=None` byte-identical; the 0042
    prompt↔surface drift guard stays green).
  - If a ceiling/turn-cap change instead: add
    `test_<lever>_is_named_settings_change_not_params` in
    `harpyja/config/test_settings.py` + `harpyja/scout/test_explorer_backend.py`,
    with the `params` pin still asserted green.
  - `test_selected_lever_recorded_as_data` (in `test_diagnosis_config.py` or the
    driver tests) — the selected lever is carried AS DATA in the outcome artifact,
    auditable, not prose.
- Tests fail: the lever is not yet implemented.

### Step 13 — lever implementation (GREEN) [AC4, FIX]
- Implement the T9-selected lever on the SUT, preserving every prior pin: a prompt
  nudge rides `messages` in `harpyja/scout/context_map.py::build_initial_prompt`;
  a ceiling/turn-cap change is a named `Settings` field + single call site (never
  `_default_model_call` params). A wall-clock raise alone carries the recorded
  "cheaper levers insufficient" rationale.
- Step-12 tests pass; VERIFY the `params==2048` pin + the 0042 drift guard stay
  green.

### Step 14 — total AC6 verdict (RED) [AC6]
- Add `harpyja/eval/test_diagnosis_outcome.py`:
  - `test_decide_diagnosis_outcome_grid_totality` — over the cross of
    {found-unsubmitted drops / does not}, {net conversions positive / negative /
    zero}, {covered BEFORE subset ≥ / < `MIN_COVERED_BEFORE_CELLS`},
    `decide_diagnosis_outcome` returns exactly one of `CLOCK_BOUND_FIXED` /
    `CLOCK_BOUND_UNDER_POWERED` / `CLOCK_BOUND_PERSISTS` / `NOT_CLOCK_BOUND` for
    EVERY cell.
  - `test_under_powered_gated_by_min_covered_before_cells` — covered subset below
    the frozen floor → `CLOCK_BOUND_UNDER_POWERED` (a returned enum member, never
    prose).
  - `test_bucket_movement_is_bidirectional_net_surfaced` — conversions AND
    regressions are netted from retained per-case pairs; a single noise flip does
    NOT type `CLOCK_BOUND_FIXED` unqualified.
  - `test_per_side_inconclusive_counts_enter_verdict` — BEFORE and AFTER
    `detector-inconclusive` counts are reported per side, and a large asymmetry is
    surfaced as a named caveat.
  - `test_not_clock_bound_when_attribution_refutes` — when the attribution refutes
    the hypothesis, `NOT_CLOCK_BOUND` with the residual named.
- Tests fail: `harpyja/eval/diagnosis_outcome.py` does not exist.

### Step 15 — AC6 verdict impl (GREEN) [AC6]
- Add `harpyja/eval/diagnosis_outcome.py`: the total pure
  `decide_diagnosis_outcome(config, before_pairs, after_pairs, before_inconclusive,
  after_inconclusive)` over the frozen config and retained per-case pairs, using
  the identical `submission_gap` detector on both sides, netting bidirectional
  bucket movement, floored by `MIN_COVERED_BEFORE_CELLS`.
- Step-14 tests pass.

### Step 16 — gated live driver (RED) [AC5]
- Add `harpyja/eval/test_diagnosis_run.py` (unit, fakes):
  - `test_diagnosis_run_cell_emits_trajectory_verified_artifact` — `run_cell`
    produces a per-case artifact carrying model identity, the `submission_outcome`
    field, terminal bucket, and the `0041/pilot/2` exclusivity proof.
  - `test_diagnosis_run_refuses_without_live` — routing through
    `run_gated_pool_pilot(..., live=False)` refuses loudly (the 0040/0041/0042
    posture).
  - `test_diagnosis_run_consumes_pinned_0042_cells` — the frozen 0042 pilot cells
    are consumed, not re-selected.
  - `test_before_covered_subset_named_in_artifact` — BEFORE is computed only for
    cells whose full `eval_work` trajectory survived; the covered subset is named.
  - `test_identical_detector_both_sides` — BEFORE (offline) and AFTER (live) both
    route through `submission_gap.classify_submission`, one detector version.
- Add `harpyja/eval/test_diagnosis_run_integration.py`:
  - `test_diagnosis_closure_run_smoke` — `@pytest.mark.integration`, skip-not-fail
    under the opt-in default; asserts the driver STOPS-AND-WARNS (non-zero exit) on
    missing/contended live infra rather than silently passing.
- Tests fail: `specs/0043-diagnosis/diagnosis_run/run_diagnosis.py` does not exist.

### Step 17 — STOP-AND-WARN gated driver (GREEN) [AC5]
- Add `specs/0043-diagnosis/diagnosis_run/run_diagnosis.py` (the 0040/0041/0042
  committed-driver shape): re-measures the frozen 0042 pilot cells through
  `run_gated_pool_pilot(live=True)` with the `0041/pilot/2` exclusivity proof in
  every artifact, under the T13 lever, keyed by `DIAGNOSIS_CONFIG_HASH_0043`,
  resumable via `PoolPilotLedger`; STOP-AND-WARN (non-zero exit on
  contended/missing live infra). Model coverage read from the frozen AC5 config.
- Step-16 unit tests pass; the integration smoke skips by default.

### Step 18 — LIVE MEASUREMENT (operator run, LAST) [AC5]
- After the lever (T13) + the frozen config committed (T11), run
  `specs/0043-diagnosis/diagnosis_run/run_diagnosis.py` against the live 0041-gated
  stack. Commit the durable per-case artifacts (found-but-unsubmitted count per
  side, per-side `detector-inconclusive` count, net bidirectional bucket movement)
  under `specs/0043-diagnosis/diagnosis_run/`. Evict/re-pin any foreign resident
  per the dev-host keep-alive note. Operator run, not a test task; the hash was
  committed BEFORE this call.

### Step 19 — typed-outcome record (doc, closes) [AC6]
- Write `specs/0043-diagnosis/outcome.md`: the typed outcome DECIDED by
  `decide_diagnosis_outcome` (frozen config, retained per-case pairs) —
  `CLOCK_BOUND_FIXED` / `CLOCK_BOUND_UNDER_POWERED` / `CLOCK_BOUND_PERSISTS` /
  `NOT_CLOCK_BOUND`, a pilot-N SIGNAL not an inferential claim. Records: the
  attribution finding, the selected lever AS DATA, the 4b-inversion verdict, the
  covered BEFORE subset vs `MIN_COVERED_BEFORE_CELLS`, per-side inconclusive
  counts, and that all cells were measured on the frozen SUT.

## Delegation

- T1–T4 (detector + dual-seam schema bump) → eval-harness agent that owns the
  0033/0034/0038 dual-seam threading (reason: `build_trajectory_record` /
  `run_verified_case` written-JSON pin + `VERIFIER_SCHEMA_VERSION` gate are its
  standing surface).
- T5–T6, T9 (attribution + 4b inversion + offline run over `eval_work`) →
  eval/statistics-strong agent (reason: pure projection over persisted
  trajectories, one-oracle reuse, estimate-grade labeling — the 0021/0022 posture).
- T7–T8, T10–T11 (frozen lever table + preregistered config) → the same freeze
  agent that built `pool_precheck` / `adoption_precheck` (reason:
  `dataclasses.asdict`→sha256 hash + total selection function + committed artifact).
- T12–T13 (lever on the Scout SUT) → keep in-thread / general implementer (reason:
  coupled `context_map.py` / `explorer_backend.py` edits under the byte-frozen
  `params` pin — a handoff would fracture the lockstep).
- T14–T15 (total verdict) → freeze agent (reason: grid totality + bidirectional
  net movement mirror `decide_adoption_outcome`).
- T16–T19 (gated driver + live run + doc) → the operator agent owning the
  0040/0041/0042 committed drivers (reason: `run_gated_pool_pilot`,
  `PoolPilotLedger`, `0041/pilot/2` proof, STOP-AND-WARN precedent).

## Risk register (summary)

- **Two-stage freeze ordering violated (HIGH — the spec's core discipline).**
  Mitigation: the task order hard-sequences it — no attribution NUMBER before T9
  (after the T8 lever-table freeze), no live spend before T11 (the config freeze).
  The lever table and config each land as a committed hashed artifact before their
  gated step; the T10 test asserts the selected lever is mechanically derived from
  the frozen table over the committed attribution, not hand-picked.
- **Byte-frozen `params == {"max_tokens": 2048}` pin (HIGH — must not regress).**
  Mitigation: T13's lever rides `messages` (prompt nudge) or a named `Settings`
  field (ceiling/cap), never `_default_model_call` params; the two pin tests are
  asserted green after T13.
- **`eval_work` trajectories are machine-local + gitignored (HIGH — the 0021
  evaporation class).** Mitigation: T5 existence-asserts per artifact (typed
  `trajectory-missing`, never a silent skip); T9 commits the derived attribution
  table pinned to source filenames + content hashes so the finding survives after
  `eval_work` evaporates; the BEFORE covered subset is named in the artifact.
- **Detector-inconclusive asymmetry silently biasing the delta (MEDIUM).**
  Mitigation: identical detector version both sides (T10 pins it), per-side
  inconclusive counts reported and entering the verdict (T14), large asymmetry a
  named caveat.
- **4b-inversion over-claiming from insufficient evidence (MEDIUM).** Mitigation:
  the attributor's honest-out `UNATTRIBUTABLE_NEEDS_INSTRUMENTED_RERUN` names the
  specific missing measurement — falsifiable, not a default escape (T5).
- **Integration wall-clock outlasts one invocation (MEDIUM).** Mitigation: coverage
  pinned in the frozen config, resumable `PoolPilotLedger`, STOP-AND-WARN driver,
  `@pytest.mark.integration` skip-not-fail; closure rests on committed artifacts.
- **specs/ not on the pytest path (LOW).** Mitigation: the integration smoke lives
  at `harpyja/eval/test_diagnosis_run_integration.py` (the 0042 precedent), so the
  suite collects it; the driver stays under `specs/0043-diagnosis/diagnosis_run/`.
