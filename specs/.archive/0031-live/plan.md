---
spec: "0031-live"
status: planned
strategy: tdd
---

# Plan — 0031-live Trajectory-verified live measurement

Language is Python; tests are `test_*.py` siblings in the code's package. Project
test-naming convention (`.speccraft/conventions.md`): `def test_<subject>_<scenario>`
(snake_case). Every step is verifiable with `pytest`.

## Design decisions resolved in planning

- **New module:** `harpyja/eval/live_verifier.py` (unit-tested by
  `harpyja/eval/test_live_verifier.py`). It holds: `VERIFIER_SCHEMA_VERSION`,
  `FAILURE_CODES`, `VerifierResult`, `VerificationError`, the pure
  `verify_trajectory(traj) -> VerifierResult`, the four `extract_*` fact helpers,
  `build_trajectory_record(...)` (shared capture assembler), `validate_verifier_artifact`,
  `write_verifier_artifact` (delegates to `harpyja/eval/report.py:atomic_write_json`),
  and `verifier_preflight(...)`.
- **Trajectory artifact (verifier input)** — a dict carrying:
  `schema_version, requested_model, endpoint, served_model|None,
  configured_endpoint_models:[str], tiers_run:[int], model_turns:[{content, tool_calls}],
  terminal_bucket|None`. `model_turns` reuses the wire messages already in
  `LoopResult.history` (assistant records carry `tool_calls[].function.name`).
- **OQ1 three branches** (model identity), resolved:
  (a) `served_model` present and == `requested_model` → identity PROVEN;
  (b) `served_model` present and != `requested_model` → FAILED `model-mismatch`;
  (c) `served_model` absent → fall back to `configured_endpoint_models`: if
  `requested_model` is in that list, identity is PROVEN via fallback (details note the
  fallback source); if the list is empty or lacks it → FAILED `model-unknown`.
- **Failure precedence** (deterministic single `failure_reason` when multiple facts are
  unprovable), fixed check order: `artifact-incomplete` > `model-unknown` >
  `model-mismatch` > `model-not-invoked` > `tool-names-unextractable` >
  `terminal-bucket-missing`. Artifact-integrity is checked first (nothing else is
  trustworthy without it); first failing check wins.
- **model-invoked** fact = `(1 in tiers_run) AND len(model_turns) >= 1` (Tier-1 engaged
  AND at least one real model turn) — catches 0030-early's Tier-0 short-circuit.
- **tool_names_invoked** = ordered-unique names parsed from
  `model_turns[].tool_calls[].function.name`; a call object present but with no parseable
  name → FAILED `tool-names-unextractable`. Zero tool calls → `[]` (not a failure). This
  replaces 0030's monkeypatch of `_answer_tool_call`.
- **Capture seams (Phase 2)**: gateway surfaces `response.get("model")` additively;
  `ExplorerBackend` records `self.last_trajectory` after the loop (mirroring the existing
  `self.last_turns_used` seam) using `build_trajectory_record`. Neither changes decision
  behavior or the `run()` return type.
- **AC6 assembly**: a thin live harness merges `backend.last_trajectory` with `tiers_run`
  and the gold-span-derived `terminal_bucket` (reusing
  `harpyja/eval/locate_accuracy.py:normalize_citations`/`classify_case`), then
  verifies + writes the artifact.

## Test-first sequence

### Phase 1 — Verifier module (AC1-5, pure unit tests on fixtures)

### Step 1 — Artifact schema + atomic write (RED)
- Add `harpyja/eval/test_live_verifier.py`:
  - `test_verifier_artifact_schema_is_version_stamped_and_validated` — a complete artifact
    passes `validate_verifier_artifact`; dropping any required key fails it; `schema_version`
    equals `VERIFIER_SCHEMA_VERSION`.
  - `test_verifier_artifact_writes_outside_repo_atomically` — `write_verifier_artifact`
    writes under an out-dir and raises `ValueError` when the out-dir is inside `repo_path`.
- Tests fail: module `harpyja.eval.live_verifier` does not exist.

### Step 2 — Create the verifier artifact schema (GREEN)
- Implement `harpyja/eval/live_verifier.py` with `VERIFIER_SCHEMA_VERSION = "0031/1"`, the
  required-keys set, `validate_verifier_artifact`, and `write_verifier_artifact`
  (delegating to `report.atomic_write_json`).
- Step-1 tests pass.

