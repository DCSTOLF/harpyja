---
id: "0017"
title: "gateway_http_timeout"
status: closed
created: 2026-07-01
authors: [claude]
packages: [harpyja/gateway, harpyja/config]
related-specs: ["0008", "0015", "0016"]
---

# Spec 0017 — gateway_http_timeout

## Why

Spec 0015 (OQ2) never completed a single full sweep. The recorded **B3** blocker
(`specs/0015-oq2/live-run-findings.md`) is an **infrastructure hang**: the Model
Gateway's outbound HTTP call has **no timeout**, so a stalled or torn-down Ollama
connection wedges the entire run indefinitely (observed: **2.5 h at 0% CPU with
`caffeinate` on** — the process alive, blocked forever on a socket read). This is
*why no full OQ2 run ever finished*.

Source-verified, one concrete fact:

- **No timeout on the outbound call (`harpyja/gateway/gateway.py:105`).**
  `_default_transport` does `with urlopen(req) as resp:` with **no `timeout=`**
  argument. `urllib`'s default is the global socket default (`None` → block
  forever). When the local endpoint accepts the connection but never returns
  bytes (Ollama mid-load, a half-open/torn-down socket, an OOM-killed backend),
  the blocking read never returns and never raises — so the caller waits forever.

This path is reached in a live `mode=auto` run through the **Verification Gate**
judge: `make_scout_model_judge` → `gateway.complete(...)` → `_default_transport`
(`orchestrator/gate.py:85`, `orchestrator/wiring.py:22`). The gate *already* wraps
the judge call in `try/except Exception` and degrades to `GateOutcome(failed=True)`
(`gate.py:137-150`) — but that safety net **never fires today**, because an
un-timed-out `urlopen` raises **nothing**; it just hangs. A finite timeout converts
the silent infinite wedge into a raised `TimeoutError`/`URLError` that the existing
catch turns into a graceful degrade. This is the **"always degrade gracefully"**
guardrail applied to the one place it currently cannot: a call that can hang
forever can never degrade.

This spec makes the gateway's outbound HTTP call **time-bounded** so a stalled
endpoint fails fast and degrades instead of wedging the run — a prerequisite for
re-attempting OQ2. It is a **reliability/plumbing** fix: no tier logic, no gate
algorithm, no classifier, no citation-format change.

Ref: 0015 (B3 / `live-run-findings.md`), 0008 (Model Gateway as the single
outbound abstraction / air-gap floor), 0016 (the sibling B1 serving fix; B2/B3
were carried as the remaining 0015 blockers).

## What

**INVARIANT (reliability, not capability).** No change to what any tier computes,
how the gate *judges*, the classifier, or the citation format. This spec bounds
the wall-clock of the **single outbound HTTP call** and lets an already-present
degrade path fire. It does not make any model faster or better — it makes a hung
model *fail fast and visibly* instead of blocking forever.

**Air-gap INVARIANT preserved.** A socket timeout is a client-side blocking-op
bound, not an endpoint change. `assert_local` still runs **before** any bytes
leave the process (`complete()` asserts first — `gateway.py:139`); the Model
Gateway stays the single localhost-only egress. Adding `timeout=` touches *how
long we wait*, never *where we connect*.

**Graceful-degrade INVARIANT (the point of the fix).** A timeout must surface as a
**typed graceful degrade, never a crash and never a silent pass**. On the gate
path this is already true by construction: a raised `TimeoutError`/`URLError`
propagates out of `judge()` into the existing `except Exception` and yields
`GateOutcome(failed=True)` (best-effort, escalation-eligible) — consistent with
specs 0006/0014's typed-degrade discipline. This spec's job is to make the call
*raise* on a stall; the existing catch does the rest.

**What `urlopen(timeout=)` actually bounds (no-false-capability).** The `urllib`
timeout is a **per-socket-operation** timeout (applied to connect and to each
blocking read), **not** a total-request deadline. That is exactly enough for the
observed pathology — a connection that accepts and then goes silent trips the read
timeout — and we claim only that. A pathological endpoint that *dribbles* bytes
slower than the timeout on every read could still outlast it; that is a known limit
of the stdlib transport and is **not** solved here (a total-deadline wrapper is a
possible follow-up, out of scope).

Scope:

- **Add a Settings field** `lm_http_timeout_s` for the gateway HTTP timeout — a
  finite `float` seconds value, default **`120.0`** (Decision D1). It participates
  in the layered precedence **defaults < `harpyja.toml` < `HARPYJA_*` env**,
  coerced like the other numeric settings. There is deliberately **no per-request
  layer** for this field (Decision D2): the timeout is fixed at gateway
  construction from resolved Settings, not per `complete()` call.
- **Thread the timeout into `_default_transport`** so `urlopen(req, timeout=...)`
  is always bounded. The value must be **finite** (never `None`) at every layer:
  the Settings default (AC1) AND the `ModelGateway.timeout_s` **dataclass field
  default itself** (AC2), so that *any* `ModelGateway(...)` construction — not just
  the two wired sites — is hang-bounded out of the box.
