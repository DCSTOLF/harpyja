---
spec: "0010"
closed: 2026-06-28
---

# Changelog — 0010 SWE-bench Verified eval dataset

## What shipped vs spec

Spec 0009-6a built the eval **instrument** but shipped only a 5-case starter seed, so
every run was `indicative_only` and OQ2 was uncalibratable. This wave supplies the
real dataset adapter and the multi-repo driver the single-repo harness lacked, and
fully builds + live-validates the instrument on **real SWE-bench Verified data** — all
35 tasks complete, measurement-only / recommend-only INVARIANT (B1) preserved.

- **SWE-bench adapter (`harpyja/eval/swebench_eval.py`).** Network-staged pipeline:
  `convert` (HuggingFace) → portable committed `swebench_verified.raw.jsonl`;
  `provision` (`git clone` + worktree at `base_commit`) → gitignored
  `…resolved.jsonl`; `prune`; and the offline `run` / `sweep` subcommands that load the
  resolved fixture and drive the per-case-repo driver. `parse_patch` derives pre-image
  hunk spans (the **standalone-localization** oracle — no Docker, no patch apply, no
  test exec); `_to_eval_case` emits the real `EvalCase` shape; classification is by
  patch shape (`classify_by_patch_shape`, `POINT_SPAN_MAX_LINES=25`).
- **Per-case-repo driver `run_swebench` / `run_swebench_sweep`.** The 0009-6a harness
  was single-repo (`run_dataset(..., repo_path, stack)`); SWE-bench is one worktree per
  case, so the driver builds its **own** `LocateStack` per case (with the D-route
  classifier injected) and pools outcomes into the UNCHANGED `metrics` / `recommend`
  layers + the additively-extended report; artifacts written outside every case repo.
- **D-route intervention (resolves review B1).** Production routing keys on
  `classify_query(query)` (issue prose), uncorrelated with patch shape, so the driver
  injects a classifier returning `case.classification` through the existing
  `LocateStack.classifier` seam to force routing to the patch-shape label so the gate
  genuinely fires. The production `classify_query` label is captured BEFORE the
  override; both labels recorded per case + an aggregate `classifier_agreement_rate`;
  a SUT-observed `production_gate_ran` (from `result.tiers_run`/`notes`) is kept
  distinct from the harness Scout-probe `gate_triggered`. Surfaced loudly, never hidden.
- **OQ2 agreement guard (review round-2).** Below `AGREEMENT_FLOOR=0.5` the sweep
  recommendation is flagged `oq2_low_confidence` / `oq2_basis=deltas-only` — a relative
  ranking, never a calibration to flip a default on.
- **Additive report schema.** `SCHEMA_VERSION` bumped `0009-6a/1` → `0010/1`; six run /
  three case / one aggregate field appended-last-with-defaults in `report.py`, the
  field set + defaults centralized in `_*_DEFAULTS` (the single anti-drift source), so
  BOTH the single-run and multi-repo shapes validate. Durable metadata fields: protocol
  id, `new_file_only_excluded_count`, `malformed_skipped_count`, classifier-agreement
  rate, span-inflation tolerance, contamination caveat, dataset provenance.
- **`mode=fast` seam (R3).** `run_case` now threads `mode`; `fast` is Scout-terminal
  (Wave-5 gate informational, never escalates).
- **D-newfile + B2.** All-new-file instances (`--- /dev/null`) flagged `new_file_only`,
  EXCLUDED from scoring with a surfaced count. `base_commit` lives only in the raw JSONL
  (`provision` reads it via `_read_jsonl`); `load_dataset` ignores it.
- **Plumbing.** Root `Makefile` (`swebench-sample`/`run`/`run-fast`/`sweep`/`full`/
  `prune`, with `LM_MODEL`/`MODELFLAGS`); `uv add datasets`; `.gitignore` for
  `eval_work/` + `…resolved.jsonl`; committed `…raw.jsonl` (50 cases) + `.provenance.json`.

