---
id: "0035"
title: "grep-scope-markers"
status: reviewed
started_at_sha: 2d6843f
created: 2026-07-09
authors: [claude]
packages: []
related-specs: ["0034-reasoning-observability", "0033-scoped-grep-paths", "0029-loop"]
---

# Spec 0035 — grep-scope-markers (silent-`[]` affordance gap + file-scope delegation; SUT fix before the eval set)

## Why

The explorer's `grep` wrapper returns a bare `[]` for two failure shapes that are NOT
"searched and found nothing" — both land on the SAME branch (`if scope and not
scoped_path.is_dir(): return []`), and `confine_path` resolves NON-STRICT (verified: a
nonexistent in-repo path does not raise), so neither shape ever reaches the loop's
error handling. Two attributable live observations (visible thanks to the 0031–0034
instrument stack):

- **0033 astropy run (observed):** the model grepped
  `scope="astropy/modeling/separable.py"` — a FILE, and the gold-span file — twice;
  the wrapper returned bare `[]` both times; the run finished honest-empty.
- **0034-era run (observed):** a 6554-char reasoning turn produced
  `grep(scope="repo")` — a nonexistent directory; the wrapper returned bare `[]`; the
  model's next actions explored a different subsystem and the run finished
  honest-empty. (Stated observationally; no N=1 causal claim.)

Both shapes inflate the `empty` bucket with runs where the model searched an
unsearchable scope — the no-silent-coverage rule ("we never looked" must not read as
"we looked and found nothing") applied to tool scopes, and a systematic bucket
distorter the eval set must not baseline on. **The 0033 precedent is exact: a
tool-contract defect is fixed in its own small SUT spec BEFORE anything trusts the
distributions** — a measurement spec runs SUT-byte-frozen and structurally cannot
contain this change.

