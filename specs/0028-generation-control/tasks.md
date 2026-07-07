---
spec: "0028"
---

# Tasks

- [x] T1 — RED: gateway tests pin `finish_reason` (present, `"unknown"` absent, backward-additive) [AC0]
- [x] T2 — GREEN: `complete_with_tools` returns additive `finish_reason` from `choices[0]` [AC0]
- [x] T3 — RED: `explorer_max_tokens` default==2048 + env-int; `ExplorerBackend` field-default introspection + gateway kwarg [AC2]
- [x] T4 — GREEN: add `explorer_max_tokens` Settings, `ExplorerBackend.max_tokens=2048`, wire in `build_scout_engine`; gateway stays param-only [AC2]
- [x] T5 — RED: `explorer_enable_thinking` default==True + env-bool; bidirectional `chat_template_kwargs`; reject `/no_think` [AC1]
- [x] T6 — GREEN: add `explorer_enable_thinking` Settings, thread `enable_thinking` through `_default_model_call`, wire it [AC1]
- [x] T7 — REFACTOR: fold `max_tokens` + conditional `chat_template_kwargs` into one `params` dict [AC1/AC2]
- [x] T8 — GUARD: Deep outbound (`rlm(query=...)`) carries neither the explorer cap nor `enable_thinking` — passes on introduction, rots false on leak [AC8]
- [x] T9 — RED: loop `finish=length` ⇒ `GENERATION_TRUNCATED`, including with a valid tool_call present [AC3]
- [x] T10 — GREEN: `run_explorer_loop` returns `GENERATION_TRUNCATED` right after `model_call`, regardless of tool_calls [AC3]
- [x] T11 — RED: truncation outcome ⇒ `ScoutUnavailable(generation-truncated)`, distinct from model-unreachable [AC3]
- [x] T12 — GREEN: add `errors.GENERATION_TRUNCATED` + `_EXHAUSTION_CAUSE` entry [AC3]
- [x] T13 — RED: runner counts `scout-degraded:generation-truncated` distinctly [AC3]
- [x] T14 — GREEN: add cause to `_SCOUT_NATIVE_CAUSES` + `scout_degrade_generation_truncated_count` aggregate field [AC3]
- [x] T15 — RED: report field defaults 0, legacy 0027 block still validates, `SCHEMA_VERSION=="0028/1"` [AC3]
- [x] T16 — GREEN: add report field + `_AGGREGATE_DEFAULTS` entry, bump `SCHEMA_VERSION` to `0028/1` [AC3]
- [x] T17 — LIVE: AC4 first-call tool_calls in ~2s (PASS); AC5 stays xfail RE-POINTED to a newly-diagnosed loop parallel-tool-call bug (not generation control) [AC4/AC5]
- [x] T18 — OPERATOR: AC6 lever-choice deferred behind the AC5 blocker (data recorded); AC7 cap validated for well-formed turns + N=10 unchanged; findings written [AC6/AC7]
