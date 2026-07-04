---
spec: "0020"
closed: 2026-07-04
---

# Changelog — 0020 OQ2 (the operator sweep)

## What shipped vs spec

Spec 0020 is a **measurement/eval** spec (SUT frozen; all code additive under
`harpyja/eval/`). It is the OPERATOR SWEEP that runs the 0019 instrument as a
four-gate sequential stop-and-report protocol (G0 preflight → G1 smoke →
G2 gate-quality → G3 sweep) and emits exactly one typed outcome plus a durable
gate-ledger. It SHIPPED and was **unit-verified**: 43 new tests, **777 → 820 unit
pass**, ruff clean. It was then **run live**, producing a recorded typed outcome.

**Shipped modules (all new, under `harpyja/eval/`):**

- `oq2_classify.py` — the pure G3 outcome projection `classify_g3_outcome`
  (+ `G3Classification`) sitting ABOVE the byte-frozen 0019 `recommend_oq2`
  dispatcher. Precedence **DEGRADED_DOMINATED > GATE_CONFOUNDED > NOT_SEPARABLE >
  RECOMMENDATION**; the no-survivor `S` signal =
  `incumbent_validated is False AND advantage_exceeds_variance is False`, derived on
  the frozen `Recommendation` and computed ONLY when not gate-confounded (so no
  phantom `NOT_SEPARABLE` is booked alongside `GATE_CONFOUNDED`); `indicative_only`
  is a RECOMMENDATION-only sub-flag (effective-N < `n_floor`).
- `oq2_ledger.py` — a NEW pinned artifact `LEDGER_SCHEMA_VERSION = "0020/1"` (distinct
  from the sweep report `0014/1`), with `build_gate_ledger` / `validate_gate_ledger`
  (loud `LedgerSchemaError`) / `write_gate_ledger` reusing `report.atomic_write_json`
  (the outside-the-indexed-repo guard stays single-sourced).
- `oq2_protocol.py` — `run_oq2_protocol`, the sequential G0→G1→G2→G3 driver over
  injected collaborators, each verdict recorded before the next gate. The close/hold
  split is drawn **by cause** (D7): an environment non-completion (OOM / resource
  exhaustion / preflight fail / fixtures absent) is a **BLOCKED hold**; a run that
  *completed* then degrade-dominated or gate-false-rejected is a **STOP:SMOKE close**.
- `oq2_live.py` + an `oq2` CLI subcommand (`cmd_oq2` in `swebench_eval.py`) — the live
  seam that builds the real G0→G3 collaborators over the served stack + provisioned
  fixture and drives the driver end-to-end, plus a skip-not-fail integration test.

The two front-loaded review items were honored: **P1** — the NOT_SEPARABLE
discriminator is reachable on the frozen `Recommendation` without touching the
dispatcher (locked in `test_recommend.py`); **P2** — a byte-frozen behavior snapshot
of `recommend_oq2` / `rank_sweep` (locked, not a source grep).

## The operator-run outcome (the load-bearing story)

The instrument was run live against the served stack + provisioned SWE-bench point
subset. **Typed outcome: DEFERRED** — a valid deliverable per AC11 that names the next
spec. It is NOT a calibrated OQ2 and Scout was NOT fixed.

- **G0 preflight — PASS** (required served tags present, validated twice).
- **G1 smoke (astropy-12907, `mode=auto`) — PASS, with an honest caveat.** Run
  completed, tiers alive (0 % degrade), no gate-false-rejection — but
  `tier1_correct = False`: Scout missed the gold span, the gate correctly *caught* the
  wrong citation (catch_rate 1.0) and escalated to Deep, which also missed. Sub-check
  (c) is **vacuously** satisfied (no correct Tier-1 to reject); the case is not solved
  end-to-end. Recorded honestly.
