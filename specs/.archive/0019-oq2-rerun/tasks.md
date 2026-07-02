---
spec: "0019"
---

# Tasks

- [x] T1 — (RED) EvalConfig.gate_false_escalation_ceiling default + Settings-disjointness tests [D2]
- [x] T2 — (GREEN) add `gate_false_escalation_ceiling: float = 0.20` to EvalConfig [D2]
- [x] T3 — (RED) recommend.py gate-confounded tests: below/above/at ceiling + carries measured rate [D2/AC9]
- [x] T4 — (GREEN) implement gate-confounded typed-null outcome + branch in recommend.py [D2/AC9]
- [x] T5 — (LOCK) characterize one-oracle reuse + null-with-zero-count in test_metrics.py [AC5]
- [x] T6 — (RED) report.py tests: SCHEMA 0014/1, new fields validate, legacy tolerated, round-trip [AC5/AC6/D2]
- [x] T7 — (GREEN) bump SCHEMA_VERSION + append ceiling/gate-confound/A-B fields last-with-defaults [AC5/AC6/D2]
- [x] T8 — (REFACTOR) hoist gate-confound field-name set to one anti-drift source [AC5/D2]
- [x] T9 — (RED) preflight unit tests: all-present pass, missing names it, assert_local-first, pulled-not-coresident [AC2]
- [x] T10 — (GREEN) implement preflight_models_present + PreflightError + cmd_preflight + subparser [AC1/AC2]
- [x] T11 — (INTEGRATION) G1→G2→G3 skip-not-fail scaffolding + sweep-runner recommend_oq2/ceiling wiring [AC1/AC3/AC4/AC6/AC7/AC8/AC9]
- [x] T12 — (STANDING) any defect surfaced at scale gets its own unit regression test before complete — no scale defect surfaced this implement pass; obligation carries to the operator sweep [AC10]
