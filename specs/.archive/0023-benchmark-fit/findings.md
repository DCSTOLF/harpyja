# Findings — Spec 0023 (benchmark-fit): reformulation probe + representativeness verdict

> **Instrument shipped, unit-verified, and live-smoke green — the operator VERDICT is
> deliberately not yet emitted.** This spec builds the *typed, two-axis, pre-registered*
> discriminator that decides whether 0022's provisional `RETRIEVAL_FUNDAMENTAL` is a real
> capability wall or a `BENCHMARK_UNREPRESENTATIVE` artifact. The verdict is a **pure
> function** over a frozen config; running it for real requires operator SWE-bench
> long-issue cases (the legacy fixtures cannot fire it — see below). This mirrors
> 0019/0020/0022: *instrument shipped and live-verified ≠ the operator measurement.*

## What shipped (all additive under `harpyja/eval/`; SUT byte-frozen)

- **`benchmark_fit.py`** — the pure verdict machinery:
  - `mcnemar_exact_p` / `mcnemar_rejects` — an exact two-sided McNemar test from scratch
    (`math.comb`, no scipy). Boundary-pinned: `6/0→0.03125` rejects, `5/0→0.0625` does
    not, `8/0→0.0078125` rejects, `7/1→0.0703125` does not. These are the numbers that
    make `MIN_DISCORDANT_PAIRS = 8` the right floor.
  - `BenchmarkFitConfig` (frozen) + `PREREGISTERED_CONFIG` — `MIN_DISCORDANT_PAIRS=8`,
    `DELTA_EMPTY_BAND=0.20`, `min_n=12`, `alpha=0.05`, and the representativeness
    threshold inputs. Declared in code before any run; cannot be tuned post-hoc.
  - `PairedRow` + `aggregate_paired` — `delta_empty`, `delta_file_accuracy`, and the
    discordant `(b, c)` counts computed FROM retained per-case pairs (AC3), never a
    difference of aggregate rates.
  - `decide_axis1` — the total Axis-1 verdict with a paired uncertainty gate and three
    **named, non-overlapping** `INCONCLUSIVE` triggers (`INSUFFICIENT_POWER`,
    `DISTILLER_ARM_DISAGREEMENT`, `AXIS_SIGNAL_DISAGREEMENT`).
  - `RepresentativenessRecord` + `is_representative` (AC5), and `compose_verdict` — the
    pre-registered 2×2 (AC6), total over `Axis1Verdict × bool`.
- **`distill.py`** — the dual distiller (AC2):
  - `mechanical_distill` — PRIMARY, verdict-driving. First non-empty line → NL words,
    with code-identifier tokens stripped (paths, dotted/CamelCase symbols, stack-trace
    frames, quoted error strings). Output tokens are a **subset of the issue tokens** by
    construction → structurally incapable of injecting gold-span vocabulary. Case-agnostic
    and gold-span-blind by signature (`issue_text` only). Pre-registered:
    `MECHANICAL_RULE_HASH = 5a77d3ee…f3138`.
  - `llm_distill_guarded` — LABELED, non-primary SENSITIVITY arm; an injected `Callable`
    gated by a post-hoc token-subset HARD REJECT (`DistillRejected`). Pre-registered:
    `LLM_PROMPT_HASH = e7a54bab…a0079`.
- **`locate_probe.py`** (EXTENDED, not rewritten — AC7): `ReformulationResult` gained
  `paired_rows`, `delta_file_accuracy`, `discordant_pairs`, `llm_delta_empty`, `usable_n`,
  `excluded_case_ids` (appended last-with-defaults, so 0022's constructor and callers are
  byte-compatible). New `run_paired_reformulation_probe` (within-case paired A/B, per-case
  pairs retained) and `is_raw_issue` (AC8 raw-arm provenance precondition).

## Axis-1 verdict — the branch table (AC4)

