---
spec: "0049"
status: planned
strategy: tdd
---

# Plan — 0049 serving (greedy serving — deterministic variant tags)

## Reconciliation decisions (resolve before coding)

- **REUSE vs CREATE.** REUSE by identity: `LocateBucket` (the bucket-taxonomy
  oracle, `harpyja/eval/locate_accuracy.py`), `gateway.assert_local`,
  `exclusivity_gate.build_exclusivity_record` / `validate_exclusivity_record`,
  the `bakeoff_config_hash` k=v-join shape, and the frozen `BakeoffConfig` class.
  DO NOT modify the bucket oracle, the replay probe's taxonomy, the completions
  Gateway, the explorer, the verifier, or the tool suite (Out of scope).
- **2-draw vs ≥3-draw (EXPLICIT reconciliation — Step 9/10).** The invariant
  "probe IDENTITY-REUSED, no oracle change" binds the **bucket taxonomy**
  (`LocateBucket`), NOT the arity of `bakeoff_run.reproducibility_replay_probe`
  (a 2-draw function). Decision: **leave `reproducibility_replay_probe` untouched
  (0048 keeps it)** and add a NEW K-draw orchestration `greedy_replay_proof(...)`
  that (a) runs ≥3 draws per (tag, case), (b) classifies each draw through the
  **reused** `LocateBucket` taxonomy (oracle unchanged), (c) emits per-cell
  reproduce/flip verdicts across all three tags. Generalizing the 2-draw
  function's arity is rejected: it would silently change 0048's preflight
  semantics.
- **Config hash re-freeze.** Adding `served_variant_tags` +
  `served_variant_fingerprints` to `BakeoffConfig` flows into `bakeoff_config_hash`
  automatically (it hashes `sorted(dataclasses.asdict(cfg))`). The recomputed
  `BAKEOFF_CONFIG_HASH_0048` value shifts; no committed 64-char literal pins the
  old value (verified by grep — a task guards this), so ledgers stay internally
  consistent. The new offline-reproducible digest is pinned as a NEW known-value
  literal `SERVED_VARIANT_CONFIG_HASH`.
- **Committed fingerprints are pure literals.** `served_variant_fingerprints`
  default holds PINNED digest literals (committed values), keeping
  `bakeoff_config.py` I/O-free (the invariant: the hash is a pure function of
  in-repo data). A unit test re-derives the digests from the committed
  `serving/Modelfile.*` bytes via the one parser and asserts equality (chain of
  custody committed-file → config).

## Test-first sequence

### Step 1 — Fingerprint parser + committed Modelfiles (RED)  [unit] AC1
- Copy the three archived Modelfiles into a committed repo-root `serving/` dir:
  `serving/Modelfile.qwen3-14b`, `serving/Modelfile.qwen3-8b`,
  `serving/Modelfile.qwen3.5-4b` (from `specs/.archive/0048-bake-off/serving/`).
- Add `harpyja/eval/test_greedy_serving.py`:
  - `test_parse_modelfile_fingerprint_extracts_from_params_template_system` —
    reduces a Modelfile to `FROM` + sorted `PARAMETER` map + `TEMPLATE` + `SYSTEM`.
  - `test_parse_modelfile_fingerprint_sorts_parameter_map` — PARAMETERs
    canonicalize to a sorted key→value map regardless of source order.
  - `test_parse_modelfile_fingerprint_rejects_duplicate_parameter_keys` —
    dup/conflicting `PARAMETER` key raises loud (fail-loud, never silent last-wins).
  - `test_parse_modelfile_fingerprint_rejects_out_of_set_directive` — a directive
    outside the selected set raises (not coerced/dropped).
  - `test_parse_modelfile_fingerprint_normalizes_line_endings_and_comments` —
    CRLF/LF, stripped comments, collapsed incidental whitespace → identical
    fingerprint.
  - `test_greedy_modelfiles_set_temperature_zero` — the three committed `serving/*`
    Modelfiles each parse to `temperature=0`.
- Tests fail: `harpyja/eval/greedy_serving.py` and `parse_modelfile_fingerprint`
  do not exist; `serving/` Modelfiles are not yet committed.

