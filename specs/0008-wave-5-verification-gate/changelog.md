---
spec: "0008"
closed: 2026-06-27
---

# Changelog — 0008 Wave 5 — Verification Gate + Tier-0→1→2 auto-escalation

## What shipped vs spec

`mode=auto` now climbs the tier ladder. The orchestrator wires the four deferred
seams — query classifier, planning matrix, Verification Gate, and the escalation
ladder — so `auto` runs the cheapest tier that can answer and escalates only on a
real signal. Tier internals (Tier-0 seed, Scout, Deep) are untouched: this wave is
orchestration-only. Shipped TDD-complete: 513 tests pass (all integration ACs ran
**live**), ruff clean.

Resolved open questions:
- **OQ1 (gate backend) = `scout_model` reuse.** The gate reuses the already-loaded
  Scout fine-tune as the relevance judge — no new model to serve on the single-GPU
  profile. It is the **only** value `verify_method` accepts; `embedding` /
  `model_judge` / anything else is rejected loudly (no-false-capability).
- **OQ3 (gate scope) = bounded top-N.** The gate scores at most `verify_top_n`
  ranked citations; the dropped count is logged (no-silent-truncation).
- **OQ2 (numeric defaults)** ships **provisional** (`verify_threshold=0.6`,
  `verify_top_n=3`) — eval-repo tuning task carried forward, does not block.

### AC-by-AC status (all met)

- **AC1 — new `auto` contract pinned, Wave-0 lock retired in lockstep.** Realized
  `tiers_run`: gated-pass ⇒ `[0,1]`; escalated ⇒ `[0,1,2]`; broad ⇒ `[0,2]`;
  `index_ready=false` prefixes ⇒ `[1]` / `[1,2]`. The `_MODE_NO_EFFECT` lock and its
  guard tests (`orchestrator/test_locate.py` **and** `server/test_app.py`) were
  deleted in the **same** change that wired the new contract — no unspecified window.
- **AC2 — classifier.** Heuristic point/broad; ambiguous → `point`. Pluggable
  `Classifier` callable seam (heuristic only ships).
- **AC3 — planning matrix, all 12 rows.** `plan_ladder` over a 6-row
  `(mode, classification)` seeded table; `index_ready=false` drops the leading `0` →
  all 12 rows asserted.
- **AC4/AC5/AC6 — cost lever + gate catch/pass.** A passing gate holds at `[0,1]`
  (Tier-2 unspent); a failing gate escalates to `[0,1,2]`.
- **AC7 — mode routing.** broad+auto → straight to Deep (`[0,2]`, Scout skipped, no
  gate); `fast` never escalates (informational gate); `deep` skips to Tier-2.
- **AC8 — empty-case three-way split + gate-scoring-failed contract.**
  typed-unavailable → degrade (`scout-degraded:<cause>`, `confidence="degraded"`, no
  climb); honest-empty → gate skipped, seed returned `gate-skipped:scout-empty`
  (`[0,1]` and `[1]` both asserted); malformed → escalate; gate-scoring-failed →
  escalate in `auto` (flag retained), best-effort Tier-1 in `fast`.
- **AC9 — confidence map + stable flag ids.** Confidence keyed on terminal-tier +
  flags; honest-empty distinguished from gated-pass (`medium`/`low` vs `high`); flag
  ids asserted as exact identifier strings.
- **AC10 — air-gap.** `gateway.assert_local()` fires **before** the judge; judge
  never called on a non-loopback endpoint (unit). Network-deny zero-egress
  **integration test PASSED live**.
- **AC11 — bounded top-N.** Scores ≤ `verify_top_n`; dropped count logged.
- **AC12 — end-to-end `auto`.** point resolves cheap `[0,1]`; broad routes `[0,2]`.
  **PASSED live** over the real stack (FastContext Scout + scout_model gate judge +
  Deep `qwen2.5-coder:3b` over Deno).
- **AC13 — `verify_method` inert-value rejection.** Unsupported values raise
  `UnsupportedVerifyMethod` at every `Settings` construction path.

## Deviations from the plan

- **T11/T12 (empty-case split) landed inside T10's `_locate_auto`.** The three-way
  split and the gate-scoring-failed routing were implemented as part of T10's
  cohesive `_locate_auto` body rather than a separate RED→GREEN pair; the T11 tests
  lock the behavior in after the fact.
