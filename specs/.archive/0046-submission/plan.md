---
spec: "0046"
status: planned
created: 2026-07-13
strategy: tdd
---

# Plan — 0046 submission

Dissolve the confidence-gate TRADE (0043→0045) with TWO mechanism changes inside the
explorer loop, both measured on a fresh baseline of the CURRENT SUT. (1) REVERT 0045's
require-corroboration-to-fire (retire it as a measured regression, pinned by an
import-absence guard; the LEVER is already reverted in the loop — this formally retires the
unwired refined-gate symbols and keeps the 0045 APPARATUS regression-pinned). (2) Add a
REACTIVE policy (default submit-best-span; explore only on a named gold-blind trigger) and a
host-side CONFIRM-BEFORE-SUBMIT interceptor on `submit_citations` (deterministic
lexical/symbolic containment; confirm-FAIL emits a FLAGGED citation, never silence). The
predicate grows to FIVE sides (the new `flagged-wrong-emitted` cost partitions the
fired-wrong-submitted mass with s→wc; the sum is conserved and reported). Schema bumps
`0045/1 → 0046/1` (additive, dual-seam). A three-point freeze governs a gated BASELINE arm
(band `[1,3]` else `BASELINE_DRIFT_STOP`) and a NEW arm head-to-head, and the outcome is
typed `DISSOLVES_TRADE` / `TRADES_AGAIN` / `NO_EFFECT` over the five-sided ledger.

## Overview

Nine work areas, all in strict RED→GREEN TDD order (every GREEN preceded by its RED):

