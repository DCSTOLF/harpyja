# Review — spec 0046 "submission"

- **Date:** 2026-07-13
- **Reviewers:** codex (gpt-5.5), claude-p
- **Rounds:** 3
- **Final verdict:** both **approve-with-comments** → **quorum MET** (≥1 approve/approve-with-comments)
- **Status:** `draft` → `reviewed`

## Verdict

Both reviewers judged the spec **plannable and testable as written**. The three
round-3 comments were non-blocking, freeze-discipline fill-ins ("a plan-step action,
not a re-spec") — **all three have been folded into the spec post-quorum** (the
0041–0044 precedent), so they are recorded here as resolved, not outstanding.

## Round history (what each round resolved)

**Round 1 — both changes-requested.** AC3 overclaim ("structurally impossible"), AC5
"≈net +2" untestable, confirm-before-submit placement/semantics under-specified,
trigger enum unresolved while AC2 needs fixtures, tool-count/byte-pin reconciliation
unstated, artifact schema not concrete. → All fixed in round 2.

**Round 2 — both changes-requested (new, deeper findings; round-1 fixes confirmed
adequate and not re-raised).** Headline (both, a formal per-direction-conjunct
convention violation): emit-with-flag could only move the four-sided predicate
*favorably* — a flagged-but-wrong citation on a fired cell landed in no counted side,
so `DISSOLVES_TRADE` was favorable-by-construction and the real cost (flag rate) sat
outside the verdict (0045's de-attribution trap through a new channel). Plus: two
triggers not yet fixturable, the confirmation "intent" predicate not deterministic,
AC7's 4b branch internally inconsistent, AC3(a) needing module-boundary teeth. → All
fixed in round 3.

**Round 3 — both approve-with-comments. Quorum met.** All five round-2 resolutions
confirmed genuine (not relabeled):
- **(C)** the counted fifth side `flagged-wrong-emitted` with s→wc as its conservation
  partner (sum reported), `DISSOLVES_TRADE` now genuinely refutable, "flag everything"
  scored as a failure through two independent nets — "coherent," "the right fix."
- **(A)** the three triggers mechanical/fixturable with near-miss negatives, no gold.
- **(B)** the confirmation predicate deterministic with an undecidable→CONFIRM_ERROR
  branch that makes ambiguity SAFE.
- **(D)** AC7's 4b reconciliation split per-lever and wired to `submit_disposition`.
- **(E)** AC3(a) asserting both symbol-reference and module-boundary isolation.

## Round-3 comments (all folded post-quorum)

1. **Pin the frozen thresholds (both).** The `flagged-wrong-emitted` ceiling and the
   AC4d flag-rate range were referenced but not given a value/derivation rule, unlike
   the numerically-pinned `[1,3]` baseline band; since the ceiling is a conjunct of the
   *frozen* predicate, its bar must be fixed before the freeze.
   → **Folded:** added the **Frozen thresholds (two-stage freeze)** note to AC7 — both
   are baseline-relative, committed as config literals *after* the baseline arm yields
   per-model s→wc and *before* the new-arm spend; the ceiling is a relabel-tolerance
   fraction (< 1) of baseline s→wc (so a whole-mass relabel breaches it), the flag-rate
   range an upper bound on the flagged fraction. The derivation *rule* is frozen in the
   spec; the derived literals are the config commit (driver re-verifies the hash).
   Also corrected AC7's reasoning: the CEILING (not the sum conjunct) blocks a pure
   relabel; the sum conjunct blocks *new* wrong mass.

2. **Tighten the truth-table column semantics (both).** The "gate fired?" column was
   undefined and could let a naive grid-totality implementer route a flagged-wrong
   *regression* into the wrong bucket, given the interceptor runs on every submit.
   → **Folded:** the column is now **`s→wc-eligible?`** = the retained 0045 condition
   (baseline-silent ∧ 0044 gate fired); the flag is an explicit *orthogonal* axis that
   changes the counted side only inside the s→wc-eligible-wrong partition. Added the two
   `wrong | no` rows making the boundary explicit, and an AC4b fixture that pins it in
   test (not-eligible-wrong-FAIL → regression/miss; eligible-wrong-FAIL →
   flagged-wrong-emitted).

3. **Pin the query key-identifier extraction rule (claude-p).** The FAIL/CONFIRM_ERROR
   boundary was author-discretionary until the query-side extraction was pinned like the
   triggers (safe, because undecidable → CONFIRM_ERROR, but unpinned).
   → **Folded:** extraction is now mechanical — identifier-shaped tokens in the query
   (`[A-Za-z_][A-Za-z0-9_]*`, length ≥ floor, dotted paths whole), preferring
   backtick/quote-delimited tokens; reads the query only, never the gold.

Editorial (codex): the `hit-in-comment` docstring wording risked excluding real
docstrings ("inside NO function/class/statement span"). → **Folded:** reworded to
"comment node or docstring node (a string literal in statement position)."

## Strengths (reviewer-noted)

The REVERT-lever/KEEP-apparatus framing; the reactive + confirm-in-submit-path
decomposition; the disciplined 0045 apparatus retention; the AC3 code-structure /
fixture split as the correct dissolution of the round-1 overclaim; the host-side
placement that keeps the five-tool suite and the byte-pin intact; and — the round-2
centerpiece — counting the flag's cost as a fifth side with a conserved s→wc partition
rather than documenting the hole with a side-observable.

## Next step

`/speccraft:spec:plan` — turn the reviewed spec into a test-first plan. Two derived
literals are deferred to the plan's two-stage freeze (committed after the baseline arm,
before the new-arm spend): the `flagged-wrong-emitted` ceiling fraction and the AC4d
flag-rate range. The derivation rules and freezing order are already pinned in AC7.
