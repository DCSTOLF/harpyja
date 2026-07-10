---
id: "0038"
title: "reconciliation"
status: closed
started_at_sha: "61fa124e4baa3f1867e42d7d3afd9f8c8e5e3159"
created: 2026-07-10
---

# Spec 0038 — reconciliation

Thinking-control reconciliation — route `explorer_think` through a path the model honors.

## Why

0037 proved the `explorer_think` knob is a NO-OP: Ollama's OpenAI-compat `/v1` layer silently drops the top-level `think` field, so all three arms (true/false/omitted) generate identically. The decisive control was clean — native `/api/chat` with `think:false` genuinely works (content, zero thinking, 4 tokens) — so the param and model-side mechanism are correct; only the `/v1` transport ignores it. This spec routes the explorer's thinking control through a path the model actually honors, so `explorer_think` toggles GENERATION, not just serialization. It is the prerequisite the thinking A/B now depends on (the A/B cannot build a real off-arm until this lands).

Ref: 0037 (NO_OP_BLOCKED, `probe_result.json`, the /v1-drops-think finding + native-/api/chat control), 0034 (`explorer_think` + `think_mode` recording + the two-factor probe technique), 0028 (the `/no_think`-inert precedent), the reconciliation-not-silent-re-point invariant from 0037's review.

## What

