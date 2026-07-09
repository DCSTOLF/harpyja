---
spec: "0032"
status: planned
strategy: tdd
---

# Plan — 0032 trajectory-parser (dedup the tool-name parser)

## Design decisions (grounding the steps)

- **Canonical home (OQ1): no move.** Keep `extract_tool_names` in
  `harpyja/eval/live_verifier.py`. `explorer_backend.py` already imports
  `build_trajectory_record` from `live_verifier` (line 26), so no new import
  direction is created. Hoisting adds churn without invariant value — default
  no-move stands.
- **Typed-sentinel, non-raising (AC2/AC7).** `build_trajectory_record` is called
  LIVE by `ExplorerBackend.run()` (explorer_backend.py:291) and must never raise
  on a malformed model output. The cutover repoints it to `extract_tool_names`
  and surfaces the strict failure as **data**: an additive
  `tool_names_failure: str | None` key on the returned record dict
  (`None` on success, `"tool-names-unextractable"` on a nameless tool_call),
  with `tool_names_invoked` becoming `[]` on failure. This is a key on the
  *internal partial-record dict only* — it does NOT touch `VERIFIER_SCHEMA_VERSION`
  nor the persisted VerifierResult artifact (AC5/AC6 preserved), because
  `run_verified_case` re-assembles `traj`/`artifact` from explicit fields
  (model_turns, served_model), never by copying the record wholesale.
- **Known behavior shift, and it is the point.** The old inline parse skipped a
  nameless call and KEPT later names; `extract_tool_names` returns `([], False, …)`
  on the first nameless call (strict-wins). On all-valid input the two are
  identical — the AC3/AC6 pins use all-valid fixtures, so they are unaffected.
- **AC7 control flow is byte-identical for free.** `ExplorerBackend` only stores
  `self.last_trajectory = build_trajectory_record(...)` and never branches on its
  contents. Adding a data key and returning (never raising) leaves `run()`'s
  outcome, citations, and degrade paths untouched.

## Test-first sequence

### Step 1 — Pin behavior-preserving invariants (CHARACTERIZATION, stays GREEN)
Author regression pins that must survive the cutover unchanged. All pass NOW
(pre-refactor); their job is to fail loudly if Step 4 alters valid-input behavior
or the frozen contract.
- Add to `harpyja/eval/test_live_verifier.py`:
  - `test_build_trajectory_record_valid_multitool_names_preserved` (AC3) — a
    well-formed history with `ls`/`grep`/`symbols`/`submit_citations` yields
    `tool_names_invoked == ["ls","grep","symbols","submit_citations"]`
    (ordered-unique) and, post-cutover, `tool_names_failure is None`.
  - `test_verifier_schema_version_and_failure_codes_frozen` (AC5) — assert
    `VERIFIER_SCHEMA_VERSION == "0031/1"`, `FAILURE_CODES` equals the exact
    six-member frozenset, and `FAILURE_PRECEDENCE` equals the exact ordered list.
  - `test_verify_result_field_by_field_stable_on_valid_trajectory` (AC6) — snapshot
    `verify_trajectory(_traj()).to_dict()` (minus `timestamp`) against a literal
    golden dict covering schema_version, status, failure_reason,
    tool_names_invoked (incl. order), model_identity, model_invoked,
    terminal_bucket, served_model. This is the field-by-field artifact-equivalence
    guard the bake-off depends on, expressed as a hermetic fixture (no live stack).
- Tests pass now: they lock current behavior before any code moves.

### Step 2 — Divergence, identity, typed-failure (RED)
- Add to `harpyja/eval/test_live_verifier.py`:
  - `test_build_trajectory_record_delegates_to_canonical_extract_tool_names` (AC1)
    — monkeypatch `live_verifier.extract_tool_names` to a stub returning
    `(["__SENTINEL__"], True, None)`; call `build_trajectory_record` with a valid
    history; assert `record["tool_names_invoked"] == ["__SENTINEL__"]`. Import-identity
    proof: only a call to the module-level symbol can observe the patch.
  - `test_build_trajectory_record_nameless_tool_call_returns_typed_failure_without_raising`
    (AC2/AC4) — history with `{"tool_calls":[{"function":{}}]}`; assert the call
    does NOT raise, `record["tool_names_failure"] == "tool-names-unextractable"`,
    and `record["tool_names_invoked"] == []` (no partial list that drops a nameless
    call silently).
  - `test_nameless_tool_call_yields_identical_typed_outcome_in_both_paths` (AC2) —
    assert `verify_trajectory(_traj(model_turns=[nameless])).failure_reason`
    equals `build_trajectory_record([nameless], 1)["tool_names_failure"]`.
