---
id: "0026"
title: "eval"
status: closed
created: 2026-07-06
authors: [claude]
packages: [harpyja/eval]
related-specs: [0010, 0020, 0021, 0022, 0023, 0024, 0025]
---

# Spec 0026 — eval (terse-query eval set — ranking instrument for the model bake-off)

## Why

Model selection for the explorer's driving LLM needs an eval set that resembles
Harpyja's REAL target — **terse NL queries** — not SWE-bench's verbose
multi-paragraph issue text. Specs 0020–0023 proved SWE-bench issue-text is the
wrong query distribution (the QUERY_SHAPE probe + the Axis-2 representativeness
gap), and its only virtue was free patch-derived labels. This spec builds the
smallest labeled set that can **RANK** candidate models in the bake-off: keep the
free, sha256-pinned patch-derived spans as labels but pair each with a **terse
Harpyja-style query** authored from the issue's intent. It is a **relative-ranking
instrument**, deliberately small and paired — not an absolute-accuracy benchmark.
**This unblocks the bake-off; it is NOT the bake-off.**

Ref: 0010 (swebench provisioning + patch→span oracle), 0020–0023 (QUERY_SHAPE
falsified, Axis-2 representativeness gap, the distiller leakage guard), 0024/0025
(the explorer is now the sole Scout backend).

### The through-line

The project's recurring lesson — **a guarantee that isn't structurally enforced
silently becomes false** — applied to the dataset layer: **one integrity-pinned
label source** (join the sha256-verified committed spans by `case_id`; never a
hand-copied second transcription), **validated provenance fields** (in the loud
loader, gated by a dataset schema version; never an unvalidated passenger key), and
a **pinned representativeness caveat** (a schema-validated field that travels with
every result). The leakage guard's real teeth come from an **executable two-model
blind protocol** — author and verifier are *separately-invoked model contexts* (the
same aux-delegator model seam used for cross-review), reviewable per case — labelled
exactly that: executable and reviewable, NOT a structural proof (a determined leak
could still pass), and NOT a human honor-system attestation.

### Load-bearing invariants

- **INVARIANT (dataset, not model/harness change):** builds an eval fixture only.
  No change to Scout, the explorer loop, the gate, or the orchestrator. Reuses the
  existing patch→span oracle output and provisioned repos.
- **INVARIANT (labels JOINED from ONE integrity-pinned source):** the terse fixture
  does NOT store spans. Each case references a raw case by `case_id` and carries only
  the terse `query` + guard/provenance fields; at load the loader **joins**
  `expected_spans`, `base_commit`, and the source-issue text (the raw `query`, i.e.
  SWE-bench `problem_statement`) from the git-tracked
  `harpyja/eval/fixtures/swebench_verified.raw.jsonl`, integrity-verified against the
  sha256 in `swebench_verified.provenance.json`. So `raw.jsonl` stays the **sole
  authority** and there is literally no second transcription of a span. Those spans
  are the deterministic `parse_patch` output frozen at the audited network `convert`
  stage (the gold patches are not committed → nothing to re-derive offline; the
  sha256 pin is the integrity guarantee). Label provenance = `patch-derived-at-convert`.
