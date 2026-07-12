---
spec: "0041"
status: planned
strategy: tdd
---

# Plan — 0041 gates

Measurement-hygiene gates: an exclusive-endpoint gate (start + per-block, recorded at
its actual strength), driver-scoped bounded residency proven probe-first, and opt-in live
tests with an enforced consumer. Every deliverable is measurement/driver/config/test —
the production `ModelGateway` request body and both model tiers stay byte-frozen.

## Approach & ordering rationale

Contracts before mechanism, mechanism before wiring, wiring before config, config before
live drivers, live drivers before doc — the 0038/0040 order. Concretely:

1. **Typed contracts first (their own modules, own schema versions).** The exclusivity
   record (`0041/exclusivity/1`) and the residency probe (`0041/residency-probe/1`) are
   committed, validated, loud-rejecting shapes BEFORE any live call touches them — the
   0038 probe-first discipline (`reconcile_probe.py` is the mirror). Schema ids follow the
   0040 precedent (`0040/preflight/1`, `0040/pilot/1`); the pilot ledger bumps
   `0040/pilot/1 → 0041/pilot/2` additively.
2. **Predicates and pure helpers next** (`foreign_residents`, `_cell_needs_run` suspect
   branch, `attribute_reload_churn`, `judge_residency_outcome`) — each a pure function
   with a unit RED→GREEN, so the driver wiring assembles proven parts.
3. **Driver wiring** (`run_gated_pool_pilot`) integrates start-gate refusal, per-block
   re-check + boundary suspect typing, and the exclusivity log into the `0041/pilot/2`
   ledger — no-bypass pinned by signature introspection (the 0039 `run_ab_paired`
   precedent).
4. **Config gate** (`addopts = -m "not integration"`) + its enforced executable consumer
   (a `pytest --collect-only` assertion) — safe-by-default, opt-in with a named consumer.
5. **SUT-boundary regression guards** re-assert the 0034/0038 byte-identical explorer pin
   and the Deep no-new-field pin survive verbatim, plus a new ast guard confining the
   `keep_alive`/`/api/ps` residency mechanism to the driver/native-API seam.
6. **Live integration** (residency probe run; gate run on exclusive vs contended
   endpoint) — skip-not-fail via `require_live_stack`.
7. **Doc last** — the 0040 run-1 incident + the four convention amendments.

The frozen-config-constants-before-any-live-call rule holds: all schema versions,
`EXCLUSIVITY_CHECK_KIND`, the two named residuals, the residency bound value, and the
forbidden-bypass-parameter set are module constants defined in the GREEN steps that
precede every live driver.

## File map

New:
- `harpyja/eval/exclusivity_gate.py` — `0041/exclusivity/1`; `foreign_residents`,
  `check_exclusive_endpoint` (behind `gateway.assert_local`), `ExclusiveEndpointContended`
  typed stop, `validate_exclusivity_record`, `EXCLUSIVITY_CHECK_KIND`,
  `EXCLUSIVITY_UNSEEABLE_RESIDUALS`.
- `harpyja/eval/test_exclusivity_gate.py`
- `harpyja/eval/gate_run.py` — `run_gated_pool_pilot` (start + per-block gate, suspect
  typing, writes the `0041/pilot/2` exclusivity log; no force/bypass param),
  `attribute_reload_churn`.
- `harpyja/eval/test_gate_run.py`
- `harpyja/eval/residency_probe.py` — `0041/residency-probe/1`; outcomes
  `{touch-rebounds, touch-ignored}`, `judge_residency_outcome` (expires_at movement only),
  `assert_residency_wiring_matches_committed_outcome` (loud-fail tripwire), loaders
  (archive-first), `run_residency_probe`.
- `harpyja/eval/test_residency_probe.py`
- `harpyja/eval/live_test_selection.py` — `assert_live_optin_selection` (the AC6 enforced
  consumer: `pytest --collect-only` asserting non-zero live-marked under opt-in / zero
  under default).
