---
spec: "0030"
status: planned
strategy: tdd
---

# Plan — 0030 Tier-0 symbols as a callable explorer tool

## AC3 decision point (resolved during planning)

**Parse-failure provenance lives in the EXISTING `index/manifest.py::ManifestEntry.degraded`
field (manifest-provenance), NOT a new `SymbolRecord.fallback_source` field.** Rationale,
grounded in the code:
- `ManifestEntry.degraded: str | None` already exists (spec Wave-2, additive-last) and is
  the per-file degradation outcome (`None` = clean; else `DEGRADED_PARSE_ERROR` /
  `DEGRADED_GRAMMAR_MISSING` from `symbols/extract.py`).
- On parse failure `extract.py` returns `ExtractResult(records=[], degraded=<reason>)` —
  a degraded file has **zero** `SymbolRecord` rows, so a per-record `fallback_source` field
  has nothing to attach to; the signal structurally must live on the manifest.
- Reuses Tier-0's existing artifact (Invariant 1: no new parser, one source of truth); no
  new record field, no `SCHEMA_VERSION` bump on the symbol artifact.

The `symbols` tool therefore needs BOTH `symbol_records` (the rows) AND `manifest` (the
degraded provenance) threaded into `build_explorer_tools` — the ExplorerBackend already
holds `self._manifest`; only `symbol_records` is net-new to the explorer wiring.

## Test-first sequence

### Step 1 — New Settings clamp field (RED)
- Add to `harpyja/config/test_settings.py`:
  - `test_scout_symbols_max_entries_default_is_finite_positive_bound` — asserts
    `Settings().scout_symbols_max_entries` is an `int`, `> 0`, and equals its pinned default
    (mirrors `test_scout_ls_max_entries_default_is_finite_positive_bound`).
- Tests fail: the field does not exist on `Settings` yet (`AttributeError`).

### Step 2 — Add the clamp field (GREEN)
- Edit `harpyja/config/settings.py`: add `scout_symbols_max_entries: int = 400`
  **appended last** on the scout budgets (additive-last, parallel to
  `scout_glob_max_paths` / `scout_ls_max_entries`), with a one-line rationale comment.
- Step-1 test passes. Existing drift-guard `dataclasses.fields(Settings)` tests stay green
  (field default is a plain positive int, names no external resource).

### Step 3 — `symbols` tool: Tier-0 wrapper, kind+span, ≥2 languages, path-normalized (RED)
- Add to `harpyja/scout/test_explorer_tools.py` (extend the `_tools(...)` helper to accept
  `symbol_records=` and `manifest=`, defaulting to empty):
  - `test_symbols_tool_wraps_tier0_records_python` — a Python multi-symbol fixture returns
    `CodeSpan`s carrying `kind` + `symbol` + real `start_line`/`end_line` (not file-level).
  - `test_symbols_tool_wraps_tier0_records_go` — same over a Go fixture (the ≥2-of-9
    languages requirement; records constructed as `SymbolRecord` rows, no new parser invoked).
  - `test_symbols_tool_normalized_path` — a query for `pkg/../pkg/file.py` resolves to the
    same records as `pkg/file.py` (path normalized/resolved before the record lookup).
  - `test_symbols_tool_no_new_parser` — the tool reads only the injected `symbol_records`
    (no tree-sitter/parse call); asserted by passing records for a path whose file does not
    exist on disk and still getting them back (proves it filters rows, not re-parses).
- Tests fail: `build_explorer_tools` accepts no `symbol_records`/`manifest` and returns no
  `symbols` key (`KeyError`) / `TypeError` on the new kwargs.

### Step 4 — Implement the `symbols` tool + thread records (GREEN)
- Edit `harpyja/scout/explorer_tools.py`:
  - Widen `build_explorer_tools(...)` signature with keyword-only
    `symbol_records: Sequence[SymbolRecord]` and `manifest: Sequence[ManifestEntry]`.
  - Add a `symbols(path)` closure mirroring `deep/host_tools.py::symbols`: **normalize the
    path first** (resolve), then filter `symbol_records` by the normalized repo-relative
    path, returning `CodeSpan(path, start_line, end_line, symbol=name, language, kind)`.
  - Add `"symbols": symbols` to the returned dict.
- Step-3 tests pass. (Confinement + clamp + degradation added in the next steps.)

### Step 5 — Repo-confinement (post-resolution) + output clamp (RED)
- Add to `harpyja/scout/test_explorer_tools.py`:
  - `test_symbols_tool_out_of_repo_path_rejected` — a resolved path escaping the repo root
    (e.g. `pkg/../../etc/passwd`) raises `PathConfinementError` — confinement enforced
    **after** normalization.
  - `test_symbols_tool_clamps_to_scout_symbols_max_entries` — a records set larger than
    `Settings(scout_symbols_max_entries=N)` is clamped to `N`.
