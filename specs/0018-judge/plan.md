---
spec: "0018"
status: planned
strategy: tdd
---

# Plan — 0018 judge (B2 fix: the Verification Gate's relevance judge)

## Approach

B2 is two coupled gate-quality defects: (1) the judge reuses the OOD `scout_model`
finder as a 0–1 scorer, and (2) `_parse_score` grabs the first number anywhere and
clamps, fabricating passes/rejects. The fix introduces an in-distribution
`instruct_model` judge over `settings.lm_model` (new default), makes `_parse_score`
strict (`float | None`, shared by both judges), and turns a `None` parse into a typed
`ScoreParseError` that the gate's *existing* `except` degrades on — never a fabricated
score. `verify_method` finally selects the judge via a dispatch in
`build_verification_gate`, retaining `make_scout_model_judge` (non-default) for the
future finder-vs-instruct A/B.

This is a judging-*mechanism* fix, not a calibration change. Nothing here proves
astropy-12907 now passes end-to-end (that needs a calibrated `verify_threshold` over the
new score distribution — the OQ2 re-run). AC10/AC11 are honestly disclaimed as plumbing.

## File-by-file change list

- `harpyja/config/settings.py`
  - `_VERIFY_METHODS = frozenset({"scout_model", "instruct_model"})`.
  - `verify_method: str = "instruct_model"` (default flip).
  - Update the `verify_method` block comment: default flip + `lm_model` dual-consumer
    coupling note (now backs Deep **and** the gate judge).
- `harpyja/orchestrator/gate.py`
  - New `class ScoreParseError(ValueError)`.
  - `_parse_score(reply) -> float | None` — strict grammar; `None` for anything
    non-conforming (incl. out-of-range and prose-after-number).
  - New `make_instruct_judge(gateway, settings) -> Judge` — constrained bare-number
    prompt; `gateway.complete(messages, model=settings.lm_model, temperature=0)`;
    raises `ScoreParseError` when `_parse_score` returns `None`.
  - `make_scout_model_judge` — same `None → ScoreParseError` degrade (was: fabricate),
    so the retained finder judge shares the strict contract (AC13).
  - `VerificationGate.verify` `except` — branch on `ScoreParseError` **first**
    (distinct WARNING naming the non-conformance, no `exc_info` double, **not** the
    generic message), then `TimeoutError/socket.timeout/URLError` (0017), then generic.
  - Docstrings: judge is the instruct model; strict-parse-degrade + `ScoreParseError`
    contract.
- `harpyja/orchestrator/wiring.py`
  - `_JUDGE_FACTORIES = {"scout_model": make_scout_model_judge, "instruct_model":
    make_instruct_judge}`; `build_verification_gate` dispatches on
    `settings.verify_method` and points the gateway at `settings.lm_model` for the
    instruct default (keeps the `lm_http_timeout_s` threading intact).
- Docs (AC12): `ARCHITECTURE.md` Verification-Gate note, `README.md` if it names
  the gate model, and a new `specs/0018-judge/changelog.md` B2 entry.

## RED → GREEN → REFACTOR sequence

### Step 1 — Settings accepts instruct_model; default flips (RED) — AC1, AC2
- In `harpyja/config/test_settings.py`:
  - `test_settings_verify_method_default_is_instruct_model` — field-default
    **introspection** (`dataclasses.fields(Settings)` default), value `"instruct_model"`.
  - `test_verify_method_instruct_model_loads_clean` — `Settings(verify_method=
    "instruct_model")` constructs.
  - `test_verify_methods_membership_is_scout_and_instruct` — `_VERIFY_METHODS ==
    frozenset({"scout_model", "instruct_model"})`.
  - Amend existing verify-defaults assertion to expect `"instruct_model"`.
- Tests fail: default is still `"scout_model"`; frozenset lacks `"instruct_model"`, so
  constructing with it raises `UnsupportedVerifyMethod`.

### Step 2 — Settings implements the new method + default (GREEN) — AC1, AC2
- `settings.py`: add `"instruct_model"` to `_VERIFY_METHODS`; flip
  `verify_method` default to `"instruct_model"`.
- Existing `scout_model` accepted / unknown-rejected tests still pass unchanged.

