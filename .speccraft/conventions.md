# Conventions

## Naming

- Modules/functions/variables: `snake_case`. Classes: `PascalCase`. Constants: `UPPER_SNAKE_CASE`.
- Test functions: `test_<subject>_<scenario>`. <!-- enforce: regex pattern="^def test_" scope="**/test_*.py" -->

## Types & interfaces

- Public functions are fully type-annotated. Tier engines implement the shared `Locator` protocol and return the common `CodeSpan` / `Citation` shapes — callers never branch on which engine ran.
- A shared cross-tier value type may express **coarser precision** rather than forcing
  a fabricated value: `CodeSpan.start_line`/`end_line` are `int | None`, with `None ⇒
  file-level` (a path-only citation with no honest line range — never a `0`/`1`/EOF
  sentinel that reads as a real span). Expose the distinction as **one predicate**
  (`CodeSpan.is_file_level`, both-lines-`None`) that every downstream consumer branches
  on, so a coarse path-only result can never read as a line-verified one (the
  honest-precision/no-false-capability rule, in the type). Enforce a **both-or-neither**
  invariant at every boundary that constructs the type — a half-`None` span is not a
  sanctioned shape and is rejected at the parse/normalize boundary, so a single-field
  guard downstream is sound. (See `harpyja/server/types.py` `CodeSpan.is_file_level`,
  AC23.)
- A type-shape change to a shared contract (e.g. widening a required `int` field to
  `int | None`) **enumerates its full blast radius by category, not piecemeal**: a
  single `grep -rn '<field>'` surfaces **every** consumer at once, and each is made
  shape-safe in the **same** change with its **own** RED→GREEN, ordered along the data
  path (producer → … → sink) so the new shape is handled before the next stage sees it.
  The failure mode this prevents is a missed consumer that crashes a tier on exactly
  the case the change exists to fix (the round-3 formatter miss); the same class of
  miss recurs once per stage left un-grepped (e.g. a primary metric oracle guarded but
  its sibling secondary oracle missed). (See spec 0011's `start_line`/`end_line`
  widening across `scout/`, `orchestrator/`, `eval/`.)
- A routing/decision matrix is the **single source of truth**, *driven by* the routing code rather than duplicated by it. When dispatch depends on a small fixed product of dimensions, encode the full mapping in one table (e.g. `(mode × classification × index_ready) → planned ladder`) that both the executor and the tests read; the executor derives its branches **from** the table (a refactor that catches the executor re-deriving a routing rule is a real bug, not a style nit), and every row is asserted. Documented escalation/branch rules are *derived from* the table, never a second authority that can silently drift. (See `harpyja/orchestrator/matrix.py` `plan_ladder`, consulted by `_locate_auto`; AC3.)

## Config & immutable state

- Config is a frozen dataclass (`Settings`). Produce overrides with `dataclasses.replace`, never mutation — every override returns a new instance.
- Layer precedence is explicit and one-directional: defaults < `harpyja.toml` < `HARPYJA_*` env < per-request override. `harpyja.toml` keys mirror `Settings` field names; values are coerced to the field's declared type.

## Errors & failure posture

