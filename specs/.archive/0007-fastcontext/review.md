---
spec: "0007"
title: "FastContext"
revision: 2
reviewers: [codex, claude-p]
verdicts: {codex: changes-requested, claude-p: approve-with-comments}
quorum: 1
quorum_outcome: MET
status: reviewed
generated: 2026-06-27T00:00:00Z
---

# Cross-model review — 0007 "FastContext" (revision 2)

## codex

**Verdict:** changes-requested

Concerns:

- Async seam contradiction: the spec says `await agent.run(...)` inside the tool handler but also says the `ScoutBackend.run(...)` stays synchronous and bridges with `asyncio.run(...)`. If the handler is already on a running FastMCP/event-loop path, `asyncio.run(...)` will raise — this is not safe as written without a stated precondition pinning the calling context to a loop-free thread.
- `fastcontext-missing` vs `cli-missing` terminal-cause boundary: Path B is attempted whenever the package is unimportable, so `fastcontext-missing` is only a transition state in the fallback chain, never a terminal `ScoutUnavailable` cause under that logic. The spec needs a deterministic state machine that says exactly when `fastcontext-missing` surfaces as the final emitted cause versus when it is an internal transition.
- Read-only test surface underspecified: "byte-unchanged" needs a concrete exclusion list or snapshot method that covers `.harpyja/`, mtime-only changes, ignored files, and temp files under the repo root — otherwise the AC's assertion surface is ambiguous.
- Single-flight lock scope and env restoration unspecified: the spec does not say whether the lock is process-global, module-global, or per-backend; and `FC_*` values are set but never stated to be restored in `finally` (preserving unset-vs-empty) when construction or `agent.run()` fails.

Suggestions:

- Choose one explicit bridge design: async FastContext client bridged at a known sync boundary, or a dedicated worker thread where `asyncio.run(...)` is legal and the handler never calls it from inside a loop.
- Add a sentence defining the fallback priority state machine: package import fails → try CLI if present → emit `cli-missing` if no CLI; `fastcontext-missing` is only emitted when the CLI path is intentionally disabled or the injected runner is wired to None.
- Define the no-repo-writes test as a hash/manifest snapshot over the repo tree excluding `.harpyja/` and ignored files, or name those artifacts as sanctioned and explain why they do not violate the read-only guardrail.
- Add an AC requiring env restoration after exceptions and nested calls, including the unset-vs-empty distinction for every managed `FC_*` key; name the lock scope.

Guardrail violations:

- **Read-only locator** (precision request, not a design breach): AC8's "byte-unchanged" assertion surface is not precise enough to exclude normal sanctioned derived-artifact churn. Location: AC8 / Read-only section.

Convention violations:

- **Async / sync test bridging**: production `asyncio.run(...)` inside an existing event loop path contradicts the "loop-free calling context" requirement implicit in the convention. Location: "What / Backend client — two paths / Path A."
- **Distinct cause identifiers / non-overlapping**: `fastcontext-missing` and `cli-missing` overlap unless the fallback state machine makes the terminal/transition distinction explicit. Location: "Degradation — four distinct causes" section.

---

## claude-p

**Verdict:** approve-with-comments

Concerns:

- Lock primitive unnamed: Path A mutates process-global `os.environ` while bridging the awaitable via `asyncio.run(...)`. Concurrent Scout calls arrive on different threads (each `asyncio.run` spins its own loop), so the lock MUST be a `threading.Lock`, not an `asyncio.Lock` — an asyncio-scoped lock would not serialize cross-thread writes to `os.environ` and the AC3/AC4 guarantee would silently fail to hold.
- `asyncio.run()` inside the sync `ScoutBackend.run` is unsafe if the tool handler already runs inside a running event loop. The spec asserts the bridge works but does not state the precondition: the handler must be dispatched on a loop-free thread. The prior round explicitly flagged this; the revision asserts the mechanism without pinning down the calling context.
- `fastcontext-missing` vs `cli-missing` terminal-cause boundary: if Path B is attempted whenever the package is unimportable, `fastcontext-missing` is never a terminal `ScoutUnavailable` cause — `cli-missing` (both unavailable) is the terminal state. The spec lists `fastcontext-missing` as a degrade cause but the fallback chain implies it is only a transition. When exactly is `fastcontext-missing` the final emitted cause (e.g., when the injected runner is wired to None)? One sentence to fix, but required.
- `os.environ` cleanup after the locked run not specified: `FC_*` are set under the lock spanning `agent.run()` but the spec never states they are restored (try/finally) or that staleness is intentionally tolerated. Specify set-then-restore or explicitly record the residual leak.
- Local-path absolute install (`uv add /Users/daniel.stolf/Development/fastcontext`) pins to a machine-specific path not reproducible on any other host or in CI. The spec treats "no PyPI" as the only portability axis but the install source itself is non-portable. Vendor as a submodule or record non-portability as an explicit deviation.

