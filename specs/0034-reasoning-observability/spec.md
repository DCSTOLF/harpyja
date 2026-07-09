---
id: "0034"
title: "reasoning-observability"
status: draft
started_at_sha: 34c2c3b
created: 2026-07-09
authors: [claude]
packages: []
related-specs: ["0033-scoped-grep-paths", "0031-live", "0028-generation-control"]
---

# Spec 0034 — reasoning-observability (measurement-integrity fix, priority one)

## Why

The 0033-adjacent think-experiment probes established a hidden variable: **qwen3:14b on
Ollama thinks BY DEFAULT** — the `/v1` response carries a `reasoning` field (3949 chars on
a trivial prompt) even with no `think` param — and the gateway's `complete_with_tools`
return dict silently DROPS it while the generated reasoning counts against
`explorer_max_tokens=2048`. Consequence: **every 0031–0033 live capability read ran under
invisible-reasoning cap pressure and none of it is observable from the trajectory
artifacts** — those baselines carry an asterisk; they are not clean. This spec is the
measurement-integrity fix that closes the blind spot: make the reasoning VISIBLE in the
trajectory record (per-turn lengths at minimum) and make `think` a RECORDED,
`explorer_*`-scoped knob — exposing and controlling a thing that is ALREADY HAPPENING,
not adding a feature.

**The cap mechanics are empirically pinned (2026-07-09 probes):** Ollama's `/v1`
compat layer translates our `max_tokens` into `num_predict` and enforces it exactly —
`max_tokens=20` → `completion_tokens: 20`, `finish_reason: length`, identical to native
`options.num_predict=20` (`eval_count: 20`, `done_reason: length`). So
`explorer_max_tokens` IS a real hard bound on Ollama (no unbounded-generation gap behind
the naming difference) — AND the probe showed the budget is consumed REASONING-FIRST:
with the cap at 20, all 20 tokens went to `reasoning` (51 chars of thinking, zero
content) before any content/tool_call could be emitted. A hard turn under the 2048 cap
therefore starves the ACTING tokens after thinking takes its cut, the loop types it
`generation-truncated`, and pre-0034 nothing in the artifact shows reasoning was the
consumer. Per-turn reasoning lengths alongside the existing `finish_reason` make
cap-pressure attribution possible for the first time. (Note the cap is per-TURN — each
loop turn gets a fresh `max_tokens`; whole-run bounds remain the turn cap + wall-clock
ceiling, unchanged.)

This is NOT the causation experiment. The think-experiment's verdict stands: mechanism
UNESTABLISHED, most likely variance (both tested knobs measured inert — thinking already
default-on, cap never bound at max 1041 tokens/turn). Run 2's first-ever right-file +
first-ever `symbols` invocation is a proof-of-mechanism for the 0030 tool chain, NOT
evidence that thinking improves localization. The paired thinking-arm vs default-arm A/B
belongs to the eval set (the ONLY thing that settles causation — no more ad-hoc single
runs) and CONSUMES this spec's observability.

**Ref:** specs/0033-scoped-grep-paths/thinking-experiment/ (probes, findings, the two
committed trajectories), 0028 (the obsolete disable rationale: llama.cpp-era
`<think>`-in-content contamination — the Ollama API shape isolates reasoning
structurally), 0031 (trajectory-verified measurement), conventions.md
(generation-control knob scoping, 0028 AC2/AC8 pattern).

## Invariants

**INVARIANT (observability, not behavior):** this spec changes what is RECORDED, never
what the model generates or how the loop decides. `verify_trajectory`'s outcomes on
existing trajectories are byte-unchanged; the loop's control flow is byte-unchanged.

**INVARIANT (additive gateway contract):** `complete_with_tools` surfaces `reasoning`
ADDITIVELY (existing keys unchanged, absent → `None`/`""`), the same discipline as the
0028 `finish_reason` and 0031 `model` additions. No transport change, no second outbound
path.

