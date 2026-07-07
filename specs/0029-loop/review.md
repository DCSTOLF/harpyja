---
spec: "0029"
title: "loop"
reviewers: [codex, claude-p]
quorum: 1
verdict: approve-with-comments
generated: 2026-07-07T00:00:00Z
rounds: 1
---

# Cross-model review — 0029 (loop)

One round. **codex: changes-requested. claude-p: approve-with-comments.** Quorum (1
approve/approve-with-comments) is **met** on claude-p alone, but both agents converge —
independently — on the same crux the spec itself flags as unresolved: **the spec's own
text defers its central decision ("A vs B — decide in review before plan") and its
sharpest sub-question (OQ2) to this review, and neither is actually decided on the page.**
A quorum-mechanical "approve-with-comments" is technically correct, but treating this as a
plain pass-through to `/speccraft:spec:plan` would ignore the spec's own instruction. The
right read: this review **is** the decision point the spec asked for — resolve A vs B and
OQ2 here, bake the resolution into `spec.md`, then plan.

## codex

**Verdict:** changes-requested

Concerns:
- A vs B unresolved; the spec defers to review but the acceptance criteria are written to
  depend on which path is chosen (AC1 in particular reads as two mutually exclusive specs
  glued together).
- The (B) path is under-specified for mixed parallel batches — specifically
  `submit_citations` issued alongside navigation calls in the same batch (OQ2).
- AC5/AC6 require live backend access, which codex reads as in tension with the air-gap
  guardrail unless a test-time egress exception is stated explicitly.
- No graceful-degradation spec for per-tool failure inside a parallel batch — a failed
  tool call, invalid args, or a terminal call colliding with navigation calls in the same
  turn has no defined fallback.
- AC7 mixes three distinct concerns (harness correctness, model capability measurement,
  xfail policy) into one criterion, weakening its pass/fail clarity.

Suggestions:
- Resolve A vs B before implementation planning; if (B), define ordering, per-call failure
  handling, terminal-call precedence, and the echo format explicitly.
- Add a state-machine description of one assistant turn: receive calls → validate →
  execute → append results → detect terminal → continue/stop.
- Distinguish offline/unit measurement from live/operator measurement, and document the
  air-gap exception explicitly if the live AC5/AC6 runs are approved as-is.
- Split AC6 (harness health) and AC7 (capability reporting + xfail policy) into separate
  criteria.
- Require a concrete, typed identifier format for the possible fifth-layer cause (AC8),
  not prose alone — matching the `scout-degraded:<cause>` pattern established in 0027/0028.

Guardrail violations:
- Air-gap: AC5/AC6 require a live backend without stating an exception.
- Graceful degradation: AC1–AC4 don't define a fallback for failed/invalid/conflicting/
  terminal parallel calls.

Convention violations:
- Parallel tool-calls: OQ2 leaves mixed-batch semantics — including a terminal call inside
  a parallel batch — unresolved.
- Cause taxonomy: AC8 requires a typed identifier for a possible fifth layer but doesn't
  define its format.

## claude-p

**Verdict:** approve-with-comments

Concerns:
- OQ1 is left as "lean B," not decided — the spec says to resolve it in review before
  plan, and AC1 currently carries two mutually exclusive definitions (one per path).
- OQ2 is flagged as "a sharp sub-question that could complicate B" but never folded into
  AC1/AC2 as a testable condition.
- AC4's "determinism assertion" is soft/unfalsifiable as written — no concrete test shape
  is named.
- AC7's fallback (xfail stays, or converts to a documented capability finding) doesn't
  name a concrete follow-up, breaking from the HOLD-BY-CAUSE convention's pattern of
  naming the next spec.

Suggestions:
- Resolve OQ1 as (B) explicitly in the review, and rewrite AC1/AC2 against (B) only —
  drop the (A) branch from the acceptance criteria (keep it in Why/What as the
  considered-and-rejected alternative).