- **T17 caught `_locate_auto` re-deriving routing** and refactored it to consult
  `plan_ladder`, making the matrix the genuine single source of truth (not a second
  authority duplicated in the ladder code).
- **"Malformed Scout result → escalate" is realized as "gate cannot score the
  returned citations → `GateOutcome.failed` → escalate."** Scout's contract is
  spans-or-`ScoutUnavailable`, so a malformed/un-readable result manifests at the
  gate (e.g. a citation whose file is absent fails read-back), not as a separate
  Scout signal. Same realized path as a gate-fail.
- **Integration ACs (10/12) ran live, not skipped** — FastContext Scout, the
  scout_model gate judge, and Deep over Deno all exercised end-to-end; point resolved
  cheap, broad climbed to Tier-2.
- **`confidence="degraded"` literal preserved** for the typed-unavailable path; the
  confidence map's `low` rows are gate-states only (the two never collide).
- **Aggregation choice:** the gate takes `max` over the top-N scores — one strongly
  relevant citation is enough for a locate answer to pass (recorded, not specified).

## Files touched

- `harpyja/config/settings.py` — 3 additive fields appended last
  (`verify_method`/`verify_threshold`/`verify_top_n`), `_VERIFY_METHODS`,
  `UnsupportedVerifyMethod`, `__post_init__` validation, `_coerce` float support.
- `harpyja/orchestrator/classify.py` *(new)* — `classify_query` heuristic +
  `Classifier` seam.
- `harpyja/orchestrator/matrix.py` *(new)* — `plan_ladder` over `_SEEDED_LADDER`
  (the 12-row planning matrix).
- `harpyja/orchestrator/gate.py` *(new)* — `VerificationGate`, `GateOutcome`,
  `make_scout_model_judge`, read-back + top-N + `assert_local`.
- `harpyja/orchestrator/wiring.py` *(new)* — `build_verification_gate` (production
  `gate_factory`).
- `harpyja/orchestrator/locate.py` — `_locate_auto` ladder, three-way empty split,
  `fast` informational gate, confidence map, stable flag constants; `_MODE_NO_EFFECT`
  removed.
- `harpyja/server/app.py` — `gate_factory` param threaded into `locate`.
- Tests: `orchestrator/test_classify.py`, `test_matrix.py`, `test_gate.py`,
  `test_locate_integration.py` *(new)*; `test_locate.py`, `config/test_settings.py`,
  `server/test_app.py` *(extended; Wave-0 lock tests retired)*.

## ADR proposed for history.md

2026-06-27 — Wave 5 Verification Gate + Tier-0→1→2 auto-escalation shipped (see
`history.md` entry). Load-bearing decisions: gate = `scout_model` judge through
`ModelGateway.complete` (not a parallel client); bounded top-N; Wave-0 zero-call
lock retired in lockstep with the explicit AC1 contract; planning matrix as the
single source of truth driven by code; empty-case three-way split; confidence keyed
on terminal-tier + flags with honest-empty distinguished from gated-pass;
`verify_method` no-false-capability rejection.

## Conventions proposed

- **Planning/routing matrix as the single source of truth, consulted by the code
  that routes.** A `(mode × …)` → planned-sequence table that both the executor and
  the tests read, with the executor deriving its branches *from* the table rather
  than re-encoding the rules. (See `orchestrator/matrix.py`, `_locate_auto`.)
- **A best-effort gate/scorer maps any failure to a typed "could-not-vouch" outcome,
  never raises and never silently passes.** A scoring failure routes exactly like a
  negative verdict (escalate where a tier remains) with a stable diagnostic flag
  retained. (See `orchestrator/gate.py` `GateOutcome.failed`, `gate-scoring-failed`.)
- **Derived confidence keys on terminal-tier + flags, never path tokens alone**, so
  an honest-empty result that shares `tiers_run` tokens with a verified pass is given
  a distinguishing marker and can never read as high confidence. (See AC9,
  `gate-skipped:scout-empty`.)

## Still open (carried forward)

- **OQ2** — `verify_threshold` / `verify_top_n` provisional defaults; tune against
  the eval repo.
- **Wave-2.1 substring/fuzzy matching** — the long-standing remaining symbol-layer
  follow-up.
