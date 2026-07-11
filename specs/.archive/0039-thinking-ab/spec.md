---
id: "0039"
title: "thinking-ab"
status: closed
started_at_sha: "ee08532da1a0fbd033810e82fe93c58e1ab5357e"
created: 2026-07-10
---

# Spec 0039 — thinking-ab

Thinking A/B — does reasoning-on rescue the conceptual cases?

## Why

Since the N=2 think-experiment (run 2: first-ever right-file + first-ever `symbols` use), the open
question has been whether thinking-on causally improves localization or run 2 was variance — the two
tested knobs were measured inert, so nothing was established. That question is now answerable: 0034 made
reasoning observable, 0037 caught the knob was a no-op, 0038 reconciled it (`reasoning_effort` on `/v1`)
so `explorer_think` toggles GENERATION, proven behaviorally (off-arm zero reasoning vs 850–3980 chars on).
And 0036 built the reachability-tagged eval set whose natural sample is conceptual-MAJORITY (15/19) —
exactly the stratum thinking is hypothesized to help (structural navigation vs phrase-grep). This spec
runs the paired A/B to settle causation, split by reachability.

Ref: think-experiment (N=2 motivation, cause-unestablished), 0034 (reasoning recording), 0038 (working
knob, behavioral proof), 0036 (reachability-tagged eval set, min-usable=12 / min-discordant=8,
conceptual-majority), 0031–0035 (the trustworthy verifier instrument), 0026/0023 (paired-power
discipline).

### Invariants

- **Paired, not difference-of-rates:** thinking-arm vs off-arm on the SAME cases, same seed where
  controllable; McNemar on signal-bearing discordant pairs (a flip where at least one arm localizes),
  per the committed floor (min-discordant=8). Not two independent accuracy rates.

- **The contrast is DECISION-RELEVANT: None(default-on) vs False(off) — decided here, not deferred.**
  The follow-up decision this spec feeds is whether to flip the shipped default `explorer_think=None`
  → `False`; that decision needs None-vs-False measured. None is NOT a soft control — 0038 proved it
  behaviorally ON (852–3457 reasoning chars/turn live, default-on through the `/v1` `reasoning_effort`
  omission), so None-vs-False is a clean generation-level contrast AND the shipped one. Running
  True(`reasoning_effort:"high"`) vs False instead would earn a verdict for an effort level nobody
  ships. True(`high`) MAY run as a cheap third OBSERVATIONAL arm (recorded, reported alongside), but
  it never enters the paired verdict.

- **Arms are genuinely different — the 0037 lesson, guarded TWO-FACTOR per pair:** the off arm must be
  behaviorally-proven distinct from the on arm from the ARTIFACT, not the config, on BOTH factors the
  `0038/1` artifact already carries: (a) reasoning present/absent (per-turn `reasoning_chars`) AND
  (b) the `completion_tokens` budget delta from `per_turn` — field-presence alone is the
  serialization-level assertion the generation-level-proof convention warns against. A pair whose
  "off" arm shows reasoning is INVALID: excluded-and-recorded with its cause (the 0036 exclusion
  discipline), never silently dropped and never counted; an invalid-pair rate above the pre-registered
  ceiling trips CONFOUNDED at run level. An A/B over two secretly-identical arms is the exact failure
  0037/0038 existed to prevent — guard it at the measurement, not just the setting.

- **Reachability split is first-class — and only reported where powered:** results reported SPLIT by
  the 0036 reachability tag (lexical vs conceptual). The headline is not one accuracy number — it's
  "does thinking move the CONCEPTUAL stratum," because that's the hypothesis and the majority. A
  whole-set average would hide the effect the spec exists to measure (the RETRIEVAL_FUNDAMENTAL
  confound: conceptual cases defeating lexical nav must not average into "thinking doesn't help").
  The lexical stratum is N=4 — below any floor — so its line is typed STRATUM_UNDER_POPULATED
  (the `conceptual_stratum_report` pattern): described, never verdicted, never implied comparable.

