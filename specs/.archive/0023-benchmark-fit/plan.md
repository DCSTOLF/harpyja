---
spec: "0023"
status: planned
strategy: tdd
---

# Plan — 0023 benchmark-fit: reformulation probe + representativeness verdict

## Overview

A measure-don't-fix, cheap-before-expensive diagnostic that decides the *next* spec via a
typed, two-axis, pre-registered benchmark-fit verdict. Axis 1 (query shape) is a
within-case paired A/B whose power lives in McNemar discordant pairs; Axis 2
(representativeness) is a structured record that can downgrade Axis 1's routing through a
fixed 2×2. All code is ADDITIVE under `harpyja/eval/`; the SUT (`harpyja/scout/`,
`harpyja/orchestrator/`) stays byte-frozen. The verdict is a PURE FUNCTION over a frozen,
pre-registered config — no post-hoc tuning.

## Design decisions

- **New pure module `benchmark_fit.py`** owns all verdict machinery (config, McNemar,
  paired aggregator, Axis-1/Axis-2 verdicts, 2×2 composition). No SUT import; no I/O.
- **New module `distill.py`** owns the dual distiller: `mechanical_distill` (PRIMARY,
  structurally blind, token-subset extraction that STRIPS code identifiers) and the
  LLM sensitivity arm as a labeled, injected `Callable[[str], str]` guarded by a post-hoc
  token-subset hard-reject. No live LLM in unit tests — a fake that tries to inject a
  foreign token proves the reject.
- **`locate_probe.py` is EXTENDED additively (AC7)**: a new `run_paired_reformulation_probe`
  retains per-case `(case_id, raw_bucket, distilled_bucket)` pairs and file-level flags,
  emits `delta_file_accuracy` + discordant count + both arms, and applies the raw-arm
  provenance precondition `is_raw_issue` feeding `usable_n`. The existing
  `run_reformulation_probe` / `ReformulationResult` keep working — new fields are appended
  last-with-defaults, so legacy tests and callers are untouched.
- **McNemar exact test implemented from scratch** (no scipy): two-sided binomial sign test
  on discordant pairs at p=0.5 via `math.comb`. Boundary pins: 6/0 rejects (~0.031),
  5/0 does not (~0.063), 8/0 rejects (~0.0078), 7/1 does not (~0.070).
- **Totality by construction**: `decide_axis1` and `compose_verdict` are total functions
  with non-overlapping predicates; the three INCONCLUSIVE triggers are named separately
  (`INSUFFICIENT_POWER`, `DISTILLER_ARM_DISAGREEMENT`, `AXIS_SIGNAL_DISAGREEMENT`) so no
  path silently defaults. Totality is pinned by a grid test that asserts every input
  returns an enum member and never raises.
- **Pre-registration = hashed**: the mechanical rule id and the LLM prompt are hashed and
  recorded before any live run; the default config instance is the pre-registered constant
  and is frozen.
- **Integration honesty**: live tests are `@pytest.mark.integration`, gated through the
  existing `require_live_stack(scout_stack_available(...))` — skip-not-fail on a stackless
  host, hard-fail under `HARPYJA_REQUIRE_LIVE_STACK=1`. On the terse legacy fixtures
  `delta_empty ≈ 0` BY CONSTRUCTION; findings.md states this honestly — the real
  discriminator needs operator SWE-bench long-issue cases.

## File map

| File | New/extend | Concern |
|------|-----------|---------|
| `harpyja/eval/benchmark_fit.py` | new | config, McNemar, paired aggregator, Axis-1/2 verdicts, 2×2 composition |
| `harpyja/eval/distill.py` | new | mechanical (primary) + LLM-guarded (sensitivity) distillers, pre-reg hashes |
| `harpyja/eval/locate_probe.py` | extend | `run_paired_reformulation_probe`, `is_raw_issue`, additive `ReformulationResult` fields |
| `harpyja/eval/test_benchmark_fit.py` | new | unit: McNemar, aggregator, decide_axis1, representativeness, compose_verdict, config frozen |
| `harpyja/eval/test_distill.py` | new | unit: subset, case-agnostic, symbol-strip, stripped-token record, LLM reject filter, gold-span independence |
| `harpyja/eval/test_locate_probe.py` | extend | unit: is_raw_issue, paired rows, delta_file_accuracy, discordant, usable_n gate, legacy-unbroken |
| `harpyja/eval/test_locate_probe_integration.py` | extend | integration: paired probe both arms, raw provenance/usable_n, no non-loopback egress |
| `specs/0023-benchmark-fit/findings.md` | new (doc) | doc facet of AC4/AC5/AC6 + honest legacy-fixture caveat + pre-reg hashes |