- **INVARIANT (leakage guard — the honesty crux — an EXECUTABLE two-model blind
  protocol, run OFFLINE as an operator/dev activity):** the terse query is authored
  from the ISSUE'S INTENT, not the gold span's code. **The authoring runs OUTSIDE
  Harpyja's air-gapped runtime** — a one-time OPERATOR/DEV activity (like the 0010
  network `convert`/`provision` stages), using the operator's cross-model invocation
  tooling (the same separate-model-context seam Speccraft uses for cross-review), NOT
  `harpyja/` product code and NOT the product `ModelGateway`; it produces the
  committed terse fixture + a loud-validated authoring-provenance record. **Layer (a)
  — unit-testable tripwire (weak, first-pass only):** provenance fields present,
  token-subset flag computed (a query with gold-span-only identifiers — tokens absent
  from the joined source issue — is flagged), loud loader rejects a terse-schema case
  missing the guard fields. Near-vacuous by construction (the terse query is authored
  FROM the issue, so its tokens are almost always a subset), so kept only as a cheap
  tripwire. **Layer (b) — the REAL guard, two-model blind:** one model authors the
  terse query from issue-intent with the gold span WITHHELD; a **separately-invoked**
  second model verifies the query does not *semantically* encode the span (catching
  the paraphrase/synonym leakage the token flag cannot). EXECUTABLE and REVIEWABLE,
  NOT a human honor-system attestation, and NOT "structurally enforced" either (a
  determined leak could still pass; the spec claims exactly "executable + reviewable,"
  no more). Three pins: **(1) independence is STATE-level, not CAPABILITY-level** —
  separate invocation guarantees no shared conversation/state (real + checkable), but
  NOT that the verifier catches every leak the author is prone to make; so author and
  verifier SHOULD be different model families, and any overlap with a model-under-test
  is recorded. **(2) blindness is VERIFIED REAL, operationally** — a test asserts the
  recorded author-invocation input (`author_input_hash`) contains NONE of the joined
  `expected_spans` content (file paths, line ranges, span code) for that `case_id`
  (the concrete "is-the-skip-actually-skipping" assertion, not a bare claim). **(3)
  the verifier verdict is DATA, NOT A SILENT GATE** — leaky → re-author/drop, counts
  recorded (provenance-of-a-null). **Named residual risk (not closed):** model
  CIRCULARITY — author, verifier, and the models-under-test may share a
  training-distribution blind spot that is CORRELATED (does not cancel) and would pass
  a leak while flattering the models that exploit it; mitigated by
  author≠verifier≠subject model diversity + the floor below, but named-not-closed,
  symmetric to the representativeness/language-monoculture gaps. **Model-independent
  FLOOR (CO-PRIMARY, not a mere backstop):** because the instrument is RELATIVE,
  residual leakage is shared across models A and B on the same case and largely
  cancels in the within-case discordant comparison — a statistical property that holds
  even when every model shares a blind spot, so it is the defense that SURVIVES the
  circularity risk. Kept co-primary with the blind protocol.
- **INVARIANT (small + paired; cite committed constants; PROVE power before authoring
  the whole set):** the McNemar power lives in the **discordant localization-flip
  pairs** (model-A-vs-model-B on the same case), not raw N. Size to the repo's
  committed floors — `PREREGISTERED_CONFIG.min_n = 12` usable, `MIN_DISCORDANT_PAIRS
  = 8` discordant per pairwise comparison — across ~20–40 cases spanning multiple
  repos. Because 0023 measured near-zero Scout localization (79% empty, 0/14
  span-correct) — a floor where two models' "flips" are empty↔wrong-file NOISE, not
  rankable signal — power is not assumed: a **pre-registered pilot-gated go/no-go**
  (AC8) fires two reference models on a pilot and STOPs if the *signal-bearing*
  discordant count is unreachable, rather than re-running 0023's dead end at full
  authoring cost.

## What

- **Labels — join by `case_id`, don't copy.** Each terse record carries `case_id` +
  terse `query` + guard/provenance fields; the loader joins `expected_spans` /
  `base_commit` / source-issue text from the sha256-verified `raw.jsonl` (asserting
  the pin BEFORE the join). No span is transcribed into the terse fixture. Provenance
  tag `patch-derived-at-convert`.
- **Queries — model-authored OFFLINE under the executable two-model blind protocol.**
  A one-time operator/dev activity outside Harpyja runtime (operator cross-model
  tooling, not the product `ModelGateway`): one separately-invoked model authors the
  terse query from issue INTENT with the gold span WITHHELD; a separately-invoked
  verifier model (different family where feasible; NOT the `parse_patch` oracle)
  records a per-case verdict on semantic leakage. The per-case **authoring-provenance
  is a loud-validated shape** (not prose) carrying `author_model`, `verifier_model`,
  `author_input_hash`, `verifier_input_hash`, `verifier_verdict ∈ {clean, leaky}`,
  `outcome ∈ {kept, reauthored, dropped}`, plus aggregate `leaky_count` /
  `dropped_count` (null-provenance). A "leaky" verdict → re-author or drop (never a
  silent gate). Pin (2)'s blindness check asserts the `author_input_hash` payload
  contains none of the joined span content.
