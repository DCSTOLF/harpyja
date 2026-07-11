# Cross-model review — spec 0039 (Thinking A/B — does reasoning-on rescue the conceptual cases?)

- **Date:** 2026-07-10
- **Spec:** `specs/0039-thinking-ab/spec.md`
- **Agents consulted (round 2):** codex, claude-p
- **Round-2 verdicts:** codex → `approve-with-comments`; claude-p → `approve-with-comments`
- **Quorum rule:** 1 `approve` or `approve-with-comments` required
- **Quorum outcome:** MET (2/2). **Spec status moves `draft` → `reviewed`.**
- **Gate status:** No item below blocks the review gate. All items are carried forward as the PLAN-phase action list, to be resolved before `PREREGISTERED_AB_CONFIG_0039` is committed and before the live run fires.

## Round-1 history (brief)

Round 1 (both agents `changes-requested`, quorum not met, 0/2) found the core measurement design sound
but flagged 11 open items at the pre-registration seam: an undecided contrast arm (reconciled here to
None-vs-False), an undefined `CONFOUNDED` trigger predicate, a missing frozen+hashed pre-registered
decision config AC, an unfrozen K-repeat fold rule, no committed resumable STOP-AND-WARN driver AC,
non-canonical frontmatter, a single-factor (not two-factor) distinctness guard, no typed
under-populated line for the N=4 lexical stratum, an under-specified invalid-pair disposition, and
non-archive-first evidence path pins. The spec was revised to close all 11: contrast fixed to
None-vs-False as the decision-relevant primary pair with True(`high`) demoted to observational-only;
`CONFOUNDED` given a concrete predicate (invalid-pair ceiling OR degrade-asymmetry OR verifier
failure, checked first); AC1 added for the frozen+hashed `PREREGISTERED_AB_CONFIG_0039` as a total
pure function over the outcome grid; the K-fold rule frozen inside that config; AC6 added for a
committed, resumable, STOP-AND-WARN driver; frontmatter brought to the canonical schema; AC3 made
two-factor (reasoning-presence + `completion_tokens` delta); AC4 added a typed
`STRATUM_UNDER_POPULATED` line for the lexical stratum; AC3 made exclude-and-record explicit; and
evidence pins authored archive-first against `specs/.archive/0039-thinking-ab/`. (Full round-1 detail
is preserved in git history at this file's prior revision, commit `61fa124`.)

## Round-2 outcome

Both agents independently return `approve-with-comments`. Neither reports a guardrail violation.
Neither reports a convention violation that rises to `changes-requested` — codex's one
`convention_violations` entry (typed-outcome-space totality) is folded into its comments/suggestions
rather than treated as blocking, and both agents' discussion text explicitly frames the spec as
"ready to plan" once the noted gaps are closed at plan time. Per the stated rule (any `reject` →
`reject`; else quorum approve/approve-with-comments → `approve-with-comments`; else
`changes-requested`), with 2/2 approve-with-comments the overall verdict is
**`approve-with-comments`**, and quorum (1 required) is met.

## Synthesis

Both reviewers agree the revision closed the round-1 gaps correctly in substance: the None-vs-False
contrast is now the decision-relevant primary pair (matching the actual downstream default-flip
decision), `CONFOUNDED` has a real predicate, the frozen+hashed pre-registered config AC exists, the
K-fold rule lives inside it, a committed resumable STOP-AND-WARN driver is required, frontmatter is
canonical, the distinctness guard is two-factor, the lexical stratum gets a typed
`STRATUM_UNDER_POPULATED` line, and evidence pins are archive-first. Neither agent found a guardrail
violation; the spec stays inside eval/operator scope, read-only against target repos, and preserves
the default-flip separation (no default flip decided in this spec).

What remains is refinement at the pre-registration seam that the spec itself says must be frozen
before the live run — i.e., exactly the kind of gap that belongs in PLAN, not a re-review. Two
concerns are raised independently by both agents (strong signal):

1. **AC5's power pre-check needs an honesty relabel and an explicit method.** The 0036 pilot artifacts
   it draws on measured MODEL-vs-MODEL discordance (qwen3:14b vs a smaller model), not within-model
   think-on-vs-off discordance. As currently framed the projection risks reading as a power estimate
   for this A/B when it can only bound — not estimate — the achievable signal. Both agents want this
   relabeled an upper-bound feasibility check, with the projection formula and its exact 0036 inputs
   made explicit in the spec text.
2. **The `completion_tokens` half of the two-factor distinctness guard has no operational predicate.**
   As written it names the field but not the comparison: per-turn or aggregate, what delta counts as a
   fail, in which direction. Left unpinned, it will either misfire on legitimate content-driven token
   variance (invalidating real signal) or get quietly ignored at scoring time (collapsing back to the
   single-factor `reasoning_chars` check the two-factor guard exists to prevent). This predicate must
   be a named part of `PREREGISTERED_AB_CONFIG_0039`, not a scoring-time judgment call.

Beyond the shared items, each agent raised distinct, narrower points (see the action list below).
codex's solo concern is taxonomy hygiene: the typed-outcome surface now spans the five-member verdict
enum plus `UNDER_POWERED_STOP` and `STRATUM_UNDER_POPULATED`, and these should be unified into one
total report shape (plus a literal count fix — "all four members" but five are listed).
claude-p's solo concerns are more numerous and substantive: the frozen config is missing the MODEL
identity itself (resolve-at-runtime is a servability check, not pre-registration, and is exactly the
kind of post-hoc lever the freeze discipline exists to close); the "localizes" bucket definition for
signal-bearing discordance should reuse the committed 0026 `is_signal_discordant` oracle rather than
being re-derived locally; the distinctness guard's asymmetry (off-arm-reasoning invalidates, on-arm-
no-reasoning is kept) is deliberate but unstated, risking a well-meaning "fix" into wrongful symmetry;
the frozen seed schedule should not be trusted without verifying `/v1` honors `seed` (the 0037 lesson
verbatim — the compat layer has silently dropped fields before); the spec should state the power
arithmetic out loud (N=15 conceptual, floor 8, ~50% pilot base rate → `UNDER_POWERED_STOP` is the
probable and legitimate deliverable); AC5 should also project on-arm truncation/degrade asymmetry
(predictable `CONFOUNDED` is discoverable for free using the same artifacts); the per-stratum floor
derivation rule needs to be pinned as fixed-or-re-derivable; and AC5's exact inputs need precision
(the committed ledger path under `specs/.archive/0036-terse-query/pilot/`, the gitignored-durable
per-case artifacts under `eval_work/live_artifacts/pilot_0036/`, and the fact the pilot covered only
the first 10 of 19 cases, so the projectable conceptual subset is smaller than 15).

