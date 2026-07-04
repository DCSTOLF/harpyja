---
spec: "0021"
status: planned
strategy: tdd
---

# Plan — 0021 escalation_rate=0 (metric-integrity diagnostic)

## Approach

This is a **measurement/diagnostic** spec in the 0019/0020 lineage. The SUT
(`harpyja/orchestrator/` tiers/gate/matrix/judge) is **FROZEN**. All new code is
additive under `harpyja/eval/`. The PRIMARY deliverable is a recorded typed
finding (`specs/0021-escalation-rate-0/findings.md`), not a feature.

The leading hypothesis is `accounting = CORRECT_NO_ESCALATION`: `escalation_rate`
is derived (`metrics.py:129`, `_escalated(o) = 2 in o.tiers_run`), there is no
independent counter, so 0.0 means no case reached Tier-2 — not a lost count.
Under that hypothesis there is **NO production code change**: AC1/AC2 are
characterization/PIN tests over frozen behavior + a new *additive* eval-side
trigger classifier; AC3 is a skip-not-fail micro-run; AC4/AC5 are the doc.

A SUT/metric code change is permitted **only** if Step 1's coupling test goes RED
against the current code — i.e. a genuine accounting bug — in which case it lands
in `harpyja/eval/metrics.py` (never `orchestrator/`) with the coupling test as
its regression guard (the `ACCOUNTING_BUG` branch of AC4).

Feasibility is pinned FIRST (Step 0): the 0020 per-case dump is already verified
**absent** (`eval_work/reports/oq2_{fast,incumbent}/` empty; `eval_work/`
gitignored; secondaries exist only in transcript). So AC3 degrades to a LABELED
ESTIMATE up front — no fabricated recorded 3.3h split.

Routing facts confirmed against the tree (AC2/AC4 hinge on these):
`plan_ladder("auto","point",True) → [0,1,2]` (Tier-2 **on-ladder**, so wrong /
honest-empty Tier-1 *should* escalate — `escalation_rate=0` therefore genuinely
narrows the fate to gate-false-acceptance vs Deep-degraded/OOM vs accounting
bug); `plan_ladder("fast","point",True) → [0,1]` (no Tier-2 — the
`NO_ESCALATION_PATH` fixture). `tier1_correct(())` is `False` (honest-empty is a
"wrong" case that should escalate under auto/point).

## Test-first sequence

### Step 0 — Pin the feasibility precondition (INVESTIGATION, no code)
- Path the actual 0020 per-case dump on disk. VERIFIED at planning time:
  `eval_work/reports/oq2_fast/` and `oq2_incumbent/` are EMPTY; the quoted
  secondaries (span_hit_rate_primary=0.2, catch_rate, wrong=5, empty=33) are in
  NO committed file.
- Record present/absent into `findings.md` under a "Feasibility" heading:
  **ABSENT** → AC3 is a labeled sample estimate, not a corroborated split; AC4's
  3.3h attribution is anchored only by the micro-run wall-clock × 38 cases.
- No test. Gates AC3/AC4 honesty. Delegatable (mechanical search).

### Step 1 — tiers_run⇄escalation_rate coupling (RED)
- Extend `harpyja/eval/test_metrics.py` (reuse existing outcome/`Span` helpers;
  place beside `test_escalation_rate_counts_tier2_over_all_auto_cases`):
  - `test_escalation_rate_counts_case_reaching_tier2` — a single `tiers_run=(0,1,2)`
    case yields rate `1.0`: reaching Tier-2 *increments the numerator*.
  - `test_escalation_rate_ignores_tier1_terminal_case` — a single `tiers_run=(0,1)`
    case yields rate `0.0`: a Tier-1-terminal case does *not* increment it.
  - `test_escalation_rate_zero_when_no_case_reaches_tier2` — mix of `(0,)`,`(0,1)`
    only ⇒ `0.0`; reproduces the 0020 result from injected fixtures (pins that
    `0.0` is a real no-escalation, not a lost count).
- Tests fail: they are new; this is the novel COUPLING assertion absent from the
  existing plain-rate test.

### Step 2 — Coupling holds against frozen metric (GREEN / PIN)
- **No production change expected.** `escalation_rate` (`metrics.py:129`) already
  couples to `tiers_run`; Step-1 tests pass against the frozen SUT — a
  characterization/PIN of `CORRECT_NO_ESCALATION`.
