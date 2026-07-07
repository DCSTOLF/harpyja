---
id: "0029"
title: "loop"
status: closed
created: 2026-07-07
authors: [claude]
packages: []
related-specs: [0024, 0027, 0028]
---

# Spec 0029 — loop

## Why

Spec 0028 PROVED generation control (the `max_tokens` cap bounds runaway; `finish_reason`
surfaces the real failure), and its first live run diagnosed the next layer precisely: the
explorer loop **echoes the N parallel `tool_calls` the model emits (measured N=4) but answers only
`tool_calls[0]`**, leaving N−1 unanswered → malformed conversation → turn-2 runaway that the cap
correctly catches as `generation-truncated`. Controlled proof from the 0028 operator run: FULL echo
→ `finish=length` 101s vs TRIMMED-to-answered → `finish=tool_calls` 0.8s.

This is the **SOLE remaining prerequisite** for AC5 localization, and downstream for the 0026 pilot
re-run and the model bake-off. It is the **FOURTH diagnosed layer** in a chain of distinct, real
defects — 0026 (under-powered instrument) → 0027 (eager-map + unbounded generation) → 0028
(generation-control) → this (parallel-tool-call handling). Each layer was a genuine defect;
layered-RCA is working.

**Capability is STILL UNMEASURED** — no model has ever completed a full localization run through
this explorer. So this spec is as much "unblock the first full run and *see what it shows*" as it is
"pass AC5." Treat the first full run as a MEASUREMENT, not an assumed payoff.

Ref: 0024 (explorer loop invariants — the message-handling being changed), 0027 (eager-map removal +
cause taxonomy), 0028 (generation control, `finish_reason`, the turn-2 diagnostic + the A-vs-B fork),
`specs/0028-generation-control/operator-run-findings.md`.

## What

Fix the explorer loop's parallel `tool_call` handling so a turn emitting N>1 `tool_calls` produces a
well-formed conversation (no unanswered call) — the direct fix of the 0028 turn-2 diagnostic — then
run the FIRST full end-to-end localization ever attempted through this explorer and report what it
shows.

**CENTRAL DECISION — DECIDED: PATH (B) `answer-all-N`**

The spec originally considered two paths (carried below for historical context):
- **(A) trim-to-answered** (considered & rejected) — echo only the answered `tool_call`; minimal,
  well-formed, small blast radius on the 0024 loop invariants. BUT discards the N−1 proposed calls
  → the model re-requests them → more turns against the N=10 budget.
- **(B) answer-all-N** (chosen) — execute and echo all N parallel calls the model emitted;
  OpenAI-correct, preserves parallelism → fewer turns. Larger change to the 0024 loop message
  handling, but it is how tool-calling agents actually work, it preserves the turn budget (which
  (A) silently spends), and "answer only the first of N" being the bug suggests the loop was
  never built for parallel calls at all.

**This spec implements (B).** Prove turn-2 clean, and if the choice materially affects
localization quality / turn-count, record the comparison.

**INVARIANT — surgical to the loop's message handling.** Change ONLY the explorer loop's `tool_call`
echo/answer handling. The ScoutBackend/ScoutEngine/Locator seam, the four-tool suite
`{grep,glob,read_span,ls}`, the `submit_citations` contract, the gateway generation knobs (0028), the
cause taxonomy, the orchestrator, the gate, and the matrix stay untouched. No eager repo context
(push→pull holds). No new tools (exact-four holds).

