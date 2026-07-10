---
id: "0038"
title: "reconciliation"
status: planned
strategy: tdd
created: 2026-07-10
---

# Plan — 0038 reconciliation

This spec is **probe-first, then a recorded transport switch** — NOT a greenfield build. 0034
already ships the tri-state `explorer_think` field, native `think` threading, `derive_think_mode`,
the `per_turn` accumulator, and the Deep-scope guard; 0037 already proved (committed evidence) that
Ollama's `/v1` OpenAI-compat layer silently drops the top-level `think` field while native
`/api/chat` with `think:false` genuinely toggles generation. The genuinely new surface is (a) a
committed PROBE that pins WHICH honoring path works on this Ollama across ALL THREE arms
(true/false/omitted) with native default/on OBSERVED (never inferred from 0037's false-control arm),
plus the endpoint-migration cost (tool_call_id presence, usage/reasoning field names); and (b) — only
if the probe says so — moving the explorer's WHOLE tool-calling loop onto the proven transport
INSIDE `ModelGateway`, deliberately superseding the 0034 `None ⇒ byte-identical` pin in the same
change.

**Sequencing law (PROBE-FIRST, hard gate):** the probe runs FIRST and returns exactly one typed
outcome (`native-api-chat` / `v1-variant` / `still-blocked`). NO production wiring is authored before
the probe resolves. The wiring phases (Steps 4–12) are CONDITIONAL on a honoring outcome; a
`still-blocked` result routes to a typed **STILL_BLOCKED** close (`findings.md` + self-skipping
conditional pins), named, never forced to pass. `v1-variant` routes to the smaller wiring set
(think passthrough on the existing `/v1` transport, no endpoint switch, the 0034 byte-identical pin
largely survives); `native-api-chat` (the 0037-proven leading candidate) routes to the full endpoint
migration below.

**Invariants honored throughout:** the honoring path ships as a `ModelGateway` method — the SINGLE
outbound abstraction — asserting `assert_local` BEFORE any I/O and carrying the finite per-socket-op
`timeout_s` (spec 0017 B3); NO parallel HTTP client anywhere. Unit tests use fakes (no live model);
`[integration]` files stay skip-not-fail; the deliverable-producing runs are LOUD STOP-AND-WARN
committed drivers. `explorer_`-scope ONLY — Deep/RLM untouched, enforced by an explicit negative
test. The 0038 probe artifact is a spec-local schema (`0038/1`), path-pinned against
`specs/.archive/0038-reconciliation/probes/…` FROM AUTHORING (0037's close proved live-path pins
break at archive time); while the spec is live+unarchived the pin resolves BOTH locations explicitly
per the evidence-path convention. The archived, drift-pinned
`specs/.archive/0037-explorer-think-knob/probes/probe_result.json` and its `test_think_probe_result.py`
expectations are NEVER edited. Reference instance: `qwen3:14b` on the dev Ollama.

## Test-first sequence

### Phase 0 — Reconcile-probe result contract + committed evidence (AC1)

#### Step 1 — Pin the 0038 probe-result schema, typed outcome, and split shape (RED)
- Add `harpyja/eval/test_reconcile_probe_result.py`:
  - `test_reconcile_probe_outcomes_are_the_three_typed_values` — imports `RECONCILE_PROBE_OUTCOMES`
    from `harpyja.eval.reconcile_probe` and asserts it equals
    `frozenset({"native-api-chat", "v1-variant", "still-blocked"})` (the TOTAL answer space; NOT a
    reuse of the 0037 outcome set).
  - `test_reconcile_probe_schema_version_is_0038_1` — asserts
    `RECONCILE_PROBE_SCHEMA_VERSION == "0038/1"` (own schema, not `0037/1`, not the verifier set).
  - `test_validate_reconcile_probe_result_accepts_a_conforming_result` — a fake dict with
    `chosen_path`, `outcome`, `usage_mapping` (the native→`completion_tokens` source, e.g.
    `{"completion_tokens": "eval_count"}`), the migration-cost block
    (`tool_call_id_present`, `usage_field_name`, `reasoning_field_name`), and per-arm observed facts
    for `think_true`/`think_false`/`omitted` (each: `content_present`, `finish_reason`,
    `completion_tokens`, `reasoning_chars`, `think_in_content`) validates clean.
  - `test_validate_rejects_unknown_outcome` / `_rejects_missing_usage_mapping` /
    `_rejects_missing_arm_block` / `_rejects_missing_migration_cost` / `_rejects_unknown_schema_version`
    — each raises `ReconcileProbeError`.
  - `test_committed_reconcile_probe_loads_and_validates` — loads
    `specs/.archive/0038-reconciliation/probes/probe_result.json` via `load_reconcile_probe_result`,
    asserts `schema_version == "0038/1"`, `model == "qwen3:14b"`, a loopback `endpoint`,
    `outcome in RECONCILE_PROBE_OUTCOMES`, and the split shape (`chosen_path` / `outcome` /
    `usage_mapping` / per-arm facts) is present.
- Tests fail: `harpyja/eval/reconcile_probe.py` does not exist yet (import error), AND the committed
  `probes/probe_result.json` does not exist yet (drift-pin: the claim cannot exist until the recorded
  evidence does).

#### Step 2 — Implement the reconcile-probe validator/enum (GREEN)
- Implement `harpyja/eval/reconcile_probe.py` with the MINIMAL surface, modeled on
  `harpyja/eval/think_probe.py`:
  - `RECONCILE_PROBE_OUTCOMES = frozenset({"native-api-chat", "v1-variant", "still-blocked"})`
  - `RECONCILE_PROBE_SCHEMA_VERSION = "0038/1"` (a NEW spec-local artifact schema; adds no persisted
    verifier field on its own).
  - `class ReconcileProbeError(ValueError)` — typed, loud on any non-conforming shape.
  - `validate_reconcile_probe_result(obj) -> None` — known schema_version, outcome in the set,
    model/endpoint present, `usage_mapping` present, the migration-cost block present, the three arm
    blocks present with the five per-arm keys.
  - `load_reconcile_probe_result(path) -> dict` — read JSON, validate, return.
- The module-contract + reject tests pass. `test_committed_reconcile_probe_loads_and_validates`
  STILL fails (no committed file) — satisfied by the operator step below.

#### Step 3 — Author + run the committed reconcile probe; commit the typed outcome (OPERATOR / LIVE — not unit-RED-able)
- Author `specs/0038-reconciliation/probes/run_probes.sh` — a LOUD curl-on-loopback STOP-AND-WARN
  operator script modeled on 0037's `run_probes.sh` (`qwen3:14b`, `set -e`, `/api/tags` preflight,
  resumable). It exercises the candidate honoring path (native `/api/chat`, the 0037-proven control)
  across ALL THREE arms — `think:true`, `think:false`, `think` OMITTED (the endpoint default; native
  default/on behavior OBSERVED, never inferred) — with the two-factor discrimination:
  - tiny-cap discriminator via `options.num_predict` (small cap): a genuinely-off arm surfaces
    content / `done_reason != "length"`; a still-thinking arm exhausts the cap reasoning-first;
  - the native usage cross-check (`eval_count` → `completion_tokens` per the mapping under test);
  - a `<think>`-in-content leak scan on the off arm.
  It ALSO scopes the migration cost — `tool_call_id` presence on a native tool-call response,
  the usage field name (`eval_count` vs served equivalent), and the reasoning field name
  (`message.thinking` vs served equivalent) — and re-checks any not-yet-ruled-out `/v1` passthrough
  arm before committing to a full switch. Raw per-arm outputs commit as `probes/probe_arm_*.json`.
