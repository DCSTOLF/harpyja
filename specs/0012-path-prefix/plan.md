---
spec: "0012"
status: planned
strategy: tdd
---

# Plan — 0012 path-prefix

Test-first sequence ordered along the data path **producer → sink**, per the
conventions' blast-radius rule (the new shape is handled before the next stage sees
it). The two anti-drift seams that must move together in one change:

- `normalize_spans_with_tally` return arity grows (adds `recovered_spanned`,
  `recovered_filelevel`); its only non-test callers are `normalize.py::normalize_spans`
  and `engine.py::ScoutEngine.search` — both made shape-safe in the same step.
- The report `_AGGREGATE_*` field set is the single declared source; the two
  aggregation readers (`eval/runner.py`, `eval/swebench_eval.py`) both consume the new
  counts.

Signature decisions (load-bearing):

- `normalize_spans_with_tally(raw, repo_root, *, max_citations, max_span_lines,
  file_set: frozenset[str] | None = None) -> tuple[list[CodeSpan], int, int, int]`
  returning `(spans, dropped, recovered_spanned, recovered_filelevel)`. `file_set`
  defaults to `None`/empty ⇒ **no recovery** (spec §1 graceful degrade); the legacy
  `normalize_spans` wrapper unpacks and discards the new ints, so its callers are
  untouched.
- `MIN_TAIL_SEGMENTS = 2` is a module constant in `normalize.py`.

## Test-first sequence

### Step 1 — normalize.py suffix-recovery core (RED) — AC1, AC2, AC3(a–e)
- Extend `harpyja/scout/test_scout_normalize.py`. **Fixture:** a `tmp_path` repo with
  real on-disk files so the post-recovery `is_file` re-validation passes — at minimum
  `src/flask/blueprints.py` (multi-line) and the directory `src/flask/__init__.py`;
  `file_set` is passed explicitly as a `frozenset` of repo-relative paths (the same
  strings the manifest would yield). Tests call
  `normalize_spans_with_tally(raw, str(tmp_path), max_citations=…, max_span_lines=…,
  file_set=…)` and assert on the returned `(spans, dropped, recovered_spanned,
  recovered_filelevel)` tuple.
  - `test_recover_unique_suffix_keeps_filelevel` — a file-level cite of
    `/pallets/flask/src/flask/blueprints.py` (out-of-repo absolute) recovers to
    `src/flask/blueprints.py`; span kept, `is_file_level` stays `True` (lines `None`),
    `recovered_filelevel == 1`, `dropped == 0`. (AC1)
  - `test_recover_unique_suffix_keeps_spanned_shape` — same path with a real line range
    recovers, stays spanned, `recovered_spanned == 1`, bucket unchanged. (AC1)
  - `test_recover_drops_when_no_unique_suffix` — cite `/pallets/flask/src/__init__.py`
    (suffix `src/__init__.py` not in flask, real file is `src/flask/__init__.py`) →
    dropped, `recovered_* == 0`, `dropped == 1`. (AC2)
  - `test_recover_skipped_when_file_set_absent` and
    `test_recover_skipped_when_file_set_empty` — `file_set=None` / `file_set=frozenset()`:
    every out-of-repo ref falls back to the spec-0011 drop, `recovered_* == 0`. (AC2)
  - `test_recover_interior_overlap_not_rewritten` — a cited path whose match would be an
    **interior** (non-trailing) segment overlap is never rewritten; only a manifest path
    that *ends with* the segment-aligned tail matches. (AC3a)
  - `test_recover_ambiguous_suffix_dropped` — `file_set` with two files ending
    `pkg/util.py` (`a/pkg/util.py`, `b/pkg/util.py`); cite tail `pkg/util.py` matches
    >1 → dropped, no fall-back to a shorter tail. (AC3b)
  - `test_recover_below_min_tail_segments_dropped` — a bare basename (`__init__.py`,
    1 segment < `MIN_TAIL_SEGMENTS`) is never recovered even if unique. (AC3c)
  - `test_recover_leading_segment_guard_dropped` — `file_set=["src/flask/blueprints.py"]`
    (top-level entry `src`); a cite whose only suffix match is via tail
    `flask/blueprints.py` (head `flask`, **not** a top-level manifest entry) is dropped,
    while the `src/flask/blueprints.py`-headed tail would be kept. (AC3d)
  - `test_recovered_span_revalidated_and_clamped` — a recovered **spanned** cite with an
    over-long / out-of-range line range is re-validated and clamped exactly like a
    non-recovered span (recovery composes with, never bypasses, 0011 validation). (AC3e)