- **Schema — additive VALIDATED fields, gated by a NEW dataset schema version.**
  Introduce a dataset schema-version tag in `dataset.py` (there is none today — a new
  constant, not a bump). Extend `EvalCase` with additive last-with-default fields
  (`case_id`-ref join marker, `label_provenance`, `query_provenance` / `gold_withheld`,
  `leaked_tokens`, `classification_provenance`). The loud loader (`_parse_case`)
  enforces the guard fields **only for records at the new terse schema version**;
  legacy/seed/raw records (no version tag) load unchanged with defaults — so
  additive-defaults (backward-compat) and reject-if-missing (terse guard) coexist via
  the version gate, and `seed.jsonl` / `legacy/` fixtures and their tests keep
  loading. The Layer-(b) authoring-provenance fields (`author_model`, `verifier_model`,
  `author_input_hash`, `verifier_input_hash`, `verifier_verdict`, `outcome`) are ALSO
  loud-validated (additive terse-schema `EvalCase` fields OR a loud-validated authoring
  sidecar keyed by `case_id` — the plan picks; the load-bearing proof is carried in a
  validated shape, NEVER prose). `base_commit` stays a raw-record key per review B2
  (resolved via provisioning, AC6 — NOT promoted to a validated `EvalCase` field).
- **Classification — hand-labeled by query intent, provenance recorded.** Re-label by
  query intent (0010's patch-shape heuristic was a proxy for the replaced
  distribution); carry `classification_provenance` = `hand-labeled-by-intent` marking
  it a deliberate, audited exemption from the span-reproducibility rule (intent labels
  are not reproducible from the patch). Where intent and patch-shape disagree, intent
  wins.
- **Scoring — reuse the existing single oracle, no new scoring code.** File-level AND
  span-level (file-level primary; span-level secondary) via `metrics.span_hit_kind` +
  `locate_accuracy.score_distribution`, already wired through
  `locate_probe.run_locate_probe` → `build_scout_engine`.
- **Representativeness caveat — a pinned schema field.** Emit the query-shape-only /
  codebase-character-NOT scope as a schema-validated `run_metadata` field (mirroring
  `CONTAMINATION_CAVEAT`), bumping the report `SCHEMA_VERSION`.

## Acceptance criteria

([unit]=fakes; [integration]=offline scoring, skip-not-fail)

1. **[unit]** **Labels joined from one integrity-pinned source.** A test asserts
   `sha256(raw.jsonl) == provenance.json` pin, then that each terse case's `case_id`
   resolves in the pinned `raw.jsonl` and the loader joins its `expected_spans` /
   `base_commit` / source-issue text — the terse fixture stores NO spans (no second
   transcription). Provenance is `patch-derived-at-convert`, never "human-confirmed",
   never re-derived (no committed patch exists).
2. **[unit + executable-protocol]** **Two layers — a weak tripwire + an EXECUTABLE
   two-model blind protocol (LOAD-BEARING), run OFFLINE as an operator activity**
   (outside Harpyja runtime; operator cross-model tooling, not the product
   `ModelGateway`). *Layer (a), unit:* provenance-field presence, the token-subset flag
   recomputed against the JOINED source issue, and the loud loader's rejection of a
   terse case missing guard fields (AC5) — a near-vacuous first-pass tripwire. *Layer
   (b), executable + reviewable (the real guard):* a separately-invoked author model
   writes the query with the gold span withheld; a separately-invoked verifier model
   records a per-case verdict. **The load-bearing proof is carried in a loud-validated
   shape** (`author_model`, `verifier_model`, `author_input_hash`, `verifier_input_hash`,
   `verifier_verdict`, `outcome`, + aggregate leaky/dropped counts) — NEVER prose.
   Pins: (1) independence is STATE-level, not CAPABILITY-level → recommend
   author≠verifier model family, record overlap with any model-under-test; (2)
   blindness verified real OPERATIONALLY → a test asserts the recorded author input
   contains none of the joined `expected_spans` content for that `case_id`; (3) the
   verdict is DATA → leaky → re-author/drop, counts recorded (null-provenance).
   Labelled "executable + reviewable," NOT "structurally enforced" (a determined leak
   could still pass). The `parse_patch` oracle is NOT a verifier. **Named residual
   risk:** model circularity (author/verifier/subject shared blind spot — correlated,
   does not cancel). The paired-ranking cancellation is retained CO-PRIMARY as the
   model-independent floor that survives that risk.
