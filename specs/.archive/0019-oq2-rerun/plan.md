---
spec: "0019"
status: planned
strategy: tdd
---

# Plan — 0019 OQ2 re-run — complete, prove the gate, then calibrate

## Overview

Spec 0019 is a **measurement** spec: the SUT (tiers/gate/matrix/judge) is FROZEN.
All new code lands in `harpyja/eval/` (the harness), which the conventions explicitly
hold to be additively extensible even under the measurement-not-construction invariant.
Nearly all RED→GREEN lives on four unit surfaces; the G1/G2/G3 gate demonstrations are
`@pytest.mark.integration`, skip-not-fail operator runs that DEMONSTRATE and never gate CI.

Test command: `uv run pytest` (unit-only: `uv run pytest -m "not integration"`).
Test files are EXTENDED, never duplicated (`test_<subject>.py`, fns
`test_<subject>_<scenario>`).

### Files touched

- `harpyja/eval/config.py` — add `EvalConfig.gate_false_escalation_ceiling: float = 0.20`
  (eval-only; disjoint from `Settings`).
- `harpyja/eval/recommend.py` — add a `gate-confounded` typed-null outcome + branch
  (today emits only incumbent-validated / flip / not-cleared).
- `harpyja/eval/report.py` — bump `SCHEMA_VERSION` `"0013/1"` → `"0014/1"`; append
  additive fields last-with-defaults (`gate_false_escalation_ceiling`, the
  gate-confounded outcome + measured rate, the instruct-vs-scout A/B twins).
- `harpyja/eval/swebench_eval.py` — add `preflight_models_present` + `PreflightError`
  + `cmd_preflight` + a `preflight` CLI subparser; wire the ceiling into report
  metadata and the gate-confounded branch into the sweep decision.
- `harpyja/eval/metrics.py` — NO code change expected (the one overlap oracle and
  null-with-zero-count already exist); AC5 characterization-locks that behavior.

### Existing symbols reused (not reinvented)

- `metrics._any_primary_overlap` (the single oracle), `gate_false_escalation` /
  `gate_catch_rate` (already return `(rate|None, count, total)` — null-with-count).
- `recommend.rank_sweep` / `Recommendation` / `INCUMBENT = (0.6, 3)` /
  `advantage_exceeds_spread`.
- `report.build_report` / `validate_report` / the `_*_DEFAULTS` maps.
- `gateway.assert_local(endpoint, *, resolver=…)` + `AirGapError` (the ONE air-gap seam).
- The 0016 AC7 positive-membership `/api/tags` probe pattern in
  `test_swebench_integration.py`.

## Test-first sequence

### Group A — gate-confound ceiling knob (D2)

#### Step 1 — EvalConfig ceiling default (RED)
- Extend `harpyja/eval/test_config.py`:
  - `test_eval_config_has_gate_false_escalation_ceiling_default` — a fresh
    `EvalConfig()` exposes `gate_false_escalation_ceiling == 0.20`.
  - `test_eval_config_is_independent_of_settings` (existing) still passes — the new
    knob is eval-only and its name is NOT a `Settings` field.
- Tests fail: `EvalConfig` has no `gate_false_escalation_ceiling` attribute.

#### Step 2 — add the ceiling field (GREEN)
- Edit `harpyja/eval/config.py`: add `gate_false_escalation_ceiling: float = 0.20`
  (frozen dataclass field, appended with default + a provisional-bar comment).
- All step-1 tests pass. (AC: D2, feeds AC4/AC9.)

### Group B — gate-confounded typed-null branch (D2 / AC9)

#### Step 3 — gate-confounded decision (RED)
- Extend `harpyja/eval/test_recommend.py`:
  - `test_gate_confounded_below_ceiling_defers_to_rank_sweep` — a measured instruct
    false-escalation `≤ ceiling` yields the normal `rank_sweep` recommendation
    (incumbent-validated / flip), NOT a confound null.
  - `test_gate_confounded_above_ceiling_emits_typed_null` — a measured rate
    `> gate_false_escalation_ceiling` yields the `gate-confounded` outcome instead of
    a clean pick (no `verify_threshold` calibrated over a broken judge).
  - `test_gate_confounded_carries_measured_rate` — the confounded result carries the
    exact measured false-escalation rate and a stable outcome identifier
    (`outcome == "gate-confounded"`).
  - `test_gate_confounded_exactly_at_ceiling_is_not_confounded` — boundary: `== 0.20`
    is NOT confounded (`>` is strict, mirroring the ceiling wording in AC4).
