---
spec: "0025"
status: planned
strategy: tdd
---

# Plan — 0025 removal (FastContext removal + Scout cutover to the explorer backend)

## Approach

A staged deletion, not a redesign. Every edit either **repoints a caller** onto the
already-shipped explorer or **removes dead code behind an executable absence guard**.
The explorer loop, the `ScoutBackend`/`Locator` boundary, `ScoutEngine`, the gate,
matrix, and orchestrator are untouched. Tests are Python `pytest`, colocated
`test_*.py`; RED steps expect `uv run pytest` failure, GREEN expect green.

The spec's two invariants drive the ordering:

- **Migrate before you delete.** Two deletions would take a still-needed capability
  with them. They are sequenced as migrations that prove equivalence FIRST:
  the turns-used diagnostic (AC3) gets a native explorer seam and the 0022 probe is
  repointed onto it before the `agent_factory=` seam is cut; `normalize.py` (AC5)
  keeps the shared tally core and removes ONLY the FC-era suffix-recovery.
- **Suite stays green at every step.** The canonical-factory swap keeps a transitional
  no-op `agent_factory=` kwarg alive across the AC3 migration; the FC-only Settings
  fields are removed only when their sole consumer (`client.py`) is deleted; the
  `SCHEMA_VERSION` bump updates every version-pinned test in lockstep.

Ordering (the safety sequence): (1) canonical-factory swap + explorer wiring →
(2) surface the turns-used seam + migrate the diagnostic + prove equivalent →
(3) `normalize.py` suffix-recovery removal (two-sided proof) → (4) `scout_model`
audit / drift guard → (5) report-schema retirement → (6) delete the FC surface behind
the import-absence guard (including the FC-only Settings fields, now orphaned) →
(7) drop the dependency + clean `uv sync` → (8) the live cutover integration test.

### Key seams (verified in code)

- `harpyja/scout/wiring.py` — `build_scout_engine` (FastContext, ~34-76) becomes the
  canonical explorer factory; `build_explorer_scout_engine` (~79-125) is deleted, its
  body folded in (keeps its `gateway=` / `model_call=` params so AC8 can pin the tag).
- `harpyja/scout/explorer_loop.py` — `LoopResult.turns_used` (line 59) already exists;
  it is surfaced as a per-run seam `ExplorerBackend.last_turns_used` →
  `ScoutEngine.last_turns_used`, mirroring the `last_tally` side-channel
  (`engine.py:64,84`).
- `harpyja/eval/locate_probe.py` — the only remaining FC-factory caller
  (`build_scout_only_stack`, :155, `agent_factory=`), the trajectory turns machinery
  (`count_turns` :72, `counting_agent_factory` :98, `_CountingAgent`, `turns_sink`,
  `_resolve_turns` :235), and `scout_stack_available` (:419, hard-imports `fastcontext`).
- `harpyja/scout/normalize.py` — remove ONLY `_recover_suffix` (:28) + `MIN_TAIL_SEGMENTS`
  (:20); KEEP `normalize_spans` / `normalize_spans_with_tally` / `ScoutTally` /
  `last_tally` (the shared ScoutEngine path feeding `runner.py`, `locate_probe.py`, and
  the 0022 `locate_accuracy.py`). Recovered counts become structurally zero.
- `harpyja/config/settings.py` — KEEP `scout_model` (:91, served 0018 gate baseline);
  remove `scout_max_tokens`/`scout_temperature`/`scout_reasoning_effort` (:92-94) in the
  FC-surface phase (sole consumer is `client.py:_fc_env_from_settings`).
- `harpyja/eval/report.py` — retire `fc_citation_recovered_{spanned,filelevel}_count`
  to always-zero; KEEP `fc_citation_{spanned,filelevel,dropped}_count`; bump
  `SCHEMA_VERSION "0014/1"` (:28); `_AGGREGATE_DEFAULTS` legacy validation stays.
- FC surface to delete: `harpyja/scout/fastcontext.py`, `harpyja/scout/client.py`
  (`DefaultFastContextClient`, `parse_final_answer`, `_SCOUT_ENV_LOCK`,
  `_managed_fc_env`, `_run_coro_on_worker_thread`, `_fc_env_from_settings`),
  `errors.FASTCONTEXT_MISSING`/`CLI_MISSING`, plus the FC tests
  (`test_fastcontext_client.py`, the FC-live `test_scout_integration.py`).
