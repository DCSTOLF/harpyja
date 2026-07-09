---
spec: "0030"
---

# Tasks

- [x] T1 — RED: `test_scout_symbols_max_entries_default_is_finite_positive_bound` in `harpyja/config/test_settings.py`
- [x] T2 — GREEN: add `scout_symbols_max_entries: int = 400` (additive-last) in `harpyja/config/settings.py`
- [x] T3 — RED: symbols-tool unit tests (`test_symbols_tool_wraps_tier0_records_python`, `..._go`, `test_symbols_tool_normalized_path`, `test_symbols_tool_no_new_parser`) in `harpyja/scout/test_explorer_tools.py`
- [x] T4 — GREEN: add `symbols(path)` + `symbol_records`/`manifest` params to `build_explorer_tools` in `harpyja/scout/explorer_tools.py`
- [x] T5 — RED: `test_symbols_tool_out_of_repo_path_rejected`, `test_symbols_tool_clamps_to_scout_symbols_max_entries` in `harpyja/scout/test_explorer_tools.py`
- [x] T6 — GREEN: post-resolution `confine_path` + `scout_symbols_max_entries` clamp in `harpyja/scout/explorer_tools.py`
- [x] T7 — RED (AC3): `test_symbols_tool_degraded_file_falls_back_to_ripgrep`, `..._marks_output_degraded`, `test_symbols_tool_clean_file_not_marked_degraded`, `..._degraded_never_raises` in `harpyja/scout/test_explorer_tools.py`
- [x] T8 — GREEN (AC3): manifest-`degraded` provenance lookup + ripgrep fallback + `{"symbols","degraded"}` return shape in `harpyja/scout/explorer_tools.py`
- [x] T9 — RED (AC4): flip count/schema/parallel tests — `test_build_explorer_tools_returns_exactly_five_navigation_tools` (`test_explorer_tools.py`), updated `test_tool_schemas_match_the_built_tool_surface_single_source` (`test_explorer_backend.py`), `test_symbols_participates_in_parallel_tool_calls` (`test_explorer_loop.py`)
- [x] T10 — GREEN (AC4 LOCKSTEP, single commit): amend `.speccraft/conventions.md` 4→5 with rationale + add `symbols` schema and `symbol_records` param to `harpyja/scout/explorer_backend.py`
- [x] T11 — RED: `test_build_scout_engine_threads_symbol_records_into_symbols_tool` in `harpyja/scout/test_scout_wiring.py`
- [x] T12 — GREEN: load + thread `symbol_records` via `load_symbols_or_none` in `harpyja/scout/wiring.py`
- [x] T13 — REFACTOR (optional): extract shared `record_to_codespan` used by `deep/host_tools.py` + `scout/explorer_tools.py`
- [x] T14 — RED (AC5): `test_lift_report_schema_is_version_stamped_and_validated`, `test_lift_report_writes_outside_repo_atomically` in `harpyja/eval/test_symbols_lift_report.py`
- [x] T15 — GREEN (AC5): pinned version-stamped lift-report schema + atomic outside-repo writer in `harpyja/eval/symbols_lift_report.py`
- [x] T16 — LIVE (AC5/AC6): `test_symbols_lift_astropy_django_live` in `harpyja/eval/test_symbols_lift_live.py`; PASSED with qwen3:14b on Ollama (astropy-12907 + django-12774, buckets recorded honestly, durable report written)