- **G2 gate-quality — DEFERRED.** The instruct pass over 38 point cases completed
  (~3.3 h) with **`correct_tier1_count = 0`** → `gate_false_escalation = null` **by
  definition**: you cannot measure whether a judge false-*rejects* correct citations
  when Scout emits none. The finder-judge A/B and the G3 sweep are therefore **moot**
  (`verify_method` changes the judge, not Scout's citations) and were not run.
- **Root cause — verified real, not a harness artifact.** Direct Tier-1 spot-checks
  confirmed `expected_spans` load correctly, Scout runs and returns citations, and the
  overlap oracle is right. Scout Tier-1 is genuinely ≈ 0 correct on SWE-bench point
  cases: at best **right-file-wrong-span** (astropy-12907: cited `separable.py:66-102`,
  gold `242-248`), otherwise empty or wrong-file.
- **Not a model-swap fix — verified.** `qwen3:4b-instruct` as the Scout finder also
  got 0/3, same pattern; on astropy-12907 **both models produced the identical wrong
  span** — evidence of span-level localization / task difficulty, not a model-quality
  gap.

**Environment findings (recorded, D9-a / D9-b):** `qwen3-coder:30b` as Deep+judge
**OOM'd** the 32 GB host (swap 94 % full) — the D9 co-residency risk realized, an
AC4/D7 BLOCKED-hold cause; resolved by dropping to `qwen3:8b` (~9.5 GB co-resident).
And `make_instruct_judge` (0018 SUT) does **not** defend against model "thinking" (the
anchored `_parse_score` would fail on a `<think>` block) — a latent 0018 SUT robustness
gap; not biting this run (`qwen3:8b` empirically returns bare, well-calibrated numbers).

**Named follow-up:** **Scout Tier-1 span-level localization on SWE-bench** (the
right-file-wrong-span pattern from long issue-text queries; file/proximity vs
exact-span scoring; finder capability) — NOT a gate-accuracy, threshold-calibration, or
finder-model-swap spec. Secondary: judge thinking-defense hardening (D9-b),
smaller-footprint Deep + a co-residency budget (D9-a), and reconciling an
`escalation_rate: 0.0` vs 3.3 h-runtime accounting anomaly before trusting secondary
metrics.

## Scope honesty

Mechanism + instrument shipped and unit-verified; G0/G1 validated live; **OQ2 gate
calibration remains blocked upstream** on Scout locate accuracy. That block is itself
the honest, typed deliverable. Never claim OQ2 was calibrated or that Scout was fixed.

## Deviations recorded

- The five RED/GREEN protocol pairs (T7–T16) were implemented as one comprehensive RED
  (full `test_oq2_protocol.py`) then one GREEN (`oq2_protocol.py`) — test-first
  preserved, pairs batched.
- T18 (refactor: verdict→ledger mapping consolidation) was a **no-op**: the driver
  already single-sources `_verdict_dict` / `commit`.
- T19: the live harness is built + G0/G1 executed live; the full G2/G3 sweep is
  operator-gated and (given the DEFERRED root cause) moot. AC12's "skip-not-fail ≠
  close" was honored — the spec closes on a **recorded, SUT-observing DEFERRED
  outcome**, not a skip.

## Files touched

- `harpyja/eval/oq2_classify.py` (new)
- `harpyja/eval/oq2_ledger.py` (new)
- `harpyja/eval/oq2_protocol.py` (new)
- `harpyja/eval/oq2_live.py` (new)
- `harpyja/eval/swebench_eval.py` (`cmd_oq2` + `oq2` CLI subparser)
- `harpyja/eval/test_oq2_classify.py` (new)
- `harpyja/eval/test_oq2_ledger.py` (new)
- `harpyja/eval/test_oq2_protocol.py` (new)
- `harpyja/eval/test_recommend.py` (P1/P2 locks)
- `harpyja/eval/test_swebench_integration.py` (skip-not-fail live G0→G3)
- `specs/0020-oq2/{spec,plan,tasks,review}.md`
- `.speccraft/index.md`

## ADR proposed for history.md

See the 2026-07-04 entry prepended to `.speccraft/history.md` — the instrument shipped;
the DEFERRED typed null; Scout Tier-1 ≈ 0 on SWE-bench (verified, model-independent) as
the real upstream blocker; the OOM co-residency + judge thinking-defense findings; and
the named follow-up (Scout span-level localization, not gate-accuracy).

## Conventions proposed

- New (Measurement & eval harness): a taxonomy label is a **projection layer ABOVE a
  byte-frozen dispatcher**, never a widening of it — measurement-not-construction in
  the type. (from `oq2_classify.py` / D1.)
- New (Measurement & eval harness): a measurement spec's close gate is a **recorded,
  SUT-observing typed outcome that names the next spec** — a typed null (incl. a
  DEFERRED/unmeasurable metric) is a complete deliverable, and skip-not-fail is not a
  close. (from AC11/AC12 / D7.)
- New (Measurement & eval harness): before reporting a **null/undefined** measurement,
  **verify the null is real, not a harness artifact** — spot-check the oracle,
  fixtures, and SUT invocation directly, and separate a genuine upstream limit from a
  measurement bug. (from the G2 DEFERRED root-cause verification.)

## Architecture updates

The `harpyja/eval/` section gains the operator-protocol layer: `oq2_protocol` (the
G0→G3 driver), `oq2_classify` (the four-label projection over the frozen dispatcher),
`oq2_ledger` (the new pinned `0020/1` artifact), and `oq2_live` + the `oq2` CLI. Report
schema stays `0014/1` (unbumped — the ledger is its own schema).
</content>
</invoke>
