---
spec: "0014"
status: planned
strategy: tdd
---

# Plan — 0014 AdapterParseError

Map dspy `AdapterParseError` out of the Deep/RLM driver to a typed
`DeepUnavailable(parse-error)` degrade, then make that degrade visible in the eval
report (mirroring spec 0011's Scout machinery), bumping the report schema
`0012/1 → 0013/1`. Steps are ordered producer→sink along the data path:
cause taxonomy → RLM seam → orchestrator routing (regression lock; already
cause-agnostic) → report schema → runner aggregation → swebench sibling → live
integration → refactor → close deliverable.

Key design facts confirmed by reading the code:

- **Seam**: only the `rlm(query=...)` call in `harpyja/deep/rlm.py`
  `RlmBackend.run` (line 94). `_assert_local` (line 91) and `_rlm_factory(...)`
  (line 93) stay outside the catch so `AirGapError` / config faults propagate.
  `DeepUnavailable` raised here flows untouched through `DeepRunner.run` (catches
  only `DeepBudgetExceeded`) and `DeepEngine.run` up to `locate`'s
  `_locate_deep` / `_run_deep`, which already catch `DeepUnavailable` and build
  `deep-degraded:{err.cause}` notes generically — so **no orchestrator code
  change is needed**, only a regression lock.
- **dspy-absent-safe narrow catch**: `AdapterParseError.__init__` needs heavy
  args (`adapter_name`, a real `Signature`, `lm_response`), and the module must
  keep its no-top-level-`import dspy` rule. Resolve the class lazily into a tuple;
  `except ()` is valid Python and catches nothing, so the catch stays genuinely
  narrow (no bare `except`) and the module still imports when dspy is absent:

  ```python
  def _adapter_parse_error_types() -> tuple[type, ...]:
      try:
          from dspy.utils.exceptions import AdapterParseError
      except Exception:
          return ()
      return (AdapterParseError,)
  ...
      try:
          prediction = rlm(query=_compose_prompt(query, seed))
      except _adapter_parse_error_types() as err:
          raise DeepUnavailable(PARSE_ERROR) from err
  ```
- **Degrade observation path (production→aggregation, chosen explicitly)**: Deep
  needs **no `last_tally` side-channel** like Scout's. Scout's `ScoutTally` is for
  *shape distribution* (spanned/filelevel/dropped), not degrade counting; the
  Scout degrade itself is already observed from `result.notes` via
  `_is_scout_degraded`. Deep mirrors that exactly: the `deep-degraded:<cause>`
  string in `result.notes` is the single production→aggregation path. Add a
  sibling `_is_deep_degraded(notes)`; no engine/tally plumbing.
- **Single producer for the new report fields**: `aggregate_outcomes`
  (`harpyja/eval/runner.py`) is the only place the aggregate block is built; both
  `run_dataset` and `run_swebench` call it, and `build_report`/`validate_report`
  are the only schema sinks. `run_swebench_sweep` builds a `sweep`/`recommendation`
  shape that is never validated against `_AGGREGATE_FIELDS`, so it needs no change.
  Grep gate before coding: `grep -rn "aggregate_outcomes\|_AGGREGATE_FIELDS\|scout_degrade" harpyja/eval`.

## Test-first sequence

### P1 — Deep `parse-error` cause constant (RED)
- Add to `harpyja/deep/test_deep.py`:
  - `test_deep_unavailable_parse_error_cause_is_stable` — assert
    `errors.PARSE_ERROR == "parse-error"` and that it is distinct from
    `SANDBOX_ABSENT` / `RLM_DOWN` / `BACKEND_ERROR` (a sibling, not a replacement).
- Tests fail: `PARSE_ERROR` does not exist in `harpyja/deep/errors.py` (ImportError).
- Satisfies: AC2.

### P2 — Add the cause constant (GREEN)
- `harpyja/deep/errors.py`: add `PARSE_ERROR = "parse-error"` next to the existing
  `SANDBOX_ABSENT` / `RLM_DOWN` / `BACKEND_ERROR`, with a comment that a named,
  narrow-caught seam earns its own cause while unforeseen exceptions still fold to
  `BACKEND_ERROR`.
- P1 passes.
- Satisfies: AC2.

### P3 — RLM seam: AdapterParseError → DeepUnavailable(parse-error) (RED)
- Add to `harpyja/deep/test_deep.py` (reuse the existing `_FakeRlm` / `_Prediction`
  helpers; import `AdapterParseError` directly — dspy is a pinned `>=3.2.1` dep —
  and construct an instance via `AdapterParseError.__new__(AdapterParseError)` to
  avoid the heavy constructor):
  - `test_rlm_backend_adapter_parse_error_maps_to_deep_unavailable` — a factory
    whose `rlm(query=...)` raises `AdapterParseError`; assert `RlmBackend.run`
    raises `DeepUnavailable` with `.cause == errors.PARSE_ERROR` (the raw
    `AdapterParseError` does **not** escape — no crash).
  - `test_rlm_backend_parse_error_preserves_cause` — assert the raised
    `DeepUnavailable.__cause__` **is** the original `AdapterParseError` instance.
  - `test_rlm_backend_unrelated_exception_not_swallowed` — a factory whose `rlm`
    raises `RuntimeError("bad config")`; assert `RuntimeError` propagates and is
    **not** wrapped as `DeepUnavailable` (narrow-catch guard).
  - `test_rlm_backend_weak_answer_stays_result` — a factory returning a prediction
    with a weak/empty `answer`; assert `run` returns a (possibly empty) `list`,
    **not** a `DeepUnavailable` (typed-failure-only boundary at the seam).
  - `test_rlm_backend_module_has_no_toplevel_dspy_import` — read the module source
    and assert no top-level `import dspy` / `from dspy` (the lazy-import rule the
    seam must honor); complements the existing
    `test_rlm_backend_module_imports_without_dspy`.
- Tests fail: the seam does not catch `AdapterParseError` yet, so the raw
  exception escapes and the `DeepUnavailable`-expecting asserts fail.
- Satisfies: AC1, AC3, AC4, AC9.

### P4 — Implement the narrow seam wrap (GREEN)
- `harpyja/deep/rlm.py`: add the lazy `_adapter_parse_error_types()` helper and
  wrap **only** the line-94 `rlm(query=...)` call in
  `except _adapter_parse_error_types() as err: raise DeepUnavailable(PARSE_ERROR) from err`
  (import `DeepUnavailable` / `PARSE_ERROR` from `harpyja.deep.errors`). Leave
  `self._assert_local(...)` and `self._rlm_factory(...)` outside the try.
- All P3 tests pass; the existing `test_rlm_backend_airgap_blocks_before_factory`
  still passes (AirGapError raised before the seam).
- Satisfies: AC1, AC3, AC4, AC9.

### P5 — Orchestrator routing regression lock (RED→GREEN, no production change)
- Add to `harpyja/orchestrator/test_locate.py` (reuse the existing
  `_UnavailableDeep` double, importing `PARSE_ERROR`):
  - `test_locate_deep_parse_error_degrades_to_scout` — `mode="deep"` with
    `deep_engine=_UnavailableDeep(PARSE_ERROR)` and a wired Scout; assert
    `tiers_run == [0, 1]` (floor actually reached, not `[0,2]`) and
    `result.notes.startswith("deep-degraded:parse-error")`.
  - Extend `test_locate_deep_distinct_cause_notes` (or add
    `test_locate_deep_parse_error_note_is_distinct`) so the cause set includes
    `"deep-degraded:parse-error"` alongside the existing
    `sandbox-absent`/`rlm-down`/`backend-error`.
- RED before P2 (the test imports `PARSE_ERROR`); GREEN immediately after P2/P4
  because `_locate_deep`/`_run_deep` are already cause-agnostic — this step
  **proves no routing change is required** and locks AC5's tiers_run + note.
- Satisfies: AC1, AC2, AC5.

### P6 — Report schema bump `0012/1 → 0013/1` + deep degrade fields (RED)
- Edit/add in `harpyja/eval/test_report.py`:
  - Update the existing `test_report_schema_version_is_0012` →
    `test_report_schema_version_is_0013`, asserting `SCHEMA_VERSION == "0013/1"`.
  - `test_deep_degrade_fields_present_with_defaults` — `build_report` output's
    aggregate contains `deep_degrade_count` (== 0) and `deep_degrade_rate`
    (== `None`) via the centralized defaults; `validate_report` does not raise.
  - `test_0012_and_0013_aggregate_shapes_both_validate` — a legacy aggregate
    omitting the deep fields (filled by defaults) **and** a fully populated 0013
    aggregate (`deep_degrade_count=2, deep_degrade_rate=0.5`) both pass the single
    `validate_report`.
- Tests fail: `SCHEMA_VERSION` is `"0012/1"`; `deep_degrade_*` are absent from
  `_AGGREGATE_FIELDS` / `_AGGREGATE_DEFAULTS`.
- Satisfies: AC6, AC7, AC10.

### P7 — Add the schema fields + defaults (GREEN)
- `harpyja/eval/report.py`:
  - Bump `SCHEMA_VERSION = "0013/1"` (update the module comment to note the
    additive Deep-degrade twins).
  - Append `"deep_degrade_count"`, `"deep_degrade_rate"` **last** in
    `_AGGREGATE_FIELDS`.
  - Add `"deep_degrade_count": 0` and `"deep_degrade_rate": None` to
    `_AGGREGATE_DEFAULTS` (null-with-zero-count default = the "not computed" shape).
- All P6 tests pass.
- Satisfies: AC6, AC7, AC10.

### P8 — Runner aggregation: deep degrade count/rate + union dominance (RED)
- Add to `harpyja/eval/test_runner.py` (add a `_ParseErrorDeep` double whose
  `run(query)` raises `DeepUnavailable(PARSE_ERROR)`, and a `_degrade_deep_stack`
  with `deep_engine` wired so `mode="deep"`/auto floors through Deep):
  - `test_runner_reports_deep_degrade_count_and_rate` — two deep-degraded cases →
    `agg["deep_degrade_count"] == 2`, `agg["deep_degrade_rate"] == 1.0`.
  - `test_runner_deep_degrade_rate_null_with_zero_denominator` — empty case list →
    `agg["deep_degrade_rate"] is None` and `agg["deep_degrade_count"] == 0`.
  - `test_runner_degraded_dominated_counts_case_once_when_both_degrade` — a case
    whose notes carry **both** `scout-degraded:` and `deep-degraded:` is counted
    **once** for `degraded_dominated`; assert `scout_degrade_rate` and
    `deep_degrade_rate` remain separately attributed while the combined per-case
    degraded rate drives `degraded_dominated`.
- Tests fail: `aggregate_outcomes` emits no `deep_degrade_*` keys and
  `degraded_dominated` keys off the scout-only rate.
- Satisfies: AC6, AC11.

### P9 — Compute deep degrade + union dominance (GREEN)
- `harpyja/eval/runner.py`:
  - Add `_is_deep_degraded(notes)` mirroring `_is_scout_degraded` (membership of
    `"deep-degraded"` in `notes`).
  - In `aggregate_outcomes`: compute `deep_degrade_count` /
    `deep_degrade_rate` (null-with-count on zero denominator, identical shape to
    the scout twins); compute a **combined** per-case degraded count as the union
    `_is_scout_degraded(notes) or _is_deep_degraded(notes)` (counted once per
    case), derive the combined rate, and set
    `degraded_dominated = combined_rate is not None and combined_rate > threshold`.
    Keep `scout_degrade_count` / `scout_degrade_rate` unchanged for attribution;
    add `deep_degrade_count` / `deep_degrade_rate` to the returned dict.
- All P8 tests pass; existing scout-only degrade tests still pass (a scout-only
  run's combined rate equals its scout rate).
- Satisfies: AC5 (visibility channel), AC6, AC11.

### P10 — Swebench sibling sink coverage (RED→GREEN regression lock)
- Add to `harpyja/eval/test_swebench_runner.py` (reuse the existing degrade
  fixtures, adding a deep-degrade variant):
  - `test_swebench_reports_deep_degrade_fields` — a `run_swebench` report's
    aggregate carries `deep_degrade_count` / `deep_degrade_rate` populated by the
    shared `aggregate_outcomes`.
  - `test_swebench_degraded_dominated_counts_deep_degrade` — a Deep-degraded
    majority run flags `degraded_dominated` and carries `"degraded-dominated"` in
    `reliability_notes` (proves the sibling driver is not a missed consumer).
- RED before P9; GREEN after P9 with **no swebench_eval.py change** required
  (single producer `aggregate_outcomes`) — the step exists to prove the recurring
  missed-consumer lesson is honored. If the grep gate reveals any other field
  consumer, that consumer gets its own RED→GREEN here.
- Satisfies: AC7, AC11 (swebench path).

### P11 — Live integration: auto-mode degrades, no crash (RED→GREEN, skip-not-fail)
- Add `@pytest.mark.integration` test in `harpyja/deep/test_deep_integration.py`:
  - `test_deep_auto_parse_error_degrades_not_crash` — skip-not-fail when dspy is
    absent (`pytest.skip` via the existing `_deep_stack_available` gate, or a
    narrower dspy-only guard). Build a `RlmBackend` with an **injected**
    `rlm_factory` whose returned callable raises a real `AdapterParseError` at
    `rlm(query=...)` (deterministic fault, not a model crash); wrap it in a real
    `DeepEngine` and drive `locate(mode="auto")` (or `run_swebench`); assert the
    run **completes without raising**, `tiers_run` floors below Tier-2, and the
    `deep-degraded:parse-error` note / `deep_degrade_rate` is recorded. Document
    the real-weights variant model names (`hf.co/dstolf/FastContext-1.0-4B-{SFT,RL}-Q8_0-GGUF:latest`)
    as an operator opt-in, not the default fault source.
- RED before P4/P9 (raw AdapterParseError would crash the run); GREEN after.
- Satisfies: AC8. (Confirms the AC5 `mode=fast` workaround can revert to
  `mode=auto`.)

### P12 — Refactor (optional)
- Factor the degrade-note membership checks so `_is_scout_degraded` /
  `_is_deep_degraded` share one predicate (e.g. `_has_degrade_note(notes, prefix)`),
  removing the count duplication in `aggregate_outcomes`. Confirm
  `compose_reliability_notes` is unchanged. Run `pytest harpyja -q` (and the
  integration subset where deps allow) — all tests still pass.

### P13 — Close deliverable (AC12, not a pytest target)
- Record the standing convention in `.speccraft/conventions.md` via
  `memory-keeper`: *every new tier/backend typed-degrade floor must report a
  `<tier>-degraded:<cause>` rate and feed `degraded_dominated`.* Tracked as a
  required closeout gate so the visibility rule is not re-litigated at the next
  floor.

## Delegation

- P4, P11 → delegate to `deep-driver` agent if available (reason: dspy/RLM seam +
  sandbox integration expertise); otherwise implement inline — the seam is small
  and fully specified.
- P7, P9, P10 → `eval-harness` agent (reason: report schema + aggregation +
  swebench sibling are its strength area; the missed-consumer lesson lives there).
- P13 → `memory-keeper` (reason: owns `.speccraft/conventions.md`; this is its
  explicit close deliverable).

## Risk

- **Bare-except creep at the seam** → mitigation: the lazy
  `_adapter_parse_error_types()` tuple keeps the catch narrowed to the single
  named class; P3's `test_rlm_backend_unrelated_exception_not_swallowed` is the
  standing guard (AC4).
- **dspy-absent unit run / heavy AdapterParseError constructor** → mitigation:
  module resolves the class lazily (`except ()` catches nothing when absent);
  unit tests instantiate via `AdapterParseError.__new__` to skip the constructor;
  the integration test is skip-not-fail.
- **Schema bump breaks an existing version-pin test** → mitigation: P6 explicitly
  updates `test_report_schema_version_is_0012`; grep
  `grep -rn '0012/1\|SCHEMA_VERSION' harpyja` before P7 to catch any other pin.
- **degraded_dominated double-counting when both tiers floor** → mitigation: P8's
  union test asserts a single count per case; the combined rate (not the sum of
  per-tier rates) drives the flag.
- **Missed consumer of the new fields** → mitigation: P10 + the grep gate on
  `aggregate_outcomes` / `_AGGREGATE_FIELDS`; `run_swebench_sweep` confirmed not a
  validated-aggregate sink.

## AC → step coverage

| AC | Steps |
|----|-------|
| AC1 (parse-error → DeepUnavailable, no crash) | P3, P4, P5 |
| AC2 (distinct stable cause) | P1, P2, P5 |
| AC3 (typed-failure-only; weak stays Tier-2) | P3, P4 |
| AC4 (narrow catch) | P3, P4 |
| AC5 (existing path; tiers_run = floor; visible via note + deep_degrade_rate) | P5, P8, P9 |
| AC6 (first-class deep-degrade rate; degraded_dominated aware) | P6, P7, P8, P9 |
| AC7 (schema 0013 additive; runner + swebench populate) | P6, P7, P10 |
| AC8 (integration auto, deterministic fault, no crash) | P11 |
| AC9 (cause preserved via `from err`) | P3, P4 |
| AC10 (both shapes validate; null-with-count) | P6, P7 |
| AC11 (union, count once; per-tier rates separate) | P8, P9, P10 |
| AC12 (convention recorded — close deliverable) | P13 |