Suggestions:

- Enumerate the full `FC_*` mapping, not just `FC_MODEL←scout_model`. The factory reads `FC_BASE_URL` / `FC_API_KEY` / `FC_MAX_TOKENS` / `FC_TEMPERATURE` / `FC_REASONING_EFFORT`; `FC_BASE_URL←lm_api_base` appears only in AC3 prose, not the "Model selection" section; `FC_API_KEY` (dummy for Ollama?), `FC_MAX_TOKENS`, and `FC_TEMPERATURE` are unmapped. A small mapping table removes ambiguity.
- Commit `FASTCONTEXT_INSTALL.md` in this wave — the spec references it as its primary reference but the file is untracked; a draft whose primary reference is untracked is fragile.
- Make AC3's "lock held across the full `agent.run()`" concretely assertable: have the fake factory/agent record whether the lock is held at construction AND at each model-call boundary (`FC_REASONING_EFFORT` lazy-read), so the test actually proves the span rather than only construction-time holding.
- Clarify where the factory's `RuntimeError` on missing `FC_MODEL` maps in the cause taxonomy. `scout_model`'s default makes it unreachable in practice, but the taxonomy should state the mapping (presumably `backend-error`) so the wrap-preserving-cause path is unambiguous.

Guardrail violations: none.

Convention violations: none.

---

## Synthesis

### Quorum and overall verdict

Quorum is met. `claude-p` returned `approve-with-comments`; `codex` returned `changes-requested` and is the minority. The spec advances to status `reviewed`. The concerns below are **conditions to resolve during `/speccraft:spec:plan`**, not grounds for a third review round. The tdd-planner must fold them into plan.md before implementation begins.

### What revision 2 fixed (round-1 blockers resolved)

The revision did exactly what the round-1 synthesis required:

1. **Config-injection contradiction resolved via source verification.** The spec now cites a verified SHA (`1522d6d6b5e040e817b468e12826662aa069a8b0`) and records the actual `make_fastcontext_agent` signature: env-only, no `model`/`base_url` params, no config-file seam. The design lands on env-under-single-flight-lock spanning the full `agent.run()` (because `FC_REASONING_EFFORT` is lazy-read per call at `llm.py:77`). The "guarded context" ambiguity is gone; the lock rationale is grounded in code.

2. **Read-only guardrail addressed with a recorded residual risk.** AC8 adds a no-repo-writes integration test proving byte-unchanged `work_dir` and explicitly records the residual in-process write risk, symmetric to AC9's network-deny treatment. Both agents accept this as the correct pattern.

3. **Four-way cause taxonomy enumerated.** The degradation section now names four distinct stable identifiers: `fastcontext-missing`, `cli-missing`, `connection-refused`, `backend-error`. AC10 names all four and prohibits collapse. The convention violation is remedied.

The smaller round-1 items are also addressed: Path B air-gap extended to "before the subprocess runner is invoked" (AC2); `scout_model` acknowledged as a new additive field with standard precedence; async seam bridging stated (`asyncio.run` inside the sync adapter); `FASTCONTEXT_INSTALL.md` referenced as a near-term commit target; SHA and `FC_*` mapping now in the spec body.

### Carry-forward concerns for planning (ranked by load-bearingness)

#### Tier 1 — Both agents raised independently (strongest signal, must be in plan.md)

