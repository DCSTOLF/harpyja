# Cross-model review — 0045-refinement

**Date:** 2026-07-13
**Round:** 1
**Reviewers:**
- codex — verdict: `changes-requested`
- claude-p — verdict: `changes-requested`

## Consolidated verdict: `changes-requested` (quorum not met)

Quorum requires at least 1 `approve` or `approve-with-comments`. Both agents returned `changes-requested`, so quorum is **not met**. The spec should not proceed to implementation as written.

Both reviewers agree the spec is well-motivated and structurally on-pattern (per-model reporting, endpoint exclusivity, offline-first diagnosis, disciplined out-of-scope list, correctly consuming 0044's reserved refinement). The convergent finding is that **AC6 (the `GATE_CALIBRATED` verdict predicate) is the weakest part of the spec, and it's the part that cannot be safely patched after freezing** — both agents independently flagged that the predicate can be satisfied by a refinement that changes nothing of substance.

## Required changes

Items below are numbered and attributed. Where both agents converged independently, this is called out explicitly as a strong signal.

1. **[BOTH AGREE — highest priority] Give `GATE_CALIBRATED` a benefit conjunct; it is currently reachable by an inert refinement.**
   As written, a refinement that leaves 0044's behavior unchanged — net 0, no model negative, silence→wrong-confidence merely flat — types as `GATE_CALIBRATED`. codex: "the positive outcome predicate is too permissive... can pass with no improvement in the never-fired found-but-unsubmitted cell, and with silence→wrong-confidence merely not rising rather than falling." claude-p, independently, ties this to a named repo convention: 0044's `NUDGE_INERT` label exists precisely to catch this shape, and this spec re-opens the hole a net-only predicate closes. **Action:** add a benefit conjunct (e.g., silence→wrong-confidence strictly drops, OR the never-fired fu cell converts, OR fu drops) alongside the net≥0 / no-model-negative conjuncts, and consider a distinct `GATE_INERT` (or similarly named) label for the do-nothing case, per the 0044 convention (claude-p, convention violation).

2. **[BOTH AGREE] The ledger/predicate arithmetic is not formally specified.**
   codex: the three-sided NET (conversions / regressions / silence→wrong-confidence) has no stated exact arithmetic, precedence, baseline join, or whether the new cost is subtractive per cell — suggests defining NET explicitly (e.g., `conversions − regressions − silence_to_wrong_confidence`) and stating exactly which baseline→after transition is counted. claude-p arrives at the same gap from a different angle: found-but-unsubmitted is reported in AC4 but is *absent* from the `GATE_CALIBRATED` conjuncts, making the reopened-error space four-sided against a three-sided predicate — a gate tightened to cut silence→wrong-confidence could resurrect fu (the (b) direction) and still type calibrated. **Action:** formally define NET's arithmetic, add "fu does not rise" as an explicit conjunct, and state which baseline the "does not rise / does not fall" comparisons are relative to.

3. **[BOTH AGREE] The refinement-selection ("choosing") step is not adequately frozen — record it as partially-sighted, not blind.**
   codex: the refinement-selection process needs a frozen, test-pinned decision rule over the committed 0044 attribution data; "diagnose first, pre-register before any run" still leaves room for hand-picked calibration unless the attribution-to-ranking rule is explicit and pinned. claude-p sharpens this: the two-stage freeze is only half-invoked — "pre-register before the run" covers stage-2 config only, but no stage-1 choosing rule (attribution pattern → discriminator) is frozen before the attribution is computed. Critically, full blindness is unattainable here: 0044's committed outcome already names the top-level attributions (5 of 6 fired-on-wrong-span are 8b empty→wrong-file; the never-fired fu cell), so the spec must either freeze a stage-1 rule over the still-uncomputed per-cell detail, or honestly record that the choosing step is partially sighted (claude-p, convention violation — 0043's two-stage-freeze discipline). **Action:** add a committed, hashed discriminator-selection table (attribution shape → ranking rule) frozen before per-cell attribution is computed, plus an explicit recorded acknowledgment of which 0044-published facts were already visible at freeze time.

4. **[BOTH AGREE] The dual-seam schema obligation is not spelled out.**
   codex: the schema bump is described as additive, but the spec doesn't explicitly require the recurring dual-seam verifier checklist — both `build_trajectory_record` and `run_verified_case`'s written JSON must carry the new field, with a written-artifact test. claude-p makes the identical ask independently: state the dual-seam obligation in AC2 explicitly (both call sites, written-JSON pinned), noting this is now a three-recurrence standing checklist item the spec should carry rather than rediscover. **Action:** amend AC2 to name both write paths and require a written-artifact test for each.