None of this changes the spec's core design, which both reviewers independently call correct and
well-scarred against this project's measurement-integrity history (0023 paired-not-rates, 0026
frozen-config/exclude-and-record, 0036 pilot-gate, 0037/0038 arm-distinctness-at-the-measurement).

**Action:** Move spec 0039 to `reviewed` and proceed to PLAN. Before `PREREGISTERED_AB_CONFIG_0039`
is committed and before the live paired run fires, resolve the consolidated action list below — the
two CONSENSUS items first, since both are load-bearing on what the frozen config must contain.

## Consolidated plan-phase action list

### CONSENSUS (both agents)

1. **Relabel and specify the AC5 power pre-check.** State explicitly that it is an *upper-bound
   feasibility check*, not a power estimate — the 0036 pilot measured cross-MODEL discordance
   (14b vs a smaller model), which cannot estimate within-model think-flip rates, only bound them.
   Make the projection formula explicit: which 0036 fields are consumed, why they're predictive
   (even as an upper bound) for this A/B, and what happens if the projection is not defensible.
   *(codex: concerns[1]/suggestions[1]; claude-p: concerns[2]/discussion.)*
2. **Pin the `completion_tokens` distinctness-guard predicate.** Define, inside the frozen config, the
   operational form of factor (b): per-turn vs aggregate comparison, the expected delta/direction, and
   the pass/fail threshold — precise enough that it cannot invalidate genuinely distinct pairs (legit
   small deltas on easy cases) or silently collapse to single-factor field-presence.
   *(codex: concerns[2]/suggestions[2]; claude-p: concerns[3]/suggestions unlabeled but stated in
   discussion.)*

### codex-solo

3. **Normalize the typed-outcome taxonomy into one total report shape.** `UNDER_POWERED_STOP` (AC5)
   and `STRATUM_UNDER_POPULATED` (AC4) should be integrated cleanly with the five-member verdict enum
   (THINKING_HELPS / THINKING_HURTS / NO_EFFECT / UNDER_POWERED / CONFOUNDED) rather than living as
   separate typed lines alongside it. Also fix the literal count mismatch: the invariant text says
   "all four members" but lists five.

### claude-p-solo

