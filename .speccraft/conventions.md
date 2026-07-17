# Conventions

## Naming

- Modules/functions/variables: `snake_case`. Classes: `PascalCase`. Constants: `UPPER_SNAKE_CASE`.
- Test functions: `test_<subject>_<scenario>`. <!-- enforce: regex pattern="^def test_[a-z0-9]+\(" scope="harpyja/" -->
  (Enforce-tag semantics: speccraft-drift treats a pattern MATCH as a VIOLATION, so the
  pattern must match BAD code — here a single-segment `def test_foo(` missing the
  `_<scenario>` part. Scope uses the tool's directory-prefix form (`harpyja/`) because
  its globber (`filepath.Match`) has no `**` recursion; RE2 has no lookahead.)

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
- A **generation-control knob is scoped to ONE tier by construction — an `explorer_`-prefixed
  `Settings` field name PLUS a single call site — never a callee-level default on the shared
  `ModelGateway`, which would leak to the other tier.** When a per-call parameter (a
  `max_tokens` cap, a `chat_template_kwargs.enable_thinking` flag) must bound the explorer tier
  but NOT Deep, name it `explorer_*` and pass it ONLY from the explorer's `_default_model_call`;
  keep the shared `ModelGateway` **purely param-driven with NO default of its own** for that
  field, so the Deep-tier path (which calls the gateway without the `explorer_*` param) is never
  affected. Enforce the boundary with an **outbound-field guard test** that asserts the OTHER
  tier's actual outbound request carries NEITHER knob (asserting on the real request fields, not
  the mere absence of the `explorer_*` Settings names) — it passes on introduction and ROTS
  FALSE on any future leak. Scope by field naming + call site, not by a prose promise. (Note the
  deliberate contrast with the invariant-guarding DRIFT-GUARD above: the cap DOES get an
  object-level default on the *explorer-owned* object (`ExplorerBackend.max_tokens = 2048`) so a
  Settings-bypassing explorer construction is still bounded, but the *shared* `ModelGateway`
  gets none, so Deep stays uncapped — the guard lives on the tier-owned object, never the shared
  one.) (See `harpyja/scout/explorer_backend.py` `_default_model_call`, `Settings.explorer_max_tokens`
  / `explorer_enable_thinking`, `harpyja/deep/test_rlm.py` outbound-field guard, spec 0028 AC2/AC8.)

## Errors & failure posture

- Prefer graceful degradation over raising (see guardrails.md): fall back a tier and attach a confidence flag rather than hard-failing a `locate`.
- Graceful degradation has a floor: when a *hard precondition* for a tier is absent and there is no honest degraded answer to give, fail loudly with a typed, actionable error naming the missing dependency — never a silent empty result that reads as "nothing found." (e.g. `rg` missing → `RipgrepMissingError` on search/locate, surfaced by `doctor`; `index` does not require `rg` and still succeeds.) The same honesty rule means distinct failure causes get distinct caller-visible notes, never one collapsed empty result (e.g. unrecognized `language_hint` vs null-language exclusion).
- **Every outbound or otherwise-blocking call carries a finite timeout** — no unbounded `urlopen`/socket connect-or-read, no `timeout=None`. "Always degrade gracefully" is only *structurally possible* if the call can **raise**: a call that can hang forever can never degrade, so an un-timed-out blocking op silently defeats every downstream `try/except` degrade path (the B3 pathology — a stalled/torn-down local endpoint wedged the whole run at 0% CPU because `urlopen(req)` raised nothing and just blocked). The fix is to **make the un-raisable raisable, not to add a new degrade branch**: a finite `urlopen(req, timeout=…)` lets the *existing* best-effort catch fire (here the Verification Gate's `except Exception → GateOutcome(failed=True)`, which never fired until the call could raise). Be honest about what the bound is (no-false-capability): `urlopen(timeout=)` is a **per-socket-op** timeout (connect + each blocking read), **not** a total-request deadline — claim only that; a dribble-slow endpoint can still outlast it (a total-deadline wrapper is a possible follow-up, not the same bound). (See `harpyja/gateway/gateway.py` `_default_transport(..., timeout_s)` → `urlopen(req, timeout=timeout_s)`, spec 0017 AC3/AC7.)
- An **UNSEARCHABLE tool scope (nonexistent path) is a typed, model/RLM-visible, NON-TERMINAL marker — never a silent `[]` that reads as "searched, nothing found," and never routed through the 0029 execution-error degrade** (spec 0035). The wrappers return a bare marker STRING (`grep-scope-not-found: '<scope>'` / `ls-path-not-found: '<path>'` / `search-scope-not-found: '<scope>'`, `<id>: '<scope>'` shape per the cause-taxonomy rule) BEFORE delegating to the engine — ordering is load-bearing: a nonexistent cwd crashes the engine's subprocess (`FileNotFoundError`, the uncaught-crash defect this replaced in Deep's `search`). The marker-return route (not an exception) is deliberate twice over: the 0029 catch would stamp a composite `tool-call-degraded:execution-error:` prefix that mislabels a navigation mistake AND its degrade path returns before `note_navigation`, silently defeating loop detection on repeated bad scopes; the marker string needs ZERO loop changes (`_spans_of` yields no spans, `session.add` stringifies it model-visibly, `note_navigation` still runs). The split is three-way and each state stays distinct: searchable-but-empty → plain `[]` (honest-empty, never blurred); unsearchable → marker; existing FILE scope → DELEGATES to the engine (post-0033 the one `RipgrepEngine` searches files for real — explorer `grep` == Deep `search` == one engine contract; the wrapper `is_dir()` redirect guard is DELETED, and `ls`-on-a-file keeps `[]` because "list children" of a file is honestly empty). `confine_path`'s NON-STRICT resolve (a nonexistent in-repo path passes confinement) is pinned by its own fixture — the marker branches depend on the wrapper's `exists()` guard, not confinement, detecting absence. (See `harpyja/scout/explorer_tools.py` `grep`/`ls`, `harpyja/deep/host_tools.py` `search`, `harpyja/server/test_tools.py`, spec 0035 AC1–AC5.) **Spec 0042 (AC2) extends the marker convention with a SECOND, distinct case: the successful-but-degraded ANNOTATION.** The 0035 case above is a REPLACEMENT (a bare marker string IS the whole result — no spans exist for an unsearchable scope). A degraded-but-successful result (real spans obtained via a fallback, e.g. the `symbols` ripgrep fallback on a parse-degraded file) instead PREPENDS the stable marker to the span list — `[f"symbols-degraded: '<path>'", *CodeSpans]`, marker FIRST, same `<id>: '<scope>'` cause-taxonomy shape. The two cases stay mechanically distinct: replacement = bare `str` result (zero spans by construction); annotation = `list[str | CodeSpan]` whose `str` element is skipped by `_spans_of` (never counted as a span) while the REAL spans enter seen-span/loop-detection accounting, and `session.add`'s stringification keeps the marker model-visible (0030's never-a-silent-downgrade contract). Rationale: the pre-0042 `symbols` nested dict `{"symbols": [...], "degraded": bool}` was the ONLY nav-tool result `_spans_of` could not unwrap — zero spans registered, so every repeat read as unproductive and the tool was structurally penalized for being called (the 0040 0/28-adoption defect). (See `harpyja/scout/explorer_tools.py` `symbols`, `test_explorer_loop.py` spec-0042 pins, spec 0042 AC2.)
- **A tool-routing branch keyed on an OPTIONAL arg treats an empty string as ABSENT (`not path`, never `is None`) — a small tool-calling model emits `""` for an omitted arg, not omission.** When one tool multiplexes modes on the presence of an optional parameter (e.g. `symbols(path=…, name=…)`: with `path` → file-local, `name` only → repo-wide), an `is None` presence check is DEFEATABLE by a model that sends `{"path": "", "name": "…"}` — the empty path reads as present, routes file-local, and silently ignores the `name`, so the repo-wide affordance the routing exists to reach is never taken. This was observed LIVE (a 0042 astropy cell): route on truthiness (`if not path:`), and where an empty-everything call is itself meaningless, return the typed args-missing marker rather than a silent empty result. The rule is the honest-empty discipline applied to arg parsing — a falsy optional is the model omitting it, and a routing decision must not read "omitted" as "provided-and-empty." (See `harpyja/scout/explorer_tools.py` `symbols` `if not path`, `test_symbols_empty_string_path_routes_repo_wide_not_file_local`, spec 0042 post-T12 fix.)
- Caller-visible degrade/failure markers are **stable machine-readable identifiers**, not free prose, so callers and tests branch on the identifier rather than the wording. A cause taxonomy is an enumerated, stable set with a composable suffix that keeps otherwise-collapsible states distinct — e.g. Scout emits `scout-degraded:{connection-refused|no-endpoint-configured|backend-error}` with a `+no-matches` suffix that distinguishes "Tier-0 honestly empty" from "Tier-0 had results." (See `harpyja/scout/errors.py`, `harpyja/orchestrator/locate.py`.)
- A **model-call tool-calling RETURN CONTRACT surfaces the generation `finish_reason`
  ADDITIVELY — from the CHOICE, not the message — because a downstream degrade cannot be
  TYPED without it.** When a loop must discriminate a truncated turn from a clean one, the
  gateway's `complete_with_tools` returns `finish_reason` alongside the existing
  `{content, tool_calls}` (backward-additive, existing keys unchanged), read from
  `choices[0].finish_reason` (the choice-level field — NOT `choices[0].message`), `str`-cast
  when present and defaulting to the exact sentinel string **`"unknown"`** when absent, pinned
  by a unit test covering both a present value AND the absent-default. This is the load-bearing
  enabler for truncation-vs-clean discrimination: without the surfaced field the truncated-turn
  degrade below is untestable and an implementer is forced into brittle log/transport scraping.
  (See `harpyja/gateway/gateway.py` `complete_with_tools`, `test_gateway.py`, spec 0028 AC0.)
- A **`finish_reason == "length"` turn is a typed degrade REGARDLESS of whether a syntactically
  valid `tool_call` rode along — a truncated turn never takes the success path.** A
  length-truncated response was cut off mid-generation, so its tool-call args may be silently
  incomplete; accepting a parseable-but-truncated call would mask cap pressure (the model quietly
  losing turns to a too-small cap). Emit the stable cause `scout-degraded:generation-truncated`
  (an identifier per the cause-taxonomy rule) — checked right after the model call, before any
  tool dispatch — never a silently-swallowed empty turn and never a success even when a valid
  tool_call is present. It is a DISTINCT native terminal cause with its OWN per-cause count
  (`scout_degrade_generation_truncated_count`, additive, `SCHEMA_VERSION` bumped), counted
  separately from `model_unreachable` etc. (See `harpyja/scout/explorer_loop.py`
  `GENERATION_TRUNCATED`, `harpyja/scout/errors.py`, `harpyja/eval/runner.py`, spec 0028 AC3.)
