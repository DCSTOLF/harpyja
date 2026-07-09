---
id: "0033"
title: "scoped-grep-paths"
status: closed
started_at_sha: f736bde
created: 2026-07-08
authors: [claude]
packages: []
related-specs: ["0032-trajectory-parser", "0031-live"]
---

# Spec 0033 — scoped-grep-paths (measurement-integrity blocker before bake-off)

## Why

Spec 0032's AC6 live run surfaced this with a within-run A/B that isolates the variable.
The explorer's `grep(pattern, scope=...)` returns **scope-relative** paths: `RipgrepEngine.search`
runs `rg` with cwd=scope and parses the reported paths verbatim (`symbols/ripgrep.py::_parse`,
`data["path"]["text"]`). A model that greps a subdirectory gets paths like `modeling/core.py`
(missing the `astropy/` prefix), faithfully cites them in `submit_citations`, and
`normalize_spans`' repo-confine + `is_file` check drops them — **found-then-dropped reads as
EMPTY**, indistinguishable from found-nothing in the terminal bucket.

The 0032 evidence pair (specs/0032-trajectory-parser/ac6-findings.md + ac6-artifacts/):

- **astropy-12907**: `grep(..., scope="astropy/")` → hit → submitted `modeling/core.py:812` →
  DROPPED at normalize → bucket `empty`. The model found and cited; the tool contract lost it.
- **django-12774** (the control): `grep(..., scope=".")` → repo-relative paths → submitted
  `django/db/models/query.py:693` → KEPT → bucket `correct` (genuine gold-span overlap).

Same tool, same run pair — only the scope string differs, and it alone flips the measured
bucket. This is a tool-contract inconsistency (`glob`/`ls` return repo-relative paths; scoped
`grep` does not), NOT model capability variance. It systematically converts would-be
wrong-file/right-file outcomes into EMPTY for any model that greps scoped — **penalizing
models that grep more precisely** — and distorts the 0022 file-vs-span diagnostic axis the
bake-off depends on. This is a BLOCKER: it must clear before the bake-off or eval set trusts
bucket distributions.

**History (the 0012/0025 arc — this defect is a regression re-creation, not a novelty):**
spec 0012 built suffix recovery (`normalize.py::_recover_suffix`, longest-unique ≥2-segment
manifest-anchored suffix match) for EXACTLY this path shape, in the FastContext era. Spec 0025
removed it as FC-era code when FastContext was deleted (recovered counts structurally zero).
The native explorer has now re-created the input shape that machinery existed to fix — but the
RIGHT fix this time is at the producer (the tool seam), not a downstream repair: the tool
should never emit a path the submit path can't validate.

**Ref:** 0032 ac6-findings.md (the A/B evidence), `harpyja/symbols/ripgrep.py::search`/`_parse`
(rg cwd=scope, verbatim relative paths), `harpyja/scout/explorer_tools.py::grep` (the wrapper),
conventions.md "one bounded rg source of truth" (the fix location rule), 0012/0025 history.

## Invariants

**INVARIANT (fix at the ENGINE seam, once — DECIDED, wrapper option eliminated):** scoped
output is made repo-relative INSIDE `RipgrepEngine` — the ONE bounded rg source of truth —
never per-caller, never by re-adding a downstream suffix-recovery repair. A wrapper-level
re-prefix in `explorer_tools.grep` is EXCLUDED: it would not reach Deep's `search` host tool
(which passes subdirectory scopes through the same engine and has the same defect today),
i.e. it IS the per-caller fix this invariant forbids. The mechanism choice at plan is
between two ENGINE-level options only: (a) run rg from the repo root with the scope as a
relative path argument (note: callers pass ABSOLUTE scopes today, so the engine must compute
the repo-relative scope — the repo root likely needs threading into the engine), or
(b) engine-level re-prefix of parsed paths with the scope's repo-relative prefix. Every
consumer of the engine inherits the fix in the same change — blast radius enumerated and
EACH pinned: explorer `grep` (scoped + unscoped), Deep `search` (scoped + unscoped), Tier-0
locate (which passes `scope=req.repo_path`, the ABSOLUTE REPO ROOT — a distinct variant to
pin, not a no-scope call), the `symbols` degraded fallback (see next paragraph), and any
eval driver.

