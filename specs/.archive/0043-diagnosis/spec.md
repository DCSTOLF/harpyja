---
id: "0043"
title: "diagnosis"
status: closed
started_at_sha: 9e971b3289c486bf6fda5b3186845e5e3203fc8c
created: 2026-07-12
---

# Spec 0043 — diagnosis

Submission-gap diagnosis — why do runs find the span but not submit it?

## Why

0042 changed the failure mode. With symbols adopted (0/28 → 24/31), 14b's marquee case shows symbols
delivering `separability_matrix` at `separable.py:66–102` EXACTLY as designed — and 14b then ran out of
wall-clock before submitting. RFWS failures shifted from "wrong span" to "found the right span, didn't
submit in time." That is a budget/latency problem, not a capability gap — and it is now the THIRD
independent signal pointing at wall-clock as the binding constraint:

- (a) 0040's finding that "per-case timeout sensitivity on heavy repos is binding, AHEAD of model
  capability";
- (b) the persistent heavy-repo model-unreachable degrades that SURVIVED 0040's clean isolated re-run
  (3/5 on the smallest model — an unexplained inversion);
- (c) 14b finding-but-not-submitting in 0042.

Conversions are being lost to the clock on spans the models have already located. This spec DIAGNOSES the
gap and fixes what it names — it is the cheapest path to conversions AND to the model spread the bake-off's
power needs (a capability fix, not a data fix).

Ref: 0040 (timeout-binding finding, 4b degrade inversion, ~14.7k reasoning chars/case for 14b/8b vs 3.9k
for 4b), 0042 (adoption + the found-but-unsubmitted trajectories), 0028/0034 (generation cap, reasoning
budget), 0041 (exclusive-endpoint gate — required for any clean re-measurement), 0021 (labeled-estimate /
evidence-provenance rule), 0033/0034/0038 (dual-seam artifact threading class).

### The evidence base (named honestly)

The committed `specs/.archive/{0040-pool,0042-adoption}/**/artifacts/*.json` are per-cell SUMMARIES —
no `model_turns`, no `per_turn`, no tool results. The full trajectories this spec's attribution and
detector depend on live in **gitignored, machine-local `eval_work/live_artifacts/{pilot_0040,adoption_0042}/`**
(verified present on the dev machine at spec time). They contain the persisted message history including
tool-role messages with stringified `CodeSpan` results, `per_turn` records, and terminal metadata. This is
exactly the "per-run diagnostics evaporate" class 0021 warns about, so:

- The attribution step MUST assert per-artifact existence FIRST (a missing trajectory is a typed
  `trajectory-missing` degrade for that cell, never a silent skip);
- The DERIVED attribution table is COMMITTED to the repo, pinned to the artifact filenames + content
  hashes it was computed from, so the finding survives after `eval_work` evaporates;
- Any quantity NOT recoverable from a persisted artifact is a LABELED ESTIMATE or an honest
  "needs instrumented re-run" — never presented as measured. Known limits, verified against the artifacts:
  **per-turn latency was never recorded** (the 0034 `per_turn` accumulator carries only
  `{reasoning_chars, completion_tokens, finish_reason}`; the only temporal fields are artifact-level);
  **case-level latency was ALSO never recorded** (verified at revision time: the run-ledger entries carry
  `{artifact, attempts, bucket, citations_submitted, citations_surviving, degrade, symbols_invocations,
  tools, verifier_artifact}` — no elapsed/duration field — and each verifier artifact carries exactly one
  `timestamp`), so case-level timing is ESTIMATE-GRADE ONLY, derivable as deltas between successive
  verifier-artifact timestamps within a sequential run block, labeled as such; and `per_turn` and
  `model_turns` can differ in length (a `finish_reason=length` final turn appears in `per_turn` but not in
  history) — attribution code must never zip the two lists positionally.

### Invariants

**INVARIANT (diagnose before fixing — attribute the clock):** the deliverable is first a MEASURED
attribution of where the per-case budget goes, computed from the persisted `eval_work` trajectories (no
new model compute): turns-to-first-symbols-hit, turns-after-hit-before-submit, reasoning-chars and
completion-tokens per turn, tool-call count, finish_reason, terminal cause, case-level timing (ESTIMATE-
GRADE: successive verifier-artifact timestamp deltas — see evidence-base limits), and cells lost to
degrades. ALL timing quantities, per-turn and per-case, are LABELED ESTIMATES (0021 rule) or deferred to
an instrumented re-run. Do NOT raise the timeout and re-run hoping — that would fix nothing and hide the
cause.

