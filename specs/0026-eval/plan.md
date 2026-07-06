---
spec: "0026"
status: planned
strategy: tdd
---

# Plan — 0026 eval (terse-query eval set — ranking instrument for the model bake-off)

Test-first, ordered along the data path:
schema/loader → join → guard fields + token flag → authoring provenance + offline
tool → classification/excluded-count → report caveat + schema bump → scoring
integration → AC8 pilot gate. Every GREEN is preceded by a RED. Python / pytest /
colocated `test_*.py`; units run `uv run pytest -m "not integration"`, live steps are
`@pytest.mark.integration` (skip-not-fail). Reuses the frozen oracle
(`metrics.span_hit_kind` / `locate_accuracy.classify_case`) — no new scoring code. SUT
(`harpyja/scout/`, `harpyja/orchestrator/`, `Settings`) is byte-frozen: this builds a
dataset + authoring/measurement harness only.

---

## Two plan-level decisions (spec left these open)

### Decision 1 — Authoring-provenance home: **loud-validated sidecar keyed by `case_id`** (NOT EvalCase fields)

Split the load-bearing shapes by *who produces them and who reads them*:

- **Per-case DATASET guard fields → additive validated `EvalCase` fields.**
  `label_provenance`, `query_provenance`, `gold_withheld`, `leaked_tokens`,
  `classification_provenance` are properties of the loadable record; the loud loader
  must *enforce* them at load time (AC3/AC5) and the scoring path consults them. They
  belong on `EvalCase`, appended last-with-defaults.
- **Operator-produced AUDIT metadata → a NEW loud-validated sidecar artifact**
  `swebench_verified.authoring.json`, keyed by `case_id`, with its own
  `AUTHORING_SCHEMA_VERSION` + `validate_authoring_record` / `AuthoringError`. Carries
  the Layer-(b) fields `author_model`, `verifier_model`, `author_input_hash`,
  `verifier_input_hash`, `verifier_verdict ∈ {clean,leaky}`, `outcome ∈
  {kept,reauthored,dropped}` **plus the aggregate `leaky_count` / `dropped_count`**
  (provenance-of-a-null).

Rationale: this is exactly the split the spec names — the audit fields are produced
OFFLINE by the two-model authoring tool and are **never read by the loader or the AC6
scoring path**, so folding them into `EvalCase` would make every dataset load carry
per-case invocation hashes the scoring path ignores — the same coupling smell the
`EvalConfig`-field-disjoint-from-`Settings` convention forbids. The aggregate
leaky/dropped counts have **no per-case home** at all; a sidecar gives them one. This
mirrors the repo's own precedent of separate pinned, version-stamped artifacts
(`report.py`, `oq2_ledger.py`) and the `swebench_verified.provenance.json` sidecar that
already rides alongside `raw.jsonl`. Keyed by `case_id`, it joins to the terse fixture
by the same integrity story as the span join.

**Tradeoff (stated):** two loud validators instead of one (`dataset._parse_case` +
`validate_authoring_record`) and a join to correlate a terse case with its authoring
record. Accepted: it keeps the loadable dataset free of audit-only payload, homes the
aggregate counts, and keeps pin (2)'s blindness assertion in the audit artifact where it
belongs.

### Decision 2 — AC8 pre-registration concrete values (frozen + hashed BEFORE the pilot)

A `frozen=True` `Ac8PilotConfig` exposed as a single `PREREGISTERED_AC8_CONFIG` constant,
hashed to `AC8_CONFIG_HASH` before any live pilot run (mirroring
`benchmark_fit.PREREGISTERED_CONFIG` / `MECHANICAL_RULE_HASH`):

- **Two reference models (servable on loopback Ollama, tool-calling, capability
  contrast to generate flips):**
  - Arm A `reference_model_a = "hf.co/Qwen/Qwen3-8B-GGUF:latest"` — the current
    `Settings.lm_model` default; the explorer's driving model, definitely served.
  - Arm B `reference_model_b = "qwen3:4b-instruct"` — the smaller Qwen3-4B-instruct
    used as the spec-0020 A/B model; a real capability contrast (size) is what produces
    *discordant* localization flips rather than two identical arms. Both co-load on the
    32 GB dev host (per memory). Grounded: the bake-off ranks general tool-calling
    models over `ModelGateway.complete_with_tools`; these are two genuinely servable
    such models.
- **Pilot N = 10** (top of the AC8 "author 8–10 first" band — a 10-case pilot bounds
  the signal-rate estimate variance better than 8 while staying well under the full-set
  authoring cost).
