---
spec: "0024"
---

# Tasks

- [x] T1 — RED: new Scout loop Settings budgets present with provisional defaults (AC4/AC5/AC2)
- [x] T2 — GREEN: add `scout_max_turns`/`scout_wall_clock_s`/`scout_loop_repeat_n`/`scout_history_char_cap`/`scout_glob_max_paths` to Settings, justified (AC4/AC5/AC2)
- [x] T3 — RED: three navigation tools bounded/confined/read-only + hostile-input + glob→CodeSpan tests (AC2)
- [x] T4 — GREEN: `explorer_tools.build_explorer_tools` mirroring `build_host_tools`, `grep` over shared `RipgrepEngine` (AC2)
- [x] T5 — RED: context map from manifest (no bytes), query-injected, map-filter ≠ tool-scope tests (AC3)
- [x] T6 — GREEN: `context_map.build_context_map` filtered tree (AC3)
- [x] T7 — RED: `submit_citations` strict-schema + normalize + honest-empty + no-read tests (AC6)
- [x] T8 — GREEN: `submit.submit_citations` + `SubmitCitationsSchemaError` via `normalize_spans` (AC6)
- [x] T9 — RED: gateway `complete_with_tools` returns content+tool_calls, asserts_local-first (AC7)
- [x] T10 — GREEN: `ModelGateway.complete_with_tools` (air-gap first, injectable transport) (AC7)
- [x] T11 — RED: bounded loop — one call/turn, turn cap, wall-clock ceiling, unknown-tool reject (AC4)
- [x] T12 — GREEN: `explorer_loop.run_explorer_loop` (AC4)
- [x] T13 — RED: self-recovery — loop detection + truncation + PRESERVATION negative (AC5)
- [x] T14 — GREEN: corrective injection + citation-preserving truncation with dropped-span re-inject (AC5)
- [x] T15 — RED: `ExplorerBackend` satisfies seam, DI-injected, fakes drive deterministically, assert_local-before-loop (AC1/AC7)
- [x] T16 — GREEN: `explorer_backend.ExplorerBackend` assembling map+tools+submit+loop over `complete_with_tools` (AC1/AC7)
- [x] T17 — RED: four distinct typed causes + honest-empty + AirGap-never-degrades + degrade-rate field (AC8/AC9)
- [x] T18 — GREEN: new cause constants in `errors.py` + terminal-state mapping + degrade-rate field (AC8/AC9)
- [x] T19 — RED: `build_explorer_scout_engine` wires `ExplorerBackend` + threads loop budgets (AC1) — added a parallel factory (NOT an in-place swap) so FastContext removal stays a separate cleanup
- [x] T20 — GREEN: `wiring.build_explorer_scout_engine` builds `ExplorerBackend` (FastContext factory left intact) (AC1)
- [x] T21 — REFACTOR: dispatch table already single-source in `run_explorer_loop`; pinned the schema↔tool-surface coupling guard instead of a hollow no-op
- [x] T22 — RED: live integration — real tool-calling model → citation list within turn cap + zero non-loopback egress, skip-not-fail (AC10)
- [x] T23 — GREEN: wire the live integration entry via `build_explorer_scout_engine` (AC10) — PASSED LIVE (~28s, Qwen3-8B, zero non-loopback egress)
