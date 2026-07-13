---
spec: "0045"
closed: 2026-07-13
---

# Changelog — 0045 refinement

## What shipped vs spec

- **Verdict: `TRADES_DIRECTIONS`** (frozen six-member total order, `decide_refinement_outcome`).
  The refined **require-corroboration** confidence gate FIXED the too-loose direction
  (silence→wrong-confidence 5 → 1) but REOPENED the too-tight one (found-but-unsubmitted
  1 → 8). Firing collapsed to 3/33 (0044 ~15/33); aggregate bucket net −1 (0044 +2,
  head-to-head Δ −3). Per model: 4b +2, 14b −1, 8b −2. The four-sided frozen predicate
  caught the trade a two-sided net would have sold as "s→wc fixed."
- **Decision (operator-directed): the require-corroboration operating point is REJECTED
  and the refined gate is REVERTED/RETIRED.** 0044's conditioned gate (net +2, fu 6 → 1)
  remains the best operating point to date. The next lever is chosen mechanically from this
  run's four-sided ledger: model-conditional corroboration (8b's weak singletons are the
  wrong-submission source; 14b was already zero-regression and should not have been
  tightened) OR decoupling "submit — you found it" from "this is confidently right." Both
  are new specs, never re-levered post-hoc on this data.
- **Infrastructure that SHIPS and is correct independent of the rejected gate:**
  1. `silence→wrong-confidence` is now a first-class counted cost class in every artifact —
     schema bump `VERIFIER_SCHEMA_VERSION 0044/1 → 0045/1` (dual-seam, 5th application),
     PLUS a **record-only unfired-s→wc cross-check** that caught a de-attribution (1 cell,
     `qwen3:14b`) the fired-conditioned metric would have hidden.
  2. The trajectory signals (grep-inside-symbol containment, convergent evidence) MOVED to
     a gold-blind `scout/confidence_signals.py`, imported back into eval BY IDENTITY (one
     definition); the parser `_parse_tool_content` relocated there and re-exported from
     `submission_gap`. `classify_confidence_null` (gold-needing) STAYS eval-side.
  3. The four-sided frozen predicate (conversions / regressions / s→wc / fu) — the 4th
     instance of make-the-invisible-countable (0033 found-then-dropped, 0043
     found-but-unsubmitted, 0044 empty→wrong-file named, 0045 counts it in the predicate).
  4. Six-member total-order verdict (`decide_refinement_outcome`), grid-totality tested.
  5. The two-stage freeze (stage-1 discriminator table committed before attribution;
     stage-2 config committed after the SUT lands, before any live call).
- **Run integrity:** 33/33 cells, 0 degrades, exclusivity clean (start + per-block),
  foreign resident `qwen3-14b-cc:latest` evicted-before / re-pinned-after (expiry 2318),
  ~3.5 h across resumable budget-bounded invocations via the detached nohup wrapper.

## Deviations

- **Harness bug fixed mid-run (non-SUT, hashes unaffected):** `refinement_run._API_BASE`
  wrongly included `/v1`, so the preflight hit `/v1/api/tags` (404). Fixed to the bare base
  `http://127.0.0.1:11434` (the reused OpenAI-compatible runner still appends `/v1`). This is
  eval-harness code, NOT in the frozen SUT, so `compute_sut_hash()` is unaffected and run
  integrity holds.
- **0044's committed config pin reconciled to HISTORICAL:** because 0045 evolved
  `scout/confidence_gate.py` (+ `confidence_signals.py`), the live `compute_sut_hash()` no
  longer equals the `sut_hash` 0044 froze. The committed-config pin test was amended to assert
  the divergence EXPLICITLY (every field except `sut_hash` still matches; the frozen digest is
  a valid 64-char sha that now DIFFERS from live) rather than rot false — the 0044 freeze is
  made explicit as historical.
- **The refined gate is the LEVER that trades** — recorded as a candidate to be replaced, not
  a settled operating point; the operator directs its revert (see below).
- **T18 dedup DECLINED with reason** (mirror-not-share): `refinement_outcome`/`refinement_config`
  intentionally do not share code with 0044's `submission_*` — coupling would let a 0045 edit
  perturb 0044's byte-stable head-to-head axis. The one genuine duplication (`_tool_spans_in_order`)
  was removed by the T5 scout move.

## Post-close operator action (directed at close)

- **Revert/retire the require-corroboration gate:** the live explorer loop is restored to
  0044's conditioned gate (`qualifying_symbols_spans`, net +2) as the best operating point to
  date. The require-corroboration predicate (`qualifying_confidence_spans`) is retired in place —
  kept in `scout/confidence_gate.py` as the documented REJECTED lever with its 0045 measurement
  archived, no longer wired into the loop. Reverting `explorer_loop.py` evolves the SUT, so the
  0045 committed-config pin was reconciled to HISTORICAL in the same change (the same pattern
  0045 applied to 0044's pin).

## Files touched (SUT)

- `harpyja/scout/confidence_signals.py` (NEW — gold-blind one-definition home)
- `harpyja/scout/confidence_gate.py` (refined require-corroboration ranking — RETIRED in place)
- `harpyja/scout/explorer_loop.py` (refined gate wired in for the run, then REVERTED to 0044's gate)
- `harpyja/eval/live_verifier.py` (schema `0045/1`, dual-seam)
- `harpyja/eval/submission_observability.py` (imports signals by identity from scout)
- `harpyja/eval/submission_gap.py` (parser re-export)

## Files touched (eval machinery, new)

- `harpyja/eval/discriminator_table.py`, `refinement_attribution.py`,
  `refinement_config.py`, `refinement_outcome.py`, `refinement_run.py`

## Spec artifacts

- `specs/0045-refinement/discriminator_table/discriminator_table.json` (stage-1 freeze)
- `specs/0045-refinement/refinement_config/refinement_config.json` (stage-2 freeze)
- `specs/0045-refinement/refinement_run/` (results, summary, 33 artifacts, driver)
- `specs/0045-refinement/outcome.md`
