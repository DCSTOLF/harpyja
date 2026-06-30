---
spec: "0014"
closed: 2026-06-30
---

# Changelog — 0014 AdapterParseError

## What shipped vs spec

- Mapped dspy `AdapterParseError` out of the Deep/RLM driver to a typed
  `DeepUnavailable(parse-error)` degrade and made that degrade first-class-visible in
  the eval report, mirroring spec 0011's Scout machinery. Full producer→sink path
  delivered as specced; all 12 ACs satisfied (AC12 is this close deliverable).
- `harpyja/deep/errors.py` — new stable cause `PARSE_ERROR = "parse-error"`, a
  **sibling** of `BACKEND_ERROR` under `DeepUnavailable` (a named, narrow-caught seam
  earns its own cause; truly-unforeseen exceptions still fold to the `BACKEND_ERROR`
  catch-all). (AC2)
- `harpyja/deep/rlm.py` — lazy `_adapter_parse_error_types()` resolving
  `dspy.utils.exceptions.AdapterParseError` (pinned vs dspy 3.2.1; the single class all
  four adapters raise; `except ()` catches nothing when dspy is absent, preserving the
  module's no-top-level-`import dspy` rule). Wraps **only** the `rlm(query=...)` seam →
  `raise DeepUnavailable(PARSE_ERROR) from err`. `_assert_local` (AirGapError floor) and
  `_rlm_factory` (config faults) stay outside the catch; `parse_citations` never raises.
  (AC1, AC3, AC4, AC9)
- `harpyja/orchestrator/locate.py` — **no change** (already cause-agnostic;
  `_locate_deep`/`_run_deep` build `deep-degraded:{cause}` notes generically). Proven by
  a routing regression lock (`test_locate_deep_parse_error_degrades_to_scout`,
  `tiers_run == [0,1]`, not `[0,2]`). (AC1, AC5)
- `harpyja/eval/report.py` — `SCHEMA_VERSION 0012/1 → 0013/1`; additive
  `deep_degrade_count` / `deep_degrade_rate` appended **last** in `_AGGREGATE_FIELDS` +
  `_AGGREGATE_DEFAULTS` (null-with-zero-count default; both old- and new-shape blocks
  pass the single loud validator). (AC6, AC7, AC10)
- `harpyja/eval/runner.py` — shared `_has_degrade_note` predicate; `_is_deep_degraded`
  twin of `_is_scout_degraded`; `deep_degrade_count`/`deep_degrade_rate`;
  `degraded_dominated` now keys off the **union** of scout+deep per-case degrades (a case
  counted **once** even when both tiers floor), per-tier rates kept separate for
  attribution. (AC5, AC6, AC11)
- `harpyja/eval/swebench_eval.py` — **no change** (single producer `aggregate_outcomes`;
  sibling driver covered automatically, proven by a lock test in
  `test_swebench_runner.py`). (AC7, AC11)

## Deviations from the spec/plan

- A pre-existing `test_report_schema_version_is_0012` exact-version pin (not named by
  the plan, though the plan's risk note flagged the class) was converted to a
  `test_report_schema_version_bumped_past_0012` ratchet, matching the codebase's
  established ratchet pattern; the new exact pin is `test_report_schema_version_is_0013`.
- AC12 is a `[close-deliverable]` (this step), not a pytest target.
- `ContextWindowExceededError` (the only sibling dspy exception) was deliberately left
  OUT of scope as a future `deep-degraded:context-window` cause — folding it into
  `parse-error` would violate the narrow-catch invariant.

## Files touched

- harpyja/deep/errors.py
- harpyja/deep/rlm.py
- harpyja/deep/test_deep.py
- harpyja/deep/test_deep_integration.py
- harpyja/eval/report.py
- harpyja/eval/runner.py
- harpyja/eval/test_report.py
- harpyja/eval/test_runner.py
- harpyja/eval/test_swebench_runner.py
- harpyja/orchestrator/test_locate.py
- .speccraft/index.md

## Tests

- 699 unit pass + ruff clean.
- Integration `test_deep_auto_parse_error_degrades_not_crash` (deterministic injected
  fault, skip-not-fail) passes — real `RlmBackend` → `DeepEngine` → `locate(mode=auto)`
  completes with the degrade recorded; the AC5 `mode=fast` workaround can revert to
  `mode=auto`.

## ADR proposed for history.md

See the dated block below (proposed; the parent applies).

## Conventions proposed

- New (P13 standing convention): every new tier/backend typed-degrade floor must report
  a `<tier>-degraded:<cause>` rate as a first-class aggregate field AND feed
  `degraded_dominated` (the union, counted once per case). Generalizes the spec-0011
  Scout machinery now that Deep is the second such floor. (See proposal below.)
