---
spec: "0036"
title: "terse-query"
reviewers: [codex (gpt-5.5), claude-p]
quorum: "1 approve / approve-with-comments"
rounds: 2
quorum_met: true
verdict: approve-with-comments
status: reviewed
round1_generated: 2026-07-09
round2_generated: 2026-07-09
code_verified_against: a983bcc
---

# Cross-model review — 0036-terse-query

## Round 1

### Verdict summary

| Reviewer | Verdict | Guardrail violations | Convention violations |
|---|---|---|---|
| codex (gpt-5.5) | changes-requested | 0 | 3 |
| claude-p | changes-requested | 0 | 2 |
| **Overall** | **changes-requested** | **0** | **converges on 2 shared + 1 codex-only** |

Quorum (1 approve or approve-with-comments) was **NOT met** — both reviewers
independently landed on `changes-requested`. Spec 0036 stayed `draft` pending
revision.

---

### codex (gpt-5.5)

**Verdict:** changes-requested

Concerns:
- "No new schema" invariant vs. mandatory new per-case tags (lexical-reachability,
  concept-vs-patch) — 0026's shipped schema does not carry those fields.
- AC4's pilot gate is under-specified relative to 0026: doesn't require reusing the
  frozen/hashed `PREREGISTERED_AC8_CONFIG`, named reference models, pilot N,
  projection rule, or exact STOP threshold.
- Full-set acceptance path doesn't pin minimum usable N, minimum discordant-pair
  floor, or multi-repo/no-domination constraints, even though 0026 made those
  load-bearing.
- "Concept gold" is introduced without defining whether concept spans are joined
  from an integrity-pinned source, authored in a sidecar, or scored as a secondary
  oracle.

Suggestions:
- Resolve the schema contradiction: additive version-gated fields on 0026's schema,
  or a loud-validated authoring sidecar keyed by `case_id`.
- Make AC4 cite and reuse 0026's frozen AC8 machinery verbatim, including config
  hash and `UNDER_POWERED_STOP` semantics.
- Add an AC requiring `validate_terse_set_floor`-style enforcement for full-set N,
  discordant-pair floor, and repo spread.
- Define concept-vs-patch gold as data provenance + scoring behavior + artifact
  shape explicitly.

