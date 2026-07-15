---
spec: "0047"
status: planned
strategy: tdd
---

# Plan — 0047 enlargement

Pool enlargement — the audited convert step that unblocks the bake-off (0040), the
thinking A/B (0039), and the policy re-measurement (0043–0046) by raising the
blind-clean pool past 19 so the instrument can resolve effect sizes again. This is
**measurement machinery + DATA, no SUT change**: no live model/harness run at all
(enlargement is authoring-time/offline). It is NOT greenfield — it REUSES, verbatim,
the 0036/0040/0039 surfaces (`swebench_eval` audited convert, `terse_dataset`
drift-guard + floors, `terse_authoring`/`authoring_provenance` blind protocol,
`terse_reachability` + `dataset` tags, `pool_precheck`/`think_ab_precheck` power
arithmetic). The genuinely new surface is one owning module, `harpyja/eval/enlargement.py`:
a frozen+hashed `EnlargementConfig` (target-N arithmetic), a pinned `SamplingFrame`
(candidate manifest), a frozen `PowerVerdict` vocabulary committed BEFORE numbers, and
the theoretical-ceiling re-check + expected-variance computation.

## spec.md follow-up (the six review must-fixes land here as tasks)

The user chose to proceed to /plan directly, so the six convergent must-fix items from
`review.md` are folded in as concrete tasks below. spec.md SHOULD be updated to match:
fill `packages: ["harpyja/eval"]`; move the target-N arithmetic (OQ1) and the ≤3/repo
rule (OQ3) into What/Acceptance; declare `[doc]` in the AC scope-key preamble; state
the AC6 theoretical-ceiling-only scope; promote OQ2 (variance at N) to an AC deliverable.
Mapping: AC1↔Steps 9–11 (+ integrity/dup/source-snapshot), AC2↔Steps 12–13,
AC3↔Steps 14–15, AC4↔Steps 1–4 (raw-vs-output pin + ≤3/repo), AC5↔Steps 5–6, 16–17
(frozen vocabulary), AC6↔Step 18 (theoretical-ceiling scope fix), OQ2→AC↔Steps 7–8.

## Decision A — raw-vs-output pin (AC4): freeze the RAW convert count, float the OUTPUT

The chicken-and-egg (AC4 wants a pinned N; OQ1's 38% yield is unconfirmed on a new
SWE-bench slice) is resolved by pinning the **RAW convert count upfront** (assumption-
driven, frozen in the hashed config) and letting the **blind-clean OUTPUT count FLOAT**
with measured attrition (reported per-case, never silently short). The arithmetic, stated
and pinned as `EnlargementConfig` literals + `*_derivation` strings (mirroring
`PoolConfig.coverage_derivation`/`floor_derivation`), drift-pinned to SUT constants:

- Binding downstream floor `F = benchmark_fit.PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS`
  (= 8 conceptual discordant pairs) — copied, never re-derived.
- Design target `target_conceptual_output_n`: the conceptual stratum sized so expected
  discordant ≥ F WITH headroom for degrades, blind-attrition, and the nested-sets risk
  (0040 had ZERO slack: 8 conceptual vs minimum 8). `F / r_d × (1 + h)` with a
  conservative realized-discordance rate `r_d ≈ 0.35` (0040 ceilings 6/8/3 on 15) and a
  combined headroom `h` for degrade + variance + nesting ⇒ **40** conceptual (not a round
  guess: it is `8/0.35` floored-then-headroomed).
- Assumed yield from 0036 (the SOLE prior): `blind_clean_yield = 19/50 = 0.38`,
  `conceptual_fraction = 15/19 ≈ 0.79` ⇒ conceptual-clean per raw ≈ 0.30.
- **Frozen RAW target** = `ceil(target_conceptual_output_n / 0.30 × (1 + yield_uncertainty))`
  ≈ `ceil(40/0.30 × 1.15)` ⇒ a pinned, deliberately non-round **154** (the exact literal
  is committed in the GREEN config task with its derivation string). This is what AC4
  freezes.
- FLOATS (measured, reported, NOT frozen): actual blind-clean N, actual conceptual N,
  per-case leaky/ineligible attrition. A driver reports these against the target; a
  measured yield below assumption that leaves conceptual N < target is a TYPED reported
  shortfall (`INSUFFICIENT_ENLARGED_COVERAGE`), never a silent pass.

## Decision B — frozen typed power-verdict vocabulary (AC5), committed BEFORE numbers

