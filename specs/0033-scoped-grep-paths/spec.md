---
id: "0033"
title: "scoped-grep-paths"
status: draft
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

**INVARIANT (fix at the tool seam, once):** scoped-grep output is made repo-relative at the
`RipgrepEngine`/tool-wrapper seam — the ONE bounded rg source of truth shared by the explorer
`grep` and the Deep `search` host tool — never per-caller, never by re-adding a downstream
suffix-recovery repair. Every consumer of the engine inherits the fix in the same change
(blast radius enumerated: explorer grep, Deep search, Tier-0 locate path, any eval driver).

**INVARIANT (tool-contract consistency):** after the fix, EVERY explorer tool that returns
paths (`grep`, `glob`, `ls`, `symbols`, `read_span`) returns repo-relative paths — asserted
as one contract test over the tool suite, not per-tool prose.

**INVARIANT (found-then-dropped is visible forever):** the trajectory/verifier record carries
a submitted-vs-surviving citation count (`citations_submitted` / `citations_surviving`),
so a normalization drop is DISTINGUISHABLE from an honest-empty submission in the artifact.
This class of defect must never again hide inside `empty`. Additive fields,
`VERIFIER_SCHEMA_VERSION` bumped per the additive-last-with-defaults rule.

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
`run_verified_case` (live_verifier.py) currently catches `ScoutUnavailable` without binding
it and then raises a cause-less `ValueError("Explorer did not capture trajectory")` when the
explorer degraded before producing a `LoopResult` — the 0031 diagnosability gap that cost a
masked-cause debugging round in 0032's AC6 run. Since 0033's AC6 re-run drives this exact
function, the fix folds in: bind the exception, carry the typed cause in the raise
(`... (scout cause: {e.cause})`, `raise ... from e`). No behavior change on any path that
captures a trajectory; only the failure message/chain improves.

**INVARIANT (behavior-preserving on unscoped input):** `grep(pattern)` with no scope (or
scope=".") returns byte-identical results to today. The fix changes ONLY the path prefix of
scoped results; match content, bounds, and clamps are untouched.

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
- Fix `run_verified_case`'s cause-swallowing: bind the caught `ScoutUnavailable` and carry
  its typed cause into the "Explorer did not capture trajectory" raise (`from e`).
- Re-run the 0032 AC6 astropy case live: the scoped-grep citation should now survive
  normalization and the bucket should reflect the model's actual output (expected:
  wrong-file for the historical cite, but the RUN's bucket is whatever the model does —
  the point is the citation is no longer silently dropped).

## Acceptance Criteria

1. **[unit]** `RipgrepEngine.search` with a subdirectory scope returns repo-relative paths;
   with no scope / scope="." results are byte-identical to today (regression pin).
2. **[unit]** Tool-contract consistency: one test asserts every path-returning explorer tool
   emits repo-relative paths (grep scoped + unscoped, glob, ls, symbols).
3. **[unit]** The astropy shape end-to-end: a scoped-grep hit cited via `submit_citations`
   survives `normalize_spans` (no drop); the django shape unchanged.
4. **[unit]** Blast radius: the Deep `search` host tool and the Tier-0 locate path are
   asserted unaffected on unscoped input (shared-engine consumers enumerated + each pinned).
5. **[unit]** Verifier carries submitted-vs-surviving, counted AT THE SUBMIT SEAM:
   `submit_citations` surfaces `(submitted, surviving)`; the counts thread LoopResult →
   backend → `build_trajectory_record` → artifact (additive); a found-then-dropped fixture
   (submitted=1, surviving=0) is distinguishable from an honest-empty fixture
   (submitted=0, surviving=0) in the artifact; `VERIFIER_SCHEMA_VERSION` bumped, legacy
   artifacts still validate. `fc_citation_dropped_count` and the eval-report schema are
   byte-untouched (asserted), its engine-pass-only scope documented.
6. **[unit]** `run_verified_case` carries the typed cause: when the explorer degrades
   pre-trajectory, the raise names `e.cause` and chains `from e` — pinned by a unit test
   with a raising fake backend; behavior on trajectory-capturing paths unchanged.
7. **[integration]** The 0032 astropy case re-run live: the scoped-grep citation is no longer
   dropped (surviving count > 0 when the model cites a scoped-grep hit), and the artifact
   records both counts. Skip-not-fail on absent stack; the deliverable run fails loud.
8. **[doc]** conventions.md: the tool-contract rule (every path-returning tool emits
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

1. Fix mechanism: run rg from repo root with scope as a path argument (canonical output,
   possibly changes match ordering/`./` prefixes) vs re-prefix parsed paths with the scope's
   repo-relative prefix (smaller diff, keeps rg invocation untouched)? Decide at plan after
   reading `_default_runner_factory` and every `RipgrepEngine` constructor site.
2. Does the engine need the repo root threaded as a constructor field, or can the wrapper
   (`explorer_tools.grep`) re-prefix — and if the wrapper does it, does the Deep `search`
   host tool have the same defect today (check: does Deep pass subdirectory scopes)?
