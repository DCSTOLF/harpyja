---
id: "0039"
spec: "0039"
title: "thinking-ab"
status: planned
strategy: tdd
created: 2026-07-10
---

# Plan — 0039 thinking-ab

Thinking A/B — the paired None(default-on)-vs-False(off) run that settles whether reasoning-on
causally rescues the conceptual stratum. This spec is **NOT greenfield**: 0038 already ships the
working `explorer_think` knob on the reconciled `/v1 reasoning-effort` transport (committed probe:
`outcome=v1-variant`, `model=qwen3:14b`), 0034 the `0038/1` verifier artifact (`reasoning_chars`,
per-turn `completion_tokens`, `think_mode`, `serving_transport`), 0036 the reachability-tagged
conceptual-majority set (`terse_dataset.conceptual_stratum_report`, lexical N=4 / conceptual N=15),
0026 the committed `is_signal_discordant` localization oracle + `PilotPair`, and 0023 the exact
`mcnemar_rejects` / `MIN_DISCORDANT_PAIRS=8` floor. The genuinely new surface is a frozen+hashed
verdict config, its total pure verdict function, the two-factor distinctness guard, the reachability
split, the AC5 upper-bound feasibility pre-check, and a resumable STOP-AND-WARN live driver.

## Sequencing law (freeze-before-run, hard gate)

1. **OQ1 (K sizing) and OQ2 (seed schedule + honoring) are resolved and frozen into
   `PREREGISTERED_AB_CONFIG_0039` at PLAN TIME (Steps 1–2), BEFORE any live arm fires.** Frozen
   choices: **K=2, `any-success` fold** for the paired None/False arms (~19×2×2×~200s ≈ 4.2h
   wall-clock, the resumable driver outlasts one invocation); the observational True(`high`) arm
   gets **K=1** and NEVER enters the paired verdict. **Seed: a fixed per-repeat schedule** (repeat
   `k` uses seed `S_k` for BOTH arms) recorded in the config, with its `seed_honoring="unverified"`
   claim carried until the driver's two-call preflight probe (Step 11/12) confirms `/v1` honors
   `seed` — the 0037 lesson verbatim; on a negative probe the config's seed claim stays
   `unverified` and the paired-per-repeat property is downgraded, never asserted falsely.
