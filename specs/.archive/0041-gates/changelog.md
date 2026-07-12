---
spec: "0041"
closed: 2026-07-12
---

# Changelog — 0041 gates

## What shipped vs spec

Measurement-hygiene gates that make the 0040 run-1 contamination class structurally
impossible before the enlargement/bake-off spends hours of live compute on it. ALL
machinery + operator drivers + committed live evidence, ZERO SUT change (the 0034/0038
byte-identical `explorer_think=None ⇒ params == {max_tokens: 2048}` pin survives
verbatim, regression-asserted). Four invariants delivered: refuse-don't-bypass;
exclusivity recorded at actual strength with two named unseeable residuals; sent ≠
honored probe-first for the hygiene knob itself; safe-by-default tests with an enforced
consumer; hygiene-only (SUT byte-frozen).

New prod/operator modules (all operator-side, `harpyja/eval/`):
- `exclusivity_gate.py` — `0041/exclusivity/1` contract: `foreign_residents` PINNED
  predicate (resident tag not in the frozen config's model set — the driver's own block
  loads never self-trigger), `build_exclusivity_record` / `validate_exclusivity_record`,
  `check_exclusive_endpoint` routing `/api/ps` behind `gateway.assert_local` FIRST (0019
  rule), `EXCLUSIVITY_CHECK_KIND="start-plus-per-block"`,
  `EXCLUSIVITY_UNSEEABLE_RESIDUALS=("intra-block-window","same-tag-contention")`, and the
  typed stop `ExclusiveEndpointContended` (`exclusive-endpoint-contended`) with
  `as_failed_check()` so the refusal is auditable.
- `gate_run.py` — `run_gated_pool_pilot` (start + per-block gate, boundary-suspect typing,
  no force/bypass signature), `mark_cells_suspect_since_last_clean`,
  `attribute_reload_churn` (the two-condition AC8 predicate: NEW-vs-committed-0040-profile
  AND an `expires_at`-reset marker), `clean_0040_degrade_profile` (archive-first loader).
- `residency_probe.py` — `0041/residency-probe/1`, `judge_residency_outcome` from
  `/api/ps` `expires_at` movement ONLY, self-consistency re-judging validator, archive-first
  loaders, `assert_residency_wiring_matches_committed_outcome` (loud-FAIL drift tripwire),
  `run_residency_probe` live procedure with a refuse-if-not-resident typed guard.
- `live_test_selection.py` — `assert_live_optin_selection`, the AC6 mechanical consumer.
- `pool_pilot.py` bump — `POOL_PILOT_LEDGER_SCHEMA_VERSION_0041="0041/pilot/2"`,
  version-gated optional `PoolPilotLedger(exclusivity=…)` + `set_exclusivity`, the suspect
  THIRD `_cell_needs_run` branch (re-runnable only after a subsequent clean gate check;
  clean never re-runs; typed degrades keep one bounded re-run); legacy `0040/pilot/1`
  write/read byte-unchanged.
- `pyproject.toml` — `addopts = ["-m", "not integration"]` (live tests OPT-IN by default).

Committed live evidence under `specs/0041-gates/`:
- `residency_probe/probe_result.json` — LIVE outcome **touch-rebounds** (expires_at
  2318→now+300 s on `qwen3-14b-cc:latest`, Ollama `/api/generate` bounded touch honored);
  `residency_probe/run_residency_probe.py` (operator driver, exit 0/2).
- `gate/run_gate.py` (operator driver: AC6 consumer preflight → probe-first residency gate
  → gate-proof pass, exit 0/2); `gate/gate_proof.json` (LIVE exclusive endpoint → PASS, 4
  clean checks: start + 3 pre-block); `gate/gate_proof.contended.json` (LIVE contended
  endpoint `qwen3-14b-cc` foreign → typed stop `exclusive-endpoint-contended`, exit 2,
  zero cells).

## Acceptance criteria — all 9 met

