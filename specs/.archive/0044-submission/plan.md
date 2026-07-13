---
spec: "0044"
status: planned
created: 2026-07-12
strategy: tdd
---

# Plan — 0044 submission

Confidence-conditioned submit-early nudge: replace 0043's unconditional
`build_initial_prompt` sentence with a mid-loop, evidence-gated injection that fires
ONLY on a symbols-derived confident span, then re-measure the 0043 pilot cells on the
0041-gated endpoint against the committed pre-nudge baseline and type the outcome.

## Overview

Six work areas, all in strict RED→GREEN TDD order (every GREEN preceded by its RED):

1. **Gold-blind confidence predicate** — new SUT module `harpyja/scout/confidence_gate.py`
   (lives in `scout/`, sees only a tool result). Qualifying projection: a `symbols` result
   that is clean (no 0035 marker of either shape), bounded (1..`CONFIDENCE_MAX_QUALIFYING_SPANS = 5`),
   exact-span-shaped (every span has non-`None` start/end). File-local AND repo-wide by-name
   both qualify; the span-count bound excludes the repo-wide blast radius. Owns the frozen
   nudge template (multi-span wording).
2. **Mid-loop injection seam** — extend `harpyja/scout/explorer_loop.py`: after a COMPLETED
   tool-result batch (0029 post-batch boundary, never mid-answer-all-N), on the FIRST qualifying
   pass append ONE `role: user` nudge, at most once, no turn/wall-clock fallback. Remove the 0043
   unconditional sentence from `build_initial_prompt`. Survive `scout_history_char_cap`
   truncation, no loop-detection perturbation, not a model turn. `LoopResult` gains
   `confidence_fired`/`confidence_triggering_signal`/`confidence_firing_turn`.
3. **Artifact schema bump** — `VERIFIER_SCHEMA_VERSION 0043/1 → 0044/1` threaded through BOTH
   seams (`build_trajectory_record` + `run_verified_case`), written-JSON pinned, legacy versions
   validate unchanged (4th dual-seam application). SUT-side confidence fields ride the loop;
   record-only (b)/(c) and the attributable-null classification are computed EVAL-SIDE POSTFLIGHT,
   reusing `metrics.span_hit_kind` BY IDENTITY.
4. **Frozen config + verdict** — `PREREGISTERED_SUBMISSION_CONFIG_0044`
   (`harpyja/eval/submission_config.py`) + `decide_submission_outcome`
   (`harpyja/eval/submission_outcome.py`), a total pure function over per-model (net, firing-rate),
   aggregate net, conversions, fu_before/fu_after, and live coverage, FIVE enum members under
   frozen precedence, grid-totality tested.
5. **Gated live re-measurement** — `harpyja/eval/submission_run.py` via `run_gated_pool_pilot`
   (resumable ledger keyed by `SUBMISSION_CONFIG_HASH_0044`, SUT-hash verify at startup),
   operator driver `specs/0044-submission/submission_run/run_submission.py` (STOP-AND-WARN,
   exit 0/2/3), integration smoke `harpyja/eval/test_submission_run_integration.py`. BEFORE =
   the committed pre-nudge per-cell table `specs/.archive/0043-diagnosis/attribution/attribution_table.json`
   (the "0040/0042 ledger" — 0040 pilot + 0042 adoption cells carrying `bucket` +
   `submission_outcome`; fu_before = 6, 14b 2 / 8b 1 / 4b 3). Re-check the 0043 casualties.
6. **Doc close-out** — typed `outcome.md` via `decide_submission_outcome`.

### Two-stage freeze ordering (hard-sequenced)

- Stage 1 (choosing rules) is already frozen in `spec.md` (gate = symbols solely; precedence;
  floors; readings) BEFORE implementation — no data was seen.
