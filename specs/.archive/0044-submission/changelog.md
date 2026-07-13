---
spec: "0044"
closed: 2026-07-13
---

# Changelog — 0044 submission

## What shipped vs spec

Confidence-CONDITIONED submit-early nudge: the ONE two-part SUT delta —
(i) REMOVE the 0043 unconditional submit-early sentence from `build_initial_prompt`,
(ii) ADD a gold-blind, evidence-gated mid-loop nudge that fires only when a confident
symbols-derived exact span is already in hand — re-measured against the committed
0040/0042 pre-nudge baseline through the 0041-gated exclusive endpoint. All 8 ACs met.

- **AC1 (gate, unit)** — `harpyja/scout/confidence_gate.py`: a `symbols` result QUALIFIES
  iff clean (no 0035 marker of either shape), bounded (1..`CONFIDENCE_MAX_QUALIFYING_SPANS=5`
  spans), and exact-span-shaped (every span non-None start/end). `CONFIDENCE_SIGNAL =
  "symbols-exact-span"`; `CONFIDENCE_NUDGE_TEMPLATE` multi-span wording, `role: user`.
  Gold-blind by construction (lives in `scout/`, sees only the trajectory; ast-pinned
  no-eval-import). Fixture-pinned on every edge (qualifying → fires once; grep-only/degraded
  ANNOTATION/REPLACEMENT/over-bound → no fire; multi-span → fires with multi-span wording).
- **AC2 (evidence-gated, unit)** — `harpyja/scout/explorer_loop.py`: a many-turn no-span run
  receives NO nudge (the 0043 turn/time failure mode is structurally impossible); fires at
  most once per case; no turn-count / wall-clock fallback.
- **AC3 (injection seam, unit)** — `explorer_loop.py`: qualifying result stashed in
  `_answer_tool_call`; ONE `role:user` nudge appended strictly at the POST-BATCH boundary
  (0029 answer-all-N safe — never interleaved inside an N-call batch); a non-tombstoned
  `"confidence-nudge"` record kind survives `scout_history_char_cap` truncation; no
  loop-detection perturbation; not a model turn. The 0043 unconditional sentence is REMOVED
  (`context_map.py`, `test_submit_early_nudge_removed_from_prompt`). `LoopResult` gains
  `confidence_fired` / `confidence_triggering_signal` / `confidence_firing_turn` /
  `confidence_firing_spans`. Params byte-pin held: `test_params_pin_survives_confidence_nudge`
  (params == `{max_tokens: 2048}` verbatim — the whole delta rides `messages` only).
