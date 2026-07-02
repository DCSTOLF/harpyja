---
id: "0019"
title: "OQ2 re-run — complete, prove the gate, then calibrate"
status: closed
created: 2026-07-01
authors: [claude]
packages: [harpyja/eval, harpyja/orchestrator]
related-specs: ["0010", "0011", "0014", "0015", "0016", "0017", "0018"]
---

# Spec 0019 — OQ2 re-run — complete, prove the gate, then calibrate

## Why

Spec 0015 (the OQ2 live run) never completed. It wedged on **B3** and, in doing so,
surfaced **B1/B2/B3** — each now fixed:

- **0016 (B1)** — `scout_model`/`lm_model` flipped to served Ollama tags + `--scout-model`/`--deep-model` CLI flags (an unserved default 404'd every Scout call).
- **0017 (B3)** — the Model Gateway's outbound `urlopen` gained a finite timeout (an un-timed socket wedged the whole run — *why no run ever finished*).
- **0018 (B2)** — an in-distribution instruct-model judge over `lm_model` + a strict, non-fabricating score parser replaced the OOD finder-as-scorer that false-rejected **correct** citations.

The 0015 stack is now unblocked. But two things remain **unproven**, and this spec
exists to prove them on real data:

1. **0018 fixed the judging MECHANISM and explicitly DEFERRED proving accuracy.**
   astropy-12907 passing end-to-end was disclaimed as plumbing, not demonstrated —
   the changelog says "B2 *mechanism* fixed," never "B2 closed."
2. **`verify_threshold=0.6` is meaningless.** It was calibrated against the OLD
   finder-model score distribution; the new instruct judge produces a different
   distribution, so `0.6` is unvalidated-from-scratch, not a starting default.

So this spec must prove **three things 0015 couldn't reach, IN ORDER** — they are
**sequential dependencies, not parallel goals**.

Ref: 0010 (sweep + N_FLOOR + variance-gated recommend), 0011/0014 (degrade
visibility + the "every floor reports its rate" convention), 0015 (failed run +
`live-run-findings.md`), 0016/0017/0018 (the three blocker fixes); the Wave-5 gate
spec (OQ1 backend decision, reopened by 0018).

### Invariants

**INVARIANT — measurement, not construction.** This spec runs the EXISTING
instrument with the shipped 0016–0018 fixes. There is **no behavior change** to
tiers/gate/matrix/judge. Any code change is a **defect surfaced by the run**,
recorded as a deviation with its regression test (AC8) — never a feature added here.

**INVARIANT — three sequential gates, each willing to stop-and-report.** This spec
does NOT assume readiness at any stage. If gate **G1** fails, that is a **FINDING**
and G2/G3 are not attempted; likewise **G2 → G3**. A clean OQ2 table is the
**success** outcome, not the **required** one.

| Gate | Proves | First achievable |
| --- | --- | --- |
| **G1** | a run COMPLETES end-to-end | never before 0017 |
| **G2** | the B2 fix DEMONSTRABLY works (astropy-12907 + false-escalation cases pass; gate false-escalation rate measured) — not merely wired | never before 0018 |
| **G3** | OQ2 CALIBRATES: `verify_threshold` tuned over the NEW instruct-judge distribution (`0.6` treated as unvalidated-from-scratch) | this spec |

**INVARIANT — reliability-gated reporting.** The existing `N_FLOOR` +
`degraded_dominated` (scout∪deep union) guards hold unchanged. A
degraded-dominated sweep **withholds OQ2** and reports a finding rather than
publishing a number measured mostly on floored runs.

## What

A three-stage, operator-run measurement flow over the existing eval harness. Each
stage gates the next; each is willing to stop and report a finding.

- **PREFLIGHT (before any repo clone).** Assert all three served models are pulled
  on the run host — `scout_model` (FastContext-Q8), `lm_model` (Qwen3-8B, the
  judge), deep-model — or fail loudly at setup. This is B1's 404 re-surfacing as a
  mid-run failure if skipped; doctor-style, **not** mid-run discovery. Two honesty
  constraints (D4): **(a)** the presence probe goes through the **existing
  sanctioned local-only seam** — `gateway.assert_local` on the resolved loopback
  endpoint **before** the `/api/tags` membership read — so preflight introduces
  **no second outbound path** (the air-gap stays enforced in the one place). **(b)**
  Preflight proves each model is **pulled**, NOT that Scout + Deep + judge are
  **co-resident-loadable without OOM**; `mode=auto` co-loads the tiers and the
  memory trail warns Q8 OOMs `auto` on 16 GB (32 GB "resolved" it, unproven at
  sweep scale). So preflight makes the no-false-capability claim it can back —
  "pulled" — and explicitly names OOM as a **residual mid-run risk** G1 exists to
  catch cheaply, never claiming co-residence it did not test.
- **G1 SMOKE (cheap, before the expensive sweep).** Run astropy-12907 ALONE,
  end-to-end, `mode=auto` — the single case B2 was diagnosed on. Exercises the full
  chain (served Scout + finite timeout + instruct judge + strict parser). If it
  doesn't pass clean, the full sweep won't either — **stop here.** This is the
  "cheap interpretable check gating the expensive run" lesson from 0015's 2.5-h wedge.
- **G2 GATE-QUALITY.** On the point subset, measure gate **false-escalation rate**
  (correct Scout citation rejected → escalated) and **catch rate** (wrong Scout
  citation caught → escalated) as first-class metrics. Correctness for **both** is
  the **single existing span-overlap oracle** (spec 0009) that already backs
  accuracy — no second oracle, no ad-hoc "correct" definition — with explicit
  denominators and an explicit `null`-paired-with-a-zero-count on a zero
  denominator (spec 0011 convention). Use 0018's **RETAINED** `scout_model` judge
  path as the A/B baseline: `instruct_model` vs `finder_model` false-escalation,
  side by side on real data — the empirical vindication (or not) of 0018's
  OQ1-backend reopening. **G2's typed pass condition (D2):** astropy-12907's correct
  citation passes AND the `instruct_model` false-escalation rate is `≤ 0.20`
  (`gate_false_escalation_ceiling`, eval-only, provisional — a named bar, not a
  tuned prior). If the ceiling is exceeded, **G2 does not pass**: G3 is not run for
  a clean OQ2 — it emits the `gate-confounded` typed null (below), the honest
  outcome the whole flow is built to produce.
- **G3 SWEEP.** `verify_threshold` × `verify_top_n` over the full 12-repo subset,
  `K` runs/point, mean+spread; **variance-gated recommend**
  (`mean(A) − mean(B) > spread(B)`) → a recommended `(threshold, top_n)` OR a
  **typed null** — one of `not-separable`, `degraded-dominated`, or
  **`gate-confounded`** (a DECIDED outcome, D2: "judge false-rejects correct
  citations at rate X > ceiling — a threshold tuned over this distribution would
  calibrate a still-broken gate"). The `verify_threshold` grid is **coarse-first
  over a range DERIVED from the G1/G2 instruct-judge score distribution**, not the
  old `[…,0.6,…]` prior (D1) — `0.6` carries no privileged position. Report
  accuracy, escalation rate, scout∪deep degrade rates, Tier-0-alone accuracy, and
  the `fc_citation_*` distribution.
- **NO Settings default is flipped here** — the variance-gated flip is a follow-up
  spec citing this evidence. The A/B (AC4) and side-by-side reporting are **config
  overrides + ADDITIVE report fields** (appended last-with-defaults, `SCHEMA_VERSION`
  bumped): the measurement-not-construction invariant freezes the **SUT**
  (tiers/gate/matrix/judge), not the harness/report schema, which stays additively
  extensible (spec 0010 convention).

## Acceptance criteria

`[integration]` = operator-run, `@pytest.mark.integration`, **skip-not-fail**;
`[unit]` = fakes.

1. **[integration] Preflight — models present or loud setup failure.** Preflight
   asserts the three served models (`scout_model`, `lm_model`/judge, deep-model)
   are present **before** provisioning; a missing model → a loud setup failure, not
   a mid-run 404. The presence probe runs **behind `gateway.assert_local` on the
   loopback endpoint** (no second outbound path) and claims only **"pulled"**, not
   co-resident-loadable (OOM is a named residual risk, caught by G1).
2. **[unit] Preflight assertion logic.** The three-model membership check is
   unit-tested against a **fake `/api/tags` payload**: all-three-present → pass;
   any one absent → a loud typed failure naming the missing model (mirrors the 0016
   AC7 positive-membership pattern; `assert_local`-first is exercised on a fake
   resolver — never a live call).
3. **[integration] G1 — end-to-end completion, sweep-gated.** astropy-12907 runs
   end-to-end `mode=auto` to completion; the pass/fail is recorded. G2 and the full
   sweep are **NOT** attempted if G1 fails (a recorded G1 failure is an accepted
   terminal outcome).
4. **[integration] G2 — gate quality is first-class, B2 deferral discharged.** Gate
   false-escalation rate + catch rate are first-class reported metrics scored by
   the **single span-overlap oracle** (AC5); astropy-12907's correct citation is
   **no longer false-rejected** (the B2 deferral, now proven on real data). G2's
   typed pass/fail is recorded: pass requires astropy-12907 correct AND
   `instruct_model` false-escalation `≤ gate_false_escalation_ceiling` (0.20).
5. **[unit] One oracle, explicit denominators.** Gate false-escalation and catch
   rate reuse the **same** span-overlap oracle as accuracy (no second correctness
   definition); each rate carries an explicit denominator and serializes an
   explicit `null` paired with a **zero count** when its denominator is zero (never
   a silent `0.0`).
6. **[integration] G2 A/B — judge comparison.** `instruct_model` vs `scout_model`
   judge false-escalation is measured side-by-side on the subset via config
   override + **additive** report fields (SUT unchanged; schema extended
   last-with-defaults, `SCHEMA_VERSION` bumped).
7. **[integration] G3 — sweep completes at scale, only if G1∧G2 pass.** Conditional
   on G1 passing AND G2 passing (AC4): the full 12-repo sweep completes (0017 holds
   at scale — no wedge); `N ≥ N_FLOOR`; a trade-off table with mean+spread per grid
   point is produced over the **G1/G2-derived** `verify_threshold` range (`0.6` not
   assumed). A run **stopped** at G1 or G2 satisfies this AC by recording the
   stop-reason finding and **not** producing the table — a stopped run is an
   accepted outcome, never a failure to meet AC7.
8. **[integration] G3 — reliability gate enforced.** scout∪deep degrade-rate is
   recorded; a `degraded_dominated` sweep → OQ2 **withheld** as a finding (the
   reliability gate is enforced, not bypassed).
9. **[integration] OQ2 — recommended or typed-null, never forced.** OQ2 is emitted
   via the variance-gated recommender OR an explicit typed null (`not-separable` /
   `degraded-dominated` / `gate-confounded`) — never a forced pick; `verify_threshold`
   is treated as unvalidated-from-scratch (`0.6` is not assumed as a starting
   default). If G2 failed its ceiling, the emitted result is the `gate-confounded`
   typed null carrying the measured false-escalation rate.
10. **[unit] Any defect surfaced at scale gets a regression test.** Any defect the
    run surfaces (an `int | None` consumer, a schema sink, model-default drift) gets
    a unit regression test **before** the run is declared complete, where "complete"
    means: a schema-valid G3 report written to the out-of-repo output dir carrying
    either a recommended `(threshold, top_n)` or a typed null — **or** a recorded
    G1/G2 stop-finding artifact.

## Out of scope

- **Flipping `verify_threshold` / judge Settings defaults** — a variance-gated
  follow-up spec, citing this run's evidence.
- **FIXING any residual gate inaccuracy G2 surfaces** — measure, don't fix; a fix
  is a further gate spec.
- `ContextWindowExceededError` handling.
- Q-model provisioning automation.
- Wave-2.1 substring/fuzzy matching.

## Decisions

Resolved during review (codex + claude-p); each was load-bearing enough that
leaving it open would have blocked `/spec:plan` or let the spec contradict itself.

- **D1 — `K` and the grid are committed, coarse-first, range-derived.** `K = 5`
  runs/point — the shipped `EvalConfig.k_runs` default, unchanged (the
  variance-gated recommender already reports mean+spread over `K` via `pstdev`).
  The `verify_threshold` grid is **coarse-first** over a range **derived from the
  observed instruct-judge score distribution** gathered as a G1/G2 by-product (NOT
  the old `0.6`-anchored grid — centering on `0.6` is question-begging), then
  optionally refined in the promising region; `verify_top_n` sweeps its small
  existing set. **Reconciliation with the shipped recommender:** `recommend.rank_sweep`
  frames its decision as *validate-or-flip the incumbent* `(0.6, 3)` (the current
  `Settings` default). So the derived grid **must still include the `(0.6, 3)`
  point** — otherwise `_find_incumbent` returns `None` and the run cannot answer
  "is the current default justified?". `0.6` therefore gets **no *centering*
  privilege** in the grid range (D-per-distribution) but **remains measured** as the
  incumbent — the two are consistent: the spec forbids assuming `0.6` is good, not
  measuring it. Concrete coarse grid + any refinement pass are named in `plan.md`;
  the method (range-from-distribution, include-incumbent, coarse-then-refine) is
  fixed here so wall-clock on the 32 GB M1 Max is bounded and AC7 is reachable.
- **D2 — `gate-confounded` is a DECIDED G3 outcome, not an open question.** When G2's
  `instruct_model` false-escalation exceeds `gate_false_escalation_ceiling` (0.20),
  G3 emits the `gate-confounded` typed null carrying the measured rate instead of a
  clean OQ2. An honest confound flag beats a threshold calibrated over a
  still-broken judge (0018 fixed the mechanism, not necessarily the accuracy). This
  removes the earlier contradiction where the body treated `gate-confounded` as live
  while an open question still asked whether to emit it. **These are NEW eval-harness
  additions, permitted by the measurement-not-construction invariant** (which freezes
  the SUT — tiers/gate/matrix/judge — not the harness): a new
  `EvalConfig.gate_false_escalation_ceiling = 0.20` knob, a new `gate-confounded`
  branch on the sweep outcome (`recommend.py`, which today emits only
  incumbent-validated / flip / not-cleared), and additive report fields
  (`SCHEMA_VERSION` bumped from `0013/1`). All are **unit-tested with fakes** — none
  touches the SUT.
- **D3 — `mode=fast` line is deferred (recorded).** No `mode=fast` (Scout-only)
  apples-to-apples line vs the FastContext paper's Table 2 in THIS run — it doubles
  the model-backed wall-clock and is not on the G1→G2→G3 critical path. Deferred to
  a follow-up, noted so the omission is a choice, not an oversight.
- **D4 — preflight is seam-routed and honesty-scoped.** The model-presence probe
  runs behind `gateway.assert_local` (no second outbound path) and claims only
  "pulled", explicitly naming co-resident OOM as a residual mid-run risk that G1
  catches cheaply (see PREFLIGHT + AC1).

## Open questions

1. **Refinement-pass budget.** After the coarse grid (D1), is a refinement pass
   around the promising `(threshold, top_n)` region affordable within the run's
   wall-clock, or is the coarse recommendation reported as-is with a
   "coarse-grid-only" caveat? Decide from the measured coarse-sweep duration — a
   runtime observation, not a pre-commit.
2. **Co-residence load-probe depth.** D4 keeps preflight at "pulled" and lets G1
   surface OOM. If G1 OOMs, is a lightweight co-resident load-probe worth adding to
   preflight in a follow-up (fail-fast before the smoke), or is G1 the right place
   to catch it? Left open pending whether OOM actually recurs at 32 GB.
