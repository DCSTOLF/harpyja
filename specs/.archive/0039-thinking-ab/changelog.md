---
spec: "0039"
closed: 2026-07-10
---

# Changelog — 0039 thinking-ab

## What shipped vs spec

Spec 0039 built the complete paired None(default-on)-vs-False(off) thinking-A/B
verdict machinery on the trustworthy 0031–0035 verifier instrument — frozen config,
total pure verdict function, two-factor arm-distinctness guard, reachability split,
upper-bound feasibility pre-check, resumable STOP-AND-WARN driver, and a test-pinned
claim artifact — with NO SUT change (all pure/operator machinery in `harpyja/eval/`).

**Headline outcome: `UNDER_POWERED_STOP` at the AC5 gate, on committed evidence,
before any live arm fired.** The pre-check projected the achievable conceptual-stratum
signal-bearing discordant count from the committed 0036 pilot ledger: the pilot covered
only the first 10 of 19 cases → 7 conceptual; the pinned `qwen3:14b` arm located 3/7
(astropy-12907, requests-1766, sklearn-10844 via the committed 0026 oracle); the
projected UPPER BOUND round(15 × 3/7) = 6 < the frozen floor 8. The ~4h live paired run
was correctly NOT spent (the 0026 gate-before-spending discipline); the committed driver
ran live and exited 2 with the typed stop; `claim.json` (schema `0039/1`, `config_hash`
`f3cb5d67…`) commits the stop, pinned to computed truth by
`test_committed_ab_claim_matches_computed_verdict`.

The projection is LABELED an upper-bound-feasibility check, not a power estimate — the
0036 pilot measured cross-MODEL discordance (14b vs 4b-instruct), which BOUNDS but cannot
estimate within-model think-flip rates; every located case was generously assumed to flip
and even that ceiling cannot reach the floor.

### Per-AC disposition

- **AC1 [unit] — MET.** `PREREGISTERED_AB_CONFIG_0039` frozen+hashed (`AB_CONFIG_HASH_0039`):
  arms None/False/True(observational), `lm_model=qwen3:14b` + `serving_transport=v1-reasoning-effort`
  pinned to the committed 0038 probe BY TEST, `alpha=0.05`, `k_repeats=2` + `any-success` fold +
  `observational_k=1`, conceptual floor 8 fixed-not-re-derivable (reusing
  `benchmark_fit.MIN_DISCORDANT_PAIRS`), `stratum_min_cases=12` (reusing `min_n`),
  `invalid_pair_ceiling=0.20`, `degrade_asymmetry_threshold=0.20`, factor-b predicate
  (per-case-aggregate `completion_tokens`, on≥off, `min_on_vs_off_token_delta=64`, biting only
  when on-arm reasoning ≥ 256 chars). `decide_ab_verdict` is a TOTAL PURE function over the
  5-member `AbVerdict` (THINKING_HELPS / THINKING_HURTS / NO_EFFECT / UNDER_POWERED / CONFOUNDED),
  CONFOUNDED checked FIRST, grid-totality tested, predicates non-overlapping.
- **AC2 [unit] — MET.** Paired McNemar over signal-bearing discordant pairs (reusing
  `benchmark_fit.mcnemar_rejects`, direction-split for HELPS vs HURTS); under-floor null →
  UNDER_POWERED, never NO_EFFECT, never a forced result.
- **AC3 [unit] — MET.** `classify_pair_validity` two-factor guard, deliberately ASYMMETRIC:
  off-arm reasoning present → instrument defect → excluded-and-recorded (rate above ceiling →
  CONFOUNDED); on-arm zero reasoning → KEPT (legitimate shipped-None behavior); factor-b hidden-
  thinking signature invalidates. Exclusions surface in the report, never silently attrit N.
- **AC4 [unit] — MET.** `decide_ab_report` splits by reachability: conceptual stratum gets its
  own verdict line + floor; lexical N=4 emits typed `STRATUM_UNDER_POPULATED` (reusing the
  `terse_dataset` constant). Unified `AB_REPORT_OUTCOMES` taxonomy = 5 verdicts + under-powered-stop
  + stratum-under-populated. Headline is the per-stratum lines, never a whole-set average.
- **AC5 [unit] — MET.** `ab_power_precheck` / `run_precheck` load the committed 0036 pilot ledger
  and fixture reachability tags archive-first, compute the explicit upper bound, project degrade
  asymmetry (honest warning about unavailable per-turn artifacts), and return typed
  `PROCEED` / `UNDER_POWERED_STOP` that GATES the run.
- **AC6 [integration] — MET on the GATED branch.** The committed `run_thinking_ab.sh` ran LIVE
  (gate first → exit 2 typed stop, distinct from infra exit 1), under strict
  `HARPYJA_REQUIRE_LIVE_STACK` posture on the PROCEED path. `run_ab_paired` (precheck-gated, NO
  force/bypass parameter, full PROCEED branch implemented) + `AbLedger` (resumable per-cell,
  keyed to the config hash) + `ab_preflight` (STOP-AND-WARN on an unserved pinned tag) +
  `seed_honoring_probe` are all built; the integration test asserts the paired run is
  N/A-on-branch and the stop is the deliverable. PROCEED branch = built-not-exercised (N/A-on-branch).
