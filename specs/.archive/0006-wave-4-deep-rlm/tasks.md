---
spec: "0006"
---

# Tasks

- [x] 01. RED: Deep budget settings defaults/toml/env (harpyja/config/test_settings.py::test_settings_deep_defaults) [AC10]
- [x] 02. GREEN: append eight deep_* fields to Settings (harpyja/config/settings.py) [AC10]
- [x] 03. RED: normalize_spans honors explicit deep budgets (harpyja/scout/test_scout_normalize.py::test_normalize_spans_honors_explicit_deep_budgets) [AC9]
- [x] 04. GREEN: parameterize normalize_spans + Scout-compat wrapper (harpyja/scout/normalize.py) [AC9]
- [x] 05. RED: DeepUnavailable stable causes (harpyja/deep/test_deep.py::test_deep_unavailable_carries_stable_cause) [AC5, AC5a]
- [x] 06. GREEN: implement deep/errors.py (harpyja/deep/errors.py) [AC5, AC5a]
- [x] 07. RED: DeepBackend Protocol accepts fake (harpyja/deep/test_deep.py::test_deep_backend_protocol_accepts_fake) [AC4]
- [x] 08. GREEN: implement DeepBackend Protocol (harpyja/deep/backend.py) [AC4]
- [x] 09. RED: DeepBudget counters + truncated_bound (harpyja/deep/test_deep.py::test_budget_tool_calls_stops_after_max) [AC10]
- [x] 10. GREEN: implement DeepBudget meter (harpyja/deep/budget.py) [AC10]
- [x] 11. RED: host tools confinement/clamp/read-only/whitelist (harpyja/deep/test_host_tools.py::test_host_tools_whitelist_exact_equality) [AC7, AC8, AC8a]
- [x] 12. GREEN: implement build_host_tools, exactly four tools (harpyja/deep/host_tools.py) [AC7, AC8, AC8a]
- [x] 13. RED: runner counter facet contract (harpyja/deep/test_deep.py::test_runner_surfaces_truncated_bound_from_budget) [AC10]
- [x] 14. GREEN: implement host-terminable DeepRunner (harpyja/deep/runner.py) [AC10]
- [x] 15. RED: wall-clock hard-kills non-yielding busy loop (harpyja/deep/test_deep_integration.py::test_runner_hard_kills_nonyielding_busy_loop_on_wall_clock) [AC10]
- [x] 16. RED: DeepEngine seed/dual-surface/typed-only/normalize (harpyja/deep/test_deep.py::test_deep_engine_run_returns_citations_and_truncated_bound) [AC1, AC3, AC4, AC5, AC5a, AC9]
- [x] 17. GREEN: implement DeepEngine (harpyja/deep/engine.py) [AC1, AC3, AC4, AC5, AC5a, AC9]
- [x] 18. RED: RlmBackend injected runner, no hard import (harpyja/deep/test_deep.py::test_rlm_backend_delegates_to_injected_runner) [AC4, AC6]
- [x] 19. GREEN: implement RlmBackend via injected runner + gateway.complete (harpyja/deep/rlm.py) [AC4, AC6]
- [x] 20. RED: delete+invert lockstep guard, lock deep branch (harpyja/orchestrator/test_locate.py::test_locate_deep_emits_tier2_marker_when_wired) [AC1, AC2, AC2a, AC3, AC5, AC5a, AC6, AC10, AC13]
- [x] 21. GREEN: deep routing + degradation, delete _DEEP_PENDING (harpyja/orchestrator/locate.py) [AC1, AC2, AC2a, AC3, AC5, AC5a, AC6, AC10, AC13]
- [x] 22. RED: build_app deep wiring + zero-deep on auto/fast (harpyja/server/test_app.py::test_build_app_deep_uses_deep_engine) [AC2, AC13]
- [x] 23. GREEN: wire deep_factory into build_app (harpyja/server/app.py) [AC2, AC13]
- [x] 24. RED: sandbox isolation / runaway / network-deny / live (harpyja/deep/test_deep_integration.py::test_deep_sandbox_exposes_only_four_tools) [AC8b, AC10a, AC11, AC12]
