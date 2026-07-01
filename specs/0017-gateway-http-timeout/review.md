# Review — Spec 0017 "gateway_http_timeout"

Reviewers: `codex` (codex-cli, `codex exec --full-auto`), `claude-p` (local `claude -p`)
Synthesis: cross-reviewer + orchestrator source-verification

## Round 1 (2026-07-01)

| Reviewer | Verdict |
|----------|---------|
| claude-p | **approve-with-comments** |
| codex | **changes-requested** → folded (see below) |

**Quorum (≥1 approve / approve-with-comments): MET** (claude-p). Status → `reviewed`.

Both reviewers confirmed the core B3 fix is correct and **every concrete source claim
in the spec was verified true** against the tree: `gateway.py:105`
(`with urlopen(req) as resp:` — no `timeout=`, `# noqa: S310`); `complete()` calls
`assert_local()` **before** `send(...)` (the air-gap-first ordering AC9 guards);
the gate's `try/except Exception → GateOutcome(passed=False, failed=True)` with
`assert_local()` **outside** the try and the `judge → complete → transport` call
**inside** it (so a raised `TimeoutError` lands in the catch exactly as claimed —
AC5 is load-bearing *and* achievable); both wiring sites; `deep_wall_clock_ms = 60000`;
and Scout's already-bounded `cli_timeout_s → subprocess(timeout=)` (`client.py:347`).
No guardrail violations — a socket timeout bounds *how long we wait*, never *where we
connect*, so the air-gap is untouched. The reviewers converged on six load-bearing
precision/coverage items; **all six were folded into the spec before marking
reviewed**, which resolves codex's `changes-requested`.

### Folded — the six convergent load-bearing items

1. **Load-bearing default was unresolved (codex #1 + suggestion; claude-p OQ1).** A
   reviewed spec must not leave an AC-load-bearing default at "candidate: 120 s."
   **Fold:** OQ1/OQ2 promoted to **Decision D1** — `lm_http_timeout_s: float = 120.0`,
   seconds, and **explicitly decoupled** from `deep_wall_clock_ms` (claude-p: they
   bound different things — one per-socket-op wait vs. a total Deep budget — so
   equating them is a false equivalence).

2. **Dataclass-default gap (claude-p's strongest #1).** Every AC pinned the finite
   default on *Settings*, but the mechanism (D3) puts the actual timeout on
   `ModelGateway.timeout_s`; direct constructions (`scout/wiring.py:61`, much of the
   test suite) pass no timeout and fall back to the field's own default. If that is
   `None`, the "out-of-box gateway can never hang" invariant is **false**. **Fold:**
   new **AC2** pins the `ModelGateway.timeout_s` *dataclass* default to a finite
   positive float, independent of Settings; D3 states the field default must be
   finite.

3. **Typed-degrade visibility (codex #2 + convention_violation, citing 0014).** The
   generic `except Exception → failed=True` does not let later analysis tell "judge
   timed out" from "parser failed." The repo's standing convention (visibility
   promoted in 0014) applies. **Fold:** **Decision D4** + new **AC6** — the timeout
   path emits a timeout-**naming** log signal so the degrade is distinguishable;
   a full structured gate-degrade-cause schema is explicitly out of scope (a
   gate-quality concern), so the fix stays proportionate.

4. **Per-request precedence tension (codex #3 + claude-p #2).** **What** claimed
   `... < per-request` precedence, but the construction-time-field design has no
   per-request path (`complete(**params)` threads into the JSON payload, not
   `urlopen`). **Fold:** **Decision D2** — precedence is defaults < toml < env only;
   the "per-request" wording is dropped for this field to avoid implying an API the
   design does not want.

5. **AC3 overstated / split (codex #4 + suggestion 4; claude-p AC5 mechanism note).**
   A fake that merely raises proves propagation, not that the timeout was *supplied*.
   **Fold:** split into **AC3** (monkeypatched `urlopen` asserts a non-`None` positive
   `timeout=` is threaded — the *supplied* proof) and **AC4** (a raised timeout
   *propagates* out of `complete()`, is not swallowed). AC8 now names the
   partial-binds-only-when-`transport is None` invariant.

6. **AC8 was happy-path-only (codex #5 + suggestion 5; claude-p #3).** A healthy
   Ollama returns far under the timeout and never exercises the silent-read stall, so
   live smoke validated nothing about the fix. **Fold:** new **AC7** — a deterministic
   **local loopback server that accepts then withholds all bytes**, with a tiny
   configured timeout, proves `complete()` **raises within a small bound** (no Ollama,
   fully deterministic). The old live smoke is retained as **AC11**, explicitly
   relabeled happy-path-only / not-the-stall-proof.

### Also folded (claude-p suggestions)

- **Scout-site wiring is defense-in-depth, not the hang site.** The observed B3 hang
  is the *gate* gateway (`orchestrator/wiring.py`); the scout gateway is largely
  vestigial for Path A. **Fold:** the wiring scope bullet now says so in one sentence,
  so a reader doesn't assume the scout gateway's `complete()` is on the live path.

## Plan-level items (carry to `/speccraft:spec:plan`, not spec blockers)

- Implement D3's `functools.partial(_default_transport, timeout_s=...)` binding, gated
  on `transport is None`; keep the two-arg `Transport` signature (AC8).
- AC7's silent-server harness: bind a `127.0.0.1` listener that `accept()`s and never
  writes, drive `complete()` with `timeout_s≈0.25`, assert it raises well under ~1 s
  and the test itself is bounded.
- AC6: assert the timeout-naming log via `caplog`; decide the exact log message/level
  (WARNING) so it's greppable and distinct from the parse-failure path.
- Confirm the `120.0 s` default reads right against the eval host's Ollama cold-load
  first-byte latency at implementation time.

## Action recommendation

**Reviewed — proceed to `/speccraft:spec:plan`.** The core B3 fix (finite
`urlopen(timeout=)` + let the *existing* gate catch fire) is unambiguously correct and
source-verified; the six convergent review items — most importantly the dataclass-default
floor (AC2), the timeout-visibility decision (D4/AC6), and the deterministic stall proof
(AC7) — are folded, so the spec is now precise and review-hookable.