- `pyproject.toml` — `"fastcontext"` (:22) + `[tool.uv.sources] fastcontext` (:60);
  mirrored in `uv.lock`.

## Test-first sequence

### Step 1 — Canonical factory constructs the explorer; parallel factory gone (RED)  [AC1/AC2]
- Rewrite `harpyja/scout/test_scout_wiring.py` (drop the FastContext-asserting tests):
  - `test_build_scout_engine_constructs_explorer_backend` — `engine._backend` is
    `ExplorerBackend`, not `FastContextBackend`.
  - `test_build_scout_engine_threads_gateway_and_loop_budgets` — an injected `gateway=`
    reaches the backend; `scout_max_turns`/`scout_wall_clock_s` thread through.
  - `test_build_explorer_scout_engine_removed` — the name no longer resolves in
    `harpyja.scout.wiring` (no lingering parallel factory).
  - `test_wiring_constructs_no_fastcontext_backend` — no code path builds a FC backend.
- Repoint `harpyja/scout/test_explorer_integration.py` import/call
  `build_explorer_scout_engine` → `build_scout_engine`.
- Tests fail: `build_scout_engine` still builds `FastContextBackend`; the parallel
  factory still exists.

### Step 2 — Fold the explorer into `build_scout_engine`; delete the parallel factory (GREEN)  [AC1/AC2]
- `harpyja/scout/wiring.py`: `build_scout_engine` constructs `ExplorerBackend`
  (loopback gateway + shared `RipgrepEngine` + manifest map + explorer tools),
  keeping the `gateway=`/`model_call=` params folded from `build_explorer_scout_engine`;
  delete `build_explorer_scout_engine`; drop the `client`/`fastcontext` imports.
- Keep a **transitional no-op `agent_factory=` kwarg** so `locate_probe.py:155` stays
  green until AC3's migration removes it (documented as AC3-transitional).
- All Step-1 tests pass; `runner.py`/`test_locate_integration.py` callers unaffected.

### Step 3 — Native turns-used seam + equivalence to the trajectory count (RED)  [AC3]
- Add to `harpyja/scout/test_explorer_backend.py`:
  - `test_backend_exposes_last_turns_used` — after `.run()`, `backend.last_turns_used`
    equals the loop's `LoopResult.turns_used`; set on submit AND on degrade paths.
  - `test_last_turns_used_reset_per_run` — reset at the start of each `.run()`.
- Add to `harpyja/scout/test_scout.py`:
  - `test_scout_engine_surfaces_last_turns_used` — `ScoutEngine.search` reads the
    backend's per-run count into `engine.last_turns_used` (getattr-guarded for backends
    that lack it), reset per call.
- Add `test_native_turns_used_equals_trajectory_step_count` — a scripted fake loop
  making N tool calls then submitting reports `turns_used == N`, and a frozen N-record
  trajectory JSONL fixture reports `count_turns == N` (the counter contract asserted
  against a golden trajectory, not cross-backend semantic identity).
- Tests fail: no `last_turns_used` seam on backend or engine.

### Step 4 — Implement the turns-used seam (GREEN)  [AC3]
- `harpyja/scout/explorer_backend.py`: add `last_turns_used: int | None`, reset to
  `None` at the top of `run`, set from `LoopResult.turns_used` on every terminal path
  (submit and the exhaustion raises).
- `harpyja/scout/engine.py`: after `self._backend.run(...)`, populate
  `self.last_turns_used = getattr(self._backend, "last_turns_used", None)`, reset per
  `search`.
- Step-3 tests pass.

### Step 5 — Repoint the 0022 diagnostic onto the native seam; retire the trajectory path (RED)  [AC3/AC2]
- Add to `harpyja/eval/test_locate_probe.py`:
  - `test_run_locate_probe_turns_from_native_seam` — `run_locate_probe` collects
    per-case turns from `scout_engine.last_turns_used`; `turns_used_source == "explorer"`;
    no `turns_sink` and no `agent_factory` required.
  - `test_build_scout_only_stack_wires_no_agent_factory` — the stack builder no longer
    injects a counting factory.
  - `test_count_turns_and_counting_agent_factory_removed` — `count_turns` /
    `counting_agent_factory` / `_CountingAgent` no longer resolve in
    `harpyja.eval.locate_probe` (executable absence guard).
- Tests fail: the probe still reads `turns_sink` via `counting_agent_factory`; the
  trajectory helpers still exist.