## Test-first sequence

### Step 1 — Exact two-sided McNemar boundary (RED) [AC4]
- Add `harpyja/eval/test_benchmark_fit.py`:
  - `test_mcnemar_rejects_six_zero_at_alpha05` — 6/0 discordant → p≈0.031 rejects.
  - `test_mcnemar_does_not_reject_five_zero` — 5/0 → p≈0.063 does not reject.
  - `test_mcnemar_rejects_eight_zero` — 8/0 → p≈0.0078 rejects.
  - `test_mcnemar_does_not_reject_seven_one` — 7/1 → p≈0.070 does not reject.
  - `test_mcnemar_symmetric_in_arm_order` — swapping (b,c) gives same p.
- Tests fail: `benchmark_fit` module / `mcnemar_exact_p` do not exist.

### Step 2 — McNemar test (GREEN) [AC4]
- Implement `harpyja/eval/benchmark_fit.py` `mcnemar_exact_p(b: int, c: int) -> float`
  and `mcnemar_rejects(b, c, *, alpha=0.05) -> bool` using `math.comb` (two-sided sign
  test on `n=b+c` at p=0.5). All step-1 tests pass.

### Step 3 — Frozen pre-registered config (RED) [AC4/AC6]
- Add to `test_benchmark_fit.py`:
  - `test_config_default_is_frozen_preregistered` — `BenchmarkFitConfig` is a frozen
    dataclass; mutating a field raises `FrozenInstanceError`; `PREREGISTERED_CONFIG` is
    the default instance.
  - `test_config_min_discordant_pairs_is_eight` — `MIN_DISCORDANT_PAIRS == 8`.
  - `test_config_delta_empty_band_is_twenty_hundredths` — `DELTA_EMPTY_BAND == 0.20`.
  - `test_config_min_n_is_twelve` — `min_n == 12`.
- Tests fail: `BenchmarkFitConfig` / `PREREGISTERED_CONFIG` undefined.

### Step 4 — Config dataclass (GREEN) [AC4/AC6]
- Implement `BenchmarkFitConfig` (`frozen=True`) with `MIN_DISCORDANT_PAIRS=8`,
  `DELTA_EMPTY_BAND=0.20`, `min_n=12`, `alpha=0.05` and the `REPRESENTATIVE_THRESHOLD`
  inputs; expose `PREREGISTERED_CONFIG = BenchmarkFitConfig()`. Step-3 tests pass.

### Step 5 — Paired aggregator from retained pairs (RED) [AC3]
- Add to `test_benchmark_fit.py`:
  - `test_paired_aggregate_delta_empty_from_pairs` — from hand-built `PairedRow`s with a
    known per-case flip pattern, `delta_empty` equals the within-case mean, not a
    difference of two independent aggregate rates.
  - `test_paired_aggregate_delta_file_accuracy_from_pairs` — same for file-level accuracy.
  - `test_paired_aggregate_discordant_count_from_pairs` — discordant count equals the
    number of empty/not-empty flips between arms (b and c recorded separately).
- Tests fail: `PairedRow` / `aggregate_paired` undefined.

### Step 6 — Paired aggregator (GREEN) [AC3]
- Implement `PairedRow(case_id, raw_bucket, distilled_bucket, raw_right_file,
  distilled_right_file)` and `aggregate_paired(rows) -> PairedAggregate` returning
  `delta_empty`, `delta_file_accuracy`, `discordant_b`, `discordant_c`,
  `discordant_pairs` computed from the retained pairs. Step-5 tests pass.

