---
spec: "0011"
---

# Tasks

Dependency order. Each task tagged with its AC numbers. RED precedes its GREEN.
Phase 0 is a blocking decision gate; no Phase 1–5 task starts until it is closed.

## Phase 0 — Gating spike (decision gate)
- [x] T0 — SPIKE (done 2026-06-28): ran FC `citation=False` live (FC-4B/Ollama); confirmed citation=True raises the RCA TypeError while citation=False returns raw model text (no crash); pinned the per-line `<no-space-path>[:start[-end]] [(explanation)]` grammar; committed `harpyja/scout/fixtures/fc_citation_false_{raw_samples,final_answer}.txt` + README (with the AC22 prose negative-control line). **DECISION GATE → seam (a) LOCKED** (seam (c) not needed). [AC11, AC22]

## Phase 1 — Representation
- [x] T1 — RED: `server/test_types.py` `is_file_level` + half-None predicate tests. [repr]
- [x] T2 — GREEN: `server/types.py` `start_line`/`end_line` → `int | None` + `is_file_level` property. [repr]

## Phase 2 — Scout text-parser + fixture (producer)
- [x] T3 — RED: `scout/test_fastcontext_client.py` parser shape + tally + half-None + citation=False + floor tests (fixture-driven). [AC1, AC2, AC3, AC4, AC5, AC8, AC11, AC17, AC22, AC23]
- [x] T4 — GREEN: `scout/client.py` FC `citation=False`, `parse_final_answer` both shapes + file-level + tally + half-None reject. [AC1, AC2, AC3, AC4, AC5, AC8, AC17, AC22, AC23]

## Phase 3 — Downstream None-safety (data path)
- [x] T5 — RED: `scout/test_scout_normalize.py` file-level survive + drop count/log + half-None + deep-budget byte-identical. [AC6, AC7, AC9, AC10, AC23]
- [x] T6 — GREEN: `scout/normalize.py` file-level branch + drop tally + per-drop log; Tier-2 path unchanged. [AC6, AC7, AC9, AC10, AC23]
- [x] T7 — RED: `orchestrator/test_formatter.py` file-level survives, not merged, sorts after lined. [AC12]
- [x] T8 — GREEN: `orchestrator/format.py` line-less survive-path. [AC12]
- [x] T9 — RED: `orchestrator/test_gate.py` file-level → not-verifiable `skipped_reason="no-line-range"`, distinct from scoring-failure. [AC13]
- [x] T10 — GREEN: `orchestrator/gate.py` `GateOutcome.skipped_reason` + pre-read-back detection. [AC13]
- [x] T11 — RED: `orchestrator/test_locate.py` escalate-when-tier-remains / carry-with-marker / marker-distinct. [AC13]
- [x] T12 — GREEN: `orchestrator/locate.py` `gate-skipped:no-line-range` propagation + routing. [AC13]

## Phase 4 — Harness degrade visibility
- [x] T13 — RED: `eval/test_metrics.py` path-only credit + branch-before-arithmetic. [AC18]
- [x] T14 — GREEN: `eval/metrics.py` `None`-line guard in the one overlap oracle. [AC18]
- [x] T15 — RED: `eval/test_config.py` `degraded_dominated_threshold` default + Settings-disjointness. [AC15]
- [x] T16 — GREEN: `eval/config.py` add `degraded_dominated_threshold: float = 0.5`. [AC15]
- [x] T17 — RED: `eval/test_report.py` SCHEMA 0011/1, new fields via `_*_DEFAULTS`, both shapes validate, null cited lines tolerated. [AC16, AC19]
- [x] T18 — GREEN: `eval/report.py` version bump + additive fields + null-line tolerance. [AC16, AC19]
- [x] T19 — RED: `scout/test_scout.py` `ScoutEngine` exposes the `{spanned, filelevel, dropped}` tally. [AC17]
- [x] T20 — GREEN: `scout/engine.py` (+ `normalize.py`) thread the tally to Scout-result metadata (orchestrator `list[CodeSpan]` unchanged). [AC17]
- [x] T21 — RED: `eval/test_runner.py` degrade count/rate (+ null/zero), fc_citation_* aggregation, null cited-line serialization. [AC14, AC17, AC19]
- [x] T22 — GREEN: `eval/runner.py` degrade counters + shape-count aggregation + null serialization. [AC14, AC17, AC19]
- [x] T23 — RED: `eval/test_swebench_runner.py` `degraded_dominated` above/below threshold + composable `reliability_notes`. [AC15]
- [x] T24 — GREEN: `eval/swebench_eval.py` degrade-dominance + notes + threshold recorded at report top. [AC15]

## Phase 5 — Integration (skip-not-fail)
- [x] T25 — `scout/test_scout_integration.py` live Scout on flask returns tier-1, zero backend-error. [AC20]
- [x] T26 — `eval/test_swebench_integration.py` N=12 re-run: `scout_degrade_rate < 1.0`, ≥1 tier-1 span, measured non-null escalation, per-case escalation reason. [AC21]

## Optional refactor
- [x] R1 (satisfied by CodeSpan.is_file_level property, used by parse/normalize/gate/formatter/metrics) — extract one `is_file_level` / shape-invariant helper shared by `parse_final_answer` + `normalize_spans` (after T4/T6). [AC23]
- [x] R2 (compose_reliability_notes shared by runner + swebench) — fold the tally / degrade-marker counting into one helper shared by `runner.py` + `swebench_eval.py` (after T22). [AC14, AC17]