- Tests fail: `normalize_spans_with_tally` has no `file_set` parameter (TypeError) and
  returns a 2-tuple, so unpacking 4 values fails; no recovery logic exists.

### Step 2 — normalize.py recovery implementation (GREEN) — AC1, AC2, AC3(a–e)
- Implement in `harpyja/scout/normalize.py`:
  - Add `MIN_TAIL_SEGMENTS = 2` and `file_set` keyword param; widen the return to
    `(spans, dropped, recovered_spanned, recovered_filelevel)`.
  - On the existing out-of-repo / nonexistent branch, **before** counting a drop, attempt
    bounded suffix recovery against `file_set`: for `k` from `len(segs)` down to
    `MIN_TAIL_SEGMENTS`, collect manifest paths equal to or ending in `"/" + tail`
    (segment-aligned); exactly-one at the longest `k` whose **tail head is a top-level
    manifest entry** → rewrite `span.path` to that manifest path and re-enter the normal
    repo-confine + `is_file` (+ clamp) validation; ambiguous / none / below-floor / empty
    `file_set` → fall through to the existing drop.
  - Increment `recovered_spanned` / `recovered_filelevel` by the kept span's shape.
  - Factor the suffix-match into a small private helper (e.g. `_recover_suffix(path,
    file_set) -> str | None`) so Step 1's cases and any future suffix index share one
    definition.
- Update the in-module caller `normalize_spans` to unpack the 4-tuple and discard the
  new ints (its public signature/return is unchanged).
- All Step-1 tests pass.

### Step 3 — honesty floor for a recovered file-level keep (RED) — AC3(f)
- The 0011 mechanism (`gate.py` sets `skipped_reason="no-line-range"` for any file-level
  citation; `locate.py` maps it to `GATE_SKIPPED_NO_LINE_RANGE` and never returns `"high"`)
  already governs file-level spans. A recovered file-level span is **still** `is_file_level`,
  so it must inherit that floor — this step is the guard test that recovery cannot
  smuggle in a fabricated line range or a verified read.
- Add to `harpyja/scout/test_scout_normalize.py`:
  - `test_recovered_filelevel_keeps_none_lines` — the recovered file-level span returned by
    normalize has `start_line is None and end_line is None` (no fabricated range), so it
    cannot read as line-verified downstream.
- Add to `harpyja/orchestrator/test_locate.py` (the gate-path sink):
  - `test_recovered_filelevel_citation_carries_no_line_range_marker` — drive `locate`
    `mode=auto` with a Scout engine whose normalized output is a single **recovered**
    file-level citation; assert the result notes contain `gate-skipped:no-line-range`
    and the confidence is **never** `"high"` (a recovered keep reads no more confidently
    than a non-recovered file-level one). Uses the existing fake-engine harness in
    `test_locate.py`; no live model.
- Tests fail only if Step 2 fabricated lines on a recovered keep; written here as the
  pinned regression guard for AC3(f).

### Step 4 — ScoutTally recovered_* + ScoutEngine threading (RED) — AC4
- Extend `harpyja/scout/test_scout.py`. **Fixture:** `tmp_path` repo with a real
  recoverable file (e.g. `src/flask/blueprints.py`).
  - `test_scout_tally_carries_recovered_counts` — construct `ScoutEngine(backend, seed,
    settings, repo_root, file_set=frozenset({"src/flask/blueprints.py"}))`; backend
    returns an out-of-repo file-level cite whose suffix recovers; after `.search`,
    `engine.last_tally.recovered_filelevel == 1` (and `recovered_spanned` for a lined
    variant), shape buckets `spanned`/`filelevel`/`dropped` consistent.
  - `test_scout_engine_no_file_set_means_no_recovery` — `ScoutEngine` built without a
    `file_set` (defaults empty) drops the same cite; `recovered_* == 0`. (AC2 degrade at
    the engine seam)
- Tests fail: `ScoutTally` has no `recovered_spanned`/`recovered_filelevel` fields;
  `ScoutEngine.__init__` has no `file_set` parameter.

