---
spec: "0012"
closed: 2026-06-29
---

# Changelog — 0012 path-prefix

## What shipped vs spec

Spec 0011 made Scout robust on real SWE-bench queries, and the N=12 Q8 re-measurement
(0010/0011 follow-up) showed the pipeline going from dead to alive — but **7/12** cases
still ended `scout-empty`, **not** because the model found nothing but because it emits
**out-of-repo absolute paths** fabricated from the repo slug (e.g.
`/pallets/flask/src/flask/blueprints.py`), which spec 0011 correctly **drops** as
out-of-repo (10 dropped in the N=12 auto run). The *meaningful tail* of those paths is
usually the real in-repo file. This spec is the deterministic, model-independent fix:
recover such citations by their longest **unique, specific** path suffix against the
repo's own indexed file set — only ever mapping to a file that actually exists. All 14
tasks complete (T1–T14); recovery **composes with, never bypasses**, 0011's validation,
and **no production Scout model default was changed**.

- **Scout path-suffix RECOVERY (`harpyja/scout/normalize.py`).** When a parsed citation
  does not resolve to a real in-repo file, before dropping it (the 0011 behavior)
  `_recover_suffix(cited_path, file_set, top_level)` matches the longest unique
  `≥ MIN_TAIL_SEGMENTS (=2)`-segment path suffix against the repo's indexed manifest
  file set — recovering a hallucinated out-of-repo absolute path
  (`/pallets/flask/src/flask/blueprints.py` → `src/flask/blueprints.py`). Three guards
  against wrong-but-existing: **exactly-one** match at the longest `k` required
  (ambiguous → drop, never a silent pick and never a fall-back to a shorter, less
  specific tail), the **MIN_TAIL_SEGMENTS=2** specificity floor (a bare basename like
  `__init__.py` is never recovered), and a **manifest-keyed leading-segment guard** (the
  matched tail's *head* must be a known top-level manifest entry, so a fabricated
  mid-tree suffix is rejected). A recovered path re-enters the normal repo-confine +
  `is_file` (+ line-range clamp for spanned) validation — recovery never skips 0011's
  checks. Manifest **absent/empty ⇒ no recovery** (graceful degrade to the 0011 drop).

- **AC3(f) honesty floor (proven end-to-end).** A recovered **file-level** citation stays
  `is_file_level` (`None` lines, no fabricated range), so it inherits spec 0011's
  `gate-skipped:no-line-range` floor and never reads as a verified / high-confidence pass
  — a recovered keep reads no more confidently than a non-recovered one. The guard is
  load-bearing because a file-level citation skips read-back, so a wrong-but-existing
  recovery would propagate **un-verified** — strictly worse than the honest drop it
  replaces. Pinned in `orchestrator/test_locate.py` (gate path) +
  `scout/test_scout_normalize.py` (no fabricated range).

- **Producer→sink blast radius, each shape-safe in the same change.**
  - `normalize_spans_with_tally` return widened **2-tuple → 4-tuple**
    `(spans, dropped, recovered_spanned, recovered_filelevel)` + a non-breaking
    `recovered_paths_out` out-param carrying the recovered **file-level** paths (chosen
    over a 5-tuple to avoid re-churning the just-updated 4-tuple callers — a mild
    out-param smell, noted). `normalize_spans` (legacy spans-only view) gains a
    `file_set` kwarg and unpacks-and-discards the new ints.
  - `ScoutTally` gained `recovered_spanned` / `recovered_filelevel` /
    `recovered_filelevel_paths`; `ScoutEngine(file_set=…)` threads the set into
    `normalize_spans_with_tally` and fills the tally on `last_tally`.
  - `build_scout_engine` loads the set via `read_manifest(art_dir)` →
    `frozenset(e.path …)`; manifest absent/empty ⇒ empty set ⇒ no recovery.
  - Report `SCHEMA_VERSION 0011/1 → 0012/1` with two additive last-with-default fields
    `fc_citation_recovered_{spanned,filelevel}_count` in the one `_AGGREGATE_DEFAULTS`
    source (both shapes validate).
  - **BOTH** `eval/runner.py::aggregate_outcomes` **and** `eval/swebench_eval.py`
    aggregate the new counts (the sibling-driver enumeration a reviewer flagged).

## Deviations

- **AC5 run was `mode=fast`, not `auto`.** On the dev host (16 GB) `auto` OOMs (jetsam,
  swap 18/19.5 GB) co-loading the 5 GB Q8 Scout + Deep + Deno/Pyodide, **and** Deep
  crashes via a dspy `AdapterParseError` on the qwen model's malformed JSON (sphinx-9698).
  Recovery is Scout-side, so `fast` measures `scout_empty` / `fc_*` / `recovered_*` in
  full and they are comparable to the auto baseline; only the auto-only gate/escalation
  counts are excluded from the delta. The committed integration test still runs `auto`
  (for a beefier host).
- **`recovered_paths_out` out-param** chosen deliberately over a 5-tuple return to avoid
  re-churning the just-updated 4-tuple callers — recorded as a mild, intentional smell.
- **`scout_model` Q8 default flip DEFERRED** to a follow-up spec (out of scope), pending
  the rl-vs-sft comparison + the variance-gated recommend→flip discipline.