1. **Revert the lever, keep the apparatus (AC1)** — formally RETIRE
   `qualifying_confidence_spans` + `_is_corroborated` from
   `harpyja/scout/confidence_gate.py` (the LEVER is already reverted in `explorer_loop.py`,
   which wires `qualifying_symbols_spans`), recording the rationale ("a measured regression,
   not a deletion") and pinning the removal with an EXECUTABLE import-absence / public-name
   guard (the deletion convention). RETAIN, regression-pinned: `spans_overlap_line` +
   `confidence_signals.py` (still consumed), the four-sided predicate, s→wc counting, the
   gold-blind signal defs, and the record-only `unfired_silence_to_wrong_confidence`
   cross-check. The 0045 refined-RANKING tests are retired WITH the lever; the apparatus
   tests stay green unchanged.
2. **Reactive policy (AC2)** — NEW SEPARABLE module `harpyja/scout/reactive_policy.py`: the
   three gold-blind, fixturable triggers (`symbols-empty`, `hit-in-comment`,
   `tool-disagreement`), default submit-best-span, explore-on-named-trigger, triggers as a
   SET (multi-trigger first-class). Then wire it into `explorer_loop.py` — record
   `reactive_triggers_fired`; a triggered explore is bounded by the EXISTING
   `scout_max_turns` / `scout_wall_clock_s` caps (byte-pinned, unchanged).
3. **Confirm-before-submit (AC3)** — NEW SEPARABLE module `harpyja/scout/confirm.py`: the
   host-side interceptor predicate (mechanical query key-identifier extraction; lexical /
   symbolic containment; outcomes `PASS` / `FAIL` / `CONFIRM_ERROR` / `NO_CANDIDATE`;
   FAIL & CONFIRM_ERROR → emit-with-flag) PLUS the pure `submit_disposition` derivation.
   Wired at the `explorer_backend.py` `submit` seam (query + host-side `read_span` in scope),
   reusing the EXISTING `read_span` (no new registered tool — exact-count stays five). The
   AC3(a) separable-modules import guard (reactive_policy/gate import NEITHER `confirm` nor
   `ConfirmationOutcome` nor the disposition derivation — symbol AND module boundary) and the
   AC3(b) confirm-FAIL-emits-flagged-without-changing-firing-count fixture.
4. **LoopResult fields + schema bump dual-seam (AC4a)** — four additive `LoopResult` fields
   (`reactive_triggers_fired`, `confirmation_ran`, `confirmation_outcome`,
   `submit_disposition`) + the emitted-flag carrier, threaded through
   `build_trajectory_record` AND `run_verified_case`; `VERIFIER_SCHEMA_VERSION 0045/1 →
   0046/1` (additive; legacy incl. `0044/1` + `0045/1` validate unchanged);
   presence-required on `0046/1`; version-pin tests amended SAME change; the 0034/0038 params
   byte-pin (`explorer_think=None ⇒ params == {max_tokens: 2048}`) survives verbatim.
5. **Eval accounting — five-sided + truth-table + cross-checks + flag-rate (AC4b/c/d)** —
   NEW eval sibling `harpyja/eval/reactive_observability.py` (mirror-not-share vs
   `submission_observability.py`): the `flagged-wrong-emitted` counted side, the truth-table
   grid-totality (every row → exactly one side, including the two `wrong|no` partition-boundary
   rows), the retained `unfired_silence_to_wrong_confidence` + NEW
   `unfired_confirm_found_but_unsubmitted`, the s→wc / `flagged-wrong-emitted` SUM, and the
   record-only per-model FLAG-RATE diagnostic — reusing `metrics.span_hit_kind` BY IDENTITY.
6. **Frozen config + five-sided verdict (AC7)** — NEW `harpyja/eval/reactive_outcome.py`
   (total-pure `DISSOLVES_TRADE` / `TRADES_AGAIN` / `NO_EFFECT` over the five-sided ledger,
   frozen precedence, grid-total, 4b reconciliation wired to `submit_disposition`) and NEW
   `harpyja/eval/reactive_config.py` (`PREREGISTERED_REACTIVE_CONFIG_0046`, hash,
   `compute_sut_hash` over gate + reactive_policy + confirm + confidence_signals; the
   baseline-relative threshold-DERIVATION RULE frozen, the derived LITERALS committed at the
   three-point freeze).
7. **Baseline + new-arm run machinery (AC5/AC6)** — NEW `harpyja/eval/reactive_run.py`: the
   BASELINE arm (reverted 0044 gate, current SUT; aggregate NET band `[1,3]` else
   `BASELINE_DRIFT_STOP`), the NEW arm on the same 33 cells (five sides + sum + flag-rate),
   head-to-head vs the BASELINE arm (not vs 0044's history), named cells (flask-5014,
   django-14315::8b, pytest-10081::14b), via `run_gated_pool_pilot` (0041 exclusivity
   endpoint), resumable dual-hash STOP driver; integration smoke (skip-not-fail).
8. **VERIFY + REFACTOR** — full offline suite green (params byte-pin, exact-tool-count =
   FIVE unchanged, dual-seam written-JSON pins, ast no-eval-import + the AC3(a)
   separable-modules import guard, legacy schema validates, deletion import-absence); and the
   mirror-not-share dedup decision vs the 0044 modules recorded.
9. **Three-point freeze + live + typed close-out** — the predicate freeze (pre-baseline), the
   baseline live arm, the config-with-thresholds freeze (pre-new-arm), the new-arm live run,
   and the typed `outcome.md`.

### Three-point freeze ordering (hard-sequenced)

The `flagged-wrong-emitted` ceiling and the flag-rate range are BASELINE-DERIVED, so this
spec's freeze is a THREE-point sequence, not the usual two:

- **Point 1 — predicate freeze (pre-baseline).** The FIVE-sided predicate + the verdict
  precedence (`reactive_outcome.py`) are frozen, hashed, and **committed (T22) BEFORE any
  number** — before the baseline arm runs. Pinned by
  `test_committed_predicate_matches_computed_truth`. The predicate cannot be reshaped after
  the baseline s→wc is seen.
- **Point 2 — baseline arm (yields the thresholds' base).** The BASELINE arm (T26, live)
  runs on the byte-final SUT and yields per-model s→wc (and fixes baseline
  `flagged-wrong-emitted = 0` by construction). Its aggregate NET is checked against the
  frozen sanity band `[1,3]`; outside ⇒ `BASELINE_DRIFT_STOP` (artifacts retained).
- **Point 3 — config-with-thresholds freeze (pre-new-arm).** `PREREGISTERED_REACTIVE_CONFIG_0046`
  (`reactive_config.py`) is built offline (T20/T21) with the SUT hash + cells + the
  threshold-DERIVATION RULE, but the DERIVED literals (the `flagged-wrong-emitted` ceiling =
  a pre-registered FRACTION < 1 of baseline s→wc; the flag-rate range) are committed at T27
  AFTER the baseline arm and BEFORE any new-arm spend. `compute_sut_hash` MUST include
  `confidence_gate.py`, `reactive_policy.py`, `confirm.py`, AND `confidence_signals.py`, so
  the config cannot be frozen until the SUT surface is byte-final (after T12). The driver
  re-verifies BOTH the config hash AND the working-tree SUT hash at every invocation (typed
  STOP on drift).

## Task table

| ID | Phase | Area | File(s) | Done-when |
|----|-------|------|---------|-----------|
| T1 | RED | 1 | `harpyja/scout/test_confidence_gate.py` | Import-absence / retained-apparatus pins fail (symbols still present) |
| T2 | GREEN | 1 | `harpyja/scout/confidence_gate.py` | `qualifying_confidence_spans`+`_is_corroborated` retired w/ rationale; apparatus retained; refined-ranking tests removed |
| T3 | RED | 2 | `harpyja/scout/test_reactive_policy.py` | Trigger + near-miss + multi-trigger + default + bounded-explore tests fail (module absent) |
| T4 | GREEN | 2 | `harpyja/scout/reactive_policy.py` | Three gold-blind triggers, default submit-best, set-valued, cap-bounded pass |
| T5 | RED→GREEN | 2 | `harpyja/scout/test_explorer_loop.py`, `explorer_loop.py` | `reactive_triggers_fired` recorded; no-trigger submits; triggered explore bounded by existing caps |
| T6 | RED | 3 | `harpyja/scout/test_confirm.py` | Key-id extraction + 4 outcomes + reads-query-only fail (module absent) |
| T7 | GREEN | 3 | `harpyja/scout/confirm.py` | Predicate + outcomes + `submit_disposition` derivation pass |
| T8 | RED | 3 | `harpyja/scout/test_reactive_policy.py`, `test_confidence_gate.py` | AC3(a) separable-modules import guard fails until asserted |
| T9 | RED→GREEN | 3 | `harpyja/scout/test_explorer_backend.py`, `test_submit_citations.py`, `explorer_backend.py` | Interceptor at submit seam; FAIL emits flagged w/o changing firing count vs PASS; read_span reused; five tools unchanged |
| T10 | RED→GREEN | 4 | `harpyja/scout/test_explorer_loop.py`/`test_explorer_backend.py`, `explorer_loop.py`, `explorer_backend.py` | Four `LoopResult` fields + flag carrier threaded into `build_trajectory_record`; params byte-pin stays green |
| T11 | RED | 4 | `harpyja/eval/test_live_verifier.py` | `0046/1` bump + dual-seam written-JSON + legacy validate + presence-required + version-pins fail |
| T12 | GREEN | 4 | `harpyja/eval/live_verifier.py` | `0046/1` both seams; four fields; presence-required; legacy validate; T11 passes |
| T13 | RED | 5 | `harpyja/eval/test_reactive_observability.py` | Five-side truth-table grid-totality + partition boundary + cross-checks + SUM + flag-rate fail (absent) |
| T14 | GREEN | 5 | `harpyja/eval/reactive_observability.py` | Five-sided accounting via `span_hit_kind` by identity passes |
| T15 | RED | 6 | `harpyja/eval/test_reactive_outcome.py` | Three-member verdict + precedence + grid-totality + 4b reconciliation fail (absent) |
| T16 | GREEN | 6 | `harpyja/eval/reactive_outcome.py` | `decide_reactive_outcome` total pure, three members, precedence, grid total |
| T17 | RED | 6 | `harpyja/eval/test_reactive_config.py` | Frozen+hashed config + SUT-hash coverage + threshold-rule + baseline pins + floors fail (absent) |
| T18 | GREEN | 6 | `harpyja/eval/reactive_config.py` | `PREREGISTERED_REACTIVE_CONFIG_0046` + hash + `compute_sut_hash` pass (derived literals pending T26) |
| T19 | RED | 7 | `harpyja/eval/test_reactive_run.py` | Baseline-band/`BASELINE_DRIFT_STOP`, new-arm five-side head-to-head, dual-hash STOP, named cells fail (absent) |
| T20 | GREEN | 7 | `harpyja/eval/reactive_run.py` | `run_reactive_arms` + `build_reactive_run_summary` pass |
| T21 | RED | 7 | `harpyja/eval/test_reactive_run_integration.py` | Integration smoke fails (opt-in, marked) |
| T22 | FREEZE | 6/9 | `specs/0046-submission/predicate_freeze/five_sided_predicate.json` | **Point 1**: predicate committed BEFORE any number; committed-matches-computed pin green |
| T23 | GREEN | 7 | `harpyja/eval/test_reactive_run_integration.py` | Smoke skip-not-fail green; named cells enumerated; STOP-AND-WARN refusal smoke |
| T24 | VERIFY | 8 | (source-sweep / full offline suite) | Params byte-pin, exact-tool-count = five, dual-seam pins, ast no-eval-import + AC3(a) guard, legacy validate, deletion import-absence all green |
| T25 | REFACTOR | 8 | (evaluate; record decision) | Dedup vs 0044 `submission_config`/`outcome`/`run` DECLINED-with-reason (mirror-not-share) |
| T26 | LIVE | 9 | `specs/0046-submission/reactive_run/baseline_results.json` | **Point 2**: baseline arm; band `[1,3]` or `BASELINE_DRIFT_STOP`; per-model s→wc emitted |
| T27 | FREEZE/DOC | 9 | `specs/0046-submission/reactive_config/reactive_config.json`, `.../reactive_run/run_reactive.py` | **Point 3**: config w/ derived thresholds committed (post-baseline, pre-new-arm); dual-hash STOP driver committed |
| T28 | LIVE | 9 | `specs/0046-submission/reactive_run/reactive_results.json` | New arm complete; five sides + sum + flag-rate + head-to-head + named cells emitted |
| T29 | DOC | 9 | `specs/0046-submission/outcome.md` | Typed three-member outcome; all-true + cross-checks + confounds recorded |

Offline (no endpoint): T1–T24 (incl. T22 predicate freeze commit), T25. Live-spend (dev
Ollama): T26 (baseline), T28 (new arm), and the skip-not-fail smoke behind
`HARPYJA_REQUIRE_LIVE_STACK` (T21/T23). T27 freeze/driver commit is offline but hard-sequenced
between T26 and T28.

## Test-first sequence

### T1 — Retire the corroboration lever (RED)
Extend `harpyja/scout/test_confidence_gate.py`:
- `test_qualifying_confidence_spans_public_name_absent` — `qualifying_confidence_spans` no
  longer resolves on `confidence_gate` (deletion public-name guard).
- `test_is_corroborated_private_symbol_absent` — `_is_corroborated` gone.
- `test_corroboration_retirement_rationale_recorded` — a module-level
  `CORROBORATION_RETIRED_RATIONALE` constant records "a measured regression (firing 3/33,
  fu 1→8), not a deletion".
- `test_spans_overlap_line_retained_and_gold_blind` — `spans_overlap_line` still importable
  (the reactive triggers/confirm may reuse it); the gate stays ast no-eval-import.
- `test_qualifying_symbols_spans_is_the_live_firing_condition` — the 0044 condition
  (`qualifying_symbols_spans`) is unchanged and remains the loop's wired gate.
- Fails: both symbols still present.

### T2 — Retire the corroboration lever (GREEN)
Delete `qualifying_confidence_spans` + `_is_corroborated` from
`harpyja/scout/confidence_gate.py`; add `CORROBORATION_RETIRED_RATIONALE`; keep
`qualifying_symbols_spans`, `build_confidence_nudge`, `CONFIDENCE_*`, and the
`spans_overlap_line` import. Remove the 0045 refined-RANKING tests
(`test_weak_singleton_evidence_no_longer_fires`,
`test_0044_never_fired_evidence_shape_now_fires`, `test_refined_ranking_matches_stage1_...`)
in the SAME change (they pin the retired lever); the APPARATUS tests (four-sided predicate,
s→wc, gold-blind signals, unfired cross-check) stay green untouched. T1 passes.

### T3 — Reactive policy (RED)
Add `harpyja/scout/test_reactive_policy.py`:
- `test_no_trigger_fires_defaults_to_submit_best_span` — a clean converged trajectory fires
  no trigger; the policy default is submit-best.
- `test_symbols_empty_trigger_fires_on_zero_span_result` / `..._does_not_fire_on_nonempty` —
  the honest-empty `symbols` marker fires it; a non-empty symbols result does not.
- `test_hit_in_comment_trigger_fires_on_comment_node` /
  `test_hit_in_comment_trigger_fires_on_trailing_comment_ripgrep_fallback` /
  `test_hit_in_comment_does_not_fire_on_code_token` — comment/docstring node via the symbol
  layer; ripgrep-fallback whole-line/after-comment-token rule; a hit in a code token (comment
  sharing the line) does NOT fire.
- `test_tool_disagreement_fires_on_divergent_owning_file` /
  `test_tool_disagreement_does_not_fire_on_agreeing_files` — grep-candidate-file ≠
  symbols-owning-file after path normalization fires; agreeing files do not.
- `test_multi_trigger_records_both_identifiers_order_stable` — two triggers on one case
  record BOTH (a SET, order-stable).
- `test_reactive_policy_is_gold_blind` — ast pin: no `harpyja.eval` import, no gold param.
- `test_triggered_explore_bounded_by_existing_caps` — a triggered explore does NOT extend the
  budget (the policy returns "keep exploring" but termination stays with
  `scout_max_turns`/`scout_wall_clock_s`; asserted at the policy contract, cap enforcement
  proven in T5).
- Fails: module absent.

### T4 — Reactive policy (GREEN)
Implement `harpyja/scout/reactive_policy.py`: `REACTIVE_TRIGGERS` (closed frozenset
`{symbols-empty, hit-in-comment, tool-disagreement}`), `fired_triggers(trajectory) ->
list[str]` (set-valued, order-stable, gold-blind — consumes only tool results, reusing
`confidence_signals`/`spans_overlap_line` where useful), and `should_keep_exploring(...)`
(true iff any trigger fired). No budget knob of its own. T3 passes.

### T5 — Reactive policy wiring (RED→GREEN)
In `harpyja/scout/test_explorer_loop.py`:
- `test_loop_records_reactive_triggers_fired` — RED until the loop threads
  `reactive_triggers_fired` onto `LoopResult`.
- `test_loop_no_trigger_submits_best_span` — a no-trigger terminal path submits.
- `test_triggered_explore_terminates_at_turn_cap` /
  `test_triggered_explore_terminates_at_wall_clock` — a persistently-triggering trajectory
  still terminates at the EXISTING caps (0043's dawdle bounded, not reopened).
- `test_keep_exploring_without_named_trigger_is_countable_violation` — a no-trigger continue
  is a visible policy violation, countable.
GREEN: `explorer_loop.py` consumes `reactive_policy` at the terminal decision point; caps
unchanged. T5 passes.

### T6 — Confirm predicate (RED)
Add `harpyja/scout/test_confirm.py`:
- `test_key_identifier_extraction_matches_token_floor` — `[A-Za-z_][A-Za-z0-9_]*` ≥ pinned
  floor, dotted paths whole; reads the QUERY only.
- `test_key_identifier_extraction_prefers_backtick_quoted` — backtick/quote-delimited tokens
  preferred when present.
- `test_confirm_pass_on_lexical_containment` / `test_confirm_pass_on_symbol_name_match` —
  PASS iff key id in span text OR matches the span's symbol name.
- `test_confirm_fail_when_key_id_extractable_but_absent` — FAIL.
- `test_confirm_error_when_no_key_id_extractable` /
  `test_confirm_error_when_read_span_errors_or_empty` — CONFIRM_ERROR (could-not-decide),
  never a guessed PASS/FAIL.
- `test_confirm_no_candidate_when_nothing_submitted` — NO_CANDIDATE.
- `test_confirm_reads_query_only_never_gold` — ast/contract pin: no gold parameter.
- `test_submit_disposition_derivation_five_shapes` — the pure derivation maps
  (triggers, confirmation_outcome, submitted?) → one of `{never-triggered,
  triggered-and-explored, confirmed-then-submitted, confirm-failed-flagged, no-candidate}`.
- Fails: module absent.

### T7 — Confirm predicate (GREEN)
Implement `harpyja/scout/confirm.py`: `ConfirmationOutcome` (`PASS`/`FAIL`/`CONFIRM_ERROR`/
`NO_CANDIDATE`), `extract_query_key_identifiers(query)`, `confirm_before_submit(query,
citation, read_span)` (host-side `read_span` injected — reuses the EXISTING implementation,
no new registered tool), and `derive_submit_disposition(...)` (pure). T6 passes.

### T8 — Separable-modules import guard (RED, AC3(a))
Extend `harpyja/scout/test_reactive_policy.py` + `test_confidence_gate.py`:
- `test_reactive_policy_does_not_import_confirm_module` /
  `test_confidence_gate_does_not_import_confirm_module` — ast MODULE-boundary: neither
  imports `harpyja.scout.confirm`.
- `test_reactive_policy_does_not_reference_confirmation_symbols` /
  `test_confidence_gate_does_not_reference_confirmation_symbols` — ast SYMBOL: neither names
  `ConfirmationOutcome`, the confirmation fields, or `derive_submit_disposition` (the 0045
  collapse made structurally impossible — the gate cannot read the confirmation result).
- Fails until the separation is asserted (green once T2/T4/T7 land; RED here documents the
  guard as a first-class pin, not an accident of current imports).

### T9 — Interceptor at the submit seam (RED→GREEN, AC3(b))
In `harpyja/scout/test_explorer_backend.py` (and `test_submit_citations.py` for the pure
seam's untouched invariants):
- `test_confirm_fail_emits_flagged_citation_not_silence` — a confirm-FAIL citation is
  EMITTED with the confidence flag, never silenced, never re-explored.
- `test_confirm_fail_firing_count_equals_confirm_pass` — the gate fires at the 0044 rate in
  BOTH the FAIL and PASS variants of one case (confirm gates the OUTPUT, not the ACTION).
- `test_confirm_error_emits_flagged_same_route_distinct_cause` — CONFIRM_ERROR emits flagged
  via the same route, distinct recorded cause.
- `test_interceptor_reuses_existing_read_span_no_new_tool` — the interceptor calls the
  host-side `read_span`; `build_explorer_tools` still returns EXACTLY five.
- `test_submit_citations_pure_seam_unchanged` — `submit_citations` stays a pure
  validate+normalize (the interceptor lives OUTSIDE it, in the backend seam).
GREEN: wire `confirm_before_submit` into the `explorer_backend.py` `submit` closure (query +
`read_span` in scope), attaching the flag via the existing confidence-flag surface and
recording `confirmation_ran`/`confirmation_outcome`. T9 passes.

### T10 — LoopResult fields + backend threading (RED→GREEN, AC4a producer side)
- `test_loop_result_carries_four_reactive_fields_defaulted` — `reactive_triggers_fired=[]`,
  `confirmation_ran=False`, `confirmation_outcome=None`, `submit_disposition=None` appended
  last with defaults (additive).
- `test_trajectory_record_carries_four_reactive_fields` — `build_trajectory_record` threads
  all four (dual-seam producer side).
- `test_params_pin_survives_reactive_and_confirm` — with `think=None`, outbound `params ==
  {"max_tokens": 2048}`; both levers ride `messages`/record fields + the submit-path
  interceptor only.
GREEN: `explorer_loop.py` (`LoopResult` fields + stamping) and `explorer_backend.py`
(threading into `build_trajectory_record`, signature coordinated with T12). T10 passes.

### T11 — Schema bump + dual-seam (RED, AC4a)
In `harpyja/eval/test_live_verifier.py`:
- `test_verifier_schema_version_is_0046_1`.
- `test_legacy_verifier_versions_validate_unchanged` — 0031/0033/0034/0038/0043/0044/**0045/1**
  still validate.
- `test_written_artifact_carries_four_reactive_fields` — read the `run_verified_case` file
  back; all four fields present (dual-seam written-JSON pin).
- `test_reactive_fields_presence_required_on_0046_1` — a 0046/1 artifact missing any of the
  four fails validation.
- Amend the existing version-pin tests SAME change.
- Fails: version 0045/1; fields absent from the written seam.

### T12 — Schema bump + dual-seam (GREEN, AC4a)
`live_verifier.py`: `VERIFIER_SCHEMA_VERSION = "0046/1"`; add `"0046/1"` to
`_KNOWN_VERIFIER_SCHEMA_VERSIONS`; presence-require the four fields on a 0046/1 artifact
(legacy branches untouched); thread all four into `run_verified_case`'s written artifact
(from `backend.last_trajectory`). T11 passes.

### T13 — Five-sided accounting + truth table (RED, AC4b/c/d)
Add `harpyja/eval/test_reactive_observability.py`:
- `test_every_truth_table_row_maps_to_exactly_one_side` — grid-totality over
  (correct? × s→wc-eligible? × confirmation) → exactly one counted side incl.
  `flagged-wrong-emitted`.
- `test_not_eligible_wrong_fail_counts_as_regression_or_miss` — the partition BOUNDARY: a
  not-eligible wrong span that FAILs is `regression`/miss (flag → diagnostic only, NEVER
  `flagged-wrong-emitted`).
- `test_eligible_wrong_fail_counts_as_flagged_wrong_emitted` — the other side of the boundary.
- `test_eligible_wrong_pass_counts_as_swc` — confirmation false-positive → s→wc.
- `test_flagged_but_correct_still_located_flag_rate_pluspl` — a flagged-but-correct citation
  is still located; the flag rides the flag-rate axis only.
- `test_null_attributable_across_five_submit_dispositions` — a null maps across all five
  `submit_disposition` shapes.
- `test_swc_plus_flagged_wrong_emitted_sum_reported` — the fired-wrong-submitted SUM is
  reported (de-attribution guard).
- `test_unfired_confirm_found_but_unsubmitted_record_only` — NEW cross-check counts fu on
  cells where confirmation did NOT fire; record-only.
- `test_unfired_silence_to_wrong_confidence_retained` — the 0045 cross-check retained.
- `test_flag_rate_recoverable_from_confirmation_outcome` — the per-model flag-rate diagnostic.
- `test_accounting_reuses_span_hit_kind_by_identity` — one-oracle reuse.
- Fails: module absent.

### T14 — Five-sided accounting (GREEN, AC4b/c/d)
Implement `harpyja/eval/reactive_observability.py` (mirror-not-share vs
`submission_observability.py`): `classify_reactive_side(...)` over the truth table,
`reactive_ledger(...)` (five sides + sum), `unfired_confirm_found_but_unsubmitted(...)`,
`flag_rate(...)`; `span_hit_kind` imported BY IDENTITY. T13 passes.

### T15 — Five-sided verdict (RED, AC7)
Add `harpyja/eval/test_reactive_outcome.py`:
- `test_dissolves_trade_requires_all_conjuncts` — fu falls ∧ s→wc does not rise ∧
  `flagged-wrong-emitted` ≤ ceiling ∧ (s→wc + fwe) sum does not rise ∧ no model net-negative.
- `test_ceiling_and_sum_conjuncts_do_different_work` — a pure s→wc→flagged RELABEL (sum flat)
  breaches the CEILING (pinned below baseline s→wc); NEW eligible-wrong mass breaches the SUM.
- `test_trades_again_names_reopened_direction` — fu / s→wc / `flagged-wrong-emitted` each
  named when reopened.
- `test_flag_everything_operating_point_is_not_a_dissolve` — relabel-the-whole-mass breaches
  the ceiling; correct-cells-flagged caught by flag-rate; neither scores as a win.
- `test_4b_triggered_and_explored_net_negative_is_inert_with_cost_null` — wired to
  `submit_disposition` (NOT `TRADES_AGAIN`).
- `test_4b_no_trigger_net_negative_is_trades_again` — the reactive-lever cost partition.
- `test_no_effect_otherwise`.
- `test_precedence_first_true_wins` / `test_all_true_conditions_recorded`.
- `test_grid_totality_every_tuple_types_exactly_one_member` — cartesian sweep returns exactly
  one member, never raises.
- Fails: module absent.

### T16 — Five-sided verdict (GREEN, AC7)
Implement `harpyja/eval/reactive_outcome.py`: `ReactiveVerdict`
(`DISSOLVES_TRADE`/`TRADES_AGAIN`/`NO_EFFECT`), `decide_reactive_outcome(config,
baseline_cells, new_cells, named_cells)` total pure over per-model five-sided tuples +
`submit_disposition`-keyed 4b reconciliation, frozen precedence, grid-total, all-true
recorded. T15 passes.

### T17 — Frozen config (RED, AC7)
Add `harpyja/eval/test_reactive_config.py`:
- `test_config_is_frozen_dataclass` / `test_config_hash_is_stable`.
- `test_sut_hash_covers_gate_reactive_confirm_and_signals` — `_SUT_FILES` includes
  `confidence_gate.py`, `reactive_policy.py`, `confirm.py`, `confidence_signals.py`.
- `test_baseline_band_is_1_to_3_frozen` — the sanity band `[1,3]` as data.
- `test_flagged_wrong_emitted_ceiling_is_baseline_relative_fraction_below_one` — the
  DERIVATION RULE (fraction < 1 of baseline s→wc) is frozen; the literal is committed at T27.
- `test_flag_rate_range_derivation_rule_frozen` — the flag-rate range rule frozen; literal at T27.
- `test_named_cells_pinned` — flask-5014, django-14315::8b, pytest-10081::14b.
- `test_thirty_three_cells_consumed_from_frozen_pool` — cells never re-selected.
- `test_three_member_precedence_encoded`.
- Fails: module absent.

### T18 — Frozen config (GREEN, AC7)
Implement `harpyja/eval/reactive_config.py`: `PREREGISTERED_REACTIVE_CONFIG_0046` (frozen
literals + the threshold-derivation RULE, derived literals defaulted/None until T27),
`REACTIVE_CONFIG_HASH_0046`, `compute_sut_hash` over `_SUT_FILES`. T17 passes.

### T19 — Baseline + new-arm machinery (RED, AC5/AC6)
Add `harpyja/eval/test_reactive_run.py`:
- `test_run_refuses_without_live`.
- `test_baseline_arm_net_in_band_types_reproduced` / `test_baseline_arm_out_of_band_stops` —
  band `[1,3]` else `BASELINE_DRIFT_STOP` (artifacts retained).
- `test_baseline_arm_flagged_wrong_emitted_is_zero_by_construction`.
- `test_new_arm_reports_five_sides_sum_and_flag_rate` — per model.
- `test_head_to_head_is_vs_baseline_arm_not_0044_history`.
- `test_ledger_keyed_by_reactive_config_hash` (resumable).
- `test_startup_verifies_sut_hash_and_config_hash` — typed STOP on drift (both re-verified).
- `test_named_cells_enumerated_in_run_set`.
- `test_summary_feeds_decide_reactive_outcome`.
- Fails: module absent.

### T20 — Baseline + new-arm machinery (GREEN, AC5/AC6)
Implement `harpyja/eval/reactive_run.py`: `run_reactive_arms(...)` via `run_gated_pool_pilot`
(dual-hash verify, `_evict_other_models` per block, resumable), the baseline-band /
`BASELINE_DRIFT_STOP` typing, and `build_reactive_run_summary(...)` (five-sided per-model
ledger + sum + flag-rate + head-to-head vs baseline → `decide_reactive_outcome`), mirroring
`submission_run.py`. T19 passes.

### T21 — Integration smoke (RED, AC5/AC6)
Add `harpyja/eval/test_reactive_run_integration.py` (`@pytest.mark.integration`,
skip-not-fail):
- `test_reactive_run_smoke_gated_and_dual_hash_verified` — under `HARPYJA_REQUIRE_LIVE_STACK`,
  one gated cell produces a verifier-PASSED artifact carrying the four 0046/1 fields.
- `test_named_cells_enumerated_in_run_set` — the three AC6 targets present.
- `test_stop_and_warn_refusal_path_smoke`.
- Fails: driver absent. (Lives in `harpyja/eval/`, the collection-path precedent.)

### T22 — Predicate freeze (FREEZE) — Point 1, BEFORE any number
Commit `specs/0046-submission/predicate_freeze/five_sided_predicate.json` (the five-sided
predicate + verdict precedence + hash), pinned by
`test_committed_predicate_matches_computed_truth` (in `test_reactive_outcome.py`). Done-when:
artifact committed, hash matches, and NO baseline/new-arm number has been computed (the
predicate-before-numbers ordering is auditable).

### T23 — Integration smoke (GREEN, AC5/AC6)
Make the smoke skip-not-fail green (opt-in default per 0041); named cells enumerated;
STOP-AND-WARN refusal-path smoke green. No live spend in CI.

### T24 — Surviving-pins verify (VERIFY)
Executable source-sweep / full offline re-run: `test_params_pin_survives_reactive_and_confirm`,
`test_initial_prompt_binds_to_registered_tool_surface_single_source`,
`test_build_explorer_tools_returns_exactly_five_navigation_tools` (exact-tool-count UNCHANGED
— the interceptor reuses `read_span`, no new registered tool), the dual-seam written-JSON
pins, the scout no-eval-import ast pins, the AC3(a) separable-modules import guard, and the
AC1 deletion import-absence guard all green. Done-when: `uv run pytest -m "not integration"`
green.

### T25 — Deduplication evaluation (REFACTOR)
Evaluate whether `reactive_config`/`reactive_outcome`/`reactive_run`/`reactive_observability`
should share code with the 0044 `submission_*` modules. DECLINE-with-reason
(mirror-not-share): the 0044 modules are frozen historical pins; sharing would let a 0046 edit
perturb 0044's byte-stable head-to-head axis, and the two specs' FROZEN verdict orders and
pinned artifacts must not couple. Record the decision (0040-T22 / 0041-T21 / 0042-T7 /
0045-T18 decline precedent). All tests still pass.

### T26 — Baseline arm (LIVE, dev Ollama) — Point 2
Run the baseline arm (reverted 0044 gate, byte-final SUT) on the evicted-before /
re-pinned-after 0041-gated endpoint (detach per the long-run memory note). Produces
`specs/0046-submission/reactive_run/baseline_results.json` (per-model s→wc, baseline
`flagged-wrong-emitted = 0`, aggregate NET). If NET ∉ `[1,3]` ⇒ `BASELINE_DRIFT_STOP`
(artifacts retained), STOP before the new arm.

### T27 — Config-with-thresholds freeze + driver (FREEZE/DOC) — Point 3
AFTER T26 (baseline s→wc known) and BEFORE any new-arm spend: commit
`specs/0046-submission/reactive_config/reactive_config.json` (frozen config +
`REACTIVE_CONFIG_HASH_0046` + post-lever SUT hash + the DERIVED `flagged-wrong-emitted`
ceiling = fraction < 1 of baseline s→wc + the flag-rate range), pinned by
`test_committed_reactive_config_matches_computed_truth`. Commit the dual-hash STOP-AND-WARN
resumable driver `specs/0046-submission/reactive_run/run_reactive.py` (`_preflight()` →
`/api/tags`; re-verifies BOTH the config hash AND the working-tree SUT hash each invocation;
`SystemExit("STOP-AND-WARN: …")`; exit 0 complete / 3 work-remaining / 2 exclusive-endpoint
contended). Done-when: config artifact + driver committed; no new-arm spend yet.

### T28 — New arm (LIVE, dev Ollama)
Run the committed driver on the 0041-gated endpoint. Produces
`specs/0046-submission/reactive_run/reactive_results.json` (five-sided ledger per model +
the s→wc + `flagged-wrong-emitted` SUM + the flag-rate diagnostic, `0041/pilot/*` exclusivity
proof, head-to-head vs the BASELINE arm) + the run summary. Named cells: flask-5014,
django-14315::8b, pytest-10081::14b.

### T29 — Typed close-out (DOC)
`specs/0046-submission/outcome.md` via `decide_reactive_outcome`: the typed label
(`DISSOLVES_TRADE` / `TRADES_AGAIN` naming the reopened direction / `NO_EFFECT`), the selected
member PLUS all true conditions recorded, the retained `unfired_silence_to_wrong_confidence`
+ NEW `unfired_confirm_found_but_unsubmitted` reported beside the conditioned counts, the
s→wc + `flagged-wrong-emitted` SUM, the per-model flag-rate vs its pre-registered range, the
head-to-head aggregate net + the three named-cell outcomes, and the 4b per-lever
reconciliation. Pilot-N signal, not an inferential claim; train-on-test confound (three specs
on the same 33 cells) recorded. Flip `status:` at close; path-pins point at
`specs/.archive/0046-submission/`.

## Risks / sequencing notes

- **Emit-with-flag surface discovery** — the confirm-FAIL/CONFIRM_ERROR flag must reuse the
  EXISTING confidence-flag surface (`Confidence="degraded"` on the result / a `gate-skipped`-style
  note / a per-citation carrier), not a new field. Identify the exact carrier during T7/T9 and
  pin it; a flagged-but-correct citation must still read as `located`, never as a regression.
- **Trajectory-record seam ownership** — confirm which seam owns the SUT-side trajectory
  record vs the eval-side written artifact (0045 threaded BOTH `build_trajectory_record` in
  `live_verifier.py` AND `run_verified_case`). T10 (producer) and T11/T12 (written) read the
  file back for all four fields at BOTH seams; version-pin tests amended same-change;
  presence-required on 0046/1.
- **Three-point freeze** — the ceiling/flag-rate literals are baseline-derived, so the freeze
  is predicate (T22, pre-baseline) → baseline arm (T26) → config-with-thresholds (T27,
  pre-new-arm). Hard-sequence T27 strictly between T26 and T28; the driver re-verifies BOTH
  the config hash AND the working-tree SUT hash each invocation (typed STOP).
- **AC3(a) separability is load-bearing** — the reactive_policy/gate modules must NOT import
  `confirm` / `ConfirmationOutcome` / `derive_submit_disposition` (symbol AND module
  boundary). This is the structural guarantee that makes the 0045 collapse impossible; keep
  the `submit_disposition` derivation in `confirm.py` (or a dedicated module), never in the
  gate. T8 pins it; T24 re-verifies.
- **Exact-tool-count stays FIVE** — the interceptor reuses the host-side `read_span`; it adds
  NO tool to the model's registered suite. `test_build_explorer_tools_returns_exactly_five_...`
  must stay green (T9/T24).
- **Params byte-pin** — both levers ride `messages` / record fields + the submit-path
  interceptor only; `test_params_pin_survives_reactive_and_confirm` keeps `params ==
  {max_tokens: 2048}` (think=None) green (T10).
- **De-attribution channel** — the s→wc / `flagged-wrong-emitted` SUM is reported (T13/T14),
  and the ceiling sits BELOW baseline s→wc so a pure relabel breaches it (T15/T16); the SUM
  and CEILING conjuncts do DIFFERENT work in `DISSOLVES_TRADE`.
- **Baseline drift** — `BASELINE_DRIFT_STOP` is a sanity check on SUT reproduction, NOT a
  pass/fail gate on the new lever; a baseline of +1 is survivable and the head-to-head still
  holds (T19/T26).
- **Live contamination / SUT-frozen-for-one-measurement** — `run_gated_pool_pilot` exclusive
  endpoint, evict-before / re-pin-after; never run the suite concurrently with T26/T28; any
  live-observed SUT defect is fixed AFTER the run, never mid-run.
- **Retiring 0045 tests, not the apparatus** — T2 removes only the refined-RANKING tests that
  pin the retired lever; the four-sided predicate, s→wc counting, gold-blind signals, and the
  unfired cross-check tests stay green unchanged (regression-pinned).
