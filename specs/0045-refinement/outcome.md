---
spec: "0045"
status: complete
verdict: TRADES_DIRECTIONS
created: 2026-07-13
---

# Outcome — 0045 refinement

**Typed verdict (frozen six-member total order, `decide_refinement_outcome`): `TRADES_DIRECTIONS`.**
The reopened direction is **found-but-unsubmitted**. Pilot-N SIGNAL, not an inferential claim.

The refined require-corroboration gate fixed the too-loose direction it was designed for —
silence→wrong-confidence fell 5 → 1 — but it reopened the too-tight direction catastrophically:
found-but-unsubmitted rose 1 → 8. This is precisely the trade the four-sided predicate was frozen to
catch, and precisely the risk the spec named ("a uniform tighten/loosen cannot fix it — it would
trade (a) for (b)"). Requiring corroboration made the gate fire so rarely (3/33, down from 0044's
~15/33) that the submit-discipline benefit the 0044 nudge bought (fu 6 → 1) was lost — fu came back
worse than even the pre-nudge baseline of 6.

## The six-member verdict (all enumerated; selected + all-true recorded)

| Member | Selected? | Why |
|---|---|---|
| `UNDER_POWERED` | no | covered joined = 31 ≥ floor 8; comparator s→wc = 5 ≥ 3 |
| **`TRADES_DIRECTIONS`** | **YES** | s→wc dropped (1 < 5) **AND** fu rose (8 > 1) — the (b) direction reopened |
| `RESIDUAL_PERSISTS` | (true, lower precedence) | `django-14315::8b` is not correct — recorded in `conditions_true`, out-ranked by the trade |
| `GATE_INERT` | no | benefit holds (s→wc dropped) |
| `GATE_CALIBRATED` | no | fu rose above 1 and a model is net-negative |
| `MISCALIBRATION_REMAINS` | no | the trade shape claimed it first |

`conditions_true = [trades-directions, residual-persists]` — worse-first precedence surfaced the
trade over the residual; both are recorded as data (the 0020/0023 discipline).

## Four-sided ledger (per model)

| Model | fired | conv | reg | net | s→wc | unfired-s→wc | fu |
|---|---|---|---|---|---|---|---|
| qwen3:14b | 1/11 (9%) | 2 | 3 | **−1** | 0 | 1 | 4 |
| qwen3:8b | 1/11 (9%) | 0 | 2 | **−2** | 0 | 0 | 3 |
| qwen3.5:4b | 1/11 (9%) | 2 | 0 | **+2** | 1 | 0 | 1 |
| **aggregate** | **3/33** | **4** | **5** | **−1** | **1** | **1** | **8** |

## Head-to-head vs 0044 (the pinned comparator)

| Metric | 0044 | 0045 | Δ |
|---|---|---|---|
| aggregate net (bucket axis) | +2 | −1 | **−3** |
| silence→wrong-confidence | 5 | **1** | −4 (the fix) |
| found-but-unsubmitted | 1 | **8** | +7 (the trade) |
| firing rate | ~15/33 | 3/33 | collapsed |

The one improved axis (s→wc 5 → 1) is partly a **de-attribution, not an elimination**: the record-only
`unfired_silence_to_wrong_confidence = 1` (qwen3:14b) shows one cell still went empty → wrong-file but
UNFIRED — the fired-conditioning loophole the record-only cross-check was built to expose, caught in
the data. Most of the s→wc drop is real (8b's weak-singleton wrong submissions stopped), but the
metric's fired-conditioning would have hidden this one cell without the cross-check.

## Named cells (AC5/AC6)

- **`django-14315::8b`** (the 0043+0044 residual): **still not correct** — but its failure mode
  CHANGED. In 0044 it was correct → wrong-file (fired, a confident wrong citation). Now the gate never
  fires → empty / found-unsubmitted. The confident-wrong-citation cost is gone; the submit-discipline
  cost replaced it. RESIDUAL_PERSISTS holds. Evidence needed to fix it: an 8b run whose verification
  time is preserved AND whose located span is credited without a wrong submission — not reachable by a
  purely stricter gate.
- **`pytest-10081::14b`** (the never-fired fu cell): **still never-fired, still found-unsubmitted** —
  exactly as the AC1 attribution predicted. It was uncorroborated in 0044, so require-corroboration
  cannot make it fire. The (b) direction was never going to be fixed by this rule; the run confirms it.
- **`flask-5014` (14b and 8b)** (rescued in 0044): **both REGRESSED** to empty / found-unsubmitted.
  In 0044 the nudge fired and they submitted correctly; the refined gate no longer fires on them, so
  they located the span but ran out the clock without submitting. These are 2 of the 5 regressions —
  the rescue was lost to the stricter gate.

## Interpretation

Require-corroboration is the wrong operating point: it eliminates the confident-wrong-citation cost by
almost never firing, which re-imposes the dawdle-after-locate cost the 0044 nudge existed to fix. The
gate errs in two directions on different cells, and this rule moved the whole population to the tight
side rather than separating the cells. The stage-1 attribution already recorded that the never-fired
cell was uncorroborated (so no corroboration rule rescues it) — the live run is consistent with that:
the rule helped the too-loose direction and hurt the too-tight one, with no net benefit.

The honest next lever is NOT a further threshold move (it would trade back). Candidates the recorded
data points to: (a) a corroboration requirement that is CONDITIONAL on model (8b's weak singletons are
the wrong-submission source; 14b's firing was already zero-regression in 0044 and should not have been
tightened), or (b) crediting the located-but-uncorroborated span for a SUBMIT nudge without the
confidence framing — decoupling "you found it, submit" from "this is confidently right." Both are new
specs, chosen mechanically from this run's four-sided ledger, never re-levered post-hoc on this data.

## Confounds & scope (recorded per the 0042 precedent)

- **Train-on-test**: the require-corroboration rule was derived from attributions on the same 33 cells
  re-measured here. At pilot N with enlargement parked this is an accepted, recorded confound — the
  verdict is a SIGNAL, not a generalizing claim. Pool enlargement remains THE standing unblock.
- **Single-cell sensitivity**: `RESIDUAL_PERSISTS` gates on one pilot-N cell (`django-14315::8b`);
  here it is out-ranked by the trade anyway, but the sensitivity is noted.
- **Run integrity**: 33/33 cells, 0 degrades, exclusivity clean (start + per-block), foreign resident
  `qwen3-14b-cc:latest` evicted before / `keep_alive=-1` re-pinned after (expiry 2318 verified),
  ~3.5 h across resumable budget-bounded invocations via the detached nohup wrapper.

## What shipped regardless of the verdict

The refinement's INFRASTRUCTURE ships and is correct independent of the operating-point result: the
silence→wrong-confidence cost class is now first-class and countable in every artifact (schema
`0045/1`), the (b)/(c) signals live in one gold-blind definition shared by the gate and the eval
postflight, the record-only unfired cross-check exposes the fired-conditioning loophole, and the
four-sided frozen predicate demonstrably caught a trade a two-sided net would have sold as "s→wc fixed."
The require-corroboration GATE itself is the lever that TRADES_DIRECTIONS — a candidate to be replaced,
not kept, by the mechanically-chosen next lever.

**Related specs:** [0044, 0043, 0042, 0041, 0040, 0035, 0033, 0030, 0029, 0023, 0020].
