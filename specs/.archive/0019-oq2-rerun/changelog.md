---
spec: "0019"
closed: 2026-07-02
---

# Changelog — 0019 OQ2 re-run — complete, prove the gate, then calibrate

## What this spec is (read this first)

A **measurement/eval** spec. The SUT (harpyja tiers / gate / matrix / judge) is
**FROZEN** — every change lands in `harpyja/eval/` (the harness), which is additively
extensible even under the measurement-not-construction invariant. This spec ships the
**gate-confound MECHANISM** and the **calibration INSTRUMENT** for the OQ2 re-run.

**It does NOT calibrate OQ2.** No OQ2 recommendation, no typed null, and no
`verify_threshold` tuning over the real N=12 subset was produced here — that is the
**operator sweep** (served models + `HARPYJA_N12_FIXTURES`), still pending. Do not read
this changelog as "OQ2 closed" or "B2 closed." astropy-12907 end-to-end is **not**
demonstrated here.

## What shipped vs spec

Baseline **757 → 777 unit pass (+20)**, ruff clean. All ACs' unit surfaces (AC2, AC5,
AC9, plus the schema/config/recommend units feeding AC1/AC4/AC6/AC7) are GREEN; the
G1/G2/G3 integration ACs (AC1/AC3/AC4/AC6/AC7/AC8/AC9 at scale) are `@pytest.mark.integration`,
skip-not-fail **operator demonstrations**, not CI-run.

- **Gate-confound ceiling (D2).** `EvalConfig.gate_false_escalation_ceiling = 0.20`
  (`config.py`) — a new eval-only, `Settings`-disjoint knob. The bar above which the
  gate is judged too unreliable to calibrate over. **Provisional** — a named bar, not a
  tuned prior; revisit once the instruct-judge score distribution is measured on real data.
- **Gate-confounded typed null (D2/AC9).** `recommend.py` gains
  `OUTCOME_RECOMMENDED` / `OUTCOME_GATE_CONFOUNDED`; an **additive** `Recommendation.outcome`
  + `.gate_false_escalation_measured` (appended last-with-defaults so every existing
  construction stays valid); `gate_confounded_recommendation(measured_rate, eval_config)`;
  and `recommend_oq2(points, measured_false_escalation, eval_config)` — the dispatcher.
  Measured instruct false-escalation **strictly `> ceiling`** → the `gate-confounded`
  typed null carrying the rate; otherwise defers to the **unchanged** `rank_sweep`.
  Boundary `== ceiling` is **not** confounded (strict `>`); `None` (unmeasured) defers.
- **Report schema 0013/1 → 0014/1 (AC5/AC6/D2).** Run-metadata `gate_false_escalation_ceiling`;
  aggregate `gate_confounded` (default `False`) / `gate_confounded_measured_rate` (default
  `None`) + the instruct/scout A/B twins (`gate_false_escalation_{instruct,scout}` +
  `_count` / `_total`), all null-with-zero-count defaults. Field names hoisted to a single
  `_GATE_CONFOUND_AGG_FIELDS` anti-drift source with a drift-guard test. Legacy 0013-shaped
  blocks still validate; round-trip preserves the typed null.
- **Preflight doctor (AC1/AC2/D4).** `swebench_eval.py` gains `PreflightError` +
  `preflight_models_present(settings, tags_payload, *, resolver=None)` — `assert_local`
  runs **FIRST** (no second outbound path), then a deduped required-tag membership check
  (`_required_model_tags`) raising and **naming** the first absent tag. It claims models
  are **"pulled"**, NOT co-resident-loadable, and explicitly names OOM as a G1-caught
  residual risk. Plus `cmd_preflight` + a `preflight` CLI subparser. Live preflight
  **PASSED** on this host (the three required tags are pulled).
- **One-oracle characterization lock (AC5).** `test_metrics.py` gains a lock proving both
  gate denominators (false-escalation vs catch-rate) flip with the single
  `_any_primary_overlap` oracle — no second correctness definition, null-with-zero-count
  preserved. No production edit (the behavior already existed).
- **Integration scaffolding (AC1/AC3/AC4/AC6/AC7/AC8/AC9).** `test_swebench_integration.py`
  gains skip-not-fail demonstrations: live preflight, G1 astropy-12907 smoke, G2
  gate-quality + A/B, G3 sweep-at-scale + OQ2-typed, reliability-gate. Sweep-scale ones
  gate on `HARPYJA_N12_FIXTURES`; each skip carries a diagnostic naming the missing
  precondition.

