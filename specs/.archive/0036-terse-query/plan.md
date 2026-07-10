---
spec: "0036"
status: planned
strategy: tdd
---

# Plan — 0036 terse-query (representative terse-query eval set: the populated cases)

## Shape of this spec

0036 produces **DATA plus the minimal validated shape that data requires** — no new
instrument. The code footprint is small and additive; the bulk of the work is
offline operator/live authoring + a gated pilot run. The plan front-loads all
pure-unit RED/GREEN pairs (schema fields, mechanical reachability, floor helpers,
the new pre-registered pilot config, the pilot-aggregation glue), then sequences the
expensive offline/live steps (blind authoring, fixture replacement, the ~35-min
pilot run, the `decide_ac8` gate) late and batched, and makes the entire full-set
phase explicitly conditional on the pilot returning PROCEED.

## Decision — pilot config: option (b), a NEW pre-registered frozen+hashed config

**Decision: (b) — commit a new frozen+hashed `Ac8PilotConfig` before any pilot run.**

Rationale (grounded against the live stack, `127.0.0.1:11434/api/tags`):

- The committed `PREREGISTERED_AC8_CONFIG` (ac8_pilot.py:56) freezes
  `reference_model_a = "hf.co/Qwen/Qwen3-8B-GGUF:latest"` and
  `reference_model_b = "qwen3:4b-instruct"`. The live Ollama stack **does not serve
  `hf.co/Qwen/Qwen3-8B-GGUF:latest`** — arm A is not servable as frozen. (Arm B,
  `qwen3:4b-instruct`, IS served.)
- Running the pilot on the frozen config as-is is therefore impossible without
  provisioning a model the stack does not have; substituting a live model silently
  under the old hash is exactly the post-hoc steering the freeze exists to prevent.
- So we PRE-REGISTER a new config `PREREGISTERED_AC8_CONFIG_0036` with a real
  capability contrast drawn from servable models: `reference_model_a = "qwen3:14b"`
  (strong) vs `reference_model_b = "qwen3:4b-instruct"` (weak). Every OTHER frozen
  field is copied verbatim — `pilot_n=10`, `full_n_target=30`,
  `min_discordant_pairs=8` (still `PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS`). Only
  the arm identities change, to what is actually servable.
- This new config gets its own `config_hash` and is **committed (T7/T8) strictly
  BEFORE the pilot-run task (T15)** — the freeze predates the data. The pilot
  artifact cites the new hash. `full_n_target` may be sized UPWARD post-PROCEED but
  never re-derived (per the pilot invariant).

## Schema-bump design (AC1/AC2)

Mirror the `live_verifier` known-versions-set pattern
(`_KNOWN_VERIFIER_SCHEMA_VERSIONS`) in `dataset.py`:

- Keep `DATASET_SCHEMA_VERSION = "0026/1"` UNCHANGED (it is what the blind-authoring
  tool stamps for a freshly-authored, not-yet-tagged case, and existing tests pin
  it). Add `DATASET_SCHEMA_VERSION_0036 = "0036/1"` and
  `_KNOWN_TERSE_SCHEMA_VERSIONS = frozenset({"0026/1", "0036/1"})`.
- Widen the terse-branch detection at dataset.py:123 from exact-match
  (`schema_version == DATASET_SCHEMA_VERSION`) to
  `schema_version in _KNOWN_TERSE_SCHEMA_VERSIONS`. Both legacy `0026/1` and new
  `0036/1` rows load down the terse branch (spans join-only, guard fields enforced);
  legacy rows keep loading with the new fields defaulted.

New additive `EvalCase` fields (all `... = None`/absent by default, backward-compat):

| field | type | values | contract |
|---|---|---|---|
| `reachability` | str\|None | `lexical` \| `conceptual` | MANDATORY on 0036/1 |
| `reachability_provenance` | str\|None | `mechanical` \| `hand-labeled` | MANDATORY on 0036/1 |
| `concept_patch_relation` | str\|None | `same` \| `divergent` | MANDATORY on 0036/1 |
| `concept_span` | ExpectedSpan\|None | one span | REQUIRED iff `divergent`, else ABSENT |
| `concept_span_provenance` | str\|None | non-empty (e.g. `hand-labeled-concept-span`) | REQUIRED iff `divergent`, else ABSENT |

Validation matrix (the loud loader, all raise `DatasetError`):

| version | reachability / provenance | concept_patch_relation | concept_span(+prov) |
|---|---|---|---|
| `0026/1` (legacy) | absent → defaults None | absent → default None | absent → default None |
| `0036/1`, missing either tag | REJECT | REJECT | — |
| `0036/1`, `relation=same` | required | required | MUST be absent (REJECT if present) |
| `0036/1`, `relation=divergent` | required | required | both required (REJECT if missing) |
| any version, bad enum value | REJECT | REJECT | REJECT |