Convention violations:
- Pre-registered pilot POWER-GATE must be frozen + hashed (Invariant "pilot-gated
  authoring" / AC4).
- Eval fixture must join labels by key from a sha256-pinned source, never
  transcribe twice (Invariants / What — concept-vs-patch gold's source-of-truth and
  join mechanics unspecified).
- A NEW schema-version tag must gate strict validation so additive-defaults and
  reject-if-missing coexist in one loud loader (Invariant "build on 0026's
  instrument" vs. AC1–2).

---

### claude-p

**Verdict:** changes-requested

Concerns:
- Internal contradiction: "No new schema" invariant vs. AC1's loud rejection of
  cases missing the new reachability/concept-vs-patch tags — loud rejection of NEW
  required fields IS a loader/schema change, and per 0026's own version-gate
  convention that requires a NEW gated dataset schema version, not a guard bolted
  onto the existing one.
- The concept-vs-patch invariant says "record both" spans, but the label invariant
  (and 0026 AC1) says the terse fixture stores no spans — labels are only ever
  JOINED from the sha256-pinned `raw.jsonl`. A concept span cannot be joined from
  there; it is a second, hand-authored label source with no stated storage
  location, provenance tag, or audited exemption.
- "So scoring doesn't penalize a concept-correct localization as wrong" implies a
  scoring change, but "Any harness/verifier behavior change" is listed Out of
  Scope — the concept tag's consumer is ambiguous as written.
- Fate of the five committed PLACEHOLDER cases in `swebench_verified.terse.jsonl`
  is unstated: if the loader starts rejecting cases missing the new tags, the
  placeholders (which lack them) break existing tests; must be decided in-spec.
- Pilot config interplay under-specified: OQ1 proposes sizing the full set from the
  pilot, but the frozen projection rule extrapolates to `full_n_target=30`;
  re-sizing without re-registering is post-hoc steering of the gate the freeze
  exists to protect. Any deviation (reference models, `explorer_think`, etc.)
  requires a NEW frozen+hashed config committed BEFORE the pilot.
- Blindness of the new tags is unstated: the mechanical reachability check and
  hand-labeling both require gold visibility — safe only if tagging happens
  strictly post-authoring and is never author-visible, else it's a leakage
  side-channel into the protocol AC3 relies on.
- Frontmatter `packages: []` is inconsistent with AC1–AC3, which require
  validation code and unit tests in `harpyja/eval`.

Suggestions:
- Amend the first invariant to land reachability + concept-vs-patch tags as
  additive `EvalCase` fields under a NEW gated `DATASET_SCHEMA_VERSION` (e.g.
  `0036/1`), per the 0026 version-gate pattern; `0026/1` and legacy rows keep
  loading.
- Resolve concept-vs-patch storage explicitly: patch-derived label stays join-only
  (unchanged authority); concept span is a NEW, hand-labeled, additive field with
  its own provenance (mirroring `classification_provenance =
  hand-labeled-by-intent`). Reword the scoring clause to "so the bake-off's
  scoring can split/credit on this axis" and keep scoring changes out of scope.
- Give the reachability tag per-case provenance (mechanical | hand-labeled); state
  the tag is computed post-authoring, never surfaced to the author model.
- State AC4 runs the EXISTING frozen `PREREGISTERED_AC8_CONFIG` / `decide_ac8`
  unchanged; any deviation is a new pre-registered frozen+hashed config committed
  before the pilot fires.
- Decide the placeholder fixture fate in-spec: replace the five placeholder rows
  with the real pilot cases in the same change, updating join/floor tests.
- Have AC5 name the persistence convention: verifier artifacts via the 0035
  `live_artifacts` helper, `status=PASSED` under `VERIFIER_SCHEMA_VERSION 0034/1`.
- Set frontmatter `packages: [harpyja/eval]`.

Convention violations:
- A NEW schema-version tag must GATE strict validation so additive-defaults and
  reject-if-missing coexist (0026 pattern) — new mandatory fields require a
  version gate, not a guard on an existing version (Invariants vs. AC1).
- An eval fixture JOINS labels by key from a sha256-pinned source of truth, never
  transcribes a second time (Invariants, concept-vs-patch bullet — a concept span
  cannot be joined from `raw.jsonl`, storage/provenance unspecified).

---

### Synthesis

Both reviewers independently reached `changes-requested` and, working
independently, converged on the same two structural contradictions — a strong
signal these are real, not reviewer idiosyncrasy. The orchestrator's code
verification (against HEAD `a983bcc`) confirms the factual predicates under both
and adds one sharper detail neither reviewer stated as precisely.

#### Convergent blocking findings (both reviewers)

**1. "No new schema" invariant vs. AC1's loud rejection of missing tags**

Both reviewers flag the same internal contradiction: the spec's own invariant says
"No new schema, no new authoring tool," but AC1 requires a case missing a
reachability or concept-vs-patch tag be "rejected loudly." Loud rejection of new
*required* fields is schema surface by 0026's own convention (a NEW
schema-version tag gates strict validation so additive-defaults and
reject-if-missing coexist).

- CONFIRMED (orchestrator): `EvalCase` in `harpyja/eval/dataset.py` has no
  reachability or concept-vs-patch fields today; it carries `label_provenance`,
  `leaked_tokens`, `classification_provenance`. The contradiction is real, not a
  wording nit.
- CONFIRMED, and sharper than either reviewer stated: `DATASET_SCHEMA_VERSION =
  "0026/1"` (dataset.py:32), and **dataset.py:123 keys terse-branch detection on
  an EXACT version match** (`is_terse = schema_version ==
  DATASET_SCHEMA_VERSION`). A naive "0036/1" bump would not even be parsed as
  terse under today's code — this needs the known-versions-set treatment (the
  `_KNOWN_VERIFIER_SCHEMA_VERSIONS` pattern from `live_verifier`), not just new
  additive fields on an unchanged version string.

