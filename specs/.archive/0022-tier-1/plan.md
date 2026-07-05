---
spec: "0022"
status: planned
strategy: tdd
---

# Plan — 0022 Tier-1 (Scout locate-accuracy diagnosis on SWE-bench)

## Approach

Measurement-not-construction, frozen-SUT lineage (0019/0020/0021). ALL new code is
additive under `harpyja/eval/`; nothing under `harpyja/scout/` or
`harpyja/orchestrator/` changes. Two new modules plus one doc:

- `harpyja/eval/locate_accuracy.py` — a PURE eval-side projection above the frozen
  oracle: citation normalization (reads `ScoutTally`, never re-derives suffix
  recovery), a `LocateBucket` 4-way taxonomy with strict precedence, two-granularity
  scoring with `gap` as a first-class metric, and the ordered `decide_finding`
  decision rule. The single deliberate re-map (path-only right-file `"file"` →
  `RIGHT_FILE_WRONG_SPAN`) lives ONLY here; `metrics.py` is untouched and its
  `span_hit_kind` is reused as the overlap oracle.
- `harpyja/eval/locate_probe.py` — a Scout-ONLY micro-run (no gate/judge/Deep): drives
  `scout_engine.search` per case, resets/reads `last_tally` (spec 0011/0012
  side-channel), captures turns-used HONESTLY at the eval boundary (labeled
  `unavailable` when no seam exists — never a fabricated counter), stratifies cases
  (repo × gold-span-size band), builds the regenerated distribution, and runs the
  labeled-non-primary query-reformulation probe (raw vs distilled), keeping probe
  cases OUT of the baseline.
- `specs/0022-tier-1/findings.md` — the AC7/AC8/AC9 deliverable (typed finding via the
  decision rule, per-case rows + aggregates, representativeness judgment,
  pre-registered prior). Doc task, last.

Reused seams (verified, unchanged): `metrics.span_hit_kind` / `span_hit_secondary`;
`EvalConfig.proximity_window_lines` (the window — no new constant);
`scout.engine.ScoutTally` + `ScoutEngine.last_tally`; `runner.LocateStack` /
`build_live_stack` / `scout_engine.search(query, scope=repo)`; integration gating
`_live_stack_available` / `_NEEDS_STACK` / `_settings_live` / `_deny_nonloopback_egress`
/ `_live_cases`; and the 0019 preflight `preflight_models_present` / `PreflightError`
(behind `gateway.assert_local`). All GREEN preceded by RED.

## Fail posture (a skip must never masquerade as a completed measurement)

Two distinct postures, deliberately NOT the same answer (developer decision, 2026-07-05):

- **Integration test files stay skip-not-fail by default** — a host without a served
  4B stack must not red-fail `uv run pytest` for infrastructure this spec doesn't own
  (the 0019–0021 convention). Gated on `_live_stack_available()` → `pytest.skip`.
- **The deliverable-producing path fails LOUD.** `findings.md` may never be produced
  from a skip. Two mechanisms, both additive:
  1. **Preflight gate.** Before the live probe that feeds `findings.md`, call
     `preflight_models_present(settings, tags_payload)` (0019) behind
     `assert_local`; an absent/misconfigured stack raises `PreflightError` naming the
     missing model — never a silent empty distribution (the guardrail's
     "fail-loud-at-setup, no silent empty result" floor).
  2. **Opt-in strict switch.** A new `require_live_stack()` eval helper reads
     `HARPYJA_REQUIRE_LIVE_STACK` (truthy) and, when set, converts the integration
     `skip` into a hard **failure** (`pytest.fail(_NEEDS_STACK)`) — so the intentional
     closure run cannot go green by skipping. Default-unset = skip (CI-safe).

  Net: unrelated CI stays green; the run that produces the finding cannot.

## Test-first sequence

### Step 1 — Citation normalization before classification (RED)  [AC3]
- Add `harpyja/eval/test_locate_accuracy.py`:
  - `test_normalize_citations_reads_recovery_counts_from_tally` — a citation resolved
    by suffix recovery is present in the effective set; `recovered_*` counts come from
    `ScoutTally`, not re-derived.
  - `test_normalize_citations_drops_malformed_into_normalization_dropped` — `dropped`
    from the tally surfaces as `normalization_dropped`, never re-bucketed.
  - `test_normalize_empty_only_after_drop_is_distinct_from_returned_nothing` — effective
    citations empty but `normalization_dropped > 0` is recorded distinctly from a case
    Scout returned nothing for (`normalization_dropped == 0`).
  - `test_normalize_citations_retains_file_level_shape` — a line-less `CodeSpan`
    (`is_file_level`) survives normalization as a path-only citation.
