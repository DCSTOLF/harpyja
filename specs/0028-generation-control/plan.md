---
spec: "0028"
status: planned
strategy: tdd
---

# Plan — 0028 generation-control

Test-first sequence in strict dependency order: **AC0 → AC2 → AC1 → AC8 guard →
AC3 (loop → backend → runner → report) → live AC4/AC5 → operator AC6/AC7**. AC0
(`finish_reason`) lands FIRST because AC3/AC4/AC5 all branch on it and are
untestable without it. Every GREEN is preceded by a RED naming a concrete failing
test. Python/pytest; test files are `test_*.py` colocated with source; async is
driven via `asyncio.run` (no plugin). Naming convention: `test_<subject>_<scenario>`.

Byte-untouched by construction (assert nothing changed, change nothing):
`submit_citations`, the four-tool suite `{grep,glob,read_span,ls}` + terminal
`submit_citations` (EXACT-TOOL-COUNT — this spec adds NO tools), the orchestrator,
gate, matrix, ScoutEngine/Locator seam, and the single gateway air-gap enforcement
point (AIR-GAP). `ModelGateway` gains NO `max_tokens` default of its own — it stays
purely param-driven so the Deep path is never capped (AC8).

## Test-first sequence

### Step 1 — `finish_reason` surfaced from the gateway return contract (RED) [AC0]
- Add to `harpyja/gateway/test_gateway.py`:
  - `test_complete_with_tools_surfaces_finish_reason` — transport returns
    `{"choices": [{"finish_reason": "tool_calls", "message": {...}}]}`; assert
    `out["finish_reason"] == "tool_calls"`. (`finish_reason` lives on the CHOICE,
    not the message.)
  - `test_complete_with_tools_finish_reason_defaults_unknown_when_absent` —
    transport omits `finish_reason`; assert `out["finish_reason"] == "unknown"`
    (exact sentinel string).
  - `test_complete_with_tools_finish_reason_is_additive_backward_compatible` —
    reuse the existing anchor payload (message with `content`/`tool_calls`, NO
    `finish_reason`); assert the two existing keys are unchanged AND
    `out["finish_reason"] == "unknown"` (backward-additive, third key only).
- Tests fail: `complete_with_tools` (lines 190-193) returns only
  `{content, tool_calls}` — no `finish_reason` key ⇒ `KeyError`/assertion fail.

### Step 2 — Add `finish_reason` additive key (GREEN) [AC0]
- Edit `harpyja/gateway/gateway.py` `complete_with_tools` (lines 188-193): read
  `choice = response["choices"][0]`, then `fr = choice.get("finish_reason")`, and
  return the third key `"finish_reason": str(fr) if fr is not None else "unknown"`
  alongside the unchanged `content` / `tool_calls`. Update the docstring return
  shape to `{content, tool_calls, finish_reason}`. No other change; air-gap
  ordering and `**params` forwarding untouched.
- All Step-1 tests pass. (AIR-GAP: single enforcement point unchanged.)

### Step 3 — `explorer_max_tokens` Settings + object-level drift-guard (RED) [AC2]
- Add to `harpyja/config/test_settings.py`:
  - `test_explorer_max_tokens_default_is_2048` — `Settings().explorer_max_tokens == 2048`.
  - `test_explorer_max_tokens_env_coerces_to_int` — `HARPYJA_EXPLORER_MAX_TOKENS=512`
    resolves to `int` `512` (env-coercion via `_FIELD_TYPES`/`_coerce` int branch).
- Add to `harpyja/scout/test_explorer_backend.py`:
  - `test_explorer_backend_max_tokens_field_default_is_2048` — via
    `inspect.signature(ExplorerBackend.__init__).parameters["max_tokens"].default
    == 2048` (field-default INTROSPECTION, NEVER a source grep — DRIFT-GUARD
    convention: the finite runaway-guarding cap lives on the constructed object's
    OWN field default so a `Settings`-bypassing construction is still bounded).
  - `test_default_model_call_passes_max_tokens_to_gateway` — build an
    `ExplorerBackend` with a fake gateway recording `complete_with_tools` kwargs;
    invoke `_default_model_call()`'s returned `call`; assert the fake received
    `max_tokens=2048`.
