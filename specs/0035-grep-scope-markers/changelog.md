---
spec: "0035"
closed: 2026-07-09
---

# Changelog — 0035 grep-scope-markers

## Epistemic status (read this first — the closing verdict, carried verbatim-faithful)

Markers implemented and unit-proven; live redirection unobserved (this run used
valid scopes); whether markers change model behavior is the eval set's measurement.
"AC6 landed honestly" must NOT blur into "the fix works": it works MECHANICALLY
(markers fire, fixtures green); its BEHAVIORAL effect is still unmeasured, by design.

- **MECHANICALLY PROVEN** — markers fire, file-scope delegation returns REAL
  repo-relative matches, the Deep uncaught-crash path is closed; all hermetic
  fixtures green (1193 units).
- **LIVE REDIRECTION UNOBSERVED** — no live run has yet shown a model RECEIVING a
  marker (this run's model used only valid scopes: bucket wrong-file, clean terminal
  submit). The NOT-EXERCISED record is the honest close, not a gap.
- **BEHAVIORAL EFFECT UNMEASURED BY DESIGN** — whether the markers or the delegation
  change model behavior or bucket distributions is the EVAL SET's paired measurement,
  not this spec's claim.

## What shipped vs spec

13/13 tasks; all 8 ACs met at their stated strength; 1193 units pass; ruff 36 =
baseline (zero-new). The spec's own review round resolved the design toward
delegation and discovered a new defect — both are reflected in what shipped.

### AC1 — file-scope grep DELEGATES (unit)
The `is_dir()` file-scope early-return guard in `grep` was DELETED. An existing FILE
scope now falls through to the engine (the 0033 parent-dir + filename mechanism) and
returns REAL repo-relative matches. The 0033 astropy observation (the model grepped
the RIGHT file, `astropy/modeling/separable.py`, and got a bare `[]`) is now a
POSITIVE regression fixture: the same grep returns the engine's real spans, not a
marker, not `[]`.

### AC2 — nonexistent-scope marker, in the loop conversation (unit)
A nonexistent scope returns the stable identifier `grep-scope-not-found: '<scope>'`
BEFORE delegation. Ordering is pinned by an injected raising-engine (a missing cwd
crashes the engine's subprocess, so the marker MUST return first). The marker string
reaches model-visible history verbatim, is non-terminal (the run reaches terminal
submit), `note_navigation` still trips loop detection on repeated bad scopes, and it
never wears the 0029 `tool-call-degraded:execution-error:` mislabel. ZERO
`explorer_loop.py` changes — the marker-return design's whole point.

### AC3 — honest-empty preserved (unit)
Three ways: a real DIRECTORY scope with zero matches → plain `[]`; a real FILE scope
with zero matches → delegates to the engine and returns plain `[]` (engine WAS
called, asserted); success-path grep byte-identical. "Searched, nothing found" and
"could not search" stay distinct states.

### AC4 — ls marker + confine_path pin (unit)
`ls` on a nonexistent path returns `ls-path-not-found: '<path>'`. `ls` on an existing
FILE keeps honest-`[]` (OQ1 resolved toward keep — "list children" of a file is
genuinely empty, categorically distinct from path-absent). `confine_path`'s
NON-STRICT resolve (a nonexistent in-repo path passes confinement without raising) is
pinned in the NEW `harpyja/server/test_tools.py` — the contract the marker branches'
`exists()` guard depends on cannot silently switch to strict.

### AC5 — Deep `search`, per-shape (unit) — the review-discovered defect fixed
The RED test reproduced the exact uncaught `FileNotFoundError`
(`subprocess.run(cwd=<nonexistent>)`, no typed catch anywhere on the
`host_tools.search` / `RlmBackend.run` path) — a graceful-degradation guardrail
violation found by review, WORSE than the silent-`[]` the spec originally claimed as
"the same gap." The exists-guard was added before delegation (`_charge()` kept first
— a bad-scope call is still a real, charged tool call), returning
`search-scope-not-found: '<scope>'`. Deep `search` and explorer `grep` now converge
on the one engine contract. File-scope no-defect pinned as the behavior the explorer
now converges to.

### AC6 — live: NOT-EXERCISED, honestly (integration)
The live run's model used only valid scopes (bucket wrong-file, clean terminal
submit), so no marker was exercised — the 0023 NOT-EXERCISED fallback printed (never
a silent pass). The marker/loop mechanism proof is carried by the hermetic
wrapper/loop tests. AND the harness fix proved itself in the SAME run: the verifier
artifact persisted durably at
`eval_work/live_artifacts/bad_scope_marker/20260709T183038Z-20622/` — the FIRST live
run whose bucket question is answerable later WITHOUT a re-run.

