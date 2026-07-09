---
spec: "0034"
status: planned
strategy: tdd
---

# Plan — 0034 reasoning-observability

Test-first, ordered along the data path: **gateway → backend accumulator → record/artifact + schema → knob + guards → live → docs**. Every GREEN is preceded by a RED. Characterization pins come first (green now, stay green — the safety net the additive changes must not disturb). Drift-guards and the doc step are green-on-introduction by design (0028 AC8 / 0032 house style), called out as such.

Code-grounding confirmed before planning (wire shapes are load-bearing):
- Reasoning rides `choices[0].message.reasoning`; the cap's currency is top-level `usage.completion_tokens`; `finish_reason` is on the choice (probe C: `message` keys `[role, content, reasoning, tool_calls]`, `usage.completion_tokens=642`). Gateway today (`gateway.py` ~197-202) returns `{content, tool_calls, finish_reason, model}` and never reads `usage`.
- The DECIDED seam is real: `wrapped_model_call` (`explorer_backend.py` ~258-261) is the only site that sees every response including a `finish="length"` final turn; `_last_served_model` is a per-run last-write scalar reset in `run()` (~230). The accumulator grows here, resets beside it.
- `build_trajectory_record` (`live_verifier.py` ~312) takes keyword-defaulted optionals already; `run_verified_case` (~538-555) re-assembles the persisted artifact BY HAND (the 0033 copy lesson — a written-JSON test is required, not just a record test).
- Schema: `VERIFIER_SCHEMA_VERSION="0033/1"`, `_KNOWN_VERIFIER_SCHEMA_VERSIONS={"0031/1","0033/1"}`, gate in `validate_verifier_artifact` (~92).
- Knob wiring: `ExplorerBackend.__init__` takes `enable_thinking`/`max_tokens` ctor args (not settings directly); fed at `wiring.py:68` and `live_verifier.py:487`. `explorer_think` follows the same ctor-arg + two-site wiring path. `_default_model_call` (~213-215) is where the `think` param is added when non-None.

## Test-first sequence

### Step 1 — Characterization pins (CHARACTERIZATION; green now, stay green)
- Add to `harpyja/gateway/test_gateway.py`:
  - `Test_CompleteWithTools_ExistingReturnKeys_Pinned` — the pre-0034 return dict keys `{content, tool_calls, finish_reason, model}` are all present (additive floor the new keys must not remove).
- Add to `harpyja/scout/test_explorer_backend.py`:
  - `Test_DefaultOutbound_RequestBody_Pinned` — capture the params a default-`Settings` `_default_model_call` sends to `complete_with_tools`; assert exactly `{"max_tokens": 2048}` (no `think`, no `chat_template_kwargs`). This is the byte-identity baseline AC3 defends.
- Add to `harpyja/eval/test_live_verifier.py`:
  - `Test_ValidFixture_VerifyOutcome_Pinned` — record `(status, failure_reason, four fact fields)` for the existing valid-trajectory fixture(s). The AC4 baseline.
- Tests pass on current code (characterization).

### Step 2 — Gateway surfaces reasoning + completion_tokens (RED)
- Add to `harpyja/gateway/test_gateway.py`:
  - `Test_CompleteWithTools_SurfacesReasoning` — `message.reasoning="…2833 chars…"` → return `reasoning` equals it.
  - `Test_CompleteWithTools_ReasoningAbsent_IsNone` — no `reasoning` key on message → `reasoning is None`.
  - `Test_CompleteWithTools_ReasoningPresentEmpty_IsEmptyString` — `message.reasoning=""` → `reasoning == ""` (the honest 0-vs-None distinction at the source).
  - `Test_CompleteWithTools_SurfacesCompletionTokens` — `usage.completion_tokens=642` → return `completion_tokens == 642`.
  - `Test_CompleteWithTools_CompletionTokensAbsent_IsNone` — no `usage` → `completion_tokens is None`.
  - `Test_CompleteWithTools_ExistingKeys_Unchanged` — `content/tool_calls/finish_reason/model` values identical to pre-0034 on the same fake response.
- Tests fail: `reasoning`/`completion_tokens` keys are not in the return dict (KeyError / assertion).

### Step 3 — Gateway return dict (GREEN)
- `harpyja/gateway/gateway.py` `complete_with_tools`: add to the returned dict, additively, `"reasoning": message.get("reasoning")` (absent → None, present-empty → "") and `"completion_tokens": (response.get("usage") or {}).get("completion_tokens")`. No transport change, no second path.
- All Step-1 and Step-2 gateway tests pass.

