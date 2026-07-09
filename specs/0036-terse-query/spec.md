---
id: "0036"
title: "terse-query"
status: in-progress
started_at_sha: a983bcc
created: 2026-07-09
authors: [claude]
packages: ["harpyja/eval"]
related-specs: ["0026-eval", "0031-live", "0032-trajectory-parser", "0033-scoped-grep-paths", "0034-reasoning-observability", "0035-grep-scope-markers"]
---

# Spec 0036 — terse-query (representative terse-query eval set: the populated cases — bake-off input)

## Why

0026 built the eval-set INSTRUMENT (loader, provenance schema, blind-authoring
protocol, pilot power-gate) but the actual representative cases were never authored —
placeholders only. Every spec since (0027–0035) closed a measurement-integrity gap
that would have corrupted a bake-off run (silent-Tier-0, found-then-dropped,
invisible reasoning, silent-`[]` scopes, lost artifacts); the instrument is now
trustworthy. The last missing input is the cases themselves. This spec authors the
real set so the thinking A/B and the model bake-off finally have representative data
to run on.

This is the spec the last dozen were clearing the runway for. It builds **DATA, not
instrument** — and the reason it can finally produce trustworthy data is that every
way the harness could have lied has been closed.

**Ref:** 0026 (instrument + blind protocol + pilot gate + reachability/scoring
lessons), 0031–0035 (verifier + integrity fixes), the astropy lessons
(lexical-reachability, concept-vs-patch location — the `separability_matrix()` case).

## Invariants

**INVARIANT (build on 0026's instrument, don't rebuild it — schema mechanics
review-resolved):** populate cases through 0026's existing
loader/provenance/blind-authoring machinery. No new authoring tool, no rebuilt
loader. The two mandatory tags (next invariant) land as ADDITIVE `EvalCase` fields
under a NEW gated `DATASET_SCHEMA_VERSION` (`"0036/1"`) per the 0026 version-gate
pattern — the sanctioned mechanism by which additive-defaults (legacy compat) and
reject-if-missing (a new guard) coexist in one loud loader. Code-verified knock-on
(dataset.py:123): terse-branch detection today is an EXACT version match
(`is_terse = schema_version == DATASET_SCHEMA_VERSION`), so the bump widens
detection to a known-versions SET (the `_KNOWN_VERIFIER_SCHEMA_VERSIONS` pattern
from live_verifier) — `0026/1` legacy rows keep loading with the new fields
defaulted; only `0036/1`+ rows are held to AC1's tag-required rule. This spec
produces DATA (authored, tagged cases); the version-gated field additions are the
minimal validated shape that data requires, not new instrument.

**INVARIANT (the two lessons the astropy arc forced — both mandatory tags):**

- **LEXICAL-REACHABILITY of gold:** each case tagged whether the gold span is
  findable by the query's own vocabulary vs. only by structural/conceptual
  navigation. Bake-off results MUST be splittable on this axis, or "models can't
  localize" will confound with "lexical tools can't reach conceptual gold" (the
  RETRIEVAL_FUNDAMENTAL trap). A query whose gold is lexically unreachable will
  defeat ANY grep-anchored model — if the set is unknowingly full of those, the
  bake-off concludes "no model works" when the truth is "these queries need
  structural navigation no current tool provides." Tagging reachability and
  splitting results on it is the difference between "we need a better model" and
  "we need the semantic tier" — and it is the axis that finally MEASURES THE
  FREQUENCY of astropy-shaped cases, the evidence-gate the call-graph tier has been
  deferred behind. The tag carries per-case provenance (`mechanical` |
  `hand-labeled`) so OQ2's mixed strategy is auditable.
- **CONCEPT-vs-PATCH gold (storage review-resolved):** where the query's honest
  answer (the function that computes X) differs from the patch span (where the fix
  landed), record both — the patch-derived label stays JOIN-ONLY from the
  sha256-pinned raw fixture (unchanged authority, unchanged source, never
  re-transcribed); the concept span is a NEW, hand-labeled, ADDITIVE field carrying
  its own provenance tag — a deliberate, named, audited exemption from
  span-reproducibility, mirroring the existing
  `classification_provenance = "hand-labeled-by-intent"` precedent — so the
  BAKE-OFF's scoring can split/credit on this axis (the `separability_matrix()`
  case). Scoring-behavior changes stay out of scope here: this spec records the
  tag; the bake-off consumes it. Per-row shape pinned (round-2 review): every
  `0036/1` row carries a MANDATORY `concept_patch_relation` tag
  (`same` | `divergent`); only `divergent` rows carry the additional
  `concept_span` + `concept_span_provenance` fields (conditionally REQUIRED there,
  absent otherwise) — the mandatory axis tag and the optional span are two
  different validation contracts, both loud.