- The air-gap is enforced in **one** place only: reuse `gateway.assert_local` / `AirGapError` — never introduce a parallel air-gap error type or a second check. A new outbound path (e.g. `ModelGateway.complete()`) asserts loopback on **resolved** addresses *before* any I/O leaves the process; a non-loopback endpoint is a loud floor error, never a degrade note.
- A **preflight/doctor probe asserts a precondition at SETUP, loudly — never mid-run discovery** — and routes through the **single sanctioned seam**, adding no parallel path: `gateway.assert_local` runs FIRST (the probe's own read, e.g. `/api/tags`, is the same loopback-gated egress class as the calls it is checking, so it introduces no second outbound path), then the membership/precondition check raises a typed error **naming** the missing dependency. It claims only what it actually verified (no-false-capability): the model-presence probe asserts models are **"pulled"**, NOT co-resident-loadable, and explicitly names the un-probed failure (OOM under co-load) as a **residual risk** a later cheap check catches — never a co-residence guarantee it did not test. (See `harpyja/eval/swebench_eval.py` `preflight_models_present` / `PreflightError` / `cmd_preflight`, spec 0019 AC1/AC2/D4.)
- Third-party in-process code that can open its own socket is an **assumption verified by test**, never an asserted air-gap guarantee. The air-gap is enforced only at the Gateway; everything Harpyja *hands* such code is constrained to an exact positive-equality whitelist (no raw `base_url`, no env-derived endpoint, no HTTP client), and the residual in-process egress risk is backed by a network-deny integration test plus a tracked sandbox follow-up — recorded, not buried (no false-capability claim). (See `harpyja/scout/tools.py`, AC10/AC11.)
- An untrusted, in-process code-**writing** loop is bounded in a **layered** way at different seams — no single ignorable counter is load-bearing. Externally-enforced counters the loop cannot evade (host-tool wrappers stop dispatching; the Gateway refuses further completions) plus a **wall-clock hard-kill via an out-of-band, host-terminable subprocess** are the load-bearing guarantees — a same-thread/event-loop deadline can never preempt a synchronous WASM busy loop, so enforcement is by hard termination, never cooperative cancellation. Internal control-flow bounds (recursion depth / sub-query fan-out) are host-mediated where the runtime exposes a spawn/recurse hook, else **recorded as residual risk** and **transitively contained** by the external counters (every sub-query spends tool-calls, tokens, and wall-clock). A bound the third party can ignore is not a bound. (See `harpyja/deep/runner.py`, `harpyja/deep/budget.py`, AC10/AC10a.)
- A budget/quality **truncation** is a distinct, caller-visible, **stable non-degrade marker** (`deep-truncated:<bound>`, one of `depth`/`subqueries`/`tool-calls`/`tokens`/`wall-clock`) — never silently indistinguishable from a complete result, and never a tier-degrade (dropping a tier on a *successful but truncated* run would be the ungated escalation a verification gate is meant to govern). Distinct from both a complete run and a typed `DeepUnavailable` degrade. (See `harpyja/orchestrator/locate.py`, `harpyja/deep/engine.py`.)
- When a third-party tier owns its **own** model client and cannot be routed through the in-house Gateway, enforce the air-gap by calling `gateway.assert_local` on the configured endpoint **before** constructing that client, and **prove** no non-loopback egress with a network-deny integration test — assumption-verified-by-test, not an asserted guarantee. Still **one** air-gap helper, never a parallel check. (See `harpyja/deep/rlm.py`, AC6/AC12.) When that third party is **env-configured** (reads its endpoint/model from `os.environ`, with no constructor/config-file seam — verify against the pinned source) and must be bridged off the request loop, inject its env **only while holding a module-level `threading.Lock`** — *not* an `asyncio.Lock`: each call runs the awaitable on its **own loop-free worker thread** (`asyncio.run` is illegal inside a running loop, so a worker thread keeps the sync seam intact), so concurrent calls land on different OS threads and only a thread lock serializes their `os.environ` writes. Hold the lock across `assert_local` → env-set → construct → the **full** off-loop run when any config key is read lazily per model call (closes the TOCTOU window). The env guard is **set-then-restore** in `try/finally` preserving per-key **unset-vs-empty** (a key absent before is `del`-eted after; a `""` is restored to `""`). This serializes the tier — accept it only where calls already contend for one resource (e.g. a single local GPU), and confine the latitude to that tier (never leak it to a sibling that keeps "config from `Settings`, not ambient env"). The fallback subprocess path scopes env to the **child** via `subprocess env=`, never mutating the parent. (See `harpyja/scout/client.py` `_SCOUT_ENV_LOCK` / `_managed_fc_env` / `_run_coro_on_worker_thread`, AC3/AC4.)
- A **model-driven navigation loop's tool suite is a set of `confine_path`-guarded, Settings-bounded, READ-ONLY closures built by ONE factory mirroring `deep/host_tools.build_host_tools`** — the driving model is an untrusted caller of the tools (same posture as the RLM host tools), so every tool is repo-path-confined, output-bounded from the existing `Settings` clamps, and has no shell/write/terminal access. The tool COUNT is asserted exactly (`build_explorer_tools` returns EXACTLY `{grep, glob, read_span, ls, symbols}` — **amended from three to four in spec 0027**: `ls` is the on-demand single-directory layout-discovery affordance `glob` lacks, added deliberately when the eager whole-repo context map was removed, push → pull; **amended from four to five in spec 0030**: `symbols` is the file-local symbol index tool (functions/classes/types and their line spans), Tier-0 file-local extraction reused, adding span-precision affordance when the model has navigated to the right file; both are RECONCILED, rationale-carrying changes — updated in the same commit as both hard-count tests — NOT the silent weak-model tool creep the exact-count guard exists to catch), so a weak model can never motivate silent tool-suite creep — a weak-model result is a finding, not a bug. Any ripgrep-backed tool shares ONE bounded `RipgrepEngine` with the Deep `search` host tool (single source of truth for bounds and repo-confinement — never a second, subtly-different grep surface); each tool returns the shared `CodeSpan`/text shape (a path-listing tool normalizes to file-level `CodeSpan` records, not raw strings). A pre-model context map's vendor/test/generated exclusion is a DISPLAY concern ONLY: it filters the rendered map, never the tool search scope (an excluded test/vendor file stays reachable via the tools — map-filter ≠ tool-scope filter), because a test can be the real localization target. (See `harpyja/scout/explorer_tools.py` `build_explorer_tools` + `harpyja/scout/context_map.py`, mirroring `harpyja/deep/host_tools.py`, spec 0024 AC2/AC3.)
- A **model-driven navigation/exploration loop discovers repo structure ON DEMAND through
  tools it chooses to call — never via an eager whole-repo dump injected into the prompt
  (push → pull).** An up-front whole-repo listing is a repo-size-dependent per-turn bloat
  that a general model re-prefills every turn; past a point it pushes the model into a
  generation that outlasts the per-call timeout, and the loop's own degrade floor then
  converts that timeout into a phantom "nothing found." REMOVE it entirely (full removal,
  not a smaller tree — shrinkage leaves a "how much did I leave in?" confound inside the
  very fix meant to remove one), keep the initial prompt a small constant (task/query +
  tool framing), and give the model a cheap layout-discovery tool (`ls`, single-directory)
  so it walks down on demand. Measured: astropy's turn-1 payload dropped ~10,181 → ~60
  tokens (~170×), repo-size-independent — asserted at the BACKEND level (a small AND a
  large synthetic manifest, both clearing the bound, byte-identical because no manifest
  term survives), since the map is built in the backend, not the loop. (See
  `harpyja/scout/context_map.py` `build_initial_prompt` replacing the retired-from-live
  `build_context_map`, `harpyja/scout/explorer_backend.py` `_run_loop`, spec 0027 AC1/AC2.)
- A **bounded loop's "why did it end" is the TYPED cause/outcome, never a `turns_used`
  integer comparison.** A loop with multiple terminal states (mid-turn exception,
  turn-exhaustion, wall-clock exhaustion, honest-empty) MUST be discriminated by the
  already-typed `ScoutUnavailable.cause` + `LoopResult.outcome`, not by arithmetic on the
  turns count — `turns_used` is `None` on ANY degrade (the count is copied only on the
  success path) and a *sub-cap* int on wall-clock exhaustion, indistinguishable from a
  low-turn honest-empty. The real reporting gap is per-cause granularity: a collapsed
  degrade boolean/count cannot say WHICH state a re-emptied case hit, so surface a
  per-cause count for each native terminal cause alongside the retained collapsed count
  (additive-last-with-defaults, `SCHEMA_VERSION` bumped), and pin with an executable
  source-sweep guard that the outcome-deciding modules never branch on
  `turns_used`/`last_turns_used`. `turns_used` survives ONLY as a turns-CONSUMED
  measurement, never a discriminant. (See `harpyja/eval/runner.py` `_scout_degrade_cause`
  + the four `scout_degrade_*_count` fields, the backend `_EXHAUSTION_CAUSE[result.outcome]`
  mapping, and `test_explorer_outcome_logic_does_not_branch_on_turns_used`, spec 0027
  AC4/AC8.)
- A **model-driven loop ends via a tool-call-native TERMINAL ACTION with a STRICT arg schema — never by emitting free text to be regexed, and the strict schema IS the locator-not-diagnoser guard, not a soft check.** When a model must return a structured result to end a loop, give it a dedicated terminal tool (`submit_citations`) whose STRUCTURED args are validated (unknown/extra fields rejected → a typed `SubmitCitationsSchemaError`) and normalized through the existing validation (`normalize_spans`: repo-confine + clamp + drop malformed/out-of-repo/over-budget; empty is honest-empty, never a raise). The terminal action carries NO repo-read capability (it only validates+normalizes refs). Two load-bearing properties: (a) structured args over prose-regexing RETIRES an inherited text-grammar parse path (the 0011/0012 `<final_answer>` grammar), killing the exact text-parsing fragility class behind that era's worst bugs; (b) a diagnosis-shaped field (`root_cause`/`fix`/`explanation`) FAILING the strict schema is the ENFORCEABLE form of the locator-not-diagnoser boundary — the finder finds, downstream agents reason. (See `harpyja/scout/submit.py` `submit_citations` / `SubmitCitationsSchemaError`, spec 0024 AC6/OQ2.)
- A **bounded loop's context truncation is CITATION-PRESERVING BY RULE — truncation must never convert a real find into honest-empty, and that negative is PROVEN, not assumed.** When a loop truncates history to stay under a bloat cap, truncation MAY drop ONLY stale navigational chatter (repeated calls, superseded listings), NEVER the raw output of an observation whose location could still appear in the final result; if recency-capping forces dropping such an observation, a compact index of the dropped spans is re-injected so nothing citable is unrecoverable. Assert the PRESERVATION negative directly — a final citation depending on an observation OLDER than the bloat threshold STILL resolves after truncation runs — not merely that truncation fired (asserting the mechanism fires is necessary but does not prove it is safe; the correctness leak is the silent honest-empty). Pair it with a deterministic loop-detector defined by a CHECKABLE equality (an exact `(tool_name, normalized_args)` repeat over N consecutive no-new-progress turns → a corrective injection), never by intent alone. The turn cap and a distinct WHOLE-LOOP wall-clock ceiling are separate budgets (turns ≠ time for a general model; the per-call HTTP timeout is the floor, the ceiling stops one slow turn wedging the loop). (See `harpyja/scout/explorer_loop.py` `run_explorer_loop`, `scout_history_char_cap` / `scout_loop_repeat_n` / `scout_wall_clock_s`, spec 0024 AC4/AC5/OQ3.)
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

## Deletions & migrations

- A **deletion is pinned by an EXECUTABLE import-absence / public-name guard, never a
  point-in-time grep** — a test that ROTS FALSE when a deleted symbol reappears, not a
  prose note that silently goes stale. Assert the module raises `ModuleNotFoundError`,
  the deleted public names no longer resolve, and (via `ast`, not a text scan) the
  surviving modules no longer import the removed package — so a reintroduction fails a
  test instead of quietly landing. A packaging deletion gets the same teeth: parse the
  real `pyproject.toml` / lockfile and assert the dropped dependency is absent, so a
  clean `uv sync` cannot pull it back. (See `harpyja/scout/test_fastcontext_absent.py`,
  `harpyja/test_packaging.py`, spec 0025 AC4/AC9.)
- **Migrate before you delete a capability-carrying seam.** When the thing being removed
  also carries a still-needed capability — e.g. the `agent_factory=` seam the 0022
  turns-used diagnostic read through — it is a MIGRATION, not a dead-seam delete: surface
  an equivalent PUBLIC per-run seam on the survivor (`LoopResult.turns_used` →
  `ExplorerBackend.last_turns_used` → `ScoutEngine.last_turns_used`, mirroring the
  `last_tally` side-channel), prove it equivalent, repoint the consumer onto it and get it
  GREEN, and only THEN cut the old seam. Distinguish a *cap/budget* from a *used/measured*
  reading (`scout_max_turns` is the loop cap, not the turns-consumed count) — removing the
  measurement seam because a same-named budget exists would silently regress the metric.
  (See spec 0025 AC3.)
- **Disentangle a mixed module; don't symbol-delete it.** When a module mixes retired code
  with a shared core (`normalize.py`: the FC-era suffix-recovery `_recover_suffix` /
  `MIN_TAIL_SEGMENTS` embedded inside the shared `normalize_spans_with_tally` / `ScoutTally`
  / `last_tally` core that EVERY backend and three live eval consumers run through), remove
  ONLY the retired remainder and KEEP the shared core, and PROVE the survivor path still
  resolves without it (a pre-delete consumer inventory + a post-delete import-absence guard,
  two-sided). Ripping the whole path because part of it was dead would strand the live
  consumers. A retired-but-kept computation collapses to a structural constant (recovered
  counts → 0) rather than a signature change. (See `harpyja/scout/normalize.py`, spec 0025
  AC5.)
- **Re-scan for SECOND-ORDER orphans after the primary deletion — the enumerated surface is
  not the whole surface.** A deletion can orphan code that was NOT on the deletion list: once
  FastContext was removed, `scout/tools.py::build_tool_whitelist` (FC's read/glob/grep/model
  whitelist) had only its own test as a consumer. Leaving it is exactly the silently-orphaned
  case a cutover is meant to prevent — a deletion spec must re-scan for newly-unreferenced
  code and remove it in the same change, not stop at the named surface. (See the
  `scout/tools.py` removal, spec 0025.)

## Tests

- pytest. Test files are `test_*.py`, kept next to the package under test unless a top-level `tests/` root is added later (no test root configured yet).
- Cover the fallback paths explicitly: parser-missing → ripgrep, model-down → Tier 0, gate-fail → escalation.
- Drive async code from sync tests with `asyncio.run(...)` rather than adding an async-test plugin (no `pytest-asyncio` dependency). See `server/test_app.py`, `server/test_stdio_hygiene.py`.
- Keep tests network-free by injecting collaborators: pass a `resolver` to `assert_local` and a `which` to `run_doctor` instead of touching live DNS or `PATH`. Default to the real implementation, override in tests.
- Mark tests that spawn a real process or event loop with `@pytest.mark.integration` (declared in `pyproject.toml`) so they are skippable in constrained environments.
- A **deliberate change to a code-enforced EXACT-COUNT / exact-set guard is RECONCILED in
  one change — the convention text AND every hard-count test that pins it move together,
  each with a rationale — never a silent break of the guard.** When an invariant like
  "`build_explorer_tools` returns EXACTLY `{grep,glob,read_span}`" exists precisely to
  catch silent creep, legitimately widening it (adding `ls`) is not exempt from the guard:
  amend the `.speccraft/conventions.md` text (`3 → 4`, `{…,ls}`) WITH a one-line rationale
  naming why the affordance is deliberate, and update BOTH pinning tests in the SAME commit
  (`test_build_explorer_tools_returns_exactly_four_navigation_tools` and the
  schema-vs-dispatch `test_tool_schemas_match_the_built_tool_surface_single_source`). A
  reconciled, rationale-carrying widening is the sanctioned path; a count bumped in one
  test but not the convention (or vice versa) silently disarms the very guard. (See
  `harpyja/scout/test_explorer_tools.py` + `test_explorer_backend.py`, the amended
  tool-suite convention, spec 0027 AC3.)
- **A model-driven loop's initial PROMPT enumeration is bound to the registered tool
  surface by a DRIFT GUARD derived from the SAME single source as the exact-count test —
  a new tool is un-shippable without appearing in the prompt.** The exact-count/exact-set
  guards above pin what `build_explorer_tools` returns and what the schema surface exposes,
  but NOT what the initial prompt ADVERTISES: for an instruction-following 4–14B the
  prompt's enumerated tool list IS the menu, so a tool absent from the prompt is
  structurally unadvertised even when it is registered and schema-correct. This is not
  hypothetical — the 0027 prompt enumerated only "ls, glob, and grep" and silently omitted
  `symbols` (added 0030) and `read_span` for 5 specs, the root cause of the 0040 0/28
  `symbols`-adoption defect (0030's "lift unproven" and every subsequent "not invoked" had
  measured an UNADVERTISED tool). Assert every registered tool name (the full navigation
  surface PLUS the terminal action, documented distinctly) appears in `build_initial_prompt`,
  deriving the asserted set from the SAME single source
  `test_tool_schemas_match_the_built_tool_surface_single_source` uses — never a second
  hand-maintained list. Name-presence alone is necessary but not sufficient where a
  capability needs SELLING (e.g. the repo-wide by-name lookup): add a when-to-use presence
  check for that affordance specifically, because the adoption hypothesis depends on
  advertisement, not mere naming. (See `harpyja/scout/context_map.py` `build_initial_prompt`,
  `test_initial_prompt_binds_to_registered_tool_surface_single_source`, spec 0042 AC1.)

## Filesystem & artifacts

- Harpyja is read-only on **source** files. The manifest and symbol index are *derived artifacts* and are the only sanctioned writes: default to `<repo>/.harpyja/` with a self-ignoring `.gitignore` of `*` (never modify the repo's root `.gitignore`); fall back to `${XDG_CACHE_HOME:-~/.cache}/harpyja/<repo-hash>/` when the repo dir is unwritable.
- Durable artifact writes are atomic: write to a temp file **in the same directory** as the final file, then `os.replace`. The same-dir requirement is load-bearing — it keeps the rename atomic on one filesystem, including the external-cache fallback, so a crash can't leave a truncated artifact.
- Files that must be byte-reproducible (e.g. `manifest.jsonl`) are written with a fixed key order and a stable sort, so two runs over an unchanged tree diff cleanly.
- A derived artifact that is treated as **untrusted on read** must self-authenticate against its **own generation**, not just its producer. Pair the data file with a sidecar carrying (a) a content fingerprint — a sha256 over the data file's exact bytes plus a record count — and (b) the producer identity (engine + each grammar version). On read, rebuild from source whenever the data is missing/unreadable/truncated, the sidecar is missing/unreadable, the producer identity differs, or the fingerprint mismatches. Commit the multi-file pair **data-first, sidecar-last** (each via same-dir temp + `os.replace`) so a crash residue — fresh data under a stale sidecar — fails the fingerprint and rebuilds. The producer identity alone is not enough: it misses a same-engine clean-truncation and a crash residue; the fingerprint is what binds the sidecar to *this* generation. (See `symbols/symbols_io.py`, `symbols/engine_identity.py`.)
- The producer-identity cache key enumerates **one slot per external grammar/plugin entry point**, each with a real version or a `"missing"` / `"load-error:<abi>"` sentinel, via a slot→(dist, module, load-fn) map — not a flat per-package list. Entry points that ship in the **same package share one version and move together** (bump/absence is coupled) but keep distinct identity keys; install/bump of any slot invalidates the cache and triggers a rebuild that clears stale `grammar-missing` flags. (See `symbols/engine_identity.py` `_GRAMMAR_SLOTS`; `typescript` + `tsx` share `tree-sitter-typescript`.)
- Additive dataclass / record fields are appended **last** with a default, so a legacy on-disk artifact still reads and an unchanged tree stays byte-reproducible (the field is absent from old entries, defaulted on read). E.g. the manifest per-file `degraded` field and `CodeSpan.kind`.

## Measurement & eval harness

- **A cost metric CONDITIONED on a mechanism firing carries a RECORD-ONLY, UNCONDITIONED
  cross-check counting the same transition when the mechanism did NOT fire — so a refinement
  that suppresses the mechanism cannot read as "cost eliminated" when it is merely "cost
  de-attributed."** When a counted cost is causally attributed to a lever
  (`silence→wrong-confidence` = empty→submitted-but-not-correct AND `confidence_fired`), the
  conditioning is correct for attribution but has a loophole: a refinement that simply stops the
  lever firing on the offending cells makes the metric drop BY DEFINITION even though those cells
  still incur the cost, now UNFIRED. Freezing the predicate blocks deliberate tuning toward that
  shape but not the mechanism drifting there, so pair the fired-conditioned metric with a
  record-only per-model line counting the SAME empty→(submitted, non-correct) transition where
  the lever did NOT fire (`unfired_silence_to_wrong_confidence`), threaded through the same seams
  and reported BESIDE the conditioned metric — RECORD-ONLY, never in the verdict predicate
  (adding it mid-run would re-open a definitional argument). It is the cross-check the reader
  applies to a fired-conditioned drop; on the 0045 live run it caught one cell whose
  empty→wrong-file cost the fired-conditioned metric had de-attributed to zero. This is the
  fired-conditioning twin of the 0044 record-only observability posture. (See
  `harpyja/eval/live_verifier.py` `silence_to_wrong_confidence` +
  `unfired_silence_to_wrong_confidence`, `harpyja/eval/live_verifier.py` `build_trajectory_record`,
  spec 0045 AC2/AC7.)
- **A frozen NET band can only GATE a stochastic re-measurement if the estimator under it
  is a MULTI-DRAW estimate — a point estimate from ONE stochastic run is not one, and a
  single-draw band will flag drift on noise.** A sanity band frozen before the numbers
  (0046's baseline `[1, 3]`) is sound only if the quantity it bounds is stable enough that
  a same-config re-run lands inside it; on pilot-N stochastic models (qwen3, 33 cells) it
  is not. 0044's operating point drew conv 3 / reg 1 (net +2); the SAME reverted gate on
  the SAME 33 cells drew conv 3 / reg 3 (net 0) — a 2-regression swing on ~7 correct cells,
  well within run-to-run variance — and the frozen band correctly typed
  `BASELINE_DRIFT_STOP`, refusing to certify a comparison point that did not reproduce. The
  discipline is: DO NOT loosen the band post-hoc and DO NOT run the downstream arm "for
  observability" (both are the steering the freeze exists to prevent); instead certify the
  comparison point with a MULTI-DRAW estimate — the median of 2–3 draws, or a band derived
  from the observed per-run variance — before a frozen NET band can gate a re-measurement.
  When the instrument's run-to-run noise reaches the effect sizes the levers are being
  tuned against, the honest reading is not "the lever traded" but "the instrument can no
  longer resolve whether it traded" — and the next move is enlarging the pool, not
  re-levering. This extends the two-stage-freeze/frozen-predicate discipline down one
  level: a frozen band is only as sound as the estimator beneath it. (See
  `harpyja/eval/reactive_outcome.py` `decide_reactive_outcome` `BASELINE_DRIFT_STOP`,
  `specs/0046-submission/outcome.md`, spec 0046 AC5.)
- **A two-arm lever comparison on ONE SUT wires the BEHAVIOR behind a single-bit
  `explorer_`-scoped toggle (baseline off / new on) — an observability-only lever
  (record-but-don't-change) produces a NO_EFFECT null BY CONSTRUCTION, because the arms are
  behaviorally identical and net is 0 a priori.** When a spec measures a NEW policy against
  a BASELINE on the same code, the two arms must differ in exactly one thing: the behavior
  under test. If the "new" arm only RECORDS extra fields (triggers fired, confirmation
  outcome) without changing what the model does or what gets emitted, both arms run the
  identical SUT and any measured delta is pure noise — the comparison cannot come out
  anything but null. The clean construction is a single-bit toggle (0046's
  `explorer_reactive_confirm`, default OFF = baseline byte-identical to the prior operating
  point; ON = the new behavior: reactive nudge-suppression on a disconfirming trigger + the
  confirm-before-submit partition), so both arms share ONE byte-identical SUT and only the
  flag differs — and the production default stays the known-good baseline. This was caught
  MID-IMPLEMENTATION in 0046 (T1–T12 were observability-only; Option A wired the real
  behavior behind the toggle) and is the two-arm twin of the harness-never-mutates-SUT
  rule: the toggle is the sanctioned single point of behavioral difference, and a record-only
  field is a DIAGNOSTIC beside the verdict, never the lever itself. (See
  `harpyja/config/settings.py` `explorer_reactive_confirm`, `harpyja/scout/reactive_policy.py`
  + `harpyja/scout/confirm.py`, spec 0046 AC2/AC3.)
- **A frozen predicate must have a CONJUNCT PER DIRECTION the lever can err in — a predicate with
  fewer sides than the lever's error space will sell a TRADE as a win.** When a lever errs in
  opposite directions on different cells (a confidence gate too loose on some, too tight on
  others), a uniform tighten/loosen cannot fix it — it trades one error for the other. A two-sided
  net (conversions − regressions) or a three-sided ledger that omits the reopened direction would
  type such a trade a success: the 0045 refined gate cut silence→wrong-confidence 5 → 1 but
  resurrected found-but-unsubmitted 1 → 8, and only the FOUR-SIDED predicate (conversions /
  regressions / s→wc / fu), with a `TRADES_DIRECTIONS` member carrying a disjunct per direction
  `((s→wc < X ∧ fu > Y) ∨ (fu < Y ∧ s→wc > X))`, surfaced it. This is the make-the-invisible-
  countable discipline applied to the predicate SHAPE: count the reopened cost as a first-class
  side, don't let it net-cancel. (See `harpyja/eval/refinement_outcome.py`
  `decide_refinement_outcome` `TRADES_DIRECTIONS`, spec 0045 — 4th instance after 0033/0043/0044.)
- **A frozen SUT-hash pin AGES: when a later spec evolves the SUT an earlier spec's frozen config
  hashed, the earlier committed pin's `sut_hash` no longer equals the live recompute — reconcile
  by asserting the DIVERGENCE explicitly (the freeze is HISTORICAL), never by deleting the pin or
  letting it rot false.** A committed-config pin test that asserts
  `committed["config"]["sut_hash"] == compute_sut_hash()` is correct only while the SUT is
  byte-stable; once a successor spec touches the hashed modules (0045 evolving
  `confidence_gate.py` + adding `confidence_signals.py`), that equality breaks. The reconciling
  move is to amend the earlier pin test to assert every field EXCEPT `sut_hash` still matches the
  in-code config AND that the frozen digest is a valid 64-char sha that now DIFFERS from the live
  recompute — the historical freeze made explicit, its provenance preserved. This is the
  anti-tautology freeze discipline extended across spec boundaries: a frozen hash is a
  point-in-time attestation, not a live invariant, and a successor must reconcile it deliberately.
  (See the amended `test_committed_submission_config_matches_computed_truth`, spec 0045.)
- **Live integration artifacts write to the persistent, gitignored `eval_work/live_artifacts/<test>/<UTC-basic-timestamp>-<pid>/` — never a `TemporaryDirectory`** (spec 0035, harness-side/non-SUT). Three bucket-unanswerable re-runs were forced by tempdir-discarded artifacts (0032 astropy, 0033-T14, 0034-AC5): a live run's artifact IS the answer to every follow-up question, so it must survive the test process. The helper (`harpyja/eval/live_artifacts.py`) reuses the SAME outside-repo `atomic_write_json` (inside-repo refusal + atomic semantics inherited, never re-implemented); the measurement TARGET (`repo_path`, the worktree) must be a separate tree from the artifact dir or the refusal fires (pinned both ways); the base path is NOT a `Settings` field (eval-knobs-disjoint). This item is harness/test-file-only, so a following measurement spec can still claim SUT-byte-frozen. (See `harpyja/eval/live_artifacts.py`, `test_live_artifacts.py`, spec 0035 AC6/AC7.)
- A measurement/eval harness observes the system under test through its **real public
  seam** and never mutates its config or behavior — it measures, it does not modify.
  Drive the production entrypoint via injected collaborators (fakes for unit, the real
  `build_*` factories for integration through one stack object), and produce any
  configuration override with `dataclasses.replace`, never mutation
  (`test_sweep_does_not_mutate_settings`). (See `harpyja/eval/runner.py` `LocateStack`
  / `build_live_stack`, `harpyja/eval/sweep.py`.)
- **A defect the LIVE run reveals in the SUT is fixed AFTER the run completes, never
  mid-run — the SUT is frozen for the duration of one measurement, and the fix + its
  pins land only once every cell has been recorded on the pre-fix SUT.** A measurement's
  validity rests on every cell seeing the SAME system; patching the SUT partway through
  would split the run across two SUTs and silently invalidate the comparison (the
  run-granularity contamination class 0040/0041 exist to prevent, self-inflicted). So a
  live-observed bug (e.g. 0042's `path=""` silent-routing and nonexistent-path silent-`[]`
  defects, surfaced in specific cells) is RECORDED as a live observation, the run finishes
  and types its outcome on the frozen SUT, and only then does the fix + its regression pins
  land — with the outcome doc explicitly stating that all cells were measured on the pre-fix
  SUT so run integrity is auditable. This is the SUT-side twin of the harness-never-mutates
  rule above: the harness never mutates the SUT during a run, and neither does the operator.
  (See `harpyja/scout/explorer_tools.py` `symbols` post-T12 fixes, `specs/0042-adoption/outcome.md`
  live observations, spec 0042.)
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
  spec 0014 AC6/AC11. Spec 0024's `ExplorerBackend` inherits the same first-class
  degrade-rate field for its four native-loop causes.)
- When a versioned report schema gains **additive** fields, append them
  last-with-defaults AND **centralize the field set + its defaults in one anti-drift
  source** (a `_*_DEFAULTS` map the builder injects), so an older-shape block and a
  newer-shape block **both** pass the one loud validator and there is a single place a
  new field is declared. Bump `SCHEMA_VERSION`. (See `harpyja/eval/report.py`
  `_RUN_METADATA_DEFAULTS` / `_CASE_DEFAULTS` / `_AGGREGATE_DEFAULTS`, `_with_defaults`,
  `SCHEMA_VERSION` `0009-6a/1` → `0010/1`.)
- When the **measured backend changes and a field no longer describes anything, RETIRE it
  to always-zero with a `SCHEMA_VERSION` bump — keep the field for schema stability, stop
  populating it, and let the bump record that the measured thing changed** (the honest
  default, adopted unless a downstream consumer reads the field expecting non-zero, in which
  case remove-with-bump). A field that STAYS populated but whose backend-specific NAME has
  become a misnomer is documented as **backend-neutral**, not silently misread: the kept
  `fc_citation_{spanned,filelevel,dropped}` shape-tally fields are now populated by the
  explorer, so the `fc_` prefix reads as FastContext-specific but is backend-neutral going
  forward — record the naming debt (rename with a future bump, or treat the prefix as
  neutral) so a later reader does not mistake the data for FastContext-only. The retired
  `fc_citation_recovered_*` fields default 0 and legacy blocks keep validating via
  `_AGGREGATE_DEFAULTS`. (See `harpyja/eval/report.py` `SCHEMA_VERSION` `0014/1` → `0025/1`,
  spec 0025 AC7.)
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
  A projection may carry a **single deliberate, SCORED departure** from the frozen
  oracle when the whole diagnostic axis depends on it — e.g. spec 0022 re-maps a
  path-only right-file hit (`span_hit_kind == "file"`) to `RIGHT_FILE_WRONG_SPAN`
  rather than the oracle's coarse primary-hit, because "found the file" vs "found the
  span" IS the measurement. The departure lives ONLY in the additive eval classifier
  (never in `metrics.py`), is named in the module docstring, and is double-guarded by
  a `SUT_SURFACE` frozenset **allowlist** of the exact frozen public names the module
  may touch + the frozen-oracle **behavior snapshot** — so a silent re-map into the
  shared oracle cannot happen. (See `harpyja/eval/locate_accuracy.py` `SUT_SURFACE` /
  `classify_case`, spec 0022 AC10.)
- A **lift/capability measurement's per-case outcome bucket is computed by the SAME
  ground-truth oracle used everywhere else (one-oracle reuse) — never a `has_citations`
  presence proxy — and the intervention it tests (a tool call) must be CONFIRMED, not
  assumed.** A bucket mapped as "returned something → CORRECT" measures citation
  PRESENCE, not correctness; paired with a STRUCTURAL CONTROL that then moves by a
  mechanism the intervention cannot produce, it is a FALSE-CAPABILITY read — the
  degrade-masks-outcome trap at the measurement layer. Route the outcome through the
  existing span oracle (`locate_accuracy` buckets), and instrument the tool call so its
  invocation is asserted, not tolerated-if-absent. A tool shipping proven + a harness
  running clean with it present is NOT the same as its lift being measured. (See
  `harpyja/eval/test_symbols_lift_live.py` deviation vs the 0022/0026 oracle-reuse
  discipline, spec 0030 deviations.)
- **Proving a GENERATION-CONTROL knob works is a GENERATION-level claim, not a
  REPORTING-level one — never assert only on the response FIELD the knob is
  supposed to suppress.** A knob that suppresses output (a `think:false`, a
  reasoning-off flag) is proven effective only by evidence the MODEL's behavior
  changed, because a knob that merely stops SERIALIZING the field in the reply —
  while the model still generates and burns budget invisibly, or leaks `<think>`
  into content — would satisfy a "field is now `{None, 0}`" assertion and read as a
  working knob (the 0028 `/no_think`-was-inferior hole one level down: a control
  believed effective that never took effect). The proof is therefore MULTI-FACTOR
  and non-collapsible — for a thinking knob: (a) the per-turn field itself
  (`reasoning_chars`), (b) a GENERATION-level discriminator (the tiny-cap
  technique — small `max_tokens` + suppress → content appears / `finish≠length`
  iff generation genuinely stopped, vs a still-generating model exhausting the cap
  suppressed-stream-first), and (c) a budget cross-check (`completion_tokens`
  across arms) + a leak scan (`<think>`-in-content). None may substitute for
  another, and it must not quietly collapse back to single-factor field-presence.
  This is the sibling of the presence-proxy false-capability rule above (a
  `has_citations→CORRECT` proxy measures PRESENCE, not correctness) applied to
  suppression: field-absent ≠ generation-stopped. (See spec 0037's probe
  three-factor discriminator + `test_live_think_knob_three_factor_effectiveness`,
  `specs/0037-explorer-think-knob/probes/run_probes.sh`, spec 0037 AC1/AC3.)
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
  spec 0020 D7/D8/AC2/AC11/AC12.) The two postures are deliberately SPLIT and NOT the
  same answer: an integration test FILE stays skip-not-fail (a host missing
  infrastructure this spec doesn't own must not red-fail CI), but the
  DELIVERABLE-producing run fails LOUD — a `preflight` gate (`preflight_models_present`
  behind `assert_local`) plus an opt-in strict switch (`require_live_stack` reading
  `HARPYJA_REQUIRE_LIVE_STACK`, which converts the integration skip into a hard fail
  for the closure run). Net: unrelated CI stays green; the run that produces the
  finding cannot go green by skipping. (See `harpyja/eval/locate_probe.py`
  `require_live_stack`, spec 0022 fail-posture.)
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
- A diagnostic/attribution that cannot be **recovered from a persisted artifact is a
  LABELED ESTIMATE, never a fabricated recorded number** — the honest-precision /
  no-false-capability rule applied to a measurement's provenance. Two instances, one rule.
  (a) A metric-integrity diagnostic that rests on a per-run dump asserts that dump's
  **existence FIRST**: `eval_work/` is gitignored / machine-local, so per-run diagnostics
  evaporate and un-committed secondaries survive only in an operator transcript — if the
  dump is absent the deliverable **degrades to an explicitly-labeled estimate** (e.g.
  per-tier proportions from a ≤2-case micro-run × N cases), anchored on the one recorded
  aggregate (a wall-clock total), never a re-quoted transcript figure dressed as measured.
  (b) A per-tier decomposition the frozen runner never persisted (case-level `latency_ms`
  only, not Scout/judge/Deep granularity) is attributed at the **eval boundary** by
  wrapping a collaborator's **public** method (a `_wrap_timed` that is a safe no-op on a
  missing/None method and restores in `finally`) — **never inside frozen orchestrator
  internals** — and the split is labeled `"estimate"` while the total stays
  wall-clock-anchored. (See `harpyja/eval/escalation_microrun.py` `_wrap_timed` /
  `build_micro_result`, spec 0021 T0 / AC3, review C1.)
  (c) A signal the frozen SUT **tracks internally but discards** (FastContext records
  turns in a trajectory JSONL the frozen client `os.unlink`s in its `finally`) is
  recovered through a **PUBLIC injection seam**, not a frozen-internals edit: an
  eval-side factory passed to `build_scout_engine(..., agent_factory=…)` wraps the
  REAL `make_fastcontext_agent` and reads the trajectory BEFORE cleanup fires,
  surfacing `turns_used_source ∈ {"trajectory","unavailable"}` — a labeled source, an
  honest `unavailable` fallback on the seamless path (Path B / unwired), never a
  fabricated counter. Recovering a discarded signal via a public seam beats both a
  frozen-internals edit and a guessed number. (See `harpyja/eval/locate_probe.py`
  `counting_agent_factory` / `count_turns`, spec 0022 AC5.)
  (d) A spec claim that a quantity is **MEASURED is VERIFIED against the actual
  persisted-artifact schema BEFORE it is asserted, not after** — an unverified
  "from the ledger / from the record" claim is a latent fabrication until the field is
  shown to exist. When the field is absent it downgrades to an explicitly-labeled
  estimate (or an honest "needs instrumented re-run"), never carried as measured.
  Spec 0043's round-1 spec asserted "case-level latency from the run ledger" as
  measured; direct inspection of the committed 0042 `adoption_results.json` proved the
  ledger entries carry NO elapsed/duration field (one `timestamp` per verifier
  artifact, `per_turn` carries only `{reasoning_chars, completion_tokens,
  finish_reason}`), so ALL timing was reclassified ESTIMATE-GRADE (successive
  verifier-artifact timestamp deltas within a sequential run block) across the
  evidence-base section, AC1, and the What section, and the attributor's tests pin
  that no measured-latency field is ever read. The verification is the obligation —
  the downgrade is only its consequence. (See `harpyja/eval/clock_attribution.py`
  `test_no_measured_latency_field_anywhere` / `test_case_timing_is_estimate_grade_labeled`,
  spec 0043 AC1.)
- A recorded diagnostic **finding taxonomy is MECE**: when candidate outcome values are
  not mutually exclusive — one is an *explanation UNDER* another rather than an
  *alternative TO* it — split the finding into **orthogonal axes, one value per axis**,
  rather than forcing a false either/or into a single flat enum. Spec 0021 records
  `accounting ∈ {ACCOUNTING_BUG, CORRECT_NO_ESCALATION}` × `wrong_citation_fate ∈
  {GATE_FALSE_ACCEPTANCE, NO_ESCALATION_PATH, DEEP_DEGRADED_OR_UNAVAILABLE, NOT_APPLICABLE}`
  because `GATE_FALSE_ACCEPTANCE` *explains why* `escalation_rate=0` was correct (it is not
  a rival to `CORRECT_NO_ESCALATION`): whether the count was faithful is independent of why
  the wrong cases didn't escalate. Each axis value is grounded independently (the accounting
  axis by a coupling PIN over the derived metric; the fate axis by a projection over the
  frozen SUT). A projection/characterization of frozen SUT behavior is grounded in READING
  THE FROZEN SOURCE, not the spec/plan's assumption about it — when they conflict the code
  wins and the test is corrected to pin the actual behavior (spec 0021's honest-empty case:
  the plan assumed Tier-1 escalates, `_locate_auto` gate-skips it and never does;
  `classify_escalation` gained a `tier1_empty` parameter and the trigger test was corrected
  — a test asserting a false claim about the SUT is worse than none). (See
  `harpyja/eval/escalation.py` `WrongCitationFate`, spec 0021 AC4 / review C2.)
