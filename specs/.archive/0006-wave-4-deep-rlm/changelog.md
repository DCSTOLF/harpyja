---
spec: "0006"
closed: 2026-06-27
---

# Changelog — 0006 Wave 4 — Deep (RLM)

## What shipped vs spec

Tier 2 (Deep) landed as specified: a `dspy.RLM` explorer driven through four
bounded, read-only host tools inside a host-terminable sandbox, reached only via
`mode=deep`. `mode=auto` stays byte-identical and model-free; `mode=fast` stays
Scout. The Verification Gate and the Tier-0→1→2 auto-escalation ladder remain
deferred to Wave 5, as scoped. All 24 TDD tasks complete; full suite **413 passed
/ 1 skipped**, ruff clean. The four live integration ACs (AC8b / AC10a / AC11 /
AC12) were verified **PASSING** against the real stack.

### New package `harpyja/deep/`

- `DeepBackend` Protocol (`run(query, seed, tools) -> list[CodeSpan]`) — injected,
  no top-level `import dspy`, so an absent package/sandbox can never break the suite
  (mirrors the Wave-3 `ScoutBackend` seam). A fake backend drives all unit tests.
- `DeepEngine` — self-seeds its own Tier-0 lookup **before** the backend; exposes a
  **dual surface**: `.search(query, scope) -> list[CodeSpan]` for `Locator`
  conformance **and** `run(query, seed) -> (citations, truncated_bound | None)`,
  because the truncation bound is metadata the bare `list[CodeSpan]` `.search`
  contract cannot carry.
- `DeepBudget` — pure-Python per-request meter (tool-calls / tokens / depth /
  subqueries counters + wall-clock) against the `deep_max_*` caps, exposing a
  `truncated_bound: str | None`.
- `DeepUnavailable` — typed degrade error with stable causes
  `{sandbox-absent, rlm-down, backend-error}`.
- `build_host_tools` — exactly `{list_manifest, search, symbols, read_span}`, each a
  thin wrapper over existing Tier-0 machinery, repo-path-confined via the existing
  `server.tools.confine_path` and bounded by the existing `Settings` clamps. No
  mutating operation exists (read-only by construction).
- `DeepRunner` — the host-terminable out-of-band execution boundary: an in-process
  counter facet (tool-calls / tokens / depth / subqueries, unit-testable) plus an
  out-of-band subprocess `run_isolated` that **hard-kills** on `deep_wall_clock_ms`.
- `RlmBackend` — `dspy.RLM` impl via an injected runner, fresh instance per request,
  no top-level `import dspy`.
- `wiring.build_deep_engine` — the real `deep_factory`.

### Orchestrator

- `mode=deep` → Tier 2 (`tiers_run = [0, 2]`, `source_tier = 2`); removed `"deep"`
  from `_SCOUT_MODES` (→ `{"fast"}`) and **deleted** `_DEEP_PENDING`.
- `_locate_deep` degrades to Scout best-effort **only** on a typed `DeepUnavailable`
  (prepends `deep-degraded:<cause>`; `tiers_run` `[0, 1]` on Scout success, `[0]` on
  double-degrade carrying **both** `deep-degraded:<cause>` and `scout-degraded:<cause>`).
- Weak/zero citations stay an honest Tier-2 result — no ungated escalation.
- `RipgrepMissingError` (seed runs first) and `AirGapError` propagate as the floor.

### Shared

- `normalize_spans` generalized to explicit `max_citations` / `max_span_lines`; kept
  a thin `normalize_spans_for_scout` wrapper so every Scout call site stays byte-green.
- 8 additive `deep_*` Settings (appended last, with defaults): `deep_seed_top_n=5`,
  `deep_max_citations=20`, `deep_max_span_lines=200`, `deep_max_depth=3`,
  `deep_max_subqueries=8`, `deep_max_tool_calls=200`, `deep_token_ceiling=32000`,
  `deep_wall_clock_ms=60000`.
- `build_app` gained a `deep_factory` param.
- `dspy` added to dependencies (`pyproject.toml` / `uv.lock`).

## AC-by-AC status

- **AC1** [unit] PASS — `tiers_run==[0,2]`, `source_tier==2`, reached behind the
  `DeepEngine` Locator adapter; orchestrator/formatter never branch on `DeepBackend`.
- **AC2** [unit] PASS — `mode=auto` byte-identical, zero Gateway/Deep calls;
  `mode=fast`→Scout.