**INVARIANT (leakage guard — reused, not reinvented; tag-blindness ordering
pinned):** terse queries authored from issue INTENT with the gold span withheld,
via 0026's two-author blind protocol (author model ≠ verifier model, separate
invocation), provenance recorded per case. A query encoding gold-span vocabulary is
flagged. Both new tags require gold-span visibility to compute (the mechanical
reachability check literally intersects query tokens with the gold span), so
tagging happens STRICTLY POST-AUTHORING, by the operator/mechanical check — the tag
and the gold are NEVER visible to the author model, and the recorded author input
remains covered by `assert_author_input_blind` (extended to the new surface if the
tagging step touches the recorded input; otherwise its coverage is asserted
unchanged). If the mechanical reachability check lands as code in `harpyja/eval`,
it inherits the 0026 non-product posture (operator-side eval machinery: no
`ModelGateway` import, outside the product runtime) — it computes over gold spans
and must stay structurally unreachable from the authoring or SUT paths.

**INVARIANT (pilot-gated authoring — pre-registration binding review-resolved):**
author the pilot subset FIRST, run it through the (now trustworthy) harness +
verifier, and gate on 0026's frozen machinery: `decide_ac8` under a pre-registered
frozen+hashed config, UNDER_POWERED_STOP semantics intact. The committed
`PREREGISTERED_AC8_CONFIG` froze reference arms `Qwen3-8B` vs `qwen3:4b-instruct`
(pilot_n=10, full_n_target=30, min_discordant_pairs=8, `config_hash`); the current
live stack runs `qwen3:14b` — IF the pilot arms deviate from the frozen config in
ANY field (reference models, think knob, pilot N, full_n_target, projection rule),
a NEW frozen+hashed config is committed BEFORE the pilot fires (arm choice decided
at plan; the RULE is pinned here). Re-sizing the full-set target after seeing pilot
data without re-registering is post-hoc steering of the very gate the freeze
protects — sizing UPWARD of the frozen target post-PROCEED is permitted;
re-deriving the target is not. Authoring 20–40 blind cases is real work; the pilot
is the cheap-check-before-expensive-authoring discipline applied to human/agent
effort. UNDER-POWERED is a legitimate finding, not a failure, exactly as it was in
the 0023 dead-end. The full set MUST NOT be authored before the pilot proves the
set is powerable.