### Step 3 — Four-fact PASS path + artifact-incomplete (RED)
- Add to `test_live_verifier.py` a `_traj(**overrides)` fixture builder and:
  - `test_verify_extracts_four_facts_from_valid_trajectory` — complete valid traj →
    `status=="PASSED"`, `failure_reason is None`, all of
    `model_identity/model_invoked/tool_names_invoked/terminal_bucket` populated (AC1 pass).
  - `test_verify_missing_required_field_fails_artifact_incomplete` — drop a required top-level
    field → `status=="FAILED"`, `failure_reason=="artifact-incomplete"` (AC1/AC5).
- Tests fail: `verify_trajectory`/`VerifierResult`/`VerificationError` do not exist.

### Step 4 — Verifier core + completeness gate (GREEN)
- Implement `VerifierResult`, `VerificationError`, `FAILURE_CODES`, and `verify_trajectory`
  with the completeness check first, then the four extractions returning `PASSED` when all
  provable (minimal: identity = served-present-and-matching only, invoked = model_turns
  nonempty, tools = plain name parse, bucket = present).
- Step-3 tests pass.

### Step 5 — Model-identity OQ1 three branches (RED, AC2)
- Add:
  - `test_verify_model_identity_matching_passes` — served == requested → PASSED.
  - `test_verify_model_identity_mismatch_fails_model_mismatch` — served != requested →
    FAILED `model-mismatch`.
  - `test_verify_model_identity_absent_resolves_via_configured_fallback` — served None but
    requested in `configured_endpoint_models` → PASSED; `details` records the fallback source.
  - `test_verify_model_identity_absent_and_unlisted_fails_model_unknown` — served None and
    fallback list empty/lacks requested → FAILED `model-unknown`.
- Tests fail: step-4 minimal only handles the present-and-matching branch.

### Step 6 — extract_model_identity with fallback (GREEN)
- Implement `extract_model_identity(traj)` with the three OQ1 branches + configured-list
  fallback. Step-5 tests pass.

### Step 7 — Model-invoked / Tier-0 short-circuit (RED, AC3)
- Add:
  - `test_verify_model_invoked_tier0_only_fails_model_not_invoked` — `tiers_run=[0]`,
    `model_turns=[]` → FAILED `model-not-invoked`.
  - `test_verify_model_invoked_requires_tier1_and_a_model_turn` — `tiers_run=[0,1]` with
    `model_turns=[]` → FAILED `model-not-invoked` (tier claim without a real turn).
- Tests fail: step-4 minimal did not require the `1 in tiers_run` condition.

### Step 8 — extract_model_invoked (GREEN)
- Implement `extract_model_invoked = (1 in tiers_run) and (len(model_turns) >= 1)`.
  Step-7 tests pass.

### Step 9 — Tool-name extraction, symbols distinguishability (RED, AC4)
- Add:
  - `test_verify_tool_names_lists_invoked_tools_by_name` — turns calling `grep` then
    `symbols` → `tool_names_invoked == ["grep", "symbols"]` (ordered-unique).
  - `test_verify_symbols_present_vs_absent_is_distinguishable` — a symbols-called traj vs a
    grep-only traj → `"symbols"` in one and not the other (the 0030-final miss).
  - `test_verify_tool_calls_without_names_fail_tool_names_unextractable` — tool_call objects
    lacking `function.name` → FAILED `tool-names-unextractable`.
- Tests fail: step-4 minimal parse mishandles unextractable + dedupe/order.

### Step 10 — extract_tool_names (GREEN)
- Implement ordered-unique name parse over `model_turns[].tool_calls[].function.name`;
  raise/flag `tool-names-unextractable` when a call object carries no parseable name.
  Step-9 tests pass.

### Step 11 — Terminal bucket (RED, AC1/AC4)
- Add:
  - `test_verify_terminal_bucket_present_passes` — `terminal_bucket="correct"` (one of
    correct/right-file-wrong-span/wrong-file/empty) → carried into the result.
  - `test_verify_terminal_bucket_missing_fails_terminal_bucket_missing` —
    `terminal_bucket` None/absent → FAILED `terminal-bucket-missing`.
- Tests fail: bucket-label validation not yet implemented.

### Step 12 — Terminal-bucket check (GREEN)
- Validate `terminal_bucket` against the four `LocateBucket` labels; missing/invalid →
  `terminal-bucket-missing`. Step-11 tests pass.

### Step 13 — Precedence, exactly-one status, all six codes reachable (RED, AC1/AC5c)
- Add:
  - `test_verify_status_is_exactly_passed_or_failed` — `status in {"PASSED","FAILED"}`;
    FAILED ⇒ `failure_reason in FAILURE_CODES`; PASSED ⇒ `failure_reason is None`.
  - `test_verify_failure_precedence_is_deterministic` — a traj unprovable on several facts
    (missing served + `tiers_run=[0]`) returns the single documented higher-precedence code.
  - `test_verify_all_six_failure_codes_reachable` — parametrized over the six codes, each
    fixture fires exactly its code (proves no silent pass; each unprovable fact ⇒ distinct code).
