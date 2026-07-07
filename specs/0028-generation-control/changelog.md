---
spec: "0028"
closed: 2026-07-07
---

# Changelog — 0028 generation-control (bound the explorer's per-call generation)

## What shipped vs spec

- **`finish_reason` surfaced additively from the Model Gateway (AC0 — PROVEN).**
  `ModelGateway.complete_with_tools` now returns `{content, tool_calls, finish_reason}`,
  reading `choices[0].finish_reason` (the CHOICE, not the message), `str`-cast when
  present and defaulting to the exact sentinel `"unknown"` when absent. Backward-additive
  (the two existing keys unchanged), pinned by unit tests. This is the load-bearing key:
  it is what made the AC5 blocker below **diagnosable** where 0027 saw only a masked hang.
- **`explorer_max_tokens` cap — the PRIMARY anti-runaway lever (AC2 — PROVEN).** A
  `Settings` field (`= 2048`, additive-last, env-coerced) threaded into the explorer's
  per-call `complete_with_tools`. Per DRIFT-GUARD the finite cap ALSO lives on the
  explorer-owned object's own field default (`ExplorerBackend.max_tokens = 2048`, pinned
  by a field-default introspection test), so a `Settings`-bypassing construction is still
  bounded. `ModelGateway` stays purely param-driven (NO `max_tokens` default of its own),
  so the Deep-tier path is never capped.
- **`explorer_enable_thinking` thinking knob (AC1 — PROVEN, the KNOB not a mandate).** A
  `Settings` bool; when False the explorer's gateway call carries request param
  `chat_template_kwargs={"enable_thinking": False}`, when True the param is OMITTED. The
  inferior `/no_think` query token is rejected. Bidirectional unit test. Shipped default
  `True` (see AC6 below).
- **`generation-truncated` — the fifth explorer degrade cause (AC3 — PROVEN).** A
  `finish_reason == "length"` turn is a typed degrade emitting the stable cause
  `scout-degraded:generation-truncated` — REGARDLESS of whether a syntactically valid
  `tool_call` rode along (a length-truncated response was cut off mid-generation; its
  args may be silently incomplete). Plumbed through the whole chain:
  `explorer_loop.GENERATION_TRUNCATED` outcome (checked right after the model call,
  before any tool dispatch) → `errors.GENERATION_TRUNCATED` → `ExplorerBackend`
  `_EXHAUSTION_CAUSE` → runner `_SCOUT_NATIVE_CAUSES` + `scout_degrade_generation_truncated_count`
  → report field + `_AGGREGATE_DEFAULTS`; `SCHEMA_VERSION 0027/1 → 0028/1` (legacy blocks
  still validate).
- **Explorer scope enforced by construction (AC8 — PROVEN).** The knobs are
  `explorer_`-prefixed and passed ONLY by the explorer's `_default_model_call`. A new
  `harpyja/deep/test_rlm.py` guard asserts the Deep-tier outbound call (`rlm(query=...)`)
  carries NEITHER the cap NOR `chat_template_kwargs.enable_thinking` — asserting on the
  actual outbound fields, not the absence of the Settings names. It PASSES on introduction
  (Deep is byte-untouched) and ROTS FALSE on any future leak.
- **AC4 first-call latency — PROVEN LIVE.** On the served 16B stack a first explorer
  model call returns a well-formed, non-truncated `finish_reason == "tool_calls"` in ~2s
  (measured 1.9–2.6s across caps 2048–16384, both thinking modes) — far inside ≤30s. The
  0027 "the model never finishes generating turn 1" symptom is GONE with a cap present.
  `test_first_explorer_call_returns_toolcall_under_30s` is a REAL passing integration test.

Units: **1046 pass** (unit), **0 fail**, ruff clean. Live: AC4 pass, AC5 xfail (below).

## AC5 HOLD — RE-POINTED from a FIXED cause to a NEW, precise one

The 0027 blocker — **unbounded generation** (the 16B ran to a 300s timeout, masked as
`model-unreachable`) — is **FIXED**: the cap bounds it, AC0 surfaces `finish_reason`, and
AC3 types it as `generation-truncated`. But the live AC5 run surfaced a **second, distinct
downstream blocker**, and the new machinery diagnosed it precisely.

**The mechanism (named, not "a loop bug"):** on turn 1 the model emits **N parallel
`tool_calls`** (measured N=4). The explorer loop (`explorer_loop.py`) echoes ALL N into
the assistant message but processes and answers only `tool_calls[0]`, leaving **N−1
`tool_calls` with no matching `tool` response**. That is malformed per the OpenAI tool
protocol, and it derails the model into a runaway generation on turn 2 — which the new cap
then correctly catches as `generation-truncated`. Controlled turn-2 diagnostic (same cap
4096, thinking off, only the assistant message shape differs):

| turn-2 assistant state | turn-2 finish | latency |
|------------------------|---------------|---------|
| **FULL** — all 4 tool_calls, 1 answered (current loop behavior) | `length` (runaway) | 101.4s |
| **TRIMMED** — only tool_calls[0], 1 answered (well-formed) | `tool_calls` | 0.8s |

`generation-truncated` here **≠ "can't localize"** — the same degrade-masks-outcome trap
the 0026 RCA and 0027 close both flag. `test_harness_live.py`'s AC5 case stays `xfail`
(non-strict), its reason RE-POINTED from "unbounded generation" to name the exact
mechanism (**parallel-tool-call echo mismatch → turn-2 runaway**), so the follow-up starts
from the diagnosis, not a re-investigation. It flips to xpass when the loop echo is made
well-formed.

## AC6 — lever choice DEFERRED (with data), honestly

