---
spec: "0048"
closed: 2026-07-17
---

# Changelog — 0048 bake-off

## What shipped vs spec

- **The full T1–T22 bake-off machinery shipped and is tested** — the frozen+hashed
  analysis contract, the pure verdict core (per-pair `b+c` via identity-reused
  `is_signal_discordant`, the four coverage/closeness outcomes, exact-McNemar +
  Holm–Bonferroni `m=3` FIXED, per-repo leave-one/leave-two-out concentration, the
  reachability split, the typed assembly over the full `RANKING` / `INTRANSITIVE` /
  `PARTIAL` / `NO_SEPARATION` / `INFRASTRUCTURE_HALTED` enum), the AC1 preflight
  (assert-local-first → positive `/api/tags` → coherence + `/v1` tool-calling →
  reproducibility replay probe), the AC2 resumable config-hash-keyed ledger + durable
  full-schema artifact, and the AC4/AC5/AC6 report assembly. 62 bake-off tests green;
  full repo 1761 passed; ruff clean.
- **MEASUREMENT, not construction:** SUT byte-untouched; the discordance/located/McNemar
  oracles are identity-reused, never re-derived. The staged detached driver +
  `run_bakeoff.sh` nohup launcher + operator CLI are turnkey.

## Deviation — the powered ranking was NOT produced

- **AC7 typed a pre-run `INFRASTRUCTURE_HALTED`, not a ranking.** The operator run was
  ATTEMPTED on the dev stack; the replay gate (0040/0041 preflight discipline + this
  spec's determinism probe) fired PRE-RUN and refused to certify the ~15h grid (wall-clock
  measured ≈350 s/case for reasoning-on `qwen3:14b`, ~1.75× the ~200 s estimate). This is
  the designed refuse-to-certify behavior, not a machinery failure — the pipeline
  (settings → gateway → explorer → verifier → bake-off artifact) validated end-to-end on
  real model output (`astropy__astropy-12907`, `qwen3:14b`, exclusive gated endpoint).
- **Honest AC status:** AC1–AC6 machinery is built and unit/integration-tested; AC7's
  typed outcome was produced and is `INFRASTRUCTURE_HALTED` (pre-run), NOT a
  `NO_SEPARATION` / model-homogeneity finding (that requires a completed powered run).

### Two blockers, both named and evidenced

- **Blocker 1 — DETERMINISM (SOLVED + validated):** the served models run non-greedy by
  default; the `qwen3:14b` double-run on `astropy-12907` gave `empty` (found-unsubmitted)
  vs `right-file-wrong-span` — a temp>0 sampling flip of the submit-vs-dawdle decision
  (the 0043 class), both runs fully validated, divergence precise not chaotic, NOT
  batching. Greedy (`temperature=0`, `top_p=1`) validated on 2 cases / 2 repos as
  bucket-reproducible. Honest caveat: greedy gives BUCKET-reproducibility, not
  bit-identical trajectories (pytest greedy took 9 vs 6 tool paths, same `empty` bucket).
  Greedy + bucket-level exclude-on-flip replay is the sound pairing. The explorer's
  outbound params are byte-pinned to `{max_tokens: 2048}` (0034/0038), so greedy MUST be a
  server-side default — the Modelfiles + README are staged in `serving/`; adopting a path
  is an operator/environment decision.
- **Blocker 2 — COVERAGE (unresolved, provisioning scripted next):** 0047's enlargement
  19→53 was authoring-time only — 34 of 53 cases have no worktree and no resolved gold.
  Only 19 are runnable (15 conceptual / 4 lexical); eligible conceptual N ≤ 15 < the
  coverage floor of 36, so every pair types `PAIR_UNDER_POWERED` — the exact 0040 stop the
  enlargement existed to escape. A powered run requires provisioning the 34 missing
  worktrees + audited gold.

### Defect surfaced by the operator probe and FIXED (measurement invariant)

- The verifier writes invoked tools into `model_turns` but left the top-level
  `tool_names_invoked` convenience field **null** despite 8 real `symbols` tool calls.
  `bakeoff_live.bakeoff_artifact_from_verifier` had trusted that field, so it would have
  recorded `symbols_adopted=False` for every cell and silently zeroed AC6's
  symbols-adoption metric — the 0042 uncounted-tool class, now its 3rd occurrence
  (0040/0042/0048). The mapper now DERIVES per-tool call counts from `model_turns`,
  cross-checked by identity against the committed `extract_tool_names` oracle;
  regression-pinned by
  `test_bakeoff_artifact_derives_tools_from_model_turns_when_field_null`.

## Files touched (all new, uncommitted; ~1375 lines prod + tests)

- `harpyja/eval/bakeoff_config.py`
- `harpyja/eval/bakeoff_analysis.py`
- `harpyja/eval/bakeoff_run.py`
- `harpyja/eval/bakeoff_driver.py`
- `harpyja/eval/bakeoff_live.py`
- `harpyja/eval/bakeoff_cli.py`
- `harpyja/eval/run_bakeoff.sh`
- `harpyja/eval/test_bakeoff_config.py`
- `harpyja/eval/test_bakeoff_analysis.py`
- `harpyja/eval/test_bakeoff_run_integration.py`
- `harpyja/eval/test_bakeoff_driver.py`
- `harpyja/eval/test_bakeoff_live.py`
- `harpyja/eval/test_bakeoff_cli.py`
- `specs/0048-bake-off/serving/` (3 greedy Modelfiles + README)
- `specs/0048-bake-off/outcome.md` (preliminary — attempt documented)
- `.speccraft/index.md` (one-line)

## Sequence to the powered run (both required, in order)

1. Greedy-serving spec — adopt a `serving/` path (PATH A: variant tags + config re-freeze,
   NOT recreate-base-tags), then pass the formal 3-case×2 replay preflight.
2. Provisioning driver — resumable, STOP-AND-WARN, audited gold, preserving the
   `385107934f61…` pool provenance; materialize the 34 missing worktrees + resolved spans.
3. Relaunch `harpyja/eval/run_bakeoff.sh` (detached, resumable, ~15h projected) and author
   the ranking from `outcome.json`.

## ADR proposed for history.md

2026-07-17 — see the prepended `## 2026-07-17 — **Spec 0048 (bake-off)…**` entry.

## Conventions proposed

- New (Measurement & eval harness): a POWERED verdict requires RUNNABLE cases, not merely
  AUTHORED ones — the 0047 correction.
- New (Trajectory-verified measurement): determinism for a single-draw stochastic
  comparison is a SERVING precondition, verified by a bucket-level replay probe — greedy
  gives bucket-reproducibility, not bit-identical trajectories.
- New (Trajectory-verified measurement): greedy is a relative-ranking CONTROL, not a
  deployment rate.
- Reinforced (Trajectory-verified measurement): the uncounted-tool class recurred a 3rd
  time — derive metrics from the authoritative trajectory (`model_turns`), never a
  convenience field.
