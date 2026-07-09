---
spec: "0033"
status: planned
strategy: tdd
---

# Plan — 0033 scoped-grep-paths

The fix rides the data path once: **engine → tools → submit → loop → backend →
verifier → docs**. Each stage's output shape lands (RED→GREEN) before the stage that
consumes it is tested. The full suite (`uv run pytest` / `python -m pytest`) stays
green at every GREEN step; `ruff` gains no new errors.

## Plan-time decisions (the spec's two OQs)

**OQ1 — engine mechanism: (b) engine-level re-prefix of parsed paths.** The runner
invocation is left byte-identical (`rg` still runs with `cwd=scope`, no new path arg,
same flags), and only the *parsed* paths are re-prefixed with the scope's
repo-relative prefix. Rationale: this changes ONLY the path prefix — exactly the
invariant's stated fix surface — so AC1's repo-root byte-identical pin (match
ordering + ignore-file resolution) holds *trivially* because the real `rg` command
never changes; mechanism (a) (rg-from-repo-root with the scope as a path arg) would
shift `./`-prefixing / ordering / `.gitignore` resolution and force the pin to defend
that drift. Smallest correct diff, matches "match content, bounds, and clamps are
untouched."

**OQ2 — repo-root threading: an optional `search(..., repo_root: str | None = None)`
keyword param, NOT a constructor field.** Rationale: `RipgrepEngine` is built ONCE and
SHARED across repos at several sites (`server/app.py` `engine_factory(s)` serves many
repos from one engine; `cli.py` likewise), so the repo root is a per-CALL fact, not a
per-instance one — it must ride `search()`. The param is optional/defaulted: when
omitted the engine behaves EXACTLY as today (process-cwd-relative, verbatim parse — no
production caller relies on this). The re-prefix LOGIC lives solely in the engine; the
two `_Search` structural protocols and both wrappers (explorer `grep`, Deep `search`)
merely SUPPLY `repo_root=repo_path` as DATA — this is not the per-caller re-prefix the
invariant forbids. `scope=None` comes to mean "repo root" ONLY when `repo_root` is
supplied (`scope` then defaults to `repo_root`); no production caller passes bare
`scope=None`, so there is no production behavior change. **Tier-0 locate**
(`orchestrator/locate.py`, `scope=req.repo_path`) is deliberately left un-threaded —
it already passes the absolute repo root and needs no re-prefix, so it stays on the
legacy path and is byte-identical (pinned in Step 1).

**OQ2 edge — `symbols()` degraded fallback file-scope: supported, not rejected.** The
fallback calls `search_engine.search("", scope=<resolved FILE path>)`, which crashes
today with `NotADirectoryError` under the default runner (`cwd=<file>`). Decision: the
engine, when `repo_root` is supplied and `scope` resolves to a FILE, runs `rg` from the
file's PARENT directory with the file passed as an rg path argument and re-prefixes by
the parent's repo-relative prefix → repo-relative, file-local results. This PRESERVES
the degraded-file ripgrep fallback's only content path (loud rejection was considered
and rejected because it would delete that fallback's results entirely) and eliminates
the current crash. The `symbols` fallback is updated to pass `repo_root=repo_path`.

## Interface shapes (named now so steps don't drift)

- `submit_citations(...) -> SubmitResult` where
  `SubmitResult = dataclass(spans: list[CodeSpan], submitted: int, surviving: int)`
  (`submitted = len(raw_spans_in)`, `surviving = len(normalized_out)`; counted AT the
  submit seam — the one normalize pass where the explorer drop occurs).
- `LoopResult` gains `citations_submitted: int | None = None`,
  `citations_surviving: int | None = None` (defaults keep positional construction
  working).
- `build_trajectory_record(..., citations_submitted=None, citations_surviving=None)`;
  the fields land in the record and the verifier artifact.
- `VERIFIER_SCHEMA_VERSION "0031/1" → "0033/1"`; `validate_verifier_artifact` grows a
  version GATE (`_KNOWN_VERIFIER_SCHEMA_VERSIONS = {"0031/1", "0033/1"}`, 0026
  `DATASET_SCHEMA_VERSION` pattern) with the two count fields OPTIONAL (defaulted) so a
  legacy `0031/1` artifact still validates.
- `fc_citation_dropped_count` and the eval-report schema are BYTE-UNTOUCHED (asserted);
  their engine-pass-only scope is documented in Step 15 (AC8).

## Test-first sequence

