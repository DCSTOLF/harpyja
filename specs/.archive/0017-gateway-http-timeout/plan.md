---
spec: "0017"
status: planned
strategy: tdd
---

# Plan — 0017 gateway_http_timeout (the B3 fix)

The B3 fix in one line: give the gateway's outbound `urlopen` a **finite,
config-driven timeout** so a silent-but-accepting endpoint raises instead of
wedging forever, and let the gate's *existing* `except Exception → failed=True`
turn that raise into a graceful, **visibly-named** degrade.

Groups (data path order): Settings field → gateway field + transport threading →
propagation/stall proofs → seam + air-gap regression locks → gate degrade +
visibility → both wiring sites → doc blast-radius → optional live integration.

Load-bearing ACs: **3** (timeout supplied to the blocking op), **5** (timeout
degrades gracefully), **7** (deterministic real-socket stall proof).

## Test-first sequence

### Step 1 — Settings timeout field (RED) — AC1
- Add to `harpyja/config/test_settings.py`:
  - `test_settings_has_http_timeout_default` — `Settings().lm_http_timeout_s == 120.0`, `isinstance(..., float)`, is finite and `> 0`, and (field-introspection over `dataclasses.fields`) the default is **not `None`**.
  - `test_http_timeout_coerces_float_from_toml` — `lm_http_timeout_s = 5.0` in toml resolves to `5.0` as a `float`.
  - `test_http_timeout_coerces_float_from_env_beats_toml` — `HARPYJA_LM_HTTP_TIMEOUT_S=2.5` over a toml `10.0` resolves to `2.5` (env > toml), and `base` (a prior `load_settings`) is unchanged (frozen `replace`, no per-request layer per D2).
- Tests fail: `Settings` has no `lm_http_timeout_s` field → `AttributeError` / the toml+env keys are dropped by `_known` (not in `_FIELD_TYPES`).

### Step 2 — Add `Settings.lm_http_timeout_s` (GREEN) — AC1
- Edit `harpyja/config/settings.py`: append (last field, after the verify block) `lm_http_timeout_s: float = 120.0` with a one-line comment (spec 0017 D1: seconds, finite, decoupled from `deep_wall_clock_ms`). No `_coerce` change needed — the existing `float` branch handles it; `_from_toml`/`_from_env` pick it up automatically via `_FIELD_TYPES`.
- All step-1 tests pass.

### Step 3 — Gateway timeout field + supplied to the blocking op + real stall (RED) — AC2, AC3, AC7
- Add to `harpyja/gateway/test_gateway.py`:
  - `test_modelgateway_timeout_s_dataclass_default_is_finite` (AC2) — a bare `ModelGateway(api_base="http://127.0.0.1:11434/v1")` has `gw.timeout_s` a finite positive `float`, **not `None`** — independent of `Settings`, closing the direct-construction gap.
  - `test_default_transport_passes_timeout_to_urlopen` (AC3) — monkeypatch `harpyja.gateway.gateway.urlopen` to capture kwargs (returning a fake response context manager); drive `ModelGateway(api_base=loopback, timeout_s=3.5).complete([...])` with `transport=None`; assert the captured `timeout` kwarg is **non-`None`, `> 0`, and `== 3.5`** (really threaded to the socket op, not dropped).
  - `test_gateway_complete_raises_on_silent_server_within_bound` (AC7) — bind a `127.0.0.1:0` listener that `accept()`s in a daemon thread then **withholds all bytes**; `ModelGateway(api_base=f"http://127.0.0.1:{port}/v1", timeout_s=0.25).complete([...])` (default transport) must **raise** a timeout (`TimeoutError`/`socket.timeout`/`URLError`) with measured wall-clock **well under ~1 s**; `try/finally` closes the socket so the test itself cannot hang. Loopback-only, no Ollama.
- Tests fail: `ModelGateway` has no `timeout_s` field (constructor `TypeError`) and `_default_transport` calls `urlopen(req)` with no `timeout=` (AC7 would hang → the tiny-timeout constructor arg does not yet exist, so it errors first).

