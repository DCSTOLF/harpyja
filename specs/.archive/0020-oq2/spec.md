---
id: "0020"
title: "OQ2"
status: closed
created: 2026-07-02
authors: [claude]
packages: [harpyja/eval]
related-specs: [0009, 0010, 0011, 0014, 0015, 0016, 0017, 0018, 0019]
---

# Spec 0020 — OQ2

## Why

Specs 0016 / 0017 / 0018 fixed the three blockers that wedged the failed 0015
OQ2 run — B1 (served-model 404), B3 (unbounded gateway HTTP timeout that hung
`mode=auto` for hours), and B2 (the gate false-escalating correct citations
because it scored with an out-of-distribution finder model). Spec 0019 then
shipped the *instrument*: the OQ2 re-run harness, the gate-confound mechanism
(`recommend_oq2` + `gate_false_escalation_ceiling`), the preflight doctor, and
the `0014/1` report schema — but deliberately deferred the numbers. Mechanism +
instrument ≠ OQ2 calibrated.

This spec is the **operator sweep**: run that instrument against the served
model stack + provisioned N=12 subset and produce the deliverable OQ2 result —
a concrete `(verify_threshold, verify_top_n)` recommendation with a trade-off
table, OR a typed null (`gate-confounded` / `degraded-dominated` /
`not-separable`) that is itself the honest deliverable and names the next spec.
The dev host is now 32 GB with `mode=auto` OOM resolved and the served models
pulled into Ollama, so the run is feasible end-to-end — there is no
infrastructural reason left to defer the numbers again (that is why AC12 makes a
recorded typed outcome the close gate, not another skip-not-fail demo).

The structure is four sequential stop-and-report gates
(G0 preflight → G1 smoke → G2 gate-quality → G3 sweep). That sequencing is the
load-bearing lesson of 0015: find a wedge in minutes, not hours, and never tune
a threshold over a judge you have already measured to be broken. The sequencing
*is* the spec — it makes 0015's mistake (a long, expensive run over a broken
gate) structurally impossible.

## What

An operator run of the 0019 instrument as a four-gate sequential protocol, each
gate willing to stop-and-report, emitting a durable **gate-ledger** artifact and
exactly one typed outcome.

**Invariants (carried from 0019):**

- **Measurement-not-construction.** The SUT — tiers, verification gate, escalation
  matrix, judge, classifier, citation format — stays FROZEN. This spec measures;
  it does not construct. Any code change discovered necessary during the run is an
  eval-harness defect fixed with a regression test under `harpyja/eval/`, never a
  SUT edit. The orchestrator `mode=auto` path is the **observed** SUT (read-only,
  no edits) — hence `packages: [harpyja/eval]`.
- **Sequential stop-and-report gates.** Each gate runs only after the prior gate's
  verdict is recorded; a stopping gate halts the protocol before the next, more
  expensive stage.
- **Reliability-gated reporting.** `n_floor` and `degraded_dominated` can withhold
  or caveat a numeric OQ2 even over a clean-looking grid.
- **No defaults flipped from this run.** A `RECOMMENDATION` is emitted as evidence;
  applying it is a *separate* variance-gated follow-up spec.

**The four gates:**

- **G0 — Preflight (before any clone).** Assert the three required served models
  are pulled via the 0019 `preflight_models_present` doctor BEFORE
  cloning/provisioning any repo. A missing model here is B1's 404 surfaced at
  setup, not mid-run. Fail → **BLOCKED** (a hold, not a close — see D7).
- **G1 — Single-case smoke (astropy-12907), `mode=auto`.** The cheap check that
  gates the expensive sweep — one case, the full chain (served Scout + finite
  gateway timeout + instruct judge + strict parser). Checks: (a) the run completes;
  (b) scout-degrade and deep-degrade are **not dominant** (tiers alive, models
  actually served); (c) astropy-12907's correct citation is **not
  gate-false-rejected** (the B2 deferral, now proven end-to-end). Pass → G2. Fail
  splits **by cause** (D7): a non-completion caused by the **environment** — OOM /
  resource exhaustion under co-load, the G0-invisible residual 0019 named (G0 asserts
  models are *pulled*, not co-resident-loadable) — is a **BLOCKED** hold, not a close;
  a run that **completed** but is degrade-dominant or gate-false-rejects a correct
  citation is a **STOP:SMOKE** close (a valid, SUT-observing finding — the fixes
  regressed end-to-end, which names the next fix), with the failing sub-check and its
  measured values recorded. Either way the full sweep cannot pass.