- `harpyja/eval/test_deselect_default.py`
- `harpyja/eval/test_sut_boundary_residency.py` — AC5 confinement ast guard.
- `harpyja/eval/test_residency_probe_integration.py`, `test_gate_run_integration.py`
- `specs/0041-gates/residency_probe/run_residency_probe.py` — operator driver (exit-code
  posture per 0040; refuses without `live=True`).
- `specs/0041-gates/gate/run_gate.py` — operator driver (start/per-block gate;
  `exclusive-endpoint-contended` → non-zero exit, zero cells).

Modified:
- `harpyja/eval/pool_pilot.py` — add `POOL_PILOT_LEDGER_SCHEMA_VERSION_0041 =
  "0041/pilot/2"`, optional `PoolPilotLedger(exclusivity=…)` (version-gated: new version
  REQUIRES the record, legacy `0040/pilot/1` validates unchanged), `_cell_needs_run`
  suspect third branch.
- `harpyja/eval/test_pool_pilot.py` — AC3 + AC2 extensions.
- `pyproject.toml` — `[tool.pytest.ini_options] addopts = ["-m", "not integration"]`.
- `harpyja/scout/test_explorer_backend.py`, `harpyja/deep/test_rlm.py` — re-assert the
  byte-identical / no-new-field pins survive (AC5).
- `.speccraft/conventions.md`, `.speccraft/architecture.md`, `history.md` — AC9.

## Test-first sequence

### Step 1 — Exclusivity contract + foreign-resident predicate (RED)
- Add `harpyja/eval/test_exclusivity_gate.py`:
  - `test_exclusivity_schema_version_is_0041_exclusivity_1`
  - `test_exclusivity_check_kind_is_start_plus_per_block`
  - `test_exclusivity_record_names_two_unseeable_residuals` — the record carries exactly
    `("intra-block-window", "same-tag-contention")`.
  - `test_foreign_residents_flags_only_tags_outside_frozen_model_set` — a resident tag not
    in the frozen model set is foreign; every configured model is never foreign.
  - `test_validate_exclusivity_record_rejects_missing_checks_or_model_set_or_kind`
- Fails: module `harpyja.eval.exclusivity_gate` does not exist.

### Step 2 — Exclusivity contract impl (GREEN)
- Implement `harpyja/eval/exclusivity_gate.py`: constants, `foreign_residents`,
  `build_exclusivity_record`, `validate_exclusivity_record`, `ExclusivityError`.
- All step-1 tests pass.

### Step 3 — `check_exclusive_endpoint`: assert_local routing + typed stop (RED)
- Extend `test_exclusivity_gate.py`:
  - `test_check_exclusive_endpoint_routes_through_assert_local_first` — a non-loopback
    `api_base` raises `AirGapError` before the injected `/api/ps` reader is called.
  - `test_check_exclusive_endpoint_refuses_on_foreign_resident_typed_stop` — a fake
    `/api/ps` with a foreign tag → raises `ExclusiveEndpointContended`, stop id
    `exclusive-endpoint-contended`, naming the residual(s) it could not see.
  - `test_check_exclusive_endpoint_passes_on_configured_only_and_records_check` — only
    configured tags resident → returns a clean check record (result True + timestamp).
- Fails: `check_exclusive_endpoint` / `ExclusiveEndpointContended` not implemented.

### Step 4 — `check_exclusive_endpoint` impl (GREEN)
- Implement `check_exclusive_endpoint(api_base, model_set, *, ps_reader=None,
  resolver=None, now=None)`: `assert_local` first (the 0019 rule; `/api/ps` is the same
  loopback-gated class as `/api/tags`), read residents, compute `foreign_residents`, raise
  the typed stop or return the check record.
- All step-3 tests pass.

### Step 5 — Pilot ledger schema bump: additive + version-gated (RED)
- Extend `harpyja/eval/test_pool_pilot.py`:
  - `test_pool_ledger_0041_version_requires_exclusivity_record` — a `0041/pilot/2` obj
    lacking `exclusivity` → `PoolRunError`.
  - `test_pool_ledger_0041_version_accepts_full_exclusivity_record` — with every check +
    timestamp + `exclusivity_check_kind` + the frozen model set the predicate ran against,
    validates and round-trips at `0041/pilot/2`.
  - `test_pool_ledger_legacy_0040_version_still_validates_without_exclusivity` — a
    `0040/pilot/1` block loads unchanged (both directions).
