---
id: "0022"
title: "Tier-1"
status: closed
created: 2026-07-04
authors: [claude]
packages: [harpyja/eval]
related-specs: [0011-citation-shape, 0012-path-prefix, 0020-oq2, 0021-escalation-rate-0]
---

# Spec 0022 — Tier-1

> Scout Tier-1 locate-accuracy on SWE-bench (diagnosis, not fix)

## Why

OQ2 was DEFERRED in spec 0020 because Scout Tier-1 produced **0 correct citations**
across the 38 SWE-bench point cases; spec 0021 then showed that **empty-Tier-1
dominates** (~33/38) and that the ladder was structurally inert (honest-empty never
escalates). The bottleneck is **Scout locate-accuracy**, which sits upstream of
everything OQ2 tried to calibrate — the gate, the judge, the escalation threshold
all measure a signal that Scout never produces.

This spec **CHARACTERIZES that failure precisely enough to decide its nature**:

- **FIXABLE** — span-precision refinement within a correctly-found file (Scout finds
  the right file but misses the exact span), or
- **FUNDAMENTAL** — the 4B finder cannot localize long-issue→span queries at all
  (it doesn't even find the right file), or
- **BENCHMARK-UNFIT** — Scout could localize a *terse* query fine, but SWE-bench's
  multi-paragraph issue text is the wrong-shaped input (a query-shape failure, not a
  finder-capability failure).

It does **NOT** fix Scout; the fix is *named* by the diagnosis. The frame mirrors
spec 0020: a **branching typed finding** is the deliverable, not a feature.

Refs: 0020 (DEFERRED, 3-repo spot-check), 0021 (empty-dominant distribution,
`wrong_tier1_count` contaminated, metric-trust verdict), the eval oracle
(patch-derived gold spans; `metrics.span_hit_kind` — `"line"` / `"file"` / `None`),
spec 0011 (file-level/path-only citation shape), spec 0012 (suffix-recovery), and the
`harpyja/scout/` client.

## What

Produce a clean, **mutually-exclusive** failure distribution over the point cases,
then score it at two granularities and route to exactly one typed finding.

### Citation normalization (runs BEFORE classification)

Scout's raw output is normalized once, at the eval boundary, before any case is
classified — so the taxonomy scores Scout's *effective* citations, not raw noise:

- **Suffix-recovery (spec 0012) is applied first** — a path resolved by suffix
  recovery counts as a real citation; the recovery hit/drop is recorded (AC4), not
  silently folded in.
- **Malformed / unresolvable citations are dropped and counted separately**
  (`normalization_dropped`) — they are never silently reclassified as `EMPTY` or
  `WRONG_FILE`; a case that is EMPTY *only after* dropping malformed output is
  recorded distinctly from a case Scout returned nothing for.
- **File-level (line-less, `start_line=end_line=None`) citations** are retained as
  path-only citations (spec 0011 shape), and are handled explicitly by the taxonomy
  below (they are NOT a span localization).

### The 4-way taxonomy (per case; precedence-ordered → MECE)

A case can carry multiple citations of mixed quality, and the oracle is any-citation
× any-gold-span. To stay mutually-exclusive-and-total, each case takes the **single
best** bucket by this strict precedence — **`CORRECT > RIGHT_FILE_WRONG_SPAN >
WRONG_FILE > EMPTY`**:

- **CORRECT** — some normalized citation has a **`"line"`-kind** hit (overlapping
  line ranges, same file) against some gold span. This is a true span localization.
- **RIGHT_FILE_WRONG_SPAN** — no line-overlap, but some citation is **in a gold
  file**. This deliberately includes two sub-cases (both recorded as sub-flags):
  - a **path-only / file-level** citation in a gold file (oracle `span_hit_kind ==
    "file"`) — *reclassified out of the oracle's coarse primary-hit*: for THIS
    diagnostic a path-only citation has found the file but **not** the span; and
  - a lined citation in the gold file whose lines miss gold, with a
    **`within_window`** sub-flag when the miss is within `proximity_window_lines`
    (the secondary-metric zone) vs beyond it — so no case falls between buckets.
- **WRONG_FILE** — at least one normalized citation, but **none** lands in any gold
  file (retrieval failure).
- **EMPTY** — no normalized citation at all (recall failure).

> The one deliberate departure from the frozen oracle is scored, not silent: the
> oracle's `span_hit_primary` counts a path-only right-file hit as a localization;
> this eval **re-maps** it to `RIGHT_FILE_WRONG_SPAN` because the whole diagnostic
> axis is "found the file" vs "found the span." The re-map lives in the additive eval
> classifier and never touches `metrics.py`.

### Two-granularity scoring

- **FILE-level accuracy** = fraction of cases in `CORRECT ∪ RIGHT_FILE_WRONG_SPAN`
  (Scout put a citation in a gold file, span aside).
- **SPAN-level accuracy** = fraction of cases that are `CORRECT` (line-overlap).
- **The gap `G = FILE-level − SPAN-level` is a first-class reported metric.** A large
  gap is the precision-fixable signal; a low FILE-level is the fundamental-gap signal.

Also record: **empty-rate**; **turns-used distribution** (does Scout give up early or
exhaust `max_turns`?); **suffix-recovery hit/drop** counts (spec 0012 instrument);
and `normalization_dropped`.

### The query-reformulation probe (labeled non-primary)

On a small labeled subset, run Scout on a **distilled one-line query** alongside the
raw multi-paragraph issue text and record the **empty-rate delta**. This is the
**discriminator** between two otherwise-identical empty-dominant outcomes: if
distilling materially cuts the empty-rate, the failure is **query-shape**
(→ `BENCHMARK_UNREPRESENTATIVE`); if it doesn't, it's **finder capability**
(→ `RETRIEVAL_FUNDAMENTAL`). It is labeled non-primary and its cases are excluded
from the regenerated baseline distribution so it cannot contaminate it.

### The typed-finding decision rule (AC5)

Over the regenerated point-case distribution, with `F`=file-level acc, `S`=span-level
acc, `E`=empty-rate, `G = F − S`, `Δempty`=probe empty-rate reduction. Bands are
**pre-declared** (provisional; the per-case rows are the auditable ground truth), and
evaluated in this order:

1. **BENCHMARK_UNREPRESENTATIVE** — empty-dominant / low-`F`, **but** the probe shows
   `Δempty` materially positive (distilled query localizes) **OR** the AC6
   representativeness judgment concludes the issue text is pathologically long vs
   Harpyja's terse target → the failure is query-shape, routes to a **dataset/
   benchmark** spec, not a Scout fix. (This is 0020's typed-DEFERRED precedent: name
   the real blocker, don't force a downstream label.)
2. **PRECISION_FIXABLE** — `F` materially exceeds `S` (large `G`, `F` not low) → Scout
   finds files, misses spans → names a span-refinement fix (e.g. Tier-0 AST
   re-narrowing within the found file).
3. **RETRIEVAL_FUNDAMENTAL** — low `F` / empty-dominant **and** the probe did NOT help
   (`Δempty ≈ 0`) → the 4B finder can't localize this query distribution → names a
   **finder-capability** spec (different/larger finder), NOT a span fix.
4. **MIXED** — the distribution splits with no dominant mode → both leads, prioritized
   by count.

### Invariants

- **Measure, don't fix.** Primary deliverable is a recorded typed finding + a clean
  failure distribution. No change to Scout, gate, tiers, matrix, or judge. Any code
  change is eval/measurement-only (measurement-not-construction) with a regression
  test.
- **Regenerate, don't inherit.** Per 0021's metric-trust verdict,
  `wrong_tier1_count`, `span_hit_rate_primary`, and `gate_catch_rate` are
  CONTAMINATED — regenerate the distribution from scratch. Only `escalation_rate=0`,
  `correct_tier1_count=0`, and `gate_false_escalation=null` are trusted.
- **Cheap: Scout-only, offline.** Measure Scout in isolation — NO gate, NO judge, NO
  Deep. Iterate on a stratified subset before the full 38.

## Acceptance criteria

1. **[unit]** The 4-way classifier (`EMPTY` / `WRONG_FILE` / `RIGHT_FILE_WRONG_SPAN`
   / `CORRECT`) is **mutually exclusive and total** on hand-built fixtures, enforcing
   the stated precedence `CORRECT > RIGHT_FILE_WRONG_SPAN > WRONG_FILE > EMPTY`.
   Fixtures MUST cover the boundary cases: a path-only right-file citation (→
   `RIGHT_FILE_WRONG_SPAN`, not `CORRECT`), a within-window non-overlapping citation
   (→ `RIGHT_FILE_WRONG_SPAN` + `within_window` flag), a multi-citation case mixing a
   gold-file and a wrong-file citation (precedence takes the better), and a
   malformed-only case (→ `EMPTY` with `normalization_dropped > 0`).
2. **[unit]** FILE-level and SPAN-level accuracy are computed **independently**, and
   the **`G = FILE − SPAN` gap is a first-class reported metric** (asserted on a
   fixture where the two differ, e.g. all-path-only → FILE=1.0, SPAN=0.0, G=1.0).
3. **[unit]** Citation normalization runs before classification: suffix-recovery
   (spec 0012) applied, malformed citations dropped into `normalization_dropped`
   (never silently `EMPTY`/`WRONG_FILE`), file-level shape retained — asserted on
   fixtures.
4. **[integration]** A **Scout-only** run over a **stratified subset** (strata named:
   by repo × gold-patch span-size band) produces the regenerated clean distribution
   (NOT inheriting 0021's contaminated counts); **empty-rate recorded**.
   (skip-not-fail when served models/fixtures absent.)
5. **[integration]** `turns-used` and suffix-recovery hit/drop are recorded on real
   cases, captured at the **eval boundary** (à la 0021's `_wrap_timed` / the existing
   `fc_citation_recovered_{spanned,filelevel}_count` instrument) — **never** by
   reaching into frozen Scout/FastContext internals. (skip-not-fail.)
6. **[integration]** The query-reformulation probe runs on a small labeled subset,
   records the raw-vs-distilled **empty-rate delta**, and is kept **out of** the
   baseline distribution (labeled non-primary). (skip-not-fail.)
7. **[doc]** A **typed finding**, exactly one of `PRECISION_FIXABLE` /
   `RETRIEVAL_FUNDAMENTAL` / `BENCHMARK_UNREPRESENTATIVE` / `MIXED`, chosen by the
   decision rule above, stating the observed `F` / `S` / `E` / `G` and the probe
   `Δempty`, and naming the fix/next spec it routes to.
8. **[doc]** The report includes **raw per-case rows** (case-id, bucket, sub-flags,
   citation vs gold) **plus aggregate counts**, so the distribution is auditable and a
   future spec can reuse the regenerated evidence without inheriting 0021's counts.
9. **[doc]** An explicit **representativeness** judgment (AC6 question): are SWE-bench
   issue-text queries representative of Harpyja's target (terse legacy-codebase NL
   queries) or pathologically long — a real-world Scout failure vs a benchmark-fit
   artifact — with the probe `Δempty` as supporting evidence.
10. **[unit/doc]** A guard asserting **no change** under `harpyja/scout/`,
    `harpyja/orchestrator/` (tiers/gate/matrix/judge) — all new code is additive under
    `harpyja/eval/` (measurement-not-construction).

## Out of scope

- **FIXING Scout** — the diagnosis *names* the fix spec; it does not implement it.
- **OQ2** — blocked until Scout localizes; not reopened here.
- **The gate / judge / escalation threshold** — all downstream of locate-accuracy.
- **The 5-case wrong-content fate from 0021** — undetermined, not worth a
  served-model hour.
- **Wave-2.1 substring/fuzzy matching** — may be *NAMED* by the finding, not done here.
- **Acting on the probe** — the probe *discriminates* the finding; distilling queries
  in production (or swapping the finder) is the named follow-up, not this spec.

## Open questions

_Resolved at review (2026-07-04):_

- **Query-reformulation probe** → **included** as a labeled non-primary probe (AC6),
  because it is the discriminator between `BENCHMARK_UNREPRESENTATIVE` and
  `RETRIEVAL_FUNDAMENTAL` — deferring it would make the 4th finding branch
  undiagnosable.
- **Benchmark-unfit outcome** → expressed as a **4th finding branch**
  (`BENCHMARK_UNREPRESENTATIVE`), routing to a dataset/benchmark spec (0020 precedent).

_Still open (settled by the run, not presumed):_

1. **Is right-file-wrong-span (astropy) representative or exceptional?** 0021's
   empty-dominance suggests exceptional → leans `RETRIEVAL_FUNDAMENTAL`. The
   distribution settles it.
2. **Pre-registered prior (falsifiability guard):** 0021 gives ~33/38 `EMPTY` + the
   one known astropy `RIGHT_FILE_WRONG_SPAN`, which pre-registers
   `RETRIEVAL_FUNDAMENTAL` **unless** the probe fires (→ `BENCHMARK_UNREPRESENTATIVE`).
   Recording the expected label up front guards the "distribution settles it, don't
   presume" invariant against confirmation bias — name what distribution would
   overturn it.
