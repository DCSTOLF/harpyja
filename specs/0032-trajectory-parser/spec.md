---
id: "0032"
title: "trajectory-parser"
status: closed
started_at_sha: f736bde
created: 2026-07-08
authors: [claude]
packages: []
related-specs: ["0031-live"]
---

# Spec 0032 — trajectory-parser

## Why

Spec 0031 shipped the trajectory verifier but left T20 undone: the trajectory is parsed for tool-call names in TWO places with DIVERGENT behavior — `extract_tool_names` (the verify path) FAILS `tool-names-unextractable` on a tool_call lacking function.name, while the inline parse in `build_trajectory_record` silently SKIPS it. Today this is masked because the verify path is the sole gate, so the divergence can't bite. But the bake-off and the eval set will consume verifier artifacts (tool-adoption per case is now a measured dimension — 0031 proved the model may never invoke a tool), and the moment any downstream reads `build_trajectory_record`'s tool list instead of the verify path, the silent-skip copy lets a nameless call through undetected — a false measurement in the very tool built to prevent false measurements. Two divergent parsers of the thing the instrument measures violates its core one-source-of-truth contract. This is a BLOCKER, not tech debt: it must clear BEFORE any downstream spec consumes verifier artifacts.

**Ref:** 0031 (live_verifier.py: `extract_tool_names` vs `build_trajectory_record` inline parse; the recorded T20 divergence), the `record_to_codespan` / normalize.py-split dedup precedents (same two-copies-drift hazard), conventions.md (trajectory-verified measurement).

## Invariants

**INVARIANT (one parser, one source of truth):** tool-call-name extraction from a trajectory has exactly ONE implementation. Both the verify path and the trajectory-record builder call it. No second copy, no divergent behavior on any input.

**INVARIANT (the strict behavior wins, per the measurement contract):** the unified parser adopts `extract_tool_names`' STRICT behavior — a tool_call lacking function.name is a `tool-names-unextractable` FAILURE, never a silent skip. A measurement tool must not silently drop the thing it measures; the verify path's fail-loud semantics are correct, the build path's silent-skip is the bug.

**INVARIANT (cutover, not redesign):** change ONLY the tool-name parsing seam. VERIFIER_SCHEMA_VERSION, the six FAILURE_CODES + precedence, the four-facts contract, verify_trajectory's outward behavior on already-valid trajectories stay unchanged. This removes a duplicate and repoints one caller; it adds no capability and changes no passing-trajectory outcome.

**INVARIANT (nothing silently orphaned):** before/after the dedup, grep every consumer of tool-call parsing (verify path, build_trajectory_record, any test or downstream reader) and prove each now routes through the single parser. An import-absence / single-definition assertion, not a prose grep.

## What

- Extract the single canonical tool-name parser (the strict `extract_tool_names` behavior) as the one implementation; delete the inline silent-skip parse in `build_trajectory_record` and repoint it to the canonical one.
- Reconcile the divergent input: a nameless tool_call now yields the SAME result everywhere (`tool-names-unextractable` / typed failure), not skip-in-one-place-fail-in-another. **Critical design constraint:** since `build_trajectory_record` is called live by ExplorerBackend's Scout loop during real runs (not just in eval/verify contexts), the failure on a nameless call must surface as a typed/sentinel field in the returned record (e.g. `build_trajectory_record` returning a dict with a `failed: bool` or `names: list[str] | None` field), NOT as a raised exception. This preserves ExplorerBackend's live control flow and honors the "cutover, not redesign" boundary.
- Regression-pin both call sites against a nameless-tool_call fixture: both must now return a typed failure identically.
- Regression-pin ExplorerBackend's live run behavior: calling build_trajectory_record with a malformed trajectory (containing a nameless tool_call) produces the same downstream control flow and loop state before and after the dedup.
- Confirm every already-passing 0031 trajectory (the real astropy/django runs) still produces byte-identical verifier artifacts — the dedup is behavior-preserving on valid input at the granularity the bake-off will depend on (full VerifierResult field-by-field, not just terminal status/bucket).