- Fails: version constant + version-gated exclusivity requirement absent.

### Step 6 — Pilot ledger bump impl (GREEN)
- `pool_pilot.py`: add `POOL_PILOT_LEDGER_SCHEMA_VERSION_0041 = "0041/pilot/2"`, extend
  `_KNOWN_LEDGER_SCHEMA_VERSIONS`, add optional `exclusivity` to `PoolPilotLedger` (writes
  `0041/pilot/2` + requires the record when provided; writes/reads `0040/pilot/1`
  unchanged when absent — existing 0040 tests stay green).
- All step-5 tests pass.

### Step 7 — `_cell_needs_run` suspect third branch (RED)
- Extend `test_pool_pilot.py`:
  - `test_cell_needs_run_suspect_reruns_only_after_clean_gate_check` — a suspect cell is
    NOT re-runnable until a subsequent clean gate check; clean cells still never re-run;
    typed degrades still get exactly one bounded re-run.
- Fails: the suspect branch does not exist (`_cell_needs_run` has only clean/degrade).

### Step 8 — `_cell_needs_run` suspect branch impl (GREEN)
- `pool_pilot.py`: add the third branch — a `status == "suspect"` cell (invalidated +
  archived, the 0040 contaminated-run posture) becomes re-runnable only when a
  `clean_gate_since` flag is passed.
- All step-7 tests pass.

### Step 9 — Gated run driver: refuse-zero-cells, no-bypass, per-block boundary (RED)
- Add `harpyja/eval/test_gate_run.py`:
  - `test_gated_run_refuses_to_start_on_contended_endpoint_zero_cells` — a fake `/api/ps`
    showing a foreign resident → `run_gated_pool_pilot` raises the typed stop, the ledger
    records zero executed cells.
  - `test_gated_run_has_no_bypass_or_force_parameter` — signature introspection over
    `run_gated_pool_pilot` asserts none of `{force, bypass, allow_contended,
    skip_gate, ignore_contention}` exists (the 0039 `run_ab_paired` precedent).
  - `test_gated_run_mid_run_contention_stops_before_block_and_types_boundary_suspect` — a
    fake endpoint clean at start, foreign before block N: stops BEFORE block N, records the
    contamination boundary (failed check + timestamp), types block N−1's cells (all since
    the last clean check) suspect, blocks 1..N−2 stay valid under their own recorded clean
    checks — asserted outcome-blind on the flipping fake.
  - `test_gated_run_writes_full_exclusivity_log_at_0041_pilot_2` — the produced ledger is
    `0041/pilot/2` and its exclusivity record carries every check + timestamp + kind +
    model set.
- Fails: `harpyja.eval.gate_run` / `run_gated_pool_pilot` does not exist.

### Step 10 — Gated run driver impl (GREEN)
- Implement `gate_run.py::run_gated_pool_pilot`: start gate → per-model-block re-check →
  on failure stop-before-block + `mark_cells_suspect_since_last_clean` + record boundary;
  accumulate the exclusivity log and persist it via `PoolPilotLedger(exclusivity=…)` at
  `0041/pilot/2`; `live=False` refuses loudly (0040 posture); no force parameter.
- All step-9 tests pass.

### Step 11 — Residency probe contract + judge + wiring tripwire (RED)
- Add `harpyja/eval/test_residency_probe.py` (mirrors `test_reconcile_probe_result.py`):
  - `test_residency_probe_outcomes_are_the_two_typed_values` — exactly
    `{touch-rebounds, touch-ignored}`.
  - `test_residency_probe_schema_version_is_0041_residency_probe_1`
  - `test_judge_residency_outcome_reads_only_expires_at_movement` — outcome derived from
    `/api/ps` `expires_at` before/after, never from the sent request body.
  - `test_validate_residency_probe_result_rejects_missing_expires_at_evidence`
  - `test_assert_residency_wiring_matches_committed_outcome_fails_loud_on_drift` — a driver
    wired to native-touch while the committed outcome is `touch-ignored` (or vice versa)
    FAILS loudly, never skips (the 0038 posture).
  - `test_committed_residency_probe_loads_and_validates` (archive-first resolver).