### Step 4 — Record builder grows per-turn + think_mode (RED)
- Add to `harpyja/eval/test_live_verifier.py`:
  - `Test_BuildTrajectoryRecord_CarriesPerTurn` — passing `per_turn=[{...}]` lands verbatim under a named record key (`per_turn`).
  - `Test_BuildTrajectoryRecord_CarriesThinkMode` — `think_mode="default-omitted"` lands on the record.
  - `Test_BuildTrajectoryRecord_PerTurnDefaults_WhenOmitted` — omitting both yields a safe default (`per_turn == []`, `think_mode` defaulted/absent) — legacy callers unbroken.
  - `Test_Record_Discriminates_ReasoningTruncated_From_ContentTruncated_And_Clean` — three per-turn shapes are distinguishable IN THE RECORD: reasoning-truncated (`finish_reason="length", reasoning_chars>0, completion_tokens=cap`, empty content/tool_calls — probe A), content-truncated (`finish_reason="length", reasoning_chars=0`), clean (`finish_reason="tool_calls"`).
- Tests fail: `build_trajectory_record` has no `per_turn`/`think_mode` params (TypeError).

### Step 5 — build_trajectory_record additive params (GREEN)
- `harpyja/eval/live_verifier.py` `build_trajectory_record`: add keyword params `per_turn: list[dict] | None = None` and `think_mode: str | None = None`; write `"per_turn": per_turn or []` and (when non-None) `"think_mode": think_mode` onto the record. Additive-last, defaulted.
- All Step-4 tests pass; Step-1 fixture test unchanged.

### Step 6 — think_mode derivation, one function pinned per combination (RED)
- Add to `harpyja/scout/test_explorer_backend.py`:
  - `Test_ThinkMode_DefaultOmitted` — `(think=None, enable_thinking=True) → "default-omitted"`.
  - `Test_ThinkMode_NativeThinkTrue` — `(think=True, *) → "native-think-true"`.
  - `Test_ThinkMode_NativeThinkFalse` — `(think=False, *) → "native-think-false"`.
  - `Test_ThinkMode_ChatTemplateDisabled` — `(think=None, enable_thinking=False) → "chat-template-disabled"`.
  - `Test_ThinkMode_Unknown_Fallback` — an out-of-enum combination → `"unknown"`.
  - `Test_ThinkMode_NativeWinsOverChatTemplate` — `(think=False, enable_thinking=False)` pins native precedence (`"native-think-false"`), so the record is never ambiguous.
- Tests fail: `derive_think_mode` does not exist (ImportError).

### Step 7 — derive_think_mode (GREEN)
- `harpyja/scout/explorer_backend.py`: add module fn `derive_think_mode(think: bool | None, enable_thinking: bool) -> str` — native (`think` set) checked first, then `enable_thinking False → chat-template-disabled`, then `None+True → default-omitted`, else `unknown`.
- All Step-6 tests pass.

### Step 8 — Backend accumulator + wiring into record (RED)
- Add to `harpyja/scout/test_explorer_backend.py`:
  - `Test_Run_AccumulatesPerTurn_ReasoningAndFinish` — a two-turn scripted run lands two `per_turn` entries on `last_trajectory` with `(reasoning_chars, completion_tokens, finish_reason)`.
  - `Test_Accumulator_CapturesFinalLengthTruncatedTurn` — a final response with `finish_reason="length"` (the loop returns before session.add) still contributes a `per_turn` entry even though `model_turns` does NOT grow for it — the AC2 discriminator the history route can't reach.
  - `Test_Accumulator_ResetPerRun` — `per_turn` from run 1 does not leak into run 2 (reset beside `_last_served_model`).
  - `Test_PerTurn_ReasoningChars_NoneWhenAbsent_ZeroWhenEmpty` — response with no `reasoning` → `reasoning_chars is None`; `reasoning=""` → `0` (never fabricated).
  - `Test_LastTrajectory_CarriesThinkMode` — `last_trajectory["think_mode"]` matches `derive_think_mode` for the backend's config.
- Tests fail: no accumulator attribute; `last_trajectory` has no `per_turn`/`think_mode`.

### Step 9 — Backend accumulator (GREEN)
- `harpyja/scout/explorer_backend.py`:
  - Add ctor arg `think: bool | None = None` → `self._think`; wire it at `wiring.py` and `live_verifier.py` construction sites from `settings.explorer_think`.
  - Init `self._per_turn: list[dict] = []`; reset it in `run()` beside `_last_served_model = None`.
  - In `wrapped_model_call`, after the call append `{"reasoning_chars": len(r) if (r:=response.get("reasoning")) is not None else None, "completion_tokens": response.get("completion_tokens"), "finish_reason": response.get("finish_reason")}`.
  - Pass `per_turn=self._per_turn` and `think_mode=derive_think_mode(self._think, self._enable_thinking)` into `build_trajectory_record`.