Label authority is untouched: patch-derived `expected_spans` stay JOIN-ONLY from the
sha256-pinned `raw.jsonl`; `concept_span` is the named, audited hand-labeled
exemption (mirrors `classification_provenance = hand-labeled-by-intent`). The join
in `load_terse_dataset` already uses `dataclasses.replace` on only
`expected_spans`/`label_provenance`/`leaked_tokens`/`classification_provenance`, so
the new fields pass through the join untouched and `concept_span` is never
overwritten — no join-code change is needed for preservation (asserted by
fixture-backed tests, not a vacuous unit pair).

## Mechanical reachability check (AC2, OQ2) — operator-side, non-product

A new pure module `harpyja/eval/terse_reachability.py`: `classify_reachability(query,
span_text) -> ("lexical" | "conceptual")` — intersects the query's code-like
identifier tokens (reuse `_is_code_like`/`_IDENTIFIER_RE` semantics from
terse_dataset) with the gold-span source text; `lexical` when the gold span contains
a query code-token, else `conceptual`. Provenance constants `MECHANICAL` /
`HAND_LABELED`. Pure, no I/O, **no `ModelGateway` import** — pinned by an
ast-import-absence guard test exactly like `terse_authoring` (inherits the 0026
non-product posture: computes over gold spans, structurally unreachable from
authoring/SUT). It runs STRICTLY POST-AUTHORING (needs gold visibility) and is never
surfaced to the author model.

## Floor helpers (AC7, OQ3)

`validate_terse_set_floor` already enforces `min_n=12` / multi-repo / no-domination
and CARRIES `MIN_DISCORDANT_PAIRS=8` (discordance stays a run-time paired property of
`decide_ac8` + the bake-off — never claimed statically). Two additive helpers in
`terse_dataset.py`:

- `meets_full_n_target(dataset, cfg) -> bool` — the full set must ALSO clear the
  governing frozen config's `full_n_target` (upward-only).
- `conceptual_stratum_report(dataset) -> (lexical_n, conceptual_n, status)` — counts
  the reachability strata; `status = UNDER_POPULATED` when the conceptual stratum
  holds < 5 (full) / < 2 (pilot), a typed finding, never silently merged.

## Authoring pipeline (AC3, leakage guard)

Offline OPERATOR steps via 0026's existing machinery (author model ≠ verifier model,
separate invocations; `assert_author_input_blind` covers the recorded author input;
Ollama live at 127.0.0.1:11434). Ordering is pinned: (1) blind-author the terse
query from issue INTENT with the gold span withheld → `author_terse_set` +
committed `AuthoringArtifact`; (2) ONLY THEN, operator runs the mechanical
reachability check + hand-labels concept-vs-patch, assembling the final `0036/1`
rows. The two new tags require gold visibility, so they are computed strictly
post-authoring and never enter the author input. Per the user's standing directive,
authoring/live steps STOP-AND-WARN on infra error — they do not skip.

## Fixture replacement

The five `0026/1` PLACEHOLDER rows (`gold_withheld: false`) in
`swebench_verified.terse.jsonl` are REPLACED by the real blind-authored, tagged
`0036/1` pilot rows in the same change; the join/floor fixture-backed tests are
updated in the same commit. (Legacy rows would load fine under the known-set gate;
they are replaced because placeholder queries cannot serve as pilot cases and would
pollute the floor count — the corrected DECIDED rationale.)

## Pilot-run procedure (AC4, AC5) — late, batched, ~35+ min live

Per pilot case: `run_verified_case(...)` → `VerifierResult` + artifact, persisted
durably via the 0035 `write_live_artifact` helper
(`eval_work/live_artifacts/...`), `VERIFIER_SCHEMA_VERSION 0034/1`, expecting
`status=PASSED` (model identity, tools, reasoning tokens, submitted/surviving,
bucket). Degraded-case posture: a typed environment degrade (e.g. model-unreachable)
is recorded per case BY CAUSE, does NOT count as verifier-clean, and triggers a
bounded re-run or a recorded exclusion — never silent acceptance, never a masked
capability finding. A pure `pilot_runner` helper maps per-case buckets → `PilotPair`
list (degrades excluded + recorded) and calls `decide_from_pairs` under
`PREREGISTERED_AC8_CONFIG_0036`; the gate artifact cites the config hash and records
PROCEED or UNDER_POWERED_STOP.

## Conditional full-set phase (AC7)