AC6 asks the shipped `explorer_enable_thinking` be chosen against AC5 localization
QUALITY. That comparison is **not yet measurable** — the parallel-tool-call blocker stops
every run from reaching a citation regardless of thinking mode (both truncate on turn 2).
What IS measured: first-call latency is essentially identical (~2s) both ways, thinking-on
marginally faster. Shipped the provisional **`explorer_enable_thinking=True`,
`explorer_max_tokens=2048`** (both first-call-clean and cap-fitting). If thinking-off later
proves better for localization, the knob makes it a one-line flip. Deferral recorded, not
hidden.

## AC7 — cap validated against BOTH bounds

- **Upper (runaway):** bounded — an unbounded turn now degrades instead of hanging
  forever (2048 → 52s degrade; 8192 → 237s degrade; both bounded, confirmed live).
- **Turn-budget headroom:** a WELL-FORMED turn completes far under 2048 — the first call
  (4 tool_calls) in ~2s and the TRIMMED turn-2 (`finish=tool_calls`) in 0.8s. So 2048 has
  ample headroom for legitimate turns (incl. a multi-span `submit_citations`, ~8000 chars).
  The truncations are NOT cap-too-small; they are the loop bug generating unboundedly.
  **Both bounds checked, not latency alone.** `N=10` inherited unchanged from 0026/0027.

## OPEN DESIGN QUESTION for the follow-up — NOT a foregone 1-liner

The fix is **not** pre-decided. Two shapes, with a real trade-off the follow-up spec must
weigh deliberately:

- **(A) Trim-to-answered** — echo only the `tool_calls[0]` the loop actually processes
  (drop the N−1 it ignores). Minimal, well-formed, and matches the loop's existing
  one-call-per-turn model. Cost: discards the model's other N−1 proposed calls each turn —
  the model must re-propose them, spending more turns against the `N=10` budget (a
  turn-budget pressure — the exact degrade-masks-outcome axis AC7 guards).
- **(B) Answer-all-N** — dispatch every parallel `tool_call` the model emits and append a
  `tool` response for each (the OpenAI-correct shape). Uses the model's parallelism (fewer
  turns to cover the same ground), but changes the loop from one-dispatch-per-turn to
  N-per-turn — more per-turn output volume (bounded by the tool clamps), reordering of the
  loop-detection / truncation bookkeeping, and a larger blast radius on the 0024 loop
  invariants.

The turn-budget tradeoff (A spends turns, B spends per-turn volume) is the crux; the
follow-up should decide it against localization quality once it can measure, not by default.

## Honest project status — the fourth consecutive downstream layer

This is the **fourth consecutive real layer** peeled between the project and its first
PROVEN localization, and each layer was a genuine, distinct defect — this is the
layered-RCA process working, not failure:

1. **0026** — terse-query instrument built, but the AC8 pilot could not measure
   (`UNDER_POWERED_STOP`): the general candidates under-powered terse-query ranking.
2. **0027** — the eager whole-repo context map bloated turn-1; removed (~170× payload cut,
   proven). AC5 localization **HELD** — blocked downstream by unbounded generation
   (masked as `model-unreachable`).
3. **0028** (this spec) — generation control proven (cap bounds runaway, `finish_reason`
   surfaced, `generation-truncated` typed, AC4 first-call ~2s live). AC5 localization
   **HELD AGAIN** — blocked downstream by the parallel-tool-call echo mismatch.

**AC5 (drive-to-citation) has now been a recorded HOLD across 0027 → 0028**, each time by
a DIFFERENT, correctly-attributed downstream cause — and 0026 was its under-powered
precursor. State it plainly: **generation control is PROVEN; drive-to-citation is still
UNPROVEN**, now gated on **parallel-tool-call handling** in the explorer loop — the next,
and hopefully final, layer before the first honest localization measurement. Each hold
narrowed the search; the harness now bounds AND diagnoses runaway cleanly, but cannot yet
DRIVE the model to a citation until the turn-2 conversation is well-formed.

## Follow-up (named) — the BLOCKING next prerequisite

A follow-up spec must make the explorer loop's assistant echo well-formed (decide (A) vs
(B) above). It is a BLOCKING PREREQUISITE for AC5 localization, the 0026 pilot re-run, and
the model bake-off. First evidence recorded: TRIMMED turn-2 = 0.8s clean vs FULL = 101.4s
runaway.

## Files touched

- `harpyja/gateway/gateway.py`, `harpyja/gateway/test_gateway.py` (AC0 finish_reason)
- `harpyja/config/settings.py`, `harpyja/config/test_settings.py` (explorer_max_tokens, explorer_enable_thinking)
- `harpyja/scout/explorer_backend.py`, `harpyja/scout/test_explorer_backend.py` (cap/thinking threading, drift-guard, truncation cause map)
- `harpyja/scout/explorer_loop.py`, `harpyja/scout/test_explorer_loop.py` (GENERATION_TRUNCATED outcome + finish=length detection)
- `harpyja/scout/errors.py` (GENERATION_TRUNCATED cause constant)
- `harpyja/scout/wiring.py` (feed both knobs at the build site)
- `harpyja/eval/runner.py`, `harpyja/eval/test_runner.py` (fifth cause count)
- `harpyja/eval/report.py`, `harpyja/eval/test_report.py` (per-cause field, SCHEMA_VERSION 0028/1)
- `harpyja/eval/test_harness_live.py` (AC4 live-pass test; AC5 xfail RE-POINTED)
- `harpyja/deep/test_rlm.py` (NEW — AC8 Deep-scope guard)
- `specs/0028-generation-control/operator-run-findings.md` (NEW — the live proof + diagnosis)
