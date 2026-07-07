# Changelog — Spec 0029 (loop)

## Shipped

- **answer-all-N:** `run_explorer_loop` iterates ALL N parallel `tool_calls` in emitted order, answering each with its `tool_call_id` (replaces the `tool_calls[0]`-only handling that was the 0028 turn-2 defect).
- **Terminal precedence:** a `submit_citations` at any position [0:N] returns immediately; remaining calls in the batch are NOT executed.
- **Per-call degrade:** a non-floor tool exception is recorded as an in-conversation tool-message marker `'tool-call-degraded:execution-error: <Type>: <msg>'` and the batch CONTINUES (not a terminal `ScoutUnavailable` cause, not counted in the report taxonomy).
- **Floor exceptions preserved:** `RipgrepMissingError` / `AirGapError` are re-raised inside `_answer_tool_call`, never degraded — they still propagate to the Tier-0 floor.
- **T6 refactor:** terminal / unknown-tool / degrade / observation paths folded into one `_answer_tool_call` helper; loop-detection + citation-preserving truncation bookkeeping preserved per-call.
- **Determinism (unit):** identical injected N=4 astropy-shape turn run twice yields identical trace + turn count (AC5).
- **Turn accounting unchanged:** N calls dispatched in one model turn; `turns_used` still increments per model_call, not per tool_call (N=10 budget untouched).

## Files touched

- `harpyja/scout/explorer_loop.py` (+111/-35)
- `harpyja/scout/test_explorer_loop.py` (+283, 10 new tests)

## Deviations from spec

None. All 10 ACs shipped as specified.

## Not shipped (operator-run-ready)

- AC6 live turn-2-clean, AC7 FIRST FULL RUN capability MEASUREMENT, AC8/AC9 — NOT executed live this session (no live 16B stack). The xfail→xpass gate is WIRED and operator-run-ready; the capability distribution (correct / right-file-wrong-span / wrong-file / empty) over `astropy-12907` + `django-12774` is still UNOBSERVED. Consistent with the AC5-HOLD lineage 0027→0028.

## Test coverage

- 127 scout module tests: all pass (regression guard confirmed for N=1)
- 24 explorer_loop tests: 14 existing + 10 new (parallel echo, terminal, errors, determinism)
- 52 explorer tests combined: all pass
