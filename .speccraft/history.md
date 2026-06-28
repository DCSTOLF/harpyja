# History

Append-only. Newest first.

## 2026-06-28 — Wave 6a Eval harness + OQ2 calibration shipped — measurement-only, recommend-only, live-validated

**Spec:** specs/0009-6a/
**Decision:** Land a NEW **measurement-only** package `harpyja/eval/` that observes
the real `mode=auto` `locate()` path and reports locate accuracy, escalation rate,
and gate catch / false-escalation metrics, plus an OQ2 `(verify_threshold,
verify_top_n)` recommendation — and flips **no** `Settings` default (B1; the flip is
a future one-line follow-up spec, so "measurement only, no behavior change" stays
literally true). The harness is the first non-tier layer: it does not answer queries,
it *measures* the system that does. Seven durable choices were pinned. (1) **The
harness observes the SUT through its real public seam and never mutates its config.**
The runner drives the production `harpyja.orchestrator.locate.locate(...)` via an
injected `LocateStack` (fakes for unit, `build_live_stack` real factories for
integration); the only `Settings` interaction is the sweep building grid points via
`dataclasses.replace` on the real `verify_threshold` / `verify_top_n` fields, never
mutation (`test_sweep_does_not_mutate_settings`). (2) **Eval-only knobs live off the
production frozen `Settings` (K-placement deviation).** The spec body's "additive
eval-only `Settings` field carrying K" was reconciled at plan time to a dedicated
frozen `EvalConfig` (k_runs / proximity_window_lines / n_floor / catch_rate_bar),
**field-name-disjoint** from `Settings` (`test_eval_config_is_independent_of_settings`)
— K is a runner loop count the SUT never reads, so putting it in the production config
is a coupling smell with no compensating uniformity benefit. (3) **ONE overlap oracle
defines correctness for every derived metric (D3/D5).** `_any_primary_overlap` (ANY
cited span overlaps ANY expected span in the same file; touching ranges count, D6) is
reused by span-hit accuracy, gate catch-rate, AND gate false-escalation — there is no
second notion of correctness that could drift, asserted by
`test_gate_metrics_use_same_oracle_as_span_hit`. The Tier-1 signal is captured
**independently of escalation**: because the gate replaces citations when it
escalates, `CaseOutcome` carries both `tier1_citations` (gate oracle, an honest extra
Scout call on point cases) and `final_citations` (accuracy). (4) **Gate metrics are
scoped to the point-query subset only (D1).** `gate_catch_rate` /
`gate_false_escalation` range over `classification == "point"` cases; broad queries
bypass the gate (straight to Deep per the 0008 matrix) and are EXCLUDED from both gate
denominators, while `escalation_rate` is a separate aggregate over ALL auto cases —
the two are never conflated. (5) **Null-with-count sentinel on a zero denominator
(D2).** An undefined gate metric serializes as explicit `null` paired with its (zero)
count field, so AC7 "all metrics populated" is honored by a present null-with-count,
never an omitted key or a false `0.0`; the seed must carry ≥1 wrong- and ≥1
correct-Tier-1 point case to keep live denominators non-zero. (6) **Recommendation is
variance-gated and recommend-only (D3/D4, B1).** A sweep point displaces the incumbent
`(0.6, 3)` only when its advantage strictly exceeds the incumbent's run-to-run spread
(`mean(A) - mean(B) > pstdev(B)` over K runs); the D4 lexicographic scorer keeps points
clearing the catch-rate bar, then minimizes false-escalation, tie-breaks lower top_n
then lower threshold. Within noise, the incumbent is recorded **validated**, not
guessed — a `0.55`-over-`0.6` flip on noise is the precise failure this prevents. (7)
**Harness artifacts write outside the indexed repo + a pinned D7 schema.**
`atomic_write_json` refuses (`ValueError`) to write inside or under `repo_path`
(read-only guardrail mirroring the FastContext `trajectory_file`-outside-repo
precedent) via a same-dir temp + `os.replace`; `validate_report` is loud
(`ReportSchemaError`) over the enumerated D7 field set, and small-N runs self-flag
`indicative_only`.
**Why:** All three tiers and `mode=auto` were live and unit-green, but the design's
core claims — escalation stays low, the gate catches wrong Tier-1 citations, the
`scout_model` judge + `top_n=3` hold up — were **unfalsified**: no instrument measured
locate accuracy on a real tree, and OQ2 (`verify_threshold=0.6` / `verify_top_n=3`,
provisional since Wave 5) had no evidence behind it. This wave is that instrument. The
single-oracle and point-scoped denominators exist so two implementers cannot produce
silently incomparable harnesses; the variance gate exists so the recommendation cannot
flap on model non-determinism.
**Consequence — OQ2 partially resolved (the honest outcome).** The harness runs live
and produces a recommendation, BUT the shipped seed is a **5-case starter** over one
small vendored `legacy/` repo (N=5 ≪ the pinned `N_FLOOR=30`), so every run over it is
correctly flagged `indicative_only=true` and the incumbent `(0.6, 3)` is **NOT
displaced**. OQ2 therefore resolves as **"instrument built + live-validated;
calibration deferred to a larger seed"** — NOT a fabricated tuning result. The
provisional `0.6/3` and the `0.90` catch-rate bar remain provisional; a real
calibration (one that could justify a default flip) needs the larger curated D1
dataset (a vendored OSS legacy repo with ≥30 hand-labeled cases), which the plan
explicitly delegates, and the flip itself is a separate one-line follow-up spec.
Shipped TDD-complete: **557 unit tests pass** (+58 new), ruff clean; **5 integration
tests (AC7 ×3 + AC8 ×2) passed LIVE in 634s** — real FastContext Scout + `scout_model`
gate judge + Deep `qwen2.5-coder:3b` over Deno + rg (genuinely verified, not skipped).
`per_tier_model_calls` is honest-`None` (no counter wired through `LocateStack` — a
present null, not a false zero). Open follow-ups carried forward: **the larger D1
dataset → a real OQ2 calibration → a potential default flip in a follow-up spec**; and,
still open from Wave 2, **Wave-2.1 substring/fuzzy matching**.

