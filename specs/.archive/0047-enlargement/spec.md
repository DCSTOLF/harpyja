---
id: "0047"
title: "enlargement"
status: closed
created: 2026-07-14
authors: [claude]
packages: ["harpyja/eval"]
related-specs: ["0046", "0044", "0043", "0042", "0041", "0040", "0039", "0036"]
---

# Spec 0047 — enlargement

Pool enlargement — the audited convert step (unblocks everything).

## Why

0046's baseline arm typed `BASELINE_DRIFT_STOP`: the same gate on the same 33
cells drew NET 0 where 0044 drew +2 (conv 3/reg 1 → conv 3/reg 3 — a
2-regression swing well inside qwen3 run-to-run variance). The finding is **not**
"the lever traded" — it is that **the instrument can no longer resolve whether a
lever traded at all**.

Four submission-policy specs (0043–0046) have been fitting levers to a metric
whose noise is comparable to the effect sizes being measured, on eleven cells per
model, with a compounding train-on-test confound (flask-5014, django-14315::8b,
pytest-10081::14b have become a de facto test set). Every downstream question is
blocked on the same root cause:

- 0039's thinking A/B stopped `UNDER_POWERED`.
- 0040's three-model bake-off typed `INSUFFICIENT_PILOT_EVIDENCE` on all three
  pairs (ceilings 6/8/3 vs floor 8; coverage 7/4/5 vs minimum 8).

Pool size is the single shared blocker. This spec enlarges the blind-clean pool
past 19.

Ref: 0036 (eval-set instrument, two-model blind protocol, sha256-pinned
patch-derived labels, reachability tags, floor=12/min-discordant=8; the exhausted
50-case raw pool: 36 attempts → 19 blind-clean, 17 leaky-dropped, 14
blind-ineligible); 0039/0040 (the power stops); 0046 (the variance finding); 0041
(gated endpoint).

## What

**Invariants (carried from the brief; each is a constraint on HOW enlargement is
done, not a re-derived target):**

- **Audited convert step — never a re-derived target.** The raw pool is enlarged
  by an AUDITED convert of NEW SWE-bench cases (the future step 0036 named),
  producing sha256-pinned patch-derived labels. Existing committed labels are
  reused VERBATIM — never re-transcribed, never re-derived. Provenance chain
  unbroken.
- **0036's blind protocol reused, not reinvented.** Terse queries authored from
  issue INTENT with the gold span withheld, via the two-author blind protocol
  (author model ≠ verifier model, separate invocation); provenance recorded per
  case; leaky queries dropped WITH THE COUNT RECORDED. 0036 proved this
  necessary: 14 cases were blind-INELIGIBLE because the issue text names the gold
  path — expect a similar attrition rate and size the raw convert accordingly.
- **Reachability + concept-vs-patch tags mandatory.** Every new case carries the
  lexical-reachability tag (is gold findable by the query's own vocabulary?) and
  the concept-vs-patch tag. 0036's natural sample was conceptual-MAJORITY (15/19)
  — the axis that predicts outcome more than model quality does. Without these,
  the bake-off re-runs the `RETRIEVAL_FUNDAMENTAL` confound.
- **Size to the DOWNSTREAM floors, with headroom (the 0040 lesson).** 0040 had
  ZERO coverage slack (8 conceptual vs minimum 8: any single degrade forced
  INSUFFICIENT). Target N is derived from the binding consumer (per-pair bake-off
  discordance ≥8 on the CONCEPTUAL stratum, and a variance-tolerant baseline for
  policy re-measurement), PLUS explicit headroom for degrades and blind-attrition.
  State the arithmetic; do not pick a round number.
- **Nested-sets caveat — enlargement is necessary, not automatically sufficient.**
  0040 found the models' located sets are nearly NESTED (4b ⊂ 14b; 8b-conceptual
  = ∅) — they fail the SAME cases, so added cases may add concordant cells rather
  than discordant ones. Enlargement raises coverage and reduces variance; whether
  it raises DISCORDANCE is an empirical question this spec must re-check (re-run
  the 0040 per-pair ceiling arithmetic on the enlarged pool) — not assume.

**Work:**