- **Full-size target `full_n_target = 30`** (mid of the ~20–40 multi-repo range).
- **Projection rule:** `projected_flips = round((signal_bearing_discordant /
  pilot_pairs_run) * full_n_target)` — the pilot's *signal-bearing* discordant RATE
  extrapolated linearly to the full size.
- **Exact STOP threshold:** `projected_flips < MIN_DISCORDANT_PAIRS (= 8)` →
  `UNDER_POWERED_STOP`. (Reuses the committed `benchmark_fit.PREREGISTERED_CONFIG.
  MIN_DISCORDANT_PAIRS = 8`, the exact-McNemar reachability floor — not a new guess.)
  Arithmetic consequence: the pilot must show `≥ round⁻¹` i.e. `≥ 3` signal-bearing
  discordant pairs of 10 to clear the projection (`3/10 * 30 = 9 ≥ 8`; `2/10 * 30 = 6 <
  8` STOPs) — an honest bar given 0023's near-zero localization floor.
- **Signal-bearing-flip definition (the 0023 guard):** a discordant pair
  (arms disagree on the binary localization outcome) counts ONLY when **≥1 arm is a
  CORRECT localization** — oracle file-or-span hit, i.e. `locate_accuracy.LocateBucket ∈
  {CORRECT, RIGHT_FILE_WRONG_SPAN}` for that arm. An empty↔wrong-file flip (neither arm
  a hit) is NOISE and is excluded. Computed through the frozen oracle — no forked
  scoring.
- **Typed outcome:** `Ac8Outcome ∈ {PROCEED, UNDER_POWERED_STOP}`; `UNDER_POWERED_STOP`
  names the next step (the finder-capability work 0022/0023 pointed at), a total pure
  function over the frozen config — never "author a set to rank noise."

---

## Test-first sequence

### Step 1 — Dataset schema-version gate: RED [unit]
- Add to `harpyja/eval/test_dataset.py`:
  - `test_dataset_schema_version_constant_exists` — asserts a NEW
    `dataset.DATASET_SCHEMA_VERSION == "0026/1"` (introduce, not bump; there is none
    today).
  - `test_parse_case_terse_schema_requires_guard_fields` — a row tagged
    `{"schema_version": "0026/1", ...}` missing `query_provenance` raises `DatasetError`.
  - `test_parse_case_terse_schema_omits_spans_ok` — a terse-tagged row with NO
    `expected_spans` loads (spans are joined later), where a legacy row without spans
    still raises.
  - `test_parse_case_legacy_no_version_tag_loads_with_defaults` — an existing
    seed/legacy row (no `schema_version`) loads unchanged and the new guard fields read
    back as their defaults.
- Tests fail: `DATASET_SCHEMA_VERSION` does not exist; `_parse_case` unconditionally
  requires `expected_spans` and knows no guard fields (AC3/AC5 contradiction unresolved).

### Step 2 — Dataset schema-version gate: GREEN [unit]
- `harpyja/eval/dataset.py`:
  - Introduce `DATASET_SCHEMA_VERSION = "0026/1"`.
  - Append last-with-defaults `EvalCase` fields: `schema_version: str | None = None`,
    `label_provenance: str | None = None`, `query_provenance: str | None = None`,
    `gold_withheld: bool = False`, `leaked_tokens: tuple[str, ...] = ()`,
    `classification_provenance: str | None = None`. Centralize their defaults so legacy
    on-disk rows still read.
  - Version-gate `_parse_case`: when `row.get("schema_version") ==
    DATASET_SCHEMA_VERSION` → **terse branch** (require case_id + the guard fields;
    `expected_spans` optional, default `()`); else → **legacy branch** (today's
    behavior: require non-empty `expected_spans`, default the guard fields). Still loud
    — no silent drops.
