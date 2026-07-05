---
spec: "0022"
closed: 2026-07-05
---

# Changelog — 0022 Tier-1 (Scout locate-accuracy diagnosis on SWE-bench)

## What shipped vs spec

- A **Scout locate-accuracy diagnostic instrument** (diagnosis-not-fix, in the
  0019/0020/0021 measurement-not-construction lineage), complete and unit-verified,
  plus a **live end-to-end fixture smoke** and a **provisional typed finding**
  (`RETRIEVAL_FUNDAMENTAL`). All additive under `harpyja/eval/`; the SUT
  (`harpyja/scout/`, `harpyja/orchestrator/`) is byte-frozen.
- `locate_accuracy.py` — a pure eval-side projection ABOVE the frozen oracle
  (`metrics.span_hit_kind` / `span_hit_secondary`): `normalize_citations` (reads
  spec-0012 `ScoutTally` recovery counts, never re-derives suffix recovery) →
  `NormalizedCitations`; a 4-way `LocateBucket` enum `{EMPTY, WRONG_FILE,
  RIGHT_FILE_WRONG_SPAN, CORRECT}` with strict precedence `CORRECT >
  RIGHT_FILE_WRONG_SPAN > WRONG_FILE > EMPTY`; `classify_case` carrying the ONE
  deliberate scored re-map (path-only right-file `span_hit_kind=="file"` →
  `RIGHT_FILE_WRONG_SPAN`, NOT `CORRECT` — the file-vs-span diagnostic axis, living
  only in eval); `score_distribution` → `LocateDistribution` with file-level acc,
  span-level acc, and first-class `gap = file − span`; `decide_finding` — an ordered
  4-branch rule (`BENCHMARK_UNREPRESENTATIVE > PRECISION_FIXABLE >
  RETRIEVAL_FUNDAMENTAL > MIXED`) over pre-declared named bands; a `SUT_SURFACE`
  frozenset allowlist + a frozen-oracle behavior-snapshot test (AC10 guard).
- `locate_probe.py` — a Scout-ONLY driver (no gate / judge / Deep): `stratify_cases`
  (repo × gold-span-size band), `run_locate_probe` (drives `scout_engine.search`
  only, resets `last_tally` per case, regenerates the distribution — does NOT inherit
  0021's contaminated counts), `run_reformulation_probe` (raw-vs-distilled empty-rate
  delta, held OUT of the baseline), the turns-used machinery, and the fail-posture
  gate.
- Turns-used via the **public `agent_factory` seam** (AC5): `count_turns(trajectory)`
  (pure JSONL step-counter; malformed/absent → `None`), `counting_agent_factory`
  (wraps the REAL `make_fastcontext_agent`, reads the trajectory BEFORE the frozen
  client's `os.unlink` cleanup), `build_scout_only_stack`.
  `turns_used_source ∈ {"trajectory","unavailable"}` — a labeled estimate, never
  fabricated. Corrects a planner overstatement: turns ARE tracked (trajectory) but
  discarded by the frozen client; recoverable via the injection seam.
- Fail posture: `require_live_stack(available, env)` → `"proceed"/"skip"/"fail"`
  (pytest-free, unit-testable); `HARPYJA_REQUIRE_LIVE_STACK=1` converts the
  integration skip into a hard fail for the closure run.

## Deviations (recorded honestly)

- **`scout_stack_available()` (instrument-hardening deviation).** The Scout-only
  integration tests initially reused the Deep-oriented `_live_stack_available`, which
  requires Deno (Tier-2) + the Deep model — both irrelevant to a Scout probe — and
  **false-skipped** a Scout-capable host. Added a Scout-scoped predicate (fastcontext
  + `rg` + a reachable Scout endpoint; no Deno). The 4 integration tests now RUN LIVE
  here rather than skipping.
- **Provisional finding, one branch not yet excludable.** The finding is
  `RETRIEVAL_FUNDAMENTAL`, but `BENCHMARK_UNREPRESENTATIVE` is NOT excludable — its
  discriminator (the reformulation probe on REAL multi-paragraph SWE-bench issue text)
  is operator-gated; on the terse fixture queries `delta_empty ≈ 0` by construction.
  The real 38-case SWE-bench distribution is likewise operator-gated. Honest close per
  the 0019/0020 lineage: instrument shipped + live-fixture-verified + carried-forward
  prior; the real operator measurement is a named follow-up.

## Files touched (all additive; SUT byte-frozen)

- `harpyja/eval/locate_accuracy.py` (new)
- `harpyja/eval/locate_probe.py` (new)
- `harpyja/eval/test_locate_accuracy.py` (new)
- `harpyja/eval/test_locate_probe.py` (new)
- `harpyja/eval/test_locate_probe_integration.py` (new)
- `specs/0022-tier-1/{spec,plan,tasks,findings}.md`

## Verify

- 883 unit passed (835 baseline → +48), ruff clean. 4 integration tests PASS LIVE
  (real Scout, ~44s), not skip.
- Live fixture smoke (N=5 legacy seed, real FastContext Q8 Scout on Ollama):
  `CORRECT=1, EMPTY=4, F=0.20, S=0.20, gap=0.00, empty_rate=0.80`.
  `turns_used_source="trajectory"`, turns `(5,5,7,3,5)`. `decide_finding` →
  `RETRIEVAL_FUNDAMENTAL`, matching the pre-registered 0020/0021 prior.
