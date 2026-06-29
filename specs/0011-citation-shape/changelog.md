---
spec: "0011"
closed: 2026-06-28
---

# Changelog — 0011 citation-shape

## What shipped vs spec

Spec 0010 surfaced (and the RCA `1b7fed2` localized) a real defect: Scout was
**systematically dead on real SWE-bench queries** — 12/12 `scout-degraded:backend-error`,
the gate upstream-starved, bare Tier-0 at 2/12 = 0.167 — and the degrade was **invisible
in aggregate metrics**. This wave fixes both: Scout citation-shape robustness
(Deliverable 1) **and** harness degrade visibility (Deliverable 2), shipped together
because the visibility gap is *why* the bug hid. All 29 tasks complete (T0–T26 + R1/R2);
the **single-wire-format-owner** and **honest-precision** invariants held, **FastContext
is not patched**.

- **Root cause corrected by the live spike (T0).** The RCA's first framing
  ("normalize FC's dict-vs-string citation *objects*") was a **false premise** —
  Harpyja never receives FC citation objects. FC's `format_citations` runs **inside**
  `agent.run(prompt, citation=True)` and raises `TypeError: string indices must be
  integers` when the model's final message has no parseable `<final_answer>` block
  (`parse_citations` returns a dict fallback; `format_citations` iterates its string
  keys). The crash is on FC's hot path, mapped to `ScoutUnavailable(backend-error)` →
  Tier-0 degrade. The gating spike confirmed this live (FastContext-4B via Ollama):
  `citation=True` raises the exact RCA `TypeError`; `citation=False` returns the raw
  final message and structurally cannot reach `format_citations`.

- **Fix = seam (a) (`scout/client.py`).** Scout now invokes FC with **`citation=False`**
  on both Path A (in-process `agent.run`) and Path B (CLI: the `--citation` flag is
  dropped), bypassing the crashing formatter entirely — no exception on the hot path,
  no catch-as-control-flow. `parse_final_answer` was rewritten to parse the raw
  `<final_answer>` text **per line, anchored** to the observed FC grammar
  `<no-space-path>[:start[-end]] [(explanation)]`: `path:start[-end]` → spanned
  `CodeSpan` (both int — regression-preserved); bare path / malformed-or-non-numeric
  line → **file-level** `CodeSpan` (`None` lines, no fabricated range). A `_looks_like_path`
  guard (dir separator or dotted extension; stray markup rejected) keeps a bare word or
  prose mention from becoming a spurious file-level citation (AC22). New
  `parse_final_answer_with_tally` returns a `ParseTally{spanned, filelevel}`;
  `parse_final_answer` is the spans-only legacy view.

- **Representation (`server/types.py`).** `CodeSpan.start_line`/`end_line` widened to
  `int | None`, pinned semantics **`None` ⇒ file-level**. New **`CodeSpan.is_file_level`**
  property (`start_line is None and end_line is None`) is the single predicate every
  downstream consumer branches on. Both-or-neither: a half-`None` span is not a
  sanctioned shape and is rejected at the parse/normalize boundary (AC23).

- **Blast radius closed by category (`grep -rn 'start_line\|end_line'`).** Each
  `None`-line consumer on the Scout→report path got its own RED→GREEN, ordered
  producer→…→metrics so a `None` span is made safe before the next stage sees it:
  - `scout/normalize.py` — `normalize_spans_with_tally` returns `(spans, dropped)`; a
    file-level span skips the line-range validate/clamp but still passes
    repo-confine + `is_file` + dedup (keyed on a `None` line slot); each discarded
    ref is **counted** and logged (no silent coverage); half-`None` dropped. The
    Deep/Tier-2 lined path is byte-identical (`normalize_spans` is the spans-only view).
  - `orchestrator/format.py` — file-level spans survive **un-merged** (no range to
    order/merge against), sort **after** lined spans on a None-safe rank key.
  - `orchestrator/gate.py` — `GateOutcome` gains `skipped_reason: str | None`
    (`"no-line-range"`); a file-level citation is detected **before** read-back, **not**
    scored and **not** a verified pass; only lined citations are scored.
  - `orchestrator/locate.py` — stable `GATE_SKIPPED_NO_LINE_RANGE =
    "gate-skipped:no-line-range"`, distinct from `gate-low-confidence` /
    `gate-scoring-failed`; in `auto` escalate-if-a-tier-remains else carry best-effort
    tagged (never high confidence); `fast` informational-only.
  - `eval/metrics.py` — new `span_hit_kind` returns `"line"`/`"file"`/`None`; the
    path-only (file-level) branch is taken **before** the line arithmetic in **both**
    the primary oracle and the secondary (window) oracle. A coarse hit is never a line hit.