- Stage 2: `PREREGISTERED_SUBMISSION_CONFIG_0044` — naming the choice, the exact nudge
  template + `max_qualifying_spans`, the baseline ledger identity, and the **post-lever SUT
  hash** — is frozen + hashed + **committed AFTER the SUT lever lands (T2, T6, T7, T9, T11 all
  merged) and BEFORE any live call (T21 driver / T22 live spend)**. `compute_sut_hash` MUST
  include the new `harpyja/scout/confidence_gate.py`, so the config cannot be frozen until the
  SUT surface is byte-final. No live spend before the stage-2 config artifact is committed.

## Task table

| ID | Phase | Area | File(s) | Done-when |
|----|-------|------|---------|-----------|
| T1 | RED | 1 | `harpyja/scout/test_confidence_gate.py` | New predicate tests fail (module/functions absent) |
| T2 | GREEN | 1 | `harpyja/scout/confidence_gate.py` | All T1 edges pass |
| T3 | RED | 2 | `harpyja/scout/test_context_map.py` | Removal test fails (0043 sentence still present) |
| T4 | GREEN | 2 | `harpyja/scout/context_map.py` | 0043 sentence gone; drift guard + query still present |
| T5 | RED | 2 | `harpyja/scout/test_explorer_loop.py` | Injection-seam tests fail (no injection yet) |
| T6 | GREEN | 2 | `harpyja/scout/explorer_loop.py` | Injection + `LoopResult` fields land; T5 passes |
| T7 | RED→GREEN | 2 | `harpyja/scout/test_explorer_backend.py`, `explorer_backend.py` | Confidence fields threaded to `build_trajectory_record`; params byte-pin stays green |
| T8 | RED | 3 | `harpyja/eval/test_live_verifier.py` | 0044/1 bump + dual-seam + written-JSON + legacy pins fail |
| T9 | GREEN | 3 | `harpyja/eval/live_verifier.py` | 0044/1 threaded both seams; legacy validate; T8 passes |
| T10 | RED | 3 | `harpyja/eval/test_submission_observability.py` | (b)/(c) + attributable-null tests fail |
| T11 | GREEN | 3 | `harpyja/eval/submission_observability.py`, `live_verifier.py` | Postflight fields computed + written; T10 passes |
| T12 | RED | 4 | `harpyja/eval/test_submission_config.py` | Frozen-config tests fail (absent) |
| T13 | GREEN | 4 | `harpyja/eval/submission_config.py` | Config + hash + drift/baseline pins pass |
| T14 | RED | 4 | `harpyja/eval/test_submission_outcome.py` | Verdict + grid-totality tests fail |
| T15 | GREEN | 4 | `harpyja/eval/submission_outcome.py` | FIVE members under precedence; grid total; T14 passes |
| T16 | VERIFY | 4 | (source-sweep) | Params byte-pin + prompt↔surface drift guard + exact-tool-count all green post-SUT |
| T17 | RED | 5 | `harpyja/eval/test_submission_run.py` | Runner/summary tests fail (absent) |
| T18 | GREEN | 5 | `harpyja/eval/submission_run.py` | Resumable + SUT-verify + BEFORE/AFTER summary pass |
| T19 | RED | 5 | `harpyja/eval/test_submission_run_integration.py` | Integration smoke fails (opt-in, marked) |
| T20 | GREEN | 5 | `harpyja/eval/test_submission_run_integration.py` | Smoke skip-not-fail green; casualty cells enumerated |
| T21 | FREEZE/DOC | 5 | `specs/0044-submission/submission_config/*.json`, `.../submission_run/run_submission.py` | Config artifact committed (post-SUT, pre-live); STOP-AND-WARN driver committed |
| T22 | LIVE | 5 | `specs/0044-submission/submission_run/submission_results.json` | Gated live run complete; ledger + summary emitted |
| T23 | DOC | 6 | `specs/0044-submission/outcome.md` | Typed outcome recorded; per-model firing rates + all true conditions |

Offline (no endpoint): T1–T19, T21 (freeze+commit). Live-spend (dev Ollama): T22, and the
executable-but-skip-not-fail smoke behind `HARPYJA_REQUIRE_LIVE_STACK` (T19/T20).