### Step 6 — Migrate the diagnostic + cut the `agent_factory=` seam (GREEN)  [AC3/AC2]
- `harpyja/eval/locate_probe.py`: read per-case turns from
  `scout_engine.last_turns_used` in `run_locate_probe`; rewrite `_resolve_turns`/
  `build_scout_only_stack` to the native seam; delete `count_turns`,
  `counting_agent_factory`, `_CountingAgent`, the `turns_sink` plumbing, and the old
  trajectory turns tests (lines ~149-208).
- `harpyja/scout/wiring.py`: remove the transitional `agent_factory=` kwarg from
  `build_scout_engine` (its last caller is gone).
- Step-5 tests pass; the diagnostic is green on the native seam before any FC deletion.

### Step 7 — `normalize.py` split: two-sided proof for suffix-recovery removal (RED)  [AC5]
- Add to `harpyja/scout/test_scout_normalize.py`:
  - `test_explorer_citation_path_triggers_no_suffix_recovery` — in-repo submitted paths
    normalize with `recovered_spanned == recovered_filelevel == 0` (the explorer never
    needed the 0012 hack; recovery is a structural no-op for its output).
  - `test_recover_suffix_and_min_tail_segments_removed` — `_recover_suffix` /
    `MIN_TAIL_SEGMENTS` no longer resolve in `harpyja.scout.normalize` (post-delete
    import-absence guard; RED while present).
- Add to `harpyja/scout/test_scout.py`:
  - `test_last_tally_still_populated_after_recovery_removed` — `ScoutEngine.search`
    still sets `last_tally` (the shared consumers — `runner`, `locate_probe`, the 0022
    `locate_accuracy` diagnostic — keep reading it); recovered counts read zero.
- Tests fail: `_recover_suffix`/`MIN_TAIL_SEGMENTS` still present.

### Step 8 — Remove suffix-recovery, keep the shared tally core (GREEN)  [AC5]
- `harpyja/scout/normalize.py`: delete `_recover_suffix` + `MIN_TAIL_SEGMENTS` and the
  recovery branch/`top_level`/`recovered_paths_out` population in
  `normalize_spans_with_tally`; it now always returns `recovered_spanned=0,
  recovered_filelevel=0`. `normalize_spans` / `normalize_spans_for_scout` / `ScoutTally`
  / `last_tally` signatures and behavior are otherwise unchanged (Tier-2/Deep callers
  unaffected).
- Update the recovery-expecting assertions in `test_scout_normalize.py`, `test_scout.py`,
  `test_locate_accuracy.py`, `test_runner.py`, `test_swebench_runner.py` to the zeroed
  shape.
- Step-7 tests pass.

### Step 9 — `scout_model` audit / drift-guard lock (GUARD)  [AC6]
- Harden `harpyja/config/test_settings.py`:
  - Strengthen `test_settings_defaults_drop_unserved_tags` to assert the AC6 property —
    no `Settings` field default names an *unserved/unobtainable* tag (field-default
    introspection over `dataclasses.fields`, never a source grep).
  - `test_scout_model_preserved_as_served_gate_baseline` — `scout_model` retains its
    served default and is explicitly scoped OUT of the FC-removal (it is the
    `verify_method="scout_model"` gate consumer, not Scout-backend plumbing).
- Guard-lock only (no production change here): the FC-only Settings *fields* are removed
  in Step 13 with their sole consumer (`client.py`); this step pins the invariant that
  removal must not sweep `scout_model` and that no reintroduced FC default may be unserved.

