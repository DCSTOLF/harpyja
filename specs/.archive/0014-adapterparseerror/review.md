---
spec: "0014-adapterparseerror"
reviewers: [codex (gpt-5.5), claude-p]
quorum: 1
verdict: approve-with-comments
generated: 2026-06-30T00:00:00Z
---

# Cross-model review — 0014-adapterparseerror

## codex (gpt-5.5)

**Verdict:** approve-with-comments

Concerns:
- The exact upstream exception class is still unresolved. Acceptable for a draft, but load-bearing: implementation must pin against the dspy path actually used before `spec:plan`, or the narrow-catch invariant is not testable.
- The report schema change is directionally right but underspecified: exact new field names, defaults, denominator/count fields, and validator behavior should be named so producers and sinks cannot drift.
- `degraded_dominated` needs precise semantics when both Scout and Deep degrade in one case, otherwise implementations may double-count or inconsistently classify pooled outcomes.
- The memory/convention update is described in prose but not represented as an acceptance criterion, so it could be skipped during closeout.

Suggestions:
- Add an AC requiring `raise DeepUnavailable(...) from err` so the foreign parse exception cause is preserved.
- Add an explicit AC for old-shape report compatibility using centralized defaults, matching the existing schema convention.
- Promote the `.speccraft/conventions.md` update to a numbered acceptance criterion.
- Specify the exact report keys, including numerator/count fields and `null` behavior for zero denominators.

Guardrail violations: none.
Convention violations: none.

Discussion: Spec is sound; preserves the Deep boundary (malformed infra output degrades, weak-but-valid Tier-2 stays honest). Strongest part is the explicit refusal of a broad catch; AC3/AC4 are the right regression pair. Main thing to tighten before planning is observability shape — name the field set, defaults, validator expectations, and every sink category; make the central-defaults/old-shape compatibility convention explicit. Would not block on the unresolved dspy exception class as long as it stays a MUST before `spec:plan`; if approving for immediate implementation, that would be changes-requested because the catch boundary is the core behavioral contract.

## claude-p

**Verdict:** approve-with-comments

