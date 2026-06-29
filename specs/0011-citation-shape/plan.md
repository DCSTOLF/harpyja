---
spec: "0011"
status: planned
strategy: tdd
---

# Plan — 0011 citation-shape

Strict TDD (RED→GREEN→REFACTOR). Every GREEN is preceded by its RED. Steps are
ordered along the real data path so a `None`-line span is made safe at each
consumer before the next consumer sees it: **representation → scout parser
(producer) → normalize → formatter → gate/locate → eval metrics/carrier/runner →
swebench**, with the gating spike first and the live integration ACs last.

Test naming follows `test_<subject>_<scenario>` (conventions.md). Test files live
beside the package under test. Async is driven from sync via `asyncio.run`.
Integration ACs are `@pytest.mark.integration`, **skip-not-fail**.

## Test-first sequence

### Phase 0 — Gating spike (decision gate; NOT a code change)

#### Step 0 — Confirm seam (a) on the flask reproduction (SPIKE)
- Investigation only (spec Open Question 1). Run the real FastContext agent with
  `citation=False` against the flask SWE-bench worktree and capture the
  `<final_answer>` text.
- Confirm two things, and **pin** them:
  1. the answer text still carries `<final_answer>` path refs under
     `citation=False`;
  2. the **exact delimiting structure** of those refs (structured list? newline-
     delimited? back-tick wrapped? prefixed?) — the AC22 bare-path regex is built
     against this *observed* structure, not a naked optional `:\d+`.
- Record the captured text as the committed fixture
  `harpyja/scout/fixtures/flask_final_answer_citation_false.txt` (grounds AC11 +
  AC1–5 + AC22). The fixture MUST include a **non-citation slashed/extension prose
  token** as the AC22 negative control.
- **DECISION GATE — RESOLVED 2026-06-28 → seam (a) LOCKED.** Spike captured live
  (FastContext-4B via Ollama, effort=none): `citation=True` raises the exact
  `TypeError: string indices must be integers`; `citation=False` returns the
  model's raw final message and structurally cannot reach `format_citations`. The
  model emits `<final_answer>` blocks AND bare absolute paths with no line, so the
  file-level case is real. Grammar pinned: per-line
  `<no-space-path>[:start[-end]] [(explanation)]`, anchored (never a naked
  optional `:\d+`). Fixtures committed under `harpyja/scout/fixtures/`
  (`fc_citation_false_raw_samples.txt` = evidence; `fc_citation_false_final_answer.txt`
  = curated edge-case fixture; note: captured on a small temp repo, NOT flask —
  the 4B model returns empty on the full tree, and the seam/grammar question is
  repo-independent). Seam (c) NOT needed; all phases proceed as written.
- **DECISION GATE (original criteria, for the record):**
  - If (1) holds → **lock seam (a)**; all phases below proceed as written.
  - If (1) fails → **fall back to seam (c)** (catch `format_citations`'s crash,
    parse the recovered text). Amend §Deliverable 1, keep `citation=True`, and
    re-point Step 2.2's "invoke `citation=False`" sub-task to "catch-and-parse";
    **AC20's zero-backend-error still holds** (crash caught-and-parsed, not mapped
    to `backend-error`). Every other step (representation, normalize, formatter,
    gate, eval) is **unchanged** — they key on the file-level span, not on how the
    text was acquired.
- No implementation in Phases 1–5 begins until this fixture is committed and the
  gate is decided.

### Phase 1 — Representation (foundational: line-less `CodeSpan`)

#### Step 1 — `CodeSpan` optional line fields (RED)
- Extend `harpyja/server/test_types.py`:
  - `test_codespan_accepts_file_level_none_lines` — `CodeSpan(path="a.py",
    start_line=None, end_line=None)` constructs and reads back `None`/`None`.
  - `test_codespan_keeps_int_lines_unchanged` — a both-int span is byte-identical
    to today (regression anchor for the additive shape change).
- Tests fail: `CodeSpan.start_line`/`end_line` are declared `int`; the file-level
  construction is not yet a sanctioned shape (type contract not widened).

#### Step 2 — Widen the line fields to `int | None` (GREEN)
- `harpyja/server/types.py`: `start_line: int | None`, `end_line: int | None`
  with the pinned semantics `None ⇒ file-level`. Purely additive; existing int
  constructions unaffected.
- All Step-1 tests pass.

### Phase 2 — Scout text-parser + fixture (Deliverable 1, the producer)

