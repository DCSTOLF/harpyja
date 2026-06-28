---
spec: "0008"
---

# Tasks — spec 0008 Wave 5: Verification Gate + auto-escalation

- [x] T01 — RED: Settings verify_* defaults + AC13 rejection tests in test_settings.py [unit] (AC13)
- [x] T02 — GREEN: append verify_method/verify_threshold/verify_top_n + __post_init__ validation in settings.py [unit] (AC13)
- [x] T03 — RED: classifier point/broad/ambiguous tests in test_classify.py [unit] (AC2)
- [x] T04 — GREEN: classify.py heuristic + pluggable seam [unit] (AC2)
- [x] T05 — RED: planning matrix all-12-rows tests in test_matrix.py [unit] (AC3)
- [x] T06 — GREEN: matrix.py plan_ladder single source of truth [unit] (AC3)
- [x] T07 — RED: gate pass/fail/top-N+dropped/air-gap/scoring-failed tests in test_gate.py [unit] (AC10, AC11)
- [x] T08 — GREEN: gate.py VerificationGate (read-back, top-N, assert_local, scoring-failed) [unit] (AC10, AC11)
- [x] T09 — RED: AC1 lockstep auto-contract tests (gated-pass/escalate/broad/no-seed/no-mode-no-effect) in test_locate.py [unit] (AC1, AC4, AC5, AC6, AC7) — also retired the Wave-0 lock tests in server/test_app.py (lockstep)
- [x] T10 — GREEN: remove _MODE_NO_EFFECT + wire classifier→matrix→ladder for auto in locate.py [unit] (AC1, AC4, AC5, AC6, AC7)
- [x] T11 — RED: empty-case split + gate-scoring-failed escalation tests in test_locate.py [unit] (AC8) — behavior landed with T10's cohesive _locate_auto; tests lock it in
- [x] T12 — GREEN: three-way Tier-1 split + scoring-failed routing in locate.py [unit] (AC8) — implemented in T10
- [x] T13 — RED: fast informational gate + gate-low-confidence tests in test_locate.py [unit] (AC7, AC8)
- [x] T14 — GREEN: fast informational gate implementation in locate.py [unit] (AC7, AC8)
- [x] T15 — RED: confidence map + stable flag-id tests in test_locate.py [unit] (AC9)
- [x] T16 — GREEN: confidence derivation from terminal-tier+flags in locate.py [unit] (AC9)
- [x] T17 — REFACTOR: flag-id constants + _join helper extracted; _locate_auto now drives off plan_ladder (matrix is the real source of truth) [unit] (AC8, AC9)
- [x] T18 — GREEN: production wiring — orchestrator/wiring.py build_verification_gate + gate_factory param on build_app [unit] (AC10, AC12)
- [x] T19 — network-deny zero-egress integration test in test_gate.py [integration] (AC10) — PASSED live
- [x] T20 — end-to-end auto point-cheap + broad-to-deep integration tests in test_locate_integration.py [integration] (AC12) — PASSED live (real FastContext + gate + Deep stack)
