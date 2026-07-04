# Review — Spec 0020 (OQ2)

**Reviewers:** codex (cli), claude-p (cli)

## Round 2 (rev 2) — 2026-07-03 — QUORUM MET

**Synthesized verdict:** **approve-with-comments** (2 of 2 approve-with-comments;
quorum ≥1 met → spec advanced to `reviewed`).

Both reviewers confirmed rev 2 genuinely resolves the four blocking rev-1 findings
rather than papering over them, and both walked the `classify_g3_outcome` truth table
to totality. Neither asked for another Socratic revision; both scoped their remaining
comments to `plan.md`. The two most load-bearing comments were folded into the spec
before advancing (below); the rest are carried into planning.

### Verdict table (round 2)

| Reviewer | Verdict | Residual comments |
|---|---|---|
| codex | approve-with-comments | S-input undefined under gate-confound short-circuit; "byte-unchanged" not directly observable (add a golden/no-diff check) |
| claude-p | approve-with-comments | NOT_SEPARABLE vs flip-RECOMMENDATION need a discriminator field distinct from `incumbent_validated`; OOM-at-G1 close/hold seam |

### Comments folded into the spec now

- **C1 — the NOT_SEPARABLE discriminator (both reviewers; load-bearing).** A
  variance-beating flip and a no-survivor both carry `outcome=="recommended"` **and**
  `incumbent_validated=False`, so `incumbent_validated` alone cannot distinguish them.
  Verified against `recommend.py`: the no-survivor branch (:90–99) is the **unique**
  state with `incumbent_validated is False AND advantage_exceeds_variance is False`
  (both flip branches, :132–149, are `advantage_exceeds_variance is True`). The
  discriminator is therefore reachable on the **byte-frozen** `Recommendation` without
  editing the dispatcher — folded into the G3-projection prose, AC8, and D-notes.
- **C2 — the OOM-at-G1 close/hold seam (claude-p).** G0 proves models are *pulled*,
  not co-resident-loadable; an OOM non-completion at G1 sub-check (a) was routed to
  `STOP:SMOKE` (a close) but is an environment failure D7 would otherwise HOLD. Fixed:
  G1 non-completion is now classed **by cause** — environment/OOM → `BLOCKED` hold;
  run-completed-then-degrade/false-reject → `STOP:SMOKE` close (updated in the G1
  bullet, AC4, AC12, D7).
- **C3 — ledger schema id + guarded S boolean (both).** The new gate-ledger now carries
  its own version id (`ledger 0020/1`), and the `NOT_SEPARABLE` boolean is recorded in
  the ledger **only when `rank_sweep` actually ran** (never under the gate-confound
  short-circuit), preventing a phantom `NOT_SEPARABLE` alongside `GATE_CONFOUNDED`
  (AC2, AC7).
- **C4 — precedence is not a partition (both).** Added a D3 note that the four label
  conditions overlap by construction and are disambiguated solely by precedence; the
  `GATE_CONFOUNDED`-vs-`NOT_SEPARABLE` order is vacuous (they never co-occur), and the
  only genuine co-occurrence is `DEGRADED_DOMINATED` with the others.

### Carried into plan.md (both reviewers agreed these are plan-time)

- **P1 — prove `advantage_exceeds_variance` + `incumbent_validated` are reachable and
  sufficient** as the NOT_SEPARABLE discriminator by a direct field-reachability test
  before implementing the projection (codex's truth-table + claude-p concern #1).
- **P2 — make "byte-unchanged `recommend_oq2`/`rank_sweep`" concretely observable**
  (codex): a golden checksum / snapshot / no-diff guard, not just "existing tests pass."
- **P3 — the `classify_g3_outcome` truth table** (both reviewers reproduced it) becomes
  the projection's unit-test matrix: D > G > S > default, with `indicative_only` a
  sub-flag on RECOMMENDATION only.

### Reviewer-endorsed truth table (for the plan)

Reduce to three booleans — D=`degraded_dominated`, G=`outcome=="gate-confounded"`,
S=no-survivor-cleared-bar (`incumbent_validated is False and advantage_exceeds_variance
is False`, computed only when `rank_sweep` ran) — apply total order D > G > S > default:

| D | G | S | label |
|---|---|---|---|
| T | * | * | DEGRADED_DOMINATED |
| F | T | (n/a) | GATE_CONFOUNDED |
| F | F | T | NOT_SEPARABLE |
| F | F | F | RECOMMENDATION (`indicative_only = effective_N < n_floor`) |

## Round 1 (rev 1) — 2026-07-03 — changes-requested

Both reviewers returned `changes-requested`. Four blocking findings, all fixed in
rev 2:

- **F1/F2 — G3 taxonomy contradicted the instrument** (claude-p, verified vs code): the
  spec named four outcomes but `recommend_oq2` emits only two, and `NOT_SEPARABLE`
  *inverted* `rank_sweep`'s validated-incumbent semantics. → Fixed via the
  `classify_g3_outcome` projection layer (dispatcher frozen) + validated-incumbent =
  RECOMMENDATION.
- **F3 — precedence unspecified** (both): outcomes not mutually exclusive; gate-confound
  short-circuits past degrade. → Fixed: DEGRADED_DOMINATED > GATE_CONFOUNDED >
  NOT_SEPARABLE > RECOMMENDATION, all true conditions recorded.
- **F4 — AC10 was a 0019-redux loophole** (both, emphatic): skip-not-fail could close
  with zero numbers. → Fixed: close gate is a recorded SUT-observing outcome;
  environment BLOCKED is a hold.
- **F5–F9** (descriptive-only G3-under-confound; packages trimmed; thresholds cited to
  `EvalConfig`; ledger as a new pinned artifact; OQ-B/OQ-C resolved) — all applied.

Both reviewers explicitly endorsed the sequential G0→G3 stop-and-report skeleton, the
invariants block, the "typed null IS the deliverable" posture (AC11), and OQ-A's
flag-don't-re-decide default.

## Recommendation

Proceed to `/speccraft:spec:plan`. The plan must front-load P1 (discriminator
field-reachability) and P2 (byte-frozen guard), and use the round-2 truth table as the
projection's test matrix. No further spec revision required.
