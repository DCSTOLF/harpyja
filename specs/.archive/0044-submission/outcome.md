# Spec 0044 — typed outcome

## Verdict: `CONDITIONED_NUDGE_SHIPS`

Typed mechanically by `decide_submission_outcome` (total pure, frozen five-member
precedence, `PREREGISTERED_SUBMISSION_CONFIG_0044`, config hash `0079c627de…`,
post-lever SUT hash `1ef7ce8a5a…`) over the committed BEFORE baseline
(`specs/.archive/0043-diagnosis/attribution/attribution_table.json`,
sha256-verified `4fa58df66e…`, detector `0043/1` both sides) and the gated AFTER
ledger (`submission_run/submission_results.json`, `0041/pilot/2`, exclusivity
`start-plus-per-block` — 4 checks, all clean, zero foreign residents, the two
unseeable residuals named in the proof). **Pilot-N SIGNAL, not an inferential
claim** (the standing 0039/0040/0042/0043 pool-enlargement unblock applies to
any powered claim).

`conditions_true = [conditioned-nudge-ships]` — exactly one condition held:
not under-powered (covered_before 31 ≥ 8; fu_before 6 ≥ 3), not never-fires
(14b fired on 5 cells > 0), not still-trades-off (no model net-negative,
aggregate net +2 > 0), not nudge-inert (3 conversions, fu dropped).

## The headline numbers (vs 0043's unconditional nudge)

|                        | 0043 unconditional | 0044 conditioned |
|------------------------|--------------------|-------------------|
| found-but-unsubmitted  | 6 → 2              | **6 → 1**         |
| conversions            | 2                  | **3**             |
| regressions            | 3                  | **1**             |
| NET                    | **−1**             | **+2**            |

The evidence-conditioned gate preserved most of the unconditional nudge's
found-but-unsubmitted fix while cutting its regression cost from 3 to 1.

## Per-model (the pre-registered readings, checked)

| model | cells | conv | reg | net | firings | rate |
|-------|-------|------|-----|-----|---------|------|
| qwen3:14b  | 11 | 1 | 0 | **+1** | 5 | 45% |
| qwen3:8b   | 11 | 1 | 1 | **0**  | 9 | 82% |
| qwen3.5:4b | 10 | 1 | 0 | **+1** | 1 | 10% |

- **14b (pre-registered beneficiary)**: net +1 — `django__django-14315`
  wrong-file → correct with the nudge FIRED, zero regressions. The gate fired
  on 5/11 cells; NEVER_FIRES did not trigger.
- **8b (pre-registered: regressions are the ship/no-ship signal)**: firing was
  HIGH (9/11, 82%) — exactly the pre-registered expected shape given 8b's
  10/11 symbols adoption — and 8b **regressed one cell** (see residual below)
  while converting one (`pydata__xarray-3993` empty → correct, fired — the
  same cell the unconditional nudge converted). Net 0: the frozen predicate's
  no-model-NET-negative conjunct holds (the conversion offsets the
  regression), so SHIPS types mechanically — but under the pre-registered 8b
  reading (success = regressions **= 0** at any firing rate) this is a
  QUALIFIED ship with a named single-cell residual, not a clean 8b pass.
- **4b (pre-registered inert)**: firing 1/10 — consistent with expectation.
  Its one conversion (`pallets__flask-5014` empty → correct) happened with
  the nudge NOT fired, so it is NOT attributable to the conditioned gate —
  it is attributable to the other half of the one SUT delta (the removal of
  the 0043 unconditional sentence) or to run noise. 4b's lever remains the
  future tool-result-compression spec.

## AC7 — the 0043 casualty re-checks

| cell | 0042 (pre-nudge) | 0043 (unconditional) | 0044 (conditioned) | holds? |
|------|------------------|----------------------|--------------------|--------|
| pallets__flask-5014::qwen3:14b | correct | regressed | **correct** (fired) | YES |
| pallets__flask-5014::qwen3:8b  | correct | regressed | **correct** (fired) | YES |
| django__django-14315::qwen3:8b | correct | regressed | **wrong-file** (fired) | **NO** |

Two of the three casualties are rescued — the conditioned nudge fired on both
flask cells and they still submitted correctly. `django__django-14315::qwen3:8b`
regressed AGAIN (fired): this cell is where 8b's verification time still
matters, and it is the named residual. Notably the same case moved the
opposite way on 14b (wrong-file → correct, fired): the cell swapped models
rather than being lost.

## Attributable nulls (the AC3 instrumentation, over non-correct AFTER cells)

- `never-fired`: 16 — includes the ONE remaining found-but-unsubmitted cell
  (`pytest-dev__pytest-10081::qwen3:14b`): the trajectory never contained a
  qualifying clean ≤5-span symbols result, so the gate never fired — this is
  the codex round-2 "gate may be too narrow" risk surfacing as DATA, exactly
  where the record-only fields (b)/(c) feed the next spec's gate choice.
- `fired-on-wrong-span`: 6 — the measured cost of the deliberately-loose
  pre-registered projection. Five of the six are 8b cells that moved
  empty → wrong-file with the nudge fired: the nudge converts 8b's honest
  empties into wrong-file SUBMISSIONS. This movement is invisible to the
  bucket-net predicate (empty and wrong-file are both non-correct) but it is
  a real behavioral cost, named here for the record.
- `fired-but-ignored`: 1.

## Run integrity

- 33 cells attempted, 32 clean, 1 typed degrade retained:
  `sympy__sympy-16792::qwen3.5:4b` `model-unreachable` after the one bounded
  re-run (attempts 2) — the known 4b heavy-repo class (0040/0042/0043), out of
  scope, excluded from the join.
- Driver: `submission_run/run_submission.py`, 9 budget-bounded invocations
  (~75 min wall clock, detached via nohup wrapper — the 0042 harness-cap
  lesson), resumable ledger keyed `SUBMISSION_CONFIG_HASH_0044`, exit 0.
- Stage-2 freeze honored: `submission_config/submission_config.json` committed
  after the SUT lever landed and before any live call; the driver verified the
  committed config hash AND the working-tree SUT hash at every invocation.
- Endpoint hygiene: foreign resident `qwen3-14b-cc:latest` evicted before the
  run; `keep_alive=-1` pin restored after (expiry 2318 verified).
- Params byte-pin (`explorer_think=None ⇒ params == {max_tokens: 2048}`) and
  the 0042 prompt↔surface drift guard green throughout; the whole delta rode
  `messages` only.

## Named residuals / follow-ups

1. **`django__django-14315::qwen3:8b`** — the one casualty the conditioned
   nudge did not rescue; 8b's pre-registered reading (regressions = 0) is not
   met, so the ship is qualified at pilot-N.
2. **The 8b fired-on-wrong-span pattern** (5 cells empty → wrong-file, fired) —
   a bucket-net-invisible cost; a tighter gate for 8b (or per-model gating)
   is a candidate refinement, to be chosen from the recorded (b)/(c)
   observability fields, never post-hoc on this run.
3. **The narrow-gate tail** — `pytest-10081::qwen3:14b` stayed
   found-but-unsubmitted because the gate never fired; grep/read_span-derived
   evidence is outside the pre-registered signal (a) by design.
4. **Pool enlargement** remains THE standing unblock for any powered claim.
5. The 4b `model-unreachable` degrade class and its compression lever remain a
   separate named future spec.
