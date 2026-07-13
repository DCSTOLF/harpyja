---
spec: "0045"
---

# Tasks

## Area 1 — Stage-1 discriminator-selection table (frozen BEFORE attribution, offline)
- [x] T1 (RED) — `harpyja/eval/test_discriminator_table.py`: frozen dataclass + stable hash, CLOSED candidate set, typed `NO_DISCRIMINATOR_SEPARATES` row, 0044 headline facts as data, per-cell (b)/(c) detail declared uncomputed, per-model gate branch frozen
- [x] T2 (GREEN) — `harpyja/eval/discriminator_table.py`: `DISCRIMINATOR_SELECTION_TABLE_0045` + `CANDIDATE_SIGNALS` + `NO_DISCRIMINATOR_SEPARATES` + `DISCRIMINATOR_TABLE_HASH_0045`
- [x] T3 (FREEZE) — commit `specs/0045-refinement/discriminator_table/discriminator_table.json` BEFORE any attribution; `test_committed_discriminator_table_matches_computed_truth`

## Area 2 — One-definition move to scout + per-cell attribution (offline)
- [x] T4 (RED) — `harpyja/scout/test_confidence_signals.py`: containment detected/absent, convergence two-tools/none, trajectory-only scanner, ast no-eval-import gold-blind pin, overlap agrees with `span_hit_kind` "line" grade
- [x] T5 (GREEN) — `harpyja/scout/confidence_signals.py` (move `_tool_spans_in_order`/`grep_hits_inside_symbol_spans`/`convergent_evidence` + gold-free overlap primitive); `eval/submission_observability.py` imports BY IDENTITY; `classify_confidence_null` stays eval-side; identity + stays-eval-side tests amended SAME change
- [x] T6 (RED) — `harpyja/eval/test_refinement_attribution.py`: over 32 pinned 0044 firing artifacts, name each fired-on-wrong-span triggering signal + the never-fired (`pytest-10081::14b`) unrecognised evidence; uses scout signals by identity; sha256-pinned
- [x] T7 (GREEN) — `harpyja/eval/refinement_attribution.py`: per-cell attribution feeding the frozen stage-1 table

## Area 3 — Refined ranking in the gate (offline)
- [x] T8 (RED) — `harpyja/scout/test_confidence_gate.py`: weak/singleton no longer fires; 0044 never-fired evidence shape now fires; ranking matches stage-1-selected rule; gate stays gold-blind (ast)
- [x] T9 (GREEN) — `harpyja/scout/confidence_gate.py`: refine `qualifying_symbols_spans`/ranking per the selected rule, consuming `scout.confidence_signals` (scout-only), both directions pinned

## Area 4 — Schema bump 0044/1 → 0045/1 + s→wc first-class (dual-seam, offline)
- [x] T10 (RED→GREEN) — `harpyja/scout/test_explorer_backend.py` + `explorer_backend.py`: thread `silence_to_wrong_confidence` + record-only `unfired_silence_to_wrong_confidence` into `build_trajectory_record`; `test_params_pin_survives_refinement` stays green
- [x] T11 (RED) — `harpyja/eval/test_live_verifier.py`: `0045/1` bump, legacy (incl. `0044/1`) validate unchanged, written artifact carries both fields, presence-required on `0045/1`, version-pin tests amended same-change
- [x] T12 (GREEN) — `harpyja/eval/live_verifier.py`: `VERIFIER_SCHEMA_VERSION="0045/1"`, `_KNOWN_...` widened, both fields threaded into `run_verified_case` written artifact, presence-required

## Area 5 — Frozen config + total-pure six-member verdict (offline)
- [x] T13 (RED) — `harpyja/eval/test_refinement_config.py`: frozen+hashed, baseline + 0044 comparator (results `e75b0a29…`, config `f5088aa4…`, 32 artifacts) pinned path+sha256, literals (net/model, fu_after=1, s→wc=5 by 14b0/8b5/4b0) RE-DERIVED, floors 8 (live) + 3 (re-derivation guard, role documented), six-member precedence, gate-projection drift pin, SUT hash covers refined gate + moved signals
- [x] T14 (GREEN) — `harpyja/eval/refinement_config.py`: `PREREGISTERED_REFINEMENT_CONFIG_0045` + `REFINEMENT_CONFIG_HASH_0045` + `compute_sut_hash`
- [x] T15 (RED) — `harpyja/eval/test_refinement_outcome.py`: six members, precedence first-true-wins, UNDER_POWERED both floors, TRADES_DIRECTIONS both disjuncts (reopened direction named), RESIDUAL_PERSISTS (django-14315::8b), GATE_INERT + actively-worse caveat, GATE_CALIBRATED all-conjuncts + bucket-net-0 reachability caveat, MISCALIBRATION_REMAINS names failed conjunct, all-true recorded, grid-totality
- [x] T16 (GREEN) — `harpyja/eval/refinement_outcome.py`: `RefinementVerdict` (SIX members) + `decide_refinement_outcome` total pure over per-model tuples + named-cell outcomes
- [x] T17 (VERIFY) — full offline suite green: params byte-pin, prompt↔surface drift guard, exact-tool-count (five, unchanged), Deep outbound-field guard, dual-seam written-JSON pins, scout no-eval-import ast pins
- [x] T18 (REFACTOR) — evaluate dedup vs 0044 `submission_outcome`/`submission_config`: DECLINE-with-reason (mirror-not-share; the genuine `_tool_spans_in_order` duplication already removed in T5); record the decision (0040-T22/0041-T21/0042-T7 precedent)

## Area 6 — Gated live re-measurement + named cells (offline unit + live)
- [x] T19 (RED) — `harpyja/eval/test_refinement_run.py`: refuse-without-live, coverage-from-frozen-config, ledger keyed by config hash, startup dual-hash (SUT+config) verify typed STOP, four-sided per-model ledger + NET, head-to-head vs 0044 pinned numbers, feeds `decide_refinement_outcome`
- [x] T20 (GREEN) — `harpyja/eval/refinement_run.py`: `run_refinement_cells` (via `run_gated_pool_pilot`) + `build_refinement_run_summary`
- [x] T21 (RED) — `harpyja/eval/test_refinement_run_integration.py` (`integration`, skip-not-fail): gated + dual-hash-verified smoke carrying `silence_to_wrong_confidence`; named cells (django-14315::8b, pytest-10081::14b, flask-5014 both cells) enumerated; STOP-AND-WARN refusal-path smoke
- [x] T22 (GREEN) — integration smoke skip-not-fail green; named cells enumerated; refusal path green
- [x] T23 (FREEZE/DOC) — commit `specs/0045-refinement/refinement_config/refinement_config.json` (AFTER SUT lands, BEFORE live) pinned by `test_committed_refinement_config_matches_computed_truth`; commit dual-hash STOP-AND-WARN resumable driver `.../refinement_run/run_refinement.py` (exit 0/2/3)
- [x] T24 (LIVE — dev Ollama) — run the gated driver on the evicted-before/re-pinned-after 0041 endpoint; emit `specs/0045-refinement/refinement_run/refinement_results.json` four-sided ledger + head-to-head vs 0044 + record-only unfired-s→wc + named-cell outcomes

## Area 7 — Doc close-out
- [x] T25 (DOC) — `specs/0045-refinement/outcome.md`: typed six-member `decide_refinement_outcome` label, all six enumerated, selected + all-true conditions recorded, record-only unfired-s→wc beside s→wc, head-to-head net + flask-5014 hold, train-on-test + single-cell (django-14315::8b) sensitivity recorded; flip `status:`, archive path-pins
