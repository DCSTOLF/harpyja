---
spec: "0009-6a"
title: "Wave 6a — Eval harness + OQ2 calibration"
round: 2
reviewers: [codex, claude-p]
quorum: 1
verdict: approve-with-comments
generated: 2026-06-27T00:00:00Z
---

# Cross-model review — 0009-6a (ROUND 2)

## codex

**Verdict:** approve-with-comments

Concerns:
- B4 materially improved, but "spread", "observed variance", and "advantage exceeds variance" still need a precise rule before implementation is deterministic across authors.
- The recommendation objective "false-escalation + over-escalation cost" has no defined cost function or weighting; different implementers could pick different winners from the same sweep table.
- D3 oracle defines correctness by expected-span overlap but does not state how multiple returned citations/spans collapse into one Tier-1 correctness label (any-overlap vs primary-citation-only).

Suggestions:
- Define spread explicitly (std dev, min/max, CI, or max delta) and state the exact comparison the recommendation helper uses.
- Pin the sweep ranking formula, or require the report to emit a recommendation only after a named scorer with documented weights is selected.
- Add one sentence to D3/AC3: a Tier-1 result is correct if any evaluated citation overlaps any expected span in the same file, unless the intended rule differs.

Guardrail violations: none

Convention violations: none

---

## claude-p

**Verdict:** approve-with-comments

Concerns:
- Gate-metric denominator under-defined for mode=auto. Broad queries go straight to Deep and never touch the gate; only point queries run seed→Scout→gate. Gate catch-rate and false-escalation (D3) are only meaningful over the gate-eligible (point) subset, but the escalation-rate metric ("% auto queries reaching Tier-2") mixes broad-direct-to-Deep with gate-driven escalation. The spec never states that gate metrics are computed over the point-query subset only — two implementers could produce silently incomparable harnesses.
- Zero-denominator case unaddressed. catch-rate = caught / (wrong Tier-1 total); false-escalation = wrongly-escalated / (correct Tier-1 total). If the small seed set has no wrong-Tier-1 (or no correct-Tier-1) cases, a metric is 0/0 — yet AC7 asserts "all metrics populated." The seed set must guarantee both populations; the spec should say so and define the undefined-metric sentinel.
- N floor specified as mechanism but not as a value. The catch-rate bar got a concrete number (>=0.90); the N floor did not (deferred to "stated in the report"). AC8 conditions behavior on "when seed N is below the floor" — without a spec-pinned floor that branch is not deterministically testable.
- D2 secondary metric depends on a "proximity window" whose size is never given, yet AC2 tests boundary cases "within/outside the proximity window" — untestable without a defined value.

Suggestions:
- Justify or relocate K. Eval-only run-count in production-frozen Settings is a coupling smell. Consider a runner arg or separate eval config, or state explicitly why Settings is the right home (e.g. so dataclasses.replace sweep overrides compose uniformly).
- Enumerate the pinned report schema's top-level field names in the spec (or link a fixture). AC4 asserts conformance but the schema is defined nowhere; gate-metric computation depends on per-case gate-decision fields the schema carries.
- State the undefined-metric representation (null vs omitted vs sentinel) so AC7's "all metrics populated" and report consumers agree.

Guardrail violations: none

Convention violations: none

---

## Synthesis

### Prior blockers — closure

Both reviewers independently confirm all five Round 1 blockers and the plus-group are genuinely closed in this revision.

| Blocker | Closure summary |
|---------|----------------|
| **B1** INVARIANT vs Settings-default contradiction | Clean separation: this wave emits a recommendation only; default flip is a one-line follow-up spec. No Settings defaults touched here. Both reviewers confirm. |
| **B2** Undefined catch-rate target | >=0.90 provisional target is now explicit and marked as tunable once N grows. Both reviewers confirm. |
| **B3** Two blocking open questions (D1/D2) | D1 resolved (vendored OSS repo + hand-labeled spans). D2 resolved (primary line-range overlap; secondary file+proximity). Neither is open. Both reviewers confirm. |
| **B4** Determinism / small-N | K repeated runs per grid point; mean + spread reported; advantage-exceeds-variance gate on the recommendation helper. Mechanism is closed; precision of "spread" and "exceeds" is the residual non-blocking concern. Both reviewers confirm closure. |
| **B5** Gate oracle underspecified | Single D3 overlap oracle (expected-span overlap) is named once and reused by span-hit, catch-rate, and false-escalation. Both reviewers confirm; residual is multi-citation reduction rule (non-blocking). |
| **Plus — report schema** | "Pinned schema" is committed in the spec text and asserted in AC4/AC7. Field enumeration or fixture link is the residual (non-blocking). |
| **Plus — artifact location** | Written outside any indexed/target repo, read-only guardrail, FastContext precedent cited. Both reviewers confirm. |
| **Plus — N floor** | Mechanism committed (indicative-only flag + AC8 branch). Concrete value not yet pinned (residual, tracked below). |
| **Plus — dataclasses.replace** | Explicit in spec body and asserted in AC6. Both reviewers confirm. |