**(a) Async seam and lock primitive.**
Both agents flag the same structural risk: `asyncio.run(...)` inside `ScoutBackend.run` raises `RuntimeError: asyncio.run() cannot be called from a running event loop` if the calling handler is already inside a loop. The spec asserts the bridge works but does not state the required precondition (handler dispatched on a loop-free thread). Additionally, because concurrent Scout calls arrive on different OS threads (each `asyncio.run` spins its own event loop), the lock MUST be `threading.Lock`, not `asyncio.Lock` — the asyncio primitive is loop-scoped and will silently fail to serialize cross-thread `os.environ` writes, voiding the AC3/AC4 guarantee. The plan must name the primitive, state the calling-context precondition, and add a test that proves the lock actually serializes concurrent threads, not merely concurrent coroutines.

**(b) `fastcontext-missing` terminal-vs-transition boundary.**
Both agents note that if Path B (CLI) is attempted whenever the package is unimportable, `fastcontext-missing` is never a terminal `ScoutUnavailable` cause — `cli-missing` (both paths unavailable) is always the terminal state. The spec's four-cause taxonomy is correct in intent, but the fallback priority state machine must be stated explicitly so `fastcontext-missing` is deterministically reachable (e.g., when the injected runner is wired to `None`, or when CLI fallback is intentionally disabled). Without this, AC10's test for `fastcontext-missing` cannot be written unambiguously.

**(c) `os.environ` restoration and lock scope naming.**
Both agents flag that the spec sets `FC_*` under the lock but never says they are restored in a `try/finally` block (preserving the unset-vs-empty distinction). For Scout-internal reads staleness is harmless (every call re-sets all `FC_*`), but leaked values persist for any other `os.environ` reader in the process. The plan must specify set-then-restore or explicitly record the residual leak. The lock scope must also be named: process-global, module-global, or per-backend — each has different concurrency implications.

#### Tier 2 — Single agent only

**(d) Read-only test surface precision (codex only).**
AC8's "byte-unchanged" criterion needs a concrete exclusion list: `.harpyja/` (sanctioned derived artifacts), mtime-only changes, files matching the repo's `.gitignore`, and temp files under the repo root. Without this, the assertion surface is ambiguous and the test may pass or fail for unrelated reasons. The plan should choose one of: hash-based snapshot excluding `.harpyja/`, or a manifest of non-ignored files before/after.

**(e) Full `FC_*` mapping table (claude-p only).**
The spec maps `FC_MODEL←scout_model` and mentions `FC_BASE_URL←lm_api_base` in AC3 prose, but `FC_API_KEY`, `FC_MAX_TOKENS`, `FC_TEMPERATURE`, and `FC_REASONING_EFFORT` have no explicit mapping from `Settings` fields. A small two-column table in plan.md resolves the ambiguity at implementation time.

**(f) AC3 lock-span assertability (claude-p only).**
The fake factory/agent in the unit test should record whether the lock is held at construction AND at each model-call boundary (simulating the `FC_REASONING_EFFORT` lazy-read window), so the test proves the full span rather than just construction-time holding.

**(g) Missing `FC_MODEL` RuntimeError cause mapping (claude-p only).**
The factory raises `RuntimeError` on missing `FC_MODEL`. `scout_model`'s default makes this unreachable in practice, but the taxonomy should state the mapping (presumably `backend-error`) so the wrap-preserving-cause path (`raise ... from err`) is unambiguous for the implementer.

**(h) Local-path absolute install portability (claude-p only).**
`uv add /Users/daniel.stolf/Development/fastcontext` is machine-specific and non-reproducible in CI. The plan should either vendor fastcontext as a submodule under the repo or record the non-portability as an explicit deviation alongside the AC3 deviation. Whichever choice, CI instructions must not reference an absolute personal path.

**(i) Commit `FASTCONTEXT_INSTALL.md` (claude-p only).**
The spec references this file as its primary reference for install and API facts. It is currently untracked (`??` in git status). It must be committed in this wave so the reference is durable.

### Guardrail and convention violations

**claude-p found no guardrail violations and no convention violations.** The reviewer explicitly resolved the apparent conventions tension: FastContext's env-derived endpoint (`FC_BASE_URL`) is NOT a violation of the "no env-derived endpoint" whitelist in `scout/tools.py` — that whitelist governs the tool surface. The model-client surface is governed by the `rlm.py` precedent, which explicitly handles a configured/env endpoint by asserting `assert_local` first. The TOCTOU risk is shut by holding the lock across `assert_local`→construction. The read-only treatment is textbook assumption-verified-by-test. The cause taxonomy is correct.

