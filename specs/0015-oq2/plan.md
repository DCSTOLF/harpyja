---
spec: "0015"
status: planned
strategy: tdd
---

# Plan — 0015 OQ2

**Stack: Python / `uv run pytest` (NOT go test).** Tests are `test_*.py` siblings of
the code under test in `harpyja/eval/`. Naming: `test_<subject>_<scenario>`.
Integration tests carry `@pytest.mark.integration` and **skip-not-fail** when the
live model / sandbox / 12-repo clones are absent.

This spec is **MEASUREMENT**: it reuses the existing instrument
(`metrics.gate_false_escalation` / `gate_catch_rate`, `runner.py:182-184` pre-gate
span capture, `recommend.rank_sweep` D3/D4, `sweep.run_sweep`,
`report.SCHEMA_VERSION` machinery) and adds only the honesty/provenance surface the
ACs demand. Order: pure-unit honesty machinery (enum / precedence / numeric
thresholds / per-point gate) lands FIRST, then report + provenance wiring, then the
integration scaffold + operator runbook, then the AC8 regression.

## Predeclared evidence standard (resolves OQ1 — fixed BEFORE any data)

- **Stage-1 COARSE grid:** `verify_threshold ∈ {0.5, 0.6, 0.7, 0.8}` ×
  `verify_top_n ∈ {1, 3, 5}` = **12 points**, **K=3 constant** (constant-K-within-stage
  so per-point `pstdev` is comparable — the `mean(A)−mean(B) > spread(B)` comparator's
  assumption).
- **Predeclared REFINE rule:** if a non-incumbent survivor's false-escalation advantage
  over the incumbent `(0.6, 3)` is *within* the incumbent's spread BUT *exceeds*
  `0.5 × spread` (promising-but-not-yet-significant), run **Stage-2** over a ±1-grid-step
  neighborhood around that best survivor at **K=5 constant**; otherwise STOP.
- **Predeclared STOP conditions:** incumbent validated, OR a (refined) point beats noise,
  OR a typed null result fires.
- **Numeric thresholds (fixed here):** `gate_confound_threshold = 0.30`,
  `gate_rate_n_floor = 5`, `degraded_dominated_threshold = 0.5` (existing knob reused,
  now also composed per-grid-point).

The grid/K/refine/stop rule is recorded in the operator runbook (Step 11) so the search
cannot be tuned after seeing data.

## Per-grid-point "dominated" baseline (review carry-over, stated explicitly)

`degraded_dominated_threshold = 0.5` is applied **two** ways, both keyed off the
scout∪deep per-case degrade UNION (counted once per case, per the existing
`aggregate_outcomes` rule): (a) the existing **global** run gate (a majority-degraded
run is a finding, OQ2 withheld); (b) a NEW **per-grid-point** drop inside the
recommender — a point whose OWN `scout_deep_degrade_rate > 0.5` is removed from the
comparison set, so a degrade-heavy high-threshold point cannot lose to a clean point on
a degrade artifact rather than worse tuning. Same threshold, same union definition,
applied at two scopes — never silently redefined.

## Test-first sequence

### Step 1 — Eval-only confound knobs (RED)
- Extend `harpyja/eval/test_config.py`:
  - `test_eval_config_has_gate_confound_threshold_default` — `EvalConfig().gate_confound_threshold == 0.30`.
  - `test_eval_config_has_gate_rate_n_floor_default` — `EvalConfig().gate_rate_n_floor == 5`.
  - (existing `test_eval_config_is_independent_of_settings` must still pass — the new knobs are eval-only, field-disjoint from `Settings`.)
- Tests fail: `EvalConfig` has no `gate_confound_threshold` / `gate_rate_n_floor` fields (`AttributeError`).

### Step 2 — Add the knobs to EvalConfig (GREEN)
- `harpyja/eval/config.py`: append `gate_confound_threshold: float = 0.30` and
  `gate_rate_n_floor: int = 5` **last** on the frozen `EvalConfig` (additive,
  last-with-default; eval-only, never reaches the SUT).
- Step-1 tests pass; disjointness invariant intact.