- Tests fail: today `build_trajectory_record` runs an INLINE parse (lines 337–347)
  that (a) ignores the module symbol so the monkeypatch is unobserved, (b) silently
  skips the nameless call, and (c) emits no `tool_names_failure` key (KeyError).

### Step 3 — ExplorerBackend live-run regression (RED)
- Add to `harpyja/scout/test_explorer_backend.py`:
  - `test_run_nameless_tool_call_carries_typed_failure_as_data_not_raise` (AC7) —
    drive the backend with fakes whose model turn emits a tool_call lacking
    `function.name`; assert `backend.run(...)` follows the SAME terminal path as an
    equivalent named run (no new exception type, same outcome/citations, same
    `last_turns_used`), AND `backend.last_trajectory["tool_names_failure"] ==
    "tool-names-unextractable"`.
- Test fails on the sentinel assertion: today `last_trajectory` has no
  `tool_names_failure` key (the inline parse silently produced a partial/empty list).
  The control-flow assertions in the same test pass now and must keep passing —
  they pin AC7's "byte-identical control flow" half across the cutover.

### Step 4 — The cutover (GREEN)
- Edit `harpyja/eval/live_verifier.py`, `build_trajectory_record`, lines 336–355:
  replace the inline `for turn in history … seen` loop with:
  - `names, _proven, reason = extract_tool_names({"model_turns": history})`
  - `record["tool_names_invoked"] = names`
  - `record["tool_names_failure"] = reason`  (None on success, code on failure)
  Delete the duplicated `tool_names = []; seen = set()` block. No other function,
  no schema constant, no precedence list changes.
- Result: Step 2 + Step 3 RED tests pass; Step 1 pins stay green; the full existing
  `test_live_verifier.py`, `test_live_verifier_integration.py`, and
  `test_explorer_backend.py` suites stay green.

### Step 5 — Consumer audit + codify invariant (REFACTOR / DOC)
- Add to `harpyja/eval/test_live_verifier.py`:
  - `test_single_tool_name_parser_definition_by_symbol_audit` (AC8) — via
    `inspect.getsource(build_trajectory_record)` assert it contains
    `extract_tool_names(` and NO longer contains an inline `seen = set()` tool-name
    loop; assert `extract_tool_names` is the sole module-level definition. A
    symbol/source-identity assertion, not a prose grep.
- Edit `.speccraft/conventions.md`: codify the "one parser, strict-wins" rule —
  tool-call-name extraction has exactly ONE implementation (`extract_tool_names`);
  both the verify path and `build_trajectory_record` call it; a nameless tool_call
  is a `tool-names-unextractable` typed failure (surfaced as data in the live
  builder, raised-as-status in the verify path), never a silent skip. Reference
  spec 0032 AC1/AC2/AC8.
- Record OQ2 audit finding in this plan (below): tool-names was the ONLY duplicated
  parse. All tests still pass.

## OQ2 audit (checked while here — required by spec)

`verify_trajectory` sources every other fact through a single dedicated extractor
with no second copy: `extract_model_identity` (identity), `extract_model_invoked`
(tiers_run + model_turns), `extract_terminal_bucket` (bucket). `run_verified_case`
assembles `tiers_run`/`terminal_bucket` from `classify_case`/literals, not a rival
parser. `explorer_backend.py` only reads `_last_served_model` (served identity) and
delegates tool-names to `build_trajectory_record`. **Finding: tool-names was the
sole duplicated parse.** No parallel spec needs to be filed. Step 5's audit test
codifies this so a fourth copy cannot creep back in.

## Delegation

- Steps 1–4 → keep in-house (single-file, tightly-coupled to the verifier contract;
  no strong external-agent match).
- Step 5 conventions.md edit → author-reviewed doc change; no delegation.

## Risk

- **Sentinel key leaks into persisted artifact (would break AC5/AC6).** Mitigation:
  Step 1's field-by-field VerifierResult pin plus the integration path builds
  `artifact` from explicit fields — the new key lives only on the internal record;
  the pins fail loudly if it ever reaches `to_dict()`.
- **Mixed valid-then-nameless history changes from partial-list to empty.** This is
  the intended strict-wins closure, not a regression. Mitigation: AC3/AC6 pins use
  all-valid fixtures; Step 2/Step 3 assert the empty+typed-failure outcome is the
  new contract on nameless input.
- **AC6 needs a live stack for the real astropy/django run.** Mitigation: the
  hermetic field-by-field golden pin (Step 1) captures the same field granularity
  offline; the existing live integration test remains the skip-gated confirmation.
