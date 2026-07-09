---
spec: "0033"
---

# Tasks

- [ ] T1 — Pin current shapes: repo-root/Tier-0 scope byte-identical + `0031/1` artifact (PIN)
- [ ] T2 — RED: engine returns repo-relative for subdir/nested/trailing-slash/`./`/file scopes + real-rg case
- [ ] T3 — GREEN: `RipgrepEngine.search(repo_root=...)` re-prefixes parsed paths (mechanism b)
- [ ] T4 — RED: tool-contract + astropy/django end-to-end + Deep scoped + symbols file-scope fallback
- [ ] T5 — GREEN: wrappers (`grep`, `symbols` fallback, Deep `search`) supply `repo_root=repo_path`
- [ ] T6 — RED: `submit_citations` counts (found-then-dropped vs honest-empty) + single-caller assert
- [ ] T7 — GREEN: `SubmitResult(spans, submitted, surviving)` in `submit.py`
- [ ] T8 — RED: `LoopResult` carries `citations_submitted`/`citations_surviving`
- [ ] T9 — GREEN: thread counts through `explorer_loop` (`_answer_tool_call` unpacks `SubmitResult`)
- [ ] T10 — RED: backend→trajectory counts, schema `0033/1`, legacy `0031/1` validates, report untouched
- [ ] T11 — GREEN: backend threading + `build_trajectory_record` fields + version-gated validator
- [ ] T12 — RED: `run_verified_case` names + chains the typed degrade cause (`__cause__`)
- [ ] T13 — GREEN: capture cause outside except, chain `from`, delete dead shadowed assignment
- [ ] T14 — Integration: astropy live re-run — surviving>0 when scoped-grep cited, else NOT-EXERCISED
- [ ] T15 — Doc: conventions.md tool-contract rule + 0012→0025→0033 history + two-normalize-passes note