## Acceptance Criteria

1. **[unit]** Exactly ONE tool-name parser definition exists, importable/referenceable as a named function/constant; both `build_trajectory_record` and `verify_trajectory` call it (proven by import-identity assertion, not source grep — test that both code paths invoke `extract_tool_names` by the SAME symbol name, e.g. via `inspect.getsource` or an identity check).

2. **[unit]** Divergence closed: a nameless tool_call fixture produces the SAME typed outcome (`tool-names-unextractable` / typed failure) through BOTH the verify path AND `build_trajectory_record` — the 0031 silent-skip is gone. **Critical clarification:** `build_trajectory_record`'s strict-wins failure must surface as a **non-raising typed/sentinel field in the returned record** (e.g. a `failed: bool | None` or `error: str | None` field), NOT as a raised exception, so that ExplorerBackend's live control flow on a malformed model output is unchanged and the 'cutover, not redesign' scope boundary is honored.

3. **[unit]** Behavior-preserving on valid input: a well-formed multi-tool trajectory (ls/grep/symbols/submit_citations names present) parses to the same tool-name list as before through both paths.

4. **[unit]** The strict-wins rule is asserted for both the verify path AND `build_trajectory_record` (scoped to these two known call sites, not a whole-repo universal claim): both return a typed failure (not a silent skip) when a nameless tool_call is encountered; no partial tool list that drops a nameless call without failure is produced by either path.

5. **[unit]** Unchanged contract: VERIFIER_SCHEMA_VERSION, the six FAILURE_CODES + precedence, and verify_trajectory's outcome on the 0031 valid trajectories are unchanged (regression).

6. **[integration]** The real 0031 astropy + django trajectories produce byte-identical (or field-by-field equivalent) verifier artifacts before and after the dedup — compare schema_version, status, failure_reason, tool_names_invoked (incl. ordering), model_identity, model_invoked, terminal_bucket, served_model fields in the persisted VerifierResult JSON, not just the terminal PASSED/FAILED + bucket label. This proves the dedup is behavior-preserving on valid input at the granularity the bake-off will depend on.

7. **[regression]** ExplorerBackend.run()'s live control flow on a trajectory with a nameless tool_call is byte-identical before and after the dedup — the unified parser's failure is carried as data (per AC2), never raises, and the loop's error-handling path is unchanged.

8. **[doc]** Consumer audit recorded: every tool-parsing caller now routes through the single canonical parser; the "one parser, strict-wins" rule codified in conventions.md so the bake-off/eval-set can consume artifacts safely.

## Out of Scope

- The representative eval set (built AFTER this, on the deduped instrument)
- The model bake-off (runs after, consuming these artifacts)
- Tool-adoption analysis / whether the model invokes symbols (a measurement the eval set makes, not this dedup)
- Any verifier schema/failure-code change
- Any Scout/tool/gateway behavior change

## Open Questions

1. **Canonical parser home:** keep the canonical `extract_tool_names` in live_verifier.py (co-located with the verify path) or hoist to a shared trajectory module so both the backend's build_trajectory_record and the verifier import it? explorer_backend.py already imports from live_verifier.py today (confirmed), so the backend→verifier import-direction concern is largely moot; keeping it in live_verifier.py is the smaller, invariant-preserving choice. Decide before plan if hoisting is independently justified; default to no-move unless there's a reason other than avoiding a single import.

2. **OQ2 (ACTION ITEM — audit while here):** Does any OTHER field get parsed from the trajectory in two places (model identity, tiers_run, terminal bucket), or is tool-names the only duplicated parse? Audit while here — if a second divergent parse IS found, it's the same blocker and a new spec should be filed to fix it (parallel to how 0032 was carved out of 0031 rather than folded in), not fixed in this spec, so it doesn't violate the "change ONLY the tool-name parsing seam" invariant. **One divergent parser found usually means the codebase tolerated the pattern; check it didn't happen four times.** AC7's consumer audit will confirm the findings.
