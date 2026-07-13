---
spec: "0045"
status: planned
created: 2026-07-13
strategy: tdd
---

# Plan — 0045 refinement

Confidence-gate refinement — fix BOTH mis-ranking directions and make the invisible
cost countable. A FROZEN stage-1 discriminator-selection table (committed BEFORE any
per-cell attribution) selects a refined RANKING rule over 0044's committed firing data;
the containment/convergence predicates MOVE to `scout/` (gold-blind, one-definition,
imported back by identity); `silence→wrong-confidence` becomes a first-class schema fact
(`0044/1 → 0045/1`, dual-seam); a frozen `PREREGISTERED_REFINEMENT_CONFIG_0045` and a
total-pure SIX-member verdict govern a gated live re-measurement of the 0044 cells,
head-to-head vs 0044, and the outcome is typed.

## Overview

Seven work areas, all in strict RED→GREEN TDD order (every GREEN preceded by its RED):

1. **Stage-1 discriminator-selection table (AC1, first half)** — new eval module
   `harpyja/eval/discriminator_table.py`: `DISCRIMINATOR_SELECTION_TABLE_0045`, a frozen,
   hashed dataclass mapping attribution shapes → refined ranking rule over a CLOSED
   candidate set (`symbols-exact-span`, `grep-hit-inside-symbol containment`,
   `convergent-evidence`, `weak/singleton`), carrying a typed `NO_DISCRIMINATOR_SEPARATES`
   honest-exit row, the OQ2 per-model-gate branch as a frozen row, and the already-visible
   0044 headline facts as DATA. Committed to `specs/0045-refinement/discriminator_table/`
   **BEFORE** the per-cell (b)/(c) attribution is computed (partial-sightedness recorded).
2. **One-definition move + per-cell attribution (AC3 move, AC1 second half)** — move the
   trajectory-only `grep_hits_inside_symbol_spans` / `convergent_evidence` /
   `_tool_spans_in_order` from `eval/submission_observability.py` to a new gold-blind
   `harpyja/scout/confidence_signals.py`; `eval` imports them BY IDENTITY;
   `classify_confidence_null` (gold-needing) STAYS eval-side. Then
   `harpyja/eval/refinement_attribution.py` computes attribution over 0044's committed
   firing artifacts using the moved scout helpers.
3. **Refined ranking in the gate (AC3 ranking)** — refine `qualifying_symbols_spans` /
   the ranking in `harpyja/scout/confidence_gate.py` per the stage-1-selected rule:
   a weak/singleton signal no longer fires; the 0044 never-fired evidence shape
   (`pytest-10081::qwen3:14b`) now fires. Fixture-pinned BOTH directions; gate stays
   ast-pinned no-eval-import.
4. **Schema bump + s→wc first-class (AC2)** — `VERIFIER_SCHEMA_VERSION 0044/1 → 0045/1`
   threaded through BOTH seams (`build_trajectory_record` in `scout/explorer_backend.py`
   AND the `run_verified_case` written artifact in `eval/live_verifier.py`): the AFTER-side
   `silence_to_wrong_confidence` fact + the record-only `unfired_silence_to_wrong_confidence`
   cross-check line. Written-JSON pinned, presence-required on `0045/1`, legacy versions
   validate unchanged, existing version-pin tests amended SAME change (5th dual-seam
   application). Params byte-pin survives verbatim.
5. **Frozen config + six-member verdict (AC4)** — `PREREGISTERED_REFINEMENT_CONFIG_0045`
   (`harpyja/eval/refinement_config.py`): frozen LITERALS drift-pinned to SUT constants,
   BOTH axes pinned by path+sha256 (pre-nudge baseline + the 0044 comparator: results,
   config, 32 per-cell artifacts), comparison literals RE-DERIVED from the pinned artifacts
   in the pin test, power floors `min_covered_joined_cells=8` (live) and
   `min_comparator_swc=3` (re-derivation guard, role documented), the six-member precedence.
   `decide_refinement_outcome` (`harpyja/eval/refinement_outcome.py`): total pure, SIX
   members under frozen precedence, grid-totality tested, all-true conditions recorded.
