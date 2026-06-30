---
spec: "0007"
---

# Tasks

- [x] T1 — Commit `FASTCONTEXT_INSTALL.md` + add FastContext local-path editable dependency at the pinned SHA (record non-portability deviation) [setup]
- [x] T2 — RED: `test_settings.py` scout field defaults (`scout_model` GGUF, `scout_max_tokens`/`scout_temperature`/`scout_reasoning_effort`) + precedence
- [x] T3 — GREEN: append the four Scout `Settings` fields last with defaults
- [x] T4 — RED: `test_scout_error_causes_are_distinct_identifiers` (`fastcontext-missing` / `cli-missing`)
- [x] T5 — GREEN: add `FASTCONTEXT_MISSING` / `CLI_MISSING` to `scout/errors.py`
- [x] T6 — RED: `FC_*` mapping + `_managed_fc_env` set-then-restore (unset-vs-empty, restore-on-exception)
- [x] T7 — GREEN: `scout/client.py` `_fc_env_from_settings` + `_managed_fc_env`
- [x] T8 — RED: Path A air-gap-before-construct (AC2), trajectory-outside-repo (AC7), parse `<final_answer>` (AC5), running-loop worker-thread bridge (D1)
- [x] T9 — GREEN: `DefaultFastContextClient` Path A + `parse_final_answer` + `_run_coro_on_worker_thread`
- [x] T10 — RED: lock held across full `agent.run()` (AC3 span) + parallel-threads no `FC_MODEL` cross-contamination (AC4)
- [x] T11 — GREEN: module `threading.Lock` single-flight; `FC_*` injected under the lock across the full run
- [x] T12 — RED: Path B injected runner (AC6), assert-local-before-spawn (AC2 Path B), env-scoped-to-child (D2 Path B)
- [x] T13 — GREEN: Path B CLI branch via injected `cli_runner` + `which`, child `env=`
- [x] T14 — RED: fallback causes — `fastcontext-missing` (runner unwired), `cli-missing`, `connection-refused`, `no-endpoint-configured`, `backend-error` (cause preserved), `rg`-floor propagates, weak citations stay honest-empty (AC10)
- [x] T15 — GREEN: fallback state machine + cause mapping (`raise ... from err`)
- [x] T16 — RED: `test_build_scout_engine_wires_default_client`
- [x] T17 — GREEN: `scout/wiring.py::build_scout_engine` (production `scout_factory`)
- [x] T18 — RED: integration — read-only byte-unchanged (AC8), network-deny Path A (AC9), live flip (AC1/AC11), skip-not-fail
- [x] T19 — GREEN: integration passes when env present / skips otherwise; wire `scout_factory=build_scout_engine`
- [x] T20 — REFACTOR: extract shared citation parsing if it duplicates `deep/rlm.py`; tidy `_managed_fc_env`