### AC7 — persistent-artifacts helper (unit)
NEW `harpyja/eval/live_artifacts.py` (`live_artifact_dir` + `write_live_artifact`)
over the SAME outside-repo `atomic_write_json` (inside-repo refusal + atomic
semantics inherited, never re-implemented). Path shape, writer reuse, and the
repo/out-dir separation both directions pinned; the base path is NOT a `Settings`
field (eval-knobs-disjoint asserted over `dataclasses.fields(Settings)`). Three
integration tests migrated off `TemporaryDirectory`.

### AC8 — conventions.md (doc)
Gained the unsearchable-scope typed-marker rule + the file-scope-delegation
convergence (explorer `grep` == Deep `search` == one engine contract) + the
persistent-artifacts harness rule (all written in T12 — not duplicated here).

## The two load-bearing review findings

1. **The delegation fork.** Review resolved the file-scope design toward DELETING the
   `is_dir()` guard and delegating to the engine, rather than adding a file-scope
   marker: post-0033 the engine searches a FILE scope for real, so the guard blocked
   a strictly-better outcome. This turned the spec's headline fixture (the 0033
   astropy right-file grep) from a marker case into a positive delegated-match test.
2. **The Deep uncaught-crash discovery.** Review corrected the spec's "Deep has the
   same silent-`[]` gap" framing (code-wins): Deep's nonexistent-scope shape was an
   uncaught `FileNotFoundError` — a DISTINCT, worse defect than a silent `[]`, a
   graceful-degradation guardrail violation an audit told to look for "the same gap"
   would have wrongly closed as not-applicable. Fixed at guardrail altitude in this
   spec.

## Deviations

- 3 transient ruff errors self-caught and fixed during implementation (net ruff 36 =
  baseline, zero-new).
- T13 (optional refactor) evaluated and deliberately SKIPPED: the three wrappers'
  guards are three 2-line shapes with distinct identifiers and (for `ls`) a distinct
  second branch — extraction over-abstracts; the wrappers stay separate.
- The persistent-artifact durability is a POSITIVE first, not a gap: the AC6 run is
  the first live run whose artifact survived its own process.

## Files touched

- `harpyja/scout/explorer_tools.py` (grep guard deleted + marker; ls marker)
- `harpyja/deep/host_tools.py` (search exists-guard-before-engine + marker)
- `harpyja/eval/live_artifacts.py` (NEW — persistent-artifacts helper)
- `harpyja/eval/test_live_artifacts.py` (NEW)
- `harpyja/eval/test_live_verifier_integration.py` (migration + AC6 live test)
- `harpyja/scout/test_explorer_tools.py`
- `harpyja/scout/test_explorer_loop.py`
- `harpyja/deep/test_host_tools.py`
- `harpyja/server/test_tools.py` (NEW — confine_path non-strict pin)
- `.speccraft/conventions.md` (T12 — AC8 rules)

## ADR proposed for history.md

See the prepended 2026-07-09 entry in `.speccraft/history.md`.

## Conventions proposed

None new here — the two rules (typed unsearchable-scope marker + delegation
convergence; persistent live-artifacts harness) were authored in T12/AC8 and are
already in `conventions.md`. No duplication.

## Named next step

The eval-set spec: its full prerequisite stack is now shipped
(0031 verifier → 0032 one-parser → 0033 repo-relative paths + submitted/surviving
counts → 0034 reasoning observability → 0035 honest affordances + durable artifacts).
Two measurement inputs wait on it: the thinking-arm A/B (0034) and the
marker/delegation bucket effect (0035) — the behavioral question this spec left
unmeasured by design.
