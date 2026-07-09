---
id: "0035"
title: "grep-scope-markers"
status: draft
started_at_sha: 2d6843f
created: 2026-07-09
authors: [claude]
packages: []
related-specs: ["0034-reasoning-observability", "0033-scoped-grep-paths", "0029-loop"]
---

# Spec 0035 — grep-scope-markers (silent-`[]` affordance gap; SUT fix before the eval set)

## Why

The explorer's `grep` wrapper returns a bare `[]` for two failure shapes that are NOT
"searched and found nothing": a FILE scope (`if scope and not scoped_path.is_dir():
return []` — by-design redirect toward `read_span`) and a NONEXISTENT scope (same
branch — a hallucinated directory silently reads as no-matches). Two attributable live
observations (visible only thanks to the 0031–0034 instrument stack):

- **0033 astropy run:** the model grepped `scope="astropy/modeling/separable.py"` (a
  file — the RIGHT file) twice, read the bare `[]` as no-matches, and finished
  honest-empty. It was one affordance away from the gold file.
- **0034-era run:** a 6554-char reasoning turn produced `grep(scope="repo")` — a
  hallucinated directory — whose silent `[]` sent the model into the wrong subsystem
  (`coordinates/matrix_utilities.py`), finishing honest-empty.

Both shapes inflate the `empty` bucket with runs where the model searched an
unsearchable scope — a tool-contract honesty gap (the same "we never looked" reading as
"we looked and found nothing" the no-silent-coverage convention forbids), and a
systematic bucket distorter the eval set must not baseline on. **The 0033 precedent is
exact: a tool-contract defect is fixed in its own small SUT spec BEFORE anything trusts
the distributions** — an eval/measurement spec runs SUT-byte-frozen and structurally
cannot contain this change.

**INVARIANT (causal claim withheld):** this spec claims only that the two shapes become
DISTINGUISHABLE to the model and in the trajectory — NOT that the markers improve
localization. Whether the affordance moves buckets is the eval set's measurement (the
same epistemics as the think-experiment verdict).

## Invariants

**INVARIANT (marker, not raise; the 0029 shape):** the fix is a typed, MODEL-VISIBLE,
non-terminal in-conversation message — the same posture as the sanctioned
`tool-call-degraded:execution-error` marker (spec 0029): recorded in-conversation, the
batch/loop continues, NOT a `ScoutUnavailable`, NOT counted in the degrade report. A bad
scope is a recoverable navigation mistake, never a run-terminal event.

**INVARIANT (stable identifiers):** the markers are stable machine-readable identifiers
per the cause-taxonomy rule — `grep-scope-not-found: '<scope>'` and
`grep-scope-is-a-file: '<scope>' — use read_span for file contents` (exact strings at
plan) — so trajectories and tests branch on the identifier, never prose.

**INVARIANT (tool surface unchanged):** exact-tool-count stays five; `grep`'s signature
and its CodeSpan-list SUCCESS shape are untouched — only the two early-return `[]`
branches change what the LOOP sees (decided at plan: the wrapper returns a marker value
the loop's stringification surfaces, or the wrapper raises a narrow typed error the
loop's existing per-call degrade catch converts — whichever keeps `_spans_of`/history
semantics byte-identical for success paths). Deep's `search` host tool is explicitly
audited for the same gap and fixed-or-excluded with rationale in the same change (the
one-rg-seam blast-radius discipline — note the gap lives in the WRAPPERS, not the
engine, so each wrapper is its own decision).

**INVARIANT (empty stays honest):** a real directory scope with zero matches still
returns plain `[]` — no marker. The marker fires ONLY when the scope itself was
unsearchable; "searched, nothing found" and "could not search" are the two states being
separated, and the separation must not blur the honest-empty case.

## What

- The `grep` wrapper's two early-return branches emit the typed model-visible markers
  instead of bare `[]` (mechanism decided at plan per the invariant above).
- The 0033/0034 observed shapes become regression fixtures: a file-scope grep and a
  nonexistent-scope grep each produce their marker in the loop conversation; a
  valid-scope empty grep stays plain `[]`.
- Deep `search` audited for the same two shapes; fixed or excluded-with-rationale.
- **Harness line item (the 0034-close agreed follow-up):** live integration tests write
  verifier artifacts to a persistent gitignored location
  (`eval_work/live_artifacts/<test>/<timestamp>/`, same outside-repo atomic writer)
  instead of `TemporaryDirectory` — three bucket-unanswerable re-runs were forced by
  discarded artifacts (0032 astropy, 0033-T14, 0034-AC5). This spec's own live AC
  consumes it.

## Acceptance Criteria (sketch — refine at review)

1. [unit] File-scope grep: the loop conversation carries
   `grep-scope-is-a-file: '<scope>'` (stable identifier), loop continues, non-terminal,
   not in the degrade report; the 0033 astropy shape as the fixture.
2. [unit] Nonexistent-scope grep: `grep-scope-not-found: '<scope>'` likewise; the 0034
   hallucinated-`repo` shape as the fixture.
3. [unit] Honest-empty preserved: a real-directory scope with zero matches returns
   plain `[]`, NO marker (byte-identical loop content to today); success-path grep
   byte-identical.
4. [unit] Tool surface unchanged: exact-five count test untouched; grep success shape
   (list[CodeSpan]) untouched; Deep `search` audited — same-fix or
   excluded-with-rationale, pinned either way.
5. [integration] A live run that greps a bad scope shows the marker in the persisted
   trajectory (model-visible), and the run reaches a terminal submit (non-terminal
   marker proven live). Skip-not-fail; model-behavior-contingent condition gets the
   0023 NOT-EXERCISED fallback.
6. [unit] Persistent artifacts: the live-test helper writes under
   `eval_work/live_artifacts/...` via the outside-repo atomic writer (unit-pinned on
   the path shape + writer reuse); the AC5-style tests updated to use it.
7. [doc] conventions.md: the "unsearchable-scope is a typed marker, never a silent
   empty" rule (the no-silent-coverage rule applied to tool scopes) + the
   persistent-artifacts harness rule.

## Out of Scope

- Any claim the markers improve localization (the eval set measures bucket effects).
- Engine (`RipgrepEngine`) changes — the gap lives in the wrappers; the engine's
  contract is untouched.
- Prompt/tool-description changes beyond the marker text itself.
- The eval set (next after this).

## Open Questions

1. Marker mechanism: wrapper returns a marker the loop stringifies naturally, vs a
   narrow typed exception the loop's existing per-call degrade catch converts to the
   0029 marker shape? (The latter reuses an existing path but stamps
   `tool-call-degraded:execution-error:` prefixes; the former needs the loop to not
   treat a non-list as spans — check `_spans_of` tolerance.) Decide at plan by reading
   `_answer_tool_call` + `_spans_of`.
2. Does `ls` on a nonexistent path have the same silent-`[]` gap (it returns `[]` for
   non-dirs too)? Audit while here; if yes it is the same one-change class (fix in this
   spec), if its semantics differ (ls of a file is arguably meaningful), exclude with
   rationale.