| Condition | Verdict |
|---|---|
| `delta_empty ≥ 0.20` AND exact McNemar rejects (α=0.05) AND `discordant ≥ 8` AND `usable_n ≥ 12` | **QUERY_SHAPE** |
| flat `delta_empty` AND `discordant ≥ 8` AND `usable_n ≥ 12` (power to have detected an effect) | **CAPABILITY** |
| `discordant < 8` OR `usable_n < 12` OR (material but McNemar fails to reject) | INCONCLUSIVE(`INSUFFICIENT_POWER`) |
| mechanical vs LLM `delta_empty` differ in sign | INCONCLUSIVE(`DISTILLER_ARM_DISAGREEMENT`) |
| `delta_empty` vs `delta_file_accuracy` differ in sign | INCONCLUSIVE(`AXIS_SIGNAL_DISAGREEMENT`) |

Order (each guard returns → total, non-overlapping): power → axis-signal disagreement →
distiller-arm disagreement → QUERY_SHAPE → (material-but-not-significant) → CAPABILITY.

## The pre-registered 2×2 composition (AC6)

| | representative | ¬representative |
|---|---|---|
| **QUERY_SHAPE** | add a reformulation layer | build a terse-query benchmark first (**NOT** a finder swap) |
| **CAPABILITY** | N=38 confirmation + finder-capability work | retire SWE-bench as the yardstick |
| **INCONCLUSIVE** | hold — discriminator unresolved | hold — discriminator unresolved |

## What was run vs. NOT run (honest scope)

- **Unit — complete.** +52 unit tests (`test_benchmark_fit.py` ×30, `test_distill.py`
  ×12, `test_locate_probe.py` +10), all green; ruff clean.
- **Live smoke — green, but non-informative by construction.** All 7 Scout-only
  integration tests pass live (~56s) with the served Q8 FastContext stack. **But the
  legacy fixtures are TERSE queries**, so `is_raw_issue` excludes every one of them: the
  paired probe reports `usable_n = 0`, every case accounted for in `excluded_case_ids`,
  and the air-gap holds under `_deny_nonloopback_egress`. This is the AC8 guard working
  as designed — an underpowered run self-flags rather than faking a `CAPABILITY`. It does
  **not** exercise the discriminator on real long-issue text.
- **The operator verdict — NOT emitted (gated).** Firing `decide_axis1` for real needs
  real multi-paragraph SWE-bench issue cases (≥ `min_n=12` usable, ≥ `8` discordant
  pairs). Those are the operator SWE-bench checkouts absent on this host (the 0020 G2
  setup). Until then the 0022 provisional `RETRIEVAL_FUNDAMENTAL` stands, and
  `BENCHMARK_UNREPRESENTATIVE` remains not-yet-excluded — exactly the state this
  instrument exists to resolve.

## The honest cost (surfaced by review, not glossed)

A *binary* paired probe is **not** as cheap as the paired-continuous intuition suggested.
Power lives in discordant pairs, and reaching `MIN_DISCORDANT_PAIRS = 8` may need ~15–25
raw cases depending on the discordance rate. That is still well below N=38 and
Scout-only-cheap — but it is not "a handful," and the config says so rather than
pretending otherwise (the `INSUFFICIENT_POWER` trigger makes a short run name the
discordant-pair count it still needs).

## Named follow-ups

1. **The operator run — fire the discriminator.** Stand up real SWE-bench long-issue
   cases and run `run_paired_reformulation_probe` (mechanical primary; LLM sensitivity arm
   optional) with `HARPYJA_REQUIRE_LIVE_STACK=1`, then `decide_axis1` + `is_representative`
   + `compose_verdict`. The 2×2 cell it lands in **names the next spec** — and if it fires
   `QUERY_SHAPE`/`¬representative`, that next spec is a benchmark/query-layer, **NOT** a
   finder swap (a poor score on verbose issue prose is a benchmark-fit artifact against
   Harpyja's terse-query target).
2. **OQ1 — reachability vs power floor.** Decide before the live run whether to raise
   `MIN_DISCORDANT_PAIRS` from the reachability floor (8) to a formal target-power floor at
   `DELTA_EMPTY_BAND` (~12–15), which also raises the raw-case count.
3. **OQ2 — promote `delta_file_accuracy`?** Currently diagnostic + the axis-disagreement
   `INCONCLUSIVE` trigger; confirm whether it belongs in the primary rule.