- Tests fail if precedence is not yet a fixed, documented order.

### Step 14 — Fix precedence ordering (GREEN)
- Add the `_CHECK_ORDER` constant encoding the precedence and route `verify_trajectory`
  through it. Step-13 tests pass.

### Step 15 — Refactor verifier internals (REFACTOR, optional)
- Consolidate the four `extract_*` helpers and the `_traj` fixture builder; ensure the
  tool-name parser is a single shared function (reused by Phase 2). All tests still green.

### Phase 2 — Capture seams (read-only measurement plumbing)

### Step 16 — Gateway surfaces served model (RED)
- Add to `harpyja/gateway/test_gateway.py`:
  - `test_complete_with_tools_surfaces_served_model` — fake transport returns a response
    with top-level `"model": "served-xyz"`; returned dict has `["model"] == "served-xyz"`.
  - `test_complete_with_tools_served_model_absent_is_none` — response without `model` →
    returned `["model"] is None`.
- Tests fail: the current return dict has no `model` key.

### Step 17 — Add model extraction to gateway (GREEN)
- In `harpyja/gateway/gateway.py:complete_with_tools`, add `"model": response.get("model")`
  to the returned dict (additive; `complete()` and request semantics untouched).
  Step-16 tests pass.

### Step 18 — Explorer backend trajectory capture (RED)
- Add to `harpyja/scout/test_explorer_backend.py`:
  - `test_run_captures_last_trajectory_after_loop` — inject a fake `model_call` producing two
    tool turns then `submit_citations`; after `run()`, `backend.last_trajectory` is a dict
    with `model_turns` (count matches turns), tool-call names including the injected tools,
    and `served_model` threaded from the model call.
  - `test_last_trajectory_is_reset_per_run` — `last_trajectory is None` before the first run
    and is replaced (not accumulated) on the next run.
- Tests fail: `ExplorerBackend.last_trajectory` and the served-model capture do not exist.

### Step 19 — Implement the backend capture seam (GREEN)
- In `harpyja/scout/explorer_backend.py`: initialize `self.last_trajectory = None`; have the
  `_default_model_call` wrapper record `self._last_served_model = resp.get("model")`; after
  `run_explorer_loop` returns (before any degrade raise), set
  `self.last_trajectory = build_trajectory_record(result.history, result.turns_used,
  served_model=self._last_served_model, endpoint=self._gateway.api_base)`. `run()` still
  returns `list[CodeSpan]`. Add `build_trajectory_record` to `live_verifier.py`, reusing the
  shared tool-name parser. Step-18 tests pass.

### Step 20 — Refactor shared trajectory helpers (REFACTOR, optional)
- Ensure `build_trajectory_record` and `verify_trajectory` share one tool-name parser and one
  `model_turns` shape. All tests green.

### Phase 3 — AC6 proof-of-instrument (integration)

### Step 21 — Verifier preflight (RED)
- Add to `test_live_verifier.py` (unit-level, injected payload/resolver):
  - `test_verifier_preflight_passes_when_model_present` — `/api/tags` payload lists the
    configured model → returns ok.
  - `test_verifier_preflight_fails_when_model_absent` — model absent → `PreflightError`
    naming the missing tag.
  - `test_verifier_preflight_rejects_non_localhost_endpoint` — non-loopback endpoint →
    `AirGapError` before any probe.
- Tests fail: `verifier_preflight` not implemented.

### Step 22 — Implement verifier_preflight (GREEN)
- Implement `verifier_preflight(settings, tags_payload, *, resolver=None)` in
  `live_verifier.py`, reusing `gateway.assert_local` first then a model-presence membership
  check (same discipline as `swebench_eval.preflight_models_present`). Step-21 tests pass.

### Step 23 — Proof-of-instrument re-run, astropy + django (RED, integration)
- Add `harpyja/eval/test_live_verifier_integration.py`:
  - `test_proof_of_instrument_astropy_django_produce_verifier_artifacts`
    (`@pytest.mark.integration`) — run `verifier_preflight`; if the gateway is unreachable,
    the model is absent, or the endpoint is non-localhost, `pytest.skip` with the documented
    invalid-setup reason (not a measurement failure). For each of `astropy-12907`,
    `django-12774`: build the live engine, drive the case, read `backend.last_trajectory`,
    assemble the full trajectory (merge `tiers_run` + gold-span `terminal_bucket`), call
    `verify_trajectory`, `write_verifier_artifact`; assert the artifact carries all four facts
    OR a distinct `failure_reason`, `status in {"PASSED","FAILED"}`, and record whether
    `"symbols" in tool_names_invoked` as-is (not graded). Assert both artifact files exist.
