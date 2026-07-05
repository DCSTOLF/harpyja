# Findings — Spec 0022 (Tier-1): Scout locate-accuracy on SWE-bench

> **Typed finding (provisional): `RETRIEVAL_FUNDAMENTAL`** — Scout's failure is
> recall/retrieval (it does not find the file), not span precision. **One branch is
> not yet excludable:** `BENCHMARK_UNREPRESENTATIVE`, because its discriminator (the
> query-reformulation probe on *real* long-issue text) is operator-gated. The full
> 38-case SWE-bench distribution is likewise operator-gated; what is recorded here is
> the **instrument (complete, unit-verified) + a live end-to-end fixture smoke +** the
> carried-forward 0020/0021 prior. This mirrors 0019/0020: *instrument shipped and
> live-verified ≠ the full operator measurement.*

## TL;DR (the two-granularity axis)

| Signal | Legacy-fixture live smoke (N=5) | Carried-forward SWE-bench prior (0020/0021) |
|---|---|---|
| FILE-level accuracy `F` | 0.20 | ~0.05 (≈ empty-dominant; 1 known right-file case, astropy) |
| SPAN-level accuracy `S` | 0.20 | ~0.00 (`correct_tier1_count = 0`) |
| **Gap `G = F − S`** | **0.00** | **~0.05** (no precision gap → not precision-fixable) |
| Empty-rate `E` | 0.80 (4/5) | ~0.87 (≈ 33/38) |
| `decide_finding` label | **RETRIEVAL_FUNDAMENTAL** | **RETRIEVAL_FUNDAMENTAL** (pre-registered) |

The gap is ~0 in both: when Scout finds a gold file it tends to also hit the span; the
dominant failure is finding *nothing* (empty) or the *wrong file*, not landing in the
right file with a wrong span. That is the retrieval-fundamental signature, not the
precision-fixable one.

## What was actually run here (honest scope)

- **Instrument — complete, unit-verified.** 48 unit tests (`test_locate_accuracy.py`
  ×33, `test_locate_probe.py` ×15) + 4 live integration tests, all green; ruff clean.
  The SUT (`harpyja/scout/`, `harpyja/orchestrator/`) is byte-frozen — all code is
  additive under `harpyja/eval/` (`locate_accuracy.py`, `locate_probe.py`), guarded by
  the `SUT_SURFACE` allowlist + the frozen-oracle behavior snapshot (AC10).
- **Live end-to-end smoke — real Scout, legacy fixture, N=5 seed cases.** Model
  `hf.co/dstolf/FastContext-1.0-4B-RL-Q8_0-GGUF` on local Ollama. Result:
  `CORRECT=1, RIGHT_FILE_WRONG_SPAN=0, WRONG_FILE=0, EMPTY=4`; `F=0.20, S=0.20,
  gap=0.00, empty_rate=0.80, normalization_dropped_total=1`.
  Per-case rows (AC8):

  | case_id | bucket | n_citations | dropped | turns |
  |---|---|---|---|---|
  | backoff | EMPTY | 0 | 0 | 5 |
  | authenticate | EMPTY | 0 | 1 | 5 |
  | hash | CORRECT | 1 | 0 | 7 |
  | retry_policy | EMPTY | 0 | 0 | 3 |
  | flow | EMPTY | 0 | 0 | 5 |

- **Turns-used — captured live (`turns_used_source == "trajectory"`).** The
  `agent_factory` injection seam works end-to-end: turns `(5, 5, 7, 3, 5)` were read
  from FastContext's trajectory JSONL BEFORE the frozen client's `os.unlink` cleanup —
  no SUT edit. This answers AC4's "exhausts turns then emits nothing?": the empty cases
  used **3–5 of the available turns and still emitted nothing** — they are NOT
  turn-exhaustion; Scout converges (early) to an empty answer. That is a recall gap in
  the finder, consistent with `RETRIEVAL_FUNDAMENTAL`.

## What is NOT run here (operator-gated)

- **The real SWE-bench 38-case distribution.** `_live_cases` is the legacy-fixture
  smoke dataset (the 0019/0020 stand-in), NOT the real SWE-bench repos (astropy, etc.).
  The real distribution needs the SWE-bench dataset + per-case checkouts (the 0020 G2
  operator setup) — not present on this host. The carried-forward prior stands in for
  it: `correct_tier1_count = 0`, empty-dominant.