### Step 3 — Strict `_parse_score` boundary table (RED) — AC5
- In `harpyja/orchestrator/test_gate.py` (import `_parse_score`):
  - `test_parse_score_conforming_returns_value` — parametrized over the AC5 conforming
    rows: `"0.8"→0.8`, `"0.0"→0.0`, `"1.0"→1.0`, `"1"→1.0`, `"0"→0.0`, `"1."→1.0`,
    `"Score: 0.8"→0.8`, `"Score: 0.8."→0.8`, `"  0.42  "→0.42`.
  - `test_parse_score_nonconforming_returns_none` — parametrized over: `"219"`,
    `"…at line 219…"`, `"Score: 219"`, `"1.2"`, `"-0.1"`,
    `"0, because the span is unrelated"`, `""`, `"n/a"` → all `None`.
- Tests fail: current `_parse_score` returns `0.0` (not `None`) for no-number and
  **clamps** `219→1.0`, `1.2→1.0`, `-0.1→0.0`; never returns `None`.

### Step 4 — Strict parse + typed error (GREEN) — AC5
- `gate.py`: add `class ScoreParseError(ValueError)`. Rewrite `_parse_score` to
  `float | None` with a single-match anchored grammar:
  optional case-insensitive `Score:` label → one number → optional trailing `.` →
  trailing whitespace → end; return the float only if `0.0 <= v <= 1.0`, else `None`;
  `None` when the whole reply does not match.
- Step-3 tests pass. (Existing gate tests inject fake judges, so they are unaffected;
  `make_scout_model_judge` now `return _parse_score(...)` may be `None` — not yet
  exercised by any test until Step 9.)

### Step 5 — Instruct judge: model, prompt, air-gap (RED) — AC3, AC4, AC9
- In `test_gate.py` (import `make_instruct_judge`; capture via injected `transport`):
  - `test_instruct_judge_scores_via_lm_model_not_scout_model` — spy the `model` param
    passed to `complete`; assert `== settings.lm_model` and `!= settings.scout_model`,
    and `temperature == 0`.
  - `test_instruct_judge_prompt_demands_bare_number` — capture the messages; assert the
    instruction text constrains the reply to a single number in `[0,1]` with no prose
    (stable greppable contract).
  - `test_instruct_judge_asserts_local_before_egress` — a non-loopback gateway
    (`api_base=REMOTE`) makes the judge raise `AirGapError` and the transport spy is
    **never** invoked.
- Tests fail: `make_instruct_judge` does not exist (ImportError).

### Step 6 — Implement `make_instruct_judge` (GREEN) — AC3, AC4, AC6, AC9
- `gate.py`: `make_instruct_judge(gateway, settings)` builds a constrained
  system+user prompt (bare `[0,1]` number, no prose), calls
  `gateway.complete(messages, model=settings.lm_model, temperature=0)`, then
  `score = _parse_score(reply)`; `if score is None: raise ScoreParseError(...)`;
  else return `score`. Air-gap is inherited (`complete` asserts local first).
- Step-5 tests pass. AC6's degrade-never-fabricate for the instruct judge is now
  reachable and covered in Step 7.

### Step 7 — Non-conformance degrades, never fabricates; whole-gate (RED then covered) — AC6
- In `test_gate.py`:
  - `test_instruct_judge_nonconforming_reply_degrades_not_fabricates` — gate with a real
    `make_instruct_judge` over a `transport` returning `"219"`; assert
    `outcome.failed is True`, `outcome.passed is False`, and `outcome.score != 1.0`
    (never a fabricated pass or a line-number-derived score).
  - `test_gate_whole_gate_degrades_on_single_nonconforming_reply` — two lined citations,
    the (one) judge reply non-conforming; per D7 the whole call degrades
    (`failed=True`), not a per-span partial pass.
- These are authored alongside Step 6 (they need the judge). They pass once Step 6
  lands via the existing generic `except → failed=True`; the RED reason is the judge's
  prior nonexistence / fabricating parse.

