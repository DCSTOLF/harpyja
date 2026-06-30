---
id: "0011"
title: "citation-shape"
status: closed
created: 2026-06-28
authors: [claude]
packages: [harpyja/scout, harpyja/eval, harpyja/orchestrator, harpyja/server]
related-specs: ["0005", "0007", "0008", "0010"]
---

# Spec 0011 — citation-shape

## Why

RCA (commit `1b7fed2`) found Scout is **systematically dead on real SWE-bench
queries**. FastContext's `format_citations` (`fastcontext/agent/utils.py:96`)
does `c["path"]`, assuming dict-shaped citations; the FC-4B model emits
**bare-string** citations on real issue prose → `TypeError` →
`client.py::_run_path_a` catches → `ScoutUnavailable(BACKEND_ERROR)` (the
spec-0007 AC10 defensive mapping) → Tier-0 degrade.

On the N=12 point subset this produced **12/12 `scout-degraded:backend-error`**,
`escalation_rate=0`, the gate **upstream-starved**, and bare Tier-0 running at
**2/12 = 0.167**. The 0007 floor did its job and **thereby hid the defect**: a
floored Scout is indistinguishable from "cheapest tier works" at the metrics
layer.

There are **two defects**:
1. Scout is not robust to FastContext's string citation shape.
2. Tier degradation is invisible in aggregate metrics.

Until both are fixed, **OQ2 is uncalibratable on real data** and the NL ladder
(Scout → gate → Deep) is **non-functional on exactly the real-world queries
Harpyja targets**. The low Tier-0-alone accuracy proves that ladder is
load-bearing, not redundant.

Ref: spec 0005 (ScoutBackend seam), 0007 (FC live + AC10 backend-error +
`normalize_spans`), 0008 (Verification Gate), 0010 (SWE-bench eval); history.md
`scout-broken-on-real-swebench`.

**Invariant (single wire-format owner).** The `scout/` adapter remains the
**only** module that **parses FastContext's wire format** (0005/0007) — shape
parsing/normalization lands there, not upstream and not in the orchestrator.
**FastContext is NOT patched.** This invariant governs *who parses FC output*;
it is **not** about who owns `CodeSpan`. `CodeSpan`/`Citation` are the shared
cross-tier **contract** and already live in `harpyja/server/types.py`;
extending that contract to *express* coarser precision (§Representation) is
consistent with the invariant, not a violation of it.

**Invariant (honest precision).** A bare-string citation yields a path but no
line range → normalize to a **FILE-LEVEL** `CodeSpan`. Do **not** fabricate a
line range (no `0`/`1`/EOF sentinel that reads as a real span). Carry coarser
precision **visibly**, all the way through the gate (§Gate handling) **and the
eval oracle** (§Deliverable 2) — a coarse, path-only span must never read as a
line-verified one.

## What

### Representation — line-less `CodeSpan` (`harpyja/server/types.py`)

The honest-precision invariant cannot hold over today's type: `CodeSpan`
declares `start_line: int` / `end_line: int` as **required** ints, and
`normalize_spans` (`scout/normalize.py:49`) **rejects** any span with
`start_line < 1`. So "file-level, no lines" has no encoding and the existing
path would silently drop it — the exact silent-degrade this spec exists to kill.

**Decision:** make the line fields **optional** — `start_line: int | None`,
`end_line: int | None` — with the pinned semantics **`None` ⇒ file-level (no
line range)**. A file-level span has `start_line is None and end_line is None`
(**both, never one** — the half-`None` state is rejected at the parse/normalize
boundary, AC23); a spanned span keeps both as ints (unchanged). This is an
additive shape change on the shared contract; existing constructions that pass
ints are unaffected.

**Touch-points (the full blast radius — enumerated from
`grep -rn 'start_line\|end_line' harpyja/`; every `CodeSpan`/`Citation`
consumer on the Scout→report path is listed, the category closed at once):**
- `server/types.py` — optional line fields (above).
- `scout/client.py` — invoke FC `citation=False`; `parse_final_answer` emits a
  **file-level** span for a bare-path ref (§Deliverable 1, the corrected fix
  locus).
- `scout/normalize.py` — file-level branch (below).
- `orchestrator/format.py` — **Citation Formatter** survives a `None`-line span
  without line arithmetic (§Formatter). *Sits between `normalize_spans` and the
  gate on the load-bearing path (`locate.py:163`/`:238`), so a `None`-line span
  crashes here first if unhandled — the round-3 blocker.*