- Fails: module `harpyja.eval.residency_probe` does not exist.

### Step 12 — Residency probe impl + `_evict_other_models` regression pin (GREEN)
- Implement `residency_probe.py`: constants, `judge_residency_outcome`,
  `validate_residency_probe_result`, loaders, `assert_residency_wiring_matches_committed_outcome`.
- Add `test_evict_other_models_retained_as_defense_in_depth` to `test_pool_pilot.py`
  (regression-pinning the native-API eviction seam survives).
- All step-11 tests pass.

### Step 13 — Reload-churn attribution pure function (RED)
- Extend `test_gate_run.py`:
  - `test_attribute_reload_churn_requires_new_degrade_and_expires_at_reset_marker` — a NEW
    typed-degrade counts as churn-attributable ONLY when an observed-reload marker
    (`expires_at` reset since the previous cell) is present; a degrade already in the 0040
    clean-run profile does not, and a new degrade without a marker does not.
- Fails: `attribute_reload_churn` not implemented.

### Step 14 — Reload-churn attribution impl (GREEN)
- Implement `gate_run.py::attribute_reload_churn(this_run_degrades, clean_0040_profile,
  reload_markers)`.
- All step-13 tests pass.

### Step 15 — SUT-boundary regression guards (REGRESSION, test-only)
- `harpyja/scout/test_explorer_backend.py`: re-assert `explorer_think=None ⇒ params ==
  {max_tokens: 2048}` (the 0034/0038 pin) survives verbatim under 0041 — reference the
  existing `test_default_outbound_request_body_pinned` and add
  `test_explorer_byte_identical_pin_survives_0041` if a distinct anchor is wanted.
- `harpyja/deep/test_rlm.py`: re-assert `test_deep_outbound_carries_no_reasoning_effort`
  et al. hold (Deep acquires no new field).
- Add `harpyja/eval/test_sut_boundary_residency.py`:
  - `test_keep_alive_and_api_ps_confined_to_driver_native_api_seam` — an `ast`-based sweep
    (the deletion-guard discipline, not a text grep) asserts `keep_alive` / `/api/ps`
    appear ONLY in `eval/pool_pilot.py`, `eval/gate_run.py`, `eval/residency_probe.py`,
    and NEVER in `gateway/`, `scout/`, `deep/`.
- Passes on introduction; rots false on any future SUT leak.

### Step 16 — Deselect default + enforced consumer (RED)
- Add `harpyja/eval/test_deselect_default.py`:
  - `test_pyproject_addopts_deselects_integration_by_default` — parse `pyproject.toml`,
    assert `addopts` applies the `-m "not integration"` deselect.
  - `test_marker_deselect_collects_zero_integration_and_optin_collects_them` — a subprocess
    `pytest --collect-only` over a written tmp test file (one `@pytest.mark.integration` +
    one plain) collects zero integration under `-m "not integration"` and non-zero under
    `-m integration` (mechanical).
  - `test_assert_live_optin_selection_is_the_enforced_consumer` — `assert_live_optin_selection`
    returns the non-zero opt-in count / zero default count, and raises when the default
    selection is non-empty of live-marked tests.
- Fails: no `addopts` yet; `live_test_selection` module absent.

### Step 17 — Deselect config + enforced-consumer impl (GREEN)
- `pyproject.toml`: `addopts = ["-m", "not integration"]`.
- Implement `harpyja/eval/live_test_selection.py::assert_live_optin_selection` (runs
  `pytest --collect-only` for both selections; the mechanical assertion, not doc-only).
- All step-16 tests pass; the full suite still collects (opt-in path `-m integration` for
  closure runs).

### Step 18 — Live residency-probe run (INTEGRATION, AC7)
- Add `specs/0041-gates/residency_probe/run_residency_probe.py` — operator driver, refuses
  without `live=True`, 0040 exit-code posture, writes the `0041/residency-probe/1` artifact.