Per the standing 0040–0046 two-stage-freeze discipline (a frozen-then-wrong label is
durable in committed artifacts, and this spec itself names the train-on-test confound),
the `PowerVerdict` enum + its predicate order are committed in Steps 5–6, BEFORE the
enlarged stratum counts exist. Five members, total answer space, one home:

- `POWERED` — the theoretical discordance ceiling (= enlarged conceptual N) clears
  `F` with coverage ≥ the derived minimum: the bake-off/A/B MAY run (feasibility, not a
  promise of empirical discordance).
- `STILL_UNDER_POWERED` — the theoretical ceiling is STILL < `F` even enlarged (the
  0039/0040 true-bound stop persists; enlargement did not remove the N-blocker).
- `DISCORDANCE_STILL_INSUFFICIENT` — the ceiling clears but observed discordance stays
  < `F`: the AC6 nested-sets finding (enlargement added CONCORDANT not discordant cells —
  model homogeneity, not data volume). Typed here so the answer space is pre-frozen;
  RESOLVABLE only empirically → deferred to the next (bake-off) spec.
- `INSUFFICIENT_ENLARGED_COVERAGE` — coverage still below the derived minimum after
  enlargement (attrition ate the headroom): the measured-output shortfall branch.
- `VARIANCE_REQUIRES_MULTI_DRAW` — for the policy-baseline question (OQ2→AC): expected
  variance at the enlarged N still exceeds the effect band ⇒ a single-draw baseline is
  illegitimate, median-of-2–3 required (0046's named follow-up).

Drift-pinned: `F` reads `benchmark_fit.PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS`; the
coverage minimum reuses `pool_precheck`'s derived arithmetic; the conceptual floor reuses
`terse_dataset._CONCEPTUAL_FLOOR_FULL`. The re-check REUSES `pool_precheck` /
`think_ab_precheck` (identity-asserted), never re-deriving the projection.

## Freeze-before-run sequencing law (hard gate)

1. **All frozen config/vocabulary/pure machinery land BEFORE any convert/author/tag
   executes** (Steps 1–8): `EnlargementConfig` (raw-vs-output arithmetic), `SamplingFrame`
   (candidate manifest + ≤3/repo + source-snapshot pin), the `PowerVerdict` vocabulary,
   and the expected-variance predicate are ALL committed before the first raw case is
   acquired — the 0036/0040 re-registration rule.
2. **AC1 integrity is a DRIFT-GUARD, not a re-transcription** (Steps 9–11): new labels are
   sha256-pinned + provenance-chained and APPENDED; the existing 19 terse + their raw
   labels + the 36 authoring records are proven byte-identical against a committed
   baseline; duplicates (case-id collisions with the pinned 50) are rejected, never
   silently merged.
3. **No live SUT/model run anywhere.** Raw acquisition is authoring-time, one-time,
   offline-of-the-SUT (does NOT touch the runtime Model Gateway / air-gap seam); blind
   authoring uses INJECTED author≠verifier callables (operator cross-model tooling), never
   the product gateway (the 0026/0036 posture). Scope: `[unit]`=fakes,
   `[integration]`=authoring/convert with no live model runs, `[doc]`=findings.

## Test-first sequence

### Step 1 — Frozen+hashed enlargement config: target-N arithmetic, raw-vs-output pin (RED)
- Add `harpyja/eval/test_enlargement.py`:
  - `test_enlargement_config_pins_raw_convert_target_not_output` — `raw_convert_target`
    is a frozen literal; `target_conceptual_output_n` is the design goal; the docstring/
    field names make explicit that the OUTPUT floats with attrition.
  - `test_enlargement_config_floor_reuses_benchmark_fit_not_re_derived` — the binding floor
    is `benchmark_fit.PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS`, copied verbatim.
  - `test_enlargement_config_conceptual_floor_reuses_terse_dataset` — the conceptual
    reportability floor reads `terse_dataset._CONCEPTUAL_FLOOR_FULL` (=5), not a literal.
  - `test_enlargement_config_target_n_is_not_a_round_number_and_carries_derivation` — the
    target/raw literals are the stated arithmetic (`F / r_d`, yield-backed), each with a
    non-empty `*_derivation` string; raw ≠ a round multiple.
  - `test_enlargement_config_pins_max_per_repo_three` — `MAX_PER_REPO == 3` (the 0036
    ≤3/repo discipline, first-class).
  - `test_enlargement_config_hash_0047_is_stable` — `ENLARGEMENT_CONFIG_HASH_0047` matches
    a recomputed hash (freeze integrity).
- Tests fail: `harpyja/eval/enlargement.py` and its config do not exist.

### Step 2 — Implement the frozen enlargement config (GREEN)
- Implement `harpyja/eval/enlargement.py` with `EnlargementConfig` (frozen dataclass:
  `raw_convert_target`, `target_conceptual_output_n`, `assumed_blind_clean_yield`,
  `assumed_conceptual_fraction`, `yield_uncertainty`, `conceptual_min_discordant`,
  `max_per_repo`, and the `*_derivation` strings), `PREREGISTERED_ENLARGEMENT_CONFIG_0047`,
  `enlargement_config_hash`, `ENLARGEMENT_CONFIG_HASH_0047` (mirroring `pool_config_hash`).
- All Step-1 tests pass.

### Step 3 — Pinned sampling frame: source-snapshot, ≤3/repo, deterministic selection (RED)
- Extend `harpyja/eval/test_enlargement.py`:
  - `test_sampling_frame_schema_validates_loud` — a bad/absent `schema_version`
    (`0047/frame/1`) or a missing source-snapshot field is loudly rejected.
  - `test_sampling_frame_pins_source_snapshot` — the frame carries the HF snapshot
    identity (`hf_dataset_id`, `hf_revision`, `hf_split`) + the sha256 chain to the
    committed raw fixture (the drift-guard root).
  - `test_select_candidates_excludes_already_pinned_fifty` — candidate selection excludes
    the 50 already-committed `case_id`s (no train-on-test re-draw), new-file-only, and
    malformed, recording each exclusion reason.
  - `test_select_candidates_caps_at_three_per_repo` — no repo contributes > `MAX_PER_REPO`
    candidates; a 4th from one repo is dropped with a recorded reason.
  - `test_select_candidates_is_deterministic_by_case_id_order` — selection is a pure
    deterministic function of (snapshot, frozen config), ordered by `case_id` (the
    existing `_stratify`/sort discipline), reproducible across runs.
- Tests fail: `SamplingFrame`, `validate_sampling_frame`, `select_candidates` absent.

### Step 4 — Implement the sampling frame + selection (GREEN)
- Implement `SamplingFrame` (frozen), `SAMPLING_FRAME_SCHEMA_VERSION="0047/frame/1"`,
  `validate_sampling_frame` (loud), and `select_candidates(snapshot_rows, cfg,
  already_pinned_ids)` (pure: exclude pinned/new-file-only/malformed, cap ≤3/repo, order
  by `case_id`, record exclusion reasons). Reuses `swebench_eval.is_new_file_only` /
  `parse_patch` for the exclusion predicates (identity, not re-derived).
- All Step-3 tests pass.

### Step 5 — Frozen PowerVerdict vocabulary + predicate order + theoretical ceiling (RED)
- Extend `harpyja/eval/test_enlargement.py`:
  - `test_power_verdict_values_are_exactly_the_five_committed` — `POWERED`,
    `STILL_UNDER_POWERED`, `DISCORDANCE_STILL_INSUFFICIENT`,
    `INSUFFICIENT_ENLARGED_COVERAGE`, `VARIANCE_REQUIRES_MULTI_DRAW`; no more, no fewer.
  - `test_theoretical_discordance_ceiling_is_conceptual_stratum_size` — the ceiling used
    by AC5/AC6 is the enlarged conceptual N (max possible discordance, computable from tag
    counts ALONE — no located sets, the scope fix), not a pilot-derived quantity.
  - `test_decide_bakeoff_power_types_powered_when_ceiling_clears_and_coverage_ok` —
    conceptual N ≥ F and coverage ≥ derived minimum ⇒ `POWERED`.
  - `test_decide_bakeoff_power_types_still_under_powered_below_floor` — conceptual N < F ⇒
    `STILL_UNDER_POWERED` (the true-bound stop persists).
  - `test_decide_bakeoff_power_types_insufficient_enlarged_coverage` — conceptual N ≥ F but
    coverage below the derived minimum ⇒ `INSUFFICIENT_ENLARGED_COVERAGE` (attrition ate the
    headroom), never a shaky POWERED.
  - `test_power_verdict_predicate_order_frozen` — evaluated in the frozen, non-overlapping
    order; an input satisfying multiple predicates types the earliest.
- Tests fail: `PowerVerdict`, `theoretical_discordance_ceiling`, `decide_bakeoff_power`
  absent.

### Step 6 — Implement the power vocabulary + theoretical-ceiling re-check (GREEN)
- Implement `PowerVerdict` (5-member enum), `POWER_VERDICT_ORDER`,
  `theoretical_discordance_ceiling(conceptual_n)`, `decide_bakeoff_power(cfg, conceptual_n,
  coverage)` and `decide_ab_power(...)` (the 0039 feasibility twin). Floor reads
  `benchmark_fit.PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS`; the coverage minimum reuses
  `pool_precheck.coverage_below_minimum` arithmetic. Docstring states: the ceiling is the
  THEORETICAL max (tag-count-only); empirical discordance (`DISCORDANCE_STILL_INSUFFICIENT`)
  is deferred to the bake-off spec.
- All Step-5 tests pass.

### Step 7 — Expected variance at target N + single-draw sufficiency (OQ2→AC) (RED)
- Extend `harpyja/eval/test_enlargement.py`:
  - `test_expected_variance_shrinks_with_n` — `expected_variance_at_n` is monotone
    decreasing in N (the enlarged pool tames variance vs the 33-cell baseline).
  - `test_single_draw_suffices_false_when_variance_exceeds_band` — at a variance above the
    0046 effect band the predicate returns False and the verdict is
    `VARIANCE_REQUIRES_MULTI_DRAW` (median-of-2–3 needed).
  - `test_single_draw_suffices_true_when_variance_within_band` — at the enlarged N whose
    variance falls inside the band, a single-draw baseline is typed legitimate.
- Tests fail: `expected_variance_at_n`, `single_draw_suffices` absent.

### Step 8 — Implement the variance predicate (GREEN)
- Implement `expected_variance_at_n(n, ...)` and `single_draw_suffices(n, effect_band, ...)`
  (pure; the binomial/effect-band arithmetic stated in the docstring). `decide_ab_power`
  routes a failing sufficiency to `VARIANCE_REQUIRES_MULTI_DRAW`.
- All Step-7 tests pass.

### Step 9 — Audited-convert append integrity + drift-guard (AC1) (RED)
- Extend `harpyja/eval/test_swebench_eval.py`:
  - `test_append_converted_cases_preserves_existing_bytes_exactly` — appending new cases to
    the raw fixture leaves the original 50 lines byte-identical (per-`case_id` line-sha map
    against a committed baseline); order stable.
  - `test_append_converted_cases_rejects_duplicate_case_ids` — a new case whose `case_id`
    collides with a pinned one is rejected loudly, never silently merged/overwritten.
  - `test_extend_provenance_chains_source_snapshot_and_new_sha` — the extended
    `provenance.json` carries the source snapshot (`hf_revision`) + the NEW
    `raw_fixture_sha256` over the appended file, and grows `sample_case_ids`; the old sha is
    superseded, not dropped-silently (recorded as `prior_raw_fixture_sha256`).
  - `test_assert_pool_append_preserves_existing_labels_reuses_raw_pin` — the drift-guard
    reuses `terse_dataset.assert_raw_pin`-style sha checking so existing labels are proven
    unchanged BEFORE any join runs.
- Tests fail: `append_converted_cases`, `extend_provenance`,
  `assert_pool_append_preserves_existing_labels` absent.

### Step 10 — Implement the audited-convert append + integrity (GREEN)
- Implement in `harpyja/eval/swebench_eval.py`: `append_converted_cases(existing_rows,
  new_cases)` (dedup-by-`case_id` reject, stable sort, byte-preserving),
  `extend_provenance(prov, raw_path, new_ids, snapshot)`, and
  `assert_pool_append_preserves_existing_labels(raw_path, baseline_sha_map)`. REUSE
  `_to_eval_case`/`parse_patch`/`classify_by_patch_shape`/`is_new_file_only` verbatim (the
  audited-convert entrypoint), and the `_write_jsonl`/`_sha256_file` writers.
- All Step-9 tests pass.

### Step 11 — Acquire + audited-convert the NEW raw cases (operator) [integration]
- Per the frozen `SamplingFrame` (Step 4), acquire `raw_convert_target` NEW SWE-bench
  Verified cases via `load_swebench_verified()` (authoring-time, ONE-TIME, offline-of-the-
  SUT — does NOT touch the runtime Model Gateway; the air-gap seam is untouched). Run the
  audited convert (`append_converted_cases` → `_to_eval_case`), APPEND to
  `swebench_verified.raw.jsonl`, sha256-pin + extend `provenance.json`. Commit the enlarged
  raw fixture + provenance; the Step-9 drift-guard proves the original 50 byte-identical.
  STOP-AND-WARN on any acquisition/convert error — never a partial commit.

### Step 12 — Extended authoring artifact records attrition, not silent drop (AC2) (RED)
- Extend `harpyja/eval/test_terse_authoring.py`:
  - `test_author_terse_set_extends_records_without_touching_existing_36` — authoring the
    new raw cases appends `AuthoringRecord`s; the committed 36 records
    (`swebench_verified.authoring.json`, `0026/1`) are byte-identical (drift-guard).
  - `test_author_terse_set_records_leaky_and_ineligible_counts` — `leaky_count` and the
    blind-ineligible count (issue names the gold path) are aggregated and recorded, not
    silently dropped (provenance-of-a-null); `assert_author_input_blind` gates each.
  - `test_extended_authoring_artifact_validates_loud` — the extended artifact passes
    `validate_authoring_artifact` at `0026/1` (schema additive, legacy validates unchanged).
- Tests fail until the extended-artifact assembly helper + counts exist.

### Step 13 — Blind-author the new terse queries (operator) [integration] (GREEN)
- Run 0036's `author_terse_set` with INJECTED author≠verifier callables (operator cross-
  model tooling, separate invocations — NOT the product gateway) over the new raw cases;
  route `leaky` verdicts to drop WITH THE COUNT RECORDED; tally blind-ineligible cases.
  Commit the extended `swebench_verified.authoring.json`. STOP-AND-WARN on infra error.