- Run the driver against the dev Ollama, read the evidence, and hand-write
  `specs/0038-reconciliation/probes/probe_result.json` (schema `0038/1`, split shape) with the ONE
  typed `outcome` the evidence supports, the `chosen_path`, the `usage_mapping`, the migration-cost
  block, and the per-arm summaries.
- `test_committed_reconcile_probe_loads_and_validates` (Step 1) goes GREEN — the claim is now pinned
  to recorded evidence and can no longer drift. The pin resolves the `.archive` path (safe from
  authoring; the file lands there at close with no follow-up edit) and, while unarchived, the live
  `specs/0038-reconciliation/…` path explicitly per the evidence-path convention.

> **BRANCH GATE (read `probe_result.json.outcome` before Phase 1):**
> - `native-api-chat` → proceed to Steps 4–12 as the FULL endpoint migration (native `/api/chat`
>   inside `ModelGateway`, the 0034 byte-identical pin superseded per Step 6).
> - `v1-variant` → proceed to the SMALLER wiring set: add `think` passthrough on the EXISTING `/v1`
>   transport (no endpoint switch); Steps 4–5 collapse to a `/v1`-passthrough pin, the 0034
>   byte-identical pin survives (only the `think` key is added), Steps 6–12 assert against the `/v1`
>   outbound. Recorded as the honoring outcome.
> - `still-blocked` → typed **STILL_BLOCKED** close: Steps 4–12 are authored as self-skipping
>   conditional pins (skip WITH the recorded outcome as reason), no live effectiveness run is
>   constructible, close via `findings.md` (Step 15). A finding, never a forced pass, never a silent
>   re-point.

