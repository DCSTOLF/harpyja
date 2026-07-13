---
spec: "0043-diagnosis"
reviewers: [codex, claude-p]
quorum: 1
round: 2
verdict: approve-with-comments
generated: 2026-07-12T00:00:00Z
---

# Cross-model review — 0043-diagnosis

## Round 1 (condensed)

| Reviewer  | Verdict            |
|-----------|--------------------|
| codex     | changes-requested  |
| claude-p  | changes-requested  |

**Round-1 overall: changes-requested. Quorum NOT met.** Spec stayed `draft`.

Round 1 found the spec's evidence-base claim factually wrong (committed `.archive` artifacts are summaries
only; full trajectories live in gitignored `eval_work`), AC1's per-turn latency unsatisfiable as written, no
freeze discipline before the AC5/AC6 live spend, an underspecified found-but-unsubmitted detector, an
unnamed artifact/schema bump target, and a frontmatter convention violation. Full round-1 detail (concerns,
suggestions, synthesis, convergent/divergent findings) is preserved in git history at this file's prior
revision.

**Round-1 action list — all 10 items applied before round 2:**

1. Fix frontmatter (`started_at_sha` present, canonical schema) — DONE.
2. Correct the evidence-base claim (real evidence base named: gitignored `eval_work/live_artifacts/`) —
   DONE.
3. Rescope AC1 to recorded quantities; per-turn/per-turn timing labeled ESTIMATE; `per_turn`/`model_turns`
   length-skew note added — DONE.
4. Pin the found-but-unsubmitted detector (AC2): one-oracle-reuse, stringified `CodeSpan` string-parse,
   fixture matrix, `detector-inconclusive` typed outcome — DONE.
5. Name the artifact/schema bump explicitly (VERIFIER/TRAJECTORY artifact, both assembly seams,
   written-JSON test) — DONE.
6. Add a freeze step before AC5/AC6 (`PREREGISTERED_DIAGNOSIS_CONFIG_0043`, total-pure-function verdict,
   bidirectional bucket movement) — DONE.
7. Add a frozen attribution-to-lever decision table, lever recorded as data — DONE.
8. Require AC5's BEFORE/AFTER to use the identical detector; commit the derived attribution table pinned
   to artifact hashes — DONE.
9. Strengthen AC3 with named discriminating evidence for the 4b inversion — DONE.
10. Add an explicit SUT-pin preservation clause to AC4/FIX (`messages` not `params`; deliberate,
    reviewed ceiling change) — DONE.

## Round 2 — 2026-07-12

| Reviewer  | Verdict                  |
|-----------|--------------------------|
| codex     | approve-with-comments    |
| claude-p  | approve-with-comments    |

**Overall: approve-with-comments. Quorum (1 approve / approve-with-comments) MET.** Spec status →
`reviewed`.

### codex

**Verdict:** approve-with-comments

Concerns:
- AC2 still under-specifies the detector output for submitted-but-dropped cases: the fixture matrix names
  `submitted-then-dropped`, but the typed outcome set only lists `found-unsubmitted`, `never-found`, and
  `detector-inconclusive` — does not say what the detector emits when the model did submit a
  gold-overlapping raw candidate that normalization later dropped.
- AC4's freeze timing should say "before attribution numbers are computed/inspected", not "before the live
  attribution numbers are computed"; the attribution is explicitly offline, so wording is muddy.

Suggestions:
- Add an explicit classification for submitted-then-dropped so submit-discipline failures are not
  conflated with never-found.
- Name the run ledger source/path pattern used for case-level latency, matching the artifact-hash pinning
  posture.

Guardrail violations: none. Convention violations: none.

Discussion: Round 2 addresses the blocking round-1 issues — evidence base honest, per-turn latency
correctly downgraded, freeze discipline substantially repaired (preregistered config, gated endpoint,
bidirectional movement, total pure AC6 verdict, frozen lever table). Remaining detector issue not blocking
but should be tightened before implementation. Now implementable and convention-aligned.

### claude-p

**Verdict:** approve-with-comments

Concerns:
- AC2's typed-outcome enum is not total against its own six-case fixture matrix: submitted hit and
  submitted-then-dropped have no named outcome — needs the full enum (e.g. `submitted`,
  `submitted-then-dropped` via the 0033 `citations_submitted`/`citations_surviving` counts).
- AC6 has no mechanical power floor: 0042 had `MIN_RFWS_DENOMINATOR=3` as a frozen branch; 0043's guard is
  only prose ("must not type `CLOCK_BOUND_FIXED` unqualified"). If the eval_work-surviving BEFORE subset
  is 1–2 cells, nothing stops an unqualified positive verdict.
- AC5's before/after delta can be silently biased by an asymmetric detector-inconclusive rate (BEFORE
  parsed from stringified reprs, AFTER produced under the new schema/possibly changed prompt) —
  inconclusive counts must be reported per side and enter the verdict.
- AC1 asserts "case-level latency from the run ledger" as measured, but the spec never verified the ledger
  records it — if not, it silently becomes another labeled-estimate case and should be stated now.