## Verification evidence

- **Unit:** 678 passed, ruff clean.
- **Integration:** 5 passed / 1 skipped (the AC5 operator test, env-gated; runs `auto`).
- **AC5 LIVE** (committed `run_q8rl_recovery_n12.json`, `mode=fast`, Q8 fastcontext-4b-rl,
  recovery ON vs the committed `baseline_q8rl_n12.json`): **scout_empty 7 → 4 (3 of 7
  dead cases RESCUED)**, **dropped 10 → 0**, **recovered_spanned = 10**,
  **recovered_filelevel = 0**. Every recovery was **SPANNED** — the model emitted the
  out-of-repo paths *with* line numbers — so `recovered_filelevel_paths` is honestly
  empty: the riskiest un-gated file-level recovery category did not occur in this run.
  `N=12 < n_floor` ⇒ self-flagged `indicative_only`; an honest recorded delta, no
  strict-inequality gate (no production default flipped).

## Files touched

- `harpyja/scout/normalize.py` — `MIN_TAIL_SEGMENTS`, `_recover_suffix`, `file_set` +
  `recovered_paths_out` params, 4-tuple return, recover-before-drop branch.
- `harpyja/scout/engine.py` — `ScoutTally.recovered_*` + `recovered_filelevel_paths`;
  `ScoutEngine(file_set=…)` threading into `last_tally`.
- `harpyja/scout/wiring.py` — `read_manifest(art_dir)` → `frozenset(e.path)` →
  `ScoutEngine(file_set=…)`.
- `harpyja/eval/report.py` — `SCHEMA_VERSION = "0012/1"` + two additive recovered
  aggregate fields/defaults.
- `harpyja/eval/runner.py` — `aggregate_outcomes` sums `recovered_*`.
- `harpyja/eval/swebench_eval.py` — per-case driver carries `recovered_*`.
- `specs/0012-path-prefix/run_q8rl_recovery_n12.json` — the AC5 live artifact.
- Tests: `scout/test_scout_normalize.py`, `scout/test_scout.py`,
  `scout/test_scout_wiring.py`, `orchestrator/test_locate.py`, `eval/test_report.py`,
  `eval/test_runner.py`, `eval/test_swebench_runner.py`,
  `eval/test_swebench_integration.py`.

## ADR proposed for history.md

2026-06-29 — Scout path-suffix recovery — rescue an out-of-repo hallucinated citation by
its unique, manifest-keyed in-repo suffix, composing with (never bypassing) the 0011
drop + honesty floor (prepended to `.speccraft/history.md`).

## Conventions proposed

- New: **recovery-only-to-an-existing-unique-manifest-path.** When a model fabricates a
  leading root onto an otherwise-real path, recover by the longest **unique** `≥2`-segment
  suffix that matches the indexed manifest set, guarded by a manifest-keyed
  leading-segment anchor; ambiguous / below-floor / no-anchor → honest drop, never a
  guessed rewrite. Empty manifest ⇒ no recovery (graceful degrade).
- New: **a recovery/rewrite composes with, never bypasses, prior validation** — a
  recovered path re-enters the same repo-confine + `is_file` (+ clamp) gates, and a
  recovered keep inherits the same downstream honesty floor (`gate-skipped:no-line-range`)
  as a non-recovered one, so it can never read more confidently.
- New (narrow): prefer a **non-breaking out-param** over widening an already-churned
  return tuple past ~4 elements when the extra payload is needed by only one caller —
  recorded as a bounded, intentional smell, not a default.

## Architecture updates

- Layer-5 `harpyja/scout/`: the `normalize.py` recover-before-drop step
  (`_recover_suffix`, `MIN_TAIL_SEGMENTS`), the `file_set` thread
  (`build_scout_engine` → `ScoutEngine` → `normalize_spans_with_tally`), and the
  `ScoutTally.recovered_*` / `recovered_filelevel_paths` side-channel additions.
- Layer-9 `harpyja/eval/`: `SCHEMA_VERSION 0012/1` + the two
  `fc_citation_recovered_{spanned,filelevel}_count` aggregate fields, summed in **both**
  `runner.py` and `swebench_eval.py`.

## Open leads (carried forward)

1. **Q8 `scout_model` default flip** (deferred follow-up; rl favored 5/12 vs 2/12
   gate-fire, though sft edges accuracy 0.25 vs 0.167) — must apply the variance-gated
   recommend→flip discipline + a missing-model degrade story (typed `scout-degraded` →
   Tier-0 floor).
2. **Gate false-escalation of a correct Scout answer** (requests-1766: the gate rejected
   a correct `auth.py` citation and escalated to a Deep miss) — a gate-quality lead.
3. **Deep `AdapterParseError` robustness gap** — Deep should map a malformed dspy/model
   response to a typed `DeepUnavailable` degrade (like Scout's `backend-error`), not
   crash the run.
4. **Two upstream FastContext bug reports** drafted this session (`format_citations`
   crash on string citations; recommended-Q4-model quality).
5. Still open from Wave 2: **Wave-2.1 substring/fuzzy matching**.
</content>
</invoke>
