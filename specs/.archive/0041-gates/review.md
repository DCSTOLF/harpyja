---
spec: "0041-gates"
reviewers: [codex, claude-p]
quorum: 1 (approve or approve-with-comments)
verdict: approve-with-comments (quorum-met)
round: 2
generated: 2026-07-11T00:00:00Z
---

# Cross-model review — 0041-gates (round 2)

**Quorum status: MET.** codex returned `changes-requested`, claude-p returned `approve-with-comments`. Per the quorum config (1 approve or approve-with-comments required), the spec CLEARS review. Overall verdict: **approve-with-comments**. The spec advances to `status: reviewed`.

This is round 2. Round 1 (`review.round1.md`) ended `changes-requested` from both agents (quorum NOT met) with a 13-item checklist. This round evaluates the revision against that checklist.

## codex

**Verdict:** changes-requested

Concerns:
- Same-model contention still not pinned: the foreign-resident predicate correctly catches unconfigured tags, but a concurrent process using a CONFIGURED model tag still queues on the serial Ollama endpoint, and the spec doesn't define a reliable in-flight/non-idle signal or how `/api/ps` is supposed to prove it.
- Per-block suspect-boundary wording is internally ambiguous: AC2 says cells since the previous clean check are suspect, but also says blocks 1..N-1 retain clean-check records — readable as "all prior cells remain clean" rather than the intended boundary-granularity rule.
- The live opt-in consumer is improved but still abstract; the spec should name the exact executable command or preflight assertion shape rather than describing it generically.

Suggestions:
- Define the endpoint-idle check precisely, including whether `/api/ps` can observe active/queued same-model work; if it cannot, narrow the exclusivity claim or require a lease/lock for same-model contention specifically.
- State the contamination-boundary rule with an explicit worked example (clean before block N-1, fail before block N → block N never runs, block N-1 is suspect).
- Pin the opt-in test command / driver assertion (marker expression or flag) concretely.

Guardrail violations: none. Convention violations: none.

Discussion: the revision resolves all major round-1 blockers — canonical frontmatter, exclusivity overclaim, recorded (not first-only) checks, a named ledger target, version-gating, driver-scoped bounded residency, probe-first discipline, the byte-identical SUT pin preserved verbatim, residual gaps named, a typed stop replacing "STOP-AND-WARN," `assert_local` routing, and an enforced opt-in consumer. The remaining blocker is narrower and structural: exclusivity is framed as endpoint exclusivity, but the pinned predicate is model-SET residency (foreign tag detection). Same-tag traffic — a client using a model already in the frozen set — is just as contaminating as foreign-tag traffic and is invisible to that predicate. If `/api/ps` genuinely cannot distinguish idle-resident from actively-serving/queued for a configured tag, the spec needs either a stronger mechanism (lease/lock for same-tag contention) or an honest narrowing of the claim. "Once those are tightened, this looks approvable."

## claude-p

**Verdict:** approve-with-comments

Concerns:
- Exclusivity evidence source is weaker than the claim it backs: `/api/ps` lists loaded models, not queued/in-flight requests. Same-tag contention (a client using a tag already IN the frozen set) is invisible to both the start check and the per-block re-check. AC1's "non-idle endpoint" phrasing may not be mechanically checkable from `/api/ps` at all — the 0040 incident was only catchable because the suite happened to touch OTHER tags; a same-tag-only contamination would have sailed through this gate unchanged.
- Resume semantics for "suspect" cells are unstated: suspect is neither clean nor typed-degrade, and the interaction with `_cell_needs_run` and the resumable ledger needs one sentence — is suspect a third branch (invalidate-and-archive, re-run only after a subsequent clean gate check)?
- AC8's "no NEW timeout degrades attributable to reload churn" lacks an operationalized attribution criterion — as written it reads as a close-time judgment call rather than a checkable condition.
- Block-granularity suspect typing amends the 0040 "run granularity" invalidation convention but doesn't say so explicitly; AC9 should name the amendment (run-granularity when no per-check records exist, boundary-granularity when they do).
- AC6's enforced consumer is still mechanically vague — name the actual mechanism (e.g., `pytest --collect-only -m integration` with the opt-in flag, asserting non-zero selection).

Suggestions:
- Pin what `/api/ps` actually exposes as part of the residency probe (or a sibling probe), and extend `exclusivity_check_kind` semantics to name same-tag / non-resident-visible traffic as a second named residual alongside the existing intra-block-window residual.
- State the suspect-cell resume disposition explicitly as a third `_cell_needs_run` branch.
- Operationalize AC8's attribution criterion (e.g., compare the typed-degrade set against the 0040 clean-run degrade profile on the pinned case set, and/or record an observed-reload marker via an `expires_at` reset immediately before a degrading cell).
- Add one line to AC9 amending the run-granularity convention explicitly.
- Name the AC6 mechanism concretely.