## 2026-06-27 — Wave 5 Verification Gate + Tier-0→1→2 auto-escalation shipped — `mode=auto` now climbs

**Spec:** specs/0008-wave-5-verification-gate/
**Decision:** Make `mode=auto` trustworthy by wiring the four seams Waves 3/4
deferred — query classifier, planning matrix, Verification Gate, and the escalation
ladder — so `auto` runs the cheapest tier that can answer and climbs only on a real
signal. Tier internals (Tier-0 seed, Scout, Deep) are **unchanged**; this wave is
orchestration only. Seven durable choices were pinned. (1) **The gate is the
`scout_model` reuse judge, routed through the one outbound caller (OQ1 resolved).**
The gate reads the cited lines back from disk and scores their relevance to the query
by reusing the already-loaded Scout fine-tune as a generative judge — no new model to
serve on the single-GPU profile. Because the gate is **in-house orchestrator code**,
its judge call goes through `ModelGateway.complete()` (the only outbound caller, which
already air-gaps at resolution time), **not** a parallel judge client — this is
deliberately *not* the third-party-owns-its-client pattern (Deep/FastContext); it
**additionally** calls `gateway.assert_local()` **before** the judge as a
belt-and-suspenders pre-check (still the one helper, no parallel air-gap type), proven
by a live network-deny integration test. (2) **A generative judge is affordable only
because the scan is bounded top-N (OQ3 resolved) — one causal decision, not two.** The
gate scores at most `verify_top_n` ranked citations (`max` over their scores: one
strongly-relevant span carries the verdict); the dropped count is logged so a bounded
scan is never indistinguishable from a full one (no-silent-truncation). An unbounded
generative judge would put a result-set-sized model cost on the hot path. (3) **The
Wave-0 "auto byte-identical / zero Gateway calls" lock was retired in lockstep** with
the explicit new contract: `_MODE_NO_EFFECT` and its guard tests in **both**
`orchestrator/test_locate.py` and `server/test_app.py` were deleted in the **same**
change that wired the classifier→matrix→ladder, so the suite never holds a state where
`auto` neither emits the old lock nor honors the new AC1 contract — the unspecified
window is closed by construction (the same atomic-invariant-swap discipline as Wave 4's
`deep` guard inversion). (4) **The planning matrix is the genuine single source of
truth — driven by code, not duplicated by it.** `plan_ladder(mode, classification,
index_ready)` over a 6-row `(mode, classification)` seeded table (×`index_ready`
dropping the leading `0` → all 12 rows) is read by both `_locate_auto` and the tests;
a refactor (T17) caught `_locate_auto` re-deriving routing and rewired it to consult
`plan_ladder`, so the escalation branches are *derived from* the table, never a second
authority. (5) **The empty-case three-way split** mirrors the codebase's entrenched
typed-failure-vs-honest-result convention: a Scout **typed-unavailable** degrades to
the Tier-0 floor (`scout-degraded:<cause>`, `confidence="degraded"` UNCHANGED, **no**
climb); an **honest-empty** Scout (clean run, zero citations) skips the gate — nothing
to score — and returns the Tier-0 seed tagged `gate-skipped:scout-empty` (+`no-matches`
on an empty seed), **no** climb; only a **malformed** result escalates. Malformed is
realized as "the gate cannot read back / score the returned citations →
`GateOutcome.failed` → escalate" (Scout's contract is spans-or-`ScoutUnavailable`, so a
malformed result manifests *at the gate*, e.g. a citation whose file is absent fails
read-back — not as a separate Scout signal). (6) **Confidence is keyed on terminal-tier
+ flags, never path tokens alone**, so honest-empty — which shares the `[0,1]`/`[1]`
tokens of a verified gated-pass — gets the distinguishing `gate-skipped:scout-empty`
marker and a distinct `medium`/`low` row, never reading as `high` (no-false-capability:
"nothing found" must never look high-confidence). The typed-unavailable `"degraded"`
literal is preserved; the map's `low` rows are gate-states only, so AC8 and AC9 never
collide. A best-effort gate **never blocks and never silently passes**: a scoring
failure routes exactly like a gate-fail (escalates in `auto` where a tier remains, with
`gate-scoring-failed` retained and `confidence=low`; best-effort un-gated Tier-1 in
`fast`). (7) **`verify_method` honors no-false-capability at the config surface.** Three
additive `Settings` fields are appended last (`verify_method="scout_model"`,
`verify_threshold=0.6`, `verify_top_n=3`); `__post_init__` rejects any unsupported
`verify_method` (`embedding`/`model_judge`/arbitrary) with a typed
`UnsupportedVerifyMethod` naming the field + accepted set — on **every** construction
path (defaults, toml, env, per-request `replace`), never a silent fall-through to
`scout_model`. The seam is pluggable in *code*, but the config accepts only what
actually functions.
**Why:** All three tiers were live and verified end-to-end, but `auto` had nowhere to
climb — it stayed pinned to Tier 0. The honest cost lever ("cheapest tier that works")
only exists once a gate can decide whether the Scout answer is good enough to stop, and
the gate is the precise mechanism the Wave-3/4 entries kept deferring (Deep's "weak
output is NOT a degrade — that is the ungated escalation the Wave-5 gate governs" was a
direct forward reference). Reusing `scout_model` makes the sharper judge free on the
single-GPU profile; bounding it top-N is what keeps that generative call affordable on
the hot path — the two resolutions are one coupled decision, not two.
**Consequence:** `mode=auto` now realizes `tiers_run` as a prefix of the planned ladder
(gated-pass `[0,1]` / `[1]`; escalated `[0,1,2]` / `[1,2]`; broad straight-to-Deep
`[0,2]` / `[2]`); `fast` runs the gate **informationally** and never climbs (a
would-fail gate tags `gate-low-confidence`); `deep` is unchanged. Shipped TDD-complete:
513 tests pass with **all** integration ACs run live (FastContext Scout + scout_model
gate judge + Deep `qwen2.5-coder:3b` over Deno — point resolved cheap, broad climbed to
Tier-2), ruff clean. Three new stable flag ids join the taxonomy
(`gate-low-confidence` / `gate-scoring-failed` / `gate-skipped:scout-empty`). Open
follow-ups carried forward: **OQ2** — the provisional `verify_threshold=0.6` /
`verify_top_n=3` defaults still need tuning against the eval repo (the ACs assert
thresholding *behavior*, not the numbers); and, still open from Wave 2, **Wave-2.1
substring/fuzzy matching**.

