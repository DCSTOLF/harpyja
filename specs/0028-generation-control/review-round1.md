---
spec: "0028"
date: 2026-07-07
agents: [codex, claude-p]
verdicts:
  codex: changes-requested
  claude-p: changes-requested
quorum: 1
quorum_met: false
recommendation: changes-requested
status: draft
---

# Cross-model review — 0028-generation-control

## codex (codex-cli 0.140.0, model gpt-5.5)

**Verdict:** changes-requested

Concerns:
- AC1 conflicts with the What section: AC1 says thinking-off is pre-decided and required, while What says thinking-off may be optional after empirical comparison.
- AC3 is not fully testable as written because `ModelGateway.complete_with_tools` currently does not surface `finish_reason`; the spec must require an API/return-shape change or define where truncation is detected.
- AC7 is left too open for an implementation spec: Deep-tier scope must be decided here, not deferred to the implementer.
- AC5 depends on a live local model stack and N=10 turns, but does not define exact command, fixture selection, timeout budget, or success assertion shape.

Suggestions:
- Decide whether `enable_thinking:false` is mandatory or experimentally chosen; then align AC1, AC6, and the What section.
- Specify the exact stable degrade cause for `finish=length` without a valid tool_call, e.g. `scout-degraded:generation-truncated`.
- Require `finish_reason` to be returned by `complete_with_tools` (or wrapped into a typed gateway result) so AC3/AC4 can be asserted without log scraping.
- State Deep-tier RLM is explicitly out of scope unless there is a concrete reason to apply the knobs there too.