- **G2 — Gate quality (point subset).** Measure whether the instruct judge actually
  judges. Run the point subset, capture `gate_false_escalation_rate` and
  `catch_rate` as first-class outputs, and run the A/B against the retained
  finder-judge baseline. Check: instruct false-escalation ≤
  `gate_false_escalation_ceiling` (0.20, provisional). **PASS (≤ ceiling)** → G3
  expecting a clean OQ2. **OVER CEILING** → do NOT abort; proceed to a
  **descriptive-only** G3 (D6) knowing it will report `GATE_CONFOUNDED` — that is
  the honest outcome, not a failure; record the measured rate (it seeds the next
  gate-accuracy spec). If the finder judge beats instruct on false-escalation, flag
  that 0018's judge choice needs revisiting (a flag, per OQ-A — this spec does not
  re-decide the judge).
- **G3 — The sweep (full N=12 subset).** `verify_threshold` × `verify_top_n` grid,
  `k_runs` (=5) runs/point, mean + spread, over the instruct-judge distribution —
  treating `verify_threshold=0.6` as **unvalidated-from-scratch** (the old value was
  calibrated against the wrong judge). G3 also records overall accuracy, escalation
  rate, Tier-0-alone accuracy, and the `fc_citation_*` shape distribution. Its
  verdict is exactly one of four typed labels, produced by the **outcome projection**
  below — never a forced pick.

**G3 outcome projection (D1/D2/D3).** The four labels are produced by a new pure
function `classify_g3_outcome(recommendation, aggregate, eval_config)` in
`harpyja/eval/`, mapping the **byte-unchanged** 0019 `recommend_oq2` result plus the
runner aggregate down to one label. The frozen dispatcher still emits only its two
strings (`recommended` / `gate-confounded`); the projection layer adds the two
reliability labels above it, so `recommend_oq2` / `rank_sweep` are not touched
(measurement-not-construction). Precedence — **DEGRADED_DOMINATED > GATE_CONFOUNDED >
NOT_SEPARABLE > RECOMMENDATION** — with **all** true blocking conditions recorded in
the ledger, not only the winning label:

- **DEGRADED_DOMINATED** — `aggregate.degraded_dominated` is true (scout∪deep
  per-case degrade rate > `degraded_dominated_threshold`, 0.5). Wins first: if the
  tiers did not run, the false-escalation reading is itself untrustworthy — a broken
  measurement apparatus invalidates the reading before it is interpreted. OQ2
  withheld; finding reported.
- **GATE_CONFOUNDED** — `recommend_oq2.outcome == "gate-confounded"` (measured
  instruct false-escalation strictly > ceiling). OQ2 withheld; measured rate reported.
- **NOT_SEPARABLE** — the recommend path ran but **no grid point cleared the
  catch-rate bar**. The discriminating signal is reachable on the byte-frozen
  `Recommendation` without touching the dispatcher: the no-survivor branch
  (recommend.py:90–99) is the **unique** state with `incumbent_validated is False`
  **and** `advantage_exceeds_variance is False`, whereas both variance-beating flips
  (recommend.py:132–149) carry `advantage_exceeds_variance is True` and a validated
  incumbent carries `incumbent_validated is True`. The honest "no defensible pick"
  null. NOTE (D2): a best alternative whose advantage is **within** the incumbent's
  variance is *not* this — `rank_sweep` calls that a **validated incumbent**, i.e. a
  RECOMMENDATION of `(0.6, 3)`.
- **RECOMMENDATION** — `recommend_oq2.outcome == "recommended"` (a validated
  incumbent OR a variance-beating flip). Because the N=12 subset is below
  `n_floor` (=30), the recommendation carries `indicative_only=True` (deltas-only,
  low-confidence — D4); it is evidence for a follow-up default-flip spec, never an
  applied default.

