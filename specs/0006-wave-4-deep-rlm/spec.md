---
id: "0006"
title: "Wave 4 — Deep (RLM)"
status: closed
created: 2026-06-27
authors: [claude]
packages: [harpyja/deep, harpyja/orchestrator]
related-specs: ["0005"]
---

# Spec 0006 — Wave 4 — Deep (RLM)

## Why

Tier 0 answers symbol/literal point-lookups; Tier 1 (Scout, Wave 3) answers
single-shot conceptual queries by letting a model explore. But the hardest
retrieval — "trace how a request flows from the HTTP handler to the DB write",
"find every place the retry budget is consulted across packages" — needs
*iteration*: search, read, partition, spawn sub-queries, and pull only the spans
that matter into token space, repeatedly. A single Scout pass can't do that
without blowing the context window.

Wave 4 introduces **Tier 2 — Deep**, a Recursive Language Model (`dspy.RLM`)
that runs inside a sandboxed REPL with a small set of **bounded, read-only host
tools** as its entire world. It is the strongest (and most expensive) tier, used
only when explicitly asked (`mode=deep`). This wave also makes the Wave-3
provisional `mode=deep` real: where Wave 3 routed `deep` to Scout with a "Deep
pending" note, Wave 4 routes it to an actual Tier 2 — closing the
no-false-capability gap by shipping routing **and** implementation together.

Because the RLM writes and runs code against the host tools, it is an
**untrusted caller** of them: the repo-path confinement and bounds that Wave 3
hardened at the FastContext boundary now apply one layer deeper, at every host
tool inside the sandbox.

## What

Scoped to a **shippable Deep tier**: `mode=deep` runs Tier 2; the Verification
Gate and the Tier-0→1→2 **auto-escalation** ladder are explicitly **not** in this
wave (Wave 5). `mode=auto` stays byte-identical and model-free; `mode=fast`
stays Scout.

### Deep tier (`harpyja/deep/`)

- A `DeepBackend` Protocol (`run(query, seed, tools) -> list[CodeSpan]`) with
  **`dspy.RLM` as the first concrete impl**, reached only through an **injected**
  runner — no top-level hard import, so the package/sandbox being absent can
  never break the suite (mirrors the Wave-3 `ScoutBackend` seam). A fake backend
  drives all unit tests.
- The RLM impl constructs a **fresh instance per request** (`dspy.RLM` is not
  thread-safe with a custom interpreter) and drives the explorer model strictly
  through the **Model Gateway** (`gateway.complete`). The air-gap reuses the
  **single helper** `gateway.assert_local` / `AirGapError` — **no** parallel
  Deep-specific check — with resolved-address validation **before** any RLM/model
  I/O. The Deno/Pyodide sandbox runs offline.
- A `DeepEngine` exposes the shared `Locator` `.search` seam (like `ScoutEngine`)
  and wraps the `DeepBackend`, so the orchestrator/formatter **never branch on
  `DeepBackend`** — Deep is an implementation detail *inside* a `Locator`,
  returning the common `CodeSpan` shape.
- Deep is **not cached** (model-backed/non-deterministic; no engine-identity
  slot), like Scout.

### Bounded read-only host tools (the RLM's entire world)

All four ship, each a thin wrapper over **existing** Tier-0 machinery, bounded by
the **existing** `Settings` caps, and each enforcing repo-path confinement
because the RLM is an untrusted caller:

- `list_manifest(filter)` → the ranked manifest reader (bounded by `manifest_page`).
- `search(pattern, scope)` → `RipgrepEngine` (bounded by `search_max_files` /
  `search_max_matches`; `scope` confined to the repo root).
- `symbols(path)` → the Tier-0 symbol index for a file (`path` confined to the repo).
- `read_span(path, start, end)` → the bounded snippet reader `read_snippet`
  (bounded by `tool_max_lines` / `tool_max_chars`; `path` confined).

