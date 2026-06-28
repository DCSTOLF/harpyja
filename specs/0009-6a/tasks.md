---
spec: "0009-6a"
---

# Tasks

## Phase 1 — Dataset (AC1)

- [x] T1 — RED: `harpyja/eval/test_dataset.py` loader/reject tests (AC1)
- [x] T2 — GREEN: `harpyja/eval/dataset.py` `EvalCase` + `load_dataset` + `DatasetError` (AC1)

## Phase 2 — Metric / oracle layer (AC2, AC3)

- [x] T3 — RED: `harpyja/eval/test_metrics.py` span-hit primary/secondary boundary tests (AC2)
- [x] T4 — GREEN: `harpyja/eval/metrics.py` `span_hit_primary` / `span_hit_secondary` (AC2)
- [x] T5 — RED: `test_metrics.py` aggregate + gate metrics (point-scoped, same-oracle, any/any, null+count) (AC3, D1/D2/D5)
- [x] T6 — GREEN: `metrics.py` `escalation_rate` / `tier01_resolve_rate` / `gate_catch_rate` / `gate_false_escalation` / `tier1_correct` (AC3)

## Phase 3 — EvalConfig + repeated-run aggregation (AC5 part)

- [x] T7 — RED: `harpyja/eval/test_config.py` EvalConfig constants + Settings-independence + `aggregate_runs` mean/pstdev (AC5, D6)
- [x] T8 — GREEN: `harpyja/eval/config.py` `EvalConfig` + `aggregate_runs`; wire proximity window into secondary metric (AC5, D6)

## Phase 4 — Report schema (AC4, AC7)

- [x] T9 — RED: `harpyja/eval/test_report.py` schema fields, validate, null+count, artifact-outside-repo (AC4, AC7, D7)
- [x] T10 — GREEN: `harpyja/eval/report.py` schema + `build_report` / `validate_report` / `write_report` guard (AC4, AC7)

## Phase 5 — Runner over fakes (AC4)

- [x] T11 — RED: `harpyja/eval/test_runner.py` drives auto path via fakes, schema-conforming, outside-repo, gate-decision fields (AC4)
- [x] T12 — GREEN: `harpyja/eval/runner.py` `run_case` / `run_dataset` over injected fakes (AC4)

## Phase 6 — Recommend + sweep (AC5, AC6, AC8)

- [x] T13 — RED: `harpyja/eval/test_recommend.py` variance gate + lexicographic OQ2 scorer (AC5, AC8, D3/D4)
- [x] T14 — GREEN: `harpyja/eval/recommend.py` `prefer` + `rank_sweep` (AC5, AC8)
- [x] T15 — RED: `harpyja/eval/test_sweep.py` grid enumeration, `dataclasses.replace`, no-mutation, per-point mean+spread (AC6)
- [x] T16 — GREEN: `harpyja/eval/sweep.py` `run_sweep` (AC6)
- [x] T17 — REFACTOR: extract single overlap oracle + dedup per-case event assembly (AC2/AC3 integrity)

## Phase 7 — Integration (AC7, AC8)

- [x] T18 — RED: `harpyja/eval/test_eval_integration.py` e2e live, all-metrics-populated, air-gap (AC7, `@pytest.mark.integration`)
- [x] T19 — GREEN: `harpyja/eval/fixtures/` vendored repo + hand-labeled `seed.jsonl`; `build_live_fakes` live-build helper (AC7, D1)
- [x] T20 — RED: `test_eval_integration.py` live OQ2 sweep recommendation + N-floor caveat (AC8)
- [x] T21 — GREEN: live `eval` sweep entrypoint + N-floor caveat + changelog deliverable; NO `Settings` default flip (AC8, B1)
