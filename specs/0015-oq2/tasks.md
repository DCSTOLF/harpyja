---
spec: "0015"
---

# Tasks

> **REVERTED on close (spec failed).** T1–T12 below were implemented and green in the
> working tree, but the OQ2 run could not complete (B1/B2/B3, see changelog.md) so the
> entire implementation was **reverted to HEAD**. The tasks are retained for the record
> only — the code they describe is NOT in the tree. The one salvaged change is the B0
> provision fix (`test_provision_relative_work_dir_resolves_to_real_worktrees`), which
> is not in this list.

- [x] T1 — RED: EvalConfig confound knobs (`gate_confound_threshold` / `gate_rate_n_floor`) in `test_config.py`
- [x] T2 — GREEN: add both knobs to `config.py::EvalConfig` (last, eval-only, disjoint from Settings)
- [x] T3 — RED: `OQ2Outcome` enum + precedence + exactly-one-reason tests in `test_recommend.py`
- [x] T4 — GREEN: enum + `Recommendation.outcome/reason` + `SweepPoint` new fields + `rank_sweep` precedence ladder in `recommend.py`
- [x] T5 — RED: per-point degrade drop + quantified gate-confound firing tests in `test_recommend.py`
- [x] T6 — GREEN: per-point degrade drop, reliable-and-over-threshold confound, under_n_floor in `recommend.py`
- [x] T7 — REFACTOR (optional): SKIPPED — precedence is the authoritative ordered-returns sequence (test-locked + enum-docstring documented); a table would add indirection for no behavioral gain
- [x] T8 — RED: schema-version pin ratchet + sweep provenance-field tests in `test_report.py` / `test_sweep.py`
- [x] T9 — GREEN: bump `SCHEMA_VERSION` 0013/1→0014/1 + `combined_degrade_rate` field; sweep records grid/K/N/thresholds/subset/air-gap + outcome/reason
- [x] T10 — RED: sibling-lock unit tests (`run_swebench_sweep` outcome/provenance) + `@pytest.mark.integration` skip-not-fail 12-repo scaffold (AC1/2/3/6)
- [x] T11 — GREEN: sibling `run_swebench_sweep` wiring + operator entrypoint `run_oq2_sweep` + `make oq2-full` + predeclared `RUNBOOK.md`
- [x] T12 — RED→GREEN: AC8 regression — None-gate-rate confound sink guarded + locked in `recommend.py`
