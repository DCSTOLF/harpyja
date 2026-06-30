---
spec: "0005"
closed: 2026-06-27
---

# Changelog — 0005 Wave 3 — Scout

## What shipped vs spec

Tier 1 (Scout) and the Model Gateway **request path** landed as an explicit-opt-in
capability: `mode=auto` is byte-identical to Wave 2 with zero Gateway calls, `mode=fast`
runs Scout, and `mode=deep` provisionally mirrors `fast` (best-available tier) with a
`Deep pending` note. All 31 TDD tasks complete; full suite 359 passed / 1 skipped (the
live AC1), ruff clean.

- New `harpyja/scout/` package: `ScoutBackend` Protocol (`run(query, seed) -> list[CodeSpan]`),
  `ScoutEngine` (self-seeds via the `seed_fn` **before** the backend, behind the shared
  `Locator` `.search` seam), `normalize_spans` (drops/clamps hostile `<final_answer>`
  output), `build_tool_whitelist` (exact four-tool set), `FastContextBackend` (injected
  client, no hard import), and a `ScoutUnavailable` error carrying a stable `cause`.
- Gateway request path: `ModelGateway.complete()` asserts the air-gap (resolution-time,
  via the injected resolver) **before** an injected transport — no request leaves the
  process until loopback is proven.
- Four-state degradation floor wired in `locate.py`: Scout-ok → `tiers_run=[0,1]`;
  model-down + Tier-0-results → `degraded` + `scout-degraded:<cause>`; Tier-0
  honestly-empty → same note + `+no-matches`; Tier-0 precondition absent
  (`RipgrepMissingError`) → propagates loudly. `AirGapError` propagates as a floor
  violation, never a note.

### AC-by-AC status

- AC1 `[integration]` — SHIPPED as skip-not-fail (`test_scout_fast_returns_tier1_citations_live`);
  deterministic shape assertions covered by the unit ACs below. (The 1 skipped test.)
- AC2 `[unit]` — PASS. `auto` byte-identical + zero Gateway calls (`_BoomScout` double),
  re-locked after the `_tier0_seed` refactor (T27).
- AC3 `[unit]` — PASS. Self-seed runs as part of the Scout path; top-`scout_seed_top_n` hints reach the backend.
- AC4 `[unit]` — PASS. `gateway.complete()` enforces loopback on resolved addresses before any send. (See deviation 1.)
- AC5 `[unit]` — PASS. All four degrade states + three distinct cause notes; `rg`-missing-and-model-down asserts state 4 wins; non-loopback raises.
- AC6 `[unit]` — PASS. Scout behind `Locator`; `FastContextBackend` is one impl; fake backend injected; no engine-identity branching.
- AC7 `[unit]` — PASS. Hostile output (outside-root, nonexistent, inverted/out-of-range, dupes, over-budget) clamped or dropped.
- AC8 `[unit]` — PASS. `mode=deep` attaches `Deep pending`, no `2` in `tiers_run`, no Tier-2 marker.
- AC9 `[unit]` — PASS. `index`/`read`/`auto`-`locate` make zero Gateway calls.
- AC10 `[unit]` — PASS. Positive equality on the exact four-tool whitelist.
- AC11 `[integration]` — PASS (deterministic). Scout runs to completion under network-deny with a loopback-only endpoint.

## Deviations from spec

1. **`NonLoopbackEndpointError` → reused Wave-0 `AirGapError`.** The spec named a new
   typed air-gap error; per the single-air-gap-helper guardrail the implementation reused
   the existing `AirGapError(ValueError)` (its message already names the offending host).
   Wave-0 `assert_local` already enforced resolution-time air-gap (injected resolver +
   `ipaddress` loopback predicate), so AC4's genuinely-new work was the Gateway **request
   path** (`ModelGateway.complete()`), not the resolver seam.
2. **One `scout_engine` param, not a separate gateway param.** The Gateway lives *inside*
   the injected Scout engine (single outbound abstraction), so `locate` gained one
   `scout_engine: _Engine | None` param matching the existing `engine` / `symbol_engine`
   DI style.
3. **`mode=deep` is provisionally identical to `mode=fast`.** Both route to Scout;
   `deep` adds the `Deep pending` note and asserts no Tier-2 marker. They diverge when
   Deep lands.
4. **Stable note identifiers.** Degrade notes are machine-readable strings
   (`scout-degraded:{connection-refused|no-endpoint-configured|backend-error}`, `+no-matches`
   suffix for honestly-empty Tier-0), so callers/tests branch on identifiers, not prose.
5. **Scout is not cached** — model-backed/non-deterministic, no engine-identity / cache slot.
6. **FastContext package/version remains the sole open question**, isolated behind the
   `ScoutBackend` Protocol (injected client, no top-level hard import).

## Files touched

- harpyja/server/types.py (added `"degraded"` to `Confidence`)
- harpyja/config/settings.py (`scout_seed_top_n=5`, `scout_max_citations=20`, `scout_max_span_lines=200`)
- harpyja/gateway/gateway.py (`ModelGateway.complete()` + `_default_transport` + `Transport` type)
- harpyja/orchestrator/format.py (`source_tier` param)
- harpyja/orchestrator/locate.py (`_tier0_seed`, `_locate_scout`, `_degrade`, `scout_engine` DI)
- harpyja/server/app.py (`scout_factory` wiring)
- harpyja/scout/{backend,engine,errors,fastcontext,normalize,tools}.py (new package)
- Tests: harpyja/{server/test_types,config/test_settings,gateway/test_gateway,orchestrator/test_formatter,orchestrator/test_locate,server/test_app}.py + harpyja/scout/{test_scout_normalize,test_scout,test_scout_integration}.py