Convention violations flagged:
- CAUSE TAXONOMY — location AC3 (no stable cause identifier specified for truncation-without-tool-call).
- DRIFT-GUARD ON DEFAULTS — location AC2 (drift-guard mentioned only in relation to Settings, not the constructed object's own field default per convention).

## claude-p (claude -p)

**Verdict:** changes-requested

Concerns:
- AC3 and AC4 both hinge on `finish_reason` (`finish=length` vs `finish=tool_calls`), but per repo memory `complete_with_tools` currently returns ONLY `{content, tool_calls}` and does NOT surface `finish_reason`. The "What" only describes threading new Settings knobs INTO the request — it never states the gateway's return contract must be extended to expose `finish_reason` OUT. Without that, AC3 and AC4 cannot be implemented or unit-tested as written.
- AC5 requires BOTH astropy and django to localize within N=10 turns, but the spec has no stated handling for an asymmetric outcome (one localizes, the other doesn't). Prior specs use HOLD-BY-CAUSE for exactly this kind of partial result; this spec should say whether a single-instance failure is a hold, a fail, or needs a new cause label.
- AC2's default is only bounded below ("> 512") with no pinned value, while AC6 asks the implementer to empirically choose between thinking-off and thinking-capped against localization quality. Two empirical choices (max_tokens default AND thinking mode) resolved by the same AC6 comparison is underspecified — unclear if AC6 jointly sweeps both knobs or holds max_tokens fixed at 2048 while only varying thinking.
- The interaction between the new per-call max_tokens cap (AC2) and the fixed N=10 turn budget (AC5) is not discussed. A tighter cap could force the model into more, smaller tool-call turns to reach a citation, making turn-budget exhaustion a NEW confound distinct from "can't localize" — the same degrade-masks-outcome trap that motivated this spec's own AC5 framing.

Suggestions:
- Add an explicit item requiring `complete_with_tools`'s return dict to gain an additive `finish_reason` key (with a unit test pinning it). Flag this as an additive-return-contract change alongside the additive-Settings-field changes already scoped.
- State explicitly in AC5 (or the close) what happens on an asymmetric pass (e.g., "partial pass is a hold on the failing instance, not a spec-wide fail, recorded with its own cause").
- Pin AC2's default explicitly (e.g., 2048, matching the probe's clean result) rather than only a floor, or explicitly say the default is set empirically during AC6 and the doc will be updated post-hoc.
- Name the new Settings fields with an explorer-scoped prefix (e.g. `explorer_max_tokens`, `explorer_enable_thinking`) so AC7's scope boundary (explorer-only, not Deep-tier RLM) is enforced by naming/call-site structure, not just prose.
- Note whether N=10 remains appropriate given the new cap, or confirm it's inherited unchanged from 0026/0027.

No guardrail or convention violations flagged (assessment framed as gaps rather than violations, but substantively overlaps with codex's CAUSE TAXONOMY / DRIFT-GUARD findings above).

## Consensus (both agents agree — strongest signals)

1. **BLOCKING — `finish_reason` is not surfaced by the gateway.** Both agents independently identified, without prompting from each other, that `ModelGateway.complete_with_tools` currently returns only `{content, tool_calls}` and has no `finish_reason` field. AC3 ("truncation is a failure") requires detecting `finish=length` without a valid tool call; AC4 ("LIVE first-call latency") requires verifying `finish=tool_calls`. Both criteria are literally unwritable as unit/guard tests against the current return contract. The spec's "What" section only describes threading new knobs **into** the request (inbound); it says nothing about extending the gateway's return shape **out**. This is the single load-bearing gap in the spec — everything else is secondary to fixing this.
2. **AC1 ↔ What internal inconsistency on thinking-off.** codex calls this out directly (AC1 says pre-decided/mandatory, What/AC6 say empirically chosen); claude-p's AC2/AC6 concern about two empirical choices resolved by one comparison is a variant of the same underlying tension — the spec has not decided what is fixed vs what is experimentally swept.
3. **AC7 (Deep-tier scope) is under-specified**, though the two agents differ on remedy (see disagreement below) — both agree the current "state explicitly... at close" framing leaves a scope-creep risk that a Settings-level change (not call-site-scoped) could silently reach the Deep-tier RLM path.
4. **AC2's default/drift-guard treatment is incomplete** — codex flags the drift-guard convention (own-field default, not just Settings) is not addressed; claude-p flags the default itself is only a floor ("> 512"), not pinned. Both are pointing at the same underspecified AC2 default-value story.

## Concerns by agent — de-duplicated, ranked by severity

**BLOCKING**

1. **`finish_reason` not surfaced by `complete_with_tools`** (codex + claude-p, independently, strongest signal). AC3 and AC4 are unimplementable/untestable as written. Fix: add an explicit additive-return-contract item requiring `complete_with_tools` to return a `finish_reason` key (or equivalent typed field), with a unit test pinning it — presented as a same-class change alongside the additive-Settings-field changes already in scope.
2. **AC1 vs What/AC6 inconsistency on whether thinking-off is mandatory or empirically chosen** (codex, sharpened by claude-p's related AC2/AC6 point). As written, AC1 mandates `enable_thinking:false`, while What and AC6 frame it as an empirical comparison. These cannot both be literally true; the spec must pick one framing and align AC1/AC6/What.
3. **AC3 lacks a stable cause-taxonomy identifier** (codex, convention violation: CAUSE TAXONOMY). "handled as a degrade, never silently swallowed" needs a named cause (e.g., `scout-degraded:generation-truncated`) so downstream tooling/close-notes can rely on it.

**MODERATE (soft-blocking — should be resolved before implementation, but narrower fixes)**

4. **AC7 Deep-tier scope left to implementer/close-time** (codex + claude-p, disagreement on remedy — see below).
5. **AC2 default not pinned, only floored** (claude-p) + **drift-guard convention gap on AC2** (codex, convention violation: DRIFT-GUARD ON DEFAULTS). Combined: AC2 should state a concrete default (e.g., 2048) and specify where the drift-guarded own-field default lives per convention, not just "Settings."
6. **AC5 has no stated handling for an asymmetric pass** (claude-p). One instance localizing and the other not is a plausible real outcome given HOLD-BY-CAUSE precedent in this spec chain; the spec should say whether that's a hold, a fail, or a new cause label, rather than leaving it to be discovered live on the 16B stack.

**SOFT (worth noting, not blocking)**

7. **AC5's live-run mechanics under-specified** — exact command, fixture selection, timeout budget, success-assertion shape (codex).
8. **max_tokens cap × N=10 turn-budget interaction unexamined** (claude-p) — a tighter cap could force more/smaller turns, turning turn-budget exhaustion into a new confound distinct from "can't localize," which is the exact trap this spec's own AC5 framing was written to avoid.
9. **Settings field naming for explorer-only scope enforcement** (claude-p suggestion) — name new fields with an `explorer_` prefix so AC7's boundary is structurally enforced, not just asserted in prose.

## Disagreement flagged

On **AC7 (Deep-tier RLM scope)**, the two agents diverge on remedy:
- **codex**: resolve it *in the spec text now* — the spec should state directly "Deep-tier RLM is out of scope and must not be changed," not defer the decision to the implementer or the close.
- **claude-p**: recording the decision *at close* is acceptable in spirit (mirrors how this spec chain already records empirical/scope decisions at close, e.g. AC6), provided the explorer-only scope is *structurally* enforced via call-site wiring and Settings field naming (e.g., `explorer_max_tokens`) rather than left to prose alone.

Both agree the current state (a bare "state explicitly whether... in or out of scope" instruction with no lean) is too open. The spec author should pick one of these two remedies — either commit to "Deep-tier out of scope" as spec text now (codex's stronger position), or keep record-at-close but add the naming/call-site enforcement claude-p proposes as a structural backstop.

## Recommended spec edits (ranked, concrete)

1. **Add an explicit AC (or fold into AC3/AC4) requiring `ModelGateway.complete_with_tools`'s return contract to gain an additive `finish_reason` key**, pinned by a unit test, alongside the existing additive-Settings-field changes. This is the load-bearing fix — without it AC3 and AC4 cannot be built or tested as currently worded.
2. **Resolve the AC1/What/AC6 tension**: either (a) state in the What section and AC1 that `enable_thinking:false` is a fixed, mandatory mechanism decision (already measured/settled per the Grounding addendum) and AC6 records only *why* it was chosen, not *whether*; or (b) reframe AC1 as "the knob exists and is wired" while explicitly deferring the on/off *choice* to the AC6 empirical comparison. Pick one and make AC1/AC6/What textually consistent.
3. **Give AC3 a named, stable cause-taxonomy identifier** for truncation-without-tool-call (e.g. `scout-degraded:generation-truncated`), matching the cause-taxonomy convention already used elsewhere in this spec chain.
4. **Decide Deep-tier RLM scope now, in spec text** (per codex): state "Deep-tier RLM path is out of scope; the new knobs apply only to the explorer's tool-calling path" — or, if keeping record-at-close, add claude-p's structural backstop: name new Settings fields with an `explorer_` prefix and ensure only the explorer call site passes them.
5. **Pin AC2's default value explicitly** (e.g., 2048, matching the probe's clean measured result) rather than only a floor ("> 512"), and state where the drift-guarded own-field default lives per convention (not just "Settings-controlled").
6. **State AC5's handling of an asymmetric outcome** (one instance localizes, the other doesn't) — hold-by-cause on the failing instance vs. spec-wide fail vs. a new cause label — consistent with this spec chain's existing HOLD-BY-CAUSE precedent.
7. *(Lower priority, non-blocking)* Note whether N=10 turns remains appropriate given the new max_tokens cap, and/or flag the cap×turn-budget confound risk explicitly so it's watched for during the AC5 live run rather than discovered as a surprise.
8. *(Lower priority, non-blocking)* Tighten AC5's live-run mechanics (exact command, fixture selection, timeout budget, success-assertion shape) if not already covered by referenced docs (`operator-run-findings.md`, `changelog.md`).

## Quorum

Quorum requirement: 1 approve or approve-with-comments.
Result: **NOT MET** — both codex and claude-p returned `changes-requested`; neither approved.

Per policy, the spec **stays `draft`** and does not advance until the blocking finish_reason gap (and, ideally, the AC1/AC6 consistency and AC7 scope items) are addressed and the spec is re-reviewed.

## Synthesis

Both independent reviewers converge on the same load-bearing blocker without prompting each other: `ModelGateway.complete_with_tools` does not currently return `finish_reason`, and AC3/AC4 as written cannot be implemented or unit-tested without it. This is a single, additive, well-scoped fix (add a `finish_reason` key to the return contract, pin it with a unit test) and should be the first edit made. Beyond that shared blocker, the reviewers' concerns cluster around three further threads: (1) an internal inconsistency in the spec about whether `enable_thinking:false` is a mandatory, pre-decided mechanism or an empirically-swept choice (AC1 vs. What vs. AC6); (2) AC7's Deep-tier RLM scope being left open rather than resolved, where the reviewers differ only on whether to settle it in spec text now (codex) or keep it at close with structural enforcement via naming (claude-p); and (3) a cluster of AC2/AC5 underspecification issues — no pinned default, no drift-guard-convention placement, no asymmetric-pass handling, and an unexamined cap×turn-budget confound — that are individually narrower but collectively suggest the spec needs another editing pass before it is safe to hand to an implementer. No guardrail violations were raised by either agent; the two convention violations codex flagged (CAUSE TAXONOMY on AC3, DRIFT-GUARD ON DEFAULTS on AC2) are corroborated in substance by claude-p's parallel concerns even though claude-p did not classify them as formal violations.

**Action:** The spec author should revise `spec.md` to (a) add the additive `finish_reason` return-contract requirement to the gateway (blocking, do this first), (b) resolve the AC1/What/AC6 thinking-off consistency, (c) commit to a Deep-tier-out-of-scope statement in spec text (or add the `explorer_`-prefix naming backstop if keeping record-at-close), and (d) pin AC2's default and address the AC5 asymmetric-outcome and cap/turn-budget gaps — then resubmit for a fresh cross-model review. The spec remains `draft`; quorum was not met.