6. **Gated live re-measurement + named cells (AC5, AC6)** — `harpyja/eval/refinement_run.py`
   via `run_gated_pool_pilot` (resumable ledger keyed by `REFINEMENT_CONFIG_HASH_0045`,
   re-verifies BOTH the committed config hash AND the working-tree SUT hash at every
   invocation — typed STOP on drift), the four-sided ledger per model (conv/reg/s→wc/fu +
   NET), head-to-head vs 0044; integration smoke under `harpyja/eval/` (skip-not-fail),
   named cells enumerated (django-14315::8b holds correct? pytest-10081::14b now fires+
   submits? flask-5014 both cells stay correct?).
7. **Typed close-out (AC7)** — `specs/0045-refinement/outcome.md` via
   `decide_refinement_outcome`: all six members enumerated, selected + all-true conditions
   recorded, record-only unfired-s→wc reported beside s→wc, head-to-head aggregate net +
   flask-5014 holds recorded, train-on-test AND single-cell (django-14315::8b) sensitivity
   recorded per the 0042 precedent.

### Two-stage freeze ordering (hard-sequenced)

- **Stage 1 (choosing rule)** — `DISCRIMINATOR_SELECTION_TABLE_0045` is frozen, hashed, and
  **committed (T3) BEFORE the per-cell attribution (T6/T7) is computed**. The table records
  the already-visible 0044 headline facts and declares the per-cell (b)/(c) detail as
  NOT-yet-computed (partial sightedness recorded); its `NO_DISCRIMINATOR_SEPARATES` row is
  the honest exit if the closed candidate set fails to separate.
- **Stage 2 (config)** — `PREREGISTERED_REFINEMENT_CONFIG_0045` is frozen + hashed +
  **committed (T23) AFTER every SUT lever lands (T5 move, T9 refined ranking, T11/T13 schema
  bump merged — SUT byte-final) and BEFORE any live call (T24 live spend)**.
  `compute_sut_hash` MUST include `scout/confidence_gate.py` AND `scout/confidence_signals.py`,
  so the config cannot be frozen until the SUT surface is byte-final. No live spend before
  the stage-2 config artifact is committed.

## Task table