- Tests fail: the Step-4 minimal tool does neither confinement nor clamping.

### Step 6 — Implement confinement + clamp (GREEN)
- Edit `harpyja/scout/explorer_tools.py::symbols`: call `confine_path(repo_path, path)` on
  the resolved path (confinement AFTER resolution, per AC1), and slice the result to
  `settings.scout_symbols_max_entries`.
- Step-5 tests pass.

### Step 7 — Graceful degradation, visible provenance (AC3) (RED)
- Add to `harpyja/scout/test_explorer_tools.py`:
  - `test_symbols_tool_degraded_file_falls_back_to_ripgrep` — a path whose `ManifestEntry`
    carries `degraded=DEGRADED_PARSE_ERROR` (and zero symbol records) returns the injected
    ripgrep engine's spans (the shared `search_engine`, scoped to that file), never empty.
  - `test_symbols_tool_degraded_file_marks_output_degraded` — the same call surfaces a
    **visible `degraded: True` marker** in the tool output (not a silent swap).
  - `test_symbols_tool_clean_file_not_marked_degraded` — a clean file (no manifest
    `degraded`) carries `degraded: False`.
  - `test_symbols_tool_degraded_never_raises` — a degraded file returns a normal tool
    result, never an exception (untrusted-caller boundary).
- Tests fail: the tool has no manifest-degraded lookup and no marker in its return shape.

