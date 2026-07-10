---
id: "0037"
title: "explorer-think-knob"
status: closed
started_at_sha: "99fd8cf05d97f6450e4e0fc1e63ab8b27e0cb26e"
created: 2026-07-09
revision: 1
---

# Spec 0037 — explorer-think-knob

## Why

0034 already SHIPPED the knob: the `explorer_think` tri-state Settings field, the native `think` request param threading, `derive_think_mode`, and `think_mode` recorded in BOTH the trajectory record and the written verifier artifact (schema `0034/1`), plus the `bool|None` env coercion and the Deep outbound leak guard. What 0034 did NOT prove is that the knob is EFFECTIVE. It pinned only the None arm (request byte-identical to default) and the recording path. Nobody has shown that `think: true` / `think: false` actually toggles generation on this Ollama `/v1` path — the recorded `think_mode` is derived from config, so it can match the setting even if the underlying param is a no-op field.

That gap is the whole reason this spec exists. 0028 believed thinking was disabled and it was NOT (the `/no_think`-was-inferior finding was drawn against a knob that never took effect); that lesson is exactly why a live effectiveness proof is mandatory before the A/B (next spec) is allowed to trust the knob to construct its on/off arms. This spec answers one question — **does the knob actually work?** — and "no, it doesn't" (the param is a no-op, thinking stays on regardless) is a legitimate, recordable answer that BLOCKS the A/B rather than a failure to paper over.

Ref: 0028 (generation control, the mistaken thinking-disable that motivates the live proof), 0034 (shipped the knob + recording, proved only the None arm and the recording), 0035 (`explorer_`-prefixed tier-scoping convention), the review round's finding (ACs 1–4 re-specified shipped work; only the live effectiveness proof and the param-pinning probe are genuinely new).

## What

Prove and pin the 0034 knob live.

**INVARIANT (probe-then-pin, total outcome space):** a live probe runs FIRST against the actual Ollama `/v1` path and returns exactly one value of a TYPED outcome enum — `native-think-effective` / `chat-template-effective` / `no-op` — so every possible answer has a named disposition (the 0023 every-input-returns-a-named-outcome discipline). Native `think` is the EXPECTED HYPOTHESIS (per 0034), not a pre-commitment: AC2/AC3 are CONDITIONAL on `native-think-effective`. `chat-template-effective` (a param toggles thinking but it is NOT native `think`) ⇒ recorded finding + a deliberate reconciliation revision — NEVER a silent re-point of `explorer_think` at the other mechanism, which would re-collide the two knobs `derive_think_mode` deliberately separated. `no-op` ⇒ the NO_OP_BLOCKED terminal path. No unit request-body assertion is authored until the probe resolves.

**INVARIANT (effectiveness observed at the GENERATION level, three-factor):** effectiveness is asserted on OBSERVED behavior in the persisted verifier artifact — never on the config-derived `think_mode` recording ("recorded matches setting" proves only recording; it passes even against a no-op param). But `reasoning_chars` alone is a REPORTING signal, not a generation signal: a `think:false` that merely suppresses the reasoning field in the reply while the model still burns thinking tokens would show `reasoning_chars=0` and fake a working off-arm — the 0034 invisible-thinking discovery wearing the opposite mask, silently turning the A/B into thinking-on vs thinking-still-on. The proof is therefore THREE-FACTOR, and all three must land — this must not quietly collapse back to single-factor field presence: (a) per-turn `reasoning_chars` (on/default arms ≥1 turn `> 0`; off arm `{None, 0}` across ALL turns); (b) the 0034 probe-A tiny-cap discriminator (`think:false` + small `max_tokens` → content appears / finish≠length proves generation genuinely stopped reasoning; a still-thinking model exhausts the cap reasoning-first with zero content); (c) `completion_tokens` cross-check across arms + a `<think>`-in-content leak scan on the off arm.

**INVARIANT (explorer-scoped only):** the knob touches the EXPLORER's tool-calling gateway call only. Deep/RLM path untouched, enforced structurally by the `explorer_`-prefix (the 0034 Deep-scope guard). None ⇒ param omitted ⇒ request byte-identical to default-on baseline.

**INVARIANT (knob, not fix):** this ships NO tuning and NO default flip. It makes no claim that thinking-on improves localization — that is the A/B's measurement. The N=2 think-experiment is motivation for building the A/B, not evidence thinking helps (mechanism unestablished, likely variance).

**INVARIANT (no-op is a finding; two terminal close paths):** the spec closes on exactly one of two named terminal outcomes, both legitimate. **EFFECTIVE**: the probe returns `native-think-effective` and AC2/AC3 land — the A/B is unblocked. **NO_OP_BLOCKED**: the probe returns `no-op` (thinking stays on regardless of `think: true/false`) — a recorded FINDING that BLOCKS the A/B (you cannot construct a thinking-off arm), surfaced honestly, not worked around. Either way the finding is DURABLE: a `findings.md` under `specs/0037-explorer-think-knob/` (the 0021/0022 precedent) plus the committed `probes/probe_result.json`, with a unit test pinning the claimed outcome to the recorded probe output so the claim cannot drift from the evidence. The `chat-template-effective` branch also lands in `findings.md` and blocks the A/B pending the reconciliation revision.

