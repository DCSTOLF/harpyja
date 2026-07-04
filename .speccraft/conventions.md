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
- When an already-churned return tuple would need to grow past ~4 elements but the extra
  payload is consumed by only **one** caller, prefer a **non-breaking out-param** (an
  optional `*_out: list[...] | None = None` the caller passes to collect the extra) over
  re-widening the tuple again and re-touching every unpacking site. This is a bounded,
  **recorded** smell — not a default — justified only by avoiding a second churn of
  callers updated in the same change. (See `harpyja/scout/normalize.py`
  `normalize_spans_with_tally` `recovered_paths_out`, spec 0012.)
- A routing/decision matrix is the **single source of truth**, *driven by* the routing code rather than duplicated by it. When dispatch depends on a small fixed product of dimensions, encode the full mapping in one table (e.g. `(mode × classification × index_ready) → planned ladder`) that both the executor and the tests read; the executor derives its branches **from** the table (a refactor that catches the executor re-deriving a routing rule is a real bug, not a style nit), and every row is asserted. Documented escalation/branch rules are *derived from* the table, never a second authority that can silently drift. (See `harpyja/orchestrator/matrix.py` `plan_ladder`, consulted by `_locate_auto`; AC3.)

## Config & immutable state

- Config is a frozen dataclass (`Settings`). Produce overrides with `dataclasses.replace`, never mutation — every override returns a new instance.
- Layer precedence is explicit and one-directional: defaults < `harpyja.toml` < `HARPYJA_*` env < per-request override. `harpyja.toml` keys mirror `Settings` field names; values are coerced to the field's declared type.
- A `Settings` default that names an **external resource** (a model tag, an endpoint) must name one that is actually **served/reachable by the documented backend** — an unserved default is an **infrastructure defect, not a config preference** (no-false-capability applied to config values: a default that 404s on every call degrades every out-of-box run for a non-model reason). Pin it with a **field-default introspection** drift guard — assert over `dataclasses.fields(Settings)` / resolved `Settings()` values that no field default equals a known-unserved/placeholder tag — **never a source grep** (which trips false positives on docstrings, comments, and historical fixtures). Where the served set is instance-relative (e.g. a local Ollama), an env-gated skip-not-fail integration test does a **positive** membership check (`/api/tags`) so it cannot pass trivially when the endpoint is down. (See `harpyja/config/settings.py` `scout_model` / `lm_model`, `test_settings_defaults_drop_unserved_tags`, `test_scout_model_default_present_in_ollama_served_set`, spec 0016 AC1/AC2/AC6/AC7.)
- When **one `Settings` value is consumed by two subsystems** (e.g. `scout_model` backs BOTH Scout-tier retrieval AND — via `verify_method="scout_model"` — the Verification Gate's scoring model; as of spec 0018 the gate judge default moved to `lm_model`, so `scout_model`'s gate role is now the retained non-default A/B baseline and the live dual-consumer is `lm_model`, backing BOTH Deep (Tier 2) AND the gate judge), a spec that changes that value must **state the cross-subsystem coupling explicitly** and keep it distinct from any adjacent-but-separate change: flipping the value is *plumbing* (which served model both call), NOT a change to how either subsystem behaves — conflating the two would let a value swap read as a logic change. A **canonical CLI flag with a deprecated alias** reconciles at the **application layer** on **distinct argparse dests** (`deep = args.deep_model or args.lm_model`), so the canonical flag wins **regardless of CLI order** — never via argparse positional last-wins on a shared dest. (See `harpyja/eval/swebench_eval.py` `_settings_from_args` / `_add_model_flags`, `--deep-model` canonical / `--lm-model` deprecated, spec 0016 D1/D2.)
- A finite/safe default that **guards an invariant** must live on the **constructed object's own field default**, not only on the config layer that feeds it — otherwise a construction that bypasses the config (a test, an unwired call site, a direct instantiation) falls back to the *unguarded* value (`None`, unbounded) and the invariant silently does not hold at that site. Put the floor where the object is built: `ModelGateway.timeout_s: float = 120.0` is finite at the **dataclass default itself**, so *any* `ModelGateway(...)` is hang-bounded out of the box, with `Settings.lm_http_timeout_s` merely feeding the wired sites (a Settings-only default would leave direct constructions unbounded). Pin the object-level default with a **field-default introspection** test independent of `Settings` (the same drift-guard discipline as the served-tag default — never a source grep). (See `harpyja/gateway/gateway.py` `ModelGateway.timeout_s`, `test_gateway.py` dataclass-default-finite, spec 0017 AC1/AC2/D3.)