- Tests fail: `explorer_max_tokens` does not exist on `Settings`;
  `ExplorerBackend.__init__` has no `max_tokens` param; `_default_model_call`
  (lines 176-177) passes no `max_tokens`.

### Step 4 — Thread `explorer_max_tokens` to the request (GREEN) [AC2]
- `harpyja/config/settings.py`: append `explorer_max_tokens: int = 2048`
  additive-LAST (after `lm_http_timeout_s` at line 144, following the
  `scout_ls_max_entries` additive-last pattern). No coercion code needed (int
  branch already handles it). (ADDITIVE-SETTINGS convention.)
- `harpyja/scout/explorer_backend.py` `__init__` (lines 139-167): add kwarg
  `max_tokens: int = 2048` stored as `self._max_tokens` (the OWN field default =
  2048 is here — the drift-guard target). `_default_model_call`'s inner `call`
  (line 177): pass `max_tokens=self._max_tokens` into
  `self._gateway.complete_with_tools(messages, schemas, max_tokens=self._max_tokens)`.
- `harpyja/scout/wiring.py` `build_scout_engine` (lines 53-60): construct
  `ExplorerBackend(..., max_tokens=settings.explorer_max_tokens)` so Settings
  feeds the object default at the wire site.
- `ModelGateway` UNCHANGED (no `max_tokens` default — param-driven only).
- All Step-3 tests pass.

### Step 5 — `explorer_enable_thinking` knob, bidirectional threading (RED) [AC1]
- Add to `harpyja/config/test_settings.py`:
  - `test_explorer_enable_thinking_default_is_true` — `Settings().explorer_enable_thinking is True`.
  - `test_explorer_enable_thinking_env_coerces_to_bool` —
    `HARPYJA_EXPLORER_ENABLE_THINKING=false` resolves to `bool` `False`
    (bool coercion, lines 173-176).
- Add to `harpyja/scout/test_explorer_backend.py`:
  - `test_thinking_off_sends_enable_thinking_false` — construct backend with
    `enable_thinking=False`; the fake gateway records
    `chat_template_kwargs == {"enable_thinking": False}`.
  - `test_thinking_on_omits_chat_template_kwargs` — construct with
    `enable_thinking=True`; the recorded kwargs do NOT contain
    `chat_template_kwargs` at all (omission, not `True`).
  - `test_explorer_rejects_no_think_query_token` — assert the outbound request
    (query/messages) carries NO `/no_think` token (measured inferior at 43s; the
    knob is `chat_template_kwargs`, never a query-token path).
- Tests fail: no `explorer_enable_thinking` field; no `enable_thinking` param;
  `_default_model_call` never sets `chat_template_kwargs`.

### Step 6 — Thread the thinking knob (GREEN) [AC1]
- `harpyja/config/settings.py`: append `explorer_enable_thinking: bool = True`
  additive-LAST (provisional default — thinking-ON+cap measured clean at 2.5s;
  AC6 finalizes). Bool coercion already handled.
- `harpyja/scout/explorer_backend.py` `__init__`: add kwarg
  `enable_thinking: bool = True` → `self._enable_thinking`. In
  `_default_model_call`'s `call`: when `self._enable_thinking is False`, pass
  `chat_template_kwargs={"enable_thinking": False}` into `complete_with_tools`;
  when True, OMIT it. `gateway.complete_with_tools` already forwards `**params`
  into the payload — NO gateway change needed for threading (AC0's return change
  was the only gateway edit).
- `harpyja/scout/wiring.py`: add `enable_thinking=settings.explorer_enable_thinking`
  to the `ExplorerBackend(...)` construction.
- All Step-5 tests pass.

