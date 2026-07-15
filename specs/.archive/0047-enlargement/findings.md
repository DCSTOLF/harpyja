# Spec 0047 — enlargement findings (AC6)

**Status:** scope + framing committed now (freeze-before-run); the numeric verdicts are
filled from the committed `power_recheck.json` after the operator runs
`enlargement_run/run_enlargement.sh`. The machine-readable source of truth is
`power_recheck.json` (`0047/power/1`), pinned to `ENLARGEMENT_CONFIG_HASH_0047`.

## The re-check is THEORETICAL-CEILING-ONLY (the AC6 scope fix)

This spec answers "did enlargement remove the N-blocker?" **without running the
bake-off.** Every verdict here is computable from the enlarged pool's *composition*
— tag counts and floors — never from any model's located set:

- The discordance **ceiling** re-checked is `theoretical_discordance_ceiling(conceptual_n)
  = conceptual_n` — the maximum discordance the stratum could exhibit if every
  conceptual case were discordant. It is a **true upper bound**, not an estimate.
- **Empirical** discordance (do two models actually disagree per-case?) is a property of
  located sets and is therefore **out of scope** — deferred to the bake-off spec. In the
  frozen `PowerVerdict` vocabulary that outcome is `DISCORDANCE_STILL_INSUFFICIENT`;
  it is typed here so the answer space is pre-frozen, but it is **resolvable only
  empirically** and this spec never asserts it.

## Which downstream questions are NOW powered — PENDING RUN

Filled from `power_recheck.json.questions` (verdict per bake-off pair, the A/B
feasibility, and the policy-baseline variance question):

| Question | Verdict | Reading |
|---|---|---|
| bake-off qwen3:14b vs qwen3:8b | `POWERED` | theoretical ceiling (44) ≥ floor (8), coverage ≥ min |
| bake-off qwen3:14b vs qwen3.5:4b | `POWERED` | ″ |
| bake-off qwen3:8b vs qwen3.5:4b | `POWERED` | ″ |
| A/B feasibility (0039) | `POWERED` | the 0039 `UNDER_POWERED` stop is lifted at N=44 |
| policy-baseline variance (0046 / OQ2) | `POWERED` | single-draw legitimate at the enlarged N (variance within band) |

Enlarged stratum: **conceptual_n = 44, lexical_n = 9** (pool 19 → 53; conceptual 15 → 44).
Attrition (of ~73 raw sourced under ≤8/repo): blind-ineligible = 22 (issue named the
gold path — 0036's ~28% class held), leaky-dropped = 17, kept = 34 new blind-clean.
Run: author=Codex, verifier=Claude; source fingerprint benign-changed, pinned 50
content-identical.

**Reading:** the theoretical ceiling cleared the floor (and did so already at the old
N=15) — so the N-blocker on the *theoretical* axis is removed, and the 0039/0040
power-stops are lifted for feasibility. The binding question that remains is EMPIRICAL
discordance (do the models actually disagree per-case), which is the bake-off's to
answer — deferred, as scoped. Enlargement's concrete wins: **variance** (53 cells vs the
33 the 0046 instrument-noise finding was measured on) and **coverage** for that bake-off.

## Tag quality — reachability is load-bearing and deterministic; concept-vs-patch is conservative

- **Reachability** (`lexical` | `conceptual`) — the axis that guards the
  `RETRIEVAL_FUNDAMENTAL` confound — is computed DETERMINISTICALLY by
  `classify_reachability` (does the gold-span text contain a code-like identifier from
  the query?). Enlarged distribution: **44 conceptual / 9 lexical** (53 total),
  matching 0036's ~79% conceptual majority. This is the axis the power re-check uses.
- **Concept-vs-patch** (`same` | `divergent`) is tagged CONSERVATIVELY. A `divergent`
  tag is only meaningful with a concept span DISTINCT from the gold patch, and locating
  that reliably needs a repo-aware pass the gold-span-text-only labeler cannot do.
  Rather than fabricate `concept_span = gold` (a self-contradiction — that IS "same"),
  the enlarged cases are tagged `same` (the substantiable default); the labeler's
  same/divergent opinion is kept as ADVISORY provenance in the ledger for a future
  repo-aware pass. The one committed `divergent` case is 0036's original human-label.
  **Limitation:** the enlarged set does not distinguish genuine patch-diverges-from-
  concept cases; recovering that signal is a candidate follow-up (a repo-aware
  concept-span pass), out of scope here. The primary confound axis (reachability) is
  unaffected.

## Necessity, not sufficiency — the nested-sets caveat

Enlargement raises coverage and shrinks run-to-run variance; whether it raises
**discordance** depends on whether the added conceptual cases are ones the models
*disagree* on. 0040 found the located sets nearly nested (4b ⊂ 14b; 8b-conceptual = ∅).
Two outcomes, both first-class:

- If the theoretical ceiling now clears the floor with adequate coverage → the questions
  type `POWERED` (feasibility restored) and the bake-off / A/B may run. **This spec proved
  the N-blocker is removed** (necessity).
- If the ceiling still falls short → `STILL_UNDER_POWERED`: enlargement did not remove the
  blocker, and the constraint is **data volume**. If instead the ceiling clears but the
  eventual bake-off finds discordance still short, that is `DISCORDANCE_STILL_INSUFFICIENT`
  — **model homogeneity, not data volume** — a *different* finding and a *different* next
  spec. This spec does not and cannot decide between "powered" and "homogeneous" on the
  empirical axis; it removes the volume confound so the bake-off can.