- Add `harpyja/eval/test_residency_probe_integration.py`:
  - `test_committed_residency_probe_run_records_typed_outcome` — `@pytest.mark.integration`,
    skip-not-fail via `require_live_stack`, asserts the committed artifact carries one typed
    outcome judged from `expires_at` movement.

### Step 19 — Live gate run: exclusive passes, contended stops (INTEGRATION, AC8)
- Add `specs/0041-gates/gate/run_gate.py` — start + per-block gate; exclusive endpoint →
  passes and the ledger carries the full recorded proof; a deliberately-contended endpoint
  → `exclusive-endpoint-contended`, non-zero exit, zero cells.
- Add `harpyja/eval/test_gate_run_integration.py`:
  - `test_gate_run_on_exclusive_endpoint_records_proof` (skip-not-fail).
  - `test_gate_run_on_contended_endpoint_stops_typed` (skip-not-fail).
  - `test_reload_churn_attribution_against_0040_clean_profile` — on the touch-rebounds
    branch, per-case typed-degrade set compared vs the committed 0040 clean-run profile on
    shared pinned cases, with the `expires_at`-reset marker required.

### Step 20 — Docs + convention amendments (DOC, AC9)
- Record the 0040 run-1 contamination as the motivating incident (`history.md`) and amend
  `.speccraft/conventions.md` / `.speccraft/architecture.md`:
  - exclusive-endpoint is a hard gate (start + per-block, recorded at actual strength, two
    named unseeable residuals);
  - live tests are opt-in with a named executable consumer;
  - residency bounds are driver-scoped and probe-proven (sent ≠ honored);
  - AMEND the 0040 run-granularity invalidation convention: run-granularity when no
    per-check records exist, boundary-granularity when they do — same outcome-blind
    criterion, never per-suspicious-cell.

### Step 21 — Refactor: shared `/api/ps` reader (REFACTOR, optional)
- Extract the `/api/ps` loopback-gated resident-reader shared by `exclusivity_gate`,
  `residency_probe`, and `_evict_other_models` into one helper (single source, still
  behind `assert_local`).
- All tests still pass.

## Delegation

- Steps 1–10 (contracts, predicates, gated driver) → keep with `tdd-planner`/primary
  implementer: tightly coupled to the 0038/0040 typed-outcome + ledger idioms already in
  `harpyja/eval/`.
- Step 15 ast confinement guard → delegate to a guards-focused reviewer if available
  (reason: mirrors the `test_fastcontext_absent.py` deletion-guard ast discipline).
- Steps 18–19 live integration → operator-run (single-host Ollama; the drivers are the
  executable consumers). Reason: requires the live dev stack + exclusive/contended
  endpoint setup, not CI.

## Risk

- **Global `addopts` deselect changes every run's default selection.** → mitigation: the
  opt-in `-m integration` is documented AND mechanically exercised by
  `assert_live_optin_selection`; closure runs under `HARPYJA_REQUIRE_LIVE_STACK` opt back
  in. Prove non-zero opt-in / zero default in step 16 before committing the config.
- **Same-tag contention is structurally invisible to `/api/ps`.** → mitigation: not
  mechanized (declined lease/lock, single-operator host); carried by the deselect default +
  named as the second unseeable residual in the exclusivity record (step 1–2 assert it
  present). No overclaim.
- **Bumping the pilot ledger write version could break committed 0040 tests.** →
  mitigation: the new version is opt-in via the `exclusivity=` argument; absent it, the
  ledger writes/reads `0040/pilot/1` byte-unchanged. Step 5 asserts both directions.
- **Per-block boundary suspect typing mis-scoping (the AC2 ambiguity codex flagged).** →
  mitigation: the worked example (clean before N−1, fail before N → N never runs, N−1
  suspect, 1..N−2 valid) is the exact assertion in step 9's flipping-fake test.
- **Wiring↔evidence drift on the residency mechanism.** → mitigation: the loud-fail
  tripwire (step 11) fails, never skips, when the driver's touch-enabled state disagrees
  with the committed probe outcome.
