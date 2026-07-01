# Spec 0015 — OQ2 — changelog

Status: **CLOSED — run failed.** The OQ2 measurement did not produce a
recommendation. This spec is closed for its **findings**, not its deliverable.

## Outcome

The live `mode=auto` OQ2 sweep over the 12-repo subset **could not be completed**.
The eval instrument built for this spec was **reverted**; only one incidental bug
fix was salvaged. The value of this spec is the set of defects it surfaced (below),
which seed follow-up specs.

## What shipped (salvaged)

- **B0 — provision worktree-path fix** (`swebench_eval.py::cmd_provision`:
  `Path(args.work_dir).resolve()`) + regression test
  `test_swebench_eval.py::test_provision_relative_work_dir_resolves_to_real_worktrees`.
  Fixes: a relative `--work-dir` made `git worktree add` (cwd=<clone>) create trees
  under the clone while the fixture recorded `wt.resolve()` → every resolved repo
  path 404'd. This is the ONLY code change retained.

## What was reverted

All OQ2 measurement machinery (typed-outcome enum + precedence, per-point degrade
gate, gate-confound threshold, report schema bump `0013/1→0014/1` +
`combined_degrade_rate`, sweep provenance, sibling-driver wiring, `run_oq2_sweep`
entrypoint, `make oq2-full`, and their tests). Reverted to `HEAD` (7aedad8). Rationale:
the run never produced usable output, and the machinery is not worth carrying
un-exercised; it will be re-derived once the blockers below are fixed.

## Why the run failed — findings (seed new specs)

Detail, evidence, and proposed fix/test loci: `live-run-findings.md`.

- **B0** — provision worktree path (FIXED here + test).
- **B1** — default `scout_model` is an unserved model (`mitkox/…RL-Q4_K_M` → HTTP 404);
  no `--scout-model` CLI flag to override. Out-of-box eval 404s on every case.
- **B2** — verification gate reuses the FastContext citation-*finder* model as a
  relevance *judge* → rejects CORRECT citations (astropy-12907 cited the right file,
  got `gate-low-confidence`); `_parse_score` grabs the first number in the reply.
  (This is the AC4 gate-false-escalation phenomenon itself — its fix was always a
  separate gate-quality spec.)
- **B3** — model gateway `urlopen` has no HTTP timeout → a stalled/torn-down Ollama
  connection wedges the whole run indefinitely (observed: 2.5 h, 0% CPU, `caffeinate`
  on). Related: `run_swebench`'s `ThreadPoolExecutor(max_workers=1)` per-case timeout
  can't kill the blocked worker, so cases deadlock behind it. This is why no full run
  completed.

## Verified NOT bugs (do not re-chase)

- `parse_final_answer` parses real Q8-RL output correctly (3 citations from a real
  astropy answer).
- Suffix recovery is wired (`scout/wiring.py:46` loads `file_set` from the manifest)
  and works on the model's out-of-repo absolute paths.

## AC status

- AC1 (runs mode=auto to completion, no crash): **partially proven** (3-case smoke)
  — but the full N=50 run could not complete (B3).
- AC2–AC7 (trade-off table, degrade/gate metrics, recommendation): **NOT delivered**
  (machinery reverted; run blocked by B1–B3).
- AC8 (defect surfaced at scale gets a regression test): **honored for B0**;
  B1/B3 fixes deferred to follow-up specs (recorded with proposed test loci).

## Next

New specs (per the user) to fix B1, B2, B3; then a fresh spec to re-attempt the OQ2
measurement once the stack can run to completion.
