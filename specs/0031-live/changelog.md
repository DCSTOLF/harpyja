---
spec: "0031-live"
closed: 2026-07-08
---

# Changelog — 0031-live Trajectory-verified live measurement

## What shipped vs spec

- **Postflight verifier module** (`harpyja/eval/live_verifier.py`, new): `VERIFIER_SCHEMA_VERSION="0031/1"`,
  the six-code `FAILURE_CODES` + fixed `FAILURE_PRECEDENCE`, `VerifierResult`, `VerificationError`,
  the pure `verify_trajectory`, the four `extract_*` fact helpers, `validate_verifier_artifact`,
  `write_verifier_artifact` (delegates to `report.atomic_write_json`), `build_trajectory_record`,
  `verifier_preflight`, and `run_verified_case`. Proves the FOUR FACTS (model identity, model
  invoked, tool names, terminal bucket) or FAILs with exactly one of six enumerated codes in a
  deterministic precedence (`artifact-incomplete > model-unknown > model-mismatch >
  model-not-invoked > tool-names-unextractable > terminal-bucket-missing`). AC1–AC5 unit-complete
  (26 tests, `test_live_verifier.py`).
- **OQ1 model-identity three branches** resolved in `extract_model_identity`: served==requested →
  PROVEN; served!=requested → `model-mismatch`; served absent → `configured_endpoint_models`
  fallback (PROVEN via fallback, else `model-unknown`). AC2 covered across all three.
- **Gateway capture seam** (AC-plumbing): `gateway.complete_with_tools` now surfaces
  `response.get("model")` additively (`harpyja/gateway/gateway.py`, one line; verified in
  `test_gateway.py`). Request/response semantics unchanged.
- **Explorer backend capture seam**: `ExplorerBackend.last_trajectory` captured after the loop via
  `build_trajectory_record`, mirroring the existing `last_turns_used` seam; served model threaded
  from the model call. `run()` still returns `list[CodeSpan]` (`harpyja/scout/explorer_backend.py`,
  `test_explorer_backend.py`).
- **verifier_preflight** (AC6 gate): `assert_local` first, then a `/api/tags` model-presence
  membership check — an absent model or non-loopback endpoint is a documented skip, not a
  measurement failure. Unit-covered.
- **0029 reconciliation** (AC7): `_MODEL_OVERRIDE_REASON` constant + the
  `test_recorded_model_matches_settings_or_documents_override` assertion in `test_harness_live.py`
  bind the committed 16B/llama.cpp:8131 harness config to a stated rationale — the committed-test /
  changelog mismatch is closed.
- **Convention codified** (AC7): the "Trajectory-verified measurement" section in
  `.speccraft/conventions.md` binds all future live measurement specs (bake-off, eval set,
  capability reports) to a verifier artifact + trajectory proof.

## Deviations from spec / plan

- **`run_verified_case` shipped FULLY IMPLEMENTED, NOT as a stub (T24 / AC6 CORRECTION).**
  Originally planned as a minimal stub (per task notes), but implemented as a FULL live assembly:
  constructs an `ExplorerBackend` (lines 469-478), drives `backend.run(query, [])` (line 482),
  captures the real trajectory via `backend.last_trajectory` (line 489), derives `terminal_bucket`
  via `locate_accuracy.classify_case` (line 500). The proof-of-instrument live run (0030 astropy
  + django re-run, symbols-invocation resolution) IS EXECUTED, not deferred. The verifier
  processes durable JSON artifacts from actual explorer loop execution. The integration test
  (`test_live_verifier_integration.py`) skips gracefully on absent live stack, but when the
  stack is present, runs real cases end-to-end. AC6 "both cases complete with verifier-produced
  artifacts" is SHIPPED, not a HOLD.
- **T15 / T20 / T25 (REFACTOR, optional) intentionally left undone.** Consequence of skipping T20:
  the tool-name parser is DUPLICATED — `extract_tool_names` (verify path) and the inline parse in
  `build_trajectory_record` are two copies with divergent behavior on an unnamed call
  (`extract_tool_names` FAILs `tool-names-unextractable`; `build_trajectory_record` silently skips
  it). **Filed as T20-tool-name-parser-dedup.md: MEASUREMENT-INTEGRITY BLOCKER** (not just tech debt).
  Currently safe because verify is sole gate. But this is exactly the copy-drift hazard the verifier
  was built to prevent. **Blocker for bake-off and any spec that consumes verifier artifacts
  outside the verify gate.** Must be deduped before downstream specs bypass verification.

## Files touched

- `harpyja/eval/live_verifier.py` (new)
- `harpyja/eval/test_live_verifier.py` (new, 26 tests)
- `harpyja/eval/test_live_verifier_integration.py` (new, integration stub — skips on absent stack)
- `harpyja/gateway/gateway.py` + `harpyja/gateway/test_gateway.py`
- `harpyja/scout/explorer_backend.py` + `harpyja/scout/test_explorer_backend.py`
- `harpyja/eval/test_harness_live.py` (`_MODEL_OVERRIDE_REASON` + reconciliation test)
- `.speccraft/conventions.md` (Trajectory-verified measurement section — already committed)
- `specs/0031-live/tasks.md` (25 [x], 3 [ ] optional)