- Test fails: the `run_verified_case` assembly harness does not exist.

### Step 24 — Live assembly harness (GREEN)
- Implement `run_verified_case(case, settings, gateway, gold_span, out_dir)` (in
  `live_verifier.py` or a sibling `live_verifier_run.py`): construct the `ExplorerBackend`
  (directly, so `last_trajectory` is reachable), run the case, derive `terminal_bucket` via
  `locate_accuracy.normalize_citations`/`classify_case` against `gold_span`, merge
  `tiers_run`, build + verify + write the artifact, return `(VerifierResult, artifact_path)`.
  This replaces 0030's `_answer_tool_call` monkeypatch with durable capture. Step-23 test
  passes when the local stack is up; skips cleanly otherwise.

### Step 25 — Retire the 0030 monkeypatch logger (REFACTOR, optional)
- Point `harpyja/eval/test_symbols_lift_live.py` at `run_verified_case`/`tool_names_invoked`
  instead of monkeypatching `_answer_tool_call`, or annotate it as superseded by 0031. Any
  retained assertions still pass/skip.

### Phase 4 — Doc / convention reconciliation (AC7)

### Step 26 — 0029 committed-test vs changelog reconciliation (RED)
- Add to `harpyja/eval/test_harness_live.py`:
  - `test_recorded_model_matches_settings_or_documents_override` — assert the test's
    `_MODEL`/`_API` (16B, llama.cpp `127.0.0.1:8131`) either equals `Settings().lm_model`/
    default endpoint OR a committed `_MODEL_OVERRIDE_REASON` constant explicitly states why the
    run used a different model, with a linked spec/issue rationale.
- Test fails: no such constant/assertion exists; `_MODEL` currently diverges from Settings
  default (the documented 0029 mismatch) with nothing binding them.

### Step 27 — Commit the override rationale (GREEN)
- Add `_MODEL_OVERRIDE_REASON` (naming the reason + linked 0029/0031 rationale) and the
  reconciling assertion in `test_harness_live.py`. Code and recorded run are no longer at
  odds. Step-26 test passes.

### Step 28 — Codify the trajectory-verified convention (DOC)
- Add a convention to `.speccraft/conventions.md`: no live capability number is trusted
  without its verifier artifact + trajectory proof; binds all future live specs (bake-off,
  eval set, capability reports). Reference `harpyja/eval/live_verifier.py`,
  `VERIFIER_SCHEMA_VERSION`, and the six failure codes. Prose step (no test).

## Delegation

- Steps 1-22 (pure verifier + gateway/backend seams) → delegate to `codex`
  (strengths: refactoring — strong at tight, isolated Python units driven by fixtures;
  these steps have no live dependency and are fully TDD-checkable with `pytest`).
- Steps 23-24 (AC6 integration re-run) → run by the operator/live-run path (needs the local
  Model Gateway + pulled model). `codex` writes the harness; the live execution is an operator
  step gated by `verifier_preflight` (skips cleanly when the stack is absent).
- Steps 26-28 (0029 reconciliation + convention) → delegate to `claude-p`
  (strengths: general — spans the test edit, the committed rationale, and the conventions prose).

## Risk

- **Served model absent on the real endpoint (OQ1c).** Ollama/llama.cpp may omit
  `response['model']`. → Mitigation: the `configured_endpoint_models` fallback (Step 6) plus
  `verifier_preflight` (Step 22) resolve identity from `/api/tags`; only a genuine
  unresolvable case emits `model-unknown` — recorded, never silently passed.
- **`tiers_run` lives at the orchestrator/runner layer, not the backend.** The backend
  captures `model_turns`/tools/served-model; `tiers_run` is merged in at assembly (Step 24).
  → Mitigation: keep `tiers_run` an explicit assembly input; the unit fixtures (Phase 1) carry
  it directly so `model-not-invoked` is proven before any live wiring.
- **`ScoutEngine` wraps the backend, hiding `last_trajectory`.** → Mitigation: Step 24
  constructs `ExplorerBackend` directly (as the harness owner) so the seam is reachable without
  widening the `ScoutEngine` public surface.
- **AC6 flakiness / stack unavailable.** → Mitigation: `verifier_preflight` makes an absent or
  non-localhost stack a documented `pytest.skip` (invalid setup), never a false measurement
  failure; the artifact records `status` explicitly.
- **0030 monkeypatch coupling.** The old `_answer_tool_call` patch is brittle. → Mitigation:
  durable trajectory capture (Steps 18-19) supersedes it; Step 25 retires or annotates the
  old logger.