- An **availability/skip predicate must be scoped to the tier it actually gates** — a
  measurement of tier X must not reuse a sibling tier Y's availability check, or it
  **false-skips a capable host** for a dependency X never needed (the mirror of a
  false-skip masking absence). Spec 0022's Scout-only probe initially reused the
  Deep-oriented `_live_stack_available` (which requires Deno — the Tier-2 WASM sandbox
  — and the Deep model, both irrelevant to Scout) and skipped on a Scout-served,
  Deno-absent host; the fix is an additive tier-scoped predicate
  (`scout_stack_available` = fastcontext + `rg` + a reachable Scout endpoint, no Deno,
  no Deep model). A gate that over-requires is as dishonest as one that under-requires.
  (See `harpyja/eval/locate_probe.py` `scout_stack_available` vs the Deep-oriented
  `_live_stack_available`, spec 0022.)
- An **isolated eval probe that drives a tier OUTSIDE the production wrapper must tolerate
  the SUT's typed degrade taxonomy — record a degrade as the honest floor outcome, never a
  crash.** When a probe runs a tier directly (Scout only, no orchestrator), it does not get
  the production degrade wrapper that floors a typed failure, so it must catch the tier's
  own typed error and record the same "no usable citation" outcome the orchestrator would
  (an EMPTY localization) — not propagate the raise and abort the run. This is load-bearing
  when a backend swap CHANGES the failure posture: the FastContext backend returned
  honest-empty on failure, but the explorer RAISES on turn/wall-clock exhaustion and
  model-unreachable, so the isolated probe had to learn the explorer's `ScoutUnavailable`
  taxonomy to keep the harness running end-to-end. Recording the degrade as the floor is
  the SUT-faithful outcome, never a fabricated citation. (See `harpyja/eval/locate_probe.py`
  `_run_scout_query` catching `ScoutUnavailable` → `normalize_citations([], None)`,
  spec 0025 AC5/AC8.)