- Tests fail: no gate-confound function / outcome exists in `recommend.py`.

#### Step 4 — implement the gate-confounded branch (GREEN)
- Edit `harpyja/eval/recommend.py`: add a `GATE_CONFOUNDED` stable identifier and a
  function (`gate_confounded_recommendation(measured_rate, eval_config)`) plus a
  typed-null carrier — either an additive `outcome: str = "recommended"` +
  `gate_false_escalation_measured: float | None = None` on `Recommendation`
  (appended last-with-defaults, so existing constructions keep working) or a sibling
  `GateConfoundedResult`. The dispatcher: measured `> ceiling` → confound null;
  else `rank_sweep`. Keep `rank_sweep` itself unchanged for the clean path.
- All step-3 tests pass. (AC: D2, AC9.)

### Group C — one oracle + explicit denominators (AC5) [characterization lock]

#### Step 5 — lock the single oracle + null-with-count (LOCK)
- Extend `harpyja/eval/test_metrics.py`:
  - `test_gate_metrics_use_same_oracle_as_span_hit` — assert `gate_false_escalation`
    and `gate_catch_rate` classify Tier-1 correctness through the SAME
    `_any_primary_overlap` that backs `case_span_hit_primary` (no second oracle):
    construct a case where the oracle flips and show both the accuracy oracle and the
    gate denominator membership flip together.
  - `test_gate_false_escalation_null_with_zero_count` — empty correct-Tier-1 point
    population → `(None, 0, 0)`, never a silent `0.0`.
  - `test_gate_catch_rate_null_with_zero_count` — empty wrong-Tier-1 point population
    → `(None, 0, 0)`.
- These are **characterization locks**: they pass against the current `metrics.py`
  (the behavior already exists per spec). No production edit accompanies them — they
  regression-lock the AC5 invariant so a later change cannot introduce a second
  correctness definition or a false `0.0`. (AC: AC5.)

### Group D — report schema bump + additive fields (AC5 denominators / AC6 A/B / D2)

#### Step 6 — schema bump + additive gate/ceiling/A-B fields (RED)
- Extend `harpyja/eval/test_report.py`:
  - `test_schema_version_bumped_to_0014` — `SCHEMA_VERSION == "0014/1"`.
  - `test_validate_report_accepts_gate_confound_and_ceiling_fields` — a report built
    with `run_metadata.gate_false_escalation_ceiling`, aggregate
    `gate_confounded` / `gate_confounded_measured_rate`, and the A/B twins
    (`gate_false_escalation_instruct` + count/total, `gate_false_escalation_scout` +
    count/total) validates.
  - `test_validate_report_tolerates_legacy_omitting_new_fields` — a block that omits
    every new field still validates because `build_report` default-populates them
    (null-with-count / `False` / `None` defaults).
  - `test_report_round_trip_gate_confounded` — `build_report` → `json.dumps` →
    `json.loads` → `validate_report` preserves the gate-confound outcome + measured
    rate and the A/B twins.
- Tests fail: `SCHEMA_VERSION` is `"0013/1"`; new fields absent from the field tuples
  and the `_*_DEFAULTS` maps.

#### Step 7 — bump + append fields last-with-defaults (GREEN)
- Edit `harpyja/eval/report.py`: bump `SCHEMA_VERSION` to `"0014/1"`; append
  `gate_false_escalation_ceiling` to the run-metadata field set (+ default `None`);
  append to the aggregate field set (+ defaults): `gate_confounded` (default `False`),
  `gate_confounded_measured_rate` (default `None`), and the A/B twins
  `gate_false_escalation_instruct` / `_instruct_count` / `_instruct_total`,
  `gate_false_escalation_scout` / `_scout_count` / `_scout_total` (rates default
  `None`, counts default `0` — the null-with-zero-count convention). All additive,
  appended last.