**INVARIANT (two-stage freeze, ordered):** (1) the attribution-to-lever decision table is frozen +
committed BEFORE any attribution numbers are computed or seen (the attribution is offline over persisted
artifacts — no live compute); (2) `PREREGISTERED_DIAGNOSIS_CONFIG_0043` — which names the SELECTED
lever(s) under test — is frozen + hashed + committed AFTER the table has mechanically selected the lever
from the attribution, but BEFORE any live re-measurement compute is spent. The config freeze being
post-attribution is by design, not a violation: the post-hoc-steering risk lives in lever CHOICE (closed
by stage 1) and in outcome predicates (closed by stage 2 preceding the live spend).

**INVARIANT (found-but-unsubmitted is a FIRST-CLASS typed outcome):** a run where the model's tool results
CONTAINED a gold-overlapping span but it never reached `submit_citations` must be distinguishable in the
artifact from a run that never found it. Today both are "empty"/RFWS — the same degrade-masks-outcome
class this project keeps killing. The detector is a PURE PROJECTION over the persisted trajectory that
reuses the ONE existing span-overlap oracle (the metrics machinery that already defines gold overlap for
locate buckets — one-oracle-reuse, never a second overlap definition). Tool results in persisted history
are STRINGIFIED `CodeSpan` reprs, so the detector is a string parse over tool-role messages; a tool
message the parser cannot decode yields the distinct typed outcome `detector-inconclusive` — NEVER
silently classified never-found (that would reintroduce, one level down, the exact collapse this
invariant exists to kill).

**INVARIANT (fix what the diagnosis names, not what's convenient — and freeze the choosing rule):**
candidate levers — wall-clock ceiling, turn cap, reasoning budget/effort, an earlier-submission prompt
nudge, cheaper navigation — are chosen by a FROZEN attribution-to-lever decision table committed BEFORE
the attribution numbers are seen (the 0023/0026/0039/0040/0042 discipline applied to lever selection),
not assumed and not steered post-hoc. A timeout raise that merely lets an inefficient run finish is a
last-resort, not the first move (it multiplies bake-off wall-clock across models × cases). Whatever lever
lands must preserve prior SUT pins: a prompt nudge rides `messages`, never `params` (the 0034/0038
`explorer_think=None ⇒ params == {max_tokens: 2048}` byte-frozen pin survives; the 0042 prompt↔surface
drift guard stays green); a wall-clock/turn-cap change is a deliberate, reviewed explorer SUT change,
never a silent side effect.

**INVARIANT (measure on a gated endpoint, behind a freeze):** any re-measurement runs behind 0041's
exclusivity gate with proof in every artifact, and only AFTER a `PREREGISTERED_DIAGNOSIS_CONFIG_0043` is
frozen + hashed + committed (model/case cells, SUT hash, endpoint gate proof version, the exact counted
buckets, the detector version, the lever(s) under test). Symbols-tool surface is the post-0042 fixed SUT
(`path=""` routing + `symbols-path-not-found` marker); the SUT hash pin makes pre/post comparability
explicit. The AC6 verdict is a TOTAL PURE function over the frozen config and the retained per-case
pairs; the bucket-movement predicate is BIDIRECTIONAL (conversions AND regressions, net surfaced) per
0042's lesson — a single noise flip must not type `CLOCK_BOUND_FIXED` unqualified.

## What

- **ATTRIBUTION** (from the persisted `eval_work/live_artifacts/{pilot_0040,adoption_0042}/` trajectories,
  existence-asserted per artifact, no new model compute): where does the budget go? Break each case into
  turns-to-locate vs turns-after-locate; reasoning chars + completion tokens per turn; tool-call count;
  case-level timing (estimate-grade, from verifier-artifact timestamp deltas — see evidence-base limits);
  how many cases contain a gold-overlapping span in a TOOL RESULT but
  never submit; how many die to wall-clock vs the 240s/300s HTTP timeout vs turn cap (from terminal
  cause/finish_reason). Per-turn timing only as a labeled estimate. The derived attribution table is
  committed, pinned to artifact filenames + hashes.
- **THE 4b INVERSION**: why does the SMALLEST model carry the most model-unreachable degrades on heavy
  repos? Candidate causes and the persisted evidence that discriminates them: more turns (turn counts per
  case), larger tool outputs (tool-result byte sizes per turn), prefill amplification (prompt growth
  across turns × 4b's 131k context), serving behavior under load (degrade timestamps vs block boundaries
  in the ledger). Name the cause the evidence supports, or conclude honestly "unattributable from
  persisted evidence — needs instrumented re-run" WITH the specific missing measurement named.
- **ARTIFACT**: add the found-but-unsubmitted fact to the VERIFIER/TRAJECTORY artifact (additive,
  schema-bumped). The new field threads through BOTH assembly seams — `build_trajectory_record` AND
  `run_verified_case`'s hand-assembled written artifact — pinned by a written-JSON test (the
  0033/0034/0038 dual-seam class is a standing checklist item). This makes the loss class countable in
  every future run.
