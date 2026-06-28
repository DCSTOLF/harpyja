---
id: "0009"
title: "6a"
status: closed
created: 2026-06-27
authors: [claude]
packages: []
related-specs: ["0008"]
---

# Spec 0009 — Wave 6a — Eval harness + OQ2 calibration

## Why

All three tiers and `mode=auto` are live and unit-green, but the design's core
claims — escalation rate stays low, the gate catches wrong Tier-1 citations, the
`scout_model` judge + `top_n=3` hold up — are unfalsified. No instrument measures
locate accuracy on a real legacy tree. This harness provides it, and OQ2
(`verify_threshold=0.6` / `verify_top_n=3`, provisional since spec 0008) is
calibrated as a byproduct of running it.

Ref: `IMPLEMENTATION_PLAN.md` Wave 6 (accuracy harness); `history.md` 0008 (gate +
matrix).

**INVARIANT (measurement only, recommend-only):** No change to tier internals,
orchestrator, gate, or matrix behavior. The harness observes; it does not modify
the system under test. This wave emits a **recommendation** — the OQ2 trade-off
table and a recommended `(verify_threshold, verify_top_n)` — and **does not flip
any `Settings` default**. The actual default change is a one-line follow-up spec
that cites this wave's evidence, so "measurement only, no behavior change" stays
literally true here. (B1)

Eval-only knobs (the repeated-run count `K` (B4), proximity window, N-floor,
catch-rate bar) live on a **dedicated `EvalConfig` dataclass in `harpyja/eval/`,
not on the production frozen `Settings`** — they are inert to every tier/gate/matrix
branch and never reach the system under test (decided at plan time; see plan.md
"Design decisions"). The *only* `Settings` interaction is the sweep building grid
points via `dataclasses.replace` on the real `verify_threshold` / `verify_top_n`
fields, never mutation.

## Resolved decisions (formerly open questions)

These are frozen before planning; they cascade into the ACs.

- **D1 — Eval repo source (was OQ1):** a **vendored OSS legacy repo with
  hand-labeled expected spans**. This measures real retrieval difficulty rather
  than labeling intuition. The repo is vendored at a pinned revision; expected
  spans are authored by hand and version-controlled with the fixture. (B3)
- **D2 — Span-hit definition (was OQ2-span):** **line-range overlap is the primary
  metric**; **file-level + proximity is a secondary, looser metric** reported
  alongside it. A "hit" for the headline accuracy number means the cited span's
  line range overlaps an expected span's line range in the same file; the
  secondary metric credits a same-file citation within a proximity window even
  without line overlap. (B3)
- **D3 — Gate oracle (B5):** "correct vs wrong Tier-1" is defined by **expected-span
  overlap** — the *same* line-range span-hit metric from D2, evaluated against the
  case's labeled expected span(s). This single oracle definition is stated once and
  reused by **both** the gate catch-rate and the false-escalation metrics; there is
  no second notion of correctness.

## What

- **Eval dataset format:** per-case `{query, repo, expected file:line span(s),
  classification label}`. Stored as a versioned fixture (the D1 vendored repo +
  hand-labeled spans); ships with a small seed set + a documented "add a case"
  path.
- **Metrics:** locate accuracy (span-hit per D2 — primary line-overlap, secondary
  file+proximity), escalation rate (% auto queries reaching Tier-2), Tier-0/1
  resolve rate, per-tier latency + model-call count, and — via the **single D3
  oracle** — gate catch rate (wrong Tier-1 → escalated) and gate false-escalation
  rate (correct Tier-1 → wrongly escalated).
- **Runner:** executes a case set through the real `mode=auto` path, emits a JSON +
  human report conforming to a **pinned schema** (stable field names for per-case
  events and aggregate metrics). Report artifacts are written to a temp/output
  directory **outside any indexed/target repo** (read-only guardrail; mirrors the
  FastContext `trajectory_file` precedent). Offline/air-gap respected (local stack
  only). Non-determinism is **controlled, not just surfaced** (see repeated runs).
- **Repeated runs (B4):** each measured configuration runs `K` times (`K` the
  additive eval-only `Settings` field); the report carries **mean + spread** per
  metric, not a single shot. A configuration is only recommended over another if
  its advantage **exceeds the observed variance** — a `0.55`-over-`0.6` flip on
  noise is precisely the failure this prevents.
