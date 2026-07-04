# Findings — Spec 0021 (escalation_rate=0)

A metric-integrity diagnostic. The recorded typed finding is the primary deliverable.

## TL;DR — the typed finding (two orthogonal axes, MECE)

| Axis | Value | Basis |
|------|-------|-------|
| **accounting** | **`CORRECT_NO_ESCALATION`** | `escalation_rate` is derived from `tiers_run` (no rival counter); coupling PINNED by tests; no production change. `escalation_rate=0` is a faithful no-escalation, not a lost count. |
| **wrong_citation_fate** (the 38 point cases) | **33 empty → `NO_ESCALATION_PATH` (confirmed)** · **5 wrong-content → `GATE_FALSE_ACCEPTANCE` \| `DEEP_DEGRADED_OR_UNAVAILABLE` (undetermined; dump absent)** | Frozen `_locate_auto` code reading + the vanished per-case dump. |

**The 3.3h-vs-escalation_rate=0 contradiction dissolves:** the time sink is **Scout's
FastContext exploration × 38 cases**, not Deep. `escalation_rate=0` is *correct* — Deep barely
or never ran — because the auto path structurally could not escalate most cases. **The DEFERRED
verdict from 0020 is unchanged** (`correct_tier1_count=0` is an independent direct count).

---

## Feasibility (T0) — the 0020 per-case dump is **ABSENT**

**Resolution of review C1 / Open Question 2.** The spec's cheap method ("resolve from the
existing 0020 partial dump + per-case trajectory/timing") was checked against disk:

| Path | State |
|------|-------|
| `eval_work/reports/oq2_fast/` | **empty** (`total 0`) |
| `eval_work/reports/oq2_incumbent/` | **empty** (`total 0`) |
| `eval_work/reports/oq2_smoke/sweep.json` | present (13 KB) — the **G1 smoke**, 1 case, **not** the G2 instruct pass |
| quoted G2 secondaries (`span_hit_rate_primary=0.2`, `wrong_tier1_count=5`, `empty=33`, `escalation_rate=0`, 3.3h) | **in no committed file** — session transcript only |

`eval_work/` is gitignored (machine-local); the G2 per-case events were never committed and are
no longer on disk. **Consequence (honesty gate):** the per-case wall-clock cannot be
*recovered*, only *estimated* (T6 micro-run × 38), and must be labeled an estimate — never a
recorded 3.3h split. Persisted 0020 timing was in any case only case-level `latency_ms`
(`runner.py:190,229`) bucketed by terminal tier, not the Scout/judge/Deep decomposition AC3
asks for.

**What the surviving smoke dump corroborates.** `oq2_smoke/sweep.json` (schema `0014/1`,
threshold 0.6 / top_n 3, single case astropy-12907): `escalation_rate.mean = 1.0` — the auto
ladder **did reach Tier-2** there; `gate_catch_rate = None`, `gate_false_escalation = None`
(zero denominators); **no** `per_tier_latency_ms` key. So the escalation path is wired and
*can* fire — the G2 pass's `escalation_rate=0` is a genuine per-pass signal, not a structural
"Deep never connected."

---

## Accounting axis (T1/T2) — **`CORRECT_NO_ESCALATION`**

`escalation_rate` is **derived**: `metrics.escalation_rate = mean(2 in o.tiers_run)` via
`_escalated` (`harpyja/eval/metrics.py:126,129`). There is **no independent escalation
counter** that could disagree with `tiers_run` — the classic "two sources drift" bug locus does
not exist. Three coupling tests (`test_metrics.py`,
`test_escalation_rate_counts_case_reaching_tier2` / `_ignores_tier1_terminal_case` /
`_zero_when_no_case_reaches_tier2`) PIN that a Tier-2 case increments the numerator, a
Tier-1-terminal case does not, and a no-Tier-2 population yields exactly `0.0`. **All pass
against the frozen metric — no `ACCOUNTING_BUG`, no production change.** `escalation_rate=0` is
a faithful measurement.

## Wrong-citation fate axis (T3/T4 + frozen-SUT code reading)

Over the G2 point subset, `correct_tier1_count=0`: every point case had a wrong-or-empty
Tier-1. Reading the **frozen** `_locate_auto` (`harpyja/orchestrator/locate.py:114-197`) gives
each case's structural fate:

