---
spec: "0046"
closed: 2026-07-14
---

# Changelog — 0046 submission

## What shipped vs spec

- **Typed outcome: `BASELINE_DRIFT_STOP`** (frozen rule, first-true over the five-sided
  predicate's precedence). The BASELINE arm (reverted 0044 gate, current SUT,
  `explorer_reactive_confirm=False`) scored **NET 0** (conv 3 / reg 3 over 29 paired
  cells) vs the committed 0040/0042 pre-nudge table — **outside the frozen sanity band
  `[1, 3]`**. Per the rule frozen BEFORE the numbers, an out-of-band baseline types
  `BASELINE_DRIFT_STOP` and the run **STOPPED before typing the new-arm verdict**. The
  NEW arm (T28) was **not run** (operator-confirmed).
- **The first-class deliverable is the METHODOLOGICAL FINDING, not the null:** a single
  stochastic run's NET band on 33 cells cannot gate a re-measurement. 0044 drew
  conv 3 / reg 1 (net +2); the SAME gate on the SAME cells drew conv 3 / reg 3 (net 0) —
  a 2-regression swing on ~7 correct cells, well within qwen3 run-to-run variance. The
  metric's noise is comparable to the effect sizes four specs (0042–0046) have tuned
  against. **The band did its job (refused to certify a comparison point that did not
  reproduce), and the frozen-rule discipline held — the band was NOT loosened post-hoc.**
- **The mechanism SHIPS, unit-verified and byte-pinned, but is UNMEASURED against a valid
  baseline:** 0045's corroboration lever reverted (retired in place, import-absence
  pinned); `scout/reactive_policy.py` (3 gold-blind triggers: `symbols-empty` /
  `hit-in-comment` / `tool-disagreement`, set-valued, order-stable); `scout/confirm.py`
  (deterministic `PASS`/`FAIL`/`CONFIRM_ERROR`/`NO_CANDIDATE` submit-path interceptor
  reusing host `read_span`, no model turn, no gold); and Option A's real behavior behind
  a one-bit `explorer_reactive_confirm` toggle (OFF = baseline pure-0044; ON = reactive
  nudge-suppression + confirm partition). Tool suite still EXACTLY five;
  `explorer_think=None ⇒ params == {max_tokens: 2048}` byte-pin SURVIVES; dual-seam
  `VERIFIER_SCHEMA_VERSION 0045/1 → 0046/1`.
- **The five-sided predicate is frozen and reusable:** `flagged-wrong-emitted` counts the
  confirm-flag's real cost as a first-class side (partition-partner of s→wc with the sum
  conserved — the de-attribution guard), the total-pure verdict, the disposition-keyed 4b
  reconciliation, and the frozen config (SUT hash + derived thresholds as audit) all
  exist, are grid-total, and await a powered baseline.

## AC status

- **AC1 (revert + keep apparatus)** — met (unit). 0045's `qualifying_confidence_spans` /
  `_is_corroborated` retired with `CORROBORATION_RETIRED_RATIONALE`; 0044 firing restored;
  four-sided apparatus + s→wc counting + gold-blind signals + unfired cross-check retained.
- **AC2 (reactive policy)** — met (unit). Three gold-blind triggers with near-miss
  negatives, multi-trigger set order-stable, no-trigger→submit-best, triggered-explore
  bounded by the existing `scout_max_turns` / `scout_wall_clock_s` caps.
- **AC3 (confirm-before-submit)** — met (unit). (a) separable-modules import guard
  (reactive_policy/gate import NEITHER `confirm` module NOR `ConfirmationOutcome`); (b)
  confirm-FAIL emits FLAGGED without changing the firing count vs confirm-PASS.
- **AC4 (artifact + accounting)** — met (unit). Four additive fields appended-last,
  legacy `0045/1` validates, `0046/1` threaded through both seams; grid-totality incl.
  `flagged-wrong-emitted`; partition boundary pinned; both cross-checks + flag-rate.
- **AC5 (baseline arm)** — typed `BASELINE_DRIFT_STOP`: the baseline did NOT reproduce the
  0044 operating point on this single stochastic draw.
- **AC6 (new arm)** — **NOT run** per the AC5 frozen-rule STOP (operator-confirmed). The
  three named cells (flask-5014, django-14315::8b, pytest-10081::14b) enumerated but not
  re-measured.
- **AC7 (typed outcome)** — machinery met (unit); the live five-sided verdict was not
  reached because the run stopped at the baseline gate.

## Files touched

- `harpyja/scout/confidence_gate.py`, `harpyja/scout/reactive_policy.py` (new),
  `harpyja/scout/confirm.py` (new), `harpyja/scout/explorer_loop.py`,
  `harpyja/scout/explorer_backend.py`
- `harpyja/config/settings.py` (`explorer_reactive_confirm`)
- `harpyja/eval/live_verifier.py` (`0046/1`), `harpyja/eval/reactive_config.py` (new),
  `harpyja/eval/reactive_observability.py` (new), `harpyja/eval/reactive_outcome.py` (new),
  `harpyja/eval/reactive_run.py` (new)
- Sibling tests for each of the above; `specs/0046-submission/reactive_run/` artifacts
  (baseline ledger + config freeze + drivers), `predicate_freeze/five_sided_predicate.json`

## Deviations

- **Option A behavior addition mid-implementation.** T1–T12 were initially
  observability-only (record-but-don't-change), which makes the two arms behaviorally
  identical and NET 0 a priori. Caught mid-build; Option A wired the REAL behavior
  (reactive nudge-suppression on a trigger + the confirm partition) behind the single-bit
  `explorer_reactive_confirm` toggle so both arms share byte-identical code and only the
  flag differs.
- **Confirmation records on backend attributes, not `LoopResult`.** The confirm outcome +
  disposition are carried on the explorer backend seam / trajectory record, not as
  `LoopResult` return fields.
- **T28 skipped** per the AC5 `BASELINE_DRIFT_STOP` frozen rule (operator-confirmed) — no
  further live spend.
- **Derived thresholds committed as AUDIT data, config hash stable.** The
  `flagged-wrong-emitted` ceiling (⌊0.5 × baseline s→wc 6⌋ = 3) and the flag-rate range
  were computed from the baseline arm and recorded in `reactive_run/reactive_config.json`
  as audit — never applied (the new arm did not run), so the frozen `REACTIVE_CONFIG_HASH_0046`
  is unchanged.
- **T25 dedup DECLINED with reason** (mirror-not-share vs the 0044 `submission_*` modules —
  frozen historical pins must not couple; the 0040-T22/0041-T21/0042-T7/0045-T18 precedent).
- **Run integrity:** 33/33 cells, `0041/pilot/2` exclusivity proof present, 3 typed
  degrades retained (not folded); foreign resident `qwen3-14b-cc:latest` evicted-before /
  `keep_alive=-1` re-pinned-after (expiry 2318). Train-on-test confound recorded.

## Next spec (named): POOL ENLARGEMENT

This is **not** "the lever traded" — it is "the instrument can no longer resolve whether a
lever traded at all," because the metric's run-to-run noise now equals the effect sizes
0042–0046 have chased. Policy tuning on 33 cells is DONE until there is enough data to
measure it. Pool enlargement was pre-committed two specs ago (the standing 0039–0045
unblock); the baseline stop makes it BLOCKING. Carry-forward: reactive-submit +
confirm-before-submit remain toggleable (`explorer_reactive_confirm`, default OFF), fully
instrumented, and byte-pinned, awaiting a powered baseline.