- **The decision surface is FROZEN BEFORE the run:** every verdict-shaping choice lives in a
  pre-registered frozen+hashed config committed BEFORE any live arm fires (the 0023/0026
  `PREREGISTERED_*` convention) — arm identities, McNemar alpha, the K-repeat fold rule, per-stratum
  floors, the invalid-pair ceiling, the degrade-asymmetry threshold, and the verdict mapping. The
  verdict is a TOTAL PURE FUNCTION over that config and the run's pair records; nothing about the
  mapping is decidable after outcomes are visible.

- **Typed outcome, causation withheld unless earned — all four members defined:**
  - `THINKING_HELPS` — signal-bearing discordant pairs ≥ the floor on the stratum, AND the McNemar
    exact test on b/c favors the on arm at the frozen alpha.
  - `THINKING_HURTS` — same, favoring the off arm (the enum is direction-complete; a one-sided label
    set would be a steering surface).
  - `NO_EFFECT` — floor met, test not significant at the frozen alpha. NO_EFFECT REQUIRES the floor:
    an under-floor null is UNDER_POWERED, never NO_EFFECT.
  - `UNDER_POWERED` — signal-bearing discordant pairs < the floor on the stratum (per-stratum: the
    conceptual stratum gets its own line and its own power). N=19 with the 0036 shortfall is real; if
    the floor isn't met on the conceptual stratum specifically, that's UNDER_POWERED, not a null.
  - `CONFOUNDED` — the run-integrity predicate fires: invalid-pair (arm-indistinct) rate above the
    frozen ceiling, OR per-arm typed-degrade asymmetry above the frozen threshold (the on arm pays
    the reasoning tax against `explorer_max_tokens=2048`, so generation-truncated/wall-clock degrades
    can differ systematically by arm and masquerade as an effect — the 0026/0027 degrade-masks-outcome
    trap), OR any verifier-failed/missing artifact in a counted pair. CONFOUNDED is checked FIRST;
    a confounded run never emits a statistical verdict.
  The predicates are non-overlapping and total (the 0023 total-outcome-space discipline), unit-tested
  over the full outcome grid.

- **Cheap gate before the expensive run:** a power PRE-CHECK projects the achievable conceptual-stratum
  signal-bearing discordant count from the existing 0036 pilot artifacts BEFORE the paired run fires
  (the 0026 pilot-gate discipline). If the projection cannot reach the floor, the typed stop
  `UNDER_POWERED_STOP` is the run's honest deliverable — "enlarge the pool first (the named 0036
  carry-forward)" — discovered for free, not after ~4+ hours of live wall-clock.

## What

- Run each eval case paired through the working 0038 knob on the trustworthy verifier instrument:
  arm A `explorer_think=None` (shipped default, behaviorally ON) vs arm B `explorer_think=False`
  (off). Optional third observational arm `explorer_think=True` (`high`) if wall-clock allows — never
  in the paired verdict.
- K-repeats per case+arm to separate thinking-effect from run-variance (the think-experiment's
  unresolved confound): the K value and the fold rule collapsing K repeats to ONE binary outcome per
  case+arm (any-success / majority / all — McNemar needs one outcome per cell; repeats must never
  become pseudo-independent samples) are frozen in the pre-registered config, sized against the floor
  and wall-clock (~200s/case × arms × K).
- Per case+arm: durable verifier artifact (bucket, tools incl. symbols-adoption, reasoning
  tokens/chars, `completion_tokens` per turn, submitted/surviving, think_mode, `serving_transport`).
  Reasoning-token COST recorded (the bake-off cost axis).
- A committed operator driver under `specs/0039-thinking-ab/` (authored archive-aware per the
  evidence-path convention): STOP-AND-WARN preflight (served `lm_model` tag resolved — the default
  tag is NOT servable, per 0036 — verifier preflight green) before any arm fires; RESUMABLE per-case
  ledger (the run outlasts one invocation); strict skip→hard-fail posture for the deliverable run
  (the 0038 `run_effectiveness.sh` precedent).
- Aggregate: McNemar exact test on signal-bearing discordant pairs, SPLIT by reachability;
  symbols-adoption rate per arm (the think-experiment's other signal — does thinking drive tool
  adoption?); reasoning-cost delta; per-arm typed-degrade table (the CONFOUNDED input).
- Emit the typed verdict + the split table as a committed, test-pinned claim artifact; evidence path
  pins authored against `specs/.archive/0039-thinking-ab/` from the start (the 79f7bf2 lesson).