| ID | Phase | Area | File(s) | Done-when |
|----|-------|------|---------|-----------|
| T1 | RED | 1 | `harpyja/eval/test_discriminator_table.py` | Table tests fail (module absent) |
| T2 | GREEN | 1 | `harpyja/eval/discriminator_table.py` | Frozen/hashed table + closed set + typed no-sep row pass |
| T3 | FREEZE | 1 | `specs/0045-refinement/discriminator_table/discriminator_table.json` | Table committed BEFORE any attribution; committed-matches-computed pin green |
| T4 | RED | 2 | `harpyja/scout/test_confidence_signals.py` | Scout-side containment/convergence + ast-no-eval-import fail (module absent) |
| T5 | GREEN | 2 | `harpyja/scout/confidence_signals.py`, `harpyja/eval/submission_observability.py` | Helpers moved; eval imports BY IDENTITY; gold-needing `classify_confidence_null` stays eval-side |
| T6 | RED | 2 | `harpyja/eval/test_refinement_attribution.py` | Attribution-over-0044-firing tests fail (module absent) |
| T7 | GREEN | 2 | `harpyja/eval/refinement_attribution.py` | Per-cell attribution via scout helpers; pinned to committed firing data |
| T8 | RED | 3 | `harpyja/scout/test_confidence_gate.py` | Both-directions refined-ranking tests fail (ranking unchanged) |
| T9 | GREEN | 3 | `harpyja/scout/confidence_gate.py` | Weak/singleton no longer fires; 0044 never-fired shape now fires; gate stays gold-blind |
| T10 | RED→GREEN | 4 | `harpyja/scout/test_explorer_backend.py`, `explorer_backend.py` | s→wc + unfired-s→wc threaded into `build_trajectory_record`; params byte-pin stays green |
| T11 | RED | 4 | `harpyja/eval/test_live_verifier.py` | 0045/1 bump + dual-seam written-JSON + legacy validate + version-pins fail |
| T12 | GREEN | 4 | `harpyja/eval/live_verifier.py` | 0045/1 both seams; presence-required; legacy validate; T11 passes |
| T13 | RED | 5 | `harpyja/eval/test_refinement_config.py` | Frozen-config + both-axes-pin + re-derived-literals + floors + six-precedence fail (absent) |
| T14 | GREEN | 5 | `harpyja/eval/refinement_config.py` | `PREREGISTERED_REFINEMENT_CONFIG_0045` + hash + `compute_sut_hash` pass |
| T15 | RED | 5 | `harpyja/eval/test_refinement_outcome.py` | Six-member verdict + grid-totality + all-true-recorded fail (absent) |
| T16 | GREEN | 5 | `harpyja/eval/refinement_outcome.py` | `decide_refinement_outcome` total pure, six members, precedence, grid total |
| T17 | VERIFY | 5 | (source-sweep / full offline suite) | Params byte-pin, prompt↔surface, exact-tool-count, dual-seam, scout no-eval-import all green |
| T18 | REFACTOR | 5 | (evaluate; record decision) | Dedup vs 0044 modules evaluated and DECLINED-with-reason (mirror-not-share) |
| T19 | RED | 6 | `harpyja/eval/test_refinement_run.py` | Runner/summary tests fail (absent) |
| T20 | GREEN | 6 | `harpyja/eval/refinement_run.py` | Resumable + dual-hash verify + four-sided ledger + head-to-head pass |
| T21 | RED | 6 | `harpyja/eval/test_refinement_run_integration.py` | Integration smoke fails (opt-in, marked) |
| T22 | GREEN | 6 | `harpyja/eval/test_refinement_run_integration.py` | Smoke skip-not-fail green; named cells enumerated; STOP-AND-WARN refusal smoke |
| T23 | FREEZE/DOC | 6 | `specs/0045-refinement/refinement_config/*.json`, `.../refinement_run/run_refinement.py` | Config artifact committed (post-SUT, pre-live); dual-hash STOP-AND-WARN driver committed |
| T24 | LIVE | 6 | `specs/0045-refinement/refinement_run/refinement_results.json` | Gated live run complete; four-sided ledger + head-to-head emitted |
| T25 | DOC | 7 | `specs/0045-refinement/outcome.md` | Typed six-member outcome; all-true + unfired-s→wc + confounds recorded |

Offline (no endpoint): T1–T21, T23 (freeze+commit). Live-spend (dev Ollama): T24, and the
executable-but-skip-not-fail smoke behind `HARPYJA_REQUIRE_LIVE_STACK` (T21/T22).

## Test-first sequence

### T1 — Stage-1 discriminator table (RED)
Add `harpyja/eval/test_discriminator_table.py`:
- `test_discriminator_table_is_frozen_dataclass` / `test_discriminator_table_hash_is_stable`.
- `test_candidate_signal_set_is_closed` — exactly `{symbols-exact-span,
  grep-hit-inside-symbol-containment, convergent-evidence, weak-singleton}`; no open-ended add.
- `test_table_carries_no_discriminator_separates_row` — the typed `NO_DISCRIMINATOR_SEPARATES`
  honest-exit row exists (the 0043 lever-table totality posture).
- `test_table_records_0044_headline_facts_as_data` — 5/6 fired-on-wrong-span are 8b
  empty→wrong-file; never-fired cell = `pytest-10081::qwen3:14b`; fired-but-ignored = 1 — DATA.
- `test_table_declares_per_cell_bc_detail_uncomputed` — the per-cell (b)/(c) values the table
  freezes OVER are declared not-yet-computed (partial sightedness recorded in the artifact).
- `test_table_carries_per_model_gate_branch_explicitly` — the OQ2 single-vs-per-model branch is
  a frozen row, so the choice is not post-hoc.
- Fails: module absent.

### T2 — Stage-1 discriminator table (GREEN)
Implement `harpyja/eval/discriminator_table.py`: `DISCRIMINATOR_SELECTION_TABLE_0045` (frozen
dataclass), `CANDIDATE_SIGNALS` (closed frozenset), the `NO_DISCRIMINATOR_SEPARATES` typed row,
the per-model branch, the headline facts as data, `DISCRIMINATOR_TABLE_HASH_0045`. T1 passes.