Concerns:
- Cause-id collision with precedent: the spec mints a NEW distinct cause `deep-degraded:parse-error`, but the Scout precedent it leans on (and conventions memory: "map ANY unexpected backend exception to `...Unavailable(backend-error)`") collapses third-party post-processing crashes into `backend-error`. `AdapterParseError` IS a third-party parse/post-processing crash. The spec asserts "distinct cause, not reusing an existing one" without reconciling against that precedent — is `parse-error` a deliberate new sibling of 0006 `backend-error`, or should it fold in? Must be justified, not asserted (Open question #3 only addresses a finer adapter-vs-model split, not the backend-error reuse question).
- `tiers_run` semantics on a Deep degrade are ambiguous and intersect the visibility invariant. 0006 says an honest empty Deep run is `tiers_run=[0,2]` and a degrade falls back to Scout best-effort. AC5 says `tiers_run` reflects the floor reached. If a parse-error degrade records `[0,1]`, the run looks like Deep was never attempted — the degrade goes dark in `tiers_run` and survives only via the flag, which is precisely the invisibility this spec exists to prevent. Define whether `tiers_run` records the attempted Tier-2 or only the floor.
- AC8 (integration) requires "a run that previously crashed now completes" — but a malformed model response is nondeterministic. The spec doesn't say how the live trigger is reproduced (canned/fixtured bad response? fault injection at the seam?). Without a deterministic trigger this AC is unrunnable or flaky, even as skip-not-fail.

Suggestions:
- State null/zero-denominator handling for the new `deep-degraded` rate explicitly (convention: undefined metric = explicit `null` + count field, never omitted, never false `0.0`, `indicative_only` on too-few-samples). Presumably inherited from the 0011 Scout machinery, but say so since AC6 makes it first-class.
- Open question #2 (partial/streaming salvage): lean treat-as-failed is correct, but salvaging a valid prefix from a response whose parse FAILED risks emitting a citation off an incompletely-parsed response — flirts with "never a confident unverified citation." Make the guardrail link the deciding factor, not just "simpler."
- Resolution of Open question #1 (exact dspy exception class) should be captured back in the spec/plan before close, with the specific class names pinned, so the narrow-catch surface is auditable later.

Guardrail violations: none.
Convention violations:
- rule: "When wrapping a foreign exception, preserve the cause (`raise ... from err`)" — location: "What — bullet 1 (catch `AdapterParseError` → `DeepUnavailable`); wrapping specified but cause-preservation never required."
- rule: "Versioned report schema additive fields: centralize the field set + defaults in one anti-drift `_*_DEFAULTS` map; both old-shape and new-shape pass one loud validator" — location: "What — degrade-visibility bullet / AC7 (schema bump 0012/1 → 0013/1). Bump and blast radius required, but centralized `_*_DEFAULTS` map and single loud validator not carried forward."

Discussion: Strong, well-grounded spec. Does the three things this project keeps relearning: preserves typed-failure-only (AC3 load-bearing, guarded both sides), refuses bare-except (AC4), promotes degrade-visibility to a standing convention deliverable via memory-keeper. Scoping discipline good ("unblocks, does not run"). Open question #1 correctly gated MUST-before-plan. The one substantive worry is the cause-id question: the spec leans on the Scout `backend-error` pattern for authority but forks a NEW `parse-error` cause — a coherent answer exists (a parse failure is a recognized/typed seam, not an unexpected exception, so it earns its own cause while truly-unexpected exceptions still fold to `backend-error`) but the spec must write it down. The `tiers_run` ambiguity is small but adjacent to the spec's own thesis. None blocking.

## Synthesis

Both reviewers independently converge on approve-with-comments and agree the spec gets the load-bearing invariants right: the typed-failure-only boundary stays intact (malformed Deep output degrades, weak-but-valid Tier-2 output stays honest), the narrow-catch refusal is correctly framed as a MUST, and the degrade-visibility machinery extension to Deep is the right move. Neither reviewer found a guardrail violation.

The two reviews are complementary rather than contradictory: codex focuses on observability-shape underspecification (exact schema fields, defaults, validator behavior, `degraded_dominated` semantics), while claude-p surfaces three sharper structural questions — whether `deep-degraded:parse-error` should really be a new cause or fold into the existing `backend-error` precedent, whether `tiers_run` on a degrade silently erases evidence that Deep was attempted (undermining the spec's own visibility thesis), and whether AC8's live-crash trigger is deterministic enough to be a real regression test. Both reviewers independently flag the same two completeness gaps as convention/AC omissions: cause preservation (`raise ... from err`) and the centralized-defaults/single-validator pattern for the schema bump.

## Must-address before `spec:plan`

1. **Open question #1 — pin the dspy exception class.** Already gated as a hard MUST in the spec; both reviewers reaffirm it blocks implementability of the narrow-catch invariant. Resolve against the actual dspy source path in use before planning.
2. **Cause-id reconciliation.** Justify, in writing, why `deep-degraded:parse-error` is a deliberate new sibling cause rather than a fold-in to the existing `...Unavailable(backend-error)` convention. The "parse failure is a recognized/typed seam vs. truly-unexpected exception" distinction is a plausible answer — but the spec currently asserts distinctness without reconciling it against precedent.
3. **`tiers_run` semantics on a Deep degrade.** Decide and state explicitly whether `tiers_run` records the Tier-2 attempt (e.g. `[0,2]` per 0006's honest-empty-run precedent) or only the floor reached (e.g. `[0,1]` per AC5's current wording). This is directly adjacent to the spec's own visibility thesis — an ambiguous answer risks the degrade going dark outside the explicit flag.
4. **AC8 deterministic trigger.** Specify how the "previously-crashed run now completes" integration check is reproduced — fixtured/canned malformed response or fault injection at the adapter seam — rather than relying on a live, nondeterministic model failure.

## Should-address (carry into plan/What)

- Add an explicit AC requiring `raise DeepUnavailable(...) from err` to preserve the original parse exception as `__cause__`.
- Carry forward the existing schema convention: centralize new field names + defaults in one anti-drift `_*_DEFAULTS` map, and ensure a single loud validator accepts both old-shape and new-shape reports.
- Name the exact new report field set (keys, numerator/count fields), and state null/zero-denominator behavior (explicit `null` + count, never omitted, never a false `0.0`; `indicative_only` under low sample counts) — consistent with the inherited 0011 Scout convention.
- Define `degraded_dominated` semantics for the case where both Scout and Deep degrade in the same run, to prevent double-counting or inconsistent pooled classification.
- Promote the `.speccraft/conventions.md` update to a numbered, closeout-checkable acceptance criterion rather than leaving it as prose.
- Resolve Open question #2 (partial/streaming salvage) by anchoring the decision explicitly to the "never a confident unverified citation" guardrail, not just implementation simplicity.

## Non-blocking / nits

- Open question #3 (adapter-vs-model finer cause split) is acknowledged as out of scope for this round but should stay linked to the cause-id reconciliation item above so they're resolved together, not independently.

## Guardrail violations

None reported by either reviewer.

## Convention violations

Two raised by claude-p — both are spec-completeness gaps (omissions from the What/AC text), not violations present in shipped code:
- Missing requirement to preserve exception cause via `raise ... from err` when wrapping `AdapterParseError`.
- Missing carry-forward of the centralized `_*_DEFAULTS` map + single loud validator convention for the additive schema bump (0012/1 → 0013/1).

Both should be folded into the "Should-address" items above and closed via explicit ACs before/during `spec:plan`.

## Recommendation

**Action:** Proceed to `/speccraft:spec:plan`. Quorum is met (2/2 approve-with-comments, no rejects, no guardrail violations). The four must-address items above are plan-time inputs rather than blockers — Open question #1 (dspy exception class) is already a hard gate the plan must resolve; the cause-id, `tiers_run`, and AC8-determinism items should be settled and reflected back into the spec's What/AC sections either just before or during planning. Status moves to `reviewed`.