**INVARIANT (knob scoping, 0028 pattern):** `think` is an `explorer_*`-prefixed Settings
field passed ONLY from the explorer's `_default_model_call`; the shared `ModelGateway`
stays param-driven with no default of its own, and the Deep-tier outbound-field guard is
extended so Deep never carries it. Reconcile with `explorer_enable_thinking` (the 0028
`chat_template_kwargs` mechanism targeting the llama.cpp template era) — supersede or
coexist is decided at plan, but the RECORDED effective thinking-mode must be a single
unambiguous trajectory field either way.

**INVARIANT (artifact carries lengths, not prose):** the trajectory record/artifact gains
per-turn reasoning LENGTHS (and the effective think-mode), NOT the reasoning text itself
— the artifact stays a measurement record, not a transcript dump (full text stays
available via an opt-in side-channel for debugging, decided at plan). Additive fields,
`VERIFIER_SCHEMA_VERSION` bumped with the 0033 version-gate pattern (legacy 0031/1 and
0033/1 artifacts still validate).

## What

- Surface `reasoning` additively in `ModelGateway.complete_with_tools`'s return dict.
- Record per-turn reasoning lengths (+ effective think-mode) through the loop's history
  capture → `build_trajectory_record` → the persisted verifier artifact; bump the
  verifier schema with the version-gate pattern.
- Add `explorer_think` (name at plan) as the recorded, explorer-scoped knob; extend the
  Deep outbound-field guard; reconcile `explorer_enable_thinking`.
- Regression-pin: existing valid trajectories verify unchanged; a reasoning-bearing
  response with the field dropped (legacy shape) records length 0/None honestly, never a
  fabricated count.

## Acceptance Criteria (sketch — refine at review)

1. [unit] `complete_with_tools` returns `reasoning` additively; absent-field default
   pinned (both directions, the 0028 finish_reason test pattern).
2. [unit] Per-turn reasoning lengths + effective think-mode land in the trajectory
   record and the persisted artifact; schema bumped, version gate extended, legacy
   artifacts still validate (fixture-pinned). Cap-pressure attribution pinned: a
   truncated-by-reasoning turn (finish_reason="length", reasoning length > 0, empty
   content/tool_calls — the probe-established reasoning-first consumption shape) is
   distinguishable IN THE RECORD from a content-truncated turn.
3. [unit] `explorer_think` is explorer-scoped by construction: Deep's outbound request
   carries neither the knob nor a think param (outbound-field guard extended, rots false
   on leak).
4. [unit] `verify_trajectory` outcomes on existing valid trajectories byte-unchanged
   (regression); the four-facts contract and failure codes untouched.
5. [integration] One live run records non-zero per-turn reasoning lengths on the default
   arm (proving the hidden variable is now visible); skip-not-fail on absent stack.
6. [doc] conventions.md: the "invisible generation is a measurement-integrity defect"
   rule — any model-generated stream that consumes budget must be observable in the
   trajectory artifact; the 0031–0033 baseline asterisk recorded in the eval docs.

## Out of Scope

- The thinking-arm vs default-arm A/B (the eval set's paired instrument consumes this).
- Any claim that thinking improves localization (causal claim withheld per the
  experiment verdict).
- Changing `explorer_max_tokens` defaults (revisit WITH the visibility this spec adds).
- Reasoning-text storage in the artifact (lengths only; text via opt-in side-channel).
- Any loop/tool/normalize behavior change.

## Open Questions

1. `explorer_enable_thinking` reconciliation: supersede (delete the chat_template_kwargs
   mechanism, llama.cpp-era) or coexist (two backends, two mechanisms)? Check whether
   llama.cpp is still a supported gateway target before deleting.
2. Where does the per-turn length ride: on the assistant message records in
   `model_turns` (co-located with the turn) or a parallel `reasoning_lengths` list on
   the record (smaller diff)? Decide at plan with the loop's history-capture shape.
3. Opt-in full-text side-channel: a debug flag writing reasoning to a separate file
   (outside-repo, atomic writer), or drop entirely for now?