- Step-1 tests pass; the existing `test_dataset.py` legacy tests stay green (backward-compat crux, both directions TDD'd).

### Step 3 — `case_id` JOIN over the sha256-pinned raw fixture: RED [unit]
- Add `harpyja/eval/test_terse_join.py`:
  - `test_terse_load_asserts_raw_pin_before_join` — a raw fixture whose bytes don't
    match `provenance.json.raw_fixture_sha256` raises `DatasetError` (pin asserted
    BEFORE any join; tamper one byte).
  - `test_terse_case_joins_spans_from_raw_by_case_id` — a terse case's `case_id`
    resolves in `raw.jsonl` and the loaded `EvalCase.expected_spans` equals the raw
    case's spans; the terse fixture file itself contains NO `expected_spans` (no second
    transcription).
  - `test_terse_join_exposes_base_commit_and_source_issue` — the join returns
    `base_commit` and the source-issue text (raw `query`) as side data, NOT promoted to
    `EvalCase` fields (review B2).
  - `test_terse_case_id_absent_in_raw_raises` — an unknown `case_id` raises loudly.
  - `test_terse_label_provenance_is_patch_derived_at_convert` — joined cases carry
    `label_provenance == "patch-derived-at-convert"`, never "human-confirmed".
- Tests fail: no join loader exists.

### Step 4 — `case_id` JOIN: GREEN [unit]
- Add `harpyja/eval/terse_dataset.py`:
  - `load_terse_dataset(terse_path, raw_path, provenance_path) -> TerseDataset` —
    (1) assert `sha256(raw_path)` equals `provenance.raw_fixture_sha256` FIRST (reuse
    `swebench_eval._sha256_file`); (2) parse terse rows via `dataset.load_dataset`
    (terse branch); (3) for each, look up `case_id` in the parsed raw rows and
    `dataclasses.replace` in the joined `expected_spans` (+ `label_provenance =
    "patch-derived-at-convert"`); (4) return the enriched `EvalCase`s plus a
    `case_id → (base_commit, source_issue)` map (base_commit stays a raw-record key).
  - Commit a minimal `harpyja/eval/fixtures/swebench_verified.terse.jsonl` (a few real
    `case_id`s from the pinned raw fixture, hand placeholder terse queries + guard
    fields, NO spans) so the unit tests have a real join target. Real queries come from
    the offline tool (Step 9 / delegated pilot). [fixtures/build]

### Step 5 — Token-subset tripwire + loud guard rejection (Layer a): RED [unit]
- Add `harpyja/eval/test_terse_guard.py`:
  - `test_token_subset_flag_flags_gold_only_identifier` — a query containing an
    identifier absent from the JOINED source issue (raw `query`) sets
    `leaked_tokens`/the flag; a query whose tokens are all a subset does not.
  - `test_token_flag_recomputes_against_joined_source_issue` — the flag is recomputed
    from the joined raw `query`, not trusted from the terse file.
  - `test_loud_loader_rejects_terse_case_missing_guard_field` — AC5: a terse case
    missing a guard field → `DatasetError`.
  - `test_legacy_case_still_loads_alongside_terse` — AC5 other direction: a legacy
    (untagged) case loads in the same call.
- Tests fail: no token-subset computation exists.

### Step 6 — Token-subset tripwire (Layer a): GREEN [unit]
- `harpyja/eval/terse_dataset.py`: add `compute_leaked_tokens(query, source_issue) ->
  tuple[str, ...]` (identifier tokens in `query` absent from `source_issue`) and wire it
  into `load_terse_dataset` (recompute against the joined raw `query`, never the terse
  file's stored value). Document it as the near-vacuous first-pass tripwire (the real
  guard is Layer b, Steps 7–10). Guard-rejection already enforced by the Step-2 gate.

### Step 7 — Authoring-provenance sidecar shape + pin (2) blindness: RED [unit]
- Add `harpyja/eval/test_authoring_provenance.py`:
  - `test_authoring_record_requires_all_fields` — a record missing
    `author_model`/`verifier_model`/`author_input_hash`/`verifier_input_hash`/
    `verifier_verdict`/`outcome` raises `AuthoringError`.
  - `test_authoring_verdict_and_outcome_enums_validated` — `verifier_verdict ∉
    {clean,leaky}` and `outcome ∉ {kept,reauthored,dropped}` raise.
  - `test_authoring_aggregate_counts_present` — the artifact carries `leaky_count` /
    `dropped_count` (provenance-of-a-null).
  - `test_pin2_author_input_excludes_joined_span_content` — the blindness assertion:
    given an authoring record + the joined `expected_spans` for its `case_id`, a helper
    asserts the recorded `author_input_hash` payload contains NONE of the span content
    (paths, line ranges, span code); a payload containing a span path fails loudly.
  - `test_schema_version_constant_and_validate_roundtrip` —
    `AUTHORING_SCHEMA_VERSION` exists and a well-formed artifact validates.
- Tests fail: no sidecar module.

