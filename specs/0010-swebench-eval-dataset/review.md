# Review — Spec 0010 SWE-bench Verified eval dataset (round 1)

**Agents:** codex (`gpt-5.5`), claude-p · **Quorum:** 1 of 2 · **Result:** NOT met.
Both verdicts **changes-requested**. Spec stays `draft`.

## Recommendation

**changes-requested** — two blockers, both convergent across the two models; the
first is a real hole in the central (OQ2) deliverable, the second a concrete
no-false-capability violation verifiable against the code. The rest are wording +
extra-AC refinements that fold in cleanly.

## Blockers (both agents)

### B1 — D-class relabels *scoping*, not *routing* (the OQ2 hole)

The production gate only fires when `classify_query(query)` returns `point`, and
that function keys on **lexical triggers in the query text** (issue prose) — it has
no knowledge of patch shape. `runner.run_case` drives the real `locate()` and uses
`case.classification` only for **metric scoping** + the extra independent Scout call,
**not** for routing. So a patch-shape-`point` case whose prose trips a broad trigger
routes straight to Deep, the production gate never runs, yet the harness still counts
it in the point subset. `gate_catch_rate` / `gate_false_escalation` — the entire OQ2
signal — would be computed over a population production never gated, and sweeping
`verify_threshold`/`verify_top_n` over a set where the gate mostly never fires
produces metrics that are partly fiction and partly flat. **This is exactly the
"uncalibratable" failure D-class was written to prevent, and the described mechanism
does not prevent it.**

The fix forces a decision the spec is currently dodging — **measure** vs **override**:
- **(a) Override routing** via the existing `LocateStack.classifier` seam (inject a
  classifier returning `case.classification`). The gate then fires on the point
  subset and threshold sweeps have effect — but we are calibrating on an *artificial*
  routing the real text classifier would never produce. Must be recorded as a
  deliberate **evaluation intervention**, with production-classifier agreement
  reported separately.
- **(b) Measure the production classifier**: assert `classify_query(query) ==`
  patch-shape label at convert; flag/exclude mismatches loudly with a count. Pure
  observation — but may reveal SWE-bench prose is a *poor* OQ2 instrument (few cases
  gate), i.e. "SWE-bench can't calibrate OQ2" is a possible honest outcome.

### B2 — `base_commit` silently dropped (no-false-capability)

`EvalCase` is a frozen 5-field dataclass and `_parse_case` constructs it from only
those keys; extra keys like `base_commit` are **dropped**, not preserved. AC2's
"round-trips through `load_dataset` … `base_commit` preserved" is internally
contradictory. **Fix (mechanism is already correct):** `provision` reads
`base_commit` from the **raw JSONL directly** (`_read_jsonl`, never via
`load_dataset`); reword AC2 to test that the raw dict carries `base_commit` and that
`load_dataset` *ignores* it without `DatasetError`. (Alternative: add an additive
`base_commit` field to `EvalCase` — but that is an eval-package change to call out.)

## Non-blocking refinements (fold into the revision)

- **R1 (codex):** add an AC covering the real `python -m harpyja.eval.swebench_eval
  run|sweep` CLI + merged root `Makefile` targets, incl. behavior when the resolved
  fixture is absent — it is a named reconciliation seam and is currently untested.
- **R2 (codex):** make protocol identity + exclusions **durable report fields**, not
  just prose: `standalone-localization`, no harness/patch/test-exec, `new_file_only`
  excluded count, malformed-skipped count, contamination caveat.
- **R3 (claude-p):** `run_case` hardcodes `mode="auto"` (line 128); `run_dataset`'s
  `mode` only reaches metadata. AC6's `mode=fast` needs a **new seam** (thread `mode`
  into `run_case`) — it is not already available as the spec implies.
- **R4 (claude-p):** soften the "first evidence-backed OQ2 recommendation" framing
  against the contamination caveat — lean on **sweep-deltas / fast-vs-auto deltas**;
  consider a held-out non-public mini-set to sanity-check generalization.