- **AC2a** [unit] PASS — lockstep guard **inversion** shipped atomically: the two
  Wave-3 guards `test_locate_deep_attaches_pending_note` /
  `test_locate_deep_no_tier2_marker` deleted and replaced by
  `test_locate_deep_emits_tier2_marker_when_wired` in the same change.
- **AC3** [unit] PASS — self-seed top-`deep_seed_top_n` hints to backend;
  `RipgrepMissingError` from seed propagates, backend never called.
- **AC4** [unit] PASS — `DeepBackend` Protocol + injected fake.
- **AC5 / AC5a** [unit] PASS — typed-failure-only degrade; weak/zero output stays an
  honest Tier-2 result; no quality/timeout heuristic raises `DeepUnavailable`.
- **AC6** [unit] PASS — `AirGapError` + seed `RipgrepMissingError` propagate as floor,
  never a `deep-degraded` note.
- **AC7** [unit] PASS — host-tool repo-path confinement + `Settings` clamps.
- **AC8** [unit] PASS — host-tool surface is read-only.
- **AC8a** [unit] PASS — positive-equality whitelist (deno-less backstop).
- **AC8b** [integration] PASS — **real** sandbox denies ambient `open()` outside and
  inside the repo and denies a non-loopback socket connect.
- **AC9** [unit] PASS — `DeepBackend` output normalized with the deep budgets.
- **AC10** [unit] PASS — externally-enforced bounds enforce at the harness seam
  (tool-call counter + token counter) + wall-clock unit facet.
- **AC10a** [integration] PASS — a **real** `dspy.RLM` forward is hard-killed by the
  wall-clock deadline → `deep-truncated:wall-clock`.
- **AC11** [integration] PASS — **real** end-to-end `mode=deep`.
- **AC12** [integration] PASS — **real** network-deny run, zero non-loopback egress.
- **AC13** [unit] PASS — zero Deep calls on index / read / auto / fast.

## Deviations from spec

- **Headline: the RLM owns its own model client.** The spec assumed the RLM is driven
  via `gateway.complete`. The real `dspy.RLM` OWNS its own `dspy.LM` (litellm) and
  does **not** accept a model_fn. `RlmBackend` was reworked: it calls
  `gateway.assert_local(settings.lm_api_base)` **before** constructing the LM (the
  single air-gap helper), and the air-gap is then **proven** by the network-deny
  integration test (AC12) — exactly the "third-party in-process code opens its own
  socket = assumption verified by test" honest-limit the conventions already encode.
  The reworked unit tests assert assert-local-before-factory +
  AirGapError-blocks-before-factory + fresh-instance-per-request + citation parsing,
  replacing the earlier (wrong) `gateway.complete`-routing assertions.
- **Self-seed lives in `DeepEngine`.** The orchestrator calls `deep_engine.run(query)`
  with no pre-seed; the Tier-0 seed runs inside the engine before the backend.
- **AC8b honest finding.** `import socket` / `socket.socket()` SUCCEEDS in Pyodide
  (stub) but a CONNECT to a non-loopback address fails (no network) and ambient
  `open()` fails (empty WASM FS). The test asserts connect-denial + FS-denial, not
  import failure.
- **AC11/AC12 assert pipeline shape, not citation quality.** A weak 4B model yields
  low-quality output, so the live ACs assert valid (possibly-empty) `CodeSpan`s, not
  citation quality.

## Live-run environment

dspy 3.2.1, Deno 2.9.0, Ollama on loopback (qwen2.5-coder:3b used in tests;
FastContext-1.0-4B also present), ripgrep 15.1.0. Cold live run ~50s, warm ~15s.

## Files touched

- `harpyja/deep/backend.py`, `budget.py`, `engine.py`, `errors.py`,
  `host_tools.py`, `rlm.py`, `runner.py`, `wiring.py` (new)
- `harpyja/deep/test_deep.py`, `test_host_tools.py`, `test_deep_integration.py` (new)
- `harpyja/orchestrator/locate.py`, `format.py`
- `harpyja/scout/normalize.py`
- `harpyja/config/settings.py`
- `harpyja/server/app.py`
- `harpyja/orchestrator/test_locate.py`, `test_formatter.py`,
  `harpyja/scout/test_scout_normalize.py`, `harpyja/server/test_app.py`
- `pyproject.toml`, `uv.lock`