- **FIX** (scoped by the frozen attribution-to-lever table): implement the lever(s) the table selects on
  the measured attribution; record the selected lever AS DATA in the outcome artifact (auditable, not
  prose); re-measure the 0042 pilot cells on the gated endpoint behind the frozen config; report the
  found-but-unsubmitted count BEFORE vs AFTER (SAME detector both sides) and net bucket movement.

## Acceptance criteria

([unit]=fakes; [integration]=live on the 0041-gated endpoint, skip-not-fail)

1. [unit/doc] Budget attribution computed from the persisted `eval_work` trajectories (existence asserted
   per artifact; `trajectory-missing` is a typed degrade, never a silent skip; no new model compute):
   per-case turns-to-locate, turns-after-locate, reasoning-chars/turn, completion-tokens/turn,
   tool-call count, finish_reason, terminal cause (wall-clock / HTTP timeout / turn cap / submitted), and
   case-level timing (ESTIMATE-GRADE: successive verifier-artifact timestamp deltas — no ledger latency
   field exists, verified). Reported per model. ALL timing, per-turn and per-case, appears ONLY as a
   labeled estimate (0021) or as an explicit "needs instrumented re-run" honest-out. Attribution code never zips
   `per_turn` and `model_turns` positionally (length skew is test-pinned). The derived attribution table
   is committed, pinned to source-artifact filenames + content hashes.
