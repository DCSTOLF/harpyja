---
spec: "0048"
status: planned
strategy: tdd
---

# Plan — 0048 bake-off

Three-model powered ranking (`qwen3:14b` / `qwen3:8b` / `qwen3.5:4b`), split by
reachability, over the 0047 enlarged pool (53 cases: conceptual 44 / lexical 9, pool
sha256 `385107934f61…`). This is a **MEASUREMENT** spec: the harness (`harpyja/eval/`)
runs the EXISTING instrument (tiers/gate/explorer/verifier) unchanged. No SUT mutation;
any SUT change is a surfaced defect with its own regression test.

The work is REUSE-first. The pure analysis core imports the ONE committed discordance +
located oracles BY IDENTITY (`ac8_pilot.is_signal_discordant` / `ac8_pilot.PilotPair`,
`think_ab.located_via_oracle`, `benchmark_fit.mcnemar_exact_p` / `mcnemar_rejects`,
`locate_accuracy.LocateBucket`) — never re-derived (identity-asserted by test, the
pool_precheck one-oracle-reuse rule). The run mirrors `think_ab_run.AbLedger` /
`ab_preflight` / `seed_honoring_probe`, `swebench_eval.preflight_models_present`
(assert-local-first + positive `/api/tags`), and `exclusivity_gate.*` (0041 proof per
artifact), and iterates the `enlargement`/`enlargement_run` pool + `terse_reachability`
tags + `live_verifier` per-case buckets.

## New owning modules

- `harpyja/eval/bakeoff_config.py` — the FROZEN 0048 config (dataclass + sha256 hash),
  committed before the first live call.
- `harpyja/eval/bakeoff_analysis.py` — the pure analysis core (AC3, AC4-pure, AC5-pure):
  per-pair `b+c`, the four coverage/closeness outcomes, Holm step-down, per-repo
  concentration, the reachability split, the typed assembly.
- `harpyja/eval/bakeoff_run.py` — the integration wiring (AC1 preflight, AC2 ledger +
  durable artifact, AC4/AC5/AC6 report, the staged live run).
- `specs/0048-bake-off/outcome.md` — the typed-outcome writeup (AC7).

## Frozen-config divergence from 0040 (call out, do NOT silently reuse)

`pool_precheck.PoolConfig` froze `multiplicity_stance="per-pair-alpha-uncorrected"`.
0048 DELIBERATELY chooses **Holm–Bonferroni, m=3 FIXED** (the reconciled-freeze
discipline). 0048 therefore freezes its OWN `BakeoffConfig` + own hash, NEVER reuses
0040's stance or hash. The config step pins BOTH the new stance and a rationale string
naming the divergence; the ONLY things reused-by-identity are the discordance/located
oracles and the absolute floor of 8 (`benchmark_fit.PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS`).

## Test-first sequence

### Step 1 — Frozen 0048 config (RED)
- Add `harpyja/eval/test_bakeoff_config.py`:
  - `test_bakeoff_config_pins_three_tags_and_three_pairs` — `model_tags` == the exact three;
    `pairs` == (14b-8b, 14b-4b, 8b-4b) in that frozen order.
  - `test_bakeoff_config_pins_absolute_floors_and_thresholds` — `conceptual_min_discordant == 8`
    (identity-reused from `benchmark_fit.PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS`),
    `coverage_floor == 36`, `degraded_dominated_threshold == 0.5`, `holm_family_size == 3`,
    `alpha == 0.05`, `conceptual_n == 44`, `lexical_n == 9`.
  - `test_bakeoff_config_pins_decoding_and_pool_provenance` — `temperature == 0.0`,
    `top_p == 1.0`, `seed` a single pinned int; `pool_sha256` == the full
    `385107934f6107544c68a48f49d294ec4534616acd2f6e9b30b0bedd754bb7d3`; `explorer_think is None`.
  - `test_bakeoff_config_multiplicity_diverges_from_0040_holm_m3` — `multiplicity_stance`
    names Holm–m3-fixed and is NOT `PoolConfig`'s `per-pair-alpha-uncorrected`; a rationale
    string is present.
  - `test_bakeoff_config_hash_is_stable` — `BAKEOFF_CONFIG_HASH_0048` equals the recomputed
    sha256 over the frozen fields (pins every field against silent drift).
- Tests fail: `bakeoff_config` does not exist.

