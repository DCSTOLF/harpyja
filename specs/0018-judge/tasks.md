---
spec: "0018"
---

# Tasks

- [x] T1 [RED] Settings: instruct_model accepted + default-flip introspection + frozenset membership tests (amend existing verify-defaults assertion) — AC1,AC2
- [x] T2 [GREEN] settings.py: add "instruct_model" to _VERIFY_METHODS; flip verify_method default to "instruct_model" — AC1,AC2
- [x] T3 [RED] test_gate.py: `_parse_score` conforming + non-conforming boundary tables — AC5
- [x] T4 [GREEN] gate.py: add `ScoreParseError`; rewrite `_parse_score` strict `float | None` (anchored grammar, [0,1] range) — AC5
- [x] T5 [RED] test_gate.py: `make_instruct_judge` model==lm_model/temp==0, bare-number prompt, assert_local-before-egress — AC3,AC4,AC9
- [x] T6 [GREEN] gate.py: implement `make_instruct_judge` over `lm_model`, constrained prompt, raise `ScoreParseError` on None — AC3,AC4,AC6,AC9
- [x] T7 [RED] test_gate.py: instruct non-conforming reply degrades-not-fabricates; whole-gate degrade (D7) — AC6
- [x] T8 [RED] test_gate.py: single distinct non-conformance WARNING; generic "scoring failed" absent; distinct from timeout — AC7
- [x] T9 [GREEN] gate.py: `verify` except branches on `ScoreParseError` first, one distinct WARNING, no double-emit — AC7
- [x] T10 [RED] test_gate.py: both judges degrade identically on a non-conforming reply — AC13
- [x] T11 [GREEN] gate.py: `make_scout_model_judge` raises `ScoreParseError` on None (shared strict contract) — AC13
- [x] T12 [REFACTOR] gate.py: extract shared `_score_or_raise(reply)` used by both judges (folded into T6) — AC6,AC13
- [x] T13 [RED] test_gate.py: correct citation with a good faked score passes (inverted-harm regression) — AC10
- [x] T14 [RED] test_wiring.py: `build_verification_gate` dispatches instruct-by-default / scout_model-on-request — AC8
- [x] T15 [GREEN] wiring.py + gate.py: `select_judge`/`_JUDGE_FACTORIES` dispatch on `verify_method`; retain scout factory — AC8
- [x] T16 [doc] Blast-radius docs: settings.py comment, gate.py docstrings, ARCHITECTURE.md §2.7, README, specs/0018-judge/changelog.md ("B2 mechanism fixed; accuracy deferred to OQ2 re-run") — AC12
- [x] T17 [integration] test_gate.py: live instruct-judge smoke, `@pytest.mark.integration`, skip-not-fail — AC11
