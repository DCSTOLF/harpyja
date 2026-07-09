---
spec: "0026"
title: "eval — terse-query eval set (ranking instrument for the model bake-off)"
reviewers: [codex, claude-p]
quorum: 1
verdict: reviewed
generated: 2026-07-06
rounds: 4
---

# Cross-model review — 0026 (eval)

Three rounds. Each round returned convergent, code-grounded findings; the spec was
amended after each and every round-N blocker was confirmed resolved in round N+1
(never re-flagged). **Round 3 met quorum** — claude-p `approve-with-comments`, codex
`changes-requested` on two *convergent* must-fix-before-plan items, both resolved in
**revision 4**. Status → **reviewed**.

The direction was endorsed by both reviewers from round 1 and never wavered: keep the
free sha256-pinned patch-derived spans, replace SWE-bench's wrong-distribution
verbose query with a representative terse one, gate full authoring on a pre-registered
pilot. The rounds hardened *how* that is built and *what it honestly claims*.

---

## Round 1 (initial draft) — both changes-requested

Convergent: AC1 "human-confirmed" unbacked; AC2/AC4 leakage-guard had no validated
schema home (EvalCase = 5 fields, loud loader ignores extras); AC3 cited no number;
OQ1 unsettled; the token flag necessary-but-insufficient for a human author; AC6 a
toothless [doc]; base_commit/schema drift.
**Revision 2:** AC1→"mechanically-patch-derived"; AC2 two-layered (token flag +
blind protocol); additive validated EvalCase fields + extended loader; AC3 cited
`min_n=12` / `MIN_DISCORDANT_PAIRS=8`; AC7 pinned `run_metadata` caveat; OQ1–3
resolved.

## Round 2 (revision 2) — both changes-requested