- Prefer graceful degradation over raising (see guardrails.md): fall back a tier and attach a confidence flag rather than hard-failing a `locate`.
- Graceful degradation has a floor: when a *hard precondition* for a tier is absent and there is no honest degraded answer to give, fail loudly with a typed, actionable error naming the missing dependency — never a silent empty result that reads as "nothing found." (e.g. `rg` missing → `RipgrepMissingError` on search/locate, surfaced by `doctor`; `index` does not require `rg` and still succeeds.) The same honesty rule means distinct failure causes get distinct caller-visible notes, never one collapsed empty result (e.g. unrecognized `language_hint` vs null-language exclusion).
- Caller-visible degrade/failure markers are **stable machine-readable identifiers**, not free prose, so callers and tests branch on the identifier rather than the wording. A cause taxonomy is an enumerated, stable set with a composable suffix that keeps otherwise-collapsible states distinct — e.g. Scout emits `scout-degraded:{connection-refused|no-endpoint-configured|backend-error}` with a `+no-matches` suffix that distinguishes "Tier-0 honestly empty" from "Tier-0 had results." (See `harpyja/scout/errors.py`, `harpyja/orchestrator/locate.py`.)
- The air-gap is enforced in **one** place only: reuse `gateway.assert_local` / `AirGapError` — never introduce a parallel air-gap error type or a second check. A new outbound path (e.g. `ModelGateway.complete()`) asserts loopback on **resolved** addresses *before* any I/O leaves the process; a non-loopback endpoint is a loud floor error, never a degrade note.
- Third-party in-process code that can open its own socket is an **assumption verified by test**, never an asserted air-gap guarantee. The air-gap is enforced only at the Gateway; everything Harpyja *hands* such code is constrained to an exact positive-equality whitelist (no raw `base_url`, no env-derived endpoint, no HTTP client), and the residual in-process egress risk is backed by a network-deny integration test plus a tracked sandbox follow-up — recorded, not buried (no false-capability claim). (See `harpyja/scout/tools.py`, AC10/AC11.)
- An untrusted, in-process code-**writing** loop is bounded in a **layered** way at different seams — no single ignorable counter is load-bearing. Externally-enforced counters the loop cannot evade (host-tool wrappers stop dispatching; the Gateway refuses further completions) plus a **wall-clock hard-kill via an out-of-band, host-terminable subprocess** are the load-bearing guarantees — a same-thread/event-loop deadline can never preempt a synchronous WASM busy loop, so enforcement is by hard termination, never cooperative cancellation. Internal control-flow bounds (recursion depth / sub-query fan-out) are host-mediated where the runtime exposes a spawn/recurse hook, else **recorded as residual risk** and **transitively contained** by the external counters (every sub-query spends tool-calls, tokens, and wall-clock). A bound the third party can ignore is not a bound. (See `harpyja/deep/runner.py`, `harpyja/deep/budget.py`, AC10/AC10a.)
- A budget/quality **truncation** is a distinct, caller-visible, **stable non-degrade marker** (`deep-truncated:<bound>`, one of `depth`/`subqueries`/`tool-calls`/`tokens`/`wall-clock`) — never silently indistinguishable from a complete result, and never a tier-degrade (dropping a tier on a *successful but truncated* run would be the ungated escalation a verification gate is meant to govern). Distinct from both a complete run and a typed `DeepUnavailable` degrade. (See `harpyja/orchestrator/locate.py`, `harpyja/deep/engine.py`.)
- When a third-party tier owns its **own** model client and cannot be routed through the in-house Gateway, enforce the air-gap by calling `gateway.assert_local` on the configured endpoint **before** constructing that client, and **prove** no non-loopback egress with a network-deny integration test — assumption-verified-by-test, not an asserted guarantee. Still **one** air-gap helper, never a parallel check. (See `harpyja/deep/rlm.py`, AC6/AC12.) When that third party is **env-configured** (reads its endpoint/model from `os.environ`, with no constructor/config-file seam — verify against the pinned source) and must be bridged off the request loop, inject its env **only while holding a module-level `threading.Lock`** — *not* an `asyncio.Lock`: each call runs the awaitable on its **own loop-free worker thread** (`asyncio.run` is illegal inside a running loop, so a worker thread keeps the sync seam intact), so concurrent calls land on different OS threads and only a thread lock serializes their `os.environ` writes. Hold the lock across `assert_local` → env-set → construct → the **full** off-loop run when any config key is read lazily per model call (closes the TOCTOU window). The env guard is **set-then-restore** in `try/finally` preserving per-key **unset-vs-empty** (a key absent before is `del`-eted after; a `""` is restored to `""`). This serializes the tier — accept it only where calls already contend for one resource (e.g. a single local GPU), and confine the latitude to that tier (never leak it to a sibling that keeps "config from `Settings`, not ambient env"). The fallback subprocess path scopes env to the **child** via `subprocess env=`, never mutating the parent. (See `harpyja/scout/client.py` `_SCOUT_ENV_LOCK` / `_managed_fc_env` / `_run_coro_on_worker_thread`, AC3/AC4.)
- A third-party **post-processing crash** is infra failure, not a result: when a backend's own output formatter/parser raises on malformed model output (e.g. FastContext's `get_final_answer` / `format_citations` raising `TypeError`), map **any** unexpected backend exception to the tier's typed degrade cause (`...Unavailable(backend-error)`) — never let a raw third-party exception escape the tier. Floors (`RipgrepMissingError` / `AirGapError`) and the package-absent import signal still propagate; an honest-empty result (a clean run that parsed no citation) still returns `[]`, never a raise. This honors "no model → Tier 0": a buggy backend degrades, it does not crash the request. (See `harpyja/scout/client.py`, AC10.)
- When a third party's **own** output formatter is the thing that crashes and its
  **raw input is available**, don't route the result through the crashing
  post-processor and catch the exception as control flow — invoke the backend in the
  mode that **bypasses** the formatter and parse the raw output **in-adapter**. (FC's
  `format_citations` crashes inside `agent.run(citation=True)` on bare-path model
  output; Scout invokes `citation=False` and parses the raw `<final_answer>` text
  itself — no exception on the hot path, vs the alternative of keeping `citation=True`
  and catching the crash every call.) This composes with the post-processing-crash
  degrade rule above: that rule is the **floor** for a genuine backend exception
  (`agent.run` itself raising → `backend-error`); bypass-and-parse is the **fix** that
  keeps the hot path crash-free, and a clean run that parses no citation is still an
  honest-empty `[]`, never a raise. The adapter remains the **single owner** of the
  backend's wire format (parse the raw text in `scout/`, never upstream and never in the
  orchestrator). (See `harpyja/scout/client.py` seam (a), `parse_final_answer`,
  spec 0011 AC1/AC8/AC20.)
