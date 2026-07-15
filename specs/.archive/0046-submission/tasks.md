---
spec: "0046"
---

# Tasks

## Area 1 — Revert the lever, keep the apparatus (offline)
- [x] T1 (RED) — `harpyja/scout/test_confidence_gate.py`: `qualifying_confidence_spans` + `_is_corroborated` public-name/private-symbol absent, `CORROBORATION_RETIRED_RATIONALE` recorded, `spans_overlap_line` retained + gold-blind, `qualifying_symbols_spans` still the live firing condition
- [x] T2 (GREEN) — `harpyja/scout/confidence_gate.py`: retire `qualifying_confidence_spans` + `_is_corroborated` with rationale; keep the apparatus; remove the 0045 refined-RANKING tests SAME change (apparatus tests stay green)

## Area 2 — Reactive policy (offline)
- [x] T3 (RED) — `harpyja/scout/test_reactive_policy.py`: each trigger fires + a near-miss negative each (`symbols-empty`, `hit-in-comment` node + ripgrep-fallback + code-token negative, `tool-disagreement`), multi-trigger set order-stable, no-trigger→submit-best, gold-blind ast pin, triggered-explore bounded by existing caps
- [x] T4 (GREEN) — `harpyja/scout/reactive_policy.py`: closed `REACTIVE_TRIGGERS`, `fired_triggers` (set-valued, gold-blind), `should_keep_exploring`; no budget knob of its own
- [x] T5 (RED→GREEN) — `harpyja/scout/test_explorer_loop.py` + `explorer_loop.py`: record `reactive_triggers_fired`; no-trigger submits; triggered explore terminates at `scout_max_turns`/`scout_wall_clock_s`; no-trigger continue is a countable violation

## Area 3 — Confirm-before-submit (separable module, offline)
- [x] T6 (RED) — `harpyja/scout/test_confirm.py`: key-id extraction (token floor, dotted whole, backtick-preferred, query-only), PASS (lexical/symbol) / FAIL / CONFIRM_ERROR (no key-id, read_span error/empty) / NO_CANDIDATE, no gold param, `submit_disposition` five-shape derivation
- [x] T7 (GREEN) — `harpyja/scout/confirm.py`: `ConfirmationOutcome`, `extract_query_key_identifiers`, `confirm_before_submit` (injected host `read_span`), `derive_submit_disposition`
- [x] T8 (RED, AC3a) — `harpyja/scout/test_reactive_policy.py` + `test_confidence_gate.py`: separable-modules import guard — reactive_policy/gate import NEITHER `harpyja.scout.confirm` (module) NOR `ConfirmationOutcome`/confirmation fields/`derive_submit_disposition` (symbol)
- [x] T9 (RED→GREEN, AC3b) — `harpyja/scout/test_explorer_backend.py` + `test_submit_citations.py` + `explorer_backend.py`: interceptor at the `submit` seam; confirm-FAIL emits FLAGGED (not silence/re-explore) WITHOUT changing firing count vs confirm-PASS; CONFIRM_ERROR same route/distinct cause; reuses host `read_span`; five tools unchanged; `submit_citations` pure seam untouched

## Area 4 — LoopResult fields + schema bump 0045/1 → 0046/1 (dual-seam, offline)
- [x] T10 (RED→GREEN, AC4a) — `harpyja/scout/test_explorer_loop.py`/`test_explorer_backend.py` + `explorer_loop.py` + `explorer_backend.py`: four additive `LoopResult` fields (`reactive_triggers_fired`/`confirmation_ran`/`confirmation_outcome`/`submit_disposition`) + flag carrier threaded into `build_trajectory_record`; `test_params_pin_survives_reactive_and_confirm` stays green
- [x] T11 (RED, AC4a) — `harpyja/eval/test_live_verifier.py`: `0046/1` bump, legacy (incl. `0044/1`+`0045/1`) validate unchanged, written artifact carries all four fields, presence-required on `0046/1`, version-pin tests amended same-change
- [x] T12 (GREEN, AC4a) — `harpyja/eval/live_verifier.py`: `VERIFIER_SCHEMA_VERSION="0046/1"`, `_KNOWN_...` widened, four fields threaded into `run_verified_case`, presence-required

## Area 5 — Five-sided accounting + truth-table + cross-checks + flag-rate (offline)
- [x] T13 (RED, AC4b/c/d) — `harpyja/eval/test_reactive_observability.py`: truth-table grid-totality (incl. `flagged-wrong-emitted`), partition boundary (not-eligible-wrong-FAIL → regression/miss; eligible-wrong-FAIL → flagged-wrong-emitted; eligible-wrong-PASS → s→wc), flagged-but-correct still located, five-disposition null attribution, s→wc+fwe SUM, `unfired_confirm_found_but_unsubmitted` + retained `unfired_silence_to_wrong_confidence`, flag-rate, `span_hit_kind` by identity
- [x] T14 (GREEN, AC4b/c/d) — `harpyja/eval/reactive_observability.py`: `classify_reactive_side`, `reactive_ledger` (five sides + sum), `unfired_confirm_found_but_unsubmitted`, `flag_rate` (mirror-not-share vs `submission_observability`)

