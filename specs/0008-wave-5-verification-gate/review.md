---
spec: "0008"
title: "Wave 5 — Verification Gate + Auto-Escalation"
review-date: 2026-06-27
reviewers: [codex, claude-p]
quorum: 1
verdict: approve-with-comments
rounds: 3
generated: 2026-06-27
---

# Cross-model review — 0008

Three rounds. Each round = `codex` (gpt-5.5 via Codex CLI) + `claude-p`, both
given the spec + `.speccraft/` guardrails / conventions / architecture.

| round | codex | claude-p | outcome |
|-------|-------|----------|---------|
| rev 1 | changes-requested | changes-requested | revised |
| rev 2 | changes-requested | approve-with-comments | revised |
| rev 3 | approve-with-comments | approve-with-comments | **quorum met → reviewed** |

## Synthesized verdict

**approve-with-comments — quorum met** (review_quorum = 1; two
approve-with-comments in rev 3). Spec advanced `draft → reviewed`. All rev-3
comments were folded in before marking reviewed (see "Round 3"); the only
remaining open item is provisional-default tuning (OQ2), an eval-time task, not a
spec blocker.

## Round 1 — consensus blocking issues (both agents)

1. **Air-gap not pinned for the gate's scoring call** *(guardrail)* — the wave
   introduces the first per-request gate model call; the backend must assert
   loopback before egress + a network-deny AC (Scout 0007 / Deep 0006 pattern).
   → **fixed** (B1; routed through `ModelGateway.complete()`).
2. **Planning matrix declared source-of-truth but rows never enumerated** —
   `3×2×2 = 12` rows, AC3 unverifiable. → **fixed** (B2; full table inlined).
3. **New flags were free prose, not stable identifiers** *(convention)* →
   **fixed** (B3; `gate-low-confidence` / `gate-scoring-failed` /
   `gate-skipped:scout-empty`, asserted by id in AC9).

Round-1 single-agent issues (all fixed in rev 2):
- empty/missing-Tier-1 escalation contradicted AC8 honest-empty → **three-way
  split** (typed-unavailable degrade / honest-empty no-climb / malformed escalate).
- `ambiguous → point` (classifier) vs AC10 "broad/ambiguous climbs" → ambiguous
  follows point; only `broad` routes to Deep.
- `broad`+`fast` unresolved → **fast wins** (explicit cost ceiling).
- `index_ready` dimension undefined → described in prose; `false` rows skip the
  Tier-0 seed (query-only), enumerated in the 12 rows.
- freeze-gate made explicit (ACs freeze post-OQ1; OQ2 provisional).

## Round 2 — comments (both verdicts), resolved in rev 3

- **`gate-scoring-failed` contract was contradictory** across five authorities
  (both agents) — best-effort vs escalate. → **pinned**: in `auto` it escalates
  to `[0,1,2]`/`[1,2]` (flag retained as diagnostic, `confidence=low`); in `fast`
  it returns best-effort un-gated Tier-1 + flag. Aligned across the matrix,
  escalation bullets, VerificationGate, AC8, and Degradation.
- **`verify_method` inert values** (claude-p; ties to the standing
  no-false-capability rule) — unsupported values must reject loudly, not silently
  fall back. → **fixed** (AC13; loud typed rejection at `Settings` load).
- **Gate outbound path** (claude-p) — clarify it routes through
  `ModelGateway.complete()` (the only outbound caller), with `assert_local` as
  belt-and-suspenders, *not* the third-party-owns-client pattern. → **fixed**.
- **Confidence map incomplete** (claude-p) → **fixed**: full path→level table.
- **`index_ready=false` realized prefix unasserted** (claude-p) → **fixed** (AC1
  asserts `[1]` / `[1,2]`).
- **AC12 "climbs" vs broad routes-straight** (claude-p) → **fixed** ("routes").

## Round 3 — comments, resolved before marking reviewed

- **New collision introduced by the rev-2 edits** (claude-p, genuine catch):
  honest-empty realized the same `[0,1]`/`[1]` tokens as a gated-pass with no
  distinguishing flag, yet the confidence table mapped those to `high` — a
  "nothing found" result reading as high confidence (no-false-capability). →
  **fixed**: added the `gate-skipped:scout-empty` marker + a distinct confidence
  row (`medium`/`low`); AC9 asserts the honest-empty case separately.
- **AC8 missing `[1,2]` for the no-seed gate-scoring-failure path** (codex) →
  **fixed**.
- **`auto`-at-ceiling gate-scoring-failed branch effectively unreachable**
  (claude-p) → clarified the no-further-tier branch is the `fast` path in
  practice (in `auto` the gate fires only at `1→2`, where Tier-2 always remains).

## Strengths both reviewers noted

- The deliberate **invariant break** (retire the Wave-0 zero-call lock, replace
  with explicit AC1 **in lockstep**) closes the unspecified-window risk by
  construction.
- The **empty-case three-way split** mirrors the codebase's entrenched
  typed-failure-vs-honest-result convention exactly.
- **OQ1↔OQ3 coupling** framed correctly: a generative `scout_model` judge is
  affordable on the hot path *because* the scan is bounded top-N — one causal
  decision, not two independent ones.
- Degradation discipline intact; air-gap routed through the single helper.

## Open / deferred (non-blocking)

- **OQ2** — `verify_threshold` (`0.6`) and `verify_top_n` (`3`) ship provisional;
  tune against the eval repo during/after planning. Does not block the freeze
  (ACs assert thresholding *behavior*, not the numeric default).

## Recommended next step

`/speccraft:spec:plan` — turn the reviewed spec into a test-first plan. Carry the
provisional `0.6` / `3` defaults as a tuning task against the eval repo.