**Resolution (per both reviewers' suggestions, and the codebase's own precedent):**
adopt the 0026 version-gate pattern explicitly — reachability + concept-vs-patch
tags land as additive `EvalCase` fields under a NEW gated
`DATASET_SCHEMA_VERSION` (e.g. `0036/1`), with `is_terse` widened to a known-set
membership check (not exact-match) so `0026/1` legacy rows and `0036/1` new rows
both keep loading, and only `0036/1`+ rows are held to the new-tag-required rule.

**2. Concept-vs-patch gold's storage/provenance vs. join-only label invariant**

Both reviewers flag that "record both / tag it" for concept-vs-patch gold
conflicts with the spec's own label invariant (and 0026 AC1): terse fixtures store
no spans, labels are only ever JOINED from the sha256-pinned patch-derived source.
A concept span does not exist in that source and cannot be joined — it is, by
construction, a second hand-authored label with no stated storage location or
provenance tag, and the eval-fixture convention (join by key from a pinned
source, never transcribe twice) is violated as currently worded.

**Resolution:** the patch-derived label stays join-only (unchanged authority); the
concept span becomes a NEW, hand-labeled, additive field carrying its own
provenance — mirroring the `classification_provenance =
hand-labeled-by-intent` precedent already in the codebase (a named, audited
exemption from span-reproducibility, not a silent violation). Reword the scoring
clause from "so scoring doesn't penalize a concept-correct localization as wrong"
to "so the bake-off's scoring splits on this axis" — this keeps the actual
scoring-behavior change out of scope (per the spec's own Out-of-Scope list) while
making the concept tag's consumer unambiguous.

**3. AC4's pilot gate must bind to the frozen config, not restate it vaguely**

Both reviewers independently flag that AC4 doesn't pin AC4 to 0026's frozen/hashed
pilot machinery — codex on "restated vaguely, not required to reuse verbatim"
grounds, claude-p with the sharper concern that OQ1's proposal to size the full
set from the pilot risks re-deriving the projection target post-hoc, defeating the
purpose of the freeze, and that any config deviation (reference models,
`explorer_think`, pilot N) needs a NEW frozen+hashed config committed *before* the
pilot fires, not discovered mid-authoring.

- CONFIRMED (orchestrator): `PREREGISTERED_AC8_CONFIG` (`ac8_pilot.py`) freezes
  `reference_model_a = "hf.co/Qwen/Qwen3-8B-GGUF:latest"`, `reference_model_b =
  "qwen3:4b-instruct"`, `pilot_n=10`, `full_n_target=30`,
  `min_discordant_pairs=8`, with a `config_hash`. **The current live stack runs
  `qwen3:14b`** — the frozen arms genuinely differ from the current stack, so
  claude-p's "new frozen config committed before the pilot" concern is live, not
  hypothetical: authoring under today's live model without a fresh
  pre-registration would silently deviate from the instrument the freeze exists
  to protect.

**Resolution:** AC4 must state explicitly that it runs the EXISTING frozen
`PREREGISTERED_AC8_CONFIG` / `decide_ac8` unchanged (config hash cited), OR that a
NEW pre-registered frozen+hashed config is committed BEFORE the pilot if the
reference models are to track the current live stack. Sizing the full set upward
of the frozen `full_n_target=30` post-PROCEED is harmless; re-deriving the target
itself is where steering creeps in — the spec should say so.

#### Single-reviewer findings worth adopting

- **codex:** add a full-set floor AC. CONFIRMED (orchestrator):
  `validate_terse_set_floor` (`terse_dataset.py`) already enforces `min_n=12`,
  multi-repo spread, and no single-repo domination — this maps to existing
  machinery, not new code, and should simply be cited as an AC.
- **claude-p:** fate of the five placeholder fixture rows. CONFIRMED
  (orchestrator): five `PLACEHOLDER` rows exist in
  `harpyja/eval/fixtures/swebench_verified.terse.jsonl`, all `schema_version
  0026/1`, query `"PLACEHOLDER pending offline blind authoring"`,
  `gold_withheld: false`, repos astropy/django/requests/sympy/matplotlib.
  Recommend: replace with the real pilot cases in the same change, updating
  join/floor tests.
- **claude-p:** tag-blindness ordering — reachability and concept-vs-patch tags
  must be computed strictly post-authoring and never author-visible, or the new
  surface is a leakage side-channel `assert_author_input_blind` doesn't cover.
  Pin this ordering explicitly with one sentence.
- **claude-p:** AC5 should name the persistence convention explicitly —
  `live_artifacts` helper (`eval_work/live_artifacts/...`), `status=PASSED` under
  `VERIFIER_SCHEMA_VERSION 0034/1` — so pilot evidence survives the run per the
  0035 lesson.
- **claude-p:** `packages: []` in frontmatter is inconsistent with AC1–AC3, which
  require validation code and unit tests in `harpyja/eval`. Set `packages:
  [harpyja/eval]`.
- **claude-p:** AC6 should point at the pinned `REPRESENTATIVENESS_CAVEAT` rather
  than restate it in new prose. CONFIRMED (orchestrator): `REPRESENTATIVENESS_CAVEAT`
  is pinned at `harpyja/eval/report.py:41` and stamped into report payloads at
  `report.py:175` — this suggestion is directly actionable.
- **claude-p:** OQ3 should pre-declare numerically what "enough conceptual cases"
  means before the sample is drawn, rather than leaving the threshold implicit.

#### Guardrail violations

**Zero guardrail violations from both reviewers.** Authoring stays an offline
operator activity; the air-gap and read-only invariants are untouched by this
spec. Both reviewers filed convention violations only (schema-gate convention,
join-only-label convention), no guardrail-level findings.

---

### Action recommendation (round 1)

The following concrete edits to `spec.md` were required before re-review:

1. Amend the "build on 0026's instrument" invariant: reachability +
   concept-vs-patch tags land as additive `EvalCase` fields under a NEW gated
   `DATASET_SCHEMA_VERSION` (e.g. `0036/1`); widen `is_terse` detection from
   exact-match to known-versions-set membership (mirroring
   `_KNOWN_VERIFIER_SCHEMA_VERSIONS`) so `0026/1` legacy rows and `0036/1` new
   rows both keep loading; only `0036/1`+ rows are held to the new-tag-required
   rule in AC1.
2. Resolve concept-vs-patch gold storage: patch-derived label stays join-only
   (unchanged authority, unchanged source); concept span becomes a NEW,
   hand-labeled, additive field with its own provenance tag, named as a
   deliberate audited exemption mirroring `classification_provenance =
   hand-labeled-by-intent`.
3. Reword the concept-vs-patch scoring clause from "so scoring doesn't penalize a
   concept-correct localization as wrong" to "so the bake-off's scoring splits on
   this axis" — keeping scoring-behavior change explicitly out of scope.
4. Rewrite AC4 to bind explicitly to the frozen `PREREGISTERED_AC8_CONFIG` /
   `decide_ac8` (cite the config hash), OR state that a NEW pre-registered
   frozen+hashed config is committed BEFORE the pilot if reference models are to
   track the current live stack (`qwen3:14b` vs. the frozen `Qwen3-8B` /
   `qwen3:4b-instruct` arms).
5. Add an AC (or extend AC1/AC6) requiring `validate_terse_set_floor` enforcement
   (min_n, discordant-pair floor, multi-repo/no-domination) on the full set
   before it's called representative.
6. Decide the fate of the five placeholder rows in
   `swebench_verified.terse.jsonl` in-spec: recommend replace with the real pilot
   cases in the same change, updating join/floor tests accordingly.
7. Pin tag-blindness ordering: reachability and concept-vs-patch tags are
   computed strictly post-authoring, never surfaced to the author model, and
   this surface is covered by (or explicitly added to) the
   `assert_author_input_blind` guard.
8. Have AC5 name the persistence convention explicitly: 0035's `live_artifacts`
   helper, `status=PASSED`, `VERIFIER_SCHEMA_VERSION 0034/1`.
9. Set frontmatter `packages: [harpyja/eval]`.
10. Have AC6 point at the pinned `REPRESENTATIVENESS_CAVEAT` (`report.py:41`)
    rather than restating it in new prose.
11. Pre-declare numerically in OQ3 what "enough conceptual cases" means before
    the sample is drawn.

### Next step (round 1 — superseded)

Quorum was not met after round 1 — spec 0036 stayed `draft`. All 11 action items
above were applied to `spec.md`, which was then re-reviewed by the same two
agents. See **Round 2** below for the outcome of that re-review.

---

## Round 2

The spec was revised per round 1's 11-item action list, then re-reviewed by the
same two agents against the updated `spec.md`.

### Verdict summary

| Reviewer | Verdict | Guardrail violations | Convention violations |
|---|---|---|---|
| codex (gpt-5.5) | approve-with-comments | 0 | 0 |
| claude-p | approve-with-comments | 0 | 0 |
| **Overall** | **approve-with-comments** | **0** | **0** |

Quorum (1 approve or approve-with-comments) is **MET** — spec 0036 advances to
`reviewed`.

---

### codex (gpt-5.5) — round 2

**Verdict:** approve-with-comments

Concerns:
- AC7 under-specifies the full-set size floor relative to the frozen AC8 config:
  it cites `validate_terse_set_floor(min_n=12)`, while the governing AC8 config
  freezes `full_n_target=30` and the What section says full authoring must be
  at-or-above that target. *Verified status: consistent with round 1's confirmed
  `PREREGISTERED_AC8_CONFIG` freeze (`full_n_target=30`) — a real two-floors gap,
  not a code-fact codex needed to newly verify.*
- The concept-vs-patch field shape is still slightly ambiguous: the prose
  alternates between a mandatory tag for every case and an additive concept span
  "where present." *Verified status: spec-wording/shape concern, not a code
  citation — resolved by pinning an explicit per-row contract.*

Suggestions:
- Tighten AC7 to require both `validate_terse_set_floor` and the governing frozen
  `full_n_target` floor before calling the full set representative.
- Define the concept-vs-patch fields as an explicit per-row shape, e.g.
  `concept_patch_relation` plus optional `concept_span` /
  `concept_span_provenance`.

Guardrail violations: none. Convention violations: none.

Discussion (abridged, faithful): the revision resolves the round-1 blockers —
schema contradiction fixed with a new gated `0036/1` version and known-version
detection; label authority remains join-only; concept span is now a named,
audited hand-labeled additive exception; pilot pre-registration is bound before
execution; placeholder fate, tag-blindness ordering, artifact persistence,
packages frontmatter, and the pinned representativeness caveat are all
addressed. The two remaining points are non-blocking polish, not structural
defects.

---

### claude-p — round 2

**Verdict:** approve-with-comments

Concerns:
- AC7 overclaims what `validate_terse_set_floor` can enforce. *Verified status:
  CODE-VERIFIED — `terse_dataset.py:178-206` shows the validator checks `min_n`,
  multi-repo, and no-domination, but the discordant floor is only REPORTED in
  `FloorResult.discordant_floor`; discordance is a run-time paired-measurement
  property (two arms' buckets) that a static set validator structurally cannot
  check. As worded, the AC is unsatisfiable-as-stated or silently satisfied by
  the report-only field — a no-false-capability wording hazard.*
- AC5 requires `status=PASSED` for each pilot case but states no posture for a
  legitimate typed degrade (e.g. model-unreachable). *Verified status:
  spec-consistency concern (no direct code citation) — flags a gap in the AC's
  own stated close-vs-hold-by-cause discipline rather than a code defect.*
- The DECIDED placeholder rationale is internally slightly off: under the
  spec's own known-versions-set gate, the five `0026/1` placeholder rows load as
  LEGACY rows with defaults and would NOT break AC1's tag enforcement (which
  binds only `0036/1`+ rows). *Verified status: verified by applying the spec's
  own gate logic as specified in round 1's resolution — the replacement
  decision itself is right, but the stated reason for it is not.*

Suggestions:
- Reword AC7 to split enforcement altitude: `validate_terse_set_floor` enforces
  min_n/multi-repo/no-domination statically and CARRIES the discordant-floor
  constant; the discordant floor itself is enforced at measurement time by
  `decide_ac8` (pilot) and the bake-off's paired comparison — or extend the
  validator only for what is statically checkable.
- Add one sentence to AC5 naming the degraded-pilot-case posture: a typed
  degrade is recorded per case (cause taxonomy), does not count as
  verifier-clean, and triggers either a bounded re-run or a recorded exclusion —
  never silent acceptance and never a masked capability finding (the 0026
  degrade-masks-outcome trap).
- Fix the DECIDED rationale to the accurate reason: placeholders are replaced
  because placeholder queries (`gold_withheld:false`) would pollute the floor
  count and cannot serve as pilot cases — not because they would fail AC1
  validation, which the legacy gate prevents.
- State explicitly that the mechanical reachability check, if it lands as code
  in `harpyja/eval`, inherits the 0026 non-product posture (AST-guarded, no
  `ModelGateway` import) — one sentence, since it computes over gold spans as an
  operator-side step.

Guardrail violations: none. Convention violations: none.

Discussion (abridged, faithful): the revision resolves both round-1 structural
contradictions and all 11 action items — VERIFIABLY (spot-checked
`dataset.py:123` exact-match `is_terse`, `report.py:41` caveat, the AC8 frozen
config, `assert_author_input_blind`, `_KNOWN_VERIFIER_SCHEMA_VERSIONS`,
`live_artifacts` — all exist as cited). The one real remaining defect was AC7's
precision (the validator only CARRIES `discordant_floor`; enforcing it
statically is impossible — a no-false-capability wording hazard).
Approve-with-comments rather than changes-requested because none of the three
concerns is structural: invariants are now internally consistent,
pre-registration binding is pinned tighter than round 1 asked, OQ3's
reportability floor is genuinely pre-declared (≥5 full / ≥2 pilot,
UNDER-POPULATED as a typed finding), and tag-blindness ordering closes the
leakage side-channel. Zero guardrail violations; both round-1 convention
violations resolved by the mechanisms the conventions themselves prescribe.

---

### Applied post-verdict

All five round-2 comments were folded into `spec.md` by the orchestrator
immediately after both verdicts landed, before this review record was
finalized:

1. Concept-vs-patch per-row shape pinned in the invariant: mandatory
   `concept_patch_relation` (`same` | `divergent`) on every 0036/1 row; only
   `divergent` rows carry `concept_span` + `concept_span_provenance`
   (conditionally required there, absent otherwise). [codex c2/s2]
2. AC7 rewritten to split enforcement altitude: validator statically enforces
   min_n/multi-repo/no-domination and CARRIES `MIN_DISCORDANT_PAIRS=8`; the
   discordant floor is enforced by `decide_ac8` + the bake-off's paired
   comparison; the full set must ALSO meet the governing frozen config's
   `full_n_target` (upward-only). [codex c1/s1 + claude-p c1/s1]
3. AC5 degraded-case posture added: typed environment degrade recorded per case
   by cause, not verifier-clean, bounded re-run or recorded exclusion — never
   silent acceptance. [claude-p c2/s2]
4. DECIDED placeholder rationale corrected: legacy rows load fine under the
   gate; replacement is because placeholder queries can't serve as pilot cases
   and would pollute the floor count. [claude-p c3/s3]
5. Mechanical reachability check posture: inherits the 0026 non-product,
   operator-side posture (no `ModelGateway` import, structurally unreachable
   from authoring/SUT paths). [claude-p s4]

---

### Final outcome

**Quorum: MET** (both reviewers independently returned
`approve-with-comments` in round 2; no reviewer returned `reject` in either
round). None of the round-2 concerns was structural — all five were folded
into `spec.md` post-verdict per the list above, so the reviewed artifact
already reflects the fixes.

**Spec status: `reviewed`.** Spec 0036 advances from `draft` (round 1) through
revision to `reviewed` (round 2), with a full two-round record preserved above.

**Next step:** `/speccraft:spec:plan`
