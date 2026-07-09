---
spec: "0028"
kind: live-proof
date: 2026-07-07
stack: llama.cpp --jinja, unsloth/Qwen3-16B-A3B-GGUF:Q4_K_M @ 127.0.0.1:8131
ac4: PASS (first call clean tool_calls in ~2s)
ac5: BLOCKED (NEW downstream cause — loop parallel-tool-call mismatch, NOT generation control)
ac6: recorded (localization-quality comparison DEFERRED behind the AC5 blocker)
ac7: cap validated for well-formed turns; truncations traced to the loop bug, not cap size
---

# Live proof — 0028 (AC4/AC5/AC6/AC7) on the 16B llama.cpp stack

Run for real on the served stack that 0027 used. Generation control — the spec's
actual deliverable — is **proven working**. The live run then surfaced a **second,
distinct blocker** for the AC5 localization payoff, and the new AC0 `finish_reason` +
AC3 typed-truncation machinery let us **diagnose it precisely** (0027 could only see a
masked `model-unreachable` hang).

## AC4 — first-call latency (PASS)

A first explorer model call returns a well-formed `finish_reason == "tool_calls"`
(non-truncated) fast, at every cap and both thinking modes — far inside the ≤30s bound:

| cap | thinking | finish_reason | n_tool_calls | first_tool | elapsed |
|-----|----------|---------------|--------------|-----------|---------|
| 2048 | off | tool_calls | 4 | ls | 2.6s |
| 4096 | off | tool_calls | 4 | ls | 2.2s |
| 8192 | off | tool_calls | 4 | ls | 2.2s |
| 16384 | off | tool_calls | 4 | ls | 2.2s |
| 2048 | on | tool_calls | 4 | ls | 1.9s |
| 4096 | on | tool_calls | 4 | ls | 2.1s |
| 8192 | on | tool_calls | 4 | ls | 2.2s |
| 16384 | on | tool_calls | 4 | ls | 2.4s |

The 0027 "the model never finishes generating turn 1" symptom is GONE: with a cap
present the first call is clean and ~2s. Note the model emits **4 parallel tool_calls**
in that first response — the key to the AC5 blocker below.

## AC5 — localization (BLOCKED by a NEW downstream cause)

Full `engine.search` on both gold cases, cap 2048, both thinking modes: all four runs
degraded — **`generation-truncated` at ~50s** (the one exception, django thinking=on,
hit a transient `model-unreachable` at 10s — a server blip, re-run truncated too):

| case | cap | thinking | bucket | cause | elapsed |
|------|-----|----------|--------|-------|---------|
| astropy-12907 | 2048 | on | EMPTY | generation-truncated | 52.5s |
| django-12774 | 2048 | on | EMPTY | model-unreachable (blip) | 10.0s |
| astropy-12907 | 2048 | off | EMPTY | generation-truncated | 52.2s |
| django-12774 | 2048 | off | EMPTY | generation-truncated | 49.7s |

Raising the cap did NOT fix it — it only made the truncation SLOWER (astropy cap 8192,
thinking off: still `generation-truncated`, now at **237.6s**). So the model runs away
to whatever cap you set; a bigger cap is not a completion.

### Root cause — a loop parallel-tool-call mismatch (NOT generation control)

The first call is clean (~2s) but emits **4 parallel tool_calls**. The explorer loop
(`explorer_loop.py`) echoes ALL 4 into the assistant message but processes and answers
only `tool_calls[0]` — leaving **3 tool_calls with no matching `tool` response**. That
is malformed per the OpenAI tool protocol, and it derails the model into a runaway
generation on turn 2. Controlled turn-2 diagnostic (same cap 4096, thinking off, only
the message shape differs):

| turn-2 assistant state | turn-2 finish | turn-2 latency |
|------------------------|---------------|----------------|
| **FULL** — all 4 tool_calls, 1 answered (the loop's current behavior) | `length` (runaway) | 101.4s |
| **TRIMMED** — only tool_calls[0], 1 answered (well-formed) | `tool_calls` | 0.8s |

Well-formed → clean 0.8s tool_call; malformed → runaway to the cap. **The runaway is a
loop message-handling bug, not a generation-control problem.** Generation control did
its job: it converted 0027's unbounded 300s hang (masked as `model-unreachable`) into a
fast, precisely-attributed `generation-truncated` degrade, and AC0's surfaced
`finish_reason` is exactly what made the mechanism visible.

**`generation-truncated` here ≠ "can't localize"** — the same degrade-masks-outcome
trap the 0026 RCA and the 0027 close both flag. Do NOT read it as a capability result.

## AC6 — lever choice (DEFERRED, with data)

AC6 asks the shipped `explorer_enable_thinking` be chosen against AC5 localization
QUALITY. That comparison is **not yet measurable** — the loop bug blocks every run from
reaching a citation regardless of thinking mode (both truncate on turn 2). What IS
measured: first-call latency is essentially identical (~2s) both ways, and thinking-on
is marginally faster (1.9–2.4s vs 2.2–2.6s). Shipped config is the provisional
**`explorer_enable_thinking=True` (thinking on), `explorer_max_tokens=2048`** — both
first-call-clean and cap-fitting. The localization-quality comparison is deferred behind
the loop-fix follow-up; if thinking-off later proves better for localization, flip it
then (the knob makes that a one-line Settings change).

## AC7 — cap tuned for BOTH bounds

- **Upper (runaway):** the cap bounds it — an unbounded turn now degrades instead of
  hanging forever. Confirmed live (2048 → 52s degrade; 8192 → 237s degrade; both bounded).
- **Turn-budget headroom:** a WELL-FORMED turn completes far under cap 2048 — the first
  call (4 tool_calls) in ~2s and the TRIMMED turn-2 (finish=tool_calls) in 0.8s, both
  well under the 2048-token budget. So 2048 has ample headroom for legitimate turns
  (including a multi-span `submit_citations` — ~8000 chars). The truncations observed
  are NOT cap-too-small; they are the loop bug generating unboundedly. **Both bounds
  checked, not latency alone.** `N=10` is inherited unchanged from the 0026/0027 harness.

## Decision — ship the proven generation control; AC5 is a HOLD naming the NEW blocker

Per one-spec-one-concern + HOLD-BY-CAUSE: the loop parallel-tool-call fix is a DIFFERENT
subsystem (`explorer_loop.py` message handling, spec-0024 territory), out of 0028's
stated scope (generation control; loop byte-untouched except AC3's truncation check).
`test_harness_live.py`'s AC5 case stays `xfail` with its reason **re-pointed** from the
now-FIXED "unbounded generation" to the newly-diagnosed **"loop echoes N parallel
tool_calls but answers only the first → malformed conversation → turn-2 runaway."** The
AC4 first-call test is added as a REAL passing integration test (a genuine win).

## Follow-up (named) — the loop parallel-tool-call fix is the next PREREQUISITE

A follow-up spec must make the explorer loop's assistant echo well-formed — either trim
the echoed `tool_calls` to the single call it processes, or answer all N parallel calls
(the OpenAI-correct shape). The TRIMMED=0.8s-clean result above is that follow-up's first
evidence. It is a BLOCKING PREREQUISITE for AC5 localization, the 0026 pilot re-run, and
the model bake-off — the harness now bounds and diagnoses runaway cleanly, but cannot yet
DRIVE the model to a citation until the loop conversation is well-formed.
