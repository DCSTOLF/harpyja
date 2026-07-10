---
spec: "0036"
closed: 2026-07-09
---

# Changelog — 0036 terse-query (representative terse-query eval set: the populated cases)

## Epistemic status (read this first — the closing verdict, carried verbatim-faithful)

Spec 0036 SHIPPED the populated eval set — the cases the last dozen specs cleared
the runway for. Two outcomes, both recorded honestly, neither papered:

- **Pilot gate: PROCEED on REAL signal.** `qwen3:14b` 5/10 (1 correct, 4
  right-file-wrong-span) vs `qwen3:4b-instruct` 0/10 (honest empties). 20 durable
  verifier artifacts, schema `0034/1`, all `PASSED`, AC5-pinned. This is the FIRST
  clean capability contrast in the project — the instrument is trustworthy (the whole
  point of 0031→0035), and the pilot proves it.
- **Full set: UNDER-POWERED AT THE FROZEN TARGET — RECORDED, NOT PAPERED.** The
  committed 50-case raw pool is exhausted: 36 attempts → 19 blind-clean (17
  leaky-dropped, 14 blind-ineligible because the issue text NAMES the gold path). The
  frozen `full_n_target=30` is UNREACHABLE from this pool. The static floor still
  passes (19 ≥ 12, 11 repos, ≤ 3/repo) but `representative_at_frozen_target: false`,
  test-pinned to computed truth. Enlarging the pool is a FUTURE audited convert step —
  never a re-derived target.
- **The leakage guard proved necessary LIVE**, not just in theory:
  `assert_author_input_blind` stopped `django-12774`; 14 path-naming cases were
  rejected. Without the protocol they'd have measured PATH-READING, not localization.
- **Reachability sample is conceptual-heavy: 4 lexical / 15 conceptual** — the
  astropy-shape (concept ≠ patch, structurally-navigated gold) is the MAJORITY, not
  the exception. This is the first frequency evidence for the semantic-tier decision
  (pending bake-off confirmation).
- **Caveats held.** 5/10 is a PILOT SIGNAL, NOT a capability rate — the bake-off
  measures the rate on its own power. Pool-enlargement is a future audited convert
  step, never a re-derived target.

## What shipped vs spec

21/21 tasks; all 7 ACs met at their stated strength (AC7 met-with-a-finding); 1245
passed / 27 skipped; ruff zero-new vs main. This spec builds DATA plus the minimal
validated shape that data requires — no new instrument. The pilot PROCEEDed, so the
full-set phase RAN (T19–T21 executed in their honest form, NOT N/A-by-gate) and hit
pool exhaustion — a finding, not a failure.

### AC1 — cases load with complete provenance, loud version-gate (unit) — MET
`DATASET_SCHEMA_VERSION_0036 = "0036/1"` + `_KNOWN_TERSE_SCHEMA_VERSIONS =
frozenset({"0026/1", "0036/1"})` (`dataset.py`); `is_terse` widened from exact-match
to set membership. Five ADDITIVE `EvalCase` fields (`reachability`,
`reachability_provenance`, `concept_patch_relation`, `concept_span`,
`concept_span_provenance`), all defaulting `None`. `_parse_0036_tags` enforces the
validation matrix loudly: the three axis tags MANDATORY on every `0036/1` row;
`concept_span`(+provenance) REQUIRED iff `concept_patch_relation == "divergent"` and
FORBIDDEN on `same` (a `same` row carrying a span is a contradiction, rejected); bad
enum values rejected; legacy `0026/1` rows keep loading with the new fields defaulted.
Both directions TDD'd in one loader (`test_dataset.py`).

### AC2 — labels join-only; concept span the audited exemption; tags machine-checkable (unit) — MET
Patch-derived `expected_spans` stay JOIN-ONLY from the sha256-pinned raw fixture
(unchanged authority, never re-transcribed — the join's `dataclasses.replace` never
touches the new fields, so `concept_span` is never overwritten). `concept_span` is a
NEW hand-labeled additive field with its own provenance
(`hand-labeled-concept-span`), the named audited exemption mirroring
`classification_provenance = hand-labeled-by-intent`. `terse_reachability.py`
(`classify_reachability`, NEW) makes the reachability tag machine-checkable: it
intersects only the query's CODE-LIKE identifiers (reusing `_IDENTIFIER_RE` /
`_is_code_like` from `terse_dataset`) with the gold-span text — plain-English overlap
deliberately does not count.

### AC3 — leakage guard: blind provenance per case, tag-blindness ordering (unit) — MET, and proved necessary LIVE
Every case carries `query_provenance: "model-authored-blind"` via 0026's two-model
protocol (author `qwen3:14b` ≠ verifier `qwen3:8b`, separate invocations). The two
new tags require gold visibility to compute, so they are computed STRICTLY
POST-AUTHORING by the operator/mechanical check and never enter the author input;
`terse_reachability` inherits the 0026 non-product posture (no `ModelGateway` import,
ast-guarded). The guard EARNED ITS KEEP live: `assert_author_input_blind` stopped
`django-12774` (issue text contained the gold-span path); across the run 14
blind-ineligible path-naming cases were rejected — without the protocol they'd have
measured path-reading, not localization.

