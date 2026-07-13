---
spec: "0044"
---

# Tasks

## Area 1 — Gold-blind confidence predicate (offline)
- [x] T1 (RED) — `test_confidence_gate.py`: qualifying projection on all AC1 edges (single/multi-span fire, over-bound repo-wide, degraded ANNOTATION, REPLACEMENT marker, non-exact shape, zero-span, file-local == repo-wide, frozen template)
- [x] T2 (GREEN) — `confidence_gate.py`: `CONFIDENCE_MAX_QUALIFYING_SPANS=5`, `CONFIDENCE_NUDGE_TEMPLATE`, `qualifying_symbols_spans`, `build_confidence_nudge` (gold-blind, no eval/ import)

## Area 2 — Mid-loop injection seam + 0043 sentence removal (offline)
- [x] T3 (RED) — `test_context_map.py`: `test_submit_early_nudge_removed_from_prompt` (sentence still present)
- [x] T4 (GREEN) — `context_map.py`: delete the 0043 unconditional sentence; drift guard + query stay
- [x] T5 (RED) — `test_explorer_loop.py`: fires-once, post-batch-boundary (0029), evidence-gated-not-turn-gated, survives truncation, no loop-detection perturbation, not-a-model-turn, `LoopResult` confidence fields
- [x] T6 (GREEN) — `explorer_loop.py`: post-batch injection + `LoopResult.confidence_fired/triggering_signal/firing_turn` + non-tombstoned `confidence-nudge` kind
- [x] T7 (RED→GREEN) — `test_explorer_backend.py` + `explorer_backend.py`: thread confidence fields into `build_trajectory_record`; add `test_params_pin_survives_confidence_nudge`

## Area 3 — Schema bump + dual-seam + record-only observability (offline)
- [x] T8 (RED) — `test_live_verifier.py`: 0044/1 bump, legacy versions validate, confidence fields in record AND written artifact
- [x] T9 (GREEN) — `live_verifier.py`: `VERIFIER_SCHEMA_VERSION="0044/1"`, `_KNOWN_...` widened, confidence fields both seams, presence-required on 0044/1
- [x] T10 (RED) — `test_submission_observability.py`: (b) grep-inside-symbol-span, (c) convergent evidence, attributable-null (never-fired/fired-but-ignored/fired-on-wrong-span) via `span_hit_kind` BY IDENTITY
- [x] T11 (GREEN) — `submission_observability.py` + wire postflight fields into `run_verified_case` written artifact; extend written-JSON pin

## Area 4 — Frozen config + total-pure verdict (offline)
- [x] T12 (RED) — `test_submission_config.py`: frozen, hashed, gate projection == SUT constant, nudge template == SUT surface, `never_fires_max_14b_firings=0`, floors 8/3, baseline ledger identity (path+hash, fu_before=6), SUT hash covers `confidence_gate.py`, per-model readings
- [x] T13 (GREEN) — `submission_config.py`: `PREREGISTERED_SUBMISSION_CONFIG_0044` + `SUBMISSION_CONFIG_HASH_0044` + `compute_sut_hash`
- [x] T14 (RED) — `test_submission_outcome.py`: FIVE members, frozen precedence, benefit conjunct, UNDER_POWERED floor consumed, NEVER_FIRES keyed to 14b, all-true-conditions-recorded, grid-totality
- [x] T15 (GREEN) — `submission_outcome.py`: `decide_submission_outcome` total pure over per-model (net, firing-rate) + aggregate net + conversions + fu + coverage
- [x] T16 (VERIFY) — full offline suite green: params byte-pin, prompt↔surface drift guard, exact-tool-count, Deep outbound-field guard all survive

## Area 5 — Gated live re-measurement (offline unit + live)
- [x] T17 (RED) — `test_submission_run.py`: refuse-without-live, coverage-from-frozen-config, ledger-keyed-by-config-hash, startup SUT-hash verify, BEFORE(committed table)/AFTER(ledger) summary, suspect/degraded excluded
- [x] T18 (GREEN) — `submission_run.py`: `run_submission_cells` (via `run_gated_pool_pilot`) + `build_submission_run_summary`
- [x] T19 (RED) — `test_submission_run_integration.py` (marker `integration`, skip-not-fail): gated + SUT-verified smoke; 0043 casualty cells (flask-5014 14b+8b, django-14315::8b) enumerated
- [x] T20 (GREEN) — integration smoke skip-not-fail green
- [x] T21 (FREEZE/DOC) — commit `specs/0044-submission/submission_config/submission_config.json` (AFTER SUT lands, BEFORE live) pinned by `test_committed_submission_config_matches_computed_truth`; commit STOP-AND-WARN resumable driver `.../submission_run/run_submission.py` (exit 0/2/3)
- [x] T22 (LIVE — dev Ollama) — run the gated driver on the evicted-before/re-pinned-after 0041 endpoint; emit `submission_results.json` ledger + summary; per-model conversions/regressions/NET/firing-rate + fu before/after

## Area 6 — Doc close-out
- [x] T23 (DOC) — `specs/0044-submission/outcome.md`: typed `decide_submission_outcome` label, all true conditions, per-model firing rates, attributable-null distribution; flip `status:`, archive path-pins