#### Step 3 — Parser shape recognition + counter + half-None guard (RED)
- Extend `harpyja/scout/test_fastcontext_client.py` (all driven by the Step-0
  fixture where shape is asserted, satisfying AC11):
  - `test_parse_final_answer_bare_path_emits_file_level_span` — a bare `path`
    (no `:line`) → a valid file-level `CodeSpan`, `source_tier`-eligible, **no
    fabricated range** (AC1, AC11).
  - `test_parse_final_answer_bare_path_has_both_lines_none` — asserts **both**
    `start_line is None and end_line is None` (honest-precision guard, AC4).
  - `test_parse_final_answer_path_start_stays_spanned` — `path:start` and
    `path:start:end` → spanned `CodeSpan`, both lines int (regression, AC2).
  - `test_parse_final_answer_mixes_bare_and_spanned_refs` — one `<final_answer>`
    with both shapes → one file-level + one spanned span (AC3).
  - `test_parse_final_answer_malformed_line_degrades_to_file_level` — `path:` with
    a non-numeric line → file-level span, no crash, no fabricated range (AC5).
  - `test_parse_final_answer_prose_filename_not_spurious_file_level` — an
    incidental prose filename (the fixture's negative-control token) does **not**
    become a file-level span; only the real citation survives (AC22).
  - `test_parse_final_answer_rejects_half_none_span` — a constructed half-`None`
    ref (`start=int,end=None` / vice-versa) is rejected at the parse boundary
    (AC23, parser side).
  - `test_parse_final_answer_no_ref_is_honest_empty` — text with no parseable ref
    → `[]`, **not** a raise (AC8, honest-empty half).
  - `test_parse_final_answer_records_shape_tally` — the parser returns a per-shape
    tally `{spanned, filelevel}` alongside the spans (AC17, producer side).
  - `test_client_invokes_fastcontext_with_citation_false` — the injected
    agent/CLI is called with `citation=False` (seam (a) mechanism; supports AC20).
    *(Under a seam-(c) gate decision this becomes
    `test_client_catches_format_citations_crash_and_parses_text`.)*
  - `test_client_backend_failure_still_maps_backend_error` — `agent.run` raising
    → `ScoutUnavailable(backend-error)` unchanged (AC8, floor half).
- Tests fail: `parse_final_answer` only matches `path:\d+`, drops bare paths,
  returns no tally; the client still passes `citation=True`.

#### Step 4 — Parser emits file-level spans + tally; FC `citation=False` (GREEN)
- `harpyja/scout/client.py`:
  - Replace `citation=True` with `citation=False` at the Path-A (`:231`) and
    Path-B (`:266`) call sites (per the Step-0 decision).
  - Extend `parse_final_answer` to recognize **both** ref shapes against the
    Step-0-observed delimiting grammar: `path:start[:end]` → spanned; bare `path`
    / malformed-line → file-level (`None`/`None`); reject half-`None`.
  - Return the per-shape tally `{spanned, filelevel}` as metadata (e.g. a small
    `ParseTally` dataclass or a `(spans, tally)` return — pick the carrier that
    Step 9 reads).
- All Step-3 tests pass; the existing client tests stay green.

### Phase 3 — Downstream None-safety along the data path

#### Step 5 — `normalize_spans` file-level branch (RED)
- Extend `harpyja/scout/test_scout_normalize.py`:
  - `test_normalize_keeps_file_level_span_for_real_file` — a file-level span for a
    real in-repo file survives repo-confine/`is_file`/dedup and is **returned
    carrying `None` lines** (AC6, load-bearing survive-path).
  - `test_normalize_drops_file_level_span_for_missing_file` — a bare path that is
    not a real file → dropped → contributes to the dropped tally, not a crash
    (AC9).
  - `test_normalize_counts_dropped_refs` — dropped refs increment
    `fc_citation_dropped_count` and emit a stable per-drop log line (AC10;
    use `caplog`).
  - `test_normalize_rejects_half_none_span` — a half-`None` span is rejected at
    the normalize boundary (AC23, normalize side).
  - `test_normalize_deep_budget_lined_spans_byte_identical` — `normalize_spans`
    with `deep_*` budgets over lined spans is unchanged vs today; the file-level
    branch is never reached for Tier-2 (AC7, deep regression).
- Tests fail: line 49 (`span.start_line < 1`) raises/`TypeError`s on a `None`
  line; there is no file-level branch, no dropped-count return, no half-`None`
  guard.

#### Step 6 — `normalize_spans` file-level branch + drop tally (GREEN)
- `harpyja/scout/normalize.py`: when `span.start_line is None` (file-level),
  **skip** the line-range validation/clamp but still enforce repo-confine +
  `is_file()` + dedup (path keyed with a `None` line slot); a spanned span keeps
  today's exact path byte-for-byte. Reject half-`None`. Return the `dropped`
  count (fold into the Phase-2 tally) and log each drop.
- All Step-5 tests pass; AC7 keeps the Tier-2 path byte-identical.

#### Step 7 — Citation Formatter survives `None` lines (RED)
- Extend `harpyja/orchestrator/test_formatter.py`:
  - `test_formatter_passes_file_level_span_without_crash` — a `None`-line span
    flows through `format_citations` without raising (AC12).
  - `test_formatter_does_not_merge_file_level_into_lined_span` — a file-level span
    of a path is **not** adjacency-merged into a lined span of the same path; it
    sorts **after** lined spans and is returned carrying `None` lines (AC12).
- Tests fail: `_merge_same_file` sorts on `(start_line, end_line)` and does
  `s.start_line <= merged[-1].end_line + 1`; the rank key uses `m.start_line` —
  each `TypeError`s on `None`.

#### Step 8 — Formatter line-less survive-path (GREEN)
- `harpyja/orchestrator/format.py`: route file-level spans down a separate lane —
  never merged, sorted after lined spans of the same path on a stable key, dedup
  key carries the `None` slot, returned carrying `None` lines. No fabricated
  range, no crash.
- All Step-7 tests pass; the existing lined-span ranking tests stay green.

#### Step 9 — Gate not-verifiable + `GateOutcome.skipped_reason` (RED)
- Extend `harpyja/orchestrator/test_gate.py`:
  - `test_gate_skips_file_level_citation_as_not_verifiable` — a file-level
    `Citation` reaching `verify` is detected **before** `_read_cited_lines` and
    returned with `skipped_reason="no-line-range"`, `passed=False`, **not scored**,
    **not** a verified pass (AC13, gate side).
  - `test_gate_skipped_reason_distinct_from_scoring_failure` — `skipped_reason` is
    distinct from `failed=True` (not-verifiable ≠ could-not-vouch); no scoring-
    algorithm change.
- Tests fail: `GateOutcome` has no `skipped_reason` field; `_read_cited_lines`
  does `citation.start_line - 1` and crashes on `None`.

#### Step 10 — Gate detects line-less before read-back (GREEN)
- `harpyja/orchestrator/gate.py`: add `skipped_reason: str | None = None` to
  `GateOutcome` (additive, last). In `verify`, detect `start_line is None` before
  any read-back and return the not-verifiable outcome (`skipped_reason=
  "no-line-range"`, `passed=False`, `failed=False`, not scored). Scoring algorithm
  unchanged.
- All Step-9 tests pass.

#### Step 11 — `locate` propagates `gate-skipped:no-line-range` (RED)
- Extend `harpyja/orchestrator/test_locate.py`:
  - `test_locate_auto_escalates_on_not_verifiable_when_tier_remains` — in `auto`
    with a Deep tier wired, a not-verifiable gate outcome **escalates** (verification
    unavailable, don't stop), Tier-2 runs (AC13).
  - `test_locate_carries_no_line_range_marker_when_no_tier_remains` — with no Deep
    tier, the coarse span is carried best-effort tagged
    `gate-skipped:no-line-range`, never at high confidence (AC13).
  - `test_no_line_range_marker_distinct_from_low_confidence_and_scoring_failed` —
    the marker never collapses into `gate-low-confidence` / `gate-scoring-failed`
    (AC13).
- Tests fail: `locate.py` has no `GATE_SKIPPED_NO_LINE_RANGE` constant and does
  not read `outcome.skipped_reason`.

#### Step 12 — `locate` not-verifiable routing + marker (GREEN)
- `harpyja/orchestrator/locate.py`: add the stable
  `GATE_SKIPPED_NO_LINE_RANGE = "gate-skipped:no-line-range"`; read
  `outcome.skipped_reason` in `_locate_auto` (and `_locate_scout` informational
  path) — treat not-verifiable like a non-passing result: escalate in `auto` if a
  tier remains, else carry best-effort with the marker, never high confidence.
- All Step-11 tests pass.

### Phase 4 — Harness degrade visibility (Deliverable 2)

#### Step 13 — Overlap oracle path-only credit (RED)
- Extend `harpyja/eval/test_metrics.py`:
  - `test_span_hit_path_only_for_file_level_citation` — a file-level (`None`-line)
    citation in the same file as an expected span scores a **path-only** match,
    recorded **distinctly** from a line-overlap match (AC18).
  - `test_span_hit_file_level_branch_before_line_arithmetic` — the path-only branch
    is taken **before** the `cited.start_line <= expected.end_line` comparison (no
    `None` crash) (AC18).
- Tests fail: `span_hit_primary` does line arithmetic unconditionally and
  `TypeError`s on a `None` cited line; there is no path-only distinction.

#### Step 14 — `_any_primary_overlap` guards `None` lines (GREEN)
- `harpyja/eval/metrics.py`: in `span_hit_primary` (and the oracle reuse), guard
  `cited.start_line is None` → path-only match **before** the line comparison;
  surface the path-only-vs-line distinction so a coarse hit is never counted as a
  line hit. One oracle, no second definition.
- All Step-13 tests pass; existing oracle-reuse tests stay green.

#### Step 15 — `EvalConfig.degraded_dominated_threshold` knob (RED)
- Extend `harpyja/eval/test_config.py`:
  - `test_eval_config_has_degraded_dominated_threshold_default` — new field
    defaults to `0.5` (AC15).
  - `test_eval_config_is_independent_of_settings` (extend the existing
    disjointness assertion) — `degraded_dominated_threshold` is field-disjoint
    from production `Settings` (AC15).
- Tests fail: `EvalConfig` has no `degraded_dominated_threshold` field.

#### Step 16 — Add the eval-only threshold knob (GREEN)
- `harpyja/eval/config.py`: append `degraded_dominated_threshold: float = 0.5`
  (frozen dataclass, eval-only, never read by the SUT).
- All Step-15 tests pass.

#### Step 17 — Report schema 0011/1 additivity + null-line tolerance (RED)
- Extend `harpyja/eval/test_report.py`:
  - `test_report_schema_version_is_0011` — `SCHEMA_VERSION == "0011/1"` (AC16).
  - `test_new_aggregate_fields_present_with_defaults` — `scout_degrade_count`,
    `scout_degrade_rate`, `degraded_dominated`, `reliability_notes`,
    `fc_citation_spanned_count`, `fc_citation_filelevel_count`,
    `fc_citation_dropped_count` appear via `_AGGREGATE_DEFAULTS`;
    `degraded_dominated_threshold` via `_RUN_METADATA_DEFAULTS` (AC16, per the
    §Deliverable-2 placement table).
  - `test_pre_0011_and_0011_shapes_both_validate` — a block omitting the new
    fields validates via defaults, and a fully-populated 0011 block validates;
    both pass the one loud `validate_report` (AC16).
  - `test_validate_report_tolerates_null_cited_lines` — a case `citations` entry
    with `start_line: null, end_line: null` passes `validate_report`; gold
    `expected_spans` stay int-only (AC19, validator side).
- Tests fail: `SCHEMA_VERSION` is `"0010/1"`; the new fields and the null-line
  tolerance are absent.

#### Step 18 — Report fields + version bump + null tolerance (GREEN)
- `harpyja/eval/report.py`: bump `SCHEMA_VERSION` to `"0011/1"`; append the new
  field names to `_AGGREGATE_FIELDS` / `_RUN_METADATA_FIELDS`; add their defaults
  to `_AGGREGATE_DEFAULTS` / `_RUN_METADATA_DEFAULTS` (centralized, last-with-
  defaults); ensure `validate_report` tolerates null cited `start_line`/`end_line`
  on case citations.
- All Step-17 tests pass.

#### Step 19 — Scout result carries the shape tally (carrier plumbing) (RED)
- Extend `harpyja/scout/test_scout.py` (or `test_scout_normalize.py` where the
  engine is exercised):
  - `test_scout_engine_exposes_fc_citation_tally` — after `ScoutEngine.search`,
    the per-shape tally `{spanned, filelevel, dropped}` is readable as metadata on
    the result/engine (the one defined production→aggregation path) (AC17,
    carrier).
- Tests fail: `ScoutEngine.search` returns a bare `list[CodeSpan]` with no tally
  side-channel.

#### Step 20 — Thread the tally from parse/normalize to the engine (GREEN)
- `harpyja/scout/engine.py` (+ `normalize.py` return): plumb the
  `{spanned, filelevel, dropped}` tally produced in Steps 4/6 onto the Scout
  result metadata that `eval/runner.py` reads — without changing the
  `list[CodeSpan]` the orchestrator consumes (the orchestrator still never branches
  on tier internals).
- All Step-19 tests pass.

#### Step 21 — Runner degrade counters + null serialization (RED)
- Extend `harpyja/eval/test_runner.py`:
  - `test_runner_reports_scout_degrade_count_and_rate` — `scout_degrade_count`
    (cases whose outcome carries a `scout-degraded:*` marker) and
    `scout_degrade_rate = count / cases_attempted` appear in the aggregate (AC14).
  - `test_runner_degrade_rate_null_with_zero_denominator` — zero `cases_attempted`
    → `scout_degrade_rate` is `null` paired with the (zero) count, never `0.0`
    (AC14).
  - `test_runner_aggregates_fc_citation_shape_counts` — the per-run
    `fc_citation_spanned_count` / `filelevel_count` / `dropped_count` aggregate
    from the Step-20 carrier (AC17, aggregate).
  - `test_runner_serializes_file_level_citation_lines_as_null` — a file-level
    cited span serializes `start_line`/`end_line` as JSON `null` and the assembled
    report passes `validate_report` (AC19, serializer side).
- Tests fail: `aggregate_outcomes` / `_citation_dict` emit none of these; the
  span dict would carry `None` un-asserted.

#### Step 22 — Runner aggregation + null serialization (GREEN)
- `harpyja/eval/runner.py`: count `scout-degraded:*` markers per run; compute
  `scout_degrade_rate` (null-with-count on zero denominator); aggregate the
  carrier's shape counts into `fc_citation_*_count`; keep `_citation_dict`
  emitting `None` lines as JSON `null`. Populate the new aggregate fields.
- All Step-21 tests pass.

#### Step 23 — `degraded_dominated` + composable `reliability_notes` (RED)
- Extend `harpyja/eval/test_swebench_runner.py` (and/or `test_swebench_eval.py`):
  - `test_swebench_sets_degraded_dominated_above_threshold` —
    `scout_degrade_rate > degraded_dominated_threshold` (0.5) →
    `degraded_dominated=true`; `reliability_notes` carries `"degraded-dominated"`
    and marks escalation/accuracy/OQ2 unreliable (AC15).
  - `test_swebench_reliability_notes_compose` — `degraded-dominated` and
    `indicative-only` both present; neither overwrites the other (AC15).
  - `test_swebench_not_dominated_below_threshold` — rate ≤ threshold →
    `degraded_dominated=false`, note absent (AC15).
- Tests fail: `run_swebench` computes no degrade rate, sets no
  `degraded_dominated`, and has no composable `reliability_notes`.

#### Step 24 — swebench degrade-dominance + notes + threshold record (GREEN)
- `harpyja/eval/swebench_eval.py`: compute `scout_degrade_rate` from pooled
  outcomes, set `degraded_dominated = rate > eval_config.degraded_dominated_
  threshold`, append composable `reliability_notes`, and record
  `degraded_dominated_threshold` in run metadata. "12/12 scout-degraded" surfaces
  at report top.
- All Step-23 tests pass; existing swebench tests stay green.

### Phase 5 — Integration (`@pytest.mark.integration`, skip-not-fail)

#### Step 25 — Live Scout zero backend-error on flask (RED→GREEN, integration)
- Extend `harpyja/scout/test_scout_integration.py`:
  - `test_live_scout_flask_returns_tier1_without_backend_error` — live Scout on a
    real flask issue query returns tier-1 citations with **zero** `backend-error`
    (the exact 12/12-broken case) (AC20). Skips (not fails) where the live model
    is unavailable.
- Passes once Phases 1–4 land; it is the end-to-end witness, not a new prod
  change.

#### Step 26 — N=12 re-run degrade visibility (RED→GREEN, integration)
- Extend `harpyja/eval/test_swebench_integration.py`:
  - `test_swebench_n12_rerun_degrade_rate_below_one` — re-run the N=12 point
    subset and assert `scout_degrade_rate < 1.0`, Scout emitted ≥1 tier-1 span,
    `escalation_rate` is a non-null measured value, and a per-case escalation
    reason is recorded for each case (AC21). Skip-not-fail.
- Passes once Phases 1–4 land.

### Refactor (optional, after each GREEN where duplication appears)
- **R1 (after Steps 4/6):** the file-level-vs-spanned shape test
  (`start_line is None and end_line is None`, half-`None` rejection) is duplicated
  in `parse_final_answer` and `normalize_spans` — extract one `is_file_level` /
  `assert_shape_invariant` helper on the `scout/` side and have both call it. All
  parser + normalize tests stay green.
- **R2 (after Step 22):** the per-shape tally and degrade-marker counting may
  duplicate small loops between `runner.py` and `swebench_eval.py` — fold into one
  helper so the two aggregation sites cannot drift. All eval tests stay green.

## AC → step coverage

| AC | Step(s) |
|----|---------|
| AC1  bare-path → file-level span | 3, 4 |
| AC2  `path:start[:end]` stays spanned (regression) | 3, 4 |
| AC3  mixed bare + spanned in one answer | 3, 4 |
| AC4  bare-path both lines `None` (no fabricated range) | 3, 4 |
| AC5  malformed line → file-level | 3, 4 |
| AC6  normalize survive-path (returned carrying `None`) | 5, 6 |
| AC7  normalize deep-budget lined spans byte-identical | 5, 6 |
| AC8  floor preserved vs honest-empty `[]` | 3, 4 |
| AC9  dropped refs → honest-empty `[]`, not backend-error | 5, 6 |
| AC10 dropped refs counted + per-drop log | 5, 6 |
| AC11 committed real-FC fixture grounds AC1–5/AC22 | 0, 3 |
| AC12 formatter survive-path (no merge, no crash) | 7, 8 |
| AC13 gate not-verifiable + `gate-skipped:no-line-range` + routing | 9, 10, 11, 12 |
| AC14 `scout_degrade_count` / `scout_degrade_rate` (+ null/zero) | 21, 22 |
| AC15 `degraded_dominated` + composable `reliability_notes` + threshold knob | 15, 16, 23, 24 |
| AC16 schema 0011/1 additivity, both shapes validate | 17, 18 |
| AC17 fc_citation shape counters (producer→carrier→aggregate) | 3/4, 19/20, 21/22 |
| AC18 overlap oracle path-only credit, guarded before arithmetic | 13, 14 |
| AC19 null cited lines serialized + tolerated by validator | 17/18, 21/22 |
| AC20 live Scout zero backend-error (flask) | 25 |
| AC21 N=12 re-run degrade-rate < 1.0, measured escalation | 26 |
| AC22 bare-path false-positive (prose filename) negative control | 0, 3, 4 |
| AC23 half-`None` rejected at parse + normalize boundary | 3/4, 5/6 |

## Delegation

- Steps 0, 25, 26 (live FastContext spike + integration witnesses) → delegate to
  an agent with live-model / SWE-bench worktree access (reason: requires the real
  FC agent + flask worktree, outside the unit sandbox; Step 0 also decides the
  seam (a)/(c) gate the rest of the plan keys on).
- Steps 1–24 (unit RED/GREEN) → suitable for a Python TDD implementer working
  network-free with injected collaborators (reason: pure unit work behind the
  existing fakes; the bulk of the plan).

## Risk

- **Step 0 disproves seam (a)** (no `<final_answer>` refs under `citation=False`)
  → mitigation: pre-stated (c) fallback (catch-and-parse the `format_citations`
  crash); only Step 2.2's acquisition sub-task changes, AC20 still holds, every
  downstream step is seam-agnostic.
- **AC22 regex over-matches prose filenames** → mitigation: the bare-path grammar
  is built against the Step-0 *observed* delimiting structure with the fixture's
  negative-control token asserted, never a naked optional `:\d+`.
- **A missed `None`-line consumer crashes a tier** (the round-3 `format.py` miss)
  → mitigation: each consumer on the enumerated data path gets its OWN RED→GREEN
  pair (Steps 5–14), ordered producer→…→metrics so a `None` span is made safe
  before the next stage sees it.
- **Tally carrier leaks tier internals into the orchestrator** → mitigation: the
  tally rides a Scout-result side-channel read only by `eval/runner.py`; the
  `list[CodeSpan]` the orchestrator consumes is unchanged (Step 20), preserving
  "callers never branch on which engine ran".
- **Schema bump breaks the pre-0011 validator** → mitigation: additive last-with-
  defaults in centralized `_*_DEFAULTS`, and `test_pre_0011_and_0011_shapes_both_
  validate` asserts both shapes pass the one loud validator (Step 17).
- **Eval knob bleeds into production `Settings`** → mitigation:
  `degraded_dominated_threshold` lives on `EvalConfig`, asserted field-disjoint
  from `Settings` (Step 15).
