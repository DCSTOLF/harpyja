---
spec: "0049"
---

# Tasks

- [x] T1 — [unit][AC1] RED: commit `serving/Modelfile.*` (reduced to temperature-only per operator decision) + `test_greedy_serving.py` fingerprint-parser tests (from/params/template/system, sorted map, dup-key reject, out-of-set reject, normalization, temp=0)
- [x] T2 — [unit][AC1] GREEN: `harpyja/eval/greedy_serving.py` — `parse_modelfile_fingerprint`, `ModelfileFingerprint`, `fingerprint_digest`, `ModelfileGrammarError`
- [x] T3 — [unit][AC1] RED: build-driver tests (noop-on-match, stop-and-warn-on-mismatch, create-from-committed-when-absent, assert-local-first, sanitized-env OLLAMA_HOST, live-modelfile reader)
- [x] T4 — [unit][AC1] GREEN: `build_greedy_variant`, `GreedyBuildOutcome`, `read_live_modelfile`, `local_ollama_env`
- [x] T5 — [unit][AC4] RED: generation-pins-diff + `fingerprint_delta` tests (exactly-temperature, added-temperature, from-excluded, other-key-fails, template-change-fails, identical-fails)
- [x] T6 — [unit][AC4] GREEN: `fingerprint_delta`, `ParamDelta`, `is_exactly_temperature_delta`
- [x] T7 — [unit][AC2] RED: `test_bakeoff_config_served_variants.py` (pin 3 greedy tags, path-A exclusion, field-default introspection, committed-fingerprint chain-of-custody, known-value hash, tag-drift hash change, resolver mapping, ast single-consumer guard)
- [x] T8 — [unit][AC2] GREEN: `BakeoffConfig.served_variant_tags` + `served_variant_fingerprints`, `SERVED_VARIANT_CONFIG_HASH`, `resolve_served_model`; verified full bakeoff suite (50) green after hash shift — no committed literal pins old 0048 hash
- [x] T9 — [unit][AC5/AC6] RED: `test_greedy_replay_proof.py` (≥3-draw floor, reproduce-on-identical, flip-on-divergence, bucket-not-tool-path, LocateBucket identity-reuse, outcome-requires-every-cell, any-flip→residual, artifact schema + exclusivity, drift-pin)
- [x] T10 — [unit][AC5/AC6] GREEN: `greedy_replay.py` — `greedy_replay_proof`, `GreedyServingOutcome`, `ReplayCell`, `build_greedy_replay_artifact`, `GREEDY_REPLAY_ARTIFACT_KEYS`
- [x] T11 — [unit][AC3] RED: `test_greedy_membership.py` (iterates variant-tags-not-model-tags, assert-local-first, empty-served-set→all-false)
- [x] T12 — [unit][AC3] GREEN: generalize `probe_served_membership` (`tags=` kwarg) + `probe_served_variant_membership`
- [x] T13 — [integration][AC1a/AC3/AC4a] `test_greedy_serving_live.py` — all 4 live tests PASS on the rebuilt tags (env-sanitization, `/api/tags` membership, 14b-anchor exactly-temperature, base-diff exactly-temperature for all 3 pairs). AC1a first surfaced the 0048 divergence, then RESOLVED it (deleted + rebuilt all 3 from committed Modelfiles, each verified exactly-temperature).
- [x] T13b — [AC5 OPERATOR RUN] ≥3-draw × 3-tag × 2-case/2-repo replay, exclusivity-clean per tag block. Committed drift-pinned `specs/0049-serving/replay_proof.json` (sha256 4bfe8679…). Confirmatory seed-pin diagnostic run (0048 config) → REFUTES the seed/top_p hypothesis.
- [x] T14 — [doc][AC6] `findings.md` — typed outcome **`RESIDUAL_NONDETERMINISM`** (all 3 tags flip; source named = serving-stack numerical nondeterminism, seed-pin refuted; bake-off BLOCKED) + AC1a resolution + caveats + greedy fu (OQ3, now a variable outcome); routed to MEMORY (`greedy-serving-variant-tags`)
- [x] T15 — REFACTOR: `local_ollama_env(host)` is the single shared provisioning-egress seam (used by `build_greedy_variant` + `read_live_modelfile`); all tests green

## Reference paths
- Spec: `specs/0049-serving/spec.md`
- New module: `harpyja/eval/greedy_serving.py`
- Config to re-freeze: `harpyja/eval/bakeoff_config.py` (`bakeoff_config_hash` = `sha256("|".join(f"{k}={v}" for k,v in sorted(dataclasses.asdict(cfg).items())))`; new frozen fields flow in automatically)
- Probe to generalize: `harpyja/eval/bakeoff_run.py` (`probe_served_membership` line ~109, returns `{tag: tag in served for tag in cfg.model_tags}` — redirect to `served_variant_tags`)
- Reused oracle (DO NOT modify): `harpyja/eval/locate_accuracy.py` (`LocateBucket`)
- Modelfiles to copy: `specs/.archive/0048-bake-off/serving/` → committed `serving/`
- New tests (all under `harpyja/eval/`): `test_greedy_serving.py`, `test_bakeoff_config_served_variants.py`, `test_greedy_replay_proof.py`, `test_greedy_membership.py`, `test_greedy_serving_live.py`
- Findings: `specs/0049-serving/findings.md`