- **codex (CRITICAL):** AC1 was UNSATISFIABLE — `swebench_verified.raw.jsonl` has no
  `patch` field (all 50 rows carry only `case_id/query/repo/expected_spans/
  classification/base_commit/language/new_file_only`); patches were consumed at the
  network `convert` stage and discarded. Re-derivation is impossible offline. Also:
  AC2 overstated what a [unit] test can enforce (can't prove a human was blind).
- **claude-p:** the blind guard is an unverifiable human attestation dressed as
  structural enforcement; the "or the oracle" verifier collapses it to the token
  flag; **power feasibility asserted not demonstrated** (0023 = 79% empty / 0/14
  span-correct → flips are noise); two-author independence unstated (`authors:
  [claude]`); the `base_commit` "fix" collides with a prior reviewed decision (B2).
  Plus: "introduce" not "bump" the dataset version; token flag near-vacuous; OQ3
  classification not reproducible → record its provenance; filename nit.
**Revision 3 (developer decisions):** AC1 → reuse the sha256-pinned committed spans
(re-derivation dropped; committing patches out of scope). `base_commit` → keep the
raw-record key per B2, resolve in provisioning (not promoted). AC2 split into
unit-enforced vs a named manual audit; oracle-as-verifier removed; two-author
assumption stated; near-vacuous token flag acknowledged. New **AC8** pilot-gated
power go/no-go. `classification_provenance` added.

## Round 3 (revision 3)

### claude-p — approve-with-comments (quorum-meeting)

Confirmed all round-2 items resolved and the codebase backs almost every claim
(`min_n=12`/`MIN_DISCORDANT_PAIRS=8`; no dataset schema-version constant today;
`CONTAMINATION_CAVEAT`→`run_metadata`→`report.py` validation; the oracle/scoring
wiring; the no-committed-patch / sha256-pin resolution). Three comments (concerns 1–2
convergent with codex; concern 3 new and important):
1. **Join-vs-copy ambiguity** — the sha256 pins `raw.jsonl` whole; a terse fixture
   that copies spans is a second transcription the prose forbids. Decide join vs
   copy-plus-assertion.
2. **Loader backward-compat** (closest to a blocker) — `_parse_case` is the shared
   parser for `seed.jsonl`/`legacy/`; unconditional guard-field rejection breaks
   every existing fixture. Gate enforcement on the new schema version.
3. **AC2 likely unsatisfiable solo** — token flag near-vacuous + independence often
   unmet ⇒ the core guarantee rests on a solo audit. Not a hole to hide: make the
   **paired-ranking robustness** argument explicit (shared leakage cancels across
   A/B), since a relative instrument tolerates residual leakage an absolute one can't.

Suggestions: name a signal-vs-noise floor for AC8's flips; note the Python language
monoculture in AC7; reduce restatement.

### codex — changes-requested (two convergent must-fix)

Explicitly confirmed both round-2 blockers resolved (AC1 sha256-pin honesty; AC2
split, oracle hatch gone; base_commit ⇄ B2). New, code-grounded:
1. **AC3/AC5 additive-defaults vs loud-reject contradiction** — with defaults, missing
   guard fields aren't rejected; without, legacy/seed/raw fixtures break. Needs a
   schema-version gate (= claude-p concern 2).
2. **Underspecified source-of-truth join** — name the source-issue lookup for the
   leakage token test (`case_id → raw.jsonl.query`, hash-asserted) and make the terse
   fixture reference raw spans rather than second-transcribe them (= claude-p concern
   1). Plus: pre-register AC8's pilot projection rule + pilot minimum, not only the
   final floor.

### Revision 4 — resolutions

- **Join-not-copy (codex 2 / claude-p 1):** the terse fixture stores NO spans; it
  references `case_id` and the loader JOINS `expected_spans` / `base_commit` /
  source-issue text from the sha256-verified `raw.jsonl` (pin asserted before the
  join). Raw is the sole authority — literally "no second transcription" — and the
  token test recomputes against the joined `raw.jsonl.query`.
- **Version-gated loader (codex 1 / claude-p 2):** introduce a dataset schema-version
  tag; the loud loader enforces guard fields ONLY for terse-schema records; legacy/
  seed/raw records (no tag) load unchanged with defaults. AC5 asserts both a terse
  case missing a guard field is rejected AND a legacy case still loads.
- **Paired-ranking robustness (claude-p 3):** stated explicitly in the AC2 invariant
  and AC2 body — shared leakage inflates both arms and largely cancels in the
  within-case discordant comparison, so the set ranks A vs B even when AC2's
  independence is unmet; the guard is still recorded + audited.
- **AC8 signal floor (both):** a discordant pair counts only when ≥1 arm is a CORRECT
  localization (oracle file/span hit); an empty↔wrong-file flip is noise. Pilot
  projection rule + pilot min N + the two reference models are pre-registered.
- **AC7 monoculture + prose trim (claude-p):** the caveat names the Python language
  monoculture alongside documented-OSS; restatement reduced.

---

## Post-review amendment (revision 5) — AC2 upgraded to an executable protocol

After round 3 met quorum, the developer supplied a strengthening amendment to the
load-bearing AC2: because separate model contexts are invocable via the aux-delegator
seam (the same one this review used), the two-author blind protocol is **executable,
not a human attestation**. Revision 5 rewrites AC2 accordingly:

- **Layer (b) is now the executable two-model blind protocol** — one separately-invoked
  model authors the terse query with the gold span withheld; a separately-invoked
  verifier model records a per-case verdict on semantic leakage (catching paraphrase
  the token flag can't). Labelled "executable + reviewable," explicitly NOT
  "structurally enforced" (a determined leak could still pass).
- **Three pins:** (1) author/verifier are separately invoked (recorded assumption);
  (2) authoring blindness is verified real — no shared-state bleed (the
  is-the-skip-actually-skipping discipline); (3) the verifier verdict is DATA — leaky
  → re-author/drop, count recorded (null-provenance).
- **The paired-ranking robustness argument is demoted** from primary defense to a
  stated secondary backstop; the executable blind protocol is now the primary guard.
- This directly resolves claude-p's round-3 concern 3 (AC2 unsatisfiable for a solo
  operator) by making the two "authors" genuinely distinct model invocations rather
  than one human playing both roles.

The developer chose a round-4 confirmatory review of this new mechanism.

---

## Round 4 (revision 5) — confirmatory, scoped to AC2

### claude-p — approve-with-comments

Confirmed the upgrade **materially closes round-3 concern 3** (the aux-delegator seam
is a real separate-process context → genuine state-independence, and the guard is now
*checkable*), and the inconsistency sweep is clean (no stray "hand-authored"; the
"human attestation" strings are all negations; "hand-labeled" survives only for
classification). But it named the sharp remaining issue: **trust is relocated, not
eliminated.**
- **State vs capability independence:** separate invocation buys state-independence,
  NOT capability-independence — if author and verifier resolve to the same model, a
  paraphrase leak the author is prone to make is one the verifier is prone to miss
  (*quis custodiet*). Recommend author≠verifier model family; flag overlap with
  models-under-test.
- **Model circularity (unnamed residual risk):** models author, verify, and are
  ranked — a shared training-distribution blind spot is *correlated* (doesn't cancel)
  and flatters models that exploit it. Name it, symmetric to the other named-not-closed
  gaps.
- **Pin (2) aspirational:** "provably excludes" needs the concrete assertion — the
  recorded author input contains none of the joined `expected_spans` content for that
  `case_id`.
- **Keep paired-ranking co-primary** as the model-independent floor (the one defense
  that survives circularity), not a mere secondary backstop.

### codex — changes-requested (new, code-grounded)

Confirmed join/schema-gate/hash-pin/report-bump/monoculture/pilot all still hold, but
found the executable claim under-specified against the code:
- **The executable surface does not exist as named:** `aux-delegator` appears ONLY in
  the 0026 text; the repo has no product-level seam — Scout/eval use
  `build_scout_engine` / `ModelGateway` / fixtures. Either define the executable
  surface or declare it an external operator/dev artifact (not runtime/product code).
- **Load-bearing AC2 data is outside the validated schema:** `EvalCase` names
  `gold_withheld` / `leaked_tokens` / etc. but NOT `author_model` / `verifier_model` /
  invocation+input hashes / `verifier_verdict` / reauth-drop outcome / counts — so the
  actual proof lives in prose, violating "guarantees silently become false unless
  structurally carried." Give it a concrete validated artifact contract.
- **AC8 not deterministic:** name the projection rule, the two reference models, the
  pilot N, the STOP threshold, and where the pre-registration is stored.

### Revision 6 — resolutions (both reviewers, convergent)

- **Executable surface named (codex 1):** the two-model blind authoring is a one-time
  OFFLINE OPERATOR/DEV activity (like 0010's `convert`/`provision`), via operator
  cross-model tooling, explicitly NOT `harpyja/` runtime and NOT the product
  `ModelGateway`; only the AC6 scoring runs through the product offline.
- **Validated authoring-provenance contract (codex 2 / claude-p pin 2):** `author_model`,
  `verifier_model`, `author_input_hash`, `verifier_input_hash`, `verifier_verdict ∈
  {clean,leaky}`, `outcome ∈ {kept,reauthored,dropped}`, + aggregate leaky/dropped
  counts — carried in a loud-validated shape (terse-schema fields or a validated
  sidecar keyed by `case_id`), never prose.
- **Pin (2) operationalized (claude-p):** a test asserts the recorded author input
  contains none of the joined `expected_spans` content (paths, line ranges, span code)
  for that `case_id`.
- **State-vs-capability + circularity named (claude-p):** pin (1) split into state-
  vs capability-independence with an author≠verifier-family recommendation and
  model-under-test overlap recorded; model circularity added as a named residual risk
  (correlated, doesn't cancel), symmetric to the representativeness/language gaps.
- **Paired-ranking promoted to CO-PRIMARY model-independent floor (claude-p):** the
  defense that survives the circularity risk; no longer a mere secondary backstop.
- **AC8 deterministic (codex 3):** pre-registration is a frozen, hashed
  `PREREGISTERED_CONFIG`-style artifact naming the two reference models, pilot N (8–10),
  the projection rule, and the exact STOP threshold.

The executable mechanism's failure modes (context bleed, verifier fallibility, model
circularity, provenance-in-schema) are now named and the load-bearing proof is carried
in a validated shape — exactly what a confirmatory round is for. Remaining choices
(EvalCase-fields-vs-sidecar; the concrete pilot config values) are plan-level.

---

## Determination

**Quorum met** across rounds 3 AND 4 (claude-p: approve-with-comments both times).
Round 3's convergent blockers were resolved in revision 4; the developer's revision-5
AC2 upgrade (executable two-model blind protocol) was then confirmatorily reviewed in
round 4, and both reviewers' round-4 findings — codex's two code-grounded defects
(undefined executable surface; load-bearing data outside the validated schema) and
claude-p's three (state-vs-capability independence, model circularity, pin-2
operationalization) — are resolved in **revision 6**. No guardrail violations survive;
the recurring convention risk (a guarantee not structurally enforced) is met head-on:
the guard is labelled "executable + reviewable, NOT structurally enforced," its proof
is carried in a loud-validated provenance shape, and the residual model-circularity
risk is named-not-closed with a co-primary model-independent floor. Status →
**reviewed**.

Ready for `/speccraft:spec:plan`. Concrete build items the planner inherits: (1) the
`case_id` load-time JOIN over the sha256-pinned raw fixture; (2) schema-version-gated
guard validation in `_parse_case`; (3) the loud-validated authoring-provenance shape
(EvalCase-fields-vs-sidecar is the plan's to pick); (4) the offline operator
two-model authoring tool (out of `harpyja/` runtime); (5) the frozen/hashed AC8
pilot pre-registration config. Remaining open choices are plan-level, not
spec-blocking.
