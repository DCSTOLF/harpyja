---
spec: "0012"
title: "path-prefix"
reviewers: [codex, claude-p]
quorum: 1
round: 3
verdict: approve-with-comments
generated: 2026-06-29T00:00:00Z
---

# Cross-model review — 0012 (path-prefix) — Round 3 FINAL

> **Trajectory:** R1 — both changes-requested (algorithm ambiguity, model-flip scope). R2 —
> claude-p approve-with-comments, codex changes-requested (algorithm resolved to suffix-search,
> recovered split by shape, swebench_eval enumeration, Why example, AC5 wording all actioned).
> R3 — **both approve-with-comments; quorum met; status: reviewed.**

> **R1 actions acknowledged:** split/remove model-default flip into a follow-up spec.
> **R2 actions acknowledged:** suffix-search algorithm committed, `recovered` split by shape
> (`recovered_spanned`/`recovered_filelevel`), `swebench_eval.py` added to blast-radius
> enumeration, Why worked example corrected, AC5 phrasing fixed to delta + `indicative_only`.

---

## codex (gpt-5.5)

**Verdict:** approve-with-comments

Concerns:

- Recovery uses the repo file set/manifest but doesn't specify stale/unavailable-manifest
  behavior. `normalize.py` must not build or refresh artifacts; it must use the already-valid
  in-memory manifest from the run seam, or define a deterministic fallback that does not write
  into the target repo.
- Recovered file-level citations are explicitly un-verified, but the ACs do not assert that the
  confidence/notes path stays low-confidence via the existing `gate-skipped:no-line-range`
  behavior at the gate layer.
- AC5 names the committed baseline artifact path but not the NEW comparison artifact path or its
  required report fields precisely enough for reproducible operator output.

Suggestions:

- Add a unit/integration assertion that a recovered file-level citation never produces a
  verified/high-confidence gate pass and carries the `no-line-range` gate marker when it reaches
  the gate.
- Pin the recovery file universe to repo-relative regular files from the manifest/index layer,
  excluding derived artifacts and symlink escapes; make stale-manifest behavior explicit.
- Define the output path and minimal JSON keys for the N=12 delta artifact.

Guardrail violations: none

Convention violations: none

---

## claude-p (claude-sonnet)

**Verdict:** approve-with-comments

Concerns:

- **Unenumerated producer-side plumbing (convention violation).** Suffix matching needs the repo
  file set, but `normalize_spans_with_tally(raw, repo_root, *, max_citations, max_span_lines)`
  has no file-set input today, and `ScoutEngine.__init__` carries no manifest reference.
  Threading the file set (`wiring.build_scout_engine → ScoutEngine → normalize`) is a real
  producer-path shape-change that the spec's own blast-radius section omits — the What §2
  blast-radius enumerates the `recovered_*` counter wiring downstream but says nothing about the
  new file-set input that `normalize` and `ScoutEngine` require to suffix-match at all.
- **Wrong-but-UNIQUE recovery is the central correctness risk and is validated only by an
  underpowered run.** Uniqueness drops AMBIGUOUS suffixes but not a fabricated suffix that
  resolves to exactly one real-but-irrelevant file (e.g. a cited `utils/helpers.py` uniquely
  matching `tests/utils/helpers.py` when the intended file is `src/flask/helpers.py`). Such a
  recovered FILE-LEVEL citation skips gate read-back and propagates un-verified — strictly worse
  than the honest drop. AC5 (N=12, `indicative_only`, no threshold) is too underpowered to
  surface a leak rate; the load-bearing guard ships essentially unvalidated against its worst case.
- **Index-not-ready / manifest-absent path is unspecified.** The graceful-degradation rule (no
  file set → no recovery → fall back to spec-0011 drop) should be EXPLICIT, not inferred.

Suggestions:

- Enumerate how the repo file set reaches `normalize` (new `ScoutEngine` input loaded by
  `build_scout_engine`, or a passed manifest file list); pin the match-set to manifest-relative
  paths so match-set and `is_file` re-validation cannot disagree on gitignored/binary files.
- Promote OQ1 (manifest-key the leading segment to a known top-level dir) from deferred default
  to a recommended guard, OR at minimum make AC5 REPORT the `recovered_filelevel` set itself
  (the actual recovered paths) so an operator can eyeball wrong-but-unique recoveries — a count
  alone will not reveal a plausible-but-wrong recovery.
- Commit the baseline before AC5 can reference it: `specs/0012-path-prefix/baseline_q8rl_n12.json`
  exists on disk but is UNTRACKED (git ls-files empty); AC5's "records the delta against that
  committed baseline" is unsatisfiable until it is committed.
- Pin OQ2 to the manifest-list option (no extra walk); note the per-citation × per-k × files
  scan cost on the full 12-repo sweep (trivial at N=12).

Guardrail violations: none

Convention violations:

- **"Shared-contract shape change enumerates full blast radius producer→sink, each made
  shape-safe in same change."** What §2's blast-radius section enumerates the `recovered_*`
  counter wiring (normalize → ScoutTally → runner/swebench_eval → report) but omits the new
  file-set input that `normalize` and `ScoutEngine` must receive to perform suffix-matching at
  all. The producer-path change (`build_scout_engine → ScoutEngine → normalize`) is absent.
  (location: What §2 blast radius)

---

## Synthesis

### Remaining comments — ordered by severity

**1 — File-set plumbing: producer-path blast-radius is incomplete (both reviewers; one
convention violation)**

