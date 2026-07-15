---
spec: "0047"
closed: 2026-07-14
---

# Changelog — 0047 enlargement

## What shipped vs spec

- **The audited convert unblocks the backlog.** The blind-clean pool grew **19 → 53**
  (conceptual stratum **15 → 44**, lexical 4 → 9; raw fixture **50 → 123**) with the
  provenance chain preserved (raw sha `34646c52…` → `385107934f61`,
  `prior_raw_fixture_sha256` kept). All 5 downstream questions — the 3 bake-off pairs
  (0040), the 0039 A/B feasibility, and the 0046 policy-baseline variance — type
  **`POWERED`** on the THEORETICAL discordance ceiling at **N=44**, lifting the
  0039/0040 feasibility stops.
- **Honest framing (as scoped):** `POWERED` = "now worth running," NOT "will resolve."
  The concrete wins are **variance headroom** (53 cells vs the 33 that produced 0046's
  instrument-noise finding) and **coverage** for the bake-off. EMPIRICAL discordance —
  the nested-sets question (did enlargement add *discordant* cells or merely concordant
  ones) — is `DISCORDANCE_STILL_INSUFFICIENT` in the frozen vocabulary and is **DEFERRED
  to the bake-off**, never asserted here. This spec proves NECESSITY (the N-blocker is
  removed), not SUFFICIENCY.
- **New owning module `harpyja/eval/enlargement.py`** (measurement machinery + data, NO
  SUT change, no live model run anywhere): frozen+hashed `EnlargementConfig`
  (`ENLARGEMENT_CONFIG_HASH_0047 = 819af2e6…`) implementing **Decision A** — the RAW
  convert count is pinned upfront (`raw_convert_target`), the blind-clean OUTPUT floats
  with measured attrition; the discordance floor is copied by identity from
  `benchmark_fit.PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS` and the conceptual floor from
  `terse_dataset._CONCEPTUAL_FLOOR_FULL`. `SamplingFrame` (`0047/frame/1`) +
  `select_candidates` (pinned-50 exclusion, ≤`max_per_repo` cap, deterministic by
  `case_id`). **Decision B** — a five-member frozen `PowerVerdict` (`POWERED` /
  `STILL_UNDER_POWERED` / `DISCORDANCE_STILL_INSUFFICIENT` /
  `INSUFFICIENT_ENLARGED_COVERAGE` / `VARIANCE_REQUIRES_MULTI_DRAW`) committed BEFORE the
  numbers; `theoretical_discordance_ceiling(conceptual_n) = conceptual_n` (tag-count-only,
  no located sets — the AC6 scope fix); `expected_variance_at_n` / `single_draw_suffices`
  (OQ2→AC); `PowerRecheckResult` (`0047/power/1`) compute / validate / archive-first-load.
- **`swebench_eval.py` audited-convert append:** `append_converted_cases` (dup-`case_id`
  reject), `line_sha_map`, `assert_pool_append_preserves_existing_labels` (byte-identical
  drift-guard proving the original 50 unchanged), `extend_provenance` (prior sha preserved).
- **`enlargement_authoring.py`:** `is_blind_ineligible` + `author_enlarged_set` (reuses
  0036 `author_terse_set` VERBATIM; counts blind-ineligible + leaky, never silent-drops);
  `assemble_enlarged_authoring_artifact` (existing-36 prefix byte-identical drift-guard,
  additive `blind_ineligible_count`, validates loud at `0026/1`); `tag_enlarged_row`
  (deterministic reachability); `assemble_enlarged_terse` (existing-19 drift-guard);
  `audit_sample`.
- **`enlargement_run.py`:** a resumable, ledger-backed pipeline (convert → author → tag →
  assemble → recheck) with every out-of-process arm INJECTED; lossless-resume unit-tested.
  Thin real-model entrypoint at `specs/0047-enlargement/enlargement_run/run_enlargement.py`
  + `run_enlargement.sh` (the one operator command, detached, resumable).
- **`enlargement_arms.py`:** backend-selectable arms (`claude` | `codex`), author ≠
  verifier enforced STRUCTURALLY, `preflight_arm` fast check.

## AC status

- **AC1 (append integrity, no re-derivation)** — met. New labels sha256-pinned +
  provenance-chained; the existing 19 terse / 50 raw / 36 authoring records proven
  byte-identical; duplicates rejected loudly.
- **AC2 (blind-authoring provenance + attrition recorded)** — met. Author=Codex,
  verifier=Claude (backends enforced ≠ + preflighted); **22 blind-ineligible + 17
  leaky-dropped RECORDED, 34 kept.**
- **AC3 (tags mandatory, missing rejected, stratum reported)** — met. DETERMINISTIC
  reachability (44 conceptual / 9 lexical); concept-vs-patch tagged CONSERVATIVE `same`
  (see deviation 3); an untagged `0036/1` row is rejected by the loud loader.
- **AC4 (target-N arithmetic pinned, raw-vs-output)** — met. `raw_convert_target` frozen
  in the hashed config with `*_derivation` strings; OUTPUT floats; non-round; ≤/repo cap
  first-class (re-frozen to 8, see deviation 2).
- **AC5 (re-run 0040/0039 power, typed per question/pair)** — met. `power_recheck.json`
  (`0047/power/1`) types all 5 questions `POWERED`, pinned to computed truth.