- **AC4 (artifact + dual-seam bump, unit)** — `harpyja/eval/live_verifier.py`:
  `VERIFIER_SCHEMA_VERSION 0043/1 → 0044/1` (additive), confidence facts presence-required on
  0044/1 and threaded through BOTH seams (`build_trajectory_record` params + `run_verified_case`
  written artifact — the dual-seam checklist's 4th application, written-JSON pinned); record-only
  observability fields (`grep_hits_inside_symbol_spans`, `convergent_evidence`) + `confidence_null`
  presence-required on `run_verified_case`-assembled artifacts; legacy versions validate unchanged;
  5 version-pin tests amended same-change. `harpyja/eval/submission_observability.py`: eval-side
  POSTFLIGHT record-only fields (b) grep-inside-symbol-span containment and (c) convergent evidence
  (overlap via `span_hit_kind` BY IDENTITY — one-oracle-reuse), and `classify_confidence_null`
  (never-fired / fired-but-ignored / fired-on-wrong-span; None on correct), reusing
  `submission_gap._parse_tool_content` (one-parser-reuse). Signal (d) dropped.
- **AC5 (frozen config + total-pure verdict, unit)** — `harpyja/eval/submission_config.py`:
  `PREREGISTERED_SUBMISSION_CONFIG_0044` (frozen dataclass of LITERALS drift-pinned to SUT
  constants; hash `SUBMISSION_CONFIG_HASH_0044 = 0079c627de…`; sut_hash covers `confidence_gate.py`;
  baseline pinned by path + sha256 `4fa58df66e…` with fu_before=6 re-derived in the pin test;
  floors 8/3; `never_fires_max_beneficiary_firings=0` keyed to qwen3:14b; nudge template+role as
  config data; per-model expected readings as data). `harpyja/eval/submission_outcome.py`:
  `decide_submission_outcome` — total pure, FIVE members (UNDER_POWERED / NEVER_FIRES /
  STILL_TRADES_OFF / NUDGE_INERT / CONDITIONED_NUDGE_SHIPS) under frozen precedence, benefit
  conjunct on SHIPS, all true conditions recorded, grid-totality tested; the power floors are
  CONSUMED by the UNDER_POWERED branch.
- **AC6 (re-measure, integration)** — `harpyja/eval/submission_run.py`: `run_submission_cells` via
  `run_gated_pool_pilot` (live=True, ledger 0041/pilot/2 keyed by config hash, resumable, per-block
  eviction, `expected_sut_hash` startup verify = typed STOP on drift); `load_baseline_cells`
  (sha256-verified); `build_submission_run_summary` (suspect/degraded excluded). Driver
  `submission_run/run_submission.py`: STOP-AND-WARN resumable, exit 0/2/3, verifies committed config
  hash + SUT hash at every invocation.
- **AC7 (casualty re-checks, integration)** — flask-5014 holds correct on 14b AND 8b (both fired);
  django-14315::8b regressed AGAIN (correct→wrong-file, fired) — the named residual; the same case
  converted on 14b (`test_submission_run_integration.py` enumerates the casualty cells).
- **AC8 (typed outcome, doc)** — `outcome.md`: `CONDITIONED_NUDGE_SHIPS` typed mechanically, all
  true conditions recorded, per-model firing rates reported, pilot-N signal.

## The live result (T22, exit 0)

Verdict `CONDITIONED_NUDGE_SHIPS` (only true condition). found-but-unsubmitted 6→1;
conversions 3 / regressions 1 / NET +2 (vs 0043's unconditional nudge: 2/3, net −1).
Per model: 14b net +1 (fired 5/11=45%), 8b net 0 (1 conv 1 reg, fired 9/11=82% — the
pre-registered expected-high shape), 4b net +1 (fired 1/10; its conversion was UNFIRED,
attributable to the sentence removal not the gate — inert-as-predicted). Attributable
nulls: never-fired 16 (incl. the one remaining fu cell pytest-10081::14b — the narrow-gate
risk as data), fired-on-wrong-span 6 (5 are 8b empty→wrong-file, a bucket-net-invisible
cost, named), fired-but-ignored 1. 33 cells: 32 clean, 1 typed degrade
(sympy-16792::4b model-unreachable, known 4b heavy-repo class, 2 attempts). Exclusivity
0041/exclusivity/1: 4 checks clean. Endpoint qwen3-14b-cc evicted before / keep_alive=-1
re-pinned after (expiry 2318 verified). ~75 min, 9 budget-bounded invocations via detached
nohup wrapper. Suite 1508 passed / 1 skipped / 68 deselected (was 1438/1/66 at 0043 close);
ruff zero-new (40=40). Two review rounds (round-1 both changes-requested → 9 items applied;
round-2 codex approve-with-comments = quorum, claude-p changes-requested → 10 residuals folded
post-quorum per precedent).

## Files touched

- `harpyja/scout/confidence_gate.py` (NEW) + `test_confidence_gate.py` (NEW)
- `harpyja/scout/context_map.py` (0043 sentence removed) + `test_context_map.py`
- `harpyja/scout/explorer_loop.py` (injection seam, LoopResult facts, `_total_chars` fix)
- `harpyja/scout/explorer_backend.py` (threads 4 confidence facts) + `test_explorer_backend.py`
- `harpyja/eval/live_verifier.py` (0044/1 dual-seam) + `test_live_verifier.py`
- `harpyja/eval/submission_observability.py` (NEW) + `test_submission_observability.py` (NEW)
- `harpyja/eval/submission_config.py` (NEW) + `test_submission_config.py` (NEW)
- `harpyja/eval/submission_outcome.py` (NEW) + `test_submission_outcome.py` (NEW)
- `harpyja/eval/submission_run.py` (NEW) + `test_submission_run.py` (NEW) + `test_submission_run_integration.py` (NEW)
- `specs/0044-submission/submission_config/submission_config.json` (committed stage-2 freeze)
- `specs/0044-submission/submission_run/run_submission.py` (STOP-AND-WARN driver)
- `specs/0044-submission/{outcome.md,review.md,submission_run/submission_summary.json}`

## Deviations

- (a) **T3/T4 amended the 0043 params-pin test** — `test_params_pin_survives_submit_early_nudge`
  asserted the removed sentence; it became `test_params_pin_survives_confidence_nudge` in the same
  change (the exact-count/pin reconcile-in-one-change discipline).
- (b) **A latent pre-existing `_Session._total_chars` crash was fixed** — None tombstones mid
  `maybe_truncate` (reachable only with ≥2 droppable observations), exposed by the T5 truncation
  fixture; recorded as a pre-existing fix, not a 0044 behavior change.
- (c) **T19/T20 smoke follows the 0043 refusal-path-only precedent** (never fires live cells) rather
  than the plan's "one gated cell under `HARPYJA_REQUIRE_LIVE_STACK`" — integration = STOP-AND-WARN
  refusal path + AC7 casualty-cell enumeration, opt-in per 0041.
- (d) **sympy-16792::4b excluded as a typed degrade** after its bounded re-run (attempts 2) — the
  known 4b heavy-repo `model-unreachable` class, out of scope.
- (e) **QUALIFIED ship, not re-typed** — `decide_submission_outcome` types SHIPS mechanically (no
  model net-negative + benefit conjunct), but the pre-registered 8b reading (regressions = 0) is
  unmet; recorded as a QUALIFIED ship with named residuals rather than re-typing after the numbers
  (re-typing post-hoc would be steering).

## ADR proposed for history.md

2026-07-13 — Spec 0044 shipped the confidence-conditioned nudge (`CONDITIONED_NUDGE_SHIPS`,
net +2, one named residual). (See the appended history.md entry.)

## Conventions proposed

- Extended the 0043 frozen-config / two-stage-freeze rule with the FIVE-member verdict shape
  (power floors CONSUMED by an UNDER_POWERED branch; a benefit conjunct must accompany the net
  conjunct so a do-nothing lever cannot type a ship; config LITERALS drift-pinned to SUT constants,
  never references — anti-tautology).
- Extended the 0029 answer-all-N convention with the mid-loop MESSAGE-INJECTION rule (a gold-blind
  evidence-gated nudge lands only at the completed-batch boundary, rides `messages` only, is not a
  model turn, and survives truncation).