- `orchestrator/gate.py` — not-verifiable handling + `GateOutcome` status
  (§Gate handling).
- `orchestrator/locate.py` — propagates the `gate-skipped:no-line-range` marker
  (§Gate handling).
- `eval/metrics.py` — file-level (path-only) overlap credit, guarded **before**
  the line arithmetic (§Deliverable 2).
- `eval/runner.py` — serializes a `None`-line cited span as JSON `null`;
  `report.py::validate_report` must tolerate null cited lines (§Deliverable 2).

*Producers that only ever emit lined spans — `deep/rlm.py`, `deep/host_tools.py`,
`symbols/ripgrep.py`, `symbols/symbol_locator.py` — are unaffected (they never
construct `None` lines). The gold-side `ExpectedSpan` (`eval/dataset.py`) stays
int-only. The **new** file-level producer is `scout/client.py::parse_final_answer`
(§Deliverable 1).*

### Deliverable 1 — Scout citation-shape robustness (`harpyja/scout/`)

**Corrected fix locus (resolves the citation-acquisition seam — the round-3
deeper finding).** The RCA
proves Harpyja **never receives FastContext's citation *objects***: FC's
`format_citations` runs **inside** `agent.run(prompt, citation=True)`
(`client.py:231`) and crashes there on bare-path model output, so the prior
"normalize dict-vs-string citation objects" framing solved a problem that
doesn't exist at Harpyja's seam. On the success path Harpyja already parses
citations from the answer **text** (`parse_final_answer`, `client.py:142–144`).

**The fix lives in the text seam, in `scout/`, with FC unpatched:**
1. **Invoke FC with `citation=False`** — bypass the crashing object-formatter
   entirely (no exception thrown on the hot path; no catch-as-control-flow).
2. **Extend `parse_final_answer`** to recognize **both** ref shapes in the
   `<final_answer>` text and emit the matching `CodeSpan`:

| Text ref shape | Outcome |
|---|---|
| `path:start` or `path:start:end` | **spanned** `CodeSpan` (both lines int — **regression**, unchanged) |
| `path:` with a **malformed / non-numeric** line | **file-level** `CodeSpan` (`None` lines — degrade precision; don't crash, don't fabricate) |
| **bare `path`** (no `:line`) | **file-level** `CodeSpan` (`None` lines). The path is **opaque** — do **not** invent a line (OQ3). |

   The bare-path vs `path:start` distinction is now a **regex/text** concern, not
   object classification. The honest-precision invariant fits *better* here: a
   `path:start` match → spanned; a bare-`path` match → file-level.

**Result resolution (text-level):**

| Answer text | Result |
|---|---|
| ≥1 parseable ref | normalize the refs (file-level + spanned) via `normalize_spans`; refs dropped by repo-confine/`is_file` counted (no silent coverage) |
| **no parseable ref** (clean run, nothing citable) | honest-empty `[]` — **not** a raise (existing `parse_final_answer` convention) |
| **genuine FC backend failure** (`agent.run` itself raises) | `ScoutUnavailable(backend-error)` — the existing 0007 floor mapping, **unchanged** |

There is no longer an "all-citation-objects-unparseable → raise" case: 0 refs is
an honest-empty text parse, and the `backend-error` floor is reserved for a real
`agent.run` exception. **FastContext is not patched.**

**🔴 Gating check (first plan step; fail-fast).** Confirm FC's answer text still
carries `<final_answer>` path refs — **and pin their exact delimiting structure**
(structured list? newline-delimited? prefixed?) — when invoked `citation=False`,
run on the flask reproduction. The bare-path regex (AC22) is built against that
**observed structure**, not a naked optional `:\d+`. **No implementation
proceeds past this step** until the fixture is recorded (locking (a)) or seam (c)
is selected and this section amended. If the text does **not** carry refs, fall
back to seam (c) (catch the `format_citations` crash, parse the recovered text)
— the only remaining in-`scout/` option, and **AC20's "zero backend-error" still
holds** (the crash is caught-and-parsed, not mapped to `backend-error`). Do
**not** design for (c) until (a) is disproven.