### Step 4 — Thread the timeout through the gateway (GREEN) — AC2, AC3, AC7
- Edit `harpyja/gateway/gateway.py`:
  - `import functools`.
  - `_default_transport(url, payload, *, timeout_s: float = 120.0)` — keyword-only `timeout_s` with a **finite** default; `urlopen(req, timeout=timeout_s)` (keep the `# noqa: S310`).
  - Add `timeout_s: float = 120.0` to the `ModelGateway` dataclass (D3: field default itself finite, never `None`).
  - In `complete()`, bind the timeout onto the default transport **only when `transport is None`**: `send = transport or functools.partial(_default_transport, timeout_s=self.timeout_s)`. The `Transport` alias `(url, payload) -> dict` is unchanged.
- All step-3 tests pass. (The 120.0 field default matching the 120.0 Settings default is intentional; step-8 wiring tests use a non-default value to prove real threading.)

### Step 5 — Seam + propagation + air-gap regression locks (RED-as-lock) — AC4, AC8, AC9
These assert behavior the change must **preserve**; they pass at Step-4 green and each fails under a plausible *wrong* implementation (e.g. binding the `partial` onto an injected transport, catching inside the gateway, or reordering the air-gap).
- Add to `harpyja/gateway/test_gateway.py`:
  - `test_gateway_complete_uses_injected_transport_unchanged` (AC8) — inject a strict two-arg `def transport(url, payload)` (no `**kwargs`); assert `complete(...)` succeeds and the transport received exactly two positional args (no `timeout_s` leaked in). Fails if the `partial` is bound unconditionally instead of only-when-`transport is None`.
  - `test_gateway_complete_propagates_transport_timeout` (AC4) — inject a transport that raises `TimeoutError`; assert it **propagates out of** `complete()` (the gateway neither catches nor converts it). The fake makes the test itself non-hanging. Distinct from AC3 (supplied) — this proves *not swallowed*.
  - `test_gateway_complete_default_transport_never_called_for_remote` (AC9) — monkeypatch `urlopen` to raise `AssertionError` if invoked; `ModelGateway(api_base="http://8.8.8.8:11434/v1")` `.complete([...])` (no injected transport) raises `AirGapError` and `urlopen` is **never** called — the timeout-bearing default transport stays behind the assert-local-first floor.
- All still green (locks); production unchanged in this step.

### Step 6 — Gate degrades on timeout, visibly named (RED) — AC5, AC6
- Add to `harpyja/orchestrator/test_gate.py`:
  - `test_gate_degrades_on_judge_timeout` (AC5, load-bearing) — a fake judge that raises `TimeoutError`; `VerificationGate.verify(...)` returns `GateOutcome(passed=False, failed=True)` — no raise, not a silent pass. (Extends the existing `_CountingJudge` with a `raises=TimeoutError(...)` path or a small inline judge.)
  - `test_gate_logs_timeout_naming_warning_on_timeout` (AC6) — on the timeout degrade path, `caplog.at_level(WARNING)` captures a record whose message **names the timeout** (e.g. contains "timed out"/"timeout"), distinct from the generic "scoring failed" wording.
  - `test_gate_timeout_log_distinct_from_parse_failure` (AC6) — a judge raising a non-timeout `RuntimeError` produces the generic "scoring failed" WARNING and **not** the timeout-naming one, so the two degrade causes are separable in operator diagnostics.
- AC5 passes pre-change (the generic `except Exception` already yields `failed=True`) — recorded as a lock; **AC6 fails**: the current `except` logs only `"verification gate scoring failed"` and never names the timeout.

### Step 7 — Distinguish the timeout in the gate's degrade log (GREEN) — AC6
- Edit `harpyja/orchestrator/gate.py`: `import socket` and `from urllib.error import URLError`; in `VerificationGate.verify`'s `except Exception as err:` block, branch — if `isinstance(err, (TimeoutError, socket.timeout, URLError))` log a **timeout-naming** WARNING (e.g. `logger.warning("verification gate judge timed out: %r", err, exc_info=True)`), else keep the existing `"verification gate scoring failed"` WARNING. Both paths still `return GateOutcome(passed=False, failed=True, ...)` — no schema change (D4). (`socket.timeout` is an alias of `TimeoutError` on py3.10+; `URLError` covers `urlopen`'s wrapped read-timeout.)
- Step-6 tests pass; the existing `test_gate_scoring_failed_when_judge_raises` stays green.

### Step 8 — Both wiring sites carry the configured timeout (RED) — AC10
- Add to `harpyja/orchestrator/test_wiring.py`:
  - `test_build_verification_gate_threads_http_timeout` — `build_verification_gate(Settings(lm_http_timeout_s=7.5), "/some/repo").gateway.timeout_s == 7.5` (a **non-default** value proves the field is drawn from `Settings`, not the 120.0 dataclass fallback or a literal).
