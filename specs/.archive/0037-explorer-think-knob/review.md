---
spec: "0037-explorer-think-knob"
date: 2026-07-10
round: 2
spec_revision_reviewed: 1
reviewers: [codex, claude-p]
quorum: 1 (approve or approve-with-comments)
verdicts:
  codex: changes-requested
  claude-p: approve-with-comments
quorum_result: MET (1 of 2 approve-with-comments) — status moves to `reviewed`
verdict: approve-with-comments
generated: 2026-07-10T00:00:00Z
---

# Cross-model review — 0037-explorer-think-knob (round 2)

## Round-1 history (brief)

Round 1 (against revision 0) ended `changes-requested` from both agents, quorum
not met: the spec's stale premise — it re-specified work spec 0034 had already
shipped (the `explorer_think` tri-state knob, native `think` threading,
`derive_think_mode`, `think_mode` recording, and the Deep leak guard) as if it
did not yet exist. The spec was revised at revision 1 to reframe as **"probe →
pin → prove effectiveness"**: acknowledge 0034's shipped knob and recording,
sequence a live probe first to pin the effective request param, and replace
the recording-tautology effectiveness check with an observed-behavior
(`reasoning_chars`) assertion. **That finding is now resolved** — neither
round-2 agent raises the stale-premise issue again.

## codex (gpt-5.5) — round 2

**Verdict:** changes-requested

Concerns:
- No-op is declared a valid close outcome by invariant, but AC2/AC3 as written cannot pass under a no-op result — there is no coherent close path for that branch.
- AC2 pre-commits to native `think` before the probe runs, in tension with "probe-then-pin": if the probe finds a different effective param (or none), AC2 has no implementation path beyond prose.
- The live effectiveness proof (AC3) needs a more concrete driver contract: eval case/model preflight, per-mode artifact shape, and how the committed result is validated/test-pinned post-run.

Suggestions:
- Split the probe outcome into a typed enum (`native-think-effective` / `chat-template-effective` / `no-op`); make AC2/AC3 conditional on the native-think-effective branch.
- Add a committed `probe_result.json`/`findings.json` schema under `specs/0037-explorer-think-knob/probes/` with a unit test pinning the finding artifact to the recorded probe output.
- State explicitly that any non-native effective result does not silently re-point `explorer_think` — it opens a reconciliation spec for `explorer_think` vs `explorer_enable_thinking`.

## claude-p — round 2

**Verdict:** approve-with-comments

Concerns:
- **Reporting-vs-generation confound**: `reasoning_chars` observes the response's reasoning FIELD, not generation itself. A `think:false` that only suppresses field serialization (while the model still generates thinking, consuming budget invisibly or leaking `<think>` into content) would satisfy the off arm's `{None, 0}` assertion and read as a working knob — the same class of hole (0028's `/no_think`-was-inferior) the spec exists to close, now one level down.
- AC2 pre-commits to the probe's answer (native `think`) before the probe runs; only two of three probe outcomes have a defined disposition (confirms-native, no-op); the third — an effective param that is not native `think` — has no stated path.
- The on/default-arm assertion is instance-relative but ungated: assumes the served model thinks by default, without naming the reference model or gating on the shipped `probe_reasoning_default` precondition; against a non-default-thinking tag the on arm would misreport a model property as a SUT finding.
- The off arm's negative claim rests on N=1 (a single run's turns); acceptable for an API-level toggle, but the spec should state that evidence strength explicitly.
- The live run's reference model is unstated while `lm_model`'s default is known-unservable (0036 finding); should pin qwen3:14b explicitly.