### Step 8 — Authoring-provenance sidecar shape + pin (2): GREEN [unit]
- Add `harpyja/eval/authoring_provenance.py`: `AUTHORING_SCHEMA_VERSION = "0026/1"`;
  `AuthoringRecord` frozen dataclass; `AuthoringError`; loud `validate_authoring_record`
  / `validate_authoring_artifact` (per-case records + aggregate leaky/dropped counts);
  `assert_author_input_blind(record, expected_spans)` operationalizing pin (2)
  (the recorded author-input payload contains no path/line/code content of the joined
  spans). Write via the existing `report.atomic_write_json` outside-repo writer.

### Step 9 — Offline two-model authoring tool: RED [unit]
- Add `harpyja/eval/test_terse_authoring.py`:
  - `test_authoring_tool_uses_injected_cross_model_seam_not_product_gateway` — the tool
    takes an injected `author_invoke` / `verifier_invoke` `Callable`; drive with fakes,
    assert the produced terse case + `AuthoringRecord` and that the fakes were called
    separately (STATE-level independence).
  - `test_authoring_tool_withholds_gold_span_from_author` — the author callable's input
    (captured) contains none of the joined span content (drives the same pin-(2)
    assertion end-to-end).
  - `test_leaky_verdict_routes_to_reauthor_or_drop_never_silent` — a `leaky` verifier
    verdict yields `outcome ∈ {reauthored, dropped}` and increments `leaky_count`, never
    a silent keep.
  - `test_authoring_module_is_not_product_runtime` — import-absence guard (ast, per the
    deletion-guard convention): the authoring module does NOT import
    `harpyja.gateway`/`ModelGateway`, and no `harpyja/server`|`harpyja/orchestrator`
    module imports it (declares it an OFFLINE operator/dev artifact, not product
    runtime).
- Tests fail: no authoring tool.

### Step 10 — Offline two-model authoring tool: GREEN [unit]
- Add `harpyja/eval/terse_authoring.py` (dev-time operator module in the eval harness,
  same out-of-air-gap posture as `swebench_eval` `convert`/`provision`; the cross-model
  invocation is INJECTED, never the product `ModelGateway`):
  `author_terse_case(raw_case, *, author_invoke, verifier_invoke) -> (EvalCase,
  AuthoringRecord)` — builds the author input from issue-intent with the gold span
  withheld, invokes the author, invokes the verifier separately, records the loud
  provenance, maps a `leaky` verdict to re-author/drop. Emits the terse fixture line +
  the sidecar record. Depends on Steps 4/8.

### Step 11 — Classification-by-intent + labeled excluded-count + size/pairing floor: RED [unit]
- Add `harpyja/eval/test_terse_floor.py`:
  - `test_classification_provenance_is_hand_labeled_by_intent` — terse cases carry
    `classification_provenance == "hand-labeled-by-intent"` (audited exemption from
    span-reproducibility); intent wins on disagreement with patch-shape.
  - `test_excluded_count_is_labeled_field_not_silent_drop` — a known-correct-span-only
    filter records an `excluded_count` (+ ids), never a silent drop (provenance-of-a-null).
  - `test_terse_floor_cites_committed_constants` — the floor validator references
    `benchmark_fit.PREREGISTERED_CONFIG.min_n == 12` and `MIN_DISCORDANT_PAIRS == 8` (no
    re-declared magic numbers).
  - `test_terse_floor_requires_multiple_repos` — a single-repo-dominated set fails the
    floor; a ≥12-usable, multi-repo set passes.
- Tests fail: no floor validator / provenance wiring.

### Step 12 — Classification + excluded-count + floor: GREEN [unit]
- `harpyja/eval/terse_dataset.py`: set `classification_provenance` on join; add
  `TerseDataset.excluded_count` / `excluded_case_ids` (labeled null-provenance). Add
  `validate_terse_set_floor(dataset)` citing `benchmark_fit.PREREGISTERED_CONFIG`
  (≥`min_n=12` usable, multi-repo, `MIN_DISCORDANT_PAIRS=8` named as the pairing floor).

### Step 13 — Representativeness / language-monoculture caveat + report SCHEMA_VERSION bump: RED [unit]
- Add to `harpyja/eval/test_report.py`:
  - `test_run_metadata_carries_representativeness_caveat` — `run_metadata` has a new
    `representativeness_caveat` field (query-shape axis fixed, codebase-character /
    Python language-monoculture NOT — valid for RELATIVE ranking only), mirroring
    `contamination_caveat`.
  - `test_schema_version_bumped_for_terse_caveat` — `report.SCHEMA_VERSION` advanced
    past `"0025/1"` (e.g. `"0026/1"`); a legacy-shaped block still validates via
    `_RUN_METADATA_DEFAULTS`.
