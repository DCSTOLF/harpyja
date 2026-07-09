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
a submitted-vs-surviving citation count (e.g. `citations_submitted` / `citations_surviving`
or a dropped count), so a normalization drop is DISTINGUISHABLE from an honest-empty
submission in the artifact. This class of defect must never again hide inside `empty`.
Additive fields, `VERIFIER_SCHEMA_VERSION` bumped per the additive-last-with-defaults rule.

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
- Add the submitted-vs-surviving count to `build_trajectory_record` / the verifier artifact
  (additive, schema-bumped), so found-then-dropped is a first-class recorded fact.
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
5. **[unit]** Verifier carries submitted-vs-surviving: `build_trajectory_record` (and the
   artifact) record the counts additively; a found-then-dropped fixture is distinguishable
   from an honest-empty fixture in the artifact; `VERIFIER_SCHEMA_VERSION` bumped,
   legacy artifacts still validate.
6. **[integration]** The 0032 astropy case re-run live: the scoped-grep citation is no longer
   dropped (surviving count > 0 when the model cites a scoped-grep hit), and the artifact
   records both counts. Skip-not-fail on absent stack; the deliverable run fails loud.
7. **[doc]** conventions.md: the tool-contract rule (every path-returning tool emits
   repo-relative paths; fix path-shape defects at the engine seam, never per-caller, never
   by downstream repair) + the 0012→0025→0033 history recorded.

## Out of Scope

- Re-adding suffix recovery (`_recover_suffix`) or any downstream path repair — the fix is
  at the producer.
- The bake-off / eval set themselves (they run AFTER this clears).
- Any change to normalize_spans' validation rules (repo-confine + is_file stay the gate).
- `run_verified_case` cause-swallowing diagnosability gap (0031 debt, noted in 0032
  ac6-findings.md — separate line item, fold in only if trivially adjacent).

## Open Questions

1. Fix mechanism: run rg from repo root with scope as a path argument (canonical output,
   possibly changes match ordering/`./` prefixes) vs re-prefix parsed paths with the scope's
   repo-relative prefix (smaller diff, keeps rg invocation untouched)? Decide at plan after
   reading `_default_runner_factory` and every `RipgrepEngine` constructor site.
2. Does the engine need the repo root threaded as a constructor field, or can the wrapper
   (`explorer_tools.grep`) re-prefix — and if the wrapper does it, does the Deep `search`
   host tool have the same defect today (check: does Deep pass subdirectory scopes)?
3. Where exactly does submitted-vs-surviving live: on the trajectory record only, or also
   surfaced into the eval report schema (a `fc_citation_dropped`-adjacent field already
   exists — reconcile rather than duplicate)?
