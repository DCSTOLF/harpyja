# Spec 0038 — findings

## The typed outcome: `v1-variant` (reasoning_effort honors the toggle on the existing /v1 path)

The probe (`probes/run_probes.sh`, 9 arms, Ollama 0.31.1, `qwen3:14b`) answered OQ1
decisively and NOT with the leading candidate: a newer `/v1` passthrough DOES exist.
The OpenAI-compat `reasoning_effort` param on the existing `/v1/chat/completions`
path controls generation-level thinking:

| arm | request | reasoning_chars | content | finish | completion_tokens |
|---|---|---|---|---|---|
| off | `reasoning_effort:"none"` | 0 | `"391"` | stop | 4 |
| on | `reasoning_effort:"high"` | 231 | empty | length | 60/60 |
| default | omitted | 186 | empty | length | 60/60 |

Two-factor verdict (the discriminator that exposed the 0037 no-op): the off arm
produces content within the tiny cap at 4 tokens with zero reasoning and no
`<think>` leak; on/default exhaust the cap reasoning-first. This is GENERATION
control, not serialization control. Evidence: `probes/probe_result.json`
(schema `0038/1`, drift-pinned by `harpyja/eval/test_reconcile_probe_result.py`),
raw arms committed alongside.

Re-confirmed in the same probe run:

- `/v1` top-level `think:false` is STILL a no-op on this server version (237
  reasoning chars, cap-exhausted — the 0037 finding holds; the 0037 archived
  evidence needed no revisiting).
- The native `/api/chat` control still honors `think:false` (content `"391"`,
  `done_reason=stop`, 4 tokens) — 0037's control replicated. It was NOT chosen:
  `reasoning_effort` achieves the same control with no endpoint migration.

## What moved, why, and the blast radius

**What moved:** ONE line of mechanism in `ExplorerBackend._default_model_call`
(`harpyja/scout/explorer_backend.py`): `explorer_think=True/False` now rides the
outbound `/v1` request as `reasoning_effort: "high"/"none"`; the dead top-level
`think` field (0034's wiring, proven dropped by 0037) is GONE. `None` still omits
everything.

**Why this shape:** OQ2's endpoint-migration cost never materialized — the probe
scoped it before wiring (tool-calling on `/v1` with `reasoning_effort:"none"`
returns a normal `tool_calls` response with `id` present, `finish_reason`
`"tool_calls"`, zero reasoning, 19 tokens), so the change is a param re-route on
the SAME transport, not a migration. OQ3's divergent-transport debt is therefore
ZERO: explorer and Deep remain on the one `/v1` gateway path.

**Blast radius (enumerated, regression-pinned):**

- tool_call send/parse: UNCHANGED (`/v1` OpenAI-compat shape, `tool_call_id`
  present — probe evidence `probe_arm_v1_tools_effort_none.json`).
- `finish_reason` mapping, `max_tokens`, usage extraction: UNCHANGED (same
  endpoint, same response shape; `usage_mapping` pinned in the probe artifact as
  `usage.completion_tokens`).
- ModelGateway residency: UNCHANGED and preserved — the knob rides
  `complete_with_tools` params through the existing gateway method;
  `assert_local`-before-I/O and the finite `timeout_s` hold as before (no new
  outbound code path was created).
- **Superseded 0034 pins (deliberate, same-change, test + rationale together):**
  `test_explorer_think_true_sends_think_true` / `_false_sends_think_false` →
  `test_explorer_think_true_sends_reasoning_effort_high` /
  `_false_sends_reasoning_effort_none`. The 0034 `None ⇒ outbound byte-identical
  (params == {max_tokens: 2048})` pin SURVIVES intact — no endpoint switch
  happened, and None sends neither `think` nor `reasoning_effort`
  (`test_default_outbound_carries_no_think_param`, strengthened).
- New tripwire: `test_explorer_think_wiring_matches_committed_probe_outcome`
  FAILS LOUD (not skip) if the committed probe outcome ever stops matching the
  wired `v1-variant` mechanism — wiring and evidence cannot drift silently.
- Verifier: additive `serving_transport` field (present-and-None posture) under a
  version-gated `VERIFIER_SCHEMA_VERSION` bump `0034/1 → 0038/1`; legacy
  `0031/1`/`0033/1`/`0034/1` artifacts still validate
  (`test_legacy_artifacts_without_serving_transport_still_validate`).

## Live per-mode effectiveness (AC3) — observed, not config-derived

`test_live_reconciled_think_knob_effectiveness` PASSED live THREE times (strict
closure via `run_effectiveness.sh`, skip converted to hard fail; the final run
also proves the durable `serving_transport` field end-to-end). Durable
verifier-clean artifacts under
`eval_work/live_artifacts/reconciled_think_{on,off,default}/` (final closure
run `20260710T18*Z-95639`, schema `0038/1`,
`serving_transport: "v1-chat-completions"`):

- **off**: reasoning_chars `[None×5]`, 18–49 completion_tokens/turn, all
  `finish=tool_calls`, no `<think>` leak — a genuine off-arm through PRODUCTION
  wiring, the artifact the 0037 A/B was blocked on.
- **on**: 982–3980 reasoning chars/turn, 239–911 tokens/turn.
- **default**: 852–3457 reasoning chars/turn, 221–761 tokens/turn.

The off-vs-on/default separation replicated across all three runs (the first
two runs' off arms: `[None×4]` at 18–49 tokens/turn vs 1300–3400 reasoning
chars on on/default) — the toggle is stable, not a one-run artifact.

Off-arm evidence strength is N=1 (one run per mode) — acceptable for an
API-level mechanism toggle; nothing stronger is claimed. Whether thinking
on/off changes LOCALIZATION quality is the A/B's question, not answered here.

## 0037 conditional AC2/AC3: superseded-with-record

The 0037 tripwires are keyed to the /v1 top-level-`think` outcome (`no-op`),
which never legitimately flips — the /v1 layer still drops that field and the
knob now routes through `reasoning_effort`. Both tests
(`test_explorer_think_pin_gated_on_native_probe_outcome`,
`test_live_think_knob_three_factor_effectiveness`) are KEPT and marked
SUPERSEDED-BY-0038 in their docstrings, skipping forever with the archived
machine-recorded reason. The archived
`specs/.archive/0037-explorer-think-knob/probes/probe_result.json` and its
drift pin (`test_think_probe_result.py`) were NOT touched. Successor pins are
named in each docstring.

## `derive_think_mode` audit: no enum change

The 0034 labels (`native-think-true`/`native-think-false`/`default-omitted`)
still disambiguate the tri-state — they name OPERATOR INTENT; the transport
mechanism the intent rides is now recorded separately in `serving_transport`
(`v1-chat-completions`). Pinned by
`test_derive_think_mode_disambiguates_post_switch`.

## No default flip

`explorer_think=None` (endpoint default: thinking ON) remains the shipped
default. Thinking on/off is the A/B's measurement — 0038 only made the off-arm
constructible. The 0037 OQ2 interaction (off-arm vs `explorer_max_tokens`) is
now EXERCISABLE and remains unmeasured by design (the off arm ran fine at cap
256 in the AC3 run — 4 turns, 18–49 tokens each — but one run is not a
measurement).
