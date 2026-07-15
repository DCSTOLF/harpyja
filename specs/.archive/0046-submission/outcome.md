# Outcome — spec 0046 "submission"

**Typed outcome: `BASELINE_DRIFT_STOP`** (frozen rule, first-true-wins over the
five-sided predicate's precedence). Pilot-N signal, not an inferential claim.

## Verdict

The BASELINE arm (reverted 0044 gate, current SUT, `explorer_reactive_confirm=False`)
scored **NET = 0** vs the committed 0040/0042 pre-nudge table (3 conversions, 3
regressions over 29 paired cells) — **outside the frozen sanity band `[1, 3]`**. The
band was frozen in the reviewed spec BEFORE any number and re-committed in the
predicate freeze (`predicate_freeze/five_sided_predicate.json`, pre-baseline). Per
the frozen rule, an out-of-band baseline types `BASELINE_DRIFT_STOP` and the run
**STOPS before typing the new-arm verdict** — the comparison point did not reproduce
the 0044 operating point, so a NEW-vs-baseline DISSOLVES/TRADES verdict would rest on
an unvalidated baseline.

Per the operator decision, the NEW arm (T28) was **not run** — no further live spend.

## The baseline arm (33/33 cells, 3 typed degrades excluded)

- **s→wc = 6**, **found-but-unsubmitted = 5**, located = 7, honest-empty = 10,
  regression-or-miss = 2 (30 clean cells; both power floors cleared:
  covered 30 ≥ 8, baseline s→wc 6 ≥ 3).
- Derived flagged-wrong-emitted ceiling = ⌊0.5 × 6⌋ = **3** (recorded as audit in
  `reactive_run/reactive_config.json`; never applied — the new arm did not run).
- Per model: 14b {located 4, s→wc 2, fu 1, reg 1, empty 2}; 8b {s→wc 4, located 2,
  fu 2, reg 1, empty 2}; 4b {located 1, fu 2, empty 6}.
- Typed degrades (excluded from the join, per the 0044 precedent): `django-13516::4b`,
  `matplotlib-21568::14b`, `pytest-10081::4b`.

## The finding: a single-run baseline band is fragile under model stochasticity

0044's operating point was `conv 3 / reg 1` (net +2); this baseline draw is
`conv 3 / reg 3` (net 0). The difference is **two regressions on 29 paired cells with
~7 correct** — well within run-to-run variance for the stochastic qwen3 models on a
pilot-N=33 single run. The most likely reading is **noise, not a code regression**:
the reverted-gate SUT behaves like 0044, but one stochastic draw did not reproduce the
+2.

This is itself the honest result the invariant *"re-measure the baseline on the
CURRENT SUT — do not compare to history"* exists to surface: **a frozen band applied to
a single stochastic baseline can flag `BASELINE_DRIFT_STOP` on noise.** The band did
its job (it refused to certify a comparison point that didn't reproduce), and the
frozen-rule discipline held (the band was not loosened post-hoc to rescue the run — that
would be the steering the freeze exists to prevent).

**Consequence / next lever:** the baseline band needs a *multi-draw* estimate (e.g. the
median of 2–3 baseline runs, or a wider band derived from the observed per-run variance)
before it can gate a stochastic re-measurement. Pool enlargement remains the standing
unblock for any powered claim (the recurring 0039–0045 caveat). The reactive-submit +
confirm-before-submit levers themselves are **untested against a valid baseline** — the
mechanism (Option A: real nudge-suppression on a trigger + the confirm partition) is
wired, unit-verified, and byte-pinned, but its net effect is unmeasured on this run.

## What ships regardless of the verdict

- The complete, unit-verified mechanism: the reverted gate, `reactive_policy.py`
  (3 gold-blind triggers), `confirm.py` (deterministic interceptor), Option A's
  behavior toggle, all byte-pinned (`params == {max_tokens: 2048}` survives; tool
  suite still exactly five; dual-seam schema `0046/1`).
- The five-sided predicate + total-pure verdict + the s→wc/flagged-wrong-emitted
  conservation (the de-attribution guard) + the 4b reconciliation — frozen and
  grid-total, ready for a valid baseline.
- The frozen predicate (pre-baseline) and the committed config freeze (SUT hash +
  derived thresholds as audit), both pin-tested.
- The **methodological finding** above — the first-class deliverable of this run.

## Run integrity

- 33/33 cells, `0041/pilot/2` exclusivity proof present, 3 typed degrades retained
  (not silently folded).
- Foreign resident `qwen3-14b-cc:latest` evicted before / re-pinned after
  (keep_alive=-1, expiry 2318 verified).
- Baseline artifacts persisted under `reactive_run/` (ledger + per-cell artifacts +
  summary). Train-on-test confound recorded (three specs tuned on the same 33 cells).
