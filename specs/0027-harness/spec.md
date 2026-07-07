---
id: "0027"
title: "harness"
status: draft
created: 2026-07-07
authors: [claude]
packages: [harpyja/scout, harpyja/eval]
related-specs: [0011, 0014, 0017, 0020, 0021, 0022, 0023, 0024, 0026]
---

# Spec 0027 — harness (remove eager context-map; on-demand structure discovery)

## Why

An RCA on the astropy case (`specs/0026-eval/rca-explorer-context-bloat.md`) found the
explorer's per-turn prompt is dominated by spec-0024's `build_context_map` — a flat
whole-repo listing (**~1,221 lines / ~10,181 tokens for astropy**) re-sent every turn.
On local hardware a capable model (Qwen3-16B-A3B) spends **~48–68s per turn just
prefilling that map** — and the full explorer prompt (map + verbose system frame + 3
tool schemas) pushes the model into a generation that did not complete even turn 1
within a 300s timeout. So turns exceed the HTTP timeout → the gateway raises →
`ScoutUnavailable` → floored to `empty` with `last_turns_used: None` (a degrade, not an
honest "not found"). **The same model + server localizes the astropy file+block in
seconds under OpenCode**, which starts near-empty and discovers structure on demand via
`grep`/`glob`/`ls`. The eager whole-repo *push* is the defect; the fix is *pull*.

**Downstream (scoped precisely — see AC7):** the **0026** pilot's `UNDER_POWERED_STOP`
ran through this defective `ExplorerBackend` path and is **timeout-confounded** — a
degrade misread as non-localization. It is the ONLY prior finding this defect reaches:
`build_context_map`/`ExplorerBackend` are net-new in spec 0024, so specs **0020–0023
(pre-0024) ran on the now-retired FastContext backend and never touched the eager map**
— this RCA does not bear on them.

Ref: 0024 (`build_context_map` — the component being removed), 0017 (gateway per-op
timeout), 0011/0014 (typed degrade floors + per-cause degrade visibility), 0026 (the
confounded finding + the RCA).

### Load-bearing invariants

- **INVARIANT (push → pull; FULL removal, not shrinkage):** eager whole-repo context
  injection is REMOVED entirely, not reduced to a smaller tree. Shrinkage leaves a
  confound (*how much did I leave in?*) inside the very fix meant to remove one — full
  removal makes the astropy validation unambiguous. Structure is discovered on demand
  through tools the model chooses to call. (The cutover mechanism — `context_map=""`
  compatibility shim vs. deleting the `_Session` map record and refactoring its
  "right-after-the-map" index assumption — is chosen explicitly in the plan; see What.)
- **INVARIANT (blind-start guard — the opposite failure):** removing the map must not
  swing the model into aimless `grep`/`glob` that exhausts its budget — which ALSO
  degrades to empty. Add a cheap on-demand `ls`/tree TOOL. This is genuinely NOT
  redundant with existing tools: `glob` filters out directories (`explorer_tools.py`:
  `if not match.is_file(): continue`), so the suite has NO layout-discovery affordance
  today. This is the minimal pull affordance; it is NOT the Tier-0 AST symbol tool (the
  named follow-up). Adding it is a DELIBERATE, reconciled tool-suite change (AC3), not
  silent creep.
- **INVARIANT (cutover, not redesign):** no change to the `ScoutBackend`/`Locator`
  boundary, the gate, matrix, orchestrator, or the `submit_citations` contract. This
  removes ONE component (eager map), adds ONE cheap tool (`ls`/tree), retires `turns_used`
  as a diagnostic signal (AC8), and re-validates. Air-gap + per-op timeout (0017)
  unchanged.
- **INVARIANT (four terminal states, distinguished by CAUSE — not `turns_used`):** the
  loop has FOUR terminal outcomes and they MUST be separable in the recorded result via
  the **already-typed `ScoutUnavailable.cause` + `LoopResult.outcome`**, never
  `turns_used` arithmetic:
  1. **mid-turn exception** (timeout/transport) → `MODEL_UNREACHABLE`/`BACKEND_ERROR`,
     `last_turns_used` is `None` (the loop raised before returning a `LoopResult`);
  2. **turn-exhaustion** → `LOOP_TURNS_EXHAUSTED` (`turns_used == cap`);
  3. **wall-clock exhaustion** → `LOOP_WALLCLOCK_EXHAUSTED` (a real *sub-cap* int —
     realistic here given ~48–68s/turn vs a 300s ceiling);
  4. **honest-empty** → `SUBMITTED` with `[]`, no exception.
  `turns_used` cannot separate these (it is `None` on any degrade because `engine.py:78`
  copies it only on the success path, and a *sub-cap* int on wall-clock exhaustion —
  indistinguishable from low-turn honest-empty). The cause taxonomy already carries four
  stable ids; the real gap is the REPORT layer (`runner._is_scout_degraded` collapses all
  four into one boolean/count). Making a re-emptied astropy diagnosable = surfacing
  per-cause degrade counts (AC4).