## Acceptance criteria

_Legend: [unit] = fakes; [integration] = live, skip-not-fail unless noted; [doc] = documentation._

1. [unit] A frozen+hashed `PREREGISTERED_AB_CONFIG_0039` (arm identities None-vs-False, alpha, K and
   the K-fold rule, per-stratum min-discordant floors, invalid-pair ceiling, degrade-asymmetry
   threshold, verdict mapping) exists and is committed BEFORE any live arm fires; the verdict is a
   TOTAL PURE FUNCTION over (config, pair records) with unit tests covering the full outcome grid —
   every enum member reachable, predicates non-overlapping, CONFOUNDED checked first.
2. [unit] Paired McNemar exact test over signal-bearing discordant pairs (not diff-of-rates); the
   frozen min-discordant floor gates the verdict; under-floor → UNDER_POWERED, never NO_EFFECT and
   never a forced result.
3. [unit] Arm-distinctness guard is TWO-FACTOR from the artifact (reasoning present/absent AND the
   per-turn `completion_tokens` delta): a pair whose off arm shows reasoning is EXCLUDED-AND-RECORDED
   with its cause; an invalid-pair rate above the frozen ceiling yields CONFOUNDED; exclusions never
   silently attrit N.
4. [unit] Reachability split computed and reported; the conceptual stratum has its own verdict line
   with its own floor; the lexical stratum (N=4) emits a typed STRATUM_UNDER_POPULATED line — never
   an implied verdict.
5. [unit] Power pre-check: a projection of the achievable conceptual-stratum signal-bearing discordant
   count from the committed 0036 pilot artifacts, with a typed `UNDER_POWERED_STOP` outcome that
   GATES the live paired run (pre-check fails → the run does not fire; the stop is the recorded
   deliverable).
6. [integration] Live paired run over the 0036 set via the committed driver (STOP-AND-WARN preflight
   incl. served-model resolution; resumable per-case ledger; strict skip→hard-fail for the deliverable
   run): per-arm verifier-clean artifacts durable under the spec dir; McNemar computed;
   symbols-adoption-per-arm, reasoning-cost-delta, and the per-arm typed-degrade table recorded.
7. [integration] Typed verdict emitted (THINKING_HELPS / THINKING_HURTS / NO_EFFECT / UNDER_POWERED /
   CONFOUNDED), split by reachability, as a committed claim artifact test-pinned to computed truth
   (path pins archive-first); whole-set average NOT the headline.
8. [doc] Causation stance: the think-experiment N=2 is cited as motivation only; this run's verdict is
   the first powered read, and its own N/power stated honestly. No default-flip decided here (that
   follows the verdict, separate spec). The observational True(`high`) arm, if run, is reported as
   observational only.

## Out of scope

- Flipping the default think mode (follows the verdict).
- The model bake-off (separate; this is one model's think A/B, not model-vs-model).
- The semantic-tier decision (informed by this + bake-off, not made here).
- Tuning `explorer_max_tokens` for thinking (separate spec if the degrade-asymmetry data shows a
  budget interaction — this spec RECORDS the asymmetry and lets it trip CONFOUNDED; it does not tune).
- Pool enlargement past the 0036 blind-clean 19 (the named 0036 audited convert step — the power
  pre-check may make it the prerequisite, but executing it is its own spec).
- Non-Ollama backends.

## Open questions

1. **K sizing (not whether):** K-repeats and the fold rule are committed invariants; the open choice is
   K's value (K=2 vs K=3) and whether the observational True arm gets K=1 — sized against wall-clock
   (~200s/case × arms × K over 19 cases) and the floor projection from the AC5 pre-check. Freeze in
   `PREREGISTERED_AB_CONFIG_0039` at plan time, before any live run.
2. **Seed control:** Ollama exposes a `seed` option — pin one seed for all runs (maximally paired, but
   K-repeats then measure less variance) or vary seed per repeat under a recorded schedule (variance
   visible, pairing preserved per-repeat)? Lean: fixed seed schedule per repeat index (repeat k uses
   seed S_k for BOTH arms), recorded in the frozen config. Decide at plan time.