- All step-6 tests pass; every existing `test_report.py` case still passes because the
  defaults keep older-shape blocks valid. (AC: AC5, AC6, D2.)

#### Step 8 — Refactor: centralize the gate-confound field set (REFACTOR, optional)
- If Step 4 and Step 7 both name the confound outcome/measured-rate keys, hoist the
  key names to a single module-level tuple/constant shared by `recommend.py`'s carrier
  and `report.py`'s builder so the field set has one anti-drift source.
- All tests still pass.

### Group E — preflight assertion logic (AC2 unit)

#### Step 9 — preflight membership + assert_local-first (RED)
- Extend `harpyja/eval/test_swebench_eval.py`:
  - `test_preflight_models_present_all_present_passes` — a fake `/api/tags` payload
    containing `scout_model`, `lm_model` (judge), and the resolved deep-model tag →
    `preflight_models_present(...)` returns cleanly.
  - `test_preflight_models_present_missing_model_raises_naming_it` — drop one tag from
    the fake payload → a loud typed `PreflightError` whose message NAMES the missing
    model (mirrors 0016 AC7 positive membership, inverted for absence).
  - `test_preflight_asserts_local_before_tags_read` — the presence probe runs behind
    `gateway.assert_local` on the resolved loopback endpoint using an INJECTED fake
    resolver (never a live call); a non-loopback endpoint raises `AirGapError` BEFORE
    any `/api/tags` membership logic (order asserted via a spy resolver / a
    non-loopback endpoint short-circuiting).
  - `test_preflight_claims_pulled_not_coresident` — the success path asserts only
    "pulled" membership; no OOM/co-residence claim (documented by the absence of any
    load probe — an honesty assertion on the message/return wording).
- Tests fail: `preflight_models_present` / `PreflightError` do not exist.

#### Step 10 — implement preflight (GREEN)
- Edit `harpyja/eval/swebench_eval.py`: add `PreflightError(Exception)` and
  `preflight_models_present(settings, tags_payload, *, resolver=None)` — resolve the
  **deduped required-tag set** from `settings` (`scout_model`, `lm_model` judge, and
  the deep-model tag which today resolves to `lm_model`), call
  `gateway.assert_local(<endpoint>, resolver=resolver)` FIRST, then assert every
  required tag is a member of the `{m["name"] for m in tags_payload["models"]}` set,
  raising `PreflightError` naming the first absent tag. Add `cmd_preflight` (fetches
  `/api/tags` live behind `assert_local`, calls the pure function) + a `preflight`
  subparser. Membership contract is per-required-tag, not a hard count of three.
- All step-9 tests pass. (AC: AC2, feeds AC1.)

### Group F — integration scaffolding (AC1 / AC3 / AC4 / AC6 / AC7 / AC8 / AC9)