- Tests fail: the field and bump don't exist.

### Step 14 — Representativeness caveat + schema bump: GREEN [unit]
- `harpyja/eval/report.py`: bump `SCHEMA_VERSION` to `"0026/1"`; append
  `representativeness_caveat` last in `_RUN_METADATA_FIELDS` with its default in the
  single `_RUN_METADATA_DEFAULTS` source (a `REPRESENTATIVENESS_CAVEAT` constant string).
  Legacy `0025/1`-shaped blocks keep validating through defaults.

### Step 15 — AC8 frozen/hashed pilot config + signal-bearing flip + typed outcome: RED [unit]
- Add `harpyja/eval/test_ac8_pilot.py`:
  - `test_preregistered_ac8_config_is_frozen_and_hashed` — `PREREGISTERED_AC8_CONFIG`
    is a `frozen=True` dataclass with the Decision-2 values; `AC8_CONFIG_HASH` is stable
    over its fields; reuses `benchmark_fit.PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS`.
  - `test_signal_bearing_discordant_excludes_empty_wrong_file_noise` — an empty↔wrong-file
    flip is NOT counted; a discordant pair where ≥1 arm is `CORRECT`/`RIGHT_FILE_WRONG_SPAN`
    IS counted (routed through the frozen `locate_accuracy` oracle).
  - `test_project_flips_and_stop_threshold` — `project_flips(signal_discordant=3,
    pilot_pairs_run=10)` → 9 (`PROCEED`); `=2` → 6 (`UNDER_POWERED_STOP`); boundary
    pinned at the `< 8` cut.
  - `test_ac8_outcome_is_total_pure_function` — `decide_ac8` returns an `Ac8Outcome`
    member on every input, never raises/defaults; `UNDER_POWERED_STOP` names the
    finder-capability next step.
- Tests fail: no AC8 module.

### Step 16 — AC8 pilot config + verdict: GREEN [unit]
- Add `harpyja/eval/ac8_pilot.py`: `Ac8PilotConfig` (frozen) + `PREREGISTERED_AC8_CONFIG`
  + `AC8_CONFIG_HASH`; `Ac8Outcome` enum; `signal_bearing_discordant(pairs)` (over
  retained per-case `(bucket_a, bucket_b)` pairs, using the frozen oracle buckets — never
  a difference of aggregate rates); `project_flips(...)`; total `decide_ac8(...)` STOPping
  when `projected < MIN_DISCORDANT_PAIRS`. Pure, no I/O, no SUT import beyond the frozen
  `LocateBucket` (mirrors `benchmark_fit.py`).

### Step 17 — AC6 scoring end-to-end via the provisioning path: RED→GREEN [integration]
- Add `harpyja/eval/test_terse_probe_integration.py`:
  - `test_terse_set_scores_through_explorer_offline` — `@pytest.mark.integration`,
    skip-not-fail when `not scout_stack_available()`. Drives the terse set: raw
    `base_commit` → provisioned worktree (`swebench_verified.resolved.jsonl`) → the
    explorer (sole Scout backend) via `run_locate_probe` → `build_scout_engine` →
    `locate_accuracy.score_distribution`, producing file-level + span-level scores from
    the existing oracle. Assert both scores are populated and the SUT is unmutated.
- GREEN: add a thin `harpyja/eval/terse_probe.py` `run_terse_locate_probe(...)` that
  loads the joined terse set (Step 4) and delegates to the UNCHANGED `run_locate_probe`
  (no forked scoring, no SUT edit). Split fail-posture reused (`require_live_stack` /
  `HARPYJA_REQUIRE_LIVE_STACK`).

### Step 18 — AC8 live pilot go/no-go run: RED→GREEN [integration, delegated]
- `harpyja/eval/test_terse_probe_integration.py`:
  - `test_ac8_pilot_gate_runs_two_reference_models` — `@pytest.mark.integration`,
    skip-not-fail. Authors/loads the 10-case pilot, runs BOTH `PREREGISTERED_AC8_CONFIG`
    reference models through `run_locate_probe`, computes signal-bearing discordant pairs,
    projects, and emits the typed `Ac8Outcome`. Assert the outcome + the frozen
    `AC8_CONFIG_HASH` are recorded to a durable ledger (reuse `atomic_write_json`).
