---
spec: "0020"
status: planned
strategy: tdd
---

# Plan — 0020 OQ2 (the operator sweep)

Python project. Unit selection: `uv run pytest -m "not integration"`. Live/served
tests are `@pytest.mark.integration` and **skip-not-fail** when the environment is
absent. Test files `test_<subject>.py`, functions `test_<subject>_<scenario>`. Every
file created/edited is under `harpyja/eval/` — the SUT stays frozen.

## Proposed new modules (all under `harpyja/eval/`, additive)

- **`oq2_classify.py`** — the pure G3 outcome projection: label constants
  (`RECOMMENDATION` / `GATE_CONFOUNDED` / `DEGRADED_DOMINATED` / `NOT_SEPARABLE`),
  a `G3Classification` result dataclass (winning `label`, the `degraded_dominated`
  / `gate_confounded` / `no_survivor` booleans, `indicative_only`), and
  `classify_g3_outcome(recommendation, aggregate, eval_config)`.
  *Placement justification:* the spec offers "additive in recommend.py **or** a new
  module." A new module is chosen because (a) `recommend_oq2` / `rank_sweep` must stay
  **byte-frozen** (D1, measurement-not-construction) and are golden-locked in Step 2 —
  a projection layer *above* the frozen dispatcher belongs outside the file it must
  never perturb; (b) the truth-table matrix (P3) is a large, self-contained unit
  surface that reads cleanly as its own `test_oq2_classify.py` sibling.
- **`oq2_protocol.py`** — the sequential G0→G1→G2→G3 stop-and-report driver, the
  per-gate verdict dataclasses (`GateVerdict` with `gate`, `status`, measured
  sub-values, cause), and the top-level `run_oq2_protocol(...)` that threads injected
  collaborators (preflight payload/resolver, provision fn, stack_factory, sweep fn).
  Fully unit-testable with **injected fakes** — no live models in unit tests.
- **`oq2_ledger.py`** — `LEDGER_SCHEMA_VERSION = "0020/1"` (distinct from the sweep
  report `0014/1`), `build_gate_ledger(...)`, `validate_gate_ledger(...)`, and a thin
  `write_gate_ledger(...)` that reuses `report.atomic_write_json` (single-sourced
  atomic + outside-repo guard).
  *Placement justification:* D8/AC2 require a **new pinned artifact with its own
  version id**, not the sweep report. A new module keeps `report.py` at `0014/1`
  unbumped and avoids conflating two schemas + two validators in one file, while
  importing `atomic_write_json` so the write guard stays in one place.

## Test files

- **extend** `test_recommend.py` — P1 field-reachability, P2 byte-frozen golden lock.
- **new** `test_oq2_classify.py` — P3 truth-table matrix + boundaries (AC6/7/8).
- **new** `test_oq2_ledger.py` — ledger schema/validator/writer (AC2).
- **new** `test_oq2_protocol.py` — the driver with injected fakes (AC1/3/4/5/9/10/11).
- **extend** `test_swebench_integration.py` — live G0→G3 operator run (AC12).

---

## Test-first sequence

### Step 1 — P1: discriminator field-reachability on the frozen `Recommendation` (LOCK)
- Extend `test_recommend.py`:
  - `test_recommend_no_survivor_has_unique_false_false_combo` — drive `rank_sweep`
    with a grid where no point clears `catch_rate_bar`; assert
    `incumbent_validated is False and advantage_exceeds_variance is False`.
  - `test_recommend_variance_beating_flip_sets_advantage_exceeds_variance` — drive the
    flip branch (recommend.py:132–149); assert `advantage_exceeds_variance is True`
    (so it is NOT the no-survivor combo).
  - `test_recommend_validated_incumbent_sets_incumbent_validated` — drive the
    within-variance / best-incumbent branches (:104–131); assert
    `incumbent_validated is True`.
- This is a **characterization lock** against already-shipped frozen code — it passes
  on first run **by design**, proving the S-discriminator
  (`incumbent_validated is False AND advantage_exceeds_variance is False`) is reachable
  on the byte-frozen `Recommendation` **without touching the dispatcher**. It gates
  Step 4. (P1; AC8)

### Step 2 — P2: byte-frozen `recommend_oq2` / `rank_sweep` golden lock (LOCK)
- Extend `test_recommend.py`:
  - `test_recommend_oq2_behavior_snapshot_is_frozen` — a fixed table of inputs
    (no-survivor grid; validated-incumbent grid; variance-beating-flip grid;
    over-ceiling measured rate; `None` measured rate) → assert the exact
    `Recommendation` field tuple `(verify_threshold, verify_top_n, catch_rate_bar,
    advantage_exceeds_variance, incumbent_validated, outcome,
    gate_false_escalation_measured)` for each.