Full-set authoring runs ONLY if the pilot returns PROCEED. On PROCEED: author the
full set at-or-above `full_n_target=30` (upward-only), tag it, enforce
`validate_terse_set_floor` + `meets_full_n_target` + the conceptual-stratum
reportability floor, update floor tests, commit. On UNDER_POWERED_STOP: that IS a
valid deliverable — the spec closes with the finding, and the full-set tasks
(T19–T21) are marked N/A-by-gate, not executed.

## Test-first sequence

### Step 1 — schema fields + known-set gate (RED)
- Add to `harpyja/eval/test_dataset.py`:
  - `test_dataset_known_terse_schema_versions_set` — 0026/1 and 0036/1 both detected terse.
  - `test_parse_case_0036_requires_reachability_and_provenance` — missing either → `DatasetError`.
  - `test_parse_case_0036_requires_concept_patch_relation` — missing → `DatasetError`.
  - `test_parse_case_0036_divergent_requires_concept_span_and_provenance` — divergent w/o span → reject.
  - `test_parse_case_0036_same_forbids_concept_span` — `same` + concept_span present → reject.
  - `test_parse_case_0036_rejects_bad_tag_enums` — bad reachability/provenance/relation value → reject.
  - `test_legacy_0026_row_defaults_new_fields` — 0026/1 row loads, new fields None.
- Tests fail: `EvalCase` has no reachability/concept fields; `is_terse` is exact-match; no 0036 validation exists.

### Step 2 — dataset.py schema shape (GREEN)
- Implement in `harpyja/eval/dataset.py`: `DATASET_SCHEMA_VERSION_0036`,
  `_KNOWN_TERSE_SCHEMA_VERSIONS`, widen `is_terse` to set membership, add the five
  additive `EvalCase` fields, extend the terse-guard parse to enforce the 0036
  validation matrix (reachability + provenance + concept_patch_relation mandatory;
  concept_span/provenance conditionally required on `divergent`, forbidden on `same`).
- All Step-1 tests pass; existing 0026 tests stay green (`DATASET_SCHEMA_VERSION` unchanged).

### Step 3 — mechanical reachability check (RED)
- Add `harpyja/eval/test_terse_reachability.py`:
  - `test_classify_reachability_lexical_when_span_contains_query_token`
  - `test_classify_reachability_conceptual_when_no_shared_code_token`
  - `test_reachability_provenance_constants`
  - `test_reachability_module_is_not_product_runtime` — ast guard: no `ModelGateway`/`harpyja.gateway` import; no product module imports it.
- Tests fail: module `terse_reachability` does not exist.

### Step 4 — terse_reachability.py (GREEN)
- Implement `harpyja/eval/terse_reachability.py`: pure `classify_reachability`,
  `MECHANICAL`/`HAND_LABELED` constants, no I/O, no gateway import.
- All Step-3 tests pass.

### Step 5 — full-set + conceptual-stratum floor helpers (RED)
- Add to `harpyja/eval/test_terse_floor.py`:
  - `test_full_set_meets_frozen_full_n_target` — 30-case synthetic set clears `full_n_target`; 12 does not.
  - `test_conceptual_stratum_reportability_floor` — < 5 conceptual → `UNDER_POPULATED`; ≥ 5 → reportable.
- Tests fail: `meets_full_n_target` / `conceptual_stratum_report` do not exist.

### Step 6 — floor helpers (GREEN)
- Implement `meets_full_n_target(dataset, cfg)` and `conceptual_stratum_report(dataset)` in `terse_dataset.py`.
- All Step-5 tests pass; existing floor tests stay green.

### Step 7 — pre-registered 0036 pilot config (RED) — BEFORE any pilot run
- Add to `harpyja/eval/test_ac8_pilot.py`:
  - `test_preregistered_0036_config_is_frozen_hashed_and_servable` — arms `qwen3:14b` vs `qwen3:4b-instruct`, contrast, frozen, 64-hex own hash, other fields identical to base config.
- Tests fail: `PREREGISTERED_AC8_CONFIG_0036` / `AC8_CONFIG_HASH_0036` do not exist.

### Step 8 — commit 0036 pilot config (GREEN)
- Add `PREREGISTERED_AC8_CONFIG_0036` + `AC8_CONFIG_HASH_0036` to `harpyja/eval/ac8_pilot.py` (arms only differ; all thresholds copied verbatim).
- All Step-7 tests pass. This freeze is committed before T15.

### Step 9 — pilot-aggregation + degrade posture (RED)
- Add `harpyja/eval/test_pilot_runner.py`:
  - `test_pilot_runner_builds_pairs_and_decides_under_0036_config` — per-case buckets → `PilotPair`s → `decide_from_pairs` under the 0036 config.
  - `test_pilot_runner_excludes_and_records_degrades` — a typed degrade is NOT counted clean; excluded + recorded by cause.
- Tests fail: `pilot_runner` does not exist.