## Deviations (recorded honestly)

1. **Runner-wiring deviation — a plan under-scope, caught in implement.**
   `plan.md` scoped T11 as scaffolding-ONLY. But leaving `run_swebench_sweep` calling
   `rank_sweep` would have left the `gate-confounded` outcome **wired-but-dormant**,
   making AC9 aspirational. So `recommend_oq2` + the ceiling were wired **into** the sweep
   runner: when the base run uses the instruct judge, the **best-achievable** instruct
   false-escalation (min over measured grid points) is the G2 signal fed to `recommend_oq2`,
   and the ceiling is stamped into metadata + the outcome surfaced in the recommendation
   block. This stays **within** the measurement-not-construction invariant — the harness is
   additively extensible; the **SUT is untouched** — and was TDD'd with 3 new unit tests in
   `test_swebench_runner.py`. Framing: the plan under-scoped, the implement pass caught it,
   the fix honored the frozen-SUT boundary.
2. **Honest scope — mechanism + instrument shipped; OQ2 NUMBERS pending.** This spec ships
   the gate-confound mechanism and the calibration instrument. The actual OQ2
   recommendation / typed null over the real N=12 subset requires the **operator** to run
   the sweep with `HARPYJA_N12_FIXTURES` + served models. G1/G2/G3-at-scale are
   demonstrations, not CI-run. Preflight passed live; the sweep-scale ACs are operator-gated.
   astropy-12907 end-to-end pass is **not** demonstrated here (the fixture set may not
   include it). **OQ2 is not calibrated.**
3. **Provisional ceiling.** `gate_false_escalation_ceiling = 0.20` is a named bar, not a
   tuned prior — eval-only, revisit once the instruct-judge score distribution is measured
   on real data.

## Files touched

- `harpyja/eval/config.py`
- `harpyja/eval/recommend.py`
- `harpyja/eval/report.py`
- `harpyja/eval/swebench_eval.py`
- `harpyja/eval/test_config.py`
- `harpyja/eval/test_metrics.py`
- `harpyja/eval/test_recommend.py`
- `harpyja/eval/test_report.py`
- `harpyja/eval/test_swebench_eval.py`
- `harpyja/eval/test_swebench_integration.py`
- `harpyja/eval/test_swebench_runner.py`

(No file outside `harpyja/eval/` changed — the SUT is frozen.)

## ADR proposed for history.md

See the proposed `2026-07-02 — Spec 0019 (oq2-rerun)` block returned to the operator for
apply (not written here).

## Conventions proposed

- **New (strongest):** a best-effort recommender REFUSES to calibrate a parameter over a
  measurement instrument it has measured to be unreliable — it emits a typed *confound*
  null carrying the measured rate, rather than tuning over a broken upstream signal.
- **New (candidate):** a mechanism/outcome added to the harness must be **wired into the
  real run path**, not left dormant — a wired-but-dormant branch makes its AC aspirational.
- **New (candidate):** a preflight/doctor probe asserts a precondition at **SETUP, loudly**
  (not mid-run discovery), routes through the **single sanctioned seam** (`assert_local`
  first, no second outbound path), and claims only what it verified (**"pulled"**, never
  co-resident-loadable — OOM named as residual risk).
- **Already covered (propose nothing):** one-oracle-per-metric + explicit denominators
  (existing "One oracle defines correctness" convention); the `_GATE_CONFOUND_AGG_FIELDS`
  anti-drift hoist (existing "centralize the field set + its defaults" convention); the
  air-gap-in-one-place seam reuse (existing air-gap convention).

## Follow-ups carried forward

- The **actual operator OQ2 sweep** (served models + `HARPYJA_N12_FIXTURES`): produce the
  real recommendation OR typed null over the N=12 subset.
- **Permanent ceiling calibration** — replace the provisional 0.20 with a data-driven bar
  once the instruct-judge score distribution is measured.
- **astropy-12907 end-to-end proof** (the B2 accuracy deferral, still not discharged).
- **Per-span non-conformance abstain** (0018 D7 chose whole-gate degrade).
- **Permanent `lm_model` choice** (Qwen3-8B provisional; judge inherits it).
- **Q8 model footprint / co-residency** (OOM under `mode=auto`; the preflight "pulled ≠
  loadable" residual risk).
- Still open from Wave 2: **Wave-2.1 substring/fuzzy matching**.