The tool set exposes **no** mutating operation — read-only by construction. A
path resolving outside the repo root is rejected; an over-budget request is
clamped, not honored.

### Sandbox isolation — the RLM is untrusted *code*, not just an untrusted caller

The four host tools harden the RLM as a caller; the deeper threat is RLM-authored
code reaching **around** them — a bare `open('/etc/passwd')` or `import socket`
inside the Pyodide REPL. The sandbox's WASM filesystem is virtualized and
empty-by-default and the network is denied, which is *why* this is safe — but per
the project's honesty rule that is an **assumption verified by test with residual
risk recorded**, not a property we assert. Wave 4 therefore:

- exposes to sandboxed code **only** the four whitelisted host tools — no ambient
  host filesystem and no network are reachable from RLM-authored code; verified
  by a direct test (an in-sandbox `open()` outside the repo root and a raw socket
  attempt both fail), and
- **records the residual risk** (a future Pyodide/runtime change could widen the
  surface) and the verification method, exactly as the FastContext in-process
  egress risk was recorded in Wave 3.

### Concrete budgets

Per-call tool clamps are not enough: the RLM is a code-writing loop that can
recurse and fan out. Both the tools **and the explorer loop itself** are bounded,
via additive frozen `Settings` (appended last, with defaults):

- `deep_seed_top_n` — Tier-0 seed spans handed to the backend as hints. Default **5**.
- `deep_max_citations` — Deep result ceiling (clamped to `min(deep_max_citations, max_results)`). Default **20**.
- `deep_max_span_lines` — max line-range per returned citation span. Default **200**.
- `deep_max_depth` — max RLM recursion depth (sub-query nesting). Default **3**.
  *(Host-mediated or residual-risk — see Enforcement; not a hard bound in isolation.)*
- `deep_max_subqueries` — max total sub-queries spawned per request. Default **8**.
  *(Host-mediated or residual-risk — see Enforcement; not a hard bound in isolation.)*
- `deep_max_tool_calls` — max total host-tool invocations per request. Default **200**.
- `deep_token_ceiling` — max explorer-loop token spend per request. Default **32000**.
- `deep_wall_clock_ms` — max in-sandbox execution time per request. Default **60000**.

**Enforcement — layered so no single ignorable counter is load-bearing.** The
four bounds sit at different seams against an untrusted/buggy/adversarial backend:

- **Externally enforced (host-side counters, backend cannot evade):**
  `deep_max_tool_calls` via the host-tool wrappers, `deep_token_ceiling` via the
  Model Gateway, and `deep_wall_clock_ms` via a host-side execution deadline on
  the sandbox. `deep_wall_clock_ms` is the **adversarial backstop**: a tight loop
  (`while True: pass`) that touches neither a tool nor a token counter is still
  killed by the wall clock. **This requires the backend/sandbox to run in an
  out-of-band, host-terminable context** (a subprocess or sandbox worker the host
  can hard-kill) — a same-thread/same-event-loop deadline timer can never fire
  while a synchronous WASM busy loop blocks it. Enforcement is by hard
  termination, never cooperative cancellation.
- **Host-mediated where possible:** `deep_max_depth` and `deep_max_subqueries`
  only exist as real bounds if the **host drives the explorer loop / mediates
  each sub-query spawn** (so the host observes and caps nesting). The spec
  requires that mediation seam. **Residual risk (recorded, not asserted):** if
  `dspy.RLM` will not expose a spawn/recurse hook, depth/sub-query caps become
  best-effort/cooperative — that gap is documented (with the observed runtime
  capability) as residual risk rather than presented as a hard bound, and the
  externally-enforced `deep_max_tool_calls` / `deep_token_ceiling` /
  `deep_wall_clock_ms` remain the **load-bearing** guarantees. Crucially, a
  recursion/sub-query storm is **transitively contained** by those external
  ceilings — every sub-query spends tool-calls, tokens, and wall-clock — so a
  runaway terminates *even if* the mediation seam turns out cooperative; the
  host-mediated caps are a precision improvement, not the only thing between us
  and an unbounded loop.