- **AC7 [integration] — MET.** `claim.json` (schema `0039/1`) committed with the typed
  `UNDER_POWERED_STOP` + precheck detail, split by reachability, test-pinned to computed truth via
  `load_committed_ab_claim` (archive-first). No whole-set average is the headline.
- **AC8 [doc] — MET.** `findings.md` states the causation stance: think-experiment N=2 is
  motivation-only; UNDER_POWERED is typed, NOT a null (no claim thinking helps or hurts); NO
  default flip (`explorer_think=None` stays shipped); the observational True arm was not run.

## Deviations

- **(a) `classify_pair_validity` landed in T4, not T6.** T3's totality sweep required CONFOUNDED to
  be reachable, so T5's tests pinned behavior rather than starting fully red (two arrived red on the
  missing import). The factor-b misfire guard forced adding `factor_b_min_on_reasoning_chars` to the
  frozen config pre-commit, under freeze-before-run.
- **(b) The explorer request path carries NO `seed` param** (only `max_tokens` / `reasoning_effort`).
  Wiring `seed` into `ExplorerBackend` is a SUT change deferred to the re-run spec; the config's
  `seed_honoring="unverified"` claim stands (the 0037 never-false-provenance lesson), recorded in
  findings.md.
- **(c) The live paired arms are N/A-on-branch** (gated by the committed-evidence stop); the
  observational True arm was NOT run.

## Files touched (all new, untracked working-tree; started_at_sha == HEAD ee08532)

- `harpyja/eval/think_ab.py` — frozen config, `AbVerdict`, `PairRecord`, `decide_ab_verdict`,
  `classify_pair_validity`, `decide_ab_report`, `AbReport`, `located_via_oracle` (T18 one-oracle home)
- `harpyja/eval/think_ab_precheck.py` — `ab_power_precheck` / `run_precheck`, archive-first loaders
- `harpyja/eval/think_ab_run.py` — `AbLedger`, `ab_preflight`, `seed_honoring_probe`,
  `require_live_stack`, `run_ab_paired`
- `harpyja/eval/think_ab_claim.py` — `load_committed_ab_claim` (archive-first)
- `harpyja/eval/test_think_ab.py`, `test_think_ab_precheck.py`, `test_think_ab_run.py`,
  `test_think_ab_integration.py`, `test_think_ab_claim.py`
- `specs/0039-thinking-ab/run_thinking_ab.sh` — committed STOP-AND-WARN, resumable, strict driver
- `specs/0039-thinking-ab/claim.json` — schema `0039/1`, `UNDER_POWERED_STOP`, test-pinned
- `specs/0039-thinking-ab/findings.md` — AC8 causation stance
- `specs/0039-thinking-ab/{spec,plan,tasks,review}.md`

## Machinery reuse (one-oracle discipline)

- `is_signal_discordant` + `PilotPair` from `ac8_pilot` (identity-asserted in tests)
- `mcnemar_rejects` + `MIN_DISCORDANT_PAIRS` + `min_n` from `benchmark_fit` (identity-asserted)
- `STRATUM_UNDER_POPULATED` from `terse_dataset`
- `require_live_stack` from `locate_probe` (identity-asserted)
- `located_via_oracle` consolidated as the one located-predicate home (T18 refactor)

## Verification

- Spec tests: 37 passed (incl. the integration test asserting the gated branch on committed evidence).
- Full unit suite: 1280 passed / 1 skipped (the standing superseded-0037 conditional) / 58 deselected.
- Ruff: zero-new (36 = 36 vs main baseline).
- Driver `run_thinking_ab.sh` executed live: typed stop, exit 2, no arm fired.

## Named blocking follow-up

The 0036 pool-enlargement audited convert step — enlarge the blind-clean pool past 19 (the 50-case
raw pool is exhausted), THEN re-run this spec's pre-check. The PROCEED branch (runner, ledger, driver,
split report) is built and auto-activates when the committed evidence flips the gate. Standing
carry-forwards unchanged (the model bake-off, the semantic-tier decision, the total-request
wall-clock deadline, revisit `explorer_max_tokens=2048`).

## ADR proposed for history.md

See the memory-keeper close return (2026-07-10 — Spec 0039).

## Conventions proposed

See the memory-keeper close return: (1) projection epistemic-kind labeling
(upper-bound-feasibility vs power-estimate); (2) the deliberately-asymmetric two-factor per-pair
arm-distinctness validity guard; (3) no force/bypass parameter on a cost-prevention gate.
The precheck-gates-the-expensive-run pattern itself is already covered by the spec-0026 pilot
power-gate convention (applied here on committed evidence rather than a fresh pilot).
