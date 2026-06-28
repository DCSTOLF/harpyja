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
  `base_commit`, 2/2 resolved): `span_hit_primary=0.5` (flask HIT in
  `src/flask/blueprints.py`; requests MISS), escalation=0.0, agreement=0.5. Both point
  cases terminated at **Tier-0** — but **NOT** because the cheap tier sufficed or the
  gate was lax. The per-case `notes` are `scout-degraded:backend-error`: **FastContext
  Scout crashed on every real-SWE-bench query** (its own `format_citations`,
  `fastcontext/agent/utils.py:96`, does `c["path"]` on a string → `TypeError` →
  `ScoutUnavailable: backend-error` → Tier-0 degrade — the exact spec-0007 AC10
  third-party post-processing crash). So Tier-1/gate/escalation were **upstream-starved**:
  the gate never had output to score, and the 0.5 span-hit is the **Tier-0 degrade-floor
  accuracy**, not an escalation-skip finding. The instrument did its job — it surfaced a
  real Scout/FastContext robustness defect on real data, not a gate-tuning signal. (An
  earlier draft of this note mis-read it as "gate did not fire"; corrected per
  no-false-capability.) **Follow-up:** make FastContext's `format_citations` robust to
  string-shaped citations (or pin/patch upstream) before any Tier-1/gate/OQ2 measurement
  on real SWE-bench is meaningful — until then Scout is non-functional on this dataset
  and OQ2 cannot be calibrated from it regardless of N.
- **Tier-0-in-isolation on the point subset (N=12, real cloned flask/requests/pylint/sphinx):**
  follow-up measurement requested to disambiguate "cheapest-tier-works" from "Tier-0
  misfiring." Result: **12/12 `scout-degraded:backend-error`** (Scout failure is
  *systematic* on real data, not sporadic), escalation_rate **0.0**, terminal_tier 0 for
  all. **Tier-0 span-hit = 2/12 = 0.167** (primary == secondary: the 10 misses get the
  wrong *file*, not just the wrong lines). Verdict: this is the **low-accuracy +
  high-escalation-skip** quadrant — i.e. retrieval would benefit from escalation — but the
  cause is **not** lax gate triggers; the gate is *upstream-starved* by the Scout crash, so
  the ladder above Tier-0 is entirely unavailable and bare keyword Tier-0 (16.7%) is what's
  actually running. Two real defects surfaced: (1) **harden FastContext Scout** on real
  data (top priority — the whole NL ladder is dead), then (2) re-measure the gate, which
  cannot be assessed until Scout yields output. Bare Tier-0's 16.7% confirms the
  Scout→gate→Deep ladder is load-bearing on real NL queries, not redundant.

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
