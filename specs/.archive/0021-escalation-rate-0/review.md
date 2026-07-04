# Review — Spec 0021 (escalation_rate=0)

Round 1 · 2 aux reviewers (codex, claude-p) + author verification.

## Verdicts

| Reviewer | Verdict |
|----------|---------|
| codex    | changes-requested |
| claude-p | approve-with-comments |
| **Synthesis** | **changes-requested** — quorum (1 approve-with-comments) is technically met, but two concerns were **verified true by the author** and are load-bearing, not cosmetic. |

## Load-bearing concerns (both raised; author-verified)

### C1 — The primary data source may not exist (claude-p; VERIFIED)
The spec's cheapness rests on "resolve from the existing 0020 partial dump + per-case
trajectory/timing." Author check: `eval_work/reports/oq2_fast/` and `oq2_incumbent/` are
**empty** (`total 0`); only `oq2_smoke/sweep.json` (13 KB) survives. The quoted secondary
figures (`span_hit_rate_primary=0.2`, `wrong_tier1_count=5`, `gate_catch_rate`) appear
**nowhere** in the committed `specs/.archive/0020-oq2/` — only `escalation_rate=0.0` and ~3.3h
are recalled, and those live in the session transcript, not on disk. `eval_work/` is gitignored
/ machine-local. **Consequence:** the TIME-ATTRIBUTION deliverable (Q1 / AC3) may have no
persisted per-case timing to attribute; a ≤2-case micro-run can only *extrapolate* a 38-case
wall-clock split, not reconstruct it. Also: persisted timing is case-level `latency_ms`
(`runner.py:190,213`), **not** the per-tier (Scout/judge/Deep) granularity AC3 asks for — that
granularity only exists in the micro-run's new instrumentation.

### C2 — The finding taxonomy (AC4) is not MECE (both reviewers; VERIFIED gap)
- codex: `GATE_FALSE_ACCEPTANCE` is **not an alternative** to `CORRECT_NO_ESCALATION` — it is
  one *explanation under* it (gate accepts 5 wrong → Deep never runs → rate correctly 0). The
  finding conflates two orthogonal axes: **escalation accounting** vs **wrong-citation fate**.
- claude-p: a fourth, live-plausible branch is missing — **escalation suppressed by
  degradation**. Author check: `runner.py:74-78` has `_is_deep_degraded` /
  `deep-degraded:<cause>`; spec 0020 **OOM'd `qwen3-coder:30b`** on this host (memory:
  Q8 Deep OOMs on 16 GB). "Deep never ran because it *couldn't*" yields `escalation_rate=0`
  with a gate that correctly *rejected* — no home in the current three-way enum, and exactly
  the honest-degradation outcome the graceful-degradation guardrail cares about.

## Minor concerns (agreed; apply directly)

- **M1 — packages scope.** Frontmatter `packages: [harpyja/eval, harpyja/orchestrator]` reads
  like permission to edit SUT routing/gate. State that `harpyja/orchestrator` is **read-only
  reference**, touched only under the proven-accounting-bug exception (frozen-SUT invariant).
  *(convention violation flagged by both.)*
- **M2 — AC2 jargon.** AC2 says "per the Wave-5 ladder / three-way split" without citing the
  single source of truth. Cite `harpyja/orchestrator/matrix.py plan_ladder` (the table tests
  read), per the routing-matrix convention. *(convention violation flagged by both.)*
- **M3 — AC1 overlap.** `tiers_run↔escalation_rate` may overlap existing `test_metrics.py`
  coverage — extend / point at those; the novel assertion is the **coupling**, not
  `escalation_rate` itself.

## Guardrail violations
None.

## Action
Revise the spec on C1 (feasibility precondition + honest AC3 downgrade) and C2 (MECE
taxonomy), apply M1–M3, then proceed. Both reviewers agree the investigation itself is sound
and consistent with the 0019/0020 measurement lineage — this is a scoping/taxonomy tightening,
not a rethink.

## Revisions applied (round 1 → reviewed)
- **C1** — Added a **feasibility precondition** to `## What` (path the dump before planning;
  if absent, AC3 downgrades to a **labeled estimate** from the micro-run × 38 cases, never a
  fabricated recorded 3.3h split). Noted the case-level-`latency_ms`-only granularity gap.
  Tracked as Open Question 2. *(user decision: precondition + honest downgrade.)*
- **C2** — AC4 restructured to a **two-dimensional MECE finding**: `accounting ∈
  {ACCOUNTING_BUG, CORRECT_NO_ESCALATION}` × `wrong_citation_fate ∈ {GATE_FALSE_ACCEPTANCE,
  NO_ESCALATION_PATH, DEEP_DEGRADED_OR_UNAVAILABLE, NOT_APPLICABLE}`. Resolves codex's overlap
  and claude-p's missing degradation branch together. Q3 (`gate-false-acceptance ⇒ DEFERRED?`)
  reworded to the new axis. *(user decision: two-dimensional.)*
- **M1** — `packages` narrowed to `[harpyja/eval]`; added Out-of-scope line: orchestrator is
  read-only reference, any accounting fix lands in the eval metric layer.
- **M2** — AC2 now derives expectations from `harpyja/orchestrator/matrix.py plan_ladder`
  explicitly (the table the test reads), and the degradation-suppressed branch is a first-class
  trigger case.
- **M3** — AC1 reworded: the novel assertion is the **coupling**; extend existing
  `test_metrics.py` rather than duplicate.

**Status → `reviewed`.** Quorum met (claude-p: approve-with-comments); codex's
changes-requested items all incorporated above.
