---
spec: "0029"
status: planned
strategy: tdd
---

# Plan — 0029 loop (parallel `tool_call` handling in the explorer)

## The defect, precisely

`harpyja/scout/explorer_loop.py:224` — `run_explorer_loop` echoes the assistant
message with ALL `response["tool_calls"]` (line 210-217) but then dispatches only
`call = tool_calls[0]`. When the model emits N>1 parallel calls (measured N=4 on
`astropy__astropy-12907`), calls `[1:]` receive no `role:tool` answer → the next
`model_call(session.messages())` sends an OpenAI-malformed conversation (an assistant
`tool_calls` entry with no matching `tool_call_id` response) → turn-2 runaway →
`finish=length` → `generation-truncated` degrade (the 0028 turn-2 diagnostic).

**Fix (Path B, `answer-all-N`, decided in review):** iterate every emitted
`tool_call` in emitted order, answering each with a `role:tool` message carrying its
`tool_call_id`, so a turn that continues leaves NO unanswered call. A
`submit_citations` call is terminal at its position (return immediately; remaining
calls in the batch are not executed). A per-call tool failure is a recorded typed
degrade on that call; the batch continues for the other valid calls.

The whole change is surgical to the per-turn dispatch block
(`explorer_loop.py:219-261`). No touch to `ScoutBackend`/`ScoutEngine`/`Locator`,
the four-tool suite, `submit_citations`, gateway knobs, cause taxonomy, orchestrator,
gate, or matrix (invariant).

All unit tests are added to `harpyja/scout/test_explorer_loop.py` (Go-style sibling;
here the Python convention — test next to the code under test). Naming follows
`conventions.md`: `test_<subject>_<scenario>`.

## Design decisions baked into the plan

- **Turn accounting (AC5/AC7):** a batch of N calls is still ONE turn —
  `turns_used` increments once per `model_call` (the `for` loop head), never per
  tool call. N=10 turn budget is unaffected.
- **Terminal precedence (AC4 / OQ2):** the batch is scanned in emitted order; a
  `submit_citations` returns `LoopResult(SUBMITTED, …)` at its position — calls after
  it are not dispatched. The "no unanswered call" invariant (AC1) binds only the
  CONTINUE path (a terminated conversation has no next model turn to malform).
- **Per-call degrade (AC4 continue-branch, closes the review's graceful-degradation
  gap):** a tool that raises, or invalid args, is caught INSIDE the batch loop and
  recorded as a `role:tool` degrade answer with a stable marker
  (`TOOL_CALL_DEGRADE = "tool-call-degraded:<cause>"`, `cause ∈
  {execution-error, unknown-tool}`) and a `kind="degrade"` record; the batch
  continues. This is a behavior change from today's "any tool exception →
  `BACKEND_ERROR` kills the loop": a single failing call in a batch must not lose the
  other N−1 answers. A WHOLE-loop crash outside a tool call still degrades as before.
