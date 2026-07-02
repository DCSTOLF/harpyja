---
spec: "0019"
reviewers: [codex-gpt-5.5, claude-p]
quorum: 1
verdict: approve-with-comments
generated: 2026-07-01T00:00:00Z
---

# Cross-model review — 0019 (OQ2 re-run — complete, prove the gate, then calibrate)

**Codex (gpt-5.5): changes-requested. Claude-p: approve-with-comments.**
**Synthesized action:** Quorum (1 approve-with-comments) is met — the spec may move to `reviewed`. But do not treat this as a green light to `/spec:plan` as-is: five concerns below are load-bearing for planning (they change what G1/G2/G3 and AC1/AC5/AC7 actually mean or require) and should be folded into the spec text first. Recommended sequence: revise `spec.md` in place to resolve the five "must-fix-before-plan" items, THEN set `status: reviewed`, THEN run `/spec:plan`.

## codex (gpt-5.5)

**Verdict:** changes-requested

Concerns:
- Preflight underspecified vs the air-gap rule: model-presence checks may require an HTTP call to Ollama, but the spec doesn't say this goes through the existing Gateway/doctor seam with loopback enforcement.
- G2 pass/fail semantics not crisp: G2 gates G3 but no defined material false-escalation threshold / exact condition that turns measurement into `gate-confounded`.
- Gate-quality metrics need pinned denominators and a single correctness oracle; the spec doesn't require reuse of the existing span-overlap oracle or null-with-count for undefined denominators.
- AC5 reads as unconditional full-sweep completion, conflicting with the invariant that G1/G2 may stop the run.

Suggestions:
- Make preflight explicitly reuse `gateway.assert_local` / a doctor-style local-only seam; state no non-loopback endpoint is contacted.
- Define G2 outcome thresholds (false-escalation ceiling, catch-rate floor, when `gate-confounded` must suppress G3).
- Rewrite AC5 as conditional on G1 and G2 passing; add an explicit accepted outcome for stopped runs.
- Add an AC requiring gate metrics to use the same overlap oracle as accuracy metrics, with explicit denominators and null+count for zero-denominator cases.

Guardrail violations:
- rule: "Model Gateway is the only outbound caller and must point at loopback/localhost" — location: What / PREFLIGHT

Convention violations:
- rule: "One oracle defines correctness for every derived metric, with explicit denominators" — location: What / G2 and AC3-4
- rule: "Undefined metric is explicit null paired with count" — location: AC3-4

Discussion: right shape overall (measurement-not-construction preserved, flip out of scope, `0.6` correctly treated as unvalidated, correct sequencing). Main issue: G2 is not operationally decidable — "material rate" appears only in Open Question 2, while the main flow states G2 gates G3, leaving operators free to continue into calibration even when the judge still rejects correct citations. Preflight needs the sanctioned seam named explicitly. AC5 should be made conditional to match the stop-and-report invariant.

## claude-p

**Verdict:** approve-with-comments

Concerns:
- K (runs/point) + grid resolution/bounds are left as Open Question 1, but AC5/AC7 can't be planned or executed without them (N ≥ N_FLOOR, wall-clock, and the variance gate all depend on K). Must be resolved before `/spec:plan`, not during the run.
- Preflight (AC1) proves models are PULLED (`/api/tags` membership), not that scout+deep+judge are CO-RESIDENT-loadable without OOM. Per memory: Q8 OOMs under `mode=auto` on 16 GB; 32 GB "resolved" it. Presence ≠ runnable-together; a green preflight that still OOMs mid-sweep recreates the mid-run-discovery failure preflight exists to prevent.
- Thin unit surface: only AC8 is `[unit]`; the rest are `[integration]` skip-not-fail. "Run is declared complete" (AC8) is operator judgment with no automated gate; make the completion criterion concrete (what artifact/report state = G3 done).

Suggestions:
- Give AC1 a `[unit]` companion: preflight assertion logic (three-model membership vs a fake `/api/tags` payload, loud failure on absent) is unit-testable, mirroring 0016 AC7.
- Decide OQ2 (gate-confounded typed null) and OQ3 (`mode=fast` line) before `/spec:plan`. OQ2's "lean yes" is already half-committed in `What` (gate-confounded is listed as a G3 typed-null outcome) — promote it to a firm decision or the spec contradicts itself.
- State the `verify_threshold` grid RANGE explicitly; derive bounds from the observed instruct-judge score distribution (a G1/G2 by-product) — honest and non-question-begging.
- Clarify AC4 A/B vs measurement-not-construction: running the harness under `instruct_model` vs `scout_model` verify_method is pure config override; side-by-side reporting likely needs ADDITIVE report fields (permitted: last-with-defaults, bump `SCHEMA_VERSION`). The invariant scopes "no behavior change" to the SUT; make that boundary explicit.