- A **behavior snapshot** (in-grain with the codebase's field-introspection style),
  NOT a source grep — satisfies P2's "concretely observable byte-unchanged" the way
  convention prefers. Passes on first run; any later edit to the dispatcher breaks it.
  (P2; AC6, AC10)

### Step 3 — `classify_g3_outcome` truth table (RED)
- Add `test_oq2_classify.py`:
  - `test_classify_g3_outcome_degraded_dominated_wins` — D=T (with G and/or S also
    true) → `DEGRADED_DOMINATED`; assert all co-true booleans recorded.
  - `test_classify_g3_outcome_gate_confounded_when_not_degraded` — D=F, G=T →
    `GATE_CONFOUNDED`; assert the `no_survivor` boolean is **not** computed (n/a) under
    the gate-confound short-circuit (no phantom `NOT_SEPARABLE`).
  - `test_classify_g3_outcome_not_separable_no_survivor` — D=F, G=F, S=T →
    `NOT_SEPARABLE` (recommendation from the no-survivor branch).
  - `test_classify_g3_outcome_recommendation_validated_incumbent` — D=F, G=F, S=F, a
    validated incumbent → `RECOMMENDATION` (D2 boundary: within-variance is NOT
    `NOT_SEPARABLE`).
  - `test_classify_g3_outcome_recommendation_variance_beating_flip` — D=F, G=F, S=F, a
    flip → `RECOMMENDATION`.
  - `test_classify_g3_outcome_both_degraded_and_gate_confounded_records_both` — D=T,
    G=T → label `DEGRADED_DOMINATED`, both booleans set (records all true conditions).
  - `test_classify_g3_outcome_indicative_only_below_n_floor` — RECOMMENDATION with
    effective_N (12) < n_floor (30) → `indicative_only is True`.
  - `test_classify_g3_outcome_not_indicative_at_or_above_n_floor` — effective_N == 30 →
    `indicative_only is False` (sub-flag lives on RECOMMENDATION only).
- Tests fail: `harpyja.eval.oq2_classify` / `classify_g3_outcome` do not yet exist
  (ImportError). (P3; AC6, AC7, AC8)

### Step 4 — implement `classify_g3_outcome` (GREEN)
- Implement `oq2_classify.py`: the label constants, `G3Classification`, and the pure
  projection applying total order **D > G > S > default**. S is computed **only** when
  `recommendation.outcome != OUTCOME_GATE_CONFOUNDED`
  (`incumbent_validated is False and advantage_exceeds_variance is False`), else left
  n/a. `indicative_only = effective_N < eval_config.n_floor`, set on RECOMMENDATION
  only. `degraded_dominated` read from `aggregate["degraded_dominated"]`; `effective_N`
  read from an agreed `aggregate` key (see Risk — the 3-arg signature is pinned, so the
  protocol injects `effective_n` into the aggregate it hands classify).
- All Step-3 tests pass; `recommend_oq2` / `rank_sweep` untouched (Step 2 lock holds).
  (AC6, AC7, AC8)

### Step 5 — gate-ledger schema, validator, writer (RED)
- Add `test_oq2_ledger.py`:
  - `test_gate_ledger_schema_version_is_0020_1` — `LEDGER_SCHEMA_VERSION == "0020/1"`,
    distinct from report `SCHEMA_VERSION`.
  - `test_build_gate_ledger_has_all_gate_and_provenance_fields` — a built ledger from
    fake per-gate verdicts carries per-gate verdicts + each G1 sub-check measured
    value + close/hold cause + G3 label + all D/G/S booleans + provenance (SUT git SHA,
    resolved `EvalConfig`, fixture-subset id, model tags, threshold×top_n grid).
  - `test_validate_gate_ledger_loud_on_missing_field` — a ledger missing a required
    field raises the ledger's schema error.
  - `test_write_gate_ledger_refuses_inside_repo` — writing under `repo_path` raises
    (reuses `atomic_write_json`'s outside-repo guard).
  - `test_validate_gate_ledger_g3_booleans_optional_under_gate_confound` — under
    `GATE_CONFOUNDED` the `no_survivor` boolean is recorded as n/a, and validation
    still passes (guards C3's phantom-`NOT_SEPARABLE` avoidance at the schema layer).
- Tests fail: `harpyja.eval.oq2_ledger` does not yet exist. (AC2)

### Step 6 — implement `oq2_ledger.py` (GREEN)
- Implement `LEDGER_SCHEMA_VERSION`, the enumerated field contract,
  `build_gate_ledger`, `validate_gate_ledger`, `write_gate_ledger` (delegating to
  `report.atomic_write_json` with `filename="gate_ledger.json"`).
- All Step-5 tests pass. (AC2)

### Step 7 — protocol G0 preflight routing + stop-before-provision (RED)
- Add `test_oq2_protocol.py`:
  - `test_protocol_g0_missing_model_stops_before_provision` — inject a fake tags
    payload missing a required tag (routes through `preflight_models_present`); assert
    the protocol halts with a `BLOCKED` hold naming the first missing tag, and the
    injected provision fn is **never called**.
  - `test_protocol_g0_pass_records_verdict_then_enters_g1` — all tags present → G0
    verdict recorded (pulled tag set), and the driver proceeds to G1.
- Tests fail: `harpyja.eval.oq2_protocol` / `run_oq2_protocol` do not exist. (AC1, AC3)

### Step 8 — implement protocol scaffolding + G0 stage (GREEN)
- Implement `oq2_protocol.py`: `GateVerdict`, a `ProtocolResult` accumulator, and
  `run_oq2_protocol(...)` threading injected collaborators; the G0 stage routes through
  `preflight_models_present` (assert_local-first, deduped tags), records the verdict,
  and on `PreflightError` returns a `BLOCKED` hold **before** provisioning.
- All Step-7 tests pass. (AC1, AC3)

### Step 9 — protocol G1 three sub-checks, classed by cause (RED)
- Extend `test_oq2_protocol.py`:
  - `test_protocol_g1_environment_noncompletion_is_blocked_hold` — fake single-case
    run whose sub-check (a) fails for an environment reason (OOM/resource) → `BLOCKED`
    hold (NOT a close); sweep fn never called.
  - `test_protocol_g1_completed_but_degrade_dominant_is_stop_smoke` — run completes,
    sub-check (b) fails (scout/deep degrade-dominant) → `STOP:SMOKE` close with the
    measured value recorded.
  - `test_protocol_g1_completed_but_false_rejects_citation_is_stop_smoke` — run
    completes, sub-check (c) fails (astropy-12907 correct citation gate-false-rejected)
    → `STOP:SMOKE` close with the measured value recorded.
  - `test_protocol_g1_all_three_subchecks_pass_enters_g2` — all pass → G1 verdict
    (each sub-check measured value) recorded, driver proceeds to G2.
- Tests fail: the G1 stage is unimplemented (attribute/behavior gap). (AC1, AC4, AC12)

### Step 10 — implement protocol G1 stage (GREEN)
- Implement the G1 stage: single astropy-12907 `mode=auto` pass via the injected
  stack_factory, three sub-checks, non-completion classed **by cause**
  (environment/OOM → `BLOCKED` hold; completed-then-degrade/false-reject →
  `STOP:SMOKE` close), each sub-check's measured value recorded on the verdict.
- All Step-9 tests pass. (AC4, AC12)

### Step 11 — protocol G2 first-class metrics, A/B, over-ceiling-no-abort (RED)
- Extend `test_oq2_protocol.py`:
  - `test_protocol_g2_captures_false_escalation_and_catch_rate` — G2 verdict carries
    `gate_false_escalation_rate` + `catch_rate` as first-class fields.
  - `test_protocol_g2_records_instruct_vs_finder_ab` — both A/B rates recorded; when
    the finder judge beats instruct, an OQ-A **flag** is set (does not re-decide).
  - `test_protocol_g2_under_ceiling_routes_clean_g3` — instruct rate ≤ ceiling → G2
    pass, routes to a clean (full-sweep) G3.
  - `test_protocol_g2_over_ceiling_does_not_abort_routes_descriptive_g3` — instruct
    rate strictly > ceiling → recorded, **no abort**, routes to a descriptive-only G3.
- Tests fail: the G2 stage is unimplemented. (AC1, AC5)

### Step 12 — implement protocol G2 stage (GREEN)
- Implement the G2 stage: point-subset gate metrics (`gate_false_escalation_rate`,
  `catch_rate`) + the instruct-vs-finder A/B via injected fake sweep/aggregate;
  over-ceiling records + routes to descriptive-only G3 (never aborts); finder-beats-
  instruct sets the OQ-A flag.
- All Step-11 tests pass. (AC5)

### Step 13 — protocol G3 → classify + descriptive-only-under-confound (RED)
- Extend `test_oq2_protocol.py`:
  - `test_protocol_g3_clean_runs_full_sweep_then_classifies` — under a clean G2, G3
    runs the full `k_runs`×grid sweep, feeds `classify_g3_outcome`, and records the
    winning label + all D/G/S booleans on the G3 verdict.
  - `test_protocol_g3_under_confound_single_descriptive_pass_no_tuning` — under
    G2-over-ceiling, G3 runs a **single descriptive pass** (no threshold tuning),
    records accuracy / escalation / Tier-0-alone / `fc_citation_*` shapes, then reports
    `GATE_CONFOUNDED` — never a full `k_runs`×grid sweep.
  - `test_protocol_g3_never_forces_a_pick_on_typed_null` — a typed-null classification
    is returned as the deliverable; no `(threshold, top_n)` is manufactured.
- Tests fail: the G3 stage is unimplemented. (AC1, AC9, AC11)

### Step 14 — implement protocol G3 stage + ledger emission (GREEN)
- Implement the G3 stage: clean path → full sweep → `classify_g3_outcome`;
  confounded path → single descriptive pass → `GATE_CONFOUNDED`. At protocol end (or
  at any stop), assemble the accumulated gate verdicts via `build_gate_ledger` and
  write it with `write_gate_ledger` (outside any target repo). The protocol injects
  `effective_n` into the aggregate handed to classify.
- All Step-13 tests pass. (AC9, AC11, AC2)

### Step 15 — full-protocol ledger + stop-and-report ordering (RED)
- Extend `test_oq2_protocol.py`:
  - `test_protocol_emits_ledger_version_0020_1` — a full run emits a `0020/1` ledger,
    validated.
  - `test_protocol_records_each_verdict_before_next_gate` — the ledger shows each
    gate's verdict recorded before the next gate's collaborator is invoked (assert via
    call-order on the injected fakes).
  - `test_protocol_g0_blocked_ledger_has_no_g1_g2_g3_verdicts` — a G0 `BLOCKED` hold
    yields a ledger with only the G0 verdict + the hold cause + the exact remediation
    command / missing tags (AC12 hold names the fix).
  - `test_protocol_g1_stop_smoke_is_a_close_not_a_hold` — a `STOP:SMOKE` ledger is
    marked a **close** (a valid SUT-observing outcome), distinct from a `BLOCKED` hold.
- Tests fail: end-to-end ledger assembly / ordering guarantees not yet complete. (AC1,
  AC2, AC11, AC12)

### Step 16 — implement end-to-end ledger assembly + ordering (GREEN)
- Finalize `run_oq2_protocol` so every gate verdict is committed to the accumulator
  **before** the next gate's collaborator runs, the ledger records close-vs-hold cause,
  and a `BLOCKED` hold ledger names the missing tags / fixture path + the exact command.
- All Step-15 tests pass. (AC1, AC2, AC11, AC12)

### Step 17 — no-default-flip guard (LOCK)
- Extend `test_oq2_protocol.py`:
  - `test_protocol_recommendation_does_not_flip_settings_defaults` — after a
    RECOMMENDATION run, assert `Settings()` field defaults for `verify_threshold` /
    `verify_top_n` / `verify_method` are byte-unchanged (field-default introspection,
    not a source grep), and the recommendation is returned as ledger **evidence**, not
    applied.
- Characterization lock — our eval code never touches `Settings`; passes on first run,
  guards against a future edit that would apply the recommendation. (AC10)

### Step 18 — Refactor (optional)
- Consolidate the per-gate `GateVerdict → ledger record` mapping if Steps 8/10/12/14
  introduced duplication (a single verdict-to-dict projection read by
  `build_gate_ledger`). All tests still pass.

### Step 19 — live G0→G3 operator run harness (RED → integration)
- Extend `test_swebench_integration.py`:
  - `test_oq2_protocol_live_g0_to_g3` — `@pytest.mark.integration`, **skip-not-fail**
    when `HARPYJA_N12_FIXTURES` or the served stack is absent. Drives the **real**
    `run_oq2_protocol` end-to-end with the D9 config
    (`--scout-model hf.co/dstolf/FastContext-1.0-4B-RL-Q8_0-GGUF:latest`,
    `--deep-model qwen3-coder:30b`) through `_live_stack_factory`, and asserts a
    recorded `0020/1` ledger with a typed outcome (STOP:SMOKE / G3 label) **or** a
    `BLOCKED` hold naming the fix.
- Add the live wiring entry (`_live_oq2_collaborators` / `cmd_oq2`) if a thin
  live-factory seam is needed. Test skips (never fails) when the env is absent.
- **AC12 note for implement/close:** skip-not-fail is NOT a valid CLOSE for 0020. The
  operator must actually run this against the provisioned N=12 subset + served stack so
  the ledger records a real STOP:SMOKE / G3 label (a close) or a real BLOCKED hold. The
  unit steps make the harness correct; this step makes it *runnable*; **closing 0020
  requires an executed run producing a recorded outcome.** (AC12)

---

## AC coverage map

- **AC1** (sequential driver, verdict-before-next-gate) → Steps 7,9,11,13,15,16
- **AC2** (gate-ledger `0020/1`) → Steps 5,6,14,15,16
- **AC3** (G0 preflight routing, stop-before-provision) → Steps 7,8
- **AC4** (G1 three sub-checks, classed by cause) → Steps 9,10
- **AC5** (G2 first-class metrics + A/B, over-ceiling-no-abort) → Steps 11,12
- **AC6** (`classify_g3_outcome` pure; dispatcher byte-unchanged) → Steps 2,3,4
- **AC7** (precedence D>G>S>default, all booleans, S-guard) → Steps 3,4
- **AC8** (label boundaries; NOT_SEPARABLE discriminator; indicative_only) → Steps 1,3,4
- **AC9** (over-ceiling → single descriptive G3) → Steps 11,12,13,14
- **AC10** (no Settings default flipped) → Steps 2,17
- **AC11** (typed null is a valid deliverable; never a forced pick; code under eval/) →
  Steps 13,14,15,16
- **AC12** (close = recorded SUT-observing outcome; BLOCKED = hold; skip-not-fail ≠
  close) → Steps 9,10,15,16,19

## Delegation

- Steps 5–6 (`oq2_ledger.py`) → delegate-able: a self-contained
  schema/validator/writer mirroring the well-established `report.py` `0014/1` pattern
  (append last-with-defaults, loud validator, reuse `atomic_write_json`) — low coupling
  to the driver, clear precedent.
- Steps 3–4 (`oq2_classify.py`) → delegate-able: a pure function fully pinned by the
  round-2 truth table (P3) and Step-1 field-reachability — an isolated, total
  unit-test surface with no live dependencies.
- Steps 7–16 (`oq2_protocol.py`) → keep in-thread: the driver integrates classify +
  ledger + preflight + sweep across four gates with load-bearing ordering / close-vs-
  hold seams (D7) that reward holding the whole picture; not safely offloadable.

## Risk

- **`classify_g3_outcome` effective_N source vs the pinned 3-arg signature.** The spec
  fixes `classify_g3_outcome(recommendation, aggregate, eval_config)`, but the runner
  `aggregate` (runner.py:286) carries `degraded_dominated` yet **no** N/seed_n
  (seed_n lives in `run_metadata`). → Mitigation: the protocol injects an additive
  `effective_n` key into the `aggregate` mapping it hands classify (harness-side,
  additive, SUT-frozen); pin the key in the Step-3 RED so the contract is explicit.
- **STOP:SMOKE vs BLOCKED seam (D7/C2) is behavioral, not structural.** The by-cause
  split (environment/OOM → hold; completed-then-degrade/false-reject → close) is only
  as good as the injected fakes exercising each cause. → Mitigation: Step 9 tests each
  cause explicitly, and Step 15 asserts the ledger marks close vs hold distinctly.
- **AC12 close requires an executed operator run, not a passing unit suite.** All unit
  steps can be green while 0020 is still not closeable (only a HOLD is recorded). →
  Mitigation: Step 19 flags this loudly for implement/close; the D9 config + N=12
  fixtures (`HARPYJA_N12_FIXTURES`) must be present and the run actually performed,
  with the OOM-under-co-load (~22 GB co-resident, D9) risk classed as a BLOCKED hold if
  it bites on the 32 GB host.
- **Two new pinned schemas could drift from `report.py`.** The ledger `0020/1` and the
  sweep report `0014/1` share the atomic writer but not the validator. → Mitigation:
  `oq2_ledger.py` imports `atomic_write_json`, keeps its own enumerated field set +
  loud validator (Step 5), and does NOT bump `report.SCHEMA_VERSION`.