- Promote OQ2 to an explicit AC/invariant with a decided answer (e.g., "a
  `submit_citations` call inside a parallel batch is honored as terminal; the batch's
  remaining calls are not executed").
- Make AC4 concrete: a repeatable-fixture test (same injected N=4 astropy-shape turn run
  twice → identical trace/turn-count).
- Name the model bake-off explicitly as the AC7/AC8 follow-up for a wrong-file/empty,
  no-degrade outcome, matching how 0026/0027/0028 each named their next spec.

No guardrail or convention violations found. The spec correctly re-pins the invariants
(surgical to loop message handling only; four-tool suite untouched; no eager context;
measurement-not-payoff framing) and uses good HOLD-BY-CAUSE framing for a possible fifth
layer.

## Synthesis

**Convergent (both agents, load-bearing):**
1. **A vs B is not actually decided.** The spec says "lean B" and defers to review; both
   agents independently flag this as the top blocker, and both flag that AC1 as written
   straddles both paths. This has to be a real decision on the page, not a review-round
   artifact — a plan built against an undecided fork will either stall or silently commit
   to one path without recording why.
2. **OQ2 (mixed batch: terminal call + navigation calls in the same parallel batch)
   must become an explicit, testable AC, not an open question.** Both agents single this
   out as the sharpest unresolved sub-question inside (B); it is also the case most likely
   to interact with the existing `submit_citations` strict-terminal-action convention
   (spec 0024 AC6/OQ2) in a way that isn't yet reasoned through.
3. **AC4 and AC7 both need concreteness.** AC4's determinism claim needs a named,
   repeatable test shape (claude-p); AC7 conflates three different kinds of pass/fail and
   needs a named follow-up per HOLD-BY-CAUSE (claude-p) or an outright split (codex) —
   these are the same gap read two ways.

**codex-only, assessed:**
- The **per-tool-failure graceful-degradation gap** (a failed tool call, invalid args, or
  a terminal-vs-navigation collision inside one batch) is a real, unaddressed gap — the
  spec's ACs prove the *happy path* of parallel-call echo but say nothing about what
  happens when one of N calls in a batch fails. This should be added regardless of
  which path is chosen, and it overlaps directly with OQ2.
- The **AC8 cause-identifier format** gap is real and easy to close — 0027 and 0028 both
  named the exact stable string (`scout-degraded:generation-truncated`, etc.) up front;
  AC8 should do the same or explicitly state the identifier will be named at discovery
  time (acceptable, but should say so).
- The **air-gap guardrail claim on AC5/AC6 is very likely a false positive.** The Model
  Gateway's air-gap rule permits calls to a loopback/localhost endpoint by design (see
  `guardrails.md`), and 0027's AC5/AC6 and 0028's AC4–AC8 both ran identical live,
  local-backend integration tests without any air-gap flag in either of those reviews.
  Nothing in 0029 proposes non-loopback egress. This reads as codex applying the rule
  too literally to "live backend access" rather than to "non-local egress." Recommend a
  single clarifying line in the spec (state the AC5/AC6 backend is the same
  localhost-only `ModelGateway` used throughout) rather than treating this as a genuine
  block — but it costs nothing to add and removes the ambiguity for future reviewers.

## Action

**Quorum is met (claude-p approve-with-comments), but the spec's own text asks this
review to resolve OQ1 before planning — treat that as still owed.** Recommend the spec
author fold the following into `spec.md` before `/speccraft:spec:plan`, rather than
carrying them as open follow-ups into the plan:

1. **Decide OQ1 = (B).** Rewrite AC1 against (B) only; move (A) to Why/What as the
   considered-and-rejected alternative with the turn-budget rationale already in the spec.
2. **Promote OQ2 to an AC or invariant with a decided answer** — a terminal
   (`submit_citations`) call inside a parallel batch is honored immediately; remaining
   calls in that batch are not executed (or the spec's own chosen alternative), plus a
   one-line degrade rule for a failed/invalid call inside a batch (closes codex's
   graceful-degradation gap in the same edit).
3. **Make AC4 concrete** with a named, repeatable fixture test (same injected shape run
   twice → identical trace).
4. **Split or tighten AC7**: separate harness-correctness (must pass) from
   capability-measurement (reported) from xfail policy, and name the model bake-off as the
   explicit follow-up for a no-degrade wrong-file/empty outcome.
5. **Name AC8's cause-identifier format** (or state it is named at discovery time,
   matching the fifth-layer framing already in Why).
6. **One clarifying line on AC5/AC6's backend** (same localhost-only `ModelGateway`) to
   close codex's air-gap flag without further debate.

With those six folded in, the spec is plan-ready. None of them change the spec's spine
(surgical loop-only change, four-tool suite untouched, measurement-not-payoff posture) —
they sharpen the fork the spec already named as needing a decision.