## Deviations

- **D-route is a recorded evaluation INTERVENTION, not pure observation.** The point
  subset no longer purely observes the production text classifier; the override swaps
  only the *input* to the unchanged routing/gate/matrix code (no SUT code touched), and
  is surfaced via the per-case labels + agreement rate + the low-confidence guard.
- **Reconciliations of the uploads.** The uploaded `_to_eval_case` emitted the wrong
  schema (`id`/expected-dict) → reconciled to `case_id`/`expected_spans`-list; the
  uploaded `Makefile.swebench` pointed at a nonexistent `python -m harpyja.eval.runner
  --fixture` CLI → reconciled to the real `swebench_eval run|sweep` subcommands.
- **CLI fix discovered in execution.** Default `Settings.lm_model="local"` is a
  llama.cpp placeholder; `run`/`sweep` gained `--lm-model`/`--lm-api-base`/
  `--deep-max-subqueries` (applied via `dataclasses.replace`) + Makefile `LM_MODEL` so
  `make swebench-run` works against Ollama.
- **Air-gap scoping (R8).** `convert`/`provision` are dev-time tools that may reach the
  network and are explicitly OUT of the runtime air-gap guarantee; `run`/`sweep` are
  offline (live integration asserts zero non-loopback egress).
- **OQ2 honest outcome.** Instrument fully built + live-validated end-to-end on REAL
  data; committed N=50 fixture clears `N_FLOOR=30`. The FULL live OQ2 sweep (all 12
  cloned repos × K) is compute-bound (hours, multi-GB) and is the documented operator
  opt-in (`make swebench-full` → `swebench-sweep`); no `Settings` default flipped (B1).
  Contamination caveat: SWE-bench is public → relative deltas, not absolute accuracy.

## Verification evidence

- **Unit:** 611 passed project-wide (+~54 new eval unit tests), ruff clean.
- **Live integration** (`test_swebench_integration.py`, 4 tests — FastContext + dspy +
  Deno + rg + Ollama `qwen2.5-coder:3b`): **4 passed in 185s** — live multi-repo driver
  e2e, zero non-loopback egress, live OQ2 sweep + agreement guard, and a real
  HuggingFace `convert` smoke (downloaded real SWE-bench Verified, mapped real patches).
- **Real convert:** `convert --sample 50 --per-repo 5` → 50 real cases, 0 malformed, 0
  new-file-excluded, 12 repos, **38 point / 12 broad** (a usable point subset — the
  all-broad risk the review caught is avoided; OQ2 is calibratable). Committed as the
  portable raw fixture (`raw_fixture_sha256` 34646c52…, HF revision 9730d2e041ee274e).
- **Real provision + run** (flask + requests, actually cloned, worktrees at
  `base_commit`, 2/2 resolved, 0 degraded): `span_hit_primary=0.5` (flask HIT in
  `src/flask/blueprints.py`; requests MISS), escalation=0.0, agreement=0.5. Both point
  cases resolved at **Tier-0** (gate did not fire) — a genuine real-data finding the
  instrument surfaced.

## ADR proposed for history.md

2026-06-28 — SWE-bench Verified eval dataset + per-case-repo driver — measurement-only,
recommend-only, live-validated on real data (prepended to `.speccraft/history.md`).

## Conventions proposed

- New: per-case-repo driver pools per-case `LocateStack`s into the unchanged
  metrics/recommend layers + an additively-extended report.
- New: an additive report field set + defaults centralized in one anti-drift source
  (`report.py` `_*_DEFAULTS`) so old and new report shapes both validate.
- New: an evaluation intervention (injecting a non-production input through a sanctioned
  seam) must be recorded loudly — both labels per case, an aggregate agreement rate, and
  an agreement-floor guard that downgrades the result to deltas-only below the floor.

## Architecture updates

- Extended the layer-9 `harpyja/eval/` entry to note the SWE-bench adapter + multi-repo
  driver (measurement, not a runtime tier).