### T3 — Stage-1 freeze (FREEZE) — BEFORE any attribution
Commit `specs/0045-refinement/discriminator_table/discriminator_table.json` (the frozen table +
`DISCRIMINATOR_TABLE_HASH_0045`), pinned by `test_committed_discriminator_table_matches_computed_truth`
(in `test_discriminator_table.py`). Done-when: artifact committed, hash matches, and NO per-cell
attribution number has been computed (the stage-1-before-stage-attribution ordering is auditable).

### T4 — One-definition move to scout (RED)
Add `harpyja/scout/test_confidence_signals.py`:
- `test_grep_hit_inside_symbol_span_detected` / `test_grep_hit_inside_symbol_span_absent` —
  trajectory-only line-interval containment, fixture-pinned both ways.
- `test_convergent_evidence_two_tools_overlap_same_file` / `test_convergent_evidence_none_single_tool`.
- `test_tool_spans_in_order_is_trajectory_only` — the shared scanner moved; gold-free.
- `test_confidence_signals_imports_nothing_from_eval` — ast-pin: no `harpyja.eval` import, no gold
  parameter (the gold-blind guard; the move must not drag a gold dependency into scout).
- `test_convergent_overlap_agrees_with_eval_span_hit_kind_line_grade` — the gold-free overlap
  primitive convergence uses agrees with eval's `span_hit_kind` "line" grade on tool-vs-tool spans
  (one-oracle preserved WITHOUT a scout→eval import).
- Fails: scout module absent.

### T5 — One-definition move to scout (GREEN)
Create `harpyja/scout/confidence_signals.py`: move `_tool_spans_in_order`,
`grep_hits_inside_symbol_spans`, `convergent_evidence` from `eval/submission_observability.py`;
the gold-free span-overlap primitive convergence needs moves WITH them (eval's `span_hit_kind`
gold-comparison retains ONE overlap definition by referencing the moved primitive by identity —
asserted). `harpyja/eval/submission_observability.py` imports the three functions BY IDENTITY from
scout; `classify_confidence_null` (uses gold `expected`) STAYS eval-side. Amend
`test_submission_observability.py` in the SAME change:
`test_observability_containment_is_scout_function_by_identity`,
`test_observability_convergence_is_scout_function_by_identity`,
`test_classify_confidence_null_stays_eval_side_uses_gold`. T4 passes.

### T6 — Per-cell attribution (RED)
Add `harpyja/eval/test_refinement_attribution.py`:
- `test_attribution_over_0044_committed_firing_artifacts` — reads the 32 pinned
  `specs/.archive/0044-submission/submission_run/artifacts/*.submission.json`.
- `test_fired_on_wrong_span_cells_name_triggering_signal` — per fired-on-wrong-span 8b cell, the
  (weak) triggering signal is named.
- `test_never_fired_cell_names_unrecognised_evidence` — `pytest-10081::qwen3:14b`: the evidence the
  gate failed to credit is named.
- `test_attribution_uses_scout_signals_by_identity` — the (b)/(c) values come from the moved scout
  helpers, not a re-implementation.
- `test_attribution_pinned_to_committed_firing_data_by_sha256`.
- Fails: module absent.

### T7 — Per-cell attribution (GREEN)
Implement `harpyja/eval/refinement_attribution.py`: over the pinned 0044 firing artifacts, compute
per fired-on-wrong-span cell's triggering signal + the never-fired cell's unrecognised evidence
via `scout.confidence_signals`, feeding the frozen stage-1 table's selection. T6 passes.

### T8 — Refined ranking (RED)
Extend `harpyja/scout/test_confidence_gate.py`:
- `test_weak_singleton_evidence_no_longer_fires` — the over-credited 8b shape (a bare/weak
  single-source span the stage-1 rule demotes) → no fire.
- `test_0044_never_fired_evidence_shape_now_fires` — the `pytest-10081::14b` evidence shape (the
  previously-uncredited convergent/contained span) → fires.
- `test_refined_ranking_matches_stage1_selected_rule` — the predicate follows
  `DISCRIMINATOR_SELECTION_TABLE_0045`'s selected rule (not an ad-hoc threshold).