- **R5 (claude-p):** context-line inflation biases span-hit **upward** (overlap is
  easier) — D-protocol should state the tolerance magnitude, not frame it as neutral.
- **R6 (both):** justify why pure-insertion-in-existing-file is anchored-and-scored
  while all-new-file is excluded — both lack a true pre-image span; the boundary
  reads arbitrary. Define the zero-length-insertion anchor as a concrete span.
- **R7 (claude-p):** add a **runtime budget / per-case timeout / sample cap** to AC8
  and document expected wall-clock (0009-6a: 5 live cases = 634s; N≥30 × grid × K is
  plausibly many hours).
- **R8 (claude-p):** add one sentence scoping `convert`/`provision` **out** of the
  runtime air-gap guarantee (dev-time tools, never on the MCP server path).
- **R9 (claude-p):** under B1's divergence, the `gate_triggered` event field
  (harness's separate Scout call) is misleading vs whether the production gate
  actually ran — reconcile its meaning.

## What both agents affirmed

Instrument-vs-dataset framing is sound; B1-invariant discipline (recommend-only, no
`Settings` flip, `dataclasses.replace`-only) is preserved; the per-case-repo driver
gap is correctly identified and reusing the unchanged `metrics`/`report`/`recommend`
layers is the right move; network-posture staging (networked `convert`/`provision`
vs air-gapped `run` with a zero-non-loopback assertion) handles the air-gap
guardrail well (hence `guardrail_violations: []` from both).

## Convention flags

- **no-false-capability** (memory) — B2, `base_commit` accepted-then-dropped.
- **single-source-of-truth routing** (conventions.md) — B1, patch-shape label is a
  parallel classification authority that diverges from the `classify_query`/matrix
  routing the runner actually uses.

---

# Review — round 2 (post-revision)

**Agents:** codex (`gpt-5.5`), claude-p · **Both: `approve-with-comments`** ·
**Quorum 1 of 2: MET.** Status → `reviewed`.

Both models **verified the blockers closed against the code**, not just the prose:
- **B1 closed.** `LocateStack.classifier` (runner.py:42) is forwarded verbatim into
  the production `locate(...)` (runner.py:82), so injecting a classifier returning
  `case.classification` overrides the *input* to the unchanged routing/matrix/gate —
  the gate genuinely fires on the point subset and the threshold sweep bites. The
  round-1 single-source-of-truth-routing flag **dissolves**: patch-shape is injected
  *as* the `Classifier` through the sanctioned seam, so `classify_query`/`plan_ladder`
  stays the sole routing path; only its input is swapped, loudly recorded.
- **B2 closed.** `_parse_case` (dataset.py:88) builds the frozen 5-field `EvalCase`
  from only the required keys; an extra `base_commit` is ignored with no
  `DatasetError`. AC2 is now mechanically accurate.

**Four non-blocking comments — all folded into the spec before `reviewed`:**
1. Report schema described "unchanged" while AC8 adds fields → reworded **additively
   extended** (appended-last-with-defaults, `SCHEMA_VERSION` bumped; both report
   families validate).
2. `gate_triggered` is harness-observed → added a distinct SUT-observed
   **`production_gate_ran`** field (from `result.tiers_run`/`notes`); AC5 asserts gate
   firing from that, and captures the production label **before** installing the
   override (codex's accidental-self-observation guard).
3. `mode=fast` "no gate" was inaccurate → corrected to **Scout-terminal, gate
   informational** (Wave-5 `gate-low-confidence`, never escalates).
4. OQ2 recommendation unguarded by agreement → added an **agreement-rate floor**:
   below it, the result is flagged **low-confidence (deltas-only)**, never a
   calibration to flip a default on.
5. Plus **dataset provenance** pinning (codex): HF id/split/revision + raw-fixture
   hash + sample ids as durable report fields (AC8) for reproducibility.

Residual (carried to plan/changelog, non-blocking): the override remains an
evaluation **intervention**, not pure production observation — every OQ2 surface
cites it + the agreement rate.