### Step 10 — Report-schema: retire recovered fields to zero, bump version (RED)  [AC7]
- Add/adjust in `harpyja/eval/test_report.py`:
  - `test_schema_version_bumped_for_recovered_retirement` — `SCHEMA_VERSION == "0025/1"`
    (update the `== "0014/1"` pin at line 207 and the `!=` guards).
  - `test_recovered_citation_fields_default_and_stay_zero` — `fc_citation_recovered_*`
    default 0 and are never populated non-zero.
  - `test_shape_tally_fields_still_populated` — `fc_citation_{spanned,filelevel,dropped}`
    stay populated (they describe the explorer's citation shape too).
  - `test_legacy_block_still_validates_via_aggregate_defaults` — an omitted-field block
    still validates through `_AGGREGATE_DEFAULTS`.
- Add to `harpyja/eval/test_runner.py`:
  - `test_runner_does_not_populate_recovered_counts` — the writer emits 0 for both
    recovered fields.
- Tests fail: version is `"0014/1"`; `runner.py:309-310` still sources recovered counts
  from `scout_tally`.

### Step 11 — Bump `SCHEMA_VERSION`; stop populating recovered counts (GREEN)  [AC7]
- `harpyja/eval/report.py`: `SCHEMA_VERSION = "0025/1"`; keep `_AGGREGATE_DEFAULTS`
  (recovered fields default 0).
- `harpyja/eval/runner.py`: stop computing `rec_spanned`/`rec_filelevel`; write 0 for
  `fc_citation_recovered_*`; keep the spanned/filelevel/dropped shape tally populated.
- Update any other `SCHEMA_VERSION` pins in lockstep (`test_oq2_ledger` only asserts
  `!= REPORT_VERSION`, which still holds).
- Step-10 tests pass.

### Step 12 — FC surface + FC-only Settings absence guard (RED)  [AC4/AC6]
- Add `harpyja/scout/test_fastcontext_absent.py`:
  - `test_fastcontext_module_not_importable` — `import harpyja.scout.fastcontext`
    raises `ModuleNotFoundError`.
  - `test_scout_client_module_removed` — `harpyja.scout.client` gone; `parse_final_answer`,
    `DefaultFastContextClient`, `_SCOUT_ENV_LOCK`, `_managed_fc_env`,
    `_run_coro_on_worker_thread`, `_fc_env_from_settings` all unresolvable.
  - `test_wiring_imports_no_fastcontext` — `harpyja.scout.wiring` source/namespace has
    no `fastcontext`/`client` import.
  - `test_scout_stack_available_does_not_import_upstream_fastcontext` — the eval gate no
    longer depends on the `fastcontext` package.
  - `test_fc_only_scout_settings_removed` — `scout_max_tokens`/`scout_temperature`/
    `scout_reasoning_effort` are no longer `Settings` fields.
  - `test_scout_model_preserved` — the gate baseline survives (removal did not over-reach).
  - `test_fc_error_causes_removed` — `errors.FASTCONTEXT_MISSING`/`CLI_MISSING` gone.
- Tests fail: the FC surface and FC-only Settings fields still exist.

### Step 13 — Delete the FC surface + orphaned FC Settings fields (GREEN)  [AC4/AC6]
- Delete `harpyja/scout/fastcontext.py`, `harpyja/scout/client.py`,
  `harpyja/scout/test_fastcontext_client.py`, and the FC-live
  `harpyja/scout/test_scout_integration.py`.
- `harpyja/config/settings.py`: remove `scout_max_tokens`/`scout_temperature`/
  `scout_reasoning_effort` + their FC_* mapping comments; KEEP `scout_model`.
- `harpyja/eval/locate_probe.py`: repoint `scout_stack_available` — drop the
  `import fastcontext` check; gate on `rg` + a reachable loopback endpoint only.
- `harpyja/scout/errors.py`: remove `FASTCONTEXT_MISSING`/`CLI_MISSING` (now unused).
- Scrub any residual FC imports (`test_scout_wiring.py` header, etc.).
- Step-12 tests pass; full suite green (no `fastcontext` symbol resolves).

### Step 14 — Dependency-declaration absence guard (RED)  [AC9]
- Add `harpyja/test_packaging.py` (or `harpyja/eval/test_packaging.py`):
  - `test_pyproject_declares_no_fastcontext_dependency` — parse `pyproject.toml`; no
    `"fastcontext"` in `[project].dependencies` and no `[tool.uv.sources] fastcontext`.
- Tests fail: `pyproject.toml:22,60` still declare it.

### Step 15 — Drop the retracted dependency; clean sync (GREEN)  [AC9] [build]
- `pyproject.toml`: remove `"fastcontext"` (:22) and the `[tool.uv.sources]` entry (:60).
- Refresh `uv.lock` (`uv lock`) and verify a from-scratch `uv sync` succeeds without the
  retracted package.
- Step-14 test passes; `uv sync` clean.

### Step 16 — Live cutover through the explorer, zero non-loopback egress (RED, integration, skip-not-fail)  [AC8]
- Add `harpyja/eval/test_cutover_integration.py`, reusing `_deny_nonloopback_egress`
  (from `harpyja/eval/test_eval_integration.py`):
  - `@pytest.mark.integration test_eval_instrument_runs_through_explorer_produces_citations`
    — build the Scout-only stack via the canonical `build_scout_engine` with the gateway
    pinned to `settings.lm_model` (Qwen3-8B on loopback Ollama), drive one real case
    through the eval instrument, assert citations (or an honest result) and
    `turns_used_source == "explorer"`.
  - `@pytest.mark.integration test_cutover_zero_nonloopback_egress` — under
    `_deny_nonloopback_egress()` the live run makes ZERO non-loopback connections.
  - Skip-not-fail when no served stack is present.
- Tests fail (when a stack is present) until the live entry is wired; else skip.

### Step 17 — Wire the live cutover entry (GREEN, integration)  [AC8]
- Finish the live path: the test pins the served Qwen3-8B tag explicitly through the
  gateway (the `model="local"` default 404s on Ollama), drives one real query end-to-end,
  no SUT change beyond the factory cutover. Passes on a served host; skips otherwise.

### Step 18 — Refactor: collapse the now-inert recovered bookkeeping (REFACTOR, optional)  [AC5/AC7]
- With recovery gone, the `recovered_spanned`/`recovered_filelevel` return of
  `normalize_spans_with_tally` and the `ScoutTally.recovered_*` construction are constant
  zeros. Simplify their computation while KEEPING the field names (schema/side-channel
  stability). All tests still pass. (If no real duplication remains, no-op honestly.)

## AC mapping

- AC1 → Steps 1-2
- AC2 → Steps 1-2 (factory reference), 5-6 (`agent_factory=` kwarg removal)
- AC3 → Steps 3-4 (native seam), 5-6 (diagnostic migration + seam cut)
- AC4 → Steps 12-13
- AC5 → Steps 7-8 (+ 18 refactor)
- AC6 → Step 9 (audit/drift-guard), Steps 12-13 (FC-only field removal)
- AC7 → Steps 10-11 (+ 18 refactor)
- AC8 → Steps 16-17
- AC9 → Steps 14-15
- AC10 → changelog/history at close (doc, not a code task)

## Delegation

- Steps 1-14, 18 (pure/faked unit TDD — wiring, seam, normalize, settings, report,
  absence guards) → keep in-thread. Reason: deterministic RED→GREEN, no live stack.
- Step 15 (`uv lock` + from-scratch `uv sync`) → run in the build environment.
  Reason: it is a [build] verification, not a pytest unit.
- Steps 16-17 (live explorer cutover + network-deny egress) → an integration
  runner with a served **Qwen3-8B on loopback Ollama** (per repo memory: local Ollama on
  the 32 GB dev host). Reason: needs a live loopback endpoint the unit thread must never
  depend on; `@pytest.mark.integration` skip-not-fail keeps CI green when absent.

## Risk

- **Turns seam not populated on a degrade path** (would regress the 0022 measurement it
  was migrated to preserve) → mitigation: Step-3 `test_backend_exposes_last_turns_used`
  asserts population on submit AND exhaustion raises; set `last_turns_used` before the
  `ScoutUnavailable` raise.
- **`normalize.py` signature churn breaking Deep (Tier-2)** → mitigation: keep
  `normalize_spans`/`normalize_spans_with_tally`/`ScoutTally` signatures stable; only the
  recovery internals change; the 4-tuple return shape is preserved (recovered → 0).
- **Removing FC-only Settings fields while `client.py` still reads them** → mitigation:
  ordering — the field removal is bundled into the FC-surface deletion (Step 13), where
  the sole consumer and its test are deleted in the same GREEN.
- **`SCHEMA_VERSION` bump breaking other version-pinned tests** → mitigation: Step 11
  updates every pin in lockstep; `test_oq2_ledger` only asserts `!= REPORT_VERSION`
  (still holds).
- **`scout_stack_available` false-skipping after the dependency drop** (ImportError→False)
  → mitigation: repoint it OFF the `fastcontext` import in Step 13, before the dependency
  is removed in Step 15.
- **Collection errors from FC-importing integration tests after the dep drop**
  (`test_scout_integration.py`, `test_explorer_integration.py`) → mitigation: the FC-live
  file is deleted in Step 13; the explorer integration import is repointed in Step 1.
- **AC6 self-contradiction (served FC-lineage `scout_model` default)** → mitigation:
  Step 9 asserts the property the guard actually enforces (no *unserved* default) and
  scopes `scout_model` explicitly OUT of the FC-removal — no "no default is FC-branded"
  claim.
- **AC8 model ambiguity** → mitigation: the gateway pins the served Qwen3-8B tag
  explicitly (Step 17); the removed FastContext-4B is never the live model.