### AC4 — pilot gate under the governing frozen+hashed config → PROCEED (integration) — MET
A NEW pre-registered config `PREREGISTERED_AC8_CONFIG_0036` (`ac8_pilot.py`): the 0026
freeze's arm A (`hf.co/Qwen/Qwen3-8B-GGUF:latest`) was verified NOT SERVABLE on the
live stack, so running the old freeze as-frozen was impossible and a silent
substitution under the old hash would be the exact post-hoc steering the freeze
prevents. The new config swaps ONLY the arm identities to servable models with a real
contrast (`qwen3:14b` strong vs `qwen3:4b-instruct` weak); every threshold copied
verbatim; its own `AC8_CONFIG_HASH_0036 =
114574c4ffa16e90fc3e1de54080491e7bfd396bb56952b37c419b16fc0c682a`, committed at
`98ee3d0` BEFORE the pilot fired. `pilot_runner.py` (pure aggregation) built the pairs
and `decide_ac8` returned **PROCEED**: 10 pairs run, 0 excluded, 5 signal-bearing
discordant → projected 15 ≥ 8 (`MIN_DISCORDANT_PAIRS`). Gate artifact
`pilot/gate_report.json` cites the hash.

### AC5 — each pilot case produces a durable verifier-clean artifact (integration) — MET
Each of the 10 pilot cases × 2 arms produced a `status=PASSED` artifact under
`VERIFIER_SCHEMA_VERSION 0034/1` (model identity, tools, reasoning tokens,
submitted/surviving, bucket), persisted durably via the 0035 `live_artifacts` helper
under `eval_work/live_artifacts/pilot_0036/`. 20 durable artifacts, all PASSED, 0
typed degrades excluded — the AC5 integration test
(`test_pilot_cases_produced_verifier_clean_persisted_artifacts`) pins this. Per-(case,
arm) ledger: `pilot/pilot_results.json`. The set drove the real trustworthy instrument
end to end, with evidence that survives the run.

### AC6 — representativeness scope via the pinned caveat (doc) — MET
Stated by the already-pinned `REPRESENTATIVENESS_CAVEAT` (`report.py:41`, stamped into
every report payload): the set fixes the QUERY-SHAPE axis (terse) on documented-OSS
repos; it does NOT fix the codebase-character axis (undocumented legacy); valid for
relative model ranking, not a real-world-legacy performance claim. No parallel
restatement (`close-notes.md`).

### AC7 — full-set floor at the right altitude, plus the frozen target (unit) — MET, with the under-powered finding
`validate_terse_set_floor` STATICALLY enforces `min_n=12` (19 ≥ 12), multi-repo (11
repos), and no-single-repo-domination (≤ 3/repo) — `floor_ok: true`. It CARRIES
`MIN_DISCORDANT_PAIRS=8`; the discordant floor itself stays a run-time paired property
of `decide_ac8` + the bake-off, never claimed statically. Two additive helpers
(`terse_dataset.py`): `meets_full_n_target` and `conceptual_stratum_report`
(pre-declared floors 5 full / 2 pilot, `UNDER_POPULATED` typed). The conceptual
stratum is REPORTABLE (15 ≥ 5). BUT `meets_full_n_target` is **FALSE** at the frozen
`full_n_target=30` — the raw pool is exhausted (see the finding below), so
`representative_at_frozen_target: false`, recorded in `full_set_report.json` and
test-pinned to the computed truth
(`test_committed_full_set_report_matches_computed_truth`).

## The findings (recorded, not papered)

