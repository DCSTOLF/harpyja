---
spec: "0035"
status: planned
strategy: tdd
---

# Plan — 0035 grep-scope-markers

Data-path order: characterization pins → grep wrapper (marker + delegation) → loop
visibility → ls → Deep `search` → persistent-artifacts helper → live → conventions doc.
`rg`-free throughout (inject a fake/real engine with a stub `which`). Marker returns are
BARE STRINGS (OQ2) so `_spans_of` yields no spans and `session.add` stringifies them
verbatim; ZERO `explorer_loop.py` changes (the marker-return design's whole point).

## Plan-time decisions (rationale)

- **OQ1 — `ls` on an existing FILE keeps `[]` (not a marker, not a file entry).** `ls`
  means "list children"; a file honestly has none, and that empty is categorically
  distinct from "path does not exist" (which gets the marker). Mirrors grep's asymmetry
  (nonexistent → marker; searchable-but-empty → `[]`) and the existing docstring ("ls on
  a file → empty; use read_span"). Pinned by `test_ls_existing_file_returns_plain_empty`.
- **OQ2 — marker VALUE is a bare string** `"<identifier>: '<scope>'"` (e.g.
  `grep-scope-not-found: 'repo'`), built with `f"...: {scope!r}"` (repr gives the exact
  single-quoted `'repo'`). Verified against the loop: `_spans_of` returns `[]` for a
  non-list/non-Mapping (no citable spans); `session.add` records `str(result)` so the raw
  identifier appears model-visibly in the conversation and is a trivial substring assert.
  A `{"error": ...}` dict stringifies as noisy Python `repr` and buys nothing (`_spans_of`
  also finds no `path`), so the bare string wins on cleanliness.
- **Deep typed-handling mechanism — guard-in-wrapper returning a bare marker string**
  (`search-scope-not-found: '<scope>'`), NOT a raise and NOT a `DeepUnavailable` degrade.
  Rationale: (a) testable with no `dspy` present; (b) RLM-visible — `dspy.RLM` stringifies
  a tool's return into its trajectory, same visibility the explorer gets; (c) non-terminal
  — the RLM can recover by searching a valid scope, whereas `DeepUnavailable` would degrade
  the ENTIRE tier for one navigation mistake (over-aggressive vs the graceful-degradation
  posture); (d) converges the Deep `search` contract with the explorer `grep`. Traced
  crash it replaces: `host_tools.search` → `RipgrepEngine.search` with `repo_root` set →
  `Path(scope).resolve().is_file()` False → `cwd = <nonexistent>` → `_default_runner_factory`
  → `subprocess.run(cwd=<nonexistent>)` raises `FileNotFoundError`, uncaught in
  `host_tools.search` and `RlmBackend.run`.
- **Ordering invariant — the existence guard fires BEFORE the engine call.** In all three
  wrappers the nonexistent branch `return`s the marker before `search_engine.search(...)`;
  otherwise the engine crashes on a nonexistent `cwd` (the trace above). The guard is
  `if scope and not scoped_path.exists()` (NOT `is_dir`): an existing FILE now falls
  through to delegation (the deleted-guard behavior), only a truly-absent scope is marked.
  Proven by injecting an engine that RAISES on any call and asserting the marker returns
  without the raise firing.

## Test-first sequence

### Step 1 — Characterization pins (stay green; guard the untouched contracts)
- Add to `harpyja/scout/test_explorer_tools.py`:
  - `test_grep_real_dir_zero_matches_returns_plain_empty` — real dir scope, engine
    returns `[]` → wrapper returns plain `[]`, no marker (honest-empty preserved, AC3).
  - `test_ls_existing_file_returns_plain_empty` — `ls` on a real file → `[]` (OQ1 pin,
    survives the nonexistent/file split).
- Add `harpyja/server/test_tools.py` (NEW):
  - `test_confine_path_nonexistent_in_repo_path_resolves_without_raising` — a nonexistent
    in-repo path resolves and returns without raising (non-strict resolve, AC4). Pins the
    contract the marker branches depend on so a future strict/exists switch can't silently
    change it.
- Add to `harpyja/deep/test_host_tools.py`:
  - `test_deep_search_file_scope_delegates_no_defect` — real engine + a real FILE scope
    returns the engine's repo-relative matches (Deep is already engine-delegated post-0033;
    the behavior the explorer now converges to, AC5 file-scope half).
- These pass against current code (pins, not RED).

### Step 2 — grep marker + file-scope delegation (RED)
- Add to `harpyja/scout/test_explorer_tools.py`:
  - `test_grep_file_scope_delegates_returns_engine_matches` — positive astropy fixture:
    real `astropy/modeling/separable.py`, real `RipgrepEngine` (stub `which`) whose runner
    returns a match line in that file; `grep(pattern, scope="astropy/modeling/separable.py")`
    returns the engine's repo-relative span(s), NOT `[]`, no marker (AC1).
  - `test_grep_nonexistent_scope_returns_marker` — `grep("x", scope="repo")` (nonexistent)
    returns exactly `"grep-scope-not-found: 'repo'"`; the injected engine RAISES on any
    call, proving the marker fires BEFORE delegation (AC2 wrapper + ordering invariant).
  - `test_grep_real_file_zero_matches_delegates_returns_empty` — real file scope, engine
    returns `[]`; asserts the engine WAS called (`fake.calls` non-empty) AND result `== []`
    (AC3 file-scope honest-empty via delegation).
- Tests fail: current `if scope and not scoped_path.is_dir(): return []` short-circuits a
  file scope to `[]` (never delegates) and returns `[]` (not the marker) for a nonexistent
  scope.

### Step 3 — grep GREEN
- Edit `harpyja/scout/explorer_tools.py` `grep`: DELETE the `is_dir()` file-scope
  early-return; add `if scope and not scoped_path.exists(): return f"grep-scope-not-found: {scope!r}"`
  BEFORE the `search_engine.search(...)` call; existing-file/dir scopes delegate unchanged.
  Widen the annotation to `-> list[CodeSpan] | str` (success list shape untouched; the
  marker is an additive return).
- All Step 1 + Step 2 grep tests pass; existing scoped-grep tests
  (`test_grep_scoped_hit_is_repo_relative`, `test_all_path_discovering_tools_...`) stay
  green (their `astropy/` scope exists → delegates as before).

### Step 4 — loop visibility of the marker (characterization pins; zero loop changes)
- Add to `harpyja/scout/test_explorer_loop.py` (a `grep` tool returning the marker string):
  - `test_grep_scope_marker_visible_and_non_terminal` — marker string appears verbatim in
    `result.history`, loop continues, reaches `SUBMITTED` (AC2 non-terminal + visibility).
  - `test_repeated_bad_scope_trips_loop_detection` — two identical bad-scope calls (marker,
    no new span) → `note_navigation` runs → the `_CORRECTIVE` note is injected (AC2 loop
    detection still armed — the property the exception route would defeat).
  - `test_grep_scope_marker_not_flagged_execution_error` — the marker message does NOT carry
    the `tool-call-degraded:execution-error:` prefix (proves the marker-return route, not the
    0029 degrade catch).
- Pass against current loop code (`_spans_of`/`session.add`/`note_navigation` already
  tolerate the marker) — these pin that no loop change is needed.

### Step 5 — ls nonexistent-path marker (RED)
- Add to `harpyja/scout/test_explorer_tools.py`:
  - `test_ls_nonexistent_path_returns_marker` — `ls("does/not/exist")` returns exactly
    `"ls-path-not-found: 'does/not/exist'"` (AC4).
- Tests fail: current `if not target.is_dir(): return []` returns `[]` for a nonexistent
  path (same silent shape as a file).

### Step 6 — ls GREEN
- Edit `harpyja/scout/explorer_tools.py` `ls`: `if not target.exists(): return
  f"ls-path-not-found: {path!r}"` FIRST, then the existing `if not target.is_dir():
  return []` (now reached only for an existing file — the OQ1 keep). Widen annotation to
  `-> list[CodeSpan] | str`.
- Step 5 marker test passes; the Step 1 `test_ls_existing_file_returns_plain_empty` pin
  and all existing `ls` tests stay green.

### Step 7 — Deep search nonexistent-scope typed handling (RED)
- Add to `harpyja/deep/test_host_tools.py`:
  - `test_deep_search_nonexistent_scope_returns_marker_not_crash` — inject a search engine
    whose `.search` raises `FileNotFoundError` on a nonexistent scope (faithful to the traced
    subprocess-`cwd` crash); assert `tools["search"]("x", scope="nope")` returns exactly
    `"search-scope-not-found: 'nope'"` (AC5 nonexistent half). RED now: no guard → the
    engine is called → `FileNotFoundError` propagates uncaught (the discovered defect).
- The desired-behavior assertion fails until the guard is added; the raising engine also
  proves the guard fires before delegation.

### Step 8 — Deep search GREEN
- Edit `harpyja/deep/host_tools.py` `search`: keep `_charge()` first (a bad-scope call is a
  real tool call, still charged); confine once, then
  `if scope is not None and not scoped_path.exists(): return f"search-scope-not-found: {scope!r}"`
  BEFORE the engine call; else delegate as today. Widen annotation to
  `-> list[CodeSpan] | str`.
- Step 7 passes; Step 1 Deep file-scope pin and all existing `host_tools` tests stay green.

### Step 9 — persistent-artifacts helper (RED)
- Add `harpyja/eval/test_live_artifacts.py` (NEW):
  - `test_live_artifact_dir_path_shape` — `live_artifact_dir("some_test")` is
    `<harpyja-root>/eval_work/live_artifacts/some_test/<YYYYMMDDTHHMMSSZ>-<pid>/` (basic UTC
    ISO-8601 timestamp; pid suffix as the collision rule), asserted on the path parts.
  - `test_write_live_artifact_reuses_atomic_write_json_outside_target_repo` — with a fake
    TARGET repo tempdir DISTINCT from the artifact dir, `write_live_artifact(payload, ...)`
    writes and the file exists (repo/out-dir separation; writer reuse of `atomic_write_json`).
  - `test_write_live_artifact_refuses_inside_target_repo` — when `repo_path` equals/contains
    the out dir (the conflation bug), `atomic_write_json`'s inside-repo refusal raises
    `ValueError` (pins why fake-repo and out-dir must be separated).
  - `test_live_artifacts_base_path_is_not_a_settings_field` — over `dataclasses.fields(Settings)`,
    assert no field name mentions `live_artifact`/`eval_work` (eval-knobs-disjoint, AC7).
- Tests fail: `harpyja/eval/live_artifacts.py` does not exist (ImportError).

### Step 10 — persistent-artifacts helper GREEN
- Add `harpyja/eval/live_artifacts.py`: repo root via `Path(__file__).resolve().parents[2]`;
  `live_artifact_dir(test_name, *, now=None, pid=None)` →
  `root/"eval_work"/"live_artifacts"/test_name/f"{now:%Y%m%dT%H%M%SZ}-{pid}"` (defaults
  `datetime.now(timezone.utc)` and `os.getpid()`); `write_live_artifact(payload, *,
  test_name, repo_path, filename)` → `atomic_write_json(payload, out_dir=live_artifact_dir(
  test_name), repo_path=repo_path, filename=filename)`. No `Settings` field added.
- Step 9 tests pass.

### Step 11 — live marker in persisted trajectory + migrate integration tests (harness; skip-not-fail)
- Edit `harpyja/eval/test_live_verifier_integration.py`:
  - Migrate the three existing `@pytest.mark.integration` tests from `TemporaryDirectory`
    to `live_artifact_dir(...)`/`write_live_artifact(...)`, keeping the worktree `repo_path`
    (fake-repo) SEPARATE from the persistent out-dir (else the inside-repo refusal fires).
  - Add `test_live_bad_scope_marker_in_persisted_trajectory_or_not_exercised` (AC6): an
    `@pytest.mark.integration` run whose persisted artifact is inspected for a
    `grep-scope-not-found` marker; IF present AND the run reached a terminal submit →
    assert both (non-terminal proven live, artifact durable under `eval_work/live_artifacts/`);
    ELSE print the 0023 NOT-EXERCISED fallback (never a silent pass). Skip-not-fail on an
    absent/invalid stack.
- Not a hermetic RED/GREEN (integration, skippable in CI); the mechanism is proven by the
  Step 9/10 unit tests. The migration's correctness (repo/out-dir separation) is unit-pinned
  in Step 9.

### Step 12 — conventions doc (AC8)
- Edit `.speccraft/conventions.md`:
  - Under "Errors & failure posture": an unsearchable tool scope (nonexistent path) is a
    stable typed marker (`grep-scope-not-found` / `ls-path-not-found` /
    `search-scope-not-found`, `<id>: '<scope>'`), model/RLM-visible, non-terminal, NOT a
    silent `[]` and NOT routed through the 0029 execution-error degrade; and the
    file-scope-delegation convergence — explorer `grep` == Deep `search` == the one
    `RipgrepEngine` contract (a file scope delegates to the engine, no wrapper guard).
  - Under "Measurement & eval harness": live integration artifacts write to the persistent,
    gitignored `eval_work/live_artifacts/<test>/<UTC-basic-timestamp>-<pid>/` via the same
    outside-repo `atomic_write_json`, with fake-repo/out-dir kept separate and the base path
    NOT a `Settings` field (harness/SUT-fenced; the eval-set spec stays SUT-byte-frozen).
- No RED (doc step).

### Step 13 — Refactor (optional)
- The three wrappers now share a "confine → `exists()` guard → bare marker" shape. A shared
  `_scope_marker(repo_path, scope, identifier) -> str | None` helper is POSSIBLE but weakly
  motivated: `ls` keeps a distinct second branch (existing-file → `[]`) and each tool owns a
  distinct identifier, so extraction risks over-abstracting three 2-line guards. RECOMMENDATION:
  leave the wrappers separate; if extracted, keep the identifier and the marker-format
  (`f"{identifier}: {scope!r}"`) as the single shared piece. All tests still pass.

## Delegation

- Steps 2–3, 5–6 (explorer `grep`/`ls` wrapper) → `speccraft-implementer` (scout tool-surface
  edits + sibling `test_explorer_tools.py`; small, localized).
- Step 4 (loop pins) → `speccraft-implementer` (loop test-only; no source change).
- Steps 7–8 (Deep `search`) → `speccraft-implementer` (host_tools + `test_host_tools.py`).
- Steps 9–11 (eval harness helper + live migration) → `speccraft-implementer` with eval-harness
  care (reuse `atomic_write_json`, respect the outside-repo refusal, keep knobs off `Settings`).
- Step 12 (doc) → `speccraft-implementer` (conventions edit, reconciled with the identifiers).

## Risk

- **Deleting grep's file-scope guard changes a live-observed behavior (0033 astropy).** →
  mitigation: the positive delegated-match fixture (Step 2) locks the new REAL-matches
  behavior; existing scoped-grep tests (real `astropy/` dir) confirm dir scopes are
  untouched; no existing test asserted grep-on-file `== []` (verified by grep of the suite).
- **RED for the Deep crash can't spawn a real `rg`/subprocess hermetically.** → mitigation:
  inject a fake engine that raises `FileNotFoundError` on a nonexistent scope (faithful to the
  traced `subprocess(cwd=<nonexistent>)` failure); the guard-before-delegation invariant is
  what the test actually pins.
- **Return-type widening (`list[CodeSpan] | str`) could ripple to typed callers.** →
  mitigation: the loop consumes results dynamically (`_spans_of`/`str(result)`), Deep's caller
  is the RLM sandbox (stringified) — neither branches on the static list type; widen the
  annotation honestly and run `ruff` (no new errors) + the full suite.
- **AC6 live test is model-behavior-contingent and non-hermetic.** → mitigation: 0023
  NOT-EXERCISED fallback (printed, never silent), skip-not-fail on absent stack; the marker
  mechanism is deterministically proven by the Step 2/4/9 hermetic tests.
- **Artifact-writer conflation (fake-repo == out-dir) trips the inside-repo refusal.** →
  mitigation: Step 9 pins both the separation success path and the refusal path before the
  Step 11 migration relies on them.