### Step 2 — Fingerprint parser + grammar (GREEN)  [unit] AC1
- Implement `harpyja/eval/greedy_serving.py`:
  - frozen `ModelfileFingerprint(from_base, parameters, template, system)` with
    `parameters: tuple[tuple[str,str],...]` (sorted).
  - `parse_modelfile_fingerprint(text: str) -> ModelfileFingerprint` — the ONE
    deterministic grammar: normalize line endings, strip comments, collapse
    whitespace, canonicalize multiline `TEMPLATE`/`SYSTEM`, sorted PARAMETER map;
    raise `ModelfileGrammarError` on dup PARAMETER keys / out-of-set directives.
  - `fingerprint_digest(fp) -> str` — sha256 over the canonical rendering (the
    value committed into the config).
- All Step-1 tests pass.

### Step 3 — Build driver + live-modelfile reader (RED)  [unit] AC1
- Add to `test_greedy_serving.py`:
  - `test_build_greedy_variant_noop_on_fingerprint_match` — existing tag whose live
    fingerprint matches committed → `GreedyBuildOutcome.NOOP_MATCH`, no
    `ollama create`.
  - `test_build_greedy_variant_stops_and_warns_on_fingerprint_mismatch` — existing
    tag with a divergent live fingerprint → `STOP_AND_WARN_MISMATCH`, never
    overwrites (no `ollama create` issued).
  - `test_build_greedy_variant_creates_from_committed_file_when_absent` — absent tag
    → `ollama create` from the committed Modelfile (OQ1 recreate-from-committed).
  - `test_build_greedy_variant_asserts_local_on_resolved_host_first` — the resolved
    Ollama host is `assert_local`-ed BEFORE any subprocess (ordering pinned via a
    call log).
  - `test_build_greedy_variant_passes_sanitized_env_with_ollama_host` — the
    subprocess env is sanitized and carries `OLLAMA_HOST=<resolved host>` (never
    lets the CLI pick a different daemon).
  - `test_read_live_modelfile_binds_ollama_host_in_sanitized_env` —
    `read_live_modelfile` runs `ollama show --modelfile <tag>` with the same
    sanitized env + `OLLAMA_HOST`.
- Tests fail: `build_greedy_variant`, `read_live_modelfile`, `GreedyBuildOutcome`,
  and `GreedyBuildError` (STOP-AND-WARN) do not exist.

### Step 4 — Build driver + live reader (GREEN)  [unit] AC1
- Implement in `greedy_serving.py`:
  - `GreedyBuildOutcome` enum `{CREATED, NOOP_MATCH, STOP_AND_WARN_MISMATCH}`.
  - `build_greedy_variant(tag, modelfile_path, committed_fp, *, host_resolver,
    assert_local_fn, show_fn, create_fn)` — resolve host once → `assert_local` that
    exact host FIRST → read live fingerprint via `show_fn` (if present) → compare to
    `committed_fp`: match→NOOP; mismatch→STOP-AND-WARN (return outcome, warn, no
    overwrite); absent→`create_fn` from the committed file; subprocess seams receive
    a sanitized env with `OLLAMA_HOST`.
  - `read_live_modelfile(tag, *, host, run_fn)` — sanitized-env `ollama show
    --modelfile` runner returning text (parsed by the SAME
    `parse_modelfile_fingerprint`).
- All Step-3 tests pass.

### Step 5 — Generation-pins diff + fingerprint delta (RED)  [unit] AC4
- Add to `test_greedy_serving.py`:
  - `test_greedy_generation_pins_diff_base_is_exactly_temperature` — the greedy
    fingerprint's semantic delta vs the 0034/0038 pinned values (max_tokens=2048,
    reasoning_effort/explorer_think=None, tool suite, v1 transport) is EXACTLY the
    temperature field; regression-pinned against the committed pins.
  - `test_fingerprint_delta_added_temperature_is_exactly_temperature` — a base with
    no explicit temperature vs greedy `temperature=0` → delta = one ADDED
    `temperature` entry (`FROM` excluded), classified "exactly temperature".
  - `test_fingerprint_delta_other_key_change_fails` — any other added/removed/changed
    PARAMETER key → NOT "exactly temperature".