### Phase 1 — Native honoring path inside `ModelGateway` (AC4, AC2) — gated on a honoring outcome

#### Step 4 — Native adapter transport blast-radius pins (RED)
- Extend `harpyja/gateway/test_gateway.py` (new spec-0038 block) with the native `/api/chat` adapter
  method (`complete_with_tools_native`, the explorer's new single method):
  - `test_native_asserts_local_before_any_io` — a fake transport that records call order (or a
    non-loopback `api_base`) proves `assert_local` fires BEFORE the transport is touched (nothing is
    sent on a non-loopback endpoint — `AirGapError`).
  - `test_native_binds_finite_timeout_on_default_transport` — the configured finite `timeout_s`
    (never `None`) is bound onto the default native transport (spec 0017 B3).
  - `test_native_request_url_is_api_chat` — the resolved URL targets `…/api/chat` (derived from the
    configured base), NOT `…/chat/completions`.
  - `test_native_max_tokens_maps_to_options_num_predict` — request `max_tokens` → `options.num_predict`
    (the 0028 cap translation); no top-level `max_tokens` on the native wire.
  - `test_native_think_passthrough_true_false_and_omitted` — `think=True/False` ride top-level;
    `think=None` OMITS the field.
  - `test_native_done_reason_maps_to_finish_reason` — the pinned mapping TABLE, incl. the length-cap
    case (`done_reason == "length"` → `finish_reason == "length"` so the loop's truncation guard still
    fires) and the tool-call success case.
  - `test_native_eval_count_maps_to_completion_tokens` — response `eval_count` (or the probe-confirmed
    served equivalent, read from the committed `usage_mapping`) → `completion_tokens`. This mapping is
    proof-bearing (AC1/AC3 cite token deltas through it) and is pinned HERE first.
  - `test_native_thinking_field_maps_to_reasoning` — native thinking field (`message.thinking`) →
    `reasoning`; absent → `None`, present-empty → `""` (the 0034 0-vs-None floor).
  - `test_native_tool_calls_match_loop_shape` + `test_native_synthesizes_tool_call_id_when_absent` —
    native `tool_calls` map to the explorer loop's existing `{function:{name,arguments}, id}` shape;
    if the probe recorded `tool_call_id_present == false`, a positional/synthesized-id scheme
    (`call_0`, `call_1`, …) is applied so the 0029 answer-all-N protocol (keyed on `tool_call_id`)
    stays intact — an explicit, pinned adaptation, not an improvisation.
- Each pin is authored under the honoring-outcome gate (loads the committed 0038 artifact; skips WITH
  the recorded outcome on `still-blocked`). Tests fail: the native method/mappings do not exist yet.

#### Step 5 — Implement the native adapter in `ModelGateway` (GREEN)
- Implement `complete_with_tools_native` in `harpyja/gateway/gateway.py` (the single outbound
  abstraction): `assert_local` FIRST, finite `timeout_s` bound onto a `_default_native_transport`,
  URL `…/api/chat`, request `max_tokens → options.num_predict` + `think` passthrough (None omits),
  response `done_reason → finish_reason` (mapping table), `eval_count → completion_tokens`, native
  thinking → `reasoning`, native `tool_calls → {content, tool_calls, finish_reason, model, reasoning,
  completion_tokens}` with the synthesized-id scheme per the probe. Minimal code to green Step 4.

#### Step 6 — Move the explorer WHOLE onto the honoring transport + supersede the 0034 pin (RED)
- Extend `harpyja/scout/test_explorer_backend.py`:
  - `test_explorer_routes_tool_calls_through_native_transport` — the backend's default model-call
    invokes `gateway.complete_with_tools_native` (not the `/v1` `complete_with_tools`); all three arms
    {True/False/None} run through the SAME method (no per-value transport split).
  - **SUPERSEDE (same change, test + rationale together):** amend
    `test_default_outbound_request_body_pinned` and `test_default_outbound_carries_no_think_param` —
    the 0034 `None ⇒ captured == {"max_tokens": 2048}` byte-identical pin CANNOT survive the endpoint
    switch (URL changes; `max_tokens` becomes `options.num_predict`). Successor pin, with an inline
    rationale comment citing the 0038 exact-pin reconciliation: `None` ⇒ NO `think` field on the
    native transport's outbound request, AND `options.num_predict == 2048` with no top-level
    `max_tokens`.
  - Re-point `test_explorer_think_true_sends_think_true` / `_false` to assert against the native
    outbound.
- Tests fail: the backend still calls `complete_with_tools` (`/v1`); the amended pins assert the new
  native wire shape.

#### Step 7 — Route `ExplorerBackend` (+ wiring) to the native method (GREEN)
- Point `ExplorerBackend._default_model_call` at `gateway.complete_with_tools_native` and translate
  its params (`max_tokens`, `think`) to the native call; keep `scout/wiring.py`'s gateway
  construction (`assert_local` + `timeout_s` already threaded). Minimal code to green Step 6 and the
  Step-4 explorer-side pins. On the `v1-variant` branch this step is a no-op beyond adding the
  `think` passthrough on the existing method.

### Phase 2 — Live per-mode effectiveness on the honoring path (AC3) — gated

#### Step 8 — Live per-mode two-factor effectiveness test (RED / skip-not-fail)
- Extend `harpyja/eval/test_live_verifier_integration.py`:
  - `test_live_reconciled_think_knob_effectiveness` — `@pytest.mark.integration`, skip-not-fail.
    Preflight: `/api/tags` membership for `qwen3:14b`; `probe_reasoning_default` gate; and read the
    committed 0038 `probe_result.json` — skip WITH the recorded reason if
    `outcome == "still-blocked"`. Drives one `run_verified_case` per mode (on / off / default)
    through the NOW-native path via `dataclasses.replace(Settings(), explorer_think=…)`, off arm using
    a SMALL `explorer_max_tokens` (the tiny-cap discriminator). Asserts the two-factor proof as
    SEPARATE, non-collapsible assertions: (a) per-turn `reasoning_chars` present on on/default,
    absent/0 on off; (b) `completion_tokens` delta via the PINNED native `usage_mapping`; (c) no
    `<think>` leak in off-arm content. The 0037 tautology (config-derived recording) is explicitly NOT
    the proof — observed generation is. Docstring states off-arm N=1 evidence strength.
- Reads only persisted fields + the committed artifact; authoring it is the RED (as an integration
  file it skips, never red-fails CI).

#### Step 9 — Author + run the committed per-mode effectiveness driver (OPERATOR / LIVE)
- Author `specs/0038-reconciliation/run_effectiveness.sh` — a LOUD STOP-AND-WARN committed driver
  (preflight `/api/tags` + `probe_reasoning_default`; strict `require_live_stack` /
  `HARPYJA_REQUIRE_LIVE_STACK` switch converts the integration skip into a hard fail for the closure
  run) producing one verifier-clean persisted artifact per mode under `eval_work/live_artifacts/` via
  `live_artifact_dir`. Run it; Step 8's two-factor assertions hold on the produced artifacts → AC3
  GREEN. Record any off-vs-default cap interaction (OQ tuning) in `findings.md`; do NOT tune (that is
  the A/B's job).

### Phase 3 — Deep/RLM isolation (AC5)

#### Step 10 — Deep never calls the native adapter, emits no `think` field (RED / guard)
- Extend `harpyja/deep/test_rlm.py`:
  - `test_deep_does_not_call_native_adapter` — a spy gateway whose `complete_with_tools_native` raises
    if invoked; a Deep forward call must NOT touch it (Deep stays on its current path).
  - Confirm the existing `test_deep_outbound_carries_no_think_param` /
    `test_deep_outbound_carries_no_enable_thinking` remain green (Deep-scope guard rots-false on
    `explorer_`-scope leak).
- The negative test is RED-able: it fails if Step 7 accidentally routed the gateway change globally
  rather than explorer-scoped. Green once isolation holds (no new SUT code if Step 7 was correctly
  scoped).

### Phase 4 — Verifier four facts survive + serving transport recorded + `derive_think_mode` audit (AC6)

#### Step 11 — Four-facts-survive + optional serving-transport field + enum audit (RED)
- Extend `harpyja/eval/test_live_verifier.py`:
  - `test_four_facts_survive_native_trajectory` — `verify_trajectory` on a native-path trajectory
    still proves model_identity / model-invoked / tool_names / terminal-bucket (the four facts).
  - `test_trajectory_records_serving_transport` — `build_trajectory_record(..., serving_transport=…)`
    persists the serving transport (endpoint identity) as an OPTIONAL field, so the four-facts
    invariant is checkable per-transport; a legacy artifact WITHOUT it still validates (version-gated
    validator).
  - `test_derive_think_mode_disambiguates_post_switch` — the 0034 enum audit: assert the existing
    `derive_think_mode` labels (`native-think-true`/`native-think-false`/`default-omitted`) still
    disambiguate now that native think is genuinely effective. Extend the enum ONLY if this fails.
- Fails: `serving_transport` is not yet a `build_trajectory_record` field.

#### Step 12 — Add the optional serving-transport field + record the enum audit (GREEN)
- Add the optional `serving_transport` param/field to `build_trajectory_record` in
  `harpyja/eval/live_verifier.py` (bump `VERIFIER_SCHEMA_VERSION` to `"0038/1"`, version-gated
  validator so `0031/1`/`0033/1`/`0034/1` artifacts still validate), thread it from `ExplorerBackend`.
  Record in the step that the `derive_think_mode` audit PASSED (no enum change) — or, if Step 11
  proved otherwise, extend the enum in this same change. Green Step 11.

### Phase 5 — Supersede-with-record + doc (AC7)

#### Step 13 — Refactor: single reconcile-probe loader (REFACTOR, optional)
- Confirm the 0038 probe artifact is loaded/validated in ONE place
  (`load_reconcile_probe_result`), reused by the Step 1 pin, the Step 4/6 gates, and the Step 8 gate —
  no duplicated JSON parsing or inline outcome-string literals. All tests still pass.

#### Step 14 — Supersede-with-record the 0037 conditional AC2/AC3 (EDIT, recorded)
- Retire/re-point the 0037 conditional pins via an EXPLICIT, recorded edit:
  `test_explorer_think_pin_gated_on_native_probe_outcome` (in `test_explorer_backend.py`) and
  `test_live_think_knob_three_factor_effectiveness` (in `test_live_verifier_integration.py`) are keyed
  to the `/v1` top-level-`think` `no-op` outcome, which never legitimately flips (wiring moves OFF
  `/v1`). Add a rationale comment marking them SUPERSEDED-BY-0038 (0038 authors its own honoring-path
  live tests, Step 8) and re-point/retire them against the 0038 artifact. NEVER edit the archived
  `specs/.archive/0037-explorer-think-knob/probes/probe_result.json` nor
  `test_think_probe_result.py`'s expectations of that archived file.

#### Step 15 — findings.md (DOC)
- Author `specs/0038-reconciliation/findings.md` recording: the probe's typed `outcome` + `chosen_path`
  (cited to `probes/probe_result.json`); the transport/mechanism change — WHAT moved (`/v1` →
  native `/api/chat` inside `ModelGateway`), WHY, and the enumerated blast radius (tool_call
  send/parse + the `tool_call_id` scheme, `done_reason→finish_reason` table, `max_tokens→num_predict`,
  `eval_count→completion_tokens`, verifier four-facts, `assert_local`+`timeout_s` on the new path, the
  **superseded 0034 byte-identical pin**); the **0037 conditional AC2/AC3 supersede-with-record**
  (archived evidence untouched); the `derive_think_mode` audit result; and the **no-default-flip**
  statement (thinking on/off is the A/B's measurement, not decided here). On `still-blocked`, the
  typed STILL_BLOCKED close instead, per the two-terminal-paths invariant.

## Delegation

- Step 3 (reconcile-probe driver author + live run) → delegate to `live-eval-operator` (reason: needs
  the dev Ollama + `qwen3:14b`; LOUD curl-on-loopback STOP-AND-WARN operator script producing the
  committed deliverable — operator tooling outside the runtime air-gap).
- Step 9 (per-mode effectiveness driver author + strict live run) → delegate to `live-eval-operator`
  (reason: same live stack; strict `require_live_stack` closure run producing durable per-mode
  verifier artifacts under `eval_work/live_artifacts/`).
- Steps 1, 2, 4, 5, 6, 7, 8, 10, 11, 12, 13 (validator, native adapter, unit blast-radius pins,
  routing, integration-test authoring, Deep negative test, verifier field, refactor) → delegate to
  `tdd-implementer` (reason: fakes-only unit/adapter/harness work, no live model).
- Steps 14 (0037 supersede edit) and 15 (findings.md) → keep with the planner/closer (reason: the
  recorded supersede-with-record edit + the durable close artifact binding claim to evidence).

## Risk

- **Probe returns `still-blocked`** → mitigation: the branch is pre-authored, not discovered late —
  Steps 4–12 skip WITH the recorded outcome, `findings.md` carries the typed STILL_BLOCKED close, and
  the outcome is pinned by Step 1. A blocked result is a valid recorded close, never a pass-by-default
  and never a silent re-point of `explorer_think`.
- **Native `tool_calls` omit `tool_call_id`** (breaks 0029 answer-all-N) → mitigation: the probe
  scopes `tool_call_id_present` explicitly (Step 3); the synthesized-id/positional scheme is a pinned
  adaptation (Step 4/5), authored BEFORE wiring, not improvised after.
- **Reporting-vs-generation confound** (a native `think:false` that suppresses only the reasoning
  FIELD while still burning tokens / leaking `<think>`) → mitigation: three SEPARATE, non-collapsible
  assertions in both the probe (Step 3) and AC3 (Step 8) — `reasoning_chars`, the tiny-cap
  `completion_tokens` delta via the pinned mapping, and the `<think>` leak scan.
- **Superseded 0034 byte-identical pin read as a surprise regression** → mitigation: superseded
  DELIBERATELY in the same change (Step 6), test + rationale together, per the exact-pin reconciliation
  convention — never left to fail unexplained.
- **Two divergent gateway transports to maintain** (explorer native vs Deep `/v1`, spec OQ3) →
  mitigation: note the debt in `findings.md`; do NOT force-converge Deep in this spec (out of scope),
  and pin the isolation with the Step 10 Deep negative test.
- **New verifier field churns the schema** → mitigation: `serving_transport` is an ADDITIVE optional
  field under a version-gated `VERIFIER_SCHEMA_VERSION` bump (`0034/1 → 0038/1`), so legacy
  `0031/1`/`0033/1`/`0034/1` artifacts still validate; the reconcile-probe `0038/1` is a SEPARATE
  spec-local schema namespace, not the verifier schema.
- **Off-arm negative rests on N=1** → mitigation: stated explicitly in the Step 8 docstring and
  `findings.md` as acceptable for an API-level mechanism toggle, not implied as stronger.