## Test-first sequence

### T1 — Confidence predicate (RED)
Add `harpyja/scout/test_confidence_gate.py`:
- `test_qualifying_symbols_result_single_exact_span_fires` — clean 1-span `list[CodeSpan]` → returns the span.
- `test_qualifying_symbols_result_multi_exact_span_fires_and_names_all_spans` — clean multi-span (e.g. 3) → qualifies; the built nudge names ALL spans (multi-span wording, not first-span steering).
- `test_over_bound_repo_wide_batch_does_not_qualify` — a `symbols(name=…)` batch of > `CONFIDENCE_MAX_QUALIFYING_SPANS` (e.g. 6, up to `scout_symbols_repo_max_entries`) → no fire.
- `test_degraded_annotation_result_does_not_qualify` — `["symbols-degraded: 'x.py'", *CodeSpans]` (leading marker) → no fire.
- `test_replacement_marker_string_does_not_qualify` — bare `str` result (`symbols-args-missing…`) → no fire.
- `test_non_exact_span_shape_does_not_qualify` — a span with `start_line=None`/`end_line=None` present → no fire (file-level is not "exact").
- `test_zero_span_result_does_not_qualify` — empty `list` → no fire.
- `test_file_local_and_repo_wide_qualify_under_same_three_conditions` — both routes qualify when clean/bounded/exact.
- `test_nudge_template_is_frozen_constant` — `build_confidence_nudge` uses `CONFIDENCE_NUDGE_TEMPLATE` verbatim; `role == "user"`.
- Fails: module/functions absent.