**Deliverable & close gate.** A `RECOMMENDATION` → the number exists (indicative-only
at N=12); the next step is a *separate* variance-gated Settings default-flip spec
(defaults are NOT flipped from this run directly). Any typed null → that IS the
deliverable; it names the next spec (gate-accuracy / harder dataset / more K). The
spec **closes** on any recorded protocol outcome that actually observed the SUT — a
`STOP:SMOKE` with measured sub-checks, or a G3 label. An environment **BLOCKED** (G0
preflight fail or fixtures absent) is a **HOLD**, not a close (D7).

## Acceptance criteria

1. A single sequential protocol driver runs G0 → G1 → G2 → G3 in order with
   stop-and-report semantics: G0 failure halts before any clone/provision; G1
   failure halts before the sweep; each gate's verdict is recorded before the next
   gate is entered. (unit-testable with injected fakes)
2. The protocol emits a durable, machine-readable **gate-ledger** — a NEW pinned
   artifact with its own version id (`ledger 0020/1`), distinct from the sweep report
   `0014/1` — recording each gate's verdict (G0 pulled / first-missing tag; G1
   pass/stop/blocked with each sub-check's **measured value** and, on a stop, the
   completion-failure cause; G2 pass/over-ceiling with the measured instruct + finder
   false-escalation A/B; G3 winning label + **all** true blocking-condition booleans)
   plus run provenance (SUT git SHA, resolved `EvalConfig`, fixture-subset id, model
   tags, the `verify_threshold`×`verify_top_n` grid), written outside any
   indexed/target repo via `atomic_write_json`, conforming to a pinned schema.
3. G0 routes through the 0019 `preflight_models_present` doctor (`assert_local`
   first, deduped required-tag set) and stops the protocol **before** provisioning
   when a required model is absent, naming the first missing tag.
