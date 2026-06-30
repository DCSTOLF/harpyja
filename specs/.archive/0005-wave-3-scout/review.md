---
spec: "0005"
title: "Wave 3 — Scout"
reviewers: [codex, claude-p]
quorum: 1
verdict: approve-with-comments
quorum-met: true
generated: 2026-06-27T00:00:00Z
rounds: 2
---

# Cross-model review — 0005 Wave 3 — Scout

**Date:** 2026-06-27
**Reviewers:** codex, claude-p
**Rounds:** 2 (round 1 → `changes-requested` ×2; round 2 → `approve-with-comments` ×2)
**Quorum result:** MET — 2 of 2 reviewers approved-with-comments (1 approval required).

---

## Round 1 — `changes-requested` (both)

Two consensus blockers, both guardrail-adjacent, both since resolved:

1. **Graceful-degradation floor.** "Never raises, never goes blind" composed
   badly: Scout degrades *to Tier-0*, which has its own hard precondition
   (`rg` → `RipgrepMissingError`). Model-down **+** Tier-0-can't-run forced a
   silent empty reading as "nothing found" — the exact anti-pattern the floor
   guardrail exists to stop.
2. **Resolution-time air-gap.** `assert_local` matched literal loopback strings,
   but the real egress boundary is **name resolution** — a configured hostname
   can resolve off-loopback (and the lookup itself is egress). AC4's "no
   non-loopback egress possible" wasn't a network-free testable claim without an
   injected resolver seam.

Plus shared/related: `mode=deep` lockstep guard, `ScoutBackend`↔`Locator`
reconciliation, concrete seed/output budgets, enumerated hostile-input tests;
and claude-p-only items (distinct notes per cause, duplicated bullet, missing
`orchestrator` package + `related-specs`, unit/integration split, Scout
not-cached call-out).

## Round 2 — `approve-with-comments` (both)

Both reviewers confirmed **the two blockers are adequately resolved** and that
the design is sound. Remaining items are implementation-time clarifications, the
substantive ones already folded into the revised `spec.md`.

### Resolved in the revision

- **Degradation floor → a four-state machine** (Scout ok / Tier-0-has-results
  degraded / Tier-0 honestly-empty / Tier-0 precondition-absent raises loudly),
  with seed-before-backend ordering making state 4 win by construction. AC5
  exercises all four + distinct cause notes.
- **Air-gap at resolution time** via an injected resolver + `ipaddress` loopback
  predicate; AC4 tests it network-free.
- `mode=deep` lockstep guard (no Tier-2 marker); `ScoutBackend` exposed behind
  the shared `Locator`/`CodeSpan` boundary; concrete budgets
  (`scout_seed_top_n=5`, `scout_max_citations=20`, `scout_max_span_lines=200`);
  AC7 hostile-input cases; distinct stable note identifiers; unit/integration
  split; Scout explicitly not-cached; `orchestrator` package + `related-specs`
  added; duplicate bullet removed.

### Round-2 comments — also folded into the spec (honesty-driven)

- **FastContext side-channel overclaim.** Both flagged that "no side-channel"
  was *asserted*, not enforced — tool injection can't stop in-process
  third-party code from opening its own socket (Scout has no WASM sandbox like
  Deep). Reframed as an **honest limit + assumption verified by test**: exact
  tool whitelist (AC10), a **network-deny integration test** (AC11), and a
  process/WASM-sandbox **follow-up** in Out-of-scope. Aligns with the project's
  no-false-capability rule.
- **DNS wording.** "before any implicit DNS lookup that would itself be egress"
  overstated zero DNS egress. Reworded: resolution *is* the check, so a
  misconfigured external host leaks at most one lookup via the approved resolver
  before rejection; IP-literal / hosts-file endpoints are the documented posture
  to keep that at zero. No request ever reaches a non-loopback address.
- **Air-gap violation vs degradation.** Made explicit that a resolved
  non-loopback endpoint is a **loud floor error** (`NonLoopbackEndpointError`),
  deliberately *not* one of the four degrade states (absent endpoint degrades;
  hostile endpoint raises).
- **Stable identifiers** for notes/errors; **AC1 flakiness** pinned to a fixture
  query (deterministic shape assertions live in unit ACs).

### Residual (carry into implementation / plan)

- FastContext exact **package + version / pip-pinnability** — the only genuinely
  open item; de-risked by the `ScoutBackend` Protocol (the sole Open Question).
- Process-level **sandboxing** of FastContext — tracked follow-up, not Wave 3.

---

## What both reviewers affirmed

`mode=auto` byte-identical with **zero** Gateway calls as the regression lock;
the `ScoutBackend` Protocol + fake-backend DI seam; single-point air-gap
enforcement; honest-degrade posture; no-false-capability `mode=deep` handling;
concrete budgets and enumerated hostile-input tests. The shape matches the
architecture — clarifications, never a redesign.

## Recommended action

Quorum met → spec moves to **`reviewed`**. Proceed to **`/speccraft:spec:plan`**
to turn it into a test-first plan. Carry the two residual items (FastContext
version pin; sandbox follow-up) into planning.
