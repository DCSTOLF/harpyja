---
spec: "0047"
---

# Tasks

Legend: `[x]` code + tests committed & green · `[»]` machinery committed & tested,
DATA produced by the single operator run `enlargement_run/run_enlargement.sh`
(needs HF fetch + Claude/Codex; not runnable in the authoring sandbox).

- [x] T1 — [RED] enlargement config tests: raw-vs-output pin, floor reuse (benchmark_fit), conceptual-floor reuse (terse_dataset), non-round target + derivation, MAX_PER_REPO=3, stable hash (AC4)
- [x] T2 — [GREEN] implement `harpyja/eval/enlargement.py` `EnlargementConfig` + `PREREGISTERED_ENLARGEMENT_CONFIG_0047` + `ENLARGEMENT_CONFIG_HASH_0047` (AC4)
- [x] T3 — [RED] sampling-frame tests: loud schema `0047/frame/1`, source-snapshot pin, exclude pinned-50/new-file/malformed, ≤3/repo cap, deterministic by case_id (AC4)
- [x] T4 — [GREEN] implement `SamplingFrame` + `validate_sampling_frame` + `select_candidates` (reuse `is_new_file_only`/`parse_patch`) (AC4)
- [x] T5 — [RED] frozen `PowerVerdict` 5-member vocabulary + predicate order + theoretical-ceiling (=conceptual N) + POWERED/STILL_UNDER_POWERED/INSUFFICIENT_ENLARGED_COVERAGE (AC5)
- [x] T6 — [GREEN] implement `PowerVerdict` + `theoretical_discordance_ceiling` + `decide_bakeoff_power` + `decide_ab_power` (floor reuse, coverage reuse) (AC5)
- [x] T7 — [RED] expected-variance-at-N monotone; single-draw-suffices false>band / true<band → VARIANCE_REQUIRES_MULTI_DRAW (OQ2→AC)
- [x] T8 — [GREEN] implement `expected_variance_at_n` + `single_draw_suffices`; route failure to VARIANCE_REQUIRES_MULTI_DRAW (OQ2→AC)
- [x] T9 — [RED] audited-convert append integrity: existing-50 byte-identical, duplicate-case-id reject, provenance source-snapshot+new-sha chain, drift-guard reuses raw-pin (AC1)
- [x] T10 — [GREEN] implement `append_converted_cases` + `extend_provenance` + `assert_pool_append_preserves_existing_labels` in `swebench_eval.py` (reuse `_to_eval_case`/`parse_patch`) (AC1)
- [x] T11 — [OP] RAN: audited convert enlarged raw 50→123 (≤8/repo, 73 new); content-guard confirmed pinned-50 byte-identical (benign HF fingerprint change recorded); provenance chained. `sampling_frame.json` frozen; pipeline unit-tested incl. snapshot-drift StopAndWarn (AC1)
- [x] T12 — [RED+GREEN] `enlargement_authoring.assemble_enlarged_authoring_artifact` — appends records, existing prefix byte-identical drift-guard, additive `blind_ineligible_count`, validates loud at `0026/1`; `author_enlarged_set` counts leaky + blind-ineligible (AC2)
- [x] T13 — [OP] RAN: blind-authored via 0036 `author_terse_set` (author=Codex, verifier=Claude, backends enforced ≠ + preflighted); 22 blind-ineligible + 17 leaky-dropped RECORDED, 34 kept; per-case ledger (lossless resume unit-tested) (AC2)
- [x] T14 — [RED+GREEN] loud rejection of an untagged enlarged `0036/1` row (existing loud loader) + `assemble_enlarged_terse` existing-19 drift-guard + dedup; deterministic `tag_enlarged_row` reachability; stratum computed in `_phase_recheck` (AC3)
- [x] T15 — [OP] RAN: DETERMINISTIC reachability (44 conceptual / 9 lexical) — the load-bearing axis; concept-vs-patch tagged CONSERVATIVE `same` (audit caught + fixed a fabricated-`concept_span` bug: `divergent` without a repo-verified distinct span is unsubstantiable); enlarged terse committed (existing 19 preserved byte-identical), 20-case `audit_sample.json` emitted (AC3)
- [x] T16 — [RED] `power_recheck.json` round-trips compute→validate; archive-first loader; loud validate (off-enum verdict / unknown schema rejected) (AC5)
- [x] T17 — [GREEN] `PowerRecheckResult` + `validate_power_recheck` + `load_committed_power_recheck` (`0047/power/1`); `_phase_recheck` emits the machine-readable per-question/per-pair verdict + stratum + attrition (AC5)
- [x] T18 — [DOC] `findings.md` filled from the run: all 5 questions `POWERED` (theoretical ceiling clears at N=44; the 0039/0040 stops lifted for feasibility), empirical discordance deferred to the bake-off, tag-quality + concept-vs-patch limitation documented (AC6)
- [x] T20 — [OP-FIX] additions surfaced by the run: content-identity source-snapshot guard (replacing the brittle arrow-fingerprint gate); backend-selectable arms (`enlargement_arms`, author≠verifier + preflight); `≤3→≤8/repo` config RE-FREEZE (OQ3, hash `819af2e6…`); pre-enlargement 19-case snapshot committed + 0036/0039 historical drift-guards redirected to it (live pool grows, history preserved)
- [x] T19 — [REFACTOR] DECLINED deeper fold with reason: the theoretical-ceiling re-check must NOT reuse `pool_precheck.union_located_ceiling`/`observed_discordance` (those consume located sets — the empirical bake-off this spec avoids); the floor + named pairs ARE reused by identity, pinned by `test_power_recheck_reuses_pool_pairs_and_floor_by_identity`
