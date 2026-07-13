---
spec: "0043"
closed: 2026-07-12
---

# Changelog — 0043 diagnosis

## What shipped vs spec

All 6 acceptance criteria met, 19/19 tasks `[x]`. The spec DIAGNOSED the
submission gap ("found the span but didn't submit it") off the persisted 0040/0042
trajectories, added a first-class found-but-unsubmitted detector, attributed the 4b
heavy-repo degrade inversion, selected a lever by a frozen decision table, froze the
re-measurement config, implemented the lever preserving every SUT pin, re-measured
the 0042 pilot cells on the 0041-gated endpoint, and typed the outcome mechanically.

- **Verdict: `CLOCK_BOUND_PERSISTS`** (AC6), decided by `decide_diagnosis_outcome`
  (total pure, frozen precedence) over `PREREGISTERED_DIAGNOSIS_CONFIG_0043` (hash
  `4c7a871a…`). A pilot-N SIGNAL, not an inferential claim. Numbers: covered BEFORE
  subset 31 (≥ floor 8); found-unsubmitted 6 → 2 (BEFORE 14b 2 / 8b 1 / 4b 3; ≥ floor
  3, NOT under-powered); inconclusive 0/0 both sides (detector `0043/1`); conversions
  2 (`psf__requests-1766::qwen3:14b`, `pydata__xarray-3993::qwen3:8b` — the latter a
  BEFORE found-unsubmitted cell); regressions 3 (`pallets__flask-5014::qwen3:14b`,
  `pallets__flask-5014::qwen3:8b`, `django__django-14315::qwen3:8b`, all
  premature-submission losses from correct); **net −1**. `fu_after (2) < fu_before
  (6)` but `net ≤ 0` → the FIXED branch's second conjunct fails → PERSISTS.
- **The honest reading:** the submit-early nudge closed most of the submission gap
  (the astropy marquee case now submits; 1 cell converted all the way to correct)
  but induced submit-before-verify regressions on 3 previously-correct cells. The
  0042 BIDIRECTIONAL predicate is exactly what caught the trade — 2 conversions alone
  would have read as a win. Named follow-up: a CONFIDENCE-CONDITIONED nudge (a future
  spec, chosen mechanically NOT post-hoc — the stage-1 freeze forbids re-levering).
- **AC1 attribution** (`attribution/attribution_table.json`, offline, no model
  compute, pinned by per-source sha256): located-but-unsubmitted cells dawdled a
  median of 5 assistant turns AFTER the gold span was already in a tool result;
  terminal causes on the 0042 SUT turn-cap 11 / wall-clock 7 / submitted 13. All
  timing ESTIMATE-GRADE (verified: no latency field exists anywhere).
- **AC3 4b inversion NAMED — `larger-tool-outputs`:** 4b mean tool-result bytes
  18,245 vs peer mean ~8,149 (ratio 2.24 ≥ frozen 1.5); turns ratio 1.33 and
  prompt-chars 2.07 do not lead. Corroboration: on this gated exclusive run the
  chronic 4b heavy-repo degrades did NOT recur (33/33, zero degrades) — consistent
  with serving load as the amplifier.
- **AC2 machinery** (all flat in `harpyja/eval/`, sibling tests): `submission_gap.py`
  (5-member `SubmissionOutcome` enum, total over a 6-row fixture matrix; overlap via
  `metrics.span_hit_kind` BY IDENTITY — one-oracle; submitted-then-dropped via the
  0033 `citations_submitted`/`citations_surviving` counts — one-counter; unparseable
  ⇒ `DETECTOR_INCONCLUSIVE`, never `never-found`; `DETECTOR_VERSION` `0043/1`),
  `clock_attribution.py`, `lever_table.py`, `diagnosis_config.py` (two power floors:
  `min_covered_before_cells=8` AND `min_before_found_unsubmitted=3`),
  `diagnosis_outcome.py` (4-branch verdict, `UNDER_POWERED` an enum member never
  prose), `diagnosis_run.py` (gated via `run_gated_pool_pilot`).
- **Dual-seam schema bump:** `VERIFIER_SCHEMA_VERSION` `0038/1 → 0043/1` —
  `submission_outcome` + `detector_version` threaded through BOTH seams
  (`build_trajectory_record` param + `run_verified_case` computed-from-gold),
  presence-REQUIRED on a `0043/1` artifact (value may be None when no gold), legacy
  versions validate unchanged. 4 existing version-pin tests amended in the same change.