- Tests fail: `fingerprint_delta` / `is_exactly_temperature_delta` do not exist.

### Step 6 — Generation-pins diff + fingerprint delta (GREEN)  [unit] AC4
- Implement `fingerprint_delta(base_fp, greedy_fp) -> ParamDelta` (over the
  canonical PARAMETER map, `FROM` excluded) and
  `is_exactly_temperature_delta(delta) -> bool` (added `temperature` OR
  changed-only-`temperature` ⇒ True; any other key ⇒ False).
- All Step-5 tests pass.

### Step 7 — Re-frozen served config (RED)  [unit] AC2
- Add `harpyja/eval/test_bakeoff_config_served_variants.py`:
  - `test_bakeoff_config_pins_three_greedy_variant_tags` — `served_variant_tags ==
    ("qwen3-14b-greedy","qwen3-8b-greedy","qwen3.5-4b-greedy")`.
  - `test_served_variant_tags_exclude_base_tags_path_a_not_b` — no base tag
    (`qwen3:14b` etc.) appears in `served_variant_tags`.
  - `test_served_variant_tags_field_default_no_placeholder` — field-default
    INTROSPECTION over `dataclasses.fields(BakeoffConfig)` (NOT a source grep): the
    `served_variant_tags` default is the three greedy tags and none equals a
    known-unserved/placeholder sentinel.
  - `test_served_variant_fingerprints_match_committed_modelfiles` — each committed
    `served_variant_fingerprints` digest equals `fingerprint_digest(parse(...))`
    over the committed `serving/Modelfile.*` bytes (chain of custody).
  - `test_served_variant_config_hash_known_value` — `SERVED_VARIANT_CONFIG_HASH`
    equals a pinned 64-char literal (offline-reproducible known-value drift test).
  - `test_served_variant_config_hash_changes_on_tag_drift` — replacing any greedy
    tag via `dataclasses.replace` changes the hash (drift guard is real).
  - `test_resolve_served_model_maps_logical_to_greedy_variant` —
    `resolve_served_model(cfg, "qwen3:14b") == "qwen3-14b-greedy"` (the single
    model-resolution consumer).
  - `test_served_variant_tags_read_only_by_model_resolution` — an `ast` sweep over
    `harpyja/` (tests + config module excluded) asserts the ONLY attribute read of
    `served_variant_tags` is inside `resolve_served_model` (deployment/unrelated
    paths do not read it).
- Tests fail: the two new frozen fields, `SERVED_VARIANT_CONFIG_HASH`, and
  `resolve_served_model` do not exist.

### Step 8 — Re-frozen served config (GREEN)  [unit] AC2
- In `harpyja/eval/bakeoff_config.py`:
  - add frozen fields `served_variant_tags: tuple[str,...]` (the three greedy tags)
    and `served_variant_fingerprints: tuple[tuple[str,str],...]` (sorted `(tag,
    digest)` literals, the COMMITTED digests) — appended last with defaults.
  - `SERVED_VARIANT_CONFIG_HASH = bakeoff_config_hash(BakeoffConfig())` and a pinned
    literal mirror.
  - `resolve_served_model(cfg, logical_tag) -> str` — the SINGLE call site reading
    `served_variant_tags`.
- Verify no committed 64-char literal pins the old `BAKEOFF_CONFIG_HASH_0048` value
  (the recomputed value legitimately shifts; ledger tests recompute).
- All Step-7 tests pass.

