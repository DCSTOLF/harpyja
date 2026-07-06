---
spec: "0025"
closed: 2026-07-06
---

# Changelog — 0025 removal (FastContext removal + Scout cutover to the explorer backend)

## What shipped vs spec

FastContext is fully removed and the native `ExplorerBackend` (spec 0024) is now the
**sole** Scout backend — no longer a parallel factory. All 7(+3 doc) ACs met; full
suite **985 passed / 23 skipped**, ruff clean; the AC8 live cutover proof passed
end-to-end through the explorer on a loopback Ollama endpoint (Qwen3-8B), zero
non-loopback egress.

- **AC1 — one canonical factory.** `build_scout_engine` is the single production Scout
  factory and constructs `ExplorerBackend`; the parallel `build_explorer_scout_engine`
  is deleted (its body folded in). No code path builds a FastContext backend.
- **AC2 — eval harness repointed.** The runner/swebench/`locate_probe` drivers reference
  the canonical `build_scout_engine` only; the `agent_factory=` kwarg is gone (removed
  AFTER the AC3 turns-migration landed, so repointing never broke the diagnostic).
- **AC3 — turns-used MIGRATED, then the seam cut.** A native per-run seam
  `ExplorerBackend.last_turns_used` (fed from `LoopResult.turns_used`, set on submit AND
  both exhaustion-degrade paths, reset per run) is surfaced on `ScoutEngine.last_turns_used`
  (getattr-guarded for backends without it). The 0022 diagnostic reads this instead of
  scraping FastContext's trajectory JSONL; `count_turns` / `counting_agent_factory` /
  `_CountingAgent` / `turns_sink` are deleted. `turns_used_source` is now `"explorer"` /
  `"unavailable"` (was `"trajectory"` / `"unavailable"`).
- **AC4 — executable absence guard.** New `harpyja/scout/test_fastcontext_absent.py`:
  AST-based import-absence + public-name assertions that rot-false if `fastcontext` /
  `client` / `tools` re-imports, or if the FC error causes / FC-only Settings fields
  reappear — durable where a point-in-time grep goes stale.
- **AC5 — `normalize.py` split.** Only the FC-era suffix-recovery (`_recover_suffix` /
  `MIN_TAIL_SEGMENTS`, spec 0012) is removed; the shared `normalize_spans` /
  `normalize_spans_with_tally` / `ScoutTally` / `last_tally` core is KEPT (still feeds
  `runner`, `locate_probe`, and the 0022 `locate_accuracy` diagnostic). Recovered counts
  are structurally zero.
