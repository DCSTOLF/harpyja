---
spec: "0023"
closed: 2026-07-05
---

# Changelog — 0023 benchmark-fit: reformulation probe + representativeness verdict

## What shipped vs spec

- Built the **typed, two-axis, pre-registered benchmark-fit discriminator** that decides
  whether 0022's provisional `RETRIEVAL_FUNDAMENTAL` is a real capability wall or a
  `BENCHMARK_UNREPRESENTATIVE` artifact. All ACs met. A MEASUREMENT/eval diagnostic in
  the 0019/0020/0021/0022 measurement-not-construction lineage: SUT (`harpyja/scout/`,
  `harpyja/orchestrator/`) **byte-frozen**, all code additive under `harpyja/eval/`.
- **`benchmark_fit.py` (new):** exact two-sided McNemar from scratch (`math.comb`,
  no scipy; boundary-pinned 6/0→0.03125 rejects, 5/0→0.0625 not, 8/0→0.0078125 rejects,
  7/1→0.0703125 not); frozen `PREREGISTERED_CONFIG` (`MIN_DISCORDANT_PAIRS=8` derived
  from exact-McNemar reachability, `DELTA_EMPTY_BAND=0.20`, `min_n=12`, `alpha=0.05`);
  `PairedRow` + `aggregate_paired` (within-case deltas; discordant `(b,c)` FROM retained
  pairs, never a difference of aggregate rates); total `decide_axis1` with a paired
  uncertainty gate and THREE named non-overlapping `INCONCLUSIVE` triggers
  (`INSUFFICIENT_POWER` / `DISTILLER_ARM_DISAGREEMENT` / `AXIS_SIGNAL_DISAGREEMENT`);
  `RepresentativenessRecord` + `is_representative` (Axis 2); total `compose_verdict`
  encoding a pre-registered 2×2 where Axis 2 can downgrade Axis 1's routing.
- **`distill.py` (new):** a DUAL distiller with asymmetric roles. `mechanical_distill`
  is PRIMARY/verdict-driving — a single case-agnostic rule whose output tokens are a
  SUBSET of the raw-issue tokens (extraction, never generation) that STRIPS code-identifier
  tokens (paths, dotted/CamelCase symbols, stack-trace frames, quoted error strings) so the
  distilled query is natural-language-shaped and structurally incapable of injecting
  gold-span vocabulary; every stripped token recorded per case; pre-registered
  `MECHANICAL_RULE_HASH`. `llm_distill_guarded` is a LABELED non-primary SENSITIVITY arm
  (injected `Callable`) gated by a post-hoc token-subset HARD REJECT (`DistillRejected`);
  pre-registered `LLM_PROMPT_HASH`. The LLM arm never decides — it only disambiguates a
  flat mechanical delta.
- **`locate_probe.py` (extended, AC7):** `ReformulationResult` gained `paired_rows`,
  `delta_file_accuracy`, `discordant_pairs`, `llm_delta_empty`, `usable_n`,
  `excluded_case_ids` appended **last-with-defaults** (0022 constructor + callers
  byte-compatible); new `run_paired_reformulation_probe` (within-case paired A/B,
  per-case pairs retained); new `is_raw_issue` (AC8 raw-arm provenance precondition).

## Deviations

- **The operator VERDICT is deliberately NOT emitted.** Unit-complete (+52 unit tests;
  `test_benchmark_fit.py` ×30, `test_distill.py` ×12, `test_locate_probe.py` +10; all
  green, ruff clean) and live-smoke green — but non-informative BY CONSTRUCTION: the
  legacy fixtures are TERSE queries, so `is_raw_issue` excludes every one, `usable_n=0`,
  all cases in `excluded_case_ids`, air-gap held under `_deny_nonloopback_egress`. The
  AC8 guard working as designed (an underpowered run self-flags rather than faking a
  `CAPABILITY`). Firing `decide_axis1` for real needs operator SWE-bench long-issue cases
  (≥`min_n=12` usable, ≥8 discordant) with `HARPYJA_REQUIRE_LIVE_STACK=1`. Until then
  0022's provisional `RETRIEVAL_FUNDAMENTAL` stands and `BENCHMARK_UNREPRESENTATIVE`
  remains not-yet-excluded — the exact state this instrument exists to resolve. (This
  mirrors 0019/0020/0022: instrument shipped and live-verified ≠ the operator measurement.)
- **Honest cost surfaced by review:** a binary paired probe is NOT as cheap as the
  paired-continuous intuition suggested — power lives in discordant pairs, and reaching 8
  may need ~15–25 raw cases (still well below N=38, Scout-only-cheap, but not "a handful").
  Written into the config rather than glossed.

## Files touched

- `harpyja/eval/benchmark_fit.py` (new)
- `harpyja/eval/distill.py` (new)
- `harpyja/eval/locate_probe.py` (extended, additive)
- `harpyja/eval/test_benchmark_fit.py` (new)
- `harpyja/eval/test_distill.py` (new)
- `harpyja/eval/test_locate_probe.py` (extended)
- `harpyja/eval/test_locate_probe_integration.py` (extended)
- `specs/0023-benchmark-fit/findings.md` (new, the doc deliverable)

## Named follow-ups

1. **The operator run — fire the discriminator.** Stand up real SWE-bench long-issue
   cases and run `run_paired_reformulation_probe` (mechanical primary; LLM sensitivity arm
   optional) under `HARPYJA_REQUIRE_LIVE_STACK=1`, then `decide_axis1` + `is_representative`
   + `compose_verdict`. The 2×2 cell it lands in NAMES the next spec — and a
   `QUERY_SHAPE`/¬representative outcome routes to a benchmark/query-layer spec, **NOT** a
   finder swap.
2. **OQ1 — reachability vs power floor.** Decide before the live run whether to raise
   `MIN_DISCORDANT_PAIRS` from the reachability floor (8) to a formal target-power floor
   (~12–15), which raises the raw-case count.
3. **OQ2 — promote `delta_file_accuracy`?** Currently diagnostic + the axis-disagreement
   `INCONCLUSIVE` trigger; confirm whether it belongs in the primary rule.