## Errors & failure posture

- Prefer graceful degradation over raising (see guardrails.md): fall back a tier and attach a confidence flag rather than hard-failing a `locate`.
- Graceful degradation has a floor: when a *hard precondition* for a tier is absent and there is no honest degraded answer to give, fail loudly with a typed, actionable error naming the missing dependency — never a silent empty result that reads as "nothing found." (e.g. `rg` missing → `RipgrepMissingError` on search/locate, surfaced by `doctor`; `index` does not require `rg` and still succeeds.) The same honesty rule means distinct failure causes get distinct caller-visible notes, never one collapsed empty result (e.g. unrecognized `language_hint` vs null-language exclusion).
- **Every outbound or otherwise-blocking call carries a finite timeout** — no unbounded `urlopen`/socket connect-or-read, no `timeout=None`. "Always degrade gracefully" is only *structurally possible* if the call can **raise**: a call that can hang forever can never degrade, so an un-timed-out blocking op silently defeats every downstream `try/except` degrade path (the B3 pathology — a stalled/torn-down local endpoint wedged the whole run at 0% CPU because `urlopen(req)` raised nothing and just blocked). The fix is to **make the un-raisable raisable, not to add a new degrade branch**: a finite `urlopen(req, timeout=…)` lets the *existing* best-effort catch fire (here the Verification Gate's `except Exception → GateOutcome(failed=True)`, which never fired until the call could raise). Be honest about what the bound is (no-false-capability): `urlopen(timeout=)` is a **per-socket-op** timeout (connect + each blocking read), **not** a total-request deadline — claim only that; a dribble-slow endpoint can still outlast it (a total-deadline wrapper is a possible follow-up, not the same bound). (See `harpyja/gateway/gateway.py` `_default_transport(..., timeout_s)` → `urlopen(req, timeout=timeout_s)`, spec 0017 AC3/AC7.)
- Caller-visible degrade/failure markers are **stable machine-readable identifiers**, not free prose, so callers and tests branch on the identifier rather than the wording. A cause taxonomy is an enumerated, stable set with a composable suffix that keeps otherwise-collapsible states distinct — e.g. Scout emits `scout-degraded:{connection-refused|no-endpoint-configured|backend-error}` with a `+no-matches` suffix that distinguishes "Tier-0 honestly empty" from "Tier-0 had results." (See `harpyja/scout/errors.py`, `harpyja/orchestrator/locate.py`.)
- The air-gap is enforced in **one** place only: reuse `gateway.assert_local` / `AirGapError` — never introduce a parallel air-gap error type or a second check. A new outbound path (e.g. `ModelGateway.complete()`) asserts loopback on **resolved** addresses *before* any I/O leaves the process; a non-loopback endpoint is a loud floor error, never a degrade note.
- A **preflight/doctor probe asserts a precondition at SETUP, loudly — never mid-run discovery** — and routes through the **single sanctioned seam**, adding no parallel path: `gateway.assert_local` runs FIRST (the probe's own read, e.g. `/api/tags`, is the same loopback-gated egress class as the calls it is checking, so it introduces no second outbound path), then the membership/precondition check raises a typed error **naming** the missing dependency. It claims only what it actually verified (no-false-capability): the model-presence probe asserts models are **"pulled"**, NOT co-resident-loadable, and explicitly names the un-probed failure (OOM under co-load) as a **residual risk** a later cheap check catches — never a co-residence guarantee it did not test. (See `harpyja/eval/swebench_eval.py` `preflight_models_present` / `PreflightError` / `cmd_preflight`, spec 0019 AC1/AC2/D4.)
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
- A **recovery/repair of a malformed-but-recoverable input keeps only an existing,
  unique, anchored target — never a guessed rewrite — and composes with, never
  bypasses, the prior validation it sits in front of.** When a model fabricates a
  leading root onto an otherwise-real path, recover by the **longest unique** `≥2`-segment
  suffix that matches the indexed manifest set (segment-aligned: `p == tail` or `p` ends
  with `"/" + tail`), guarded by (a) a specificity floor (`MIN_TAIL_SEGMENTS=2`, never a
  bare basename), (b) **exactly-one** match at the longest length — ambiguous (>1) →
  honest **drop**, never a silent pick and never a fall-back to a shorter, less specific
  tail — and (c) a **manifest-keyed leading-segment anchor** (the matched *tail's head*
  must be a known top-level manifest entry, rejecting a fabricated mid-tree suffix). The
  recovered target re-enters the **same** downstream gates as a non-recovered one
  (repo-confine + `is_file` + clamp) and inherits the same honesty floor
  (`gate-skipped:no-line-range`), so a recovered keep can never read more confidently —
  load-bearing because a wrong-but-existing un-gated keep would be strictly worse than
  the honest drop it replaces. An **empty/absent** match set ⇒ **no recovery** (graceful
  degrade to the prior drop); recovery only ever *adds* keeps. (See
  `harpyja/scout/normalize.py` `_recover_suffix` / `MIN_TAIL_SEGMENTS`, spec 0012
  AC1/AC2/AC3.)
- A best-effort verification/scoring step **never raises and never silently passes**: it maps **any** internal failure (a judge call erroring, an un-readable input) to a typed *could-not-vouch* outcome (`GateOutcome.failed=True`, `passed=False`) and routes it exactly like a negative verdict — escalate where a further tier remains (retaining a stable diagnostic flag, e.g. `gate-scoring-failed`), else return the best-effort current-tier result tagged with that same flag. A could-not-vouch is never a hard block and never an unflagged pass. Relatedly, **derived confidence keys on the terminal tier + flags, never path tokens alone**: a result that shares its `tiers_run` shape with a higher-confidence path (e.g. an honest-empty `[0,1]` vs a verified gated-pass `[0,1]`) is given a distinguishing marker (`gate-skipped:scout-empty`) and its own confidence row, so "nothing found" can never read as high confidence (no-false-capability). (See `harpyja/orchestrator/gate.py`, the `gate-scoring-failed` / `gate-low-confidence` / `gate-skipped:scout-empty` flags, AC8/AC9.)
- A best-effort scorer/judge **degrades on a non-conforming reply — it never fabricates a
  value from noise.** When a step extracts a decision from untrusted model output, an
  *extractable-but-untrustworthy* reply (a number that IS present but is a line number, an
  out-of-range value, or a leading digit inside prose) must be treated as **could-not-vouch**,
  not mined for a value. Parse **strictly** (anchored, single-match, range-checked → `float |
  None`, not "grab the first number and clamp"), and on `None` raise a typed error the existing
  degrade catch turns into a floor — prefer **degrade-and-escalate over reject** on ambiguity
  (the 0015 harm was false *rejection*: a line number clamped to a fabricated `1.0` pass, prose
  misread as a `0.0` reject). Fold the range check and the malformed check into **one rule**
  where possible (an out-of-range number and a line number are both non-conforming). When the
  strict parser is shared by more than one caller, every caller inherits the degrade and each
  gets its own assertion (the type-shape-change blast-radius rule). (See
  `harpyja/orchestrator/gate.py` `_parse_score` / `_score_or_raise` / `ScoreParseError`, shared
  by `make_instruct_judge` + `make_scout_model_judge`, spec 0018 D2/D6/AC5/AC13.)
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
- A calibration recommender **refuses to tune a parameter over an instrument it has
  measured to be unreliable** — it emits a typed *confound* null rather than a value fit
  over a broken upstream signal. When the recommender's own quality metric (e.g. the gate's
  measured false-escalation rate) exceeds a named ceiling, it returns a stable
  `gate-confounded`-class outcome carrying the measured rate, distinct from both a real pick
  and the other typed nulls (`not-separable` / `degraded-dominated`) — because a threshold
  tuned over a judge that rejects correct citations would calibrate a still-broken gate. The
  ceiling is an **eval-only** knob (field-disjoint from `Settings`), boundary-strict
  (`> ceiling`, `== ceiling` is not confounded), and an **unmeasured** signal (`None`) defers
  to the normal recommender rather than tripping the confound. The confound branch is a
  DISPATCHER wrapping the unchanged clean recommender, not a rewrite of it. An honest confound
  flag beats a number fit over a broken instrument. (See `harpyja/eval/recommend.py`
  `recommend_oq2` / `gate_confounded_recommendation` / `OUTCOME_GATE_CONFOUNDED`,
  `EvalConfig.gate_false_escalation_ceiling`, spec 0019 D2/AC9.)
- A harness **mechanism must be wired into the real run path, not left dormant** — a
  wired-but-dormant branch (built, unit-tested, but never reached by the production driver)
  makes its acceptance criterion aspirational. When a plan scopes only the scaffolding but
  the runner would still call the pre-change code, wire the new dispatcher/outcome into the
  runner (staying within the frozen-SUT / additively-extensible-harness boundary) and TDD it
  at the runner seam — and record the plan under-scope as a deviation, not a silent fix.
  (See `harpyja/eval/swebench_eval.py` `run_swebench_sweep` calling `recommend_oq2`, spec 0019
  T11 deviation.)
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
- **Every typed-degrade floor reports its rate as a first-class aggregate field AND
  feeds `degraded_dominated`** — or it can go dark exactly the way Scout's
  `format_citations` crash did (a graceful floor hides the defect it floors on). When a
  tier/backend gains a typed-unavailable degrade (a stable `<tier>-degraded:<cause>`
  note), the eval report MUST surface a paired `<tier>_degrade_count` / `<tier>_degrade_rate`
  twin (additive, last-with-defaults, **null-with-count on a zero denominator**, never a
  false `0.0`), and the case MUST join the `degraded_dominated` reckoning. Dominance keys
  off the **UNION** of all tiers' per-case degrades — a case counts **ONCE** even when
  multiple tiers floor in it (a sum would double-count) — while each per-tier rate stays a
  separate first-class field for attribution. This generalizes the spec-0011 Scout
  machinery: Deep's `deep_degrade_*` twins (spec 0014) are one *instance* of the rule, not
  the rule itself, so the next floor inherits visibility by default instead of
  re-litigating it. (See `harpyja/eval/runner.py` `_has_degrade_note` /
  `_is_scout_degraded` / `_is_deep_degraded` + the union-based `degraded_dominated` in
  `aggregate_outcomes`, `harpyja/eval/report.py` `scout_degrade_*` / `deep_degrade_*`,
  spec 0014 AC6/AC11.)
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
- A new taxonomy/outcome **label is a projection layer ABOVE a byte-frozen dispatcher,
  never a widening of it** — measurement-not-construction in the type. When a
  measurement needs richer outcomes than the SUT's own frozen dispatcher emits, add a
  **pure projection** that maps the byte-unchanged dispatcher result (+ the harness
  aggregate) down to the extended label set, in a **separate module**, so the file that
  must never be perturbed is not touched (and can be golden-locked). Encode any
  precedence as a **total order over overlapping (non-partition) conditions**, record
  **all** true conditions (not only the winner), and compute a condition **only when its
  input actually ran** (e.g. a no-survivor signal only when the sweep executed, never
  under a short-circuit) so a phantom label is never booked alongside the one that
  short-circuited it. Prove the extended labels' discriminators are reachable on the
  frozen result **without editing the dispatcher** (a field-reachability lock) and pin
  the dispatcher with a **behavior snapshot**, not a source grep. (See
  `harpyja/eval/oq2_classify.py` `classify_g3_outcome` above the frozen
  `recommend_oq2` / `rank_sweep`, `test_recommend.py` P1/P2 locks, spec 0020 D1/D3/AC6.)
- A **measurement spec closes on a recorded, SUT-observing typed outcome that names the
  next spec — skip-not-fail is never a close**, and a typed null (including an
  *unmeasurable* / DEFERRED metric with a zero-count denominator) is a **complete, valid
  deliverable**, never a forced pick to manufacture a clean-looking number. Draw the
  **close-vs-hold boundary BY CAUSE, not by which stage stopped**: an outcome that
  actually observed the SUT (a completed-then-failed finding, or a produced label) is a
  **close**; an environment failure (a missing dependency, absent fixtures, OOM /
  resource exhaustion under co-load) is a **BLOCKED hold** that names the exact fix — so
  a resource failure can never masquerade as a SUT finding. Emit a durable, loudly
  validated **ledger** artifact (its own pinned, version-stamped schema, distinct from
  the sweep report; reuse the one atomic outside-repo writer) recording each stage's
  verdict + measured sub-values + the close/hold cause + run provenance, so a STOP /
  BLOCKED verdict is reproducible. (See `harpyja/eval/oq2_protocol.py`
  `run_oq2_protocol`, `harpyja/eval/oq2_ledger.py` `LEDGER_SCHEMA_VERSION` `"0020/1"`,
  spec 0020 D7/D8/AC2/AC11/AC12.)
- Before reporting a **null / undefined measurement, verify the null is real — not a
  harness artifact** — by spot-checking the oracle, the fixtures, and the SUT
  invocation directly, and separate a genuine **upstream** limit from a measurement bug
  before naming a follow-up. A metric that is `null` because its denominator is
  legitimately zero (e.g. a judge's false-*rejection* rate is undefined when the finder
  emits zero correct citations to reject) is an honest deliverable ONLY once the zero
  denominator is confirmed to reflect the SUT and not a loading/scoring defect — and the
  follow-up it names must target the **actual** upstream blocker (here: finder locate
  accuracy), not the downstream metric that merely went undefined (gate calibration).
  Cross-check with an independent A/B where feasible (a second model reproducing the same
  failure argues task difficulty, not model quality). (See spec 0020's G2 DEFERRED
  root-cause verification: `correct_tier1_count = 0` confirmed via direct Tier-1
  spot-checks + a `qwen3:4b-instruct` A/B, not accepted at face value.)

## Logging

- Use the standard `logging` module. Never log secrets, repo source content, or full file contents at info level. Keep stdout clean on the stdio MCP transport (logs go to stderr).
- A typed-degrade's **visibility** requirement can be satisfied by a **distinct log signal** when a schema field is not (yet) warranted. When a new failure *cause* degrades through an **existing** generic catch and a structured cause-field would be premature, branch the log so the cause is **named, not swallowed anonymously**: the Verification Gate's timeout degrade emits a distinct timeout-naming WARNING (`isinstance(err, (TimeoutError, socket.timeout, URLError))`), separable from the generic "scoring failed", with **no** `GateOutcome` schema change. This is the lightweight tier of the 0014 typed-degrade visibility convention — a *log-level* distinction — reserved for causes the eval harness need not count; a first-class aggregate/`<tier>_degrade_rate` schema field remains the heavyweight tier for degrades that must be measured. (See `harpyja/orchestrator/gate.py`, spec 0017 D4/AC6.) A degrade `except` that branches by `isinstance` to name distinct causes is now a **multi-cause** pattern (spec 0017 timeout WARNING + spec 0018 `ScoreParseError` non-conformance WARNING, each exactly one message, no double-emit). **Ordering is load-bearing: a typed cause that is a SUBCLASS of another caught/branched type MUST be isinstance-checked FIRST** — `ScoreParseError ⊂ ValueError`, so `verify`'s `except` tests it before the generic branch; otherwise the supertype branch catches it, it degrades under the wrong name, and the diagnostic contract (one distinct, correctly-named WARNING) silently breaks. Assert the generic message is **absent** for the typed cause (on the log *record* message, never `caplog.text`). (See `harpyja/orchestrator/gate.py` `verify` except-branch order, spec 0018 D4/AC7.)
