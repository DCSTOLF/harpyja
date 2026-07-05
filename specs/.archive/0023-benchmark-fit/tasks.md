---
spec: "0023"
---

# Tasks

- [x] T1 — RED: exact two-sided McNemar boundary tests (6/0, 5/0, 8/0, 7/1, symmetry) [AC4]
- [x] T2 — GREEN: `mcnemar_exact_p` / `mcnemar_rejects` via `math.comb` in `benchmark_fit.py` [AC4]
- [x] T3 — RED: frozen pre-registered `BenchmarkFitConfig` / constants tests [AC4/AC6]
- [x] T4 — GREEN: `BenchmarkFitConfig` + `PREREGISTERED_CONFIG` (8 / 0.20 / min_n 12) [AC4/AC6]
- [x] T5 — RED: paired aggregator tests (delta_empty, delta_file_accuracy, discordant count from pairs) [AC3]
- [x] T6 — GREEN: `PairedRow` + `aggregate_paired` from retained pairs [AC3]
- [x] T7 — RED: `decide_axis1` branch + three named INCONCLUSIVE + totality tests [AC4]
- [x] T8 — GREEN: `Axis1Verdict` / `InconclusiveReason` / total `decide_axis1` [AC4]
- [x] T9 — RED: representativeness record + threshold tests [AC5]
- [x] T10 — GREEN: `RepresentativenessRecord` + `is_representative` [AC5]
- [x] T11 — RED: pre-registered 2×2 `compose_verdict` totality tests [AC6]
- [x] T12 — GREEN: `BenchmarkFitVerdict` + total `compose_verdict` [AC6]
- [x] T13 — RED: mechanical distiller subset / symbol-strip / audit / case-agnostic / gold-independence tests [AC2]
- [x] T14 — GREEN: `mechanical_distill` + `MECHANICAL_RULE_HASH` in `distill.py` [AC2]
- [x] T15 — RED: LLM arm subset-reject filter + prompt-hash tests [AC2]
- [x] T16 — GREEN: `llm_distill_guarded` + `LLM_PROMPT` / `LLM_PROMPT_HASH` [AC2]
- [x] T17 — RED: `is_raw_issue` provenance tests [AC8]
- [x] T18 — GREEN: `is_raw_issue` in `locate_probe.py` [AC8]
- [x] T19 — RED: paired probe unit over fake Scout + legacy-unbroken tests [AC3/AC7/AC8]
- [x] T20 — RED: paired probe integration tests (both arms, provenance/usable_n, no non-loopback egress) [AC1/AC8]
- [x] T21 — GREEN: `run_paired_reformulation_probe` + additive `ReformulationResult` fields [AC1/AC3/AC7/AC8]
- [x] T22 — REFACTOR: extract shared per-case Scout-drive helper (no third copy) [AC7]
- [x] T23 — DOC: write `specs/0023-benchmark-fit/findings.md` (branch table, 2×2, hashes, honest legacy caveat) [AC4/AC5/AC6]
- [x] T24 — VERIFY: `uv run pytest` + `uv run ruff check`; baseline (~883 unit) grows and stays green
