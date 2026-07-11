---
id: "0039"
spec: "0039"
---

# Tasks

- [x] T1 — RED: config + hash tests, model tag & factor-(b) predicate & fixed conceptual floor pinned (AC1)
- [x] T2 — GREEN: implement `PREREGISTERED_AB_CONFIG_0039` + hash, OQ1/OQ2 frozen, asymmetry rationale in docstring (AC1)
- [x] T3 — RED: total-pure verdict grid, CONFOUNDED-first, under-floor→UNDER_POWERED, 0026 oracle + benchmark_fit reuse (AC1, AC2)
- [x] T4 — GREEN: implement `decide_ab_verdict` / `AbVerdict` / `PairRecord` (AC1, AC2)
- [x] T5 — RED: two-factor distinctness guard — off-arm-reasoning excludes, factor-(b) aggregate predicate, asymmetry kept, ceiling→CONFOUNDED (AC3)
      *(deviation: `classify_pair_validity` landed in T4 — T3's totality sweep required CONFOUNDED to be reachable — so T5's tests pinned behavior rather than starting red; two arrived red on the missing import and the factor-(b) misfire guard forced the `factor_b_min_on_reasoning_chars` config field, added pre-commit under freeze-before-run)*
- [x] T6 — GREEN: implement `classify_pair_validity` + exclusion/invalid-rate wiring into CONFOUNDED (AC3)
- [x] T7 — RED: reachability split, lexical `STRATUM_UNDER_POPULATED`, unified `AbReport` taxonomy, no whole-set headline (AC4, AC7)
- [x] T8 — GREEN: implement `decide_ab_report` + `AbReport` (split, symbols/cost/degrade slots) (AC4)
- [x] T9 — RED: AC5 upper-bound feasibility pre-check — explicit formula, first-10 conceptual subset, degrade projection, archive-first load, STOP gates run (AC5)
- [x] T10 — GREEN: implement `ab_power_precheck` with power arithmetic + cross-model caveat stated (AC5)
- [x] T11 — RED: resumable ledger, STOP-AND-WARN preflight (served-tag), two-call seed-honoring probe, strict skip→hard-fail (AC6)
- [x] T12 — GREEN: implement `AbLedger` + `ab_preflight` + `seed_honoring_probe` + `require_live_stack` (AC6)
- [x] T13 — RED: live paired run integration (skip-not-fail), precheck-gated N/A-on-branch (AC6)
- [x] T14 — GREEN: implement `run_ab_paired` + committed strict `run_thinking_ab.sh` driver (AC6)
      *(branch note: the driver RAN LIVE and exited 2 with the typed stop — the AC5 gate fired
      `UNDER_POWERED_STOP` on committed evidence (projected conceptual upper bound 6 < floor 8), so
      the live paired arms are N/A-on-branch by design; the PROCEED path is fully implemented and
      auto-activates when a pool enlargement flips the committed pre-check. Seed note: the explorer
      request path carries no `seed` param — wiring it is a SUT change deferred to the re-run spec;
      the config's `seed_honoring="unverified"` claim stands, recorded in findings.md)*
- [x] T15 — RED: committed claim artifact — matches computed verdict, archive-first pin, split-by-reachability (AC7)
- [x] T16 — GREEN: emit `specs/0039-thinking-ab/claim.json` + archive-first loader; UNDER_POWERED_STOP on gated branch (AC7)
- [x] T17 — DOC: `findings.md` causation stance — N=2 motivation-only, first powered read, no default-flip, observational True reported observational-only (AC8)
- [x] T18 — REFACTOR: consolidated the located predicate into `think_ab.located_via_oracle` (one oracle home for verdict + pre-check); further cross-module path-resolver consolidation skipped to avoid touching pinned 0038 code (all ACs)

## Verification

- Spec tests: 37 passed (unit + the integration test, which asserts the gated branch on committed evidence).
- Full unit suite: 1280 passed / 1 skipped (the standing superseded-0037 conditional) / 58 deselected.
- Ruff: zero-new (36 = 36 vs main baseline); all 0039 files clean.
- Driver `run_thinking_ab.sh` executed live: typed stop, exit 2, no arm fired.
