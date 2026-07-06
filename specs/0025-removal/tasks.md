---
spec: "0025"
---

# Tasks

- [x] T1 — RED: rewrite `test_scout_wiring.py` — `build_scout_engine` constructs `ExplorerBackend`, threads gateway/budgets, `build_explorer_scout_engine` removed, no FC backend; repoint `test_explorer_integration.py` to `build_scout_engine` (AC1/AC2)
- [x] T2 — GREEN: fold the explorer into `build_scout_engine` (keep `gateway=`/`model_call=` + transitional no-op `agent_factory=`), delete `build_explorer_scout_engine`, drop FC imports from `wiring.py` (AC1/AC2)
- [x] T3 — RED: `test_explorer_backend.py`/`test_scout.py` — `last_turns_used` on backend + engine (reset per run) + `test_native_turns_used_equals_trajectory_step_count` against a frozen trajectory (AC3)
- [x] T4 — GREEN: implement `last_turns_used` on `ExplorerBackend` (submit + degrade paths) and surface it on `ScoutEngine.search` (AC3)
- [x] T5 — RED: `test_locate_probe.py` — probe reads turns from the native seam (`source=="explorer"`, no sink), stack wires no `agent_factory`, `count_turns`/`counting_agent_factory` absence guard (AC3/AC2)
- [x] T6 — GREEN: migrate `run_locate_probe`/`_resolve_turns`/`build_scout_only_stack` to `last_turns_used`; delete `count_turns`/`counting_agent_factory`/`_CountingAgent`/`turns_sink`; remove the `agent_factory=` kwarg from `build_scout_engine` (AC3/AC2)
- [x] T7 — RED: `test_scout_normalize.py`/`test_scout.py` — explorer path triggers no suffix recovery, `last_tally` still populated/consumed, `_recover_suffix`/`MIN_TAIL_SEGMENTS` absence guard (AC5)
- [x] T8 — GREEN: delete `_recover_suffix`+`MIN_TAIL_SEGMENTS`, recovered counts → structurally zero, keep the shared tally core; update recovery-expecting assertions across scout/eval tests (AC5)
- [x] T9 — GUARD: harden `test_settings.py` drift guard to the AC6 property (no unserved default) + `scout_model` preserved as served gate baseline, scoped OUT of FC-removal (AC6)
- [x] T10 — RED: `test_report.py`/`test_runner.py` — `SCHEMA_VERSION == "0025/1"`, `fc_citation_recovered_*` retired to zero, shape-tally fields stay, legacy block still validates (AC7)
- [x] T11 — GREEN: bump `SCHEMA_VERSION` to `"0025/1"`, stop populating recovered counts in `runner.py`, keep `_AGGREGATE_DEFAULTS`; update version pins in lockstep (AC7)
- [x] T12 — RED: `test_fastcontext_absent.py` — FC module/client/public-names/error-causes unresolvable, wiring FC-import-free, `scout_stack_available` upstream-import-free, FC-only Settings fields removed, `scout_model` preserved (AC4/AC6)
- [x] T13 — GREEN: delete `fastcontext.py`/`client.py`/`test_fastcontext_client.py`/FC-live `test_scout_integration.py`; remove FC-only Settings fields + FC error causes; repoint `scout_stack_available` off `fastcontext` (AC4/AC6)
- [x] T14 — RED: `test_packaging.py` — `pyproject.toml` declares no `fastcontext` dependency and no `[tool.uv.sources]` entry (AC9)
- [x] T15 — GREEN: remove `fastcontext` from `pyproject.toml` + `[tool.uv.sources]`, refresh `uv.lock`, verify a clean from-scratch `uv sync` (AC9) [build]
- [x] T16 — RED: cutover integration (`test_locate_probe_integration.py`) — eval instrument runs through the explorer producing citations (`turns_used_source=="explorer"`) + zero non-loopback egress under `_deny_nonloopback_egress`, skip-not-fail; + unit RED pinning the wiring model-tag (AC8)
- [x] T17 — GREEN: thread `settings.lm_model` into `build_scout_engine`'s default gateway (served tag, not "local"); cutover test skips-not-fails on an unserved stack (AC8)
- [x] T18 — REFACTOR: collapse the now-inert recovered-count bookkeeping (dead `recovered` branches) in `normalize_spans_with_tally`, keeping field names/arity for schema stability; + harden the isolated probe to record a `ScoutUnavailable` degrade as EMPTY (not a crash) so the eval harness runs end-to-end through the explorer's degrade taxonomy (AC5/AC7)