**Blast-radius edge (enumerated, decide-at-plan):** `explorer_tools.symbols()`'s degraded
fallback calls `search_engine.search("", scope=str(candidate))` where `candidate` is a
resolved FILE path — with the default runner (`subprocess.run(cwd=scope)`) this raises
`NotADirectoryError` TODAY (broken outside injected-runner tests), and the two engine fix
mechanisms change its behavior differently. This consumer is IN scope: the plan must pin its
post-fix behavior explicitly (a file scope either becomes a supported rg path argument under
mechanism (a), or is normalized/rejected loudly — never a silent behavior drift).

**INVARIANT (tool-contract consistency):** after the fix, every explorer tool that DISCOVERS
paths (`grep` scoped + unscoped, `glob`, `ls`, `symbols`) returns repo-relative paths —
asserted as one contract test over the tool suite, not per-tool prose. `read_span` is
EXCLUDED from the producer contract with rationale: it echoes the caller-supplied path and
discovers nothing, so it has no path-shape authority of its own. `ls` directory entries
(the trailing-`/` shape, e.g. `modeling/`) are repo-relative but non-citable listings — the
contract test states that semantic explicitly rather than treating them as citation paths.

**INVARIANT (found-then-dropped is visible forever):** the trajectory/verifier record carries
a submitted-vs-surviving citation count (`citations_submitted` / `citations_surviving`),
so a normalization drop is DISTINGUISHABLE from an honest-empty submission in the artifact.
This class of defect must never again hide inside `empty`. Named concretely:
`citations_submitted` / `citations_surviving`, `VERIFIER_SCHEMA_VERSION "0031/1" → "0033/1"`.
**Validator mechanism scoped (the additive claim must be implementable):**
`validate_verifier_artifact` today hard-fails on `schema_version != VERIFIER_SCHEMA_VERSION`
(strict equality) and `live_verifier.py` has none of `report.py`'s `_with_defaults`
machinery — so "legacy artifacts still validate" requires the validator to version-gate
(accept the enumerated known versions, defaulting the new fields for `0031/1` blocks — the
0026 `DATASET_SCHEMA_VERSION` pattern) or grow a `_with_defaults` map (the `report.py`
pattern). Pick at plan; either way the mechanism ships IN this spec, not assumed.
**Interface shape named:** `submit_citations` returns `list[CodeSpan]` today and
`LoopResult` carries only spans/outcome/history/turns — the counts ride a small result
shape (or non-breaking out-param per the `recovered_paths_out` precedent) from
`submit_citations` through `LoopResult` to the backend; the loop's terminal handling is the
single production caller and is updated in the same change, with an assertion that no other
caller of `submit_citations` exists.

**DECIDED (count at the drop seam — `fc_citation_dropped_count` is NOT this measurement):**
there are TWO normalize passes and the existing field watches the wrong one. The explorer's
drop happens inside the loop's terminal action — `submit.submit_citations` →
`normalize_spans` — where the count is currently DISCARDED (no tally). `ScoutEngine.search`
then re-normalizes the backend's ALREADY-normalized survivors via
`normalize_spans_with_tally`, and THAT pass feeds `ScoutTally.dropped` →
`fc_citation_dropped_count` — structurally ~0 for submit-time drops in the explorer era
(the 0032 astropy drop was invisible to it). Therefore: (a) the counts are captured AT the
submit seam (`submitted = len(citations)` in, `surviving = len(normalized)` out — the one
pass where the explorer drop occurs), threaded as data `LoopResult` → `ExplorerBackend` →
`build_trajectory_record` → verifier artifact, mirroring the `last_turns_used` /
`last_trajectory` side-channel discipline; (b) `fc_citation_dropped_count` is NOT overloaded,
repurposed, or duplicated — its actual scope (engine-pass drops, ~0 for the explorer) is
documented as part of this spec's conventions entry, extending the 0025 backend-neutral
naming-debt record; the eval-report schema is NOT touched (the bake-off consumes verifier
artifacts, where the per-case counts now live).