- A diagnostic that must **route a failure to the right FIX kind scores at two
  granularities and makes the GAP a first-class metric** — the gap IS the
  discriminator, not a derived afterthought. Spec 0022 reports file-level accuracy
  (found the right file) and span-level accuracy (found the right span) independently
  and surfaces `gap = file − span` as a reported field: a large gap routes to a
  **precision fix** (find files, miss spans), a low file-level routes to a
  **capability/retrieval fix** (doesn't find the file), and the two are never
  conflated into one accuracy number that hides which fix the data actually calls for.
  Pair it with a **pre-registered prior** (the expected label + what distribution would
  overturn it) recorded BEFORE the run, as a falsifiability guard against confirmation
  bias. (See `harpyja/eval/locate_accuracy.py` `score_distribution` / `LocateDistribution`
  `gap` / `decide_finding`, spec 0022 AC2/AC7.)
- A **pre-registered decision config is a FROZEN object and the verdict is a TOTAL PURE
  FUNCTION over it** — declared in code before the run so it cannot be steered post-hoc —
  and each threshold is **derived from the test's own reachability arithmetic, not a round
  guess**. The config is a `frozen=True` dataclass exposed as a single `PREREGISTERED_*`
  constant, the rule/prompt inputs are **hashed before any live run**, and the decision
  functions are total with **non-overlapping predicates** pinned by a grid totality test
  (every input returns an enum member, never raises, never silently defaults; distinct
  outcomes get **separately named** reasons). A threshold is justified by the test that
  consumes it: `MIN_DISCORDANT_PAIRS=8` is the exact-McNemar reachability floor (under H0
  the discordant pairs are a sign test at p=0.5, so α=0.05 is first clearable at
  `n_discordant≥6`; 8 buys one contrary pair of slack) — a round `5` was wrong because it
  made the positive verdict structurally unreachable (the small-N trap in reverse: every
  run would default to `INCONCLUSIVE`). This is the successor to the 0022 pre-registered
  *prior* (a recorded prose expectation): here the whole verdict is a frozen-config pure
  function, not just its prior. (See `harpyja/eval/benchmark_fit.py` `PREREGISTERED_CONFIG`
  / `decide_axis1` / `compose_verdict` / `MECHANICAL_RULE_HASH` / `LLM_PROMPT_HASH`,
  spec 0023 AC4/AC6.)
- **When a spec both SELECTS an intervention FROM measured data AND then measures that
  intervention, the freeze is TWO-STAGE and ordered — the CHOOSING RULE freezes before
  the numbers exist, the CONFIG naming the choice freezes after selection but before any
  live spend.** The single-stage freeze above closes post-hoc steering of the *verdict*;
  it does NOT by itself close post-hoc steering of *which intervention was chosen*. When
  the same spec derives a lever/arm from an attribution and then re-measures under it,
  split the freeze: (1) the selection rule (a `dataclasses.asdict`→sha256-hashed decision
  table with a TOTAL selection function) freezes + commits its artifact BEFORE any
  attribution number is computed or seen — so the choice is mechanical, not fitted to the
  numbers; (2) the `PREREGISTERED_*_CONFIG` naming the SELECTED intervention (+ the frozen
  power floors, counted buckets, detector version, and the SUT hash the driver re-verifies
  at startup) freezes + hashes + commits AFTER the table has mechanically selected from the
  committed attribution but BEFORE any live re-measurement compute. The config freeze being
  post-attribution is BY DESIGN, not a violation: the choice-steering risk is closed by
  stage 1 and the predicate-steering risk by stage 2 preceding the spend. Pin that the
  config's lever field EQUALS `select_lever(...)` over the committed attribution
  (mechanical, never hand-picked), and hard-sequence it in the task order (no attribution
  number before the stage-1 commit; no live spend before the stage-2 commit). (See
  `harpyja/eval/lever_table.py` `FROZEN_LEVER_TABLE_0043` / `select_lever` +
  `diagnosis_config.py` `PREREGISTERED_DIAGNOSIS_CONFIG_0043`, and their committed
  `specs/0043-diagnosis/{lever_table,diagnosis_config}/*.json`, spec 0043 AC4/AC5.)
- **A frozen decision config carries LITERALS drift-pinned to the SUT constants, NEVER
  references to them (anti-tautology), and a total verdict's POWER FLOORS are CONSUMED by a
  branch while a BENEFIT conjunct accompanies the net conjunct so a do-nothing lever cannot
  type a ship.** Two failure modes the 0043 frozen-config rule above does not by itself close:
  (1) a config that IMPORTS the SUT constant it claims to pin re-derives whatever the code says
  and can never catch a drift — so `PREREGISTERED_*_CONFIG` fields are hand-written LITERALS
  (`CONFIDENCE_MAX_QUALIFYING_SPANS=5` copied as a number, the nudge template + role copied as
  data, the baseline pinned by path + sha256 with its derived quantity — `fu_before=6` —
  RE-DERIVED in the pin test), and a drift-guard test asserts the literal EQUALS the live SUT
  constant (`sut_hash` covering the gate module), so a code change that desyncs from the frozen
  choice ROTS THE TEST FALSE rather than silently agreeing with itself; (2) a verdict whose
  positive branch is `aggregate net ≥ 0 AND no model net-negative` types a do-NOTHING mechanism
  (a nudge that never fires, or fires and buys nothing) as a SHIP at net 0 — so the SHIPS branch
  carries a BENEFIT conjunct (`conversions ≥ 1 OR the primary metric improved`) AND a distinct
  `*_INERT` label (fired-but-bought-nothing) precedes it, and the pre-registered power floors are
  CONSUMED by an explicit `UNDER_POWERED` branch (never dormant config — the 0043 discipline),
  all under a FROZEN TOTAL ORDER over overlapping conditions with a grid-totality test and every
  true condition recorded in the artifact. When the numbers meet the mechanical ship predicate
  but MISS a pre-registered per-model reading, record a QUALIFIED ship with named residuals —
  never re-type the verdict after seeing the numbers (post-hoc re-typing is steering). (See
  `harpyja/eval/submission_config.py` `PREREGISTERED_SUBMISSION_CONFIG_0044` /
  `SUBMISSION_CONFIG_HASH_0044` + `submission_outcome.py` `decide_submission_outcome` (five
  members: UNDER_POWERED / NEVER_FIRES / STILL_TRADES_OFF / NUDGE_INERT /
  CONDITIONED_NUDGE_SHIPS), spec 0044 AC5.)
- A **within-case paired A/B over a BINARY outcome is a McNemar test, and its power lives
  in the DISCORDANT PAIRS — the effective sample size is the discordant (flip) count, not
  N.** When each case is its own control (run the SUT on arm A and arm B for the *same*
  gold target so per-case difficulty cancels) and the outcome is binary (empty / not-empty),
  compute deltas and the discordant `(b,c)` **from retained per-case `(case_id, a_bucket,
  b_bucket)` pairs**, never as a difference of two independent aggregate rates; the paired
  test is the exact two-sided McNemar (a sign test on the discordant pairs at p=0.5,
  implementable from `math.comb` — no scipy). Size the case set by the discordant floor the
  verdict needs, not by a raw-N intuition: a binary paired probe is **not** as cheap as the
  paired-continuous intuition suggests (reaching 8 flips can need ~15–25 cases), and the
  config states that honest cost rather than glossing it. (See `harpyja/eval/benchmark_fit.py`
  `mcnemar_exact_p` / `PairedRow` / `aggregate_paired`, spec 0023 AC3/AC4/OQ1.)
- A **verdict-driving instrument is made STRUCTURALLY INCAPABLE of the bias it is trusted
  against; a smarter instrument is a LABELED, NON-DECIDING SENSITIVITY arm.** When a probe's
  credibility rests on it *not* cheating (e.g. not injecting the answer's vocabulary), make
  the PRIMARY arm structurally blind by construction — a single **case-agnostic**,
  answer-blind rule whose output is a **subset of its input** (extraction, never generation),
  so it *cannot* manufacture the favorable verdict — and record its full per-case output +
  everything it discarded for audit. A more capable arm (an LLM reformulator) is admitted
  only as a **labeled, non-primary sensitivity check** gated by a post-hoc same-property
  **hard reject** (a subset-violating output is rejected, never passed through); it **never
  decides** — it only disambiguates the one case the blind arm cannot (a flat primary delta:
  real null *or* the blind rule was too crude). Structural blindness is *why* the primary
  drives the verdict; the smart arm's agreement corroborates across a dumb and a smart
  instrument, its disagreement is itself a named `INCONCLUSIVE` trigger. (See
  `harpyja/eval/distill.py` `mechanical_distill` (subset + code-identifier strip, gold-blind)
  vs `llm_distill_guarded` (injected `Callable`, `DistillRejected`), spec 0023 AC2.)
- A **per-case INPUT-VALIDITY precondition on a measurement arm makes an underpowered /
  degenerate-input run SELF-FLAG rather than fake a null** — the no-false-capability rule
  applied to the *sample*, not just the metric. When a null result is only interpretable if
  the input arm was genuinely exercised (a `delta≈0` means "capability wall" ONLY if the raw
  arm actually carried the hard input), gate each case on a recorded precondition
  (`is_raw_issue`: real multi-paragraph body, not a terse fixture), **exclude** failing cases
  from the effective sample (`usable_n`) and record them (`excluded_case_ids`), and force the
  power-starved verdict (`usable_n < min_n` → `INCONCLUSIVE(INSUFFICIENT_POWER)`). So a
  by-construction null (terse fixtures → `delta≈0`) **cannot masquerade** as the real finding
  it superficially resembles — the run reports `usable_n=0` and every case accounted-for
  rather than a false `CAPABILITY`. This sharpens the 0020 "verify the null is real" rule
  into a *structural* per-case guard, not a post-hoc spot-check. (See
  `harpyja/eval/locate_probe.py` `is_raw_issue` / `usable_n` / `excluded_case_ids`,
  spec 0023 AC8.)
- A **two-axis verdict may let one axis DOWNGRADE the other's routing via a PRE-REGISTERED
  N×M composition — a second axis is a qualifier, not an inert caveat.** Where the 0021
  MECE rule keeps orthogonal axes as independent *reporting* dimensions, a decision can go
  further: a **representativeness** axis (is the benchmark even the right yardstick?) can cap
  or re-route a **capability** axis's conclusion, provided the full grid is fixed BEFORE the
  run as a total function over `(axis1 × axis2)` — e.g. `QUERY_SHAPE×¬representative` routes
  to *build a truer benchmark first*, **NOT** the finder swap that `QUERY_SHAPE×representative`
  would imply; `CAPABILITY×¬representative` routes to *retire the benchmark*. The cell the run
  lands in **names the next spec**. Encoded and totality-tested exactly like a single-axis
  verdict (`compose_verdict` total over `Axis1Verdict × bool`), never applied as a
  read-time judgment call. (See `harpyja/eval/benchmark_fit.py` `RepresentativenessRecord` /
  `is_representative` / `compose_verdict`, spec 0023 AC5/AC6.)

- An **eval fixture JOINS its labels by key from a sha256-pinned source of truth — it
  never transcribes them a second time.** When a labeled set reuses ground truth that
  already lives in a committed, integrity-pinned artifact, the derived fixture stores
  ONLY the new payload (here: the terse query + guard provenance) and references the
  source by key (`case_id`); the loader asserts the source's sha256 pin FIRST — refusing
  to join against an unverified source — and only then joins the label. A copied label
  is a second transcription that can silently drift from the authority the pin protects;
  a join keeps ONE authority. Side data the fixture needs but must not promote to a
  validated record field (e.g. `base_commit`, resolved later via provisioning) rides a
  separate join-meta shape, not the record. (See `harpyja/eval/terse_dataset.py`
  `load_terse_dataset` / `assert_raw_pin` / `JoinMeta`, spec 0026 AC1.)
- A **NEW schema-version tag can GATE strict validation so additive-defaults (legacy
  compat) and reject-if-missing (a new guard) coexist in ONE loud loader** — resolving
  the contradiction between "append fields last-with-defaults so old rows still read"
  and "reject a new row missing a load-bearing field." Introduce a version constant
  (introduced, not a bump; distinct from any report `SCHEMA_VERSION`); the loud parser
  branches on it — a tagged (new-schema) row MUST carry the guard fields, an untagged
  (legacy/seed) row loads unchanged with those fields defaulted. Both directions are
  TDD'd in one loader call (the new row rejected-if-missing AND the legacy row
  loads-with-defaults), because the parser is shared and a naive unconditional guard
  breaks every existing fixture. (See `harpyja/eval/dataset.py` `DATASET_SCHEMA_VERSION`
  / version-gated `_parse_case` / `_parse_terse_guard`, spec 0026 AC3/AC5.)
- **When a schema-version-gated validator gains its SECOND accepted version, the exact
  `== VERSION` gate WIDENS to membership in a `_KNOWN_*_SCHEMA_VERSIONS` frozenset — the
  new version is ADDED to the set, never chained as a second `==`, and a legacy row keeps
  validating down the SAME branch rather than being silently reclassified as
  non-terse/unknown-schema.** This is the multi-version successor to the single-version
  gate above: the gate started as an exact match (`schema_version == DATASET_SCHEMA_VERSION`
  → `is_terse`) and, when a new version was introduced, became `schema_version in
  _KNOWN_TERSE_SCHEMA_VERSIONS` so the older tag still routes down the terse branch with the
  new fields defaulted while the new tag is held to its added guard. The frozenset is the
  single enumerated source of accepted versions (`not in → loud reject`), so a validator
  cannot silently accept an unknown shape and an old artifact cannot silently fall off the
  validated path. Widening the accepted set is deliberate and adds the new version WITH its
  guard in the same change, never a silent `==`-to-`==` drift. (See
  `harpyja/eval/live_verifier.py` `_KNOWN_VERIFIER_SCHEMA_VERSIONS` grown
  `0031/1 → 0033/1 → 0034/1`, and `harpyja/eval/dataset.py` `_KNOWN_TERSE_SCHEMA_VERSIONS`
  grown `0026/1 → 0036/1` with `is_terse` widened from `==` to `in`, spec 0033/0034/0036.
  `authoring_provenance.py` remains single-version exact-match — correct until it gains a
  second version.)
- **The DRIVER script for a live/operator run — and its committed output artifacts — live
  under `specs/NNNN/`, NOT in `harpyja/`, as the reproducible provenance of the finding;
  every such driver is STOP-AND-WARN on infra (a loud abort naming the missing/unservable
  dependency, NEVER a skip), and a long-running driver is additionally RESUMABLE.** A live
  finding is only auditable if the exact script that produced it, plus its inputs and its
  emitted artifacts, are committed beside the spec (e.g. `specs/0034-.../probes/run_probes.sh`
  + `probe_*.json`; `specs/0036-.../authoring/run_authoring.py` + `authored_queries.json`;
  `specs/0036-.../pilot/run_pilot.py` + `pilot_results.json` / `gate_report.json`) — the
  driver imports the frozen SUT/harness modules from `harpyja/` but is itself operator
  tooling, never product code (it never enters the runtime import graph, same posture as the
  0026 authoring tool and the 0010 convert/provision stages). Two rules travel with it: (i)
  a `_preflight()` probes the live dependency (Ollama `/api/tags`, arm servability) and
  raises `SystemExit("STOP-AND-WARN: …")` naming the exact missing piece — an infra failure
  loudly aborts, it is never absorbed as an empty/clean result (the BLOCKED-not-close cause
  boundary applied to the driver); (ii) a driver whose run outlasts one invocation budget is
  RESUMABLE — each per-unit outcome is written to a ledger IMMEDIATELY, completed units are
  skipped on re-invocation, and it exits `3` while work remains / `0` when complete, so a
  bounded-budget live run reaches a verdict across re-invocations without re-spending
  completed work. This composes with the persistent live-artifacts home (a driver writes its
  durable verifier artifacts through `live_artifact_dir`) and the
  recovered-from-a-persisted-artifact rule. (See `specs/0036-terse-query/pilot/run_pilot.py`
  `_preflight` / resumable `pilot_results.json` ledger,
  `specs/0034-reasoning-observability/probes/run_probes.sh`, spec 0034/0036.)
- A **live probe that ADJUDICATES a capability question returns exactly one value of
  a committed TYPED-OUTCOME enum (the total answer space), persisted as a
  schema-versioned SPEC-LOCAL artifact pinned by a unit test, with downstream ACs
  made CONDITIONAL on the recorded outcome — a TRIPWIRE: the conditional tests skip
  with the machine-recorded outcome as the reason and AUTO-ACTIVATE, zero edits,
  when a future run flips the outcome.** When a spec's work depends on an unproven
  capability (does this knob/endpoint actually do X?), do not pre-commit to the
  happy path: enumerate every possible answer as a typed enum (the 0023
  named-outcome discipline — e.g. `{native-think-effective, chat-template-effective,
  no-op}`), run the probe FIRST, and commit the one outcome the evidence supports as
  a `<spec>/N` spec-local artifact (NOT a verifier-schema field — it adds no
  persisted product field) validated loudly and DRIFT-PINNED by a unit test, so the
  claim cannot exist without the recorded evidence backing it. The downstream ACs
  (a request-body pin, a live effectiveness proof) load the committed outcome and
  are authored as conditional pins: a non-target outcome is a legitimate terminal
  close via `skip`-with-the-recorded-reason (the two-terminal-paths shape — a blocked
  result is a valid recorded close, not a failure to paper over and never a
  pass-by-default), and a reconciliation spec that RE-RUNS the probe and flips the
  outcome makes the withheld pins enforce themselves with no test change. A
  non-target outcome NEVER silently re-points the mechanism the spec was probing —
  that is its own reviewed follow-up with the probe re-run as its acceptance gate.
  This composes the committed-driver rule (the probe is a committed operator driver),
  the drift-pin (claim bound to evidence), and the measurement-close rule
  (skip-not-fail is a close only because the outcome is machine-recorded and gates
  the ACs). (See `harpyja/eval/think_probe.py` `PROBE_OUTCOMES` /
  `PROBE_RESULT_SCHEMA_VERSION="0037/1"` / `load_probe_result`,
  `specs/0037-explorer-think-knob/probes/probe_result.json` pinned by
  `test_think_probe_result.py`, the conditional
  `test_explorer_think_pin_gated_on_native_probe_outcome` /
  `test_live_think_knob_three_factor_effectiveness`, spec 0037 AC1/AC2/AC3.)
- A **probe pricing a costly MIGRATION scopes the not-yet-ruled-out VARIANTS of the
  INCUMBENT transport FIRST — the cheaper honoring path may already exist on the endpoint
  you are about to leave, and probe-before-wire is the gate that finds it** (spec 0038).
  When a spec's leading candidate is a big-blast-radius switch (a new endpoint, a new
  adapter, a divergent transport), do NOT pre-commit to it: make the probe matrix include
  a re-check of the incumbent's own not-yet-eliminated variants (a newer passthrough, an
  alternate param on the SAME path), and price the migration only after those are ruled
  out. 0037 proved `/v1` DROPS top-level `think` and named native `/api/chat` as the
  leading reconciliation candidate; 0038's probe found `reasoning_effort` on the EXISTING
  `/v1/chat/completions` path genuinely toggles generation — so the reconciliation shipped
  as ONE mechanism line on the incumbent transport (True→`"high"` / False→`"none"` /
  None→omit), with ZERO endpoint-migration blast radius (tool_calls shape, usage/finish
  extraction, `assert_local`/`timeout_s` all unchanged) and zero divergent-transport debt
  (explorer and Deep stay on one `/v1` path) — the full-migration steps the plan
  pre-authored were recorded N/A-on-branch, never built. The migration you avoid by
  probing is the cheapest migration of all. (See `harpyja/eval/reconcile_probe.py`
  `RECONCILE_PROBE_OUTCOMES` `{native-api-chat, v1-variant, still-blocked}` /
  `load_committed_reconcile_probe_result`, `specs/0038-reconciliation/probes/probe_result.json`
  (outcome `v1-variant`) pinned by `test_reconcile_probe_result.py`,
  `harpyja/scout/explorer_backend.py` `_default_model_call`, spec 0038 AC1/AC2.)