- All Step-8 tests pass; Step-1 trajectory characterization holds.

### Step 10 — Schema bump + version gate (RED)
- Add to `harpyja/eval/test_live_verifier.py`:
  - `Test_SchemaVersion_Is_0034_1` — `VERIFIER_SCHEMA_VERSION == "0034/1"`.
  - `Test_Legacy_0031_And_0033_Artifacts_StillValidate` — artifacts stamped `0031/1` and `0033/1` (no reasoning fields) pass `validate_verifier_artifact` unchanged (defaulted, never rejected).
  - `Test_0034_Artifact_ReasoningFields_Optional` — a `0034/1` artifact lacking `per_turn`/`think_mode` still validates (a non-reasoning model legitimately produces none).
- Tests fail: version is still `0033/1`; `0034/1` not in the known set.

### Step 11 — Schema bump (GREEN)
- `harpyja/eval/live_verifier.py`: `VERIFIER_SCHEMA_VERSION = "0034/1"`; add `"0034/1"` to `_KNOWN_VERIFIER_SCHEMA_VERSIONS` (keep `0031/1`, `0033/1`). Do NOT add the new fields to `required_keys` (they stay optional/defaulted).
- All Step-10 tests pass; Step-1 fixture-verify OUTCOMES unchanged.

### Step 12 — Persisted artifact copies per_turn + think_mode (RED)
- Add to `harpyja/eval/test_live_verifier.py` (against the WRITTEN JSON, the 0033 lesson):
  - `Test_WrittenArtifact_CarriesPerTurn_And_ThinkMode` — drive `run_verified_case` with a stub backend whose `last_trajectory` carries `per_turn`/`think_mode`; read back the written artifact JSON and assert both fields survive assembly.
- Tests fail: `run_verified_case`'s hand-built artifact dict (~538-555) omits the new fields.

### Step 13 — run_verified_case artifact assembly (GREEN)
- `harpyja/eval/live_verifier.py` `run_verified_case`: copy `"per_turn": last_trajectory.get("per_turn", [])` and `"think_mode": last_trajectory.get("think_mode")` into the written `artifact` dict (mirror the `citations_submitted/surviving` copy).
- Step-12 test passes.

### Step 14 — Settings knob field + drift guard (RED)
- Add to `harpyja/config/test_settings.py`:
  - `Test_ExplorerThink_Default_IsNone` — `Settings().explorer_think is None`.
  - `Test_ExplorerThink_IsDeclaredField` — field-default introspection over `dataclasses.fields(Settings)` (the 0028 pattern; drift guard, not a source grep) confirms `explorer_think` declared with default `None`.
  - `Test_ExplorerThink_Env_CoercesToBool` — `HARPYJA_EXPLORER_THINK` env → coerced `True/False`.
- Tests fail: `Settings` has no `explorer_think`.

### Step 15 — Settings field (GREEN)
- `harpyja/config/settings.py`: add `explorer_think: bool | None = None` (additive-last, `explorer_`-scoped), with `__post_init__`/env coercion mirroring `explorer_enable_thinking`.
- Step-14 tests pass.

