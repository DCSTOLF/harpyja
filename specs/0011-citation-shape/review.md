---
spec: "0011"
title: "citation-shape: Scout citation-shape robustness + harness degrade visibility"
reviewers: [codex, claude-p]
quorum: 1
status: reviewed
rounds: 4
date: 2026-06-28
final_verdicts: { codex: changes-requested, claude-p: approve-with-comments }
---

# Review — spec 0011 citation-shape

Date: 2026-06-28 · Reviewers: `codex`, `claude-p` (cross-model, `.speccraft/agents.toml`)

## Status: REVIEWED — quorum met at round 4

Quorum = 1 approve / approve-with-comments. **Round 4: `claude-p`
approve-with-comments, `codex` changes-requested → quorum met, spec → `reviewed`.**
It took four rounds because each round the reviewers read **deeper into the
actual code** and surfaced a genuine, verified issue the prose had glossed — the
document improved substantially each round and its spine (honest precision, safe
+ observable degradation, ship-together) held firm throughout.

## Round-by-round arc

**Round 1 — both changes-requested.** Convergent: (1) the `degraded_dominated`
threshold was deferred to an open question but AC9 needs a concrete value; (2)
schema-additivity discipline (SCHEMA_VERSION bump, centralized `_*_DEFAULTS`,
`validate_report`) was missing; (3) `degrade-rate` numerator/denominator +
zero-denominator null-with-count undefined; (4) AC7/AC10 skip-not-fail give no
deterministic CI proof. Highest-value (claude-p only): the **line-less CodeSpan
× Verification Gate** interaction — a line-less span has nothing to read back; if
it auto-passes, a coarse unverified citation is returned at full confidence
(graceful-degradation guardrail brush). → folded into r2.

**Round 2 — both changes-requested.** r2 pinned the threshold (`0.5`), defined
degrade-rate, added schema-additivity (AC13), the real-FC fixture (AC10), and a
Gate-handling section. **But claude-p read the code and found a structural
blocker:** the "file-level / line-less `CodeSpan`" had **no representation** —
`CodeSpan.start_line/end_line` are required ints (`server/types.py:17-20`),
`normalize_spans` rejects `start_line < 1` (`normalize.py:49`), and
`_read_cited_lines` does `start_line - 1` (`gate.py:56`). The spec named a data
shape that doesn't exist and a routing path that contradicts the code. → folded
into r3 (verified against the code first).

**Round 3 — both changes-requested (current).** r3 pinned the representation
(`start_line/end_line: int | None`, `None ⇒ file-level`), a `normalize_spans`
file-level branch, Deep-unaffected proof, the `gate-skipped:no-line-range`
marker, the `fc_citation_unparseable_count` drop-counter, `_*_DEFAULTS`
placement table, opaque-string (no `:`-split) handling, and path-only eval
overlap credit. The reviewers confirmed all of that is now implementation-shaped
— **but both independently caught the same NEW miss the representation change
introduced:**

> **BLOCKER — the touch-points list ("the full, bounded blast radius — no other
> consumer changes") omits the Citation Formatter `orchestrator/format.py`,** a
> `start_line/end_line` consumer that sits on the load-bearing path **between
> `normalize_spans` and the gate** (`locate.py:163` `format_citations(...)`
> before `gate.verify` at `:169`; `_locate_scout` at `:238`). `format.py` does
> line arithmetic — `sorted(key=lambda s: (s.start_line, s.end_line))` (`:52`),
> `s.start_line <= merged[-1].end_line + 1` (`:55`), `max(m.end_line, s.end_line)`
> (`:57`), rank keys (`:94-95`) — and a `None`-line span raises
> `'<' not supported between NoneType and int` **before AC12 (gate handling) is
> ever reachable**. An implementer following the touch-points literally ships
> code that crashes on exactly the 12/12 case the spec exists to fix.

Secondary (r3):
- **codex:** `GateOutcome` (passed/score/scored_count/dropped_count/failed)
  can't represent "not-verifiable" distinctly — without an explicit
  `status`/`skipped_reason` field consumed by `locate.py`,
  `gate-skipped:no-line-range` collapses into `gate-low-confidence` (fast) or an
  ordinary gate failure (auto). Add `format.py` **and** `locate.py` to
  touch-points.
- **claude-p:** `eval/runner.py:69-70` serializes cited `start_line/end_line` →
  a file-level citation emits **JSON null** lines; confirm `validate_report`
  tolerates that. `metrics.py:61` (`cited.start_line <= expected.end_line`) has
  the same `None`-arithmetic crash — AC17's path-only branch must guard
  **before** the arithmetic, not after.
- claude-p's process note: this is the **same class** of miss as round 2 (a
  required-int line consumer the change would silently break). A
  `grep -rn 'start_line\|end_line' harpyja/` surfaces **all** consumers at once
  and closes the category.

