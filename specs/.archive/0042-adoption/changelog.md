---
spec: "0042"
closed: 2026-07-12
---

# Changelog — 0042 adoption

## What shipped vs spec

Symbols-tool adoption: all FOUR stacked adoption defects fixed IN LOCKSTEP (the
fairness invariant), the measurement predicate frozen and hashed before any live
call, the re-measure run through the 0041-gated driver, and the outcome typed
mechanically. Delivered exactly as planned; the live outcome is
**`ADOPTED_AND_CONVERTS`** (a signal at pilot scale, NOT an inferential claim).

The four fixes:

1. **Prompt (AC1).** `build_initial_prompt` (`context_map.py`) now names all five
   navigation tools (`grep`/`glob`/`read_span`/`ls`/`symbols`) plus the terminal
   `submit_citations`, carries the `symbols` when-to-use (candidate-file → exact
   definition span; repo-wide by-name lookup when the query is ungreppable). A NEW
   drift guard (`test_initial_prompt_binds_to_registered_tool_surface_single_source`)
   binds the prompt enumeration to the SAME single-source registered surface the
   existing `test_tool_schemas_match_the_built_tool_surface_single_source` uses — a
   new tool is now un-shippable without appearing in the prompt. The 0027 text had
   silently omitted `symbols` and `read_span` for 5 specs (the root of the 0/28
   defect).
2. **Description (AC1-desc).** The `symbols` schema description (`explorer_backend.py`)
   now states the when-to-use and that results carry exact start/end spans (the
   citation-shaped-output pitch).
3. **Result shape (AC2).** `symbols` returns a bare `list[CodeSpan]` (parity with
   every other nav tool) clean / `[marker, *CodeSpans]` degraded (marker first,
   annotation). The `{"symbols": ..., "degraded": bool}` nested dict is GONE.
   `_spans_of` needed NO code change (the fix was the return type); its behavior is
   regression-pinned. The 0035 marker convention was amended IN LOCKSTEP (T4) to
   record the second, distinct "successful-but-degraded ANNOTATION" case.
4. **Positioning (AC3).** `path` is now OPTIONAL; `symbols(name=…)` does a repo-wide
   by-name lookup over Tier-0 records, ranked exact > prefix > substring (ties by
   `(path, start_line)`), clamped by a NEW distinct knob
   `scout_symbols_repo_max_entries=200`. Absent/degraded Tier-0 index → 0035
   REPLACEMENT marker, never a silent `[]`.

The measurement scaffold:

- `PREREGISTERED_ADOPTION_CONFIG_0042` frozen + hashed
  (`ADOPTION_CONFIG_HASH_0042 = c4e24c249e81…`), committed at
  `precheck/adoption_config.json` BEFORE any live call. Total pure
  `decide_adoption_outcome` (grid-totality tested): adoption boundary, RFWS
  denominator, bidirectional per-case paired-bucket conversion predicate (both
  conversions AND regressions, net surfaced), `MIN_RFWS_DENOMINATOR=3` power floor,
  pinned model coverage, per-model partial-coverage denominators.
- `run_adoption.py` STOP-AND-WARN operator driver (exit 0/2/3) via
  `harpyja/eval/adoption_run.py`, routing through `run_gated_pool_pilot(live=True)`
  with the `0041/pilot/2` exclusivity proof, resumable ledger keyed by the config
  hash, coverage consumed from the frozen config.

## Per-AC disposition

- **AC1** (prompt drift-guard + when-to-use) — MET. Full registered surface asserted
  from the single source; repo-wide advertisement check present unconditionally.
- **AC2** (result shape + `_spans_of` accounting + 0035 amendment) — MET.
- **AC3** (repo-wide lookup, ranking, clamp, hostile input, absent-index marker) — MET.
- **AC4** (tool-count reconciliation) — MET as a **no-op VERIFY**: OQ1 resolved
  optional-path (no new tool), so the count stays 5; both hard-count tests stay green
  and the conventions prose is unchanged (recorded, per the OQ1 decision).
- **AC5** (frozen + hashed config, total decider) — MET.
- **AC6** (gated re-measure, committed trajectory-verified artifacts) — MET (exit 0,
  33 cells, artifacts + ledger + summary committed).
- **AC7** (typed outcome record) — MET: `ADOPTED_AND_CONVERTS`, decided mechanically.

## Live result