- All Step-12 tests pass.

### Step 14 — Every new case tagged; missing tag rejected loudly; stratum reported (AC3) (RED)
- Extend `harpyja/eval/test_dataset.py` and `harpyja/eval/test_terse_floor.py`:
  - `test_enlarged_terse_case_missing_reachability_is_rejected` — an enlarged `0036/1` row
    missing `reachability` or `concept_patch_relation` raises `DatasetError` (the loud
    loader, unchanged) — the "rejected loudly" guard on the enlarged set.
  - `test_enlarged_conceptual_stratum_report_counts_both_strata` —
    `conceptual_stratum_report` over the enlarged set returns `(lexical_n, conceptual_n,
    status)` with `status == STRATUM_REPORTABLE` at the enlarged conceptual N.
  - `test_enlarged_set_clears_floor_and_full_n_target` — `validate_terse_set_floor` ok
    (multi-repo, no ≤50%-domination) and the enlarged conceptual N ≥
    `target_conceptual_output_n` (or a typed shortfall).
- Tests fail while the enlarged terse fixture is unauthored/untagged.

### Step 15 — Tag + assemble + commit the enlarged terse fixture (operator) [integration] (GREEN)
- Post-authoring (gold-visible): run `terse_reachability.classify_reachability` +
  hand-label concept-vs-patch per new kept case, assemble `0036/1` rows, APPEND to
  `swebench_verified.terse.jsonl` (existing 19 byte-identical — drift-guard). Report the
  lexical/conceptual stratum distribution. Commit; all Step-14 tests pass.

