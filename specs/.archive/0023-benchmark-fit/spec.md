---
id: "0023"
title: "benchmark-fit:"
status: closed
created: 2026-07-05
authors: [claude]
packages: [harpyja/eval]
related-specs: [0020-oq2, 0021-escalation-rate-0, 0022-tier-1]
---

# Spec 0023 — benchmark-fit: reformulation probe + representativeness verdict

## Why

Spec 0022 landed a provisional `RETRIEVAL_FUNDAMENTAL` finding (Scout's failure is
recall, not span precision) but **explicitly could not exclude
`BENCHMARK_UNREPRESENTATIVE`**. Its discriminator — the query-reformulation probe run
on *real* multi-paragraph GitHub-issue text — was operator-gated, and on the terse
legacy fixtures `delta_empty ≈ 0` **by construction** (there is nothing to distill from
a one-word query). So the branch that would flip the whole finding was never actually
tested.

Two expensive commitments hang off that unanswered branch:

1. The **N=38 SWE-bench confirmation run** (0022 follow-up 1a).
2. A **finder swap** (replace the 4B) if `RETRIEVAL_FUNDAMENTAL` stands.

Both are premature until we resolve *which experiment is even correct*: is Scout's
empty-rate a **localization capability wall**, or an **artifact of SWE-bench's
multi-paragraph issue prose**, which is nothing like Harpyja's founding target (terse
NL queries over undocumented legacy code)? The reformulation probe is a handful of
cases and is **logically upstream** of the N=38 run — it decides whether N=38 measures
Scout's real capability or a benchmark mismatch. Cheap-before-expensive: spend one
bounded probe to pick the correct next spec before spending the confirmation run or a
finder replacement.

This also surfaces a standing, never-decided question: **SWE-bench was chosen for
convenient patch-derived ground truth, not for representativeness** of Harpyja's
proprietary-legacy / terse-query target. The project may be about to discover it
measured its ten-spec OQ2 arc against the wrong yardstick — which is the eval discipline
working one level up: questioning not just the gate or the finder, but whether the
benchmark fits the tool's purpose. Better one cheap probe than swapping out a 4B finder
that may be perfectly adequate for the terse-query legacy job it was actually built for.

Refs: 0020 (OQ2 DEFERRED), 0021 (empty-dominant; two-axis MECE finding template), 0022
(`RETRIEVAL_FUNDAMENTAL` provisional + AC9 representativeness + the
`locate_probe.run_reformulation_probe` seam — which this spec **extends**, see AC7).

## What

A **measure-don't-fix, cheap-before-expensive** diagnostic. Scout-only, offline, over a
**bounded** case set — explicitly **NOT** the full N=38. The deliverable is a **typed,
two-axis benchmark-fit verdict** that decides the *next* spec. **No SUT change** — all
code additive under `harpyja/eval/`; SUT (`harpyja/scout/`, `harpyja/orchestrator/`)
byte-frozen. The 0022 `run_reformulation_probe` is a starting seam but is **extended**,
not reused as-is (AC7).

**Two orthogonal axes, decided by a pre-registered rule (never post-hoc):**

- **Axis 1 — query shape** (the reformulation probe). For each case, run Scout on the
  **raw** multi-paragraph issue text and on a **distilled terse query** for the *same*
  gold span. This is a **within-case paired A/B** — each case is its own control, so
  per-case difficulty cancels. Because the outcome (empty / not-empty) is **binary**, the
  paired test is **McNemar's**: its power lives in the **discordant pairs** (cases that
  flip between arms), not in raw N. The verdict fires only when a paired uncertainty gate
  clears the pre-registered band (AC4); otherwise `INCONCLUSIVE`.
- **Axis 2 — representativeness** (codebase character). Independently assess how far
  SWE-bench issue text + documented-OSS repos sit from Harpyja's target (terse queries,
  undocumented legacy). A structured, pre-registered record (AC5) — because even a clean
  query-shape result can be capped by a benchmark whose *codebases* never resembled the
  target (AC6).

