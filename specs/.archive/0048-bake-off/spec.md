---
id: "0048"
title: "bake-off"
status: closed
created: 2026-07-14
authors: [claude]
packages: []
related-specs: [0047, 0040, 0036, 0031, 0032, 0033, 0034, 0035, 0041, 0043, 0044, 0045, 0046]
---

# Spec 0048 — bake-off

## Why

Three-model bake-off — the powered ranking, split by reachability.

0040's three-model bake-off typed `INSUFFICIENT_PILOT_EVIDENCE` on all three pairs
(ceilings 6/8/3 vs floor 8, coverage 7/4/5 vs minimum 8). 0047 enlarged the pool
19→53 (conceptual 15→44); all five downstream questions now type `POWERED` on the
theoretical ceiling. This is the ranking the entire post-RCA arc has been clearing the
runway for: **qwen3:14b vs qwen3:8b vs qwen3.5:4b** (three sizes, two generations), on a
trustworthy instrument (0031–0035 verifier), a gated endpoint (0041), a
coherence-preflighted model set, and a pool with variance headroom. The 8b-vs-4b cut
(newer-smaller vs older-larger) is the comparison Harpyja's ~16B memory box most needs
answered.

Ref: 0040 (the INSUFFICIENT stop, preflight discipline, per-pair machinery), 0047
(enlarged pool, reachability tags, ≤8/repo, per-repo-distribution mandate), 0036
(reachability/concept-vs-patch axes), 0031–0035 (verifier), 0041 (gated endpoint),
0043–0046 (found-but-unsubmitted + the four/five-sided predicate — bucket-classing that
applies here too).

**INVARIANT (measurement, not construction):** runs the EXISTING instrument across the
enlarged pool. No change to tiers/gate/explorer/verifier. Any code change is a surfaced
defect with its regression test. Deliverable is a per-pair ranking + the reachability
split, not a tuning.

**INVARIANT (per-PAIR, empirical discordance — the nested-sets question 0047 deferred):**
report signal-bearing discordant pairs per contrast (14b-8b, 14b-4b, 8b-4b) from PER-CASE
cross-model buckets via `is_signal_discordant` — NOT marginal locate-counts (the 0040
counts-vs-pairs lesson). A pair under-powered because the models perform IDENTICALLY
(concordant, few disagreements) is `PAIR_MODELS_TOO_CLOSE` — a distinct, reportable
finding from too-few-cases. This is where 0047's theoretical-POWERED meets reality: the
ceiling clears the floor; whether actual discordance does is what this spec measures.

**INVARIANT (reachability split is first-class — the RETRIEVAL_FUNDAMENTAL guard):** every
result reported SPLIT by the 0036/0047 reachability tag (lexical vs conceptual). The
headline is per-pair AND per-stratum, never a whole-pool average. 0047 is
conceptual-MAJORITY (44/9); a pooled number would let conceptual cases (which defeat
lexical navigation independent of model) average into "no model is better." The
conceptual stratum is the real question; the lexical stratum is the sanity floor.

**INVARIANT (per-repo distribution reported — the ≤8/repo hedge, now measured):** 0047
relaxed ≤3→≤8/repo, accepting per-repo overfit risk on the condition it be MEASURED.
Report per-repo result distribution; flag any pair whose ranking is driven by one or two
repos (a repo-specific artifact masquerading as a model difference).

**INVARIANT (arms parity + preflight):** `explorer_think=None` for all three (no thinking
confound — that's 0039's question). Each model coherence + tool-calling preflighted on
THIS /v1 (the 16B-gibberish lesson) before its numbers count; a model failing preflight
is EXCLUDED with a recorded reason, not scored zero.

**INVARIANT (reliability-gated + gated endpoint):** N_FLOOR / degraded-dominated guards
hold; exclusivity proof per artifact (0041); SUT hash pinned; a degraded-dominated pair
withholds its ranking as a finding. The heavy-repo timeout degrade class (last seen clean
on the gated endpoint in 0043) is watched — if it recurs at scale it caps coverage, not
capability.

## What