### Step 8 — Single distinct non-conformance WARNING (RED) — AC7
- In `test_gate.py` (reuse `_warning_messages(caplog)`):
  - `test_gate_logs_single_nonconformance_warning` — `_parse_score→None` path logs
    **exactly one** WARNING whose **record message** names the parse non-conformance
    (e.g. `"non-conforming"` / `"parse"`); assert `len(nonconformance_msgs) == 1`.
  - `test_gate_nonconformance_warning_absent_generic_scoring_failed` — assert the
    generic `"scoring failed"` message is **absent** for a `ScoreParseError` (the 0017
    double-emit lesson).
  - `test_gate_nonconformance_warning_distinct_from_timeout` — the non-conformance
    message contains no `"timed out"/"timeout"`.
- Tests fail: without a dedicated branch, `ScoreParseError` (a `ValueError`) hits the
  generic branch and logs `"scoring failed"` — wrong message, and the generic-absent
  assertion fails.

### Step 9 — `ScoreParseError` branch in `verify` (GREEN) — AC7
- `gate.py` `verify` `except`: add `if isinstance(err, ScoreParseError):
  logger.warning("verification gate score parse non-conforming: %r", err)` **first**
  (no `exc_info`, distinct wording), then the existing timeout branch, then generic.
  Return the same `GateOutcome(failed=True, ...)`.
- Step-8 tests pass; existing 0017 timeout/generic tests still pass (branch order
  preserves them).

### Step 10 — Both factories share the strict degrade (RED) — AC13
- In `test_gate.py`:
  - `test_both_judges_degrade_identically_on_nonconforming_reply` — build a gate with
    `make_scout_model_judge` over a `transport` returning `"219"` and, separately, one
    with `make_instruct_judge`; assert **both** yield `GateOutcome(failed=True,
    passed=False)` and the same distinct non-conformance WARNING.
- Fails for the scout judge: `make_scout_model_judge` still `return _parse_score(...)`,
  which now returns `None` → `max([None])` `TypeError` → generic `"scoring failed"`
  branch, not the non-conformance branch.

### Step 11 — Scout judge raises `ScoreParseError` too (GREEN) — AC13
- `gate.py`: `make_scout_model_judge` mirrors the instruct judge — `score =
  _parse_score(reply); if score is None: raise ScoreParseError(...)`.
- Step-10 tests pass; both callers now degrade identically.

### Step 12 — Refactor: extract shared score-or-raise (REFACTOR, optional)
- Extract `_score_or_raise(reply) -> float` (calls `_parse_score`, raises
  `ScoreParseError` on `None`) used by both judges, removing the duplicated guard.
- All tests still pass.

### Step 13 — Correct citation with a good score passes (RED→GREEN) — AC10
- In `test_gate.py`:
  - `test_gate_passes_correct_citation_with_good_score` — a lined citation whose faked
    judge reply is `"0.9"` (≥ `verify_threshold` `0.6`) → `GateOutcome(passed=True,
    failed=False)`. Uses a fake judge/transport; disclaimed in-comment as plumbing, not
    a live-accuracy claim.
- Passes on the plumbing from Steps 4/6; authored to lock the inverted-harm regression.

### Step 14 — Wiring dispatches on `verify_method` (RED) — AC8
- In `harpyja/orchestrator/test_wiring.py`:
  - `test_build_verification_gate_dispatches_instruct_by_default` — with `Settings()`
    the built gate's judge calls `settings.lm_model` (capture the `model` via an
    injected transport on the gate's gateway, or assert the selected factory).
  - `test_build_verification_gate_dispatches_scout_model` — with
    `Settings(verify_method="scout_model")` the judge calls `settings.scout_model`.
- Fails: `build_verification_gate` hardcodes `make_scout_model_judge` over
  `scout_model`, so the default no longer matches the (now instruct) `verify_method`.

### Step 15 — Implement the dispatch (GREEN) — AC8
- `wiring.py`: `_JUDGE_FACTORIES` registry; `build_verification_gate` looks up
  `settings.verify_method`, points the gateway `model` at `settings.lm_model`, and
  builds the matching judge. Retains the `lm_http_timeout_s` threading.
- Step-14 tests pass; existing wiring tests (loopback, timeout) still pass.

