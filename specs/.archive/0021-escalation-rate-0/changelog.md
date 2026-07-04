---
spec: "0021"
closed: 2026-07-04
---

# Changelog — 0021 escalation_rate=0

## What shipped vs spec

- A **metric-integrity diagnostic** in the 0019/0020 measurement-not-construction
  lineage. The deliverable is a RECORDED TYPED FINDING (`findings.md`), not a feature;
  the SUT (`harpyja/orchestrator/` tiers/gate/matrix/judge) was **NOT modified** —
  read-only reference only. All new code is additive under `harpyja/eval/`.
- **Accounting axis = `CORRECT_NO_ESCALATION` (PROVEN).** `escalation_rate` is derived
  (`metrics.py:126,129` `mean(2 in o.tiers_run)`) with no rival counter; the
  `tiers_run ⇄ escalation_rate` coupling is PINNED by 3 new tests, all GREEN against the
  frozen metric — no accounting bug, no production change. `escalation_rate=0` is a
  faithful no-escalation, not a lost count.
- **Wrong-citation-fate axis** (the 38 point cases, all wrong-or-empty since
  `correct_tier1_count=0`): **33 empty → `NO_ESCALATION_PATH`, CONFIRMED** by reading the
  frozen `_locate_auto:161-165` (empty Tier-1 → `_honest_empty`, gate-skipped,
  `tiers_run=[0,1]`, "Never escalates"); **5 wrong-content → `GATE_FALSE_ACCEPTANCE` |
  `DEEP_DEGRADED_OR_UNAVAILABLE`, UNDETERMINED** (per-case dump gone; resolvable only by a
  served-model micro-run).
- **3.3h attribution = LABELED ESTIMATE.** The 0020 per-case dump is ABSENT
  (`eval_work/reports/oq2_{fast,incumbent}/` empty; `eval_work/` gitignored; secondaries
  live only in the operator transcript). The sink is Scout FastContext exploration × 38
  cases (~5.2 min/case), NOT Deep (`escalation_rate=0`). The total anchors on the recorded
  wall-clock; the per-tier split is labeled an estimate.
- **Metric-trust verdict (AC5):** TRUST `escalation_rate=0`, `correct_tier1_count=0`,
  `gate_false_escalation=null`; treat `wrong_tier1_count=5`, `span_hit_rate_primary=0.2`,
  `gate_catch_rate` as CONTAMINATED — the next spec must regenerate them, not inherit them
  (the transcript's "5" is inconsistent with the aggregate lens, which counts empties as
  wrong → would be 38).
- The 0020 **DEFERRED** verdict is unchanged (`correct_tier1_count=0` is independent).

## Deviations

- **Plan AC2 assumption corrected mid-implement.** The plan assumed honest-empty Tier-1
  escalates (point-auto ladder `[0,1,2]`); reading the frozen `_locate_auto` showed
  `_honest_empty` is gate-skipped and never reaches Tier-2. The classifier gained a
  `tier1_empty` parameter and `test_escalation_trigger.py` was written to pin the ACTUAL
  frozen behavior (`tier1_empty=True → NO_ESCALATION_PATH`) — a test asserting a false
  claim about the SUT is worse than none.
- `classify_escalation` signature is `(*, tier1_correct, gate_rejected, deep_available,
  ladder, tier1_empty=False)` (the plan omitted `tier1_empty`).
- Unit suite **820 → 835** (+15), ruff clean, 1 integration skip-not-fail (T6 live
  micro-run, gated on served models).

## Files touched

- `harpyja/eval/escalation.py` (NEW, 84 lines) — `WrongCitationFate` enum + pure
  `classify_escalation(...)`, a faithful projection of the frozen `_locate_auto`
  escalation decision (ladders passed IN, never re-derives `plan_ladder`).
- `harpyja/eval/test_escalation_trigger.py` (NEW, 7 tests) — the four-way trigger truth
  table; every ladder obtained by CALLING `harpyja.orchestrator.matrix.plan_ladder`, with
  a regression guard asserting the test ladders equal `plan_ladder(...)`.
- `harpyja/eval/escalation_microrun.py` (NEW, 133 lines) — additive instrumented ≤2-case
  micro-run: `_wrap_timed` / `build_micro_result` (labels the per-tier split `"estimate"`,
  flags `deep_degraded`) / `run_escalation_microrun`; timing attributed at the eval
  boundary, no orchestrator edit.
- `harpyja/eval/test_escalation_microrun.py` (NEW, 5 unit + 1 integration skip-not-fail).
- `harpyja/eval/test_metrics.py` — +3 tests pinning the `tiers_run ⇄ escalation_rate`
  coupling (novel: the coupling, not the plain rate).
- `specs/0021-escalation-rate-0/findings.md` — THE deliverable.