4. **Pin the MODEL identity in the frozen config.** Add the served `lm_model` tag (and expected
   `serving_transport`) to the AC1 enumeration — resolve-at-runtime in the driver preflight proves
   *servability*, not *pre-registration*; without it, model choice is a post-hoc lever the freeze
   discipline exists to close.
5. **Pin the "localizes" bucket set via oracle reuse, not re-derivation.** The signal-bearing-
   discordance bucket set (CORRECT vs CORRECT+RIGHT_FILE_WRONG_SPAN) must reuse the committed 0026
   `is_signal_discordant` oracle rather than a locally re-derived definition.
6. **State the distinctness guard's asymmetry rationale in one line.** Off-arm-shows-reasoning =
   instrument defect → pair invalid; on-arm-shows-no-reasoning = legitimate None-arm behavior under
   the shipped default → pair kept. Without the rationale an implementer may "fix" it into wrongful
   symmetry and bias the sample.
7. **Probe (don't assume) that Ollama's `/v1` honors `seed`.** Add a two-call preflight probe (same
   request + same seed twice → identical completion?) before trusting the frozen seed schedule, or
   downgrade the config's claim to "seed requested, honoring unverified" — the 0037 lesson verbatim.
8. **State the power arithmetic out loud in the spec.** N=15 conceptual, floor 8, ~50% pilot base
   rate → `UNDER_POWERED_STOP` is the probable and legitimate deliverable; say so explicitly to set
   operator expectations and to sharpen the OQ1 K-sizing decision.
9. **Extend AC5 to also project on-arm truncation/degrade asymmetry.** Using the same 0036 per-turn
   artifacts (`completion_tokens`/`finish_reason`), a predictable `CONFOUNDED` is as discoverable-for-
   free as a predictable `UNDER_POWERED`.
10. **Pin the per-stratum floor derivation rule.** State whether the conceptual floor may be
    re-derived (e.g., to the 0023 arithmetic minimum of 6) or is fixed at 8 — an unstated latitude on
    the floor value is a steering surface even inside a config that is otherwise frozen-before-run.
11. **Make AC5's inputs precise.** The committed 0036 pilot ledger lives under
    `specs/.archive/0036-terse-query/pilot/` (`pilot_results.json` / `gate_report.json`); per-case
    verifier artifacts are gitignored-durable under `eval_work/live_artifacts/pilot_0036/`; the pilot
    covered only the first 10 of 19 cases, so the projectable conceptual subset available is smaller
    than 15.

---

## Appendix A — codex round-2 raw verdict (verbatim)

<details>
<summary>codex — approve-with-comments</summary>

```yaml
verdict: approve-with-comments
concerns:
  - "The power pre-check is underspecified and may be invalid: 0036 pilot artifacts measure model-vs-model discordance, not None-vs-False thinking discordance, so they may not project achievable conceptual-stratum signal-bearing flips for this A/B without a clearly defined bridge."
  - "The arm-distinctness guard's completion_tokens delta requirement is too vague for real localization runs; token totals can vary for legitimate content reasons, so the spec should define the expected direction/threshold and whether this is per-turn, per-pair, or aggregate."
  - "The outcome space is slightly inconsistent: the text says 'all four members' but lists five verdicts, and `UNDER_POWERED_STOP` / `STRATUM_UNDER_POPULATED` are used as typed outcomes without being integrated cleanly into the main verdict enum/report schema."
suggestions:
  - "Define the AC5 projection formula explicitly, including which 0036 fields are consumed, why they are predictive for thinking A/B discordance, and what happens if the projection is not defensible."
  - "Make the arm-distinctness proof two-layered: a pre-run probe proves generation-level separation with the tiny-cap/budget discriminator, while live pair validity requires off-arm zero reasoning plus recorded budget/degrade data rather than an ambiguous token-delta pass/fail."
  - "Normalize the typed outcome taxonomy so pre-check stops, run-level confounds, stratum-under-populated lines, and statistical verdicts are all represented in one total report shape."
guardrail_violations: []
convention_violations:
  - rule: "A pre-registered decision config must make the verdict a total pure function over a clearly enumerated outcome space."
    location: "Invariants / Typed outcome and Acceptance criteria 5-7"
```

**Discussion:**

The spec is directionally solid: paired McNemar, reachability split, pre-registration, arm-validity
checks, durable verifier artifacts, and strict no-default-flip posture all match the project's
measurement discipline. The main thing I would tighten before implementation is the cheap gate. As
written, it risks becoming a false confidence gate because 0036's pilot signal was a model contrast,
while this spec's causal question is a within-model thinking contrast. If the projection is just
"0036 had enough model-discordant conceptual cases, so thinking might too," that is not a power
estimate for the proposed A/B. It can still be useful as a heuristic, but the spec should label it
honestly or define a defensible projection. The second issue is the completion-token arm-distinctness
check. It is right to avoid a serialization-only proof, but live localization tasks are not tiny-cap
probes. A valid off-arm could spend more content tokens than the on-arm, or both arms could have
similar completion totals while still differing in reasoning. Make the pass/fail predicate precise
enough that it cannot invalidate real signal or create post-hoc discretion. No hard guardrail
violation: this is eval/operator work, local-model oriented, read-only against target repos, and it
preserves the default-flip separation. The convention issue is mostly taxonomy hygiene, but it matters
because this project relies heavily on total, test-pinned outcome spaces.

</details>

## Appendix B — claude-p round-2 raw verdict (verbatim)

<details>
<summary>claude-p — approve-with-comments</summary>

```yaml
verdict: approve-with-comments
concerns:
  - "The frozen config's enumerated contents omit the MODEL identity: 'arm identities None-vs-False' names only the knob values, but which served `lm_model` tag runs the A/B is itself verdict-shaping (the spec says 'one model's think A/B' without pinning which model). Left out of `PREREGISTERED_AB_CONFIG_0039`, model choice becomes a post-hoc lever — run on several tags, report the favorable one — exactly what the 0023/0026 freeze discipline exists to prevent."
  - "The power arithmetic makes UNDER_POWERED_STOP the *probable* deliverable and the spec should surface that: the conceptual stratum is N=15, the committed floor is 8 signal-bearing discordant, and the 0036 pilot's qwen3:14b arm localized 5/10 — so the projectable UPPER BOUND on signal-bearing discordance (every localizing case flips, which won't happen for a same-model contrast) is ~7–8, at or below the floor before any realism discount. The spec honestly designs for the stop, but AC5's projection method should be stated as an upper-bound feasibility check, not a power estimate — the pilot measured cross-MODEL discordance (14b vs 4b), which cannot estimate within-model think-flip rates, only bound them."
  - "Factor (b) of the two-factor arm-distinctness guard (the per-turn `completion_tokens` delta) has no defined per-pair predicate: an easy case where the on arm thought little produces a small legitimate delta, so either the factor invalidates genuinely distinct pairs or it silently collapses back to factor (a) field-presence — the exact single-factor regression the invariant forbids. The operational predicate (what delta, compared how, per-turn or per-case) must be in the frozen config, not decided at scoring time."
  - "The 'localizes' predicate for signal-bearing discordance (CORRECT only vs CORRECT+RIGHT_FILE_WRONG_SPAN) is verdict-shaping and never named. The 0036 pilot's 5 signal-bearing pairs counted right-file-wrong-span as located; 0039 must pin the same bucket set explicitly — by reusing the committed 0026 `is_signal_discordant` oracle (one-oracle reuse), never a re-derived local definition."
  - "OQ2 freezes a seed schedule without verifying Ollama's `/v1` compat path honors `seed` — this project's defining lesson (0037: the compat layer silently drops `think`) applies verbatim. A recorded-but-dropped seed schedule is false provenance in the frozen config ('repeat k used seed S_k' when nothing did)."
  - "Per-stratum floors are declared plural-and-config-frozen while invariant 1 cites 'the committed floor (min-discordant=8)' — if the conceptual floor may be re-derived (e.g. to the 0023 arithmetic minimum of 6), the spec should say so and pin the derivation rule; if it may not, say that. An unstated latitude on the floor value is a steering surface even when frozen-before-run."
suggestions:
  - "Add the served model tag (and expected `serving_transport`) to the AC1 frozen-config enumeration; the verifier artifact then proves per-case what the config pre-registered."
  - "State the deliberate ASYMMETRY of the distinctness guard in one line: off-arm-shows-reasoning = instrument defect → pair invalid; on-arm-shows-no-reasoning = legitimate None-arm behavior under the shipped default → pair kept. Without the rationale, an implementer will 'fix' it into symmetry and wrongly exclude valid pairs."
  - "Extend the AC5 pre-check to also project on-arm truncation/degrade asymmetry from the existing 0036 per-turn artifacts (schema 0034/1 carries `completion_tokens`/`finish_reason`) — a predictable CONFOUNDED is as discoverable-for-free as a predictable UNDER_POWERED, and 850–3980 reasoning chars/turn against `explorer_max_tokens=2048` makes it a live risk."
  - "Make AC5's input precise: the committed 0036 pilot evidence is the ledger under `specs/.archive/0036-terse-query/pilot/` (pilot_results.json / gate_report.json); the per-case verifier artifacts live in gitignored `eval_work/live_artifacts/pilot_0036/` and are durable-but-not-committed. Also note the pilot ran the first 10 of 19 cases, so the conceptual subset available for projection is smaller than 15."
  - "Add a two-call seed probe (same request + same seed twice → identical completion?) to the driver preflight before trusting the frozen seed schedule, or downgrade the config's claim to 'seed requested, honoring unverified'."
guardrail_violations: []
convention_violations: []
```

**Discussion:**

This is a strong revision. It internalizes essentially every measurement-integrity convention the
last dozen specs paid for: the paired-McNemar-not-diff-of-rates discipline (0023), the frozen
pre-registered config with a total pure verdict function, the exclude-and-record exclusion posture
(0036), the degrade-masks-outcome trap as a first-class CONFOUNDED input (0026/0027), the
arm-distinctness guard at the measurement rather than the config (the 0037 lesson), archive-first path
pins from authoring (79f7bf2), and the committed STOP-AND-WARN resumable driver. The None-vs-False
framing is the standout decision — it's the contrast the default-flip actually needs, and the spec
correctly demotes True(`high`) to observational. The direction-complete verdict enum with
UNDER_POWERED distinct from NO_EFFECT is exactly right. I found no guardrail or written-convention
violations; the concerns are freeze-completeness and honesty-of-projection gaps, all fixable at plan
time before the config is committed.

The load-bearing concern is what's *in* the frozen config. The invariant's blanket statement ("every
verdict-shaping choice") is correct, but the enumerated list is what an implementer will build, and
it's missing at least three verdict-shaping choices: the model identity, the localization-success
bucket set, and the operational form of distinctness factor (b). Each is a place where a
post-outcome decision could quietly shape the verdict. The model tag is the sharpest: the spec never
names the model anywhere, and "the preflight resolves a served tag" is a *servability* check, not a
*pre-registration* — resolve-at-runtime means the arm identity is chosen after the config hash exists.

On power, do the arithmetic out loud. N=15 conceptual, floor 8, base localization ~50% on the pilot:
the ceiling on signal-bearing discordance is roughly 7–8 *if every localizing case flips between
arms* — and a same-model think-on/off contrast will flip far fewer. K-repeats with an any-success
fold can raise per-arm localization somewhat, which is presumably why OQ1 sizes K against the
projection, but the honest prior is that AC5 fires UNDER_POWERED_STOP and this spec's deliverable is
the typed stop naming the 0036 pool-enlargement carry-forward. That is a legitimate close under the
repo's own conventions — the spec says so — but stating the arithmetic in the spec would set operator
expectations correctly and sharpen the K-sizing decision (if even K=3/any-success can't reach the
floor in projection, don't burn wall-clock on the observational arm either). Relatedly, the
pre-check's inference should be labeled honestly: pilot discordance was *model-capability*
discordance; it bounds, but cannot estimate, think-flip discordance.

The distinctness guard is right to be asymmetric — but only if it says why. An off arm showing
reasoning means the knob failed (instrument defect → invalid pair, and enough of them → CONFOUNDED).
An on arm showing *no* reasoning is legitimate behavior of the shipped None default — excluding those
pairs would bias the sample toward cases where thinking fired, which is not the shipped contrast the
default-flip decision needs. One rationale line prevents a well-meaning symmetry "fix." Factor (b)
needs an actual predicate; as written it will either be dropped in practice or misfire on easy cases.

Seed is a small thing with a familiar failure shape. After 0037 (top-level `think` silently dropped)
and 0038 (the honoring path found by probing), freezing a seed schedule *without probing whether
`/v1` honors `seed`* would be ironic. The probe is two requests; the alternative is one honest label.
Either satisfies no-false-capability; silence does not.

Out-of-scope boundaries are drawn correctly — no default flip, no `explorer_max_tokens` tuning
(recorded as CONFOUNDED input instead), pool enlargement as its own audited convert step. AC8's
causation stance (N=2 as motivation only, this run as the first powered read) closes the loop the
think-experiment opened.

With the frozen-config enumeration completed and the projection honestly labeled, this is ready to
plan.

</details>
