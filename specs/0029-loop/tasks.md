---
spec: "0029"
status: complete
---

# Tasks

- [x] T1 — RED: parallel navigation batch fully answered, in order, N=4 astropy regression, terminal-in-batch honored, bounded-per-call, turn-2 reached (AC1/AC2/AC3/AC4/AC6-unit)
- [x] T2 — GREEN: answer-all-N in-order dispatch with `submit_citations` terminal precedence (`explorer_loop.py`)
- [x] T3 — RED: per-call tool failure / invalid args recorded as typed degrade, batch continues, terminal-after-failure honored (AC4)
- [x] T4 — GREEN: per-call `try/except` typed degrade (`TOOL_CALL_DEGRADE`), batch continues (`explorer_loop.py`)
- [x] T5 — RED→GREEN: N=4 astropy-shape turn trace + turn_count deterministic across two runs (AC5)
- [x] T6 — REFACTOR: fold terminal/degrade/observation paths into one `_answer_tool_call` helper
- [x] T7 — INTEGRATION: live turn-2 clean + no non-loopback egress + FIRST FULL RUN (astropy+django) + xfail→xpass, AC8 gate (AC6/AC7/AC8/AC9)
- [x] T8 — DOC (conditional): if a fifth layer surfaces, name `scout-degraded:<cause>`, re-point xfail, HOLD-BY-CAUSE, record status, name bake-off follow-up (AC10)
