---
spec: "0014"
---

# Tasks

- [x] P1 — RED: `test_deep_unavailable_parse_error_cause_is_stable` in `harpyja/deep/test_deep.py` (AC2)
- [x] P2 — GREEN: add `PARSE_ERROR = "parse-error"` to `harpyja/deep/errors.py` (AC2)
- [x] P3 — RED: RLM seam tests in `harpyja/deep/test_deep.py` — parse-error maps, cause preserved, unrelated not swallowed, weak stays result, no top-level dspy import (AC1, AC3, AC4, AC9)
- [x] P4 — GREEN: narrow lazy `except _adapter_parse_error_types()` wrap of the `rlm(query=...)` call in `harpyja/deep/rlm.py` (AC1, AC3, AC4, AC9)
- [x] P5 — RED→GREEN lock: `test_locate_deep_parse_error_degrades_to_scout` + distinct-cause-note in `harpyja/orchestrator/test_locate.py`; proves routing needs no change (AC1, AC2, AC5)
- [x] P6 — RED: schema-version-0013 + deep-degrade-fields + both-shapes-validate tests in `harpyja/eval/test_report.py` (AC6, AC7, AC10)
- [x] P7 — GREEN: bump `SCHEMA_VERSION="0013/1"`, append `deep_degrade_count`/`deep_degrade_rate` to `_AGGREGATE_FIELDS` + `_AGGREGATE_DEFAULTS` in `harpyja/eval/report.py` (AC6, AC7, AC10)
- [x] P8 — RED: runner deep-degrade count/rate, null-on-zero, and both-tiers-counted-once tests in `harpyja/eval/test_runner.py` (AC6, AC11)
- [x] P9 — GREEN: add `_is_deep_degraded` + compute `deep_degrade_*` and union-based `degraded_dominated` in `aggregate_outcomes` (`harpyja/eval/runner.py`) (AC5, AC6, AC11)
- [x] P10 — RED→GREEN lock: swebench sibling populates deep-degrade fields + dominance in `harpyja/eval/test_swebench_runner.py` (no driver change; grep-gate consumers) (AC7, AC11)
- [x] P11 — RED→GREEN integration (skip-not-fail): `test_deep_auto_parse_error_degrades_not_crash` with injected AdapterParseError fault in `harpyja/deep/test_deep_integration.py`; auto-mode completes, degrade recorded (AC8)
- [x] P12 — REFACTOR: share the degrade-note predicate across scout/deep; full `pytest harpyja -q` green
- [x] P13 — CLOSE DELIVERABLE: `memory-keeper` records the "every typed-degrade floor reports its rate + feeds degraded_dominated" convention in `.speccraft/conventions.md` (AC12)