2. **The AC5 power pre-check (Steps 9–10) GATES the live run.** A typed `UNDER_POWERED_STOP`
   short-circuits: the live paired-run tasks (Steps 13–14) are recorded **N/A-on-branch**, the stop
   artifact naming the 0036 pool-enlargement carry-forward IS the deliverable, and the claim
   artifact (Step 16) commits that stop. The honest prior (stated out loud, review carry-in #8):
   N=15 conceptual, floor 8, ~50% pilot base localization, upper bound on signal-bearing discordance
   ~7–8 *if every localizing case flips* (a same-model contrast flips far fewer) → `UNDER_POWERED_STOP`
   is the *probable and legitimate* deliverable.

## Test-first sequence

### Step 1 — Frozen+hashed config, model tag & factor-(b) predicate pinned (RED)
- Add `harpyja/eval/test_think_ab.py`:
  - `test_preregistered_ab_config_0039_pins_all_verdict_shaping_fields` — arm identities
    (`arm_a_think=None`, `arm_b_think=False`, `arm_c_think=True` observational), `alpha=0.05`,
    `k_repeats=2` + `k_fold_rule="any-success"`, `observational_k=1`, per-stratum floors,
    `invalid_pair_ceiling`, `degrade_asymmetry_threshold`, seed schedule, verdict-mapping fields.
  - `test_ab_config_pins_model_tag_and_serving_transport` — `lm_model=="qwen3:14b"` and
    `serving_transport=="v1-reasoning-effort"` (0038 probe), so model choice is pre-registered, not
    a runtime lever (carry-in #4).
  - `test_ab_config_pins_completion_tokens_factor_b_predicate` — the config carries the operational
    factor-(b) form: per-case aggregate of per-turn `completion_tokens`, expected direction (on ≥
    off), and `min_on_vs_off_token_delta` (carry-in consensus #2).
  - `test_ab_config_conceptual_floor_fixed_at_eight_reuses_benchmark_fit` — the conceptual floor is
    FIXED at `benchmark_fit.PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS` (8), derivation rule pinned
    fixed-not-re-derivable (carry-in #10).
  - `test_ab_config_hash_0039_is_stable` — `AB_CONFIG_HASH_0039` matches a recomputed hash.
- Tests fail: `harpyja/eval/think_ab.py` and its constants do not exist.

### Step 2 — Implement the frozen config (GREEN)
- Implement `harpyja/eval/think_ab.py` with `AbConfig` (frozen dataclass), `PREREGISTERED_AB_CONFIG_0039`,
  `AB_CONFIG_HASH_0039` (`config_hash` mirroring `ac8_pilot`). Module docstring states the
  **distinctness-guard asymmetry rationale** (off-arm-reasoning = instrument defect → invalid;
  on-arm-no-reasoning = legitimate shipped None behavior → kept — carry-in #6) and the OQ1/OQ2 freeze.
- All Step-1 tests pass.

### Step 3 — Total pure verdict over the full outcome grid (RED)
- Extend `harpyja/eval/test_think_ab.py`:
  - `test_decide_ab_verdict_full_outcome_grid_every_member_reachable` — a constructed record set
    reaches each of `THINKING_HELPS / THINKING_HURTS / NO_EFFECT / UNDER_POWERED / CONFOUNDED`.
  - `test_confounded_checked_first` — a record set that is BOTH confounded and would-be-significant
    returns `CONFOUNDED`.
  - `test_under_floor_null_is_under_powered_not_no_effect` — signal-discordant < floor → `UNDER_POWERED`,
    never `NO_EFFECT`, never a forced result (AC2).
  - `test_verdict_predicates_non_overlapping_and_total` — every grid point maps to exactly one member.
  - `test_signal_discordance_reuses_committed_0026_oracle` — the localizes-bucket set routes through
    `ac8_pilot.is_signal_discordant` (CORRECT + RIGHT_FILE_WRONG_SPAN), not a re-derived local rule
    (carry-in #5).
  - `test_mcnemar_reuses_benchmark_fit_exact_test` — significance uses `benchmark_fit.mcnemar_rejects`
    on the discordant `(b,c)`, direction split for HELPS vs HURTS.
- Tests fail: `decide_ab_verdict`, `AbVerdict`, `PairRecord` absent.

### Step 4 — Implement the verdict function (GREEN)
- Implement `AbVerdict` enum, `PairRecord` (case_id, reachability, folded on/off buckets, on/off
  `reasoning_chars`, on/off aggregate `completion_tokens`, degrade flags, `valid`/`invalid_reason`),
  and `decide_ab_verdict(config, records)` — CONFOUNDED first, then floor gate, then directional
  `mcnemar_rejects`. Reuses `ac8_pilot.is_signal_discordant` (via a `PilotPair` adapter: A=on, B=off)
  and `benchmark_fit`.
- All Step-3 tests pass.

### Step 5 — Two-factor arm-distinctness guard (RED)
- Extend `harpyja/eval/test_think_ab.py`:
  - `test_off_arm_reasoning_excludes_and_records_pair` — an off-arm pair with `reasoning_chars>0` is
    excluded-and-recorded with its cause, never silently dropped (AC3).
  - `test_factor_b_completion_tokens_predicate_per_case_aggregate` — factor (b) compares per-case
    aggregate `completion_tokens` (on ≥ off + `min_on_vs_off_token_delta`); a legit small delta on an
    easy case where the on arm genuinely reasoned (`reasoning_chars>0`) is NOT invalidated
    (guards against factor-(b) misfire, consensus #2).
  - `test_on_arm_no_reasoning_pair_kept_asymmetry` — an on-arm pair with `reasoning_chars==0` is KEPT
    (shipped-None legitimate behavior), proving the deliberate asymmetry (carry-in #6).
  - `test_invalid_pair_rate_above_ceiling_yields_confounded` — invalid-pair fraction > ceiling →
    `CONFOUNDED` (AC3).
  - `test_exclusions_never_silently_attrit_n` — excluded case ids surface in the report.
- Tests fail: `classify_pair_validity` / exclusion path absent.

### Step 6 — Implement the distinctness guard (GREEN)
- Implement `classify_pair_validity(record, config)` (two-factor: invalid iff off-arm reasoning
  present, OR on-arm reasoning≈0 AND factor-(b) budget delta below `min_on_vs_off_token_delta`) and
  thread its exclusion set + invalid-pair-rate into `decide_ab_verdict`'s CONFOUNDED input.
- All Step-5 tests pass.

### Step 7 — Reachability split + unified total report taxonomy (RED)
- Extend `harpyja/eval/test_think_ab.py`:
  - `test_reachability_split_conceptual_gets_own_floor_and_verdict_line` — the conceptual stratum is
    verdicted with its own floor/power (AC4).
  - `test_lexical_stratum_typed_stratum_under_populated` — the N=4 lexical stratum emits a typed
    `STRATUM_UNDER_POPULATED` line (reusing `terse_dataset.conceptual_stratum_report` pattern), never
    an implied verdict (AC4).
  - `test_ab_report_unifies_verdict_precheck_and_stratum_shapes` — one `AbReport` total shape spans
    the five verdict members + `UNDER_POWERED_STOP` (pre-check) + `STRATUM_UNDER_POPULATED`; the
    member-count taxonomy is internally consistent (fixes the four-vs-five slip, carry-in #12).
  - `test_whole_set_average_not_the_headline` — the report headline is the per-stratum lines, no
    whole-set average field is emitted as the verdict.
- Tests fail: `decide_ab_report` / `AbReport` absent.

### Step 8 — Implement the split + unified report (GREEN)
- Implement `AbReport` and `decide_ab_report(config, records)` computing per-stratum `decide_ab_verdict`,
  the lexical `STRATUM_UNDER_POPULATED` line, symbols-adoption-per-arm slot, reasoning-cost-delta slot,
  and the per-arm typed-degrade table slot.
- All Step-7 tests pass.

### Step 9 — AC5 upper-bound feasibility pre-check + degrade projection (RED)
- Add `harpyja/eval/test_think_ab_precheck.py`:
  - `test_ab_power_precheck_upper_bound_feasibility_from_0036_ledger` — the projection is LABELED an
    upper-bound feasibility check (not a power estimate); formula = the 0036 stronger-arm localizing
    count over the projectable conceptual subset, every localizing case assumed to flip, compared to
    the conceptual floor 8 (carry-in #1).
  - `test_precheck_projects_only_first_10_of_19_conceptual_subset` — the projectable subset is the
    first-10-piloted conceptual cases, smaller than 15 (carry-in #11).
  - `test_precheck_projects_on_arm_degrade_asymmetry` — the same 0036 per-turn `completion_tokens` /
    `finish_reason` artifacts project a predictable-`CONFOUNDED` warning (carry-in #9).
  - `test_precheck_loads_committed_ledger_archive_first` — inputs resolve
    `specs/.archive/0036-terse-query/pilot/pilot_results.json` archive-first, live path fallback
    (carry-in #11, the `reconcile_probe.load_committed_*` pattern).
  - `test_precheck_under_powered_stop_gates_live_run` — an under-floor projection returns
    `UNDER_POWERED_STOP` and its `next_step` names the 0036 pool-enlargement carry-forward.
- Tests fail: `ab_power_precheck` absent.

### Step 10 — Implement the pre-check (GREEN)
- Implement `ab_power_precheck(...)` in `harpyja/eval/think_ab_precheck.py`: load the committed 0036
  ledger (archive-first), map its conceptual subset via `terse_dataset` reachability tags, compute the
  explicit upper bound, project degrade asymmetry, and return a typed `PrecheckOutcome` (`PROCEED` /
  `UNDER_POWERED_STOP`). Docstring states the power arithmetic out loud (carry-in #8) and that pilot
  discordance was cross-MODEL (bounds, cannot estimate, within-model think-flips).
- All Step-9 tests pass.

### Step 11 — Resumable driver, ledger, STOP-AND-WARN preflight incl. seed probe (RED)
- Add `harpyja/eval/test_think_ab_run.py`:
  - `test_ab_ledger_resumes_completed_cases` — a per-case×arm×repeat ledger skips already-recorded
    cells on re-invocation (the run outlasts one process).
  - `test_ab_ledger_schema_validates_loud` — a pinned version-stamped ledger schema with a loud validator.
  - `test_driver_preflight_stops_when_model_tag_unserved` — preflight resolves the frozen
    `qwen3:14b` served tag (the default tag is NOT servable, 0036) and STOPS loudly if absent.
  - `test_seed_honoring_probe_two_call_identical_completion` — a two-call same-request+same-seed probe
    reports honored iff completions are identical (carry-in #7, OQ2).
  - `test_seed_probe_negative_keeps_config_claim_unverified` — a non-identical probe leaves the config
    seed claim `unverified` and records the downgrade, never a false "repeat k used seed S_k".
  - `test_strict_run_skip_is_hard_fail` — under `HARPYJA_REQUIRE_LIVE_STACK` a skip becomes a hard fail.
- Tests fail: ledger/preflight/`seed_honoring_probe` absent.

### Step 12 — Implement driver, ledger, preflight (GREEN)
- Implement `harpyja/eval/think_ab_run.py`: `AbLedger` (pinned schema, resumable, reusing
  `report.atomic_write_json` outside-repo writer), `ab_preflight` (served-tag resolution behind
  `assert_local` + `seed_honoring_probe` + verifier preflight), and `require_live_stack` posture.
- All Step-11 tests pass.

### Step 13 — Live paired run, precheck-gated (RED, integration skip-not-fail)
- Add `harpyja/eval/test_think_ab_integration.py` (`@pytest.mark.integration`, skip-not-fail):
  - `test_ab_live_paired_run_emits_verifier_clean_artifacts` — drives `run_verified_case` per
    case×arm×K over the 0036 set, folds K via `any-success`, writes durable `0038/1` artifacts under
    the spec dir, records symbols-adoption-per-arm + reasoning-cost-delta + per-arm typed-degrade
    table, computes McNemar; **gated**: if `ab_power_precheck` returns `UNDER_POWERED_STOP` the test
    asserts the paired run is N/A-on-branch and the stop artifact is the deliverable (AC6).
- Test fails / skips: `run_ab_paired` absent (skips without a live stack).

### Step 14 — Implement the paired runner + committed strict driver (GREEN)
- Implement `run_ab_paired(...)` in `think_ab_run.py` (per-case stack, `dataclasses.replace` for the
  arm's `explorer_think`, no SUT mutation) and commit `specs/0039-thinking-ab/run_thinking_ab.sh` —
  the STOP-AND-WARN, resumable, strict skip→hard-fail operator driver (the 0038 `run_effectiveness.sh`
  precedent): preflight → precheck gate → paired run → aggregate.
- Step-13 test passes live (or skips honestly); the strict driver run is the deliverable seam.

### Step 15 — Typed verdict claim artifact, archive-first pin (RED)
- Add `harpyja/eval/test_think_ab_claim.py`:
  - `test_committed_ab_claim_matches_computed_verdict` — the committed claim's verdict + split table
    equal `decide_ab_report` (or the `UNDER_POWERED_STOP` on the gated branch) recomputed from the
    committed records (AC7).
  - `test_claim_artifact_path_pins_archive_first` — the loader resolves
    `specs/.archive/0039-thinking-ab/claim.json` archive-first, live fallback (carry-in, 79f7bf2).
  - `test_claim_split_by_reachability_not_whole_set_average` — the claim is split by reachability; no
    whole-set average is the headline (AC7).
- Tests fail: claim loader/artifact absent.

### Step 16 — Emit + pin the committed claim (GREEN)
- Implement `load_committed_ab_claim()` (archive-first) and commit
  `specs/0039-thinking-ab/claim.json` — the typed verdict + reachability split (or the
  `UNDER_POWERED_STOP` deliverable on the gated branch, naming the 0036 carry-forward), test-pinned to
  computed truth.
- All Step-15 tests pass.

### Step 17 — Doc: causation stance (AC8, doc)
- Write `specs/0039-thinking-ab/findings.md`: the think-experiment N=2 cited as MOTIVATION only, this
  run's verdict the first powered read with its own N/power stated honestly, NO default-flip decided
  here (separate spec), the observational True(`high`) arm reported observational-only. Add a light
  content pin `test_findings_cites_n2_as_motivation_only` if a machine-checkable line is warranted.
- Doc present; pin (if added) green.

### Step 18 — Refactor (optional)
- Fold the on/off→`PilotPair` adapter, the reachability tag lookup, and the archive-first path
  resolver into single shared helpers so the oracle-reuse and path-pin conventions have one home.
- All tests still pass.

## Delegation

- Steps 1–10 (pure verdict/config/pre-check machinery) → keep in-thread; tightest match to this
  repo's frozen-config + total-pure-function convention, no live stack needed.
- Steps 13–14 (live integration + operator driver) → delegate to an operator/live-run agent with the
  Ollama `qwen3:14b` stack; reason: needs the served model + ~4h resumable wall-clock, strength match
  on live-stack orchestration.

## Risk

- **`UNDER_POWERED_STOP` is the probable outcome** (N=15/floor 8/~50% base) → mitigation: the pre-check
  gates BEFORE ~4h wall-clock; the typed stop naming the 0036 pool-enlargement carry-forward is a
  first-class deliverable (Steps 9–10, 16), not a failure.
- **`/v1` silently drops `seed`** (0037 shape) → mitigation: the two-call preflight probe (Step 11/12);
  a negative keeps the config claim `unverified` and downgrades the paired-per-repeat property rather
  than asserting false provenance.
- **Factor-(b) misfires on easy cases** → mitigation: the predicate is frozen as per-case aggregate
  with a `min_on_vs_off_token_delta` and only bites when on-arm reasoning≈0 (Steps 1, 5–6), so a legit
  small delta on a genuinely-reasoning on-arm is never invalidated.
- **On-arm reasoning tax against `explorer_max_tokens=2048` → predictable CONFOUNDED** → mitigation:
  projected for free in the pre-check (Step 9) and captured as the per-arm typed-degrade table
  CONFOUNDED input (Step 8), never tuned here (out of scope).
- **Model choice as a post-hoc lever** → mitigation: `lm_model`/`serving_transport` pinned IN the
  frozen hashed config (Steps 1–2), verifier artifact proves per-case what the config pre-registered.
