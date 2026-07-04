---
spec: "0020"
---

# Tasks

- [x] T1 — P1 field-reachability lock on the frozen `Recommendation` (test_recommend.py) — LOCK
- [x] T2 — P2 byte-frozen `recommend_oq2`/`rank_sweep` golden snapshot (test_recommend.py) — LOCK
- [x] T3 — `classify_g3_outcome` truth-table matrix (test_oq2_classify.py) — RED --delegate
- [x] T4 — implement `oq2_classify.py` (classify_g3_outcome + G3Classification) — GREEN --delegate
- [x] T5 — gate-ledger schema/validator/writer tests (test_oq2_ledger.py) — RED --delegate
- [x] T6 — implement `oq2_ledger.py` (LEDGER_SCHEMA_VERSION "0020/1") — GREEN --delegate
- [x] T7 — protocol G0 preflight routing + stop-before-provision (test_oq2_protocol.py) — RED
- [x] T8 — implement `oq2_protocol.py` scaffolding + G0 stage — GREEN
- [x] T9 — protocol G1 three sub-checks classed by cause — RED
- [x] T10 — implement protocol G1 stage — GREEN
- [x] T11 — protocol G2 first-class metrics + A/B + over-ceiling-no-abort — RED
- [x] T12 — implement protocol G2 stage — GREEN
- [x] T13 — protocol G3 → classify + descriptive-only-under-confound — RED
- [x] T14 — implement protocol G3 stage + ledger emission — GREEN
- [x] T15 — full-protocol ledger `0020/1` + verdict-before-next-gate ordering — RED
- [x] T16 — implement end-to-end ledger assembly + ordering + close/hold cause — GREEN
- [x] T17 — no-default-flip guard (Settings defaults byte-unchanged) — LOCK
- [x] T18 — refactor: consolidate verdict→ledger mapping (optional) — REFACTOR (no-op: driver already single-sources `_verdict_dict`/`commit`)
- [x] T19 — live G0→G3 operator run harness (oq2_live.py + `oq2` CLI + skip-not-fail integration test) — DONE (code); live G0+G1 executed, full G2/G3 sweep operator-gated