- `test_refined_gate_stays_gold_blind` — ast-pin retained (no eval import, no gold param) even
  where the rule consumes `scout.confidence_signals` (scout→scout only).
- Fails: ranking unchanged.

### T9 — Refined ranking (GREEN)
Refine `harpyja/scout/confidence_gate.py` per the selected rule: discredit the weak/singleton shape
(e.g. require convergence/containment for the previously-over-credited case) and credit the
previously-uncredited shape, consuming `scout.confidence_signals` where the rule needs
trajectory-level convergence/containment (the gate input broadens to the prior trajectory spans;
still gold-blind, scout-only). Both directions pinned. T8 passes.

### T10 — Backend threading + params pin (RED→GREEN)
In `harpyja/scout/test_explorer_backend.py`:
- `test_trajectory_record_carries_silence_to_wrong_confidence` — RED until the backend threads the
  AFTER-side s→wc ingredient (fired ∧ submitted-but-not-correct) into `build_trajectory_record`.
- `test_trajectory_record_carries_unfired_swc_record_only` — the record-only
  `unfired_silence_to_wrong_confidence` cross-check line is present.
- `test_params_pin_survives_refinement` — with `think=None`, outbound `params == {"max_tokens": 2048}`;
  the refinement rides `messages`/record fields ONLY.
GREEN: `explorer_backend.py` passes the new fields into `build_trajectory_record` (signature
coordinated with T12). Params pin unchanged.

