---
id: "0040"
spec: "0040"
title: "pool"
status: planned
strategy: tdd
created: 2026-07-10
---

# Plan — 0040 pool

Three-model preflight + pilot + per-pair power pre-check — the cheap gate deciding, PER PAIR
(14b-8b, 14b-4b, 8b-4b), whether the bake-off runs on the current 19-case set or needs pool
enlargement, BEFORE ~hours of live compute. This spec is **measurement machinery, no SUT change**.
It is NOT greenfield: it reuses the committed `is_signal_discordant` / `located_via_oracle`
localization oracle (`ac8_pilot`, `think_ab`), the `benchmark_fit.PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS=8`
floor arithmetic, the `PREREGISTERED_*` frozen+hashed config pattern (`config_hash` over
`dataclasses.asdict`), the typed-probe-result contract shape (`think_probe`/`reconcile_probe`:
enum + loud validator + archive-first loader), the resumable `AbLedger` + `ab_preflight` +
`require_live_stack` driver posture (`think_ab_run`), the `run_verified_case` live seam
(`live_verifier`), and the STOP-AND-WARN committed-operator-driver convention (`specs/0036/pilot/run_pilot.py`,
`specs/0038/probes/run_probes.sh`). The genuinely new surface is `PREREGISTERED_POOL_CONFIG_0040`,
the five-member asymmetric preflight enum + precedence, the TWO per-pair quantities (union-located
ceiling as a true bound vs observed discordance as a labeled point estimate), the total per-pair
verdict with frozen predicate order, the derived coverage minimum, and the three-model live
preflight + pilot drivers.

## Sequencing law (freeze-before-run, hard gate)

1. **Config + both enums + the total pure machinery land BEFORE any live-touching code**
   (Steps 1–10). `PREREGISTERED_POOL_CONFIG_0040` (frozen + hashed), the preflight enum +
   precedence, the two projection quantities, the derived coverage minimum, and the per-pair
   verdict are ALL committed before the first preflight/pilot call fires — the 0036/0039
   re-registration rule: a frozen-then-wrong label is durable in committed artifacts.
2. **Preflight EXCLUDES before the pilot measures capability (the 16B-gibberish lesson):** the
   live preflight (Steps 13–14) runs the same typed enum for ALL THREE models (14b re-confirmed,
   not assumed); an EXCLUDING outcome removes the model with a recorded typed reason and types
   every pair containing it `PAIR_NOT_EVALUATED_MODEL_EXCLUDED` — never a partial artifact.
3. **The per-pair pre-check GATES pool enlargement, not a live bake-off:** no bake-off compute is
   spent here. The fork (Step 19–21) names, per pair, `PAIR_FEASIBLE` (bake-off may run) vs
   UNDER_POWERED / TOO_CLOSE / INSUFFICIENT / MODEL_EXCLUDED (pool enlargement, which also unblocks
   the 0039 A/B). Integration wrappers skip-not-fail on an absent live stack; the committed
   operator drivers STOP-AND-WARN on infra and resume from a ledger.

## Test-first sequence

