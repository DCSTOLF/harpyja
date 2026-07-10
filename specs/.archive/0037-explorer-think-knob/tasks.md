---
spec: "0037"
---

# Tasks

- [x] T1 — RED: `test_think_probe_result.py` pins `PROBE_OUTCOMES`, the validator's reject path, and the committed `probe_result.json` schema+outcome (fails: no module, no file)
- [x] T2 — GREEN: implement `harpyja/eval/think_probe.py` (`PROBE_OUTCOMES`, `PROBE_RESULT_SCHEMA_VERSION="0037/1"`, `ProbeResultError`, `validate_probe_result`, `load_probe_result`)
- [x] T3 — OPERATOR/LIVE: author + run `probes/run_probes.sh` (curl-on-loopback, qwen3:14b, /v1, three arms, tiny-cap, completion_tokens, `<think>`-leak); commit `probes/probe_result.json` typed outcome → T1 file-pin green. **OUTCOME: `no-op`** — all three /v1 arms behaviorally identical (reasoning generated, cap exhausted reasoning-first); chat-template supplementary arm ALSO no-op; /api/chat control proves the mechanism works one path over (the /v1 compat layer drops the field)
- [x] T3b — BRANCH GATE: outcome = `no-op` → NO_OP_BLOCKED terminal path taken; T4/T6 authored as self-skipping conditional pins (activate on a future outcome flip), T7's live run skipped (no distinguishable arms exist), close via T10 findings
- [x] T4 — RED: extended `test_explorer_backend.py` with `test_explorer_think_pin_gated_on_native_probe_outcome` — skips with the machine-recorded `no-op` reason
- [x] T5 — GREEN: confirmed skip-with-reason (the legitimate close on this branch); no new SUT code
- [x] T6 — RED/skip-not-fail: extended `test_live_verifier_integration.py` with `test_live_think_knob_three_factor_effectiveness` (three separate non-collapsible assertions, N=1 in docstring) — skips at the outcome gate with the recorded reason
- [x] T7 — SKIPPED (branch gate, recorded): no per-mode effectiveness run is constructible against a no-op knob — three identical thinking-on runs would prove nothing; `run_effectiveness.sh` not authored, per the NO_OP_BLOCKED terminal path
- [x] T8 — REGRESSION: all four 0034 pin files green in full (147 passed, 1 skip = the new conditional pin)
- [x] T9 — REFACTOR: single `load_probe_result` loader in `harpyja/eval/think_probe.py`, reused by the pin test, the AC2 guard, and the AC3 gate — no duplicated JSON parsing
- [x] T10 — DOC: `findings.md` — NO_OP_BLOCKED close, the /api/chat control localizing the defect to the /v1 compat layer, A/B-blocking consequence + reconciliation-is-a-revision, no-default-flip, N=2 as motivation-not-evidence, evidence index