### Step 8 — Implement degradation path (GREEN)
- Edit `harpyja/scout/explorer_tools.py::symbols`:
  - Build a `degraded_paths` set from `manifest` entries whose `.degraded` is truthy (the
    AC3 manifest-provenance decision).
  - When the normalized path is in `degraded_paths`: run the shared `search_engine.search`
    scoped to that file (Tier-0's existing ripgrep fallback), clamp, and return the
    result with `degraded: True`.
  - Settle the **return shape** here (implementation decision): return a dict
    `{"symbols": [...CodeSpan...], "degraded": bool}` for a machine-readable, always-present
    marker (a stable identifier per the errors convention), clean path → `degraded: False`.
    Update Step 3/5 assertions to read `["symbols"]` if the dict shape is chosen.
- Step-7 tests pass; Step-3/5 tests updated to the final shape stay green.

### Step 9 — Exact-tool-count 4→5 + schema/dispatch + parallel tool_call (AC4) (RED)
- Edit `harpyja/scout/test_explorer_tools.py`:
  - Rename/replace `test_build_explorer_tools_returns_exactly_four_navigation_tools` →
    `test_build_explorer_tools_returns_exactly_five_navigation_tools`; assert
    `set(tools) == {"grep","glob","read_span","ls","symbols"}` and `"submit_citations" not in`.
- Edit `harpyja/scout/test_explorer_backend.py`:
  - Update `test_tool_schemas_match_the_built_tool_surface_single_source` to include
    `symbols` (schema set == built-tool set == 5 nav tools + terminal).
- Edit `harpyja/scout/test_explorer_loop.py`:
  - Add `test_symbols_participates_in_parallel_tool_calls` — a turn emitting N parallel
    `tool_calls` including `symbols` answers ALL N in emitted order, each with its own
    `tool_call_id`, no unanswered call (spec 0029 invariant extended to the 5th tool).
- Tests fail: schema lists 4 nav tools, count assertions expect 5, `symbols` schema absent.

### Step 10 — Amend convention + schema IN LOCKSTEP (single commit) (GREEN)
- Edit `.speccraft/conventions.md`: in the exact-tool-count entry, amend `4 → 5` and
  `{grep,glob,read_span,ls,symbols}` with a one-line rationale: "Tier-0 file-local symbol
  localization, measured on the 0029 baseline cases (right-file-wrong-span target)."
- Edit `harpyja/scout/explorer_backend.py`:
  - Add the `symbols` function schema (single required `path: string`) to `_tool_schemas()`.
  - Add `symbol_records` to `ExplorerBackend.__init__` and pass it (plus the held
    `self._manifest`) into the `build_explorer_tools(...)` call site (line ~221).
- **All of Step-9 plus the conventions edit land in ONE commit** (the 0027 precedent: a
  count bumped in a test but not the convention, or vice versa, silently disarms the guard).
- Step-9 tests pass.

### Step 11 — Production wiring threads symbol_records (RED)
- Add to `harpyja/scout/test_scout_wiring.py` (or `test_explorer_backend.py`):
  - `test_build_scout_engine_threads_symbol_records_into_symbols_tool` — the live factory
    loads symbol records and the built `symbols` tool returns non-empty for an indexed
    fixture file (guards against a routed-but-empty silent-false-claim: the tool is wired,
    not degenerate).
- Tests fail: `wiring.py` never loads/threads symbol records; the tool would return empty.

### Step 12 — Wire the loader (GREEN)
- Edit `harpyja/scout/wiring.py`: `load_symbols_or_none(art_dir, engine_identity()) or []`
  (mirroring `deep/wiring.py`) and pass `symbol_records=records` into `ExplorerBackend(...)`.
- Step-11 test passes.

### Step 13 — Refactor: one symbols→CodeSpan mapping (optional)
- `deep/host_tools.py::symbols` and `scout/explorer_tools.py::symbols` now share the
  record→`CodeSpan` projection. Extract a single helper (e.g. `symbols/project.py::
  record_to_codespan`) both call, so the shared shape has one source of truth.
- All prior tests still pass.

### Step 14 — Lift-report durable JSON schema (AC5) (RED)
- Add `harpyja/eval/test_symbols_lift_report.py`:
  - `test_lift_report_schema_is_version_stamped_and_validated` — the report carries a pinned
    `SCHEMA_VERSION`, per-case `{case_id, before_bucket, after_bucket}` using the 0029 labels
    (`WRONG_FILE`/`RIGHT_FILE_WRONG_SPAN`/`CORRECT`), model tag, endpoint/loopback proof,
    settings overrides, and harness degrade status; a malformed report fails the validator.
  - `test_lift_report_writes_outside_repo_atomically` — reuses `eval/report.py::
    atomic_write_json`, refusing an in-`repo_path` output dir (existing harness invariant).
- Tests fail: no lift-report schema/writer exists.

### Step 15 — Implement the lift-report schema/writer (GREEN)
- Add `harpyja/eval/symbols_lift_report.py`: a pinned, version-stamped schema + loud
  `validate_*` (modeled on `eval/report.py` / `oq2_ledger.py`), written via the existing
  atomic outside-repo writer. Buckets reuse the 0029 label projection (one-oracle reuse).
- Step-14 tests pass.

### Step 16 — Operator lift run + honest record (AC5/AC6) (RED→record)
- Add `harpyja/eval/test_symbols_lift_live.py`:
  - `test_symbols_lift_astropy_django_live` — `@pytest.mark.integration`, gated by
    `require_live_stack` / `scout_stack_available`; runs astropy-12907 + django-12774 on the
    14B WITH the 5-tool suite, emits the durable JSON report. Encoded as a non-strict
    `@pytest.mark.xfail` that flips to `xpass` when the live stack is present (spec 0027
    precedent: CI-safe skip, self-un-holding).
  - **Success criterion (self-contained, AC5):** django `RIGHT_FILE_WRONG_SPAN → CORRECT`
    is the hypothesis; astropy `WRONG_FILE → WRONG_FILE` is EXPECTED and NOT a failure
    (file-local tool cannot fix file navigation); ANY harness `degrade` ⇒ harness failure,
    not tool failure.
- Operator runs it, then records the measured outcome directly (AC6): whichever way django
  lands, plus astropy's expected control result, into the durable JSON + a one-line honest
  note. N=2 is signal, not proof — no overfitting to these two cases.

## Delegation

- Steps 1–13 (unit: Settings, tool, degradation, lockstep count, wiring) → `tdd-implementer`
  (reason: pure test-first Python in the scout/config packages, all `go test`-equivalent
  `pytest` verifiable, no live infra).
- Steps 14–15 (report schema) → `tdd-implementer` (reason: mirrors existing `eval/report.py`
  schema discipline).
- Step 16 (live lift run + honest record) → `operator` / measurement owner (reason: requires
  the 14B live stack, loopback endpoint, and honest measurement recording — not a unit seam).

## Risk

- **AC3 return-shape churn** (list vs dict marker) touches Step-3/5 assertions written
  before the shape is final → mitigation: settle the dict `{"symbols", "degraded"}` shape
  in Step 8 and update the earlier assertions in the same step; the shape is load-bearing
  for AC3's visible marker so it is decided once, centrally.
- **Lockstep guard disarm** (count bumped in a test but not conventions.md, or schema added
  without the dispatch test) → mitigation: Step 9 + Step 10 are a single commit covering the
  convention text AND both hard-count tests AND the schema (0027 precedent, explicit in the
  tasks).
- **Silent routed-but-empty tool** (schema advertises `symbols` but wiring never threads
  records → every call empty, a false "no symbols" reading) → mitigation: Step 11 wiring
  test asserts non-empty on an indexed fixture before the live run.
- **astropy misread as a tool failure** (WRONG_FILE stays WRONG_FILE) → mitigation: AC5
  encodes astropy as the expected control; only django's lift and any degrade decide.
- **Live run degrades and masks the outcome** (the 0026/0027 degrade-masks-outcome trap) →
  mitigation: any degrade is recorded as a harness failure/HOLD naming the fix, never a
  capability finding; xfail-flips-to-xpass keeps it self-un-holding.