- **The query-reformulation probe as a *discriminator*.** The probe ran green in the
  integration suite, but on the fixture's *terse* queries (`"backoff"`, `"retry_policy"`)
  there is nothing to distill → `delta_empty ≈ 0` by construction, which is **not
  evidence** about the real question. The meaningful probe distills *real
  multi-paragraph GitHub-issue text* — operator-gated. **Until it runs,
  `BENCHMARK_UNREPRESENTATIVE` cannot be excluded** (a low SWE-bench score could indict
  the benchmark, not Scout — AC9).

## Representativeness judgment (AC9)

SWE-bench point-case queries are verbose GitHub-issue prose; Harpyja's founding target
is a *terse* legacy-codebase NL query ("where's the retry logic for the payment
gateway"). The fixture smoke uses terse queries and STILL shows 80% empty — a data
point that the empty-dominance is **not** purely a long-query artifact (Scout misses
even short queries on the fixture). But this is N=5 on a synthetic repo; it is
suggestive, not decisive. The decisive test is the reformulation probe on real
SWE-bench issue text: **if distilling cuts the empty-rate materially → the finding flips
to `BENCHMARK_UNREPRESENTATIVE`** (query-shape, route to a dataset spec); **if not → it
stays `RETRIEVAL_FUNDAMENTAL`** (route to a finder-capability spec). This is why AC5/AC6
kept both in scope: the branch is only diagnosable *because* the probe is.

## Pre-registered prior (falsifiability guard)

Before the run: 0021 gave ~33/38 EMPTY + one astropy right-file-wrong-span →
**pre-registered `RETRIEVAL_FUNDAMENTAL`**. What would overturn it: a materially
positive reformulation `delta_empty` (→ `BENCHMARK_UNREPRESENTATIVE`) or a large
file-minus-span gap (→ `PRECISION_FIXABLE`). The fixture smoke did **not** overturn it
(gap 0.0, probe non-informative). The prior therefore holds provisionally, explicitly
pending the operator run.

## Metric-trust (regenerate, don't inherit)

Per 0021's verdict, the distribution here is **regenerated** from `scout_engine.search`
outputs via the frozen oracle — it does **not** read 0021's contaminated
`wrong_tier1_count` / `span_hit_rate_primary` / `gate_catch_rate`. The one deliberate
re-map (path-only right-file → `RIGHT_FILE_WRONG_SPAN`) lives only in the eval
classifier; `metrics.py` is untouched.

## Instrument-hardening discovery (recorded)

The Scout-only integration tests initially reused the Deep-oriented
`_live_stack_available`, which requires **Deno** (the Tier-2 WASM sandbox) and the Deep
driver model — both **irrelevant to a Scout probe**. On this host (Deno absent, Scout
served) that **false-skipped** a Scout-capable run. Fixed additively with
`scout_stack_available()` (fastcontext + `rg` + a reachable Scout endpoint; no Deno, no
Deep model). With it, the four integration tests **run live** here rather than skipping
— the exact "a skip must not mask availability" concern that motivated the preflight
gate, in reverse.

## Named follow-ups

1. **The operator SWE-bench run** (the real deliverable): stand up the SWE-bench repos,
   run `run_locate_probe` + the reformulation probe over the stratified 38 with
   `HARPYJA_REQUIRE_LIVE_STACK=1` (preflight fails loud if the stack is down). This
   settles `RETRIEVAL_FUNDAMENTAL` vs `BENCHMARK_UNREPRESENTATIVE`.
2. **The fix spec, named by branch:** if `RETRIEVAL_FUNDAMENTAL` → a finder-capability
   spec (larger/different finder); if `BENCHMARK_UNREPRESENTATIVE` → a dataset/query
   spec (distill-before-Scout, or a terse-query benchmark truer to Harpyja's target).
3. **Trajectory turn-count schema validation:** `count_turns` assumes one JSONL record
   per turn; the live smoke produced plausible counts (3–7, within `max_turns`), but
   pin it against FastContext's documented trajectory schema before trusting it beyond a
   labeled estimate.
