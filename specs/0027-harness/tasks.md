---
spec: "0027"
---

# Tasks

- [x] T1 — RED: `scout_ls_max_entries` Settings field + drift-guard tests [unit]
- [x] T2 — GREEN: add `scout_ls_max_entries` to frozen `Settings` (additive-last) [build]
- [x] T3 — RED: `ls` tool tests (single-dir, read-only, confine_path, clamp) + exact-four count + schema-drift amendment [unit]
- [x] T4 — GREEN: implement `ls` tool + `_tool_schemas` `ls` + amend exact-count convention 3→4 with rationale [build]
- [x] T5 — RED: backend turn-1 payload — no repo listing, ≤2000 tok, small+large manifest, repo-size-independent [unit]
- [x] T6 — GREEN: cut over to minimal `build_initial_prompt` (query preserved, no repo tree) — DEVIATION from the planned `context_map=""` because the query was baked into `build_context_map` [build]
- [x] T7 — RED: per-cause scout-degrade counts in runner + `SCHEMA_VERSION` 0027 + `_AGGREGATE_DEFAULTS` [unit]
- [x] T8 — GREEN: per-cause degrade plumbing + additive report fields + `SCHEMA_VERSION` 0026/1→0027/1 [build]
- [x] T9 — guard: retire `turns_used` as a why-did-it-end signal (behavioral pin + scoped source sweep; code already routes on `outcome`) [unit]
- [x] T10 — truncation still fires + citation-preserving with `context_map=""` (AC9) [unit]
- [x] T11 — REFACTOR: no-op — cause parsing already single-authority in `_scout_degrade_cause` [build]
- [x] T12 — integration: live astropy+django AC5 test written (`test_harness_live.py`, xfail). RAN on the 16B stack → BOTH degraded `model-unreachable` @300s. AC5 = HOLD (generation-runaway, downstream of the fixed map defect) [integration]
- [x] T13 — integration: live turn-1 payload measured (~10,181→~60 tok, 170× cut) + committed evidence artifact `operator-run-findings.md`; map removal PROVEN, AC5 held [integration]
- [x] T14 — build/guard: AC7 0026-only doc correction verified consistent across spec + RCA + operator-run-findings [build]
