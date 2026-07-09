---
spec: "0030"
closed: 2026-07-08
---

# Changelog — 0030 Tier-0 symbols as a callable explorer tool

## What shipped vs spec

- **Tool (PROVEN):** `symbols(path)` added as the 5th explorer tool, wrapping the
  EXISTING Tier-0 file-local `SymbolRecord` index (mirrors `deep/host_tools.py::symbols`,
  no new parser — Invariant 1). Path-normalized before lookup, repo-confined AFTER
  resolution, output-clamped by a new `Settings.scout_symbols_max_entries=400`
  (additive-last). Returns `{"symbols": [...CodeSpan...], "degraded": bool}`.
- **Graceful degradation (PROVEN):** a file marked `ManifestEntry.degraded` (the AC3
  manifest-provenance decision — NOT a new `SymbolRecord` field, since a degraded file
  has zero records) falls back to the shared ripgrep engine and surfaces a visible
  `degraded: true` marker, never a crash.
- **Exact-tool-count convention amended 4 → 5 IN LOCKSTEP (PROVEN):** `.speccraft/conventions.md`
  updated with rationale + `test_build_explorer_tools_returns_exactly_five_navigation_tools`
  + schema-vs-dispatch test + parallel-tool-call test, all in one commit.
- **Wiring (PROVEN):** `wiring.py` threads `symbol_records` (via `load_symbols_or_none`)
  and the held manifest into `build_explorer_tools`; guarded by a non-empty wiring test.
- **Refactor:** shared `record_to_codespan` extracted, used by both `deep/host_tools.py`
  and `scout/explorer_tools.py` (one projection source of truth).
- **Lift-report schema (SHIPPED):** `eval/symbols_lift_report.py`, version-stamped
  `0030/1`, atomic outside-repo writer.
- **Harness with 5th tool present (VALIDATED):** the loop runs clean with `symbols`
  available, reaches a terminal, no degrade (AC8-equivalent holds at 5 tools).

## Deviations (the honest record)

- **AC5/AC6 lift is NOT proven — symbols not invoked in spec 0031 measurement run.** 
  Spec 0031 AC6 re-ran the same two cases (astropy-12907, django-12774) with the
  verifier instrument to measure lift. **Finding: symbols tool was available (Tier 0 
  symbol index built) but NOT invoked by the explorer in either case.** Tool names 
  in trace for astropy: ["ls", "grep", "submit_citations"]. Django: ["grep", "ls"]. 
  The hypothesis that symbols availability affects tool selection is unproven (N=2 
  too small to confirm or refute). **Lift claim RETRACTED.** Tool ships (integrated, 
  unit-correct) but claimed benefit is unsupported by measurement.
  
- **Original deviations (0030 closure record):**
  - **AC5/AC6 lift was NOT actually measured in 0030's closure** — recorded as 
    inconclusive-and-inconsistent, explicitly NOT "hypothesis validated." The live test 
    did not use a ground-truth span oracle: it mapped outcome → bucket with a crude 
    proxy (`has_citations → CORRECT` else `WRONG_FILE`), so the "both CORRECT" run 
    measured citation-PRESENCE, not span correctness.
  - **The control moved by a mechanism the tool cannot produce.** astropy was baseline 
    `WRONG_FILE`; a file-local symbols tool structurally cannot fix wrong-FILE navigation 
    (AC5 made astropy the expected control that stays `WRONG_FILE`). Its flip to "CORRECT" 
    was therefore evidence of the crude oracle, not of lift — internally inconsistent.
  - **Tool invocation unconfirmed.** Symbols usage was probed by monkeypatching 
    `_answer_tool_call`; the test itself tolerated `symbols` not appearing.
  - **Non-representative live rig:** ad-hoc query strings, hardcoded model, and engine/gateway 
    built with separate Settings objects — not the 0026 terse instrument, N=2.
  - **Stray artifact:** `measure_symbols_lift.py` shipped at the repo ROOT.

## Files touched

- harpyja/config/settings.py, harpyja/config/test_settings.py
- harpyja/scout/explorer_tools.py, harpyja/scout/test_explorer_tools.py
- harpyja/scout/explorer_backend.py, harpyja/scout/wiring.py, harpyja/scout/test_scout_wiring.py
- harpyja/deep/host_tools.py, harpyja/symbols/symbols_io.py (shared record_to_codespan refactor)
- harpyja/eval/symbols_lift_report.py, harpyja/eval/test_symbols_lift_report.py
- harpyja/eval/test_symbols_lift_live.py
- measure_symbols_lift.py (repo root — stray)
- .speccraft/conventions.md (exact-tool-count 4→5, in-lockstep)
