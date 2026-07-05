---
spec: "0022-tier-1"
reviewers: [codex, claude-p]
quorum: 1
verdict: changes-requested
generated: 2026-07-04T00:00:00Z
---

# Cross-model review — 0022-tier-1 (Scout Tier-1 locate-accuracy on SWE-bench, diagnosis-not-fix)

**Verdicts:** codex — `changes-requested` · claude-p — `approve-with-comments`

## codex

**Verdict:** changes-requested

Concerns:
- Typed-finding decision rule under-specified: PRECISION_FIXABLE / RETRIEVAL_FUNDAMENTAL / MIXED depend on qualitative terms (file>>span, low file-level, empty-dominant, split) with no numeric thresholds or tie-break rules. Two implementers with the same counts could pick different conclusions — risky because it drives a later Scout fix-or-replace decision.
- Query reformulation probe left as an open question even though it affects the core diagnosis (retrieval failure vs long-query parsing failure). Without deciding include/defer, results may be interpreted inconsistently.
- Suffix-recovery hit/drop asked for but denominator / data source / how-unavailable-is-represented undefined.
- EMPTY vs WRONG_FILE boundary needs an explicit citation-normalization rule (malformed citations, file-level citations, partial paths, suffix-dropped citations).

Suggestions:
- Add a decision table with concrete thresholds/bands for file-level acc, span-level acc, empty-rate, file-minus-span gap.
- Decide the reformulation probe in this spec (labeled non-primary or explicitly deferred).
- Define citation normalization before classification.
- Require raw per-case rows + aggregate counts so the distribution is auditable/reusable.
- Add an AC confirming no changes under Scout/orchestrator/gate/tiers/matrix/judge.

Guardrail/convention violations: none.

## claude-p

**Verdict:** approve-with-comments

Concerns:
- AC5's typed-finding enum {PRECISION_FIXABLE, RETRIEVAL_FUNDAMENTAL, MIXED} is NOT MECE with AC6/OQ3. If the representativeness check concludes SWE-bench issue text is pathologically long and unlike Harpyja's terse legacy target, the honest verdict is neither a span fix nor a finder swap — it's "benchmark-unfit / inconclusive." AC5 forces one of three finder-indicting labels even when AC6 says the score is a benchmark-fit artifact. Per 0020's precedent (typed DEFERRED naming the real upstream blocker), add a fourth branch (BENCHMARK_UNREPRESENTATIVE / INCONCLUSIVE) OR make AC5 explicitly gated/routed by AC6's outcome. **(Reviewer's must-fix-before-plan.)**
- AC1 "mutually exclusive and total" has undefined boundary cases and the existing oracle contradicts one:
  (a) `span_hit_kind` (metrics.py:68) returns "file" for a line-less path-only citation and `span_hit_primary` counts it a hit — so a correct-file line-less citation is CORRECT under today's oracle, but the taxonomy seems to want RIGHT_FILE_WRONG_SPAN; mapping unstated.
  (b) RIGHT_FILE_WRONG_SPAN = "misses gold beyond proximity window" leaves within-window-but-non-overlapping (secondary-metric zone, metrics.py:84) unassigned.
  (c) Scout can return MULTIPLE mixed citations; any/any oracle means a case can be both CORRECT and WRONG_FILE — a per-case precedence order (CORRECT > RIGHT_FILE_WRONG_SPAN > WRONG_FILE > EMPTY) must be stated or MECE fails.