## 2026-06-27 — Scout Tier-1 real default client shipped — FastContext agent, env-under-threading-lock, off-loop bridge

**Spec:** specs/0007-fastcontext/
**Decision:** Supply the **real default client** for the already-shipped
`FastContextBackend` seam (Wave 3 left it injected-only), so Scout (Tier 1) drives the
real Microsoft FastContext agent (`make_fastcontext_agent` — its own Read/Glob/Grep
loop, **not** `dspy.RLM`; the load-bearing invariant keeping Tier 1 structurally
distinct from Tier 2) end-to-end and the Wave-3 live AC flips skip → genuine pass. The
`ScoutBackend`/`ScoutEngine`/`Locator`/formatter seams stayed **unchanged**; all new
code lives in `harpyja/scout/` plus four additive `Settings` fields and two new
`errors.py` causes. Six durable choices were pinned. (1) **One client, two paths.**
Path A (primary, in-process): lazy-import the factory, build a fresh agent
(`work_dir=<repo>`, `trajectory_file=<temp OUTSIDE repo>`),
`await agent.run(..., citation=True)`. Path B (fallback): injected CLI runner with
`FC_*` scoped to the child via `env=` (no parent-env mutation). (2) **Off-loop bridge +
`threading.Lock`, verified against FastContext source @ SHA `1522d6d6…`.** The factory
is **env-only** (no `model`/`base_url` params; reads `FC_*` from `os.environ`;
`FC_REASONING_EFFORT` is read **lazily per model call** at `llm.py:77`), so AC3's
absolute ban on `os.environ` mutation relaxed to a conditional one: `FC_*` are injected
via process env, but **only while holding a module-level `threading.Lock`
(`_SCOUT_ENV_LOCK`)** — *not* an `asyncio.Lock`, because each call bridges
`agent.run` onto its **own loop-free worker thread** (`_run_coro_on_worker_thread`, so
`asyncio.run` is legal even when the MCP handler is already on a loop), and only a
thread lock serializes cross-thread `os.environ` writes. The lock is held across the
**entire run** (the lazy reasoning-effort read), set-then-restore with per-key
unset-vs-empty preservation. This **serializes Scout** — accepted for the single-GPU
profile (concurrent Scout calls already contend for the one 4B model); Scout-only,
never leaks to Deep. (3) **Air-gap before construct/spawn, TOCTOU closed.** A single
`gateway.assert_local` on the resolved `FC_BASE_URL` fires before the agent is built
(Path A) and before the subprocess is spawned (Path B); on Path A the lock spans
assert → env-set → construct → run. FastContext owns its own model client (the
`rlm.py` precedent, not the `scout/tools.py` whitelist — the whitelist is **vestigial**
for Path A, recorded as an honest limit), proven by a network-deny integration test.
(4) **Read-only assumption-verified-by-test.** `trajectory_file` resolves outside the
repo; a no-repo-writes integration test (content-hash manifest excluding `.harpyja/`)
proves the scanned repo is byte-unchanged; residual in-process write risk recorded,
symmetric to the network-deny. (5) **Four-way degrade taxonomy + deterministic state
machine.** Added `fastcontext-missing` / `cli-missing` to the existing
`connection-refused` / `no-endpoint-configured` / `backend-error`; the Path-A→Path-B
machine makes `fastcontext-missing` terminal **only** when the CLI runner is unwired,
so AC10's test is unambiguous. (6) **AC10 broadened live (graceful-degradation
guardrail).** A live run surfaced that FastContext's **own** `get_final_answer` /
`format_citations` can raise (e.g. `TypeError`) on malformed model output — confinement
worked, but the third-party post-processing crashed; the client now maps **any**
unexpected backend exception → `ScoutUnavailable(backend-error)` so Scout degrades to
Tier 0 rather than letting a raw exception escape. Floors (`RipgrepMissingError` /
`AirGapError`) and the Path-B `ImportError` signal still propagate; honest-empty (a
clean run, no parseable citation) returns `[]`, never raises.
**Why:** Tier 1 was structurally present since Wave 3 but never ran a model
end-to-end — the live AC only ever skipped. FastContext is real and installable, so
this wave cashes in the seam exactly as Wave 4 did for Deep, turning the suite's last
skip into a genuine pass. The lock rationale is grounded in the actual factory
signature at a pinned SHA, not assumed; the env-under-lock design stops the precise
cross-request race AC3 existed to prevent without overstating the guarantee.
**Consequence:** Scout is **not cached** (model-backed/non-deterministic, no
engine-identity slot — like Deep). Verified live (~42s, suite 442 passed / 0 skipped,
ruff clean); FastContext's confinement blocked the model reading `/harpyja` outside
`work_dir`, and the live ACs accept either Tier-1 success (`[0,1]`) or an honest
`scout-degraded:backend-error` (`[0]`) — both prove the real stack ran. FastContext
ships as a **portable `git`-rev pin** at the SHA — the plan's provisional local-path
editable install (flagged non-portable for CI) was tested and corrected: the
`third_party/mini-swe-agent` submodule is **vestigial** (unreferenced by the package),
so the submodule-skipping `git+https` install resolves and imports cleanly; the
non-portability deviation no longer applies. The **FastContext default client is now
DONE** — no longer an open question. Open follow-ups carried forward: the
**Verification Gate +
Tier-0→1→2 auto-escalation ladder** (Wave 5 — `mode=auto` still does not climb) and,
still open from Wave 2, **Wave-2.1 substring/fuzzy matching**.

