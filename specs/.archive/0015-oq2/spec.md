---
id: "0015"
title: "OQ2"
status: closed
outcome: failed-run
closed-note: "OQ2 run could not complete (B1/B2/B3); implementation reverted, only B0 provision fix salvaged. See changelog.md + live-run-findings.md."
created: 2026-06-30
authors: [claude]
packages: [harpyja/eval, harpyja/orchestrator, harpyja/deep]
related-specs: ["0010", "0011", "0012", "0014"]
---

# Spec 0015 — OQ2

## Why

Every blocker that made the full sweep premature is now cleared — Scout fires
(0011), recovers hallucinated path prefixes (0012), Deep maps `AdapterParseError`
to a typed degrade instead of crashing the run (0014), the box has the RAM (32 GB
M1 Max), and degrade-visibility (0011/0014) means an all-floor run cannot
masquerade as success. This is the measurement the whole eval arc (0010→0014) has
been building toward: produce a **MEASURED** OQ2 recommendation, not an unblocked
one. The sweep also naturally yields the data to characterize the still-open gate
false-escalation lead (requests-1766) across 12 repos — far better evidence than
the single observed case — so it's folded in as a first-class measured output
rather than a prerequisite.

Ref: 0010 (eval harness + sweep + N_FLOOR), 0011 (degrade-rate first-class), 0012
(suffix recovery), 0014 (Deep typed-degrade + the "every floor reports its rate"
convention); session leads: 12-repo sweep, gate false-escalation.

## What