- **Preserve the injectable-transport seam (Decision D3).** The `Transport` type
  (`Callable[[url, payload], dict]`) that unit tests inject as a fake **must not
  change signature** — the timeout is carried by the `ModelGateway` (a
  `timeout_s` field) and bound onto the default transport **only** (e.g. via
  `functools.partial`, applied only when `transport is None`), so every existing
  injected fake in the suite keeps working untouched.
- **Make the timeout degrade distinguishable (Decision D4).** A timed-out judge
  call degrades through the gate's *existing* catch, but the timeout must be
  **observably separable** from other judge failures (a parse error, an unexpected
  throw) — honoring the standing typed-degrade *visibility* convention (spec 0014):
  the timeout path emits a distinct, timeout-naming log signal. This spec does
  **not** add a structured gate-degrade-cause schema (that larger taxonomy is a
  gate-quality concern, deferred); it only requires the timeout be named, not
  swallowed anonymously.
- **Wire the field through both production construction sites** — the gate/orch
  builder (`orchestrator/wiring.py:22`, the **observed B3 hang path**) and the
  scout builder (`scout/wiring.py:61`, **defense-in-depth**: that gateway is
  largely vestigial for Scout's Path A, which drives FastContext via a
  subprocess — but wiring it keeps every constructed gateway uniformly bounded) —
  so the live gateway carries the configured timeout, not a hardcoded one.

Explicitly **not** in scope (already bounded elsewhere or a separate concern):

- Scout's FastContext CLI path — **already** timeout-bounded via `cli_timeout_s`
  → `subprocess(..., timeout=)` (`scout/client.py:347`). Untouched.
- Deep's `dspy.RLM`/litellm connection — owns its **own** outbound socket
  (`deep/rlm.py`), not `_default_transport`. Whether `dspy.LM` needs its own
  timeout is a **separate** reliability question, out of scope here.

## Acceptance criteria

`[unit]` = fakes/no network; `[integration]` = operator-run /
`@pytest.mark.integration`, skip-not-fail.

1. **[unit]** `Settings.lm_http_timeout_s` defaults to the **finite positive**
   `float` `120.0` (Decision D1), **never `None`**. A test asserts the default and
   that it coerces from `harpyja.toml`/`HARPYJA_*` like the other numeric settings
   (precedence per D2 — defaults < toml < env, **no** per-request layer; base not
   mutated — frozen `replace`).
2. **[unit]** **Dataclass-default floor (closes the direct-construction gap).** The
   `ModelGateway.timeout_s` **dataclass field default** is itself a finite positive
   `float` (never `None`), so a bare `ModelGateway(api_base=...)` built **without**
   a timeout argument — as unwired/test constructions do — is still hang-bounded.
   A test asserts the field default independent of `Settings`.
3. **[unit]** **Timeout supplied to the blocking op (the actual B3 fix).**
   `_default_transport` passes the gateway's `timeout_s` to `urlopen` as a
   **non-`None`, positive `timeout=`** equal to the configured value — proven by
   monkeypatching `urlopen` and asserting the received keyword. Locks that the
   argument is really threaded to the blocking socket op, not dropped.
4. **[unit]** **Timeout propagates, is not swallowed.** A transport/`urlopen` that
   raises a timeout (`TimeoutError`/`socket.timeout`/`URLError`) propagates **out
   of** `ModelGateway.complete()` (it is not caught or converted inside the
   gateway), so a caller's degrade handler can see it. Distinct from AC3 (which
   proves the timeout is *supplied*); this proves *propagation* only, and the fake
   makes the test itself unable to hang.
5. **[unit]** **Graceful degrade on timeout (load-bearing behavior).** Given a
   gateway/judge that raises a timeout, `VerificationGate.verify(...)` returns
   `GateOutcome(passed=False, failed=True)` — **not** a raised exception and
   **not** `passed=True`. Locks that a stalled model degrades (escalation-eligible)
   instead of crashing or silently passing.
6. **[unit]** **Timeout degrade is distinguishable (Decision D4 / 0014 visibility
   convention).** On the timeout degrade path the gate emits a log signal that
   **names the timeout** (WARNING), so a "judge timed out" degrade is separable in
   operator diagnostics from a parse failure or an unexpected throw. A test asserts
   the timeout-naming log record is produced (e.g. via `caplog`) on the timeout
   path. (No schema change — this is observability, not a new structured field.)
7. **[unit]** **Deterministic stall proof (no external model).** A local loopback
   server that **accepts the connection then withholds all bytes**, driven through
   `ModelGateway.complete()` with a **tiny** configured `timeout_s`, makes the call
   **raise a timeout within a small bound** (e.g. well under a second) rather than
   hang. This proves the real socket-stall pathology is bounded — not merely that a
   fake can raise (AC3/AC4) — and is fully deterministic, loopback-only, and needs
   no Ollama.
8. **[unit]** The injectable-transport seam is preserved (Decision D3): a test that
   injects a custom two-arg `Transport` (the existing fake pattern) still works
   **unchanged** — the timeout `partial`-binding applies **only** when
   `transport is None`; an explicit `transport=` is used verbatim, its signature
   untouched.