**`normalize_spans` file-level branch.** A span with `start_line is None`
**skips the line-range validation/clamp** (lines 49–57) but still passes
**repo-confine** (`relative_to(root)`) + **`is_file()`** + **dedup** (keyed on
path with a `None` line slot). A **spanned** span (both lines int) keeps today's
exact behavior; **Tier-2/Deep — which always emits lined spans — is provably
unaffected** (it never produces `None` lines; its `deep_*`-budget call never
reaches the new branch).

### Formatter — line-less spans (`harpyja/orchestrator/format.py`)

The Citation Formatter sits **between `normalize_spans` and the gate** on the
load-bearing path (`locate.py:163` formats Scout spans before `gate.verify` at
`:169`; `_locate_scout` at `:238`). It does line arithmetic (`sorted` on
`(start_line, end_line)` `:52`; adjacency-merge `:55–57`; rank keys `:94–95`),
so a `None`-line span crashes there **before** the gate is reached if unhandled.

**Decision:** a file-level (`None`-line) span **survives formatting un-merged**:
it is **never adjacency-merged into a lined span** (no line to order or merge
against), it sorts **after** lined spans of the same path on a stable key (file-
level is coarser), its dedup key carries the `None` line slot (already hashable),
and it is **returned carrying `None` lines** — the formatter neither crashes nor
fabricates a range. This is the formatter analogue of the normalize survive-path
(AC6).

### Gate handling — line-less spans (`harpyja/orchestrator/gate.py`, `locate.py`)

