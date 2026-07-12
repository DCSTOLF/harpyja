# Spec 0042 — typed outcome record (AC7)

## Outcome: `ADOPTED_AND_CONVERTS`

Decided mechanically by `decide_adoption_outcome` (total pure function) over the
frozen `PREREGISTERED_ADOPTION_CONFIG_0042` (hash `c4e24c249e81c63b9e926c400266b99dd89971c17a8c2c46121287401ec0bcb2`,
committed at `precheck/adoption_config.json` BEFORE any live call) and the AC6
trajectory-verified artifacts (`adoption_run/artifacts/`, ledger
`adoption_run/adoption_results.json`, summary `adoption_run/adoption_summary.json`,
schema `0042/adoption-run-summary/1`).

**Label strength (pinned wording): observed ≥1 conversion signal at pilot N with
net flip count +1 — a SIGNAL at pilot scale, NOT an inferential claim. The
0023/0026 ≥8-discordant-pairs floor is what a claim would need.**

## The numbers

| quantity | value |
|---|---|
| symbols ADOPTION (clean cells) | **24/31 (77%)** vs the 0/28 baseline |
| — qwen3:14b | 7/11 |
| — qwen3:8b | 10/11 |
| — qwen3.5:4b | 7/9 |
| RFWS denominator (0040 clean RFWS cells of models run) | 4 (≥ floor 3 → NOT under-powered) |
| RFWS→exact conversions | **1** (`pallets__flask-5014::qwen3:8b` → correct, symbols invoked) |
| exact→RFWS regressions | 0 |
| net | **+1** |
| run integrity | 33 cells recorded; 31 clean; 2 typed degrades; **0 suspect** |

The two degrades are both `qwen3.5:4b` `model-unreachable` at the bounded
re-run cap (`django-13516`, `sympy-16792`) — the SAME persistent heavy-repo
degrade class 0040 recorded (3 of 5 were 4b's), explicitly out of this spec's
scope and still a separate spec's diagnosis.

Exclusivity: every block ran under the 0041 gate (`0041/pilot/2` proof in the
ledger, start + per-block checks, zero contended checks, zero suspect cells);
single-operator context; the foreign resident `qwen3-14b-cc:latest` was evicted
before the run and its `keep_alive=-1` pin restored after (expiry 2318 verified
both ways).

## Required framings (per AC7)

- **0030's record is corrected**: its "lift unproven" refutation — and every
  subsequent "symbols not invoked" observation (0031/0034/0035/0040) — was
  measured on an UNUSABLE tool: unadvertised in the prompt (stale 0027 text),
  when-less description, unreachable before a candidate file (`path` required),
  and structurally penalized in span accounting (nested dict → zero spans).
- **The 0/28 baseline was measured under that defect condition**, so the
  24/31-vs-0/28 delta is **fix-vs-defect, not tool-vs-no-tool**. No
  tool-vs-no-tool claim is made here.
- **Attribution confound (accepted, recorded)**: all four fixes landed at once
  (the fairness invariant), so this result cannot attribute WHICH fix drove
  adoption. Deliberate trade; no follow-up should re-litigate it.
- **No capability claim**: model spread here (8b adoption 10/11 and correct
  1→3; 14b correct 3→3; 4b correct 1→1) is a bake-off INPUT, not a ranking.

## Live observations (recorded for follow-up; SUT frozen during the run)

1. **`path=""` routing defect — observed live, FIXED POST-MEASUREMENT.** The
   14b astropy cell sent `{"path": "", "name": "separability matrix"}`; the
   `path is None` check routed it file-local and silently ignored `name`. All
   33 cells were measured on the pre-fix SUT (run integrity preserved); the fix
   (`if not path:`) + two pins (`test_symbols_empty_string_path_routes_repo_wide_not_file_local`,
   `test_symbols_empty_path_and_no_name_is_args_missing`) landed immediately
   after exit 0.
2. **`symbols` on a NONEXISTENT path returned silent `[]`** (observed:
   `symbols({"path": "digest-auth/*"})` in the 14b requests cell) — a 0030-era
   gap of the same silent-`[]` class 0035 fixed for grep/ls and AC3 fixed for
   the absent index. **FIXED POST-MEASUREMENT** (operator-prompted, after exit
   0, all cells measured on the pre-fix SUT): no-records AND file-absent →
   `symbols-path-not-found: '<path>'` (0035 replacement marker); records still
   win over disk absence (the no-new-parser contract, pinned by
   `test_symbols_records_win_over_disk_absence`); a real file with no records
   keeps honest-`[]` (`test_symbols_existing_file_without_records_is_honest_empty`;
   marker pin `test_symbols_nonexistent_path_returns_replacement_marker`).
3. **The 14b RFWS→empty movements are (at least partly) wall-clock artifacts,
   not tool failures.** In the astropy cell the tool DELIVERED the exact target
   (`separability_matrix`, `astropy/modeling/separable.py:66–102` — this spec's
   own lexical-unreachability example) on the final turn; the 240s
   `scout_wall_clock_s` expired before the model submitted. 9/12 turns used,
   every turn finish=tool_calls, no degrade markers. The heavy-repo timeout
   class remains the binding constraint on pilot coverage (0040's finding,
   unchanged, still out of scope here).
4. **Failure-mode shift**: with symbols adopted, 14b's two 0040 RFWS cells
   ended `empty` (explored correctly, ran out of clock / didn't submit) rather
   than citing a wrong span. A different failure to fix (submit discipline /
   wall-clock), not a span-precision failure.

## Disposition

The four stacked defects (prompt, description, positioning, result shape) were
the adoption barrier — `STILL_NOT_ADOPTED` is refuted by a fair test. The tool
is adopted (24/31) and shows a positive conversion signal (net +1 on N=4). The
value question graduates from "unusable" to "under-measured": a powered
conversion claim needs the pool enlargement (the standing 0040/0039 unblock),
which remains the named next step.