- AC4/AC5 freeze sequencing is implicit: lever table freezes before attribution, but the config (naming
  the lever) can only freeze after lever selection — state the two-stage ordering explicitly.

Suggestions: complete the AC2 enum via 0033 SubmitResult counts; add a frozen MIN floor plus a
`CLOCK_BOUND_UNDER_POWERED` fourth branch; report inconclusive counts per side; verify-or-downgrade the
ledger latency claim; state the two-stage freeze order explicitly; reword "live attribution numbers".

Guardrail violations: none. Convention violations: none.

Discussion: All ten round-1 action items discharged, mostly verbatim. Substantively better spec; remaining
issues are precision gaps, not structural — hence approve-with-comments.

### Convergent round-2 findings (both agents)

1. **AC2 outcome-enum totality.** Both agents independently flag that the typed-outcome enum did not cover
   every row of its own fixture matrix — specifically the `submitted` / `submitted-then-dropped` rows had
   no named outcome member, risking a silent collapse of submit-discipline failures into `never-found`.
2. **"Live attribution numbers" wording in AC4/the two-stage-freeze invariant.** Both flag the phrase as
   muddy given the attribution is explicitly offline (no live compute); the freeze-ordering language needed
   to be stated precisely.

### Guardrail / convention violations

None reported by either agent in round 2.

## Post-quorum residuals

Quorum was met at round 2 (both agents approve-with-comments), so the spec's status advances to `reviewed`
without a round 3. Per the 0041/0042 precedent (residual reviewer comments folded into the spec directly
after quorum, rather than gating another review cycle), all round-2 residual comments — convergent and
per-agent — were folded into `spec.md` post-quorum. Recorded as DONE:

1. **AC2 enum completed to five members.** `found-unsubmitted`, `submitted`, `submitted-then-dropped`
   (routed through the existing 0033 `citations_submitted`/`citations_surviving` counts —
   one-counter-reuse, never re-derived from history parsing), `never-found`, `detector-inconclusive`. The
   fixture matrix now maps each of its six rows to its enum value (tool-result hit → `found-unsubmitted`;
   submitted hit → `submitted`; submitted-then-dropped → `submitted-then-dropped`; path-only (no gold
   line overlap) → `never-found`; never-found → `never-found`; unparseable → `detector-inconclusive`).
2. **AC6 gained a frozen power floor.** `MIN_COVERED_BEFORE_CELLS` is now a named field in
   `PREREGISTERED_DIAGNOSIS_CONFIG_0043` (the 0042 `MIN_RFWS_DENOMINATOR` pattern), and AC6 gained a fourth
   typed branch, `CLOCK_BOUND_UNDER_POWERED` (covered subset below the frozen floor — the qualification is
   a returned enum member, never prose).
3. **AC5 now requires detector-inconclusive counts reported PER SIDE**, with a large BEFORE/AFTER
   asymmetry named as an explicit caveat in the outcome (identical detector prevents definition drift, not
   input-distribution drift).
4. **Ledger-latency claim VERIFIED during residual folding** by direct inspection of the committed 0042
   `adoption_results.json`: ledger entries carry `{artifact, attempts, bucket, citations_submitted,
   citations_surviving, degrade, symbols_invocations, tools, verifier_artifact}` — no elapsed/duration
   field; each verifier artifact carries exactly one timestamp. Case-level timing is therefore reclassified
   ESTIMATE-GRADE (successive verifier-artifact timestamp deltas within a sequential run block) in the
   evidence-base section, AC1, and the What section — this resolves codex's "name the ledger source"
   suggestion the same way (no such field exists to name; the derivation method is named instead).
5. **A new explicit two-stage freeze invariant added:** stage 1 — the attribution-to-lever decision table
   freezes before attribution numbers are computed or seen; stage 2 — `PREREGISTERED_DIAGNOSIS_CONFIG_0043`
   (naming the selected lever) freezes after lever selection but before any live spend — with the rationale
   stated for why post-attribution config freeze is by design, not a violation.
6. **AC4 rewording applied**: "before the attribution numbers are computed or seen … the attribution is
   offline, no live compute" replaces the muddier "before the live attribution numbers are computed."

**Verification note:** all six items above were confirmed present in `specs/0043-diagnosis/spec.md` by
direct re-read at synthesis time (evidence-base section, INVARIANT blocks, AC1/AC2/AC4/AC5/AC6). No further
residuals are open.

## Synthesis

Round 2 closes all ten round-1 blocking items, several with verified evidence (direct artifact inspection
for both the trajectory-summary claim and the ledger-latency claim) rather than assertion. Both round-2
reviewers converge on the same two remaining precision gaps — AC2 enum totality and the offline-wording of
the freeze invariant — plus each raised additional non-blocking precision issues (codex: named ledger
source; claude-p: mechanical power floor, per-side inconclusive reporting, explicit two-stage freeze
ordering). Neither agent found a guardrail or convention violation in round 2. Because quorum was met, these
residuals were folded into `spec.md` directly post-quorum per the 0041/0042 precedent rather than gating a
round 3, and verified present by re-read.

**Action:** None outstanding — spec 0043-diagnosis moves to status `reviewed`. Next step:
`/speccraft:spec:plan`.