### Step 3 — Typed null-result enum + precedence (RED)
- Extend `harpyja/eval/test_recommend.py`:
  - `test_oq2_outcome_enum_pins_members` — import `OQ2Outcome`; assert its value set is
    exactly `{recommendation, not_separable, under_n_floor, degraded_dominated, gate_quality_confounded}`.
  - `test_rank_sweep_emits_recommendation_outcome_when_point_separates` — separating point ⇒ `rec.outcome is OQ2Outcome.RECOMMENDATION`.
  - `test_rank_sweep_emits_not_separable_when_no_point_clears_bar` — no survivor ⇒ `OQ2Outcome.NOT_SEPARABLE`.
  - `test_rank_sweep_under_n_floor_when_seed_n_below_floor` — `seed_n=10 < n_floor=30` ⇒ `OQ2Outcome.UNDER_N_FLOOR`.
  - `test_rank_sweep_emits_exactly_one_reason` — `rec.reason` is a single non-empty `str`.
  - `test_rank_sweep_precedence_under_n_floor_wins_on_multiply_degenerate` — fixture where seed_n<floor AND all points degrade-dominated AND gate reliably over threshold ⇒ `UNDER_N_FLOOR` (most-fundamental first).
  - `test_rank_sweep_precedence_degraded_over_gate_confound` — not under floor, all-degrade-dominated AND gate over threshold ⇒ `DEGRADED_DOMINATED`.
  - `test_rank_sweep_precedence_gate_confound_over_not_separable` — reliable gate over threshold AND no separation ⇒ `GATE_QUALITY_CONFOUNDED`.
- Tests fail: `OQ2Outcome` does not exist; `Recommendation` has no `outcome`/`reason`;
  `rank_sweep` has no `seed_n` / gate-rate parameters.

### Step 4 — Enum + precedence ladder in recommend (GREEN)
- `harpyja/eval/recommend.py`:
  - Add `class OQ2Outcome(str, Enum)` with the five members above.
  - `Recommendation` gains `outcome: OQ2Outcome` and `reason: str` (exactly one reason
    string), appended last.
  - `SweepPoint` gains `scout_deep_degrade_rate: float | None = None` and
    `gate_false_escalation_correct_total: int = 0` (per-point degrade rate + per-point
    gate-rate reliability denom), appended last with defaults so existing constructors
    keep working.
  - `rank_sweep(points, eval_config, *, seed_n: int = ..., gate_false_escalation_rate: float | None = None, gate_false_escalation_correct_total: int = 0)`
    — new kwargs default so the existing `rank_sweep(pts, EvalConfig())` call sites stay
    green. Insert the **precedence ladder** BEFORE the existing separation logic:
    `under_n_floor → degraded_dominated → gate_quality_confounded → not_separable`,
    emitting the matching `OQ2Outcome` + one `reason`. Map the existing
    "alternative beats noise" and "incumbent validated within noise" branches to
    `OQ2Outcome.RECOMMENDATION` (both emit a concrete `(threshold, top_n)`); map the
    existing "no point clears the bar" branch to `OQ2Outcome.NOT_SEPARABLE`.
- Step-3 tests pass; all prior `test_recommend.py` tests stay green (defaults).

### Step 5 — Per-point degrade drop + quantified gate confound (RED)
- Extend `harpyja/eval/test_recommend.py`:
  - `test_rank_sweep_drops_per_point_degrade_dominated_from_comparison` — a clean
    incumbent plus a degrade-heavy alternative (`scout_deep_degrade_rate=0.8`) with a
    better false-escalation mean; the degrade-heavy point is dropped, so it is NOT the
    winner (incumbent validated instead). Asserts the degrade artifact cannot win.
  - `test_rank_sweep_all_points_degrade_dominated_is_degraded_dominated` — every point
    `scout_deep_degrade_rate > 0.5` ⇒ `OQ2Outcome.DEGRADED_DOMINATED`.
  - `test_gate_confound_fires_when_reliable_and_over_threshold` —
    `gate_false_escalation_rate=0.40`, `gate_false_escalation_correct_total=10` (≥5) ⇒
    `OQ2Outcome.GATE_QUALITY_CONFOUNDED`.
  - `test_gate_confound_suppressed_under_gate_rate_floor` — rate `0.90` but
    `correct_total=3 (<5)` ⇒ NOT confounded (no firing on noise; falls through to the
    separation outcome).
  - `test_gate_confound_not_fired_below_threshold` — rate `0.20`, `correct_total=10` ⇒
    NOT confounded.
- Tests fail: per-point drop + reliable-and-over-threshold confound logic not yet
  implemented.

### Step 6 — Implement per-point drop + confound firing (GREEN)
- `harpyja/eval/recommend.py`:
  - Before ranking, drop survivors whose `scout_deep_degrade_rate is not None and
    > eval_config.degraded_dominated_threshold`. If the drop empties the comparison set
    (and points existed), emit `DEGRADED_DOMINATED`.
  - `gate_quality_confounded` fires only when
    `gate_false_escalation_rate is not None AND gate_false_escalation_correct_total >= eval_config.gate_rate_n_floor AND gate_false_escalation_rate > eval_config.gate_confound_threshold`.
  - `under_n_floor` when `seed_n < eval_config.n_floor`.
  - All ordered by the Step-4 precedence ladder.
