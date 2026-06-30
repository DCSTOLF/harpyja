---
id: "0012"
title: "path-prefix"
status: closed
created: 2026-06-29
authors: [claude]
packages: [harpyja/scout, harpyja/eval]
related-specs: ["0010", "0011"]
---

# Spec 0012 — path-prefix

## Why

The N=12 point-subset re-measurement (spec 0010/0011 follow-up, run this session) showed
that with a Q8-class FastContext Scout model the pipeline goes from dead to alive — Scout
emits real `<final_answer>` blocks, the gate fires 5/12, escalation runs 2/12. But on
**7/12** cases Scout still ends up `scout-empty` — **not** because the model found nothing,
but because it emits **out-of-repo absolute paths** fabricated from the `owner/name` repo
slug. Spec 0011's `normalize_spans_with_tally` correctly **drops** these as out-of-repo refs
(10 dropped in the N=12 auto run), so the case degrades to Tier-0. The *meaningful tail* of
these paths is often the real in-repo path — the model knows the file, it just prefixes a
hallucinated root.

Worked example (from the live rl trajectory): Scout cites
`/pallets/flask/src/flask/blueprints.py:117-621`. No such absolute path exists, so spec 0011
drops it. But the **suffix** `src/flask/blueprints.py` is a real file in the flask worktree —
recovering it turns a dropped citation into a usable one. (Contrast: a cite of
`/pallets/flask/src/__init__.py` has suffix `src/__init__.py`, which does **not** exist in
flask — the real file is `src/flask/__init__.py` — so recovery correctly **fails** and the
ref is dropped. Recovery only ever keeps a path that resolves to a real, indexed file.)

This spec is the **deterministic, model-independent** fix: recover such citations by matching
the longest **unique, specific** path suffix against the repo's own indexed file set — only
ever mapping to a file that actually exists. It does **not** change which Scout model ships;
adopting a Q8 model as the default is a separate follow-up (see Out of scope), pending the
in-flight rl-vs-sft comparison and the repo's variance-gated recommend→flip discipline. The
recovery is what makes that future model swap pay off, but the two are decoupled.

## What

1. **Scout path-suffix recovery** (`harpyja/scout/normalize.py`). When a parsed Scout
   citation path does **not** resolve to a real file inside the repo root, before dropping it
   attempt **bounded suffix recovery** against the repo's **indexed manifest file set** — the
   repo-relative regular files the indexer already enumerated (no GitHub slug / external
   repo-identity input; `normalize` **receives** the file set, it never builds or refreshes an
   artifact and never writes into the target repo). The algorithm is fixed and deterministic
   (review-resolved: suffix-search, **not** an anchored slug-strip):
   - Let `segs` be the cited path's segments. For `k` from `len(segs)` down to
     `MIN_TAIL_SEGMENTS` (= 2): let `tail` = the last `k` segments; collect the manifest files
     whose repo-relative path **equals** `tail` or ends with `"/" + tail` (segment-aligned
     suffix match).
   - **Exactly one** match at the longest such `k` → recover to that repo-relative path.
     **More than one** match (ambiguous) → **drop** (do not fall back to a shorter, even more
     ambiguous tail). **Zero** matches → continue to `k-1`.
   - **Manifest-keyed leading-segment guard** (adopted from OQ1): the recovered path's
     **leading** segment must be a known top-level entry of the manifest; a suffix whose head
     is not a real top-level dir/file is **dropped**. This narrows the wrong-but-unique
     surface beyond bare segment-count.
   - No `k ≥ MIN_TAIL_SEGMENTS` yields a unique, manifest-keyed match → **drop**.
     `MIN_TAIL_SEGMENTS = 2` is the specificity floor (a bare basename like `__init__.py` is
     never recovered).
   - **Graceful degradation:** if the file set is **absent or empty** (index not ready),
     recovery is skipped entirely — every out-of-repo ref falls back to the spec-0011 drop.
     Recovery only ever adds keeps; it never changes the no-file-set behavior.
   - A recovered span is re-validated by the existing repo-confine + `is_file` (+ line-range
     clamp for spanned) before it is kept — recovery composes with, never bypasses, spec
     0011's validation, and the match-set is **manifest-relative** so match and re-validation
     cannot disagree on gitignored/derived files.