- **AC6 [doc] (nested-sets re-check, theoretical-ceiling only)** — met.
  `findings.md`: N-blocker removed on the theoretical axis; empirical discordance deferred.

All 20 tasks `[x]`; 854 eval tests pass, 58 deselected, ruff clean.

## Files touched

- `harpyja/eval/enlargement.py` (new), `enlargement_arms.py` (new),
  `enlargement_authoring.py` (new), `enlargement_run.py` (new) + sibling `test_*.py`
- `harpyja/eval/swebench_eval.py` (audited-convert append + integrity)
- `harpyja/eval/fixtures/swebench_verified.raw.jsonl` (50 → 123),
  `swebench_verified.terse.jsonl` (19 → 53), `swebench_verified.authoring.json` (+records),
  `swebench_verified.provenance.json` (chained sha + source-fingerprint provenance)
- Redirected historical drift-guards → the pinned pre-enlargement snapshot:
  `harpyja/eval/test_terse_floor.py`, `test_think_ab_precheck.py`, `test_think_ab_claim.py`,
  and `specs/0047-enlargement/pre_enlargement_terse_snapshot.jsonl` (new)
- `specs/0047-enlargement/power_recheck.json`, `sampling_frame.json`, `audit_sample.json`,
  `enlargement_run/` (operator entrypoint + ledger)

## Deviations (each discovered by RUNNING it — the run was the verification)

1. **Content-identity source-snapshot guard REPLACED a brittle arrow-fingerprint gate.**
   HF `_fingerprint` changes across datasets-lib / cache state even for identical content
   (it is NOT the HF content revision; the original convert mislabeled it `hf_revision`).
   The gate now re-derives each pinned-50 case from the fresh snapshot and asserts
   byte-identical to the committed fixture (StopAndWarn on real drift / a missing pinned
   case); the fingerprint is recorded as informational provenance
   (`source_fingerprint_observed` `1fdfd21ba2621130` / `source_fingerprint_frozen`
   `9730d2e041ee274e`). Strictly STRONGER than the fingerprint check.
2. **≤3/repo → ≤8/repo config RE-FREEZE (OQ3, forced by convert data).**
   SWE-bench_Verified has only **12 repos**, so ≤3/repo hard-ceilings new raw at 12×3=36
   (the convert discarded 420 cases → 30, below the need). ≤8/repo (12×8=96 = the derived
   raw need, crediting the existing 15 conceptual) is the MINIMAL relaxation making the
   40-conceptual target attainable without leaving the benchmark. Re-freeze recorded via
   `max_per_repo_derivation`, new hash `819af2e6…`; deepens per-repo coverage (accepted
   overfit risk); broadening to new repos is deferred (the homogeneity axis, a distinct
   spec). OQ3 marked RESOLVED.
3. **Concept-vs-patch tagging bug caught BY THE 20-CASE AUDIT and fixed.** The driver
   fabricated `concept_span = gold` for every "divergent" verdict — a self-contradiction
   (concept == patch IS "same"). Corrected deterministically (fabricated-divergent → same;
   the model's opinion kept as advisory), the driver patched to tag the substantiable
   "same" default. The REACHABILITY axis (the load-bearing `RETRIEVAL_FUNDAMENTAL`
   confound guard, 44/9, deterministic) was always correct. Divergent-detection at scale
   needs a repo-aware concept-span pass — a documented limitation / candidate follow-up.
4. **Enlarging the SHARED terse fixture broke 3 downstream drift-guards** that pin
   0036/0039's historical claims by recomputing from the (now-enlarged) live fixture.
   Resolved by committing a pre-enlargement 19-case snapshot
   (`specs/0047-enlargement/pre_enlargement_terse_snapshot.jsonl`) and REDIRECTING the
   historical tests to it via the pure `ab_power_precheck` core — zero touch to 0039's
   live loaders; history preserved EXACTLY, live pool free to grow.
5. **Attrition (of ~73 raw sourced under ≤8/repo):** 22 blind-ineligible (issue named the
   gold path — 0036's ~28% class held), 17 leaky-dropped, 34 kept. Run: author=Codex,
   verifier=Claude (backends enforced ≠ + preflighted).

## ADR proposed for history.md

Prepended (newest-first) — see `.speccraft/history.md` 2026-07-14 (spec 0047).

## Conventions proposed (applied)

- (a) **Content-identity (not fingerprint) source-snapshot pinning for HF-derived
  fixtures.** — Measurement & eval harness.
- (b) **Enlarging a shared committed fixture: snapshot the prior state and redirect the
  historical drift-guards to it via the pure cores (never rewrite the historical claim).**
- (c) **Audit-the-sample discipline: a plausible model label + fabricating code can
  bypass schema guards — eyeball a sample.**
- (d) **A frozen-config RE-FREEZE with a recorded derivation is legitimate when the
  instrument structurally cannot reach the target (not steering).**

## Next spec (unblocked, not run)

The bake-off (0040), the 0039 thinking A/B, and the 0046 policy re-measurement are now
POWERED for feasibility. The bake-off is the one that ANSWERS the empirical discordance
question (`DISCORDANCE_STILL_INSUFFICIENT` vs a real signal) — model homogeneity, not
data volume, is the remaining risk this spec deliberately did not resolve.