### Step 7 — Axis-1 verdict: branches + named INCONCLUSIVE triggers (RED) [AC4]
- Add to `test_benchmark_fit.py`:
  - `test_decide_axis1_query_shape_when_delta_power_and_reject` — delta≥band, McNemar
    rejects, discordant≥8 → `QUERY_SHAPE`.
  - `test_decide_axis1_capability_when_flat_and_power` — flat delta, discordant≥8,
    McNemar cannot reject → `CAPABILITY`.
  - `test_decide_axis1_inconclusive_insufficient_power_low_discordant` — discordant<8 →
    `INCONCLUSIVE(INSUFFICIENT_POWER)`.
  - `test_decide_axis1_inconclusive_insufficient_power_low_usable_n` — usable_n<min_n →
    `INCONCLUSIVE(INSUFFICIENT_POWER)`.
  - `test_decide_axis1_inconclusive_insufficient_power_mcnemar_fails` — delta≥band but
    McNemar fails to reject → `INCONCLUSIVE(INSUFFICIENT_POWER)`.
  - `test_decide_axis1_inconclusive_distiller_arm_disagreement` — mechanical vs LLM arm
    deltas differ in sign → `INCONCLUSIVE(DISTILLER_ARM_DISAGREEMENT)`.
  - `test_decide_axis1_inconclusive_axis_signal_disagreement` — `delta_empty` vs
    `delta_file_accuracy` differ in sign → `INCONCLUSIVE(AXIS_SIGNAL_DISAGREEMENT)`.
  - `test_decide_axis1_is_total_over_grid` — parametrized grid; every input returns an
    `Axis1Verdict` member and never raises (totality + non-overlap).
- Tests fail: `Axis1Verdict`, `InconclusiveReason`, `decide_axis1` undefined.

### Step 8 — decide_axis1 (GREEN) [AC4]
- Implement `Axis1Verdict{QUERY_SHAPE, CAPABILITY, INCONCLUSIVE}`,
  `InconclusiveReason{INSUFFICIENT_POWER, DISTILLER_ARM_DISAGREEMENT,
  AXIS_SIGNAL_DISAGREEMENT}`, and total `decide_axis1(agg, *, llm_delta, usable_n,
  config) -> (Axis1Verdict, InconclusiveReason | None)` with non-overlapping predicates
  in the AC4 order (disagreement/power gates before QUERY_SHAPE/CAPABILITY). Step-7 tests
  pass.

### Step 9 — Axis-2 representativeness record + threshold (RED) [AC5]
- Add to `test_benchmark_fit.py`:
  - `test_representative_false_when_low_doc_and_weak_proxy` — both conditions → `False`.
  - `test_representative_true_when_only_documentation_low` — one condition only → `True`.
  - `test_representative_true_when_only_weak_proxy` — one condition only → `True`.
  - `test_representativeness_record_is_structured` — fields `query_shape, repo_type,
    documentation_density, codebase_age, target_proxy_validity` present.
- Tests fail: `RepresentativenessRecord` / `is_representative` undefined.

### Step 10 — RepresentativenessRecord (GREEN) [AC5]
- Implement frozen `RepresentativenessRecord` and `is_representative(record, *, config)`
  applying `REPRESENTATIVE_THRESHOLD` (`False` iff `documentation_density=="low"` AND
  `target_proxy_validity=="weak"`). Step-9 tests pass.

### Step 11 — Pre-registered 2×2 composition (RED) [AC6]
- Add to `test_benchmark_fit.py`:
  - `test_compose_verdict_query_shape_representative_adds_layer`.
  - `test_compose_verdict_query_shape_unrepresentative_builds_benchmark`.
  - `test_compose_verdict_capability_representative_routes_n38`.
  - `test_compose_verdict_capability_unrepresentative_retires_swebench`.
  - `test_compose_verdict_inconclusive_axis1_holds` — Axis-1 INCONCLUSIVE routes to a
    HOLD next-spec regardless of Axis 2.
  - `test_compose_verdict_is_total_over_axes` — every `(Axis1Verdict × bool)` returns a
    `BenchmarkFitVerdict` and never raises.
- Tests fail: `BenchmarkFitVerdict` / `compose_verdict` undefined.

### Step 12 — compose_verdict (GREEN) [AC6]
- Implement `BenchmarkFitVerdict` (axis1, representative, `next_spec` routing) and total
  `compose_verdict(axis1, representative) -> BenchmarkFitVerdict` encoding the fixed 2×2
  (Axis 2 downgrades Axis 1). Step-11 tests pass.

### Step 13 — Mechanical distiller: subset + symbol-strip + audit (RED) [AC2]
- Add `harpyja/eval/test_distill.py`:
  - `test_mechanical_distill_output_tokens_subset_of_input` — output tokens ⊆ issue
    tokens (extraction, never generation).
  - `test_mechanical_distill_strips_file_paths` — `path/to/foo.py` removed.
  - `test_mechanical_distill_strips_dotted_and_camelcase_symbols` — `mod.Thing`,
    `CamelCase` removed.
  - `test_mechanical_distill_strips_stack_trace_frames` — `File "...", line N` frames
    removed.
  - `test_mechanical_distill_strips_exact_error_strings` — quoted/`Error:`-shaped strings
    removed.
  - `test_mechanical_distill_records_stripped_tokens` — every stripped token returned for
    the audit trail.
  - `test_mechanical_distill_is_case_agnostic` — identical text under two different
    `case_id`s yields identical output (no case-id parameter / branching).
  - `test_mechanical_distill_ignores_gold_spans` — signature takes only `issue_text`;
    never sees `expected_spans`.
  - `test_mechanical_distill_rule_is_prehashed` — `MECHANICAL_RULE_HASH` is a stable
    recorded digest of the rule id.