**The distiller (Axis 1's honesty guard) is dual, with asymmetric roles:**

- **Mechanical extraction — PRIMARY, verdict-driving.** A single case-agnostic rule (no
  case-id branching) whose distilled tokens are a **subset of the raw-issue tokens**
  (extraction, never generation). It is therefore **structurally incapable** of injecting
  gold-span vocabulary — it cannot manufacture a false `QUERY_SHAPE`. This structural
  blindness is *why* it drives the verdict.
- **LLM distiller — LABELED, non-primary SENSITIVITY arm.** A more natural reformulation
  under a fixed, pre-registered, issue-text-only prompt, with the token-subset check
  applied post-hoc as a hard reject filter. It **never decides**; it only **disambiguates
  the one case the mechanical arm cannot** — a flat mechanical `delta_empty`, which is
  otherwise "CAPABILITY *or* the extraction rule was too crude." If the LLM arm is *also*
  flat → CAPABILITY is corroborated across a dumb and a smart distiller. If the LLM arm
  moves delta materially → the mechanical rule under-distilled and the truth is
  `QUERY_SHAPE`. Both distillers' outputs (the rule, the pre-registered prompt, and the
  actual distilled query *per case for both arms*) go in the audit trail.

## Pre-registered decision config (declared before the run, in code)