- Tests fail: `locate_accuracy` module / `normalize_citations` do not exist yet.

### Step 2 — Implement normalization projection (GREEN)  [AC3]
- Implement `harpyja/eval/locate_accuracy.py` with a frozen `NormalizedCitations`
  (`effective: tuple[CodeSpan, ...]`, `normalization_dropped: int`,
  `recovered_spanned/recovered_filelevel: int`) and pure
  `normalize_citations(citations, tally: ScoutTally | None) -> NormalizedCitations`
  reading counts off `ScoutTally`. No suffix logic re-implemented.
- All step-1 tests pass.

### Step 3 — 4-way taxonomy: MECE + precedence (RED)  [AC1]
- Add to `harpyja/eval/test_locate_accuracy.py`:
  - `test_classify_case_correct_on_line_overlap` — a `"line"`-kind hit → `CORRECT`.
  - `test_classify_case_path_only_right_file_is_right_file_wrong_span` — oracle
    `"file"` hit re-mapped to `RIGHT_FILE_WRONG_SPAN` (NOT `CORRECT`), with the
    path-only sub-flag.
  - `test_classify_case_within_window_sets_within_window_flag` — lined miss within
    `proximity_window_lines` → `RIGHT_FILE_WRONG_SPAN` + `within_window`.
  - `test_classify_case_beyond_window_is_right_file_wrong_span_without_flag` — lined
    miss in gold file beyond window → `RIGHT_FILE_WRONG_SPAN`, no `within_window`.
  - `test_classify_case_wrong_file_when_no_citation_in_gold_file` → `WRONG_FILE`.
  - `test_classify_case_empty_when_no_effective_citation` → `EMPTY`.
  - `test_classify_case_multi_citation_precedence_takes_best` — gold-file + wrong-file
    mix → the better bucket wins.
  - `test_classify_case_correct_beats_right_file_wrong_span` — line-hit + path-only in
    same case → `CORRECT`.
  - `test_classify_case_malformed_only_is_empty_with_dropped_positive` → `EMPTY` with
    `normalization_dropped > 0` (boundary from AC1).
  - `test_classify_case_is_mece_and_total_over_fixture_matrix` — every fixture lands in
    exactly one bucket.
- Tests fail: `LocateBucket` enum and `classify_case` do not exist.

### Step 4 — Implement `LocateBucket` + `classify_case` (GREEN)  [AC1]
- Add `LocateBucket` enum `{EMPTY, WRONG_FILE, RIGHT_FILE_WRONG_SPAN, CORRECT}`, a
  `SubFlags` record (`within_window: bool`, `path_only_right_file: bool`), and pure
  `classify_case(citations, expected_spans, *, window) -> tuple[LocateBucket, SubFlags]`
  enforcing `CORRECT > RIGHT_FILE_WRONG_SPAN > WRONG_FILE > EMPTY` via
  `metrics.span_hit_kind` (`"line"` → CORRECT; `"file"` → RIGHT_FILE_WRONG_SPAN) and
  `span_hit_secondary(..., window)` for the `within_window` sub-flag.
- All step-3 tests pass.

### Step 5 — Two-granularity scoring + first-class gap (RED)  [AC2]
- Add to `harpyja/eval/test_locate_accuracy.py`:
  - `test_file_level_and_span_level_computed_independently`.
  - `test_gap_is_first_class_all_path_only_file_one_span_zero` — all-path-only fixture →
    FILE=1.0, SPAN=0.0, `gap == 1.0`.
  - `test_span_level_counts_only_correct`.
  - `test_empty_rate_recorded_on_distribution`.
  - `test_distribution_counts_are_mece_sum_to_n`.
- Tests fail: `score_distribution` / `LocateDistribution` do not exist.

### Step 6 — Implement scoring (GREEN)  [AC2]
- Add frozen `LocateDistribution` (per-bucket counts, `n`, `file_level_accuracy`,
  `span_level_accuracy`, `gap`, `empty_rate`, `normalization_dropped_total`) and pure
  `score_distribution(classified) -> LocateDistribution` with
  `file = |CORRECT ∪ RIGHT_FILE_WRONG_SPAN| / n`, `span = |CORRECT| / n`,
  `gap = file - span`.
- All step-5 tests pass.