### Step 16 — Re-run 0040/0039 power on the enlarged pool → committed artifact (AC5) (RED)
- Extend `harpyja/eval/test_enlargement.py`:
  - `test_committed_power_recheck_matches_computed_truth` — the committed
    `power_recheck.json` (`0047/power/1`) per-question/per-pair verdicts equal
    `decide_bakeoff_power`/`decide_ab_power` recomputed from the committed enlarged
    stratum counts + frozen config (the 0040 claim-pin pattern).
  - `test_load_committed_power_recheck_archive_first` — the loader resolves
    `specs/.archive/0047-enlargement/power_recheck.json` first, live spec-dir fallback
    (the 79f7bf2 convention).
  - `test_power_recheck_result_validates_loud` — an off-enum verdict or unknown schema is
    loudly rejected.
- Tests fail: `PowerRecheckResult`, `validate_power_recheck`, `load_committed_power_recheck`
  absent.

### Step 17 — Emit + pin the power-recheck artifact (GREEN)
- Implement `PowerRecheckResult`, `POWER_RECHECK_SCHEMA_VERSION="0047/power/1"`,
  `validate_power_recheck`, `load_committed_power_recheck` (archive-first), and emit
  `specs/0047-enlargement/power_recheck.json` from the committed enlarged tag counts:
  a machine-readable verdict per question (bake-off per-pair via `decide_bakeoff_power`;
  A/B feasibility via `decide_ab_power`; the variance/single-draw line) plus the enlarged
  stratum counts and attrition counts. Test-pinned to computed truth.
