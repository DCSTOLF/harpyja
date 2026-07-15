---
spec: "0047-enlargement"
reviewers: [codex, claude-p]
quorum: 1 (approve or approve-with-comments)
verdict: approve-with-comments
generated: 2026-07-14T00:00:00Z
---

# Cross-model review — 0047-enlargement

**Quorum status: MET** — claude-p returned `approve-with-comments`, satisfying the
1-approval quorum. codex returned `changes-requested`; per policy that verdict is
folded in as strong pre-plan refinement input, not a blocker, since quorum is
already satisfied by an independent approve-with-comments.

## codex

**Verdict:** changes-requested

Concerns:
- Target N is a binding AC (AC4) but left as an open question with only an
  illustrative "(say) 40 conceptual cases" — makes AC4 non-verifiable as written.
- Sampling frame for NEW SWE-bench cases unpinned: same-repos-vs-new-repos, repo
  caps, exclusions, ordering, and seed are all still open — selection bias and
  train-on-test leakage remain possible.
- The re-check of 0040 discordance / 0039 feasibility (AC5) does not define the
  typed outcome vocabulary or stop/pass thresholds for "NOW powered," per
  question and per pair.
- AUDITED CONVERT step underspecified operationally: sha256-pinning is named but
  not the source snapshot, case manifest format, duplicate handling, or the
  integrity check proving the existing 19 remain byte-identical while new cases
  are appended.

Suggestions:
- Move raw-case count, expected yield, target conceptual N, headroom, and repo
  sampling rule out of Open Questions into frozen What/Acceptance sections.
- Add a pinned input manifest for candidate SWE-bench cases (source snapshot
  hash, repo/case IDs, ordering, exclusion reasons, deterministic selection
  rule).
- Define the post-enlargement verdict labels per downstream consumer (e.g.
  `POWERED`, `STILL_UNDER_POWERED`, `DISCORDANCE_STILL_INSUFFICIENT`,
  `VARIANCE_REQUIRES_MULTI_DRAW`).
- Make AC5/AC6 require machine-readable output artifacts (per-pair ceilings,
  0039 feasibility, stratum counts, attrition counts) — not only prose.

Guardrail violations: none

Convention violations:
- Acceptance scope tags should be declared before use — AC6 uses `[doc]` but the
  scope-key preamble only defines `[unit]` and `[integration]`.

Discussion: Core direction is sound — pool enlargement is correctly framed as an
instrument-quality problem, not a policy lever, and preserves the 0036
constraints. The main blocker in codex's read: the spec asks the implementation
to "state the arithmetic" while leaving the arithmetic itself unresolved. For a
measurement spec, target N and sampling frame are not implementation details — a
compliant implementation could pick a convenient raw count, discover
insufficient conceptual/discordant coverage, and still satisfy much of the text
by honestly reporting failure, without ever producing a frozen enlargement plan.
Recommends either freezing the candidate-source manifest and target arithmetic
now, or making the spec explicitly two-phase (phase 1 = dry-run yield audit,
phase 2 = pinned enlargement) — the current draft mixes both modes.

## claude-p

**Verdict:** approve-with-comments

Concerns:
- AC5/AC6 vs Out-of-scope tension: "re-run 0040's per-pair ceiling" and "did
  enlargement add DISCORDANT cells" read as requiring actual located sets (the
  bake-off) — but the bake-off is explicitly out of scope and the scope key
  promises "no live model runs required." The spec must state unambiguously that
  the AC5/AC6 re-check is the THEORETICAL ceiling (max discordance =
  conceptual-stratum size, computable from tags alone), with EMPIRICAL
  discordance deferred to the next spec. As worded, "add discordant cells"
  invites either running out-of-scope models or shipping an uncomputable
  criterion.
- Chicken-and-egg between AC4 (Target-N pinned) and OQ1 (the 38% yield is
  unconfirmed on a new slice). Blind-clean OUTPUT N cannot be pinned until
  convert attrition is actually measured. The spec should distinguish RAW
  convert size (pinned upfront from an assumed yield) from blind-clean OUTPUT
  size (which floats with measured attrition), and say explicitly which one AC4
  freezes.