### Finding 1 — raw-pool exhaustion: under-powered at the frozen target
The committed 50-case raw fixture yields only 19 blind-clean cases: 36 authoring
attempts → 17 leaky-dropped (the leakage guard's verdict-as-data) + 14
blind-ineligible (the issue text itself names the gold path — cannot be blind-authored
at all). The frozen `full_n_target=30` is UNREACHABLE from this pool. This is a FINDING
recorded on `full_set_report.json` (`meets_full_n_target: false`,
`representative_at_frozen_target: false`), NOT papered over by re-deriving the target
downward — that would be exactly the post-hoc steering the freeze exists to prevent.
Enlarging the pool is a FUTURE audited convert step (its own spec), never a
re-derived target.

### Finding 2 — the reachability distribution is conceptual-heavy (4 lexical / 15 conceptual)
The natural-sample (never forced-balanced) reachability mix is 4 lexical vs 15
conceptual: the astropy-shape (gold reachable only by structural/conceptual
navigation, not the query's own vocabulary) is the MAJORITY of the set, not the
exception. This is the first FREQUENCY evidence for the semantic/call-graph-tier
decision the project has deferred behind an evidence gate — pending bake-off
confirmation on its own power (this is a pilot-scale observation, not the measurement).

### Finding 3 — the leakage guard is load-bearing, proved live
`assert_author_input_blind` stopped `django-12774` mid-run, and 14 path-naming cases
were rejected as blind-ineligible. This is the protocol catching real leakage on real
issues — without it the set would have silently measured path-reading, not
localization.

## Deviations from plan

- **The pilot ran on the realized 19-case fixture's first 10 cases** — the pilot subset
  was authored FIRST, exactly as the plan sequenced it (Steps 11–17 before the
  conditional full-set phase). Not a deviation in ordering; recorded for provenance.
- **`full_n_target=30` unreachable (pool exhaustion) — T19–T21 completed in their
  HONEST form, not N/A-by-gate.** The pilot PROCEEDed, so the full-set phase RAN; it
  authored what the 50-case pool allowed (19), committed the fixture, and ran the floor
  tests (static floor passes; the frozen-target claim is pinned FALSE). This is the
  under-powered-at-frozen-target FINDING, recorded — the alternative branch
  (UNDER_POWERED_STOP at the pilot gate) did not fire because the pilot showed real
  signal.
- **Two protocol amendments, both recorded query-blind (before any authoring output was
  seen):** (a) a BLIND-ELIGIBILITY precondition — a case whose ISSUE TEXT contains the
  gold-span path cannot be blind-authored at all, so such cases are SKIPPED AND RECORDED
  (exclude-and-count, provenance-of-a-null), never silently dropped; the pre-declared
  selection rule became "per repo, the alphabetically first case whose issue text names
  no gold-span path." (b) the verifier verdict parser was upgraded to FAIL-CLOSED
  explicit-statement parsing after a live ambiguous verdict — an unparsed verbose answer
  would otherwise read as `clean` (fail-open toward keep) by the `verdict == "leaky"`
  equality check.

## Files touched

Product / harness (`harpyja/eval/`):
- `dataset.py` — `DATASET_SCHEMA_VERSION_0036`, `_KNOWN_TERSE_SCHEMA_VERSIONS`, five
  additive `EvalCase` fields, `_parse_0036_tags` validation matrix, `is_terse` widened
  to set membership
- `terse_reachability.py` (NEW) — `classify_reachability`, `MECHANICAL`/`HAND_LABELED`
  (operator-side, no gateway import, ast-guarded)
- `terse_dataset.py` — `meets_full_n_target`, `conceptual_stratum_report`
  (`STRATUM_REPORTABLE`/`STRATUM_UNDER_POPULATED`, floors 5 full / 2 pilot)
- `ac8_pilot.py` — `PREREGISTERED_AC8_CONFIG_0036` + `AC8_CONFIG_HASH_0036` (arms only
  differ; thresholds verbatim; committed at `98ee3d0` before the pilot)
- `pilot_runner.py` (NEW) — `build_pilot_pairs` + `gate_report` (pure aggregation;
  degrade excluded + recorded by cause; a bucket-less arm with no cause raises)
- `fixtures/swebench_verified.terse.jsonl` — 5 placeholder rows REPLACED by 19 real
  blind-authored, tagged `0036/1` rows
- `fixtures/swebench_verified.authoring.json` (NEW) — the committed `AuthoringArtifact`
  (36 records, 17 leaky-dropped)
- tests: `test_dataset.py`, `test_terse_reachability.py` (NEW), `test_terse_floor.py`,
  `test_ac8_pilot.py`, `test_pilot_runner.py` (NEW), `test_terse_join.py`,
  `test_live_verifier_integration.py`

Operator/live scripts + evidence (`specs/0036-terse-query/`):
- `authoring/run_authoring.py`, `authoring/run_fill.py`, `authoring/run_tagging.py`,
  `authoring/authored_queries.json`
- `pilot/run_pilot.py` (resumable ledger), `pilot/gate_report.json`,
  `pilot/pilot_results.json`
- `full_set_report.json`, `close-notes.md`

## ADR proposed for history.md

See the 2026-07-09 entry prepended to `.speccraft/history.md` (Spec 0036).

## Conventions proposed

- New: "A pre-registered selection/eligibility rule may be AMENDED only while still
  OUTCOME-BLIND, and the amendment is RECORDED with its trigger — never a post-hoc
  adjustment after outcomes are seen."
  Rationale: the blind-eligibility amendment (skip cases whose issue text names the
  gold path) and the fail-closed verdict-parser upgrade were both made before any
  authoring output was seen, and recorded; this is what keeps an amendment a protocol
  refinement rather than steering.
- New: "A committed CLAIM file is TEST-PINNED to the computed truth it claims — a
  static assertion re-derives the claim from the data at test time, so a claim can
  never silently drift from what the set actually contains."
  Rationale: `full_set_report.json` (including
  `representative_at_frozen_target: false`) is pinned by
  `test_committed_full_set_report_matches_computed_truth`, so the under-powered finding
  cannot be quietly edited to look representative.
- New: "An under-powered-AT-THE-FROZEN-TARGET result is a RECORDED finding, never
  papered by re-deriving the target — pool enlargement is a separate audited convert
  step."
  Rationale: the 50-pool exhaustion (19 < frozen 30) was recorded on the report and
  named as a future audited convert step, not resolved by lowering `full_n_target`.