### T11 — Schema bump + dual-seam (RED)
In `harpyja/eval/test_live_verifier.py`:
- `test_verifier_schema_version_is_0045_1`.
- `test_legacy_verifier_versions_validate_unchanged` — 0031/0033/0034/0038/0043/**0044/1** still validate.
- `test_written_artifact_carries_silence_to_wrong_confidence` — read the `run_verified_case` file
  back; the AFTER-side s→wc fact is present (dual-seam written-JSON pin).
- `test_written_artifact_carries_unfired_swc_record_only` — the record-only line is present.
- `test_swc_presence_required_on_0045_1` — a 0045/1 artifact missing the field fails validation.
- Amend the existing version-pin tests SAME change.
- Fails: version 0044/1; fields absent from the written seam.

### T12 — Schema bump + dual-seam (GREEN)
`live_verifier.py`: `VERIFIER_SCHEMA_VERSION = "0045/1"`; add `"0045/1"` to
`_KNOWN_VERIFIER_SCHEMA_VERSIONS`; presence-require `silence_to_wrong_confidence` +
`unfired_silence_to_wrong_confidence` on a 0045/1 artifact (legacy branches untouched); thread both
into `run_verified_case`'s written artifact (read from `backend.last_trajectory`). T11 passes.

### T13 — Frozen config (RED)
Add `harpyja/eval/test_refinement_config.py`:
- `test_config_is_frozen_dataclass` / `test_config_hash_is_stable`.
- `test_baseline_axis_pinned_by_path_and_sha256` — the committed pre-nudge baseline
  (`specs/.archive/0043-diagnosis/attribution/attribution_table.json`), fu_before re-derived.
- `test_0044_comparator_results_pinned_by_path_and_sha256` — `submission_results.json` sha256
  `e75b0a29e1bf3b27eb7939b921064fddfeee00b7d63222def70e70ab2bf02616`.
- `test_0044_comparator_config_pinned_by_path_and_sha256` — `submission_config.json` sha256
  `f5088aa4fb77f5d6e82900d239c43770e8800a3abf197a791b9503370781255f`.
- `test_0044_per_cell_artifacts_dir_pinned_32_files` — the `submission_run/artifacts/*.submission.json`
  dir, 32 files.
- `test_comparison_literals_rederived_from_pinned_artifacts` — 0044 net per model, fu_after=1,
  s→wc=5 (14b 0 / 8b 5 / 4b 0) RE-DERIVED from the pinned artifacts, NOT a hand-restated literal.
- `test_swc_by_model_rederived_5_from_artifacts` — the s→wc_0044 = 5 aggregate re-derives.
- `test_power_floor_min_covered_joined_cells_is_8` (live check).
- `test_power_floor_min_comparator_swc_is_3_documented_as_rederivation_guard` — role documented:
  checked against the freeze-time re-derived comparator literal (5), a re-derivation guard, NOT a
  live-run power check.
- `test_six_member_precedence_encoded`.
- `test_gate_projection_matches_sut_constants` — config LITERALS drift-pinned to
  `confidence_gate.CONFIDENCE_MAX_QUALIFYING_SPANS` + the refined-ranking constants.
- `test_sut_hash_covers_refined_gate_and_moved_signals` — `_SUT_FILES` includes
  `scout/confidence_gate.py` AND `scout/confidence_signals.py`.
- Fails: module absent.

### T14 — Frozen config (GREEN)
Implement `harpyja/eval/refinement_config.py`: `PREREGISTERED_REFINEMENT_CONFIG_0045` (frozen
dataclass of LITERALS), `REFINEMENT_CONFIG_HASH_0045`, `compute_sut_hash` over `_SUT_FILES`
(refined gate + moved signals), both axes' path+sha256 pins, the re-derived comparison literals,
the power floors, the per-model expected readings as DATA, the six-member precedence. T13 passes.
(The committed hash artifact with the post-lever SUT hash is emitted in T23.)

### T15 — Six-member verdict (RED)
Add `harpyja/eval/test_refinement_outcome.py`:
- `test_under_powered_when_covered_joined_below_8` — floor CONSUMED (live degrade-thinned join).
- `test_under_powered_when_comparator_swc_below_3` — the re-derivation-guard branch.
- `test_trades_directions_swc_dropped_fu_rose` / `test_trades_directions_fu_dropped_swc_rose` —
  both disjuncts of `(s→wc < 5 ∧ fu > 1) ∨ (fu < 1 ∧ s→wc > 5)`; the reopened direction named.
- `test_residual_persists_when_django_14315_8b_not_correct` — names the missing evidence.
- `test_gate_inert_when_no_benefit` — reproduces 0044 exactly ⇒ INERT (the `NUDGE_INERT` lesson).
- `test_gate_inert_even_when_both_costs_rose_and_net_not_improved` — the recorded caveat (an
  actively-worse run wearing "inert"; the risen classes recorded as data).
- `test_gate_calibrated_requires_all_conjuncts` — NET≥0 (bucket axis) ∧ no model net-negative ∧
  s→wc≤5 ∧ fu≤1 ∧ BENEFIT.
- `test_gate_calibrated_reachable_at_bucket_net_zero` — reachable even at a head-to-head regression
  vs 0044's +2 (the recorded rationale; head-to-head net + flask-5014 hold recorded beside it).
- `test_miscalibration_remains_terminal_else_names_failed_conjunct`.
- `test_precedence_first_true_wins` / `test_all_true_conditions_recorded`.
- `test_grid_totality_every_tuple_types_exactly_one_member` — cartesian sweep over (per-model net
  signs × floors × s→wc {<,=,>5} × fu {<,=,>1} × benefit × residual {correct,not}) returns exactly
  one member, never raises.
- Fails: module absent.

### T16 — Six-member verdict (GREEN)
Implement `harpyja/eval/refinement_outcome.py`: `RefinementVerdict` (SIX members —
`UNDER_POWERED` / `TRADES_DIRECTIONS` / `RESIDUAL_PERSISTS` / `GATE_INERT` / `GATE_CALIBRATED` /
`MISCALIBRATION_REMAINS`), `decide_refinement_outcome(config, before_cells, after_cells,
comparator, named_cells)` total pure over per-model tuples + named-cell outcomes, precedence 1→6
exactly per spec §Verdict, all-true conditions recorded, grid-total. T15 passes.

### T17 — Surviving-pins verify (VERIFY)
Executable source-sweep / full offline re-run: `test_params_pin_survives_refinement`,
`test_initial_prompt_binds_to_registered_tool_surface_single_source`,
`test_build_explorer_tools_returns_exactly_five_navigation_tools` (exact-tool-count unchanged — no
new tool), the Deep outbound-field guard, the dual-seam written-JSON pins, and the scout
no-eval-import ast pins all green after the SUT delta. Done-when: `uv run pytest -m "not integration"` green.

### T18 — Deduplication evaluation (REFACTOR)
Evaluate whether `refinement_outcome`/`refinement_config` should share code with
`submission_outcome`/`submission_config`. DECLINE-with-reason (mirror-not-share): the two specs'
FROZEN verdict orders and pinned axes must not be coupled — sharing would let a 0045 edit perturb
0044's byte-stable head-to-head axis. The genuine duplication (`_tool_spans_in_order`) was already
removed by the T5 move. Record the decision (0040-T22 / 0041-T21 / 0042-T7 decline precedent). All
tests still pass.

### T19 — Live re-measurement machinery (RED)
Add `harpyja/eval/test_refinement_run.py`:
- `test_run_refuses_without_live` — `live=False` raises (0040/0041 posture).
- `test_coverage_models_consumed_from_frozen_config` — required 14b + optional 8b/4b, never re-selected.
- `test_ledger_keyed_by_refinement_config_hash` — resumable ledger under `REFINEMENT_CONFIG_HASH_0045`.
- `test_startup_verifies_sut_hash_and_config_hash` — a mismatched SUT hash OR config hash is a typed
  STOP (both re-verified at every invocation).
- `test_four_sided_ledger_per_model` — conversions / regressions / s→wc / fu + NET per model, join
  on (case, model), degrade-thinned cells excluded and reported.
- `test_head_to_head_vs_0044_pinned_numbers` — AFTER ledger compared to the pinned 0044 literals.
- `test_summary_feeds_decide_refinement_outcome`.
- Fails: module absent.

### T20 — Live re-measurement machinery (GREEN)
Implement `harpyja/eval/refinement_run.py`: `run_refinement_cells(...)` via `run_gated_pool_pilot`
(dual-hash verify at startup, `_evict_other_models` per block, resumable) and
`build_refinement_run_summary(...)` (four-sided per-model ledger + head-to-head vs 0044 →
`decide_refinement_outcome`), mirroring `submission_run.py`. T19 passes.

### T21 — Integration smoke (RED)
Add `harpyja/eval/test_refinement_run_integration.py` (`@pytest.mark.integration`, skip-not-fail):
- `test_refinement_run_smoke_gated_and_dual_hash_verified` — under `HARPYJA_REQUIRE_LIVE_STACK`, one
  gated cell produces a verifier-PASSED artifact carrying the refined `confidence_fired` + the
  `silence_to_wrong_confidence` 0045/1 fields.
- `test_named_cells_enumerated_in_run_set` — `django-14315::8b`, `pytest-10081::14b`, and
  `flask-5014` (both cells) are in the run set (AC6 targets).
- `test_stop_and_warn_refusal_path_smoke` — the driver's refusal path (0043/0044 precedent).
- Fails: driver absent. (Lives in `harpyja/eval/`, NOT `specs/` — the collection-path precedent.)

### T22 — Integration smoke (GREEN)
Make the smoke skip-not-fail green (opt-in default per 0041); named cells enumerated; STOP-AND-WARN
refusal-path smoke green. No live spend in CI.

### T23 — Stage-2 freeze + operator driver (FREEZE/DOC)
AFTER T5/T9/T12 are merged (SUT byte-final) and BEFORE any live call: commit
`specs/0045-refinement/refinement_config/refinement_config.json` (the frozen config +
`REFINEMENT_CONFIG_HASH_0045` + post-lever SUT hash), pinned by
`test_committed_refinement_config_matches_computed_truth`. Commit the dual-hash STOP-AND-WARN
resumable driver `specs/0045-refinement/refinement_run/run_refinement.py` (`_preflight()` →
`/api/tags`; re-verifies BOTH the config hash AND the working-tree SUT hash each invocation;
`SystemExit("STOP-AND-WARN: …")`; exit 0 complete / 3 work-remaining / 2 exclusive-endpoint
contended). Done-when: config artifact + driver committed; no live spend yet.

### T24 — Gated live re-measurement (LIVE, dev Ollama)
Run the committed driver on the evicted-before / re-pinned-after 0041-gated endpoint (detach per
the long-run memory note). Produces `specs/0045-refinement/refinement_run/refinement_results.json`
(four-sided ledger per model, `0041/pilot/2` exclusivity proof, head-to-head vs 0044) + the run
summary. Per-model conversions / regressions / s→wc / fu + NET; the record-only unfired-s→wc line;
the named-cell outcomes.

### T25 — Typed close-out (DOC)
`specs/0045-refinement/outcome.md`: the `decide_refinement_outcome` label (all six members
enumerated — `UNDER_POWERED` / `TRADES_DIRECTIONS` names the reopened direction / `RESIDUAL_PERSISTS`
names the missing evidence / `GATE_INERT` / `GATE_CALIBRATED` / `MISCALIBRATION_REMAINS` names the
failed conjunct), the selected member PLUS all true conditions recorded as data, the record-only
unfired-s→wc cross-check reported beside s→wc, the head-to-head aggregate net + flask-5014 named-cell
hold recorded. Pilot-N signal, not an inferential claim. Train-on-test confound AND single-cell
(`django-14315::8b`) sensitivity recorded per the 0042 precedent. Flip `status:` at close;
path-pins point at `specs/.archive/0045-refinement/`.

## Risks / notes

- **Gold-entanglement in the one-definition move** → mitigation: only the trajectory-only helpers
  move (`_tool_spans_in_order` / containment / convergence); `classify_confidence_null` (uses gold
  `expected`) STAYS eval-side; `test_confidence_signals_imports_nothing_from_eval` (ast) +
  `test_classify_confidence_null_stays_eval_side_uses_gold` pin both directions. The gold-free
  overlap primitive moves WITH convergence and `span_hit_kind`'s "line" grade is asserted to agree
  (`test_convergent_overlap_agrees_with_eval_span_hit_kind_line_grade`) so ONE overlap definition
  survives without a scout→eval import.
- **Stage-1 sightedness / force-fit** → mitigation: the table is frozen+committed (T3) BEFORE any
  per-cell attribution (T6/T7); it declares the (b)/(c) detail uncomputed and carries the typed
  `NO_DISCRIMINATOR_SEPARATES` honest exit, so a non-separation is reported, not forced.
- **Gaming-by-silence (fired-conditioned s→wc)** → mitigation: the record-only
  `unfired_silence_to_wrong_confidence` line is threaded through both seams and reported beside s→wc
  in the outcome — record-only, never in the verdict predicate.
- **Dual-seam schema miss (5th recurrence risk)** → mitigation: T10 (backend) + T11/T12 (written
  artifact) written-JSON pins read the file back for both new fields at BOTH seams; version-pin
  tests amended same-change; presence-required on 0045/1.
- **Stage-2 SUT-hash freeze ordering** → mitigation: `compute_sut_hash` includes both
  `confidence_gate.py` AND `confidence_signals.py`; `test_sut_hash_covers_refined_gate_and_moved_signals`
  guards the omission; T23 hard-sequenced after all SUT GREENs and before T24; the driver
  re-verifies BOTH hashes each invocation (typed STOP).
- **Anti-tautology (hand-restated literals)** → mitigation: the comparison literals (net per model,
  fu_after=1, s→wc=5 by model) are RE-DERIVED from the pinned 0044 artifacts in the pin test, not
  asserted as bare constants; `min_comparator_swc=3` guards the re-derived base is non-vacuous.
- **Single-cell / train-on-test sensitivity** → mitigation: `RESIDUAL_PERSISTS` on `django-14315::8b`
  is a single pilot-N cell gating `GATE_CALIBRATED`; recorded as a signal-not-inference alongside
  the train-on-test confound in the outcome doc; pool enlargement stays THE unblock.
- **GATE_INERT under-describes an actively-worse run** → mitigation: all-true conditions recorded;
  the risen cost classes named as data; the outcome doc reads the recorded data, not just the label.
- **Params byte-pin** → mitigation: the refinement rides `messages` / record fields ONLY;
  `test_params_pin_survives_refinement` keeps `params == {max_tokens: 2048}` (think=None) green.
- **Live contamination** → mitigation: `run_gated_pool_pilot` exclusive-endpoint hard gate (no
  bypass param), evict-before / re-pin-after; never run the suite concurrently with T24; SUT frozen
  for the run (any live-observed defect fixed AFTER, per the run-integrity rule).
