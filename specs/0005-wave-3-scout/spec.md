---
id: "0005"
title: "Wave 3 — Scout"
status: closed
created: 2026-06-27
authors: [claude]
packages: [harpyja/scout, harpyja/gateway, harpyja/orchestrator]
related-specs: ["0002", "0003"]
---

# Spec 0005 — Wave 3 — Scout

## Why

Tier 0 (Waves 1–2) answers symbol and literal point-lookups deterministically,
for free, and offline. But it goes blind on natural-language / conceptual
queries ("where do we validate auth tokens?", "how does retry backoff work?")
that don't name a symbol or a literal — ripgrep has nothing to match and the
symbol index has no entry, so the honest Tier-0 answer is "nothing found."

Wave 3 introduces **Tier 1 — Scout**, a thin adapter over Microsoft FastContext
and Harpyja's first model-backed tier. Scout lets an explorer model run
read-only `Read`/`Glob`/`Grep` exploration to answer those exploratory queries,
while preserving the two hard guarantees: **read-only** and **air-gap** (the
model is local-only, reached through a single gateway). It also lands the
**Model Gateway** — the one outbound abstraction every later tier (Deep, the
verification judge) builds on — so this wave is the seam where Harpyja first
talks to a model at all.

Because it is the first model wave, two guarantees that were previously cheap
become load-bearing and are specified precisely here: the air-gap is enforced at
**name-resolution time** (not against literal endpoint strings), and the
graceful-degradation **floor** is made explicit so a Scout fallback can never
collapse a physically-impossible Tier-0 run into a phantom "nothing found."

## What

This wave is scoped to a **shippable, explicit-opt-in** Scout: no change to the
default `auto` behavior, model cost only when a caller asks for it, and a
deterministic fallback whenever the model is unreachable.

### Model Gateway (`harpyja/gateway/`)

- The single outbound caller — a thin client over a local OpenAI-compatible
  endpoint (llama.cpp `llama-server` or Ollama). Holds the base URL + primary
  model from config/profile (`Settings`).