### Step 1 — Characterization pin: current shapes frozen (PIN)
- Add to `harpyja/symbols/test_ripgrep.py`:
  - `test_repo_root_scope_paths_byte_identical_pin` — injected runner returns
    `django/db/models/query.py`; `search(q, scope=<abs repo root>)` with NO `repo_root`
    arg returns that path verbatim (today's behavior; the Tier-0/django shape).
  - `test_tier0_repo_root_scope_legacy_path_unchanged` — same call shape Tier-0 uses
    (`scope=req.repo_path`, no `repo_root`), verbatim parse.
- Add to `harpyja/eval/test_live_verifier.py`:
  - `test_verifier_artifact_0031_shape_pin` — a `0031/1` artifact with NO
    `citations_submitted`/`citations_surviving` validates today and records the current
    field set (the legacy shape the version-gate must keep accepting).
- These PASS against current code — they freeze the pre-move behavior.

### Step 2 — Engine emits repo-relative paths for subdir/file scopes (RED)
- Add to `harpyja/symbols/test_ripgrep.py`:
  - `test_search_subdir_scope_returns_repo_relative_paths` — `scope="<repo>/astropy"`,
    `repo_root=<repo>`; parsed `modeling/core.py` → `astropy/modeling/core.py`.
  - `test_search_subdir_scope_trailing_slash` — `scope="<repo>/astropy/"` same result.
  - `test_search_nested_subdir_scope` — `scope="<repo>/astropy/modeling"` →
    `astropy/modeling/core.py`.
  - `test_search_strips_rg_dot_slash_prefix` — parsed `./modeling/core.py` normalizes to
    `astropy/modeling/core.py` (no `astropy/./` artifact).
  - `test_search_repo_root_scope_with_repo_root_is_byte_identical` — `scope==repo_root`
    → prefix `.` collapses → parsed paths unchanged.
  - `test_search_file_scope_returns_repo_relative_via_parent` — `scope=<repo>/a/b.py`
    (a FILE), `repo_root=<repo>`; injected runner asserts `rg` cwd is the PARENT and the
    filename is passed as a path arg; parsed `b.py` → `a/b.py` (the `symbols` fallback
    shape; no `NotADirectoryError`).
  - `test_search_real_rg_subdir_repo_relative` (real `rg`; `skip` if absent) — build a
    tmp repo with a subdir + a `.gitignore`; a scoped search returns repo-relative paths
    AND the repo-root scope is byte-identical (ordering + ignore-file resolution
    included in the pin).
- Tests fail: `search()` has no `repo_root` param and `_parse` returns paths verbatim.

### Step 3 — Implement engine re-prefix (GREEN)
- Edit `harpyja/symbols/ripgrep.py`:
  - `search(self, pattern, scope=None, *, repo_root: str | None = None)`. When
    `repo_root` is None → today's path (unchanged). When supplied: `scope = scope or
    repo_root`; if `Path(scope)` is a file, effective `cwd = parent`, pass the filename
    as an rg path arg, `rel = relpath(parent, repo_root)`; else `cwd = scope`,
    `rel = relpath(scope, repo_root)`.
  - `_default_runner_factory` takes the effective cwd (and optional path arg).
  - `_parse(stdout, rel_prefix)` re-prefixes: `normpath(join(rel_prefix, path))`,
    stripping `./`; `rel_prefix == "."` leaves paths unchanged.
- Step-1 and Step-2 tests pass; rest of suite green (param is optional).

### Step 4 — Tool contract + astropy/django end-to-end + blast radius (RED)
- Add to `harpyja/scout/test_explorer_tools.py`:
  - `test_all_path_discovering_tools_emit_repo_relative_paths` — one contract test:
    `grep` scoped + unscoped, `glob`, `ls`, `symbols` clean branch all return
    repo-relative paths. Docstring states `read_span` is EXCLUDED (echoes the
    caller-supplied path; discovers nothing).
  - `test_ls_directory_entries_are_repo_relative_noncitable` — `ls` dir entries carry
    the trailing-`/` shape (`modeling/`), repo-relative, asserted as non-citable
    listings.
  - `test_grep_scoped_hit_is_repo_relative` — `grep("x", scope="astropy/")` on a tmp
    repo returns `astropy/modeling/core.py`, not `modeling/core.py`.
  - `test_symbols_degraded_fallback_file_scope_repo_relative_no_crash` — a manifest
    `degraded` file → fallback returns repo-relative spans, no `NotADirectoryError`.
- Add to `harpyja/scout/test_submit_citations.py`:
  - `test_astropy_scoped_grep_hit_survives_submit` — a repo-relative span from a scoped
    grep (`astropy/modeling/core.py:812`) survives `submit_citations`' `normalize_spans`
    (the astropy shape, no drop).
  - `test_django_unscoped_shape_unchanged` — the unscoped `django/...` span still
    survives (byte-identical control).
- Add to `harpyja/deep/test_host_tools.py`:
  - `test_deep_search_scoped_returns_repo_relative` — Deep `search(pattern, scope=subdir)`
    POSITIVELY changes to repo-relative (the inherited fix).
  - `test_deep_search_unscoped_byte_identical` — unscoped Deep `search` unchanged.
- Tests fail: wrappers do not yet pass `repo_root` to the engine.

### Step 5 — Wire wrappers to supply repo_root (GREEN)
- Edit `harpyja/scout/explorer_tools.py`: `grep` and the `symbols` degraded fallback
  call `search_engine.search(..., repo_root=repo_path)`; update the `_Search` protocol
  signature.
- Edit `harpyja/deep/host_tools.py`: `search` calls
  `search_engine.search(..., repo_root=repo_path)`; update the `_Search` protocol.
- All Step-4 tests pass; suite green.

### Step 6 — submit_citations surfaces (submitted, surviving) (RED)
- Add to `harpyja/scout/test_submit_citations.py`:
  - `test_submit_citations_returns_result_with_counts` — found-then-dropped:
    submitted=1, surviving=0 (an out-of-repo/scope-relative-style ref) vs an in-repo ref
    submitted=1, surviving=1.
  - `test_submit_citations_honest_empty_counts_zero_zero` — `[]` in → submitted=0,
    surviving=0 (distinguishable from found-then-dropped `(1, 0)`).
  - `test_submit_citations_single_production_caller` — asserts (via grep/AST over
    `harpyja/`) the ONLY non-test caller is `explorer_backend`'s `submit` closure.
- Existing `test_submit_citations_*` equality asserts are updated to read `.spans`.
- Tests fail: `submit_citations` returns `list[CodeSpan]`, no counts.

### Step 7 — Implement SubmitResult (GREEN)
- Edit `harpyja/scout/submit.py`: add `@dataclass SubmitResult(spans, submitted,
  surviving)`; `submit_citations` returns it (`submitted=len(raw)`,
  `surviving=len(normalized)`).
- Update existing submit tests to `.spans`. Step-6 tests pass.

### Step 8 — LoopResult carries the counts (RED)
- Add to `harpyja/scout/test_explorer_loop.py`:
  - `test_loop_result_carries_submitted_and_surviving_counts` — a fake `submit`
    returning `SubmitResult(spans, 1, 0)` yields a `LoopResult` with
    `citations_submitted=1`, `citations_surviving=0`.
  - `test_loop_honest_empty_counts_zero_zero` — `SubmitResult([], 0, 0)` →
    `LoopResult` counts `(0, 0)`, distinguishable from found-then-dropped.
- Tests fail: `LoopResult` has no count fields; `_answer_tool_call` builds it from a
  plain span list.

### Step 9 — Thread counts through the loop (GREEN)
- Edit `harpyja/scout/explorer_loop.py`: `LoopResult` gains
  `citations_submitted/citations_surviving` (defaulted); `_answer_tool_call` unpacks the
  `SubmitResult` (`.spans` into `LoopResult.spans`, counts into the new fields); update
  the `submit` callable type hint. Step-8 tests pass; positional constructions still
  work.

### Step 10 — Backend + verifier record the counts; schema bump + version-gate (RED)
- Add to `harpyja/scout/test_explorer_backend.py`:
  - `test_backend_threads_citation_counts_into_trajectory` — a fake loop producing
    `(submitted=1, surviving=0)` yields `last_trajectory` carrying
    `citations_submitted=1`, `citations_surviving=0`.
- Add to `harpyja/eval/test_live_verifier.py`:
  - `test_build_trajectory_record_carries_citation_counts` — the record includes both
    fields.
  - `test_verifier_schema_version_is_0033_1` — constant bumped.
  - `test_found_then_dropped_distinct_from_honest_empty_in_artifact` — `(1,0)` vs
    `(0,0)` distinguishable in the artifact.
  - `test_legacy_0031_artifact_still_validates` — a `0031/1` artifact (no count fields)
    passes `validate_verifier_artifact` via the version gate.
  - `test_fc_citation_dropped_count_and_report_schema_untouched` — asserts the
    eval-report field/schema are unchanged by this spec.
- Tests fail: `build_trajectory_record` lacks the params, backend doesn't pass them,
  version is `0031/1`, validator uses strict equality.

### Step 11 — Implement backend threading + verifier schema (GREEN)
- Edit `harpyja/eval/live_verifier.py`: `VERIFIER_SCHEMA_VERSION = "0033/1"`;
  `build_trajectory_record(..., citations_submitted=None, citations_surviving=None)`
  writes the fields; `validate_verifier_artifact` accepts
  `_KNOWN_VERIFIER_SCHEMA_VERSIONS = {"0031/1", "0033/1"}` with the count fields
  optional (defaulted).
- Edit `harpyja/scout/explorer_backend.py`: pass
  `citations_submitted=result.citations_submitted`,
  `citations_surviving=result.citations_surviving` into `build_trajectory_record`.
- Step-10 tests pass; suite green.

### Step 12 — run_verified_case carries the typed cause (RED)
- Add to `harpyja/eval/test_live_verifier.py`:
  - `test_run_verified_case_names_and_chains_degrade_cause` — a fake backend whose
    `run()` raises `ScoutUnavailable(<typed cause>)` and whose `last_trajectory` is
    `None`; assert the raised `ValueError` message NAMES the `.cause` and its
    `__cause__` IS the captured `ScoutUnavailable`.
- Test fails: `e` is discarded, the raise sits outside the except block (no chain), and
  the message is cause-less.

### Step 13 — Fix run_verified_case + delete dead assignment (GREEN)
- Edit `harpyja/eval/live_verifier.py::run_verified_case`: capture
  `degrade_cause = None`; in `except ScoutUnavailable as e:` set `degrade_cause = e` and
  DELETE the dead shadowed `last_trajectory = backend.last_trajectory`; at the
  no-trajectory raise, name `degrade_cause.cause` in the message and
  `raise ... from degrade_cause`. Trajectory-capturing paths unchanged. Step-12 passes.

### Step 14 — AC7 live re-run of the 0032 astropy case (integration)
- Add to `harpyja/eval/test_live_verifier_integration.py`:
  - `test_astropy_live_scoped_grep_survives_or_not_exercised`
    (`@pytest.mark.integration`) — `skip` when the stack/worktree is absent; run the
    astropy case; IF the model cited a scoped-grep hit, assert `citations_surviving > 0`
    and both counts recorded; ELSE record NOT-EXERCISED in findings (never a silent
    pass). AC3's hermetic Step-4 fixture is the deterministic proof; the deliverable run
    fails loud only on a genuine drop.

### Step 15 — conventions.md + record decisions (doc, AC8)
- Edit `.speccraft/conventions.md`: add the tool-contract rule (every path-DISCOVERING
  tool emits repo-relative paths; fix path-shape defects at the ONE engine seam, never
  per-caller, never by downstream repair), the 0012→0025→0033 history, and the
  two-normalize-passes scope note for `fc_citation_dropped_count` (engine-pass drops
  only; the explorer submit-time drop rides `citations_submitted/surviving`).
- The OQ1/OQ2 decisions are recorded above in this plan.
- Suite green; `ruff` clean.

## Delegation

- Steps 2–3 (engine re-prefix + real-`rg` integration) → keep with the primary
  implementer: the `rg` invocation-vs-parse boundary and the file-scope parent-dir
  special case are subtle and central to the whole fix.
- Steps 6–11 (submit → loop → backend → verifier threading + schema gate) → a single
  implementer end-to-end so the `SubmitResult`/`LoopResult`/artifact field names stay
  consistent across the four files.
- Step 14 (live integration) → run by whoever has the Ollama/`rg` stack; skip-not-fail
  keeps CI green without it.

## Risk

- **rg ordering / `.gitignore` drift on the repo-root path** → mitigation: mechanism (b)
  leaves the `rg` invocation byte-identical for directory scopes; Step-1 pins it and
  Step-2's real-`rg` case guards ordering + ignore-file resolution.
- **Schema bump breaks legacy `0031/1` artifacts** → mitigation: version GATE (not
  strict equality) with the count fields optional; Step-10 legacy-artifact fixture pins
  it.
- **submit_citations return-shape ripple** → mitigation: single production caller
  (asserted, Step-6) updated in the same change; `LoopResult` fields defaulted so
  positional constructions keep working.
- **file-scope engine special case** (`symbols` degraded fallback) → mitigation: pinned
  explicitly in Step-2 (`test_search_file_scope_...`) and Step-4 (fallback no-crash),
  supported via parent-dir cwd — never silent drift.