1. AC1 [unit] MET — exclusive-endpoint preflight refuses on a foreign resident with the
   typed stop `exclusive-endpoint-contended`, non-zero exit, zero cells; no bypass/force
   parameter (signature-introspection pinned, 0039 precedent); the driver's own configured
   models never trigger the predicate; `exclusivity_check_kind` semantics name the two
   unseeable residuals. (`test_exclusivity_gate.py` ×8, `test_gate_run.py`.)
2. AC2 [unit] MET — mid-run contention stops BEFORE block N; contamination boundary
   (failed check + timestamp) recorded; cells since the last clean check typed suspect;
   1..N−2 valid under their own clean checks; outcome-blind; suspect resumes per the third
   `_cell_needs_run` branch (invalidate-and-archive, re-run only after a clean check).
   (`test_gate_run.py`, `test_pool_pilot.py` suspect-branch test.)
3. AC3 [unit] MET — the ledger bump is additive + version-gated: `0041/pilot/2` REQUIRES
   the full exclusivity record and the validator rejects a new-version artifact lacking it;
   legacy `0040/pilot/1` validates unchanged (both directions). (`test_pool_pilot.py` ×3.)
4. AC4 [unit] MET — residency probe emits `{touch-rebounds, touch-ignored}`; honoring
   judged ONLY from `/api/ps` `expires_at` movement; loud-FAIL wiring↔committed-outcome
   tripwire; `_evict_other_models` retained defense-in-depth (regression-pinned).
   (`test_residency_probe.py` ×7, `test_pool_pilot.py` evict-regression pin.)
5. AC5 [unit] MET — SUT-boundary guards: explorer `{max_tokens: 2048}` byte-identical pin
   survives verbatim (0034/0038), Deep outbound carries no new field, and an ast confinement
   sweep confines `keep_alive`/`/api/ps` to the driver/native-API seam.
   (`test_explorer_backend.py`, `test_rlm.py`, `test_sut_boundary_residency.py`.)
6. AC6 [unit/config] MET — the committed default deselects live integration tests; a test
   asserts zero live-marked in the default and non-zero under opt-in; the opt-in has the
   named executable consumer `assert_live_optin_selection` running `pytest --collect-only`
   (mechanical, not documentation-only). (`test_deselect_default.py` ×3.)
7. AC7 [integration] MET (LIVE) — the committed residency-probe driver ran against the real
   endpoint and recorded the typed outcome **touch-rebounds**; skip-not-fail without the
   live stack via `require_live_stack`. (`test_residency_probe_integration.py`.)
8. AC8 [integration] MET (LIVE) — a run on an exclusive endpoint PASSED the gate with the
   full recorded proof; a run on a deliberately-contended endpoint STOPPED with the typed
   stop; reload-churn attribution operationalized as the two-condition predicate.
   (`test_gate_run_integration.py` ×3, `gate_proof.json` + `.contended.json`.)
9. AC9 [doc] MET — the 0040 run-1 contamination recorded as the motivating incident;
   conventions + architecture updated (hard gate, opt-in live tests + named consumer,
   driver-scoped probe-proven residency); the 0040 run-granularity invalidation convention
   explicitly AMENDED (boundary-granularity when per-check records exist, run-granularity
   when they don't — same outcome-blind criterion). (`.speccraft/conventions.md`,
   `.speccraft/architecture.md`, this changelog, `history.md`.)

## Live verification

Both gate legs and the probe ran in-session against real endpoint states fabricated ONLY
by evict/re-pin of the resident foreign tag `qwen3-14b-cc:latest`: exclusive state (pass
leg + churn-inputs test passed, contended skipped) and contended state (contended leg +
probe test passed, exclusive skipped). The operator's pinned model (`qwen3-14b-cc`,
`keep_alive=-1`) was restored to its 2318 pin after each touch (verified).

## Deviations

(a) T3/T4 collapsed into T2 — `check_exclusive_endpoint` shipped inside the contract
    module's GREEN; T3's tests landed as pins-after (the 0040 T15 shape).
