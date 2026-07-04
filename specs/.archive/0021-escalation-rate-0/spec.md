---
id: "0021"
title: "escalation_rate=0"
status: closed
created: 2026-07-04
authors: [claude]
packages: [harpyja/eval]
related-specs: ["0008", "0011", "0014", "0019", "0020"]
---

# Spec 0021 — escalation_rate=0

## Why

The G2 instruct pass in spec 0020 recorded `escalation_rate = 0.0` but took **3.3h**
(11846.9s). Taken at face value the two cannot both be true: a 3.3h pass implies heavy
activity, but `escalation_rate = 0` says Deep / Tier-2 never ran. The load-bearing DEFERRED
verdict is safe regardless — `correct_tier1_count = 0` is a direct count, independent of this
contradiction — but the **secondary** metrics from that pass (`span_hit_rate_primary = 0.2`,
`gate_catch_rate`, `wrong_tier1_count = 5`) cannot be trusted until the contradiction is
resolved, and the next spec (Scout Tier-1 span-level localization) must not build on suspect
numbers.

This is a **metric-integrity diagnostic**, not a feature: attribute the 3.3h, determine
whether `escalation_rate = 0` is a **bug** or **correct**, and — if correct — explain what
happened to the 5 wrong Tier-1 citations the gate saw.