**Round 4 — quorum met (claude-p approve-with-comments; codex changes-requested).**
r4 folded all round-3 blockers (formatter survive-path, `GateOutcome.skipped_reason`
+ `locate.py` propagation, validator null-tolerance, metrics guard ordering,
touch-points re-derived via grep) **and** the major Deliverable-1 reframe from the
author decision on the citation-acquisition seam (below). claude-p verified the
reframe against the regex and approved: "the spine is decided, grounded, and the
blockers are resolved… addressable in the plan phase without another full review
round." Remaining comments — **all folded into the spec post-r4**:
- *(codex, real)* stale Out-of-scope "opaque-string" bullet contradicted AC2's
  `path:start`→spanned rule → rewritten to the numeric-trailing-`:line` rule.
- *(claude-p, substantive)* dropping the regex `:\d+` anchor to match bare paths
  would extract **incidental prose filenames** as file-level citations,
  contaminating `fc_citation_filelevel_count` → **AC22** false-positive guard +
  the gating check now pins the ref **delimiting structure** before the regex is
  built.
- *(claude-p, correctness)* half-`None` `CodeSpan` was unrepresentable by fiat but
  unenforced → **AC23** both-int-or-both-None invariant.
- *(codex, contractual)* counter production→aggregation path undefined → carrier
  pinned (scout returns per-shape tally as Scout-result metadata; `runner.py`
  aggregates).
- *(both, editorial)* OQ-numbering collision (`OQ1` overloaded; production `OQ2`
  vs this spec's threshold OQ2) → renumbered/disambiguated; seam-(c) "zero
  backend-error still holds" stated on AC20.

## Deeper finding (round 3, author-decided in round 4) — the citation-acquisition seam

Tracing `scout/client.py` against the RCA: FastContext's `format_citations`
runs **inside** `agent.run(prompt, citation=True)` (`client.py:231`). Its
`TypeError` is caught at `client.py:243-247` → `ScoutUnavailable(backend-error)`,
so Harpyja **never reaches** `parse_final_answer`. And on success, Harpyja's
citations come from a **regex over the answer text** (`parse_final_answer`,
`client.py:142-144`) that requires `path:start` and builds int lines — it has
**no concept of FC's dict-vs-string citation *objects***; those are internal to
FC's own `format_citations`.

**Implication:** Deliverable 1's framing ("normalize FC's `{path:...}` dict vs
bare-string *citations*") describes shapes Harpyja never directly receives. The
real fix locus is the **citation-acquisition seam** — one of: (a) invoke FC with
`citation=False` and have Harpyja's own `parse_final_answer` handle bare-path
(line-less) refs → file-level spans; (b) intercept FC's raw citation list before
its `format_citations`; or (c) catch the formatter crash and fall back to text
parsing.

**Author decision (round 4): seam (a).** It is the only option whose viability
the author controls, stays in `scout/` with FC unpatched, and corrects the locus
to where Harpyja genuinely sits (answer text). (b) needs an FC raw-citation API
that may not exist without patching; (c) keeps `citation=True` so FC crashes
every call (catch-as-control-flow) and depends on answer text surviving the
exception. (a) bypasses the crash entirely. The honest-precision invariant fits
*better* as a text concern (a `path:start` match → spanned; a bare-`path` match
→ file-level). **Contingency:** (a) hinges on FC emitting `<final_answer>` path
refs under `citation=False` — carried as the **first plan step** (gating check,
open question 1); if disproven, fall back to (c). §Deliverable 1 + AC1–10 + the
shape counters were recast to the text seam accordingly.

## Outcome — all resolved

Items 1–3 (round-3 blockers) and 4 (the citation-acquisition seam) were resolved
in round 4 and re-reviewed; the residual round-4 comments were folded post-review
(see the round-4 record above). The spec is `reviewed`.

## Carried into `/spec:plan` (not blockers — plan-phase work)

- **Step 1 (gating, fail-fast):** confirm FC emits `<final_answer>` path refs
  under `citation=False` on the flask reproduction and **pin the ref delimiting
  structure**; build the AC22 bare-path regex against it. No code proceeds until
  (a) is locked or seam (c) is selected (open question 1).
- AC22 (bare-path false-positive negative control) and AC23 (half-`None`
  invariant) are the reframe's two precision guards — implement them alongside
  the parser change.

## Recommendation

Proceed to `/speccraft:spec:plan`. The spine (honest precision, safe + observable
degradation, ship-together) held firm across all four rounds; the architecture is
invariant to the one open contingency (both seam (a) and the (c) fallback live in
`scout/`, leave FC unpatched, and feed the identical downstream representation).
