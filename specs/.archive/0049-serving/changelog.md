---
spec: "0049"
closed: 2026-07-17
---

# Changelog — 0049 serving (greedy serving, path A)

## What shipped vs spec

- **All 6 ACs met at the level each specifies** (AC1/AC2/AC4 unit; AC1a/AC3/AC4a/AC5
  live-integration on the 0041-gated dev Ollama, exclusivity-clean; AC6 doc/typed).
  43 unit tests + 4 live integration tests green; ruff clean; full suite **1804 passed**.
- **PATH A machinery built end-to-end and is REUSABLE** even though the outcome is
  negative: the deterministic Modelfile fingerprint parser + tolerant live-param
  extractor + idempotent STOP-AND-WARN build driver (`greedy_serving.py`), the
  ≥3-draw bucket-keyed replay proof (`greedy_replay.py`,
  `greedy_replay_proof`/`GreedyServingOutcome`/`build_greedy_replay_artifact`), the
  re-frozen `BakeoffConfig` (`served_variant_tags` + committed
  `served_variant_fingerprints` + `SERVED_VARIANT_CONFIG_HASH` + `resolve_served_model`),
  and the three temperature-only Modelfiles all ship and are pinned.
- **AC6 typed outcome: `RESIDUAL_NONDETERMINISM`** (the headline — see below). Greedy
  is NOT the standing measurement config; the bake-off stays BLOCKED.

## The outcome (AC6 negative branch, decisively proven)

- The AC5 operator replay (≥3-draw × 3-tag × 2-case/2-repo, live, 0041-gated,
  exclusivity-clean per tag block) shows **all three greedy tags flip a bucket within a
  cell**: 14b flips django (`correct, correct, empty`), 8b flips astropy
  (`empty, empty, RFWS`), 4b flips django (`correct, correct, empty`). Clean runs, no
  degrades (`degrade=None`) — different buckets, not wall-clock artifacts.
- **Named source (AC6 requires it): serving-stack decoding numerical nondeterminism,
  NOT sampling.** Mechanism (visible in `submission_outcome`): at temperature 0 the same
  (model, case) flips its terminal submit-vs-find decision across draws.
- **Seed-pin REFUTATION (load-bearing):** a diagnostic tag rebuilt with 0048's exact
  config (temp 0 + top_p 1 + seed 0) re-run on the flipping cell (14b/django, 3 draws)
  produced the SAME flip (`correct, correct, empty`) — so seed/top_p pinning does NOT
  restore reproduction; the source is deeper (Ollama/llama.cpp batch/KV-cache), not the
  temperature-only Modelfile's dropped seed/top_p.
- **Consequence for 0048:** its "greedy reproduces" (2 cases) was a stable-cell
  coincidence — those cases sit off the submit/find decision boundary. The ≥3-draw ×
  per-tag discipline (0049's tightening over 0048's 2-draw) caught what 2 draws by
  construction could not: a 2-draw proof would have FALSELY passed 14b/django
  (correct==correct) and 8b/astropy (empty==empty); the third draw flipped both.
- **The bake-off stays BLOCKED** and is not fixable by a serving-config tweak. Paths
  forward (own spec): a genuinely deterministic backend (batch-invariant kernels /
  serialized requests / a different runtime) OR abandon single-draw for multi-draw
  majority-bucket.

## Files touched

- New: `harpyja/eval/greedy_serving.py`, `harpyja/eval/greedy_replay.py`,
  5 `test_*` files, `serving/Modelfile.{qwen3-14b,qwen3-8b,qwen3.5-4b}` (temperature-only),
  `specs/0049-serving/findings.md`, `specs/0049-serving/replay_proof.json`
  (drift-pinned `sha256 4bfe8679…`, config hash `82885d1b…`).
- Modified: `harpyja/eval/bakeoff_config.py` (frozen `served_variant_tags` + committed
  `served_variant_fingerprints` + `SERVED_VARIANT_CONFIG_HASH` + `resolve_served_model`;
  the k=v `bakeoff_config_hash` shape absorbed the new fields, `BAKEOFF_CONFIG_HASH_0048`
  derived+shifted safely, no on-disk literal pinned it), `harpyja/eval/bakeoff_run.py`
  (`probe_served_membership` backward-compatible `tags=` kwarg + `probe_served_variant_membership`).

## Deviations from spec/plan

- **Temperature-only Modelfiles** (operator decision): reduced from 0048's
  `temperature 0 / top_p 1 / seed 0`. At temperature 0 the decoder is argmax so top_p/seed
  are inert; keeping them made the greedy-vs-base delta three keys wide and failed AC4a
  ("exactly temperature"). The seed-pin refutation confirms this reduction did NOT cause
  the residual nondeterminism.
- **AC1a caught a real chain-of-custody divergence:** 0048's hand-created
  `qwen3-14b-greedy` kept top_p 1 + seed 0 (`delta = {seed, temperature, top_p}` vs base)
  → STOP-AND-WARN → 0048's draws DISCARDED; all three tags rebuilt from committed
  Modelfiles and verified exactly-temperature before the replay ran (fresh draws).
- **Seed-pin refutation experiment run beyond the plan** — an added diagnostic tag to
  test whether the dropped seed/top_p were load-bearing (they were not).
- **The AC5 live replay was run IN-SESSION** rather than deferred to a separate operator
  run.
- **A 4b/astropy backend-error redraw** occurred during the live run.