## Acceptance criteria

Convention: [unit]=fakes; [integration]=live and the TEST FILE stays skip-not-fail. The deliverable-producing runs (the probe and the per-mode effectiveness run) are LOUD committed drivers under `specs/0037-explorer-think-knob/` (probe driver + output under `probes/`, per the 0034 precedent): STOP-AND-WARN on infra unavailability, NEVER silent-skip, resumable if long-running. Durable artifacts land under `eval_work/live_artifacts/` via `live_artifact_dir`. Probe transport: a committed curl-on-loopback shell script (operator tooling, outside the runtime air-gap like convert/provision — NOT a second runtime egress path), per `specs/.archive/0034-reasoning-observability/probes/run_probes.sh`. Reference instance: `qwen3:14b` on the dev Ollama — the model the default-thinking premise was measured on (the `lm_model` default is known-unservable per 0036); the finding is about THIS endpoint+model, not a universal.

1. [probe] A committed live probe against the Ollama `/v1` path returns exactly one TYPED outcome — `native-think-effective` / `chat-template-effective` / `no-op` — recorded in `probes/probe_result.json` and pinned by a unit test so the claimed outcome cannot drift from the recorded evidence. The probe discriminates at the GENERATION level, not field presence: tiny-cap technique (per the three-factor invariant) + `completion_tokens` comparison + `<think>`-in-content leak check. Dispositions, total: `native-think-effective` → AC2/AC3 proceed (EFFECTIVE path); `chat-template-effective` → recorded finding in `findings.md` + reconciliation revision, A/B blocked until re-proven, never a silent re-point; `no-op` → NO_OP_BLOCKED close with `findings.md`, A/B blocked. Close-blocking either way — a non-effective result is a valid, recorded close, not a pass-by-default and not a failure to paper over.
2. [unit — conditional on `native-think-effective`] `explorer_think` tri-state request-body pin against the probe-confirmed native `think` param: True → `think: true`; False → `think: false`; None → param omitted, request byte-identical to current default-on. Asserted on the outbound request body. Not a rebuild — the 0034 pin remains green; this AC re-asserts it against the probe's recorded outcome, dropping the earlier `chat_template_kwargs`/"measured-correct param" hedge.
3. [integration — conditional on `native-think-effective`] Live effectiveness proof: one run per mode (on / off / default) on an eval case, each producing a verifier-clean persisted artifact, gated on the shipped `probe_reasoning_default` precondition (a non-default-thinking served model skips honestly as an input-validity failure — the 0023 rule — instead of misreading a model property as "knob ineffective"). Assertions are the THREE-FACTOR set from the invariant: (a) per-turn `reasoning_chars` — on/default arms ≥1 turn `> 0`, off arm `{None, 0}` across ALL turns; (b) the tiny-cap generation-level discriminator for the off arm; (c) `completion_tokens` cross-check across arms + `<think>`-in-content leak scan on the off arm. All three must land; none may be dropped or substituted for another. `think_mode` recorded-matches-setting is retained as a secondary check, NOT the effectiveness signal. Off-arm evidence strength is N=1 (one run, a handful of turns) — stated explicitly as acceptable for an API-level mechanism toggle, not implied as more. This is the spec's central deliverable and, together with AC1, the close gate.
4. [regression] The shipped 0034 knob is assert-still-works, not re-built: existing pins remain green — tri-state request-body pin, `bool|None` env coercion + field-default drift-guard, `think_mode` in trajectory record AND written artifact (the drop-at-assembly guard), and the Deep-scope leak guard (rots-false on `explorer_`-scope leak).
5. [doc] No default flip; the think-experiment N=2 result cited as motivation-for-the-A/B, explicitly not as evidence thinking helps.

## Out of scope

- The thinking A/B measurement (next spec, consumes this knob)
- The model bake-off
- Flipping the default think mode
- Any Deep/RLM change
- Tuning the max_tokens cap for thinking (separate if the A/B shows a budget interaction)
- Re-building the 0034 knob — it shipped (tri-state field, native `think` threading, `derive_think_mode`, `think_mode` recording, env coercion, Deep guard); this spec is regression-reference + live proof only, not reimplementation
- Any schema version bump — `0034/1` already carries `think_mode` and `reasoning_chars` is already persisted per-turn; no genuinely new persisted field is added, so a bump would only churn the known-versions set for nothing

## Open questions

1. Which request param actually toggles thinking on the Ollama `/v1` path — native top-level `think` (per 0034, the expected hypothesis) vs `chat_template_kwargs.enable_thinking` vs neither. RESOLVED BY THE PROBE (AC1) as one of the three typed outcomes, close-blocking: `native-think-effective` pins AC2; the other two are recorded A/B-blocking findings, per the `/no_think`-was-inferior lesson.
2. Does `explorer_think=False` (genuinely off) interact with the max_tokens cap differently than default-on — e.g. does disabling reasoning free budget that changes tool-call behavior? Record if observed in the per-mode run; don't tune here (that's the A/B's job).
