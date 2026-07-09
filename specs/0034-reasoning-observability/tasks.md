---
spec: "0034"
---

# Tasks

- [x] T1 — Characterization pins: gateway return keys, default outbound body {max_tokens:2048}, valid-fixture verify outcome
- [x] T2 — RED: gateway surfaces reasoning + completion_tokens (absent→None, empty→"/0), existing keys unchanged
- [x] T3 — GREEN: add reasoning + completion_tokens to complete_with_tools return dict
- [x] T4 — RED: build_trajectory_record carries per_turn + think_mode; discriminate reasoning- vs content-truncated vs clean
- [x] T5 — GREEN: build_trajectory_record additive per_turn/think_mode params
- [x] T6 — RED: derive_think_mode pinned per enum combination (+ native-wins precedence)
- [x] T7 — GREEN: derive_think_mode(think, enable_thinking)
- [x] T8 — RED: backend accumulator — per-turn tuple, final length turn not in model_turns, reset, none/zero, think_mode on trajectory
- [x] T9 — GREEN: accumulator in wrapped_model_call + reset in run() + think ctor arg + thread into build_trajectory_record
- [x] T10 — RED: schema 0034/1; legacy 0031/1 + 0033/1 validate; 0034/1 reasoning fields optional
- [x] T11 — GREEN: bump VERIFIER_SCHEMA_VERSION + extend _KNOWN set
- [x] T12 — RED: written artifact JSON carries per_turn + think_mode
- [x] T13 — GREEN: run_verified_case copies per_turn + think_mode into artifact
- [x] T14 — RED: Settings.explorer_think default None (field-introspection drift guard) + env coerce
- [x] T15 — GREEN: add explorer_think: bool | None = None
- [x] T16 — RED: default body no think param; explorer_think True/False sends think=that
- [x] T17 — GREEN: _default_model_call adds think only when non-None
- [x] T18 — DRIFT-GUARD: Deep outbound carries neither explorer_think nor think param (extend test_rlm.py)
- [x] T19 — REGRESSION: verify_trajectory outcome-equality over valid fixtures; byte-identity disclaimed
- [x] T20 — RED: live records nonzero reasoning or NOT-EXERCISED, precondition-probe fallback, skip-not-fail
- [x] T21 — GREEN: probe_reasoning_default preflight helper
- [x] T22 — DOC: conventions.md invisible-generation rule + 0031-0033 asterisk
- [x] T23 — REFACTOR (optional): dedup per-turn tuple / none-vs-zero helper; ruff clean