### Step 2 — Frozen 0048 config (GREEN)
- Implement `harpyja/eval/bakeoff_config.py`: `BakeoffConfig` frozen dataclass (mirroring
  `pool_precheck.PoolConfig`) with the fields above, `PREREGISTERED_BAKEOFF_CONFIG_0048`,
  `bakeoff_config_hash`, `BAKEOFF_CONFIG_HASH_0048`. Floor reused by identity; staging order,
  tie-break pair order, and the Holm-divergence rationale pinned as literals.
- All step-1 tests pass.

### Step 3 — Per-pair discordance `b+c` from per-case buckets (RED)
- Add `harpyja/eval/test_bakeoff_analysis.py`:
  - `test_discordant_counts_uses_is_signal_discordant_by_identity` — assert
    `bakeoff_analysis.is_signal_discordant is ac8_pilot.is_signal_discordant` and
    `bakeoff_analysis.located_via_oracle is think_ab.located_via_oracle` (the one-oracle-reuse
    identity assertion).
  - `test_discordant_counts_b_and_c_from_per_case_buckets` — a fixture of `BakeoffPairCase`
    rows yields `b` (model_a located, model_b not) and `c` (model_b located, model_a not);
    `b+c` equals the count of `is_signal_discordant` rows; NOT marginal locate-counts (pin the
    0040 counts-vs-pairs distinction with a fully-overlapping vs disjoint fixture giving equal
    marginals but different `b+c`).
- Tests fail: `bakeoff_analysis` does not exist.

### Step 4 — Per-pair discordance (GREEN)
- Implement in `harpyja/eval/bakeoff_analysis.py`: `BakeoffPairCase(case_id, repo, bucket_a,
  bucket_b)`, `discordant_counts(pair_cases) -> (b, c)`, re-exporting `is_signal_discordant`
  and `located_via_oracle` by identity import (never redefined).
- All step-3 tests pass.

### Step 5 — The four coverage/closeness outcomes (RED)
- Extend `test_bakeoff_analysis.py`:
  - `test_pair_outcome_under_powered_below_coverage_floor` — eligible paired conceptual
    N < 36 → `PAIR_UNDER_POWERED`, regardless of `b+c`.
  - `test_pair_outcome_degraded_dominated_flag_partitions_by_cause` — an under-powered pair with
    > 50% of dropped conceptual cases degrade-caused carries `degraded_dominated=True`; at ≤ 50%
    it is `False` (the frozen 0.5 threshold; partition, not a competing label).
  - `test_pair_outcome_models_too_close_when_discordance_below_floor` — N ≥ 36 and `b+c < 8`
    → `PAIR_MODELS_TOO_CLOSE` (descriptive; asserts NO powered-equivalence claim field).
  - `test_pair_outcome_no_difference_when_holm_not_reject` — `b+c ≥ 8`, Holm does not reject
    → `PAIR_NO_DIFFERENCE`.
  - `test_pair_outcome_separates_when_holm_rejects` — `b+c ≥ 8`, Holm rejects → `PAIR_SEPARATES`,
    winner = sign of `b − c`.
  - `test_pair_outcome_predicates_are_mutually_distinct` — grid over (N below/above 36) ×
    (b+c below/at/above 8) × (reject/not) lands EXACTLY one member each (totality, the 0045
    RefinementVerdict pattern; ABSOLUTE-count predicates — assert no denominator enters).
- Tests fail: `PairOutcome` / `decide_pair_outcome` absent.

### Step 6 — The four coverage/closeness outcomes (GREEN)
- Implement `PairOutcome` enum (`PAIR_UNDER_POWERED` / `PAIR_MODELS_TOO_CLOSE` /
  `PAIR_NO_DIFFERENCE` / `PAIR_SEPARATES`) + `PairResult` dataclass (b, c, eligible_n,
  dropped_total, dropped_degrade, degraded_dominated, raw_p, adjusted_p, rejected, winner,
  repo_concentrated) + `decide_pair_outcome(cfg, pair_cases, dropped_total, dropped_degrade,
  *, rejected)` in frozen predicate order: coverage → too-close → no-difference → separates.
- All step-5 tests pass.

