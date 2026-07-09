---
spec: "0036"
---

# Tasks

- [x] T1 (RED): test_dataset.py — 0036/1 validation matrix (known-set detection; reachability + reachability_provenance + concept_patch_relation mandatory; divergent requires concept_span + provenance; same forbids concept_span; bad enums reject; legacy 0026/1 defaults)
- [x] T2 (GREEN): dataset.py — add DATASET_SCHEMA_VERSION_0036 + _KNOWN_TERSE_SCHEMA_VERSIONS, widen is_terse to set membership, add 5 additive EvalCase fields + loud 0036 validation
- [x] T3 (RED): test_terse_reachability.py — classify_reachability lexical/conceptual + provenance constants + ast no-ModelGateway guard
- [x] T4 (GREEN): terse_reachability.py — pure classify_reachability + MECHANICAL/HAND_LABELED constants (operator-side, no gateway import)
- [x] T5 (RED): test_terse_floor.py — test_full_set_meets_frozen_full_n_target + test_conceptual_stratum_reportability_floor
- [x] T6 (GREEN): terse_dataset.py — meets_full_n_target(dataset,cfg) + conceptual_stratum_report(dataset) (UNDER_POPULATED typed finding)
- [x] T7 (RED): test_ac8_pilot.py — test_preregistered_0036_config_is_frozen_hashed_and_servable (arms qwen3:14b vs qwen3:4b-instruct, other fields identical, own 64-hex hash)
- [x] T8 (GREEN): ac8_pilot.py — commit PREREGISTERED_AC8_CONFIG_0036 + AC8_CONFIG_HASH_0036 (arms only differ; thresholds copied verbatim) — FREEZE, before any pilot run
- [x] T9 (RED): test_pilot_runner.py — build PilotPairs + decide_from_pairs under 0036 config; typed degrade excluded + recorded, never counted clean
- [x] T10 (GREEN): pilot_runner.py — pure aggregation glue (bucket→PilotPair, degrade exclusion), no live I/O
- [x] T11 [operator][live]: blind-author pilot queries via 0026 author_terse_set (author≠verifier, Ollama live); commit AuthoringArtifact; STOP-AND-WARN on infra error
- [x] T12 [operator]: post-authoring mechanical reachability tag + concept/patch hand-label; assemble 0036/1 pilot rows replacing the 5 placeholders in swebench_verified.terse.jsonl
- [x] T13 (RED): test_terse_join.py + test_terse_floor.py — fixture-backed tests expect real 0036/1 rows (fail while placeholders remain)
- [x] T14 (GREEN): commit replaced swebench_verified.terse.jsonl (real blind-authored + tagged pilot rows)
- [x] T15 [live][operator]: run pilot end-to-end via run_verified_case; persist each artifact via write_live_artifact (VERIFIER_SCHEMA_VERSION 0034/1); record degrades per case (bounded re-run/exclusion); batched ~35+ min; STOP-AND-WARN
- [x] T16 [live]: test_live_verifier_integration.py — pilot-set integration test asserts verifier-clean persisted artifact per case or recorded typed degrade (skip-not-fail on infra)
- [x] T17 [live][operator]: apply decide_ac8 under PREREGISTERED_AC8_CONFIG_0036 (hash cited) → PROCEED or UNDER_POWERED_STOP gate artifact
- [x] T18 [doc]: AC6 — cite pinned REPRESENTATIVENESS_CAVEAT (report.py:41) in spec close/changelog; no parallel restatement
- [x] T19 [conditional-on-PROCEED][operator][live]: author + tag the full set at-or-above full_n_target=30 (upward-only), enforcing conceptual-stratum ≥5 reportability floor
- [x] T20 (RED)[conditional-on-PROCEED]: fixture-backed full-set tests — validate_terse_set_floor ok + meets_full_n_target true + conceptual_stratum_report reportable
- [x] T21 (GREEN)[conditional-on-PROCEED]: commit full swebench_verified.terse.jsonl (Step-20 tests pass) — OR on UNDER_POWERED_STOP mark T19–T21 N/A-by-gate and close with the finding