A named, frozen config object (mirrors 0022's `LOW_FILE_BAND` etc.) — the verdict is a
pure function over it, so it cannot be steered after seeing the data:

- `MIN_DISCORDANT_PAIRS` — minimum flip count for Axis 1 to be conclusive, **derived from
  exact-McNemar reachability, not a round guess** (provisional: **8**). Rationale: under
  H0 the discordant pairs are a sign test at p=0.5, so a two-sided exact McNemar can only
  clear α=0.05 once `n_discordant ≥ 6` (6/0 → p=0.031; 5/0 → p=0.063 fails). 8 buys one
  contrary pair of slack (8/0 → p=0.008; 7/1 → p≈0.070 is honestly borderline → still
  `INCONCLUSIVE`). **5 was wrong**: it makes `QUERY_SHAPE` almost unreachable, so every
  run would default to `INCONCLUSIVE` — the small-N trap in reverse (both reviewers, C2).
  OQ1 keeps open whether to raise 8 to a formal target-power floor.
- `DELTA_EMPTY_BAND` — minimum materially-positive `delta_empty` (provisional: 0.20, the
  0022 `MATERIAL_DELTA_EMPTY`), AND the exact two-sided McNemar test must reject at
  α=0.05. Both conditions, not either.
- `REPRESENTATIVE_THRESHOLD` — the pre-registered rule on the Axis-2 structured record
  that flips `representative` → `false` (provisional: `representative = false` iff **both**
  `documentation-density = low` (undocumented, unlike OSS) **and** `target-proxy-validity
  = weak`). Declared before the assessment, not judged at write-time.
- `min_n` — floor on **usable** cases (validated raw arm, AC8), distinct from
  `MIN_DISCORDANT_PAIRS` (provisional: **12**). The bounded set must be sized so it can
  plausibly yield `MIN_DISCORDANT_PAIRS` given the observed discordance rate — an **honest
  consequence** the reviewers forced out: a *binary* paired probe is not as cheap as the
  paired-continuous intuition suggested; reaching 8 flips may need ~15–25 raw cases. That
  is still well below N=38 and Scout-only-cheap — but it is not "a handful," and the spec
  says so rather than pretending otherwise.

## Acceptance criteria

1. **[integration]** The reformulation probe runs on a bounded set of **real long-issue**
   cases (≥ the OQ1 minimum), recording **per-case rows** and aggregates for both
   distiller arms. Scout-only, offline, operator-gated **skip-not-fail** on a host without
   a served stack; hard-fail under `HARPYJA_REQUIRE_LIVE_STACK=1` (reuse 0022's
   `require_live_stack` / `scout_stack_available`).
2. **[unit]** The **mechanical** distiller is **structurally blind**: (a) its output
   tokens are a subset of the raw-issue tokens (a testable property that blocks injecting
   gold-file identifiers absent from the issue); (b) it is a single case-agnostic rule
   with **no** case-id branching; (c) the rule (and the LLM arm's prompt) are
   pre-registered/hashed before the live run. A test pins the subset property and the
   absence of gold-span dependence — cherry-picking is **structurally prevented**, not
   merely asked for. **Symbol-leakage policy (declared, per codex):** the mechanical
   distiller **STRIPS** code-identifier tokens from its candidate set — file paths,
   dotted/CamelCase symbol names, stack-trace frames, and exact error strings — so the
   distilled query is **natural-language shaped**, matching Harpyja's terse-NL target, and
   the probe measures *query-shape*, not a symbol-lookup shortcut. The **raw arm retains
   everything**; every stripped token is **recorded per case** so any identifier the issue
   did contain is auditable rather than a silent confound.
3. **[unit]** `delta_empty` and `delta_file_accuracy` are computed as **paired
   within-case deltas** (raw minus distilled on the *same* case / gold span), from
   retained per-case `(case_id, raw_bucket, distilled_bucket)` pairs — **not** a
   difference of two independent aggregate rates. Verified on a fake-Scout fixture with a
   known per-case outcome. The **discordant-pair count** is recorded.
4. **[doc][unit]** The **Axis-1 verdict** is a pure function over the pre-registered
   config, with an **uncertainty gate** — a total function with **non-overlapping**
   predicates (claude-p): `QUERY_SHAPE` iff `delta_empty >= DELTA_EMPTY_BAND` AND the exact
   two-sided McNemar test rejects at α=0.05 AND `discordant_pairs >= MIN_DISCORDANT_PAIRS`;
   `CAPABILITY` iff the arms are flat AND `discordant_pairs >= MIN_DISCORDANT_PAIRS` (i.e.
   enough power to have *detected* an effect, so flatness is real, not low-power);
   `INCONCLUSIVE` otherwise. The two distinct `INCONCLUSIVE` triggers are **named
   separately** so the branch table stays total: `insufficient_power`
   (`discordant_pairs < MIN_DISCORDANT_PAIRS` or `usable_n < min_n` or McNemar fails to
   reject), `distiller_arm_disagreement` (mechanical vs LLM arms diverge in sign), and
   `axis_signal_disagreement` (`delta_empty` vs `delta_file_accuracy` diverge in sign,
   OQ2). No path silently defaults. Unit-tested on fixtures for each branch and each named
   `INCONCLUSIVE` trigger.
5. **[doc][unit]** The **Axis-2 representativeness verdict** is a **structured record**
   (fields: query-shape, repo-type, documentation-density, codebase-age,
   target-proxy-validity), not prose — as auditable as the delta verdict. It yields a
   `representative: bool` via the pre-registered `REPRESENTATIVE_THRESHOLD`.
6. **[doc][unit]** The **composition rule is two-axis and pre-registered**: Axis 2 can
   qualify/downgrade Axis 1's routing (it is not an inert caveat). The 2×2 is fixed before
   the run — `QUERY_SHAPE × representative` → *add a reformulation layer*; `QUERY_SHAPE ×
   ¬representative` → *build a terse-query benchmark truer to the target first, NOT a
   finder swap*; `CAPABILITY × representative` → *N=38 confirmation + finder-capability
   work*; `CAPABILITY × ¬representative` → *retire SWE-bench as the yardstick*. Unit-tested
   as a total function over both axes.
7. **[unit]** The probe seam is **extended, not merely reused**: `ReformulationResult`
   (currently `n, raw_empty_rate, distilled_empty_rate, delta_empty` — a difference of
   aggregate rates, which AC3 forbids) gains per-case pair rows, `delta_file_accuracy`,
   the discordant-pair count, and the second (LLM) arm. A test pins the new per-case
   structure; the frozen SUT is untouched (extension lives in `harpyja/eval/`).
8. **[integration][unit]** Each case's **raw arm is verified to actually be raw**: a
   per-case precondition (length / paragraph-structure check) asserts `case.query` carries
   the full multi-paragraph issue body, recorded per case. A case failing it is excluded
   from `usable_n` (and cannot silently produce a `delta ≈ 0` that masquerades as
   `CAPABILITY`). If `usable_n < min_n`, the verdict is `INCONCLUSIVE`.

## Out of scope

- **The N=38 confirmation run** — gated on the `CAPABILITY` verdict from this spec.
- **Fixing Scout / swapping the finder** — a downstream spec, *named* by the 2×2 verdict.
- **Building a new / representative benchmark** — *named* by a `¬representative` verdict,
  not built here.
- **OQ2 / gate calibration** — blocked upstream on this same question.

## Open questions

1. **Minimum case count / discordant pairs.** OQ1 is answered in the config as
   `MIN_DISCORDANT_PAIRS` (provisional **8**, from exact-McNemar reachability) rather than a
   raw-N floor, *because* the probe is a **within-case paired A/B over a binary outcome** →
   the effective sample size is the **discordant-pair count** (McNemar), not N. Below
   `MIN_DISCORDANT_PAIRS` the verdict is `INCONCLUSIVE(insufficient_power)` and **names the
   discordant-pair count still needed**. **Remaining sub-question:** should 8 (the bare
   reachability floor, one contrary pair of slack) be raised to a formal **target-power**
   floor at `DELTA_EMPTY_BAND` (e.g. 80% power to detect a 0.20 shift), which would push it
   higher (~12–15 discordant pairs) and correspondingly raise the raw-case count? The
   reachability floor prevents a *structurally impossible* `QUERY_SHAPE`; a power floor
   additionally prevents an *underpowered* `CAPABILITY`. Decide before the live run.
2. **`delta_file_accuracy`: load-bearing or diagnostic?** It is recorded per-case (AC3),
   but the Axis-1 rule (AC4) currently routes on `delta_empty` only. Provisional: it is
   **diagnostic + feeds the "arms/axes disagree → INCONCLUSIVE" clause** (sign
   disagreement between `delta_empty` and `delta_file_accuracy` is one definition of
   "mixed"). Confirm whether it should be promoted into the primary rule.

## Revision log

- **2026-07-05 (post-review).** Both aux reviewers (`codex`, `claude-p`) returned
  `changes-requested`; concerns C1–C6 folded in. **C1 (distiller honesty guard)** →
  dual distiller: mechanical extraction (token-subset, case-agnostic) as the
  structurally-blind PRIMARY, LLM as a labeled non-primary sensitivity arm that
  disambiguates a flat mechanical delta (operator decision). **C2** → uncertainty gate
  on the routing (McNemar / discordant pairs; paired CI must exclude the band), pinned in
  the pre-registered config. **C3** → min-N, bands, and the "mixed" rule moved out of Open
  Questions into the config + ACs; AC4/AC6 reconciled to one materiality rule. **C4
  (code-verified)** → AC7 makes "extend `ReformulationResult`," not "reuse," explicit
  (the current form is a forbidden difference-of-aggregate-rates with no per-case pairs).
  **C5** → AC8 raw-arm provenance precondition (a null must not be uninterpretable).
  **C6** → AC5/AC6 make representativeness a first-class **second axis** that can cap the
  query-shape routing via a pre-registered 2×2 composition rule (operator decision).
- **2026-07-05 (re-review).** `claude-p` → **approve-with-comments** (all six resolved);
  `codex` → changes-requested with P2/P5 resolved. Quorum met. Three convergent residuals
  folded in before marking reviewed: (1) `MIN_DISCORDANT_PAIRS` 5 → **8**, derived from
  exact-McNemar reachability — 5 made `QUERY_SHAPE` almost unreachable (hollow-verdict /
  reverse small-N trap); (2) the **symbol-leakage policy** AC2 required is now actually
  stated (mechanical arm strips paths/symbols/traces/error-strings, raw arm retains, all
  recorded); (3) `min_n` given a value (**12**) distinct from the discordant floor, and
  AC4's `INCONCLUSIVE` split into three **named, non-overlapping** triggers
  (`insufficient_power` / `distiller_arm_disagreement` / `axis_signal_disagreement`). The
  honest cost — a binary paired probe may need ~15–25 raw cases, not "a handful" — is now
  written into the config rather than glossed.