## What

- **Remove `build_context_map`'s eager whole-repo injection** from the explorer path
  entirely. The initial prompt is OpenCode-style minimal: system prompt + task/query,
  **no repo listing**. State the cutover explicitly in the plan — either pass
  `context_map=""` (leaves a contentless `_Session` record 0, keeps
  `_refresh_index().insert(1,…)` valid) or delete the map record and refactor the
  "right-after-the-map" assumption (`explorer_loop.py`) — and PICK one, deliberately.
- **Add a bounded, read-only `ls`/tree tool** (on-demand directory listing, repo-confined
  via `confine_path`, output-clamped by a NEW dedicated `Settings` field
  `scout_ls_max_entries`) to the tool suite alongside `grep`/`glob`/`read_span` — same
  untrusted-caller boundary. **Reconcile the exact-tool-count convention**: amend
  `.speccraft/conventions.md` (EXACTLY `{grep,glob,read_span}` → EXACTLY
  `{grep,glob,read_span,ls}`) with a rationale line (a deliberate affordance change, the
  very guard the convention exists for — NOT weak-model tool creep), and update BOTH
  hard-count tests in the same change (`test_explorer_tools.py::
  test_build_explorer_tools_returns_exactly_three_navigation_tools` and
  `test_explorer_backend.py::test_tool_schemas_match_the_built_tool_surface_single_source`).
- **Ensure the per-turn prompt no longer carries a re-sent, growing map**; the turn-1
  payload drops from ~10K tokens to a small constant, independent of repo size (verified
  at the BACKEND level — `build_context_map` is called in `ExplorerBackend._run_loop`,
  not `run_explorer_loop`).
- **Retire `turns_used` as a diagnostic signal** (AC8): the cause taxonomy is the single
  source of truth for *why* a run ended; `turns_used` remains ONLY the migrated 0022
  turns-CONSUMED measurement, never a why-did-it-end discriminant.
- **Keep degradation typed + visible** (standing convention): every terminal degrade is a
  typed `ScoutUnavailable` cause → Tier-0 floor, and now reported per-cause; honest-empty
  is a well-formed empty *submission* (NOT a degrade). (Note: turn-exhaustion is a *typed
  degrade* `LOOP_TURNS_EXHAUSTED`, not an honest-empty — the earlier draft's
  "turn-exhausted → honest-empty" was wrong per the code.)

## Acceptance criteria

([unit]=fakes/injected; [integration]=live, `@pytest.mark.integration`, skip-not-fail)

1. **[unit]** The explorer's INITIAL prompt contains NO whole-repo listing; the turn-1
   payload is a small constant (assert an upper bound well below the ~10K-token
   regression), **independent of repo size** — asserted at the BACKEND level
   (`ExplorerBackend._run_loop`) with a large synthetic manifest, since the map is built
   there, not in `run_explorer_loop`.
2. **[unit]** The per-turn prompt does not re-inject a repo map; prompt growth across
   turns is bounded by tool outputs + the truncation policy only (no map term).
3. **[unit]** The new `ls`/tree tool is read-only, repo-confined (`confine_path`), and
   output-clamped by the new `scout_ls_max_entries` `Settings` field; hostile input
   (out-of-repo path, over-budget listing) is rejected/clamped — the same boundary as
   `grep`/`glob`/`read_span`. The exact-tool-count convention is amended to
   `{grep,glob,read_span,ls}` and BOTH hard-count tests updated in the same change.
4. **[unit]** The FOUR terminal states are separated in the recorded result via
   `ScoutUnavailable.cause` + `LoopResult.outcome` — NOT `turns_used`: mid-turn exception
   (`MODEL_UNREACHABLE`/`BACKEND_ERROR`), turn-exhaustion (`LOOP_TURNS_EXHAUSTED`),
   wall-clock exhaustion (`LOOP_WALLCLOCK_EXHAUSTED`), honest-empty (`SUBMITTED`, no
   citation) — asserted distinct. The report-layer gap is closed:
   `harpyja/eval/runner.py::_is_scout_degraded` currently collapses all causes into one
   `scout_degrade_count`; add **per-cause** degrade counts so a re-emptied astropy names
   WHICH state it hit. **(Makes AC5 interpretable.)**
5. **[integration]** astropy case: the explorer (Qwen3-16B-A3B on llama.cpp) **localizes
   the file+block WITHOUT degrade in ≤ a pre-stated turn ceiling `N`** — the
   OpenCode-parity proof. PLUS a **second, structurally different case** (a larger repo
   whose old map would have been even bigger), so a single lucky localization does not
   stand in for "harness fixed." If either still empties, AC4's cause taxonomy names WHICH
   failure — and it must NOT be a timeout/backend degrade. **(AC5 is the whole spec.)**