Hitting any explorer-loop bound **terminates** the run with whatever citations
were gathered (a bounded, honest Tier-2 result). This is **not** a
`DeepUnavailable` degrade — but it is **not** silent either: the result carries a
stable, caller-visible non-degrade note `deep-truncated:<bound>` (one of
`depth` / `subqueries` / `tool-calls` / `tokens` / `wall-clock`), so a truncated
exploration is never indistinguishable from a complete one (no false-capability
claim). `deep-truncated:depth` / `:subqueries` fire only when the mediation seam
is live; when the residual risk is realized (no spawn/recurse hook), the *firing
external bound's* note (`tool-calls` / `tokens` / `wall-clock`) is the honest
truncation signal — so the caller-visible note is **never silently absent**.

### Routing & self-seeding

- `mode=deep` → run its **own** lightweight Tier-0 seed (the symbol+ripgrep
  composition, top-`deep_seed_top_n`) as part of the Deep path, hand the seed to
  the backend, then run Tier 2. It **skips Scout** (per the documented lifecycle:
  deep goes straight to Tier 2 after the Tier-0 seed). A successful run has
  `tiers_run = [0, 2]` and citations carry `source_tier = 2`.
- **Seed handoff (resolved).** The seed is passed as starting **citation hints**
  (a `list[CodeSpan]` — file:line spans the RLM may expand via the `read_span`
  tool), **not** as pre-loaded source content in the prompt. Pre-loading source
  would defeat the entire RLM premise (pull only what you need into token space)
  and would bypass the confined host-tool surface; the hints reference the same
  bounded `read_span`/`symbols` tools the RLM already calls.
- `mode=auto` → Tier 0, **byte-identical** to Wave 2/3 (no model/Gateway/Deep call).
- `mode=fast` → Scout (Tier 1), **unchanged** from Wave 3.
- **No-silent-coverage lockstep (ship the guard inversion, not prose).** The
  Wave-3 provisional `Deep pending` note + its lockstep test asserting **no
  Tier-2 marker** for `deep` actively assert the opposite of what 0006 ships, so
  that test goes red the instant Deep lands. This wave **replaces/inverts that
  guard in the same change** — the new invariant asserts `deep` *does* emit the
  Tier-2 marker (`2 ∈ tiers_run`, `source_tier = 2`) and only when a `DeepBackend`
  is actually wired — so routing + implementation + the lockstep test move
  together (AC2a below).

### Degradation — typed-failure-only (NOT a quality judgment)

- Deep degrades **only** on a typed `DeepUnavailable` (stable cause:
  `sandbox-absent` / `rlm-down` / `backend-error`) → fall back to **Scout
  best-effort** (Tier 1) with a stable `deep-degraded:<cause>` note. The fallback
  reuses the Wave-3 chain unchanged: a Scout success yields `tiers_run = [0, 1]`;
  if the model is also down, Scout itself degrades to Tier 0 (`tiers_run = [0]`)
  carrying both the `deep-degraded:<cause>` and the Wave-3 `scout-degraded:<cause>`
  markers.
- `DeepUnavailable` is raised **only** for typed *infrastructure* failure
  (sandbox-absent / rlm-down / backend-error) — **never** for a quality heuristic
  (low citation count, low confidence, empty normalized output, or a
  timeout-as-weakness). A **successful** Deep run that returns few or zero
  citations is **not** degradation: it returns an honest Tier-2 result
  (`tiers_run = [0, 2]`, no fallback). Treating weak output as a reason to drop a
  tier would be an **ungated escalation** — exactly what the deferred Verification
  Gate is meant to govern, and must not be smuggled in here.
- Floor (propagate loudly, never a `deep-degraded` note): `RipgrepMissingError`
  from the Tier-0 seed (seed runs **before** the backend, so it wins by
  construction) and `AirGapError` from a non-loopback endpoint.

