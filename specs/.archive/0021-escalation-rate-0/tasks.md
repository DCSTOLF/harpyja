---
spec: "0021"
---

# Tasks

- [x] T0 — [INVESTIGATION] Path the 0020 per-case dump; recorded ABSENT in findings.md (oq2_fast/oq2_incumbent empty; only oq2_smoke survives, escalation_rate=1.0 there; G2 secondaries in no committed file) → AC3 labeled estimate [gates AC3/AC4]
- [x] T1 — [RED→PIN] Extended test_metrics.py: tiers_run⇄escalation_rate coupling (3 new tests) — PASS against frozen metric (no accounting bug) [AC1]
- [x] T2 — [GREEN/PIN] Coupling holds; NO prod change → accounting = CORRECT_NO_ESCALATION [AC1/AC4-accounting]
- [x] T3 — [RED] Added test_escalation_trigger.py: 7 tests, ladders derived from plan_ladder — RED (ModuleNotFoundError) [AC2]
- [x] T4 — [GREEN] Implemented harpyja/eval/escalation.py: WrongCitationFate enum + pure classify_escalation(...) — 7/7 pass, ruff clean [AC2]
- [x] T5 — [REFACTOR] No-op: no shared-builder duplication (test_metrics._outcome stays local; trigger test needs none); ruff clean [AC1/AC2]
- [x] T6 — [RED] Added test_escalation_microrun.py: unit tests (instrumentation + rate reproduction) + skip-not-fail live test — RED (ModuleNotFoundError) [AC3]
- [x] T7 — [GREEN] Implemented harpyja/eval/escalation_microrun.py: additive _wrap_timed + build_micro_result + run_escalation_microrun, labeled "estimate", no orchestrator edit — 5 pass/1 skip, ruff clean [AC3]
- [x] T8 — [DOC] Authored findings.md: accounting=CORRECT_NO_ESCALATION (proven); fate=33 empty NO_ESCALATION_PATH (confirmed) + 5 wrong undetermined (dump gone); 3.3h→Scout labeled estimate; metric-trust verdict (wrong_tier1_count=5 contaminated — inconsistent with aggregate=38); DEFERRED unchanged [AC4/AC5]