**codex's "Read-only locator" flag is a precision request, not a guardrail breach.** The design correctly verified the assumption by test (AC8) and recorded the residual risk — the read-only guardrail's requirement under conventions. Codex's flag is about the test's assertion surface needing an explicit exclusion list (`.harpyja/`, ignored files, mtime-only), not about the design pattern being wrong. This is a planning/implementation detail, not a violation. Codex's two convention flags (async seam, `fastcontext-missing` terminal boundary) are real precision gaps and are carried forward as items (a) and (b) above.

### What both agents praised (preserve through planning and implementation)

- **Source verification section.** Grounding the design in the actual factory signature at a pinned SHA is the right move; it resolved both former open questions and made the lock rationale traceable.
- **AC3 relaxation is honest and sound.** Resisting "OS env is fine, no lock" and landing on env-under-single-flight-lock spanning the full run (because `FC_REASONING_EFFORT` is lazy-read per call) correctly identifies and stops the race AC3 existed to prevent, without overstating the guarantee.
- **Correct guardrail precedents.** Air-gap via `gateway.assert_local` before construction and before subprocess spawn; network-deny integration test; read-only assumption-verified-by-test with recorded residual risk. All three follow established patterns exactly.
- **Tight blast radius.** No changes to `ScoutEngine`, `Locator` seam, or formatter. `normalize_spans` reused from Deep.
- **Invariant explicitly named and protected.** Scout drives `make_fastcontext_agent`, not `dspy.RLM`. Tier 1 and Tier 2 remain structurally distinct. The deviation is confined to `harpyja/scout/`.

---

## Planning checklist (for tdd-planner to fold into plan.md)

Ordered by dependency: items 1-3 must be resolved before test stubs are written, because they determine the concurrency model and the test shapes. Items 4-9 are implementer clarifications that can be resolved during planning without reopening the spec.

1. **Name the lock primitive as `threading.Lock`.** State the calling-context precondition: `ScoutBackend.run` must be dispatched on a thread without a running event loop. Add a concurrency unit test that proves serialization across OS threads (not coroutines).

2. **State the deterministic fallback state machine for `fastcontext-missing`.** Define exactly when `fastcontext-missing` is the final emitted cause (e.g., injected runner wired to `None`; CLI fallback intentionally disabled). Make AC10's `fastcontext-missing` test writable.

3. **Specify `FC_*` set-then-restore in `try/finally` (or record residual leak).** Preserve the unset-vs-empty distinction. Name the lock scope (recommend: module-level singleton, Scout-only).

4. **Define the AC8 assertion surface.** Hash-based snapshot of non-ignored files excluding `.harpyja/`; or a manifest of tracked files before/after. Document which files are excluded and why.

5. **Enumerate the full `FC_*` → `Settings` mapping table.** All five env vars: `FC_MODEL←scout_model`, `FC_BASE_URL←lm_api_base`, `FC_API_KEY` (dummy value for Ollama or derived field), `FC_MAX_TOKENS`, `FC_TEMPERATURE`. Clarify which are set unconditionally vs only when non-None in `Settings`.

6. **Make AC3's lock-span assertable end-to-end.** The fake factory/agent must record lock-held state at construction AND at each simulated model-call boundary (lazy `FC_REASONING_EFFORT` window), not just at construction.

7. **Map the factory `RuntimeError` (missing `FC_MODEL`) to `backend-error` cause.** Add a sentence to the cause taxonomy; update the wrap-preserving-cause path.

8. **Resolve install portability.** Vendor fastcontext as a git submodule under the repo OR record the non-portability of the absolute personal path as an explicit deviation in the Deviations section. CI instructions must not reference `/Users/daniel.stolf/...`.

9. **Commit `FASTCONTEXT_INSTALL.md`.** Include in this wave's commit. If the file is committed as part of the plan wave, note it in the plan as a prerequisite.

---

**Action:** Spec advances to `reviewed`. No third review round required. The tdd-planner should open plan.md and address checklist items 1-9 before writing test stubs — items 1-3 determine test shapes and must be resolved first. Items 4-9 are clarifications that can be folded in during planning without author sign-off on the spec.
