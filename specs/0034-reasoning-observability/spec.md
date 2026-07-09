---
id: "0034"
title: "reasoning-observability"
status: planned
started_at_sha: 34c2c3b
created: 2026-07-09
authors: [claude]
packages: []
related-specs: ["0033-scoped-grep-paths", "0031-live", "0028-generation-control"]
---

# Spec 0034 — reasoning-observability (measurement-integrity fix, priority one)

## Why

The 0033-adjacent think-experiment probes established a hidden variable: **qwen3:14b on
THIS Ollama thinks by default** (instance-relative — this build + this model tag, not a
universal claim) — the `/v1` response carries a `reasoning` field even with no `think`
param (probe C: 2833 chars on a one-line tool-call prompt) — and the gateway's
`complete_with_tools` return dict silently DROPS it while the generated reasoning counts
against `explorer_max_tokens=2048`. Consequence: **every 0031–0033 live capability read
was measured under invisible-truncation RISK** — truncation, when it happened, was typed
(`generation-truncated`, 0028), but the CONSUMER (reasoning vs acting tokens) and the
remaining headroom were invisible from the trajectory artifacts. Those baselines carry an
asterisk; they are not clean. This spec is the measurement-integrity fix that closes the
blind spot: make the reasoning VISIBLE in the trajectory record (per-turn lengths at
minimum) and make `think` a RECORDED, `explorer_*`-scoped knob — the recording is
mandatory observability; the knob is opt-in CONTROL of a thing already happening, inert
by default (see the invariants' split).

**The cap mechanics are empirically pinned — committed probe artifacts in `probes/`
(re-runnable via `probes/run_probes.sh`, 2026-07-09):** Ollama's `/v1` compat layer
translates our `max_tokens` into `num_predict` and enforces it exactly — probe A:
`max_tokens=20` → `completion_tokens: 20`, `finish_reason: "length"`; probe B: native
`options.num_predict=20` → `eval_count: 20`, `done_reason: "length"` (identical
mechanism). So `explorer_max_tokens` IS a real hard bound on Ollama (no
unbounded-generation gap behind the naming difference) — AND probe A shows the budget is
consumed REASONING-FIRST: all 20 tokens went to `reasoning` (51 chars of thinking, zero
content) before any content/tool_call could be emitted. A hard turn under the 2048 cap
therefore starves the ACTING tokens after thinking takes its cut, the loop types it
`generation-truncated`, and pre-0034 nothing in the artifact shows reasoning was the
consumer. Per-turn reasoning lengths + per-turn `finish_reason` + per-turn
`completion_tokens` (see What) make cap-pressure attribution possible for the first
time. (The cap is per-TURN — each loop turn gets a fresh `max_tokens`; whole-run bounds
remain the turn cap + wall-clock ceiling, unchanged.)

This is NOT the causation experiment. The think-experiment's verdict stands: mechanism
UNESTABLISHED, most likely variance (both tested knobs measured inert — thinking already
default-on, cap never bound at max 1041 tokens/turn). Run 2's first-ever right-file +
first-ever `symbols` invocation is a proof-of-mechanism for the 0030 tool chain, NOT
evidence that thinking improves localization. The paired thinking-arm vs default-arm A/B
belongs to the eval set (the ONLY thing that settles causation — no more ad-hoc single
runs) and CONSUMES this spec's observability.

**Ref:** specs/.archive/0033-scoped-grep-paths/thinking-experiment/ (the N=2 experiment,
findings, the two committed trajectories — archived at 0033's consolidation),
specs/0034-reasoning-observability/probes/ (the committed cap-mechanics probe artifacts
this Why cites), 0028 (the obsolete disable rationale: llama.cpp-era
`<think>`-in-content contamination — the Ollama API shape isolates reasoning
structurally), 0031 (trajectory-verified measurement), conventions.md
(generation-control knob scoping, 0028 AC2/AC8 pattern).

## Invariants

**INVARIANT (default-config behavior preservation — the honest form of
"observability-only"):** under DEFAULT Settings, the outbound request bodies are
byte-identical pre/post-0034 (no `think` param is sent — the knob's default is
omit-param/no-op) and the loop's control flow is byte-unchanged. `verify_trajectory`'s
OUTCOMES (status, failure_reason, the four fact fields) on existing valid trajectories
are equal — NOT artifact-byte identity, which is structurally false after any schema
bump (`VerifierResult.to_dict()` stamps the current `VERIFIER_SCHEMA_VERSION`). The
recording additions are pure observability; the knob, when an operator OPTS IN, is a
generation-control change and is scoped/tested as one (next invariant) — the spec claims
"observability-only" for the default path and says so with a request-body test, not
prose (AC3).

**INVARIANT (additive gateway contract):** `complete_with_tools` surfaces `reasoning`
ADDITIVELY (existing keys unchanged; absent field → `None`, present-empty → `""`), plus
`completion_tokens` from `usage` (additively, absent → `None`) — the cap's actual
currency, without which cap-headroom reasoning has only chars to work with. Same
discipline as the 0028 `finish_reason` and 0031 `model` additions. No transport change,
no second outbound path.

**INVARIANT (knob scoping, 0028 pattern):** `explorer_think: bool | None = None`
(tri-state; name final at plan) is an `explorer_*`-prefixed Settings field passed ONLY
from the explorer's `_default_model_call`, and ONLY when non-None (None = omit the param
= today's request byte-identical). The shared `ModelGateway` stays param-driven with no
default of its own; the Deep-tier outbound-field guard is extended so Deep's outbound
request carries neither the knob nor a `think` param (rots false on leak).

**INVARIANT (one recorded effective-think-mode):** the trajectory record/artifact
carries a single canonical `think_mode` field with enumerated values —
`{"default-omitted", "native-think-true", "native-think-false",
"chat-template-disabled", "unknown"}` — so the two mechanisms
(`explorer_enable_thinking`'s `chat_template_kwargs`, which COEXISTS as the llama.cpp
template-era knob (OQ1 resolved: index.md still documents llama.cpp as a supported
gateway target, so supersede-and-delete is premature), and the new native `think` param)
can never produce an ambiguous record.

**INVARIANT (artifact carries lengths, not prose):** the trajectory record/artifact
gains per-turn reasoning lengths measured in CHARS (a presence/attribution signal —
chars cannot quantify budget share; `completion_tokens` per turn is the token-denominated
complement), NOT the reasoning text itself — the artifact stays a measurement record,
not a transcript dump. Zero-vs-None semantics pinned: absent `reasoning` field → `None`,
present-but-empty → `0` — an honest distinction, never a fabricated count. Additive
fields, `VERIFIER_SCHEMA_VERSION "0033/1" → "0034/1"` added to
`_KNOWN_VERIFIER_SCHEMA_VERSIONS` with the 0033 version-gate pattern: legacy `0031/1`
and `0033/1` artifacts still validate with the new fields DEFAULTED (never rejected);
the reasoning fields are optional in `0034/1` artifacts too (defaulted, since a
non-reasoning model legitimately produces none).

**DECIDED (capture seam — OQ2 resolved in-spec, per the resolve-OQ-toward-the-invariant
rule):** the per-turn data rides a NEW backend-side per-turn accumulator — the existing
`wrapped_model_call` in `ExplorerBackend` grows from a last-write scalar
(`_last_served_model`) into an accumulator appending
`(reasoning_chars, completion_tokens, finish_reason)` per model response, reset per run,
threaded into `build_trajectory_record` as a parallel per-turn list alongside
`model_turns`. The history-ride option is ELIMINATED, twice over: `session.messages()`
is double-duty as BOTH `LoopResult.history` AND the outbound wire messages (annotating
it would mutate the request body — violating the default-preservation invariant), and on
`finish_reason="length"` the loop returns BEFORE the assistant message is added to the
session — the truncated turn, the exact turn AC2 must discriminate, never enters
`model_turns`. Only the backend-side model_call wrapper sees every response including
the truncated final one.

## What

- Surface `reasoning` + `usage.completion_tokens` additively in
  `ModelGateway.complete_with_tools`'s return dict.
- Accumulate per-turn `(reasoning_chars, completion_tokens, finish_reason)` in the
  backend's `wrapped_model_call` (the DECIDED seam) → thread into
  `build_trajectory_record` → the persisted verifier artifact, plus the canonical
  `think_mode` field; bump the verifier schema `0033/1 → 0034/1` with the version gate.
- Add `explorer_think` (tri-state, default None = omit param = byte-identical request)
  as the recorded, explorer-scoped knob; extend the Deep outbound-field guard;
  `explorer_enable_thinking` coexists (llama.cpp-era mechanism), disambiguated by the
  one `think_mode` record field.
- Regression-pin: default-config outbound request bodies byte-identical;
  `verify_trajectory` outcome-equality on existing trajectories; a response lacking the
  `reasoning` field records `None` (never a fabricated count), present-but-empty
  records `0`.

## Acceptance Criteria (sketch — refine at plan)

1. [unit] `complete_with_tools` returns `reasoning` and `completion_tokens` additively;
   absent-field defaults pinned in both directions (the 0028 finish_reason test
   pattern); existing keys unchanged.
2. [unit] The backend accumulator records per-turn
   `(reasoning_chars, completion_tokens, finish_reason)` — including a FINAL
   truncated turn (finish="length") that never enters `model_turns` — threaded into the
   record and persisted artifact with `think_mode`; schema `0034/1`, version gate
   extended, legacy `0031/1`/`0033/1` fixtures still validate. Cap-pressure attribution
   pinned: a truncated-by-reasoning turn (per-turn finish_reason="length",
   reasoning_chars > 0, empty content/tool_calls — probe A's reasoning-first shape) is
   distinguishable IN THE RECORD from a content-truncated turn AND from a clean turn.
3. [unit] Default-config no-op pinned by the request body: under default Settings the
   explorer's outbound request carries NO think param (byte-identical to pre-0034);
   with `explorer_think=True/False` the param appears with that value; Deep's outbound
   request carries neither the knob nor the param (outbound-field guard extended, rots
   false on leak).
4. [unit] `verify_trajectory` OUTCOME-equality (status, failure_reason, all four fact
   fields) on the existing valid-trajectory fixture set — artifact-byte identity
   explicitly disclaimed (the schema stamp changes); the four-facts contract and the six
   failure codes untouched.
5. [integration] Live recording proof with the 0023 input-validity-precondition
   fallback: preflight-probe the stack (one direct `/v1` call — does THIS served model
   emit `reasoning` by default?); if yes, a live explorer run must record non-zero
   per-turn reasoning lengths (the hidden variable is now visible); if no, record the
   condition NOT-EXERCISED (never a silent pass) — AC1/AC2's hermetic fixtures carry the
   mechanism proof. Skip-not-fail on absent stack.
6. [doc] conventions.md: the "invisible generation is a measurement-integrity defect"
   rule — any model-generated stream that consumes budget must be observable in the
   trajectory artifact; the 0031–0033 baseline asterisk (measured under
   invisible-truncation RISK) recorded.

## Out of Scope

- The thinking-arm vs default-arm A/B (the eval set's paired instrument consumes this).
- Any claim that thinking improves localization (causal claim withheld per the
  experiment verdict).
- Changing `explorer_max_tokens` defaults (revisit WITH the visibility this spec adds —
  now token-denominated via per-turn `completion_tokens`).
- Reasoning-text storage in the artifact or an opt-in full-text side-channel (OQ3
  resolved: DROPPED for now — full per-turn reasoning text is already obtainable via
  the experiment driver's trajectory JSONs when debugging demands it; a shipping writer
  expands surface for no AC).
- Deleting `explorer_enable_thinking` / dropping llama.cpp template support (coexist
  per OQ1's resolution; a removal is its own reconciled spec if llama.cpp is ever
  retired).
- Any loop/tool/normalize behavior change.

## Open Questions

(none — OQ1 resolved to coexist-with-one-recorded-mode, OQ2 resolved to the
backend-side accumulator, OQ3 resolved to drop-for-now; all recorded above with
rationale. The only plan-time freedom left is naming: `explorer_think` vs
`explorer_native_think`, and the accumulator field names.)