### Step 7 — Typed-finding decision rule, ordered (RED)  [AC7]
- Add to `harpyja/eval/test_locate_accuracy.py`:
  - `test_decide_finding_benchmark_unrepresentative_when_probe_fires` — low-F/empty-
    dominant AND `delta_empty` materially > 0 → `BENCHMARK_UNREPRESENTATIVE`.
  - `test_decide_finding_benchmark_unrepresentative_when_not_representative` — low-F/
    empty-dominant AND `representative=False` → same (rule 1's OR branch).
  - `test_decide_finding_precision_fixable_when_gap_large_and_f_not_low`.
  - `test_decide_finding_retrieval_fundamental_when_low_f_and_probe_flat` — low-F AND
    `delta_empty ≈ 0` AND representative → `RETRIEVAL_FUNDAMENTAL`.
  - `test_decide_finding_mixed_when_no_dominant_mode`.
  - `test_decide_finding_evaluates_rules_in_declared_order` — a case satisfying both
    rule 1 and rule 2 returns rule 1's label (precedence lock).
  - `test_decide_finding_bands_are_predeclared_named_constants`.
- Tests fail: `decide_finding` / `Finding` / band constants do not exist.

### Step 8 — Implement `decide_finding` + bands (GREEN)  [AC7]
- Add pre-declared band constants (e.g. `LOW_FILE_BAND`, `EMPTY_DOMINANT_BAND`,
  `LARGE_GAP_BAND`, `MATERIAL_DELTA_EMPTY`), a frozen `Finding` (`label`, observed
  `F/S/E/G`, `delta_empty`, all true conditions, `routes_to` next-spec name), and pure
  `decide_finding(dist, *, delta_empty, representative) -> Finding` evaluating the four
  rules in order (BENCHMARK_UNREPRESENTATIVE > PRECISION_FIXABLE > RETRIEVAL_FUNDAMENTAL
  > MIXED), recording every true condition (0020 pattern), not just the winner.
- All step-7 tests pass.

### Step 9 — No-SUT-change guard + frozen-oracle snapshot (RED)  [AC10]
- Add to `harpyja/eval/test_locate_accuracy.py`:
  - `test_locate_accuracy_sut_surface_is_sanctioned_allowlist` — asserts
    `locate_accuracy.SUT_SURFACE` equals the exact frozen public names the module is
    allowed to touch (`metrics.span_hit_kind`, `metrics.span_hit_secondary`,
    `ScoutTally`, `CodeSpan.is_file_level`) — a behavior/allowlist lock, not a source
    grep.
  - `test_frozen_oracle_span_hit_kind_behavior_snapshot` — a fixed input→output table
    over `metrics.span_hit_kind` (`"line"` / `"file"` / `None`); any edit to the frozen
    oracle breaks this lock (0020 P2 precedent).
  - `test_locate_accuracy_makes_no_fastcontext_internal_reference` — asserts the module
    imports nothing from `fastcontext` / `harpyja.scout.client` / orchestrator internals
    (import-surface check).
- Tests fail: `SUT_SURFACE` allowlist constant not yet declared.

### Step 10 — Declare `SUT_SURFACE` allowlist (GREEN)  [AC10]
- Add the `SUT_SURFACE` frozenset + a module docstring recording the additive-only
  contract and the single deliberate re-map.
- All step-9 tests pass.

### Step 11 — Scout-only probe: pure assembly + honest turns-used (RED)  [AC4/AC5/AC6 unit]
- Add `harpyja/eval/test_locate_probe.py` (unit, fake scout_engine exposing preset
  spans + a fixed `last_tally`, à la `test_runner.py`):
  - `test_stratify_cases_by_repo_and_span_size_band` — strata keyed (repo × gold-span-
    size band); named bands.
  - `test_run_locate_probe_resets_last_tally_per_case` — a stale tally from a prior case
    cannot leak (mirrors runner reset).
  - `test_run_locate_probe_collects_citations_tally_and_builds_distribution` — per-case
    citations + tally pooled into a `LocateDistribution` (reuses step-6 scorer).
  - `test_count_turns_from_trajectory_counts_steps` — the pure trajectory turn-counter
    (`count_turns(trajectory_path)`) counts agent steps from a **fixture** `.jsonl`
    trajectory (pin the counting rule: one turn per agent step-entry); a
    malformed/absent trajectory → `None`, never a guessed number.
  - `test_counting_agent_factory_wraps_real_and_reads_trajectory_before_cleanup` — the
    eval-side `counting_agent_factory` delegates to the REAL `make_fastcontext_agent`
    (measures real behavior, not a fake) and, inside its own `run()`, reads
    `trajectory_file` and stashes the turn count in a side-channel BEFORE the frozen
    client's `finally` cleanup unlinks it. (Uses a stub agent-factory standing in for
    `make_fastcontext_agent` to keep the unit hermetic; the real one is wired live.)
  - `test_turns_used_source_labels_trajectory_vs_unavailable` — `turns_used_source ==
    "trajectory"` when the count is read; `"unavailable"` on Path B (CLI, no factory
    seam) or when the factory is not wired — a labeled gap, NEVER a fabricated counter
    (0021 honesty precedent).
  - `test_reformulation_probe_records_empty_rate_delta` — raw vs distilled one-line
    query empty-rate delta computed.
  - `test_reformulation_probe_cases_excluded_from_baseline` — probe cases are labeled
    non-primary and absent from the regenerated baseline distribution.
  - `test_require_live_stack_skips_when_env_unset` — with `HARPYJA_REQUIRE_LIVE_STACK`
    unset and the stack absent, `require_live_stack()` requests a skip (CI-safe).
  - `test_require_live_stack_fails_when_env_set` — with the env truthy and the stack
    absent, `require_live_stack()` requests a hard failure (the strict closure switch),
    never a skip.
