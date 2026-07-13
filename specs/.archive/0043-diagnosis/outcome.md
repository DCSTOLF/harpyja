# Spec 0043 — typed outcome

## Verdict: `CLOCK_BOUND_PERSISTS`

Decided by `decide_diagnosis_outcome` (total pure function, frozen precedence)
over `PREREGISTERED_DIAGNOSIS_CONFIG_0043` (hash `4c7a871a8b20…`) and the
retained per-case pairs — **a pilot-N SIGNAL, not an inferential claim.**

Machine-readable summary: `diagnosis_run/diagnosis_summary.json`. Ledger:
`diagnosis_run/diagnosis_results.json` (33/33 cells, `0041/pilot/2`
exclusivity proof, 4 clean checks = start + 3 per-block, ZERO degrades, ZERO
suspect).

## The numbers (BEFORE = committed T9 covered subset; AFTER = this run)

| quantity | value |
|---|---|
| covered BEFORE subset | 31 cells (named in the summary; ≥ floor 8) |
| found-unsubmitted BEFORE | **6** (14b 2, 8b 1, 4b 3; ≥ floor 3 — NOT under-powered) |
| found-unsubmitted AFTER | **2** (4b: matplotlib new; sympy-16792-14b resolved to never-found) |
| detector-inconclusive | 0 BEFORE / 0 AFTER (no asymmetry caveat; detector `0043/1` both sides) |
| conversions (→ correct) | 2 (`psf__requests-1766::qwen3:14b`, `pydata__xarray-3993::qwen3:8b` — the latter a BEFORE found-unsubmitted cell) |
| regressions (correct →) | 3 (`pallets__flask-5014::qwen3:14b`, `pallets__flask-5014::qwen3:8b`, `django__django-14315::qwen3:8b`) |
| **net movement** | **−1** |

Verdict mechanics: `fu_after (2) < fu_before (6)` but `net (−1) ≤ 0` → the
FIXED branch's second conjunct fails → `CLOCK_BOUND_PERSISTS`, residual named:
the fix is insufficient on this evidence.

## What the run actually showed (the honest reading)

**The lever closed most of the submission gap — and the bidirectional
predicate caught its cost.** The submit-early nudge (the ONLY SUT delta,
`messages`-borne, params pin byte-identical) cut the found-but-unsubmitted
class from 6 to 2, and the 0042 marquee case (`astropy__astropy-12907::qwen3:14b`
— symbols delivering `separability_matrix`, previously expired on the clock)
now SUBMITS (empty → right-file-wrong-span, found-unsubmitted → submitted).
One prior found-unsubmitted cell converted all the way to correct
(`pydata__xarray-3993::qwen3:8b`). But the same nudge produced THREE
premature-submission regressions on previously-correct cells (both flask
cells and django-14315-8b submitted earlier, less-explored spans). Without
the 0042 bidirectional lesson, "2 conversions" would have read as a win; the
net −1 is exactly what the frozen predicate exists to surface.

**Residual (named):** the lever trades exploration depth for submission
discipline at the wrong margin — it fixes the dawdle-after-locate loss but
induces submit-before-verify losses. The follow-up lever is a
CONFIDENCE-CONDITIONED nudge ("submit once a tool result shows the exact
span" vs the current "submit as soon as possible" reading), a candidate next
spec; it was NOT applied here because the frozen stage-1 table names one
lever per attribution and re-levering after seeing these numbers would be the
post-hoc steering this spec's freezes exist to prevent.

## Attribution finding (AC1, committed at `attribution/attribution_table.json`)

From the persisted `eval_work` trajectories (31 clean adoption cells + 30
clean 0040 pilot cells; 5 `trajectory-missing` typed degrades for ledger
degrade cells that never wrote artifacts; sources pinned by filename +
sha256): the located-but-unsubmitted cells dawdled a **median of 5 assistant
turns AFTER the gold span was already in a tool result** (4 of 6 cells: 3–7
turns of post-locate exploration); terminal causes on the current SUT were
turn-cap 11 / wall-clock 7 / submitted 13. All timing is ESTIMATE-GRADE
(timestamp deltas — no latency was ever recorded; verified). The frozen
stage-1 lever table (hash `96626aca…`, committed BEFORE any number was
computed) mechanically selected `submit-early-prompt-nudge` (dawdle-high →
rank-1 cheapest lever), recorded as data in the config.

## The 4b inversion (AC3): NAMED — `larger-tool-outputs`

4b's mean tool-result bytes per case: **18,245** vs peer mean ~8,149 (ratio
2.24 ≥ the frozen 1.5 discriminator); turns ratio 1.33 and prompt-chars ratio
2.07 do not lead. The smallest model reads the LARGEST tool results, and at
its 131k context that converts to prefill cost on every turn of every heavy
repo — the serving-side mechanism behind its model-unreachable (HTTP-timeout
class) degrades. Observation from this run: with the endpoint gated and
exclusive, the chronic 4b heavy-repo degrades did NOT recur (33/33 clean) —
consistent with load, not model, as the amplifier.

## Provenance

- SUT hash (post-lever, frozen in config, verified by the driver at run
  start): `aeed1acab739…`; the 0034/0038 `params == {max_tokens: 2048}` pin
  and the 0042 prompt↔surface drift guard are green on the shipped surface.
- Run knobs identical to 0042 (10 turns / 240 s wall-clock / 300 s HTTP);
  the prompt nudge is the only delta.
- Two-stage freeze honored by construction: lever table committed before the
  attribution ran; config (cells, buckets, detector `0043/1`, floors, lever)
  committed before the live spend.
- Endpoint hygiene: foreign resident `qwen3-14b-cc:latest` evicted before the
  run, `keep_alive=-1` pin restored after (expiry 2318 verified).