Both reviewers independently identify the same gap from different angles: the spec specifies
the downstream `recovered_*` counter wiring (normalize → ScoutTally → runner/swebench_eval →
report) but says nothing about how the repo file set gets INTO `normalize` in the first place.
`normalize_spans_with_tally` has no file-set parameter today; `ScoutEngine.__init__` has no
manifest reference. The producer-path shape-change (`wiring.build_scout_engine → ScoutEngine →
normalize`) is real and must be enumerated in What §2 alongside the counter wiring. The
manifest-absent graceful-degradation rule (no file set → no recovery → fall back to spec-0011
drop) must be stated explicitly, not inferred. This is the single convention violation in this
round.

**2 — Wrong-but-UNIQUE recovery is unvalidated at its worst case; surface recovered paths in
AC5**

Uniqueness-plus-minimum-length guards are necessary but not sufficient: a hallucinated suffix
that uniquely matches one real-but-irrelevant file passes all guards, skips gate read-back as a
file-level citation, and propagates un-verified. AC5 at N=12 with `indicative_only` and no
threshold cannot surface the leak rate. At minimum, AC5 should record and commit the actual
recovered paths (the `recovered_filelevel` set, not just its count) so an operator can inspect
wrong-but-unique cases. Separately, consider whether promoting OQ1 (manifest-key the leading
segment to a known top-level directory) from deferred default to a recommended guard is worth
the coupling cost — it would materially reduce the wrong-but-unique surface.

**3 — Recovered-file-level citations must carry the no-line-range gate marker (low-confidence
path explicit in ACs)**

The spec notes in AC3 that a recovered file-level citation skips gate read-back via
`gate-skipped:no-line-range`. But no AC asserts that this path is enforced — a recovered
file-level citation must never yield a verified/high-confidence gate pass. Add an explicit
assertion (unit or integration) that a recovered file-level citation carries the
`gate-skipped:no-line-range` marker and does not produce a verified result at the gate layer.
This is distinct from concern 2: concern 2 is about whether recovery picked the right file;
concern 3 is about whether the gate correctly marks its output as un-verified regardless.

**4 — AC5: define the NEW delta artifact path and its minimal required JSON keys**

AC5 names the committed baseline artifact (`specs/0012-path-prefix/baseline_q8rl_n12.json`) but
not the new comparison artifact's path or the minimal set of JSON keys required for the delta to
be reproducible. Name the output path (e.g.
`specs/0012-path-prefix/run_q8rl_recovery_n12.json`) and enumerate the required top-level
fields: at minimum `scout_empty_count`, `gate_ran_count`, `fc_spanned_count`,
`fc_filelevel_count`, `fc_dropped_count`, `recovered_spanned_count`,
`recovered_filelevel_count`, `recovered_filelevel_paths`, `indicative_only: true`, and
`baseline_ref`.

**5 — Commit the untracked baseline artifact before AC5 is actionable**

`specs/0012-path-prefix/baseline_q8rl_n12.json` exists on disk but is untracked (not in git).
AC5's "records the delta against that committed baseline" is unsatisfiable until the file is
committed. Commit the baseline artifact as part of the spec revision or as the first step of
`/spec:plan`.

**6 — Pin OQ2 to manifest-list; note scan cost**

OQ2 (suffix-match index) should be pinned to the manifest-list option (no extra filesystem
walk) for the current N=12 scope, with a note that a dedicated suffix index is only worth
revisiting if per-citation × per-k × files scan is a hotspot on a large repo sweep. This
removes the open question as an implementation-time ambiguity.

---

### Convention violation (single)

- **Blast-radius enumeration incomplete (claude-p; corroborated by codex).** What §2 enumerates
  the counter-wiring consumer path but omits the producer-path shape-change: the file-set input
  that `normalize_spans_with_tally` and `ScoutEngine` must gain. Per the "shared-contract shape
  change enumerates full blast radius producer→sink" convention, the producer end
  (`build_scout_engine → ScoutEngine → normalize`) must appear in What §2 alongside the
  downstream wiring. (location: What §2 blast radius)

---

### Comments to fold into spec / resolve during /spec:plan

1. **Enumerate the file-set producer path in What §2.** Add `build_scout_engine → ScoutEngine
   (new manifest input) → normalize_spans_with_tally (new file-set param)` to the blast-radius
   enumeration, made shape-safe in the same change. State the manifest-absent fallback rule
   explicitly: no manifest → no recovery → drop (spec-0011 behavior).

2. **Surface the recovered_filelevel PATH LIST in AC5**, not just the count. This is the primary
   guard against wrong-but-unique recoveries propagating un-noticed at N=12. Optionally note
   whether OQ1's manifest-keyed leading-segment guard is being adopted or explicitly deferred.

3. **Add an AC assertion that recovered-file-level citations carry gate-skipped:no-line-range**
   and never produce a verified gate result. One sentence added to AC3 plus one unit test
   assertion is sufficient.

4. **Name the new delta artifact path and pin its minimal JSON keys in AC5.**

5. **Commit `specs/0012-path-prefix/baseline_q8rl_n12.json`** (currently untracked) before or
   as the first step of `/spec:plan`.

6. **Resolve OQ2 inline:** pin to manifest-list (no extra walk); close the open question in the
   spec text rather than leaving it to plan-time.

**Action:** Fold comments 1–6 into the spec text. Comments 1 and 2 are load-bearing for
implementation correctness. Comment 5 (commit baseline) must happen before AC5 is measurable.
Comments 3, 4, and 6 are each one to two sentences. Once folded, hand to `/spec:plan`.