- No preregistration/freeze of the power-decision verdict. Specs 0040–0046
  treat the two-stage freeze (commit the typed decision rule BEFORE seeing the
  numbers) as mandatory. AC5 promises a verdict "typed per question, per pair"
  but does not commit to freezing that typing rule before enlarged stratum
  counts are known. Given the standing train-on-test confound, an unfrozen
  power verdict is exactly the steering the freeze discipline exists to
  prevent.

Suggestions:
- Name the owning module/data location. `packages: []` is empty and no path is
  given; the eval-set, provenance.json, and authoring tooling live somewhere
  concrete (harpyja/eval/, the 0036 pool artifacts) — name it.
- Add a sentence on how NEW raw SWE-bench cases are acquired and how that
  squares with the air-gap guardrail (acquisition is authoring-time, one-time,
  offline-of-the-SUT — almost certainly fine, but say so explicitly).
- OQ2 (multi-draw baseline / variance at new N) partly belongs in an AC, not
  just an open question: if the enlarged-N variance computation gates whether a
  single-draw baseline is legitimate, "compute expected variance at target N and
  state whether single-draw suffices" is a testable deliverable, not just a
  question to ponder.
- State the ≤3/repo discipline (OQ3) as a first-class invariant or AC rather
  than an open question.

Guardrail violations: none

Convention violations:
- Specs name their packages/owning module — frontmatter `packages: []` is
  empty and no module is named in What/Work.
- Two-stage freeze: commit the typed decision rule before the numbers
  (standing 0040–0046 discipline) — AC5's typing rule is not frozen-before-numbers.

Discussion: Strong, well-motivated spec; the framing pivot — from "the lever
traded" to "the instrument can no longer resolve whether it traded" — is the
spec's best feature and is well-supported by the 0046 evidence cited. The
invariants are disciplined: each is a genuine constraint on HOW enlargement is
done, not a smuggled target. The substantive worry is the AC5/AC6 ↔
Out-of-scope boundary: the spec's entire value proposition is unblocking the
bake-off WITHOUT running it, which only works if every AC is computable from
pool composition (tags/counts/floors) rather than located sets. AC5
(feasibility/ceiling) is computable that way; AC6 as worded is not (discordance
is empirical). The intent clearly reads as ceiling-only; one clarifying
sentence fixes it. Second concern: the target-N chicken-and-egg changes the
plan's shape (pin raw vs. pin output) and should be resolved explicitly.
Everything else raised is clarification, not redesign. Would approve outright
once AC6's scope boundary and AC4's raw-vs-output pin are made explicit.

## Synthesis

Both reviewers endorse the spec's core diagnosis and direction — pool
enlargement as an instrument-quality fix, not a policy lever, correctly
carrying forward the 0036 protocol and constraints — and neither found any
guardrail violation. The disagreement in verdict label (changes-requested vs.
approve-with-comments) is mostly a difference in how strictly to gate on
under-specification before planning begins, not a disagreement about what's
wrong. Three items were independently flagged by both agents, which is the
strongest signal in this review:

1. **Target-N is under-pinned and chicken-and-egg with the unconfirmed 38%
   yield.** AC4 requires "the arithmetic" to be stated, but Open Question 1
   contains the actual unresolved arithmetic (raw count, yield assumption,
   headroom). Both agents want this resolved before AC4 can be verified, and
   both note the raw-vs-output ambiguity: does the spec pin the RAW convert
   count (assumption-driven, frozen upfront) or the blind-clean OUTPUT count
   (measured, floats with attrition)? The spec must say which.
2. **The typed power-verdict vocabulary/thresholds are not frozen before the
   numbers are seen.** codex wants concrete verdict labels defined ahead of
   time; claude-p ties this directly to the standing 0040–0046 two-stage-freeze
   discipline, which is process-critical given the train-on-test confound this
   spec itself names. This is arguably the most consequential convergent item —
   it's a repo-wide convention, not just a style nit.
3. **Owning module / manifest is unnamed.** claude-p flags this as a convention
   violation (`packages: []`, no path given); codex converges on the same gap
   from the operational side (no case manifest format, no source-snapshot
   pinning, no duplicate-handling / integrity spec for proving the existing 19
   remain byte-identical).

One additional structural point, raised only by claude-p but load-bearing: **AC6
as worded is not out-of-scope-safe.** "Did enlargement add DISCORDANT cells"
reads as requiring located sets from an out-of-scope bake-off. Given the spec's
scope key explicitly promises no live model runs, this is a real internal
inconsistency, not just a suggestion — AC6 needs one sentence restricting it to
the THEORETICAL ceiling (computable from tag counts), with empirical discordance
explicitly deferred to the next spec.

