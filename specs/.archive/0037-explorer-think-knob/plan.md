---
id: "0037"
title: "explorer-think-knob"
status: planned
strategy: tdd
created: 2026-07-10
---

# Plan — 0037 explorer-think-knob

This spec is **regression + live-proof, not a rebuild**. 0034 already shipped the tri-state
`explorer_think` field, native `think` threading, `derive_think_mode`, `think_mode`/`per_turn`
recording (schema `0034/1`), the `bool|None` env coercion, and the Deep-scope leak guard. The
only genuinely new surface is (a) the committed PROBE that pins which request param actually
toggles generation, and (b) the live three-factor EFFECTIVENESS proof. Everything else is
assert-still-works.

**Sequencing law:** the probe runs FIRST and returns exactly one typed outcome
(`native-think-effective` / `chat-template-effective` / `no-op`). AC2 (unit pin) and AC3
(live effectiveness) are CONDITIONAL on `native-think-effective`; the other two outcomes route
to `findings.md` + a blocked-A/B close, and the AC2/AC3 tests record skipped-with-reason (a
legitimate terminal close per the spec's two-terminal-paths invariant). No unit request-body
assertion is authored against a param until the probe resolves.

**Invariants honored throughout:** unit tests use fakes (no live model); integration test files
stay skip-not-fail; the deliverable-producing runs are LOUD STOP-AND-WARN committed drivers;
NO schema bump (`0034/1` already carries `think_mode`/`per_turn` and `reasoning_chars`/
`completion_tokens` are already persisted — the plan adds NO new persisted field); `explorer_`-
scope only (no Deep/RLM change); ruff zero-new. Reference instance: `qwen3:14b` on the dev
Ollama `/v1` path. Probe transport: committed curl-on-loopback operator script (0034 precedent,
NOT a runtime egress path).

## Test-first sequence

### Phase 0 — Probe result contract + committed evidence (AC1)

#### Step 1 — Pin the probe-result schema and typed outcome (RED)
- Add `harpyja/eval/test_think_probe_result.py`:
  - `test_probe_outcomes_are_the_three_typed_values` — imports `PROBE_OUTCOMES` from
    `harpyja.eval.think_probe` and asserts it equals
    `{"native-think-effective", "chat-template-effective", "no-op"}` (the total outcome space,
    the 0023 every-input-returns-a-named-outcome discipline).
  - `test_validate_probe_result_rejects_unknown_outcome` — a fake dict with
    `outcome="thinking-off"` raises the module's typed error; a dict missing the per-arm block
    (`think_true`/`think_false`/`omitted`) raises.
  - `test_committed_probe_result_loads_and_validates` — loads
    `specs/0037-explorer-think-knob/probes/probe_result.json` via `load_probe_result(...)`,
    asserts `schema_version` is the known `PROBE_RESULT_SCHEMA_VERSION`, `model == "qwen3:14b"`,
    `endpoint` is a loopback `/v1` URL, `outcome in PROBE_OUTCOMES`, and each of the three arms
    carries `completion_tokens`, `finish_reason`, `content_present`, `think_in_content`.
- Tests fail: `harpyja/eval/think_probe.py` does not exist yet (import error), AND the committed
  `probes/probe_result.json` does not exist yet (drift-pin: the claimed outcome cannot exist
  until the evidence file does).

#### Step 2 — Implement the probe-result validator/enum (GREEN)
- Implement `harpyja/eval/think_probe.py` with the MINIMAL surface:
  - `PROBE_OUTCOMES = frozenset({"native-think-effective", "chat-template-effective", "no-op"})`
  - `PROBE_RESULT_SCHEMA_VERSION = "0037/1"` (a NEW spec-local artifact schema — NOT the verifier
    `0034/1` set; adds no persisted verifier field, so no verifier bump).
  - `class ProbeResultError(ValueError)` — typed, raised on any non-conforming shape.
  - `validate_probe_result(obj: dict) -> None` — loud validator (known schema_version, outcome in
    `PROBE_OUTCOMES`, model/endpoint present, the three arm blocks present with the four
    per-arm keys).
  - `load_probe_result(path) -> dict` — read JSON, validate, return.
- The two module-contract tests and the reject test pass. `test_committed_probe_result_loads_and_validates`
  STILL fails (no committed file) — that assertion is satisfied by the operator step below.

#### Step 3 — Author + run the committed probe driver; commit the typed outcome (OPERATOR / LIVE — not unit-RED-able)
- Author `specs/0037-explorer-think-knob/probes/run_probes.sh` — a LOUD curl-on-loopback operator
  script modeled on `specs/.archive/0034-reasoning-observability/probes/run_probes.sh`
  (`qwen3:14b`, `http://localhost:11434/v1/chat/completions`, `set -e`, STOP-AND-WARN on infra
  unavailability, resumable). It exercises the three-factor discrimination:
  - three arms — `think: true`, `think: false`, and `think` OMITTED;
  - the 0034 probe-A tiny-cap technique (small `max_tokens`, per probe-A) so a genuinely-stopped
    off arm surfaces content / `finish_reason != "length"` while a still-thinking model exhausts
    the cap reasoning-first with zero content;
  - `completion_tokens` comparison across arms;
  - a `<think>`-in-`content` leak scan on the off arm.
  Raw per-arm curl outputs commit as `probes/probe_arm_*.json`.
- Run the driver against the dev Ollama, read the evidence, and hand-write
  `specs/0037-explorer-think-knob/probes/probe_result.json` (schema `0037/1`) with the ONE typed
  `outcome` the evidence supports and the per-arm summary block.
- `test_committed_probe_result_loads_and_validates` (Step 1) now goes GREEN — the claim is pinned
  to the recorded evidence and can no longer drift.

> **BRANCH GATE (read `probe_result.json.outcome` before Phase 2):**
> - `native-think-effective` → proceed to Phase 2 (AC2) and Phase 3 (AC3).
> - `chat-template-effective` → SKIP AC2/AC3 (their tests record skipped-with-reason, Step 5/Step 7);
>   `findings.md` (Phase 5) records the finding + a reconciliation-revision note; the A/B is blocked;
>   NEVER a silent re-point of `explorer_think` at the other mechanism.
> - `no-op` → SKIP AC2/AC3 (skipped-with-reason); `findings.md` records the NO_OP_BLOCKED close; A/B blocked.
> Skipped-with-reason on the non-native branches is a legitimate terminal close, not a failure.

### Phase 2 — Tri-state request-body pin, conditional on the probe (AC2)

#### Step 4 — Conditional tri-state pin against the probe-confirmed native `think` param (RED)
- Extend `harpyja/scout/test_explorer_backend.py`:
  - `test_explorer_think_pin_gated_on_native_probe_outcome` — loads the committed
    `probe_result.json` via `load_probe_result`; if `outcome != "native-think-effective"` it
    `pytest.skip`s with the exact recorded outcome as the reason; otherwise it re-asserts the
    tri-state outbound-request pin against the probe-confirmed native param — `think=True →
    captured["think"] is True`, `think=False → captured["think"] is False`, `think=None →
    "think" not in captured` (byte-identical-to-default floor) — using the existing
    `_capturing_gateway` fake, and asserts the earlier `chat_template_kwargs`/"measured-correct
    param" hedge is dropped (no `chat_template_kwargs` key on the native arms).
- Test fails before the probe file is committed (Step 3): `load_probe_result` cannot find the
  file. It is the NEW conditional-on-probe guard — the underlying 0034 threading is already green.

#### Step 5 — Satisfy the conditional pin (GREEN — no new SUT code)
- No production change: 0034 already threads `params["think"]` from `ExplorerBackend`. Confirm
  `test_explorer_think_pin_gated_on_native_probe_outcome` passes when `outcome ==
  "native-think-effective"` (or cleanly skips-with-reason otherwise). Record explicitly in the
  step that this AC adds no code — it re-asserts shipped behavior against recorded evidence.

### Phase 3 — Live three-factor effectiveness proof, conditional + gated (AC3)

#### Step 6 — Three-factor effectiveness integration test (RED / skip-not-fail)
- Extend `harpyja/eval/test_live_verifier_integration.py`:
  - `test_live_think_knob_three_factor_effectiveness` — `@pytest.mark.integration`, skip-not-fail.
    Preflight: `/api/tags` membership for `qwen3:14b` (skip if absent); `probe_reasoning_default(gateway)`
    gate (skip-honest if this served model does NOT think by default — the 0023 input-validity
    rule, so a model property never misreads as "knob ineffective"); and read the committed
    `probe_result.json` — skip-with-reason if `outcome != "native-think-effective"`. Drives one
    `run_verified_case` per mode (on / off / default) via `dataclasses.replace(Settings(),
    explorer_think=...)`, off arm using a SMALL `explorer_max_tokens` (the tiny-cap discriminator),
    artifacts under `live_artifact_dir("think_effectiveness_<mode>")`. Asserts the THREE factors as
    THREE SEPARATE, non-collapsible assertions:
    - **(a) per-turn `reasoning_chars`** — on/default arms: `any(c and c > 0 ...)` over `per_turn`
      (≥1 turn `> 0`); off arm: `all(c in (None, 0) ...)` across ALL turns.
    - **(b) tiny-cap generation-level discriminator (off arm)** — the small-`max_tokens` off run
      produces `content` and/or `finish_reason != "length"` (generation genuinely stopped
      reasoning), NOT a reasoning-first cap exhaustion with empty content.
    - **(c) `completion_tokens` cross-check + `<think>`-in-content leak scan (off arm)** — off-arm
      `completion_tokens` compares against the on/default arms, AND no `model_turns` content on
      the off arm contains `"<think>"` (the reporting-vs-generation confound guard: a `think:false`
      that only suppresses the reasoning FIELD while still burning thinking tokens or leaking
      `<think>` into content must FAIL here, not pass).
    - Secondary (retained, NOT the effectiveness signal): `think_mode` recorded-matches-setting.
    - Docstring states the **off-arm N=1** evidence strength explicitly (one run, a handful of
      turns) as acceptable for an API-level mechanism toggle, not implied as more.
- As an integration file it never red-fails CI (skips without stack); authoring it is the RED.
  It reads only already-persisted `0034/1` fields — no new persisted field, no schema bump.

#### Step 7 — Author + run the committed per-mode effectiveness driver (OPERATOR / LIVE)
- Author `specs/0037-explorer-think-knob/run_effectiveness.sh` — a LOUD STOP-AND-WARN committed
  driver that preflights (`/api/tags` membership + `probe_reasoning_default`), refuses to silent-skip
  on infra absence, and drives the strict live run (per the `require_live_stack` /
  `HARPYJA_REQUIRE_LIVE_STACK` strict-switch convention that converts the integration skip into a
  hard fail for the closure run), producing one verifier-clean persisted artifact per mode under
  `eval_work/live_artifacts/` via `live_artifact_dir`. It commits nothing under the SUT; the durable
  artifacts survive the process (the 0035 persistent-artifacts rule).
- Run it; the three-factor assertions in Step 6 hold on the produced artifacts → AC3 GREEN. Record
  any observed off-vs-default `max_tokens`/tool-call interaction (spec OQ2) in `findings.md`, do NOT
  tune (that is the A/B's job).

### Phase 4 — Regression: the 0034 knob is assert-still-works (AC4)

#### Step 8 — Verify all shipped 0034 pins remain green (no new code)
- Run and confirm green (assert-still-works, no production change):
  - `harpyja/config/test_settings.py`: `test_explorer_think_default_is_none`,
    `test_explorer_think_is_declared_field_with_none_default` (field-default drift-guard),
    `test_explorer_think_env_coerces_to_bool` (`bool|None` env coercion).
  - `harpyja/scout/test_explorer_backend.py`: `test_default_outbound_carries_no_think_param`
    (byte-identity floor), `test_explorer_think_true_sends_think_true`,
    `test_explorer_think_false_sends_think_false`, and the `derive_think_mode` set
    (`test_think_mode_default_omitted`, `test_think_mode_native_think_true`,
    `test_think_mode_native_think_false`, `test_think_mode_chat_template_disabled`,
    `test_think_mode_native_wins_over_chat_template`).
  - `harpyja/eval/test_live_verifier.py`: `test_build_trajectory_record_carries_think_mode`,
    `test_written_artifact_carries_per_turn_and_think_mode` (the drop-at-assembly guard — think_mode
    in trajectory record AND written artifact).
  - `harpyja/deep/test_rlm.py`: `test_deep_outbound_carries_no_think_param` and
    `test_deep_outbound_carries_no_enable_thinking` (Deep-scope leak guard — rots false on
    `explorer_`-scope leak).
- No new code; if any is red, that is a genuine regression to fix before close.

### Phase 5 — Doc + durable findings (AC5)

#### Step 9 — Refactor: single probe-result loader reused by both consumers (REFACTOR, optional)
- Confirm the probe-result JSON is loaded/validated in ONE place (`load_probe_result` in
  `harpyja/eval/think_probe.py`), reused by both the Step 1 pin test and the Step 4 AC2 guard — no
  duplicated JSON parsing or inline outcome-string literals. All tests still pass.

#### Step 10 — findings.md (DOC)
- Author `specs/0037-explorer-think-knob/findings.md` (the 0021/0022 precedent) recording:
  - the probe's typed `outcome` (cited to `probes/probe_result.json`, the pinned evidence);
  - the **no default flip** statement, and the **N=2 think-experiment cited as motivation-for-the-A/B,
    explicitly NOT as evidence thinking helps** (mechanism unestablished, likely variance);
  - the terminal close taken: EFFECTIVE (AC2/AC3 landed → A/B unblocked) OR — on the
    `chat-template-effective` / `no-op` branch — the A/B-BLOCKING finding per the two-terminal-paths
    invariant (reconciliation-revision note for chat-template, NO_OP_BLOCKED for no-op), never a
    workaround and never a silent re-point.

## Delegation

- Step 3 (probe driver author + live run) → delegate to `live-eval-operator` (reason: needs the dev
  Ollama `/v1` endpoint + `qwen3:14b`; produces the committed deliverable via a LOUD curl-on-loopback
  STOP-AND-WARN script — operator tooling outside the runtime air-gap).
- Step 7 (per-mode effectiveness driver author + strict live run) → delegate to `live-eval-operator`
  (reason: same live stack; strict `require_live_stack` closure run producing durable per-mode verifier
  artifacts under `eval_work/live_artifacts/`).
- Steps 1, 2, 4, 5, 6, 9 (validator, unit pins, conditional guards, integration test authoring, refactor)
  → delegate to `tdd-implementer` (reason: fakes-only unit/harness work, no live model).
- Steps 8 (regression verification) and 10 (findings.md) → keep with the planner/closer (reason: no code;
  assert-still-works + the durable close artifact binding claim to evidence).

## Risk

- **Probe returns `chat-template-effective` or `no-op`** → mitigation: the branch is pre-authored, not
  discovered late — AC2/AC3 tests skip-with-reason, `findings.md` carries the A/B-blocking finding, and
  the outcome is pinned by the Step 1 unit test. A non-native result is a valid recorded close, never a
  pass-by-default and never a silent re-point of `explorer_think`.
- **Reporting-vs-generation confound** (a `think:false` that only suppresses the reasoning FIELD while the
  model still burns thinking tokens / leaks `<think>`) → mitigation: three SEPARATE, non-collapsible
  assertions in both the probe (Step 3) and AC3 (Step 6) — per-turn `reasoning_chars`, the tiny-cap
  generation-level discriminator, and `completion_tokens` cross-check + `<think>`-in-content scan; none
  may substitute for another.
- **Off-arm negative rests on N=1** → mitigation: stated explicitly in the AC3 test docstring and
  `findings.md` as acceptable for an API-level mechanism toggle, not implied as stronger.
- **Non-default-thinking served model misreads as "knob ineffective"** → mitigation: AC3 gates on
  `probe_reasoning_default` + the `qwen3:14b` `/api/tags` membership check and skips honestly (input-validity
  precondition), never a false SUT finding.
- **Infra unavailability** → mitigation: LOUD STOP-AND-WARN committed drivers (Steps 3, 7) that never
  silent-skip; the integration test FILE stays skip-not-fail so unrelated CI stays green while the
  closure run cannot go green by skipping (`require_live_stack`).
- **Accidental new persisted field / schema churn** → mitigation: the plan reads only existing `0034/1`
  fields (`per_turn`, `reasoning_chars`, `completion_tokens`, `think_mode`, `finish_reason`, `model_turns`
  content); `probe_result.json` is a spec-local `0037/1` artifact, NOT a verifier-schema field; assert no
  `VERIFIER_SCHEMA_VERSION` change.