- Tests fail: `locate_probe` module and its functions do not exist.

### Step 12 — Implement `locate_probe.py` (GREEN)  [AC4/AC5/AC6 unit]
- Implement `stratify_cases`, `run_locate_probe(cases, settings, *, repo_path, stack)`
  (drives `scout_engine.search` ONLY — no `locate`, no gate/Deep; resets/reads
  `last_tally`), plus the turns-used machinery:
  - `count_turns(trajectory_path) -> int | None` — pure trajectory step-counter (the
    pinned counting rule); `None` on absent/malformed.
  - `counting_agent_factory(turns_sink)` — an eval-side `AgentFactory` that wraps the
    REAL `make_fastcontext_agent(work_dir, trajectory_file)` and, in its `run()`, reads
    the trajectory via `count_turns` BEFORE the frozen client cleans it up, appending to
    `turns_sink`. Wired into the live Scout stack via
    `build_scout_engine(settings, repo, agent_factory=…)` (public seam — no frozen edit,
    Path A only).
  - `turns_used_source ∈ {"trajectory", "unavailable"}` on the result.
  A `ProbeResult` carries the distribution + per-case rows + tally aggregates +
  turns-used(+source); `run_reformulation_probe(...)` returns the raw-vs-distilled
  empty-rate delta with probe cases held out of the baseline; `require_live_stack()`
  reads `HARPYJA_REQUIRE_LIVE_STACK`.
- All step-11 tests pass.

### Step 13 — Live Scout-only integration (RED, skip-not-fail)  [AC4/AC5/AC6 integration]
- Add `harpyja/eval/test_locate_probe_integration.py`, reusing
  `_live_stack_available` / `_NEEDS_STACK` / `_settings_live` / `_live_cases` /
  `_deny_nonloopback_egress`; every test routes its gate through `require_live_stack()`
  (skip when `HARPYJA_REQUIRE_LIVE_STACK` unset + stack absent; hard-fail when the env
  is set + stack absent) instead of a bare `pytest.skip`:
  - `test_scout_only_stratified_regenerated_distribution` — real Scout over the
    stratified subset produces a fresh distribution + empty-rate (NOT inheriting 0021's
    contaminated counts). (AC4)
  - `test_turns_used_and_suffix_recovery_recorded_at_eval_boundary` — `last_tally`
    recovery hit/drop + turns-used captured at the boundary via the injected
    `counting_agent_factory` (real agent, trajectory read before cleanup),
    `turns_used_source == "trajectory"`; no frozen-internals *edit*. (AC5)
  - `test_reformulation_probe_raw_vs_distilled_empty_rate_delta` — probe runs live,
    records `delta_empty`, kept out of the baseline. (AC6)
  - `test_locate_probe_no_nonloopback_egress` — under `_deny_nonloopback_egress()` the
    Scout-only run makes no non-loopback call.
- Tests fail (when stack present): live entry wiring for stratified probe not complete;
  otherwise skip.

### Step 14 — Wire live probe entry (GREEN, skip-not-fail)  [AC4/AC5/AC6 integration]
- Finish the live path in `locate_probe.py`: build a Scout-only stack whose
  `scout_engine` is constructed via `build_scout_engine(settings, repo,
  agent_factory=counting_agent_factory(sink))` (NOT the default `build_live_stack`, so
  turns-used is captured) — no gate/judge/Deep wired; iterate stratified cases, pool
  results. No SUT change; the `agent_factory` seam is a public constructor param.
- All step-13 tests pass when the stack is available; skip/fail per `require_live_stack`.