- Step-5 tests pass.

### Step 7 — Refactor: single-source precedence table (optional)
- `harpyja/eval/recommend.py`: collapse the four null checks into one ordered
  `_NULL_PRECEDENCE` sequence of `(predicate, OQ2Outcome, reason_builder)` that
  `rank_sweep` iterates, so the executor derives the precedence FROM one table rather
  than re-deriving it inline (mirrors the conventions "routing matrix is the single
  source of truth" rule). All Step 3/5 tests still pass.

### Step 8 — Schema bump pin + sweep provenance fields (RED)
- Extend `harpyja/eval/test_report.py`:
  - Replace `test_report_schema_version_is_0013` with `test_report_schema_version_is_0015`
    asserting `SCHEMA_VERSION == "0015/1"`. **(This is the spec-0014 schema-pin hit — see Risk.)**
  - Add `test_report_schema_version_bumped_past_0013` asserting `SCHEMA_VERSION != "0013/1"`.
  - `test_run_metadata_records_gate_confound_knobs` — a legacy block omitting the knobs
    still validates (defaults), and a populated block carries `gate_confound_threshold`
    / `gate_rate_n_floor`.
- Extend `harpyja/eval/test_sweep.py`:
  - `test_sweep_report_records_selected_grid_k_n` — `run_metadata` carries the selected
    grid (thresholds × top_ns), `k_runs`, `seed_n`, `n_floor`.
  - `test_sweep_report_records_three_thresholds` — `degraded_dominated_threshold`,
    `gate_confound_threshold`, `gate_rate_n_floor` recorded.
  - `test_sweep_report_records_subset_identity_and_revs` — passing a fixture
    `subset_identity` (12 repos + case commits + per-repo case counts) is echoed into the
    report (AC1 reproducibility).
  - `test_sweep_report_records_air_gap_provenance` — report records provisioning as
    staged dev-time clone and the measured run as loopback-only / no non-loopback egress
    (AC1/AC2).
  - `test_sweep_recommendation_carries_outcome_and_reason` —
    `rep["recommendation"]["outcome"]` is one of the enum values and there is exactly one
    `reason`.
- Tests fail: `SCHEMA_VERSION` still `0013/1`; new run_metadata / recommendation fields absent.

### Step 9 — Report defaults bump + sweep wiring (GREEN)
- `harpyja/eval/report.py`: bump `SCHEMA_VERSION = "0015/1"`; append
  `gate_confound_threshold: None` and `gate_rate_n_floor: None` to `_RUN_METADATA_DEFAULTS`
  (last, so legacy `0013/1` blocks still validate through the one loud validator).
- `harpyja/eval/sweep.py`:
  - Build each `SweepPoint` with `scout_deep_degrade_rate` (from the per-run aggregate
    scout∪deep degrade union mean) and `gate_false_escalation_correct_total`.
  - Compute the global gate false-escalation rate + `correct_total` from the per-run
    aggregates and thread them, plus `seed_n=len(cases)`, into `rank_sweep`.
  - Accept an optional `subset_identity` parameter and record into `run_metadata`:
    selected grid, `k_runs`, `seed_n`, `n_floor`, the three thresholds,
    `subset_identity` (repos + revs + per-repo case counts), `provisioning_mode =
    "staged-dev-time-clone"`, `egress = "loopback-only"`.
  - Emit `recommendation.outcome` (enum `.value`) + `recommendation.reason`.
- Step-8 tests pass; existing `test_sweep.py` / `test_report.py` stay green (defaults).

### Step 10 — Integration scaffold for the 12-repo sweep (RED)
- Extend `harpyja/eval/test_swebench_integration.py` (all `@pytest.mark.integration`,
  **skip-not-fail** via `pytest.skip(_NEEDS_STACK)` / missing `HARPYJA_N12_FIXTURES`,
  reusing the existing `_deny_nonloopback_egress` guard):
  - `test_n12_sweep_provisions_and_runs_auto_to_completion` — drives the operator
    entrypoint over the provisioned 12-repo subset; asserts no crash (0014 Deep fix holds
    at scale) and the report pins subset identity + revs + per-repo case counts (AC1).
  - `test_n12_sweep_trade_off_table_mean_spread_over_k` — sweep report has the
    threshold×top_n table with mean+spread per point; `seed_n ≥ n_floor` ⇒ not
    `indicative_only` (AC2).
  - `test_n12_sweep_degraded_dominated_withholds_as_finding` — when degrade-dominated,
    OQ2 is withheld and the run is a finding (`OQ2Outcome.DEGRADED_DOMINATED`), gate not
    bypassed (AC3).
  - `test_n12_sweep_air_gap_no_nonloopback_egress` — measured run asserts no non-loopback
    egress under `_deny_nonloopback_egress` (AC1/AC2).
  - `test_n12_tier0_alone_accuracy_and_fc_citation_shape_recorded` — Tier-0-alone
    accuracy + `fc_citation_*` shape distribution recorded across all 12 repos (AC6).
- Tests fail (or skip): the operator entrypoint referenced by the scaffold does not yet
  exist (`AttributeError`/`ImportError`) when fixtures ARE present; skip cleanly when absent.

### Step 11 — Operator entrypoint + runbook (GREEN)
- Add the operator-driven entrypoint (e.g. `harpyja/eval/live.py::run_oq2_sweep` + a
  `make oq2-full` target) that: provisions the predeclared 12-repo subset via the
  EXISTING staged dev-time `provision` (network clone — outside the runtime air-gap),
  pins subset identity + revs + per-repo case counts, runs the Stage-1 coarse grid
  `{0.5,0.6,0.7,0.8} × {1,3,5}` at K=3 with the predeclared REFINE→Stage-2(K=5)/STOP
  protocol, calls `run_sweep` (which asserts loopback-only on the measured phase), and
  writes `sweep.json` OUTSIDE every target tree.
- Record the predeclared grid / K / refine / stop rule + the three thresholds in the
  runbook (the actual hours-long live run is operator-driven, NOT a CI run).
- Step-10 integration tests now exercise the wired path end-to-end with the
  deterministic/injected stand-ins where the live model is unavailable, still skipping
  cleanly without fixtures.

### Step 12 — AC8 regression for the None-gate-rate sink (RED → GREEN)
- RED — `harpyja/eval/test_recommend.py`:
  `test_rank_sweep_handles_none_gate_rate_without_crash` — `gate_false_escalation_rate=None`
  (zero `correct_total`, the null-with-count shape the metrics already return) must NOT
  crash the confound check and must NOT fire `gate_quality_confounded` (a null rate
  cannot trip the flag). Fails if the confound predicate does arithmetic on `None`.
- GREEN — `harpyja/eval/recommend.py`: guard the confound predicate on
  `gate_false_escalation_rate is not None` first (the `int|None`/null-with-count
  consumer discipline). This is the concrete AC8 instance; any FURTHER defect surfaced at
  scale gets its own `test_<defect>_regression` before the run is declared complete.

## Delegation

- Steps 1–7, 12 (pure-unit honesty machinery) → keep on `tdd-implementer` / `python-pro`
  (tight `harpyja/eval` unit surface, no live deps).
- Steps 8–9 (schema ratchet + report wiring) → `python-pro` with care on the
  `SCHEMA_VERSION` pin ratchet (see Risk).
- Steps 10–11 (integration scaffold + operator runbook + the live 12-repo run) →
  operator-driven; the agent produces the runbook/entrypoint and skip-not-fail scaffold,
  NOT a CI execution of the hours-long sweep.

## Risk

- **Schema-version-pin (spec-0014 class) → HIGH.** Adding `gate_confound_threshold` /
  `gate_rate_n_floor` to `_RUN_METADATA_DEFAULTS` forces `SCHEMA_VERSION` `0013/1 → 0015/1`,
  which trips the exact pin `test_report_schema_version_is_0013`. Mitigation: ratchet in
  the SAME change — update the exact pin to `_is_0015` AND add
  `test_report_schema_version_bumped_past_0013`; keep new fields last-with-defaults so
  legacy `0013/1` blocks still pass the one loud `validate_report`. This is Step 8/9 and
  must not be split.
- **Variance comparator assumes comparable per-point spread → MED.** Mitigation:
  constant-K-within-stage is predeclared (K=3 Stage-1, K=5 Stage-2); a Stage-2 point is
  never compared against a Stage-1 point at a different K.
- **`int|None` / null-with-count gate-rate sink → MED.** A zero-denominator gate rate is
  `None`; an unguarded confound check would crash or fire on noise. Mitigation: Step 12
  guards `is not None` AND the reliability floor (`correct_total >= gate_rate_n_floor`).
- **Post-hoc search tuning invalidates the evidence → MED.** Mitigation: the grid, K, and
  refine/stop rule are predeclared in the runbook (Step 11) BEFORE the run; the operator
  cannot widen the search after seeing data.
- **Operator-run not in CI → LOW (by design).** The hours-long live `mode=auto` run is
  operator-driven; the integration scaffold skips-not-fails without fixtures, so CI stays
  green while the runbook drives the real measurement.