### Step 9 — K-draw replay proof + typed outcome (RED)  [unit] AC5/AC6
- Add `harpyja/eval/test_greedy_replay_proof.py`:
  - `test_greedy_replay_proof_requires_at_least_three_draws_per_cell` — a cell
    supplied <3 draws raises (2-draw is too weak — the reconciliation guard).
  - `test_greedy_replay_proof_cell_reproduces_when_all_draws_identical_bucket` — all
    K draws → identical `LocateBucket` ⇒ cell verdict `reproduce`.
  - `test_greedy_replay_proof_cell_flips_on_within_cell_bucket_divergence` — any draw
    in a different bucket ⇒ `flip`, naming tag+case.
  - `test_greedy_replay_proof_keys_on_bucket_not_tool_path` — draws sharing a bucket
    but differing tool-path length (9 vs 6) ⇒ still `reproduce`.
  - `test_greedy_replay_proof_reuses_locate_bucket_taxonomy_by_identity` — the proof
    classifies via `LocateBucket`, no new/forked taxonomy.
  - `test_greedy_serving_outcome_reproducible_requires_every_cell` — every (tag,case)
    cell reproduces ⇒ `GreedyServingOutcome.GREEDY_REPRODUCIBLE`.
  - `test_greedy_serving_outcome_any_flip_forces_residual_nondeterminism` — ANY
    single cell flip (any tag) ⇒ `RESIDUAL_NONDETERMINISM` globally (no per-tag
    cherry-pick), naming the offending tag+case.
  - `test_greedy_replay_artifact_schema_carries_committed_fingerprint_and_exclusivity`
    — the artifact per (tag,case) carries repo, case id, greedy tag, the tag's
    COMMITTED fingerprint, the K bucket classifications, the verdict, and the 0041
    exclusivity-evidence fields (validated via `validate_exclusivity_record`).
  - `test_greedy_replay_artifact_is_drift_pinned` — the committed artifact's schema
    keys/shape are drift-pinned.
- Tests fail: `greedy_replay_proof`, `GreedyServingOutcome`,
  `build_greedy_replay_artifact` do not exist.

### Step 10 — K-draw replay proof + typed outcome (GREEN)  [unit] AC5/AC6
- Implement in `greedy_serving.py` (or `greedy_replay.py`):
  - `GreedyServingOutcome` enum `{GREEDY_REPRODUCIBLE, RESIDUAL_NONDETERMINISM}`.
  - `greedy_replay_proof(cells, *, min_draws=3) -> dict` — per-cell reproduce/flip
    over `LocateBucket` (bucket-keyed), ≥3-draw guard, global outcome (any flip →
    RESIDUAL_NONDETERMINISM, naming tag+case).
  - `build_greedy_replay_artifact(cfg, *, tag, case_id, repo, buckets, verdict,
    exclusivity_record) -> dict` — the pinned schema incl. the committed fingerprint
    (from `cfg.served_variant_fingerprints`).
- All Step-9 tests pass.

### Step 11 — Membership probe over variant tags (RED)  [unit] AC3
- Add `harpyja/eval/test_greedy_membership.py`:
  - `test_probe_served_variant_membership_iterates_variant_tags_not_model_tags` —
    the probe checks `served_variant_tags`, NOT `model_tags` (RED: current
    `probe_served_membership` iterates `model_tags`).
  - `test_probe_served_variant_membership_asserts_local_first` — `assert_local` runs
    before the `/api/tags` read (call-log order).
  - `test_probe_served_variant_membership_empty_served_set_all_false` — an empty
    served set → every greedy tag False (cannot pass trivially when the endpoint is
    down).
- Tests fail: no served-variant membership entrypoint exists.

### Step 12 — Membership probe over variant tags (GREEN)  [unit] AC3
- Generalize `bakeoff_run.probe_served_membership` with a backward-compatible
  keyword `tags: Sequence[str] | None = None` (default `None → cfg.model_tags`,
  0048 unchanged); add `probe_served_variant_membership(cfg, *, api_base,
  assert_local_fn, tags_reader)` delegating with `tags=cfg.served_variant_tags`.
- All Step-11 tests pass.