### Step 7 — Exact McNemar + Holm step-down over three p-values (RED)
- Extend `test_bakeoff_analysis.py`:
  - `test_mcnemar_reused_by_identity` — `bakeoff_analysis.mcnemar_exact_p is
    benchmark_fit.mcnemar_exact_p` (no re-implementation of the exact test).
  - `test_holm_step_down_rejects_ascending_family_m3` — three raw p-values, `m=3` FIXED;
    reject `p(i)` iff `p(j) ≤ α/(m−j+1)` for all `j ≤ i`; pin a case where the smallest rejects
    and the next does not.
  - `test_holm_adjusted_pvalue_is_running_max` — adjusted `p = min(1, max_{j≤i}((m−j+1)·p(j)))`,
    pinned on a boundary set.
  - `test_holm_family_size_fixed_at_three_when_fewer_pairs_reach_test` — only two pairs reach
    McNemar (third TOO_CLOSE/UNDER_POWERED contributes no p-value) yet `m` stays 3 (anti-steering);
    assert the surviving tests use the divisor from m=3, not m=2.
  - `test_holm_ties_broken_by_fixed_pair_order` — equal p-values order by (14b-8b, 14b-4b, 8b-4b).
  - `test_holm_boundary_p_equal_alpha_rejects` — the `p ≤ α` (`≤`) convention at the boundary.
- Tests fail: `holm_step_down` / `holm_adjusted_pvalues` absent.

### Step 8 — Holm step-down (GREEN)
- Implement `holm_adjusted_pvalues(raw_p_by_pair, *, m=3, tie_order)` and
  `holm_rejections(..., alpha)` reusing `mcnemar_exact_p` by identity; `m` a FIXED param
  defaulting to `cfg.holm_family_size`, never data-dependent.
- All step-7 tests pass.

### Step 9 — Per-repo leave-one/leave-two-out concentration (RED)
- Extend `test_bakeoff_analysis.py`:
  - `test_repo_concentrated_when_leave_one_out_flips_direction` — dropping one repo flips
    `sign(b−c)` → `REPO_CONCENTRATED`.
  - `test_repo_concentrated_when_leave_two_out_drops_below_floor` — dropping two repos pushes
    `b+c < 8` → flagged.
  - `test_repo_not_concentrated_when_robust_to_all_drops` — a broadly-distributed fixture stays
    unflagged; assert the per-repo `b−c` distribution is returned alongside.
- Tests fail: `repo_concentrated` absent.

### Step 10 — Per-repo concentration (GREEN)
- Implement `repo_concentrated(pair_cases, *, alpha, floor) -> bool` (recompute discordance +
  McNemar direction dropping each single repo and each repo pair) and
  `per_repo_bc_distribution(pair_cases) -> dict[str,int]`.
- All step-9 tests pass.

### Step 11 — Typed assembly of the three pairwise verdicts (RED)
- Extend `test_bakeoff_analysis.py`:
  - `test_assembly_infrastructure_halted_when_fewer_than_two_survive` — < 2 surviving models →
    `INFRASTRUCTURE_HALTED`, excluded models + reasons named.
  - `test_assembly_partial_when_exactly_two_survive` — exactly 2 survive → `PARTIAL` with
    `MODEL_EXCLUDED(tag, reason)`; never `RANKING`/`INTRANSITIVE`.
  - `test_assembly_ranking_when_edges_form_total_order` — three `PAIR_SEPARATES` edges a total
    order → `RANKING`.
  - `test_assembly_intransitive_when_edges_form_cycle` — 14b≻8b, 8b≻4b, 4b≻14b → `INTRANSITIVE`
    (never coerced).
  - `test_assembly_partial_when_some_separate_some_not` — a mix → `PARTIAL` naming each pair's
    outcome.
  - `test_assembly_no_separation_when_no_pair_separates` — no conceptual pair separates →
    `NO_SEPARATION`.
  - `test_bakeoff_outcome_enum_is_total_over_grid` — the assembly is total over
    (survivor count × edge configuration); every input lands exactly one member.
- Tests fail: `BakeoffOutcome` / `assemble_bakeoff` absent.

### Step 12 — Typed assembly (GREEN)
- Implement `BakeoffOutcome` enum (`RANKING` / `INTRANSITIVE` / `PARTIAL` / `NO_SEPARATION` /
  `INFRASTRUCTURE_HALTED`), `ModelExclusion(tag, reason)`, `BakeoffReport` dataclass, and
  `assemble_bakeoff(pair_results, *, surviving_models, exclusions)` in the frozen survivorship
  order: <2 → HALTED → 2 → PARTIAL → 3 → (total order / cycle / mixed / none).
- All step-11 tests pass.

### Step 13 — Reachability split is first-class, pure part (RED)
- Extend `test_bakeoff_analysis.py`:
  - `test_split_by_reachability_conceptual_carries_verdict` — only conceptual-tagged cases enter
    the inferential `BakeoffPairCase` set.
  - `test_lexical_yields_descriptive_stats_only` — lexical produces per-model found/not-found
    raw counts, NO `PairOutcome`; assert the function returns descriptive counts, never a verdict.
  - `test_no_whole_pool_average_headline` — assert the report shape exposes per-stratum lines and
    has NO pooled/averaged headline field.
