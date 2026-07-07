---
spec: "0027"
title: "harness — remove eager context-map; on-demand structure discovery"
reviewers: [codex, claude-p]
quorum: 1
verdict: reviewed
generated: 2026-07-07
rounds: 2
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

### Amendments (revision 2)

All three blockers + every single accepted. AC7 narrowed to 0026-only (+ the two
committed artifacts `rca-explorer-context-bloat.md` / `operator-run-findings.md`
corrected in `0fdcb57`); AC4 rebuilt on the `ScoutUnavailable.cause` + `LoopResult.outcome`
four-state taxonomy with the `runner._is_scout_degraded` per-cause-count gap named; new
**AC8** retires `turns_used` as a why-did-it-end signal (grep sweep); tool-count
reconciled (convention 3→4 + both tests + `scout_ls_max_entries`); "turn-exhausted →
honest-empty" reworded to the typed degrade; AC1 backend-level; AC5 turn ceiling + second
case; `_Session` cutover stated; OQ3→AC9; OQ2 re-run-fresh guard.

---

## Round 2 (revision 2)

### claude-p — approve-with-comments (quorum-meeting)

Independently diffed `0fdcb57` and **verified the priority check**: the AC7 reframe is
factually correct against the 0024-introduced-the-map timeline, and both committed
artifacts are corrected with **no new inaccuracy**. All eight round-1 items confirmed
landed. Two non-blocking comments (accepted):
- **AC4's new per-cause report fields need `SCHEMA_VERSION` `0026/1 → 0027/1`** — the
  additive-field + bump convention has been unbroken 0011→0026; AC4 was silent on it.
- **AC1's bound was unpinned** ("well below ~10K") — needs a concrete number.
- (+ the second AC5 repo needs a named target + gold span; cosmetic AC7 commit-ref.)

### codex — changes-requested (confirmed R1 resolved; new concreteness items)

Did NOT re-flag any of the eight round-1 items (a critical line-by-line pass falling
silent on them = they landed). New/convergent:
- **AC5's turn ceiling `N` and second-repo case were unnamed** (deferred to plan) — not
  reproducible as the load-bearing binary proof. (Convergent with claude-p.)
- **Load-bearing OQs (ls granularity, zero-orientation) shouldn't stay open** in a
  plan-ready spec — decide them in the spec.
- **NEW (sharp): AC4 requires `LOOP_WALLCLOCK_EXHAUSTED` while OOS excludes a total-request
  deadline — resolve the ambiguity.** (Verified: `LOOP_WALLCLOCK_EXHAUSTED` is the
  PRE-EXISTING spec-0024 between-turns `scout_wall_clock_s` ceiling, `explorer_loop.py:196`;
  the OOS item is a *different* in-flight-preempting total deadline. No conflict —
  disambiguated.)
- **AC1/AC6 thresholds vague** ("small constant") — concrete token/byte ceilings + a
  counting method. **AC5/AC6 need a committed evidence artifact** (skip-not-fail live runs
  are weak for "AC5 is the whole spec").

### Resolutions (revision 3)

- **AC1/AC6:** turn-1 payload **≤ 2,000 tokens (≤ ~8,000 chars, `len//4`)**, repo-size-
  independent (small + large synthetic manifest, both clear the bound).
- **AC4:** `SCHEMA_VERSION 0026/1 → 0027/1` via `_AGGREGATE_DEFAULTS`; clarified
  `LOOP_WALLCLOCK_EXHAUSTED` is the pre-existing spec-0024 ceiling (surfaced, not new),
  distinct from the OOS total-deadline.
- **AC5:** pre-registered **`N = 10` turns**, two concrete cases — `astropy__astropy-12907`
  (910 `.py`) and **`django__django-12774`** (2,611 `.py` — ~2.9× astropy; gold
  `django/db/models/query.py` 689–695) — each with a hand-authored terse query; pass =
  localize (`right-file`/`correct`) without a timeout/backend degrade.
- **AC6:** committed evidence artifact (payload size, per-turn latency, turns, outcome/cause,
  bucket) under `specs/0027-harness/`.
- **Open questions → Decisions:** `ls` = single-directory listing (depth-N rejected);
  zero initial orientation (empty-start piloted; minimal orientation is a re-run-fresh
  follow-up only if AC5 shows a genuine exhaustion, not a timeout-degrade).
- **Cutover DECIDED:** `context_map=""` (zero content → satisfies full-removal; the
  `_Session` record deletion is optional cleanup). Cosmetic AC7 commit-ref → `0fdcb57`.

---

## Determination

**Quorum met** (claude-p: approve-with-comments across round 2, priority check verified),
and codex's round-2 items — convergent concreteness fixes + the wall-clock disambiguation,
none re-flagging a round-1 blocker — are resolved in revision 3. No guardrail violations
survive; the exact-tool-count convention is amended head-on with a rationale, and the
`SCHEMA_VERSION` bump convention is now honored. Status → **reviewed**. Ready for
`/speccraft:spec:plan`. The two experiment-defining choices the planner inherits as fixed:
`N=10` turns and the two named validation cases (astropy + django), on the llama.cpp
`--jinja` 16B stack.