### Step 16 — Default no-op body pin + knob param (RED)
- Add to `harpyja/scout/test_explorer_backend.py`:
  - `Test_DefaultOutbound_CarriesNoThinkParam` — default `Settings` (think=None): captured outbound params carry NO `think` key (byte-identical to Step-1's pin).
  - `Test_ExplorerThinkTrue_SendsThinkTrue` — `explorer_think=True` → outbound params include `think=True`.
  - `Test_ExplorerThinkFalse_SendsThinkFalse` — `explorer_think=False` → outbound params include `think=False`.
- Tests fail: `_default_model_call` never adds `think`.

### Step 17 — _default_model_call think param (GREEN)
- `harpyja/scout/explorer_backend.py` `_default_model_call`: after the max_tokens/chat_template assembly, `if self._think is not None: params["think"] = self._think`. None ⇒ omit ⇒ request byte-identical.
- Step-16 tests pass; Step-1 default-body pin still holds.

### Step 18 — Deep outbound guard extended (DRIFT-GUARD; green on introduction)
- Add to `harpyja/deep/test_rlm.py` (extend the existing outbound-field guard file):
  - `test_deep_outbound_carries_no_think_param` — `explorer_think=True` in Settings; Deep's captured forward kwargs carry no `think`.
  - `test_deep_outbound_carries_no_explorer_think` — the `explorer_think` value never leaks into Deep's outbound kwargs.
- Passes on introduction (Deep never carries the explorer knob); ROTS FALSE if a future change leaks it. No production change.

### Step 19 — AC4 outcome-equality regression pin (REGRESSION)
- Add to `harpyja/eval/test_live_verifier.py`:
  - `Test_VerifyTrajectory_OutcomeEquality_OverValidFixtures` — over the existing valid-fixture set, `verify_trajectory` yields the SAME `(status, failure_reason, four fact fields)` as the Step-1 pin, post-schema-bump. Byte-identity explicitly disclaimed in a comment (`to_dict()` stamps `0034/1`). Four-facts contract and the six failure codes untouched.
- Passes (the additive changes preserve outcomes); the guard rots false if a fact or code drifts.

### Step 20 — AC5 live recording proof with precondition fallback (RED)
- Add to `harpyja/eval/test_live_verifier_integration.py`:
  - `Test_Live_RecordsNonzeroReasoning_Or_NotExercised` — 0023 precondition pattern: preflight one direct `/v1` call ("does THIS served model emit `reasoning` by default?"). If yes → a live explorer run must record ≥1 `per_turn` entry with `reasoning_chars > 0`. If no → print/record NOT-EXERCISED (never a silent pass). Skip-not-fail when the stack is absent (no loopback endpoint / model not served).
- Fails until a small preflight helper exists (probes reasoning-default cleanly).

### Step 21 — AC5 preflight probe helper (GREEN)
- `harpyja/eval/live_verifier.py`: add `probe_reasoning_default(gateway) -> bool` (one `/v1` call, air-gap-first via existing `assert_local`, returns whether `message.reasoning` is present/non-empty by default). Reuse in the integration test.
- Step-20 test passes (or skips/NOT-EXERCISED cleanly) against a live stack.

### Step 22 — conventions.md doc (DOC)
- `.speccraft/conventions.md`: add the "invisible generation is a measurement-integrity defect" rule — any model-generated stream that consumes budget must be observable in the trajectory artifact (per-turn `reasoning_chars` + `completion_tokens` + `finish_reason`); record the 0031–0033 baseline asterisk (measured under invisible-truncation RISK). Cite `complete_with_tools`, the backend accumulator, `build_trajectory_record`, schema `0034/1`.

### Step 23 — Refactor (optional)
- Extract the per-turn tuple construction and the none-vs-zero `reasoning_chars` rule into one small helper if Steps 9/12 duplicate it; keep ruff clean (no new errors). All tests still pass.

## Delegation

- Steps 2–3 (gateway) → keep local: single additive return-dict change, self-contained; strongest match to the gateway test file already pinning `finish_reason`/`model`.
- Steps 4–13 (record/accumulator/schema/artifact) → the verifier+backend seam is the plan's center of gravity; sequence them under one implementer to hold the `build_trajectory_record` ↔ `run_verified_case` copy invariant (the 0033 written-JSON lesson) in view.
- Steps 14–18 (knob + guards) → the 0028 generation-control-scoping owner: same ctor-arg + two-site wiring + Deep drift-guard shape.
- Step 20–21 (live) → whoever owns the 0031/0023 live-precondition pattern (skip-not-fail, NOT-EXERCISED).

## Risk

- **Accumulator/model_turns length skew** — `per_turn` (every response, incl. the truncated final) and `model_turns` (history, minus the truncated final) have DIFFERENT lengths by design. Mitigation: Step-8 `Test_Accumulator_CapturesFinalLengthTruncatedTurn` pins the skew as intended; document it at the record key. Consumers must not zip the two lists positionally past `len(model_turns)`.
- **Persisted-artifact drift** — `run_verified_case` re-assembles the artifact by hand, so a record-only test would pass while the written JSON drops the fields (the exact 0033 defect). Mitigation: Step-12 asserts against the WRITTEN JSON, not the record.
- **think_mode ambiguity on double-set** (`explorer_think=False` + `enable_thinking=False`) — Mitigation: Step-6 `Test_ThinkMode_NativeWinsOverChatTemplate` pins native precedence so the enum is total and unambiguous.
- **Default byte-identity regression** — the knob's whole safety claim is "None ⇒ omit". Mitigation: Step-1 body pin + Step-16 no-think-param test bracket it; rots false on any drift.
- **AC5 model-contingency** — reasoning-by-default is instance-relative (qwen3/this Ollama), not portable. Mitigation: the preflight probe + NOT-EXERCISED fallback; the mechanism proof lives in the hermetic AC1/AC2 fixtures, not the live run.