**DECIDED (the file-scope fork — DELEGATE, don't redirect):** post-0033 the ENGINE
natively searches a FILE scope for real (parent-dir cwd + filename path arg,
repo-relative results — built for the `symbols` degraded fallback). The wrapper's
`is_dir()` file-scope early-return is therefore an obsolete guard blocking a strictly
better outcome: under delegation, the 0033 astropy observation — the model grepping
the RIGHT file — returns REAL matches instead of a redirect. Delete the file-scope
guard; existing-file scopes flow to the engine (converging the explorer wrapper with
Deep's `search`, which already delegates). The marker applies ONLY to the
nonexistent-scope shape, where there is genuinely nothing to search.

**INVARIANT (causal claim withheld):** this spec claims only that (a) a nonexistent
scope becomes DISTINGUISHABLE from no-matches, and (b) a file scope returns real
engine results. It does NOT claim either improves localization — bucket effects are
the eval set's measurement (the think-experiment epistemics).

## Invariants

**INVARIANT (marker mechanism — OQ resolved in-spec):** the nonexistent-scope marker
is a WRAPPER-RETURNED VALUE (a marker string, or a `read_span`-style dict carrying it
— final shape at plan), NEVER a raised exception through the 0029 execution-error
catch. Two code-verified reasons: the exception route stamps a composite
`tool-call-degraded:execution-error: <Type>:` prefix that mislabels a navigation
mistake as an execution error AND its degrade path returns before `note_navigation`
runs — silently defeating loop detection on repeated bad-scope calls. The
marker-return route needs ZERO `explorer_loop.py` changes: `_spans_of` already
tolerates a non-list/non-path result (no citable spans), `session.add` stringifies it
model-visibly, and `note_navigation` still runs.

**INVARIANT (stable identifier):** the marker is a stable machine-readable identifier
per the cause-taxonomy rule — `grep-scope-not-found: '<scope>'` (exact string at plan)
— so trajectories and tests branch on the identifier, never prose. It is
model-visible, non-terminal, NOT a `ScoutUnavailable`, NOT counted in the degrade
report (the 0029 posture).

**INVARIANT (honest-empty preserved):** a searchable scope (real directory, or —
post-delegation — a real file) with zero matches still returns plain `[]`, no marker.
"Searched, nothing found" and "could not search" are the two states being separated;
the separation must not blur the honest-empty case. Success-path grep byte-identical.

**INVARIANT (tool surface unchanged):** exact-tool-count stays five; `grep`'s
signature and CodeSpan-list success shape untouched. The `confine_path` non-strict
resolve behavior (a nonexistent in-repo path passes confinement without raising) is
PINNED by a fixture, so a future strict/exists change cannot silently alter this
contract.

**DECIDED (Deep `search` — per-shape, the code-wins correction):** Deep does NOT have
the silent-`[]` gap. Its two shapes are asymmetric and each gets its own treatment:
(a) FILE scope — already engine-delegated since 0033, real results, NO defect: pinned
with a test as the behavior the explorer now converges to. (b) NONEXISTENT scope — an
UNCAUGHT `FileNotFoundError` from `subprocess.run(cwd=<nonexistent>)`, with no typed
catch in `host_tools.search` or `RlmBackend.run`: a hard-failure path violating the
graceful-degradation guardrail (worse than silent-`[]`, a distinct defect DISCOVERED
by this spec's review). Fix in this spec at guardrail altitude: a nonexistent scope
surfaces as a typed, RLM-visible tool error or a `DeepUnavailable`-mapped degrade —
never an uncaught crash; the mechanism (guard-in-wrapper vs typed raise) is decided at
plan after tracing dspy's tool-error handling.

**DECIDED (`ls` nonexistent-path — same fix class, folded in):** `ls` on a
NONEXISTENT path hits the identical mechanics (`confine_path` non-strict → `is_dir()`
False → bare `[]`) and gets the same marker (`ls-path-not-found: '<path>'`). `ls` on
an existing FILE stays an open question (OQ1 — arguably meaningful semantics), decided
at plan with rationale either way.

## What

- **grep:** delete the file-scope early-return (existing-file scopes delegate to the
  engine, repo_root already threaded); the nonexistent-scope branch returns the typed
  marker value.
- **ls:** nonexistent-path branch returns its typed marker; file-path semantics per
  OQ1.
- **Deep `search`:** pin the file-scope no-defect behavior; fix the nonexistent-scope
  uncaught-crash path to typed handling (mechanism at plan).
- The 0033/0034 observed shapes become regression fixtures: the astropy file-scope
  grep now returns REAL matches from `separable.py` (positive fixture); the
  hallucinated-`repo` scope produces its marker in the loop conversation; a
  valid-scope empty grep stays plain `[]`.
- Pin `confine_path`'s non-strict resolve with its own fixture.
- **Harness line item (explicitly fenced as NON-SUT; justification: THIS spec's AC6
  live run consumes it):** live integration tests write verifier artifacts to a
  persistent gitignored location (`eval_work/live_artifacts/<test>/<UTC
  ISO-8601-basic timestamp>/`, collision rule: timestamp + pid suffix; the same
  outside-repo `atomic_write_json`) instead of `TemporaryDirectory` — three
  bucket-unanswerable re-runs were forced by discarded artifacts. The existing
  integration tests' conflated fake-repo/out-dir tempdirs are separated in the
  migration (the writer's inside-repo refusal fires otherwise). The base path is NOT
  a `Settings` field (eval-knobs-disjoint convention, asserted). The eval-set spec
  remains able to claim SUT-byte-frozen against this spec's close SHA because this
  item touches only test/harness files.

## Acceptance Criteria (sketch — refine at plan)

1. [unit] File-scope grep DELEGATES: `grep(pattern, scope=<existing file>)` returns
   the engine's real matches (repo-relative, the 0033 astropy shape as the positive
   fixture — grepping `separable.py` for a term it contains returns spans); no marker,
   no `[]`-when-matches-exist.
2. [unit] Nonexistent-scope grep: the loop conversation carries
   `grep-scope-not-found: '<scope>'` (stable identifier; the 0034 hallucinated-`repo`
   fixture), loop continues, non-terminal, not in the degrade report,
   `note_navigation` still runs (repeated bad scopes trip loop detection — pinned).
3. [unit] Honest-empty preserved: a real-directory scope with zero matches AND a real
   file scope with zero matches both return plain `[]`, no marker; success paths
   byte-identical.
4. [unit] `ls` nonexistent-path marker (`ls-path-not-found`); `ls` file-path per OQ1
   decision, pinned either way. `confine_path` non-strict resolve pinned.
5. [unit] Deep `search` per-shape: file-scope real-results pinned (no defect);
   nonexistent-scope produces typed handling, never an uncaught `FileNotFoundError`
   (fixture drives the current crash RED first).
6. [integration] Live: a run that greps a bad scope shows the marker in the PERSISTED
   trajectory (written to `eval_work/live_artifacts/...`), and the run reaches a
   terminal submit (non-terminal proven live). Skip-not-fail; model-behavior-contingent
   condition gets the 0023 NOT-EXERCISED fallback.
7. [unit] Persistent-artifacts helper: writes under `eval_work/live_artifacts/` via
   `atomic_write_json` (path shape + writer reuse + repo/out-dir separation pinned);
   AC-style live tests migrated; no new `Settings` field (asserted).
8. [doc] conventions.md: the "unsearchable-scope is a typed marker, never a silent
   empty" rule + the file-scope-delegation convergence (explorer grep == Deep search
   == the one engine contract) + the persistent-artifacts harness rule.

## Out of Scope

- Any claim the markers or delegation improve localization (the eval set measures
  bucket effects).
- Engine (`RipgrepEngine`) changes — 0033's contract is complete; this spec only
  removes wrapper guards and adds wrapper markers.
- Prompt/tool-description changes beyond the marker text itself.
- The eval set (next after this).

## Open Questions

1. `ls` on an existing FILE: keep returning `[]` (arguably meaningful — "no children"),
   return a single file-level entry, or a marker? Decide at plan with rationale; the
   nonexistent-path half is already decided (marker, same class as grep).
2. Marker VALUE shape: bare string vs `{"error": "<identifier>"}` dict (read_span-style)
   — both loop-compatible (code-verified); pick at plan for the cleanest
   stringification in the conversation.