- A best-effort verification/scoring step **never raises and never silently passes**: it maps **any** internal failure (a judge call erroring, an un-readable input) to a typed *could-not-vouch* outcome (`GateOutcome.failed=True`, `passed=False`) and routes it exactly like a negative verdict — escalate where a further tier remains (retaining a stable diagnostic flag, e.g. `gate-scoring-failed`), else return the best-effort current-tier result tagged with that same flag. A could-not-vouch is never a hard block and never an unflagged pass. Relatedly, **derived confidence keys on the terminal tier + flags, never path tokens alone**: a result that shares its `tiers_run` shape with a higher-confidence path (e.g. an honest-empty `[0,1]` vs a verified gated-pass `[0,1]`) is given a distinguishing marker (`gate-skipped:scout-empty`) and its own confidence row, so "nothing found" can never read as high confidence (no-false-capability). (See `harpyja/orchestrator/gate.py`, the `gate-scoring-failed` / `gate-low-confidence` / `gate-skipped:scout-empty` flags, AC8/AC9.)
- When wrapping a foreign exception, preserve the cause (`raise ... from err`).
- No-silent-coverage lockstep: a capability's routing, its identity/cache slot, and
  its implementation ship in the **same change** — never route inputs to a capability
  ahead of the code that handles them. A routed-but-unimplemented input that parses
  to an empty result is a silent false claim ("we never looked" reading as "we looked
  and found nothing"), the same honesty violation as a silent empty result. Enforce
  with a lockstep invariant test where the two sides can drift (e.g.
  `classify.KNOWN_LANGUAGES == indexer.SYMBOL_LANGUAGES`, asserted in
  `index/test_routing.py`); until a slice ships, its inputs stay on the honest
  degraded path (null-language / ripgrep-only), never silent zero.

## Tests

- pytest. Test files are `test_*.py`, kept next to the package under test unless a top-level `tests/` root is added later (no test root configured yet).
- Cover the fallback paths explicitly: parser-missing → ripgrep, model-down → Tier 0, gate-fail → escalation.
- Drive async code from sync tests with `asyncio.run(...)` rather than adding an async-test plugin (no `pytest-asyncio` dependency). See `server/test_app.py`, `server/test_stdio_hygiene.py`.
- Keep tests network-free by injecting collaborators: pass a `resolver` to `assert_local` and a `which` to `run_doctor` instead of touching live DNS or `PATH`. Default to the real implementation, override in tests.
- Mark tests that spawn a real process or event loop with `@pytest.mark.integration` (declared in `pyproject.toml`) so they are skippable in constrained environments.

## Filesystem & artifacts

- Harpyja is read-only on **source** files. The manifest and symbol index are *derived artifacts* and are the only sanctioned writes: default to `<repo>/.harpyja/` with a self-ignoring `.gitignore` of `*` (never modify the repo's root `.gitignore`); fall back to `${XDG_CACHE_HOME:-~/.cache}/harpyja/<repo-hash>/` when the repo dir is unwritable.
- Durable artifact writes are atomic: write to a temp file **in the same directory** as the final file, then `os.replace`. The same-dir requirement is load-bearing — it keeps the rename atomic on one filesystem, including the external-cache fallback, so a crash can't leave a truncated artifact.
- Files that must be byte-reproducible (e.g. `manifest.jsonl`) are written with a fixed key order and a stable sort, so two runs over an unchanged tree diff cleanly.
- A derived artifact that is treated as **untrusted on read** must self-authenticate against its **own generation**, not just its producer. Pair the data file with a sidecar carrying (a) a content fingerprint — a sha256 over the data file's exact bytes plus a record count — and (b) the producer identity (engine + each grammar version). On read, rebuild from source whenever the data is missing/unreadable/truncated, the sidecar is missing/unreadable, the producer identity differs, or the fingerprint mismatches. Commit the multi-file pair **data-first, sidecar-last** (each via same-dir temp + `os.replace`) so a crash residue — fresh data under a stale sidecar — fails the fingerprint and rebuilds. The producer identity alone is not enough: it misses a same-engine clean-truncation and a crash residue; the fingerprint is what binds the sidecar to *this* generation. (See `symbols/symbols_io.py`, `symbols/engine_identity.py`.)
- The producer-identity cache key enumerates **one slot per external grammar/plugin entry point**, each with a real version or a `"missing"` / `"load-error:<abi>"` sentinel, via a slot→(dist, module, load-fn) map — not a flat per-package list. Entry points that ship in the **same package share one version and move together** (bump/absence is coupled) but keep distinct identity keys; install/bump of any slot invalidates the cache and triggers a rebuild that clears stale `grammar-missing` flags. (See `symbols/engine_identity.py` `_GRAMMAR_SLOTS`; `typescript` + `tsx` share `tree-sitter-typescript`.)
- Additive dataclass / record fields are appended **last** with a default, so a legacy on-disk artifact still reads and an unchanged tree stays byte-reproducible (the field is absent from old entries, defaulted on read). E.g. the manifest per-file `degraded` field and `CodeSpan.kind`.

## Measurement & eval harness

- A measurement/eval harness observes the system under test through its **real public
  seam** and never mutates its config or behavior — it measures, it does not modify.
  Drive the production entrypoint via injected collaborators (fakes for unit, the real
  `build_*` factories for integration through one stack object), and produce any
  configuration override with `dataclasses.replace`, never mutation
  (`test_sweep_does_not_mutate_settings`). (See `harpyja/eval/runner.py` `LocateStack`
  / `build_live_stack`, `harpyja/eval/sweep.py`.)
- Eval-only knobs live on a **dedicated config disjoint from the production frozen
  `Settings`** — a loop count, proximity window, N-floor, or scoring bar the SUT never
  reads must not bloat the production config (coupling smell with no uniformity
  benefit). Only fields the SUT genuinely consults (e.g. `verify_threshold` /
  `verify_top_n`) are ever overridden into it. Assert field-name disjointness
  (`test_eval_config_is_independent_of_settings`). (See `harpyja/eval/config.py`
  `EvalConfig`.)
- **One oracle defines correctness for every derived metric.** When several metrics
  share a notion of "right" (accuracy, catch-rate, false-escalation), route them all
  through a single function so a second definition cannot drift; assert the reuse
  (`test_gate_metrics_use_same_oracle_as_span_hit`). Scope each metric's denominator
  explicitly (e.g. gate metrics over the point-query subset only; the rate over all
  cases) and bake the scope into the function signature. (See `harpyja/eval/metrics.py`
  `_any_primary_overlap`.)
- An **undefined metric** (zero denominator) is an explicit `null` paired with its
  (zero) count field — never an omitted key and never a false `0.0`; "all metrics
  populated" is honored by a present null-with-count (the same honesty rule as a loud
  empty result). A measurement over too few samples **self-flags** (`indicative_only`)
  in its own report rather than relying on a post-hoc caveat. (See
  `harpyja/eval/metrics.py`, `harpyja/eval/report.py`.)
- A harness is **read-only on the target tree**: its artifacts write **outside** the
  indexed repo. The writer refuses (raises) when the output dir is inside or under
  `repo_path`, via the same atomic same-dir temp + `os.replace` as every durable write
  (mirrors the FastContext `trajectory_file`-outside-repo precedent). Report shapes are
  a **pinned, enumerated, version-stamped schema** with a loud validator, so consumers
  and tests branch on stable field names. (See `harpyja/eval/report.py`
  `atomic_write_json` / `validate_report`.)
- A tuning/calibration recommendation is **variance-gated and recommend-only**: it
  records a recommended value as data and does not flip a production default (the flip
  is a separate follow-up). It displaces an incumbent only when the advantage strictly
  exceeds the incumbent's run-to-run spread over K repeated runs
  (`mean(A) - mean(B) > pstdev(B)`); within noise the incumbent is recorded *validated*,
  not guessed — never a default flip on noise. (See `harpyja/eval/recommend.py`.)
- A **multi-target measurement driver** (one repo/worktree per case, vs a single
  shared tree) builds its **own** SUT collaborator stack **per case** and **pools** the
  per-case outcomes into the **unchanged** metrics/recommend layers + an
  additively-extended report — never forking a parallel metrics/scoring path. Artifacts
  still write **outside every** target tree (the same inside-`repo_path` refusal, per
  target). (See `harpyja/eval/swebench_eval.py` `run_swebench`, which builds a per-case
  `LocateStack` and reuses `metrics.py` / `recommend.py` unchanged.)
- Tier-internal **metadata the orchestrator must not see** (e.g. a per-run citation
  shape distribution) rides a **Scout-result side-channel**, not the cross-tier
  `list[CodeSpan]` seam: the engine exposes it as result metadata
  (`ScoutEngine.last_tally`, a `ScoutTally`), the harness **resets it per case** (so a
  prior case that never ran the tier can't leak a stale tally) and **reads the
  production run's** value, and the orchestrator's `list[CodeSpan]` is unchanged so
  callers still never branch on which engine ran. This is the one defined
  production→aggregation path for a per-shape count — never inferred from the surviving
  citations (which cannot show a *dropped* ref). (See `harpyja/scout/engine.py`
  `last_tally` / `ScoutTally`, `harpyja/eval/runner.py`, spec 0011 AC17.)
- When a versioned report schema gains **additive** fields, append them
  last-with-defaults AND **centralize the field set + its defaults in one anti-drift
  source** (a `_*_DEFAULTS` map the builder injects), so an older-shape block and a
  newer-shape block **both** pass the one loud validator and there is a single place a
  new field is declared. Bump `SCHEMA_VERSION`. (See `harpyja/eval/report.py`
  `_RUN_METADATA_DEFAULTS` / `_CASE_DEFAULTS` / `_AGGREGATE_DEFAULTS`, `_with_defaults`,
  `SCHEMA_VERSION` `0009-6a/1` → `0010/1`.)
- An **evaluation intervention** — injecting a non-production *input* through a
  sanctioned seam to make a behavior measurable (e.g. forcing routing via
  `LocateStack.classifier` so the gate fires), with **no** SUT code changed — must be
  **recorded loudly, never silently observed as production**: capture the production
  value **before** installing the override (so agreement never reads the injected
  value), record both the intervened and production labels per case, report an
  aggregate **agreement rate**, and keep the SUT-observed effect (`production_gate_ran`
  from `result.tiers_run`/`notes`) **distinct** from any harness-observed probe. A
  recommendation derived under intervention is **guarded by an agreement floor**: below
  it the result is flagged low-confidence / deltas-only — a relative ranking, never a
  calibration to flip a default on. (See `harpyja/eval/swebench_eval.py` D-route,
  `classifier_agreement_rate`, `AGREEMENT_FLOOR`, `production_gate_ran`.)

## Logging

- Use the standard `logging` module. Never log secrets, repo source content, or full file contents at info level. Keep stdout clean on the stdio MCP transport (logs go to stderr).