**INVARIANT (measurement, not construction):** runs the EXISTING instrument across
the full set. No behavior change to tiers/gate/matrix/classifier. Deliverables are a
recorded OQ2 recommendation + a gate-quality finding. No Settings default is flipped
here (that's the variance-gated follow-up). Any code change is a *surfaced defect*,
recorded as a deviation with its regression test — not new capability.

**INVARIANT (reliability-gated reporting):** results obey the existing N_FLOOR and
`degraded_dominated` guards. If degrade-rate (scout∪deep) crosses the threshold, OQ2
numbers are marked unreliable and the recommendation withheld — a degraded-dominated
sweep produces a FINDING, not a calibration. The `degraded_dominated` guard composes
**per-grid-point** inside the recommender, not only globally: because higher
`verify_threshold` escalates to Deep more often (more degrade exposure), a
degrade-heavy point must not be allowed to lose to a clean point on a *degrade
artifact* rather than worse tuning — a point whose own degrade rate is dominated is
dropped from the comparison, not silently ranked.

**Confound threshold (quantified, not discretionary).** "Material" gate
false-escalation gets a numeric threshold the same way `degraded_dominated` does:
`GATE_CONFOUND_THRESHOLD` (an eval-only knob, default proposed in plan). When the
gate false-escalation rate is **reliable** (its own denominator ≥ its sample floor,
see AC4) AND exceeds that threshold, OQ2 is reported as `gate_quality_confounded` —
the "right" `(threshold, top_n)` would be measuring gate dysfunction, not gate
tuning. An under-floor gate rate cannot trip the confound flag (no firing on noise).

**Air-gap boundary (provisioning vs. measurement).** Provisioning the 12-repo subset
is a **dev-time / staged** fixture step that clones target repos over the network —
this is **outside** the runtime air-gap boundary, consistent with the existing
SWE-bench / per-case worktree driver. It is **not** runtime egress. The measured
`run` / `sweep` phase itself remains **offline**: model traffic stays on the
loopback Model Gateway and the run asserts no non-loopback egress.

Scope:

- Provision the full 12-repo point subset (staged dev-time clones, per above; uses
  the per-case worktree driver). **Pin subset identity + revs** — the exact 12 repos
  at the exact case commits — so the measurement is reproducible, not just the
  per-repo case counts. Run live `mode=auto` with the K-per-point variance
  discipline from 0010's sweep.
- Sweep `verify_threshold × verify_top_n`; per grid point report accuracy,
  escalation rate, gate-fire count, Tier-0-alone accuracy, scout/deep degrade rates,
  `fc_citation_*` distribution, and mean+spread across K runs.
- Gate quality (folds in the false-escalation lead): per case, when Scout produced a
  CORRECT citation but the gate rejected it and escalated, count it as a
  false-escalation. **Correctness is the existing `_any_primary_overlap` oracle —
  the same one that defines accuracy — reused, never redefined** (the harness
  already records pre-gate Scout spans on escalated cases at `runner.py:182-184` and
  scores them via that oracle; `gate_false_escalation()` already exists). Report gate
  false-escalation rate and gate catch rate as first-class metrics — the gate can
  reject-correct or accept-wrong, and both must be visible.
- OQ2 recommendation via the existing variance-gated recommend
  (`mean(A)−mean(B) > spread(B)`), lexicographic scorer; emit the trade-off table +
  recommended `(verify_threshold, verify_top_n)` OR a single typed null result from
  the stable enum (see AC5).

## Acceptance criteria

`[integration]` = operator-run / `@pytest.mark.integration`, skip-not-fail;
`[unit]` = fakes.

1. **[integration]** Full 12-repo subset provisions + runs `mode=auto` to completion
   (no crash; 0014's Deep fix holds at scale). The report pins **subset identity +
   revs** (the exact 12 repos at the exact case commits) AND per-repo case counts, so
   the run is reproducible. The report also records that provisioning was staged
   dev-time (network clone) and that the measured run asserted no non-loopback
   egress.
2. **[integration]** Sweep produces the `threshold × top_n` trade-off table with
   mean+spread over K runs per point; N ≥ N_FLOOR so results aren't indicative-only.
   The report records the selected grid, K, N, N_FLOOR, and the `degraded_dominated`
   / `GATE_CONFOUND_THRESHOLD` knobs in effect.
3. **[integration]** scout∪deep degrade-rate recorded; if `degraded_dominated`, OQ2
   is withheld and the run reported as a finding (reliability gate enforced, not
   bypassed). The guard composes **per-grid-point** in the recommender (a point whose
   own degrade rate is dominated is dropped from the comparison), not only as a
   single global gate.
4. **[unit + integration]** Gate false-escalation rate AND gate catch rate are
   first-class reported metrics, each with a **pinned numerator/denominator contract
   matching the existing `metrics.py` definitions** (this is measurement of the
   instrument as built, not a redefinition):
   - "correct" / "wrong" is the **existing `_any_primary_overlap` oracle**, reused —
     a `[unit]` test asserts the reuse (no second correctness definition).
   - **`gate_false_escalation`** (`metrics.py::gate_false_escalation`): over **point
     cases where Scout is oracle-correct** (the denominator — *independent of the
     gate outcome*), the **numerator** is the subset that escalated to Tier-2.
     Denominator and numerator are **distinct** (the denominator must NOT bundle the
     escalate condition, or the rate is tautologically 1.0). Returns
     `(rate|None, false_escalated, correct_total)`.
   - **`gate_catch_rate`** (`metrics.py::gate_catch_rate`): over **point cases where
     Scout is oracle-WRONG** (the denominator), the **numerator** is the subset that
     escalated (correctly caught). Returns `(rate|None, caught, wrong_total)`.
   - A **zero denominator is an explicit null-with-count** for *both* rates (the
     `None`-with-zero-counts the functions already return), never implicit/omitted.
   - The false-escalation rate **self-flags `indicative_only`** below its own sample
     floor (`GATE_RATE_N_FLOOR` on `correct_total`), exactly as AC2 does for OQ2
     numbers, so a tail-sample rate cannot fire or suppress the AC7 confound flag on
     noise.
5. **[unit + integration]** The OQ2 output is a **single stable machine-readable
   enum** with exactly one `reason` when no recommendation is emitted:
   `recommendation | not_separable | under_n_floor | degraded_dominated |
   gate_quality_confounded`. A `[unit]` test pins the enum. The variance-gated
   recommender emits `recommendation` only when a point separates above noise AND is
   not under-floor, degraded-dominated, or gate-confounded; otherwise it emits the
   matching typed null — **never a forced pick**. `gate_quality_confounded` fires per
   the quantified `GATE_CONFOUND_THRESHOLD` (reliable-and-over-threshold only). When
   **multiple** null conditions co-hold, the emitted `reason` follows a **predeclared
   deterministic precedence** so two runs (and any review-hook) cannot disagree:
   `under_n_floor → degraded_dominated → gate_quality_confounded → not_separable`
   (most-fundamental-unreliability first). A `[unit]` test pins this precedence on a
   multiply-degenerate fixture.
6. **[integration]** Tier-0-alone accuracy re-measured at scale (the
   load-bearing-ladder number) and `fc_citation_*` shape distribution recorded across
   all 12 repos.
7. **[doc]** Recommendation + gate-quality finding recorded in changelog/history with
   the evidence; if the gate false-escalation rate is reliable and over
   `GATE_CONFOUND_THRESHOLD`, the recommendation is the `gate_quality_confounded`
   null result and the doc flags that OQ2 calibration is confounded until gate
   quality is addressed.
8. **[unit]** Any defect surfaced at scale (new `int|None` consumer, schema sink,
   etc.) gets a regression test before the run is declared complete.

The load-bearing ACs are **4 and 5**. AC4 makes gate quality measurable so the
false-escalation lead resolves as data, not anecdote; AC5 forces an honest output —
a typed null result if the data won't support a clean pick — which is the discipline
that's kept this project honest at every prior measurement (N-floor,
degraded-dominated, indicative-only).

## Out of scope

- Flipping Settings defaults (variance-gated follow-up).
- FIXING gate false-escalation (this MEASURES it; a fix is a separate gate-quality
  spec).
- Q8 `scout_model` default-flip.
- `ContextWindowExceededError` handling.
- Wave-2.1 substring/fuzzy.

## Decisions (resolved during review)

- **D1 — gate-confound reporting (was OQ2): DECIDED.** If the gate false-escalation
  rate is *reliable* (denominator ≥ `GATE_RATE_N_FLOOR`) and exceeds
  `GATE_CONFOUND_THRESHOLD`, OQ2 is reported as the `gate_quality_confounded` null
  result rather than a clean recommendation — an honest confound flag beats a
  calibration tuned over a misbehaving gate. Threshold value is set in the plan; the
  mechanism is fixed here (AC5/AC7, the quantified confound threshold above).

## Open questions

1. **(resolve-in-plan, MANDATORY)** K (runs per grid point) and the
   `threshold × top_n` grid resolution vs total wall-clock on the M1 Max. Because the
   recommender is variance-gated, **K is part of the evidence standard, not a runtime
   detail** — it must be fixed before implementation. A staged coarse→refine grid is
   acceptable ONLY with a **predeclared refinement/stopping rule** (so the operator
   cannot tune the search after seeing the data). The plan must specify either a
   concrete grid + K, or the two-stage protocol with its predeclared rules.
2. **(deferrable, additive)** `mode=fast` (Scout-only) line alongside auto for the
   apples-to-apples vs FastContext Table 2 — coupled to OQ1's wall-clock budget; safe
   to defer without blocking.

The single biggest risk to the sweep's validity is the gate: if it rejects correct
citations at a rate over `GATE_CONFOUND_THRESHOLD`, the "right" `(threshold, top_n)`
is measuring gate dysfunction, not gate tuning — so the run must be willing to come
back `gate_quality_confounded` rather than hand a number that looks clean and isn't.