**DECIDED (fold the cause-swallowing fix in — same file, same function, tiny diff):**
`run_verified_case` (live_verifier.py) binds the caught exception (`except ScoutUnavailable
as e:`) but DISCARDS it — the cause-less `ValueError("Explorer did not capture trajectory")`
raise sits OUTSIDE the except block, where `e` is already out of scope (Python deletes the
except variable at block exit), so no chain is possible as the code stands. This is the 0031
diagnosability gap that cost a masked-cause debugging round in 0032's AC6 run. Since 0033's
AC6 re-run drives this exact function, the fix folds in: capture the exception (and its
typed `.cause`) into a variable that OUTLIVES the except block, name the cause in the raise
message, and chain `from` the captured exception. While in the block, delete the dead
`last_trajectory = backend.last_trajectory` assignment inside the except (immediately
shadowed by the unconditional one two lines later). No behavior change on any path that
captures a trajectory; only the failure message/chain improves.

**INVARIANT (behavior-preserving on unscoped input, pinned at a NAMED seam):** at the
`RipgrepEngine.search` seam, `scope=None` / `scope="."` today means the HARPYJA PROCESS cwd
(`scope or "."`), NOT the repo root — every production caller papers over this by passing an
ABSOLUTE scope (Tier-0 passes `scope=req.repo_path`). The pin is therefore: absolute-repo-root
scope (the Tier-0/django shape) returns byte-identical results to today, asserted via an
injected-runner fixture PLUS one real-rg integration case (rg-from-root can subtly shift
match ORDERING and ignore-file resolution — the pin must tolerate none of that on this path).
Whether bare `scope=None` comes to mean repo root (a behavior change only for a hypothetical
cwd-relying caller — none exist in production) is decided at plan when the repo-root
threading lands. The fix changes ONLY the path prefix of subdirectory-scoped results; match
content, bounds, and clamps are untouched.

## What

- Make `RipgrepEngine.search(pattern, scope=subdir)` return repo-relative paths: either run
  rg from the repo root passing the scope as a path argument, or re-prefix the parsed paths
  with the scope's repo-relative prefix at `_parse`/`search` — decide at plan (the former
  keeps rg's own output canonical; the latter is the smaller diff). Note the engine currently
  has no notion of "repo root" vs "scope" — the seam may need the repo root threaded (check
  every constructor site).
- Regression-pin the 0032 evidence pair as a unit fixture: a scoped grep whose hit is cited
  through `submit_citations` must now survive `normalize_spans` (the astropy shape), and the
  unscoped path stays byte-identical (the django shape).
- Add the submitted-vs-surviving count at the SUBMIT seam (the decided design above):
  `submit_citations` surfaces `(submitted, surviving)`, threaded through `LoopResult` →
  `ExplorerBackend` → `build_trajectory_record` → the verifier artifact (additive,
  schema-bumped), so found-then-dropped is a first-class recorded fact.
- Fix `run_verified_case`'s cause-swallowing: capture the caught `ScoutUnavailable` (and its
  typed `.cause`) into a variable that outlives the except block, name the cause in the
  "Explorer did not capture trajectory" raise, chain `from` the captured exception, and
  delete the dead shadowed `last_trajectory` assignment inside the except.
- Re-run the 0032 AC6 astropy case live: the scoped-grep citation should now survive
  normalization and the bucket should reflect the model's actual output (expected:
  wrong-file for the historical cite, but the RUN's bucket is whatever the model does —
  the point is the citation is no longer silently dropped).

## Acceptance Criteria

1. **[unit]** `RipgrepEngine.search` with a subdirectory scope returns repo-relative paths —
   parameterized over the scope variants: `"astropy"` (no trailing slash), `"astropy/"`
   (trailing slash), a nested scope (`"astropy/modeling"`), and rg's `./`-prefixed output
   shapes. The absolute-repo-root scope (the Tier-0/django shape) is byte-identical to today,
   pinned via an injected-runner fixture PLUS one real-rg integration case (ordering and
   ignore-file resolution included in the pin).
2. **[unit]** Tool-contract consistency: one test asserts every path-DISCOVERING explorer
   tool emits repo-relative paths (grep scoped + unscoped, glob, ls, symbols clean branch).
   `read_span` excluded with the echoes-input rationale; `ls` directory entries asserted as
   repo-relative non-citable listings (trailing-`/` semantics stated in the test).
3. **[unit]** The astropy shape end-to-end: a scoped-grep hit cited via `submit_citations`
   survives `normalize_spans` (no drop); the django shape unchanged.
