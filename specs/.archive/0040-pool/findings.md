# Spec 0040 — findings: the overall fork

Committed evidence: `preflight/preflight_result.json` (schema `0040/preflight/1`),
`pilot/pilot_results.json` (schema `0040/pilot/1`, 33/33 cells),
`pool_fork.json` (schema `0040/fork/1`, test-pinned to `decide_pool_fork`'s
computed truth). All cite `POOL_CONFIG_HASH_0040`. **No live bake-off compute
was spent here.**

## Preflight (AC1–AC3) — all three models PASS

| model | outcome | think-control | mechanism |
|---|---|---|---|
| qwen3:14b (re-confirmed) | `preflight-pass` | effective | `reasoning_effort` |
| qwen3:8b (new) | `preflight-pass` | effective | `reasoning_effort` |
| qwen3.5:4b (new) | `preflight-pass` | effective | `reasoning_effort` |

- No model was excluded; no `THINK_CONTROL_NOOP` recorded — **all three are
  eligible as thinking-arms in a future A/B** (OQ1 answered live: the newer
  qwen3.5 generation honors `reasoning_effort` on this Ollama 0.31.1 `/v1`,
  probed under the 0038 tiny-cap two-factor discriminator, not assumed).
- Side-note for the standing `lm_model` placeholder concern: `qwen3:8b` is
  servable and preflight-clean on this stack — the first live evidence bearing
  on the unservable `hf.co/Qwen/Qwen3-8B-GGUF:latest` default's 8B size class.

## The fork (AC8) — all three pairs: `INSUFFICIENT_PILOT_EVIDENCE`

| pair | coverage (need 8) | ceiling (bound) | observed (estimate) | verdict |
|---|---|---|---|---|
| qwen3:14b vs qwen3:8b | 7 | 6 | 6 | `insufficient-pilot-evidence` |
| qwen3:14b vs qwen3.5:4b | 4 | 8 | 4 | `insufficient-pilot-evidence` |
| qwen3:8b vs qwen3.5:4b | 5 | 3 | 3 | `insufficient-pilot-evidence` |

**No pair is `PAIR_FEASIBLE`; the bake-off does not run on the current 19-case
set. The named next step for all three pairs is pool enlargement — the 0036
audited convert step — which also unblocks the 0039 thinking-A/B re-check.**

Two independent causes, both typed, neither a capability claim:

1. **Coverage under the derived minimum.** The frozen predicate requires 8
   retained conceptual pairs (`15 − c < 8`); typed per-case degrades at the
   attempt cap (below) removed 1–4 conceptual cases per pair. The pinned
   8-conceptual pilot set carries ZERO slack against the minimum — any single
   conceptual degrade forces `INSUFFICIENT_PILOT_EVIDENCE`. (A lesson for the
   enlarged-pool pre-check: pin coverage headroom above the boundary.)
2. **Even ignoring coverage, the ceilings are at or under the floor** (6, 8, 3
   vs floor 8) — the same shape as 0039's `UNDER_POWERED_STOP`. The
   extrapolation-modulo-sampling caveat 0039 accepted applies to BOTH pinned
   quantities: the ceiling is an upper bound (`projection_kind=
   "upper-bound-feasibility"`), the observed discordance a labeled point
   estimate (`estimate_kind="point-estimate"`); neither is a power estimate,
   and a FEASIBLE-on-enlargement claim will be proven only by the bake-off's
   own run.

Pilot conceptual locate-counts (power inputs, NOT a ranking — the ranking is
the bake-off's own powered run): 14b 3/7 clean conceptual, 8b 0/8, 4b 1/5.

## Run integrity — the contaminated first run (recorded, invalidated outcome-blind)

The first pilot invocation ran while (a) a concurrent pytest suite loaded the
box and (b) the dev Ollama held `qwen3:8b` + `qwen3.5:4b` PINNED in memory
with infinite keep-alive (`expires_at` ~2318, i.e. `keep_alive=-1`) — 14.3 GB
permanently resident, so every `qwen3:14b` cell ran memory-squeezed. Effects:
wall-clock expiries recorded as honest `empty` buckets (14b collapsed to 0
located vs 0036's 5/10 on the same cases) and HTTP timeouts typed
`model-unreachable`. The full run was invalidated OUTCOME-BLIND (criterion:
"recorded during the contaminated environment" = every cell, including located
ones), archived as `pilot/pilot_results.run1-contaminated.json`, and re-run
fresh with `_evict_other_models` clearing residents before each model block.
The clean re-run restored 14b to its 0036 profile — validating the diagnosis.

Persistent per-case degrades AT THE CAP in the clean run (one bounded re-run
each, the 0036 posture; recorded-by-cause, excluded from pairs, never counted):
`matplotlib-21568::14b`, `astropy-12907::4b`, `pylint-7080::4b`,
`sympy-16792::4b` (conceptual) and `pytest-10081::8b` (lexical) — all
`model-unreachable` (explorer transport timeout). These five cells are the
coverage shortfall. Follow-up worth naming: the per-case timeout sensitivity
(240 s wall clock / 300 s HTTP) on heavy repos is now the binding constraint on
pilot coverage, ahead of model capability.

## Arm parity

All 33 cells ran at `explorer_think=None` (`think_mode="default-omitted"`,
`serving_transport="v1-chat-completions"` recorded per cell) — the locate
counts are comparable power inputs, not a thinking contrast.