- Tests fail: `distill` module / `mechanical_distill` undefined.

### Step 14 — mechanical_distill (GREEN) [AC2]
- Implement `mechanical_distill(issue_text: str) -> DistillResult` (returns
  `query: str` + `stripped_tokens: tuple[str, ...]`), a single case-agnostic extraction
  rule that strips paths/dotted-CamelCase symbols/trace frames/error strings; expose
  `MECHANICAL_RULE_HASH`. Step-13 tests pass.

### Step 15 — LLM sensitivity arm subset-reject filter (RED) [AC2]
- Add to `test_distill.py`:
  - `test_llm_distill_guarded_rejects_foreign_token` — a fake `Callable` that injects a
    token absent from the issue is hard-rejected (falls back / typed reject), never
    passed through.
  - `test_llm_distill_guarded_accepts_subset_output` — a fake whose output ⊆ issue tokens
    passes.
  - `test_llm_distill_prompt_is_prehashed` — `LLM_PROMPT_HASH` recorded/stable.
- Tests fail: `llm_distill_guarded` / `LLM_PROMPT_HASH` undefined.

### Step 16 — llm_distill_guarded (GREEN) [AC2]
- Implement `llm_distill_guarded(issue_text, *, llm: Callable[[str], str]) -> DistillResult`
  applying the post-hoc token-subset hard reject; expose `LLM_PROMPT` + `LLM_PROMPT_HASH`.
  No live LLM. Step-15 tests pass.

### Step 17 — Raw-arm provenance precondition (RED) [AC8]
- Add to `harpyja/eval/test_locate_probe.py`:
  - `test_is_raw_issue_true_for_multiparagraph_body` — long multi-paragraph text → `True`.
  - `test_is_raw_issue_false_for_short_single_line` — terse one-liner → `False`.
  - `test_is_raw_issue_false_for_blank` — empty/whitespace → `False`.
- Tests fail: `is_raw_issue` undefined in `locate_probe`.

### Step 18 — is_raw_issue (GREEN) [AC8]
- Implement `is_raw_issue(query: str) -> bool` (length + paragraph-structure check) in
  `locate_probe.py`. Step-17 tests pass.

### Step 19 — Paired probe unit over a fake Scout (RED) [AC3/AC7/AC8]
- Add to `test_locate_probe.py` (fake Scout with a scripted per-case bucket outcome):
  - `test_paired_probe_emits_per_case_rows` — one `PairedRow` per usable case, both arms.
  - `test_paired_probe_delta_file_accuracy_paired` — file-accuracy delta is paired.
  - `test_paired_probe_discordant_count_recorded` — discordant count on the result.
  - `test_paired_probe_excludes_non_raw_from_usable_n` — a non-raw case is dropped from
    `usable_n` and recorded as excluded.
  - `test_paired_probe_usable_n_below_min_n_marks_inconclusive` — `usable_n < min_n`
    surfaces the INCONCLUSIVE(INSUFFICIENT_POWER) precondition.
  - `test_reformulation_result_additive_fields_default` — legacy `ReformulationResult(n,
    raw_empty_rate, distilled_empty_rate, delta_empty)` still constructs (new fields
    default).
  - `test_run_reformulation_probe_unchanged` — the existing aggregate-rate function still
    returns the same shape (AC7 no-break).
- Tests fail: `run_paired_reformulation_probe` / new `ReformulationResult` fields absent.

### Step 20 — Paired probe integration (RED) [AC1/AC8]
- Add to `harpyja/eval/test_locate_probe_integration.py` (reuse `_gate`,
  `_legacy_repo`, `_settings_live`, `_deny_nonloopback_egress`, `_live_cases`):
  - `test_paired_reformulation_probe_records_both_arms` — bounded live cases; per-case
    rows + aggregates for mechanical (primary) and LLM arms.
  - `test_paired_probe_raw_provenance_and_usable_n` — `is_raw_issue` gate applied;
    `usable_n` recorded; legacy fixtures honestly note `delta≈0` by construction.
  - `test_paired_probe_no_nonloopback_egress` — runs inside `_deny_nonloopback_egress()`.