- Add to `harpyja/scout/test_scout_wiring.py`:
  - `test_build_scout_engine_threads_http_timeout` — build with `Settings(lm_http_timeout_s=7.5)`; assert the constructed gateway's timeout rode through: `engine._backend._tools["model"].timeout_s == 7.5` (the scout backend stores the gateway as the `"model"` tool via `build_tool_whitelist`).
- Tests fail: both wiring sites construct `ModelGateway(...)` without `timeout_s`, so it falls back to the `120.0` field default `!= 7.5`.

### Step 9 — Pass `timeout_s` at both construction sites (GREEN) — AC10
- Edit `harpyja/orchestrator/wiring.py` (`build_verification_gate`, ~line 22): add `timeout_s=settings.lm_http_timeout_s` to the `ModelGateway(...)` call (the observed B3 hang path).
- Edit `harpyja/scout/wiring.py` (`build_scout_engine`, ~line 61): add `timeout_s=settings.lm_http_timeout_s` to the `ModelGateway(...)` call (defense-in-depth; Path A is vestigial but every constructed gateway stays uniformly bounded).
- Step-8 tests pass.

### Step 10 — Doc blast-radius (doc) — AC12
- `harpyja/config/settings.py`: the `lm_http_timeout_s` field comment (added Step 2) + the module-docstring toml example gains a `lm_http_timeout_s = 120.0` line.
- `harpyja/gateway/gateway.py`: update `_default_transport`'s docstring — it currently claims "kept tiny and stdlib-only" with no mention of the bound; note it is time-bounded by the injected `timeout_s` (per-socket-op, not a total deadline).
- README / ARCHITECTURE Model Gateway note: record that the single outbound call is timeout-bounded.
- Changelog / history: record the B3 fix from spec 0015 (`live-run-findings.md`).
- No test; a `grep -rn lm_http_timeout_s` confirms every consumer is consistent.

### Step 11 — Optional live-Ollama happy-path smoke (integration) — AC11
- Add to `harpyja/gateway/test_gateway.py` (or `test_gate.py`): `test_gateway_complete_live_ollama_under_timeout` decorated `@pytest.mark.integration`. Against a reachable local Ollama, a `complete()` (or gate `verify()`) returns **well under** the configured timeout and never hangs; env-gated, `pytest.skip(...)` (never fail) when Ollama is absent. Explicitly documents the happy path — it is **not** the stall proof (AC7 is) and must not be read as validating the fix against a real stall.

## Delegation

- Steps 1–2 (Settings) → `config` owner. Straight additive field + coercion reuse; lowest risk.
- Steps 3–5 (gateway field, transport threading, stall harness, locks) → `gateway` owner. AC7's loopback silent-server harness is the one novel test-infra piece; keep it self-contained and time-bounded.
- Steps 6–7 (gate degrade visibility) → `orchestrator` owner. Small, surgical edit inside an existing `except`.
- Steps 8–9 (wiring) → whoever owns each `wiring.py`; both are one-kwarg edits.
- Step 10 doc / Step 11 integration → same owner as the gateway change (keeps the blast-radius in one change per convention).

## Risk

- **AC7 harness could hang the suite** if the listener/socket outlives the test → mitigation: `timeout_s=0.25`, bind on `127.0.0.1:0`, accept in a daemon thread, `try/finally` close the listener + client sockets, and assert measured elapsed `< ~1 s` so a regression that drops the timeout fails loudly instead of blocking.
- **Timeout exception type varies** (`urlopen` may surface `socket.timeout`/`TimeoutError` directly or wrapped in `URLError`) → mitigation: Step 7 catches all three; Step 3/AC7 asserts on the union, not one concrete class.
- **AC10 false-positive on the shared 120.0 default** (field default == Settings default would let an un-threaded wiring pass) → mitigation: wiring tests use a non-default `7.5`.
- **`120.0 s` vs eval-host Ollama cold-load first-byte** (review plan item) → mitigation: confirm the default reads right against the live host at implementation time; it is toml/env-overridable and decoupled from `deep_wall_clock_ms` (D1).
- **Scout-gateway introspection path** (`_backend._tools["model"]`) is a private seam that could drift → mitigation: if `build_tool_whitelist` changes shape, prefer capturing the `ModelGateway(...)` kwargs in `scout/wiring.py` via a monkeypatched constructor spy instead.
