---
spec: "0026"
closed: 2026-07-06
---

# Changelog — 0026 eval (terse-query eval set — ranking instrument for the model bake-off)

## Honest state (read this first)

**Infrastructure is complete; the eval set is NOT yet authored; the ranking
instrument is NOT yet usable.** The committed `swebench_verified.terse.jsonl` carries
five PLACEHOLDER cases (`query: "PLACEHOLDER pending offline blind authoring"`,
`gold_withheld: false`, `query_provenance: "placeholder-pending-offline-authoring"`) —
a unit-test JOIN target, not a real eval set. The **offline two-model blind-authoring
pilot is the REMAINING DELIVERABLE, not a formality**: real blind-authored queries
(`gold_withheld: true`, `query_provenance: "model-authored-blind"`) land only via the
delegated offline operator activity (Steps 10/18), which has not run.

**AC8's likely `UNDER_POWERED_STOP` is a SCOPED FINDING, not a rerun-until-it-passes
loop.** When the pilot fires, a STOP means "these two general reference candidates
(`hf.co/Qwen/Qwen3-8B-GGUF:latest` vs `qwen3:4b-instruct`) under-power terse-query
ranking at 0023's near-zero-localization floor" — a valid typed deliverable naming the
finder-capability next step (`N38_PLUS_FINDER_CAPABILITY`), NOT a signal to keep
re-running two arms until a clean number appears. The frozen, hashed
`PREREGISTERED_AC8_CONFIG` is what makes the STOP a legitimate close rather than a
tuned-until-favorable result.

## What shipped vs spec

All unit ACs green (suite 1010 pass / 45 integration deselected, ruff clean). AC1–AC5
and AC7 are unit-complete; AC6/AC8 are unit-covered with fakes, with the live run
correctly `@pytest.mark.integration` (skip-not-fail on CI; the deliverable run fails
loud under `HARPYJA_REQUIRE_LIVE_STACK=1`) — a delegated operator deliverable.

- **AC1 — labels JOINED, never transcribed.** `terse_dataset.load_terse_dataset`
  asserts `sha256(raw.jsonl) == provenance.raw_fixture_sha256` FIRST (`assert_raw_pin`,
  refusing to join against an unverified source), then joins `expected_spans` /
  `base_commit` / source-issue text by `case_id` from the pinned
  `swebench_verified.raw.jsonl`. The terse fixture stores NO spans. Label provenance is
  `patch-derived-at-convert` (the deterministic `parse_patch` output frozen at the
  audited network `convert` stage — never "human-confirmed", never re-derived; no gold
  patch is committed).
- **AC2 — two-layer leakage guard.** Layer (a): `compute_leaked_tokens(query,
  source_issue)` is a near-vacuous code-identifier tripwire recomputed against the
  JOINED raw `query` (a stored `leaked_tokens` value is ignored). Layer (b): the
  load-bearing proof is carried in a loud-validated `authoring_provenance.py` sidecar
  (`AuthoringRecord` / `AuthoringArtifact` / `AuthoringError`, `AUTHORING_SCHEMA_VERSION
  = "0026/1"`, verdict/outcome enums validated, hash-consistency enforced) with
  aggregate `leaky_count` / `dropped_count`; pin (2) blindness is the OPERATIONAL
  `assert_author_input_blind(record, expected_spans)` (the recorded author input
  contains none of the gold path or `path:line` citation forms). The offline tool
  `terse_authoring.py` (`author_terse_case` / `author_terse_set`) takes INJECTED
  `author_invoke` / `verifier_invoke` callables (separately-invoked model contexts),
  withholds the gold span, and routes a `leaky` verdict to drop (never a silent keep).
- **AC3 — additive validated fields under a NEW gated schema version.**
  `dataset.DATASET_SCHEMA_VERSION = "0026/1"` (introduced, not bumped — distinct from
  `report.SCHEMA_VERSION`); `EvalCase` gained additive last-with-defaults
  `schema_version` / `label_provenance` / `query_provenance` / `gold_withheld` /
  `leaked_tokens` / `classification_provenance`; `_parse_case` version-gates the guard
  (`_parse_terse_guard`) so terse rows may omit spans but MUST carry the guard, while
  legacy rows keep the original non-empty-`expected_spans` contract. `base_commit` stays
  a raw-record key (review B2) — exposed via `JoinMeta`, NOT promoted onto `EvalCase`.
- **AC4 — size/pairing floor cites committed constants.** `validate_terse_set_floor`
  references `benchmark_fit.PREREGISTERED_CONFIG.min_n == 12` and
  `MIN_DISCORDANT_PAIRS == 8` (no re-declared magic numbers), and fails a single-repo
  dominated set. Known-correct-span-only exclusion records a labeled `excluded_count` /
  `excluded_case_ids` (provenance-of-a-null), never a silent drop.