### Step 1 — Frozen+hashed pool config, all verdict-shaping fields pinned (RED)
- Add `harpyja/eval/test_pool_precheck.py`:
  - `test_preregistered_pool_config_0040_pins_all_verdict_shaping_fields` — the three model tags
    (`qwen3:14b`, `qwen3:8b`, `qwen3.5:4b`), the three named pairs (14b-8b, 14b-4b, 8b-4b), the
    per-pair-α multiplicity stance + its decision-theoretic rationale, the pinned pilot case IDs,
    `MIN_PILOT_CONCEPTUAL_COVERAGE=8`, the coverage derivation string, the preflight precedence,
    the pair-verdict predicate order, the arm-parity pin `explorer_think=None`, and the staging
    order fallback (OQ3).
  - `test_pool_config_conceptual_floor_reuses_benchmark_fit` — the floor is FIXED at
    `benchmark_fit.PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS` (8, copied verbatim from 0039), not a
    re-derivable literal.
  - `test_pool_config_coverage_minimum_is_the_consuming_arithmetic` — `MIN_PILOT_CONCEPTUAL_COVERAGE=8`
    and its derivation encodes `full_conceptual_n − c < floor` ⇒ `c ≥ 8` (the vacuity boundary), not
    a round guess; asserted against `full_conceptual_n=15` and `floor=8`.
  - `test_pool_config_two_quantities_carry_distinct_epistemic_labels` — the ceiling carries
    `projection_kind="upper-bound-feasibility"` and the observed discordance carries
    `estimate_kind="point-estimate"`; the two labels are DISTINCT (the headline anti-conflation).
  - `test_pool_config_pinned_pilot_ids_cover_at_least_eight_conceptual` — the pinned pilot IDs,
    joined against the committed 0036 reachability tags (`think_ab_precheck.load_fixture_reachability`),
    include ≥8 conceptual cases (extends the 0036 first-10's 7 by ≥1), selected by case-ID order.
  - `test_pool_config_hash_0040_is_stable` — `POOL_CONFIG_HASH_0040` matches a recomputed hash.
- Tests fail: `harpyja/eval/pool_precheck.py` and its constants do not exist.

### Step 2 — Implement the frozen config (GREEN)
- Implement `harpyja/eval/pool_precheck.py` with `PoolConfig` (frozen dataclass),
  `PREREGISTERED_POOL_CONFIG_0040`, `POOL_CONFIG_HASH_0040` (`config_hash` mirroring `think_ab`).
  Module docstring states the per-pair-α multiplicity stance (outcome-blind, uncorrected — each pair
  is a standalone decision), the deliberate preflight-enum asymmetry, and the staging order.
- All Step-1 tests pass.

### Step 3 — Preflight outcome enum + precedence + adjudicator (RED)
- Extend `harpyja/eval/test_pool_precheck.py`:
  - `test_preflight_outcomes_are_exactly_the_five_committed_values` — `PREFLIGHT_PASS`, `UNSERVABLE`,
    `COHERENCE_FAIL`, `TOOL_CALL_MALFORMED`, `THINK_CONTROL_NOOP`; no more, no fewer.
  - `test_preflight_precedence_frozen_order` — precedence
    `UNSERVABLE > COHERENCE_FAIL > TOOL_CALL_MALFORMED > THINK_CONTROL_NOOP > PREFLIGHT_PASS`.
  - `test_preflight_tiebreak_coherence_and_toolcall_types_coherence_fail` — a fixture failing BOTH
    coherence and tool-calling adjudicates to `COHERENCE_FAIL` (the committed tie-break, not
    implementer choice).
  - `test_indeterminate_think_probe_maps_to_think_control_noop` — an indeterminate think-control probe
    (effect unadjudicable under the tiny-cap discriminator) maps to `THINK_CONTROL_NOOP`, never a
    stall outside the committed answer space.
  - `test_preflight_asymmetry_noop_nonexcluding_others_excluding` — `is_excluding(THINK_CONTROL_NOOP)`
    is False (model proceeds to pilot); `is_excluding` is True for `UNSERVABLE`/`COHERENCE_FAIL`/
    `TOOL_CALL_MALFORMED`, each carrying its typed exclusion reason.
- Tests fail: `PreflightOutcome`, `PREFLIGHT_PRECEDENCE`, `adjudicate_preflight`, `is_excluding` absent.

### Step 4 — Implement the preflight enum + adjudicator (GREEN)
- Implement `PreflightOutcome` (enum), `PREFLIGHT_PRECEDENCE` (frozen ordered tuple),
  `adjudicate_preflight(observations) -> PreflightOutcome` (evaluates the checks in precedence order,
  indeterminate think → `THINK_CONTROL_NOOP`), and `is_excluding(outcome) -> bool`. Docstring states
  the asymmetry is load-bearing (excluding vs recorded-non-excluding) and must not be "fixed" symmetric.
- All Step-3 tests pass.

### Step 5 — TWO per-pair quantities from per-case pairs, oracle reuse (RED)
- Extend `harpyja/eval/test_pool_precheck.py`:
  - `test_union_located_ceiling_and_observed_discordance_from_per_case_pairs` — from per-case pairs
    `(case_id, a_bucket, b_bucket)` on the conceptual stratum, the ceiling = extrapolated per-case
    UNION-located count, the observed = extrapolated `is_signal_discordant` count.
  - `test_observed_discordance_reuses_committed_is_signal_discordant_oracle` — identity-asserted
    one-oracle reuse (monkeypatch `ac8_pilot.is_signal_discordant`; only a true delegate observes it),
    the 0032 import-identity pattern.
  - `test_ceiling_reuses_benchmark_fit_floor_comparison_not_re_derived` — the floor compared against is
    `benchmark_fit.PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS`, not a local literal.
  - `test_marginal_counts_trap_yields_different_verdicts` — two scenarios with IDENTICAL marginal
    locate-counts but different per-case overlap produce DIFFERENT quantities (union-located and
    discordance are per-case properties marginals cannot recover — the evidence-quality guard).
  - `test_ceiling_is_not_vacuous_and_distinct_from_observed_discordance` — on a fixture where models
    locate overlapping-but-discordant sets, the ceiling is neither trivially = full-N nor equal to the
    observed-discordance estimate (the two quantities genuinely differ).
- Tests fail: `build_pair_cases`, `union_located_ceiling`, `observed_discordance` absent.

### Step 6 — Implement the two quantities (GREEN)
- Implement `PairCase` (per-case `(case_id, a_bucket, b_bucket)`), `build_pair_cases`,
  `union_located_ceiling` (extrapolated `round(rate * full_conceptual_n)` over union-located per-case
  pairs, routing through `think_ab.located_via_oracle`), and `observed_discordance` (extrapolated over
  `is_signal_discordant` pairs). Docstring states the ceiling is a TRUE bound (one-oracle reuse:
  `is_signal_discordant` requires ≥1 located arm) while observed is a labeled point estimate.
- All Step-5 tests pass.

### Step 7 — Derived coverage minimum, boundary fixtures (RED)
- Extend `harpyja/eval/test_pool_precheck.py`:
  - `test_pilot_conceptual_coverage_counts_both_buckets_present` — coverage `c` counts conceptual
    cases where BOTH models produced a bucket.
  - `test_insufficient_pilot_evidence_fires_at_c_equals_seven` — the 0036 first-10 subset alone
    (7 conceptual) → the coverage predicate fires.
  - `test_insufficient_pilot_evidence_does_not_fire_at_c_equals_eight` — at `c=8` the predicate does
    NOT fire (the derived boundary `15 − c < 8`), never a shaky FEASIBLE.
- Tests fail: `pilot_conceptual_coverage` / `coverage_below_minimum` absent.

### Step 8 — Implement the coverage predicate (GREEN)
- Implement `pilot_conceptual_coverage(pair_cases)` and `coverage_below_minimum(pair_cases, cfg)`
  reading `cfg.MIN_PILOT_CONCEPTUAL_COVERAGE`. Pure; boundary-strict.
- All Step-7 tests pass.

### Step 9 — Total per-pair verdict + frozen predicate order + fork over 3 pairs (RED)
- Extend `harpyja/eval/test_pool_precheck.py`:
  - `test_pair_verdict_total_over_five_member_enum_every_member_reachable` — constructed inputs reach
    each of `PAIR_NOT_EVALUATED_MODEL_EXCLUDED / INSUFFICIENT_PILOT_EVIDENCE / PAIR_UNDER_POWERED /
    PAIR_MODELS_TOO_CLOSE / PAIR_FEASIBLE`.
  - `test_pair_verdict_predicate_order_frozen` — evaluated in exactly that order (MODEL_EXCLUDED first,
    then INSUFFICIENT, then UNDER_POWERED, then TOO_CLOSE, then FEASIBLE); non-overlapping.
  - `test_too_close_distinct_from_under_powered_when_ceiling_clears_discordance_zero` — a fixture where
    both models locate the SAME cases (ceiling ≥ 8, discordance 0) types `PAIR_MODELS_TOO_CLOSE`, not
    `PAIR_UNDER_POWERED` (the distinct reportable finding: under-powered-because-identical).
  - `test_model_excluded_voids_every_pair_containing_it_including_14b` — a preflight-excluded member
    types every containing pair `PAIR_NOT_EVALUATED_MODEL_EXCLUDED`; a 14b re-confirmation failure voids
    ALL THREE pairs.
  - `test_decide_pool_fork_types_all_three_pairs` — `decide_pool_fork` returns a typed verdict for each
    of the three named pairs over `(config, per-model pilot buckets, per-model preflight outcomes)`.
- Tests fail: `PairVerdict`, `decide_pair_verdict`, `decide_pool_fork` absent.

### Step 10 — Implement the verdict + fork (GREEN)
- Implement `PairVerdict` (5-member enum), `decide_pair_verdict(cfg, pair_cases, preflight_a, preflight_b)`
  (total pure function in the frozen order: `is_excluding` on either member → MODEL_EXCLUDED;
  `coverage_below_minimum` → INSUFFICIENT; `union_located_ceiling < floor` → UNDER_POWERED;
  `observed_discordance < floor` → TOO_CLOSE; else FEASIBLE), and `decide_pool_fork(cfg, ledger,
  preflight_by_model)` mapping the three pairs. Reuses `benchmark_fit` floor + the Step-6 quantities.
- All Step-9 tests pass.

### Step 11 — Committed per-model preflight-result contract, archive-first loader (RED)
- Add `harpyja/eval/test_pool_preflight_result.py` (mirrors `test_reconcile_probe_result.py`):
  - `test_validate_pool_preflight_result_rejects_unknown_schema` — loud reject on a bad `schema_version`.
  - `test_validate_requires_all_three_models_each_typed` — the result must carry exactly the three
    committed model tags, each with an outcome in the committed preflight enum + a recorded reason when
    excluding.
  - `test_outcome_must_be_in_committed_preflight_enum` — an off-enum outcome is loudly rejected.
  - `test_load_committed_pool_preflight_result_archive_first` — the loader resolves
    `specs/.archive/0040-pool/preflight/preflight_result.json` first, live path fallback (the 79f7bf2
    convention).
- Tests fail: `harpyja/eval/pool_preflight_result.py` absent.

### Step 12 — Implement the preflight-result contract (GREEN)
- Implement `harpyja/eval/pool_preflight_result.py`: `POOL_PREFLIGHT_SCHEMA_VERSION="0040/preflight/1"`,
  `validate_pool_preflight_result` (loud, no silent defaults — reuses the `PreflightOutcome` values),
  `load_pool_preflight_result`, `load_committed_pool_preflight_result` (archive-first). No verifier-schema
  field added (spec-local artifact, the 0037/0038 posture).
- All Step-11 tests pass.

### Step 13 — Live three-model preflight (RED, integration skip-not-fail) [LIVE]
- Add `harpyja/eval/test_pool_preflight_integration.py` (`@pytest.mark.integration`, skip-not-fail via
  `require_live_stack`):
  - `test_three_model_preflight_runs_live_and_types_each` — drives a per-model probe (coherence on a
    known-localizable case + clean `/v1` `tool_calls` + think-control) through `adjudicate_preflight`
    for all three tags (14b re-confirmed); asserts each result is a typed `PreflightOutcome` and an
    excluding model carries its recorded reason. Skips without a live stack; under
    `HARPYJA_REQUIRE_LIVE_STACK` a skip is a hard fail.
- Test skips (no live stack) / fails: `run_model_preflight` absent.

### Step 14 — Implement the live preflight probe + committed driver (GREEN) [LIVE]
- Implement `run_model_preflight(gateway, settings, model) -> PreflightOutcome` in
  `harpyja/eval/pool_pilot.py` (coherence probe via `run_verified_case` on a pinned localizable case;
  tool-call cleanliness; think-control via the 0038 `reasoning_effort` probe / its qwen3.5 equivalent).
  Commit `specs/0040-pool/preflight/run_preflight.sh` — the STOP-AND-WARN operator driver that probes
  Ollama `/api/tags`, runs all three models, and writes `specs/0040-pool/preflight/preflight_result.json`
  (the three typed outcomes). Add `test_committed_preflight_result_pins_three_models` (pins the committed
  artifact once it exists; guarded to the fixture until the live run lands).
- Step-13 test passes live (or skips honestly); the committed preflight result is the deliverable seam.

### Step 15 — Resumable pilot ledger + STOP-AND-WARN driver preflight (RED)
- Add `harpyja/eval/test_pool_pilot.py`:
  - `test_pool_pilot_ledger_resumes_completed_cells` — a per `case::model` ledger skips already-recorded
    cells on re-invocation (the ~100+ min pilot outlasts one process), config-hash pinned.
  - `test_pool_pilot_ledger_schema_validates_loud` — a pinned version-stamped ledger schema, loud validator.
  - `test_pool_pilot_preflight_stops_when_model_tag_unserved` — the driver preflight STOPs loudly when a
    pinned tag is not served (never a silent skip / substitution under the frozen hash).
  - `test_strict_run_skip_is_hard_fail` — under `HARPYJA_REQUIRE_LIVE_STACK` a skip becomes a hard fail.
- Tests fail: `PoolPilotLedger` / `pool_pilot_preflight` absent.

### Step 16 — Implement the pilot ledger + preflight (GREEN)
- Implement `PoolPilotLedger` (pinned schema `0040/pilot/1`, resumable, `case::model` keyed, entries
  carry `bucket`/`degrade`/`artifact` — the 0036 pilot-ledger shape the `decide_pool_fork` reader
  consumes) and `pool_pilot_preflight` (served-tag STOP-AND-WARN, reusing the `ab_preflight` posture),
  behind `require_live_stack`. Reuse `AbLedger`'s atomic-flush mechanics where clean.
- All Step-15 tests pass.

### Step 17 — Live three-model pilot at default-think (RED, integration skip-not-fail) [LIVE]
- Add `harpyja/eval/test_pool_pilot_integration.py` (`@pytest.mark.integration`, skip-not-fail):
  - `test_three_model_pilot_emits_verifier_clean_artifacts_at_default_think` — drives `run_verified_case`
    per preflight-passing model × pinned pilot case at `explorer_think=None` (arm parity), retains the
    per-case bucket, records each model's conceptual locate-count, and resumes from `PoolPilotLedger`.
    Skips without a live stack.
- Test skips / fails: `run_pool_pilot` absent.

### Step 18 — Implement the pilot runner + committed driver (GREEN) [LIVE]
- Implement `run_pool_pilot(cfg, out_dir, ledger_path, live=True)` in `harpyja/eval/pool_pilot.py`
  (per model+case `run_verified_case` at `explorer_think=None` via `dataclasses.replace`, no SUT
  mutation, durable `0034/1` artifacts through `live_artifact_dir`, resumable ledger). Commit
  `specs/0040-pool/pilot/run_pilot.py` — the STOP-AND-WARN, resumable, strict operator driver (the
  0036 `run_pilot.py` precedent) writing `specs/0040-pool/pilot/pilot_results.json`.
- Step-17 test passes live (or skips honestly); the committed pilot ledger is the deliverable seam.

### Step 19 — Fork claim artifact matches computed truth, archive-first pin (RED)
- Add `harpyja/eval/test_pool_fork.py`:
  - `test_committed_pool_fork_matches_computed_truth` — the committed fork's per-pair verdicts equal
    `decide_pool_fork` recomputed from the committed pilot ledger + preflight result (or, on an
    incomplete-live branch, the typed pending disposition), the 0039 claim-pin pattern.
  - `test_load_committed_pool_fork_archive_first` — the loader resolves
    `specs/.archive/0040-pool/pool_fork.json` first, live fallback.
  - `test_fork_names_pool_enlargement_for_non_feasible_pairs` — every non-`PAIR_FEASIBLE` pair names the
    pool-enlargement next step (which also unblocks the 0039 A/B).
- Tests fail: `load_committed_pool_fork` / the committed artifact absent.

### Step 20 — Emit + pin the committed fork (GREEN)
- Implement `load_committed_pool_fork()` (archive-first) and emit `specs/0040-pool/pool_fork.json` from
  the committed pilot + preflight evidence (via the operator driver or a thin emit step), test-pinned to
  `decide_pool_fork`'s computed truth. On an absent/partial live run the artifact records the typed
  pending branch, never a fabricated verdict.
- All Step-19 tests pass.

### Step 21 — Doc: the overall fork (AC8, DOC)
- Write `specs/0040-pool/findings.md`: which pairs are `PAIR_FEASIBLE` (bake-off may run now) vs
  UNDER_POWERED / TOO_CLOSE / INSUFFICIENT / MODEL_EXCLUDED (pool enlargement, which also unblocks the
  0039 A/B); the extrapolation-modulo-sampling caveat (0039 carry-in) applied to BOTH pinned quantities;
  the record of any `THINK_CONTROL_NOOP` model (bakes off default-on, barred from a future thinking-arm);
  no live bake-off compute spent here. Optional machine-checkable content pin
  `test_findings_states_no_bakeoff_compute_spent`.
- Doc present; pin (if added) green.

### Step 22 — Refactor (optional)
- Fold the union-located/discordance oracle routing, the extrapolation rounding
  (`round(rate * full_n)`), and the archive-first path resolver into single shared helpers so the
  one-oracle-reuse and evidence-path conventions have one home; reuse `AbLedger`'s atomic-flush if the
  pilot ledger duplicates it.
- All tests still pass.

## Delegation

- Steps 1–12, 15–16, 19–22 (pure config/enum/quantities/verdict/coverage machinery + the contract +
  the ledger + the fork pin) → keep in-thread; tightest match to this repo's frozen-config +
  total-pure-function convention, no live stack needed.
- Steps 13–14 and 17–18 (live three-model preflight + pilot + committed operator drivers) → delegate to
  an operator/live-run agent with the local Ollama stack serving `qwen3:14b`, `qwen3:8b`, `qwen3.5:4b`
  (the 32 GB dev host per repo memory; the two new tags must be pulled). Reason: needs the served models
  + the resumable ~100+ min pilot wall-clock, strength match on live-stack orchestration.

## Risk

- **A member model is UNSERVABLE / OOMs (`qwen3:8b`, `qwen3.5:4b` never ran this harness)** →
  mitigation: the typed `UNSERVABLE`/`COHERENCE_FAIL` preflight EXCLUDES with a recorded reason and
  types the containing pairs `PAIR_NOT_EVALUATED_MODEL_EXCLUDED`; the STOP-AND-WARN driver aborts loud,
  never a partial artifact (Steps 3–4, 9–10, 13–14).
- **14b re-confirmation regresses** → mitigation: 14b runs the SAME typed enum (not assumed from 0039);
  a failure voids all three pairs with the typed disposition, tested (Step 9).
- **`qwen3.5:4b` think-control is a new/absent param** → mitigation: probe-don't-assume; an indeterminate
  result maps to `THINK_CONTROL_NOOP` (conservative, non-excluding — bakes off default-on), tested
  (Steps 3–4).
- **Epistemic mislabel of the ceiling (the round-2 headline)** → mitigation: TWO distinct labeled
  quantities — union-located ceiling (`upper-bound-feasibility`) vs observed discordance
  (`point-estimate`) — with a fixture proving they differ, so a false UNDER_POWERED from sampling noise
  is structurally impossible (Steps 1, 5–6).
- **Marginal-counts trap** → mitigation: quantities computed only from per-case pairs; the
  counts-identical/overlap-different fixture pins it shut (Step 5).
- **Coverage vacuity** → mitigation: the derived minimum `c ≥ 8` (`15 − c < 8`) with boundary fixtures
  at `c=7`/`c=8` (Steps 7–8); a pair below it types `INSUFFICIENT_PILOT_EVIDENCE`, never a shaky FEASIBLE.
- **Pilot wall-clock outlasts one invocation** → mitigation: the resumable `case::model` ledger + the
  pre-declared staging order (preflight all 3 → pilot the widest-gap pair first), never chosen after
  early results are visible (Steps 15–18).
