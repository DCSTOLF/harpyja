---
spec: "0038"
---

# Tasks

- [x] T1 — RED: `test_reconcile_probe_result.py` pins `RECONCILE_PROBE_OUTCOMES` {native-api-chat, v1-variant, still-blocked}, schema `0038/1`, the split shape (chosen_path/outcome/usage_mapping/migration-cost/per-arm), the validator reject paths, and the committed `probe_result.json` (fails: no module, no file)
- [x] T2 — GREEN: implement `harpyja/eval/reconcile_probe.py` (`RECONCILE_PROBE_OUTCOMES`, `RECONCILE_PROBE_SCHEMA_VERSION="0038/1"`, `ReconcileProbeError`, `validate_reconcile_probe_result`, `load_reconcile_probe_result`)
- [x] T3 — OPERATOR/LIVE: author + run `probes/run_probes.sh` (native `/api/chat`, three arms true/false/omitted OBSERVED, tiny-cap via `options.num_predict`, `eval_count`→`completion_tokens` cross-check, `<think>` leak scan, migration-cost scoping: tool_call_id / usage field / reasoning field, `/v1` passthrough re-check); commit `probes/probe_result.json` typed outcome → T1 file-pin green
- [x] T3b — BRANCH GATE: **outcome = `v1-variant`** (`reasoning_effort` on the existing /v1 path: "none"→off, "high"→on, omitted→default; top-level `think` still a no-op, native control re-confirmed but unchosen) → smaller `/v1`-passthrough wiring set; T4–T12 assert against the /v1 outbound, 0034 byte-identical pin survives for None
- [x] T4 — N/A ON BRANCH (`v1-variant`): no native adapter — the /v1 transport is unchanged and `ModelGateway.complete_with_tools` already passes params through; branch blast radius covered by the T6 tripwire (`test_explorer_think_wiring_matches_committed_probe_outcome`, loud FAIL on wiring/evidence mismatch) + amended pins
- [x] T5 — N/A ON BRANCH (`v1-variant`): zero gateway change needed (existing `**params` passthrough; `assert_local` + finite `timeout_s` already enforced on the /v1 path)
- [x] T6 — RED (branch-adapted): re-pointed `test_explorer_think_true/false` pins at `reasoning_effort` ("high"/"none", dead `think` field gone) with the recorded supersede rationale; `test_default_outbound_request_body_pinned` SURVIVES (None byte-identity holds — no endpoint switch); `test_default_outbound_carries_no_think_param` strengthened (no `reasoning_effort` either); new outcome tripwire added
- [x] T7 — GREEN: `ExplorerBackend._default_model_call` translates explorer_think {True→"high", False→"none", None→omit} to `reasoning_effort` on the same /v1 transport; scout+gateway suites 220 passed / 1 skipped
- [x] T8 — RED/skip-not-fail: `test_live_reconciled_think_knob_effectiveness` in `test_live_verifier_integration.py` — two-factor per-mode on the native path, gated on the 0038 artifact, `completion_tokens` delta via the pinned `usage_mapping`, N=1 in docstring
- [x] T9 — OPERATOR/LIVE: author + run `run_effectiveness.sh` (strict `require_live_stack`) → durable per-mode verifier-clean artifacts under `eval_work/live_artifacts/`; T8 assertions hold → AC3 green
- [x] T10 — RED/guard: `test_deep_does_not_call_native_adapter` in `test_rlm.py` (spy raises on native call) + existing Deep no-`think` / no-`enable_thinking` guards stay green (Deep-scope isolation)
- [x] T11 — RED: `test_live_verifier.py` — four facts survive a native trajectory, optional `serving_transport` field recorded (legacy artifacts still validate), `derive_think_mode` post-switch disambiguation audit
- [x] T12 — GREEN: add optional `serving_transport` to `build_trajectory_record` (bump `VERIFIER_SCHEMA_VERSION` `0034/1`→`0038/1`, version-gated), thread from `ExplorerBackend`; record enum audit passed (extend only if T11 failed)
- [x] T13 — REFACTOR: single `load_reconcile_probe_result` loader reused by the T1 pin, the T4/T6 gates, and the T8 gate — no duplicated JSON parsing or inline outcome literals
- [x] T14 — EDIT (recorded): supersede-with-record the 0037 conditional AC2/AC3 pins (`test_explorer_think_pin_gated_on_native_probe_outcome`, `test_live_think_knob_three_factor_effectiveness`) — mark SUPERSEDED-BY-0038, re-point/retire; archived `specs/.archive/0037-.../probes/probe_result.json` + its drift pin NEVER edited
- [x] T15 — DOC: `specs/0038-reconciliation/findings.md` — outcome + chosen_path, transport/mechanism change + enumerated blast radius (incl. superseded 0034 pin), 0037 supersede-with-record, `derive_think_mode` audit result, no-default-flip (or the typed STILL_BLOCKED close)