- **The lever (AC4 FIX):** ONE sentence appended to `build_initial_prompt`
  (`messages` only); `params == {max_tokens: 2048}` pin survives VERBATIM
  (`test_params_pin_survives_submit_early_nudge`) + 0042 drift guard green. SUT change
  scope: ONLY `context_map.py`'s prompt.
- **Two-stage freeze honored by construction:** lever table (hash `96626aca…`)
  committed BEFORE any attribution number; config (hash `4c7a871a…`, SUT hash
  `aeed1aca…` post-lever) committed AFTER mechanical lever selection, BEFORE live
  spend; the driver verifies the working-tree SUT hash at startup (STOP exit 2 on
  drift).

## Deviations from plan

- (a) T6's optional refactor moot — `clock_attribution` reused
  `submission_gap._parse_tool_content` from the start.
- (b) `diagnosis_config.json` committed AFTER T13 (not at T11) so the recorded
  `sut_hash` names the post-lever SUT — the plan's freeze ordering (post-selection,
  pre-live-spend) still honored.
- (c) the T18 live run was launched detached via a `nohup` wrapper (9 budget-bounded
  invocations, ~70 min; the 0042 harness-cap lesson applied proactively).
- (d) the codex round-1 hang was a false alarm (the run was already non-interactive
  and complete).

## Review

Round 1 both changes-requested (headline: per-turn latency never recorded — AC1
unsatisfiable as written; "COMMITTED trajectories" factually wrong — evidence lives
in gitignored `eval_work`; missing freezes); all 10 action items applied. Round 2
both approve-with-comments, quorum met; all round-2 residuals folded post-quorum (AC2
enum totality via 0033 counts; `CLOCK_BOUND_UNDER_POWERED` fourth branch + floors;
per-side inconclusive; ledger-latency claim VERIFIED FALSE by direct inspection and
reclassified estimate-grade; explicit two-stage freeze invariant; wording).

## Files touched

- `harpyja/eval/submission_gap.py` (new) + `test_submission_gap.py`
- `harpyja/eval/clock_attribution.py` (new) + `test_clock_attribution.py`
- `harpyja/eval/lever_table.py` (new) + `test_lever_table.py`
- `harpyja/eval/diagnosis_config.py` (new) + `test_diagnosis_config.py`
- `harpyja/eval/diagnosis_outcome.py` (new) + `test_diagnosis_outcome.py`
- `harpyja/eval/diagnosis_run.py` (new) + `test_diagnosis_run.py` + `test_diagnosis_run_integration.py`
- `harpyja/eval/live_verifier.py` (VERIFIER_SCHEMA_VERSION `0038/1 → 0043/1`, dual-seam field) + `test_live_verifier.py`
- `harpyja/scout/context_map.py` (the lever — submit-early nudge on `build_initial_prompt`) + `test_context_map.py`
- `harpyja/scout/test_explorer_backend.py` (params-pin survival test)
- `specs/0043-diagnosis/` — spec/plan/tasks/review/outcome, `lever_table/lever_table.json`, `attribution/attribution_table.json`, `diagnosis_config/diagnosis_config.json`, `diagnosis_run/run_diagnosis.py` + committed durable artifacts

## Suite / lint

- Suite: 1438 passed / 1 skipped / 66 deselected (was 1397/1/65 at 0042 close; +41
  tests, +1 integration deselected).
- ruff: 40 = 40 baseline, zero-new.

## ADR proposed for history.md

2026-07-12 — see the `## 2026-07-12 — **Spec 0043 (diagnosis) …` entry appended to
`.speccraft/history.md` (newest-first).

## Conventions proposed

- **New (two-stage freeze):** when a spec both SELECTS an intervention from measured
  data AND measures that intervention, the SELECTION RULE freezes before the numbers
  are computed/seen (stage 1) and the config naming the selection freezes after
  selection but before any live spend (stage 2) — a generalization of the
  single-stage freeze-before-run convention.
- **Extension (0021 labeled-estimate rule):** a spec claim that a quantity is
  MEASURED must be VERIFIED against the actual persisted artifact schema before the
  claim is made — an unverified "from the ledger/record" claim is downgraded to a
  labeled estimate (or an honest "needs instrumented re-run"), never asserted as
  measured.
