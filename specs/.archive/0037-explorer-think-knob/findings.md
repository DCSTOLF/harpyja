# Spec 0037 — Findings

## Terminal close: NO_OP_BLOCKED

**The probe's typed outcome is `no-op`** (evidence: `probes/probe_result.json`,
schema `0037/1`, pinned by `harpyja/eval/test_think_probe_result.py::test_committed_probe_result_loads_and_validates`;
raw arm outputs: `probes/probe_arm_*.json`, probed 2026-07-10, `qwen3:14b`,
`http://localhost:11434/v1/chat/completions`).

Under the tiny-cap discriminator (`max_tokens=60`), all three `/v1` arms —
`think: true`, `think: false`, and omitted — are behaviorally IDENTICAL:
reasoning generated (205–256 chars), empty content, `finish_reason="length"`,
all 60 `completion_tokens` consumed reasoning-first. `think: false` suppressed
neither generation-level thinking nor even the reasoning field. The
supplementary `chat_template_kwargs{enable_thinking: false}` arm is EQUALLY
ineffective (197 reasoning chars, same cap exhaustion) — so the outcome is
`no-op`, not `chat-template-effective`.

## The control that localizes the defect

A supplementary control on the NATIVE API path
(`probes/probe_arm_native_api_think_false.json`) proves the mechanism itself
works: `/api/chat` with `think: false` → content `"391"` (the correct answer),
zero thinking chars, `done_reason="stop"`, `eval_count=4`. Same model, same
prompt, same moment.

**Conclusion: the param name and the model-side mechanism are right; Ollama's
OpenAI-compat `/v1` layer silently ignores the top-level `think` field.** The
0034 knob as wired (the gateway threads `params["think"]` into the `/v1`
request body) sets a field the endpoint drops — the exact no-op-field risk the
spec's OQ1 named, and the same shape as the 0028 `/no_think` lesson (a control
believed effective that never took effect), caught this time BEFORE an A/B was
built on it.

## Consequence: the thinking A/B is BLOCKED

A thinking-off arm cannot be constructed through the gateway as wired: every
`/v1` call thinks, regardless of `explorer_think`. Per the spec's
two-terminal-paths invariant this is the NO_OP_BLOCKED close:

- AC2 (`test_explorer_backend.py::test_explorer_think_pin_gated_on_native_probe_outcome`)
  and AC3 (`test_live_verifier_integration.py::test_live_think_knob_three_factor_effectiveness`)
  are authored and SKIP with the machine-recorded outcome as the reason. If a
  future revision flips the probe outcome, they activate automatically.
- The per-mode live effectiveness run (plan Step 7 / T7) was NOT run — with a
  no-op knob there are no distinguishable arms to measure; running it would
  produce three identical thinking-on runs and prove nothing.

**Reconciliation is a follow-up revision, never a silent re-point.** The
control evidence points at the likely fix — route the explorer's think control
via a path that honors it (the native `/api/chat` transport, a gateway-level
translation, or a future Ollama `/v1` that respects the field) — but changing
the gateway transport or re-pointing `explorer_think` at a different mechanism
touches the seams 0034 deliberately separated (`derive_think_mode`,
`explorer_enable_thinking` coexistence) and must be its own reviewed spec, with
this probe re-run as its acceptance gate.

## No default flip

The default think mode is UNCHANGED (`explorer_think=None` ⇒ param omitted ⇒
request byte-identical to pre-0034; default-on thinking preserved as the
untouched baseline). The N=2 think-experiment result is cited here as
MOTIVATION for building the thinking A/B — explicitly NOT as evidence that
thinking helps localization (mechanism unestablished, likely variance). No
tuning was performed; the observed off-arm/`max_tokens` budget interaction
question (spec OQ2) was NOT EXERCISED because no genuine off arm exists on
this endpoint (recorded, not papered).

## Evidence index

| Artifact | What it shows |
| --- | --- |
| `probes/run_probes.sh` | Committed curl-on-loopback driver (STOP-AND-WARN, re-runnable) |
| `probes/probe_arm_think_true.json` | /v1 `think:true` — reasoning 246 chars, cap exhausted |
| `probes/probe_arm_think_false.json` | /v1 `think:false` — reasoning 205 chars, cap exhausted (NO-OP) |
| `probes/probe_arm_omitted.json` | /v1 omitted — reasoning 256 chars, cap exhausted (baseline) |
| `probes/probe_arm_chat_template_disabled.json` | /v1 chat-template disable — reasoning 197 chars (ALSO no-op) |
| `probes/probe_arm_native_api_think_false.json` | /api/chat `think:false` — genuinely off (the control) |
| `probes/probe_result.json` | The typed outcome (`no-op`), schema `0037/1`, test-pinned |
