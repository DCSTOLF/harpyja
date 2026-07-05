---
spec: "0022"
---

# Tasks

- [x] T1 — RED: citation-normalization tests (AC3)
- [x] T2 — GREEN: `locate_accuracy.normalize_citations` + `NormalizedCitations` (AC3)
- [x] T3 — RED: 4-way taxonomy MECE + precedence tests (AC1)
- [x] T4 — GREEN: `LocateBucket` + `classify_case` via frozen `span_hit_kind` (AC1)
- [x] T5 — RED: two-granularity scoring + first-class gap tests (AC2)
- [x] T6 — GREEN: `LocateDistribution` + `score_distribution` (AC2)
- [x] T7 — RED: ordered typed-finding decision-rule tests (AC7)
- [x] T8 — GREEN: `decide_finding` + `Finding` + pre-declared bands (AC7)
- [x] T9 — RED: no-SUT-change guard + frozen-oracle snapshot tests (AC10)
- [x] T10 — GREEN: `SUT_SURFACE` allowlist + additive-only contract (AC10)
- [x] T11 — RED: Scout-only probe assembly + `count_turns`/`counting_agent_factory` (trajectory turns, labeled source) + `require_live_stack` gate tests (AC4/AC5/AC6)
- [x] T12 — GREEN: `locate_probe.py` — stratify + run_locate_probe + `count_turns` + `counting_agent_factory` (real agent, read trajectory pre-cleanup, `turns_used_source ∈ {trajectory,unavailable}`) + reformulation probe + `require_live_stack`
- [x] T13 — RED: live Scout-only integration tests, gated via `require_live_stack` (AC4/AC5/AC6)
- [x] T14 — GREEN: wire live probe entry via `build_scout_only_stack` (build_scout_engine + counting_agent_factory)
- [x] T15 — REFACTOR: per-case drive already factored into `_run_scout_case`/`_empty_rate` shared helpers; no further extraction warranted (no-op)
- [x] T16 — DOC: findings.md written — typed finding (provisional RETRIEVAL_FUNDAMENTAL) + live fixture-smoke distribution + per-case rows + turns-used (trajectory) + representativeness + pre-registered prior; real 38-case run operator-gated (AC7/AC8/AC9). Plus additive `scout_stack_available()` fixing the Deep-oriented false-skip.