- Tests fail at COLLECTION: they import `run_paired_reformulation_probe` (undefined) — a
  genuine RED regardless of stack availability, before the skip gate can fire.

### Step 21 — run_paired_reformulation_probe + extended ReformulationResult (GREEN) [AC1/AC3/AC7/AC8]
- Extend `locate_probe.py`: append last-with-defaults fields to `ReformulationResult`
  (`paired_rows: tuple[PairedRow, ...] = ()`, `delta_file_accuracy: float = 0.0`,
  `discordant_pairs: int = 0`, `llm_delta_empty: float | None = None`,
  `usable_n: int = 0`, `excluded_case_ids: tuple[str, ...] = ()`). Implement
  `run_paired_reformulation_probe(cases, *, stack, repo_path, window,
  mechanical=mechanical_distill, llm=None)` that, per case, gates on `is_raw_issue`, runs
  both arms retaining `PairedRow`s, and aggregates via `benchmark_fit.aggregate_paired`.
  Step-19 unit tests pass; step-20 integration tests import cleanly (skip on stackless
  host / proceed under `HARPYJA_REQUIRE_LIVE_STACK`).

### Step 22 — Refactor: share the single-arm run helper (REFACTOR) [AC7]
- Factor the per-case Scout drive (reset `last_tally` → `search` → `normalize_citations`
  → `classify_case`) into one helper reused by `_empty_rate`, `run_locate_probe`, and
  `run_paired_reformulation_probe` so the paired path is not a third copy. All tests
  still pass; existing `run_reformulation_probe` output unchanged.

### Step 23 — findings.md deliverable (DOC) [AC4/AC5/AC6]
- Write `specs/0023-benchmark-fit/findings.md`: the Axis-1 branch table, the Axis-2
  record schema + threshold, the pre-registered 2×2, the recorded `MECHANICAL_RULE_HASH`
  / `LLM_PROMPT_HASH`, and the honest live-smoke note (legacy fixtures give `delta≈0` by
  construction; the real discriminator needs operator SWE-bench long-issue cases).
- No RED (documentation of already-tested pure functions).

### Step 24 — Verify full suite + lint (REFACTOR/verify)
- Run `uv run pytest` and `uv run ruff check`. Expect the prior ~883-unit baseline to
  GROW (new unit tests in Steps 1–19) and stay green; integration additions skip on a
  stackless host. Fix any lint. No behavior change.

## Delegation

- Steps 1–2 (exact McNemar math) → delegate to a numerics-careful implementer (reason:
  `math.comb` two-sided boundary arithmetic must hit the pinned p-values exactly).
- Steps 20–21 (live paired probe) → delegate to the live-stack integration owner (reason:
  familiarity with `require_live_stack` skip-not-fail / hard-fail posture and
  `_deny_nonloopback_egress`).
- Remaining pure-function steps → single TDD implementer; they are self-contained and
  fully unit-testable.

## Risk

- **Legacy fixtures give delta≈0 by construction** → mitigation: findings.md states this
  honestly; the paired probe's `usable_n`/`is_raw_issue` gate + INCONCLUSIVE(INSUFFICIENT_POWER)
  make the underpowered legacy run self-flagging rather than a false `CAPABILITY`.
- **Extending `ReformulationResult` could break 0022 tests** → mitigation: append fields
  last-with-defaults; `test_reformulation_result_additive_fields_default` +
  `test_run_reformulation_probe_unchanged` pin the no-break contract (AC7).
- **Non-overlapping-predicate drift in decide_axis1 / compose_verdict** → mitigation:
  totality grid tests (`*_is_total_over_grid`, `*_is_total_over_axes`) assert every input
  returns an enum member and never raises.
- **Symbol-strip over- or under-reaching** → mitigation: one test per identifier class
  (paths, dotted/CamelCase, trace frames, error strings) plus the subset property and the
  stripped-token audit record.
- **Integration RED masked by skip** → mitigation: Step-20 tests import the new symbol so
  they fail at COLLECTION before the skip gate, making the RED real on any host.
- **Air-gap regression** → mitigation: `test_paired_probe_no_nonloopback_egress` runs the
  live probe under `_deny_nonloopback_egress()`.