### Step 7 — Refactor `_default_model_call` param assembly (REFACTOR, optional) [AC1/AC2]
- Steps 4 and 6 both mutate the same `call` kwargs; fold `max_tokens` +
  conditional `chat_template_kwargs` into one `params` dict built once before the
  `complete_with_tools` call, to remove the branch-and-append duplication.
- All Step-3/Step-5 tests still pass.

### Step 8 — Deep scope guard: explorer knobs never leak to Deep (GUARD, passes on introduction) [AC8]
- Add `harpyja/deep/test_rlm.py` (cleanest injection seam located by reading
  `rlm.py`: the public `rlm_factory=` constructor kwarg; `RlmBackend.run` invokes
  the returned rlm as `rlm(query=...)` at line 119 — the outbound call this guard
  inspects):
  - `test_deep_outbound_carries_no_explorer_max_tokens_cap` — inject a fake
    `rlm_factory` returning a fake rlm that records its `__call__` kwargs; run
    `RlmBackend` under a `Settings` with `explorer_max_tokens` set to a distinctive
    value; assert the recorded rlm call kwargs contain NO `max_tokens` equal to the
    explorer cap (the Deep model bound stays `deep_token_ceiling`, set inside the
    frozen factory — byte-untouched).
  - `test_deep_outbound_carries_no_enable_thinking` — same seam; assert the
    recorded call kwargs contain NO `chat_template_kwargs` / `enable_thinking`.
- This is a scope drift-guard (assert on ACTUAL outbound request fields, not the
  absence of the `explorer_*` Settings names), NOT a RED→GREEN pair: it PASSES on
  introduction precisely because the `explorer_`-prefixed knobs are threaded ONLY
  by the explorer's `_default_model_call` and Deep is byte-untouched. It ROTS
  FALSE if a future change leaks either field into the Deep path (scope enforced
  by field naming + call site, per AC8).

### Step 9 — `finish=length` yields a truncation outcome in the loop (RED) [AC3]
- Add to `harpyja/scout/test_explorer_loop.py`:
  - `test_finish_length_yields_generation_truncated_outcome` — a `model_call`
    returning `{"finish_reason": "length", "tool_calls": []}` ⇒
    `LoopResult.outcome == GENERATION_TRUNCATED`, `spans is None`.
  - `test_finish_length_truncates_even_with_valid_tool_call` — a `model_call`
    returning `finish_reason="length"` AND a syntactically valid `submit_citations`
    tool_call still ⇒ `GENERATION_TRUNCATED` (edge case decided: `finish=length`
    NEVER takes the success path — its args may be silently incomplete).
- Tests fail: `GENERATION_TRUNCATED` constant does not exist in `explorer_loop`;
  `run_explorer_loop` never inspects `finish_reason`.

### Step 10 — Detect truncation in the loop (GREEN) [AC3]
- `harpyja/scout/explorer_loop.py`: add terminal outcome constant
  `GENERATION_TRUNCATED = "generation-truncated"` (near `SUBMITTED`/
  `TURNS_EXHAUSTED`, lines 39-41). In `run_explorer_loop`, IMMEDIATELY after
  `response = model_call(session.messages())` (line 200) and BEFORE the
  `session.add` / tool_calls handling, insert:
  `if response.get("finish_reason") == "length": return LoopResult(GENERATION_TRUNCATED, None, turns_used, session.messages())`.
  Fires REGARDLESS of any tool_call riding along.
- All Step-9 tests pass.

### Step 11 — Truncation outcome maps to a typed degrade cause (RED) [AC3]
- Add to `harpyja/scout/test_explorer_backend.py`:
  - `test_generation_truncated_outcome_raises_scout_unavailable_generation_truncated`
    — drive the backend so the loop returns the `GENERATION_TRUNCATED` outcome
    (inject a `model_call` that returns `finish_reason="length"`); assert
    `ScoutUnavailable` is raised with `cause == errors.GENERATION_TRUNCATED`
    (`"generation-truncated"`), distinct from `MODEL_UNREACHABLE`.
