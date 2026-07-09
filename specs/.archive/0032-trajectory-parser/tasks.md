---
spec: "0032"
---

# Tasks

- [x] T1 — Pin behavior-preserving invariants (AC3/AC5/AC6 characterization) in `test_live_verifier.py`; all green pre-cutover
- [x] T2 — RED: identity + typed-failure + both-paths-parity tests in `test_live_verifier.py` (AC1/AC2/AC4) — failed pre-cutover for the planned reasons (patch unobserved; KeyError tool_names_failure)
- [x] T3 — RED: ExplorerBackend live-run nameless-tool_call regression in `test_explorer_backend.py` (AC7) — failed pre-cutover on the sentinel; control-flow half passed (pins AC7)
- [x] T4 — GREEN: repoint `build_trajectory_record` to `extract_tool_names` + add `tool_names_failure` sentinel (live_verifier.py:336-355); T2+T3 pass, T1 stays green (65/65 in both files)
- [x] T5 — REFACTOR/DOC: single-parser symbol-audit test (AC8) + codify "one parser, strict-wins" in conventions.md + OQ2 finding re-verified in-session (tiers_run propagated as data; identity/bucket single-extractor)
- [x] T6 — AC6 live: re-verify real astropy + django trajectories through the deduped parser on Ollama/qwen3:14b — astropy EXACT field-by-field match to 0031 reference (PASSED/empty/[ls,grep,submit_citations]/symbols-NOT-invoked); django PASSED (correct, symbols not invoked; no durable 0031 bucket reference exists). First django attempt degraded `model-unreachable` (typed, environment), retried once, clean. Evidence: ac6-findings.md + ac6-artifacts/
