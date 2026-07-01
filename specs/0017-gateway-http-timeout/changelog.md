# Spec 0017 — gateway_http_timeout — changelog

Fixes **B3** from spec 0015 (`live-run-findings.md`): the Model Gateway's outbound
HTTP call had **no timeout**, so a stalled/torn-down local endpoint wedged the whole
run forever (observed 2.5 h at 0% CPU) — the reason no full OQ2 run ever finished.

## What shipped

- **Finite gateway HTTP timeout** — `_default_transport` (`gateway/gateway.py`) now
  calls `urlopen(req, timeout=timeout_s)` instead of an unbounded `urlopen(req)`. The
  timeout rides on a new `ModelGateway.timeout_s` field whose **dataclass default is
  itself finite** (`120.0`), so *any* `ModelGateway(...)` — not just the wired sites —
  is hang-bounded. It is bound onto the default transport via
  `functools.partial(_default_transport, timeout_s=self.timeout_s)` **only when
  `transport is None`**, so the injected two-arg `Transport` seam is untouched (D3).
  It is a per-socket-op bound, not a total-request deadline (stated, no-false-capability).
- **Config knob** — `Settings.lm_http_timeout_s: float = 120.0` (`config/settings.py`),
  coerced from toml/env like the other numerics; precedence defaults < toml < env, **no**
  per-request layer (D2). Default `120.0 s` deliberately **decoupled** from
  `deep_wall_clock_ms` (60 s) — they bound different things (D1).
- **Graceful, visible degrade** — the Verification Gate's existing
  `except Exception → GateOutcome(failed=True)` now **fires** (an un-timed-out `urlopen`
  never raised). Per D4 / the 0014 visibility convention, the timeout path logs a
  **distinct timeout-naming WARNING** (`orchestrator/gate.py`: branch on
  `TimeoutError`/`socket.timeout`/`URLError`) so "judge timed out" is separable from a
  parse/other failure. No schema change.
- **Both wiring sites** — `orchestrator/wiring.py` (the observed B3 hang path) and
  `scout/wiring.py` (defense-in-depth) construct `ModelGateway(..., timeout_s=
  settings.lm_http_timeout_s)`.
- **Docs** — `settings.py` field comment + module-docstring toml example,
  `_default_transport` docstring (now states the bound), ARCHITECTURE §2.8 Model Gateway,
  and the README Configuration knob list all name the timeout.

## Tests

- `config/test_settings.py`: default-is-finite (field introspection), toml + env>toml
  coercion (AC1).
- `gateway/test_gateway.py`: dataclass-default-finite (AC2), timeout supplied to
  `urlopen` via monkeypatch (AC3), **deterministic loopback silent-server stall proof**
  — accept-then-withhold-bytes, `timeout_s=0.25`, raises in <1 s (AC7); plus preservation
  locks — injected transport used verbatim (AC8), timeout propagates not swallowed (AC4),
  air-gap-first on the default-transport path (AC9).
- `orchestrator/test_gate.py`: degrades-on-timeout (AC5), timeout-naming WARNING asserted
  on the record **message** not the exc_info traceback (AC6), and distinct-from-generic
  (AC6).
- `orchestrator/test_wiring.py` + `scout/test_scout_wiring.py`: both sites thread a
  non-default `7.5` (AC10) — scout via a constructor spy (robust to the vestigial backend
  tool shape).
- `gateway/test_gateway.py` (or gate): optional `@pytest.mark.integration` live-Ollama
  happy-path smoke, skip-not-fail, explicitly **not** the stall proof (AC11).

## Out of scope (unchanged)

B2 (gate-as-judge false-escalation) remains a separate gate-quality spec; a total-request
deadline / dribble-slow defense, Deep's dspy/litellm timeout, and retry/backoff are
follow-ups. Re-attempting the OQ2 measurement is a fresh spec now that B1 (0016) + B3
(this) are fixed.