- Tests fail: `split_by_reachability` / `lexical_descriptive_stats` absent.

### Step 14 — Reachability split, pure part (GREEN)
- Implement `split_by_reachability(entries, reachability, model_a, model_b)` (complete-case
  paired conceptual join, mirroring `pool_precheck.build_pair_cases` but retaining `repo` and
  dropped/degrade tallies) and `lexical_descriptive_stats(entries, reachability, model)`.
- All step-13 tests pass.

### Step 15 — Refactor (optional)
- Fold the shared located/discordance/drop-tally helpers so `decide_pair_outcome`,
  `repo_concentrated`, and `split_by_reachability` read one home. Do NOT fold in the McNemar or
  located oracles — those stay identity-imported. All tests still pass.

### Step 16 — AC1 preflight: assert-local-first → positive `/api/tags` → coherence + `/v1` tool-calling → reproducibility replay (RED, integration)
- Add `harpyja/eval/test_bakeoff_run_integration.py` (`@pytest.mark.integration`, skip-not-fail):
  - `test_preflight_routes_through_assert_local_first` — the preflight calls `assert_local`
    before any `/api/tags` read (inject a resolver/recorder; mirrors
    `preflight_models_present`).
  - `test_preflight_positive_api_tags_membership_per_tag` — each of the three frozen tags must be
    present in the resolved served set; a down endpoint cannot pass trivially.
  - `test_preflight_excludes_model_on_coherence_or_tool_call_fail` — a per-model coherence /
    `/v1` tool-calling failure → `MODEL_EXCLUDED(tag, reason)`, not scored zero.
  - `test_reproducibility_replay_excludes_on_bucket_mismatch` — the double-run of ≥3 fixed
    conceptual cases with DIFFERING per-case buckets → EXCLUDE with a replay-fail reason; identical
    buckets → pass. (Drive the probe with an injected fake `run_case` returning buckets; unit-level
    logic exercised without the live stack.)
  - `test_preflight_config_tags_asserted_present` — the pinned `BakeoffConfig.model_tags` are the
    set asserted against the served set (closes the 8b/4b un-provenanced gap).
- Tests fail: `bakeoff_run` preflight absent.

### Step 17 — AC1 preflight (GREEN)
- Implement in `harpyja/eval/bakeoff_run.py`: a `PreflightOutcome`-style adjudicator (reuse the
  `pool_precheck.adjudicate_preflight` shape, ADDING a `REPLAY_FAIL` excluding member),
  `reproducibility_replay_probe(run_case, cases) -> str`, and `bakeoff_preflight(cfg, *,
  served_tags, per_model_observations, replay_results)` routing through `assert_local` first and
  the positive `/api/tags` check (reuse `preflight_models_present`), returning per-model
  outcomes + `ModelExclusion`s.
- All step-16 tests pass.

### Step 18 — AC2 resumable ledger + durable per model+case artifact (RED, integration)
- Extend `test_bakeoff_run_integration.py`:
  - `test_bakeoff_ledger_resumable_keyed_to_config_hash` — mirror `test_think_ab_run`:
    a ledger written under a DIFFERENT config hash is not resumable (loud `BakeoffRunError`);
    an unknown `schema_version` is rejected; `has/get/record` round-trip atomically.
  - `test_bakeoff_artifact_carries_full_schema` — a built artifact carries bucket, tools (incl.
    symbols-adoption), reasoning tokens, submitted/surviving, found-but-unsubmitted, model identity,
    `serving_transport`, the frozen decoding config (`temperature=0`/`top_p=1`/pinned `seed`), the
    pool sha256, the pinned SUT hash, and the exclusivity proof (validated via
    `exclusivity_gate.validate_exclusivity_record`).
  - `test_bakeoff_artifact_records_heavy_repo_degrade_rate` — heavy-repo degrade class counted
    per model (capping-coverage vs capability, feeds the degraded-dominated guard).
- Tests fail: `BakeoffLedger` / `build_bakeoff_artifact` absent.

### Step 19 — AC2 ledger + artifact (GREEN)
- Implement `BakeoffLedger` (mirror `AbLedger`, schema `0048/1`, keyed to
  `BAKEOFF_CONFIG_HASH_0048`, atomic same-dir temp + replace) and `build_bakeoff_artifact(...)`
  reusing `live_verifier`/`live_artifacts` fields and `exclusivity_gate.build_exclusivity_record`.
