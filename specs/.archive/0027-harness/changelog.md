---
spec: "0027"
closed: 2026-07-07
---

# Changelog — 0027 harness (remove eager context-map; on-demand structure discovery)

## What shipped vs spec

- **Eager whole-repo context map REMOVED from the explorer's live path (PROVEN — AC1/AC2/AC6-payload).**
  The turn-1 payload drops from the ~10,181-token regression to ~60 tokens — a ~170×
  cut — on BOTH cases and **independent of repo size** (asserted at the backend level with
  a small AND a large synthetic manifest; the two payloads are byte-identical because no
  manifest term survives). Push → pull: structure is discovered on demand via tools.
- **On-demand `ls` tool added + exact-count convention amended 3 → 4 (AC3).** A bounded,
  read-only, single-directory listing (`confine_path`-guarded, lists files AND dirs so
  layout is discoverable — the affordance `glob` lacks) clamped by a NEW `Settings` field
  `scout_ls_max_entries: int = 200`. The `.speccraft/conventions.md` exact-tool-count
  convention was amended (`{grep,glob,read_span}` → `{grep,glob,read_span,ls}`) with a
  rationale line, and BOTH hard-count tests updated in the same change
  (`test_build_explorer_tools_returns_exactly_four_navigation_tools`,
  `test_tool_schemas_match_the_built_tool_surface_single_source`).
- **Four-cause taxonomy surfaced per-cause in the report layer (AC4).** `runner.py` gains
  `_scout_degrade_cause` (parses `scout-degraded:<cause>`, tolerant of the `+no-matches`
  suffix) and emits four additive per-cause counts
  (`scout_degrade_{model_unreachable,backend_error,loop_turns_exhausted,loop_wallclock_exhausted}_count`)
  alongside the retained collapsed `scout_degrade_count`; `report.SCHEMA_VERSION`
  bumped `0026/1 → 0027/1` via `_AGGREGATE_DEFAULTS` (legacy blocks still validate).
- **`turns_used` retired as a why-did-it-end signal (AC8).** An executable source-sweep
  guard pins that `explorer_backend.py`/`explorer_loop.py` never branch on
  `turns_used`/`last_turns_used` to infer outcome/degrade-kind; the discriminant is
  `LoopResult.outcome` / `ScoutUnavailable.cause`. `turns_used` survives ONLY as the
  migrated 0022 turns-CONSUMED measurement.
- **Truncation still fires + citation-preserving with the map absent (AC9).** The 0024
  preservation negative re-proven with `context_map=""`: onset shifts later (lighter
  baseline), the mechanism is unchanged, no citable observation is dropped.
- **AC1 bound pinned:** turn-1 payload ≤ 2,000 tokens (`len//4`, ≤ ~8,000 chars).

## Deviation

- **Cutover is a minimal `build_initial_prompt(query)`, NOT literally `context_map=""`
  (T6).** The spec DECIDED `context_map=""`, but the query was baked into
  `build_context_map`, so passing an empty string would have dropped the task/query from
  the prompt. The shipped cutover injects ZERO repo content (satisfying the full-removal
  invariant — full-removal governs prompt *content*) while PRESERVING the query in a
  small constant prompt. `build_context_map` is retained in `context_map.py` for
  reference/history; the backend simply stops calling it.
- **AC5 localization is a recorded HOLD (see below) — capability remains UNMEASURED.**

## AC5 HOLD — a generation-control blocker, NOT a capability finding

Map removal is proven, but the LIVE AC5 localization is BLOCKED downstream: both
astropy-12907 and django-12774 degraded `cause=model-unreachable` @~300s
(`turns_used=None`, no citations) — the model **never finished generating**, so it
never localized. `model-unreachable ≠ "can't localize"` — the SAME degrade-masks-outcome
trap the 0026 RCA corrected; do not read it as a capability result. Diagnosis (measured):
the runaway is two-fold — Qwen3 thinking + unbounded generation; `/no_think` alone still
ran away (180s timeout), `/no_think` + a `max_tokens` cap tool-called in 13.2s
(`finish=length`). AC5's live test (`test_harness_live.py`) ships **`xfail` (non-strict)**:
it skips with no stack (CI-safe) and flips to **xpass** when the generation-control
follow-up lands — the signal to un-hold it. Two knobs in the generation-control family,
distinct from map removal.

## AC7 record-correction — asserted consistent (not merely noted)

A factual error — 0020–0023 "likewise confounded" by the eager map — was shipped in
`1ef917f` and CORRECTED to **0026-only** across all three surfaces (spec AC7,
`specs/0026-eval/rca-explorer-context-bloat.md` Impact, `operator-run-findings.md` note)
in `0fdcb57`. `build_context_map`/`ExplorerBackend` are net-new in spec 0024, so
0020–0023 (pre-0024) ran on the retired FastContext backend and never touched the eager
map → **not confounded** by this defect (moot for current Scout, not "confounded"). The
close ASSERTED (T14, not merely noted) that the correction landed consistently — all
three surfaces are 0026-only, FastContext-scoped, zero residual "likewise confounded"
claims. A mis-correction that half-reverts is worse than the original error, which is why
this is an assertion, not a note.

## Blocking follow-up — generation control is a PREREQUISITE, not cleanup

Generation control (disable Qwen3 thinking + a tuned `max_tokens` cap + likely a more
directive tool-use prompt) is a **BLOCKING PREREQUISITE**, not 0027 polish. It GATES the
0026 pilot re-run, the model bake-off, AND any re-validation of localization capability.
Until it lands we cannot measure whether ANY model localizes through the explorer. The
REAL project status: the explorer harness is proven cheap-prompt (map removed), but its
ability to DRIVE a model to a citation is UNPROVEN pending generation control. The
`/no_think`+cap=13.2s number is that follow-up's first evidence and first AC.

## Files touched

- `.speccraft/conventions.md` (exact-tool-count convention amended 3 → 4)
- `harpyja/config/settings.py`, `harpyja/config/test_settings.py` (`scout_ls_max_entries`)
- `harpyja/scout/context_map.py` (`build_initial_prompt`; `build_context_map` retired-from-live)
- `harpyja/scout/explorer_backend.py` (`build_initial_prompt` cutover, `ls` schema)
- `harpyja/scout/explorer_tools.py` (`ls` tool; module docstring 3 → 4)
- `harpyja/scout/test_explorer_backend.py`, `test_explorer_tools.py`, `test_explorer_loop.py`
- `harpyja/eval/runner.py` (`_scout_degrade_cause`, per-cause counts)
- `harpyja/eval/report.py` (per-cause fields, `SCHEMA_VERSION 0026/1 → 0027/1`)
- `harpyja/eval/test_runner.py`, `test_report.py`
- `harpyja/eval/test_harness_live.py` (NEW — AC5/AC6 live proof, `xfail`)
- `specs/0027-harness/operator-run-findings.md` (NEW — the live proof)