2. **`recovered` observability, split by shape** (additive). A recovered citation is still
   classified by shape (spanned vs file-level); `recovered` is an **orthogonal** quality,
   tracked **by shape** because the two have different trust: a recovered **file-level**
   citation skips the gate read-back (`gate-skipped:no-line-range`, spec 0011) and so
   propagates **un-verified**, whereas a recovered **spanned** citation can still be
   gate-verified. **Blast radius by category** (`grep -rn fc_citation`; producer→sink, each
   shape-safe in the same change):
   - **Producer file-set seam (the new plumbing):** `wiring.build_scout_engine` loads the
     repo's manifest file list and passes it to `ScoutEngine`; `ScoutEngine` hands it to
     `normalize_spans_with_tally` via a new file-set parameter. Engines that have no manifest
     (unit fakes, index-not-ready) pass an empty set → no recovery (per §1 degrade).
   - **Tally:** `ScoutTally` gains `recovered_spanned` + `recovered_filelevel`; carried on the
     `ScoutEngine.last_tally` side-channel (orchestrator `list[CodeSpan]` seam unchanged).
   - **Aggregation (both readers):** `eval/runner.py` **and** `eval/swebench_eval.py` (the
     per-case driver that pools its own `LocateStack` tallies for AC5) read the counts.
   - **Report:** `fc_citation_recovered_spanned_count` + `fc_citation_recovered_filelevel_count`
     appended **last-with-default** in the one `_AGGREGATE_DEFAULTS` source; `SCHEMA_VERSION`
     bumped `0011/1 → 0012/1`; validator accepts both shapes.

3. **Operator re-measurement** of the committed N=12 point subset under a Q8 Scout model
   **override** (no production default changed), writing the new artifact
   `specs/0012-path-prefix/run_q8rl_recovery_n12.json` and recording the recovery delta vs the
   committed Q8-rl baseline.

## Acceptance criteria

1. `[unit]` Given a Scout citation whose path does **not** resolve in the repo but whose
   longest `≥ 2`-segment suffix matches **exactly one** manifest file **and** whose leading
   segment is a known top-level manifest entry, `normalize_spans_with_tally` **recovers** it
   to that file's repo-relative path (kept, not dropped) and increments the matching
   `recovered_{spanned,filelevel}` counter; its shape bucket is unchanged.
2. `[unit]` Recovery **degrades safely to the spec-0011 drop** when there is nothing to
   recover against: a cited path with **no** unique, manifest-keyed `≥ 2`-segment suffix, **or
   an absent/empty file set** (index not ready), is **dropped** — out-of-repo / nonexistent
   refs never propagate, and `dropped` counts only the truly-unrecoverable.
3. `[unit]` Recovery is **bounded and guarded against wrong-but-existing**: (a) only a
   trailing path **suffix** is matched — a non-suffix/interior overlap is never rewritten;
   (b) a suffix matching **more than one** manifest file is **dropped**; (c) a suffix below
   `MIN_TAIL_SEGMENTS = 2` is **dropped**; (d) a suffix whose **leading segment is not a known
   top-level manifest entry** is **dropped**; (e) a kept span is re-validated by repo-confine
   + `is_file` (+ line-range clamp for spanned). **(f) Honesty floor:** a recovered
   **file-level** citation carries the existing `gate-skipped:no-line-range` marker, is **never
   read-back-verified**, and **never produces a high-confidence/verified gate result** — a
   recovered keep can read no more confidently than a non-recovered one. The guard is
   load-bearing because such a citation skips read-back, so a wrong-but-existing recovery
   would propagate un-verified — strictly worse than the honest drop it replaces.