(b) `run_gate.py` is a gate-proof pass (`cases=[]`) — the enlargement/bake-off specs pass
    their own `run_cell` through `run_gated_pool_pilot`; the full gated cell loop is not
    this spec's deliverable.
(c) The T18/T19 live legs ran IN-SESSION (not deferred to the operator): the probe touched
    the resident foreign tag `qwen3-14b-cc:latest` and both gate legs ran against real
    endpoint states fabricated only by evict/re-pin of that tag; the `keep_alive=-1` pin was
    restored afterward (2318 expiry verified).
(d) `run_residency_probe` gained a refuse-if-not-resident typed guard mid-T19 when the
    idle-endpoint edge surfaced live; the probe integration test SKIPS (not fails) on an idle
    endpoint because it fabricates no traffic.
(e) AC8's live churn leg validated the attribution INPUTS (committed 0040 clean profile = 5
    degrades; predicate pure-tested); the predicate first BITES on the next real gated cell run.
(f) T21 REFACTOR DECLINED with recorded reason (0040 T22 precedent — consolidating the three
    `/api/ps` readers would edit the drift-pinned committed 0040 evidence module `pool_pilot.py`
    or force the two callers' divergent projections through one indirection; the ast confinement
    guard already pins the seam by identity).
(g) AC5's spec text named three sanctioned seam modules; `exclusivity_gate.py` is the FOURTH
    (it reads `/api/ps` for the gate itself) — the ast sweep's allowed set records all four.

## Files touched

- `harpyja/eval/exclusivity_gate.py` (new) + `test_exclusivity_gate.py` (new, 8)
- `harpyja/eval/gate_run.py` (new) + `test_gate_run.py` (new, 7) + `test_gate_run_integration.py` (new, 3)
- `harpyja/eval/residency_probe.py` (new) + `test_residency_probe.py` (new, 7) + `test_residency_probe_integration.py` (new)
- `harpyja/eval/live_test_selection.py` (new) + `test_deselect_default.py` (new, 3)
- `harpyja/eval/test_sut_boundary_residency.py` (new, ast confinement sweep)
- `harpyja/eval/pool_pilot.py` (+83) + `harpyja/eval/test_pool_pilot.py` (+156)
- `harpyja/scout/test_explorer_backend.py` (+28) + `harpyja/deep/test_rlm.py` (+9)
- `pyproject.toml` (+5)
- `specs/0041-gates/residency_probe/` (probe_result.json, run_residency_probe.py)
- `specs/0041-gates/gate/` (run_gate.py, gate_proof.json, gate_proof.contended.json)
- `.speccraft/architecture.md` (+52, T20), `.speccraft/conventions.md` (+63, T20),
  `.speccraft/history.md` (this close), `.speccraft/index.md`

## Suite / ruff

1353 passed / 1 skipped (the 0037-superseded conditional) / 64 deselected (integration, now
BY DEFAULT) / ruff 36 = 36 zero-new.

## ADR proposed for history.md

Prepended as the 0041 entry (see `.speccraft/history.md`).

## Conventions proposed

All three 0041 convention bullets + the 0040-bullet amendment were authored during T20 and
verified coherent at close — no new proposals, no duplication. (`.speccraft/conventions.md`
lines ~854–940.)

## Architecture updates

The "## Spec 0041 architecture updates" section was appended during T20 and verified at
close — no new proposals. (`.speccraft/architecture.md` lines ~1022–1073.)

## Follow-ups (recorded, not this spec)

- Pool enlargement (the standing 0040/0039 unblock) now runs through `run_gated_pool_pilot`
  with its committed proof.
- The 5 persistent heavy-repo degrades remain a separate spec's diagnosis.
- OQ1 residency bound value (300 s at probe time) is pinned by the consuming run spec's
  frozen config.
- OQ2 (scaffold frontmatter drift: 0040/scaffold emit `authors`/`packages`/`related-specs`
  and omit `started_at_sha` vs the canonical convention — 0041 followed the convention
  manually) — a conventions-maintenance follow-up.