Suggestions:
- Extend the probe with a generation-level discriminator: reuse the 0034 probe-A tiny-cap technique (small `max_tokens` + `think:false` → content appears / finish!=length) plus a `completion_tokens` cross-check and a `<think>`-in-content leak scan, in AC1/AC3.
- State the third probe branch's disposition explicitly (recorded finding + re-point as a follow-up revision, A/B blocked until re-proven) so the outcome space is total.
- Gate AC3's on/default arms on `probe_reasoning_default`.
- Name where the no-op finding lands (`findings.md` under `specs/0037`, per the 0021/0022 precedent).
- State the probe's transport explicitly (committed curl-on-loopback operator script, 0034 precedent, not a runtime egress path) to preempt misreading AC1 as a second outbound path.

## Synthesis

Both agents converge on the same two substantive gaps despite reaching
different verdicts, and neither found any guardrail or convention violation
this round.

1. **Probe outcome space is not total / ACs assume the happy path (both agents).**
   AC2 pre-commits to native `think` before the probe runs, and AC2/AC3 cannot
   pass under a no-op outcome even though the invariant declares no-op a valid
   close. Fix: a typed probe outcome enum (native-think-effective /
   chat-template-effective / no-op), AC2/AC3 made conditional on
   native-think-effective, explicit terminal close paths for each branch
   (EFFECTIVE → AC2/AC3 proceed; NO_OP_BLOCKED → a durable finding artifact,
   e.g. `findings.md` per the 0021/0022 precedent, plus a committed
   `probe_result.json` pinned by a unit test), and a stated disposition for
   the third branch (a non-native effective param → recorded finding +
   reconciliation as a follow-up revision, never a silent re-point).

2. **Reporting-vs-generation confound (claude-p, the deepest finding).**
   `reasoning_chars` observes the response's reasoning field, not generation —
   a `think:false` that only suppresses serialization would fake a working
   off-arm, exactly the class of hole the spec exists to close. Fix: two-factor
   effectiveness in AC1/AC3 — the 0034 probe-A tiny-cap technique
   (`think:false` + small `max_tokens` → content appears / finish!=length),
   a `completion_tokens` cross-check, and a `<think>`-in-content leak scan.