**DECIDED (placeholder fixture fate):** the five committed `0026/1` PLACEHOLDER
rows in `swebench_verified.terse.jsonl` (query "PLACEHOLDER pending offline blind
authoring", `gold_withheld: false`) are REPLACED by the real, blind-authored pilot
cases in the same change, with the join/floor tests updated in the same commit.
Rationale (corrected in round-2 review): under the known-versions gate the legacy
rows would load fine with defaults and never trip AC1 — they are replaced because
placeholder queries (`gold_withheld: false`, no blind authoring) cannot serve as
pilot cases and would pollute the floor count if left beside real rows.

## What

- Bump the terse dataset schema (`0036/1`, known-versions-set detection) with the
  two additive tag fields + their provenance fields; loud AC1 validation for
  `0036/1`+ rows; legacy rows keep loading with defaults.
- Author the pilot subset of representative terse-query cases through 0026's blind
  protocol (replacing the five placeholder rows); tag post-authoring; run it
  end-to-end through the harness + verifier; gate via `decide_ac8` under the
  governing frozen config (existing or newly pre-registered BEFORE the pilot — at
  plan).
- On PROCEED, author the full set (count/spread sized from the pilot's measured
  per-case cost and reachability distribution, at-or-above the frozen target —
  OQ1); on STOP, report UNDER-POWERED as the finding.
- Tag every case with lexical-reachability (mechanical where possible, per-case
  provenance — OQ2) and concept-vs-patch gold (hand-labeled additive span with its
  own provenance), with blind-authoring provenance per case.
- Labels reused verbatim from the sha256-pinned patch-derived source — never
  re-transcribed.
- Enforce the full-set floor (`validate_terse_set_floor`: min_n, discordant floor,
  multi-repo/no-domination) before the set is called representative (AC7).
- State the representativeness scope honestly via the pinned caveat (AC6).

## Acceptance Criteria ([unit]=fakes; [integration]=live, skip-not-fail)

1. [unit] Cases load through 0026's loader with complete provenance
   (blind-authoring fields, reachability tag + tag provenance, concept-vs-patch
   tag) validated — a `0036/1` case missing any required tag is rejected loudly;
   legacy `0026/1` rows keep loading with the new fields defaulted
   (known-versions-set gate pinned both directions).
2. [unit] Labels reused verbatim from the sha256-pinned patch-derived source (not
   re-transcribed); the concept span, where present, is a separate hand-labeled
   field with its own provenance tag (never overwriting the joined label);
   reachability + concept/patch tags machine-checkable.
3. [unit] Leakage guard: blind-authoring provenance present per case; a
   gold-vocabulary-encoding query is flagged (0026's two-model protocol, recorded);
   tag-blindness ordering pinned — the recorded author input contains neither tag
   nor gold (`assert_author_input_blind` coverage over the new surface asserted).
4. [integration] Pilot subset authored + run through the harness/verifier;
   `decide_ac8` under the governing pre-registered frozen+hashed config (cited by
   hash in the artifact) returns PROCEED, OR the set is reported UNDER-POWERED via
   UNDER_POWERED_STOP (a finding, not a forced full authoring).
5. [integration] Each pilot case produces a verifier-clean artifact
   (`status=PASSED`, `VERIFIER_SCHEMA_VERSION 0034/1`: model identity, tools,
   reasoning tokens, submitted/surviving, bucket), written durably via the 0035
   `live_artifacts` helper (`eval_work/live_artifacts/...`) — proving the set
   drives the real trustworthy instrument end to end, with evidence that survives
   the run. Degraded-case posture (round-2 review): a typed environment degrade
   (e.g. model-unreachable) is recorded per case by cause, does NOT count as
   verifier-clean, and triggers a bounded re-run or a recorded exclusion — never
   silent acceptance, never a masked capability finding.
6. [doc] Representativeness scope stated via the pinned
   `REPRESENTATIVENESS_CAVEAT` (report.py:41, already stamped into report
   payloads): fixes the QUERY-SHAPE axis (terse) on documented-OSS repos; does NOT
   fix the codebase-character axis (undocumented legacy) — valid for relative model
   ranking, not a real-world-legacy performance claim. No parallel restatement.
7. [unit] Full-set floor enforced at the right altitude (round-2 review):
   `validate_terse_set_floor` STATICALLY enforces min_n=12, multi-repo, and
   no-single-repo-domination on the full authored set, and CARRIES the
   discordant-floor constant (`MIN_DISCORDANT_PAIRS=8`) — the discordant floor
   itself is a run-time paired-measurement property enforced by `decide_ac8`
   (pilot) and the bake-off's paired comparison, never claimable from a static
   set. The full set must ALSO meet the governing frozen config's full-set target
   (`full_n_target`, upward-only per the pilot invariant) before being called
   representative.

## Out of Scope

- The model bake-off (runs on this).
- The thinking A/B (runs on this).
- The think-knob spec.
- Building a legacy/undocumented-codebase eval set (the deferred Axis-2 problem).
- Any harness/verifier/scoring behavior change (0027–0035 done; the concept tag's
  scoring consumer is the bake-off).
- A semantic/call-graph tier.

## Open Questions

1. Case count + repo spread for the FULL set (post-pilot): the ~20–40
   paired-ranking target vs wall-clock (~200s/case with reasoning on). Coarse pilot
   first, size the full set from the pilot's measured per-case cost and
   reachability distribution — at or above the governing frozen config's
   full-set target (upward-only post-PROCEED; see the pilot invariant).
2. Reachability-tag source: hand-labeled per case, or a mechanical check (does the
   gold span contain query tokens)? Lean mechanical where possible (reproducible,
   unbiased), hand-label only the ambiguous; either way the per-case tag
   provenance (`mechanical` | `hand-labeled`) is recorded.
3. Target reachability mix: deliberately balance lexically-reachable vs conceptual
   cases, or sample naturally and report whatever mix results? Lean
   natural-sample-then-report (a forced balance biases the distribution the
   bake-off is trying to measure). PRE-DECLARED reportability floor (fixed here,
   before any sample is drawn): the conceptual (lexically-unreachable) stratum
   must hold ≥ 5 cases in the full set (≥ 2 in the pilot) for the axis to be
   reported as a split; below that the axis is reported UNDER-POPULATED (a
   finding — the split would be anecdotal), never silently merged into the
   aggregate.