## 2026-06-27 — Wave 4 Deep (Tier 2) shipped — dspy.RLM, sandbox, layered explorer-loop bounds

**Spec:** specs/0006-wave-4-deep-rlm/
**Decision:** Land Harpyja's strongest, most expensive tier — Tier 2 Deep, a
`dspy.RLM` explorer running inside a Deno/Pyodide sandbox whose **entire world** is
four bounded, read-only host tools — reached only via `mode=deep`, and make the
Wave-3 provisional `deep` real by shipping routing **and** implementation together.
`mode=auto` stays byte-identical and model-free; `mode=fast` stays Scout. Eight
durable choices were pinned. (1) **Layered explorer-loop enforcement — no single
ignorable counter is load-bearing.** An untrusted code-writing loop is bounded at
different seams: *externally enforced* (the backend cannot evade) `deep_max_tool_calls`
(host-tool wrappers stop dispatching), `deep_token_ceiling` (the Gateway refuses
further completions), and `deep_wall_clock_ms` (a host deadline) are the load-bearing
trio; `deep_max_depth` / `deep_max_subqueries` are *host-mediated* at the spawn seam
with **recorded residual risk** (if the runtime exposes no spawn/recurse hook they
become cooperative) and are **transitively contained** by the external trio — every
sub-query spends tool-calls, tokens, and wall-clock, so a recursion storm terminates
even if the mediation seam is cooperative. A bound the third party can ignore is not
a bound. (2) **Wall-clock requires an out-of-band, host-terminable subprocess.** A
same-thread/same-event-loop deadline can never fire while a synchronous WASM busy
loop blocks it; `DeepRunner` therefore splits an in-process counter facet
(unit-testable, no process) from an out-of-band `run_isolated` worker the host
**hard-kills** — enforcement by termination, never cooperative cancellation; proven
against a genuine `while True: pass` (AC10) and a real RLM runaway (AC10a). (3)
**Typed-failure-only degradation boundary.** Deep degrades to Scout best-effort
**only** on a typed `DeepUnavailable` (`sandbox-absent` / `rlm-down` / `backend-error`);
weak or zero citations are an honest Tier-2 result, **not** a degrade — treating weak
output as a reason to drop a tier would be the ungated escalation the deferred Wave-5
Verification Gate is meant to govern, and must not be smuggled in here. (4)
**`deep-truncated:<bound>` is a stable, caller-visible non-degrade note** (one of
`depth` / `subqueries` / `tool-calls` / `tokens` / `wall-clock`) — a budget
truncation is never silently indistinguishable from a complete run and never a
tier-degrade. (5) **RlmBackend air-gap via `assert_local` on the endpoint.** The real
`dspy.RLM` owns its own `dspy.LM` (litellm) and accepts no model_fn, so it cannot be
routed through `gateway.complete` as the spec assumed; instead `RlmBackend` calls
`gateway.assert_local(settings.lm_api_base)` **before** constructing the LM (single
air-gap helper, no parallel check) and the air-gap is **proven** by the network-deny
integration test (AC12) — assumption-verified-by-test, not asserted. (6) **`DeepEngine`
dual surface.** It self-seeds Tier-0 before the backend and exposes both `.search` for
`Locator` conformance and `run() -> (citations, truncated_bound)` because the
truncation bound is metadata the bare `list[CodeSpan]` contract cannot carry. (7)
**Sandbox isolation verified by test, residual risk recorded.** In the real sandbox an
ambient `open()` (outside *and* inside the repo — the latter would bypass `read_span`'s
clamps) and a non-loopback socket connect all fail (AC8b); the four-tool surface is
also pinned by a deno-less positive-equality `[unit]` whitelist (AC8a). The
runtime-change residual risk is recorded, exactly as the Wave-3 FastContext in-process
egress risk was. (8) **Lockstep guard inversion shipped atomically:** the two Wave-3
guards asserting `deep` emits *no* Tier-2 marker were deleted and replaced by the
inverse invariant in the same change — the suite never holds both sides.
**Why:** The hardest retrieval — trace a request across packages, find every consult
of a budget — needs *iteration* (search, read, partition, spawn sub-queries, pull only
what matters into token space), which a single Scout pass cannot do without blowing the
context window. Because the RLM *writes and runs code* against the host tools, it is an
untrusted **caller** and untrusted **code**: the confinement Wave 3 hardened at the
FastContext boundary now applies one layer deeper, at every host tool, and the bounds
had to be enforced where the backend cannot evade them.
**Consequence:** Deep is **not cached** (model-backed/non-deterministic, no
engine-identity slot — like Scout). Verified live against dspy 3.2.1 + Deno 2.9.0 +
Ollama (loopback) + ripgrep 15.1.0 (cold ~50s, warm ~15s); a weak 4B model means the
live ACs assert pipeline *shape* (valid possibly-empty `CodeSpan`s), not citation
quality. Open follow-ups carried forward: the **Verification Gate + Tier-0→1→2
auto-escalation ladder** (Wave 5 — `mode=auto` still does not climb); the **FastContext
package** for Scout is still absent (Wave-3 live AC1 still skips); and, still open from
Wave 2, **Wave-2.1 substring/fuzzy matching**.