### T2 — Confidence predicate (GREEN)
Implement `harpyja/scout/confidence_gate.py`: `CONFIDENCE_MAX_QUALIFYING_SPANS = 5`,
`CONFIDENCE_NUDGE_TEMPLATE` (multi-span wording, e.g. "your symbols result contains the exact
span(s) {spans}; if one answers the query, submit it now via submit_citations"),
`qualifying_symbols_spans(result) -> list[CodeSpan]` (empty ⇒ no fire; a `list` with zero `str`
elements, 1..max length, every span exact-shaped), `build_confidence_nudge(spans) -> dict`
(role `user`, content = template formatted over all spans). Gold-blind by construction (no
`eval/` import, no gold parameter). All T1 pass.

### T3 — Remove 0043 unconditional sentence (RED)
Replace `test_submit_early_nudge_present_in_prompt` (test_context_map.py:124) with
`test_submit_early_nudge_removed_from_prompt` — asserts the 0043 sentence ("As soon as a tool
result shows the span…beats running out of time.") is ABSENT and the tool-menu + `Query:` line
remain. Fails: sentence still in `build_initial_prompt`.

### T4 — Remove 0043 sentence (GREEN)
Delete lines 76–80 of `build_initial_prompt`; keep the tool enumeration (so
`test_initial_prompt_binds_to_registered_tool_surface_single_source` stays green) and the query.
T3 passes.

### T5 — Mid-loop injection seam (RED)
Add to `harpyja/scout/test_explorer_loop.py`:
- `test_confidence_nudge_fires_once_after_qualifying_symbols_batch` — a `symbols` batch returns a
  qualifying result; the NEXT message the model sees is the `role:user` frozen nudge, appended
  AFTER the batch's final tool message.
- `test_confidence_nudge_injected_only_at_post_batch_boundary_never_mid_answer_all_n` — with N
  parallel tool_calls, every `tool_call_id` is answered BEFORE the nudge (0029 pin: no message
  interleaved between an assistant `tool_calls` and its N tool responses).
- `test_confidence_nudge_fires_at_most_once_per_case` — a second qualifying result adds no second nudge.
- `test_confidence_nudge_is_evidence_gated_not_turn_gated` — many turns, no qualifying span → ZERO
  nudge (the 0043 failure mode is structurally impossible).
- `test_confidence_nudge_survives_history_char_cap_truncation` — force truncation; the nudge
  message is retained (never dropped, never displacing citable observations).
- `test_confidence_nudge_does_not_perturb_loop_detection` — injection registers no spans and does
  not change the no-new-span/repeat counter.
- `test_confidence_nudge_is_not_a_model_turn` — `turns_used` and turn-cap arithmetic unchanged by injection.
- `test_loop_result_carries_confidence_fired_signal_and_turn` — `LoopResult.confidence_fired=True`,
  `confidence_triggering_signal="symbols-exact-span"`, `confidence_firing_turn` = the turn index.
- `test_non_firing_run_reports_confidence_fired_false` — no qualifying span ⇒ `confidence_fired=False`,
  signal `None`, turn `None`.
- Fails: no injection logic; `LoopResult` lacks the fields.

### T6 — Mid-loop injection seam (GREEN)
In `explorer_loop.py`: add `LoopResult.confidence_fired/confidence_triggering_signal/confidence_firing_turn`.
In `_answer_tool_call`, when a `symbols` result qualifies (via `confidence_gate.qualifying_symbols_spans`),
stash the qualifying spans on `_Session`. In `run_explorer_loop`, AFTER the tool_calls for-loop and
BEFORE `maybe_truncate`/next model call, if not yet fired and a pending qualifying stash exists,
append `build_confidence_nudge(spans)` (`session.add(..., "confidence-nudge")`, a new kind that
`maybe_truncate` never tombstones), set fired + record firing turn. The nudge kind carries no
spans, so `note_navigation`/loop-detection is untouched. T5 passes.

### T7 — Backend threading + pins (RED→GREEN)
In `harpyja/scout/test_explorer_backend.py`:
- `test_trajectory_record_carries_confidence_fired_signal_and_turn` — RED until backend threads
  `result.confidence_fired/…` into `build_trajectory_record`.
- Add `test_params_pin_survives_confidence_nudge` (successor to `test_params_pin_survives_submit_early_nudge`)
  — with `think=None`, the outbound `params == {"max_tokens": 2048}`; the mid-loop nudge rides
  `messages` ONLY and adds nothing to params.
GREEN: `explorer_backend.py` passes the three new `LoopResult` fields into `build_trajectory_record`
(the call must accept them — coordinate with T9 signature). Params pin unchanged.

### T8 — Schema bump + dual-seam (RED)
In `harpyja/eval/test_live_verifier.py`:
- `test_verifier_schema_version_is_0044_1`.
- `test_legacy_verifier_versions_validate_unchanged` — 0031/0033/0034/0038/0043 artifacts still validate.
- `test_build_trajectory_record_carries_confidence_fields` — `confidence_fired/…` present in the record.
- `test_written_artifact_carries_confidence_fields` — read the file back; the hand-assembled
  `run_verified_case` artifact carries the confidence fields (dual-seam written-JSON pin).
- Fails: version still 0043/1; confidence fields absent from both seams.

### T9 — Schema bump + dual-seam (GREEN)
`live_verifier.py`: `VERIFIER_SCHEMA_VERSION = "0044/1"`; add `"0044/1"` to
`_KNOWN_VERIFIER_SCHEMA_VERSIONS`; presence-require the confidence fields on a 0044/1 artifact in
`validate_verifier_artifact` (legacy branches untouched). Add `confidence_fired`/
`confidence_triggering_signal`/`confidence_firing_turn` params to `build_trajectory_record`
(present-and-None default) AND thread them into `run_verified_case`'s written artifact (reading
them from `backend.last_trajectory`). T8 passes.

### T10 — Record-only observability + attributable-null (RED)
Add `harpyja/eval/test_submission_observability.py`:
- `test_grep_hit_inside_symbol_span_detected` / `_absent` — (b): a grep result line within a
  previously-returned `symbols` span (line-interval containment, same file) — fixture-pinned both ways.
- `test_convergent_evidence_two_tools_overlap_same_file` / `_none` — (c): ≥2 distinct tools
  returned overlapping (non-empty intersection) spans on one file — fixture-pinned.
- `test_attributable_null_never_fired` — `confidence_fired=False` ⇒ `"never-fired"`.
- `test_attributable_null_fired_but_ignored` — fired, no correct submit / found-unsubmitted ⇒ `"fired-but-ignored"`.
- `test_attributable_null_fired_on_wrong_span` — fired, triggering span does NOT line-hit gold ⇒
  `"fired-on-wrong-span"` — reusing `metrics.span_hit_kind` BY IDENTITY.
- `test_wrong_span_attribution_uses_span_hit_kind_by_identity` — monkeypatch `metrics.span_hit_kind`;
  only a true delegate observes it (one-oracle-reuse, never a second overlap definition).
- Fails: module absent.

### T11 — Record-only observability + attributable-null (GREEN)
Implement `harpyja/eval/submission_observability.py`: `grep_hits_inside_symbol_spans(trajectory)`,
`convergent_evidence(trajectory)` (both eval-side postflight over the persisted trajectory, gold-free),
`classify_confidence_null(trajectory, expected)` (imports `span_hit_kind` by identity). Wire all
three into `run_verified_case` postflight and the written artifact (record-only fields (b)/(c) +
the attributable-null label). Extend the T8 written-JSON pin. T10 passes.

### T12 — Frozen config (RED)
Add `harpyja/eval/test_submission_config.py`:
- `test_config_is_frozen_dataclass` / `test_config_hash_is_stable`.
- `test_gate_projection_max_spans_matches_sut_constant` — `config.max_qualifying_spans ==
  confidence_gate.CONFIDENCE_MAX_QUALIFYING_SPANS` (drift pin).
- `test_config_nudge_template_matches_sut_surface` — `config.nudge_template ==
  confidence_gate.CONFIDENCE_NUDGE_TEMPLATE`; role `user` (prompt↔surface drift guard successor).
- `test_never_fires_threshold_is_numeric_field` — `never_fires_max_14b_firings == 0` (data, not prose).
- `test_power_floors_present` — `min_covered_before_cells == 8`, `min_before_found_unsubmitted == 3`.
- `test_baseline_ledger_identity_pins_path_and_hash` — the frozen baseline path +
  per-source sha256 match the committed `attribution_table.json`; fu_before re-derives to 6
  (14b 2 / 8b 1 / 4b 3) from that pinned artifact (guards a baseline-identity error).
- `test_sut_hash_covers_confidence_gate_file` — `confidence_gate.py` is in `_SUT_FILES`.
- `test_per_model_readings_present` — the 8b (regressions=0 at ANY firing rate), 4b (inert), 14b
  (beneficiary) readings are DATA in the config.
- Fails: module absent.

### T13 — Frozen config (GREEN)
Implement `harpyja/eval/submission_config.py`: `PREREGISTERED_SUBMISSION_CONFIG_0044` (frozen
dataclass), `SUBMISSION_CONFIG_HASH_0044`, `compute_sut_hash` (including `confidence_gate.py`),
baseline ledger identity, gate projection, nudge template, record-only definitions, floors,
`never_fires_max_14b_firings=0`, per-model readings. T12 passes. (NOTE: the committed hash
artifact is emitted in T21, post-SUT.)

### T14 — Verdict function (RED)
Add `harpyja/eval/test_submission_outcome.py`:
- `test_under_powered_when_coverage_below_floor` — covered before < 8 ⇒ `UNDER_POWERED` (floor CONSUMED).
- `test_never_fires_keyed_to_14b_only` — 14b firings ≤ 0 ⇒ `NEVER_FIRES`; an 8b zero-firing rate
  does NOT trigger it.
- `test_still_trades_off_on_any_negative_model_net` / `test_still_trades_off_on_negative_aggregate`.
- `test_nudge_inert_when_fired_but_no_benefit` — conversions=0 AND fu_after≥fu_before ⇒ `NUDGE_INERT`
  (a fired-but-ignored net-0 run does NOT ship).
- `test_ships_requires_benefit_conjunct` — aggregate net≥0 AND no model net<0 AND (conversions≥1 OR
  fu_after<fu_before) ⇒ `CONDITIONED_NUDGE_SHIPS`.
- `test_precedence_first_match_wins` — under-powered-AND-negative types `UNDER_POWERED`.
- `test_all_true_conditions_recorded` — the outcome records every satisfied condition, not only the winner.
- `test_grid_totality_every_input_types` — cartesian sweep over (per-model net signs × 14b firing
  ∈{0,>0} × coverage {<8,≥8} × conversions {0,≥1} × fu delta {<,≥}) returns an enum member, never raises.
- Fails: module absent.

### T15 — Verdict function (GREEN)
Implement `harpyja/eval/submission_outcome.py`: `SubmissionVerdict` (FIVE members),
`decide_submission_outcome(config, before_cells, after_cells)` total pure over per-model
(net, firing-rate), aggregate net, conversions, fu_before/fu_after, coverage, precedence
1→5 exactly as spec §Verdict machinery. T14 passes.

### T16 — Surviving-pins verify (VERIFY)
Executable source-sweep / re-run: `test_params_pin_survives_confidence_nudge`,
`test_initial_prompt_binds_to_registered_tool_surface_single_source`,
`test_build_explorer_tools_returns_exactly_four_navigation_tools` (exact-tool-count unchanged —
no new tool), and the Deep outbound-field guard all green after the SUT delta. Done-when: full
`uv run pytest -m "not integration"` green.

### T17 — Live re-measurement machinery (RED)
Add `harpyja/eval/test_submission_run.py`:
- `test_run_refuses_without_live` — `live=False` raises (0040/0041 posture).
- `test_coverage_models_consumed_from_frozen_config` — required 14b + optional 8b/4b, never re-selected.
- `test_ledger_keyed_by_submission_config_hash` — resumable ledger under `SUBMISSION_CONFIG_HASH_0044`.
- `test_startup_verifies_sut_hash_against_frozen_config` — a mismatched SUT hash is a typed STOP.
- `test_summary_joins_before_committed_table_vs_after_ledger` — BEFORE from the pinned
  attribution table, AFTER from this ledger, IDENTICAL detector both sides; per-model
  conversions/regressions/net/firing-rate + fu_before/after + coverage feed
  `decide_submission_outcome`.
- `test_summary_excludes_suspect_and_degraded_cells` (0041 boundary-granularity).
- Fails: module absent.

### T18 — Live re-measurement machinery (GREEN)
Implement `harpyja/eval/submission_run.py`: `run_submission_cells(...)` via `run_gated_pool_pilot`
(SUT-hash verify at startup, `_evict_other_models` per block, resumable) and
`build_submission_run_summary(...)` (per-model net + firing-rate, aggregate, conversions, fu,
coverage → `decide_submission_outcome`), mirroring `diagnosis_run.py`. T17 passes.

### T19 — Integration smoke (RED)
Add `harpyja/eval/test_submission_run_integration.py` (`@pytest.mark.integration`, skip-not-fail):
- `test_submission_run_smoke_gated_and_sut_verified` — under `HARPYJA_REQUIRE_LIVE_STACK`, one
  gated cell produces a verifier-PASSED artifact carrying `confidence_fired` + the 0044/1 fields.
- `test_0043_casualty_cells_enumerated` — flask-5014 (14b + 8b) and django-14315::8b are in the
  run set (the re-check targets AC7).
- Fails: driver absent. (Lives in `harpyja/eval/`, NOT `specs/` — the 0041/0042 collection-path precedent.)

### T20 — Integration smoke (GREEN)
Make the smoke skip-not-fail green (opt-in default per 0041); casualty cells enumerated. No live
spend in CI.

### T21 — Stage-2 freeze + operator driver (FREEZE/DOC)
AFTER T2/T6/T7/T9/T11 are merged (SUT byte-final) and BEFORE any live call: commit
`specs/0044-submission/submission_config/submission_config.json` (the frozen config +
`SUBMISSION_CONFIG_HASH_0044` + post-lever SUT hash), pinned by a
`test_committed_submission_config_matches_computed_truth`. Commit the STOP-AND-WARN resumable
driver `specs/0044-submission/submission_run/run_submission.py` (`_preflight()` → `/api/tags`,
`SystemExit("STOP-AND-WARN: …")`; exit 0 complete / 3 work-remaining / 2 exclusive-endpoint
contended). Done-when: config artifact + driver committed; no live spend yet.

### T22 — Gated live re-measurement (LIVE, dev Ollama)
Run the committed driver on the evicted-before / re-pinned-after 0041-gated endpoint (detach per
the long-run memory note). Produces `specs/0044-submission/submission_run/submission_results.json`
(ledger, `0041/pilot/2` exclusivity proof) + the run summary. Per-model conversions / regressions /
NET / firing-rate + fu_before/after. 8b regressions are the ship/no-ship signal.

### T23 — Typed close-out (DOC)
`specs/0044-submission/outcome.md`: the `decide_submission_outcome` label (UNDER_POWERED /
NEVER_FIRES / STILL_TRADES_OFF / NUDGE_INERT / CONDITIONED_NUDGE_SHIPS), all true conditions,
per-model firing rates, the attributable-null distribution (never-fired / fired-but-ignored /
fired-on-wrong-span). Pilot-N signal, names the next spec. Flip `status:` at close; path-pins
point at `specs/.archive/0044-submission/`.

## Risks / notes

- **Symbols-only gate may be too NARROW** (14b's located spans may come from grep/read_span, not
  symbols) → mitigation: NOT a spec change — the `NEVER_FIRES` branch (keyed to 14b) plus the
  attributable-null artifact + record-only (b)/(c) surface it and feed the next spec's gate choice.
- **SUT-hash freeze ordering** → mitigation: `compute_sut_hash` includes `confidence_gate.py`;
  hard-sequence T21 after all SUT GREENs and before T22. A `test_sut_hash_covers_confidence_gate_file`
  guards the file-list omission.
- **Dual-seam schema miss (4th recurrence risk)** → mitigation: T8/T11 written-JSON pins read the
  file back for the confidence + record-only fields at BOTH `build_trajectory_record` and
  `run_verified_case`; the standing checklist item is named here so it is not missed a 4th time.
- **Truncation dropping the nudge** → mitigation: the `confidence-nudge` record kind is never
  tombstoned by `maybe_truncate`; `test_confidence_nudge_survives_history_char_cap_truncation`
  pins the negative.
- **0029 mid-batch interleave** → mitigation: injection is strictly post-batch (after the
  tool_calls for-loop), pinned by `test_confidence_nudge_injected_only_at_post_batch_boundary_never_mid_answer_all_n`.
- **Inert-lever hole / dormant floor** → mitigation: `NUDGE_INERT` benefit conjunct + `UNDER_POWERED`
  consuming `min_covered_before_cells`, both grid-totality tested (0020/0023/0043 discipline).
- **Baseline identity** → mitigation: BEFORE pinned by path + per-source sha256; fu_before re-derived
  to 6 at test time; the `min_before_found_unsubmitted=3` floor re-checked as a guard.
- **Live contamination** → mitigation: `run_gated_pool_pilot` exclusive-endpoint hard gate (no
  bypass param), evict-before / re-pin-after; never run the suite concurrently with T22.
- **Params byte-pin** → mitigation: the delta rides `messages` ONLY;
  `test_params_pin_survives_confidence_nudge` keeps `params == {max_tokens: 2048}` (think=None) green.
