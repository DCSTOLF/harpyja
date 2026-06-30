---
spec: "0012"
---

# Tasks

- [x] T1 — RED: suffix-recovery core tests in `scout/test_scout_normalize.py` (unique keep / safe-drop / interior / ambiguous / <2-seg / leading-segment guard / re-validate-clamp) — AC1, AC2, AC3(a–e)
- [x] T2 — GREEN: `scout/normalize.py` `file_set` param + `_recover_suffix` + `MIN_TAIL_SEGMENTS` + 4-tuple return; update `normalize_spans` caller — AC1, AC2, AC3(a–e)
- [x] T3 — RED: honesty-floor guards — recovered file-level keeps `None` lines (`test_scout_normalize.py`) + `gate-skipped:no-line-range` / never-high in `orchestrator/test_locate.py` — AC3(f)
- [x] T4 — RED: `ScoutTally.recovered_*` + `ScoutEngine(file_set=…)` threading tests in `scout/test_scout.py` — AC4
- [x] T5 — GREEN: append `recovered_spanned`/`recovered_filelevel` to `ScoutTally`; add `file_set` to `ScoutEngine`, thread into `normalize_spans_with_tally` — AC4
- [x] T6 — RED: `build_scout_engine` loads manifest file set; empty when manifest absent (`scout/test_scout_wiring.py`) — AC4
- [x] T7 — GREEN: `scout/wiring.py` `read_manifest(art_dir)` → `frozenset(e.path)` → `ScoutEngine(file_set=…)` — AC4
- [x] T8 — RED: report `SCHEMA_VERSION == "0012/1"` + two recovered aggregate fields last-with-default + both-shape validation (`eval/test_report.py`) — AC4
- [x] T9 — GREEN: `eval/report.py` bump version; append `fc_citation_recovered_{spanned,filelevel}_count` to `_AGGREGATE_FIELDS`/`_AGGREGATE_DEFAULTS` — AC4
- [x] T10 — RED: `aggregate_outcomes` sums recovered counts (`eval/test_runner.py`); swebench driver carries them (`eval/test_swebench_runner.py`) — AC4
- [x] T11 — GREEN: `eval/runner.py::aggregate_outcomes` (+ `swebench_eval.py` pooling) emit `fc_citation_recovered_*` — AC4
- [x] T12 — REFACTOR: single `_recover_suffix` helper, shared return contract, `ruff` clean
- [x] T13 — RED (integration, skip-not-fail): N=12 Q8 override run writes `specs/0012-path-prefix/run_q8rl_recovery_n12.json` with pinned keys incl `recovered_filelevel_paths` + `baseline_ref`, recording delta vs `baseline_q8rl_n12.json`, `indicative_only` (`eval/test_swebench_integration.py`) — AC5
- [x] T14 — Verify: full unit suite green (`pytest harpyja/scout harpyja/eval harpyja/orchestrator`); `ruff check` clean