- **Sweep mode:** run the set across a grid of `verify_threshold` × `verify_top_n`
  (each grid point built via `dataclasses.replace` on `Settings`, never mutation),
  `K` runs per point; report the accuracy/escalation/cost trade per point with
  mean + spread. This is the OQ2 instrument.
- **Comparison:** report `fast` vs `auto` vs `deep` on the same set (validates
  `auto` is buying accuracy for its escalation cost, not just spending it).
- **N floor:** a seed-set size floor below which results are reported as
  **indicative-only** (not a basis for a default flip); the floor and the actual N
  are stated in the report so "small N" is a known quantity, not a post-hoc caveat.

## Acceptance criteria

`[unit]` = fakes; `[integration]` = `@pytest.mark.integration`, skip-not-fail.

1. **[unit]** Dataset loader parses the fixture format; rejects malformed cases
   loudly (typed, actionable error — never a silent skip).
2. **[unit]** Span-hit metric correct on hand-built fixtures: **primary**
   line-range overlap and **secondary** file-level + proximity (D2), each verified
   against known inputs including the boundary cases (touching ranges, partial
   overlap, same-file no-overlap within/outside the proximity window).
3. **[unit]** Aggregate metrics correct on known inputs: escalation rate,
   Tier-0/1 resolve rate, and — via the **single D3 overlap oracle** — gate catch
   rate and gate false-escalation rate. A test asserts catch-rate and
   false-escalation are computed from the *same* oracle the span-hit metric uses.
4. **[unit]** Runner drives the real auto path via injected fakes for each tier;
   assembles the report without a live model. The emitted report **conforms to the
   pinned JSON schema** (asserted), and artifacts are written **outside any indexed
   repo** (asserted against the read-only guardrail).
5. **[unit]** Repeated-run aggregation: `K` runs of a configuration aggregate to
   mean + spread; the recommendation helper only prefers a configuration when its
   advantage **exceeds the observed variance** (verified with hand-built
   high-variance and clear-signal fixtures).
6. **[unit]** Sweep enumerates the `threshold` × `top_n` grid, builds each point
   via `dataclasses.replace` (asserted — no `Settings` mutation), and aggregates
   per-point results (mean + spread over `K` runs).
7. **[integration]** End-to-end: seed set runs through the live stack, emits a
   schema-conforming report with all metrics populated; air-gap respected (zero
   non-loopback egress, network-deny style assertion).
8. **[integration]** OQ2 sweep runs live on the seed set (`K` runs per grid point);
   produces the trade-off table (mean + spread per point) that backs a recommended
   `(verify_threshold, verify_top_n)`, with the N-floor caveat applied when the
   seed N is below the floor.

### OQ2 resolution (recommend-only deliverable, B1)

- Run AC8 sweep on the eval repo. **Falsifiable bar (B2):** hold gate catch rate
  **≥ 0.90** (a provisional target — tunable once seed-set N grows; recorded as
  provisional, not load-bearing forever). Among points clearing the bar, pick the
  `(threshold, top_n)` minimizing false-escalation + over-escalation cost, **only
  where the chosen point's advantage exceeds observed run-to-run variance** (B4).
- **Deliverable is a recommendation, not a code change (B1):** record the chosen
  values, the trade-off table (with spread), the catch-rate bar used, and the
  seed-set N caveat in the changelog. **Do not edit `Settings` defaults in this
  wave.** If `0.6/3` clears the bar and no alternative beats it past the noise
  margin, record that they were *validated*, not guessed. Any actual default flip
  is a separate one-line follow-up spec citing this evidence.

## Out of scope

- **Flipping any `Settings` default value** (the recommended `(threshold, top_n)`
  is emitted as data; the flip is a follow-up spec). (B1)
- Changing tier/gate/matrix behavior (this wave only measures + recommends).
- Wave-2.1 substring/fuzzy.
- The rest of Wave 6 (air-gap/concurrency soak, packaging, doctor preflight) —
  separate spec.

## Open questions

_none — D1/D2/D3 resolved above; frozen before planning._