- **AC5 — loud loader covers the guard without breaking legacy.** A terse case missing
  a guard field raises `DatasetError`; a legacy (untagged) case still loads — both
  asserted in one loader call.
- **AC7 — pinned representativeness caveat + schema bump.** `report.SCHEMA_VERSION`
  `0025/1 → 0026/1`; new `run_metadata.representativeness_caveat` (constant
  `REPRESENTATIVENESS_CAVEAT`, centralized in `_RUN_METADATA_DEFAULTS`) naming the
  QUERY-SHAPE-fixed / codebase-character-and-Python-monoculture-NOT scope; legacy blocks
  still validate.
- **AC8 — frozen/hashed pilot power-gate.** `ac8_pilot.py`: `PREREGISTERED_AC8_CONFIG`
  (frozen; two reference models, `pilot_n=10`, `full_n_target=30`, `min_discordant_pairs`
  reusing `PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS`) + `AC8_CONFIG_HASH`;
  signal-bearing-flip = arms disagree on whether they LOCATED (empty↔wrong-file excluded
  as noise); total pure `decide_ac8` / `project_flips` / `Ac8Outcome ∈ {PROCEED,
  UNDER_POWERED_STOP}` (`UNDER_POWERED_STOP.next_step()` names the finder-capability work).
- **AC6/AC8 drivers.** `terse_probe.py` `run_terse_locate_probe` / `run_ac8_pilot`
  delegate to the UNCHANGED `run_locate_probe` / `score_distribution` (no forked
  scoring), per-arm via `dataclasses.replace(settings, lm_model=…)`, provisioning
  injected as a `provision` callable (harness stays read-only on targets).

## Deviations (two, recorded)

- **T19 sha256-hoist DEFERRED.** Hoisting the 3-line `_sha256_file` into one shared
  helper used by both `terse_dataset` and `swebench_eval._load_resolved` would couple
  the lightweight loader to the heavy HuggingFace-`datasets`-importing `swebench_eval`
  module for three lines. The one-oracle reuse pin was done instead
  (`test_ac8_uses_same_oracle_buckets_as_locate_accuracy` proves AC8's "located"
  predicate is exactly `locate_accuracy`'s file-level credit buckets); `terse_dataset`
  keeps its own local `_sha256_file`.
- **Committed terse fixture is placeholders** (see Honest state) — real blind-authored
  queries land via the delegated offline pilot; the token flag recomputes against the
  joined raw issue regardless of the placeholder.

## Refinement over plan wording (not a deviation)

The plan's Decision 1 split held: per-case DATASET guard fields on `EvalCase`,
operator-produced AUDIT metadata in the `authoring_provenance.py` sidecar. One
refinement — `AuthoringRecord` stores the full `author_input` text (not only its hash)
so pin (2)'s `assert_author_input_blind` runs on real content, with hash-consistency
validated. This strengthens the pin the spec required.

## Files touched

- `harpyja/eval/dataset.py` (modified — `DATASET_SCHEMA_VERSION`, additive `EvalCase`
  guard fields, version-gated `_parse_case` + `_parse_terse_guard`)
- `harpyja/eval/terse_dataset.py` (new — join loader, token tripwire, floor validator)
- `harpyja/eval/authoring_provenance.py` (new — loud-validated sidecar + pin-2)
- `harpyja/eval/terse_authoring.py` (new — offline two-model tool, injected seam)
- `harpyja/eval/ac8_pilot.py` (new — frozen/hashed pilot config + `decide_ac8`)
- `harpyja/eval/terse_probe.py` (new — AC6/AC8 drivers over unchanged `run_locate_probe`)
- `harpyja/eval/report.py` (modified — `SCHEMA_VERSION 0026/1`, `representativeness_caveat`)
- `harpyja/eval/fixtures/swebench_verified.terse.jsonl` (new — PLACEHOLDER join target)
- `harpyja/eval/test_dataset.py`, `harpyja/eval/test_report.py` (modified — schema-gate + caveat)
- `harpyja/eval/test_terse_join.py`, `test_terse_guard.py`, `test_terse_floor.py`,
  `test_authoring_provenance.py`, `test_terse_authoring.py`, `test_ac8_pilot.py`,
  `test_terse_probe_integration.py` (new)

## Follow-ups carried forward

- **The offline blind-authoring pilot (real queries) + the live AC8 go/no-go run** — the
  pending operator deliverable that makes the instrument usable.
- The model bake-off itself (this spec builds its instrument).
- The finder-capability work (`N38_PLUS_FINDER_CAPABILITY`) from 0022/0023.
- The deferred Axis-2 problems: a legacy/undocumented codebase eval AND a non-Python
  eval (codebase-character + the Python language monoculture).
- OQ2/threshold tuning; the Tier-0 symbol tool.
