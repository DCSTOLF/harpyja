---
spec: "0027"
kind: live-proof
date: 2026-07-07
stack: llama.cpp --jinja, unsloth/Qwen3-16B-A3B-GGUF:Q4_K_M @ 127.0.0.1:8131
ac5: BLOCKED (generation-runaway, downstream of the fixed map defect)
---

# Live proof — 0027 (AC5/AC6) on the 16B llama.cpp stack

The AC5/AC6 live proof was run for real (not skipped) on the served 16B stack that
reproduced the RCA. It produced a **clean, complete result for the fix this spec
scopes**, and **surfaced a second, distinct blocker** for the localization validation.

## What the fix ACHIEVED (map removal — proven)

The eager whole-repo context map is removed; the initial prompt is minimal.
**Turn-1 payload dropped from the ~10,181-token regression to ~60 tokens** — a ~170×
reduction — on BOTH cases, independent of repo size:

| case | old turn-1 (regression) | new turn-1 | repo `.py` files |
|------|------------------------|-----------|------------------|
| `astropy__astropy-12907` | ~10,181 tok | **~60 tok** | 910 |
| `django__django-12774` | (bigger) | **~61 tok** | 2,611 |

AC1, AC2, AC4, AC6-(payload), AC8, AC9 are met; all units (T1–T11) green. The
"simple locator out-prompts a full coding agent" defect is gone.

## What AC5 did NOT achieve (a downstream, DIFFERENT blocker)

Both cases **degraded with `cause=model-unreachable` after ~300s** (`turns_used=None`,
no citations) — a per-call HTTP timeout, NOT a localization result. AC4's cause
taxonomy named it precisely, and per AC5 that outcome "must NOT be a timeout/backend
degrade." **AC5 is therefore BLOCKED.**

Per-case (llama.cpp, `scout_max_turns=10`, `scout_wall_clock_s=600`, `lm_http_timeout_s=300`):

| case | bucket | outcome | cause | turns | turn-1 tok | elapsed |
|------|--------|---------|-------|-------|-----------|---------|
| astropy-12907 | empty | degrade | model-unreachable | None | ~60 | 307.0s |
| django-12774 | empty | degrade | model-unreachable | None | ~61 | 302.4s |

## Diagnosis — generation runaway (NOT the map, NOT localization capability)

This is **not** the context bloat (gone — 60-token prompt) and **not** a
localization-capability finding: the model never got to localize. The 16B **runs away
generating** on the explorer's open-ended localization prompt and never returns a
first response inside the 300s per-call timeout → `model-unreachable`. Measured:

- Bare `call grep` probe: **4.9s** ✅ (the model + server are healthy and DO tool-call).
- Explorer minimal prompt + 4 tool schemas: **blocked >120s** (never returned).
- **`/no_think` alone (no cap): still ran away — 180s timeout.**
- **`/no_think` + `max_tokens=512`: tool-called (`ls`) in 13.2s** (`finish=length`; the
  512 cap truncated the tool-call args — too tight, but the runaway is gone).

So the runaway is **two-fold**: Qwen3 **thinking mode** contributes, but even with
thinking off the model **over-generates without a `max_tokens` bound**. The working
lever is **generation control = thinking-off (`/no_think` / `enable_thinking:false`) +
a tuned `max_tokens` cap** (larger than 512 so a tool call completes, bounded enough to
avoid runaway). OpenCode localizes in seconds because it drives the model with exactly
this kind of bounded, directive generation.

**`model-unreachable` here ≠ "can't localize"** — the same degrade-masks-outcome trap
the 0026 RCA corrected. Do NOT read this as a capability result.

## Decision — B (ship the proven map removal; HOLD AC5)

The map removal is a clean, complete, shippable result. Generation control is a
**different fix** (a different subsystem — the model call / prompt / sampling), so per
the one-spec-one-concern + close-vs-hold-by-cause conventions, AC5 is a **HOLD naming
the fix**, not a capability finding, and the generation-control work is a **follow-up
spec** — NOT 0027 scope creep.

## Follow-up (named) — generation control is a PREREQUISITE, not cleanup

A follow-up spec must bound the explorer's model generation: disable Qwen3 thinking for
the explorer's tool-calling calls and impose a tuned `max_tokens` cap (and/or a more
directive tool-use prompt), then re-run AC5/AC6 here. This is **not 0027 cleanup** — it
is a **prerequisite for ANY honest model measurement through the explorer**, including
the confounded 0026 pilot re-run and the model bake-off. The `/no_think`+cap=13.2s
number above is that follow-up's first evidence and first AC.