### Step 5 — ScoutTally + ScoutEngine implementation (GREEN) — AC4
- In `harpyja/scout/engine.py`:
  - Append `recovered_spanned: int = 0` and `recovered_filelevel: int = 0` **last** to the
    frozen `ScoutTally` (additive, defaulted).
  - Add `file_set: frozenset[str] | None = None` to `ScoutEngine.__init__` (stored as
    `self._file_set`); pass it into `normalize_spans_with_tally` and unpack the two new
    counts into the `ScoutTally` it sets on `last_tally`.
- All Step-4 tests pass; existing `test_scout.py` tally assertions still pass (defaults).

### Step 6 — wiring loads the manifest file set (RED) — AC4
- Extend `harpyja/scout/test_scout_wiring.py`.
  - `test_build_scout_engine_threads_manifest_file_set` — build a `tmp_path` repo with a
    real file, `build_scout_engine(...)`; assert `engine._file_set` is a non-empty set
    containing the repo-relative path(s) read from the manifest under the artifact dir.
  - `test_build_scout_engine_empty_file_set_when_manifest_absent` — point at a repo/art
    dir with no manifest (or stub `read_manifest` → `[]`); assert `engine._file_set` is
    empty ⇒ no recovery (graceful, spec §1/AC2).
- Tests fail: `build_scout_engine` neither reads the manifest nor passes a `file_set`.

### Step 7 — wiring implementation (GREEN) — AC4
- In `harpyja/scout/wiring.py`: after `resolve_artifact_dir` / `index_repo`, call
  `read_manifest(art_dir)` and build `file_set = frozenset(e.path for e in entries)`;
  pass `file_set=file_set` into the `ScoutEngine(...)` construction. Manifest
  absent/empty ⇒ empty set ⇒ no recovery.
- All Step-6 tests pass; the existing `test_build_scout_engine_wires_default_client`
  still passes.

### Step 8 — report schema bump + additive recovered fields (RED) — AC4
- Extend `harpyja/eval/test_report.py`.
  - `test_schema_version_is_0012` — `SCHEMA_VERSION == "0012/1"`.
  - `test_aggregate_has_recovered_fields_last_with_default` — `build_report` populates
    `fc_citation_recovered_spanned_count` + `fc_citation_recovered_filelevel_count`
    (default `0`) and they appear **last** in `_AGGREGATE_FIELDS`.
  - `test_validate_accepts_legacy_0011_aggregate_block` — a `0011/1`-shaped aggregate
    (recovered fields absent) round-trips through `build_report` → `validate_report`
    without error (absent → defaulted).
  - `test_validate_accepts_0012_aggregate_block` — a fully-populated `0012/1` block
    validates.
- Tests fail: version is `"0011/1"`; the two recovered fields are absent from
  `_AGGREGATE_FIELDS` / `_AGGREGATE_DEFAULTS`; the validator rejects the new shape.

### Step 9 — report implementation (GREEN) — AC4
- In `harpyja/eval/report.py`: bump `SCHEMA_VERSION` to `"0012/1"`; append
  `fc_citation_recovered_spanned_count`, `fc_citation_recovered_filelevel_count`
  **last** to `_AGGREGATE_FIELDS` and to `_AGGREGATE_DEFAULTS` (default `0`). The single
  `_with_defaults` source keeps both a legacy `0011/1` block and a `0012/1` block valid.
- All Step-8 tests pass.

### Step 10 — runner + swebench driver aggregate recovered_* (RED) — AC4
- Extend `harpyja/eval/test_runner.py`:
  - `test_aggregate_outcomes_sums_recovered_counts` — `CaseRun`s carrying tallies with
    `recovered_spanned`/`recovered_filelevel` produce
    `fc_citation_recovered_spanned_count` / `fc_citation_recovered_filelevel_count` in the
    aggregate.
- Extend `harpyja/eval/test_swebench_runner.py`:
  - `test_run_swebench_carries_recovered_counts` — drive `run_swebench` with a fake
    per-case stack whose `last_tally` reports recovered counts; assert the **swebench**
    driver's pooled aggregate carries `fc_citation_recovered_*` (the test asserts the
    driver carries them, not just the single-repo runner).
- Tests fail: neither aggregation path reads `recovered_spanned`/`recovered_filelevel`.

### Step 11 — runner + swebench aggregation implementation (GREEN) — AC4
- In `harpyja/eval/runner.py::aggregate_outcomes`: add
  `recovered_spanned = sum(getattr(r.scout_tally, "recovered_spanned", 0) …)` and the
  file-level counterpart, and emit `fc_citation_recovered_spanned_count` /
  `fc_citation_recovered_filelevel_count` in the returned dict.