## Acceptance criteria

Each AC is `[unit]` (fake backend / injected runner, no model/sandbox) or
`[integration]` (`@pytest.mark.integration`, real RLM/sandbox/endpoint).

1. `[unit]` `harpyja_locate(query, repo, mode="deep")` with an injected fake
   `DeepBackend` runs Tier 2: `tiers_run == [0, 2]` and citations carry
   `source_tier == 2`. Deep is reached behind a `DeepEngine` exposing the shared
   `Locator` `.search` seam — the orchestrator/formatter do **not** branch on
   `DeepBackend`.
2. `[unit]` `mode=auto` is **byte-identical** to the Wave-2/3 Tier-0 result
   (citations + confidence + tiers_run + notes) and makes **zero**
   Gateway/Deep calls; `mode=fast` still routes to Scout. Regression-locked.
2a. `[unit]` **Lockstep guard inversion (ships with routing+impl).** The Wave-3
    test asserting `deep` emits **no** Tier-2 marker is replaced/inverted in this
    same change: the new invariant asserts `deep` *does* emit the Tier-2 marker
    (`2 ∈ tiers_run`, `source_tier = 2`) **only when** a `DeepBackend` is wired,
    and the old assertion is gone (the suite cannot hold both).
3. `[unit]` `mode=deep` runs a Tier-0 seed **as part of the Deep path** and
   passes its top-`deep_seed_top_n` spans to the `DeepBackend` as starting
   citation hints (asserted via a fake backend recording hints); a
   `RipgrepMissingError` from the seed propagates and the backend is **never**
   called.
4. `[unit]` Deep sits behind a `DeepBackend` Protocol; `dspy.RLM` is one impl;
   a fake backend is injected without a live model/sandbox (same DI seam as
   `engine` / `symbol_engine` / `scout_engine`).
5. `[unit]` **Typed-failure-only degradation, with pinned `tiers_run`**:
   `DeepUnavailable(<cause>)` → Scout best-effort + stable `deep-degraded:<cause>`
   note (the three causes yield distinct notes), `tiers_run == [0, 1]` on Scout
   success; if the model is also down, double-degrade → `tiers_run == [0]` with
   both `deep-degraded:<cause>` and `scout-degraded:<cause>`. A successful Deep
   run returning **zero/weak** citations returns an honest Tier-2 result
   (`tiers_run == [0, 2]`) and does **not** fall back.
5a. `[unit]` `DeepUnavailable` is raised **only** for typed infrastructure
    failure (sandbox-absent / rlm-down / backend-error) — asserted that low
    citation count, low/empty normalized output, and a quality/timeout heuristic
    do **not** raise it (no ungated escalation).
6. `[unit]` Floor propagation: a non-loopback endpoint raises `AirGapError`
   (via the single `gateway.assert_local` helper, resolved-address check before
   any I/O) and a seed `RipgrepMissingError` propagates — neither becomes a
   `deep-degraded` note.
7. `[unit]` Each host tool (`list_manifest` / `search` / `symbols` /
   `read_span`) enforces **repo-path confinement** and the existing `Settings`
   clamps when invoked by the RLM: a path resolving outside the repo root is
   rejected, and over-budget requests are clamped (max lines/chars/matches/files)
   — reusing the Wave-1/Wave-3 machinery.
8. `[unit]` The host-tool set is **read-only**: it exposes no operation that can
   write, edit, or delete in the target repo (asserted on the tool surface).
8a. `[unit]` **Sandbox whitelist (positive equality, deno-less backstop).** The
    in-sandbox namespace exposed to RLM-authored code equals **exactly**
    `{list_manifest, search, symbols, read_span}` — asserted as a positive
    equality on the exposed host-binding surface, so the "only four tools" claim
    is verified even in CI without `deno` (not only in the skip-able integration
    probe 8b).