- **Deliverable 2 — degrade visibility (`harpyja/eval/`).** Report schema bumped
  `0010/1` → `0011/1` with 8 additive fields (last-with-defaults in the centralized
  `_*_DEFAULTS`): aggregate `scout_degrade_count`, `scout_degrade_rate` (null-with-count
  on a zero denominator), `degraded_dominated` (rate > threshold), `reliability_notes`
  (composable list), `fc_citation_spanned_count` / `filelevel_count` / `dropped_count`;
  run_metadata `degraded_dominated_threshold`. New eval-only
  `EvalConfig.degraded_dominated_threshold=0.5` (field-disjoint from `Settings`;
  justification: a majority-degraded run characterizes the degrade floor, not the SUT).
  **Carrier:** `ScoutEngine.last_tally` (`ScoutTally{spanned, filelevel, dropped}`) is a
  side-channel — the orchestrator's `list[CodeSpan]` seam is unchanged; `runner.py`
  resets it per case, reads the production-run tally, and aggregates.
  `compose_reliability_notes` (composing `degraded-dominated` + `indicative-only`) is
  shared by `runner.py` and `swebench_eval.py` so the two aggregation sites cannot drift.

## Deviations

- **The Deliverable-1 reframe mid-review (rounds 3→4).** The spec shipped to plan with
  the corrected fix locus (text seam, not object normalization). The T0 spike then
  **confirmed it live** and pinned the grammar, so seam (c) (catch-the-crash fallback)
  was never needed — the contingency in Open Question 1 resolved to (a).
- **Spike captured on a small temp repo, not flask.** The FC-4B model returns empty on
  the full flask tree, but the seam/grammar question is repo-independent, so the
  fixtures (`harpyja/scout/fixtures/fc_citation_false_{raw_samples,final_answer}.txt`
  + README) were captured on a small repo and curated for the parser edge cases. The
  live AC20 below still ran the exact 12/12-broken flask case.
- **`span_hit_secondary` caught during implementation.** The spec enumerated the
  primary oracle (`metrics.py`) for the `None`-guard; the secondary window oracle has
  the identical `None`-arithmetic crash and was guarded the same way (path-only ⇒
  distance 0). A blast-radius miss caught by the same grep-the-category discipline the
  round-3 review lesson prescribed.
- **T26 ran on the legacy fixture, not a fresh N=12 flask sweep.** The full N=12 flask
  re-run is compute-bound and remains the documented operator opt-in; the legacy
  fixture is the live AC21 stand-in for the degrade-visibility assertions. AC20 (the
  load-bearing zero-backend-error witness) **did** run the real flask case live.
- **`reliability_notes` defaults to `None`** (not-computed) in `_AGGREGATE_DEFAULTS` to
  avoid a shared-mutable default; a real run sets a concrete list.

## Verification evidence

- **Unit:** 656 passed project-wide (+45 over the 0010 baseline of 611), ruff clean.
- **Live integration (7 passed, real FastContext-4B + Deep + Ollama):**
  - **AC20 — the load-bearing witness.** `test_scout_live_no_backend_error_citation_false`
    (22.5s) ran the **exact 12/12-broken** flask case and returned with **zero
    backend-error** — Scout now yields a Tier-1 result on the query that was 100% dead.
  - 5 Scout live + 2 SWE-bench-driver live pass against the real stack (real
    `citation=False` FC, Deep, Ollama).