### Step 15 — Refactor (optional)
- Fold shared distribution-row construction used by both `run_locate_probe` and the
  reformulation probe into one helper (avoid the two GREEN duplications); pin with a
  reuse assertion (`test_probe_rows_built_by_shared_helper`). All tests still pass.

### Step 16 — Findings deliverable (DOC, last)  [AC7/AC8/AC9]
- **Preflight FIRST (fail-loud gate):** before producing the finding, the deliverable
  path calls `preflight_models_present(settings, tags_payload)` (0019, behind
  `assert_local`). An absent/misconfigured stack raises `PreflightError` naming the
  missing model — the finding is NEVER produced from a skipped/empty run. The intended
  closure run sets `HARPYJA_REQUIRE_LIVE_STACK=1` so `require_live_stack()` also
  hard-fails rather than skips.
- Write `specs/0022-tier-1/findings.md`: the typed `Finding` from `decide_finding`
  (stating observed `F/S/E/G` and probe `delta_empty` and the routed next-spec); raw
  per-case rows (case-id, bucket, sub-flags, citation vs gold) + aggregate counts
  (AC8); the explicit representativeness judgment with `delta_empty` as supporting
  evidence (AC9); and the pre-registered prior (0021 → `RETRIEVAL_FUNDAMENTAL` unless
  the probe fires) as the falsifiability guard.
- Honesty boundary: the PRIMARY distribution must come from a real live run (preflight
  guarantees it). A *secondary/labeled-estimate* note is permitted only for genuinely
  unrecoverable sub-signals (e.g. `turns_used` when no seam exists), never for the
  headline distribution — and each such estimate is labeled, never fabricated (0021).

## AC mapping

- AC1 → Steps 3–4
- AC2 → Steps 5–6
- AC3 → Steps 1–2
- AC4 → Steps 11–12 (unit), 13–14 (integration)
- AC5 → Steps 11–12 (unit turns-used honesty), 13–14 (integration)
- AC6 → Steps 11–12 (unit), 13–14 (integration)
- AC7 → Steps 7–8 (rule), Step 16 (recorded finding)
- AC8 → Step 16
- AC9 → Step 16
- AC10 → Steps 9–10
- Fail-posture (preflight gate + `require_live_stack`) → Steps 11–12 (helper + unit),
  13–14 (integration usage), 16 (deliverable preflight)

## Delegation

- Steps 1–10 (pure classifier/scoring/decision, no I/O) → keep in-thread; tight
  RED→GREEN, no external stack. Strength match: deterministic unit TDD.
- Steps 13–14, 16 (live Scout-only run + findings) → delegate to an integration/eval
  runner with the served FastContext+Ollama stack (per repo memory: Q8 FastContext on
  local Ollama, 32 GB host). Reason: requires a live loopback endpoint the unit thread
  should never depend on; skip-not-fail keeps CI green when absent.

## Risk

- Turns-used is not on `search`'s return nor on `ScoutTally` (refs, not turns), and the
  trajectory JSONL that records turns is unconditionally `os.unlink`'d in the frozen
  client's `finally` (`client.py:322-323,359-360,372-377`) → mitigation: capture via the
  **public `agent_factory` injection seam** (`build_scout_engine(..., agent_factory=…)`
  → `ScoutClient`, Path A) — an eval-side factory wraps the REAL
  `make_fastcontext_agent` and `count_turns(trajectory)` BEFORE cleanup fires. Soft
  coupling: the turn count is read from FastContext's trajectory *format*, so the
  counting rule is pinned by a fixture unit test and labeled
  `turns_used_source="trajectory"`. Path B (CLI, no factory seam) and unwired runs fall
  back to `turns_used_source="unavailable"` — a labeled gap, never a fabricated counter
  or a frozen-client edit (0021 precedent).
- Small stratified N (≤38, per-stratum smaller) → mitigation: self-flag
  `indicative_only`; per-case rows are the auditable ground truth (AC8); bands are
  provisional named constants.
- Probe contaminating the baseline → mitigation: probe cases labeled non-primary and
  asserted absent from the baseline distribution (`test_reformulation_probe_cases_
  excluded_from_baseline`).
- Re-map drift into the SUT oracle → mitigation: the `"file"`→RIGHT_FILE_WRONG_SPAN
  re-map lives only in `locate_accuracy`; guarded by the frozen-oracle snapshot +
  `SUT_SURFACE` allowlist (AC10).
- Inheriting 0021's contaminated counts → mitigation: distribution regenerated from
  `scout_engine.search` outputs; no read of `wrong_tier1_count` /
  `span_hit_rate_primary` / `gate_catch_rate`.