- **Loop-detection + truncation:** `note_navigation` / repeat-check / `maybe_truncate`
  run PER navigation call inside the batch (identical to today's behavior at N=1), so
  every existing self-recovery test is unchanged.

## Test-first sequence

### Step 1 — Parallel navigation batch is fully answered, in order, terminal-in-batch honored (RED)
- Add to `harpyja/scout/test_explorer_loop.py`:
  - `test_parallel_tool_calls_all_answered_none_unanswered` — turn 1 emits `[grep#c0,
    glob#c1]`, turn 2 submits. Assert EVERY emitted `tool_call_id` (`c0`, `c1`) has a
    matching `role:tool` message in `result.history` (build the set of answered ids;
    assert it ⊇ the emitted ids). This is the AC1 "no emitted tool_call left
    unanswered" assertion.
  - `test_parallel_tool_calls_executed_in_emitted_order` — recording tools capture
    call order; assert dispatch order equals emitted order (`grep` before `glob`).
  - `test_n4_astropy_shape_batch_all_answered_regression_guard` — AC2: a fixed N=4
    batch (`grep#a, glob#b, ls#c, read_span#d` — the astropy shape) on turn 1, submit
    on turn 2. Assert all 4 ids answered and `result.outcome == SUBMITTED`. This is
    the explicit 0028 malformed-conversation regression guard.
  - `test_submit_citations_in_parallel_batch_is_terminal_remaining_not_executed` —
    AC4/OQ2: batch `[grep#c0, submit_citations#c1, grep#c2]`. Assert `outcome ==
    SUBMITTED`, spans come from the submit args, the leading `grep#c0` WAS executed and
    answered, and the trailing `grep#c2` was NOT executed (recording tool shows one
    grep call) and has no tool answer.
  - `test_bounded_tools_apply_to_every_call_in_parallel_batch` — AC3: a batch of N
    `read_span` calls with over-budget ranges routed through the REAL
    `build_explorer_tools` closures (a tmp repo); assert each of the N results is
    clamped/confined (no call bypasses `read_snippet` bounds). Fails today because
    calls `[1:]` are never executed.
  - `test_turn_two_reached_after_parallel_batch_all_answered` — AC6 mechanism (unit
    twin of the live proof): turn 1 = N=4 batch, turn 2 = `grep`, turn 3 = submit.
    Assert `result.turns_used == 3` and the loop reached turn 2/3 (i.e. it did not
    wedge or degrade) — the deterministic form of "turn 2 clean".
- Tests fail: `explorer_loop.py` dispatches only `tool_calls[0]`, so calls `[1:]` are
  unanswered (ids missing), out-of-order/never-executed, submit at index >0 is never
  seen (no SUBMITTED), and the N=4 batch derails.

### Step 2 — Answer-all-N in-order dispatch with terminal precedence (GREEN)
- Rewrite the per-turn dispatch block in `harpyja/scout/explorer_loop.py`
  (currently lines 219-261): replace `call = tool_calls[0]` with
  `for call in tool_calls:` iterating in emitted order. For each call:
  - `submit_citations` → `return LoopResult(SUBMITTED, submit(...), turns_used, …)`
    immediately (remaining calls not dispatched).
  - unknown tool → append a `role:tool` answer (matching `tool_call_id`) with the
    existing "unknown tool" error content; continue the batch.
  - known navigation tool → execute, append the `role:tool` observation with its
    `tool_call_id`, then run `note_navigation` / repeat-corrective / `maybe_truncate`
    for THAT call.
  - Extract a small `_answer_tool_call(session, call, tools) -> LoopResult | None`
    helper (returns a `LoopResult` only on the terminal submit; else `None` and the
    batch continues) to keep the turn loop readable.
- All Step-1 tests pass; every pre-existing `test_explorer_loop.py` test (single-call
  terminate/one-per-turn/turn-cap/wall-clock/unknown-tool/loop-detection/truncation/
  finish-length) still passes unchanged (N=1 is the identity case of the new loop).

### Step 3 — Per-call failure inside a batch is a typed degrade; batch continues (RED)
- Add to `harpyja/scout/test_explorer_loop.py`:
  - `test_failed_tool_call_in_batch_recorded_as_typed_degrade_batch_continues` —
    AC4: batch `[grep_ok#c0, grep_raises#c1, glob_ok#c2]` where `grep_raises` throws.
    Assert (a) `c1` has a `role:tool` answer whose content carries the stable marker
    `tool-call-degraded:` (per-call result recorded), (b) `c0` and `c2` were executed
    and answered (batch continued past the failure), (c) no `ScoutUnavailable`/raw
    exception propagates out of `run_explorer_loop`, and (d) the trace records a
    `kind="degrade"` entry for `c1`.
  - `test_invalid_args_tool_call_in_batch_degrades_that_call_only` — a call whose args
    make the tool raise `TypeError` (bad kwargs) is degraded on that call; siblings
    answered.
  - `test_batch_terminal_after_failed_call_still_honored` — batch `[grep_raises#c0,
    submit_citations#c1]`: the failure is recorded AND the terminal submit is still
    honored (`outcome == SUBMITTED`) — a failure is not terminal, but a real terminal
    after it is.
- Tests fail: Step-2 code lets a raising tool propagate (no per-call try/except); the
  exception escapes `run_explorer_loop` and the batch is aborted.

### Step 4 — Per-call try/except typed degrade (GREEN)
- In `harpyja/scout/explorer_loop.py`, add module constant
  `TOOL_CALL_DEGRADE = "tool-call-degraded"` and, inside `_answer_tool_call`, wrap the
  `tools[name](**args)` dispatch in `try/except Exception`: on failure append a
  `role:tool` answer with `content=f"{TOOL_CALL_DEGRADE}:execution-error: {err}"` and
  record it `kind="degrade", cause="execution-error"`; do NOT re-raise; continue the
  batch. Give the unknown-tool branch the same `kind="degrade",
  cause="unknown-tool"` record + `tool-call-degraded:unknown-tool` marker for one
  consistent per-call degrade shape.
- All Step-3 tests pass; the whole-loop `BACKEND_ERROR` path in
  `explorer_backend.py` is untouched (still catches a crash OUTSIDE a tool call).

### Step 5 — Turn-trace + turn-count determinism on the N=4 fixture (RED → GREEN)
- Add to `harpyja/scout/test_explorer_loop.py`:
  - `test_n4_astropy_shape_turn_trace_is_deterministic_across_two_runs` — AC5: build
    the SAME injected N=4 astropy-shape turn (via a repeatable-fixture factory that
    returns fresh identical scripted models + fresh recording tools), run
    `run_explorer_loop` TWICE, assert `result.history` (rendered) AND
    `result.turns_used` are byte-for-byte / value identical across both runs, AND the
    trace has all 4 tool answers (the well-formed shape). The "all 4 answered + one
    turn for the batch" assertion is what fails pre-fix; the identity assertion guards
    against any nondeterminism introduced by the batch loop (dict ordering, set
    iteration).
- Pre-Step-4 this fails (only 1 of 4 answered); post-Step-4 it passes. If the batch
  loop introduced any ordering nondeterminism, the identity half fails and is fixed by
  pinning emitted-order iteration (already the case) — no new production code expected
  beyond Steps 2/4.

### Step 6 — Refactor (optional, recommended)
- Fold the three per-call outcomes (terminal / degrade / navigation-observation) into
  the single `_answer_tool_call` helper introduced in Step 2, so the terminal-return,
  the degrade-record, and the observation-record share one append path and the turn
  loop body is a clean `for call in tool_calls: term = _answer_tool_call(...); if
  term: return term`. Remove the now-duplicated arg-parse/`call_id` extraction.
- All unit tests still pass; no behavior change.

### Step 7 — Live integration: turn-2 clean + FIRST FULL RUN + xfail→xpass (RED via live)
- `harpyja/scout/test_explorer_integration.py` (skip-not-fail, same localhost-only
  `ModelGateway`, same `_deny_nonloopback_egress` guard already in the file — AC6's
  "no non-loopback egress"): add
  - `test_live_parallel_batch_reaches_wellformed_turn_two` — AC6: drive the live
    loopback model on a small repo; assert the run reaches a well-formed turn 2 (no
    `generation-truncated` / runaway) OR terminates cleanly within budget. Loopback is
    permitted by the air-gap rule (clarified in spec review §6); the egress guard
    proves no non-loopback traffic.
- `harpyja/eval/test_harness_live.py` — AC7/AC8/AC9: the existing
  `test_explorer_localizes_without_degrade_within_n_turns` (astropy + django,
  parametrized) currently `@pytest.mark.xfail(strict=False)` naming THIS loop fix as
  the blocker. Convert it to `xpass` per AC9: remove the `xfail` marker (or flip to
  `strict=True` gated on the harness passing) so that, with the loop fix landed, both
  cases must reach a terminal state WITHOUT a `_HARNESS_DEGRADES` cause (AC8 MUST
  PASS). Report the per-case bucket (correct / right-file-wrong-span / wrong-file /
  empty) — capability is REPORTED, not gated (the existing final `bucket in {CORRECT,
  RIGHT_FILE_WRONG_SPAN}` assertion is the recorded measurement, kept as the
  capability line; AC8's `cause not in _HARNESS_DEGRADES` is the load-bearing gate).
  Placeholder citations (`path in {"string","path",""}`) already rejected in the test.
- These are integration tasks: they go GREEN when the Step-2/4 loop fix is live against
  the served stack; on a host with no stack they skip (CI-safe).

### Step 8 — Fifth-layer disposition (AC10, conditional doc)
- Only if Step 7's first full run surfaces a NEW blocker (a fifth layer): name it via
  the cause taxonomy with a stable identifier `scout-degraded:<cause>`
  (`harpyja/scout/errors.py` pattern), re-point the `test_harness_live.py` xfail reason
  to the concrete mechanism, HOLD-BY-CAUSE, and record the (fifth) honest project
  status in `specs/0029-loop/operator-run-findings.md`. The model bake-off is the named
  prerequisite follow-up (Out of scope here — this UNBLOCKS it). If the run is clean
  (terminal, no harness degrade, any bucket), AC8 passes and no fifth layer is named.

## Delegation

- Steps 1-6 (loop message-handling unit RED→GREEN→REFACTOR) → keep in-agent /
  `tdd-implementer`: single-file surgical change with a dense existing test suite; the
  strength match is precise pytest fixtures + the `_Session` bookkeeping already local
  to `explorer_loop.py`.
- Step 7 (live integration + xfail flip) → delegate to an operator with the served 16B
  stack at `127.0.0.1:8131` (reason: AC7/AC8 are a live MEASUREMENT that cannot run in
  a stackless CI sandbox; the unit twins in Steps 1/5 pin the mechanism deterministically
  so CI stays green).
- Step 8 (taxonomy/doc) → `spec-closer` (reason: cause-taxonomy identifier + HOLD-BY-CAUSE
  + status wording is the close-record discipline, not code).

## Risk

- **Per-call degrade changes the whole-loop failure posture** (a raising tool used to
  kill the loop as `BACKEND_ERROR`; now it's a per-call degrade and the batch
  continues) → mitigation: Step 3/4 pin the new behavior explicitly; the whole-loop
  `except Exception → BACKEND_ERROR` in `explorer_backend.py` is left intact for a
  crash OUTSIDE a tool call, so a genuine backend failure still degrades. Assert no
  existing `test_explorer_backend.py` degrade test regresses.
- **Loop-detection / truncation semantics shift if run per-batch instead of per-call**
  → mitigation: run `note_navigation`/`maybe_truncate` PER navigation call (N=1 =
  identity); the full existing self-recovery suite is the regression guard.
- **Turn-count drift** (a batch mis-counted as N turns would blow the N=10 budget /
  AC5 determinism) → mitigation: `turns_used` stays incremented once per `model_call`;
  `test_turn_two_reached_after_parallel_batch_all_answered` and the determinism test
  both assert the exact `turns_used`.
- **AC8 hard-gate on a live stack that may be down** → mitigation: the harness test is
  skip-not-fail without the stack; the operator run (Step 7) is where AC8 MUST PASS,
  and Steps 1/5 give a stack-free deterministic proof of the well-formed conversation.
- **Terminal-in-batch leaves calls after submit unanswered** → not a defect by design
  (a terminated conversation has no next turn); AC1's invariant is scoped to the
  CONTINUE path, asserted by
  `test_submit_citations_in_parallel_batch_is_terminal_remaining_not_executed`.