- All Step-16 tests pass.

### Step 18 — Doc: nested-sets re-check, theoretical-ceiling scope, variance finding (AC6) [doc]
- Write `specs/0047-enlargement/findings.md`: the AC6 nested-sets re-check restricted to the
  THEORETICAL ceiling (max discordance = enlarged conceptual N, computable from tag counts;
  no located sets, no bake-off compute spent); which questions are NOW `POWERED` vs
  `STILL_UNDER_POWERED` vs `INSUFFICIENT_ENLARGED_COVERAGE`; the explicit statement that
  `DISCORDANCE_STILL_INSUFFICIENT` (enlargement added CONCORDANT not discordant cells —
  model homogeneity, not data volume) is a DISTINCT finding resolvable only empirically →
  a different next spec (the bake-off); and the variance/single-draw verdict
  (`VARIANCE_REQUIRES_MULTI_DRAW` or single-draw-legitimate). Reference the machine-readable
  `power_recheck.json`. Optional pin `test_findings_states_theoretical_ceiling_only_scope`.

### Step 19 — Refactor / dedup (optional)
- Fold the extrapolation/floor-reuse and the archive-first path resolver into shared
  helpers ONLY where it does not edit committed 0039/0040 drift-pinned modules; assert the
  re-check ROUTES `pool_precheck`/`think_ab_precheck` by identity rather than re-deriving
  the projection (the 0040 T22 posture — decline with reason if consolidation would touch a
  pinned evidence module).