### Step 16 — Blast-radius docs + honest changelog (doc) — AC12
- `settings.py` comment (default flip + `lm_model` dual-consumer coupling),
  `gate.py` docstrings (instruct judge + strict-parse/`ScoreParseError` contract),
  `ARCHITECTURE.md`, `README.md` if it names the gate model, and
  `specs/0018-judge/changelog.md` with the B2 entry stating **"B2 *mechanism* fixed;
  end-to-end accuracy (astropy-12907 passes) deferred to the OQ2 re-run"** — never
  "B2 closed" / "false-rejection eliminated."

### Step 17 — Live instruct-judge smoke (integration) — AC11
- In `test_gate.py`: `test_instruct_judge_live_smoke` — `@pytest.mark.integration`;
  with a served `lm_model`, `make_instruct_judge` returns a **parseable** `[0,1]` score
  for a trivially relevant span. **Skips (never fails)** when the endpoint/model is
  absent (probe `/api/tags` or catch connection error → `pytest.skip`). Explicitly a
  wiring/parse smoke, not an accuracy/calibration claim.

## How each AC is covered

- AC1 → Step 1/2 (`test_verify_method_instruct_model_loads_clean`,
  `test_verify_methods_membership_is_scout_and_instruct`, existing unknown-rejected).
- AC2 → Step 1/2 (`test_settings_verify_method_default_is_instruct_model`, introspection).
- AC3 → Step 5/6 (`test_instruct_judge_scores_via_lm_model_not_scout_model`).
- AC4 → Step 5/6 (`test_instruct_judge_prompt_demands_bare_number`).
- AC5 → Step 3/4 (`test_parse_score_conforming_returns_value`,
  `test_parse_score_nonconforming_returns_none`).
- AC6 → Step 6/7 (`test_instruct_judge_nonconforming_reply_degrades_not_fabricates`,
  `test_gate_whole_gate_degrades_on_single_nonconforming_reply`).
- AC7 → Step 8/9 (`test_gate_logs_single_nonconformance_warning`,
  `test_gate_nonconformance_warning_absent_generic_scoring_failed`,
  `test_gate_nonconformance_warning_distinct_from_timeout`).
- AC8 → Step 14/15 (`test_build_verification_gate_dispatches_instruct_by_default`,
  `test_build_verification_gate_dispatches_scout_model`).
- AC9 → Step 5/6 (`test_instruct_judge_asserts_local_before_egress`).
- AC10 → Step 13 (`test_gate_passes_correct_citation_with_good_score`).
- AC11 → Step 17 (`test_instruct_judge_live_smoke`, integration skip-not-fail).
- AC12 → Step 16 (docs + changelog).
- AC13 → Step 10/11 (`test_both_judges_degrade_identically_on_nonconforming_reply`).

## Delegation

- Steps 1–15 → executed in the main session (single-package Python TDD; matches
  the repo's `uv run pytest` / ruff toolchain and the gate/config surface).
- Step 16 (docs) and Step 17 (integration smoke) → same session;
  the changelog wording is honesty-critical and best written by whoever landed the code.

## Risk

- **`ScoreParseError ⊂ ValueError` reaches the generic branch first.** → Mitigation:
  the `except` must test `isinstance(err, ScoreParseError)` **before** the timeout and
  generic branches; Step 8's generic-absent assertion is the guard against regression.
- **`_parse_score` regex drift** (e.g. accidentally matching `"1.2"` or `".5"` or prose).
  → Mitigation: AC5's executable table is authored RED-first and every row is an
  assertion; anchor the regex (`^…$`) and single-match.
- **Double WARNING via `caplog.text` false-green.** → Mitigation: assert on
  `record.getMessage()` via the existing `_warning_messages` helper, never `caplog.text`
  (the 0017 lesson).
- **Default-flip breaks the existing `verify_method == "scout_model"` assertion.** →
  Mitigation: Step 1 amends the existing verify-defaults assertion in the same RED.
- **`lm_model` dual-consumer coupling** (a Deep tune silently retunes the gate). →
  Mitigation: documented explicitly in the settings comment and changelog (AC12).
- **Over-claiming closure.** → Mitigation: AC12 changelog wording is "mechanism fixed,
  accuracy deferred"; AC10/AC11 comments disclaim plumbing-not-accuracy.