6. **[integration]** The turn-1 payload measured LIVE drops from the ~10,181-token
   regression to the small constant; per-turn latency is no longer dominated by map
   prefill (record the actual payload + latency for both AC5 cases).
7. **[doc]** The record is corrected, **scoped to 0026 ONLY**: the 0026 pilot
   `UNDER_POWERED_STOP` ran on `ExplorerBackend` (post-0024/0025) through the eager map and
   is **capability-mute / timeout-confounded**. Specs **0020–0023 ran on the RETIRED
   FastContext backend (pre-0024) which never called `build_context_map`** → this RCA does
   NOT bear on them (a now-removed backend; NOT "confounded" — do not claim it). The
   FastContext *dependency removal* (0024/0025) stands independently (sourcing, not a
   capability claim). Fix lands in three places already carrying the overreach: this AC7,
   `rca-explorer-context-bloat.md` Impact, and the `operator-run-findings.md` correction
   note (the latter two committed in `1ef917f` — corrected).
8. **[unit]** `turns_used` is RETIRED as a diagnostic signal for *why a run ended*: the
   cause taxonomy (`ScoutUnavailable.cause` + `LoopResult.outcome`) is the single source of
   truth. A grep sweep of `harpyja/scout` + `harpyja/eval` finds no `turns_used`-based
   inference of run outcome/degrade-kind; any found is removed. (`turns_used` survives ONLY
   as the migrated 0022 turns-CONSUMED count — a measurement, not a discriminant.)
9. **[unit]** With the map absent, the citation-preserving truncation still behaves
   (promoted from OQ3): removing the map lightens baseline history (~40K chars for
   astropy), shifting truncation onset LATER; assert `maybe_truncate` still fires past
   `scout_history_char_cap` and never drops a citable observation (the 0024 negative still
   holds with no map term).

**Load-bearing for review.** **AC5 is the whole spec** — astropy (and a second repo)
localizing without degrade is the OpenCode-parity proof, binary. **AC4 makes AC5
interpretable** — the four-state cause taxonomy tells you, if astropy still empties,
whether you fixed the timeout bug and hit the blind-start risk (turn/wall-exhaustion — an
expected-possible NEW outcome) versus didn't fix anything (a timeout/backend degrade).
**AC7 corrects a committed error and must be exact** — an inaccurate correction is worse
than none, which is why it is scoped to 0026 only and verified against the actual
0024-introduced-the-map timeline.

## Out of scope

- **Tier-0 AST-as-a-callable-symbol-tool** (the named follow-up — this ships only the
  cheap `ls`/tree affordance).
- **Re-running the 0026 pilot** (separate, AFTER this fix, with a timeout above real
  per-turn cost + a tool-call serving preflight).
- **The model bake-off.**
- **The tool-call-serving preflight itself** (name it a required pre-bake-off item; the
  explorer needs an endpoint that emits OpenAI `tool_calls` — llama.cpp `--jinja` does,
  Ollama's `--no-jinja --chat-template chatml` path does NOT for a raw HF GGUF).
- **A total-request wall-clock deadline** for the explorer (the separate 0017-caveat
  robustness follow-up — this spec removes the bloat that *triggers* the timeout; it does
  not add a hard-terminable total deadline).
- **OQ/gate/threshold tuning.**

## Open questions

1. **`ls`/tree tool granularity:** single-directory listing per call (model walks down)
   vs. bounded depth-N subtree per call. Single-dir is the purest pull and cheapest;
   depth-N saves turns but re-creates a mini-eager-dump risk. **Lean single-dir; decide
   before plan.**
2. **Does ANY minimal orientation help without re-introducing the defect** — e.g. a
   one-line "repo root has N top-level dirs: [names]" (cheap, constant) vs. truly nothing?
   **Lean truly nothing first** (cleanest astropy proof); add minimal orientation only if
   AC5 shows blind-start turn/wall-exhaustion. Pilot the empty-start; don't pre-scaffold.
   **Procedural guard:** if orientation IS added later, it MUST re-run AC5/AC6 fresh — the
   zero-orientation astropy proof does NOT transfer to an orientation-added variant (two
   variables must not be conflated across specs). **(Settle in review.)**

## Validation environment (RCA reference)

AC5/AC6 run against the served model that reproduced the RCA: Qwen3-16B-A3B on
**llama.cpp** (`--jinja`, tool-calls confirmed), model id
`unsloth/Qwen3-16B-A3B-GGUF:Q4_K_M`, `127.0.0.1:8131/v1`, 65536 context — the same
model+server that localizes astropy in seconds under OpenCode.