- **Empty Tier-1 (the 33 cases) → `NO_ESCALATION_PATH` — CONFIRMED.** `_locate_auto:161-165`
  routes an empty Scout result to `_honest_empty`, which is gate-**skipped** ("nothing to
  score") and returns `tiers_run=[0,1]` — its docstring is explicit: *"Never escalates — honest
  'nothing found'."* So the majority of the subset **could not escalate by design**, regardless
  of Deep. This is the dominant reason `escalation_rate=0`. *(This corrects the plan's AC2
  assumption that honest-empty escalates; the classifier + `test_escalation_trigger.py` were
  fixed to pin the actual frozen behavior — a `classify_escalation(tier1_empty=True, …)` →
  `NO_ESCALATION_PATH`.)*
- **Wrong-content Tier-1 (the 5 non-empty cases) → `GATE_FALSE_ACCEPTANCE` |
  `DEEP_DEGRADED_OR_UNAVAILABLE` — UNDETERMINED.** For a non-empty citation the gate runs
  (`_locate_auto:173`); on a pass it terminates `[0,1]` (false-acceptance if the citation was
  wrong), on a reject it calls `_run_deep`, which — on a `DeepUnavailable`/OOM — **falls back to
  Scout with a `deep-degraded:<cause>` note and `tiers_run` stays `[0,1]`** (`locate.py:353-359`).
  Both terminate without Tier-2, both consistent with `escalation_rate=0`. Distinguishing them
  needs the per-case `deep-degraded` notes (**dump gone**) or the T6 micro-run with served
  models (**skips without a live stack**). 0020's recorded `qwen3-coder:30b` OOM makes
  `DEEP_DEGRADED_OR_UNAVAILABLE` plausible; a completed 3.3h pass on `qwen3:8b` with no crash
  makes `GATE_FALSE_ACCEPTANCE` (gate passed wrong cites, Deep never attempted) equally
  plausible. **Honest verdict: undetermined, resolvable only by re-instrumentation.**

The instrument to resolve it is shipped: `classify_escalation` (`harpyja/eval/escalation.py`)
maps `(tier1_empty, tier1_correct, gate_rejected, deep_available, ladder)` → `(will_escalate,
WrongCitationFate)`, and `run_escalation_microrun` captures per-case `deep-degraded` + timing on
a live run.

## 3.3h attribution (T6) — labeled ESTIMATE (dump absent)

With `escalation_rate=0`, Deep contributed ~0 wall-clock. The gate/judge ran only for the ≤5
non-empty cases (`gate_triggered` requires non-empty Tier-1), so judge time is bounded and
small. That leaves **Scout's FastContext exploration as the sink**: all 38 point cases run a
full multi-turn Read/Glob/Grep loop with the 4B model *before* terminating at Tier-1 — and the
33 honest-empty cases are typically the **slowest** (the agent explores to its turn budget and
still finds nothing). 3.3h / 38 ≈ **~5.2 min/case of Scout exploration** — the labeled estimate,
consistent with `escalation_rate=0` (no Deep) and the frozen ladder (Scout runs fully on every
case). This is an estimate, not a recovered split: the per-tier granularity exists in no
persisted dump, and the T6 live micro-run that would corroborate it skips without served models.

## Metric-trust verdict (T8, AC5) — for the next spec (Scout Tier-1 localization)

| 0020 secondary | Trust | Why |
|----------------|-------|-----|
| `escalation_rate = 0` | ✅ **trustworthy** | Derived + coupling-pinned; and now *structurally explained* (33 honest-empty can't escalate; 5 wrong either accepted or deep-degraded). The contradiction is resolved. |
| `correct_tier1_count = 0` | ✅ **trustworthy** | Direct count; the load-bearing DEFERRED; independent of this finding (0020 astropy span-mismatch evidence). |
| `gate_false_escalation = null` | ✅ **trustworthy** | Zero denominator by definition (`correct_tier1_count=0`). |
| `wrong_tier1_count = 5` | ❌ **contaminated / unverifiable** | Dump gone, and **inconsistent with the aggregate metric**: `metrics.gate_catch_rate` counts empty Tier-1 as wrong, so `aggregate.wrong_tier1_count` over 38 point cases with `correct=0` would be **38, not 5**. The quoted "5" is a different lens (non-empty-but-wrong content), not `aggregate.wrong_tier1_count`. |
| `span_hit_rate_primary = 0.2`, `gate_catch_rate` | ❌ **contaminated / unverifiable** | Not in any committed file; cannot be reproduced. |

**Directive for the next spec:** treat `escalation_rate`, `correct_tier1_count`, and
`gate_false_escalation=null` as solid; **regenerate** `wrong_tier1_count` / `span_hit_rate_primary`
/ `gate_catch_rate` from a fresh instrumented run (do not inherit the transcript figures). When
`correct_tier1_count > 0` becomes achievable, the empty-vs-wrong split (33/5) should be
recomputed with the empty/non-empty lens made explicit.

## Does the finding change the DEFERRED verdict? — **No** (Open Question 3)

`correct_tier1_count=0` is an independent direct count; the accounting axis is
`CORRECT_NO_ESCALATION` and the fate axis is about *why the wrong cases didn't escalate*, not
about Tier-1 correctness. If a future live micro-run resolves the 5 cases to
`GATE_FALSE_ACCEPTANCE`, that is a **material, separate** gate-quality lead (a gate passing wrong
citations — the mirror of G2's false-escalation target) worth its own spec, but it does not
disturb the 0020 DEFERRED.

## Named follow-ups

1. **Scout Tier-1 span-level localization on SWE-bench** (the pre-existing next spec) — the real
   blocker; `correct_tier1_count=0`.
2. **Resolve the 5-wrong-case fate** with a served-model T6 micro-run (`run_escalation_microrun`
   + `deep-degraded` capture) — distinguishes `GATE_FALSE_ACCEPTANCE` from
   `DEEP_DEGRADED_OR_UNAVAILABLE`.
3. **If false-acceptance:** a gate-false-acceptance investigation (distinct from G2's
   false-escalation target).
4. **Deep co-residency budget** (0020 D9-a): the `qwen3-coder:30b` OOM that makes
   `DEEP_DEGRADED_OR_UNAVAILABLE` live on this host.