Guardrail violations: none
Convention violations: none

Discussion: strong spec, a model of measurement-not-construction; the three invariants are exactly right after the 0015 wedge, and it maps cleanly onto shipped machinery (0016/0017/0018). No guardrail or convention violations found. Concerns are about executability/planning-readiness: K/grid are load-bearing and undecided; the preflight honesty gap (pulled ≠ co-resident-loadable, OOM risk under `mode=auto`); the A/B scope boundary deserves one clarifying sentence; and the gate-confounded outcome is half-decided in a way that already contradicts itself between `What` and Open Questions.

## Points of agreement

Both reviewers independently converge on the same structural weak point from different angles:

- **G2's decidability / the gate-confounded contradiction.** Codex: G2 gates G3 but has no crisp pass/fail threshold, so "gate-confounded" exists only as a hint inside Open Question 2 with no operational trigger. Claude-p: Open Question 2's "lean yes" is *already* half-committed in the `What` narrative (gate-confounded is listed as a live G3 typed-null outcome) and in AC7, so the spec currently asserts the outcome exists while deferring the decision that would make it fire. These are the same underlying gap seen from two sides — the spec both assumes and defers the gate-confounded criterion — and it is the single most load-bearing "must fix" here, because it determines whether AC3/AC7 are checkable at all.
- **Preflight (AC1) is not yet trustworthy as a gate.** Codex flags the missing sanctioned seam (loopback-only enforcement per the Gateway guardrail); claude-p flags that presence-checking alone doesn't prove the three models are jointly loadable without OOM. Both are really saying: AC1 as written can pass green and still let the run fail for a reason preflight was supposed to catch (a 404 from an unpulled model, or an OOM from a co-residence conflict) — the spec needs either a broader guarantee or an explicit, honest scope-narrowing of what AC1 actually proves.
- **Sequencing/gating language needs to be airtight, not just implied.** Codex calls out AC5 reading as unconditional despite the "G1/G2 may stop the run" invariant; claude-p's OQ2 point is adjacent — both want the stop-and-report invariant made mechanically enforceable in the ACs rather than living only in prose above them.

Neither reviewer disagrees with the other's findings; the two reviews are complementary (codex is stronger on guardrail/convention formalism, claude-p is stronger on planning-readiness and the memory-informed OOM risk) and no concern from one contradicts a concern or suggestion from the other.

## Consolidated concerns (prioritized)

### Must-fix-before-plan (block `/spec:plan`; fold into spec.md before advancing)

1. **G2 pass/fail threshold, and the gate-confounded contradiction** — codex + claude-p (converged).
   Location: `What / G2 GATE-QUALITY`, AC3, AC7, Open Question 2.
   Concrete change: Promote OQ2's "lean yes" to a firm, numeric decision rule in the spec body (not just an open question) — e.g. a stated false-escalation ceiling and/or catch-rate floor over the point subset that, if breached, *requires* G3 to emit `gate-confounded` rather than a clean recommend. Remove the contradiction where `What`/AC7 already treat gate-confounded as a live outcome while OQ2 defers deciding when it applies.

2. **K (runs/point) and grid resolution/bounds** — claude-p.
   Location: Open Question 1; consumed by AC5 and AC7.
   Concrete change: Resolve OQ1 in the spec itself — state the chosen `K`, the grid resolution (or the coarse-then-refine rule), and the wall-clock budget it implies on the 32 GB M1 Max — before planning, since N ≥ N_FLOOR, wall-clock, and the variance-gated recommend in AC5/AC7 cannot be scoped into tasks without it.