### Step 10 — pilot_runner.py (GREEN)
- Implement pure aggregation glue in `harpyja/eval/pilot_runner.py` (no live I/O).
- All Step-9 tests pass.

### Step 11 — blind-author the pilot queries (operator, live)
- Run 0026's `author_terse_set` with author≠verifier live models (Ollama); commit the
  `AuthoringArtifact` (leaky→dropped, per-case provenance). STOP-AND-WARN on infra error.

### Step 12 — tag + assemble pilot rows (operator)
- Post-authoring: run the mechanical reachability check, hand-label concept-vs-patch,
  assemble `0036/1` rows replacing the five placeholders in `swebench_verified.terse.jsonl`.

### Step 13 — fixture-backed join/floor tests for real rows (RED)
- Update `test_terse_join.py` / `test_terse_floor.py` to assert the committed fixture
  is real `0036/1` rows (`gold_withheld: true`, tags present, join yields spans,
  floor honored). Tests fail while placeholders remain.

### Step 14 — commit replaced fixture (GREEN)
- Commit the replaced `swebench_verified.terse.jsonl`. All Step-13 tests pass.

### Step 15 — run the pilot end-to-end (operator, live, ~35+ min)
- For each pilot case: `run_verified_case` → artifact persisted via
  `write_live_artifact` (`VERIFIER_SCHEMA_VERSION 0034/1`); record degrades per case
  (bounded re-run or recorded exclusion). Batched. STOP-AND-WARN on infra error.

### Step 16 — pilot-artifact integration test (live, skip-not-fail)
- Add to `harpyja/eval/test_live_verifier_integration.py` a pilot-set test asserting
  each case yields a verifier-clean persisted artifact (or a recorded typed degrade —
  never silent); skips (not fails) when Ollama/model is unreachable.

### Step 17 — apply the AC4 gate (operator, live)
- Feed the pilot pairs to `decide_ac8` under `PREREGISTERED_AC8_CONFIG_0036` (hash
  cited in the artifact) → PROCEED or UNDER_POWERED_STOP. This outcome branches T19–T21.

### Step 18 — AC6 representativeness caveat (doc)
- Point the spec close / changelog at the pinned `REPRESENTATIVENESS_CAVEAT`
  (`report.py:41`, already stamped into report payloads). No parallel restatement.

### Step 19 — author + tag the full set (operator, live) [conditional-on-PROCEED]
- Only on PROCEED: blind-author + tag the full set at-or-above `full_n_target=30`
  (upward-only), enforcing the conceptual-stratum ≥ 5 reportability floor.

### Step 20 — full-set floor tests (RED) [conditional-on-PROCEED]
- Fixture-backed tests: `validate_terse_set_floor` ok, `meets_full_n_target` true,
  `conceptual_stratum_report` reportable. Fail until the full fixture is committed.

### Step 21 — commit the full set (GREEN) [conditional-on-PROCEED]
- Commit the full `swebench_verified.terse.jsonl`. All Step-20 tests pass.
- On UNDER_POWERED_STOP instead: T19–T21 are N/A-by-gate; spec closes with the finding.

## Delegation

- Steps 1–10 (pure unit RED/GREEN: schema, reachability, floors, config, runner) →
  keep in-agent (small, deterministic Python; TDD hook applies).
- Steps 11, 15, 19 (blind authoring + live pilot + full-set authoring) → delegate to
  an **operator/live executor** (reason: offline two-model + Ollama live runtime,
  ~35+ min wall-clock, STOP-AND-WARN discipline — not a unit-test surface).
- Step 17 (gate decision) → operator, but the decision logic is the already-tested
  `decide_ac8` — mechanical once pilot pairs exist.

## Risk

- **Wall-clock (pilot ~10×~200s ≈ 35+ min live).** → mitigation: all pure-unit pairs
  land first (Steps 1–10); the live pilot is a single late batched step (15) gated by
  the pre-committed config (8).
- **Under-powered pilot outcome (STOP).** → mitigation: STOP is a designed
  deliverable — full-set Steps 19–21 are conditional; the spec closes with the
  finding, no forced authoring of a set that can only rank noise (the 0023 lesson).
- **Authoring quality / leakage.** → mitigation: 0026 two-model blind protocol +
  `assert_author_input_blind`; tags computed strictly post-authoring, never
  author-visible; leaky verdict routes to drop, recorded.
- **Servable-model drift under a stale freeze.** → mitigation: option (b) — a NEW
  frozen+hashed config with servable arms, committed (Step 8) before the pilot fires
  (Step 15); artifact cites the hash; `full_n_target` upward-only, never re-derived.
- **Concept-span overwriting the join label.** → mitigation: label stays join-only;
  `concept_span` is a separate additive field the join's `replace` never touches;
  asserted by fixture-backed tests.