2. [unit] found-but-unsubmitted detector: a pure projection over a persisted trajectory that parses
   stringified `CodeSpan` reprs out of tool-role messages and tests gold overlap via the ONE existing
   span-overlap oracle (no new overlap definition). Typed outcomes — a TOTAL enum over the fixture
   matrix: `found-unsubmitted` (gold-overlapping span in a tool result, never in `submit_citations`),
   `submitted` (gold-overlapping span reached `submit_citations` and survived — the success case),
   `submitted-then-dropped` (reached `submit_citations` but normalization dropped it — routed through the
   EXISTING 0033 `citations_submitted`/`citations_surviving` counts, one-counter-reuse, never re-derived
   from history parsing; distinct from both `found-unsubmitted` and `never-found`), `never-found`,
   `detector-inconclusive` (unparseable tool message — never folded into never-found). Fixture matrix
   pinned, each row to its enum value: tool-result hit → `found-unsubmitted` / submitted hit → `submitted`
   / submitted-then-dropped → `submitted-then-dropped` / path-only (file-level, no gold line overlap —
   pinned as NOT a hit; the oracle's line-overlap predicate decides) → `never-found` / never-found →
   `never-found` / unparseable → `detector-inconclusive`. The artifact schema bump is additive and
   threads BOTH seams (`build_trajectory_record` + `run_verified_case`'s hand-assembled artifact),
   written-JSON test-pinned.
3. [unit/doc] The 4b heavy-repo degrade inversion is ATTRIBUTED from the persisted trajectories using the
   named discriminating evidence (turn counts vs tool-result sizes vs prompt-growth/prefill vs
   ledger-timing), OR concluded "unattributable from persisted evidence — needs instrumented re-run" with
   the specific missing measurement named (falsifiable, not a default escape).
4. [unit] The attribution-to-lever decision table is FROZEN + committed BEFORE the attribution numbers
   are computed or seen (stage 1 of the two-stage freeze — the attribution is offline, no live compute;
   e.g. after-locate turns high → submit-early prompt nudge; per-turn token cost
   high → cheaper navigation/output clamp; hard wall-clock expiry with low post-hit dawdle → bounded
   ceiling raise). The chosen lever(s) are implemented per the table, recorded as data in the outcome
   artifact; a wall-clock raise alone requires an explicit recorded rationale for why cheaper levers were
   insufficient. Whatever lands preserves the 0034/0038 `params == {max_tokens: 2048}` byte-frozen pin
   (prompt nudges ride `messages`; drift guard stays green); any ceiling/cap change is a named, deliberate
   SUT change.
5. [integration] Re-measure the 0042 pilot cells on the gated endpoint (0041 exclusivity proof per
   artifact) behind a frozen + hashed + committed `PREREGISTERED_DIAGNOSIS_CONFIG_0043` (cells, SUT hash,
   gate proof version, counted buckets, detector version, lever(s) under test, and the frozen
   minimum-covered-subset floor `MIN_COVERED_BEFORE_CELLS` — the 0042 `MIN_RFWS_DENOMINATOR` pattern;
   stage 2 of the two-stage freeze, after lever selection, before any live spend): report the
   found-but-unsubmitted count BEFORE vs AFTER using the IDENTICAL detector on both sides (BEFORE is
   computable only for cells whose full trajectory survived in `eval_work` — the covered subset is named
   in the artifact), the `detector-inconclusive` count PER SIDE (a large BEFORE/AFTER inconclusive
   asymmetry is a named caveat in the outcome — identical detector prevents definition drift, not
   input-distribution drift), plus BIDIRECTIONAL bucket movement (conversions AND regressions, net
   surfaced).
6. [doc] Typed outcome, a total pure function over the frozen config and retained per-case pairs:
   CLOCK_BOUND_FIXED (found-but-unsubmitted drops, net conversions positive, covered BEFORE subset ≥
   `MIN_COVERED_BEFORE_CELLS`) / CLOCK_BOUND_UNDER_POWERED (covered subset below the frozen floor — the
   qualification is a returned enum member, never prose) / CLOCK_BOUND_PERSISTS (fix insufficient — name
   the residual) / NOT_CLOCK_BOUND (the attribution refutes the hypothesis — the losses are elsewhere;
   say so and redirect). Pilot-N signal, not an inferential claim.

## Out of scope

- Pool enlargement (still needed for a POWERED claim — this is a capability fix, not a data fix)
- The bake-off
- The 0039 thinking A/B
- The semantic/call-graph tier
- Any model swap
- Symbols-tool surface changes beyond the already-shipped 0042 fixes

## Open questions

1. Cheapest effective lever, decided by the frozen table over the measured attribution: (a) prompt nudge
   to submit as soon as a confident span is in hand (cheapest, no budget cost), (b) turn-cap/wall-clock
   raise (costly — multiplies bake-off wall-clock), (c) reasoning-effort reduction to buy action tokens
   (0038's knob — but reasoning may be what FINDS the span), (d) cheaper navigation (fewer/larger tool
   results). The table commits the ranking rule before the numbers are seen; (a) is the presumptive
   first-rank if the data shows the model dawdles AFTER locating.
2. Does raising wall-clock merely let inefficient runs finish (masking the inefficiency and inflating
   bake-off cost across models × cases), or is the current 240s genuinely too tight for a 14b at ~3.6k
   completion tokens/case? The attribution must distinguish these before any raise — noting per-turn
   timing is estimate-grade only (see evidence-base limits), so this discrimination may itself require
   the instrumented re-run.
3. ~~Is found-but-unsubmitted detectable from EXISTING committed trajectories?~~ ANSWERED during round-1
   review (verified against the artifacts): YES from the persisted machine-local
   `eval_work/live_artifacts/{pilot_0040,adoption_0042}/` trajectories (tool-role messages carry full
   stringified `CodeSpan` results), so 0040/0042 are retroactively countable on this machine — but NOT
   from the committed `.archive` summaries, and only for cells whose full trajectory survived. Hence the
   evidence-base section: existence-assert first, commit the derived table pinned to artifact hashes.
