---
spec: "0009-6a"
closed: 2026-06-28
---

# Changelog — 0009-6a Wave 6a — Eval harness + OQ2 calibration

## What shipped vs spec

A new **measurement-only** package `harpyja/eval/` that observes the real
`mode=auto` `locate()` path and reports locate accuracy, escalation, and gate
catch / false-escalation metrics, plus an OQ2 `(verify_threshold, verify_top_n)`
recommendation. It never modifies tier/gate/matrix behavior and **flips no
`Settings` default** (B1 — recommend-only; the flip is a future one-line follow-up
spec). All 21 tasks shipped TDD-complete; every AC (AC1–AC8) is realized.

Modules:
- `dataset.py` — `EvalCase` / `ExpectedSpan` / `load_dataset`, loud `DatasetError`
  (no silent skip; AC1, D1).
- `metrics.py` — ONE overlap oracle `_any_primary_overlap` reused by span-hit,
  gate catch-rate, and false-escalation (D3/D5); gate metrics scoped to the
  point-query subset only, broad excluded (D1); null-with-count sentinel on a zero
  denominator (D2). `CaseOutcome` carries both `tier1_citations` (gate oracle) and
  `final_citations` (accuracy) so escalation does not erase the Tier-1 signal.
- `config.py` — frozen `EvalConfig` (k_runs / proximity_window_lines / n_floor /
  catch_rate_bar), **disjoint from `Settings`**; `aggregate_runs` → `{mean, spread=
  pstdev}` (AC5, D6).
- `report.py` — pinned D7 JSON schema + `validate_report` (loud `ReportSchemaError`)
  + `atomic_write_json` that REFUSES to write inside the indexed repo (read-only
  guardrail; mirrors the FastContext `trajectory_file`-outside-repo precedent;
  AC4/AC7).
- `runner.py` — drives the real `locate()` via an injected `LocateStack`; captures
  Tier-1 citations independently of escalation by calling Scout directly on point
  cases (the gate replaces citations when it escalates); `build_live_stack`
  real-factory helper (AC4/AC7).
- `recommend.py` — D3 variance rule `mean(A)-mean(B) > pstdev(B)` vs the incumbent
  spread + D4 lexicographic OQ2 scorer (clear catch-rate ≥ bar → minimize
  false-escalation → tie-break lower top_n → lower threshold); incumbent `(0.6, 3)`
  is displaced only past the noise margin, else recorded VALIDATED (AC5/AC8).
- `sweep.py` — grid via `dataclasses.replace`, never mutation; K runs/point;
  per-point mean+spread (AC6/AC8).
- `live.py` — live `run_live_eval` / `run_live_sweep` entrypoints.
- `fixtures/` — small vendored `legacy/` repo + hand-labeled `seed.jsonl`.

Pinned provisional magnitudes (D6, all on `EvalConfig`, marked tunable as N grows):
`N_FLOOR=30`, `PROXIMITY_WINDOW_LINES=50`, `CATCH_RATE_BAR=0.90`, `k_runs=5`.

## Deviations from spec/plan

1. **K-placement.** The spec body originally said "additive eval-only `Settings`
   field carrying K." A plan-time decision moved K (and the proximity window,
   N-floor, catch-rate bar) to a dedicated `EvalConfig` dataclass — a cleaner
   INVARIANT: eval-only knobs never reach the system under test, and only
   `verify_threshold` / `verify_top_n` (the real SUT fields the sweep overrides via
   `dataclasses.replace`) ever touch `Settings`. The spec line was reconciled.
   Non-controversial; recorded as a resolved design decision and asserted by
   `test_eval_config_is_independent_of_settings`.
2. **Seed fixture size.** The shipped seed is a **5-case starter** over one small
   vendored `legacy/` repo — not the 30+ case OSS legacy tree D1 envisions. That
   curation was explicitly delegated in the plan (label-authoring work, separable
   from harness code). The harness + metrics are real and live-verified; the dataset
   is seed-sized and every report says so (`indicative_only: true`).

## OQ2 resolution (the honest outcome)

**OQ2 = instrument built + live-validated; calibration deferred to a larger seed.**

The eval harness runs live and produces a recommendation, but the shipped seed is a
5-case starter (N=5 ≪ the pinned `N_FLOOR=30`). So every run over it is correctly
flagged `indicative_only=true`, and the incumbent `(verify_threshold=0.6,
verify_top_n=3)` is **NOT displaced**. OQ2 therefore resolves as: harness validated
live; incumbent held under an indicative-only seed; the provisional `0.6/3` and the
`0.90` catch-rate bar remain provisional. A real calibration (a recommendation that
could justify a default flip) requires the larger curated D1 dataset (a vendored OSS
legacy repo with ≥30 hand-labeled cases), which the plan explicitly delegates. **No
`Settings` default was changed** (correct per B1). This is recorded as a partial
resolution — NOT a fabricated tuning result. The Wave-5 open item "OQ2
`verify_threshold` tuning vs eval repo" is now **partially resolved**: the instrument
exists; tuning awaits N ≥ 30.

## Verification status

- **557 unit tests pass** (+58 new in `harpyja/eval/`), ruff clean across the
  package.
- **5 integration tests** (AC7 ×3 + AC8 ×2) **PASSED LIVE in 634s (10.5 min)** —
  real FastContext Scout + `scout_model` gate judge + Deep over Ollama
  (`qwen2.5-coder:3b`) + Deno + rg. Genuinely verified, not skipped.

## Files touched

- `harpyja/eval/__init__.py`
- `harpyja/eval/dataset.py` (+ `test_dataset.py`)
- `harpyja/eval/metrics.py` (+ `test_metrics.py`)
- `harpyja/eval/config.py` (+ `test_config.py`)
- `harpyja/eval/report.py` (+ `test_report.py`)
- `harpyja/eval/runner.py` (+ `test_runner.py`)
- `harpyja/eval/recommend.py` (+ `test_recommend.py`)
- `harpyja/eval/sweep.py` (+ `test_sweep.py`)
- `harpyja/eval/live.py`
- `harpyja/eval/test_eval_integration.py`
- `harpyja/eval/fixtures/` — `README.md`, `seed.jsonl`, vendored `legacy/`
  (`auth.py`, `main.py`, `net/retry.py`)

## ADR proposed for history.md

2026-06-28 — Wave 6a eval harness shipped (applied to history.md).

## Conventions proposed

- New: a measurement/eval harness observes the SUT through its real public seam and
  never mutates its config; eval-only knobs live on a dedicated config disjoint from
  the production frozen `Settings`; harness artifacts write outside the indexed repo;
  one oracle defines correctness for every derived metric; small-N results are
  self-flagged `indicative_only`. (Applied to conventions.md.)

## Architecture update

- New layer entry for `harpyja/eval/` — a measurement harness, not a runtime tier.
  (Applied to architecture.md.)

## Remaining follow-ups

- **Larger D1 dataset** (vendored OSS legacy repo, ≥30 hand-labeled cases) → a real
  OQ2 calibration → a potential default flip in a follow-up spec. Until then the seed
  is `indicative_only` and `(0.6, 3)` is held, not validated-at-scale.
- **`per_tier_model_calls`** is currently honest-`None` (no model-call counter is
  wired through `LocateStack`); it is a present-but-null field, not a false zero.
- Still open from earlier waves: **Wave-2.1 substring/fuzzy matching**.