3. **[unit]** **Guard/provenance are ADDITIVE VALIDATED `EvalCase` fields under a NEW,
   GATED dataset schema version.** Fields appended last-with-defaults; a dataset
   schema-version constant is introduced; the loud loader enforces guard fields ONLY
   for terse-schema records and loads legacy/seed records (no version tag) unchanged
   with defaults. `base_commit` stays a raw-record key per review B2 (not promoted).
4. **[unit]** **Size/pairing floor cites the committed constants.** ≥ `min_n = 12`
   usable and ≥ `MIN_DISCORDANT_PAIRS = 8` signal-bearing discordant (model-A-vs-B
   localization-flip) pairs per pairwise comparison; ~20–40 total; multiple repos (no
   single-repo domination).
5. **[unit]** **Loud loader covers the guard, without breaking legacy.** A terse case
   missing a guard field is rejected loudly (`DatasetError`); an existing
   seed/legacy case (no version tag) still loads. Both asserted.
6. **[integration]** **Drives the real backend end to end, via the named provisioning
   path.** Explorer (sole Scout backend) runs the set offline/Scout-only, producing
   file-level + span-level scores via the existing oracle. Path: raw record's
   `base_commit` → provisioned worktree (`swebench_verified.resolved.jsonl`,
   machine-local) → explorer runs against it, through `run_locate_probe` →
   `build_scout_engine` → `locate_accuracy.score_distribution`. Skip-not-fail when no
   served stack is present.
7. **[doc + schema]** **Representativeness scope is a PINNED, schema-validated field.**
   Emitted as a `run_metadata` field mirroring `CONTAMINATION_CAVEAT` (bump report
   `SCHEMA_VERSION`): fixes the QUERY-SHAPE axis but NOT the codebase-character axis —
   which is BOTH a documented-OSS gap AND a **language monoculture** (SWE-bench
   Verified is Python-only; all pooled cases are `language: python`). Valid for
   RELATIVE ranking; a strong score does NOT prove real-world legacy performance. The
   codebase-character gap is a separate later problem, named not closed.