- All step-18 tests pass.

### Step 20 — AC4/AC5/AC6 report assembly (RED, integration)
- Extend `test_bakeoff_run_integration.py`:
  - `test_report_splits_by_reachability_no_pooled_headline` — the built report carries per-pair
    conceptual verdicts + lexical descriptive stats, no whole-pool average (AC4).
  - `test_report_flags_repo_concentrated_on_separating_pairs` — per-repo `b−c` distribution
    reported and every `PAIR_SEPARATES` runs leave-one/leave-two-out → flagged where thin (AC5).
  - `test_report_symbols_adoption_and_found_but_unsubmitted_per_model` — per-model
    symbols-adoption rate + found-but-unsubmitted count surfaced (AC6, the 0042/0043 threads).
- Tests fail: `build_bakeoff_report` absent.

### Step 21 — AC4/AC5/AC6 report assembly (GREEN)
- Implement `build_bakeoff_report(cfg, entries, reachability)` calling the pure core
  (`split_by_reachability`, `decide_pair_outcome`, `holm_*`, `repo_concentrated`,
  `assemble_bakeoff`) and computing per-model symbols-adoption + found-but-unsubmitted from the
  artifacts (mirror `think_ab_run`'s adoption aggregation).
- All step-20 tests pass.

### Step 22 — Staged detached live run (OP, integration/live)
- Add `harpyja/eval/bakeoff_run/run_bakeoff.sh` + `run_bakeoff(cfg, ...)` live driver:
  preflight all three → run the widest-gap pair (14b-4b) FIRST as an OPERATIONAL-ONLY feasibility
  check (no threshold/model/grid/decoding/prompt/pool change; the single sanctioned early stop is a
  NAMED safety/infra halt) → full grid. Resumable through `BakeoffLedger` across the full
  ~9h run (3×53×~200s). **DETACH DISCIPLINE (repo memory):** launch `nohup … & disown`, monitor the
  log file; NEVER a harness background Bash task (those die ~20 min). Marked `@pytest.mark.integration`;
  the operator-run DATA is produced outside the authoring sandbox.

### Step 23 — Typed outcome writeup (DOC)
- Write `specs/0048-bake-off/outcome.md` from the run: the typed `BakeoffOutcome`
  (`RANKING`/`INTRANSITIVE`/`PARTIAL`/`NO_SEPARATION`/`INFRASTRUCTURE_HALTED` with
  `MODEL_EXCLUDED` annotations), honestly N'd per pair/stratum, per-repo distribution, symbols
  adoption + found-but-unsubmitted, and the provenance (pool sha256, exclusivity proof, pinned SUT
  hash, train-on-test attestation). Pre-register `NO_SEPARATION` as a VALID homogeneity finding.

## Delegation

- Steps 1–15 (pure config + analysis core) → keep in-agent (fixture-pinned unit work, fast
  feedback; the largest surface, must land first).
- Steps 16–21 (integration wiring) → keep in-agent; reuse-heavy, mirrors `think_ab_run`.
- Step 22 (the ~9h detached live run) → delegate to an OPERATOR run outside the sandbox
  (reason: exceeds the harness background-task lifetime; needs nohup+disown + log monitoring).

## Risk

- **Single-draw stochastic estimator** → mitigation: the reproducibility replay probe (Step 16)
  EXCLUDES a model whose batched backend is not bit-reproducible at temp=0, closing the 0046
  multi-draw problem before its numbers count.
- **Coverage-outcome steering the Holm family** → mitigation: `m=3` FIXED as a config literal and
  pinned by `test_holm_family_size_fixed_at_three_when_fewer_pairs_reach_test`.
- **Silent 0040-stance reuse** → mitigation: 0048 owns its config + hash; the divergence is pinned
  by `test_bakeoff_config_multiplicity_diverges_from_0040_holm_m3`.
- **Heavy-repo timeout degrade capping coverage** → mitigation: per-model heavy-repo degrade rate
  recorded (Step 18) and read by the degraded-dominated partition; a recurrence past the guard is the
  single NAMED early stop, never outcome-dependent.
- **~9h run dying mid-flight** → mitigation: `BakeoffLedger` resumable across the full run; detached
  launch (Step 22).
- **Accidental SUT mutation** → mitigation: analysis core is pure and import-by-identity; any SUT
  change is a separate surfaced defect with its own regression test.
