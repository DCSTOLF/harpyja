---
spec: "0031-live"
---

# Tasks

- [x] T1 — Verifier artifact schema + atomic-write unit tests (RED)
- [x] T2 — Create live_verifier.py schema/validate/write (GREEN)
- [x] T3 — Four-fact PASS path + artifact-incomplete tests (RED)
- [x] T4 — Verifier core + completeness gate (GREEN)
- [x] T5 — Model-identity OQ1 three-branch tests (RED, AC2)
- [x] T6 — extract_model_identity with configured-list fallback (GREEN)
- [x] T7 — Model-invoked / Tier-0 short-circuit tests (RED, AC3)
- [x] T8 — extract_model_invoked (GREEN)
- [x] T9 — Tool-name extraction + symbols distinguishability tests (RED, AC4)
- [x] T10 — extract_tool_names (GREEN)
- [x] T11 — Terminal-bucket tests (RED)
- [x] T12 — Terminal-bucket check (GREEN)
- [x] T13 — Precedence + exactly-one-status + all-six-codes tests (RED, AC1/AC5)
- [x] T14 — Fix precedence ordering (GREEN)
- [ ] T15 — Refactor verifier internals (REFACTOR, optional)
- [x] T16 — Gateway surfaces served model tests (RED)
- [x] T17 — Add response['model'] extraction to gateway (GREEN)
- [x] T18 — Explorer backend last_trajectory capture tests (RED)
- [x] T19 — Implement backend capture seam + build_trajectory_record (GREEN)
- [ ] T20 — Refactor shared trajectory helpers (REFACTOR, optional)
- [x] T21 — verifier_preflight tests (RED)
- [x] T22 — Implement verifier_preflight (GREEN)
- [x] T23 — Proof-of-instrument astropy+django integration test (RED, AC6)
- [x] T24 — Live assembly harness run_verified_case (GREEN)
- [ ] T25 — Retire/annotate 0030 monkeypatch logger (REFACTOR, optional)
- [x] T26 — 0029 committed-test reconciliation test (RED, AC7)
- [x] T27 — Commit _MODEL_OVERRIDE_REASON rationale + assertion (GREEN)
- [x] T28 — Codify trajectory-verified convention in conventions.md (DOC, AC7)
