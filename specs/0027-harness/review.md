---
spec: "0027"
title: "harness — remove eager context-map; on-demand structure discovery"
reviewers: [codex, claude-p]
quorum: 1
verdict: changes-requested
generated: 2026-07-07
rounds: 1
---

# Cross-model review — 0027 (harness)

One round. **Both reviewers `changes-requested`**, with convergent, code-grounded
findings, corroborated by an independent grounding pass over `harpyja/scout/`. The RCA
and the core fix (remove the eager whole-repo context map; add an on-demand `ls`/tree
tool) are **endorsed by both** — the code really does re-send the map every turn
(`_Session` record 0, `messages()` returns all, truncation only drops `kind=="tool"`),
and `glob` genuinely cannot discover directories (`explorer_tools.py`: `if not
match.is_file(): continue`), so the 4th tool is justified on the merits. Every blocking
item is a precision/accuracy fix, not a direction change. **Quorum (1 approve /
approve-with-comments) NOT met** — status stays **draft**.

One finding is unusually important: **claude-p found that AC7 is factually wrong about
0020–0023**, and that error was also committed into the RCA + the 0026 correction note
(`1ef917f`) — it must be corrected in all three places.

---

## Round 1

### Convergent findings (both agents + in-thread grounding)

1. **Exact-tool-count convention violation — the 4th tool is unreconciled.** Adding
   `ls`/tree breaks a *code-enforced* rule: `.speccraft/conventions.md` ("`build_explorer_tools`
   returns EXACTLY `{grep, glob, read_span}` … so a weak model can never motivate silent
   tool-suite creep"), hard-pinned by **two** tests — `test_explorer_tools.py::
   test_build_explorer_tools_returns_exactly_three_navigation_tools` (`assert set(tools)
   == {"grep","glob","read_span"}`, `len(out) == 3`) and `test_explorer_backend.py::
   test_tool_schemas_match_the_built_tool_surface_single_source` (schema-vs-dispatch
   no-drift). The spec's What/ACs never mention amending the convention or these tests.
   **Fix:** amend the convention text to exactly-four (`{grep,glob,read_span,ls}`) **with
   a rationale line** (a deliberate, non-silent affordance change — the very guard the
   convention exists for), and update both tests in the same change. `ls` is *justified*
   (both agents confirmed `glob` filters out directories, so the suite has NO layout-
   discovery affordance today) — it just must be reconciled explicitly, not slipped in.

2. **AC4 is inaccurate against the code — there are FOUR terminal states, and the
   discriminant is the cause taxonomy, not `turns_used` arithmetic.** AC4 pins the
   distinction to raw `turns_used` (`None` / `== cap` / submitted), but the code has four
   states: **mid-turn exception** (`last_turns_used is None`, `MODEL_UNREACHABLE`/
   `BACKEND_ERROR`), **turn-exhaustion** (`turns_used == cap`, `LOOP_TURNS_EXHAUSTED`),
   **wall-clock exhaustion** (a real *sub-cap* int, `LOOP_WALLCLOCK_EXHAUSTED` —
   `explorer_loop.py:195-197`), and **honest-empty** (`SUBMITTED`, `[]`, no exception).
   `turns_used` alone **cannot** separate low-turn wall-clock exhaustion from low-turn
   honest-empty — and given the RCA's own 48–68s/turn against a 300s/12-turn budget,
   wall-clock-before-turns is a *realistic* post-fix outcome. **Fix:** route AC4 through
   the already-typed `ScoutUnavailable.cause` (four stable ids) + `LoopResult.outcome`,
   NOT `turns_used` comparisons. The real plumbing gap (both agents, confirmed in code):
   `harpyja/eval/runner.py::_is_scout_degraded` **collapses all four causes into one
   boolean/count** for `scout_degrade_count`/`scout_degrade_rate` — AC4's actual work is
   adding *cause-level granularity to the report layer*, and the spec should say so.
   (Also: at the probe's read point, `engine.last_turns_used` is `None` on *any* degrade
   because `engine.py:78` copies the backend count only on the success path — another
   reason `turns_used` is the wrong discriminant.)

3. **AC7 is FACTUALLY WRONG about 0020–0023 (claude-p's headline; the sharpest catch).**
   `build_context_map` / `ExplorerBackend` are **net-new in spec 0024** (module docstrings:
   "spec 0024, AC3"; 0024 closed 2026-07-06). Specs **0020–0023 (2026-07-04/05) ran BEFORE
   0024**, on the **retired FastContext client** (`harpyja/scout/client.py`) — which never
   called `build_context_map` because it did not exist yet. So the "near-zero localization
   / RETRIEVAL_FUNDAMENTAL" findings of 0020–0023 **cannot be confounded by *this*
   eager-map defect.** Only **0026** ran through the defective `ExplorerBackend` path.
   AC7's claim that 0020–0023 are "likewise confounded" is unsupported and, per the dates
   + commit log, wrong. **Fix:** scope AC7's capability-mute correction to **0026 only**;
   for 0020–0023 state honestly that they measured a now-retired backend (FastContext),
   did NOT go through the eager map, and this RCA does not bear on them (their
   characterization is historical about a removed backend — moot for current Scout, not
   "confounded"). Unless independent evidence shows FastContext had its own prompt bloat
   (none offered), do not claim it. *An inaccurate correction is worse than none.*
   - **Committed-artifact impact (must fix beyond the spec):** the same overreach is in
     the already-committed `specs/0026-eval/rca-explorer-context-bloat.md` ("Impact" →
     "0020–0023 … likewise confounded") and the `operator-run-findings.md` correction
     note's RCA reference. Those need the same 0026-only narrowing.

### codex-specific (code-grounded)

4. **The What is inaccurate: "turn-exhausted-no-citation → honest-empty" is wrong.** The
   code raises a *typed degrade* `ScoutUnavailable(LOOP_TURNS_EXHAUSTED)` on turn
   exhaustion (`explorer_backend.py:217-218`, pinned by `test_explorer_backend.py:136-145`);
   honest-empty is ONLY a well-formed empty *submission*. Reword the What.
5. **`ls` clamp needs a named `Settings` field.** The other tools name concrete clamps
   (`search_max_matches`, `scout_glob_max_paths`, `tool_max_lines/chars`); AC3 says only
   "output-clamped from existing Settings" without naming which bounds a directory
   listing. Define a dedicated field (e.g. `scout_ls_max_entries`).
6. **AC1 repo-size independence isn't testable at the loop alone** — `build_context_map`
   is called in `ExplorerBackend._run_loop`, *before* `run_explorer_loop` (which only
   receives `context_map`). AC1 needs a **backend-level** unit test with a large manifest
   to prove the production path no longer injects a repo-sized prompt.
7. **AC5 needs a numeric turn ceiling** — "small number of turns" isn't machine-checkable;
   state `≤ N` turns under the validation env, and record actual latency/payload for AC6.
8. **State the cutover mechanism explicitly** — `context_map=""` compatibility shim
   (leaves a contentless record 0, keeps `_refresh_index().insert(1,…)` valid) vs. delete
   the record and refactor the "right after the map" assumption (`explorer_loop.py:113-178`).
   Choose deliberately.

### claude-p-specific

9. **OQ2 needs one procedural sentence:** if minimal orientation is added later (triggered
   by AC5 showing blind-start turn-exhaustion), it must **re-run AC5/AC6 fresh** — not
   reuse this spec's zero-orientation astropy proof, or the two variables (map-removal,
   orientation-add) get conflated across specs. (The invariant vs OQ2 is otherwise not a
   contradiction — the sequencing is sound.)
10. **AC5/AC6 single-case (astropy) is thin.** A single localization doesn't prove the
    *harness* generalizes (astropy may just fit the budget post-removal while a larger
    repo still blows it via tool-output accumulation). Add a **second, structurally
    different case** (a larger repo) as a stretch AC or named re-run follow-up.

### Both → promote OQ3 to a light AC

11. **OQ3 (truncation interaction) should be a one-line AC, not an open question.** Both
    agents confirmed: the astropy map (~40,725 chars) is *under* the 60,000-char
    `scout_history_char_cap` and is `kind=="map"` (never dropped — only `kind=="tool"`
    is), so removing it doesn't change the truncation *mechanism*, only delays onset.
    Low-risk — so pin it cheaply: a unit assertion that truncation still fires and stays
    citation-preserving with the map absent, rather than carrying an open question into
    plan.

### Compliance noted
No guardrail violations. `confine_path`/output-clamp for the new tool (AC3), air-gap
(pure local FS read), and measurement-not-construction (AC5/AC6 as live measurement, not
overclaiming removal as capability proof) are all correctly specified. The one convention
violation is the exact-tool-count (finding 1). The FastContext-removal-stands-independently
scoping in AC7 is correctly drawn (both agents) — it's only the 0020–0023 *confound* claim
that's wrong.

---

## Determination

**Quorum NOT met** — both `changes-requested`. Status stays **draft**. The direction is
endorsed; the blocking items are accuracy/precision fixes, and this reads
approve-on-resolution. Required amendments:

- **AC7 (+ committed RCA + correction note):** scope the capability-mute correction to
  **0026 only**; reframe 0020–0023 as a retired-backend measurement this RCA doesn't bear
  on. Fix the two committed artifacts too.
- **AC4:** discriminate via `ScoutUnavailable.cause` + `LoopResult.outcome` (FOUR states),
  not `turns_used`; name the real gap (`runner._is_scout_degraded` collapses causes → add
  cause-level report granularity). Correct the What's "turn-exhausted → honest-empty".
- **Tool count:** amend the convention + both hard-count tests to exactly-four with a
  rationale; name a dedicated `ls` clamp `Settings` field.
- **AC1/AC5/AC6:** backend-level map-absence test; a numeric turn ceiling for astropy; a
  second structurally-different case (or named follow-up). State the `_Session` cutover
  mechanism.
- **OQ2/OQ3:** add the re-run-fresh sentence to OQ2; promote OQ3 to a light AC.

Amend `spec.md`, then re-run `/speccraft:spec:review` (round 2).