**The contradiction's teeth (must be explained, not glossed).** `mode=auto` routes
Scout → gate → escalate. `wrong_tier1_count = 5` means the gate *saw* 5 wrong citations. If it
rejected them it should have escalated (Deep ran → `escalation_rate > 0`). If
`escalation_rate = 0` is correct, then EITHER the gate **accepted** wrong citations (a gate
false-**acceptance** finding — the mirror image of G2's false-escalation target) OR empty/wrong
Tier-1 does not escalate by design. Whichever it is, name it.

**Leading hypothesis, already grounded (OQ1 first, per the source-check directive).**
`escalation_rate` is **derived**, not independently counted: `metrics.escalation_rate`
(`harpyja/eval/metrics.py:129`) is `mean(2 in o.tiers_run)` via `_escalated` (`:126`) — there is
no separate escalation counter that can disagree with `tiers_run`. That collapses most of the
investigation toward **CORRECT_NO_ESCALATION** (a true count; the 3.3h went to Scout's own
FastContext exploration loops, not Deep). This spec must *verify* that — confirm the count is
faithful, attribute the wall-clock, and settle the 5-wrong-citation fate — not assume it.

## What

Resolve three questions from the existing 0020 partial dump + per-case trajectory/timing +
code reading, and **at most a 1–2 case instrumented micro-run**. A full re-run of the 3.3h pass
is out of scope and defeats the purpose.

**Feasibility precondition (resolve BEFORE planning — review C1).** The "resolve from the
existing dump" method is not guaranteed available: at author time `eval_work/reports/oq2_fast/`
and `oq2_incumbent/` are **empty**, `eval_work/` is gitignored / machine-local, and the quoted
secondaries (`span_hit_rate_primary=0.2`, `wrong_tier1_count=5`) are recorded **nowhere** in the
committed `specs/.archive/0020-oq2/` — they survive only in the operator session transcript.
The first planning step MUST path the actual per-case dump on disk. **If it is absent, AC3
degrades to an explicitly-labeled ESTIMATE** (per-tier proportions from the ≤2-case micro-run ×
38 cases) — never a fabricated "recorded 3.3h attribution." Persisted timing is also only
case-level `latency_ms` (`harpyja/eval/runner.py:190,213`), **not** the per-tier
(Scout / judge / Deep) granularity AC3 wants; that granularity exists only in the micro-run's
new instrumentation. The total anchors on the recorded wall-clock; the split is a labeled
sample estimate.

1. **TIME ATTRIBUTION** — where did 3.3h go? Attribute across Scout / FastContext exploration
   loops (`max_turns` × 38 cases, each turn a 4B call), judge calls, Deep / RLM, and
   provisioning. Likely sink: Scout's own exploration, not Deep.
2. **ESCALATION ACCOUNTING** — is `escalation_rate = 0` a counter bug (Deep ran but was not
   counted — check `tiers_run` per case for any Tier-2 vs the `escalation_rate` denominator /
   reset logic) or correct (Deep genuinely never ran)? Start from the confirmed fact that the
   metric is derived from `tiers_run`.
3. **WRONG-CITATION FATE** — for the 5 wrong Tier-1 cases, did the gate **accept** them
   (false-acceptance), was there **no escalation path** for them, or did the gate reject them
   but **Deep was degraded / unavailable** (OOM) so escalation was suppressed? Reconcile with
   the 33 empty cases (does honest-empty Tier-1 escalate, per the ladder in
   `harpyja/orchestrator/matrix.py` `plan_ladder`?). Check per-case notes for
   `deep-degraded:<cause>` (`harpyja/eval/runner.py:74`) — 0020 OOM'd `qwen3-coder:30b` on this
   host, so degradation-suppressed escalation is a live outcome, not hypothetical.

**Invariant — diagnose first, fix only if a bug is found.** The primary deliverable is a
RECORDED FINDING with a typed conclusion, not a feature. A SUT change is permitted ONLY if a
genuine accounting bug is found, as a harness / metric fix (measurement-not-construction) with
a regression test. If `escalation_rate = 0` is CORRECT, the deliverable is the
time-attribution + metric-trust verdict, **no code change**.

**Invariant — cheap; do NOT re-run the 3.3h pass.** Resolve from the existing dump + timing
data + code reading, plus at most a 1–2 case instrumented micro-run.

## Acceptance criteria

`[unit]` = fakes / injected fixtures; `[integration]` = micro-run, ≤2 cases, skip-not-fail.

1. `[unit]` **`tiers_run` ⇄ `escalation_rate` coupling** asserted on fixtures: a case
   reaching Tier-2 increments the escalation numerator; a case terminating at Tier-1 does not —
   pins the derived metric's correctness either way (it is `mean(2 in tiers_run)`). The **novel**
   assertion is the coupling; extend / point at existing `harpyja/eval/test_metrics.py` coverage
   rather than duplicating a plain `escalation_rate` test (review M3).
2. `[unit]` **Escalation-trigger logic covered**, with expectations **derived from
   `harpyja/orchestrator/matrix.py` `plan_ladder`** (the single-source-of-truth table the test
   reads — not a duplicated rule): wrong Tier-1 (gate reject, Deep available) → escalates;
   honest-empty Tier-1 → the ladder's asserted behavior; gate-accept → no escalation; gate
   reject but Deep degraded/unavailable → escalation **suppressed** (honest degradation). Makes
   the wrong-citation fate deterministic, not inferred.
3. `[integration]` **≤2-case instrumented micro-run** reproduces the `escalation_rate` value
   with per-tier timing, attributing wall-clock to Scout vs judge vs Deep. `skip-not-fail`
   (gated on served models + fixtures env, as with the 0019/0020 live tests). **Honesty:** the
   recorded wall-clock anchors the total; the per-tier split is a **labeled sample estimate**
   from this micro-run (the per-tier granularity does not exist in any persisted 0020 dump — see
   the feasibility precondition). If the 0020 per-case dump is located on disk it corroborates;
   if absent, AC3 stands on the micro-run estimate alone, labeled as such.
4. `[doc]` **Recorded typed finding on TWO orthogonal axes** (a single flat enum is not MECE —
   review C2 — because the wrong-citation fate is independent of whether the *count* was
   correct). Record **one value per axis**:
   - **accounting** ∈ { `ACCOUNTING_BUG` (Deep ran but `escalation_rate` mis-counted → fixed +
     regression test; secondary metrics re-derived) | `CORRECT_NO_ESCALATION` (the derived
     count is faithful; Deep genuinely did not run) }.
   - **wrong_citation_fate** ∈ { `GATE_FALSE_ACCEPTANCE` (gate accepted wrong Tier-1 — a new
     gate-quality lead, distinct from G2's false-escalation target) | `NO_ESCALATION_PATH`
     (empty/wrong Tier-1 does not escalate by design, per `plan_ladder`) |
     `DEEP_DEGRADED_OR_UNAVAILABLE` (gate rejected but Deep was OOM/degraded, so escalation was
     honestly suppressed — `deep-degraded:<cause>`) | `NOT_APPLICABLE` }.
   The two axes together name the 5-wrong-citation fate AND the 3.3h attribution without forcing
   a false either/or.
5. `[doc]` **Metric-trust verdict**: which 0020 secondary numbers
   (`span_hit_rate_primary`, `catch_rate`, `wrong_tier1_count`, `empty` counts) are trustworthy
   for the next spec, and which are contaminated by the finding. This is what actually unblocks
   the Scout-accuracy work.

## Out of scope

- Re-running the full 3.3h pass (explicitly forbidden — defeats the diagnostic's purpose).
- FIXING Scout Tier-1 span-level accuracy (that is the next spec).
- FIXING a gate false-acceptance if surfaced — it names a follow-up spec, not this one.
- OQ2 calibration.
- Changing any tier / gate behavior beyond a *proven* accounting-counter fix.
- **Modifying `harpyja/orchestrator`.** It is **read-only reference** here (the frozen SUT and
  the `plan_ladder` source of truth AC2 reads). Any proven accounting fix lands in the derived
  metric layer under `harpyja/eval/` (`metrics.py` / `runner.py`), not in the tiers/gate/matrix —
  hence `packages: [harpyja/eval]` (review M1).

## Open questions

1. Does the metric come from `tiers_run` (derived) or a separate escalation counter
   (independently incremented)? **Resolved at author time: derived** —
   `metrics.escalation_rate` = `mean(2 in o.tiers_run)` (`harpyja/eval/metrics.py:126,129`),
   no independent counter. Two sources that could disagree would have been the likely bug locus;
   there is only one, which pushes toward `accounting = CORRECT_NO_ESCALATION`. Confirm no
   aliasing / reset / denominator quirk before finalizing.
2. **Does the 0020 per-case dump still exist on disk?** (Review C1 precondition, resolve BEFORE
   planning.) Author check: `eval_work/reports/oq2_fast/` + `oq2_incumbent/` are **empty** and
   the quoted secondaries are absent from the committed archive. If the dump is truly gone, AC3
   is a **labeled estimate** from the micro-run, not a recovered attribution — do not let the
   spec read as if a recorded 3.3h split exists.
3. If `wrong_citation_fate = GATE_FALSE_ACCEPTANCE`, does it change the DEFERRED verdict? Lean
   **no** — `correct_tier1_count = 0` is independent — but a gate accepting wrong citations is a
   material separate finding worth its own spec.