## 2026-06-27 — Wave 3 Scout (Tier 1) + Model Gateway request path shipped

**Spec:** specs/0005-wave-3-scout/
**Decision:** Land Harpyja's first model-backed tier (Scout, Tier 1) and the Model
Gateway **request path** — the single outbound seam every later tier builds on — as an
explicit-opt-in capability that leaves `mode=auto` byte-identical to Wave 2 with **zero**
Gateway calls. Six durable choices were pinned. (1) **A four-state degradation floor.**
A Scout call resolves to exactly one caller-visible state that never collapses into
another: model-down → Tier-0 citations (`confidence="degraded"`, `tiers_run=[0]`,
`scout-degraded:<cause>` note); Tier-0-has-results vs Tier-0-honestly-empty are kept
distinct by a `+no-matches` suffix; and a Tier-0 hard precondition absent
(`RipgrepMissingError`) **propagates loudly**, never swallowed into a degraded-empty.
(2) **Seed-before-backend ordering makes the loud case win by construction.** `ScoutEngine`
runs its own Tier-0 self-seed *before* the backend (under `mode=fast` the caller skipped
`auto`'s pass), with no try/except around `seed_fn`, so `rg`-missing-and-model-down
surfaces state 4 deterministically — the dangerous composition is impossible by ordering,
not luck. (3) **Resolution-time air-gap reused from Wave 0, with a new guarded request
path.** Rather than the spec's named `NonLoopbackEndpointError`, the new
`ModelGateway.complete()` reuses the single air-gap helper (`assert_local` + `AirGapError`)
and asserts loopback on **resolved** addresses **before** an injected transport is touched
— a non-loopback endpoint raises a loud floor error, deliberately *not* one of the four
degrade states. (4) **`ScoutBackend` Protocol + `FastContextBackend` (injected client)
keep the FastContext dependency swappable** — no top-level hard import, so the sole open
question (FastContext package/version) can never break the suite, and Scout sits behind
the shared `Locator`/`CodeSpan` boundary so callers never branch on engine identity. (5)
**`auto` byte-identical / zero-Gateway lock** landed before any routing (T19) and was
re-checked after the `_tier0_seed` refactor (T27); `index`/`read`/`auto` make zero model
calls. (6) **`mode=deep` lockstep guard** (no-false-capability): `deep` provisionally
mirrors `fast`, attaching a `Deep pending` note and asserting **no** Tier-2 marker (no `2`
in `tiers_run`, no Tier-2 identity/cache key) so its later divergence is not a surprise
regression.
**Why:** Tier 0 goes blind on conceptual / natural-language queries that name no symbol
or literal — the honest Tier-0 answer is "nothing found," and a naive Scout fallback would
silently re-create that phantom. The floor and the seed-ordering exist precisely so a
model-down run can never read as a clean zero. Being the first model wave, the air-gap and
the degradation floor — previously cheap — became load-bearing and are now specified at
the Gateway request path and at resolution time, one helper, auditable in one place.
**Consequence:** Scout is **not cached** (model-backed/non-deterministic, no engine-identity
slot — the Wave-2 cache-slot question does not apply). Open follow-ups carried forward:
**FastContext package/version pinning** (the sole genuinely-open item, de-risked behind the
Protocol); a **process/WASM sandbox** for FastContext's in-process egress (tool injection
can't stop third-party in-process code opening its own socket — Scout has no sandbox unlike
Tier 2 Deep; the containment is an assumption verified by the network-deny integration test
AC11, not an asserted guarantee); and, still open from Wave 2, **Wave-2.1 substring/fuzzy
matching**.