- Tests fail: `errors.GENERATION_TRUNCATED` does not exist;
  `_EXHAUSTION_CAUSE` (lines 43-46) has no entry for the new outcome ⇒ `KeyError`
  in the `_run_loop` tail (line 237).

### Step 12 — Add the fifth cause + backend map entry (GREEN) [AC3]
- `harpyja/scout/errors.py`: add `GENERATION_TRUNCATED = "generation-truncated"`
  (line ~28, beside the other 0024 causes). (CAUSE-TAXONOMY: stable
  machine-readable id, never prose.)
- `harpyja/scout/explorer_backend.py`: import the new loop outcome
  `GENERATION_TRUNCATED` and add `GENERATION_TRUNCATED: errors.GENERATION_TRUNCATED`
  to `_EXHAUSTION_CAUSE` (lines 43-46). The existing `_run_loop` tail (line 237)
  already raises `ScoutUnavailable(_EXHAUSTION_CAUSE[result.outcome])` for any
  non-SUBMITTED outcome, so once the map has the entry truncation degrades
  correctly.
- All Step-11 tests pass.

### Step 13 — Runner counts truncation distinctly (RED) [AC3]
- Add to `harpyja/eval/test_runner.py`:
  - `test_generation_truncated_note_increments_distinct_count` — a case whose
    notes contain `scout-degraded:generation-truncated` yields aggregate
    `scout_degrade_generation_truncated_count == 1` AND
    `scout_degrade_model_unreachable_count == 0` (counted distinctly). The
    `_scout_degrade_cause` regex `scout-degraded:([a-z-]+)` (line 86) already
    matches the hyphenated cause — no parser change.
- Tests fail: `"generation-truncated"` is not in `_SCOUT_NATIVE_CAUSES` (lines
  80-85), so `scout_cause_counts` has no such key; the aggregate dict has no
  `scout_degrade_generation_truncated_count` field.

### Step 14 — Runner: add the cause + aggregate field (GREEN) [AC3]
- `harpyja/eval/runner.py`: add `"generation-truncated"` to `_SCOUT_NATIVE_CAUSES`
  (lines 80-85). Add
  `"scout_degrade_generation_truncated_count": scout_cause_counts["generation-truncated"]`
  to the aggregate return dict (beside the sibling per-cause counts at lines
  335-339). `scout_cause_counts` is built from `_SCOUT_NATIVE_CAUSES` (line 293),
  so the new key populates automatically.
- All Step-13 tests pass.

### Step 15 — Report schema gains the field + version bump (RED) [AC3]
- Add to `harpyja/eval/test_report.py`:
  - `test_generation_truncated_count_field_present_and_defaults_zero` — a report
    block omitting the new field validates and reads
    `scout_degrade_generation_truncated_count == 0` via defaults.
  - `test_legacy_0027_block_still_validates_after_schema_bump` — a legacy
    `SCHEMA_VERSION`-less/0027-shaped aggregate block still passes `validate_report`
    through `_AGGREGATE_DEFAULTS` after the bump.
  - (Assert `SCHEMA_VERSION == "0028/1"`.)
- Tests fail: the field is not in the aggregate field list nor `_AGGREGATE_DEFAULTS`;
  `SCHEMA_VERSION` is still `"0027/1"`.

### Step 16 — Report: field list, default, version bump (GREEN) [AC3]
- `harpyja/eval/report.py`: add `"scout_degrade_generation_truncated_count"` to the
  aggregate field list (beside lines 156-159) and to `_AGGREGATE_DEFAULTS` (`= 0`,
  beside lines 211-214); bump `SCHEMA_VERSION` (line 35) `"0027/1"` → `"0028/1"`.
  (Additive-last-with-defaults + version-bump convention; the paired
  `<tier>_degrade_*` first-class-field rule.)
- All Step-15 tests pass. Full suite green: `pytest -q` across all packages.