### Step 13 — Live integration checks (RED→GREEN)  [integration] AC1a/AC3/AC4a/AC5
- Add `harpyja/eval/test_greedy_serving_live.py` (`pytestmark =
  pytest.mark.integration`; each test SKIPs when the Ollama endpoint is unreachable
  and runs `gateway.assert_local` on the resolved host FIRST; each records an
  exclusivity record via `build_exclusivity_record`):
  - `test_live_greedy_14b_anchor_matches_committed_fingerprint` (AC1a) — live
    `ollama show` fingerprint of the hand-created `qwen3-14b-greedy:latest` vs the
    committed Modelfile fingerprint; STOP-AND-WARN + RECORD the match/mismatch
    (the reuse-or-discard chain-of-custody decision, OQ1).
  - `test_live_greedy_variant_tags_served_positive_membership` (AC3) — positive
    `/api/tags` membership for all three greedy tags via
    `probe_served_variant_membership`; endpoint down → SKIP (never a passing
    assertion).
  - `test_live_greedy_base_diff_is_exactly_temperature` (AC4a) — for each of the
    three pairs, `fingerprint_delta(show(base), show(greedy))` is EXACTLY
    temperature (`FROM` resolves to the identical base blob on both sides; a base
    with no explicit temperature yields an ADDED `temperature=0`).
  - `test_live_greedy_tag_conforms_to_committed_fingerprint` (AC4a) — each live
    greedy tag conforms to its committed `served_variant_fingerprints` entry.
  - `test_live_greedy_replay_proof_regenerates_committed_artifact` (AC5) — regenerate
    the ≥3-draw × 3-tag × ≥2-case/≥2-repo proof and reconcile with the committed
    artifact; skip-not-fail (the committed artifact carries acceptance).
- RED: the tests reference the live readers/probe wired above but the live test file
  does not exist → collection references are the failing edge. GREEN: file added; on
  a bare CI host every test SKIPs cleanly; on the 0041-gated host they exercise the
  real driver/probe/proof.

### Step 14 — Findings + memory (doc)  [doc] AC6
- Write `specs/0049-serving/findings.md`: the typed outcome
  (`GREEDY_REPRODUCIBLE` / `RESIDUAL_NONDETERMINISM`, with the offending tag+case
  named on a flip), the caveat set (bucket-not-bit-perfect; control-not-deployment),
  and the greedy found-but-unsubmitted (fu) observations (OQ3 — e.g. 14b still fu on
  pytest even greedy). Route a one-line note into MEMORY.
- Optional pin: `test_findings_records_typed_outcome_and_caveats` asserts findings.md
  carries the stable outcome marker + both caveats + the fu note (machine-readable).

### Step 15 — Refactor (optional)
- Extract the shared "resolve host once → `assert_local` → sanitized env with
  `OLLAMA_HOST`" subprocess seam used by `build_greedy_variant` and
  `read_live_modelfile` into one helper (`_local_ollama_env(host)`), so the
  provisioning-egress invariant lives in one place. All tests still pass.

## Delegation

- Steps 1–12 (unit parser/driver/config/proof) → keep in the implementer lane
  (pure Python, injected seams, runnable under `uv run pytest` now).
- Step 13 (live integration) → delegate to the operator/live-run agent (reason:
  needs the 0041-gated Ollama endpoint; the driver/probe code is already built and
  unit-covered, so this is a live-execution + artifact-commit task).
- Step 14 (findings/memory) → implementer after Step 13's outcome is known (the
  typed outcome depends on the live proof).

## Risk

- **Config-hash silent shift** — adding fields recomputes `BAKEOFF_CONFIG_HASH_0048`.
  Mitigation: Step 8 grep-guards that no committed 64-char literal pins the old value;
  ledger tests recompute; the new `SERVED_VARIANT_CONFIG_HASH` is the pinned digest.
- **2-draw/≥3-draw conflation** — reusing the 2-draw probe would understate the gate.
  Mitigation: Step 9/10 add a separate ≥3-draw orchestration; the 3-draw floor is a
  RED test (`..._requires_at_least_three_draws_per_cell`); the bucket oracle is reused
  by identity, arity is NOT.
- **Fingerprint grammar coercion** — a registry-normalized definition the grammar
  cannot represent losslessly could be silently coerced. Mitigation: fail-loud on
  dup keys / out-of-set directives (Step 1 RED); the SAME parser computes committed
  and live fingerprints so they are comparable by construction.
- **Live test passing trivially / leaking egress** — a down endpoint must SKIP, and
  subprocesses must not pick a stray daemon. Mitigation: positive `/api/tags`
  membership (empty set → all-False), `assert_local` on the resolved host FIRST,
  sanitized env with explicit `OLLAMA_HOST`, exclusivity recorded per live artifact.
- **AC1a discard cascade** — if the 0048 hand-created 14b tag diverges, its draws
  can't anchor the proof. Mitigation: AC1a records the reuse/discard decision; AC5
  runs fresh both-sides draws on the newly-created committed tag when discarded.