## 2026-06-26 — Wave 2 symbol layer completed (all 10 grammars) + no-silent-coverage lockstep

**Spec:** specs/0004-symbol-layer-remaining-grammars/
**Decision:** Close the Wave-2 follow-up by adding the remaining eight tree-sitter
grammars — Rust, Java, C#, JavaScript, TypeScript, TSX, C, C++ — behind the
**unchanged** `SymbolEngine` / `Locator` / formatter path, so only more languages
produce records (locate/orchestrator/contract untouched; AC15 held by construction).
Three durable choices were pinned: (1) **No-silent-coverage lockstep invariant.**
Wave 1 already shipped a latent no-false-capability violation — `classify._EXT_TO_LANG`
over-routed all 9 languages while `indexer.SYMBOL_LANGUAGES` was only `{python, go}`,
so a `.rs`/`.ts` file returned `([], None)`: a silent clean-zero indistinguishable
from a genuinely symbol-less file ("we never looked" masquerading as "we looked and
found nothing"). The fix is a permanent invariant `classify.KNOWN_LANGUAGES ==
indexer.SYMBOL_LANGUAGES`, asserted by a new `index/test_routing.py` and re-checked at
every tier boundary: a language's **routing + `engine_identity` slot + extraction
rules ship in the same change**; an unshipped tier stays null-language/ripgrep-only,
never silent zero. (2) **`.h`→C is a scoped, not absolute, guarantee.** Both reviewers
flagged the original "never a wrong-range record" overclaim; impl confirmed it —
tree-sitter-c *tolerates* a bare `class Foo {}` (parses it, no ERROR), so the test
uses `template<…>`, which reliably triggers an ERROR. The shipped guarantee: degrade
only when an `ERROR`/`MISSING` node is present; a C-legal subset of a C++ header
parsing cleanly as `c` is the documented cost of the `.h`→C default, not claimed as
rejected. (3) **Per-grammar identity slots, coupled where the package couples.**
`engine_identity` now enumerates all 10 slots via a `_GRAMMAR_SLOTS` map
(slot → dist, module, language-fn) that replaced the flat `_GRAMMARS` tuple;
`typescript` and `tsx` ship from one `tree-sitter-typescript` package, so they are
two identity keys with one version that bump/absent together (loaded via
`language_typescript()` / `language_tsx()`, not `language()`).
**Why:** Until this spec, the index advertised a symbol tier it delivered for only two
of seven languages — a Rust `fn` or Java method fell to ripgrep line hits, the exact
context-flooding Wave 2 exists to prevent. The lockstep invariant generalizes the
project's no-false-capability rule to *coverage*: routing a capability ahead of its
extraction is itself a false claim. Reuse kept the surface small — `_strip_go_type`
(generic/pointer parent normalization), the `^[A-Z][A-Z0-9_]*$` constant filter, and
`_own_region_errored` (parse-error scoping) were reused verbatim, with a shared
`_emit_named` helper backing Java/C#/JS/C-family.
**Consequence:** Tier 0 now covers all 10 grammars; the symbol-layer adapter is fully
cashed in. Two accepted, documented limitations remain: a C-legal subset of a `.h`
C++ header is parsed as `c`, and `parent` is immediate-only, so two same-named members
under different outer types/namespaces both match `Foo::bar` (a known addressing
ambiguity, not a regression). The 5-grammar follow-up opened at 0003's close is now
closed by this spec; **Wave-2.1 substring/fuzzy matching** remains the sole open
follow-up (still needs its own ranking rules + ACs). Method addressing stays a
formatter-ranking signal (a subset of name results glued by `.`/`::`), not a
membership filter.

## 2026-06-26 — Wave 2 symbol layer shipped (tree-sitter, Python + Go)

**Spec:** specs/0003-wave-2-symbol-layer/
**Decision:** Add a Tier-0, model-free symbol layer that surfaces a symbol's
**definition above its call sites**, filling the `symbols_indexed` / `degraded`
slots Wave 1 reserved. (1) A tree-sitter extractor (`symbols/`) parses **Python and
Go only** — defs-only, classified by **syntactic form** (no type inference) — into a
byte-reproducible `symbols.jsonl` ordered by the total key
`(path, start_line, end_line, kind, name)`; the other five grammars are a deliberate
follow-up spec. (2) The records file is paired with a tiny self-verifying
`symbols.meta.json` sidecar carrying `engine_identity` (tree-sitter runtime + each
pinned grammar version) + `record_count` + a sha256 `content_digest` over the
records' exact bytes; a refresh forces a full symbol rebuild — independently of the
`(mtime, size)` gate — on any missing/truncated record file, missing meta,
engine-identity mismatch, or fingerprint mismatch, committing **records-first,
meta-last** via same-dir temp + `os.replace`. (3) Graceful degradation has two
distinct, persisted causes: `grammar-missing` (absent/load-fail grammar → zero
symbols) and `parse-error` (scoped to a definition's **own region excluding
nested-definition subtrees**, so a broken method never suppresses its clean
enclosing class); `degraded` is persisted per-file on the manifest entry so a
no-reparse refresh re-surfaces it (total-in-index, like `symbols_indexed`). (4)
`SymbolEngine` implements the shared **`Locator` protocol** (exact, case-sensitive
name matching + `.`/`::` method addressing; substring matching deferred to Wave 2.1);
the orchestrator composes it with the ripgrep Locator into one `CodeSpan` stream and
never branches, and the formatter applies a placeholder **definition boost** between
`prior` and density. A no-symbol-match query degrades byte-identically to the Wave-1
ripgrep-only path.
**Why:** A raw line-grep can't tell a definition from its hundred call sites — the
exact context-flooding the project exists to prevent. The symbol layer is the first
tier where structure, not just text, drives the answer, while staying zero-cost and
fully local (air-gap untouched, audited). The self-verifying sidecar is the durable
lesson from four cross-review rounds (D15 changed three times): **an untrusted
derived artifact must authenticate its own generation — a content fingerprint — not
just its producer's identity**; engine-identity alone misses a records-first/meta-last
crash residue and a clean newline truncation, the fingerprint catches both.
**Consequence:** Tier 0 is now deterministic + symbol-aware: index → (ripgrep +
symbols) → citation formatter, all behind the same `harpyja_locate` contract. Two
deliberate follow-ups are opened: the **five remaining grammars** (Rust, JS/TS, C#,
Java, C/C++ — the extractor is built so adding a grammar is additive) and **Wave-2.1
substring/fuzzy matching** (it needs its own ranking rules + ACs and would otherwise
create a fuzzy match-state that could promote the wrong definition over a correct
text hit). Symbol-boost weights are documented placeholders tuned later but must
preserve the AC ordering.

## 2026-06-26 — Wave 1 deterministic core shipped

**Spec:** specs/0002-wave-1-deterministic-core/
**Decision:** Replace the Wave 0 `harpyja_locate` stub with a model-free Tier-0
locator and pin seven choices that the deterministic floor stands on:
(1) `.gitignore` is matched via the `pathspec` library's `gitwildmatch` — never by
invoking `git` — so non-git directories index correctly and nested per-dir
`.gitignore`, negation, dir-only, anchored, and `**` rules all work.
(2) Incremental indexing is a two-level scheme: a cheap `(mtime, size)` gate avoids
re-hashing, the sha256 hash is the change-of-record, deleted files are pruned, and
`--rehash` is the documented escape hatch for the coarse-mtime same-second/same-size
edge. (3) "Ensure-index" is *defined as* a full incremental refresh on every
`locate` — staleness is not a separate heuristic; the incremental pass *is* the
reconciliation, and it builds from scratch when no manifest exists. (4) `rg` on
`PATH` is a hard precondition for **search/locate only** (typed `RipgrepMissingError`,
named in `doctor`), never for `harpyja_index`, which is pure Python. (5) Index
artifacts default to `<repo>/.harpyja/` (self-ignoring `.gitignore`=`*`, root
`.gitignore` untouched) and fall back to `${XDG_CACHE_HOME:-~/.cache}/harpyja/<repo-hash>/`
(sha256 prefix of the abs realpath) when the repo is unwritable. (6) Ripgrep search
is literal-by-default (`--fixed-strings`); validated regex is deferred. (7) The
locate contract treats its three fields distinctly — `max_results` is a mandatory
clamp, `mode` is accept-validate-flag (inert in Wave 1 but never a silent no-op), and
`language_hint` is best-effort with *distinct* notes for an unrecognized hint vs
null-language exclusion.
**Why:** Establish an honest, reproducible, zero-cost deterministic floor that every
later tier (Scout, Deep, the verification gate) is purely additive on top of. The
hard `rg` fail and the distinct hint notes both follow the same honesty principle:
a silent empty result that reads as "nothing found" is worse than a loud, actionable
failure. Matching `.gitignore` without `git` keeps indexing dependency-free and
correct on non-git trees.
**Consequence:** Wave 2+ adds the symbol layer (`symbols_indexed`/`degraded` are the
reserved slots) and higher tiers behind the same `harpyja_locate` contract and the
same manifest. The `(mtime, size)` gate's coarse-granularity miss is a known,
documented approximation gated by `--rehash`. Toml config stayed flat (mirroring
`Settings` fields) rather than SPEC §5's `[search]/[tools]/[index]` tables — a future
nested-table need must add a flattening layer behind its own test.

## 2026-06-26 — Wave 0 foundations shipped

**Spec:** specs/0001-wave-0-foundations/
**Decision:** Ship the agent↔server skeleton with a stub-first MCP contract and
four foundational choices: (1) the air-gap is enforced in exactly one helper,
`gateway.assert_local`, reused for both the outbound endpoint and — via
`DEFAULT_HTTP_HOST=127.0.0.1` plus the CLI `--allow-remote-bind` opt-out — the
inbound HTTP listener; loopback = `127.0.0.0/8` / `::1` / literal `localhost`.
(2) `harpyja_locate` is registered and returns a schema-valid empty
`LocateResult` (`confidence="low"`) per SPEC §2.1 — no retrieval. (3) Config
resolves with precedence defaults < `harpyja.toml` < `HARPYJA_*` env <
per-request override, on a frozen `Settings` dataclass. (4) Tests live next to
the package under test (`test_*.py`); no top-level `tests/` root.
**Why:** Pin the riskiest integration surface (MCP registration, which differs
between Claude Code and Codex) early and make later waves purely additive; keep
the air-gap guarantee auditable in one place rather than scattered across layers.
**Consequence:** Wave 1+ adds retrieval behind the existing `harpyja_locate`
contract without touching transport, config, or the air-gap. The inbound bind
default and `assert_local` are the security-load-bearing surfaces to preserve.

## 2026-06-26 — speccraft adopted

**Spec:** specs/0001-speccraft-v1/
**Decision:** Adopt speccraft for spec-first TDD workflow.
**Why:** Establish disciplined spec-first development from day one.
**Consequence:** All future code changes go through `/spec:new`.
