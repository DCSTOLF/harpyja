---
spec: "0040"
closed: 2026-07-11
---

# Changelog — 0040 pool

## What shipped vs spec

All measurement machinery, ZERO SUT change (10 new files in `harpyja/eval/` +
the committed `specs/0040-pool/` artifacts). The spec is a three-model
preflight + pilot + per-pair power pre-check that decides, per pair, whether the
bake-off runs on the current 19-case set or needs pool enlargement — cheaply,
before any live bake-off compute.

**Frozen config first (AC1).** `PREREGISTERED_POOL_CONFIG_0040` +
`POOL_CONFIG_HASH_0040` committed and hashed BEFORE any live evidence: three
model tags (`qwen3:14b` anchor / `qwen3:8b` / `qwen3.5:4b`), three named pairs,
floor 8 copied verbatim from `benchmark_fit.MIN_DISCORDANT_PAIRS`
(identity-asserted), multiplicity frozen outcome-blind as **per-pair-α,
uncorrected** with its decision-theoretic rationale, an 11-case pinned pilot set
(0036 first-10 + `django__django-14315`, the next conceptual in fixture order,
reaching the coverage minimum), `MIN_PILOT_CONCEPTUAL_COVERAGE=8` **DERIVED**
(the `15 − c < 8` vacuity boundary), two epistemically-labeled quantities,
preflight precedence, pair-verdict predicate order, arm-parity pin
`explorer_think=None`, staging order. Every verdict is a total pure function
over the frozen object.

**Preflight enum (AC2).** `PreflightOutcome` (5 members) with committed
precedence `UNSERVABLE > COHERENCE_FAIL > TOOL_CALL_MALFORMED >
THINK_CONTROL_NOOP > PASS`; an indeterminate think-probe → `THINK_CONTROL_NOOP`.
The asymmetry is DELIBERATE and load-bearing: `THINK_CONTROL_NOOP` is
recorded-non-excluding, the three fundamental failures exclude. Validation
enforces that an excluding outcome carries an `exclusion_reason` and a
non-excluding one does not.

**Two per-pair quantities from retained per-case pairs (AC5).** Never marginal
counts: the union-located CEILING (a true bound —
`projection_kind="upper-bound-feasibility"`, gates `PAIR_UNDER_POWERED`) vs the
observed signal-discordance via `is_signal_discordant`
(`estimate_kind="point-estimate"`, splits `TOO_CLOSE`/`FEASIBLE`). Fixtures pin
the marginal-counts trap (counts-identical/overlap-different scenarios diverge)
and that the ceiling is neither vacuous nor equal to the estimate.

**Total 5-member `PairVerdict` (AC6)** in frozen order `MODEL_EXCLUDED >
INSUFFICIENT > UNDER_POWERED > TOO_CLOSE > FEASIBLE`; an anchor (14b) preflight
failure voids ALL three pairs (harness-integrity signal); `decide_pool_fork` is
total over the three pairs.

**Contracts + committed evidence (AC3/AC4/AC8).** `pool_preflight_result.py`
(schema `0040/preflight/1`) and `pool_fork.py` (`0040/fork/1`), both
archive-first loaders with committed artifacts test-pinned to computed truth.
`PoolPilotLedger` (`0040/pilot/1`, `case::model`, resumable, config-hash-keyed)
with a bounded degrade re-run (`_cell_needs_run`: clean cells NEVER re-run;
typed degrades get exactly one re-run) and `_evict_other_models`; committed
operator drivers `preflight/run_preflight.py` and `pilot/run_pilot.py`
(STOP-AND-WARN, exit 3 while work remains).

## Live results (committed)

**PREFLIGHT** — all three models `PREFLIGHT_PASS`; ALL THREE honor
`reasoning_effort` on Ollama 0.31.1 `/v1` (OQ1 answered live: the newer qwen3.5
generation honors it — probed under the 0038 tiny-cap two-factor discriminator,
not assumed). All three are eligible as future thinking-arms. Side-note:
`qwen3:8b` servable + preflight-clean is the first live evidence bearing on the
unservable `hf.co/Qwen/Qwen3-8B-GGUF:latest` default `lm_model` placeholder's
size class.

**PILOT** — 33/33 cells at `explorer_think=None`. Conceptual locate-counts
(power inputs, NOT a ranking): 14b 3/7, 8b 0/8, 4b 1/5. Located sets nearly
nested (4b ⊂ 14b; 8b conceptual empty) → low discordance. `symbols`-tool
adoption 0/28 clean cells across all models (a standing observation).

**FORK** — ALL THREE pairs `INSUFFICIENT_PILOT_EVIDENCE` (coverage 7/4/5 vs
derived min 8, from 5 persistent per-case model-unreachable degrades at the
attempt cap); even ignoring coverage the ceilings are 6/8/3 vs floor 8 (the 0039
stop shape). NO bake-off runs on the current 19-case set; the named next step
for all pairs is pool enlargement (the 0036 audited convert step), which also
unblocks the 0039 thinking A/B. No bake-off compute spent.