## Area 6 — Frozen config + total-pure five-sided verdict (offline)
- [x] T15 (RED, AC7) — `harpyja/eval/test_reactive_outcome.py`: `DISSOLVES_TRADE` all-conjuncts, ceiling vs sum do different work, `TRADES_AGAIN` names reopened direction, flag-everything not-a-dissolve, 4b triggered-and-explored=inert-with-cost-null / 4b no-trigger=TRADES_AGAIN (wired to `submit_disposition`), `NO_EFFECT`, precedence first-true-wins, all-true recorded, grid-totality
- [x] T16 (GREEN, AC7) — `harpyja/eval/reactive_outcome.py`: `ReactiveVerdict` (three members) + `decide_reactive_outcome` total pure over per-model five-sided tuples + disposition-keyed 4b reconciliation
- [x] T17 (RED, AC7) — `harpyja/eval/test_reactive_config.py`: frozen+hashed, SUT hash covers gate+reactive_policy+confirm+confidence_signals, baseline band `[1,3]` frozen, `flagged-wrong-emitted` ceiling = baseline-relative fraction <1 (RULE frozen, literal at T27), flag-rate range rule frozen, named cells + 33-cell pool, three-member precedence
- [x] T18 (GREEN, AC7) — `harpyja/eval/reactive_config.py`: `PREREGISTERED_REACTIVE_CONFIG_0046` + `REACTIVE_CONFIG_HASH_0046` + `compute_sut_hash` (derived literals pending T27)
- [x] T22 (FREEZE — Point 1) — commit `specs/0046-submission/predicate_freeze/five_sided_predicate.json` BEFORE any number; `test_committed_predicate_matches_computed_truth`

## Area 7 — Baseline + new-arm run machinery (offline unit + integration)
- [x] T19 (RED, AC5/AC6) — `harpyja/eval/test_reactive_run.py`: refuse-without-live, baseline band/`BASELINE_DRIFT_STOP`, baseline fwe=0 by construction, new-arm five sides+sum+flag-rate, head-to-head vs baseline arm (not 0044 history), ledger keyed by config hash, startup dual-hash (SUT+config) STOP, named cells, feeds `decide_reactive_outcome`
- [x] T20 (GREEN, AC5/AC6) — `harpyja/eval/reactive_run.py`: `run_reactive_arms` (via `run_gated_pool_pilot`, dual-hash verify, resumable) + `build_reactive_run_summary`
- [x] T21 (RED, AC5/AC6) — `harpyja/eval/test_reactive_run_integration.py` (`integration`, skip-not-fail): gated + dual-hash-verified smoke carrying the four 0046/1 fields; named cells (flask-5014, django-14315::8b, pytest-10081::14b) enumerated; STOP-AND-WARN refusal-path smoke
- [x] T23 (GREEN, AC5/AC6) — integration smoke skip-not-fail green; named cells enumerated; refusal path green

## Area 8 — Verify surviving pins + dedup decision (offline)
- [x] T24 (VERIFY) — full offline suite green: params byte-pin, exact-tool-count (FIVE, unchanged — interceptor reuses `read_span`), dual-seam written-JSON pins, scout no-eval-import ast pins + AC3(a) separable-modules import guard, legacy schema validate, AC1 deletion import-absence
- [x] T25 (REFACTOR) — evaluate dedup vs 0044 `submission_config`/`submission_outcome`/`submission_run`/`submission_observability`: DECLINE-with-reason (mirror-not-share — frozen historical pins must not couple); record the decision (0040-T22/0041-T21/0042-T7/0045-T18 precedent)

## Area 9 — Three-point freeze + live + doc close-out
- [x] T26 (LIVE — Point 2, dev Ollama) — baseline arm on the evicted-before/re-pinned-after 0041 endpoint; emit `specs/0046-submission/reactive_run/baseline_results.json` (per-model s→wc, fwe=0, aggregate NET); band `[1,3]` else `BASELINE_DRIFT_STOP` (artifacts retained, STOP)
- [x] T27 (FREEZE/DOC — Point 3) — AFTER T26, BEFORE T28: commit `specs/0046-submission/reactive_config/reactive_config.json` (config + `REACTIVE_CONFIG_HASH_0046` + post-lever SUT hash + DERIVED fwe ceiling <1·baseline-s→wc + flag-rate range) pinned by `test_committed_reactive_config_matches_computed_truth`; commit dual-hash STOP-AND-WARN resumable driver `.../reactive_run/run_reactive.py` (exit 0/2/3)
- [~] T28 (LIVE — SKIPPED per BASELINE_DRIFT_STOP frozen rule; operator-confirmed — dev Ollama) — run the gated driver on the 0041 endpoint; emit `specs/0046-submission/reactive_run/reactive_results.json` (five-sided ledger per model + s→wc+fwe SUM + flag-rate + head-to-head vs baseline + named-cell outcomes)
- [x] T29 (DOC) — `specs/0046-submission/outcome.md`: typed three-member `decide_reactive_outcome` label (reopened direction named on `TRADES_AGAIN`), selected + all-true conditions recorded, retained `unfired_silence_to_wrong_confidence` + NEW `unfired_confirm_found_but_unsubmitted` beside the conditioned counts, s→wc+fwe SUM, per-model flag-rate vs pre-registered range, head-to-head net + three named cells, 4b per-lever reconciliation, train-on-test confound; flip `status:`, archive path-pins