4. **[unit]** Blast radius, each shared-engine consumer pinned in BOTH directions: Deep
   `search` scoped output POSITIVELY changes to repo-relative (the inherited fix — not just
   unscoped non-regression) and unscoped stays byte-identical; Tier-0 locate
   (`scope=req.repo_path`) byte-identical; the `symbols` degraded fallback
   (`search("", scope=<file path>)` — raises `NotADirectoryError` with the default runner
   today) gets an explicit post-fix behavior pin (supported file-scope or loud rejection,
   decided at plan — never silent drift).
5. **[unit]** Verifier carries submitted-vs-surviving, counted AT THE SUBMIT SEAM:
   `submit_citations` surfaces the counts via the named result shape (single production
   caller — the loop's terminal handling — updated in the same change, no-other-caller
   asserted); the counts thread LoopResult → backend → `build_trajectory_record` → artifact
   as `citations_submitted` / `citations_surviving`; a found-then-dropped fixture
   (submitted=1, surviving=0) is distinguishable from an honest-empty fixture
   (submitted=0, surviving=0) in the artifact; `VERIFIER_SCHEMA_VERSION "0031/1" → "0033/1"`
   with the validator version-gated or defaults-mapped so a `0031/1` artifact still validates
   (the mechanism ships in this spec — pinned by a legacy-artifact fixture test).
   `fc_citation_dropped_count` and the eval-report schema are byte-untouched (asserted), its
   engine-pass-only scope documented.
6. **[unit]** `run_verified_case` carries the typed cause: when the explorer degrades
   pre-trajectory, the raise names the captured `.cause` and chains `from` the captured
   exception (captured OUTSIDE the except block's variable lifetime) — pinned by a unit test
   with a raising fake backend asserting both the message and `__cause__`; behavior on
   trajectory-capturing paths unchanged; the dead shadowed assignment is gone.
7. **[integration]** The 0032 astropy case re-run live: when the model cites a scoped-grep
   hit, the citation is no longer dropped (surviving count > 0) and the artifact records both
   counts. The condition is MODEL-BEHAVIOR-CONTINGENT (a run where the model never greps
   scoped cannot exercise it — the 0023 input-validity-precondition rule): such a run records
   the condition as NOT-EXERCISED in the findings (never a silent pass), and AC3's hermetic
   fixture remains the deterministic proof the fix works. Skip-not-fail on absent stack; the
   deliverable run fails loud.
8. **[doc]** conventions.md: the tool-contract rule (every path-DISCOVERING tool emits
   repo-relative paths; fix path-shape defects at the engine seam, never per-caller, never
   by downstream repair) + the 0012→0025→0033 history + the two-normalize-passes scope note
   for `fc_citation_dropped_count` recorded.

## Out of Scope

- Re-adding suffix recovery (`_recover_suffix`) or any downstream path repair — the fix is
  at the producer.
- The bake-off / eval set themselves (they run AFTER this clears).
- Any change to normalize_spans' validation rules (repo-confine + is_file stay the gate).
- Any eval-report schema change (`fc_citation_dropped_count` et al. byte-untouched — the
  per-case counts live on the verifier artifact, where the bake-off reads).
- Renaming the `fc_`-prefixed report fields (0025 naming debt — stays debt).

## Open Questions

Both remaining OQs are ENGINE-level mechanism choices — the wrapper-level option is
eliminated by the fix-at-the-engine-seam invariant (it would leave Deep's `search`, which
demonstrably has the same defect, with the old contract — the per-caller fix the invariant
forbids).

1. Engine fix mechanism: (a) run rg from the repo root with the scope as a relative path
   argument (canonical output; requires computing the repo-relative scope from the absolute
   scope callers pass; may shift match ordering / `./` prefixes / ignore-file resolution —
   AC1's byte-identical repo-root pin guards this) vs (b) engine-level re-prefix of parsed
   paths (smaller diff, rg invocation untouched; must handle the trailing-slash and nested
   variants AC1 enumerates)? Decide at plan after reading `_default_runner_factory` and
   every `RipgrepEngine` constructor site.
2. Repo-root threading: constructor field on `RipgrepEngine` vs a `search(..., repo_root=)`
   param — and does bare `scope=None` come to mean repo root (no production caller relies on
   process-cwd today; Tier-0 always passes the absolute repo path)? Decide with OQ1; the
   `symbols` degraded-fallback file-scope pin (AC4) depends on which mechanism lands.
