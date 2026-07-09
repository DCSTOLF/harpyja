---
spec: "0031-live"
reviewers: [codex, claude-p]
quorum: 1
verdict: approve-with-comments
generated: 2026-07-08T00:00:00Z
---

# Cross-model review — 0031-live (amended spec, final round)

## Executive summary

**Quorum MET.** Both Codex and Claude-p independently code-verified the amended spec against the current repository state and both return `approve-with-comments`. Neither reviewer reports a reject or a blocking finding this round. This resolves the prior round's disagreement: the amendment removed the false "ALREADY EMITS" claim that Claude-p's code inspection had shown to be factually incorrect, and both reviewers now confirm the spec's Implementation section accurately states what must be newly built (trajectory capture in `explorer_backend.py`, model extraction in `gateway.py`), and that the Out-of-scope/Implementation contradiction from the prior round is reconciled. Recommendation: proceed to `/speccraft:spec:plan`.

## Codex review

**Verdict:** approve-with-comments

Concerns:
- Line-number citation imprecision: the Implementation section cites `explorer_backend.py:269` for the point where `LoopResult.history` is discarded, but the actual line in the current source is 273.
- The new capture seams (trajectory capture in `explorer_backend.py`, model extraction in `gateway.py`) are validated end-to-end via AC6's integration re-run, not by isolated unit tests of the seams themselves.
- OQ1 (model-identity fallback design — whether `response['model']` is reliably present, and how to branch on `model-mismatch` vs `model-unknown`) is deferred to planning rather than resolved in the spec itself.

Suggestions:
- No changes required beyond the concerns above; no blocking issues identified. The prior round's blocking contradiction (the false "ALREADY EMITS" claim) has been removed, and the Implementation section now correctly states that trajectory capture and model extraction must be newly built rather than presumed to already exist.

## Claude-p review

**Verdict:** approve-with-comments

Concerns:
- Same line-number citation imprecision (269 vs. actual 273), independently observed via direct code inspection.
- Same observation that the capture seams are tested end-to-end via AC6 rather than as isolated unit tests — judged acceptable given the spec's own instrument-proving structure (acceptance is met by proving the four assertions fire on constructed pass/fail runs), but noted for the record.
- OQ1's deferral of fallback design to planning is acceptable per the spec's own structure (Open Questions are explicitly scoped for planning-phase resolution), but flagged as an item to track rather than a spec defect.

Suggestions:
- During planning, confirm AC2's fixture coverage explicitly exercises all three OQ1 branches (model present and matching, model present and mismatched, model absent/unknown) rather than only the mismatch case.
- No changes required to the spec text itself; the amendment fully reconciles the Out-of-scope/Implementation contradiction flagged in the prior review round (the prior round's premise that the trajectory data "ALREADY EMITS" durably has been corrected — the spec now states this must be built, and the Out-of-scope section now explicitly carves out the necessary read-only capture seams as in-scope measurement plumbing).

## Synthesis

Both reviewers independently code-verified the amended spec against the current repository state and reached the same verdict for the same reasons — a stronger convergence signal than either verdict alone, since it was arrived at via independent inspection rather than shared assumption.

**What changed since the prior round, confirmed by both reviewers:**
- The blocking contradiction that produced last round's `changes-requested` — the spec's false claim that the explorer loop "ALREADY EMITS a durable per-turn trajectory record" — has been removed. The Implementation section now accurately states that trajectory capture (in `explorer_backend.py`) and model extraction (in `gateway.py`'s `complete_with_tools`) are NEW capture seams that must be built, not existing behavior.
- The previously-flagged contradiction between "Out of scope" (forbidding Scout/gateway behavior changes) and "Implementation" (requiring changes to those same files) is reconciled: the spec now explicitly carves out "read-only capture seams... that do not change any decision behavior" as in-scope measurement plumbing, distinct from the out-of-scope decision-logic changes it still forbids.
- The remaining open items — OQ1's model-identity fallback design, precedence when multiple facts are simultaneously unprovable, and the exact unit-test design for the new capture seams — are appropriately left as planning-level decisions rather than spec-blocking gaps, consistent with the spec's own Open Questions structure.

**Minor concerns raised by both reviewers (non-blocking):**
1. A citation imprecision: the Implementation section references `explorer_backend.py:269` for the history-discard point, while the current source has this at line 273. This is a documentation nit, not a substantive spec defect, and should be corrected for accuracy but does not block planning.
2. The new capture seams are validated only at integration granularity (via AC6's proof-of-instrument re-run against 0030's astropy/django cases), not via isolated unit tests of the seams themselves. Both reviewers judge this acceptable given the spec's own INVARIANT that acceptance is met by proving the four assertions fire on constructed pass/fail runs, but flag it as worth tracking into the plan phase.
3. OQ1 (model-identity capture and fallback design) is explicitly and appropriately deferred to planning per the spec's own Open Questions section — both reviewers treat this as a legitimate planning-phase decision, not a spec gap requiring another revision round.

There is no disagreement between the two reviewers this round on scope, correctness, or readiness. No guardrail or convention violations were reported by either reviewer.

**Action:** Quorum is MET (2 of 2 reviewers approve-with-comments, no rejects). The spec is ready to proceed to `/speccraft:spec:plan`. Before or during planning, address the two minor housekeeping items surfaced by both reviewers: (1) correct the `explorer_backend.py:269` citation to the accurate line (273) in the spec's Implementation section, and (2) ensure the plan explicitly resolves OQ1's three fallback branches (model present/matching, present/mismatched, absent/unknown) with corresponding AC2 fixture coverage, and decide whether capture-seam unit tests are needed in addition to AC6's integration-level proof.
