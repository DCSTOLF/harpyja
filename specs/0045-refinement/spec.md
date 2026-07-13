---
id: "0045"
title: "refinement"
status: closed
started_at_sha: 9c4f16ea2119c4499fb0c61a0dd4f740b7ae9a79
created: 2026-07-13
---

# Spec 0045 — refinement

Confidence-gate refinement — fix BOTH error directions, count the invisible cost.

## Why

0044's conditioned nudge SHIPPED (net +2, fu 6→1, 2 of 3 casualties rescued) but its firing instrumentation exposed that the gate MIS-RANKS evidence in two OPPOSITE directions, so the fix is calibration, not tightening or loosening:

- **(a) TOO LOOSE** — 5 of 6 fired-on-wrong-span nulls are 8b empty→wrong-file submissions. The gate fires, 8b submits a span it previously stayed SILENT on, and the bucket goes empty→wrong-file — which is BUCKET-NET-INVISIBLE (both non-correct), so it never appears in the conversion/regression ledger. This is the same invisible-loss class as found-then-dropped (0033) and found-but-unsubmitted (0043) — a cost the headline metric cannot see.
- **(b) TOO TIGHT** — the one remaining found-but-unsubmitted cell (`pytest-10081::qwen3:14b`) is NEVER-FIRED (codex's narrow-gate risk, now data): the model HAD the span, the gate didn't recognise it as confident, no nudge, no submit.

Also unresolved: `django-14315::8b` regressed correct→wrong-file WITH the nudge fired — the named 0044 residual, a 0043 casualty not rescued.

**Why empty→wrong-file is a cost at all (the premise, resolved here, not an open question):** Harpyja is a LOCATOR whose Verification Gate exists precisely because an unverified confident citation is worse than escalation — a wrong citation sends the downstream agent to the wrong file, where it spends its budget before recovering, while an empty result routes to escalation/fallback honestly. Counting silence→wrong-confidence as a cost class is the same premise the Verification Gate already encodes, applied to the eval ledger.

Ref: 0044 (conditioned gate, firing instrumentation, the (b)/(c) record-only observability fields, the qualified ship + residual), 0043 (bidirectional predicate, found-but-unsubmitted, two-stage freeze), 0042 (symbols adoption — the confidence signal itself; the recorded-confound precedent), 0041 (gated endpoint).

### Invariants

- **Make the invisible cost COUNTABLE (the project's recurring fix)**: empty→wrong-file under a FIRED gate becomes a first-class counted cost class in the artifact and in the predicate. A metric that can't see a loss will let it compound (found-then-dropped, found-but-unsubmitted — same lesson, third time).
- **Predicate frozen BEFORE any number — and the LEDGER IS FOUR-SIDED**: conversions, regressions, silence→wrong-confidence, AND found-but-unsubmitted (§Ledger). The gate errs in two directions, so the reopened-error space is four-sided: a gate tightened until it rarely fires would cut s→wc while resurrecting fu, and a three-sided predicate would miss it. All four classes carry conjuncts in the verdict; net surfaced per model.
- **Calibrate, don't just move the threshold**: the gate errs in BOTH directions on DIFFERENT cells, so a uniform tighten/loosen cannot fix it — it would trade (a) for (b). The refinement must improve the RANKING of evidence, chosen by a FROZEN stage-1 rule over 0044's committed firing data (§Two-stage freeze) — do not re-tune blind, and do not re-tune sighted either.
- **Per-model sign is expected — 8b is the crux**: 14b fired 5/11 with ZERO regressions (gate works for it); 8b fired 9/11 and is where every miscalibration concentrates; 4b is INERT (unfired; its 0044 +1 came from the sentence removal, not the gate — its lever is the parked compression spec). Report per model; an aggregate win that hides 8b's confident-wrong submissions is NOT a ship.
- **ONE definition per signal (one-oracle-reuse, applied forward)**: the candidate discriminators (grep-hit-inside-a-symbol containment; convergent evidence) exist today as EVAL-SIDE postflight computations (0044's record-only fields in `eval/submission_observability.py`). A live gate consuming them must NOT re-implement them: the predicates move to `scout/` as pure, gold-blind, trajectory-only helpers, and `eval/submission_observability.py` imports them FROM scout (the allowed dependency direction; `scout/confidence_gate.py` stays ast-pinned no-eval-import). A test asserts the eval-side reference is the scout function BY IDENTITY. GOLD-ENTANGLEMENT GUARD: 0044's eval-side (b)/(c) code routes near `metrics.span_hit_kind` (which needs gold); only the genuinely trajectory-only part of each predicate moves to `scout/` — if any part turns out to depend on gold, that part STAYS eval-side and is not dragged into the SUT. The one-definition move must not accidentally import a gold dependency into the gold-blind gate.
- **Measure on the 0041-gated endpoint**: exclusivity proof per artifact, SUT hash pinned, params byte-identical (the 0034/0038 `explorer_think=None ⇒ params == {max_tokens: 2048}` pin survives verbatim), evict-before / re-pin-after.
- **Train-on-test is REAL and RECORDED (the 0042 recorded-confound precedent)**: the refined ranking is derived from attributions on the same 33 cells AC4 re-measures and the same named cells AC5 checks. At pilot N with enlargement parked this is an accepted, recorded confound — no follow-up re-litigates it, and pool enlargement remains THE unblock for any generalizing claim.

## What

### Comparison axes (frozen)

- **BEFORE ledger (bucket axis)** = the committed 0040/0042 pre-nudge baseline — the SAME axis 0043 and 0044 were read on (one comparison axis, three specs). Pinned by path + sha256 in the frozen config.
- **0044 comparator (head-to-head axis)** = `specs/.archive/0044-submission/submission_run/submission_results.json` (sha256 `e75b0a29e1bf…`), per-cell firing data `specs/.archive/0044-submission/submission_run/artifacts/*.submission.json` (32 files), config `specs/.archive/0044-submission/submission_config/submission_config.json` (sha256 `f5088aa4fb77…`). The comparison literals — 0044 net per model, fu_after = 1, s→wc_0044 = 5 (14b 0 / 8b 5 / 4b 0) — are pinned in the config AND re-derived from the pinned artifacts in the pin test (the anti-tautology discipline; a hand-restated literal alone is not a pin).

### Ledger (formal, four-sided — frozen before any number)

Per model, over per-case joined pairs (join on (case, model); a cell typed degrade on either side is excluded from the join and reported):

- **conversion**: BEFORE bucket non-correct → AFTER bucket correct.
- **regression**: BEFORE bucket correct → AFTER bucket non-correct.
- **silence→wrong-confidence (s→wc)**: BEFORE bucket empty ∧ AFTER bucket ∈ {wrong-file, right-file-wrong-span} (submitted-but-not-correct) ∧ `confidence_fired` in the AFTER trajectory. Counted per cell, reported per model.
- **found-but-unsubmitted (fu)**: detector `0043/1` on the AFTER trajectory (unchanged definition — one-detector-reuse).
- **NET = conversions − regressions** — the definition is UNCHANGED from 0043/0044, deliberately: redefining NET would break the head-to-head axis (0044's net +2 must stay comparable). s→wc and fu are NOT subtractive inside NET; they enter the verdict as explicit conjuncts (§Verdict). This is a recorded decision, not an omission.

### Two-stage freeze (the 0043 pattern — with the partial sightedness RECORDED)

- **Stage 1 (choosing rule)**: a discriminator-selection table mapping attribution shapes → refined ranking rule is frozen, hashed, and committed BEFORE the per-cell attribution is computed. Full blindness is UNATTAINABLE and is recorded as such in the table artifact: 0044's committed outcome already published the headline attributions (5/6 fired-on-wrong-span are 8b empty→wrong-file; the never-fired cell is `pytest-10081::14b`; fired-but-ignored 1). What is NOT yet computed — and what the table therefore freezes over — is the per-cell (b)/(c) observability detail: which containment/convergence values held on each fired-on-wrong-span cell and on the never-fired cell. The candidate discriminator set is closed here: symbols-derived exact span (the 0044 signal), grep-hit-inside-a-symbol containment, convergent evidence (≥2 independent tools agreeing on the span), weak/singleton evidence (fires nothing). The table carries a typed `NO_DISCRIMINATOR_SEPARATES` row (the 0043 lever-table totality posture): if the per-cell (b)/(c) detail fails to separate the fired-on-wrong-span cells from the never-fired cell within this closed candidate set, the mechanical selection has an honest exit — the refinement is not asserted, and the spec's outcome reports the non-separation rather than force-fitting a discriminator.
- **Stage 2 (config)**: `PREREGISTERED_REFINEMENT_CONFIG_0045` — a frozen dataclass of LITERALS drift-pinned to the SUT constants (never references), carrying the baseline + comparator pins (§Comparison axes), the power floors, the per-model expected readings as DATA, and the verdict precedence — is hashed and committed AFTER the refined gate lands in the SUT, BEFORE any live call. The driver re-verifies the committed config hash AND the working-tree SUT hash at EVERY invocation (typed STOP on drift).

### Verdict (frozen total order, six members, first-true-wins, grid-totality tested)

**Projection convention (stated to eliminate implementer choice):** unless a conjunct is explicitly per-model, `s→wc` and `fu` in the verdict formulas are AGGREGATE SUMS over the joined, non-degrade cells on the head-to-head axis, and the literals they compare against (`5`, `1`) are 0044's pinned aggregate totals (s→wc_0044 = 5, fu_0044 = 1). `NET ≥ 0` and `no model net-negative` are the per-model conjuncts.

Power floors (consumed by the UNDER_POWERED branch, never dormant config): `min_covered_joined_cells = 8` (a LIVE-run check — a degrade-thinned join trips it). `min_comparator_swc = 3` is checked against the freeze-time re-derived comparator literal (5), so it can only ever pass at runtime — it is a RE-DERIVATION GUARD on the pinned baseline (the s→wc-drop conjunct must have a non-vacuous base), NOT a live-run power check; recorded as such so no reader mistakes its role.

Precedence — worse outcomes first, so a good aggregate cannot mask them; ALL true conditions are recorded as data alongside the selected member (the 0020/0023 discipline):

1. **UNDER_POWERED** — a power floor unmet.
2. **TRADES_DIRECTIONS** — fixing one error direction reopened the other: (s→wc < 5 ∧ fu > 1) ∨ (fu < 1 ∧ s→wc > 5). The reopened direction is named as data.
3. **RESIDUAL_PERSISTS** — `django-14315::8b` is not correct in the AFTER run. What evidence would be needed is named as data. NOTE: this gates GATE_CALIBRATED on a single pilot-N cell — one noisy flip on `django-14315::8b` blocks the calibrated label regardless of every other improvement. This is deliberate (worse-first precedence, and it IS the named 0044 residual), but the single-cell sensitivity at pilot N is acknowledged here alongside the train-on-test confound — it is a signal, not an inferential gate.
4. **GATE_INERT** — no BENEFIT, where BENEFIT ≡ `(s→wc < 5)` OR `(fu < 1)` — the never-fired cell converts to submitted — OR `(aggregate NET > 0044's aggregate net on the head-to-head axis)`. A refinement that reproduces 0044's numbers exactly types INERT, never CALIBRATED (the 0044 `NUDGE_INERT` lesson, re-applied). CAVEAT recorded: because TRADES_DIRECTIONS requires one direction to IMPROVE and MISCALIBRATION_REMAINS requires BENEFIT, a run where BOTH cost classes rose and NET ≤ 0044's falls to INERT — an actively-worse run wearing an "inert" label. The all-true-conditions recording mitigates (the risen classes are named as data), but the selected label under-describes; noted so the outcome doc reads the recorded data, not just the label.
5. **GATE_CALIBRATED** — ALL of: NET ≥ 0 per the bucket axis ∧ no model net-negative ∧ s→wc ≤ 5 (does not rise) ∧ fu ≤ 1 (does not rise — the fourth side) ∧ BENEFIT (above). Reachable only when 1–4 are all false, so it structurally requires the residual cell to hold correct and at least one direction to actually improve. RECORDED RATIONALE for the head-to-head axis: `NET ≥ 0` is against the pre-nudge bucket baseline, so CALIBRATED is reachable at bucket-net 0 even if that is a head-to-head REGRESSION vs 0044's +2 (both 0044 conversions lost, s→wc merely improved). This is accepted deliberately — the spec's thesis is that eliminating an invisible cost is worth trading visible conversions the pilot N cannot power-distinguish — but the trade is made VISIBLE: the head-to-head aggregate net and the flask-5014 named-cell holds (AC6) are recorded beside the label so a conversion-losing "calibration" is never silent.
6. **MISCALIBRATION_REMAINS** — the terminal else: powered, not trade-shaped, residual correct, some benefit, but a CALIBRATED conjunct unmet (net < 0, a model net-negative, or a cost class rose outside the trade shape). Which conjunct failed is named as data. This member exists so the order is TOTAL — no input tuple falls through — and the grid-totality test proves exactly one member selects for every tuple.

The verdict function is total and pure over per-model tuples (net, conversions, regressions, s→wc, fu, firings, firing_rate) + the named-cell outcomes. Pilot-N signal, not an inferential claim.

**Record-only cross-check against gaming-by-silence (the fired-conditioning loophole):** s→wc is conditioned on `confidence_fired` — correct as the CAUSAL attribution of gate-caused wrong confidence, but it means a refinement that simply stops the gate firing on the 8b cells makes s→wc drop BY DEFINITION even if those cells still go empty→wrong-file UNFIRED (the model submitting on its own). The stage-1 freeze prevents deliberate tuning toward that shape, but not the mechanism drifting there. Closure (same posture as 0044's record-only (b)/(c) fields): a RECORD-ONLY per-model line counts unfired empty→(submitted, non-correct) transitions beside s→wc, so the outcome doc can distinguish "cost eliminated" from "cost merely de-attributed." Record-only — it does NOT enter the verdict predicate (adding it would re-open a definitional argument mid-run); it is the cross-check the reader applies to a fired-conditioned s→wc drop.

### The work

- **DIAGNOSE from 0044's COMMITTED firing data (no new compute first)**: for each fired-on-wrong-span cell, WHICH signal triggered it and why it was weak; for the never-fired cell, what evidence was present that the gate failed to credit. Computed via the one-definition helpers (§Invariants), consumed by the stage-1 table.
- **REFINE the confidence predicate's RANKING** per the stage-1-selected rule; the 8b failures suggest a signal is being credited that shouldn't be; the never-fired cell suggests a valid signal isn't credited at all.
- **COUNT the new cost class** end-to-end: additive schema bump `0044/1 → 0045/1`; s→wc threaded through BOTH seams — `build_trajectory_record` params AND the `run_verified_case`-assembled written artifact (written-JSON pinned; presence-required on `0045/1` artifacts; legacy versions validate unchanged; existing version-pin tests amended in the same change — the dual-seam checklist, fifth application).
- **RE-MEASURE the 0044 cells on the gated endpoint**; report the four-sided ledger per model, head-to-head vs 0044.

## Acceptance criteria

([unit]=fakes; [integration]=live on the 0041-gated endpoint, skip-not-fail)

1. [unit/doc] Attribution from 0044's committed firing data: per fired-on-wrong-span cell, the triggering signal named; for the never-fired cell (`pytest-10081::14b`), the unrecognised evidence named. The stage-1 discriminator-selection table is committed BEFORE this attribution is computed, and records the already-visible 0044 headline facts. Refinement justified by table + attribution, not assumed.
2. [unit] silence→wrong-confidence is a first-class counted fact: additive schema bump `0044/1 → 0045/1`, threaded through BOTH seams (`build_trajectory_record` param AND `run_verified_case` written artifact), written-JSON pinned, presence-required on `0045/1`, legacy versions validate unchanged, existing version-pin tests amended same-change. It enters the frozen predicate. Fixture-pinned.
3. [unit] Refined ranking implemented per the stage-1-selected rule; the containment/convergence predicates live in `scout/` (pure, gold-blind, trajectory-only) and `eval/submission_observability.py` imports them BY IDENTITY (asserted in a test); fixture-pinned in BOTH directions — a weak/singleton signal no longer fires; the 0044 never-fired evidence shape now DOES fire.
4. [unit] `PREREGISTERED_REFINEMENT_CONFIG_0045` frozen, hashed, committed after the SUT lever lands and before any live call: baseline + 0044 comparator pinned by path + sha256, comparison literals (net per model, fu_after = 1, s→wc = 5 by model) RE-DERIVED from the pinned artifacts in the pin test; power floors present and consumed; verdict precedence encoded; grid-totality tested; the 0034/0038 params byte-pin survives verbatim; driver re-verifies both hashes at every invocation (typed STOP on drift).
5. [integration] Re-measure 0044's cells: report per model conversions / regressions / s→wc / fu, and NET (= conversions − regressions, unchanged axis). Head-to-head vs 0044's pinned numbers.
6. [integration] The named cells: `django-14315::8b` (0043+0044 casualty, fired-on-wrong-span) — does it hold correct? `pytest-10081::14b` (never-fired fu cell) — does it now fire and submit? `flask-5014` both cells (rescued in 0044) — do they STAY correct (no regression from the refinement)?
7. [doc] Typed outcome from the frozen six-member total order (§Verdict): `UNDER_POWERED` / `TRADES_DIRECTIONS` (name the reopened direction) / `RESIDUAL_PERSISTS` (name the missing evidence) / `GATE_INERT` / `GATE_CALIBRATED` / `MISCALIBRATION_REMAINS` (name the failed conjunct) — all six members enumerated, the selected member plus all true conditions recorded as data, and the record-only unfired-s→wc cross-check reported beside s→wc. Pilot-N signal, not an inferential claim. The train-on-test confound AND the single-cell (`django-14315::8b`) sensitivity are recorded in the outcome document per the 0042 precedent.

## Out of scope

- Tool-result COMPRESSION for 4b prefill (parked spec — compression NOT truncation, positional cutoff would discard relevant hits)
- Pool enlargement
- The bake-off
- The 0039 thinking A/B
- The semantic tier
- Any model swap

## Open questions

1. Which signal is over-credited on 8b? The 0044 firing data names it. If it's a bare grep hit (weak, singleton), the fix may be requiring convergence (≥2 tools) or symbols-derivation for 8b-class models. Decided BY the stage-1 table + attribution (AC1), never ad hoc.
2. Is the right gate MODEL-DEPENDENT? 14b fires 5/11 with zero regressions; 8b fires 9/11 and miscalibrates. A per-model confidence bar is defensible (they have different verification habits) but adds a knob and a generalization risk. Lean single gate with better ranking first; per-model only if the attribution shows the SAME signal predicts correctly for 14b and wrongly for 8b — and the stage-1 table must carry this branch explicitly so the choice is frozen, not post-hoc.