**INVARIANT — the first full run is a MEASUREMENT, not an assumed payoff.** Do NOT assume "fix
parallel handling → AC5 passes → done." This is the first end-to-end localization ever run; expect it
to surface the next thing (wrong-file, right-file-wrong-span, placeholder-value citations — the
AC4-vs-AC5 gap and the 0028 probe's placeholder caveat). The deliverable is a real capability
MEASUREMENT (the right / wrong-file / right-file-wrong-span / empty distribution over the cases), with
AC5-passing as the *hoped-for* outcome, not the definition of done. If a fifth layer appears, name it
via the cause taxonomy and HOLD-BY-CAUSE — do NOT force AC5.

## Acceptance criteria

Legend: `[unit]` = fakes/injected seams; `[integration]` = live, `@pytest.mark.integration`.

1. **[unit] Path (B) parallel `tool_call` handling is correct.** Every emitted `tool_call` is
   executed in the order emitted and its result echoed; the conversation is well-formed with no
   unanswered call. Assert **no emitted `tool_call` is left unanswered** in the conversation sent
   back to the model.
2. **[unit] Malformed-conversation regression guard.** A turn emitting N>1 `tool_calls` does NOT
   produce the 0028 defect (unanswered calls); the specific **N=4 astropy shape** is covered.
3. **[unit] Bounded + read-only preserved.** N parallel calls each stay repo-confined and
   output-clamped — executing all N does NOT bypass per-tool bounds or flood context past the
   truncation policy.
4. **[unit] Terminal call + mixed batch degrade rule.** A `submit_citations` call (terminal action)
   inside a parallel batch is honored immediately and the batch is treated as terminal (remaining
   calls in the batch are not executed). A failed or invalid `tool_call` inside a parallel batch
   (parse error, validation failure, or execution error on any one call) is recorded as a typed
   degrade on that call; the batch continues for other valid calls unless the failure is a terminal
   action. Assert the per-call result and the batch's terminal-vs-continue decision are both
   recorded in the conversation trace.
5. **[unit] Turn-budget interaction recorded.** Assert the per-turn tool-answer behavior (all N
   calls answered in one turn) and its effect on turn count is deterministic — a repeatable-fixture
   test that runs the same injected N=4 astropy-shape turn twice yields identical trace and turn
   count, so AC7's turn-exhaustion-vs-localization is attributable, not confounded by echo handling.
6. **[integration] Turn-2 clean.** A live run reaches a well-formed turn 2 (`finish=tool_calls`, no
   runaway) — the direct fix of the 0028 diagnostic (all-N-answered → 0.8s baseline, same localhost
   `ModelGateway` used throughout, no non-loopback egress).
7. **[integration] THE FIRST FULL RUN (the capability MEASUREMENT).** `astropy__astropy-12907` AND
   `django__django-12774` run end-to-end through the explorer WITHOUT a timeout/backend/
   generation-truncated degrade, within N=10 turns, to a terminal state (`submit_citations` or honest
   turn-exhaustion). Report the per-case bucket (**correct / right-file-wrong-span / wrong-file /
   empty**). Placeholder-value citations are rejected (the AC4-vs-AC5 gap). This is the capability
   MEASUREMENT.
8. **[integration] Harness correctness — AC7 MUST PASS.** Both `astropy__astropy-12907` AND
   `django__django-12774` reach a terminal state (AC7's measurement bucket) without a
   timeout/backend/generation-truncated degrade. The harness drove the model to a decision; degrade
   does NOT mask the outcome. **Asymmetric outcome rule:** if one case hits a degrade
   (`model-unreachable`/`backend-error`/`generation-truncated`), the spec FAILs (harness broken). If
   a case reaches a clean terminal state with an honest-empty or wrong-file bucket (no degrade), that
   is a **CAPABILITY result** — a real measurement, not a harness failure.
9. **[integration] Model capability — reported, not gated.** Per-case localization quality (correct
   / right-file-wrong-span / wrong-file / empty) is reported as the MEASUREMENT. The xfail on
   `test_harness_live.py` converts to xpass ONLY if both cases show AC8 passes (reach terminal
   without degrade). If one case is an honest no-degrade wrong-file/empty, record it; the xfail
   stays or converts to a documented capability finding, distinguishing "harness drove the model"
   (AC8, MUST pass) from "model localized well" (AC9, a measurement).
10. **[doc] If the run surfaces a fifth layer**, name it via the cause taxonomy with a concrete,
   stable machine-readable identifier (pattern: `scout-degraded:<cause>`, matching 0027/0028
   precedent) + HOLD-BY-CAUSE, re-point the xfail reason to the mechanism, and state the (now
   fifth) honest project status. The model bake-off is the named prerequisite follow-up for any
   wrong-file/empty no-degrade outcome.

## Out of scope

- The model bake-off (this UNBLOCKS it).
- The 0026 pilot re-run (unblocked here, not done here).
- The Tier-0 AST symbol tool.
- A total-request wall-clock deadline (0017 caveat).
- Any gateway / generation-knob change (0028 is done).
- Adding / changing tools (suite stays exactly `{grep,glob,read_span,ls}`).
- Re-introducing any eager repo context / map (push→pull holds).

## Open questions

1. **Cap × turn-budget (carried from 0028).** With parallel calls answered in one turn (B), does the
   N=10 budget now suffice where it didn't? Re-confirm AC9's turn-exhaustion-vs-localization is
   attributable, not masked by the budget itself.
