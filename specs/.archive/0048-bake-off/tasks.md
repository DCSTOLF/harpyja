---
spec: "0048"
---

# Tasks

Legend: `[ ]` planned · [unit]=fakes, fast · [int]=`@pytest.mark.integration` (skip-not-fail) ·
[OP]=operator/live run outside the sandbox · [DOC]=writeup.

- [x] T1 — [RED][unit] `test_bakeoff_config.py`: three tags/pairs, absolute floors (8/36/0.5/m=3/α),
  Ns (44/9), decoding (temp0/top_p1/seed), pool sha `385107934f61…`, Holm-m3 divergence from 0040,
  stable hash (config underpins AC1–AC7)
- [x] T2 — [GREEN] implement `bakeoff_config.py` `BakeoffConfig` + `PREREGISTERED_BAKEOFF_CONFIG_0048`
  + `BAKEOFF_CONFIG_HASH_0048` (floor reused by identity)
- [x] T3 — [RED][unit] `test_bakeoff_analysis.py`: `is_signal_discordant`/`located_via_oracle`
  identity reuse; `b`/`c` + `b+c` from per-case buckets, NOT marginal counts (AC3)
- [x] T4 — [GREEN] `bakeoff_analysis.py` `BakeoffPairCase` + `discordant_counts` (identity re-export)
- [x] T5 — [RED][unit] the four coverage/closeness outcomes, mutually distinct on ABSOLUTE-count
  predicates: UNDER_POWERED (N<36) + degraded-dominated (>50%) partition, TOO_CLOSE (N≥36 & b+c<8),
  NO_DIFFERENCE (b+c≥8 & Holm-not-reject), SEPARATES (b+c≥8 & Holm-reject); grid-totality (AC3)
- [x] T6 — [GREEN] `PairOutcome` + `PairResult` + `decide_pair_outcome` (frozen predicate order)
- [x] T7 — [RED][unit] exact-McNemar identity reuse + Holm step-down over three p-values: ascending
  rejection, running-max adjusted-p, m=3 FIXED when fewer pairs test, fixed-order ties, `p≤α`
  boundary (AC3)
- [x] T8 — [GREEN] `holm_adjusted_pvalues` + `holm_rejections` (reuse `mcnemar_exact_p`, m fixed)
- [x] T9 — [RED][unit] per-repo leave-one/leave-two-out → REPO_CONCENTRATED (direction flip OR
  b+c<8), per-repo `b−c` distribution reported (AC5-pure)
- [x] T10 — [GREEN] `repo_concentrated` + `per_repo_bc_distribution`
- [x] T11 — [RED][unit] assembly totality: INFRASTRUCTURE_HALTED (<2), PARTIAL (exactly 2 +
  MODEL_EXCLUDED), RANKING (total order), INTRANSITIVE (cycle), PARTIAL (mixed), NO_SEPARATION (none)
  (AC7 core)
- [x] T12 — [GREEN] `BakeoffOutcome` + `ModelExclusion` + `BakeoffReport` + `assemble_bakeoff`
- [x] T13 — [RED][unit] reachability split first-class: conceptual carries verdict, lexical
  descriptive-only, NO pooled headline (AC4-pure)
- [x] T14 — [GREEN] `split_by_reachability` + `lexical_descriptive_stats`
- [x] T15 — [REFACTOR] fold shared located/drop-tally helpers; oracles stay identity-imported
- [x] T16 — [RED][int] AC1 preflight: assert-local-first → positive `/api/tags` per tag → coherence +
  `/v1` tool-calling → reproducibility replay (double-run ≥3 conceptual, mismatch→EXCLUDE); config
  tags asserted present (AC1)
- [x] T17 — [GREEN] `bakeoff_run.py` preflight adjudicator (+`REPLAY_FAIL`) +
  `reproducibility_replay_probe` + `bakeoff_preflight` (reuse `preflight_models_present`)
- [x] T18 — [RED][int] AC2 resumable `BakeoffLedger` (config-hash keyed, schema loud) + durable
  artifact full schema (bucket/tools/reasoning/submitted/surviving/found-but-unsubmitted/identity/
  serving_transport/decoding/pool-sha/SUT-hash/exclusivity-proof) + heavy-repo degrade rate (AC2)
- [x] T19 — [GREEN] `BakeoffLedger` (mirror `AbLedger`, `0048/1`) + `build_bakeoff_artifact`
  (reuse `exclusivity_gate.build_exclusivity_record`)
- [x] T20 — [RED][int] report: reachability split no-pooled-headline (AC4) + REPO_CONCENTRATED on
  separating pairs + per-repo distribution (AC5) + symbols-adoption & found-but-unsubmitted per model
  (AC6)
- [x] T21 — [GREEN] `build_bakeoff_report` (calls the pure core + per-model metric aggregation)
- [~] T22 — [OP][int] staged DETACHED live run — TURNKEY CODE COMPLETE, LIVE RUN PENDING OPERATOR.
  Driver `bakeoff_driver.run_bakeoff` (config-hash refusal + preflight-all-3 → feasibility-pair-
  first ordering → resumable grid → INFRASTRUCTURE_HALTED-without-2-survivors) + live SUT seams
  `bakeoff_live.py` (verifier→bake-off artifact map, live cell runner, preflight prober; explorer
  byte-pin preserved — greedy is server-side + replay-verified, never injected) + `bakeoff_cli.py`
  operator entrypoint (loads the real 44/9 pool, pins SUT hash + 0041 exclusivity, wires seams,
  writes `outcome.json`) + `run_bakeoff.sh` (nohup+disown launcher). All non-live logic unit/int
  tested & green (61 bake-off tests). REMAINING = OPERATOR: provision worktrees + audited gold
  (blind-withheld for 52/53 — a loud missing-input, never fabricated), ensure the 3 tags serve
  GREEDY on the dev Ollama, then `harpyja/eval/run_bakeoff.sh` (detached ~9h). **← PAUSED HERE.**
- [~] T23 — [DOC] `specs/0048-bake-off/outcome.md` — PRELIMINARY WRITTEN (attempt documented).
  Run ATTEMPTED on the dev stack; the preflight caught TWO hard blockers before the ~15h grid:
  (1) DETERMINISM — `qwen3:14b` double-run on astropy-12907 gave `empty` vs `right-file-wrong-span`
  → REPLAY-FAIL → would type `INFRASTRUCTURE_HALTED` (served non-greedy; explorer byte-pin forbids
  injecting temp=0 → needs greedy Modelfiles, a surface follow-up); (2) COVERAGE — only 19/53 cases
  runnable (34 worktrees + gold unprovisioned; the 0047 enlargement was authoring-time only), so
  eligible conceptual N ≤ 15 < 36 → PAIR_UNDER_POWERED. Pipeline VALIDATED end-to-end on real
  output. Powered ranking BLOCKED on greedy-serving + provisioning the 34 cases; final outcome.md
  authored from `outcome.json` once both hold.
