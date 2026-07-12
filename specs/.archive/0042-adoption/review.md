# Review — Spec 0042 (adoption) — Round 2

- date: 2026-07-12
- round: 2 (round 1 archived at review.round1.md; verdicts then: codex changes-requested, claude-p approve-with-comments)
- agents: codex (approve-with-comments), claude-p (approve-with-comments)
- quorum: met (1 required; both approve)
- guardrail/convention violations: none filed
- recommendation: Advance the spec past review. Both reviewers independently verified all six round-1 required revisions and all four round-1 advisory items are resolved, and the round-2 residual comments (five from claude-p, three from codex) have been folded into `spec.md` post-quorum per the 0041 precedent for post-quorum precision fixes — each is cited below against its landing spot in the spec text. Two items remain correctly deferred to plan time rather than resolved in spec text now: (1) OQ1 (optional `path` on `symbols` vs a distinct `find_symbol(name)` tool) must be decided before tasking, since it changes tool count, prompt/schema tests, and AC4; (2) the 0035 convention-text amendment and all dependent consumer/type/schema tests must land in the same change as the result-shape widening, or the old and new marker semantics will conflict mid-implementation. Proceed to `/speccraft:spec:plan` with OQ1 resolved as the first plan-time decision, and treat the lockstep-landing requirement for the 0035 amendment as a tasking constraint, not a follow-up.

## codex

**Verdict:** approve-with-comments

Concerns:
- The round-1 blocking findings are materially resolved: marker shape is explicit, measurement closure is gated and artifact-backed, AC1 names the bound tool surface, absent/degraded Tier-0 records get a typed marker, and no-conversion is qualified by a power floor.
- One implementation-shaping choice remains open: optional `path` on `symbols` vs a separate `find_symbol(name)` tool. The spec says to decide before plan, which is acceptable, but the plan must close it before tasking because it affects tool count, prompt checks, schemas, and AC4.
- The heterogeneous degraded return shape `[marker, *CodeSpans]` is now coherent, but it is a deliberate convention extension. The plan must make the convention edit and all consumer/type/schema tests land in the same change, or the old 0035 marker semantics will still conflict.

Suggestions:
- In AC5, name the config hash field and artifact path pattern expected for `PREREGISTERED_ADOPTION_CONFIG_0042`, so closure reviewers can mechanically find the frozen predicate.
- When resolving OQ1, prefer making the prompt assertion check the repo-wide affordance text explicitly, not just tool-name presence, because the adoption hypothesis depends on advertisement.

## claude-p

**Verdict:** approve-with-comments

Concerns:
- The conversion predicate is one-directional: `ADOPTED_AND_CONVERTS` fires on ≥1 RFWS→exact flip but the spec never mentions exact→RFWS regressions in the re-run; a net-negative re-run with one noise flip would still type CONVERTS. The frozen config should retain per-case pairs in both directions and report regressions alongside conversions.
- ≥1 flip is far below the repo's own inferential floors (the 0023/0026 discipline needs ≥8 discordant pairs before any claim); the no-proof invariant partially covers this, but `ADOPTED_AND_CONVERTS` as a label reads stronger than "observed ≥1 conversion signal at pilot N" — the AC7 record should carry that qualifier in the outcome text itself, not only in the Why.
- AC6 permits a 14b-only run ("8b/4b if wall-clock allows") but the adoption boundary is stated against the pooled 0/28 baseline; the frozen config should pin the clean-cell universe under partial model coverage (per-model boundaries, or the pooled baseline recomputed to the models actually run) so a 14b-only run's 0-invocations can't be typed against a denominator it never had.
- Two marker conventions now coexist (0035 bare-string replacement vs the new list-prepended annotation); AC3 says absent/degraded Tier-0 records produce "a TYPED marker (0035 style)" — state which shape, since the repo-wide lookup's absent-index case is a replacement (no spans exist) while the file-local degraded case is an annotation (spans exist).
- Deep's sibling `symbols` host tool (`deep/host_tools.py`) is not mentioned; if it shares any result shape with the explorer tool the blast-radius-by-category convention applies, and if it deliberately keeps its own shape, one line saying the Deep sibling is out of scope/unchanged would prevent a plan-time surprise.

Suggestions:
- Record both flip directions (RFWS→exact and exact→RFWS) in the AC6 artifacts and surface the net alongside the conversion count — cheap, and it immunizes the CONVERTS label against the noise-flip objection.
- For OQ1, the optional-path lean is right for a small model's menu, but pre-commit in the spec (not just the OQ) that whichever shape wins, the AC1 drift guard gains the repo-wide when-to-use presence check — currently that guard is conditional inside the OQ text.
- Pin in the frozen config which model(s) the closure run must cover, so "wall-clock allows" can't quietly shrink the measurement after the fact.

## Round-1 findings — resolution status

Both agents confirm, independently, that all six round-1 required revisions and all four round-1 advisory items are resolved:

**Required revisions (all six resolved):**
1. Degraded-marker shape contradiction (What #3/AC2) — resolved: `list[CodeSpan]` clean, `[marker, *CodeSpans]` degraded, marker first; `_spans_of()` counts only `CodeSpan` entries; marker stays model-visible via stringification; 0035 convention text amended in lockstep.
2. Frozen decision predicate — resolved: `PREREGISTERED_ADOPTION_CONFIG_0042` (What #5, AC5) pins the adoption boundary, RFWS denominator, per-case paired-bucket conversion predicate against the committed 0040 ledger, and `MIN_RFWS_DENOMINATOR` power floor, frozen and hashed before any live call, grid-totality tested.
3. Closure path — resolved: What #6/AC6 bind re-measurement to `run_gated_pool_pilot` (or equivalently 0041-gated driver) with the `0041/pilot/2` exclusivity proof in every artifact, a STOP-AND-WARN operator driver, and committed durable per-case trajectory-verified artifacts; the AC preamble states a skipped integration test never closes the spec.
4. AC1 tool-set scope — resolved: the asserted set derives from the same single source as `test_tool_schemas_match_the_built_tool_surface_single_source`, enumerates `{grep, glob, read_span, ls, symbols}` explicitly plus `submit_citations` as terminal, and `read_span` is promoted to asserted scope in What #1.
5. AC3 empty-index degrade — resolved: absent/degraded Tier-0 records produce a typed marker, never a silent `[]`.
6. Under-powered qualifier — resolved: `ADOPTED_UNDER_POWERED` is a first-class typed outcome gated by the frozen power floor.

**Advisory items (all four resolved):** the attribution confound is stated as an accepted trade in the Why; the OQ1↔AC1 interaction is recorded inside OQ1; the OQ2 ranking-pinning guidance is incorporated; AC7 requires the record to state the fix-vs-defect framing of the 0/28 baseline.

## Round-2 residual comments and disposition

**claude-p concern 1 / suggestion 1 — bidirectional flip accounting.** ADDRESSED post-quorum. What #5 and AC5 now retain and report both flip directions (RFWS→exact conversions and exact→RFWS regressions), with the net surfaced alongside the conversion count, so a single noise flip over a net-negative re-run cannot type CONVERTS unqualified.

**claude-p concern 2 — ADOPTED_AND_CONVERTS label strength.** ADDRESSED post-quorum. AC7's outcome text now carries the qualifier explicitly: "observed ≥N conversion signal at pilot N with the net flip count — a signal at pilot scale, NOT an inferential claim," naming the ≥8-discordant-pairs floor a claim would need.

**claude-p concern 3 — partial-model-coverage denominator.** ADDRESSED post-quorum. What #5/AC5 now pin model coverage pre-run and per-model denominators, so a 14b-only run is typed against 14b's own clean-cell universe, never the pooled 0/28 baseline it never had.

**claude-p concern 4 — AC3 marker shape disambiguation.** ADDRESSED post-quorum. What #4 now states the repo-wide absent-index case uses the 0035 REPLACEMENT shape (bare marker string, no spans exist), explicitly distinguished from What #3's file-local degraded ANNOTATION shape (marker prepended to real spans).

**claude-p concern 5 — Deep sibling symbols host tool.** ADDRESSED post-quorum. Out of scope now carries an explicit line: Deep's sibling `symbols` host tool (`deep/host_tools.py`) is deliberately unchanged; reconciling any shared shape is a separate decision, not silently included.

**claude-p suggestion 2 / codex suggestion 2 — repo-wide advertisement check unconditional of OQ1.** ADDRESSED post-quorum. AC1 now asserts the repo-wide when-to-use text is present in the prompt unconditionally of how OQ1 resolves, rather than the check being conditional inside the OQ text.

**claude-p suggestion 3 — pin model coverage in frozen config.** ADDRESSED post-quorum, same landing spot as concern 3 above: What #5/AC5 pin the model coverage the closure run must include, so "wall-clock allows" cannot quietly shrink the measurement after the fact.

**codex suggestion 1 — discoverable frozen config.** ADDRESSED post-quorum. AC5 now names `ADOPTION_CONFIG_HASH_0042`, committed under `specs/0042-adoption/`, mechanically findable at close per the 0039/0040 shape.

**codex concern 2 — OQ1 optional-path vs find_symbol.** OPEN, correctly deferred to plan time. The spec still states "decide before plan" in OQ1; both agents treat this as acceptable to leave open for review but binding before tasking, since it changes tool count, the prompt/schema drift checks, and AC4.

**codex concern 3 — convention edit and consumer/type/schema tests must land together.** OPEN, correctly deferred to plan/tasking discipline. The spec text already specifies the widened shape and states the 0035 convention text is amended in lockstep (What #3); the residual risk is purely one of execution sequencing — the plan must ensure the convention-text amendment and all dependent consumer/type/schema tests (`_spans_of()`, tool-contract tests, schema tests) land in a single change, or the old and new marker semantics will conflict mid-implementation. No spec-text change is needed for this; it is a tasking constraint.

## Verdict summary

Both reviewers verified independently that spec 0042's round-1 blocking findings are resolved and returned approve-with-comments, meeting quorum with no dissent and no guardrail or convention violations filed. Every round-2 residual concern and suggestion raised by either agent — the bidirectional flip accounting, the conversion-label strength qualifier, the partial-model-coverage denominator, the AC3 marker-shape disambiguation, the Deep sibling out-of-scope line, the unconditional repo-wide advertisement check, and the discoverable frozen-config hash — has already been folded into `spec.md` post-quorum, following the 0041 precedent of landing post-quorum precision fixes directly rather than looping another review round. What remains open is exactly what both agents agree should remain open: OQ1's optional-path-vs-`find_symbol` decision, which is explicitly scheduled as a pre-plan decision in the spec, and the tasking-level discipline of landing the 0035 convention amendment together with its dependent tests in one change. The spec is ready to proceed to planning.