4. `[unit]` The wiring is shape-safe end to end with no schema drift: the producer seam
   (`build_scout_engine` → `ScoutEngine` → `normalize_spans_with_tally`) threads the manifest
   file set; `ScoutTally` carries `recovered_spanned` + `recovered_filelevel`;
   `fc_citation_recovered_spanned_count` + `fc_citation_recovered_filelevel_count` are appended
   **last-with-default** in `_AGGREGATE_DEFAULTS`; `SCHEMA_VERSION` is `0012/1`;
   `validate_report` accepts both a legacy `0011/1` block (fields absent, defaulted) and a
   `0012/1` block; and **both** `eval/runner.py` **and** `eval/swebench_eval.py` aggregate the
   counts from the per-case `last_tally` side-channel (a test asserts the swebench driver
   carries `recovered_*`, not just the single-repo runner).
5. `[integration]` (operator-run; `@pytest.mark.integration`, skip-not-fail when the live
   model/endpoint is absent) Re-run the **committed N=12 point subset** — the point-classified
   cases in flask/requests/pylint/sphinx derived from
   `harpyja/eval/fixtures/swebench_verified.raw.jsonl` — with the Scout model **overridden**
   to a Q8 FastContext model via `dataclasses.replace(Settings(), scout_model=...)` (the
   `swebench_eval` run seam; **no production default changed**) and suffix recovery enabled.
   Write **`specs/0012-path-prefix/run_q8rl_recovery_n12.json`** with at least:
   `scout_empty_count`, `gate_ran_count`, `fc_{spanned,filelevel,dropped}_count`,
   `recovered_{spanned,filelevel}_count`, **`recovered_filelevel_paths`** (the actual recovered
   path list, so a wrong-but-unique recovery is inspectable — a count alone can't reveal a
   plausible-but-wrong keep), `indicative_only: true`, and `baseline_ref:
   "specs/0012-path-prefix/baseline_q8rl_n12.json"`. **Pass = the artifact records the run's
   delta against that committed baseline** (`scout-empty 7/12`, `gate-fire 5/12`,
   `fc 18/0/10`, `span_hit 0.167`, `escalation 2/12`) and self-flags `indicative_only`
   (N < `n_floor`). There is **no** strict-inequality gate — no production default is flipped
   here, so the criterion is an honest recorded delta, not a pass/fail threshold on a single
   non-deterministic run.

## Out of scope

- **Flipping the `scout_model` default to a Q8 model** — deferred to a follow-up spec,
  pending the in-flight rl-vs-sft N=12 comparison. That follow-up must apply the repo's
  variance-gated recommend→flip discipline (`recommend.py`, "never a default flip on noise"),
  state how a **missing** default model surfaces (typed `scout-degraded` → Tier-0 floor so
  the out-of-box default never points everyone at a non-existent model), and gate the flip on
  the model being CI/operator-provisionable. THIS spec only measures recovery under an
  operator-supplied model override.
- The full 12-repo sweep + OQ2 `verify_threshold`/`verify_top_n` tuning and any threshold flip.
- The gate **false-escalation** of a correct Scout answer (`requests-1766`: gate rejected a
  correct `auth.py` citation and escalated to a Deep miss) — a separate gate-quality lead.
- Filing/curating the two upstream FastContext bug reports drafted this session.
- Changes to the parser grammar (spec 0011 seam a), Deep, or the classifier; Wave-2.1
  substring/fuzzy.

## Open questions

1. **Suffix-match cost at scale** — the recovery resolves against the already-built manifest
   file list (no extra filesystem walk; review-resolved). The per-citation × per-`k` × files
   scan is trivial at N=12 but is `O(citations · segments · |manifest|)` on a large repo; if
   the full 12-repo sweep shows it as a hotspot, build a one-time suffix index per repo. Not a
   behavior change — defer until measured.