**Secondary (claude-p):** gate the on/default arms on the shipped
`probe_reasoning_default` precondition and name the reference model
(qwen3:14b; `lm_model`'s default is known-unservable per 0036); state the
off-arm's N=1 evidence strength explicitly; state the probe transport
(committed curl-on-loopback operator script, 0034 precedent, not a runtime
egress path).

**Points of divergence:** only verdict severity. codex holds
changes-requested until the close paths are made executable (typed outcomes,
conditional ACs, a committed/pinned finding artifact). claude-p judges the
same set of fixes as tightening the spec's already-correct shape rather than
reshaping it, and approves with comments. Both agents agree, point for point,
on what needs to change — there is no disagreement on substance, only on
whether the gaps are close-blocking or comment-level.

**Action:** Quorum is met (1 of 2 approve-with-comments) — status moves to
`reviewed`. Before running `/speccraft:spec:plan`, fold the convergent fixes
into `spec.md` as a comment-addressing edit: typed probe outcomes with
conditional ACs, two-factor effectiveness (generation-level discriminator +
`completion_tokens` cross-check + leak scan), the `probe_reasoning_default`
precondition gate, the named reference model (qwen3:14b), and the findings
artifact for the no-op/reconciliation branches. These are AC-shaping changes,
so the plan should be authored against the amended acceptance criteria, not
against revision 1 as currently written.

---

## Appendix: agent verdicts (verbatim, round 2)

### codex (gpt-5.5)

```yaml
verdict: changes-requested
concerns:
  - "The spec says a no-op probe result is a valid recorded finding, but AC2 and AC3 still require request-body and live effectiveness assertions that cannot pass if the knob is a no-op. Define explicit close paths: EFFECTIVE closes with AC2/AC3, NO_OP_BLOCKED closes with a durable finding artifact and blocks the A/B."
  - "The probe is described as resolving the request param, but AC2 pre-commits to native `think`. If the probe finds `chat_template_kwargs.enable_thinking` or no effective param, the spec currently has no coherent implementation path beyond prose."
  - "The live effectiveness proof needs a more concrete driver contract: which eval case/model preflight is required, what artifact shape records the per-mode comparison, and how the committed result is validated or test-pinned after the run."
suggestions:
  - "Split AC1 into a typed probe outcome enum such as `native-think-effective`, `chat-template-effective`, and `no-op`, then make AC2/AC3 conditional on the effective native outcome."
  - "Add a committed `findings.json` or `probe_result.json` schema under `specs/0037-explorer-think-knob/probes/` and a unit test that pins the claim file to the recorded probe output."
  - "State that any non-native effective result does not silently re-point `explorer_think`; it opens a reconciliation spec for `explorer_think` vs `explorer_enable_thinking`."
guardrail_violations: []
convention_violations: []
```

### claude-p

```yaml
verdict: approve-with-comments
concerns:
  - "Reporting-vs-generation confound in the effectiveness signal: per-turn `reasoning_chars` observes the reasoning FIELD in the response, not generation itself. A `think:false` that merely suppresses the field in the reply — while the model still spends thinking tokens against the cap, or leaks `<think>` into content — would satisfy the off arm's `{None, 0}` assertion and read as a working knob. The 'observed, not derived' invariant closes the config-derivation gap but reopens one level down."
  - "AC2 pre-commits to the probe's answer: it fixes the param to 'the probe's answer (native `think`)' before the probe runs. Only two of three probe outcomes have a defined disposition — confirms-native (AC2 proceeds) and no-op (recorded finding, blocks the A/B). The third, 'a param toggles thinking but it is NOT native `think` (e.g. `chat_template_kwargs.enable_thinking`)', has no stated path: does it re-point 0034's threading in this spec, force a revision, or also block?"
  - "The on/default-arm assertion is instance-relative but ungated: 'at least one turn reasoning_chars > 0' assumes the served model thinks by default (true for qwen3:14b today). The spec neither names the reference model tag nor gates the arms on the existing `probe_reasoning_default` precondition — against a non-default-thinking served tag the on arm fails and misreads as 'knob ineffective', a model property masquerading as a SUT finding (the 0023 input-validity-precondition rule)."
  - "The off arm's negative claim rests on N=1: 'ALL turns in {None, 0}' over a single run of a handful of turns is thin evidence for 'off works'; acceptable for an API-level mechanism toggle, but the spec should say that explicitly rather than leave the strength unstated."
  - "The live run's model is unstated while the `lm_model` default is known-unservable (spec 0036 finding); STOP-AND-WARN catches absence at run time, but the spec should pin the reference instance (qwen3:14b, the model the whole default-thinking premise was measured on)."
suggestions:
  - "Extend AC1's probe with a generation-level discriminator, not just field presence: reuse the 0034 probe-A tiny-cap technique (small `max_tokens` + `think:false` → content appears / finish!=length, vs think-on → reasoning-first exhaustion) and/or compare `completion_tokens` across arms, plus a `<think>`-in-content leak check — so 'field suppressed in reply' cannot pass as 'thinking disabled'."
  - "State the third probe branch: if the effective param is not native `think`, name the disposition (recorded finding + re-point as a follow-up revision, or in-spec re-thread) so the probe's outcome space is total, like the no-op branch already is."
  - "Gate AC3's on/default arms on `probe_reasoning_default` (already shipped as the 0034 AC5 precondition helper) so a non-thinking served model skips honestly instead of failing as a capability claim."
  - "Name where the no-op finding lands if it fires — a `findings.md` under specs/0037 per the 0021/0022 precedent — so 'recorded FINDING' has a concrete artifact."
  - "State the probe's transport explicitly: the 0034 precedent is a committed curl-on-loopback shell script (operator tooling, out of the runtime air-gap like convert/provision); saying so preempts a reviewer reading AC1 as a second outbound path."
guardrail_violations: []
convention_violations: []
```