3. **AC5 must be conditional, matching the stop-and-report invariant** — codex.
   Location: AC5 ("G3 — sweep completes at scale").
   Concrete change: Rewrite AC5 to be explicitly conditional on G1 and G2 having passed (mirroring AC2's "the full sweep is NOT attempted if G1 fails" language), and add an explicit accepted outcome/artifact for a run that legitimately stops at G1 or G2 (i.e. that outcome is a documented AC-satisfying finding, not a failure to satisfy AC5).

4. **Preflight seam + honesty gap (presence vs co-residence)** — codex + claude-p, complementary angles.
   Location: `What / PREFLIGHT`, AC1.
   Concrete change: (a) Name the sanctioned loopback-only seam explicitly (e.g. `gateway.assert_local` or a doctor-style call) and state that no non-loopback endpoint is contacted, satisfying the Gateway-is-the-only-outbound-caller guardrail; (b) either extend AC1 to check that scout+deep+judge are jointly loadable without OOM, or explicitly narrow AC1's claim to "pulled, not co-residence-verified" and note the residual OOM risk is caught by the G1 smoke test (AC2) — pick one and say so, rather than leaving AC1 implicitly over-claiming what preflight proves.

### Nice-to-have (can be addressed during `/spec:plan` or execution; do not block advancing to `reviewed`)

5. **Single oracle + pinned denominators for gate metrics** — codex.
   Location: AC3, AC4. Add a requirement that G2's false-escalation/catch-rate metrics reuse the existing span-overlap oracle used for accuracy metrics, with explicit denominators and an explicit null+count where a denominator is zero.

6. **AC1 unit companion** — claude-p. Add a `[unit]` test for the preflight assertion logic (three-model membership check against a fake `/api/tags` payload, loud failure on absence), mirroring 0016 AC7.

7. **AC8 completion criterion made concrete** — claude-p. Specify what artifact/report state constitutes "the run is declared complete" (e.g. a written G3 report with all typed fields populated, or an explicit stop-and-report finding at G1/G2), so AC8's regression-test-before-complete gate has a checkable trigger.

8. **AC4 A/B scope boundary sentence** — claude-p. Add one sentence clarifying that side-by-side judge reporting (instruct_model vs scout_model) is a pure config override plus additive report-schema fields (last-with-defaults, `SCHEMA_VERSION` bump), and that "no behavior change" in the measurement-not-construction invariant scopes to the SUT, not the report shape.

9. **OQ3 (`mode=fast` line)** — claude-p. Lower priority than OQ1/OQ2; can be decided during planning rather than before it, since it only affects report breadth, not gate decidability.

## Synthesis

The spec is structurally sound: the three-invariant frame (measurement-not-construction, three sequential stop-and-report gates, reliability-gated reporting) is exactly the right shape for re-running a now-unblocked instrument, and both reviewers agree it maps cleanly onto the shipped 0016–0018 fixes with no invented behavior. Neither reviewer found a guardrail or convention violation that is unresolved by reasonable spec edits (codex's two flagged items are both closeable by adding language, not by architecture changes), and there is no disagreement between reviewers to adjudicate — codex and claude-p reinforce each other, particularly on G2's decidability and on preflight's honesty about what it actually proves.

The gap is planning-readiness, not soundness of intent: as currently worded, several ACs reference outcomes and inputs that depend on decisions the spec defers to Open Questions (K/grid, the gate-confounded trigger) or leaves implicit (AC5's conditionality, AC1's actual scope, the Gateway seam). Advancing straight to `/spec:plan` risks producing tasks built on a G2 semantics that isn't operationally decidable and a preflight that could pass green while still permitting the exact class of mid-run failure (OOM, or an ungated confounded judge) it exists to catch.

**Action:** Revise `specs/0019-oq2-rerun/spec.md` in place to resolve the four must-fix-before-plan items (G2 threshold / gate-confounded decision in OQ2 + AC3/AC7; K/grid decision in OQ1 feeding AC5/AC7; conditional AC5; preflight seam + presence-vs-co-residence scoping in AC1), optionally folding in the nice-to-haves (oracle/denominator convention, AC1 unit companion, AC8 completion criterion, AC4 scope sentence). Once revised, set `status: reviewed` and proceed to `/spec:plan` — quorum is already satisfied and no further review round is required unless the revision changes the spec's shape materially (e.g. splits G2/G3 into separate specs).

---

## Resolution (applied post-synthesis)

All four **must-fix-before-plan** items were folded into `spec.md` in place, then
the spec was moved to `reviewed`:

- **G2 threshold + gate-confounded contradiction** → **D2**: `gate_false_escalation_ceiling = 0.20`; `gate-confounded` promoted from open question to a DECIDED G3 typed-null (AC4/AC9); OQ removed.
- **K/grid undecided** → **D1**: `K = 3`, coarse-first grid over a range DERIVED from the G1/G2 instruct-judge score distribution (`0.6` no longer privileged); method fixed, concrete grid named in `plan.md`.
- **AC5 unconditional full-sweep** → rewritten as **AC7**: conditional on G1∧G2 passing; a stopped run is an explicitly accepted outcome, not an AC failure.
- **Preflight seam + co-residence honesty** → **D4** + **AC1**: probe behind `gateway.assert_local` (no second outbound path), claims only "pulled", names OOM as a residual G1-caught risk.

Nice-to-haves also folded: single-overlap-oracle + explicit denominators / null-with-count (**AC5**), preflight `[unit]` companion (**AC2**), concrete "run complete" criterion (**AC10**), A/B additive-report scope sentence (G3 bullet + **AC6**). `mode=fast` (OQ3) → **D3** deferred-and-recorded. Two genuine remainders kept as open questions (refinement-pass budget; co-residence load-probe depth) — both runtime observations, not pre-commits.