5. **[BOTH AGREE] Baseline/source artifacts are under-pinned.**
   codex: pin the 0044 source artifacts (firing data, baseline bucket ledger) by path and sha256. claude-p: baselines are under-pinned generally — "does not rise" is relative to an unnamed baseline, and neither AC4's before-buckets nor the comparison literals (0044's silence→wrong-confidence count, fu_after=1) are named by path+sha256 with derived counts re-derived in a pin test (the 0044 anti-tautology discipline). **Action:** name the exact 0044 artifact(s) by path + sha256 in the pre-registered config, and add a pin test that re-derives the comparison literals from that artifact rather than hardcoding them.

6. **[BOTH AGREE] OQ3's harm-premise must be resolved in-spec, not left open.**
   Both agents flag that the spec already makes "empty→wrong-file is worse than empty" predicate-load-bearing (it drives the entire new cost class) while leaving its justification in Open Questions. codex: move the rationale into invariants or acceptance criteria. claude-p: resolve OQ3 now, noting the existing guardrail ("never return a confident citation that wasn't verified") already supplies the one-line justification asked for. **Action:** promote OQ3's resolution into the spec body (invariants or AC) before implementation.

7. **[claude-p only] No `UNDER_POWERED` branch and no stated power floors.**
   0043 and 0044 both carried power floors consumed by an explicit branch; AC6 has no such branch, so a degrade-thinned run (the known 4b heavy-repo exclusion class already seen in 0044) has no honest exit among the three current labels. Convention violation cited: pre-registered power floors must be consumed by an explicit `UNDER_POWERED` branch, never dormant config. **Action:** add an `UNDER_POWERED` outcome member and state the power floor(s) it's keyed to.

8. **[claude-p only] AC6's outcomes are not a partition; no frozen total order over overlapping conditions.**
   `django-14315::8b` still failing while net≥0 and silence→wrong-confidence is flat simultaneously satisfies `GATE_CALIBRATED` and `RESIDUAL_PERSISTS`; fixing silence→wrong-confidence while fu climbs back satisfies both `GATE_CALIBRATED` and `TRADES_DIRECTIONS`. Without a frozen total order, the verdict becomes implementer choice — the exact post-hoc steering the freeze discipline exists to prevent (0020/0023 convention). **Action:** rewrite AC6 as a frozen total-order enum (claude-p suggests, as one option: `UNDER_POWERED > TRADES_DIRECTIONS > RESIDUAL_PERSISTS > GATE_INERT > GATE_CALIBRATED`, or a justified alternative order), grid-totality tested, all true conditions recorded.

9. **[claude-p only] Signal-computation locus (scout/ vs eval/) is unspecified — one-definition drift risk.**
   The candidate discriminators (symbols-derived span, grep-hit-inside-symbol, convergent evidence) are currently eval-side postflight computations in `submission_observability.py` (reusing `metrics.span_hit_kind`, `_parse_tool_content`), deliberately kept off the SUT per 0044. A *live* gate consuming these must compute them in `scout/` (gold-blind, ast-pinned, no-eval-import), which risks a second, subtly different definition drifting from the eval-side postflight — the one-oracle/one-parser drift class the project has already killed three times. The spec does not say where the shared computation will live. **Action:** pre-decide the locus — put the containment/convergence predicates in `scout/` as pure helpers, and have `eval/submission_observability.py` import them from `scout/` (the allowed import direction), so the live gate and postflight attribution share one definition.

10. **[claude-p only] Train-on-test circularity is real and unnamed.**
    The refined ranking is derived from attribution on the exact 33 cells AC4 re-measures, and AC5's named cells are the very cells the ranking was tuned to fix. "Pilot-N signal" language covers statistical power, not selection-on-the-evaluation-set. This doesn't invalidate the spec at pilot N with pool enlargement parked, but per the 0042 precedent it should be explicitly recorded as a confound so a `GATE_CALIBRATED` result is read as "calibrated on the tuning set," with pool enlargement re-named as the unblock for any generalizing claim. **Action:** add an explicit line recording this circularity as a known, accepted confound at this pilot stage.

11. **[codex only] Frontmatter convention violation.**
    Repo convention requires the canonical frontmatter schema (`id`, `title`, `status`, `started_at_sha`, `created`) with no non-canonical keys added out of lockstep. The spec's frontmatter is missing `started_at_sha` and adds `authors`, `packages`, `related-specs` outside the canonical set. **Action:** conform frontmatter to the canonical schema (add `started_at_sha`; reconcile the extra keys with the current convention or drop them).

## Suggestions (optional, non-blocking)

