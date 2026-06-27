---
spec: "0006"
title: "Wave 4 — Deep (RLM)"
reviewers: [codex, claude-p]
quorum: 1
verdict: approve-with-comments
quorum-met: true
generated: 2026-06-27T00:00:00Z
rounds: 3
---

# Cross-model review — 0006 Wave 4 — Deep (RLM)

**Date:** 2026-06-27
**Reviewers:** codex, claude-p
**Rounds:** 3 (round 1 → `changes-requested` ×2; round 2 → `changes-requested` ×2;
round 3 → `approve-with-comments` ×2)
**Quorum result:** MET — 2 of 2 approve-with-comments (1 required).

---

## Round 1 — `changes-requested` (both)

Three blockers + five yellows. Blockers: (1) bound the explorer **loop**, not just
per-tool calls; (2) invert the Wave-3 "no Tier-2 marker" lockstep guard as a pinned
AC; (3) sandbox **ambient-access** under-specified. Yellows: pin `tiers_run` on
degraded branches; `DeepEngine` Locator adapter; single-helper air-gap +
resolved-address check; `DeepUnavailable`-typed-only; resolve the seed handoff.

## Round 2 — `changes-requested` (both)

Blockers 2 (lockstep, AC2a) and 3 (sandbox reframing) confirmed resolved; **all five
yellows** addressed. Blocker 1 only *partially* resolved — budgets named but the
**enforcement seam** unspecified against an untrusted code-writer. Round-2 asks:
host-mediated seam (+ recorded residual risk); AC10 enforce-not-plumb against a
non-cooperative backend + integration runaway AC; `deep_wall_clock_ms`;
`deep-truncated:<bound>` note; `[unit]` positive-equality sandbox whitelist;
inside-repo ambient `open()` assertion.

## Round 3 — `approve-with-comments` (both)

All round-2 asks landed. Both reviewers confirm the explorer-loop-enforcement blocker
and the sandbox tightening are **adequately resolved**:

- **Layered enforcement** — externally-enforced (`deep_max_tool_calls` via wrappers,
  `deep_token_ceiling` via Gateway, `deep_wall_clock_ms` via host deadline) vs
  host-mediated (`deep_max_depth` / `deep_max_subqueries`) with residual risk recorded
  and the external trio named load-bearing. No overclaim.
- **AC10 / AC10a** — enforcement proved against a non-cooperative backend at the
  harness seam, plus an integration real-runaway proof.
- **`deep-truncated:<bound>`** — closes the silent-truncation false-capability gap;
  honestly distinct from both a complete run and a `DeepUnavailable` degrade.
- **AC8a/8b** — `[unit]` positive-equality whitelist (deno-less backstop) + inside-repo
  `open()` failure (closes the fifth-unbounded-capability bypass).

### Comments folded into the spec (round 3)

Both flagged the same headline mechanism point; folded in rather than deferred:

- **Out-of-band, host-terminable execution.** `deep_wall_clock_ms` is only physically
  realizable if the backend/sandbox runs in a preemptible context (subprocess / sandbox
  worker the host can hard-kill) — a same-thread deadline can't fire during a
  synchronous WASM busy loop. The spec now **requires** this; AC10 pins that the
  wall-clock case exercises a genuinely non-yielding backend in that context and that
  neither AC10 nor AC10a relies on cooperative cancellation (and the harness must not
  hang).
- **Transitive containment.** A recursion/sub-query storm is contained by the external
  ceilings (each sub-query spends tool-calls/tokens/wall-clock) even if the mediation
  seam turns out cooperative — host-mediated caps are a precision improvement, not the
  only thing preventing an unbounded loop. (claude-p)
- **Note never silently absent.** `deep-truncated:depth`/`:subqueries` fire only when
  the seam is live; under realized residual risk, the firing *external* bound's note is
  the honest signal. (claude-p)
- **Budget forward-reference.** `deep_max_depth`/`deep_max_subqueries` budget lines now
  forward-reference the Enforcement caveat so they aren't read as hard bounds in
  isolation. (claude-p)
- **Residual-risk record** includes the observed runtime capability + the fallback
  that tool/token/wall-clock remain authoritative. (codex)

### Residual (carry into planning)

- The **out-of-band execution model** (subprocess/worker boundary) is now required in
  the spec; its concrete wiring is a planning/implementation detail to pin in the TDD
  plan, alongside the sole open question (dspy/Deno **provisioning**).

---

## What both reviewers affirmed (do not weaken)

Typed-failure-only degradation (AC5/5a — `DeepUnavailable` only on typed infra failure;
weak/zero citations stay an honest Tier-2 result, never an ungated escalation, deferring
quality judgment to the Wave-5 Gate); floor-wins-by-construction ordering; lockstep
inversion (AC2a); the `DeepBackend` DI seam + `DeepEngine` Locator adapter; no-cache;
byte-identical model-free `auto`; single-helper air-gap. These match established
Wave-2/3 patterns.

## Recommended action

Quorum met → spec moves to **`reviewed`**. Proceed to **`/speccraft:spec:plan`**.
Carry into planning: the out-of-band/host-terminable execution boundary for the
sandbox (the wall-clock mechanism), and the dspy/Deno provisioning open question.