- **Air-gap enforced at resolution time.** `gateway.assert_local` takes an
  **injected resolver** (default: the stdlib resolver; a fake is injected in
  tests, per the conventions' `assert_local` resolver seam). It resolves the
  configured endpoint host through that resolver to its address set and asserts
  **every** resolved address is loopback — using the stdlib `ipaddress`
  loopback predicate (covers `127.0.0.0/8`, `::1`, and IPv4-mapped loopback),
  not a hand-rolled literal list. A host resolving to any non-loopback address
  is rejected; the literal string `localhost` is accepted only because it
  resolves to loopback, not by string match. No **request** is ever sent to a
  non-loopback address. Note the honest residual: validating a hostname requires
  resolving it, so a *misconfigured external* host leaks at most one lookup
  through the approved resolver before rejection. To keep even that at zero,
  endpoints **should** be IP-literals or hosts-file-resolvable names; this is
  the documented posture, not a silent guarantee.
- A configured non-loopback endpoint raises a typed, actionable error naming the
  offending host — never a silent skip. This air-gap violation is a **loud floor
  case**, deliberately *not* one of the four degrade states below (an absent
  endpoint degrades; a hostile/non-loopback endpoint raises).

### Scout tier (`harpyja/scout/`)

- A `ScoutBackend` Protocol (`query + seed spans → list[CodeSpan]`) with
  **FastContext as the first concrete impl**. The adapter exists only to (a)
  hand FastContext the query + seed hints and (b) normalize FastContext's
  `<final_answer>` block into Harpyja's shared `CodeSpan` shape. The Protocol
  keeps the integration swappable and lets tests inject a fake backend with no
  live model.
- **Reconciled with the shared boundary.** `ScoutBackend` produces `CodeSpan`s
  carrying `source_tier = 1`; the Scout entry point is exposed behind the same
  `Locator` protocol every tier implements, so the orchestrator/formatter never
  branch on which engine produced a span (conventions: "callers never branch on
  which engine ran"). FastContext is an implementation detail *inside* a
  `Locator`, not a parallel citation path.
- **FastContext gets only Harpyja-owned, local-only tools.** The adapter hands
  FastContext **exactly** this whitelist — bounded read-only `Read`/`Glob`/`Grep`
  wrappers plus the loopback-enforced Gateway model client — and never a raw
  `base_url`, env-derived endpoint config, an HTTP client / `requests` session,
  or any other transport. This constrains everything *Harpyja hands* FastContext.
  **Honest limit (no false-capability claim):** tool injection cannot by itself
  prevent in-process third-party code from opening its own socket — Scout runs
  in-process, with no WASM sandbox (unlike Tier 2 Deep). The air-gap for the
  model path is enforced at the Gateway; FastContext's own egress containment is
  an **assumption verified by test**, not an asserted guarantee: Scout
  integration tests run under a network-deny environment, and process-level
  sandboxing is tracked as a follow-up. The residual risk is recorded, not
  buried.
- **Not cached.** Scout output is model-backed and non-deterministic, so it is
  **not** persisted and carries **no engine-identity / cache slot**. There is no
  cache-identity surface to reason about here (this is called out explicitly to
  pre-empt the Wave-2 no-silent-coverage cache-slot question).

### Self-seeding Scout path

- Whenever Scout is invoked it runs its **own** lightweight Tier-0 lookup to
  gather seed spans and passes the top-N as hints to the backend — it does
  **not** rely on `auto` having run a prior Tier-0 pass (under `mode=fast` the
  caller skipped `auto`, so the seed must be part of the Scout path itself).
- **Ordering is contractual, not incidental.** The self-seed Tier-0 lookup runs
  **before** the backend call. So if `rg` is missing *and* the model is down,
  the seed step surfaces `RipgrepMissingError` first and the backend is never
  reached — degrade state 4 (loud) deterministically wins over state 2/3 by
  construction. The dangerous composition is impossible by ordering, not luck.
- **Concrete budgets** (defaults; `Settings`-configurable):
  - `scout_seed_top_n` — number of Tier-0 seed spans passed as hints. Default
    **5**, taken by the formatter's existing rank order (deterministic).
  - `scout_max_citations` — Scout result ceiling; clamped to
    `min(scout_max_citations, req.max_results)`. Default **20**.
  - `scout_max_span_lines` — max line-range per returned citation span. Default
    **200**; a span exceeding it is clamped to its first `scout_max_span_lines`
    lines.

### Routing — explicit mode only

- `mode=auto` → Tier 0, **byte-identical to Wave 2** (no model/Gateway call).
- `mode=fast` → run Scout (Tier 1) and stop; this is the explicit Scout trigger.
- `mode=deep` → Tier 2 does not exist yet. It routes to the **best-available**
  higher tier (Scout) and attaches a `Deep pending` note. Per the
  no-silent-coverage lockstep, the result must **not** report any Tier-2
  capability marker (no `tiers_run` entry `2`, no Tier-2 identity/cache key).
  **`fast` and `deep` are behaviorally identical this wave** — this is
  provisional, and `deep` will diverge (skip to Tier 2 after the Tier-0 seed)
  when Deep lands; the note marks the provisional state so that later change is
  not a surprise regression.

### Graceful degradation — the floor (four distinct caller-visible states)

A Scout call resolves to exactly one of four states; they must **never** collapse
into each other (a silent empty when Tier-0 physically can't run is the phantom
"nothing found" the floor exists to prevent):

1. **Scout succeeds** → Scout citations; `tiers_run = [0, 1]`.
2. **Model/Gateway unavailable, Tier-0 has results** → Tier-0 citations,
   `confidence = degraded`, `tiers_run = [0]`, with a note that **names the
   degrade cause** (one of: connection-refused / no-endpoint-configured /
   FastContext-raised — distinct notes per cause, per conventions).
3. **Model/Gateway unavailable, Tier-0 ran and is honestly empty** → empty
   result, `confidence` low/degraded, with a **distinct** note combining "no
   matches" + the degrade cause — never silently indistinguishable from state 2.
4. **Model/Gateway unavailable, Tier-0's own hard precondition is absent** (e.g.
   `rg` missing) → the typed actionable error (`RipgrepMissingError`)
   **propagates loudly**; it is *not* swallowed into a degraded-empty.

Notes are **stable machine-readable identifiers** (not free prose), so callers
and tests can branch on them: `scout-degraded:connection-refused`,
`scout-degraded:no-endpoint-configured`, `scout-degraded:backend-error` (the
FastContext-raised case), each optionally suffixed `+no-matches` for state 3.
The air-gap violation is the typed error `NonLoopbackEndpointError` (a floor
case, not a note).

## Acceptance criteria

Each AC is marked `[unit]` (runs against a fake `ScoutBackend` / injected
resolver, no network) or `[integration]` (`@pytest.mark.integration`, real
endpoint/process).

1. `[integration]` With a reachable local endpoint, `harpyja_locate(query, repo,
   mode="fast")` returns Scout citations whose `tiers_run` includes `1` and
   whose citations carry `source_tier = 1`; a conceptual query that yields
   nothing from Tier-0 returns non-empty citations via Scout. (To avoid a
   coin-flip on a live model, this test pins a fixture repo + query known to
   resolve; the deterministic shape assertions live in the `[unit]` ACs below,
   so a flaky model degrades this to a skip, not a false failure.)
2. `[unit]` `mode=auto` produces results **byte-identical** to the Wave-2 Tier-0
   locator over the same fixture tree — compared at the serialized
   `LocateResult` boundary (citations + confidence + `tiers_run` + notes) — and
   makes **zero** model/Gateway calls (asserted via a Gateway double that fails
   if called). Regression-locked.
3. `[unit]` When Scout is invoked, a lightweight Tier-0 seed lookup runs **as
   part of the Scout path** and its top-`scout_seed_top_n` spans are passed to
   the `ScoutBackend` as hints — asserted under `mode=fast` (i.e. with no prior
   `auto` Tier-0 pass), with a fake backend recording the hints it received.
4. `[unit]` `gateway.assert_local` enforces loopback on **resolved** addresses
   via an **injected resolver**: a host resolving only to loopback passes; a
   host resolving to any non-loopback address is rejected **before** any request
   or live DNS lookup. A test using a fake resolver proves no non-loopback
   egress is reachable without touching live DNS or the network.
5. `[unit]` The four degradation states are each exercised and produce distinct
   caller-visible outcomes: (2) Tier-0-has-results → `degraded` + cause-named
   note; (3) Tier-0 honestly empty → empty + distinct `+no-matches` + cause note;
   (4) Tier-0 hard-precondition absent → `RipgrepMissingError` propagates (does
   not raise-then-swallow; does not return empty). The three degrade causes
   (`connection-refused` / `no-endpoint-configured` / `backend-error`) each yield
   their distinct stable note identifier. A `rg`-missing **and** model-down case
   asserts state 4 wins (seed-before-backend ordering). A resolved non-loopback
   endpoint raises `NonLoopbackEndpointError`, *not* a degrade note.
6. `[unit]` Scout sits behind a `ScoutBackend` Protocol exposed as a `Locator`;
   FastContext is one impl; a fake backend is injected in tests without a live
   model (same DI seam as the existing `engine` / `symbol_engine` parameters in
   `locate`). The orchestrator/formatter do not branch on engine identity.
7. `[unit]` FastContext `<final_answer>` output is normalized into valid
   `CodeSpan` values and **hostile/malformed output is clamped or dropped, not
   propagated** — explicit cases: a path **outside the repo root**, a path to a
   **nonexistent file**, an **out-of-range / inverted line range**, **duplicate**
   citations (deduped), and an **over-budget** answer (more than
   `scout_max_citations`, or a span exceeding `scout_max_span_lines`).
8. `[unit]` `mode=deep` does not silently no-op: it routes to Scout, attaches a
   `Deep pending` note, and the result reports **no** Tier-2 capability marker
   (no `2` in `tiers_run`, no Tier-2 identity/cache key) — a lockstep regression
   guard.
9. `[unit]` `harpyja_index`, `harpyja_read`, and `mode=auto` `harpyja_locate`
   make **zero** model/Gateway calls (asserted via the Gateway double) —
   preserving the offline posture for every non-Scout path.
10. `[unit]` FastContext receives **exactly** the whitelist — the tool set handed
    to the backend equals `{Read, Glob, Grep wrappers, Gateway model client}` and
    nothing else (no raw `base_url`, no env-derived endpoint, no HTTP
    client/session, no arbitrary transport). Asserted as a positive equality on
    the injected object graph, not as an attempt to prove a negative. (Defense in
    depth for FastContext's *own* in-process egress is the network-deny
    integration env per the Scout-tier "honest limit", tracked toward a sandbox
    follow-up.)
11. `[integration]` Scout runs to completion under a **network-deny** environment
    with a loopback-only Gateway endpoint — proving (not merely asserting) that
    the model path needs no non-loopback egress. This is the verification step
    backing the Scout-tier "honest limit" on FastContext's in-process egress.

## Out of scope

- The **Verification Gate** (read-back scoring, LLM-judge / embedding) and the
  Tier-0 → 1 → 2 **escalation** ladder — a later wave.
- **Tier 2 / Deep** (`dspy.RLM` + bounded host tools).
- `auto` routing `broad → Scout` (auto stays pure Tier-0 this wave).
- Embedding / judge **sub-model** wiring.
- **Wave 2.1** substring/fuzzy symbol matching (separate follow-up).
- Provisioning the model runtime itself (pulling/quantizing weights, installing
  `llama-server` / Ollama) — Wave 3 assumes an endpoint is configured.
- **Process-level / WASM sandboxing of FastContext** (defense-in-depth against a
  third-party in-process egress side-channel) — tracked as a follow-up; Wave 3
  relies on tool-injection + the network-deny integration test (AC11).

## Open questions

- Exact FastContext package + version, and whether its API is pip-pinnable now
  vs. needs a thin shim — the `ScoutBackend` Protocol de-risks either path. (The
  only remaining genuinely-open item; the seed/output budgets and `mode=deep`
  semantics are now decided in **What**, not deferred.)