- `harpyja/eval/swebench_eval.py::run_swebench` pools through the same
  `aggregate_outcomes`, so it inherits the counts — confirm no second scoring path is
  forked. If any swebench-local pooling exists, extend it identically.
- All Step-10 tests pass; the unchanged `0011` runner/report tests still pass.

### Step 12 — Refactor (optional)
- Confirm the suffix-match helper (`_recover_suffix`) is the single definition; dedup any
  top-level-entry derivation; ensure `normalize_spans` and `engine.py` share one return
  contract. Run `ruff check` / `ruff format` clean over the touched files.
- All tests still pass.

### Step 13 — AC5 operator integration artifact (RED, skip-not-fail) — AC5
- Add to `harpyja/eval/test_swebench_integration.py`, marked
  `@pytest.mark.integration`, **skipping (not failing)** when the live Q8 model/endpoint
  is absent:
  - `test_q8rl_recovery_n12_run_writes_artifact_with_delta` — re-run the committed N=12
    point subset (flask/requests/pylint/sphinx from
    `harpyja/eval/fixtures/swebench_verified.raw.jsonl`) with the Scout model
    **overridden** via `dataclasses.replace(Settings(), scout_model=<q8>)` (run seam only,
    no production default changed) and recovery enabled; write
    `specs/0012-path-prefix/run_q8rl_recovery_n12.json` containing at least
    `scout_empty_count`, `gate_ran_count`, `fc_{spanned,filelevel,dropped}_count`,
    `recovered_{spanned,filelevel}_count`, `recovered_filelevel_paths` (the actual list),
    `indicative_only: true`, and `baseline_ref:
    "specs/0012-path-prefix/baseline_q8rl_n12.json"`. Assert the artifact records the
    **delta** vs the committed baseline and self-flags `indicative_only`; **no**
    strict-inequality gate (an honest recorded delta, not a threshold). Async is driven
    via `asyncio.run` per the repo convention.
- Skips cleanly in CI; runs for the operator. (AC5)

### Step 14 — Verification
- `python -m pytest harpyja/scout harpyja/eval harpyja/orchestrator -q` green (unit
  suite; integration auto-skips without the model).
- `ruff check harpyja/scout harpyja/eval` clean.

## Delegation

- Steps 1–7 (Scout producer path) → keep with `tdd-planner`/implementer: tight,
  single-package, signature-driven; no cross-team strength to match.
- Step 13 (operator integration run) → delegate to the **operator** (human-in-the-loop):
  it needs a provisioned Q8 FastContext endpoint that CI does not have; the code is
  written test-first but the *run* that produces `run_q8rl_recovery_n12.json` is operator
  action, recorded as an artifact (reason: live-model provisioning is outside the agent
  sandbox; matches the spec's "operator-run" framing).

## Risk

- **Leading-segment guard semantics** (AC3d) — the guard keys on the matched **tail's
  head** being a top-level manifest entry, not the recovered full path's head (which is
  trivially top-level). Mitigation: Step-1 `test_recover_leading_segment_guard_dropped`
  pins the discriminating case (`flask/blueprints.py` tail dropped vs
  `src/flask/blueprints.py` tail kept) before GREEN.
- **Return-arity blast radius** — widening `normalize_spans_with_tally` to a 4-tuple can
  miss a caller. Mitigation: only two non-test callers exist (`normalize_spans`,
  `engine.py`), both updated in Steps 2/5 in the same change; a `grep -rn
  normalize_spans_with_tally` re-check is part of Step 12.
- **Fixture realism** — recovery re-validates with `is_file`, so a recovery test that
  only seeds `file_set` strings without the file on disk would silently drop. Mitigation:
  every Step-1/3/4 recovery fixture writes the real file under `tmp_path`
  (`src/flask/blueprints.py`) AND lists it in `file_set`.
- **AC5 non-determinism** — a single live run varies; a strict-inequality gate would be
  dishonest. Mitigation: Step 13 records the delta + `indicative_only`, no pass/fail
  threshold, per spec §AC5.
- **Wrong-but-unique recovery invisible to a count** — mitigation: `recovered_filelevel_paths`
  is written in the AC5 artifact so a plausible-but-wrong keep is inspectable.