## Run-integrity episode (durable lesson)

Run 1 of the pilot was CONTAMINATED: (a) a concurrent pytest suite launched
without `-m "not integration"`, so its live integration tests QUEUED requests on
the same Ollama and touched other model tags; (b) the dev Ollama pins models
with infinite keep-alive (`expires_at` ~2318), so `qwen3:8b` + `qwen3.5:4b` sat
permanently resident (14.3 GB) squeezing every `qwen3:14b` cell on the 32 GB
box. Effects: wall-clock expiries recorded as honest `empty` buckets (14b
collapsed to 0 located vs 0036's 5/10 on the same cases) and HTTP timeouts typed
`model-unreachable`. Queueing and pinning are not competing explanations — suite
traffic touching other tags is what pins them.

Remediation was OUTCOME-BLIND AT RUN GRANULARITY: the whole run was invalidated
(criterion "recorded during the contaminated environment", never "cells whose
outcome looks wrong"), archived as `pilot/pilot_results.run1-contaminated.json`,
and re-run fresh with per-block eviction. The clean re-run restored 14b to its
0036 profile — validating the diagnosis. Clean cells are NEVER re-run on
suspicion (post-hoc steering); typed degrades get one bounded re-run (0036
posture).

## Deviations

- (a) The preflight driver was committed as `preflight/run_preflight.py`
  (Python, the 0036 posture), not `run_preflight.sh`.
- (b) T15's RED collapsed — the ledger landed inside T14's module; the pin-tests
  were written after.
- (c) The bounded degrade re-run + `_evict_other_models` machinery was added
  mid-implementation (not in the original plan) in response to the run-integrity
  episode.
- (d) T22 (REFACTOR) was evaluated and DECLINED with a recorded reason: each
  candidate consolidation would edit committed, drift-pinned 0039/0038 evidence
  modules; 0040 already routes the oracle by identity
  (`is_signal_discordant`/`located_via_oracle` imports, test-asserted), so no
  re-derivation exists to consolidate.
- (e) Two spec-review rounds — round 2's headline fix (the ceiling-conflation:
  extrapolated observed discordance is an estimate, not a bound; a literal
  max-bound is vacuous; resolved by the two-quantity split) landed pre-plan.

Suite: 1320 passed / 1 skipped / 60 deselected; ruff 41 = 41 (zero new).

## Files touched

New machinery (`harpyja/eval/`):
- `pool_precheck.py` — frozen config + hash, preflight enum + precedence, the
  two per-pair quantities, `PairVerdict` + `decide_pair_verdict` +
  `decide_pool_fork`, coverage-minimum predicate.
- `pool_preflight_result.py` — schema `0040/preflight/1` contract + loud
  validator + archive-first loader.
- `pool_pilot.py` — `run_model_preflight`, `PoolPilotLedger`,
  `pool_pilot_preflight`, `run_pool_pilot`, bounded degrade re-run,
  `_evict_other_models`.
- `pool_fork.py` — schema `0040/fork/1` claim loader + emitter.
- `test_pool_precheck.py`, `test_pool_preflight_result.py`, `test_pool_fork.py`
  (unit); `test_pool_pilot.py`, `test_pool_preflight_integration.py`,
  `test_pool_pilot_integration.py` (integration, skip-not-fail).

Committed evidence (`specs/0040-pool/`):
- `preflight/run_preflight.py`, `preflight/preflight_result.json`
- `pilot/run_pilot.py`, `pilot/pilot_results.json`, `pilot/driver.log`
- `pilot/pilot_results.run1-contaminated.json`,
  `pilot/driver.run1-contaminated.log` (the invalidated first run, retained)
- `pool_fork.json`, `findings.md`

## ADR proposed for history.md

2026-07-11 — Spec 0040 (pool): three-model preflight + pilot + per-pair power
pre-check; all three preflight-PASS and honor `reasoning_effort`, all three
pairs `INSUFFICIENT_PILOT_EVIDENCE`, no bake-off compute spent; the
run-integrity contamination episode invalidated outcome-blind at run
granularity. (Full entry prepended to history.md.)

## Conventions proposed

- New: an exclusive-endpoint precondition for live-measurement drivers (foreign
  pinned residents + concurrent live-calling workloads silently convert
  environment latency into fake capability observations; invalidate a
  contaminated run outcome-blind at RUN granularity, never per-suspicious-cell).
- New: pin coverage HEADROOM above a derived pre-check minimum (a boundary-exact
  pilot set forces `INSUFFICIENT` on any single environment degrade).
- New: the two-quantity ceiling-vs-estimate split as the general resolution of
  the extrapolate-a-bound-vs-estimate conflation when direct per-case cross-arm
  pairs exist.
- Extended: the multi-model preflight enum with committed precedence and a
  load-bearing EXCLUDING-vs-RECORDED-NON-EXCLUDING asymmetry (the 0037/0038
  serving-is-version-specific lesson, re-probed per model).