8b. `[integration]` **Sandbox isolation** (assumption verified by test): code
    executed inside the real sandbox can reach **only** those four tools — an
    in-sandbox `open()` of a path **outside** the repo root, an `open()` of a
    path **inside** the repo root (which would bypass `read_span`'s
    `tool_max_lines`/`tool_max_chars` clamps — a fifth unbounded capability), and
    a raw socket / `import socket` attempt **all fail** (no ambient host FS, no
    network; all reads forced through `read_span`). The residual runtime-change
    risk + the verification method are recorded (no false-capability claim).
9. `[unit]` `DeepBackend` output is normalized to valid `CodeSpan` with
   `source_tier = 2` and the same hostile-output clamping as Scout (path outside
   repo, nonexistent file, inverted/out-of-range range, duplicates, over-budget).
10. `[unit]` **Explorer-loop bounds enforce at the harness seam (not
    self-reported).** A **non-cooperative** backend that tries to exceed the
    externally-enforced bounds is stopped by the host: `deep_max_tool_calls` (the
    tool wrappers stop dispatching), `deep_token_ceiling` (the Gateway refuses
    further completions), and `deep_wall_clock_ms` (a host deadline kills a
    backend that ignores every counter, e.g. a busy loop). Each terminates with
    the citations gathered so far, emits the matching `deep-truncated:<bound>`
    note, and does **not** raise `DeepUnavailable`. For `deep_max_depth` /
    `deep_max_subqueries`, assert the host-mediated spawn seam caps nesting (or,
    if the runtime can't expose the hook, that the documented residual-risk
    fallback holds and the externally-enforced bounds still terminate the run).
    The wall-clock case must exercise a genuinely **non-yielding** backend (a true
    busy loop, not a cooperative `sleep`) running in the **host-terminable
    out-of-band context** — enforcement is by hard termination, so neither AC10
    nor AC10a may rely on the backend cooperating, and the test harness itself
    must not hang.
10a. `[integration]` **Real runaway terminates.** A real RLM/sandbox driven to
     recurse / spin without bound is actually halted by the host (wall-clock /
     tool-call / token deadline) and returns a `deep-truncated:<bound>` result —
     proving enforcement against a genuine non-cooperative loop, not just the
     fake plumbing. Skip-not-fail when `dspy`/`deno` are absent.
11. `[integration]` `mode=deep` runs end-to-end against a live RLM + sandbox +
    endpoint; skip-not-fail when `dspy`/`deno`/endpoint are absent.
12. `[integration]` Deep runs to completion under a **network-deny** environment
    with a loopback-only Gateway — the RLM/model path needs no non-loopback
    egress and the sandbox runs offline.
13. `[unit]` `harpyja_index`, `harpyja_read`, `mode=auto`, and `mode=fast` make
    **zero** Deep calls — the offline/Tier-floor posture holds for every
    non-deep path.

## Out of scope

- The **Verification Gate** (read-back scoring, LLM-judge / embedding) and the
  Tier-0 → 1 → 2 **auto-escalation** ladder — Wave 5. (`mode=deep` is the
  explicit Tier-2 trigger this wave; `auto` does not climb.)
- Embedding / judge **sub-model** wiring.
- Provisioning the `dspy` package or the Deno/Pyodide sandbox runtime
  (install/pin/quantize) — Wave 4 assumes they are present (`doctor` already
  reports `deno`).
- **Wave-2.1** substring/fuzzy symbol matching (separate follow-up).
- Process/WASM sandboxing of **FastContext** (a Wave-3 follow-up) — Deep's
  sandbox is for the RLM, not retro-fitted onto Scout here.

## Open questions

- Exact `dspy` package + version pinnability and the Deno/Pyodide sandbox
  **provisioning** approach (install-once-offline) — the only genuinely-open
  item; de-risked by the `DeepBackend` Protocol + injected runner, but the
  concrete runtime wiring is unsettled. (Recursion/sub-query/token budgets and
  the seed handoff are now decided in **What**, not deferred.)