4. G1 evaluates astropy-12907 alone on `mode=auto` through the full served chain and
   stops the protocol unless **all three** sub-checks pass (run completes; scout/deep
   not degrade-dominant; astropy-12907's correct citation not gate-false-rejected);
   the ledger records each sub-check's measured value. A stop is classed **by cause**:
   an **environment** non-completion (OOM / resource exhaustion — sub-check (a) failing
   for a G0-invisible reason) is a `BLOCKED` **hold**; a run that **completed** but
   fails sub-check (b) or (c) is a `STOP:SMOKE` **close**.
5. G2 captures `gate_false_escalation_rate` and `catch_rate` as first-class ledger
   fields and records the instruct-vs-finder A/B; a measured instruct
   false-escalation **over the ceiling does NOT abort** — it is recorded and the
   protocol proceeds to a descriptive-only G3 (AC9).
6. `classify_g3_outcome(recommendation, aggregate, eval_config)` is a **pure
   function** mapping the byte-unchanged `recommend_oq2` result + `degraded_dominated`
   + effective-N + catch-rate-bar survival to **exactly one** of {`RECOMMENDATION`,
   `GATE_CONFOUNDED`, `DEGRADED_DOMINATED`, `NOT_SEPARABLE`}, testable with injected
   fakes; `recommend_oq2` / `rank_sweep` remain byte-unchanged (verified by their
   existing tests still passing untouched).
7. The projection applies precedence **DEGRADED_DOMINATED > GATE_CONFOUNDED >
   NOT_SEPARABLE > RECOMMENDATION**; when more than one blocking condition holds, the
   ledger records **all** of them as booleans, and the winning label is the
   highest-precedence true condition. (a fake with both degrade-dominated and
   gate-confounded true → `DEGRADED_DOMINATED`, both booleans set.) The no-survivor
   (`NOT_SEPARABLE`) boolean is computed/recorded **only when `rank_sweep` actually
   ran** (`outcome != "gate-confounded"`) — under the gate-confound short-circuit
   `rank_sweep` never executes, so recording a no-survivor boolean there would book a
   phantom `NOT_SEPARABLE` alongside `GATE_CONFOUNDED` in the ledger.
8. Label boundaries hold: a validated incumbent (advantage within variance → keep
   `(0.6, 3)`) and a variance-beating flip both project to `RECOMMENDATION`;
   `NOT_SEPARABLE` is emitted **only** in the no-survivor state, identified on the
   frozen `Recommendation` as `incumbent_validated is False and
   advantage_exceeds_variance is False`; a `RECOMMENDATION` with effective-N <
   `n_floor` (30) carries `indicative_only=True`.
9. Under G2-over-ceiling, G3 runs a **single descriptive pass** (no
   `verify_threshold` tuning) recording accuracy / escalation / Tier-0-alone /
   `fc_citation_*` shapes, then reports `GATE_CONFOUNDED` — never a full
   `k_runs`×grid sweep over a confounded gate.
10. **No Settings default is flipped** by this spec: `verify_threshold` /
    `verify_top_n` / `verify_method` defaults are byte-unchanged; a `RECOMMENDATION`
    is emitted as evidence for a separate follow-up spec, not applied.
11. A typed-null outcome (`GATE_CONFOUNDED` / `DEGRADED_DOMINATED` / `NOT_SEPARABLE`)
    is a **complete, valid deliverable** — the protocol reports it (with the measured
    rate / finding) and names the follow-up spec, and NEVER forces a
    `(threshold, top_n)` pick to manufacture a clean-looking number. The SUT stays
    frozen: any code shipped lives under `harpyja/eval/` (additively; schema bumped
    last-with-defaults if extended), and any instrument defect found during the run
    is fixed with a regression test, not worked around in the SUT.
12. The spec's **close gate** is a recorded protocol outcome that observed the SUT —
    a `STOP:SMOKE` (a run that *completed* then degrade-dominated or gate-false-rejected,
    with measured sub-checks), or a G3 label. An environment **BLOCKED** — G0 preflight
    fail, fixtures absent, **or** a G1 sub-check-(a) non-completion for an environment
    reason (OOM / resource exhaustion) — is a **HOLD** that names the missing tags /
    fixture path + the exact command to run, and is **NOT** a valid close.
    Skip-not-fail because the environment is absent is never a valid close for 0020
    (that was 0019's contribution).

## Decisions

- **D1 — G3 taxonomy via a projection layer, dispatcher frozen.** The four labels
  come from a new `classify_g3_outcome` in `harpyja/eval/`, not from widening
  `recommend_oq2`. Keeps the 0019 dispatcher byte-frozen (measurement-not-construction)
  while giving G3 its four-label contract.
- **D2 — within-variance is a validated-incumbent RECOMMENDATION, not NOT_SEPARABLE.**
  Honors the shipped `rank_sweep` semantics (recommend.py:104–131: "validated, not
  flipped"). `NOT_SEPARABLE` is reserved for the honest no-survivor-cleared-the-bar
  null.
- **D3 — precedence DEGRADED_DOMINATED > GATE_CONFOUNDED > NOT_SEPARABLE >
  RECOMMENDATION; record all true conditions.** A broken apparatus (tiers didn't run)
  invalidates the false-escalation reading, so degrade wins first; but the ledger
  never hides a co-occurring confound. The four label conditions **overlap by
  construction** (they are not a partition) and are disambiguated **solely by
  precedence**. The `GATE_CONFOUNDED`-vs-`NOT_SEPARABLE` ordering is *vacuous* — a
  gate-confound short-circuits before `rank_sweep`, so "no survivor" can never
  genuinely co-occur with it; the only pair that genuinely co-occurs is
  `DEGRADED_DOMINATED` with each of the others, which is where "record all true
  conditions" does its real work.
- **D4 — N=12 is below `n_floor` (30) → any RECOMMENDATION is `indicative_only`
  (deltas-only).** Resolves OQ-B. The run's job is the typed outcome + descriptive
  deltas; a production-grade recommendation needs a larger subset (a named follow-up).
- **D5 — the operator run is K=`k_runs` (5); raising K on `NOT_SEPARABLE` is a named
  follow-up, not a same-spec retry.** Resolves OQ-C. Prevents silent K-inflation to
  manufacture separability within this spec.
- **D6 — G2-over-ceiling routes to a descriptive-only G3** (single pass, no threshold
  tuning), so a predetermined `GATE_CONFOUNDED` never triggers the long expensive
  sweep the protocol exists to forbid, while still capturing the descriptive stats.
- **D7 — close ≠ hold, split by cause.** A SUT-observing outcome (`STOP:SMOKE` / a G3
  label) closes; an environment `BLOCKED` holds the spec and names the fix. The
  boundary is drawn **by cause**, not by which gate stopped: G0 preflight fail,
  fixtures absent, **and** a G1 sub-check-(a) non-completion for an environment reason
  (OOM / resource exhaustion under co-load — the G0-invisible residual, since G0 only
  proves models are *pulled*, not co-resident-loadable) are all `BLOCKED` holds; a run
  that *completed* and then degrade-dominated or gate-false-rejected is a `STOP:SMOKE`
  close. This keeps the F4 fix airtight against a resource failure masquerading as a
  SUT finding.
- **D8 — the gate-ledger is a new pinned artifact** (not the sweep report), carrying
  per-gate verdicts with measured values + run provenance for STOP reproducibility.
- **D9 — operator-run served-model config (this run).**
  `scout_model=hf.co/dstolf/FastContext-1.0-4B-RL-Q8_0-GGUF:latest` (Scout Tier-1 +
  the retained finder-judge A/B baseline). `lm_model` is the dual-consumer (Deep Tier-2
  **and**, since 0018, `verify_method="instruct_model"` → the **verification-gate
  judge** G2 measures) — there is no seam to give Deep and the judge different tags, so
  the one `--deep-model` choice sets both. This is a served-tag selection (config, not
  code — the frozen `Settings` *defaults* stay Qwen3-8B, honoring AC10); the exact tags
  are stamped into the gate-ledger provenance (AC2).
  **OOM finding (D9-a, 2026-07-03).** The first attempt used `lm_model=qwen3-coder:30b`
  (18 GB). Co-resident with Scout (4.3 GB) under `mode=auto` — *plus* the `dspy.RLM`
  Deno/Pyodide sandbox + the 30B KV-cache whenever a case escalates to Deep (frequent
  here, since Scout's Tier-1 often misses on this data) — the working set exceeded
  32 GB (observed **swap 94 % full, ~30 GB paged out**) and the G2 process was killed
  mid-run. This is exactly the residual risk D9 named (G0 proves *pulled*, not
  *co-resident-loadable*); under the real `run_oq2_operator` it is caught and recorded
  as a `BLOCKED` **hold** (AC4/D7), not a SUT finding. **Resolution:** drop the Deep+judge
  tag to `lm_model=qwen3:8b` (5.2 GB) — Scout 4.3 GB + 8B 5.2 GB ≈ **9.5 GB** co-resident,
  well within 32 GB. The permanent "smaller-footprint Deep + a co-residency budget"
  question is a named follow-up.
  **Judge thinking-mode (D9-b, 2026-07-03).** `make_instruct_judge` (0018 SUT) does
  **not** disable model "thinking": the prompt asks for a bare number but nothing sets
  `/no_think` / `think:false` / `enable_thinking=False`, and `_parse_score` is
  `.match`-anchored — so a model that emits a leading `<think>…</think>` would fail the
  parse on **every** call → `ScoreParseError` → the gate degrades and escalates
  everything (a fake `gate_false_escalation ≈ 1.0`). This is a **latent 0018 SUT
  robustness gap**, recorded as a finding for a follow-up judge-hardening spec — 0020
  measures/reports it, does not fix it (measurement-not-construction). It is **not
  biting this run**: an isolated 5-span probe of `qwen3:8b` through the gateway's
  OpenAI-compat path returned **bare numbers** every time (no `<think>`), well
  calibrated (relevant 1.0 / irrelevant 0.0 / partial 0.3 / realistic 0.7), so the G2
  measurement with `qwen3:8b` is thinking-safe. `qwen3:4b-instruct` was rejected as the
  judge: it scored an obvious `__eq__` definition **0.0** (the B2 false-reject
  pathology), i.e. a worse judge than `qwen3:8b`. The earlier >120 s single-call
  timeouts were **model contention + load**, not thinking (hypothesis raised, then
  empirically disproven).

## Out of scope

- Flipping any Settings default (`verify_threshold` / `verify_top_n` /
  `verify_method`) — that is the separate variance-gated follow-up spec a
  `RECOMMENDATION` outcome authorizes.
- Permanent calibration of `gate_false_escalation_ceiling` (replacing the
  provisional 0.20 with a data-driven bar) — seeded by G2's measured rate, decided
  in the follow-up gate-accuracy spec.
- Any SUT change (tiers, gate, escalation matrix, classifier, citation format, judge
  mechanism) — measurement-not-construction; 0018 shipped the judge, this spec only
  measures it.
- Provisioning/curating a larger or harder dataset beyond the existing N=12 subset,
  or raising K past the default — candidate next specs named by a `NOT_SEPARABLE`,
  low-N, or variance-limited outcome.
- Per-span non-conformance abstain, deterministic lexical judge, constrained-decoding
  parse — pre-existing follow-ups, not this run.

## Open questions

- **OQ-A (judge A/B → follow-up boundary).** If G2 shows the finder judge beats
  instruct on false-escalation, this spec **flags** that 0018's judge choice needs
  revisiting and names a follow-up gate-accuracy spec — it does **not** re-decide the
  judge here (this spec measures). Open only in the sense that the *follow-up's* shape
  (swap default judge vs. investigate the instruct judge's failure modes) is decided
  by that spec, informed by the measured A/B.

## Operator-run outcome (2026-07-04) — typed null: DEFERRED

The instrument (unit-verified: 43 new tests, 820 unit pass, ruff clean) was run live
against the served stack + provisioned SWE-bench point subset. The typed outcome is a
**DEFERRED null** — a valid deliverable per the spec (AC11) — and it names the next
spec. What happened, in gate order:

- **G0 preflight — PASS.** Required served tags present (validated twice: with
  `qwen3-coder:30b` and with `qwen3:8b`).
- **G1 smoke (astropy-12907, `mode=auto`) — PASS, with an honest caveat.** Run
  completed, tiers alive (0 % degrade), no gate-false-rejection. But `tier1_correct =
  False`: Scout missed the gold span, the gate correctly *caught* the wrong citation
  (catch_rate 1.0) and escalated to Deep, which also missed. So sub-check (c) is
  **vacuously** satisfied (no correct Tier-1 to reject) and the case is not solved
  end-to-end — a limitation of G1's formal checks, recorded.
- **G2 gate-quality — DEFERRED.** The instruct pass over the 38 point cases completed
  (~3.3 h) with **`correct_tier1_count = 0`** → `gate_false_escalation = null` **by
  definition**: you cannot measure whether a judge false-*rejects* correct citations
  when Scout emits none. The finder-judge A/B and the G3 sweep are therefore **moot**
  (`verify_method` changes the judge, not Scout's citations → `correct_tier1` stays 0
  for both), and were not run.
- **Root cause (verified, not a harness artifact).** Direct Tier-1 spot-checks
  confirmed `expected_spans` load correctly, Scout runs and returns citations, and the
  overlap oracle is right. Scout Tier-1 is genuinely ≈ 0 correct on SWE-bench point
  cases: at best **right-file-wrong-span** (astropy-12907: cited `separable.py:66-102`,
  gold `242-248`), otherwise empty or wrong-file.
- **The fix is not a model swap (verified).** A direct A/B with `qwen3:4b-instruct` as
  the Scout finder (in place of FastContext-RL-Q8) also got **0/3**, same pattern — and
  on astropy-12907 **both models produced the identical wrong span** (`66-102`),
  evidence this is **span-level localization / task difficulty**, not a model-quality
  gap. (A generic model through the FastContext agentic adapter is also slow,
  13–28 s/call — the wrong tool for that adapter.)

**Environment findings (recorded, D9-a / D9-b):** `qwen3-coder:30b` as Deep+judge
**OOM'd** the 32 GB host (swap 94 % full) — the D9 co-residency risk realized, an
AC4/D7 `BLOCKED`-hold cause; resolved by dropping to `qwen3:8b` (~9.5 GB). And
`make_instruct_judge` does **not** defend against model "thinking" (anchored
`_parse_score` would fail on a `<think>` block) — a latent 0018 SUT robustness gap;
not biting here (`qwen3:8b` empirically returns bare, well-calibrated numbers).

**Named follow-up:** **Scout Tier-1 span-level localization on SWE-bench** (the
right-file-wrong-span pattern from long issue-text queries; file/proximity vs exact-span
scoring; finder capability) — **not** a gate-accuracy, threshold-calibration, or
finder-model-swap spec. Secondary follow-ups: the judge thinking-defense hardening
(D9-b), a smaller-footprint Deep + co-residency budget (D9-a), and reconciling the
`escalation_rate: 0.0` vs 3.3 h-runtime accounting anomaly before trusting secondary
metrics.

**Scope honesty:** mechanism + instrument shipped and unit-verified; G0/G1 validated
live; **OQ2 gate calibration remains blocked upstream** (Scout locate accuracy), which
is itself the honest, typed deliverable.
