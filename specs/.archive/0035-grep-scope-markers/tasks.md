---
spec: "0035"
---

# Tasks

- [x] T1 — Characterization pins: grep honest-empty dir, ls-on-file `[]`, confine_path non-strict resolve, Deep file-scope no-defect (all stay green)
- [x] T2 — RED: grep file-scope delegates to real matches; nonexistent scope returns `grep-scope-not-found` marker before delegation; file-scope zero-match delegates to `[]`
- [x] T3 — GREEN: delete grep `is_dir()` guard, add `exists()` marker branch before the engine call, widen return annotation
- [x] T4 — Pins: marker visible + non-terminal in the loop, repeated bad scope trips loop detection, marker not flagged as execution-error (zero loop changes)
- [x] T5 — RED: ls nonexistent path returns `ls-path-not-found` marker
- [x] T6 — GREEN: ls `exists()` marker branch first, keep existing-file `[]` (OQ1), widen return annotation
- [x] T7 — RED: Deep `search` nonexistent scope returns `search-scope-not-found` marker instead of the uncaught `FileNotFoundError` crash
- [x] T8 — GREEN: add the exists-guard-before-engine to `host_tools.search`, keep `_charge()` first, widen return annotation
- [x] T9 — RED: persistent-artifacts helper tests (path shape, writer reuse + repo/out-dir separation, inside-repo refusal, no Settings field)
- [x] T10 — GREEN: add `harpyja/eval/live_artifacts.py` (`live_artifact_dir` + `write_live_artifact` over `atomic_write_json`)
- [x] T11 — Harness: migrate live integration tests to the persistent path; add AC6 live-marker-in-persisted-trajectory test with the 0023 NOT-EXERCISED fallback (skip-not-fail)
- [x] T12 — Doc: conventions.md — typed unsearchable-scope marker rule, file-scope-delegation convergence, persistent-artifacts harness rule
- [x] T13 — Refactor (optional): evaluate a shared `_scope_marker` helper; recommend leaving the three guards separate