- Run all three models × the enlarged pool through the verifier on the gated endpoint; per
  model+case durable artifact (bucket, tools incl. symbols-adoption, reasoning tokens,
  submitted/surviving, found-but-unsubmitted, model identity, `serving_transport`,
  exclusivity proof).
- Per pair: signal-bearing discordant count on the CONCEPTUAL stratum vs floor; McNemar
  where powered; typed per-pair verdict.
- Split every number by reachability; report per-repo distribution; report
  symbols-adoption per model (0042's open thread at scale).
- Assemble the three pairwise verdicts into an overall ranking (or a typed null where a
  pair is TOO_CLOSE / under-powered / degraded-dominated / intransitive).

## Analysis contract (FROZEN before any model runs)

This section pre-registers every decision rule that turns artifacts into a verdict —
committed by path+sha before the first live call, re-verified by the driver at every
invocation (the two-stage-freeze discipline of 0045; the "freeze the choosing rule before
the numbers" lesson of 0044–0046). No rule here may be edited once the run has produced a
single durable artifact; a needed change voids the run and is re-frozen, not patched
mid-flight.

**Strata and their N (going IN, before attrition).** Conceptual = 44 cases (the PRIMARY,
inferential endpoint). Lexical = 9 cases (DESCRIPTIVE ONLY — it is reported as raw
per-model found/not-found DESCRIPTIVE STATISTICS and never carries an inferential pairwise
verdict). Two reasons it is descriptive-only, not an arithmetic impossibility: (a) it is
underpowered even at maximal discordance — while `b + c = 8` or `9` of 9 could numerically
clear the floor of 8, a single-repo-sparse 9-case stratum has no room for the leave-two-out
concentration guard and no multiplicity headroom; (b) lexical reachability is
model-INDEPENDENT by construction (0036 — a lexically-reachable target is found by
navigation regardless of model), so a lexical difference is an instrument artifact, not a
capability signal. No whole-pool average is ever the headline.

**Decoding determinism — CHECKED, not asserted.** All three models run GREEDY:
`temperature=0`, `top_p=1`, `seed` pinned to a single frozen value, recorded in the frozen
config AND stamped into every durable artifact (beside model identity and
`serving_transport`). Greedy decoding removes SAMPLING variance in principle, but a batched
local backend (Ollama / llama.cpp with continuous batching) is not guaranteed
bit-reproducible at `temperature=0` — so determinism is VERIFIED, not assumed: a
**reproducibility preflight** double-runs a fixed handful (≥3) of conceptual cases per
model through the FULL explorer loop and asserts identical per-case buckets across the two
runs. A model that fails the replay probe is EXCLUDED with a recorded reason (its estimator
would be single-draw stochastic, re-opening the 0046 multi-draw problem the determinism
argument exists to close), as is any model whose backend cannot honor `temperature=0`. Only
after a model passes replay is its single-draw discordance trusted; the recorded decoding
config plus the passed replay is what makes the reproducibility claim CHECKED-and-stamped,
not merely checkable.

**Paired denominator + missingness.** Each pair's analysis is COMPLETE-CASE PAIRED: a case
enters a pair's paired table only if BOTH models produced a non-degraded, non-excluded
result on it. A case degraded/excluded for either model is dropped from THAT pair's table
and counted in a recorded per-pair missingness tally (the degraded-dominated guard reads
this). Report eligible paired N per pair, per stratum.

**Coverage floor → `PAIR_UNDER_POWERED`, and its degraded-dominated partition.** A pair
whose eligible paired conceptual N falls below **36** (≈80% of 44) is typed
`PAIR_UNDER_POWERED` (coverage) and withholds its ranking. `PAIR_UNDER_POWERED` and
`degraded-dominated` are not separate competing labels — they PARTITION the same coverage
shortfall by CAUSE: an under-powered pair is additionally reason-flagged
`degraded-dominated` when **> 50%** of its dropped conceptual cases were dropped for a
DEGRADE (model-unreachable / generation-truncated / heavy-repo-timeout — the 0027/0028
typed causes), versus honest-empty or preflight-exclusion. So a coverage shortfall is
always `PAIR_UNDER_POWERED`; the degraded-dominated flag says whether the SUT (not the
models) caused it — the capping-coverage-vs-capability distinction (AC2), now with a frozen
threshold rather than a post-run judgement.

**Discordance floor = 8 (conceptual stratum), an ABSOLUTE count.** Signal-bearing discordant
pairs = the McNemar off-diagonal `b + c` (cases where exactly one model in the pair found
it), computed from PER-CASE cross-model buckets via `is_signal_discordant` (NOT marginal
locate-counts — the 0040 counts-vs-pairs lesson). The floor of 8 is an ABSOLUTE count
carried forward verbatim from 0040 — NOT a rate; no denominator enters the predicate, so it
is well-defined for every eligible N ≥ 36. Given adequate coverage (N ≥ 36):
- `b + c < 8` → `PAIR_MODELS_TOO_CLOSE`: a DESCRIPTIVE finding of low observed discordance
  (the models rarely disagree), with adequate coverage. This is NOT a powered equivalence
  result — it asserts no TOST/CI margin — it is the honest "too few disagreements to test
  direction" outcome, reportable and distinct from `PAIR_UNDER_POWERED` (too few eligible
  cases) and from `PAIR_NO_DIFFERENCE` (ample disagreement, no directional winner). If a
  future powered equivalence claim is wanted, it needs a pre-registered TOST — out of scope
  here.
- `b + c ≥ 8` → run McNemar (below). The disagreement is ample; the test decides direction.

**Significance test + multiplicity.** Two-sided **exact (binomial) McNemar** — exact, not
the asymptotic χ² approximation, because the discordant counts are small. **α = 0.05**,
rejection at **adjusted `p ≤ α`** (the `≤` convention). Multiplicity by **Holm–Bonferroni
with family size `m = 3` FIXED** — the family is the three conceptual pairwise comparisons
as PRE-REGISTERED, not the number that happen to reach McNemar; a pair typed `TOO_CLOSE` or
`UNDER_POWERED` contributes no p-value but does NOT shrink `m` (fixing `m` before the run is
the anti-steering guard — a data-dependent family size would let coverage outcomes loosen
the surviving tests). Operationally: order the raw two-sided McNemar p-values of the pairs
that reached the test ascending `p(1) ≤ p(2) ≤ …`; the Holm step-down rejects `p(i)` iff
`p(j) ≤ α / (m − j + 1)` for all `j ≤ i`; the reported adjusted p-value is
`min(1, max over j≤i of (m − j + 1)·p(j))`. Ties broken by a fixed pair order (14b-8b,
14b-4b, 8b-4b). The lexical stratum is descriptive and NOT in the family. A pair whose Holm
step-down REJECTS → `PAIR_SEPARATES` (winner = the model with the larger exclusive-find
count, i.e. the sign of `b − c`); a pair that reached the test but is NOT rejected →
`PAIR_NO_DIFFERENCE` (ample disagreement, no directional winner — distinct from
`TOO_CLOSE`).

**Per-repo concentration (leave-one-repo-out).** For any pair typed `PAIR_SEPARATES`,
recompute the verdict dropping each repo in turn (and each pair of repos). If removing any
single repo — or any two repos — flips the McNemar direction OR drops `b + c` below the
floor of 8, the pair is additionally flagged `REPO_CONCENTRATED` (its ranking is reported
but carries the flag; the ≤8/repo overfit hedge of 0047, now operationalized). Report the
per-repo distribution of `b − c` alongside.

**Assembling the pairwise verdicts.** First, survivorship gates the assembly:
- **< 2 models survive preflight/replay** → `INFRASTRUCTURE_HALTED` (no bake-off is
  possible); the excluded models and reasons are named. This is also the type of a NAMED
  safety/infrastructure early stop (below).
- **exactly 2 models survive** → the single surviving pair is run and reported, and the
  overall outcome is `PARTIAL` with `MODEL_EXCLUDED(<tag>, <reason>)` naming the dropped
  model — a two-model bake-off never types `RANKING`/`INTRANSITIVE` (those need all three
  edges).

With all three models surviving, only `PAIR_SEPARATES` verdicts contribute a directional
edge:
- edges over {14b, 8b, 4b} form a total order → `RANKING`;
- edges form a cycle (e.g. 14b≻8b, 8b≻4b, 4b≻14b) → **`INTRANSITIVE`** (a first-class typed
  outcome, not a coerced ranking);
- some pairs separate and others are `TOO_CLOSE`/`UNDER_POWERED` (with its
  degraded-dominated flag)/`NO_DIFFERENCE` → `PARTIAL` (naming each);
- NO pair separates on the conceptual stratum → `NO_SEPARATION` (the model-homogeneity
  finding, pre-registered as valid — points at the semantic tier / beyond-Verified data,
  NOT more tuning).

The full typed-outcome enum is therefore: `RANKING` / `INTRANSITIVE` / `PARTIAL` /
`NO_SEPARATION` / `INFRASTRUCTURE_HALTED`, with `MODEL_EXCLUDED(<tag>, <reason>)` as a
per-model annotation carried into `PARTIAL`/`INFRASTRUCTURE_HALTED`.

**Feasibility stage is operational-only.** The staged 14b-4b-first run (OQ1) is a
throughput/plumbing check ONLY: it may NOT change models, tags, thresholds, the decoding
config, prompts, the pool, or whether the full grid runs. The single sanctioned early stop
is a NAMED safety/infrastructure halt (e.g. the heavy-repo timeout degrade class recurring
past the degraded-dominated guard), recorded as such — never an outcome-dependent stop.

**Provenance / no train-on-test.** Every artifact records the 0047 pool sha256 (provenance
chain head `385107934f61`) and the attestation that this pool is unseen by any policy
tuning in the arc; the exclusivity proof (0041) and the pinned SUT hash are recorded per
artifact, so the powered claim is auditable end-to-end.

## Acceptance criteria

1. **[integration]** All three served tags (`qwen3:14b`, `qwen3:8b`, `qwen3.5:4b`) pass a
   SETUP-time preflight that (a) routes through `gateway.assert_local` FIRST (the probe's
   own `/api/tags` read is the same loopback-gated egress class as the calls it checks — no
   second outbound path), (b) does a POSITIVE `/api/tags` served-membership check per tag
   (env-gated, skip-not-fail — cannot pass trivially when the endpoint is down), then (c)
   checks coherence + /v1 tool-calling, then (d) a REPRODUCIBILITY REPLAY probe: double-runs
   ≥3 fixed conceptual cases through the full explorer loop and asserts identical per-case
   buckets across the two runs (a batched local backend is not guaranteed bit-reproducible
   at `temperature=0`; a replay fail means the estimator is single-draw stochastic). A fail
   on any check EXCLUDES that model with a recorded reason (not scored zero), naming the
   missing dependency. The three tags are pinned in the frozen config and asserted present
   against the resolved served set — the `qwen3:14b` arc-verified / `qwen3:8b` +
   `qwen3.5:4b` un-provenanced gap is closed here, before their numbers count. Marked
   `@pytest.mark.integration`.
2. **[integration]** Full pool run to completion; per model+case verifier-clean durable
   artifact carrying bucket, tools (incl. symbols-adoption), reasoning tokens,
   submitted/surviving, found-but-unsubmitted, model identity, `serving_transport`, the
   **frozen decoding config (`temperature=0`, `top_p=1`, pinned `seed`)**, the 0047 pool
   sha256, the pinned SUT hash, and the exclusivity proof (0041). Heavy-repo degrade rate
   recorded (capping-coverage vs capability distinguished per the degraded-dominated guard).
   Marked `@pytest.mark.integration`.
3. **[unit]** Per-pair discordance = the McNemar off-diagonal `b + c` from PER-CASE
   cross-model buckets via `is_signal_discordant` (not marginal counts). The four
   coverage/closeness outcomes are fixture-pinned and mutually distinct on ABSOLUTE-count
   predicates (no rate/denominator enters — the floor is an absolute 8): `PAIR_UNDER_POWERED`
   (eligible paired conceptual N < 36; reason-flagged `degraded-dominated` when > 50% of
   dropped cases were degrade-caused) vs `PAIR_MODELS_TOO_CLOSE` (N ≥ 36 and `b + c < 8` — a
   descriptive low-discordance finding, NOT a powered equivalence claim) vs
   `PAIR_NO_DIFFERENCE` (`b + c ≥ 8` but Holm step-down does not reject) vs `PAIR_SEPARATES`
   (`b + c ≥ 8` and Holm step-down rejects). Exact-binomial McNemar, α = 0.05 (`p ≤ α`),
   Holm–Bonferroni with fixed family `m = 3` — all fixture-pinned, including the Holm
   step-down over all three pairwise p-values with ties and boundary values.
4. **[integration]** Reachability split first-class; NO whole-pool average as the headline.
   The **conceptual stratum (N=44)** carries the per-pair inferential VERDICTS (the primary
   read); the **lexical stratum (N=9)** yields per-model DESCRIPTIVE STATISTICS only (raw
   found/not-found counts, never an inferential pairwise verdict — underpowered even at
   maximal discordance, and model-independent by construction).
5. **[integration]** Per-repo distribution of `b − c` reported; every `PAIR_SEPARATES`
   verdict runs the leave-one-repo-out (and leave-two-out) check and is flagged
   `REPO_CONCENTRATED` if dropping ≤2 repos flips the direction or drops `b + c` below the
   floor (the ≤8/repo overfit guard, now operationalized).
6. **[integration]** Symbols-adoption rate per model reported (0042 at scale);
   found-but-unsubmitted per model (0043's class — is it material across three models?).
7. **[doc]** Typed outcome per the Analysis contract's assembly rule, from the full enum
   `RANKING` / `INTRANSITIVE` / `PARTIAL` / `NO_SEPARATION` / `INFRASTRUCTURE_HALTED` (with
   `MODEL_EXCLUDED(<tag>,<reason>)` annotations): `RANKING` (three edges a total order) /
   `INTRANSITIVE` (three edges a cycle — never coerced into a ranking) / `PARTIAL` (some
   pairs separate, others named `TOO_CLOSE` / `UNDER_POWERED`+degraded-dominated /
   `NO_DIFFERENCE`, or only two models survived) / `NO_SEPARATION` (no conceptual-stratum
   pair separates — itself a finding: the blocker is model homogeneity / benchmark breadth,
   pointing at the semantic tier or beyond-Verified data, NOT more tuning) /
   `INFRASTRUCTURE_HALTED` (< 2 models survive, or a named safety/infra stop). Powered
   claim, honestly N'd per pair/stratum; the train-on-test confound does NOT apply (this
   pool is unseen by policy tuning — provenance recorded per AC2).

_Legend: [unit]=fakes; [integration]=live on the 0041-gated endpoint, skip-not-fail,
`@pytest.mark.integration`._

## Out of scope

- The reactive-submit + confirm-before-submit knob (NEXT spec — this bake-off is
  `explorer_think=None`, default policy; it establishes the powered baseline the knob is
  then measured against).
- The 0039 thinking A/B (now powered, separate run).
- Tool-result compression (parked).
- A new tier before Deep (a candidate the NO_SEPARATION branch would point at, not built
  here).
- Any model swap beyond the three.

## Open questions

1. **Wall-clock + detach discipline:** 3 models × 53 cases × ~200s (reasoning-on-by-default
   is on for these tags — 0034) is ~9h. Stage it: preflight all three → run the widest-gap
   pair (14b-4b, most expected discordance) first as an OPERATIONAL-ONLY feasibility check
   (per the Analysis contract: no threshold/model/grid changes) → then the full grid. The
   run MUST be launched detached (`nohup … & disown`) with log monitoring, NOT a harness
   background Bash task — those die at ~20 min in this environment (repo memory:
   detach-long-live-runs). Confirm the resumable ledger (0044/0047 posture) spans the full
   ~9h run so a mid-run interruption resumes rather than restarts.
2. **The nested-sets outcome:** if the conceptual stratum comes back `NO_SEPARATION` (all
   three fail the same conceptual cases), that is the homogeneity finding 0040 foreshadowed
   — pre-register it as a valid, important outcome (points at semantic-nav capability, not
   tuning), so it isn't misread as "the bake-off failed."
3. Does symbols-adoption (0042) hold at 77% across the enlarged, conceptual-heavy pool, or
   was the pilot rate inflated by the small sample? First scaled read of the tool's real
   adoption.