- A **load-bearing guarantee whose mechanism is EXECUTABLE-BUT-NOT-STRUCTURAL carries
  its proof in a loud-validated shape, NAMES its residual risk, RETAINS a
  model-independent floor, and is labelled exactly "executable + reviewable" — never
  "structurally enforced."** When the honesty crux of a measurement cannot be enforced
  by construction (e.g. a two-model blind leakage protocol: one model authors a query
  with the answer withheld, a separately-invoked verifier judges leakage), do NOT dress
  it as a structural proof or a human honor-system attestation. (i) Carry the proof in a
  LOUD-VALIDATED record (`author_model` / `verifier_model` / input hashes /
  verdict∈{clean,leaky} / outcome∈{kept,reauthored,dropped} + aggregate null-provenance
  counts), NEVER prose. (ii) Operationalize the "is-the-skip-actually-skipping" check as
  a concrete assertion (`assert_author_input_blind`: the recorded author input contains
  NONE of the withheld gold content), not a bare claim. (iii) Distinguish STATE-level
  independence (separate invocation — real + checkable) from CAPABILITY-level (the
  verifier catching every leak the author is prone to — NOT bought by separate
  invocation), recommend author≠verifier family, and record overlap with any subject.
  (iv) NAME the residual risk (model CIRCULARITY: author/verifier/subject sharing a
  correlated blind spot that does not cancel), symmetric to the representativeness gap.
  (v) RETAIN a model-independent floor CO-PRIMARY (paired within-case cancellation for a
  relative instrument — the defense that survives the circularity), never demoted to a
  backstop. The verdict is DATA (leaky → re-author/drop, counted), never a silent gate.
  (See `harpyja/eval/authoring_provenance.py` `AuthoringRecord` /
  `assert_author_input_blind`, `harpyja/eval/terse_authoring.py`, spec 0026 AC2.)
- An **OFFLINE operator/dev authoring/generation tool may live IN the eval harness but
  is AST-GUARDED as non-product** — the same out-of-air-gap posture as the 0010 network
  `convert`/`provision` stages. Its model invocations are INJECTED callables (the
  operator's cross-model seam), NEVER the product `ModelGateway`, and the boundary is
  pinned by an ast import-absence guard (the module does not import the gateway, and no
  `harpyja/server`|`harpyja/orchestrator`|`scout/wiring` runtime module imports the
  tool) — the same executable-guard-over-grep discipline as the deletion-absence tests.
  A dev-time generator that could quietly acquire a product dependency is exactly the
  drift this prevents. (See `harpyja/eval/terse_authoring.py`
  `test_authoring_module_is_not_product_runtime`, spec 0026 AC2 layer (b).)
- A **pre-registered pilot POWER-GATE (frozen + hashed config) STOPs before spending the
  full authoring/collection cost, and its flip-signal EXCLUDES noise flips.** Extends the
  0023 "pre-registered decision config is a frozen object, the verdict a total pure
  function" rule with a cost-ordering: when the full set is expensive to build and its
  power is not assumed (a near-zero base rate makes flips noise), author a small pilot
  first, run it through two pre-registered reference arms, project the SIGNAL-BEARING
  discordant rate to full size, and emit a typed `UNDER_POWERED_STOP` below the committed
  floor rather than building a set to rank noise. A discordant pair is SIGNAL-BEARING
  ONLY when at least one arm is a genuine success (here: a correct localization — the
  arms disagree on whether they LOCATED); a both-failed flip (empty↔wrong-file) is noise
  and does not count. The STOP is a valid typed deliverable that NAMES the upstream next
  step, not a rerun-until-it-passes loop; the frozen+hashed config is what makes it a
  legitimate close rather than a tuned-until-favorable result, and its "located"
  predicate reuses the scoring oracle's own success buckets (one-oracle reuse). (See
  `harpyja/eval/ac8_pilot.py` `PREREGISTERED_AC8_CONFIG` / `is_signal_discordant` /
  `decide_ac8` / `Ac8Outcome`, spec 0026 AC8.) A stale freeze whose reference arm is
  UN-SERVABLE on the live stack is re-registered as a NEW frozen+hashed config with only
  the arm identities swapped and every threshold verbatim, committed BEFORE the pilot
  fires — never a silent substitution under the old hash. (See
  `PREREGISTERED_AC8_CONFIG_0036`, spec 0036.)