- AC4 turns-used source unstated: suffix-recovery has a durable instrument (`fc_citation_recovered_{spanned,filelevel}_count`, spec 0012), but if turns-used is not already emitted per-case it must be captured at the eval boundary (à la 0021's `_wrap_timed`), NOT by reaching into frozen Scout/FastContext internals.

Suggestions:
- Name the stratification dimension in AC3 (by repo? gold-span size? classification?).
- Pin the proximity window (reuse EvalConfig's existing secondary-metric `window`, state the value so astropy separable.py:66-102 vs gold 242-248 ~140-line gap is unambiguous).
- Resolve the probe open-question before /plan.
- State the expected prior as a falsifiable pre-registration (0021's ~33/38 EMPTY + astropy RIGHT_FILE_WRONG_SPAN pre-registers RETRIEVAL_FUNDAMENTAL).

Guardrail/convention violations: MECE finding-taxonomy convention tension flagged — AC1 and AC5 each assert MECE but have unassigned boundary cases / an AC6 outcome the enum can't express (measurement-not-construction conventions). Not treated as a hard guardrail breach, but material enough to require resolution before plan.

## Synthesis & recommendation

**Verdict: changes-requested (revise then proceed).** Quorum is technically met (one approve-with-comments), but both reviewers independently converge on the same load-bearing gaps in the typed-finding classification machinery, and claude-p explicitly marks one of them a must-fix "before plan." The two reviews are complementary, not contradictory: codex approaches the decision-rule gap from "needs numeric thresholds," claude-p from "needs a fourth outcome branch and a precedence order" — both point at the same underspecified AC5/AC1 machinery. Recommend revising the spec to close the three consensus items below, then proceeding directly to `/plan` — a second review round is not required unless the revision itself opens new questions (e.g., a genuinely new AC or scope change).

### Consensus concerns (must address)

1. **Typed-finding decision rule is under-specified and needs both numeric bands and a benchmark-unfit branch.** codex wants concrete thresholds/bands for file-level acc, span-level acc, empty-rate, and file-minus-span gap so two implementers with the same counts reach the same conclusion. claude-p wants a fourth outcome (BENCHMARK_UNREPRESENTATIVE / INCONCLUSIVE) or an explicit AC6-gates-AC5 routing, so that a benchmark-unfit finding from AC6/OQ3 isn't forced into one of three finder-indicting labels. These are complementary requirements on the same rule and should be resolved together: add thresholds AND the additional branch/gating.
2. **The finding taxonomy is not actually MECE as specified.** claude-p identifies concrete oracle-contradicting boundary cases (path-only/line-less citations under `span_hit_kind`/`span_hit_primary`, the within-window-but-non-overlapping zone, and multi-citation any/any ambiguity requiring a stated precedence order CORRECT > RIGHT_FILE_WRONG_SPAN > WRONG_FILE > EMPTY). codex independently asks for an explicit EMPTY vs WRONG_FILE citation-normalization rule (malformed citations, file-level citations, partial paths, suffix-dropped citations). Both are the same underlying gap: define citation normalization + a precedence/tie-break order before classification can be called MECE.
3. **The query-reformulation probe must be decided now, not left open.** Both reviewers flag that leaving this an open question undermines consistent interpretation of the core diagnosis (retrieval failure vs long-query parsing failure). Decide in this spec: include as a labeled non-primary measurement, or explicitly defer with rationale.

### Single-reviewer concerns (consider)

- Turns-used source for AC4 is unstated; if not already emitted per-case, capture it at the eval boundary (à la 0021's `_wrap_timed`) rather than reaching into frozen Scout/FastContext internals. (claude-p)
- Name the stratification dimension in AC3 (by repo? gold-span size? classification?). (claude-p)
- Pin the proximity window value explicitly (reuse EvalConfig's existing secondary-metric `window`) so window-boundary cases (e.g., astropy separable.py ~140-line gap) are unambiguous. (claude-p)
- Suffix-recovery hit/drop needs its denominator, data source, and how-unavailable is represented. (codex)
- State the expected prior as a falsifiable pre-registration (e.g., 0021's ~33/38 EMPTY + astropy RIGHT_FILE_WRONG_SPAN pre-registers RETRIEVAL_FUNDAMENTAL). (claude-p)
- Require raw per-case rows + aggregate counts so the distribution is auditable/reusable. (codex)
- Add an AC confirming no changes under Scout/orchestrator/gate/tiers/matrix/judge (diagnosis-not-fix boundary). (codex)

### Guardrail/convention violations

None material. One convention tension flagged: the MECE finding-taxonomy convention (measurement-not-construction conventions) is asserted by AC1/AC5 but not satisfied given the unassigned boundary cases and the AC6-outcome the enum can't express (claude-p). This is folded into consensus item 2 above and should be resolved as part of the revision rather than treated as a standalone guardrail breach.

### Revision log

Revised 2026-07-04 (same review round; all three consensus items closed → status `reviewed`).
Two acceptance-surface decisions taken by the developer via AskUserQuestion.

- [x] **Item 1 — typed-finding decision rule (thresholds + benchmark-unfit branch).**
  Added a **4th branch `BENCHMARK_UNREPRESENTATIVE`** (developer's choice over
  AC5-gated-by-AC6) and a **pre-declared, ordered decision rule** over `F` (file-level
  acc), `S` (span-level acc), `E` (empty-rate), `G = F − S`, and the probe `Δempty`
  (spec §"The typed-finding decision rule", AC7). Bands are provisional; the per-case
  rows (AC8) are the auditable ground truth. **Key interaction the developer named:**
  the probe is the *discriminator* between `BENCHMARK_UNREPRESENTATIVE` (distilled
  query cuts empty-rate → query-shape) and `RETRIEVAL_FUNDAMENTAL` (`Δempty ≈ 0` →
  finder capability) — the 4th branch is only diagnosable *because* the probe is
  in-scope.
- [x] **Item 2 — MECE taxonomy (citation normalization + precedence).** Added a
  §"Citation normalization" (suffix-recovery applied first; malformed → counted
  `normalization_dropped`, never silent `EMPTY`/`WRONG_FILE`; file-level shape
  retained) and a strict per-case precedence `CORRECT > RIGHT_FILE_WRONG_SPAN >
  WRONG_FILE > EMPTY` (AC1). The oracle boundary claude-p flagged is resolved by an
  **explicit, scored re-map**: a path-only right-file citation (`span_hit_kind ==
  "file"`) → `RIGHT_FILE_WRONG_SPAN`, not `CORRECT`; within-window non-overlapping →
  `RIGHT_FILE_WRONG_SPAN` + `within_window` sub-flag. Re-map lives in the additive
  eval classifier, never touches `metrics.py`. (AC1/AC3.)
- [x] **Item 3 — query-reformulation probe.** **Included** as a labeled non-primary
  probe (AC6), kept out of the baseline distribution. Rationale: it is the Item-1
  discriminator; deferring it would make the 4th branch undiagnosable.

Also addressed (consider items): turns-used captured at the **eval boundary** (AC5,
no frozen-internals reach); stratification named **by repo × gold-span-size band**
(AC4); proximity window pinned to **`EvalConfig.proximity_window_lines = 50`**;
`normalization_dropped` denominator defined; **pre-registered prior**
(`RETRIEVAL_FUNDAMENTAL` unless the probe fires) as a falsifiability guard (OQ2);
**raw per-case rows + aggregates** required (AC8); **no-SUT-change guard** (AC10).