- **Gating spike (T0):** `citation=True` raises the RCA `TypeError`; `citation=False`
  returns raw text; fixtures committed under `harpyja/scout/fixtures/`.

## Files touched

- `harpyja/server/types.py` — `CodeSpan.start_line/end_line: int | None` + `is_file_level`.
- `harpyja/scout/client.py` — `citation=False` (both paths), per-line anchored parser,
  `ParseTally`, `parse_final_answer_with_tally`.
- `harpyja/scout/normalize.py` — `normalize_spans_with_tally` (file-level branch, drop
  count + per-drop log, half-`None` reject); `normalize_spans` spans-only view.
- `harpyja/scout/engine.py` — `ScoutTally` + `ScoutEngine.last_tally` side-channel.
- `harpyja/orchestrator/format.py` — file-level survive-path, None-safe rank key.
- `harpyja/orchestrator/gate.py` — `GateOutcome.skipped_reason`, pre-read-back detection.
- `harpyja/orchestrator/locate.py` — `GATE_SKIPPED_NO_LINE_RANGE` propagation + routing.
- `harpyja/eval/metrics.py` — `span_hit_kind` (line/file/None), primary + secondary guard.
- `harpyja/eval/config.py` — `degraded_dominated_threshold: float = 0.5`.
- `harpyja/eval/report.py` — `SCHEMA_VERSION = "0011/1"` + 8 additive fields/defaults.
- `harpyja/eval/runner.py` — degrade counters, null-with-count, tally aggregation,
  `compose_reliability_notes`, null serialization.
- `harpyja/eval/swebench_eval.py` — degrade-dominance + composable notes + threshold record.
- `harpyja/scout/fixtures/` (new) — `fc_citation_false_{raw_samples,final_answer}.txt` + README.
- Tests: `server/test_types.py`, `scout/test_fastcontext_client.py`, `scout/test_scout.py`,
  `scout/test_scout_normalize.py`, `scout/test_scout_integration.py`,
  `orchestrator/test_formatter.py`, `orchestrator/test_gate.py`, `orchestrator/test_locate.py`,
  `eval/test_metrics.py`, `eval/test_config.py`, `eval/test_report.py`, `eval/test_runner.py`,
  `eval/test_swebench_runner.py`, `eval/test_swebench_integration.py`.

## ADR proposed for history.md

2026-06-28 — Scout citation-shape robustness (seam (a), `citation=False`) +
harness degrade visibility — line-less `CodeSpan`, the corrected fix locus, safe +
observable degradation (prepended to `.speccraft/history.md`).

## Conventions proposed

- New: the line-less `CodeSpan` representation (`int | None`, `None ⇒ file-level`) with
  the single `is_file_level` predicate every downstream consumer branches on, and the
  both-or-neither (half-`None` rejected) invariant.
- New: don't route a result through a third party's crashing post-processor when its
  raw input is available — invoke the backend in the mode that bypasses the formatter
  and parse the raw text in-adapter (seam (a)), rather than catching the crash as
  control flow.
- New: a type-shape change to a shared contract enumerates its full blast radius via a
  category grep (`grep -rn`) and closes every consumer in the same change, each with its
  own RED→GREEN ordered along the data path.
- New: the `ScoutTally` / `last_tally` carrier pattern — per-run tier-internal metadata
  rides a side-channel read only by the eval harness; the orchestrator's `list[CodeSpan]`
  seam is unchanged so callers never branch on tier internals.

## Architecture updates

- Layer-5 `harpyja/scout/`: seam (a) `citation=False` + in-adapter text parser, the
  `ScoutTally`/`last_tally` side-channel.
- Layer-2 `harpyja/orchestrator/`: file-level survive-path in the formatter; the
  `GateOutcome.skipped_reason="no-line-range"` not-verifiable state + the
  `gate-skipped:no-line-range` flag.
- Layer-9 `harpyja/eval/`: the `0011/1` schema, degrade-visibility fields, the
  `degraded_dominated_threshold` knob, and the path-only overlap-credit branch.
- `harpyja/server/types.py`: `CodeSpan` line fields are now `int | None` (the shared
  cross-tier contract expresses coarser precision).