#### Step 11 — G1→G2→G3 skip-not-fail demonstrations (integration scaffolding)
- Extend `harpyja/eval/test_swebench_integration.py` (all `@pytest.mark.integration`,
  skip when the served stack / fixtures / models are absent — DEMONSTRATE, never gate;
  each skip carries a diagnostic naming the missing precondition, per 0016 AC7):
  - `test_preflight_live_models_present_or_loud` (AC1) — live `/api/tags` behind
    `assert_local`; all three present → pass; a missing tag → a loud `PreflightError`
    at setup (skip when Ollama unreachable / tags absent).
  - `test_g1_astropy12907_smoke_completes` (AC3) — astropy-12907 ALONE, `mode=auto`,
    end-to-end to completion; records pass/fail; a recorded G1 failure is an accepted
    terminal outcome (assert the run terminates + writes an artifact, do NOT assert a
    correct citation).
  - `test_g2_gate_quality_first_class` (AC4) — on the point subset, the report carries
    `gate_false_escalation` / `gate_catch_rate` scored by the one oracle; G2 typed
    pass = astropy-12907 correct AND instruct false-escalation `≤ 0.20`; the outcome
    is recorded either way.
  - `test_g2_ab_instruct_vs_scout_judge` (AC6) — run the subset with
    `verify_method="instruct_model"` and again with `"scout_model"` (config override
    via `dataclasses.replace`, SUT unchanged); assert both A/B twin fields populate
    side-by-side in the additive report.
  - `test_g3_sweep_completes_at_scale` (AC7) — conditional on G1∧G2 pass: full sweep
    over a G1/G2-derived `verify_threshold` grid that INCLUDES the incumbent `(0.6, 3)`
    (D1); `N ≥ n_floor`; a trade-off table with mean+spread per point. A run STOPPED
    at G1/G2 satisfies AC7 by recording the stop-reason and NOT producing the table.
  - `test_g3_reliability_gate_withholds_oq2` (AC8) — a `degraded_dominated` sweep
    withholds OQ2 as a finding (reliability gate enforced, `reliability_notes`
    carries `degraded-dominated`).
  - `test_oq2_recommended_or_typed_null` (AC9) — OQ2 emits either a variance-gated
    recommendation OR an explicit typed null (`not-separable` / `degraded-dominated` /
    `gate-confounded`), never a forced pick; if G2 failed its ceiling the emitted
    result is `gate-confounded` carrying the measured rate; `0.6` is not assumed a
    starting default.
- No production code in this step — scaffolding over the Group A–E surfaces.
  (AC: AC1, AC3, AC4, AC6, AC7, AC8, AC9.)

### Group G — AC10 standing regression placeholder

#### Step 12 — defect-surfaced-at-scale regression placeholder (placeholder)
- No upfront test. A standing task: any defect the live run surfaces (an `int | None`
  consumer, a schema sink, model-default drift) gets its OWN unit regression test in
  the appropriate `test_*.py` sibling BEFORE the run is declared complete, where
  "complete" = a schema-valid G3 report (recommended `(threshold, top_n)` OR a typed
  null) written out-of-repo, OR a recorded G1/G2 stop-finding artifact. (AC: AC10.)

## Delegation

- Steps 1–10 (unit RED→GREEN on `config.py` / `recommend.py` / `report.py` /
  `metrics.py` / `swebench_eval.py`) → main-session TDD: tightly coupled to real
  harness symbols, high edit locality, one-file-at-a-time verifiable by
  `uv run pytest -m "not integration"`.
- Step 11 (integration scaffolding) → local; operator-run skip-not-fail, needs the
  served stack + provisioned fixtures, not parallelizable authorship.
- Step 12 (AC10) → deferred to whoever runs the live sweep; each surfaced defect is its
  own micro RED→GREEN at the point of discovery.

## Risk

- **Report field-list drift between `recommend.py` and `report.py`** (the confound
  outcome/measured-rate keys named twice) → mitigation: Step 8 refactor hoists the key
  set to one anti-drift constant + `_*_DEFAULTS` map (the 0011/0014 convention).
- **Schema bump breaks existing `test_report.py` / on-disk baselines** → mitigation:
  strictly additive, appended last-with-defaults; Step 6 includes an explicit
  legacy-tolerance test before Step 7 edits the version.
- **Preflight tempted into a second outbound path** (violating the one-air-gap rule) →
  mitigation: the pure `preflight_models_present` takes an INJECTED payload + resolver
  and routes only through `gateway.assert_local`; the live `/api/tags` read lives in
  `cmd_preflight` behind that same assert, never a parallel egress.
- **"Three models" ambiguity** (deep-model currently resolves to `lm_model`) →
  mitigation: preflight resolves the required tag SET from `settings` and dedupes, so a
  shared judge/deep tag is checked once; the membership contract is per-required-tag,
  not a hard count of three.
- **Integration tests silently never running** (skip-not-fail can hide a broken
  gate) → mitigation: each integration test skips with a diagnostic naming the missing
  precondition (stack / model / fixtures), mirroring the 0016 AC7 three-way skip.
- **`gate_false_escalation_ceiling` leaking into the SUT** → mitigation:
  `test_eval_config_is_independent_of_settings` (Step 1) asserts field-name
  disjointness from `Settings`.