- **AUDITED CONVERT:** enlarge the raw SWE-bench pool beyond the exhausted 50;
  sha256-pin the new patch-derived labels; provenance.json extended,
  integrity-verified.
- **BLIND AUTHORING:** terse queries via 0036's two-model protocol; record
  attrition (leaky-dropped, blind-ineligible) as data.
- **TAG:** reachability + concept-vs-patch per case; report the resulting stratum
  distribution.
- **RE-CHECK POWER:** re-run 0040's per-pair ceiling arithmetic AND 0039's A/B
  feasibility on the enlarged pool. Report which downstream questions are now
  powered.

## Acceptance criteria

Scope key: `[unit]`=fakes; `[integration]`=authoring/convert, no live model runs
required; `[doc]`=findings written from committed artifacts. No live SUT/model run
anywhere in this spec; the audited convert + blind authoring are authoring-time,
offline-of-the-SUT (they never touch the runtime Model Gateway / air-gap seam).

1. **[unit]** New labels sha256-pinned + provenance-chained; existing 19 reused
   VERBATIM (byte-identical, drift-guard test). No re-derivation.
2. **[unit]** Blind-authoring provenance per new case (author/verifier model,
   input hashes, verdict); leaky and blind-ineligible counts recorded, not
   silently dropped.
3. **[unit]** Every case carries reachability + concept-vs-patch tags; a case
   missing either is rejected loudly. Stratum distribution reported (lexical vs
   conceptual).
4. **[unit]** Target-N arithmetic stated and pinned: derived from the binding
   downstream floor (per-pair conceptual discordance ≥8) + headroom for degrades
   + blind-attrition. Not a round number.
5. **[unit]** Re-run 0040's per-pair ceiling + 0039's A/B feasibility on the
   enlarged pool; report which questions are NOW powered (typed per question, per
   pair).
6. **[doc]** The nested-sets re-check: did enlargement add DISCORDANT cells or
   merely concordant ones? If the ceilings still fail, say so — enlargement is
   then insufficient and the blocker is model homogeneity, not data volume (a
   different finding, and a different next spec).

## Out of scope

- The bake-off (this unblocks it).
- The 0039 thinking A/B (unblocked, not run).
- Re-running the 0046 policy arms (unblocked, not run).
- Tool-result compression (parked).
- A new tier before Deep (parked).
- Any model/harness/SUT change.

## Open questions

1. **How many raw cases to convert?** Work backward: 0036 got 19 blind-clean from
   50 raw (38% yield, 15 conceptual). To hit (say) 40 conceptual cases with
   headroom, that's ~130+ raw. Confirm the yield assumption against the new
   convert's actual attrition — and re-check whether the 38% holds on a different
   slice of SWE-bench.
2. **Multi-draw baseline (0046's named follow-up):** does the enlarged pool alone
   tame the variance, or does the policy re-measurement ALSO need median-of-2–3
   draws? Compute the expected variance at the new N before committing to a
   single-draw baseline again.
3. **Same repos or new repos?** Are new cases drawn from the SAME repos (deepens
   per-repo coverage, risks repo-specific overfit) or NEW repos (broadens, but
   each new repo costs provisioning + heavy-repo timeout risk)? 0036 capped at
   ≤3/repo across 11 repos — preserve that discipline or justify a change.

   **RESOLVED (2026-07-14, forced by convert data):** SWE-bench_Verified has only
   **12 repos**, so 0036's `≤3/repo` hard-ceilings new raw at 12×3=36 — the convert
   confirmed it, discarding **420** eligible cases and yielding just 30 (below the
   96-raw need). The two invariants (`≤3/repo` and *size-to-40-conceptual*) are
   mutually incompatible on a 12-repo benchmark. **Decision: relax to `≤8/repo`**
   (same repos, deeper) — the *minimal* relaxation that makes the target attainable
   (12×8=96 = the derived raw need). The `EnlargementConfig` was **re-frozen** with
   `max_per_repo=8`, `raw_convert_target=96` (crediting the existing 15 conceptual),
   and `max_per_repo_derivation` recording the justification; new config hash
   `819af2e6…`. Per-repo overfit risk is the accepted cost; broadening to new repos /
   a different benchmark is deferred (it is the nested-sets/homogeneity axis, a
   distinct next spec).