- All tests still pass.

## Delegation

- Steps 1–10, 16–17, 19 (frozen config/manifest/vocabulary/variance machinery + the
  append-integrity helpers + the power-recheck pin) → keep in-thread; tightest match to
  the repo's frozen-config + total-pure-function + drift-guard convention, no live stack.
- Steps 11, 13, 15 (audited-convert acquisition + two-model blind authoring + tag/assemble)
  → delegate to an **operator/authoring agent** with the operator's cross-model author≠
  verifier tooling. Reason: one-time offline-of-the-SUT acquisition + ~130-case blind
  authoring wall-clock + STOP-AND-WARN discipline; NOT a unit surface. No product gateway,
  no live SUT run.

## Risk

- **The 38% yield does not hold on a new SWE-bench slice** → mitigation: the RAW count is
  frozen upfront with yield-uncertainty headroom (Decision A); a measured shortfall types
  `INSUFFICIENT_ENLARGED_COVERAGE` (reported, never a silent short pool), and the OUTPUT N
  floats + is reported per-case (Steps 1–2, 12, 17).
- **Silent re-transcription / drift of the existing 19 + 50 + 36** → mitigation: AC1 is a
  byte-identical drift-guard reusing `assert_raw_pin`; new labels are APPENDED and
  sha256-pinned, duplicates rejected loudly (Steps 9–11).
- **Post-hoc steering of the power verdict** → mitigation: the `PowerVerdict` vocabulary +
  predicate order are frozen+hashed BEFORE the enlarged counts exist (Decision B, Steps
  5–6), drift-pinned to `benchmark_fit`/`pool_precheck`; the artifact cites the config hash.
- **AC6 scope leak (reading discordance as requiring a live bake-off)** → mitigation: the
  re-check is THEORETICAL-ceiling-only (tag counts, no located sets); empirical discordance
  is typed `DISCORDANCE_STILL_INSUFFICIENT` and explicitly deferred (Steps 6, 18).
- **Nested/homogeneous models: enlargement raises coverage but not discordance** →
  mitigation: named as the distinct empirical finding + different next spec, not assumed
  away (Step 18); this spec proves NECESSITY (removes the N-blocker), not SUFFICIENCY.
- **Selection bias / train-on-test re-draw** → mitigation: the pinned `SamplingFrame`
  excludes the 50 already-committed ids, caps ≤3/repo, and selects deterministically by
  `case_id` from a source-snapshot-pinned candidate set (Steps 3–4).
- **Air-gap** → mitigation: raw acquisition is authoring-time/one-time/offline-of-the-SUT
  and does not add an outbound runtime path; blind authoring uses injected callables, not
  the product gateway (sequencing law 3, Steps 11/13).