### Overall verdict

**approve-with-comments. Quorum MET (both of 2 reviewers approve-with-comments; quorum = 1).**

The spec is ready to be marked `reviewed` and proceed to `/spec:plan`. No Round 2 concern rises to blocker level. All remaining items are refinements to fold into the plan or pin during implementation — none requires a spec reset.

---

### Remaining non-blocking refinements (for /spec:plan)

The items below are grouped and de-duplicated across both reviewers. They should be addressed during planning or implementation; the most important are listed first.

**1. Gate-metric denominator scope** (claude-p — new issue, highest priority)

Gate catch-rate and false-escalation are only defined over the gate-eligible (point-query) subset. Broad queries bypass the gate per the 0008 routing matrix and must not enter the catch-rate or false-escalation denominators. The escalation-rate metric ("% auto queries reaching Tier-2") is a separate aggregate that includes both paths and must not be conflated with the gate-specific metrics. The plan must state that gate metrics are scoped to point-query cases only; the dataset classification label (already in the fixture format) is the natural selector.

**2. Zero-denominator / undefined-metric handling** (claude-p)

catch-rate and false-escalation are undefined if the seed set contains no wrong-Tier-1 cases (or no correct-Tier-1 cases). AC7 asserts "all metrics populated." Reconcile by: (a) requiring the seed set to guarantee at least one case in each population, stated as a fixture authoring constraint, and (b) defining the undefined-metric representation (null / omitted / sentinel string) so the report schema and AC7 agree. This also interacts with item 1 — after filtering to point-query cases, the sub-population sizes must still clear the floor.

**3. Pin the variance rule** (codex)

"Spread", "observed variance", and "advantage exceeds variance" are the operative terms in the recommendation helper (spec body and AC5). These must be made precise before implementation: choose one definition of spread (e.g. standard deviation, max-delta over K runs, or a percentile interval) and state the exact comparison rule (e.g. mean(A) - mean(B) > 1 std dev of B). Without this, two implementations of the recommendation helper can produce different winners from identical run data.

**4. Pin the sweep ranking / cost function** (codex)

The OQ2 resolution paragraph selects the (threshold, top_n) point "minimizing false-escalation + over-escalation cost." No weights or named scorer are given. Different implementers will produce different winners from the same table. The plan should document weights (even if equal-weight) or name a scorer function so the sweep ranking is reproducible.

**5. Multi-citation reduction rule for D3** (codex)

D3 defines Tier-1 correctness by expected-span overlap, but a Tier-1 result may return multiple citations. The spec does not state how they collapse to one correctness label. The simplest rule — a result is correct if ANY returned citation overlaps ANY expected span in the same file — should be stated explicitly in D3/AC3, or the intended alternative (e.g. primary-citation-only) should be documented.

**6. Pin the N-floor value and D2 proximity-window value** (claude-p — partially-closed plus-items)

Both values have committed mechanisms but no committed magnitudes. The N floor governs an AC8 branch ("when seed N is below the floor") that is not deterministically testable without a number; the proximity window governs AC2 boundary cases in the same way. Both should be pinned to provisional values in the plan (even if marked tunable), for parity with the >=0.90 catch-rate bar.

**7. Enumerate the pinned report schema fields** (claude-p)

AC4 asserts conformance to a pinned JSON schema; AC7 asserts all metrics are populated; gate-metric computation depends on per-case gate-decision fields (gate triggered yes/no, tier assigned, classification label). The schema field names should be enumerated in the plan (or a fixture committed alongside the spec) so AC4 is independently verifiable and consumers of the report agree on field names.

---

### Suggestions

**Justify or relocate K** (claude-p): K (repeated-run count) lives in production-frozen `Settings`. That is a mild coupling smell — production code carries an eval-only knob. The plan should either justify the placement (e.g. so `dataclasses.replace` sweep overrides compose uniformly across K and threshold/top_n in one call) or move K to a runner argument or a separate eval config class. A one-line justification in the plan is sufficient if Settings is the right home.

---

### Guardrail and convention findings

None flagged by either reviewer in this round.

---

**Action:** Mark spec 0009-6a status `reviewed`. Proceed to `/spec:plan`. The plan must address items 1–7 above, with items 1 (gate-metric denominator scope) and 3 (variance rule precision) as the highest-priority planning decisions — they are the only ones that could produce silently incompatible implementations if left to implementer discretion.