- GREEN: `terse_probe.run_ac8_pilot(...)` composing Step-16 + `run_locate_probe`.
- This deliverable-producing run (real served two-model authoring + scoring) is an
  operator activity — see Delegation.

### Step 19 — Refactor (optional)
- Hoist the sha256-pin assertion into one shared helper used by both `terse_dataset`
  and the existing `swebench_eval._load_resolved` (single integrity-check source).
- Route the AC8 signal-bearing-discordant computation and the AC6 scoring through the
  same `locate_accuracy` bucket call (prove one-oracle reuse with a
  `test_ac8_uses_same_oracle_as_locate_accuracy` reuse assertion, per the one-oracle
  convention). All tests still pass.

---

## AC-coverage map

| AC | Steps | Kind |
|----|-------|------|
| AC1 — labels joined from one sha256-pinned source | 3–4 (pin-before-join, no second transcription) | unit |
| AC2 — token tripwire (a) + executable two-model blind protocol (b), loud-validated shape, pin (2) | 5–6 (a); 7–8 (shape + pin 2); 9–10 (offline tool) | unit + executable-protocol |
| AC3 — additive validated fields under a NEW gated schema version; base_commit not promoted | 1–2 (gate); 3–4 (base_commit stays raw-key) | unit |
| AC4 — size/pairing floor cites committed constants; multi-repo | 11–12 | unit |
| AC5 — loud loader covers the guard without breaking legacy (both directions) | 2 (reject + legacy loads); 5 | unit |
| AC6 — drives the real backend via the provisioning path, file+span scores from the oracle | 17 | integration |
| AC7 — representativeness/language-monoculture caveat as a pinned schema field + SCHEMA_VERSION bump | 13–14 | doc + schema |
| AC8 — pre-registered pilot-gated power go/no-go, frozen+hashed config, signal-bearing floor, typed UNDER_POWERED(STOP) | 15–16 (unit); 18 (live) | integration |

## Delegation

- **Step 18 (AC8 live pilot run) → delegate to an operator/integration agent on the
  served loopback stack.** It requires the two reference models (`Qwen3-8B` +
  `qwen3:4b-instruct`) co-loaded on Ollama and provisioned worktrees — the same
  operator surface as spec 0022/0023/0025 live runs. Reason: served-stack + real
  cross-model invocation is outside a unit harness; the deliverable run must fail LOUD
  (`HARPYJA_REQUIRE_LIVE_STACK`) while CI stays skip-not-fail.
- **The real offline two-model authoring pilot (Step 10 driving Step 18's fixture) →
  operator activity** using operator cross-model tooling (NOT the product
  `ModelGateway`). The unit tests (Steps 9–10) fully cover the tool with injected fakes;
  only the real 10-case authoring pass is delegated.
- Step 17 (AC6 scoring) is delegatable to the same operator run but is unit-adjacent
  (skip-not-fail) and can also be exercised against the vendored `legacy/` worktree.

## Risk

- **AC8 STOP is the likely outcome** (0023 measured 79% empty / 0/14 span-correct) →
  mitigation: that is the *designed* result, not a failure — the frozen config makes
  `UNDER_POWERED_STOP` a valid typed deliverable naming the finder-capability next spec;
  the pilot spends 10-case authoring cost, not the full ~30.
- **Model circularity** (author/verifier/reference share a blind spot; correlated,
  doesn't cancel) → mitigation: author≠verifier family recommendation + the CO-PRIMARY
  model-independent paired-ranking floor (named-not-closed in AC2, symmetric to the
  representativeness gap); no code can close it, so it is recorded.
- **Terse fixture queries are placeholders until the offline pilot runs** → mitigation:
  the committed `swebench_verified.terse.jsonl` (Step 4) is explicitly a unit-test
  join target with placeholder queries; the real authored queries land via the delegated
  pilot; the token flag recomputes against the joined raw issue regardless.
- **Two loud validators can drift** (dataset guard fields vs authoring sidecar) →
  mitigation: keyed by the same `case_id`, joined; a `test_terse_case_has_authoring_record`
  reuse/coupling assertion pins that every kept terse case has a validated sidecar record.
- **`_parse_case` version gate could break existing seed/legacy fixtures** (the AC3/AC5
  contradiction) → mitigation: Step 1 TDDs BOTH directions (terse rejects-missing +
  legacy loads-with-defaults) before Step 2 touches the shared parser.