### Step 17 — LIVE AC4 first-call latency + AC5 harness payoff (integration) [AC4/AC5]
- `harpyja/eval/test_harness_live.py` (exists; stays `@pytest.mark.integration`,
  skip when the 16B stack at `127.0.0.1:8131` is unreachable — CI-safe):
  - `test_first_explorer_call_returns_toolcall_under_30s` (NEW) — integration,
    skip if `_stack_up()` false; assert the first explorer model call returns
    `finish_reason == "tool_calls"` (NOT `"length"`) within 30s (floor evidence
    2.5–7.7s). Relies on AC0's surfaced `finish_reason`.
  - `test_explorer_localizes_without_degrade_within_n_turns` — REMOVE the
    `@pytest.mark.xfail` block (lines 66-70); extend the settings build (lines
    81-84) to also set `explorer_max_tokens` and `explorer_enable_thinking` (the
    AC6-chosen config); broaden the degrade-cause guard (line 95) to ALSO exclude
    `generation-truncated`; implement the ASYMMETRIC rule (genuine degrade
    `model-unreachable`/`backend-error`/`generation-truncated` = FAIL not hold;
    honest right-file-wrong-span or honest-empty capability = PASS) across the
    three mutually-exclusive AC5 buckets; reject placeholder/semantically-empty
    citations (e.g. `path:"string"`) as non-localizations. (HOLD-BY-CAUSE /
    degrade-masks-outcome.)
- Sequenced AFTER all units are green so a live failure is a real finding, not a
  scaffolding gap.

### Step 18 — Operator close-time deliverables (NOT unit tests) [AC6/AC7]
- AC6: on the live stack, run the measured thinking-off vs thinking-on comparison
  (each capped) and record which `explorer_enable_thinking` value ships and WHY
  against AC5 localization quality → `specs/0028-generation-control/operator-run-findings.md`
  + the close/changelog. If thinking-off degrades localization, record it.
- AC7: validate the shipped `explorer_max_tokens` against BOTH bounds — runaway
  (upper) AND turn-budget headroom (a complete multi-span `submit_citations` fits
  in one generation without forcing >N turns) — and record that BOTH were checked,
  not latency alone. State N=10 is inherited unchanged from 0026/0027.
- Gated after the units are green and live AC4/AC5 pass.

## Delegation

- Steps 1-16 (units) → `python-implementer` (single-language RED→GREEN across
  `gateway/`, `config/`, `scout/`, `eval/`, `deep/`; each step verifiable by
  `pytest -q`).
- Step 17 (live AC4/AC5) and Step 18 (operator AC6/AC7) → an operator with live
  16B-stack access at `127.0.0.1:8131` + provisioned worktrees (reason: requires
  the served stack + gold fixtures; not reproducible in CI).

## Risk

- `finish_reason` may arrive non-string or nested differently across llama.cpp
  builds → mitigation: `str()`-cast on presence and the exact `"unknown"` sentinel
  on absence, both pinned by Step-1 unit tests reading `choices[0]` (not the
  message).
- Cap set too low forces more, smaller turns and blows the N=10 budget
  (turn-exhaustion masking capability — the exact degrade-masks-outcome trap) →
  mitigation: AC7 dual-bound validation (Step 18) checks turn-budget headroom, not
  latency alone; 2048 chosen because 512 truncated and 2048 completed clean.
- The AC3 truncation branch could accidentally swallow a valid tool_call as an
  empty turn → mitigation: Step-9 `test_finish_length_truncates_even_with_valid_tool_call`
  pins that `finish=length` never takes the success path even with a parseable call.
- Scope leak: a future change threads the explorer knobs into Deep → mitigation:
  the Step-8 outbound-field guard rots false; the `explorer_`-prefixed names + the
  single `_default_model_call` call site enforce scope by construction.
- Live AC5 could reveal genuine localization failure → mitigation: that is a real
  FINDING (asymmetric rule), recorded via AC6, not a harness bug to paper over.