8. **[integration]** **Pre-registered pilot-gated power go/no-go, with a signal floor.**
   Before authoring the full ~20–40, a pilot subset (**author 8–10 cases first**) runs
   through two pre-registered reference models on the paired axis to confirm enough
   non-empty localization + discordance to project the ≥8-flip floor. A discordant pair
   counts as **signal-bearing ONLY when at least one arm is a CORRECT localization**
   (file-or-span hit per the oracle) — an empty↔wrong-file flip is NOISE and does not
   count (guards exactly the 0023 failure). **Pre-registration is a FROZEN, HASHED
   config** (0023's `PREREGISTERED_CONFIG` pattern, hashed BEFORE the pilot) naming the
   two reference models, the pilot N (8–10), the **projection rule** (how the pilot's
   signal-bearing discordant RATE extrapolates to the full-size flip count), and the
   exact **STOP threshold** (projected signal-bearing discordant `< MIN_DISCORDANT_PAIRS
   = 8`). If the projection is below threshold the set is declared **UNDER-POWERED
   (STOP)** — a typed outcome naming the next step (e.g. the finder-capability work
   0022/0023 pointed at), not a set authored to rank noise.

**The load-bearing AC is #2** — the reason the set is trustworthy rather than a
flattering mirror. Its real guard is the EXECUTABLE two-model blind protocol
(separately-invoked author and verifier models, blindness verified real and carried
in a loud-validated provenance shape, verdict recorded as data) — labelled "executable
+ reviewable," not overclaimed as a structural proof, run OFFLINE as an operator
activity (not Harpyja runtime). The loader-enforced token flag is a weak first-pass
tripwire. Trust is RELOCATED, not eliminated: separate invocation buys STATE- not
CAPABILITY-independence, so model circularity (a shared author/verifier/subject blind
spot) is a named residual risk — held by author≠verifier≠subject model diversity plus
the CO-PRIMARY model-independent floor (paired-ranking cancellation, which holds even
when every model shares a blind spot). AC8 guards the orthogonal risk that even a
clean set may be under-powered to rank at 0023's near-zero localization floor.

## Out of scope

- The model bake-off itself (next spec — this builds its instrument).
- A legacy/undocumented codebase eval, and a non-Python eval (both deferred Axis-2
  problems — codebase-character AND language monoculture).
- Any Scout/explorer/gate/Tier-0 behavior change.
- **Mechanical subset-extraction distillation (0023's `mechanical_distill`) as the
  authoring mechanism** (rejected, OQ1: it yields unnatural queries + re-runs 0023).
  The chosen mechanism is a MODEL authoring a NATURAL terse query from issue intent
  under the executable two-model blind protocol — distinct from mechanical extraction;
  `mechanical_distill` may serve only as a non-primary baseline/divergence check.
- **Committing gold patches / literal offline re-derivation** (rejected round-2: the
  sha256-pinned committed spans are the trusted source).
- **Promoting `base_commit` to a validated `EvalCase` field** (rejected round-2: keep
  review B2's raw-record key, resolve in provisioning).
- OQ2/threshold tuning.

## Open questions — resolved in review

### Round 1
1. **Authoring mechanism → model-authored under an EXECUTABLE two-model blind
   protocol** (separately-invoked author + verifier models; token flag a near-vacuous
   first-pass tripwire). Supersedes the earlier "hand-authored" wording — the
   separate-model-context insight (round 3) makes the blind protocol executable.
2. **Include empty/wrong-file cases? → known-correct-span-only**; excluded count is a
   labeled field (provenance-of-a-null), never a silent drop.
3. **Classification → re-label by query intent**, recording
   `classification_provenance = hand-labeled-by-intent` (audited exemption from
   span-reproducibility); intent wins on disagreement.

### Round 2
4. **AC1 label source (no committed patches) → reuse the sha256-pinned committed
   `expected_spans`** (convert-time `parse_patch` output; the pin is the integrity
   guarantee). Re-derivation dropped; committing patches out of scope.
5. **`base_commit` vs review B2 → keep it a raw-record key** (B2 preserved), resolved
   via provisioning; NOT promoted.

### Round 3
6. **Single-source MECHANISM (join vs copy) → JOIN by `case_id` from pinned
   `raw.jsonl`** (raw is sole authority; no second transcription; also names the
   source-issue lookup for the token test).
7. **Loader backward-compat → GATE guard-field enforcement on the new dataset schema
   version** (legacy/seed load with defaults; terse-schema records require the guard).
8. **AC2 guard strength → UPGRADED to an EXECUTABLE two-model blind protocol.**
   Because separate model contexts are invocable via the aux-delegator seam (the same
   one used for cross-review), the author and verifier are genuinely distinct model
   invocations — so the blind protocol is executable and reviewable per case, not a
   human honor-system attestation. Pins: separate invocation (assumption recorded),
   blindness verified real (no shared-state bleed), verifier verdict as data (leaky →
   re-author/drop, count recorded). Labelled "executable + reviewable," NOT
   "structurally enforced." (Supersedes the revision-4 framing that treated the blind
   protocol as a non-executable human attestation tolerated only by paired ranking.)
   Plus AC8 gains a signal-bearing-flip floor + pre-registered pilot rule (author 8–10
   cases first).

### Round 4 (confirmatory, scoped to the AC2 executable protocol)
9. **Executable SURFACE → declared an OFFLINE OPERATOR/DEV activity** (codex): the
   two-model blind authoring runs outside `harpyja/` runtime (like 0010's
   `convert`/`provision`), via operator cross-model tooling, NOT the product
   `ModelGateway`; only AC6 scoring runs through the product. `aux-delegator` is that
   operator seam, not a product interface.
10. **Load-bearing proof → carried in a LOUD-VALIDATED shape** (codex + claude-p): the
    authoring provenance (`author_model`, `verifier_model`, `author_input_hash`,
    `verifier_input_hash`, `verifier_verdict`, `outcome`, + leaky/dropped counts) is
    validated, never prose; pin (2) is operationalized (author input contains none of
    the joined span content for that `case_id`).
11. **Trust relocation named** (claude-p): independence is STATE- not
    CAPABILITY-level (recommend author≠verifier family; record model-under-test
    overlap); model CIRCULARITY is a named residual risk (correlated, doesn't cancel);
    the paired-ranking floor is **retained CO-PRIMARY** as the model-independent
    defense that survives circularity (NOT demoted — this supersedes round-3 #8's
    "secondary backstop" wording).
12. **AC8 made deterministic** (codex): pre-registration is a frozen, hashed
    `PREREGISTERED_CONFIG`-style artifact (two reference models, pilot N, projection
    rule, exact STOP threshold).