- codex: Define NET explicitly as a formula in the spec text (e.g., `conversions − regressions − silence_to_wrong_confidence`), not just descriptively.
- claude-p: For the stage-1 discriminator-selection table, record explicitly which 0044-published facts were already visible at freeze time, rather than implying full blindness.
- claude-p: Consider whether the `GATE_INERT`-style label (item 1) should itself be ordered relative to `RESIDUAL_PERSISTS`/`TRADES_DIRECTIONS` in the same total order (ties into item 8).
- Both agents' framing suggests the fix cluster (items 1, 2, 8) could be resolved together by a single AC6 rewrite pass rather than three separate edits — worth doing in one motion to keep the enum internally consistent.

## Next step

Edit `specs/0045-refinement/spec.md` to address the required changes above — priority on items 1–6 (agreed by both agents) and item 8 (partition/precedence), since these together define AC6's correctness — then re-run `/speccraft:spec:review`.

---

# Cross-model review — 0045-refinement (round 2)

**Date:** 2026-07-13
**Round:** 2 (revised after round-1 `changes-requested`)
**Reviewers:**
- codex — verdict: `approve-with-comments`
- claude-p — verdict: `approve-with-comments`

## Consolidated verdict: `approve-with-comments` — quorum MET

Quorum requires at least 1 `approve` or `approve-with-comments`; both agents returned `approve-with-comments`, so quorum is **met** and the spec advances to `reviewed`. Both reviewers verified the revision as a substantive, near-complete response to round 1: claude-p walked all eleven round-1 items and confirmed each is addressed (benefit conjunct + `GATE_INERT`; four-sided ledger with NET arithmetic pinned and the not-subtractive decision recorded; two-stage freeze with partial-sightedness recorded; dual-seam AC2; both axes pinned by path+sha256 with re-derivation; OQ3 harm premise promoted into Why; `UNDER_POWERED` + floors; six-member total order with terminal else; scout/-locus identity-assert; train-on-test recorded; canonical frontmatter with `started_at_sha`). No guardrail violations; claude-p reported no convention violations, codex flagged one (AC7 label-drift) now fixed.

## Residual comments — ALL folded post-quorum (0041–0044 precedent)

1. **AC7 dropped `MISCALIBRATION_REMAINS`** (BOTH agents; codex logged it as a convention violation — documented labels must not drift from the frozen total answer space). AC7 now enumerates all six members and requires the failed-conjunct data. **Fixed.**
2. **Aggregate-vs-per-model projection unstated** (codex) — the ledger is per-model but the verdict predicates over `s→wc`/`fu` against global literals `5`/`1`. Added an explicit projection convention: those are aggregate sums over joined non-degrade cells on the head-to-head axis; `NET ≥ 0` and no-model-net-negative are the per-model conjuncts. **Fixed.**
3. **Malformed `BENEFIT` parenthetical** (codex) — the three disjuncts are now syntactically unambiguous. **Fixed.**
4. **Fired-conditioning loophole** (claude-p, emphasized) — s→wc is conditioned on `confidence_fired`, so a gate that stops firing on the 8b cells makes s→wc drop by definition even if those cells still go empty→wrong-file unfired. Added a record-only per-model unfired-empty→(submitted, non-correct) line beside s→wc (same posture as 0044's record-only fields) so the outcome doc distinguishes "cost eliminated" from "cost de-attributed." Record-only — does not enter the predicate. **Fixed.**
5. **Stage-1 table needs an honest no-separation exit** (claude-p) — added a typed `NO_DISCRIMINATOR_SEPARATES` row (0043 lever-table totality posture). **Fixed.**
6. **Head-to-head net rationale missing** (claude-p) — `GATE_CALIBRATED` can select at bucket-net 0 that is a head-to-head regression vs 0044's +2. Added a recorded rationale (the trade is deliberate — eliminating an invisible cost over pilot-N-indistinguishable conversions) AND made it visible (head-to-head aggregate net + flask-5014 holds recorded beside the label). **Fixed.**
7. **`GATE_INERT` under-describes a both-classes-rose run** (claude-p) — added a recorded caveat that an actively-worse run can wear the inert label, mitigated by all-true-conditions recording. **Fixed (recorded).**
8. **`RESIDUAL_PERSISTS` single-cell pilot-N sensitivity** (claude-p) — added an explicit acknowledgment alongside the train-on-test record; it is a signal, not an inferential gate. **Fixed (recorded).**
9. **`min_comparator_swc` is a re-derivation guard, not a live floor** (claude-p) — labeled as such; `min_covered_joined_cells` is the live power check. **Fixed.**
10. **Gold-entanglement guard on the scout/ move** (claude-p) — added: only genuinely trajectory-only predicate parts move to `scout/`; any gold-dependent part stays eval-side, so the one-definition move cannot import a gold dependency into the gold-blind gate. **Fixed.**

## Next step

Quorum met; spec status → `reviewed`. Proceed to `/speccraft:spec:plan`.