- PROBE (first, committed, loud): pin which honoring path works via two-factor on this Ollama — native `/api/chat` (0037's proven control) vs any `/v1` variant not yet ruled out. The probe matrix covers ALL THREE arms on the candidate path — `think:true`, `think:false`, AND think-omitted (the endpoint default) — native default/on behavior is OBSERVED, never inferred from 0037's `think:false` control arm. The probe also scopes the endpoint-migration cost: tool_calls shape (including whether `tool_call_id` is present — see OQ2), usage field names, reasoning field name. Commit the probe result (schema-versioned `0038/1`, drift-pinned), same posture as 0037's `probes/`.
- WIRE the proven path into the explorer's gateway call so `explorer_think` {True/False/None} genuinely toggles generation. None routing is decided: the explorer's tool-calling loop moves WHOLE to the proven transport — all three arms {True/False/None} run through the SAME endpoint (None omits the think field, i.e. the endpoint default). No per-value transport split: a split would run the A/B's off-arm and default-arm through different endpoints, confounding the exact experiment this spec exists to enable.
- The honoring path ships INSIDE `ModelGateway` (see Invariants — single outbound abstraction); the explorer keeps calling the gateway, never a transport directly.
- If the path is native `/api/chat`: adapt the tool-calling request/response shape to the explorer's existing contract per the Native-response contract below; the verifier's extraction still works.
- Deliberate pin reconciliation: the 0034 exact pin "`explorer_think=None` ⇒ outbound request body byte-identical to pre-0034 (`params == {max_tokens: 2048}`)" CANNOT survive the endpoint switch (URL changes; `max_tokens` becomes `options.num_predict`). It is superseded HERE, deliberately: the pinning test is amended in the same change with rationale, per the exact-pin reconciliation convention — never left to fail as a surprise. Its successor pin: None ⇒ no think field present on the new transport's outbound request.
- 0037 conditional AC2/AC3 disposition: those tripwires are keyed to the /v1 top-level `think` mechanism's machine-recorded `no-op` outcome, which never legitimately flips (the /v1 layer keeps dropping the field; wiring moves OFF /v1). They are SUPERSEDED-WITH-RECORD, not auto-armed: 0038 authors its own live per-mode tests keyed to the 0038 probe artifact, and the 0037 conditionals are retired/re-pointed via an explicit, recorded edit. The archived, drift-pinned `specs/.archive/0037-explorer-think-knob/probes/probe_result.json` is NEVER edited.
- `derive_think_mode` audit: confirm the 0034 enum still disambiguates post-switch (its semantics were minted under /v1, where "native-think-true/false" were serialized-but-ignored); extend it in the same change if not. Record the serving transport (endpoint identity) as an optional trajectory-artifact field so the four-facts invariant is checkable per-transport.

### Probe artifact (typed, committed)

- Outcome enum (total answer space, own schema `0038/1`, NOT a reuse of `0037/1`): `native-api-chat` | `v1-variant` | `still-blocked`.
- Artifact shape splits path from evidence: `chosen_path`, `outcome`, `usage_mapping`, and per-arm observed facts (content presence, finish/done reason, token counts, reasoning chars, leak-scan result) — so future drift can distinguish endpoint failure from adapter failure.
- The drift pin is authored against `specs/.archive/0038-reconciliation/probes/…` per the evidence-path convention (pins target `specs/.archive` from authoring; 0037's close proved live-path pins break at archive time).

### Native-response contract (IF `/api/chat`)

Exact field mappings, each regression-pinned; absent-field behavior stated, never assumed:

- request `max_tokens` → `options.num_predict` (the 0028 cap translation)
- request `think` → top-level `think` (the 0037-proven honored field)
- response `done_reason` → `finish_reason` (mapping table pinned, including the length-cap case)
- response `eval_count` (or served equivalent — probe confirms) → `completion_tokens`; the two-factor proof and the verifier keep speaking in `completion_tokens`, so this mapping is proof-bearing and MUST be pinned before AC1/AC3 cite token deltas
- response native thinking field → `reasoning`
- response native `tool_calls` → the explorer loop's existing tool-call shape; if the served version omits `tool_call_id`, the 0029 answer-all-N protocol needs a synthesized-id/positional scheme — an explicit, pinned adaptation, not an improvisation (probe decides, OQ2)

### Invariants

- **Probe-first, two-factor — do NOT wire before proving**: the chosen path is confirmed to toggle GENERATION by the 0034/0037 two-factor test (tiny-cap discriminator: `think:false` + small `max_tokens` → content appears / finish≠length; `completion_tokens` cross-check; `<think>`-in-content leak scan) BEFORE any production wiring. A path that only changes the serialized reasoning field, not generation, is rejected — the exact hole 0037 caught.
- **ModelGateway residency — single outbound abstraction**: the honoring path ships as a new/extended `ModelGateway` method. No parallel HTTP client in `harpyja/scout/` or anywhere else; the gateway remains the ONLY outbound caller, asserting `assert_local` on the resolved endpoint BEFORE any I/O and carrying the finite per-socket-op `timeout_s` bound (the B3/spec-0017 rule). Both are in AC4's regression list.
- **Explicit mechanism change, never a silent re-point**: routing the explorer's calls through native `/api/chat` instead of `/v1` is a RECORDED, reviewed transport change — its blast radius (tool_call send/parse format, `finish_reason` mapping, the 0028 cap → `num_predict` translation, model-identity/reasoning/usage extraction the verifier depends on, `assert_local` + `timeout_s` on the new path, the superseded 0034 byte-identical pin) is enumerated and regression-pinned. Do not swap the endpoint quietly.
- **Explorer-scoped, Deep untouched**: the transport/param change applies to the EXPLORER's tool-calling path only; Deep/RLM stays on its current path, enforced by the `explorer_`-prefix + the 0034/0035 Deep-scope guard, plus an explicit negative test: Deep/RLM does not call the native adapter and its outbound requests carry no `think` field.
- **Recording still true post-change**: `think_mode` + `reasoning_chars` + `completion_tokens` + `tool_names` + `model_identity` remain correctly captured in the trajectory artifact through the new path — the verifier's four facts survive the transport change (else the A/B and bake-off lose their instrument).

## Acceptance criteria

([unit]=fakes; [integration]=live, skip-not-fail)

1. [integration] PROBE: the chosen path toggles GENERATION by two-factor (content-on-off, `completion_tokens` delta via the pinned usage mapping, no `<think>` leak), with native default/on arms OBSERVED in the matrix — committed probe artifact (schema `0038/1`, outcome ∈ {native-api-chat, v1-variant, still-blocked}, path-pinned against `specs/.archive/0038-…`). If NO path honors it → typed STILL_BLOCKED close (a finding, not a forced pass).
2. [unit] `explorer_think` wired to the proven path inside `ModelGateway`: True→thinking on, False→genuinely off, None→think field omitted on the SAME transport (no per-value split); asserted on the outbound request for the new transport. The 0034 None⇒byte-identical pin is superseded in this same change, test + rationale together.
3. [integration] Live per-mode: off-arm produces reasoning-absent (two-factor), on/default reasoning-present — the 0037 tautology (config-derived recording) is NOT the proof; observed generation is. Token evidence cites the pinned native usage mapping.
4. [unit] Transport blast-radius pinned (IF `/api/chat`): tool_call send/parse (incl. the `tool_call_id` scheme the probe determines), `finish_reason` mapping, `max_tokens`→`num_predict`, `eval_count`→`completion_tokens`, verifier extraction (model/reasoning/usage/tool_names), `assert_local`-before-I/O and finite `timeout_s` on the new path — all regression-green.
5. [unit] Deep/RLM path unchanged — explorer-scope enforced; Deep-scope guard rots-false on leak; explicit negative test that Deep never calls the native adapter and emits no `think` field.
6. [integration] The verifier's four facts remain correct on an eval case run through the new path (a clean artifact, so the A/B/bake-off keep their instrument); serving transport recorded in the artifact.
7. [doc] The transport/mechanism change recorded (what moved, why, blast radius incl. the superseded 0034 pin); 0037's conditional AC2/AC3 explicitly superseded-with-record (retired/re-pointed at the 0038 artifact via a recorded edit; archived 0037 evidence untouched); no default flip (thinking on/off is the A/B's measurement, not decided here).

## Out of scope

- The thinking A/B (next, consumes the now-working knob)
- The bake-off
- Flipping the default think mode
- Any Deep/RLM change
- Tuning the cap for thinking (separate if the A/B shows a budget interaction)
- Non-Ollama backends

## Open questions

1. Native `/api/chat` vs a `/v1` variant: 0037 ruled out `/v1` top-level `think` AND the chat-template arm, so native `/api/chat` is the leading (probe-proven) candidate — but confirm no newer `/v1` passthrough exists before committing to a full endpoint switch (the switch is the bigger blast radius). Probe decides.
2. If native `/api/chat`: does its tool-calling format differ enough from `/v1`'s OpenAI-compat that the explorer's tool_call parsing needs real changes (not just field renames)? Named sub-question: is `tool_call_id` present on the served Ollama version? (Native `/api/chat` tool_calls have historically omitted `id`s, and the 0029 answer-all-N protocol answers each call BY `tool_call_id` — absent ids make this an endpoint migration with a synthesized-id/positional scheme, not a field rename.) Scope this in the probe, not after wiring.
3. Does routing explorer through `/api/chat` while Deep stays on its path create two divergent gateway transports to maintain? If so, note the debt; don't force-converge them in this spec.
4. Does `derive_think_mode`'s 0034 enum still disambiguate when "native-think-true/false" become genuinely effective (semantics minted under /v1)? Audit in-change; extend only if it fails to disambiguate.