Guardrail violations: none. Convention violations: none.

Discussion: round-1 resolution is substantively complete — every checklist item landed, including the hardest one (the `keep_alive` seam collision resolved by the strongest available move: driver-side native API, with the 0034/0038 byte-identical SUT pin surviving verbatim). Probe-first discipline is honored correctly; exclusivity strength/labeling is now correct as far as the foreign-resident predicate goes; the artifact target and version-gating are correct. The one substantive NEW gap is the `/api/ps` blind spot on same-tag contention — the spec's own epistemic-labeling invariant requires naming what a check cannot see, so this needs either a named second residual (same-tag / non-resident-visible traffic) or the "in-flight work" phrase needs to be dropped/verified rather than asserted. Suspect-cell resume disposition is the other pre-plan item. Everything else raised is precision, not direction. "Approve with the comments above; the `/api/ps` capability check and the suspect-cell disposition are the two I'd want addressed in the spec text before `/speccraft:spec:plan`."

## Round-1 resolution summary

Both agents independently confirm the full round-1 checklist landed:

- Frontmatter now canonical (`started_at_sha` present, non-canonical keys resolved).
- Exclusivity overclaim fixed: recorded at actual strength (`exclusivity_check_kind: start-plus-per-block`), every check retained with timestamp, not just the first.
- "Foreign resident" predicate pinned precisely (not in the frozen run config's model set); driver's own block-loaded models don't self-trigger.
- Mid-run race case (AC2) has acceptance coverage.
- Artifact target named explicitly (run-level driver ledgers, `PoolPilotLedger` family and successors — not the per-case verifier artifact) and version-gating applied correctly (additive, new-version-required, legacy validates unchanged).
- `keep_alive`/residency seam resolved at the driver via the native API (the seam where `_evict_other_models` already lives) — never touching the SUT's `/v1` request body. This is called out by both agents as the strongest available resolution to the round-1 sent≠honored and SUT-boundary-collision findings.
- Probe-first discipline honored: mechanism choice (native touch vs. eviction-only) is conditional on a committed, schema-versioned, spec-local typed-outcome probe, not asserted in advance.
- The pinned 0034/0038 byte-identical invariant (`explorer_think=None ⇒ params == {max_tokens: 2048}`) survives verbatim, regression-asserted — no supersession.
- Residual gaps named explicitly in the What section (Deep's `RlmBackend`, stray non-driver/live-test traffic) rather than left implicit.
- Typed stop (`exclusive-endpoint-contended`) replaces the round-1 "STOP-AND-WARN" phrasing, consistent with "refuse, don't warn."
- `/api/ps` routed behind `gateway.assert_local` (the 0019 preflight rule), stated explicitly in the What.
- AC6 gives the deselect-default an enforced opt-in consumer (operator drivers assert the opt-in path / `require_live_stack`), not documentation-only.
- AC1's "no bypass parameter" claim pinned mechanically (signature introspection, 0039 `run_ab_paired` precedent).

Neither agent found any of the round-1 items unresolved.

## Convergent remaining finding (both agents, independently)

**The `/api/ps` same-tag contention blind spot.** Both agents arrive at essentially the same diagnosis from different angles:

- codex frames it as a race/mechanism gap: the pinned predicate only catches FOREIGN tags (not in the frozen model set); a concurrent process using a tag ALREADY IN the frozen set is invisible to both the start check and the per-block re-check, and still queues on Ollama's serial endpoint exactly as in the 0040 incident.
- claude-p frames it as an epistemic-labeling gap: `/api/ps` reports resident models, not queued/in-flight requests, so AC1's "non-idle endpoint" language may not be mechanically checkable at all for same-tag traffic — and notes the 0040 incident was only catchable because the contaminating suite happened to touch OTHER tags, meaning a same-tag-only repeat of 0040 would pass this gate silently.

Both agents converge on the same two resolution paths: (1) narrow the exclusivity claim honestly — name same-tag/non-resident-visible contention as a second named residual in `exclusivity_check_kind` semantics, alongside the already-named intra-block-window residual, or (2) strengthen the mechanism for the same-tag case specifically (e.g., a lease/lock), since `/api/ps` alone cannot prove it. This is spec-text precision work, not a redesign — the decided architecture (start + per-block `/api/ps`, foreign-resident predicate, declined lease/lock for the general case) stands; what's missing is either an honest label or a narrower mechanism for the one case the current predicate structurally cannot see.

## Unique findings (raised by one agent only)

From codex (not raised by claude-p):
- The per-block suspect-boundary wording in AC2 is internally ambiguous and could be misread as "all prior cells remain clean" rather than boundary-granularity suspect typing. Fix: one worked example in the spec text (clean before N-1, fail before N → N not run, N-1 suspect).
- The opt-in live-test consumer, while now enforced in principle (AC6), is still described abstractly; name the exact command/assertion shape.

From claude-p (not raised by codex):
- Suspect-cell resume disposition is unstated — how does "suspect" interact with `_cell_needs_run` and the resumable ledger? Proposed as a third branch alongside clean and typed-degrade.
- AC8's reload-churn attribution criterion ("no NEW timeout degrades attributable to reload churn") is not operationalized — reads as a judgment call rather than a checkable condition. Proposed fix: compare against the 0040 clean-run degrade profile, and/or an observed-reload marker via `expires_at` reset.
- AC9 doesn't explicitly name that block-granularity suspect typing amends the 0040 run-granularity invalidation convention.
- AC6's mechanism, though now enforced, isn't named concretely (e.g. `pytest --collect-only -m integration` with opt-in flag asserting non-zero selection) — this overlaps with codex's "name the exact executable consumer" point but is phrased as a convention-amendment naming gap rather than an abstraction gap.

No disagreements were found between the two agents on substance. Where their concerns overlap (the `/api/ps` blind spot), they reinforce each other; where they diverge, the findings are complementary precision items on different parts of the spec text.

## Pre-plan precision-fixes checklist

Recommended before running `/speccraft:spec:plan` (spec-text precision, not redesign). **ALL SIX APPLIED to spec.md immediately post-quorum, same session (2026-07-11):**

- [x] Resolve the `/api/ps` same-tag contention blind spot — resolved by honest narrowing (path 1): the invariant and What now state `/api/ps` exposes residents + `expires_at` (not queued/in-flight requests), the gate checks and claims RESIDENT-SET exclusivity, and `exclusivity_check_kind` semantics name TWO unseeable residuals — (a) the intra-block window, (b) same-tag contention (carried by the deselect default + single-operator context, stated in the artifact). "Non-idle endpoint" phrasing removed from AC1.
- [x] Worked example added to the What and AC2 (clean before N−1, fail before N → N never runs, N−1's cells suspect, 1..N−2 valid under their own recorded clean checks).
- [x] Suspect-cell resume disposition stated as an explicit third `_cell_needs_run` branch (invalidate-and-archive, the 0040 posture; re-runnable only after a subsequent clean gate check; clean never re-runs, typed degrades keep exactly one bounded re-run) — in the What and AC2.
- [x] AC8's reload-churn attribution operationalized: per-case typed-degrade set compared against the 0040 clean-run profile on shared pinned cases, plus an observed-reload marker (`expires_at` reset since the previous cell) required for a NEW degrade to count as churn-attributable.
- [x] AC6 consumer named concretely: driver preflight runs `pytest --collect-only` with the opt-in selection, asserts non-zero live-marked collection (and zero under default).
- [x] AC9 now explicitly AMENDS the 0040 run-granularity invalidation convention: run-granularity when no per-check records exist, boundary-granularity when they do — same outcome-blind criterion, never per-suspicious-cell.

## Synthesis

Round 2 clears quorum: claude-p's `approve-with-comments` satisfies the 1-approve threshold even though codex remains at `changes-requested`. Per the quorum rule this is a legitimate pass, not a split decision requiring further arbitration — but it is not a clean approval either, since both agents, independently and by different routes, land on the same substantive gap: the exclusivity gate's `/api/ps`-based predicate proves foreign-tag residency but cannot see same-tag contention, which is precisely the shape of risk this spec exists to close (0040's incident). That convergence is a stronger signal than either agent's solo concerns and should be treated as the priority item, alongside claude-p's suspect-cell resume-disposition gap. The remaining items (AC2 wording, AC8 attribution, AC6/AC9 naming) are lower-priority precision fixes that do not block advancing the spec but should land in spec text before `/speccraft:spec:plan` so the planning phase inherits an unambiguous contract.

**Action:** Spec advances to `status: reviewed` (quorum met). Before `/speccraft:spec:plan`, apply the six-item pre-plan precision-fixes checklist above as direct spec-text edits — these are clarifications and honest-labeling fixes to the already-decided architecture, not a new design round. Priority: (1) the `/api/ps` same-tag blind spot (both agents, convergent, most load-bearing), (2) suspect-cell resume disposition (claude-p), (3) the AC2 worked example (codex), (4–6) AC8/AC6/AC9 naming precision (claude-p/codex, lower priority).