codex's remaining concerns (sampling-frame pinning for repo selection, `[doc]`
scope tag undeclared, machine-readable output artifacts for AC5/AC6) are real
but narrower — they sharpen the same underlying gaps (target-N/sampling-frame
under-specification) rather than introducing new risk categories.

## Prioritized findings

### Must-fix before /plan (convergent or scope-breaking)
- **Pin target-N arithmetic and resolve raw-vs-output ambiguity** (AC4). State
  explicitly whether AC4 freezes the RAW convert count (assumption-driven) or
  the blind-clean OUTPUT count (attrition-measured), and move the arithmetic
  from Open Question 1 into What/Acceptance. *(codex + claude-p, convergent)*
- **Freeze the typed power-verdict vocabulary and thresholds before enlarged
  numbers are seen** (AC5), per the standing 0040–0046 two-stage-freeze
  discipline. Define the labels (e.g. `POWERED`, `STILL_UNDER_POWERED`,
  `DISCORDANCE_STILL_INSUFFICIENT`) up front. *(codex + claude-p, convergent —
  claude-p flags as convention violation)*
- **Fix AC6's out-of-scope leak.** Restrict the nested-sets re-check to the
  THEORETICAL ceiling (computable from tag counts/floors), and explicitly defer
  empirical discordance to the next (bake-off) spec, matching the scope key's
  "no live model runs required" promise. *(claude-p; scope-consistency issue)*
- **Name the owning module / package.** Fill in `packages: []` and state where
  the eval-set, provenance.json, and authoring tooling live (e.g. `harpyja/eval/`
  extending the 0036 pool artifacts). *(claude-p, convention violation; codex
  converges via the manifest-format gap)*
- **Pin the candidate-case sampling frame**: same-repos vs new-repos, repo
  caps (preserve or justify changing the ≤3/repo discipline), exclusions,
  ordering, and a deterministic selection rule, to close the selection-bias /
  train-on-test-leakage risk. *(codex; claude-p's OQ3 suggestion converges on
  the ≤3/repo piece)*
- **Add the AUDITED CONVERT integrity spec**: source snapshot hash, case
  manifest format, duplicate handling, and the drift-guard proving the existing
  19 labels stay byte-identical while new cases are appended. *(codex)*

### Nice-to-have / can be resolved during planning or execution
- Declare `[doc]` in the AC scope-key preamble (currently only `[unit]` and
  `[integration]` are defined). *(codex)*
- Require machine-readable output artifacts (not just prose) for AC5/AC6:
  per-pair ceilings, 0039 feasibility, stratum counts, attrition counts.
  *(codex)*
- Add a sentence on how new raw SWE-bench cases are acquired and confirm this
  is authoring-time/offline-of-the-SUT, consistent with the air-gap guardrail.
  *(claude-p)*
- Promote OQ2 (expected variance at new N; whether single-draw suffices) to a
  testable AC deliverable rather than leaving it purely as an open question.
  *(claude-p)*

## Guardrail violations

None reported by either agent.

## Convention violations

- **Scope tags declared before use**: AC6 uses `[doc]`, undefined in the scope
  key preamble (only `[unit]`/`[integration]` are defined). — codex
- **Specs name their packages/owning module**: frontmatter `packages: []` is
  empty; no module is named in What/Work. — claude-p
- **Two-stage freeze (0040–0046 standing discipline)**: AC5's typed
  power-verdict rule is not committed before the enlarged-pool numbers are
  seen. — claude-p

## Action

Quorum is met (claude-p: approve-with-comments). **Proceed to `/plan`**, but
fold the convergent must-fix items above into the spec first — specifically:
pin the target-N arithmetic (raw vs. output), freeze the typed power-verdict
vocabulary before numbers are seen, fix AC6's out-of-scope leak, name the
owning module, pin the sampling frame, and specify the audited-convert
integrity checks. These are refinements to a sound spec, not a redesign — both
reviewers independently converge on the same root gap (target-N /
power-verdict under-specification) and neither found a guardrail violation or a
disagreement about direction. Recommend a short revision pass on spec.md
addressing the six must-fix items above, then re-run `/plan` without requiring
a second review cycle unless the revision changes scope materially.