Adoption **24/31 clean cells (77%)** vs the 0/28 baseline (14b 7/11, 8b 10/11, 4b 7/9);
conversions **1** (`pallets__flask-5014::qwen3:8b` RFWS→correct, symbols invoked),
regressions 0, net **+1** on RFWS denominator 4 ≥ floor 3 (NOT under-powered). 33 cells
recorded, 31 clean, 2 typed 4b `model-unreachable` degrades (the known out-of-scope
heavy-repo class), 0 suspect; exclusivity clean throughout. The 0/28→24/31 delta is
**fix-vs-defect, not tool-vs-no-tool**; 0030's lift-refutation (and 0031/0034/0035/0040's
"not invoked") measured an UNUSABLE tool. The all-four-fixes-at-once attribution confound
is accepted and recorded.

## Deviations

- **T3 loop tests passed pre-implementation** (pins, not RED) — `_spans_of` needed no
  code change, so the shape/accounting tests pinned already-correct behavior.
- **T7 REFACTOR evaluated and DECLINED** with a recorded reason (0040-T22/0041-T21
  precedent): the two markers follow the same inline `<id>: '<scope>'` f-string idiom
  as the 0035 grep/ls markers; extracting constants for one tool would split the
  convention's expression across two styles, and every shape is test-pinned.
- **Integration smoke lives at `harpyja/eval/test_adoption_run_integration.py`**, not
  the plan's `specs/0042-adoption/adoption_run/` path — `specs/` is not on the pytest
  collection path (the `test_gate_run_integration.py` precedent).
- **T12 first attempt killed by a harness background-task cap (~20 min)** and relaunched
  detached via `nohup`; the resumable ledger made it lossless. The run used a wrapper
  loop re-invoking the budget-bounded driver (9 invocations).
- **Two live-observed `symbols` bugs FIXED POST-MEASUREMENT** (after exit 0; all 33
  cells measured on the pre-fix SUT): (a) `path=""`+name silently ignored the name
  (routing `is None` → `not path`); (b) a nonexistent path returned a silent `[]` (now
  the `symbols-path-not-found` 0035 replacement marker; records win over disk absence).

## Files touched

Modified (SUT + tests):
- `harpyja/scout/context_map.py` — `build_initial_prompt` names all 5 tools + terminal + symbols when-text
- `harpyja/scout/explorer_backend.py` — `symbols` schema: `path` optional, when+spans description
- `harpyja/scout/explorer_tools.py` — `symbols` bare-list/annotation shape + repo-wide by-name lookup + post-T12 markers
- `harpyja/config/settings.py` — new `scout_symbols_repo_max_entries=200` knob
- `harpyja/config/test_settings.py`, `harpyja/scout/test_context_map.py`,
  `harpyja/scout/test_explorer_backend.py`, `harpyja/scout/test_explorer_loop.py`,
  `harpyja/scout/test_explorer_tools.py`
- `.speccraft/conventions.md` — 0035 marker convention amended in lockstep (T4)
- `.speccraft/index.md`

New (measurement scaffold):
- `harpyja/eval/adoption_precheck.py` — frozen config + hash + total decider
- `harpyja/eval/adoption_run.py` — gated driver machinery
- `harpyja/eval/test_adoption_precheck.py`, `harpyja/eval/test_adoption_run.py`,
  `harpyja/eval/test_adoption_run_integration.py`

New (committed spec artifacts):
- `specs/0042-adoption/precheck/adoption_config.json` — frozen config (hash committed pre-run)
- `specs/0042-adoption/adoption_run/` — driver, ledger, per-case artifacts, summary
- `specs/0042-adoption/outcome.md` — the AC7 typed-outcome record

## ADR proposed for history.md

See the 2026-07-12 spec 0042 entry appended to `.speccraft/history.md`.

## Conventions proposed

- New: the prompt↔tool-surface drift guard (the exact-count convention extended to the
  prompt — a new tool is un-shippable without appearing in it).
- New: empty-string params are treated as absent in tool routing (`not path`, not
  `is None` — small-model tool-calling emits `""` for an omitted arg).
- New: defects observed live are fixed AFTER the run completes (SUT frozen per run),
  never mid-run, and recorded in the outcome doc.
- Amended in-implementation (T4): the 0035 marker convention's second (annotation) case
  — already recorded, NOT re-proposed here.