- **Only if Step 1 goes RED:** genuine `ACCOUNTING_BUG` → minimal fix in
  `harpyja/eval/metrics.py`, Step-1 tests become the regression guard, and AC4's
  accounting axis flips to `ACCOUNTING_BUG` (secondaries re-derived).

### Step 3 — Four-way escalation-trigger truth table (RED)
- Add `harpyja/eval/test_escalation_trigger.py`. Import the (not-yet-existing)
  classifier from `harpyja.eval.escalation` and derive every ladder input by
  CALLING `harpyja.orchestrator.matrix.plan_ladder(...)` — never re-typing the
  routing rule (single-source-of-truth):
  - `test_classify_escalation_wrong_tier1_deep_available_escalates` — wrong Tier-1,
    gate rejects, Deep available, `plan_ladder("auto","point",True)`→[0,1,2]
    ⇒ escalation `True`, fate `NOT_APPLICABLE`.
  - `test_classify_escalation_honest_empty_follows_ladder` — empty Tier-1
    (`tier1_correct(())==False`), gate rejects, Deep available, point-auto ladder
    ⇒ escalates, fate `NOT_APPLICABLE`.
  - `test_classify_escalation_gate_accept_no_escalation` — wrong Tier-1 but gate
    accepts ⇒ escalation `False`, fate `GATE_FALSE_ACCEPTANCE`.
  - `test_classify_escalation_deep_degraded_suppresses_escalation` — wrong Tier-1,
    gate rejects, Deep unavailable (`deep-degraded:<cause>`) ⇒ escalation `False`,
    fate `DEEP_DEGRADED_OR_UNAVAILABLE`.
  - `test_classify_escalation_no_tier2_on_ladder_is_no_path` — fast-mode ladder
    `plan_ladder("fast","point",True)`→[0,1] (no 2) ⇒ escalation `False`, fate
    `NO_ESCALATION_PATH`.
  - `test_classify_escalation_ladder_sourced_from_plan_ladder` — guards that the
    test's ladder input equals `plan_ladder(...)` (regression against duplicating
    the matrix).
- Tests fail: `harpyja/eval/escalation.py` does not exist (import error at
  collection).

### Step 4 — Additive trigger classifier (GREEN)
- Implement `harpyja/eval/escalation.py` (additive; touches no `orchestrator/`):
  - `class WrongCitationFate(enum.Enum)` with `GATE_FALSE_ACCEPTANCE`,
    `NO_ESCALATION_PATH`, `DEEP_DEGRADED_OR_UNAVAILABLE`, `NOT_APPLICABLE`.
  - `classify_escalation(*, tier1_correct: bool, gate_rejected: bool,
    deep_available: bool, ladder: list[int]) -> tuple[bool, WrongCitationFate]`
    — pure function taking the ladder as an argument (does NOT call/duplicate
    `plan_ladder`). Minimal logic to pass:
    - `2 not in ladder` → `(False, NO_ESCALATION_PATH)`
    - `tier1_correct` → `(False, NOT_APPLICABLE)` (gate accepts a correct Tier-1)
    - not `gate_rejected` → `(False, GATE_FALSE_ACCEPTANCE)`
    - `gate_rejected and not deep_available` → `(False, DEEP_DEGRADED_OR_UNAVAILABLE)`
    - else → `(True, NOT_APPLICABLE)`
- All Step-3 tests pass.

### Step 5 — Refactor (optional)
- If Steps 1/3 duplicate outcome-building, hoist a shared fixture builder; keep
  `test_metrics.py`'s local helper. All tests still pass. `ruff` clean.

### Step 6 — Instrumented ≤2-case micro-run (RED, integration)
- Add `harpyja/eval/test_escalation_microrun.py`, marked
  `@pytest.mark.integration`, skip-not-fail (`pytest.skip(_NEEDS_STACK)` when
  served models / SWE fixtures absent — mirror `test_swebench_integration.py`):
  - `test_escalation_microrun_reproduces_rate_with_per_tier_timing` — run ≤2 auto
    cases through the *additive* timing wrapper; assert (a) `escalation_rate` over
    the collected `CaseOutcome`s is reproduced from `tiers_run`, and (b) a per-tier
    timing mapping `{scout, judge, deep}` is returned and explicitly LABELED
    `estimate` (granularity absent from any persisted dump).