- A **projection that GATES an expensive run is labeled by its EPISTEMIC KIND — an
  upper-bound feasibility check is NOT a power estimate, and the label lives in the
  config, the code, AND the committed claim.** When a cheap pre-check projects an
  achievable signal from a PROXY signal, name honestly what the proxy can and cannot
  support: a projection built from a *cross-model* capability contrast (the 0036
  pilot's 14b-vs-4b discordance) can BOUND but cannot ESTIMATE a *within-model* effect
  (the 0039 think-on/off flip rate), so it is a `projection_kind="upper-bound-
  feasibility"` field, not a probability. Compute it generously (every located case
  assumed to flip) — if even the generous ceiling cannot clear the frozen floor, the
  `UNDER_POWERED_STOP` is unimpeachable; if the ceiling clears, the gate PROCEEDs and
  the real power is measured live, never inferred from the bound. Labeling a bound as
  an estimate is the same false-capability class as a `has_citations→CORRECT` proxy (a
  projection reading as a measurement); the honest label is what makes the typed stop a
  legitimate close rather than a guess. (See `harpyja/eval/think_ab_precheck.py`
  `ab_power_precheck` `projection_kind`, `specs/.archive/0039-thinking-ab/claim.json`
  `precheck.projection_kind`, spec 0039 AC5.)
- A **per-pair arm-distinctness guard is DELIBERATELY ASYMMETRIC by which arm shows the
  aberrant signal — the same "arms look alike" observation has OPPOSITE dispositions,
  and the asymmetry rationale is stated so no one "fixes" it into symmetry.** Extends
  the 0037 generation-level-proof rule from the pre-run probe to LIVE per-pair
  validity: in a paired on/off A/B, an OFF arm showing the on-arm signal (reasoning
  present) is an instrument DEFECT (the knob failed on that pair) → the pair is
  excluded-and-recorded, and an exclusion rate above the frozen ceiling trips
  CONFOUNDED; an ON arm showing NO signal (zero reasoning) is LEGITIMATE behavior of
  the shipped default → the pair is KEPT, because excluding it would bias the sample
  toward cases where the treatment fired, which is not the shipped contrast the
  downstream decision needs. The second factor (a budget-indistinctness check) is a
  frozen per-case-aggregate predicate that bites ONLY in the hidden-treatment signature
  (the on arm genuinely worked yet the off arm burned an indistinguishable budget),
  never collapsing back to single-factor field-presence and never misfiring on a
  legitimate small delta on an easy case. The asymmetry is a one-line docstring
  rationale in the module; a symmetric "both arms must differ" rewrite is the wrongful
  fix this text exists to prevent. (See `harpyja/eval/think_ab.py`
  `classify_pair_validity` / `factor_b_min_on_reasoning_chars`, spec 0039 AC3.)
- A **gate whose whole purpose is to prevent a wasteful/steer-able expensive run
  carries NO force/bypass parameter — the escape hatch IS the post-hoc steering the
  gate exists to close.** When a pre-check gates a costly live run (a paired A/B, a
  full authoring pass) on a frozen-config projection, the runner takes no `force=` /
  `skip_precheck=` argument: the only sanctioned way past a typed stop is to change the
  committed EVIDENCE (enlarge the pool, re-run the pre-check) and let the gate flip,
  not to override the verdict at call time. An override parameter would let an operator
  spend the budget the gate protects on a favorable-looking whim, exactly the
  tuned-until-it-passes loop the freeze-before-run discipline forbids; the PROCEED
  branch is built to AUTO-ACTIVATE on the evidence flip, so no bypass is ever needed.
  (See `harpyja/eval/think_ab_run.py` `run_ab_paired` (precheck-gated, no force
  param), spec 0039 AC6.)
- A **live-measurement driver must have EXCLUSIVE use of the model endpoint for the
  run's duration, and a contaminated run is invalidated OUTCOME-BLIND at RUN
  granularity — never per-suspicious-cell.** *(Amended by spec 0041, below: the
  SHOULD-check became a HARD GATE, and invalidation is boundary-granularity when
  per-check records exist — run-granularity remains the rule when they don't; the
  outcome-blind criterion is unchanged either way.)* A shared Ollama silently converts
  environment latency into FAKE capability observations two ways at once, which are
  NOT competing explanations: (i) a concurrent live-calling workload (a pytest suite
  launched without `-m "not integration"`, whose live tests QUEUE requests and TOUCH
  other model tags) and (ii) the dev Ollama's infinite keep-alive PINNING those tags
  resident (`expires_at` ~2318 / `keep_alive=-1`) — suite traffic touching a tag is
  what pins it, and the resident set squeezes the model under test on a memory-bounded
  box, so wall-clock expiries record as honest `empty` buckets and HTTP timeouts type
  `model-unreachable` (spec 0040 run 1: `qwen3:14b` collapsed to 0 located vs 0036's
  5/10 on the SAME cases, under 14.3 GB of pinned co-residents on a 32 GB box). Two
  rules travel with this: a driver preflight SHOULD check `/api/ps` for foreign pinned
  residents and refuse/warn, and it evicts co-resident tags per model block
  (`_evict_other_models`) so a block runs on an un-squeezed box; and NEVER run the test
  suite (or any live-calling workload) concurrently with a live measurement run. When
  contamination is detected, invalidate by the criterion "recorded during the
  contaminated environment" (EVERY cell of the run, including the located ones), NOT
  "cells whose outcome looks wrong" — the latter is exactly the post-hoc steering the
  outcome-blind discipline forbids: archive the whole run (`*.run1-contaminated.json`,
  retained beside the clean re-run) and re-run fresh. The clean re-run restoring the
  prior-spec profile is what validates the diagnosis. This composes with the
  bounded-degrade rule (clean cells are NEVER re-run on suspicion; a typed degrade gets
  exactly ONE bounded re-run, the 0036 posture). (See `harpyja/eval/pool_pilot.py`
  `_evict_other_models` / `_cell_needs_run`,
  `specs/0040-pool/pilot/pilot_results.run1-contaminated.json`, spec 0040 T17/T18.)
- The **exclusive-endpoint check is a HARD GATE with a recorded, honestly-labeled
  strength — refuse, don't warn; no bypass exists; the claim never exceeds what
  `/api/ps` can show** (spec 0041, mechanizing the 0040 lesson before the
  enlargement/bake-off can re-pay it). The live driver checks `/api/ps` (loopback-
  asserted FIRST — the same egress class as `/api/tags`, the 0019 rule) BEFORE the run
  and BEFORE EACH model block; a foreign resident (the PINNED predicate: a resident tag
  NOT in the frozen config's model set — the driver's own block loads never
  self-trigger) is the typed stop `exclusive-endpoint-contended`, non-zero exit, zero
  cells; `run_gated_pool_pilot` takes no force/bypass parameter (signature-introspection
  pinned, the 0039 posture — the only sanctioned unblock is changing the environment).
  EVERY check (result + timestamp) rides the run-level ledger (`0041/pilot/2`,
  version-gated: the new version REQUIRES the proof, legacy `0040/pilot/1` validates
  unchanged — run-level, deliberately NOT the per-case verifier artifact, dodging the
  dual-seam class) under `exclusivity_check_kind: start-plus-per-block` with TWO named
  unseeable residuals: the intra-block window and SAME-TAG contention (`/api/ps` lists
  resident models, not queued requests — a contaminator on a tag inside the frozen set
  passes every check; carried by the opt-in test default, stated in the artifact, never
  implied covered). A failed per-block re-check types every cell since the last clean
  check `suspect` — boundary-granularity, outcome-blind, observations retained; suspect
  is the THIRD `_cell_needs_run` branch (re-runnable ONLY after a subsequent clean gate
  check; clean never re-runs, typed degrades keep one bounded re-run). Reload-churn
  attribution is the pinned two-condition predicate (NEW vs the committed 0040 clean-run
  degrade profile AND an observed `expires_at`-reset marker), never a close-time judgment
  call. (See `harpyja/eval/exclusivity_gate.py`, `harpyja/eval/gate_run.py`,
  `specs/0041-gates/gate/gate_proof.json` + `.contended.json`, spec 0041 AC1–AC3/AC8.)
- **Live integration tests are OPT-IN, not opt-out, and the opt-in has a NAMED
  EXECUTABLE consumer** (spec 0041 — the 0040 contamination was a plain `pytest -q`
  firing live tests at the measurement endpoint). The committed default
  (`pyproject.toml` `addopts = ["-m", "not integration"]`) deselects live-marked tests;
  the documented opt-in is `uv run pytest -m integration` (strict:
  `HARPYJA_REQUIRE_LIVE_STACK=1`). The consumer is MECHANICAL, never documentation-only:
  `assert_live_optin_selection` proves via `pytest --collect-only` that the opt-in
  reaches a non-zero live suite AND the default selection contains zero live-marked
  tests — raised loudly on either failure (a deselect default whose live suite silently
  rots into never-running is its own failure) — and the operator gate driver runs it in
  preflight before any live traffic. (See `harpyja/eval/live_test_selection.py`,
  `harpyja/eval/test_deselect_default.py`, `specs/0041-gates/gate/run_gate.py`, spec
  0041 AC6.)
- **Residency bounds are DRIVER-SCOPED and probe-proven — the production request body is
  not the seam, and sent ≠ honored applies to the hygiene knob itself** (spec 0041; the
  0037 lesson pointed at this spec's own mechanism). The dev host pins every touched tag
  (`keep_alive=-1`, `expires_at` ~2318); the fix is a native-API bounded touch FROM THE
  DRIVER (the seam where `_evict_other_models` already lives), never a `keep_alive`
  field on the SUT's `/v1` call — the 0034/0038 byte-identical pin
  (`explorer_think=None ⇒ params == {max_tokens: 2048}`) survives VERBATIM, and an
  ast-sweep guard (`test_sut_boundary_residency.py`) rots false on any leak of
  `keep_alive`/`/api/ps` into `gateway/`/`scout/`/`deep/`. Whether the touch re-bounds a
  pinned model was PROBED, not assumed: the committed `0041/residency-probe/1` artifact
  (judged ONLY from `/api/ps` `expires_at` movement; the validator re-judges the
  recorded evidence and rejects self-contradiction) typed **`touch-rebounds` live**
  (expires_at 2318 → now+300s), so the touch is the primary mechanism and
  `_evict_other_models` stays defense-in-depth; the wiring tripwire
  (`assert_residency_wiring_matches_committed_outcome`) FAILS loudly on any
  wiring↔evidence drift, never skips. The bound value (300 s at probe time) is pinned by
  the consuming run spec's frozen config, tuned ≥ a block's cadence (a too-short bound
  converts memory-squeeze into timeout churn — the AC8 attribution predicate exists for
  exactly that regression). (See `harpyja/eval/residency_probe.py`,
  `specs/0041-gates/residency_probe/probe_result.json`, spec 0041 AC4/AC7.)
- A **pre-check whose pinned pilot set sits EXACTLY at a derived coverage minimum has
  zero slack — pin coverage HEADROOM above the boundary, because any single
  environment degrade then forces the under-powered verdict.** A `MIN_PILOT_*_COVERAGE`
  minimum derived from the consuming arithmetic (spec 0040's `15 − c < 8` ⇒ `c ≥ 8`, the
  vacuity boundary at which a verdict would rest on majority-unobserved mass) is the
  FLOOR, not the target: a pilot set pinned at exactly the minimum (8 conceptual vs
  min 8) forces `INSUFFICIENT_PILOT_EVIDENCE` on the first per-case degrade, and typed
  per-case degrades at the attempt cap are a real, recurring cost on heavy repos (the
  binding constraint is per-case timeout sensitivity — 240 s wall / 300 s HTTP, a large
  context window amplifying prefill cost — ahead of model capability). Pin the pinned
  set ABOVE the boundary so the derived minimum survives the expected degrade rate. (See
  `harpyja/eval/pool_precheck.py` `MIN_PILOT_CONCEPTUAL_COVERAGE`, spec 0040 findings
  Finding 1 / secondary finding.)
- **When a pre-check HAS direct per-case cross-arm pairs, pin TWO separate quantities —
  a true CEILING and a labeled point ESTIMATE — never one number wearing the wrong
  epistemic label.** This is the successor to the 0039 upper-bound-only rule (which had
  ONLY a cross-model proxy and so could pin only a ceiling): with direct per-case pairs
  `(case_id, a_bucket, b_bucket)`, pin (1) the CEILING = extrapolated per-case
  UNION-located count (`projection_kind="upper-bound-feasibility"`, a TRUE bound because
  `is_signal_discordant` requires ≥1 located arm by its own definition — one-oracle
  reuse justifies the bound), which gates the `UNDER_POWERED` stop and is the ONLY
  quantity the stop-quality claim may rest on; and (2) the OBSERVED signal-discordance
  through the same oracle (`estimate_kind="point-estimate"`), which splits
  `TOO_CLOSE`/`FEASIBLE` as a reportable closeness finding. The split resolves the
  conflation in BOTH directions: extrapolating observed discordance and labeling it a
  bound is an epistemic mislabel (a false `UNDER_POWERED` from sampling noise while the
  artifact claims unimpeachability), and a literal max-possible bound over the unpiloted
  cases is vacuous (unobserved mass alone clears the floor, making `UNDER_POWERED`
  structurally unreachable). NEVER compute either quantity from MARGINAL locate-counts:
  6/7 vs 5/7 is identical whether the located sets fully overlap (`TOO_CLOSE`) or are
  nearly disjoint (discordant) — union-located and discordance are per-case properties
  marginals cannot recover, so a counts-identical/overlap-different fixture pair must
  yield DIFFERENT verdicts and the two quantities must differ on a fixture where the
  models locate overlapping-but-discordant sets. (See `harpyja/eval/pool_precheck.py`
  `union_located_ceiling` / `observed_discordance` / `build_pair_cases`, spec 0040
  AC5. Contrast `harpyja/eval/think_ab_precheck.py`, which pins only the ceiling because
  it lacks within-model paired flips.)
- A **multi-model preflight returns exactly ONE value of a committed enum under a
  committed PRECEDENCE, with a DELIBERATE asymmetry by exclusion power stated in the
  artifact so it is never "fixed" into symmetry — and serving is re-probed PER MODEL,
  never assumed from a sibling's or a prior spec's evidence.** Enumerate the total
  answer space before any probe (`UNSERVABLE` / `COHERENCE_FAIL` / `TOOL_CALL_MALFORMED`
  / `THINK_CONTROL_NOOP` / `PASS`), and — because a model can exhibit two failures at
  once — commit a tie-break precedence (`UNSERVABLE > COHERENCE_FAIL >
  TOOL_CALL_MALFORMED > THINK_CONTROL_NOOP > PASS`, cheapest/most-fundamental first) so
  "exactly one value" is not implementer choice; an INDETERMINATE probe (a control whose
  effect cannot be adjudicated under the tiny-cap discriminator) maps to the conservative
  `THINK_CONTROL_NOOP`, stated in the enum so the probe cannot stall outside the
  committed space. The asymmetry is load-bearing: the fundamental failures are EXCLUDING
  (the model produces no capability number — the 16B-gibberish lesson) and MUST carry an
  `exclusion_reason`; `THINK_CONTROL_NOOP` is RECORDED-NON-EXCLUDING (the model still
  bakes off default-on, only barred from a future thinking-arm) and MUST NOT — a
  validator enforces both directions. Serving is model+version specific (the 0037/0038
  lesson): a control proven on one model/generation (`reasoning_effort` on `qwen3:14b`
  `/v1`) is RE-PROBED per model under the 0038 tiny-cap two-factor discriminator, never
  carried over — an incumbent model's prior-spec history is re-confirmation evidence, not
  a preflight pass, and an anchor model's failure voids EVERY pair containing it with a
  typed `PAIR_NOT_EVALUATED_MODEL_EXCLUDED` (absence is never a disposition). (See
  `harpyja/eval/pool_precheck.py` `PreflightOutcome` / `PREFLIGHT_PRECEDENCE` /
  `adjudicate_preflight` / `is_excluding`, `harpyja/eval/pool_pilot.py`
  `run_model_preflight`, `specs/0040-pool/preflight/preflight_result.json`, spec 0040
  AC2/AC3.)
- A **pre-registered selection or eligibility rule may be AMENDED only while still
  OUTCOME-BLIND — before any authored/measured output is seen — and the amendment is
  RECORDED with the trigger that forced it.** Spec 0036 added a blind-ELIGIBILITY
  precondition (a case whose issue text NAMES the gold-span path cannot be blind-authored
  at all → SKIPPED AND RECORDED, exclude-and-count, never silently dropped) and upgraded
  the leakage verdict parser to FAIL-CLOSED explicit-statement parsing after a live
  ambiguous verdict — both decided query-blind and recorded in the committed operator
  script. An amendment made after outcomes are visible is steering, not refinement. (See
  `specs/0036-terse-query/authoring/run_authoring.py` docstring, spec 0036.)
- A **committed CLAIM artifact is TEST-PINNED to the computed truth it claims.** A static
  test re-derives the claimed values from the data at test time, so a claim file (a
  representativeness/power report) can never silently drift from what the set actually
  contains. Spec 0036's `full_set_report.json` (including
  `representative_at_frozen_target: false`) is pinned by
  `test_committed_full_set_report_matches_computed_truth` — the under-powered finding
  cannot be quietly edited to read representative. (Spec 0036 AC7.)
- **Under-powered-at-the-frozen-target is a RECORDED finding, never a re-derived
  target.** When a natural pool cannot reach a pre-registered `full_n_target`, the result
  is recorded (`meets_full_n_target: false`, `representative_at_frozen_target: false`) —
  NOT papered over by lowering the target, which is the post-hoc steering the freeze
  exists to prevent. Sizing UPWARD post-PROCEED is permitted; re-deriving the target down
  is not. Enlarging the pool is a SEPARATE audited convert step of its own. (See
  `harpyja/eval/terse_dataset.py` `meets_full_n_target`, spec 0036 Finding 1.)

- A **load-bearing LIVE acceptance criterion blocked by a DOWNSTREAM/model factor ships
  the proven part and records the AC as a HOLD via an `xfail`-that-flips-to-`xpass` naming
  the follow-up — never a skip, and never read as the capability finding it superficially
  resembles.** When a live proof cleanly establishes the fix this spec scopes (map removal,
  proven) but a SECOND, distinct blocker prevents the load-bearing measurement (the model
  ran away generating and degraded `model-unreachable` before it could localize), draw the
  close-vs-hold boundary BY CAUSE: `model-unreachable ≠ "can't localize"` — a degrade that
  masks the outcome is NOT a capability result (the 0026 degrade-masks-outcome trap). Ship
  the proven part, and encode the blocked AC as a non-strict `@pytest.mark.xfail` whose
  reason NAMES the follow-up: it skips with no live stack (CI-safe) and flips to `xpass`
  when the follow-up lands — a self-un-holding signal, superior to a bare skip (which can
  silently pass forever) or a red-fail (which blocks CI on infrastructure this spec does
  not own). The follow-up it names is stated at the right SCOPE — a BLOCKING PREREQUISITE
  for downstream work (the 0026 re-run, the bake-off, any localization measurement), not
  cleanup — with its first evidence recorded (`/no_think`+cap = 13.2s vs 180s runaway).
  (See `harpyja/eval/test_harness_live.py` `xfail`, `specs/0027-harness/operator-run-findings.md`,
  spec 0027 AC5/AC6.)
- A **correction to an already-COMMITTED record gets an executable/asserted consistency
  check at close, across EVERY surface that carried the error — not a one-line note — because
  a mis-correction that half-reverts is worse than the original error.** When a factual
  overreach was shipped into multiple committed artifacts (spec AC7 + a committed RCA's
  Impact + an operator-run-findings note all claimed 0020–0023 were "likewise confounded"),
  the fix is scoped to exactly what the evidence supports (0026-ONLY: `build_context_map`
  is net-new in spec 0024, so pre-0024 specs ran a now-retired backend that never touched
  it — moot, NOT "confounded") and VERIFIED consistent across all three surfaces at close
  (all 0026-only, zero residual "confounded" claims), not merely amended in one place. An
  over-broad correction that re-implicates the innocent cases re-introduces the exact error
  it claims to fix; an inaccurate correction is worse than none. (See spec 0027 AC7 / T14,
  the `0fdcb57` narrowing of `specs/0026-eval/rca-explorer-context-bloat.md` +
  `operator-run-findings.md`.)
- A **model-driven loop that emits N PARALLEL tool_calls in one turn ANSWERS ALL N in EMITTED
  ORDER**, each with its own `tool_call_id` — never only `tool_calls[0]`. Answering a subset
  leaves an unanswered `tool_call`, a malformed conversation per the OpenAI tool protocol that
  derails the model into a next-turn runaway (spec 0028 operator-run diagnosis: N=4 parallel
  calls with only [0] answered → turn-2 runaway, measured FULL-echo-1-answered → finish=length
  101s vs all-answered → 0.8s clean). Three rules travel with the batch: (a) a TERMINAL action
  (`submit_citations`) at ANY position returns immediately — remaining calls in the batch are
  NOT executed; (b) a non-floor per-call failure is recorded as an in-conversation,
  model-visible, NON-terminal marker (`'tool-call-degraded:execution-error: <Type>: <msg>'`)
  and the batch CONTINUES — this is deliberately DISTINCT from the terminal `ScoutUnavailable`
  cause taxonomy (`scout-degraded:<cause>`) and is NOT counted in the report; (c) FLOOR
  exceptions (`RipgrepMissingError` / `AirGapError`) are re-raised, never degraded, so a floor
  still floors the tier. N calls = ONE model turn (`turns_used` increments per model_call, not
  per tool_call), so the turn budget is unaffected. (See `harpyja/scout/explorer_loop.py`
  `_answer_tool_call` + the tool_calls loop in `run_explorer_loop`, spec 0029 AC1/AC4.)
- **A mid-loop MESSAGE INJECTION (a gold-blind, evidence-conditioned nudge) lands ONLY at a
  COMPLETED tool-result batch boundary — after the batch's final tool message, before the next
  model call — never interleaved inside an answer-all-N batch, and it rides `messages` ONLY.**
  When an evidence-conditioned nudge cannot ride turn 0 (the evidence does not exist yet), the
  loop appends the nudge mid-run — but injecting BETWEEN an assistant `tool_calls` message and
  its N tool responses is the exact malformed-conversation class the 0029 answer-all-N rule
  fixed, so the injection is gated to the post-batch boundary. It fires AT MOST ONCE per case
  with NO turn-count / wall-clock fallback (a turn/time trigger is the 0043 submit-before-verify
  failure mode; conditioning on evidence makes it structurally impossible). Four load-bearing
  properties travel with it: (a) it is `role:user` with an EXACT frozen-config template
  (test-pinned, incl. multi-span wording so the implementation cannot drift into arbitrary
  first-span steering); (b) it is a distinct, NON-tombstoned record kind that SURVIVES
  `scout_history_char_cap` truncation (never displacing citable observations); (c) it perturbs
  neither loop-detection/no-new-span accounting NOR turn arithmetic — it is not a tool result and
  not a model turn; (d) it rides the outbound `messages` list ONLY, so the 0034/0038
  `explorer_think=None ⇒ params == {max_tokens: 2048}` byte-pin survives verbatim (the successor
  `test_params_pin_survives_confidence_nudge`) — the whole SUT delta is predicate + injection, no
  params/prompt-surface change. The gold-blind predicate lives in `scout/` (sees only the
  trajectory); any gold-needing attribution (fired-on-wrong-span) is EVAL-SIDE postflight reusing
  `metrics.span_hit_kind` BY IDENTITY. (See `harpyja/scout/confidence_gate.py`,
  `harpyja/scout/explorer_loop.py` `_answer_tool_call` stash + the post-batch `"confidence-nudge"`
  injection + the `LoopResult.confidence_*` facts, spec 0044 AC2/AC3.)
- **A committed fixture derived from a THIRD-PARTY dataset is pinned by CONTENT IDENTITY — a
  per-case re-derivation from a fresh source snapshot asserted byte-identical to the committed
  bytes — NEVER by the library's incidental fingerprint.** A HuggingFace `datasets`
  `_fingerprint` is a cache/transform-state token that changes across datasets-lib versions and
  cache states even for byte-identical content — it is NOT the dataset's content revision, and
  pinning against it rots false on a benign environment change (the original SWE-bench convert
  mislabeled `_fingerprint` as `hf_revision` and would have flagged spurious drift). The
  drift-guard instead RE-DERIVES each already-pinned case from the freshly-loaded snapshot and
  asserts it byte-identical to the committed fixture, STOP-AND-WARN on a real content change or a
  now-missing pinned case; the observed fingerprint is recorded as INFORMATIONAL provenance
  (`source_fingerprint_observed` / `source_fingerprint_frozen`), never as the gate. This is
  strictly stronger than a fingerprint check (it verifies the bytes the fixture actually depends
  on) and is the eval-fixture twin of the derived-artifact self-authentication rule (a sidecar
  fingerprint over the data's own bytes, not its producer's identity). (See
  `harpyja/eval/swebench_eval.py` `assert_pool_append_preserves_existing_labels` +
  `line_sha_map`, `swebench_verified.provenance.json` `source_fingerprint_*`, spec 0047 T11/T20.)
- **When a SHARED committed fixture is ENLARGED, snapshot the prior state and REDIRECT the
  historical drift-guards to the snapshot via their pure cores — never rewrite the historical
  claim against the grown fixture.** A fixture shared across specs (e.g. the terse eval set) is
  pinned by earlier specs' drift-guards that RECOMPUTE a historical claim from the LIVE fixture;
  enlarging the fixture would break those recomputations, and editing the historical claim to the
  new numbers would silently falsify what the earlier spec actually measured. Instead commit a
  point-in-time snapshot of the pre-enlargement state (`pre_enlargement_terse_snapshot.jsonl`) and
  repoint each historical guard to LOAD the snapshot through the SAME pure projection core the
  live path uses (`ab_power_precheck`-style), touching zero live loaders — so history is preserved
  EXACTLY and the live pool is free to grow. This is the fixture-level application of the
  migrate-before-you-delete / claim-pin discipline: the old claim keeps its old evidence, the new
  work runs on the enlarged live surface, and neither perturbs the other. (See
  `harpyja/eval/test_terse_floor.py` / `test_think_ab_precheck.py` / `test_think_ab_claim.py`
  redirected to `specs/0047-enlargement/pre_enlargement_terse_snapshot.jsonl`, spec 0047 T20.)
- **A schema guard cannot catch a PLAUSIBLE-BUT-FABRICATED label — audit a hand-eyeballed SAMPLE
  of any authored/model-produced dataset before committing it.** A well-formed value that PASSES
  every schema/enum/hash check can still be semantically wrong when a label is produced by a model
  plus fabricating driver code: spec 0047's driver set `concept_span = gold` for every "divergent"
  concept-vs-patch verdict — a self-contradiction (concept == patch IS "same") that validated
  cleanly and was caught ONLY by a 20-case `audit_sample.json` eyeball, then fixed deterministically
  (fabricated-divergent → the conservative substantiable `same` default; the model's opinion
  retained as ADVISORY provenance for a future repo-aware pass). Emit a bounded audit sample
  alongside any authored fixture and inspect it; a label whose correctness needs evidence the
  labeler cannot access (here a repo-aware distinct concept span) is tagged to the DEFENSIBLE
  default, not fabricated, and the gap is recorded as a named limitation. Keep the load-bearing,
  DETERMINISTICALLY-computed axis (0047's reachability, 44/9 — the `RETRIEVAL_FUNDAMENTAL` confound
  guard) separate from the advisory one so the fabrication cannot contaminate it. (See
  `harpyja/eval/enlargement_authoring.py` `tag_enlarged_row` / `audit_sample`,
  `specs/0047-enlargement/findings.md` tag-quality section, spec 0047 T15/AC3.)
- **A frozen-config RE-FREEZE is LEGITIMATE — not steering — when the instrument STRUCTURALLY
  cannot reach the target under the old constant, provided the relaxation is MINIMAL and its
  derivation is recorded.** The freeze-before-numbers discipline forbids loosening a rule to
  rescue a result, but it does NOT forbid correcting a constant that a hard structural fact makes
  unsatisfiable: 0036's ≤3/repo cap × SWE-bench_Verified's 12 repos hard-ceilings new raw at 36,
  below the derived 96-raw need — the ≤3/repo invariant and the size-to-40-conceptual target are
  mutually incompatible on a 12-repo benchmark. The sanctioned path is to re-freeze to the MINIMAL
  relaxation that makes the target attainable (≤8/repo → 12×8=96 = the derived need), record the
  justification in a `*_derivation` string on the frozen config, mint a NEW config hash
  (`819af2e6…`), and name the accepted cost (per-repo overfit) + the deferred alternative
  (broadening to new repos — a distinct spec). The distinction from steering: the constant is
  changed because the OLD value cannot be met by ANY execution (a structural benchmark fact),
  the change is derived and minimal, and it lands BEFORE the outcome numbers — not tuned toward a
  desired verdict after seeing them. (See `harpyja/eval/enlargement.py` `EnlargementConfig`
  `max_per_repo` / `max_per_repo_derivation`, `ENLARGEMENT_CONFIG_HASH_0047`, spec 0047 OQ3.)
- **A POWERED verdict requires RUNNABLE cases, not merely AUTHORED ones — re-check power
  against the PROVISIONED set before a run is called powered** (spec 0048, the 0047
  correction). A power / discordance-ceiling claim computed over cases that exist only as
  authored rows — no checked-out worktree at the base commit, no resolved audited gold — is
  a PAPER claim: those cases cannot run, so they cannot contribute discordance or coverage.
  0047 typed `POWERED` on 53 authoring-time cases against the THEORETICAL ceiling; when 0048
  attempted the run only 19 were provisioned (34 worktrees + gold unmaterialized), so the
  eligible conceptual N ≤ 15 < the coverage floor of 36 → `PAIR_UNDER_POWERED` on every pair
  — the exact stop the enlargement existed to escape. Necessity (the N-blocker is removed on
  paper) is NOT sufficiency (the cases run). Gate the powered claim on a provisioned-set
  power re-check, and treat authoring-time enlargement as a to-be-provisioned obligation, not
  a runnable pool. (See `specs/0048-bake-off/outcome.md` Blocker 2, spec 0048 AC2/AC7;
  contrast spec 0047's theoretical-ceiling `POWERED`.)

## Trajectory-verified measurement

- **Invisible generation is a measurement-integrity defect: any model-generated stream that consumes budget must be OBSERVABLE in the trajectory artifact** (spec 0034). The 0033-adjacent probes found qwen3:14b on this Ollama emits `reasoning` BY DEFAULT (no `think` param) — invisibly generated, silently dropped by the gateway's return dict, and consuming the `explorer_max_tokens` cap reasoning-FIRST (committed probe A: cap 20 → all 20 tokens to reasoning, zero content, finish=length) — so **every 0031–0033 capability baseline was measured under invisible-truncation RISK and carries an asterisk** (truncation was typed when it fired; the CONSUMER and headroom were unobservable). The fix shape: the gateway surfaces the stream additively (`reasoning`, `completion_tokens` — the cap's actual token currency; chars prove presence, tokens quantify budget); a BACKEND-side per-turn accumulator captures `(reasoning_chars, completion_tokens, finish_reason)` per response — the only seam that sees a `finish="length"` FINAL turn, which never enters the loop history (an intrinsic `per_turn`/`model_turns` length SKEW; consumers must not zip positionally) — never a history-ride, which would mutate the outbound wire messages; the record carries ONE canonical `think_mode` enum (native wins over chat-template on double-set) so two thinking mechanisms can never produce an ambiguous artifact; 0-vs-None pinned (absent stream → None, present-empty → 0, never fabricated). Schema `0033/1 → 0034/1`, version-gated. The knob half (`explorer_think`, tri-state) is OPT-IN control of the already-happening stream — None ⇒ omit ⇒ request byte-identical, pinned on the REQUEST BODY, with the Deep outbound guard extended. (See `harpyja/gateway/gateway.py` `complete_with_tools`, `harpyja/scout/explorer_backend.py` accumulator + `derive_think_mode`, `harpyja/eval/live_verifier.py` `probe_reasoning_default`, specs/0034-reasoning-observability/probes/, spec 0034 AC1–AC5.)
- **Every path-DISCOVERING tool emits REPO-RELATIVE paths, and a path-shape defect is fixed at the ONE engine seam — never per-caller, never by downstream repair** (spec 0033). The 0032 AC6 within-run A/B proved the hazard: scoped `grep` returned SCOPE-relative paths (`rg` runs with cwd=scope, verbatim parse), so a model that cited a scoped hit had it silently dropped at `normalize_spans` — found-then-dropped read as `empty`, penalizing models that grep MORE precisely. The fix is `RipgrepEngine.search(..., repo_root=)` (parse-side re-prefix, mechanism (b): the rg invocation stays byte-identical so ordering/ignore-file resolution can't drift); every shared-engine consumer (explorer `grep`, the `symbols` degraded fallback — a FILE scope, run from the parent dir — and Deep `search`) supplies `repo_root` as DATA while the re-prefix logic lives solely in the engine. `read_span` is excluded from the producer contract (it echoes the caller's path, discovers nothing); `ls` dir entries are repo-relative non-citable trailing-`/` listings. History: spec 0012 built downstream suffix-recovery for exactly this path shape, spec 0025 deleted it as FC-era; 0033 fixes the PRODUCER instead — deterministic reconstruction (the wrapper computed the scope itself), not heuristic repair, which is why re-adding `_recover_suffix` stays banned. (See `harpyja/symbols/ripgrep.py` `search`/`_parse`, `harpyja/scout/explorer_tools.py`, `harpyja/deep/host_tools.py`, spec 0033 AC1–AC4.)
- **A citation drop is counted AT the seam where it happens, and the count rides the verifier artifact — `fc_citation_dropped_count` does NOT measure the explorer's submit-time drop** (spec 0033). There are TWO normalize passes: `submit_citations` → `normalize_spans` (the loop's terminal action — the ONE pass where an explorer citation drops; pre-0033 the count was discarded) and `ScoutEngine.search` → `normalize_spans_with_tally` (re-normalizes the backend's ALREADY-normalized survivors — its `ScoutTally.dropped` → `fc_citation_dropped_count` is structurally ~0 for submit-time drops; scope documented, field byte-untouched). `submit_citations` returns `SubmitResult(spans, submitted, surviving)`; the counts thread `LoopResult` → `ExplorerBackend` → `build_trajectory_record` → the verifier artifact as `citations_submitted`/`citations_surviving` (`VERIFIER_SCHEMA_VERSION "0031/1" → "0033/1"`, version-GATED validator so legacy artifacts still validate), making found-then-dropped `(1, 0)` structurally distinguishable from honest-empty `(0, 0)` — this class can never hide inside an `empty` bucket again. (See `harpyja/scout/submit.py` `SubmitResult`, `harpyja/eval/live_verifier.py` `_KNOWN_VERIFIER_SCHEMA_VERSIONS`, spec 0033 AC5.)
- **One parser, strict-wins: tool-call-name extraction from a trajectory has exactly ONE implementation** (spec 0032). `extract_tool_names` in `harpyja/eval/live_verifier.py` is the canonical parser; BOTH the verify path (`verify_trajectory`) and the live builder (`build_trajectory_record`, called by `ExplorerBackend`) route through it — never a second inline copy (the 0031 T20 divergence: the inline copy silently SKIPPED a nameless tool_call the verify path FAILED, a false measurement waiting for the first downstream consumer of the builder's list). The strict behavior wins: a tool_call lacking `function.name` is a `tool-names-unextractable` typed failure, never a silent skip — surfaced as raised-into-status in the verify path and as DATA (`tool_names_failure` on the record) in the live builder, which must never raise mid-loop. Pinned by an import-identity test (monkeypatch the canonical symbol; only a true delegate observes it) plus a source-audit test that rots false if an inline `seen = set()` name loop reappears. The 0032 OQ2 audit confirmed the other three facts (model identity / tiers_run / terminal bucket) are each single-sourced — tool-names was the only duplicated parse. (See `harpyja/eval/live_verifier.py` `extract_tool_names` / `build_trajectory_record`, `test_live_verifier.py` spec-0032 block, spec 0032 AC1/AC2/AC8.)
- **Every live capability measurement is accompanied by a durable trajectory-verified artifact** (spec 0031). A live run's result is trustworthy only when paired with a **verifier artifact** that **proves** the four facts: (1) model identity (the model that ran), (2) model invocation (Tier-1 was engaged), (3) tool names (which tools were invoked), and (4) terminal outcome (the gold-span classification). The verifier artifact carries a machine-readable `status ∈ {PASSED, FAILED}` and, if FAILED, a precise `failure_reason ∈ {artifact-incomplete, model-unknown, model-mismatch, model-not-invoked, tool-names-unextractable, terminal-bucket-missing}` — deterministic precedence order when multiple facts are unprovable. A live capability claim unaccompanied by the artifact is inadmissible (the no-silent-capability rule applied to measurement provenance). Bind all future live measurement specs (bake-off, eval set, capability reports) to this convention: `harpyja/eval/live_verifier.py` defines `VERIFIER_SCHEMA_VERSION`, the `verify_trajectory` function, the six failure codes, and the `VerifierResult` shape that carries all four facts. (See `harpyja/eval/live_verifier.py`, spec 0031 AC1/AC5/AC7.)

- **A new trajectory-artifact field is threaded into BOTH seams that assemble the record —
  `build_trajectory_record` AND `run_verified_case`'s HAND-ASSEMBLED written artifact — or it
  silently vanishes from the persisted JSON** (spec 0033, recurring 0034 and 0038). The
  in-memory record and the durable written artifact are TWO assembly points: `run_verified_case`
  re-builds the persisted JSON from explicit fields, so a field added only to
  `build_trajectory_record` reaches the record but NOT the file. Every additive field
  (`citations_submitted`/`citations_surviving` in 0033, `per_turn`/`think_mode` in 0034,
  `serving_transport` in 0038) must be wired at both seams and pinned by a WRITTEN-JSON test that
  reads the file back — asserting the record alone proves nothing. History: 0033 DISCOVERED the
  gap on its first live run (unit tests had asserted the record, not the file); 0034 PRE-EMPTED it
  with a written-JSON test authored before the live run; 0038 RE-CAUGHT it mid-close when the
  first live run's `serving_transport` was absent from the artifact — three recurrences make the
  dual-seam threading a standing checklist item, not a per-spec rediscovery. (See
  `harpyja/eval/live_verifier.py` `build_trajectory_record` + `run_verified_case`,
  `test_live_verifier.py` `test_written_artifact_carries_per_turn_and_think_mode` (extended for
  `serving_transport`), spec 0033/0034/0038.)

- **Determinism for a single-draw stochastic comparison is a SERVING precondition, VERIFIED
  by a bucket-level replay probe — greedy gives bucket-reproducibility, NOT bit-identical
  trajectories** (spec 0048). A capability comparison that draws ONE trajectory per model+case
  is only trustworthy if that draw is reproducible; the served models run non-greedy by
  default, and a `qwen3:14b` double-run on astropy-12907 flipped `empty` (found-unsubmitted,
  the 0043 class) vs `right-file-wrong-span` — both runs fully validated, the divergence
  PRECISE not chaotic (both reached the right file; they split only at the terminal
  submit-vs-dawdle action — temp>0 SAMPLING, not batching). Serve GREEDY (`temperature=0`,
  `top_p=1`) as a SERVER-SIDE default — the explorer's outbound params are byte-pinned to
  `{max_tokens: 2048}` (0034/0038), so temperature CANNOT be injected per-request without a
  SUT change the measurement invariant forbids; greedy is a serving precondition (like "the
  tag must be served"), not a SUT mutation. The replay probe compares TERMINAL BUCKETS and
  EXCLUDES a model on flip. Honest limit: residual Ollama numerical/batching nondeterminism
  can still vary the trajectory under greedy (observed: 9 vs 6 tool paths, same `empty`
  bucket) — claim BUCKET-reproducibility only, never bit-perfect; greedy + bucket-level
  exclude-on-flip replay is the sound pairing for the residual. (See
  `specs/0048-bake-off/serving/` Modelfiles + README, `bakeoff_run.reproducibility_replay_probe`,
  `specs/0048-bake-off/outcome.md` Blocker 1, spec 0048 AC1.)
- **Greedy is a relative-ranking CONTROL, not a deployment rate** (spec 0048). Greedy decoding
  separates SAMPLING noise from real policy behavior — a real behavioral defect reproduces
  under greedy (the 0043 found-but-unsubmitted dawdle reappears deterministically), while a
  sampling artifact collapses — so greedy is the right serving mode for a capability
  COMPARISON. But the greedy outcome is NOT the temperature the model would ship at; do not
  read a greedy capability number as a deployment rate. (See `specs/0048-bake-off/outcome.md`
  Blocker 1, spec 0048.)
- **A metric must read the AUTHORITATIVE trajectory source, never a convenience field — the
  uncounted-tool class has now recurred a 3rd time (0040/0042/0048)** (spec 0048, reinforcing
  the one-parser and dual-seam rules above). The verifier writes invoked tools into
  `model_turns` but can leave the top-level `tool_names_invoked` convenience field NULL even
  when tools WERE called; `bakeoff_live.bakeoff_artifact_from_verifier` had trusted that field,
  so it would have recorded `symbols_adopted=False` for every cell and silently zeroed the
  symbols-adoption metric. DERIVE per-tool call counts from the authoritative `model_turns`
  trajectory, cross-checked by IDENTITY against the committed `extract_tool_names` oracle
  (never a re-implementation), and regression-pin the null-field path. Three recurrences make
  "read the authoritative trajectory, not a convenience summary field" a standing checklist
  item for every adoption/tool metric. (See `harpyja/eval/bakeoff_live.py`
  `bakeoff_artifact_from_verifier`, `test_bakeoff_live.py`
  `test_bakeoff_artifact_derives_tools_from_model_turns_when_field_null`, spec 0048 AC6.)

## Speccraft memory & spec-ledger process

- **Every `.speccraft/history.md` ADR header ends with a trailing `(spec NNNN)` provenance
  suffix** (`(specs A, B)` for multi-spec entries). The spec-0024 history parser
  (`history_provenance_ids`) recovers per-decision provenance ONLY from that suffix; without
  it, `consolidate_backfill_order` cannot order by history chronology and silently falls back
  to `created:`-then-ID. Discovered at the 2026-07-09 sync: 24 of 25 live entries lacked the
  suffix (only the 0021 entry carried it). Applies to every new entry; back-annotating old
  headers is optional.
- **Spec frontmatter uses the canonical schema and nothing else**: `id: "NNNN"` (quoted,
  zero-padded), `title:`, `status:`, `started_at_sha:`, `created: YYYY-MM-DD`. Never
  `spec_id:`/`date:` (the 0030 variant, normalized at the 2026-07-09 sync) — alternate keys
  break consolidate-backfill's `created:` ordering and the id parser. A spec's terminal
  `status:` must be flipped at close (`ready-for-operator` left stale on 0031 hid it from
  backfill candidacy).
- **A test that pins committed spec evidence points at `specs/.archive/NNNN-slug/` from the
  moment it is authored — never at the live `specs/NNNN-slug/` path — and every spec close
  ends with a path-pin sweep** (`grep -rn '"specs" / "' harpyja --include='*.py'`; any hit
  not routed through `.archive` is drift). The close flow GUARANTEES the move: consolidation
  relocates the spec dir to `specs/.archive/` at zero conflicts, so a pre-archive path pin is
  a delayed test failure with three observed failure shapes (2026-07-10 sweep, 6 sites /
  5 files): a hard FAIL on clean main (the 0036 `full_set_report` pin — the "1 failed" that
  polluted 0037's close-run suite), a silent ALWAYS-SKIP that permanently disables the
  assertion (the 0036 pilot-ledger integration test — worse than the failure, it looked
  green), and an ERROR-instead-of-skip in conditional tripwire pins whose loader raises on a
  missing file (the 0037 `probe_result` pins, broken by their own spec's close hours after
  being written). Authoring against `.archive` is safe DURING the spec too: the pin test's
  RED phase fails on file-absence either way, and the file lands at the archived path at
  close without a follow-up edit. If evidence must be pinned while a spec is still live and
  unarchived, resolve both locations explicitly — never bare `specs/NNNN-slug/` alone.
  (Discovered closing spec 0037; fixed at `79f7bf2`.)

## Logging

- Use the standard `logging` module. Never log secrets, repo source content, or full file contents at info level. Keep stdout clean on the stdio MCP transport (logs go to stderr).
- A typed-degrade's **visibility** requirement can be satisfied by a **distinct log signal** when a schema field is not (yet) warranted. When a new failure *cause* degrades through an **existing** generic catch and a structured cause-field would be premature, branch the log so the cause is **named, not swallowed anonymously**: the Verification Gate's timeout degrade emits a distinct timeout-naming WARNING (`isinstance(err, (TimeoutError, socket.timeout, URLError))`), separable from the generic "scoring failed", with **no** `GateOutcome` schema change. This is the lightweight tier of the 0014 typed-degrade visibility convention — a *log-level* distinction — reserved for causes the eval harness need not count; a first-class aggregate/`<tier>_degrade_rate` schema field remains the heavyweight tier for degrades that must be measured. (See `harpyja/orchestrator/gate.py`, spec 0017 D4/AC6.) A degrade `except` that branches by `isinstance` to name distinct causes is now a **multi-cause** pattern (spec 0017 timeout WARNING + spec 0018 `ScoreParseError` non-conformance WARNING, each exactly one message, no double-emit). **Ordering is load-bearing: a typed cause that is a SUBCLASS of another caught/branched type MUST be isinstance-checked FIRST** — `ScoreParseError ⊂ ValueError`, so `verify`'s `except` tests it before the generic branch; otherwise the supertype branch catches it, it degrades under the wrong name, and the diagnostic contract (one distinct, correctly-named WARNING) silently breaks. Assert the generic message is **absent** for the typed cause (on the log *record* message, never `caplog.text`). (See `harpyja/orchestrator/gate.py` `verify` except-branch order, spec 0018 D4/AC7.)