- **AC6 — `scout_model` audit-and-keep.** FC-only Settings fields
  (`scout_max_tokens` / `scout_temperature` / `scout_reasoning_effort`) and FC error
  causes (`FASTCONTEXT_MISSING` / `CLI_MISSING`) removed. `scout_model` is KEPT as the
  served Verification-Gate A/B baseline (`verify_method="scout_model"`, 0018), explicitly
  scoped OUT of the FC-removal drift guard (the guard asserts "no default names an
  *unserved* tag," never "no default is FC-branded").
- **AC7 — report-schema fate.** `SCHEMA_VERSION` bumped `0014/1 → 0025/1`. The
  `fc_citation_recovered_{spanned,filelevel}_count` fields are retired-to-zero (kept for
  schema stability, no longer sourced from `ScoutTally`); the shape-tally fields
  `fc_citation_{spanned,filelevel,dropped}_count` STAY populated — now by the explorer.
  Legacy blocks still validate via `_AGGREGATE_DEFAULTS`.
- **AC8 — live cutover.** New integration test drives the eval instrument end-to-end
  through the explorer, gateway pinned to `settings.lm_model` (Qwen3-8B on loopback
  Ollama), `turns_used_source == "explorer"`, zero non-loopback egress under
  `_deny_nonloopback_egress`. Skip-not-fail without a served stack; hard-fail under
  `HARPYJA_REQUIRE_LIVE_STACK=1`.
- **AC9 — dependency dropped.** `fastcontext` git dependency removed from
  `pyproject.toml` + `[tool.uv.sources]`; `uv.lock` refreshed (azure / msal / aiofiles /
  aiofile / asyncio transitives dropped); new `harpyja/test_packaging.py` guards it.
- **AC10 — the arc is closed in memory.** Changelog + history record WHY (retracted /
  unobtainable upstream + the 0020–0023 finding), not merely that it was deleted.

### Two behavior changes riding in on the cutover (flagged, not buried)

1. **Isolated-probe degrade tolerance — a GENUINE BEHAVIOR CHANGE (T18), not a test fix.**
   `_run_scout_query` / `run_locate_probe` now catch a typed `ScoutUnavailable` and record
   it as an **EMPTY** localization for that case, instead of propagating a crash. This is a
   real semantic change to how the eval harness treats a Scout degrade: the FastContext
   backend returned honest-empty on failure, but the explorer **RAISES** on turn / wall-clock
   exhaustion (or model-unreachable); the probe runs Scout in isolation (no orchestrator
   degrade wrapper), so it had to learn the explorer's degrade taxonomy to run end-to-end
   (AC5/AC8). The recorded EMPTY is the same "no usable citation" floor the orchestrator
   would produce — never a fabricated result.

2. **`build_scout_engine` default gateway now pins `settings.lm_model` — a
   PRODUCTION-CORRECTNESS fix (T17), not pure cutover.** The default gateway previously used
   `ModelGateway.model`'s `"local"` default, which **404s on Ollama's tag-routed API** — the
   production Scout path would have failed on Ollama. The default now pins `settings.lm_model`
   (default Qwen3-8B). This is the AC8 "thread the model tag through the wiring" resolution;
   it also means the explorer now runs on **`lm_model` — the same model as Deep**.

### Notable in-scope discoveries beyond the plan

- **Second-order orphan (`scout/tools.py`).** `tools.py::build_tool_whitelist` was
  FastContext's read/glob/grep/model whitelist; after the primary FC deletion, only its own
  test referenced it. It was orphaned *by* the deletion (not on the enumerated deletion
  surface) and removed — "leaving it is exactly the silently-orphaned case the review warned
  against." Lesson recorded: a deletion spec must **re-scan for newly-orphaned code after the
  primary deletion**, not just delete the enumerated surface.
- **Report-schema naming debt (recorded, NOT fixed now).** The kept
  `fc_citation_{spanned,filelevel,dropped}` fields are now populated by the EXPLORER, so the
  `fc_` prefix is a misnomer (reads as FastContext-specific but is backend-neutral going
  forward); `fc_citation_recovered_*` are retired-to-zero. Future readers must treat the
  `fc_`-prefixed shape-tally fields as **backend-neutral** (or rename with a future
  `SCHEMA_VERSION` bump) — do not misread the data as FastContext-specific.

## Deviations from spec

- T17 (model-pin) and T18 (probe degrade tolerance) surfaced during the live cutover as
  in-scope corrections beyond the plan's step list — the two behavior changes above.
- The `E501` ruff fix in `test_gateway.py` is pure housekeeping folded in silently.

## Files touched

Deleted:
- `harpyja/scout/fastcontext.py`
- `harpyja/scout/client.py`
- `harpyja/scout/tools.py` (second-order orphan)
- `harpyja/scout/test_fastcontext_client.py`
- `harpyja/scout/test_scout_integration.py`
- `harpyja/test_fastcontext_source.py`
- the `fastcontext` git dependency in `pyproject.toml` + `[tool.uv.sources]` + `uv.lock`
  (azure / msal / aiofiles / aiofile / asyncio transitives)

Modified (production):
- `harpyja/scout/wiring.py` — single canonical `build_scout_engine` over `ExplorerBackend`;
  default gateway pins `settings.lm_model`
- `harpyja/scout/explorer_backend.py` — `last_turns_used` seam
- `harpyja/scout/engine.py` — surface `ScoutEngine.last_turns_used`
- `harpyja/scout/normalize.py` — suffix-recovery removed, shared tally core kept
- `harpyja/scout/backend.py` — docstring: `ExplorerBackend` is the impl
- `harpyja/scout/errors.py` — FC error causes removed
- `harpyja/config/settings.py` — FC-only fields removed, `scout_model` kept
- `harpyja/eval/locate_probe.py` — native turns seam; degrade-tolerant `_run_scout_query`;
  `scout_stack_available` off the `fastcontext` import
- `harpyja/eval/report.py` — `SCHEMA_VERSION` `0025/1`
- `harpyja/eval/runner.py` — recovered counts retired to zero
- `README.md` — current explorer-loop Scout, single FastContext retirement note

New (guards):
- `harpyja/scout/test_fastcontext_absent.py`
- `harpyja/test_packaging.py`

Modified (tests): `test_settings.py`, `test_scout.py`, `test_scout_normalize.py`,
`test_scout_wiring.py`, `test_explorer_backend.py`, `test_explorer_integration.py`,
`test_locate_probe.py`, `test_locate_probe_integration.py`, `test_report.py`,
`test_runner.py`, `test_swebench_runner.py`, `test_eval_integration.py`,
`test_locate.py`, `test_locate_integration.py`, `test_gateway.py` (E501 housekeeping).

## ADR proposed for history.md

Prepended as the 2026-07-06 entry (below the 0024 retirement entry): the FastContext
surface + dependency deletion, the canonical single factory, the turns-used migration,
the `normalize.py` split, the two behavior changes (probe degrade tolerance + the
`lm_model` pin), and the report-schema retire-to-zero + `fc_`-prefix naming debt.

## Conventions proposed

- New (Deletions & migrations): executable import-absence / public-name guards over
  point-in-time greps for a deletion — the guard rots-false when a deleted symbol reappears.
- New (Deletions & migrations): migrate-before-delete for a capability-carrying seam
  (surface an equivalent public seam and repoint the consumer BEFORE cutting the old one),
  and disentangle a mixed module (remove only the retired remainder, keep the shared core,
  prove the survivor path still resolves).
- New (Deletions & migrations): re-scan for second-order orphans after the primary deletion.
- New (Measurement & eval harness): an isolated eval probe must tolerate the SUT's typed
  degrade taxonomy — record a degrade as the honest floor outcome (EMPTY), never a crash —
  when it runs the tier outside the production wrapper that would floor it.
- New (Measurement & eval harness): a versioned-report field is retired-to-zero with a
  `SCHEMA_VERSION` bump when the measured backend changes; a kept field whose backend-specific
  name (`fc_`) is now a misnomer is documented as backend-neutral rather than silently
  misread.