- Tests fail: the micro-run wrapper `harpyja/eval/escalation_microrun.py` does not
  exist (collection import error). Under CI-without-models it will SKIP once the
  import resolves.

### Step 7 — Additive per-tier timing wrapper (GREEN, integration)
- Implement `harpyja/eval/escalation_microrun.py`: an *additive* wrapper over the
  existing public runner that drives ≤2 cases and attributes wall-clock to
  Scout/judge/Deep phases at the eval boundary. **No edit to frozen orchestrator
  internals**; total is recorded wall-clock, per-tier split is a labeled sample
  estimate (corroborate against the 0020 dump only if it ever reappears — Step 0
  says it is absent).
- Step-6 test passes locally with models; SKIPS in CI.

### Step 8 — Record the typed finding (DOC)
- Author `specs/0021-escalation-rate-0/findings.md` (precedent:
  `specs/.archive/0015-oq2/live-run-findings.md`). Record the TWO orthogonal
  MECE axes + verdict, gated on Steps 0/1/6 evidence:
  - **accounting** ∈ `{ACCOUNTING_BUG | CORRECT_NO_ESCALATION}` — expected
    `CORRECT_NO_ESCALATION` (Step 2 PIN passed, no prod change).
  - **wrong_citation_fate** ∈ `{GATE_FALSE_ACCEPTANCE | NO_ESCALATION_PATH |
    DEEP_DEGRADED_OR_UNAVAILABLE | NOT_APPLICABLE}` for the 5 wrong Tier-1 cases,
    reconciled with the 33 honest-empty (which escalate by `plan_ladder`
    point-auto=[0,1,2]); on this host `qwen3-coder:30b` OOM makes
    `DEEP_DEGRADED_OR_UNAVAILABLE` a live candidate.
  - **3.3h attribution** — labeled estimate (Scout FastContext × 38 vs judge vs
    Deep vs provisioning), anchored by the Step-6 micro-run wall-clock, NOT a
    fabricated recorded split (dump absent per Step 0).
  - **AC5 metric-trust verdict** — which 0020 secondaries (span_hit_rate_primary,
    gate_catch_rate, wrong/empty counts) are trustworthy for the next spec
    (Scout Tier-1 localization) and which are contaminated; note
    `gate_false_escalation` was `null` (correct_tier1_count=0) — a DEFERRED
    independent of this spec.

## Delegation

- Step 0 → delegate to a search/investigation agent (mechanical dump-pathing).
- Steps 3–4 (trigger classifier + tests) → delegate to a python-tdd implementer
  (self-contained pure function, RED→GREEN, no live models).
- Step 1 → keep local; if it goes RED that is the ACCOUNTING_BUG decision, not a
  routine GREEN — surface, don't auto-fix.
- Steps 6–7 (integration micro-run) → keep with an owner who has served models;
  skip-not-fail means CI cannot validate the GREEN.
- Step 8 (findings.md) → NOT delegated: cross-evidence judgment (axes + verdict).

## Risks

- **Missing 0020 dump (confirmed).** → Step 0 records ABSENT; AC3/AC4 are LABELED
  estimates anchored by the micro-run wall-clock, never a fabricated recorded
  3.3h split or re-quoted secondaries dressed as measured.
- **Coupling test goes RED (accounting bug).** → Fix in `harpyja/eval/metrics.py`
  only, Step-1 tests are the regression guard, AC4 flips to `ACCOUNTING_BUG`,
  secondaries re-derived; `orchestrator/` stays frozen.
- **Deep OOM on this host (`qwen3-coder:30b`).** → The micro-run may itself
  surface `deep-degraded:<cause>`; that is a valid
  `DEEP_DEGRADED_OR_UNAVAILABLE` observation, not a test failure — Step 6 is
  skip-not-fail and asserts rate reproduction, not Deep success.
- **Per-tier granularity not exposed by the frozen runner.** → Wrapper attributes
  time at the eval boundary and labels the split `estimate`; total stays
  wall-clock-anchored. No orchestrator edit.
- **SUT-frozen / TDD-hook ordering.** → All new code under `harpyja/eval/`; each
  prod file created AFTER its test file; classifier reads `plan_ladder` but never
  duplicates the table.