9. **[unit]** The air-gap floor still runs **before** egress: `complete()` on a
   non-loopback `api_base` raises `AirGapError` and the (timeout-bearing) transport
   is **never** invoked. (Regression-guards that the timeout change didn't reorder
   the assert-local-first contract.)
10. **[unit]** Both production wiring sites (`orchestrator/wiring.py`,
    `scout/wiring.py`) construct the `ModelGateway` with the timeout drawn from
    `Settings` (not a literal): a seam/introspection test asserts the built
    gateway's `timeout_s` equals `settings.lm_http_timeout_s`, so a future Settings
    change flows through without a source edit.
11. **[integration]** Optional live smoke (happy-path only, skip-not-fail): against
    a reachable local Ollama, a `complete()`/gate `verify()` call returns well under
    the configured timeout and never hangs; env-gated, **skips** (never fails) when
    Ollama is absent. This documents the happy path — it is **not** the stall proof
    (AC7 is), and must not be read as validating the fix against a real stall.
12. **[doc]** Every consumer of the new field is made consistent in this change
    (blast-radius convention): the `settings.py` field comment + module-docstring
    toml example, the gateway `_default_transport` docstring (which currently claims
    "kept tiny and stdlib-only" with no mention of the bound), and any
    README/ARCHITECTURE note on the Model Gateway. Recorded in changelog/history as
    the B3 fix from spec 0015.

The load-bearing ACs are **3, 5, and 7**: AC3 makes the blocking call *finite* (the
actual B3 fix — no more infinite wedge); AC5 proves the now-raisable timeout
*degrades gracefully* rather than trading a hang for a crash; AC7 proves it against
a *real* socket stall, not just a fake. AC2 (dataclass-default floor) and AC1
(finite Settings default) together guarantee the bound is truly out-of-box, and AC6
keeps the degrade *visible*.

## Out of scope

- **B2 — gate-as-judge false-escalation** (`_parse_score` / the FastContext finder
  reused as a relevance judge rejecting correct citations). Separate gate-quality
  spec; B3 is orthogonal (B3 is *when the call hangs*, B2 is *how the reply is
  judged*).
- **Re-attempting the OQ2 measurement.** A fresh spec, after B1 (done, 0016) / B2 /
  B3 (this spec) all land.
- **A total-request deadline** (bounding the whole call, not each socket op) and
  any dribble-slowly defense — `urlopen(timeout=)` is per-op by design; a
  wrapping deadline is a possible follow-up, not this spec.
- **Deep's `dspy.RLM`/litellm timeout.** A separate outbound socket, dspy-managed;
  if it too can hang, that's its own reliability spec.
- **Retry/backoff on timeout.** This spec fails fast and degrades; it does not add
  retries (a degrade is escalation-eligible via the existing gate/orchestrator
  path).
- Flipping any other `Settings` default.

## Decisions (resolved in review)

- **D1 — field name, unit, and default: `lm_http_timeout_s: float = 120.0`,
  decoupled from `deep_wall_clock_ms`.** Seconds (`_s`, `float`) for consistency
  with the numeric settings it sits beside; a **finite** `120.0 s` default —
  generous enough for an Ollama cold-load first-byte, while never `None`. The value
  is **deliberately not aligned** with `deep_wall_clock_ms` (60 s): they bound
  different things (one per-socket-op HTTP wait vs. a total Deep budget), so making
  them equal would be a false equivalence. (Resolves OQ1/OQ2.)
- **D2 — precedence scope: no per-request layer for this field.** The timeout is
  fixed at gateway **construction** from resolved Settings (defaults < `harpyja.toml`
  < `HARPYJA_*` env). `complete(**params)` threads params into the JSON payload,
  not into `urlopen`, so there is intentionally no per-`complete()`-call timeout
  override — the earlier "per-request" precedence wording is dropped for this field
  to avoid implying an API the design does not want.
- **D3 — the seam: timeout on `ModelGateway.timeout_s`, bound onto the default
  transport only.** The timeout rides on a new `ModelGateway.timeout_s` field and
  is bound onto `_default_transport` (e.g. `functools.partial(_default_transport,
  timeout_s=self.timeout_s)`) **only when `transport is None`**. The `Transport`
  callable signature (`(url, payload) -> dict`) is unchanged, so every injected
  fake still works. The **dataclass field default is itself finite** (AC2), closing
  the gap that a direct `ModelGateway(...)` (scout wiring, tests) would otherwise
  fall back to an unbounded `None`. (Resolves OQ3.)
- **D4 — timeout degrade must be distinguishable, not anonymous.** The 0014
  standing convention (typed degrades get first-class *visibility*) applies: the
  timeout still degrades via the gate's existing generic catch, but the timeout
  path emits a **timeout-naming log signal** (AC6) so operators can separate "judge
  timed out" from other judge failures. A full structured gate-degrade-cause
  taxonomy (a schema field per cause) is a larger gate-quality concern and is
  **out of scope** here — this spec only requires the timeout be named, not
  swallowed anonymously.

## Open questions

_none — OQ1/OQ2/OQ3 resolved above as Decisions D1–D4 during review._