A file-level (line-less) `Citation` reaching the Verification Gate **has no
lines to read back** — and `_read_cited_lines` would crash on `None`. The gate
**detects `start_line is None` before any read-back** and treats it as
**not-verifiable** — a **third outcome state, distinct from passed/failed**.
Because today's `GateOutcome` (`passed`/`score`/`scored_count`/`dropped_count`/
`failed`) cannot express it without overloading `passed`/`failed`, `GateOutcome`
gains a **minimal explicit field** (`skipped_reason: str | None`, value
`"no-line-range"`) — **no scoring-algorithm change** (out of scope). The gate
does **not** score the span, does **not** record it as a verified gated-pass.
`locate.py` reads `skipped_reason` and attaches the **stable marker
`gate-skipped:no-line-range`** (mirrors `gate-skipped:scout-empty`), so it can
**never collapse** into `gate-low-confidence` (fast) or `gate-scoring-failed`
(auto). Downstream routing treats not-verifiable like a non-passing result: in
`auto`, **if a tier remains, escalate** (verification was unavailable, so don't
stop here); if none remains, the coarse span is carried best-effort **tagged
`gate-skipped:no-line-range`**, never at high confidence. This preserves the
graceful-degradation guardrail ("never return a confident citation that wasn't
verified when verification was available").

### Deliverable 2 — Harness degrade visibility (`harpyja/eval/`)

First-class, machine-readable degrade reporting on the pinned schema. Field →
`_*_DEFAULTS` placement is pinned to avoid drift:

| Field | Type | Defaults dict |
|---|---|---|
| `scout_degrade_count` | int | `_AGGREGATE_DEFAULTS` |
| `scout_degrade_rate` | float \| null | `_AGGREGATE_DEFAULTS` |
| `degraded_dominated` | bool | `_AGGREGATE_DEFAULTS` |
| `reliability_notes` | list[str] | `_AGGREGATE_DEFAULTS` |
| `fc_citation_spanned_count` | int | `_AGGREGATE_DEFAULTS` |
| `fc_citation_filelevel_count` | int | `_AGGREGATE_DEFAULTS` |
| `fc_citation_dropped_count` | int | `_AGGREGATE_DEFAULTS` |
| `degraded_dominated_threshold` | float | `_RUN_METADATA_DEFAULTS` |

- **`scout_degrade_rate`** = `scout_degrade_count / cases_attempted`
  (numerator: cases whose outcome carries a `scout-degraded:*` marker). **Zero
  denominator → explicit `null` paired with the (zero) count**, never `0.0`.
- **`degraded_dominated`** = `scout_degrade_rate > degraded_dominated_threshold`.
- **`reliability_notes`** holds stable identifiers (`"degraded-dominated"`,
  `"indicative-only"`, …) and is **composable** — a run may carry several at
  once; the list never lets one overwrite another. When `degraded_dominated` is
  set, escalation / accuracy / OQ2 outputs are marked unreliable via this list.
- **`fc_citation_*_count`** record the **text-ref** shape distribution per run —
  `spanned` (`path:start`) vs `filelevel` (bare path) vs `dropped`
  (repo-confine/`is_file` rejected) — so the bare-path frequency (the root-cause
  signal) is visible and no drop is silent (OQ3 promoted; may shift with FC SHA).
  **Carrier:** these counts originate in `scout/` (where parsing/dropping
  happens), so `parse_final_answer`/`normalize_spans` return the per-shape tally
  as **metadata attached to the Scout result** (not inferred from the surviving
  citations, which can't show a dropped ref); `eval/runner.py` reads that
  metadata and aggregates it — the one defined production→aggregation path.
- **File-level overlap credit (`metrics.py`).** The one overlap oracle
  (`_any_primary_overlap`, `metrics.py:61`) scores a **file-level** (line-less)
  citation as a **path-only** match — same-file credit, recorded **distinctly**
  from a line-overlap match (honest precision in measurement too; mirrors the
  oracle's new-file-target discipline). A coarse hit is never counted as a line
  hit. The path-only branch is taken **before** the `cited.start_line <=
  expected.end_line` arithmetic (which would crash on `None`) — guard, don't
  patch downstream.
- **Report serialization (`runner.py` + `report.py`).** A file-level cited span
  serializes its line fields as JSON `null` (`runner.py:69–70`);
  `validate_report` **must tolerate null cited `start_line`/`end_line`** (the
  gold-side `expected_spans` remain int-only). Asserted so a file-level citation
  that reaches the report never trips the one loud validator.

**`degraded_dominated_threshold`** is an **eval-only** knob on `EvalConfig`
(field-disjoint from the production frozen `Settings`), **provisionally `0.5`**,
configurable, recorded in run metadata. *Justification:* at `> 0.5` a
**majority** of cases degraded, so the run characterizes the degrade-floor
rather than the system under test — the same judgment the N-floor encodes;
revisitable once real data flows (the threshold-calibration open question below).

**Schema additivity** (named repo convention): new fields appended
**last-with-defaults** in the centralized `_*_DEFAULTS` source per the table
above, `SCHEMA_VERSION` bumped (`0010/1` → `0011/1`), `validate_report` covers
them, and **both** the pre-0011 and 0011 report shapes pass the one loud
validator.

"12/12 scout-degraded" must be **impossible to miss at report top.**

### Ship-together decision (resolved OQ1)

The two deliverables are causally linked (the visibility gap is *why* the Scout
bug hid) and are one lesson: degradation must be **safe** *and* **observable**.
Shipping the Scout fix without the visibility fix would close this bug but leave
the *next* tier failure equally invisible. They land in one spec despite
touching different packages.

## Acceptance criteria

Legend: `[unit]` = fakes/injected; `[integration]` =
`@pytest.mark.integration`, **skip-not-fail**. One observable behavior per
criterion.

**Scout text-parsing + representation (Deliverable 1):**

1. `[unit]` A **bare-path** ref (no `:line`) in `<final_answer>` text →
   `parse_final_answer` emits a valid **file-level** `CodeSpan`
   (`start_line is None and end_line is None`, `source_tier=1`), **no fabricated
   range**. *(driven by the AC11 recorded fixture)*
2. `[unit]` A **`path:start`** (and `path:start:end`) ref → spanned `CodeSpan`
   (**regression**: today's behavior unchanged).
3. `[unit]` A `<final_answer>` mixing **bare-path and `path:start`** refs → each
   parsed per its shape (file-level + spanned in one result).
4. `[unit]` A bare-path ref produces a **file-level** `CodeSpan` (assert **both
   line fields are `None`** — no line range invented) — honest-precision guard.
5. `[unit]` A `path:` ref with a **malformed / non-numeric line** → **file-level**
   `CodeSpan` (`None` lines; no crash, no fabricated range — don't drop a usable
   path over a bad line).
6. `[unit]` **Survive-path (positive):** a file-level span for a real in-repo
   file **survives** `normalize_spans`' repo-confine/`is_file`/dedup and is
   **returned carrying `None` lines** (not dropped) — the load-bearing fix.
7. `[unit]` **Deep regression:** `normalize_spans` with `deep_*` budgets over
   lined spans is **byte-identical to today** (the file-level branch is never
   reached for Tier-2).
8. `[unit]` **Floor preserved:** a genuine FC backend failure (`agent.run`
   raises) → `ScoutUnavailable(backend-error)` (the existing 0007 mapping,
   unchanged); whereas a `<final_answer>` with **no parseable ref** →
   honest-empty `[]` (**not** a raise).
9. `[unit]` Refs that parse but are **dropped** by `normalize_spans`
   (out-of-repo / nonexistent / bare path that isn't a real file) → honest-empty
   `[]` (no-matches), **not** `backend-error`.
10. `[unit]` Dropped refs are **counted** via `fc_citation_dropped_count` (no
    silent coverage); a stable log line is emitted per drop.

**Fixture grounding:**

11. `[unit]` AC1–5 are driven from a **committed recorded real-FC fixture** (the
    actual `citation=False` `<final_answer>` text from the flask issue, carrying
    the bare-path refs), so the shape under test is **observed, not assumed** —
    and the regression is machine-verified even when the live AC20 is skipped.

**Formatter:**

12. `[unit]` **Formatter survive-path:** a file-level (`None`-line) span passes
    through `format_citations` **without crashing and without fabricating a
    range** — it is **not** adjacency-merged into a lined span of the same path,
    sorts after lined spans, and is returned carrying `None` lines. *(driven by
    the AC11 fixture; the missing analogue of AC6 on the formatter stage.)*

**Gate handling:**

13. `[unit]` A file-level (line-less) `Citation` reaching the Verification Gate
    is detected **before** read-back and treated as **not-verifiable** via the
    explicit `GateOutcome.skipped_reason="no-line-range"`: it is **not** scored,
    **not** recorded as a verified pass; `locate.py` attaches the stable
    **`gate-skipped:no-line-range`** marker (asserted **distinct** from
    `gate-low-confidence` / `gate-scoring-failed`); in `auto` with a tier
    remaining it **escalates**, else it is carried best-effort tagged with that
    marker — never at high confidence. No scoring-algorithm change.

**Harness degrade visibility (Deliverable 2):**

14. `[unit]` Harness reports **`scout_degrade_count`** and
    **`scout_degrade_rate`** as first-class fields; `scout_degrade_rate =
    scout_degrade_count / cases_attempted`; **zero denominator → explicit
    `null` paired with the (zero) count**, never `0.0`.
15. `[unit]` `scout_degrade_rate > degraded_dominated_threshold` (provisional
    `0.5`) → **`degraded_dominated=true`**; escalation / accuracy / OQ2 marked
    unreliable via stable **`reliability_notes`** identifiers.
    `degraded_dominated` and `indicative_only` **compose** (both can be present;
    neither overwrites the other).
16. `[unit]` New report fields are appended **last-with-defaults** in the
    centralized `_*_DEFAULTS` dicts **per the §Deliverable-2 placement table**,
    **`SCHEMA_VERSION` bumped** (`0010/1` → `0011/1`), `validate_report` covers
    them, and **both** the pre-0011 and 0011 report shapes pass the one
    validator.
17. `[unit]` FC text-ref shape distribution (**`fc_citation_spanned_count`**,
    **`fc_citation_filelevel_count`**, **`fc_citation_dropped_count`** per run)
    recorded as stable machine-readable counters (OQ3 promoted).
18. `[unit]` The overlap oracle scores a **file-level** citation as a
    **path-only** match, recorded **distinctly** from a line-overlap match (a
    coarse hit is never counted as a line hit); the path-only branch is taken
    **before** the line arithmetic (no `None` crash).
19. `[unit]` A file-level cited span serialized into the report carries JSON
    `null` line fields and **`validate_report` accepts it** (the one loud
    validator tolerates null cited lines; gold `expected_spans` stay int-only).

**End-to-end (load-bearing):**

20. `[integration]` **Live Scout** on a real SWE-bench issue query (flask
    worktree) returns **tier-1 citations with zero backend-error** — the exact
    case that was 12/12 broken.
21. `[integration]` Re-run N=12 point subset: assert **`scout_degrade_rate <
    1.0`** (no longer 12/12), **Scout emitted ≥1 tier-1 span**,
    **`escalation_rate` is a non-null measured value**, and a **per-case
    escalation reason is recorded** for each case (so "no escalation" is an
    explicit recorded reason, not silence).

**Parser precision + shape invariant (reframe guards):**

22. `[unit]` **Bare-path false-positive guard:** an **incidental filename in
    prose** inside `<final_answer>` (e.g. "similar to `test_app.py`, fix is in
    `app.py:42`") yields the **spanned** citation only — the prose mention does
    **not** produce a spurious file-level span. *(The AC11 fixture carries a
    non-citation slashed/extension token as a negative control; the bare-path
    grammar is built against the citation **delimiting structure observed in the
    gating-check reproduction** (open question 1), not a naked optional `:\d+`.)*
23. `[unit]` **Shape invariant:** a `CodeSpan` is **either both-int or
    both-None** — a half-`None` span (`start=int, end=None` or vice-versa) is
    **rejected** at the parse/normalize boundary, so AC13's single-field
    (`start_line is None`) gate guard is sound and no half-`None` reaches
    read-back arithmetic.

## Out of scope

- Patching FastContext upstream.
- The production **OQ2 calibration** itself (the `verify_threshold`/`verify_top_n`
  tuning from specs 0009–0010) — this spec **unblocks** it, doesn't do it.
- The full 12-repo sweep.
- Gate threshold / `top_n` tuning, and any change to the gate's **scoring
  algorithm** beyond the line-less / not-verifiable detection in AC13.
- Parsing line ranges from anything other than a **numeric trailing
  `:start[:end]`** (which stays spanned, AC2). A malformed/non-numeric trailing
  line degrades to **file-level** (AC5); a bare path is **file-level** (AC1) —
  Harpyja never invents a range. (Colons *inside* a path are governed by the
  pinned text-ref grammar, not split as a line — see the AC22 false-positive
  guard.)
- Wave-2.1 substring/fuzzy.

## Open questions

1. **Gating check — does FC emit `<final_answer>` path refs under
   `citation=False`? (first `/spec:plan` step; gates seam (a)).** Decision (a)
   is locked *contingent* on this. The RCA strongly implies yes — the textual
   `<final_answer>` citation format is upstream of FC's object-formatting step,
   and `parse_final_answer` already extracts `path:start` from answer text — but
   it must be confirmed on the flask reproduction (and the ref delimiting
   structure pinned, for the AC22 regex) before code is built on it. If it
   **fails**, fall back to seam (c) (catch the `format_citations` crash, parse
   the recovered text); do **not** design for (c) until (a) is disproven.
2. **`degraded_dominated_threshold` calibration (this spec's OQ2).** Ships
   provisionally at `0.5` (justified above). Revisit to a data-driven value
   once Scout fires on real data and a real degrade-rate distribution exists —
   sequenced *after* the production OQ2 (`verify_threshold`) calibration this
   spec unblocks.

### Resolved during review

- **Citation-acquisition seam (round-3 deeper finding):** resolved → **seam (a)**
  — invoke FC `citation=False`, extend `parse_final_answer` to emit a file-level
  span for a bare-path ref. The fix lives in the **text seam** (`scout/`), FC
  unpatched; the old "normalize dict-vs-string *objects*" framing is dropped
  (Harpyja never receives those objects). §Deliverable 1 + AC1–10 + the shape
  counters recast accordingly; the gating check survives as open question 1 above.
- **OQ1 (split vs ship-together):** resolved → **ship together** (causal link;
  degradation must be safe *and* observable).
- **OQ3 (record shape distribution):** resolved → **promoted to AC17**
  (spanned / file-level / dropped text-ref counters); opaque bare-path handling
  pinned (no fabricated line) in §Deliverable 1.
- **Line-less representation (round-2 blocker):** resolved → **`None` line
  fields** on `CodeSpan` (§Representation), `normalize_spans` file-level branch,
  touch-points enumerated, `harpyja/server` added to packages.
- **Coarse-precision marker id (round-2):** resolved → **`gate-skipped:no-line-range`**.
- **Drop-counter contract (round-2):** resolved → **`fc_citation_dropped_count`**
  + stable per-drop log (AC10/AC17).
- **Formatter / GateOutcome / serialization (round-3 blocker):** resolved →
  `format.py` survive-path (AC12), explicit `GateOutcome.skipped_reason` +
  `locate.py` propagation (AC13), `validate_report` null-line tolerance (AC19);
  touch-points list corrected (the round-3 "bounded blast radius" miss).
