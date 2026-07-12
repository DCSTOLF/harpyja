---
id: "0040"
spec: "0040"
---

# Tasks

- [x] T1 — [RED] config + hash tests: three tags, three pairs, per-pair-α stance, pinned pilot IDs, derived coverage min, distinct epistemic labels, floor reuse (AC1)
- [x] T2 — [GREEN] implement `PREREGISTERED_POOL_CONFIG_0040` + `POOL_CONFIG_HASH_0040`, multiplicity/asymmetry/staging in docstring (AC1)
- [x] T3 — [RED] preflight enum + precedence + tie-break (both-fail→COHERENCE_FAIL) + indeterminate→NOOP + asymmetry (AC2)
- [x] T4 — [GREEN] implement `PreflightOutcome` / `PREFLIGHT_PRECEDENCE` / `adjudicate_preflight` / `is_excluding` (AC2)
- [x] T5 — [RED] two per-pair quantities from per-case pairs: oracle-identity reuse, floor reuse, marginal-counts trap, ceiling-distinct-from-estimate (AC5)
- [x] T6 — [GREEN] implement `build_pair_cases` / `union_located_ceiling` (true bound) / `observed_discordance` (point estimate) (AC5)
- [x] T7 — [RED] derived coverage minimum boundary fixtures c=7 fires / c=8 clears (AC7)
- [x] T8 — [GREEN] implement `pilot_conceptual_coverage` / `coverage_below_minimum` (AC7)
- [x] T9 — [RED] total 5-member per-pair verdict + frozen predicate order + TOO_CLOSE≠UNDER_POWERED + MODEL_EXCLUDED voids-all + `decide_pool_fork` over 3 pairs (AC6)
- [x] T10 — [GREEN] implement `PairVerdict` / `decide_pair_verdict` / `decide_pool_fork` (AC6)
- [x] T11 — [RED] committed per-model preflight-result contract: schema/validate/all-three-typed/archive-first loader (AC3)
- [x] T12 — [GREEN] implement `pool_preflight_result.py` (`0040/preflight/1`, loud validator, archive-first) (AC3)
- [x] T13 — [RED][LIVE] live three-model preflight integration (skip-not-fail), each model typed, 14b re-confirmed (AC3)
- [x] T14 — [GREEN][LIVE] implement `run_model_preflight` + commit `preflight/run_preflight.py` + `preflight_result.json`, pin the committed artifact (AC3) — LIVE RUN DONE: all 3 PASS, all honor reasoning_effort
- [x] T15 — [RED] resumable `case::model` pilot ledger + STOP-AND-WARN driver preflight + strict skip→hard-fail (AC4)
- [x] T16 — [GREEN] implement `PoolPilotLedger` (`0040/pilot/1`) + `pool_pilot_preflight` behind `require_live_stack` (AC4)
- [x] T17 — [RED][LIVE] live three-model pilot at `explorer_think=None`, per-case buckets + conceptual locate-count, resumable (AC4) — LIVE RUN DONE 33/33 (run 1 invalidated outcome-blind: contaminated environment; clean re-run committed)
- [x] T18 — [GREEN][LIVE] implement `run_pool_pilot` + commit `pilot/run_pilot.py` + `pilot_results.json` (AC4) — added bounded degrade re-run + `_evict_other_models` (pinned-resident lesson)
- [x] T19 — [RED] committed fork matches computed `decide_pool_fork`, archive-first pin, non-feasible pairs name pool enlargement (AC8)
- [x] T20 — [GREEN] implement `load_committed_pool_fork` + emit `pool_fork.json` pinned to computed truth (AC8) — all 3 pairs INSUFFICIENT_PILOT_EVIDENCE
- [x] T21 — [DOC] `findings.md` — the overall fork (FEASIBLE vs enlargement branch unblocking 0039), sampling caveat, no bake-off compute spent (AC8)
- [x] T22 — [REFACTOR] evaluated and DECLINED with reason: each consolidation (shared archive-first resolver, ledger base, extrapolation helper) would edit committed 0039/0038 drift-pinned evidence modules; 0040 already routes the oracle by identity (`is_signal_discordant`/`located_via_oracle` imports, test-asserted) — no re-derivation exists to consolidate
