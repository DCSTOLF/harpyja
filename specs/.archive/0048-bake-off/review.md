# Spec 0048 — bake-off — Review

> **STATUS: two review rounds complete.** Round 1 (below, revision 0) flagged a missing
> analysis contract; it was added and the ACs strengthened. Round 2 (revision 1) confirmed
> **all five first-round consensus concerns RESOLVED** and surfaced a set of narrow
> contract-hygiene items, which have now ALSO been applied (revision 2). See **Round 2** at
> the bottom. Current status: `reviewed`.

**Round 1 verdict summary:** codex = changes-requested, claude-p = approve-with-comments; quorum met (1/1); recommended action = address the shared statistical-pre-registration gaps before `/speccraft:spec:plan`.

## Consensus concerns (raised by BOTH agents — load-bearing)

1. **No concrete pre-registered discordance floor.** The spec never states the empirical
   discordance floor as a hard number, per-stratum, per-pair. 0047's `POWERED` verdict was
   theoretical/tag-count only; the empirical floor was explicitly deferred to this spec. Without
   a stated number, AC3's "vs floor" language and AC7's "powered, honestly N'd" outcome are
   uncheckable at review/grading time. (Contrast: 0040 stated its floor as 8 explicitly.)

2. **Single-draw-per-model vs. run noise.** With one draw per model, McNemar discordant-cell
   counts can't distinguish genuine capability difference from sampling noise. Two fixes were
   proposed — pin decoding to deterministic (greedy / temp-0 / seed-pinned) and record that in
   the frozen config and the durable-artifact schema (cheap), or replicate borderline/close pairs
   (expensive). The spec needs to pick one and put it on the record, not leave it implicit.

3. **Served-tag verification gap.** AC1 preflights coherence and `/v1` tool-calling but never
   names the convention-mandated *positive* `/api/tags` membership check (env-gated,
   skip-not-fail) for the tags actually being scored. `qwen3:14b` is arc-verified elsewhere;
   `qwen3:8b` and `qwen3.5:4b` are asserted without equivalent provenance — and the spec's own
   architecture note warns the default 8B tag does *not* serve. This is the one gap that touches
   a hard convention, not just a statistical nicety.

4. **No slot for intransitive/cyclic ranking.** If the three pairwise contrasts produce a cycle
   (e.g., 14b>8b, 8b>4b, 4b>14b), the current RANKING/PARTIAL/NO_SEPARATION outcome enum has
   nowhere to put that result. Add a typed outcome for it before the run, not after.

5. **Multiple-comparisons posture is unstated.** 3 pairs × 2 strata = up to 6 McNemar tests
   feeding one ranking conclusion, with no family-wise correction or explicit statement of why
   none is needed. The spec should state whether/how it corrects, and set the expectation that
   thin conceptual/lexical cells may mostly type null under correction.

## Additional concerns (single-agent)

**codex:**
- `PAIR_MODELS_TOO_CLOSE` is not mathematically distinguished from ordinary low discordance —
  needs an equivalence margin / minimum-effect rule, or else should be renamed to a neutral label
  like `INSUFFICIENT_EMPIRICAL_DISCORDANCE` until such a rule exists.
- Full-pool-run vs. exclusions: the denominator, the paired-case intersection across models, and
  missingness handling are all undefined.
- The feasibility-stage ordering (run 14b-vs-4b first) must be pre-registered as
  operational-only — it cannot be allowed to change which models, thresholds, or whether the
  full grid runs, once results start coming in.
- "Driven by ≤2 repos" (per-repo concentration guard) is not operationalized — no statistic,
  threshold, or sign convention is given for what counts as repo-driven.
- "Unseen by policy tuning" (train-on-test guard) needs auditable provenance, not just an
  assertion.
- McNemar exact-vs-asymptotic test choice and alpha are both unspecified.

**claude-p:**
- The lexical stratum has only 9 cases, so a floor of 8 makes a lexical-stratum verdict
  near-structurally-unattainable. Recommend treating lexical as a preregistered *descriptive*
  sanity check rather than a graded inferential outcome, keeping conceptual (44 cases) as the
  primary inferential endpoint.
- Wall-clock/harness risk belongs in the open questions: 3 models × 53 cases × ~200s ≈ 9h of run
  time, but background Bash tasks in this environment die at ~20 minutes observed — this needs
  nohup+disown plus log-file monitoring, per existing repo memory on detaching long live runs.
- State per-stratum N (44 conceptual / 9 lexical) directly alongside whatever floors are chosen,
  so pre-doomed cells are visible to a reader before the run, not discovered after.

## Guardrail / convention flags

- **Convention (both agents):** AC1 must add the env-gated *positive* `/api/tags` served-tag
  membership check for all three tags, with field-default introspection applied where relevant.
- **Convention (codex):** integration-style ACs should explicitly require the
  `@pytest.mark.integration` marker (skip-not-fail), not just imply it.
- **Guardrail (codex, softer):** preflight should route through `gateway.assert_local` first and
  record that it did, per the sanctioned-seam rule — currently the ordering/recording isn't
  explicit in AC1.

## Recommended action

Before running `/speccraft:spec:plan`, edit spec.md to add:

- **(a) A frozen "Analysis contract" section**, pre-registering:
  - Per-stratum, per-pair discordance floors, stated as concrete numbers alongside the actual
    Ns (44 conceptual / 9 lexical).
  - McNemar test method (exact vs. asymptotic), alpha, and the multiplicity/correction posture
    across the up-to-6 tests.
  - Decoding determinism (greedy/temp-0/seed) or the replication plan for borderline pairs —
    pick one.
  - A typed outcome for intransitive/cyclic pairwise rankings.
  - A mathematical equivalence/minimum-effect rule for `PAIR_MODELS_TOO_CLOSE` (or rename it to
    a neutral `INSUFFICIENT_EMPIRICAL_DISCORDANCE` pending one).
  - Denominator, paired-case intersection, and missingness handling for the full-pool run.
  - A concrete statistic/threshold/sign convention for the per-repo concentration guard.
- **(b) Strengthen AC1** with the positive `/api/tags` served-tag check, `gateway.assert_local`
  called and recorded first, and the `@pytest.mark.integration` marker made explicit.
- **(c) Add decoding config to the durable-artifact schema in AC2**, so the determinism choice
  from (a) is actually captured per run.
- **(d) Fold the harness-detach discipline into OQ1** (or wherever open questions live), noting
  the ~9h expected wall clock and the nohup+disown/log-monitoring requirement.

---

Quorum is met (1/1 approve-with-comments) — status will move to `reviewed`. Given both
reviewers independently converged on the same core gap (a missing, concrete analysis contract),
it is strongly recommended to apply the consensus revisions above — either via a quick manual
edit or `/speccraft:spec:revise` — before `/speccraft:spec:plan`. The missing analysis contract
is exactly the kind of gap the arc's own "freeze the choosing rule before the numbers" discipline
exists to prevent.

---

# Round 2 (revision 1 → revision 2)

**Round 2 verdict summary:** codex = changes-requested, claude-p = approve-with-comments;
quorum met (1/1). Both agents confirmed **all five Round-1 consensus concerns RESOLVED**
(concrete floor of 8; determinism; positive `/api/tags` + assert-local-first + integration
marker; `INTRANSITIVE` outcome; exact McNemar + α=0.05 + Holm–Bonferroni), plus every
single-agent Round-1 item. The added specificity introduced a set of narrow contract-hygiene
issues — several are genuine internal contradictions in the frozen contract, whose whole
purpose is to leave no rule to interpretation. All were applied in **revision 2**:

1. **Denominator contradiction (BOTH agents — a real internal inconsistency).** `PAIR_MODELS_TOO_CLOSE`
   was defined as an absolute count `b + c < 8` but *described* as "rate ≤ 8/44 ≈ 0.18"; with
   eligible N as low as 36, `7/36 ≈ 0.194 > 0.182` — the two predicates disagree. **Fixed:** the
   floor is now stated as a pure ABSOLUTE count with no denominator in the predicate; the
   contradictory rate-margin language is removed.
2. **`TOO_CLOSE` overstated as "positive near-equivalence" (BOTH).** `b + c < 8` is not a powered
   equivalence result (no TOST/CI). **Fixed:** relabelled a DESCRIPTIVE low-observed-discordance
   finding (adequate coverage, too few disagreements to test direction); a real equivalence claim
   is noted as out-of-scope pending a pre-registered TOST.
3. **Reproducibility asserted, not verified (BOTH).** Batched local backends aren't guaranteed
   bit-reproducible at temp=0. **Fixed:** AC1 gains a reproducibility replay probe (double-run ≥3
   conceptual cases, assert identical buckets); a replay fail EXCLUDES the model; the claim is now
   "checked-and-stamped," not "checkable."
4. **Holm family-size ambiguity (BOTH).** **Fixed:** family `m = 3` FIXED (pre-registered, not
   data-dependent); adjusted-p and step-down rejection mechanics + `p ≤ α` convention + tie order
   pinned; AC3 fixture-pins the joint Holm over all three p-values incl. ties/boundaries.
5. **`UNDER_POWERED` vs `degraded-dominated` boundary undelineated (claude-p) + no frozen threshold
   (codex).** **Fixed:** they now PARTITION one coverage shortfall by cause — a shortfall is always
   `PAIR_UNDER_POWERED`, additionally reason-flagged `degraded-dominated` when > 50% of dropped
   cases were degrade-caused (a frozen threshold, not a post-run judgement).
6. **Outcome enum missing exclusion/halt/two-model cases (codex).** **Fixed:** added
   `INFRASTRUCTURE_HALTED` (< 2 models survive, or a named safety/infra stop) and
   `MODEL_EXCLUDED(<tag>,<reason>)` annotation; a two-model survivorship assembly rule (single
   pair → `PARTIAL`, never `RANKING`/`INTRANSITIVE`).
7. **Lexical "cannot clear the floor" is arithmetically false (claude-p) + AC4 "verdict" wording
   (codex).** **Fixed:** lexical is descriptive-only because it is underpowered even at maximal
   discordance AND model-independent by construction (0036), not because clearing 8 is impossible;
   AC4 now says lexical yields DESCRIPTIVE STATISTICS, not a verdict.

No guardrail or convention violations in either Round-2 review. With revision 2 applied, the
frozen Analysis contract now leaves no verdict-bearing rule to analysis-time interpretation —
the "freeze the choosing rule before the numbers" bar is met. Status → `reviewed`; ready for
`/speccraft:spec:plan`. (A third confirmatory review round is available on request but not
required — the Round-2 items were non-blocking per both agents and are now closed.)
