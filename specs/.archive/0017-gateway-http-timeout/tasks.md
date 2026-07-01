---
spec: "0017"
---

# Tasks

- [x] T1 [RED] Settings timeout-field tests in `config/test_settings.py` — AC1
- [x] T2 [GREEN] Add `Settings.lm_http_timeout_s: float = 120.0` — AC1
- [x] T3 [RED] Gateway `timeout_s` default + urlopen-timeout + silent-server stall tests in `gateway/test_gateway.py` — AC2, AC3, AC7
- [x] T4 [GREEN] `ModelGateway.timeout_s` field + `_default_transport(timeout_s=)` + `functools.partial` bind only when `transport is None` — AC2, AC3, AC7
- [x] T5 [RED] Seam-preserved / propagation / air-gap-first regression locks in `gateway/test_gateway.py` — AC4, AC8, AC9
- [x] T6 [RED] Gate degrades-on-timeout + timeout-naming WARNING tests in `orchestrator/test_gate.py` — AC5, AC6
- [x] T7 [GREEN] Gate `except` branches timeout vs generic, emits distinct WARNING (`gate.py`) — AC6
- [x] T8 [RED] Wiring threads timeout tests (`orchestrator/test_wiring.py`, `scout/test_scout_wiring.py`, non-default value) — AC10
- [x] T9 [GREEN] Pass `timeout_s=settings.lm_http_timeout_s` at both wiring sites — AC10
- [x] T10 [doc] Blast-radius: settings comment + toml example, `_default_transport` docstring, README/ARCHITECTURE, changelog B3 entry — AC12
- [x] T11 [integration] Optional live-Ollama happy-path smoke, skip-not-fail, NOT the stall proof — AC11
