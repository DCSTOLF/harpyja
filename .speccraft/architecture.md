# Architecture

See `ARCHITECTURE.md` (repo root) for the full design and `SPEC.md` for interface contracts. This file is the speccraft-facing summary.

## Layering (packages)

1. `harpyja/server/` — FastMCP app, tool registration, transports (stdio + HTTP). No business logic.
2. `harpyja/orchestrator/` — router, query classifier, verification gate, citation
   formatter. Owns per-request state. Live as of Wave 5 (spec 0008) the `mode=auto`
   ladder is wired and **climbs**: `classify` (`classify_query` heuristic point/broad,
   ambiguous → point, behind a pluggable `Classifier` seam) → `matrix`
   (`plan_ladder` over the 12-row `(mode × classification × index_ready)` planning
   matrix — the **single source of truth** both `_locate_auto` and the tests read) →
   `_locate_auto` executes the planned ladder (seed → Scout → `gate` → Deep), where
   `gate` (`VerificationGate.verify`) reads the cited lines back from disk, scores the
   top-N via an injected `Judge` selected by `settings.verify_method`
   (`select_judge`/`_JUDGE_FACTORIES` co-located in `gate.py`; default `instruct_model` →
   `make_instruct_judge` over the served `lm_model`, an in-distribution 0–1 scorer, spec 0018;
   the OOD `scout_model` finder judge retained non-default as the A/B baseline), routed through
   `ModelGateway.complete`, and decides whether the trailing Tier-2 step runs — so the
   realized `tiers_run` is a prefix of the planned ladder. `wiring.build_verification_gate`
   is the production `gate_factory`. Stable gate flags: `gate-low-confidence` /
   `gate-scoring-failed` / `gate-skipped:scout-empty` / `gate-skipped:no-line-range`
   (spec 0011 — a **file-level**, line-less citation reached the gate: detected
   **before** read-back via `GateOutcome.skipped_reason="no-line-range"`, not scored and
   not a verified pass; `locate.py` escalates if a tier remains in `auto` else carries it
   tagged, never at high confidence — distinct from low-confidence / scoring-failed). The
   Citation Formatter survives a line-less span un-merged (sorted after lined spans on a
   None-safe rank key, no fabricated range). As of spec 0018 (B2 fix) the judge score parse
   is **strict** and **non-fabricating**: `_parse_score -> float | None` accepts only a bare
   `[0,1]` score (an optional `Score:` label / single trailing period tolerated); a line
   number, out-of-range value, or prose returns `None`, and the judge raises a typed
   `ScoreParseError` (a `ValueError` subclass) so the gate's existing `except` degrades
   (`failed=True`) rather than fabricating a `1.0` pass — whole-gate degrade per D7, checked
   in `verify` **before** the generic branch (ScoreParseError ⊂ ValueError) and named with one
   distinct WARNING (no double-emit, distinct from the 0017 timeout WARNING). `_score_or_raise`
   is shared by both judge factories so they degrade identically. `verify_method` now backs
   `lm_model` as a SECOND consumer alongside Deep (Tier 2) — a tune of one retunes the other.
   This is a judging-*mechanism* fix; calibrating `verify_threshold` over the new score
   distribution is the OQ2 re-run. See history.md 2026-07-01 (spec 0018).
3. `harpyja/index/` — file walker, ranked JSONL manifest, incremental hashing.
   Live as of Wave 1: `walk`/`ignore` (pathspec, no `git`), `classify`, `prior`,
   `hash`, `manifest` (atomic same-dir temp + `os.replace`, per-file `degraded`
   field as of Wave 2), `artifacts` (in-repo `.harpyja/` or XDG-cache fallback),
   `indexer` (`(mtime,size)` gate + prune + `--rehash`; Wave 2 also extracts
   symbols on the change-of-record gate and forces a full symbol rebuild on a
   cache integrity / engine-identity mismatch).
4. `harpyja/symbols/` — tree-sitter engines + ripgrep engine behind one `CodeSpan`
   interface (Tier 0). Live as of Wave 2: `RipgrepEngine` (literal `--fixed-strings`,
   bounded); `extract` (defs-only by syntactic form → `SymbolRecord` / `ExtractResult`
   for all 10 grammars — Python, Go, Rust, Java, C#, JavaScript, TypeScript, TSX, C,
   C++; minimal closed kind vocabularies, nested **types** extracted with immediate
   `parent` but function-body-local defs dropped); `symbols_io` (byte-reproducible
   `symbols.jsonl` + self-verifying `symbols.meta.json` sidecar; records-first/meta-last
   `os.replace`); `engine_identity` (runtime + a per-grammar slot via `_GRAMMAR_SLOTS`,
   sentinel-safe cache key; `typescript`/`tsx` coupled under one `tree-sitter-typescript`
   version); `symbol_locator` (`SymbolEngine` — exact case-sensitive name + `.`/`::`
   method addressing, behind the `Locator` protocol). Routing is held in lockstep with
   extraction: `classify.KNOWN_LANGUAGES == indexer.SYMBOL_LANGUAGES`
   (`index/test_routing.py`), so a language is never routed ahead of its rules.
   Remaining symbol follow-up: **Wave-2.1 substring/fuzzy matching**.
5. `harpyja/scout/` — Tier 1 finder. **As of spec 0024 the production backend is the
   native `ExplorerBackend` (below); the FastContext adapter described here remains
   in-tree but OFF the production path, pending a dedicated cleanup spec.** Live as of
   Wave 3: `ScoutBackend`
   Protocol (`run(query, seed) -> list[CodeSpan]`) + `ScoutEngine` (self-seeds its own
   Tier-0 lookup **before** the backend, behind the shared `Locator` `.search` seam) +
   `normalize_spans` (drops/clamps untrusted `<final_answer>` output to the Scout budgets)
   + `build_tool_whitelist` (exact local-only four-tool set) + `FastContextBackend`
   (injected client, no hard import). Wave 4 (spec 0007) supplied the **real default
   client**: `client.py::DefaultFastContextClient` drives Microsoft's FastContext agent
   (`make_fastcontext_agent` — its own Read/Glob/Grep loop, **not** `dspy.RLM`) over two
   paths — Path A in-process (lazy-import the factory; `work_dir=<repo>`,
   `trajectory_file=<temp outside repo>`; `agent.run(..., citation=True)` bridged onto a
   loop-free worker thread `_run_coro_on_worker_thread`; `FC_*` injected from `Settings`
   under a module-level `threading.Lock` `_SCOUT_ENV_LOCK` via the set-then-restore
   `_managed_fc_env`, held across the full run because `FC_REASONING_EFFORT` is lazy-read
   per call) and Path B fallback (injected CLI runner, `FC_*` scoped to the child via
   `env=`). `wiring.py::build_scout_engine` is the production `scout_factory` (mirrors
   `deep/wiring.py`); the `FastContextBackend` tool whitelist is **vestigial for Path A**
   (FastContext owns its own tools) — an honest, recorded limit. Air-gap via
   `gateway.assert_local` on the resolved `FC_BASE_URL` before construct (Path A) / spawn
   (Path B), lock spanning assert→construct→run to close the TOCTOU window; read-only and
   no-egress are assumptions verified by integration test (residual risk recorded). Scout
   is **not cached** (model-backed/non-deterministic, no engine-identity slot). Degradable
   failures carry a stable `ScoutUnavailable.cause` — a **four-way** taxonomy
   (`fastcontext-missing` / `cli-missing` / `connection-refused` / `no-endpoint-configured`
   / `backend-error`), with a deterministic Path-A→Path-B state machine making
   `fastcontext-missing` terminal only when the CLI runner is unwired, and **any**
   unexpected backend exception (incl. FastContext's own post-processing crash) mapped to
   `backend-error`; `RipgrepMissingError` / `AirGapError` propagate as the floor.
   As of spec 0011 the FastContext citation path uses **seam (a)**: Scout invokes the agent
   with **`citation=False`** (Path A `agent.run`; Path B drops the CLI `--citation` flag),
   bypassing FastContext's own `format_citations` (which crashes on bare-path model output),
   and `client.py::parse_final_answer` parses the raw `<final_answer>` text itself, **per
   line, anchored** to the FC grammar `<no-space-path>[:start[-end]] [(explanation)]` —
   `path:start` → a spanned `CodeSpan`, a bare path / malformed line → a **file-level**
   `CodeSpan` (`None` lines, no fabricated range; `_looks_like_path` + per-line anchoring
   guard against incidental prose filenames). `normalize_spans_with_tally` returns
   `(spans, dropped_count)` with a file-level branch (repo-confine + `is_file` + dedup,
   skipping the line clamp; Tier-2/Deep's lined path byte-identical) and a half-`None`
   reject. The per-run text-ref shape distribution rides a side-channel —
   `ScoutEngine.last_tally` (`ScoutTally{spanned, filelevel, dropped}`) — read only by the
   eval harness; the orchestrator's `list[CodeSpan]` seam is unchanged.
   **As of spec 0012** Scout does **path-suffix recovery** before the 0011 drop: when a
   cited path does not resolve in-repo, `normalize.py::_recover_suffix` maps it to a real
   in-repo file by its longest **unique** `≥ MIN_TAIL_SEGMENTS (=2)`-segment suffix
   matched (segment-aligned) against the repo's indexed **manifest file set** — guarded by
   exactly-one-match (ambiguous → drop), the 2-segment specificity floor, and a
   manifest-keyed leading-segment anchor (the matched tail's head must be a top-level
   manifest entry). A recovered path **re-enters** the same repo-confine + `is_file`
   (+ clamp) validation (recovery composes with, never bypasses, 0011's checks) and a
   recovered file-level keep inherits the 0011 `gate-skipped:no-line-range` floor (never
   high-confidence). Manifest absent/empty ⇒ no recovery (graceful degrade to the drop).
   `normalize_spans_with_tally` now returns a **4-tuple**
   `(spans, dropped, recovered_spanned, recovered_filelevel)` + a non-breaking
   `recovered_paths_out` out-param. `build_scout_engine` loads the set via
   `read_manifest(art_dir)` and threads it as `ScoutEngine(file_set=…)`; `ScoutTally`
   gained `recovered_spanned` / `recovered_filelevel` / `recovered_filelevel_paths`.

   **As of spec 0024 the FastContext backend is RETIRED and REPLACED by the
   self-contained native `ExplorerBackend`, behind the byte-unchanged `ScoutBackend`/
   `ScoutEngine`/`Locator` seam** (orchestrator, gate, matrix, formatter, `engine.py`,
   `normalize.py` all untouched). A general OpenAI-compatible tool-calling model is
   driven over a bounded read-only loop to a citation list: `context_map.build_context_map`
   renders a pre-model filtered tree from the manifest (no file bytes; the
   vendor/test/generated exclusion is a DISPLAY concern only, tool scope unaffected);
   `explorer_tools.build_explorer_tools` returns EXACTLY three `confine_path`-guarded,
   Settings-bounded, read-only navigation closures `{grep, glob, read_span}` mirroring
   `deep/host_tools.build_host_tools` — `grep`/`glob` share the SAME `symbols.ripgrep.RipgrepEngine`
   the Deep `search` tool wraps (one bounded rg source of truth), `read_span` reuses
   `server.tools.read_snippet`, `glob` normalizes to file-level `CodeSpan`s bounded by
   `scout_glob_max_paths`; `explorer_loop.run_explorer_loop` runs one tool call/turn
   capped by `scout_max_turns` AND a distinct whole-loop `scout_wall_clock_s` ceiling,
   with deterministic self-recovery (loop-detection on an exact
   `(tool_name, normalized_args)` repeat over `scout_loop_repeat_n` no-new-span turns;
   citation-preserving truncation past `scout_history_char_cap` that drops only stale
   chatter and re-injects a compact dropped-span index — never converting a real find
   to honest-empty); the loop ends via `submit.submit_citations`, a tool-call-native
   terminal action with a STRICT arg schema (`SubmitCitationsSchemaError` on
   unknown/extra/diagnosis-shaped fields — the enforceable locator-not-diagnoser guard)
   normalized via the unchanged `normalize_spans` to `source_tier=1` (this REPLACES the
   0011/0012 `<final_answer>` text-grammar parse path). Model I/O goes through the NEW
   `ModelGateway.complete_with_tools`; `ExplorerBackend` calls `gateway.assert_local()`
   once before the loop starts (air-gap before any I/O), and the gateway asserts loopback
   before its transport. Degradable terminal states carry four distinct
   `ScoutUnavailable` causes — `model-unreachable` / `loop-turns-exhausted` /
   `loop-wallclock-exhausted` / reused `backend-error` — routed to the Tier-0 floor
   (a well-formed empty submission is honest-empty, never a raise; `AirGapError` /
   `RipgrepMissingError` propagate as floors), with the degrade rate a first-class
   reported field. `wiring.build_explorer_scout_engine` is the NEW production
   `scout_factory` (ExplorerBackend over the loopback gateway + shared `RipgrepEngine`
   + context map + explorer tools + the five provisional loop budgets); the FastContext
   `build_scout_engine` factory and its eval callers are left byte-untouched — a PARALLEL
   factory, so the backend swap and the deferred FastContext deletion do not entangle in
   one diff. Live-green: both integration tests pass against Qwen3-8B on loopback Ollama
   (~28s, zero non-loopback egress). See history.md 2026-07-06 (spec 0024).
6. `harpyja/deep/` — `dspy.RLM` explorer (Tier 2), reached only via `mode=deep`. Live
   as of Wave 4: `DeepBackend` Protocol (`run(query, seed, tools) -> list[CodeSpan]`,
   injected, no top-level `import dspy`) + `DeepEngine` (self-seeds its own Tier-0
   lookup **before** the backend; **dual surface** — `.search` for `Locator`
   conformance and `run() -> (citations, truncated_bound)`, since the truncation bound
   is metadata the bare `CodeSpan` list cannot carry) + `DeepBudget` (per-request meter:
   tool-calls / tokens / depth / subqueries / wall-clock + `truncated_bound`) +
   `build_host_tools` (exactly four confined, read-only tools —
   `{list_manifest, search, symbols, read_span}` — each a thin wrapper over Tier-0
   machinery, repo-path-confined via `server.tools.confine_path` and bounded by the
   existing `Settings` clamps) + `DeepRunner` (in-process counter facet + out-of-band
   subprocess `run_isolated` that **hard-kills** on `deep_wall_clock_ms`) + `RlmBackend`
   (`dspy.RLM`, fresh instance per request, air-gap via `gateway.assert_local` on the
   endpoint because the RLM owns its own LM, no top-level import) + `wiring.build_deep_engine`
   (the `deep_factory`). Deep is **not cached** (model-backed/non-deterministic, no
   engine-identity slot, like Scout). Degradable failures carry a stable
   `DeepUnavailable.cause` (`sandbox-absent`/`rlm-down`/`backend-error`/`parse-error` —
   the last a named, narrow-caught dspy `AdapterParseError` at the `rlm(query=...)` seam,
   a sibling of `backend-error` not a replacement, spec 0014); a budget
   truncation is a non-degrade `deep-truncated:<bound>` note; `RipgrepMissingError`
   (seed) / `AirGapError` propagate as the floor.
7. `harpyja/gateway/` — Model Gateway over the local OpenAI-compatible endpoint. Only
   outbound caller. Live as of Wave 3: `ModelGateway.complete()` asserts the air-gap at
   name-resolution time (injected resolver + `ipaddress` loopback predicate) **before** an
   injected transport — no request leaves the process until loopback is proven.
   As of spec 0017 (B3) the single outbound HTTP call is **time-bounded**: `_default_transport`
   passes a finite `timeout=` to `urlopen` (a **per-socket-op** bound — connect + each read —
   not a total deadline), carried by `ModelGateway.timeout_s` (finite dataclass default `120.0`,
   fed by `Settings.lm_http_timeout_s`) and bound onto the default transport via
   `functools.partial` **only when `transport is None`** (the injectable `Transport` signature
   unchanged). A stalled/torn-down local endpoint now **raises instead of wedging the run
   forever**, and the Verification Gate turns that raise into a graceful, timeout-named degrade
   (`gate.py` branches `TimeoutError`/`socket.timeout`/`URLError` to a distinct WARNING, no
   schema change). See history.md 2026-07-01 (spec 0017).
   As of spec 0024 a second gateway method, `ModelGateway.complete_with_tools(messages,
   tools, *, transport, resolver, **params)`, returns `{content, tool_calls}` from
   `choices[0].message` for tool-calling models (the Scout explorer loop) — same single
   outbound abstraction, `assert_local` asserted BEFORE the transport, injectable
   transport exactly like `complete`.
8. `harpyja/config/` — settings load/merge, profiles.
9. `harpyja/eval/` — **measurement harness, not a runtime tier** (a request never
   touches it). Live as of Wave 6a (spec 0009-6a): observes the real `mode=auto`
   `locate()` path and reports locate accuracy, escalation, and gate catch /
   false-escalation; emits an OQ2 `(verify_threshold, verify_top_n)` recommendation but
   flips **no** `Settings` default (recommend-only). `runner.py` (`LocateStack` +
   `build_live_stack` real factories; drives production `locate(...)`, captures Tier-1
   citations independently of escalation) → `metrics.py` (ONE overlap oracle
   `_any_primary_overlap` reused by span-hit + gate catch-rate + false-escalation;
   gate metrics point-subset-scoped, broad excluded; null-with-count on a zero
   denominator) → `config.py` (`EvalConfig` — k_runs / proximity_window_lines / n_floor
   / catch_rate_bar, **field-disjoint from `Settings`**; `aggregate_runs` mean+pstdev) →
   `recommend.py` (D3 variance gate `mean(A)-mean(B) > pstdev(B)` + D4 lexicographic
   OQ2 scorer; incumbent `(0.6, 3)` validated-not-flipped within noise) → `sweep.py`
   (grid via `dataclasses.replace`, never mutation; K runs/point) → `report.py` (pinned
   D7 schema + loud `validate_report` + `atomic_write_json` that refuses to write inside
   the indexed repo) → `dataset.py` (`EvalCase` / loud `DatasetError`) + `live.py`
   entrypoints + `fixtures/` (vendored `legacy/` repo + hand-labeled `seed.jsonl`).
   **As of spec 0010** the package also carries a **SWE-bench Verified adapter +
   multi-repo driver** (`swebench_eval.py`) — still measurement, not a runtime tier.
   Network-staged: `convert` (HuggingFace → portable committed
   `swebench_verified.raw.jsonl`) → `provision` (`git clone` + worktree at
   `base_commit` → gitignored `…resolved.jsonl`) → `prune`; `convert`/`provision` are
   dev-time tools explicitly **out** of the runtime air-gap (the offline `run`/`sweep`
   stages assert zero non-loopback egress). The ground-truth oracle is the
   **standalone-localization protocol** (`parse_patch` derives gold-patch pre-image hunk
   spans — no Docker/patch/test-exec; D-class `classify_by_patch_shape`,
   `POINT_SPAN_MAX_LINES=25`; new-file-only instances flagged + excluded). The per-case
   driver `run_swebench` builds its **own** `LocateStack` per case (one worktree per
   case) and pools into the **unchanged** `metrics`/`recommend` layers + the
   additively-extended report (`SCHEMA_VERSION` `0010/1`, additive defaults centralized
   in `report.py` `_*_DEFAULTS`). **D-route is a recorded evaluation intervention**: the
   driver injects a patch-shape classifier through the `LocateStack.classifier` seam so
   the gate fires, captures the production `classify_query` label first, records both +
   an aggregate `classifier_agreement_rate`, and guards the OQ2 recommendation by an
   `AGREEMENT_FLOOR=0.5` (below it → deltas-only, never a calibration). The committed
   N=50 raw fixture clears `n_floor=30` (38 point / 12 broad); the full live OQ2 sweep
   is an operator opt-in (`make swebench-full`), and **no `Settings` default is flipped**
   (recommend-only, B1) — the flip remains a follow-up spec. The earlier 5-case
   `legacy/` seed remains the small `indicative_only` starter. See history.md 2026-06-28.
   **As of spec 0011** the report schema is `0011/1` (additive degrade-visibility fields,
   centralized last-with-defaults in `_*_DEFAULTS`): aggregate `scout_degrade_count`,
   `scout_degrade_rate` (null-with-count on a zero denominator), `degraded_dominated`,
   composable `reliability_notes`, and `fc_citation_{spanned,filelevel,dropped}_count`;
   run-metadata `degraded_dominated_threshold` (a new **eval-only**
   `EvalConfig.degraded_dominated_threshold=0.5`, field-disjoint from `Settings` — a
   majority-degraded run characterizes the degrade floor, not the SUT). The one overlap
   oracle now classifies a file-level citation as a **path-only** hit via `span_hit_kind`
   (`"line"`/`"file"`/`None`), guarded **before** the line arithmetic in both the primary
   and the secondary oracle; `compose_reliability_notes` is shared by `runner.py` +
   `swebench_eval.py`. **As of spec 0012** the schema is `0012/1` (two additive
   last-with-default fields `fc_citation_recovered_{spanned,filelevel}_count` in the one
   `_AGGREGATE_DEFAULTS` source; legacy `0011/1` blocks still validate), summed in **both**
   `runner.py::aggregate_outcomes` and the `swebench_eval.py` per-case driver. **As of spec
   0014** the schema is `0013/1` (additive `deep_degrade_{count,rate}` twins; `degraded_dominated`
   now keys off the scout+deep per-case **union**, counted once per case).
   **As of spec 0019** the schema is `0014/1` (additive last-with-defaults: run-metadata
   `gate_false_escalation_ceiling`; aggregate `gate_confounded` / `gate_confounded_measured_rate`
   + instruct/scout A/B false-escalation twins, hoisted to one `_GATE_CONFOUND_AGG_FIELDS`
   anti-drift source; legacy `0013/1` blocks still validate). `recommend.py` gains a
   gate-confound DISPATCHER `recommend_oq2` wrapping the unchanged `rank_sweep`: a measured
   instruct-judge false-escalation strictly above the new eval-only
   `EvalConfig.gate_false_escalation_ceiling` (0.20, provisional) emits the `gate-confounded`
   typed null (`OUTCOME_GATE_CONFOUNDED`, carrying the rate) rather than calibrating
   `verify_threshold` over a still-broken judge — wired into `run_swebench_sweep` (best-achievable
   instruct false-escalation = min over measured grid points, instruct-base runs only). A
   setup-time **preflight doctor** (`preflight_models_present` / `PreflightError` / `cmd_preflight`
   + a `preflight` CLI subparser) asserts required served-model tags are **pulled** behind
   `assert_local` (no second outbound path; "pulled" ≠ co-resident-loadable, OOM named as a
   residual risk). SUT frozen — measurement, not construction. See history.md 2026-07-02 (spec 0019).
   **As of spec 0020** the package carries the **OQ2 operator protocol** — the sweep that RUNS the
   0019 instrument, still measurement, not a runtime tier. `oq2_protocol.py::run_oq2_protocol` is a
   sequential four-gate stop-and-report driver (G0 preflight → G1 smoke → G2 gate-quality → G3
   sweep) over injected collaborators, each verdict recorded before the next gate; close-vs-hold is
   split **by cause** (D7) — a SUT-observing outcome (`STOP:SMOKE` / a G3 label) **closes**, an
   environment failure (preflight fail / fixtures absent / G1-sub-check-(a) OOM under co-load) is a
   **BLOCKED hold** naming the fix. `oq2_classify.py::classify_g3_outcome` is a **pure projection
   ABOVE the byte-frozen `recommend_oq2` dispatcher** (which still emits only `recommended` /
   `gate-confounded`), mapping its result + `degraded_dominated` + effective-N to one of
   `{RECOMMENDATION, GATE_CONFOUNDED, DEGRADED_DOMINATED, NOT_SEPARABLE}`, precedence
   **DEGRADED_DOMINATED > GATE_CONFOUNDED > NOT_SEPARABLE > RECOMMENDATION**, all true conditions
   recorded, the no-survivor `S` (`incumbent_validated is False AND advantage_exceeds_variance is
   False`) computed only when `rank_sweep` ran (no phantom `NOT_SEPARABLE`), `indicative_only` a
   RECOMMENDATION-only sub-flag (effective-N < `n_floor`); `recommend_oq2` / `rank_sweep` stay
   byte-frozen. `oq2_ledger.py` is a **new pinned artifact** `LEDGER_SCHEMA_VERSION = "0020/1"`
   (distinct from the sweep report `0014/1`, which is NOT bumped): per-gate verdicts + measured
   sub-values + close/hold cause + G3 label & D/G/S booleans + run provenance, loud
   `validate_gate_ledger` / `LedgerSchemaError`, `write_gate_ledger` reusing
   `report.atomic_write_json` (outside-repo guard single-sourced). `oq2_live.py` + the `oq2` CLI
   subcommand (`cmd_oq2` in `swebench_eval.py`) are the live seam that drives the real G0→G3
   collaborators over the served stack. The live operator run produced a typed **DEFERRED** null —
   G2 unmeasurable (`correct_tier1_count = 0` → `gate_false_escalation = null`) because Scout Tier-1
   is ≈ 0 correct on SWE-bench point cases (verified real, model-independent), so OQ2 gate
   calibration is blocked UPSTREAM on Scout locate accuracy. SUT frozen. See history.md 2026-07-04
   (spec 0020).

   **As of spec 0021** the package carries two additive diagnostic modules from the
   `escalation_rate=0` metric-integrity investigation (still measurement, not a runtime
   tier; the SUT `harpyja/orchestrator/` was read-only reference, NOT modified).
   `escalation.py` is a **pure projection over the byte-frozen `_locate_auto`**:
   `WrongCitationFate` enum {`GATE_FALSE_ACCEPTANCE`, `NO_ESCALATION_PATH`,
   `DEEP_DEGRADED_OR_UNAVAILABLE`, `NOT_APPLICABLE`} + `classify_escalation(*,
   tier1_correct, gate_rejected, deep_available, ladder, tier1_empty=False) -> (will_escalate,
   WrongCitationFate)` — ladders are passed IN (it never re-derives `matrix.plan_ladder`;
   the test derives every ladder BY CALLING it). `escalation_microrun.py` is an additive
   instrumented ≤2-case micro-run (`_wrap_timed` / `build_micro_result` /
   `run_escalation_microrun`) that attributes per-tier wall-clock at the **eval boundary**
   by wrapping collaborators' public `scout_engine.search` / `gate.verify` /
   `deep_engine.search` (restored in `finally`), labelling the split `"estimate"` — no
   orchestrator edit. `test_metrics.py` gained the `tiers_run ⇄ escalation_rate` coupling
   PIN. The recorded typed finding (`specs/.archive/0021-escalation-rate-0/findings.md`):
   `accounting = CORRECT_NO_ESCALATION` (proven — the metric is derived, coupling-pinned),
   `wrong_citation_fate` = 33 empty → `NO_ESCALATION_PATH` (confirmed) + 5 wrong undetermined
   (0020 dump gone); the 0020 secondaries `wrong_tier1_count` / `span_hit_rate_primary` /
   `gate_catch_rate` are flagged CONTAMINATED for the next spec to regenerate. Report schema
   unchanged. See history.md 2026-07-04 (spec 0021).

   **As of spec 0022** the package carries a **Scout locate-accuracy diagnostic**
   (`locate_accuracy.py` + `locate_probe.py`) — still measurement, not a runtime tier;
   the SUT (`harpyja/scout/`, `harpyja/orchestrator/`) is byte-frozen and read-only.
   `locate_accuracy.py` is a **pure projection over the byte-frozen oracle**
   (`metrics.span_hit_kind` / `span_hit_secondary`, untouched): `normalize_citations`
   (reads spec-0012 `ScoutTally` recovery counts, never re-derives suffix recovery) →
   `NormalizedCitations`; a 4-way MECE `LocateBucket` `{EMPTY, WRONG_FILE,
   RIGHT_FILE_WRONG_SPAN, CORRECT}` with strict precedence `CORRECT >
   RIGHT_FILE_WRONG_SPAN > WRONG_FILE > EMPTY` (`classify_case`), carrying the ONE
   deliberate scored re-map (path-only right-file `span_hit_kind=="file"` →
   `RIGHT_FILE_WRONG_SPAN`, NOT `CORRECT` — the file-vs-span diagnostic axis, eval-only,
   guarded by a `SUT_SURFACE` allowlist + a frozen-oracle behavior snapshot);
   `score_distribution` → `LocateDistribution` (file-level acc, span-level acc, and
   first-class `gap = file − span`); and `decide_finding` — an ordered 4-branch rule
   (`BENCHMARK_UNREPRESENTATIVE > PRECISION_FIXABLE > RETRIEVAL_FUNDAMENTAL > MIXED`)
   over pre-declared named bands, all true conditions recorded (0020 pattern).
   `locate_probe.py` is a **Scout-ONLY driver** (no gate/judge/Deep): `stratify_cases`
   (repo × gold-span-size band), `run_locate_probe` (drives `scout_engine.search` only,
   resets `last_tally` per case, REGENERATES the distribution — never inherits 0021's
   contaminated counts), `run_reformulation_probe` (raw-vs-distilled empty-rate delta,
   held OUT of the baseline), turns-used via the public `agent_factory` seam
   (`count_turns` / `counting_agent_factory` reading FastContext's trajectory before the
   frozen client's `os.unlink`, `turns_used_source ∈ {"trajectory","unavailable"}`), a
   tier-scoped `scout_stack_available()` (fastcontext + `rg` + reachable Scout endpoint;
   no Deno, fixing the Deep-oriented false-skip), and a split fail-posture
   (`require_live_stack` + `HARPYJA_REQUIRE_LIVE_STACK`: integration skip-not-fail, the
   deliverable run fails loud). The recorded typed finding
   (`specs/0022-tier-1/findings.md`) is **provisional `RETRIEVAL_FUNDAMENTAL`**
   (empty-dominant, gap ≈ 0 → recall/retrieval failure, not span precision); one branch,
   `BENCHMARK_UNREPRESENTATIVE`, is NOT YET EXCLUDABLE because its reformulation-probe
   discriminator (on real multi-paragraph SWE-bench issue text) and the full 38-case
   distribution are operator-gated (see `specs/.archive/0022-tier-1/findings.md`).
   Report schema unchanged. See history.md 2026-07-05 (spec 0022).

   **As of spec 0023** the package carries the **benchmark-fit discriminator** that
   decides whether 0022's provisional `RETRIEVAL_FUNDAMENTAL` is a real capability wall
   or a `BENCHMARK_UNREPRESENTATIVE` artifact — still measurement, not a runtime tier;
   the SUT (`harpyja/scout/`, `harpyja/orchestrator/`) is byte-frozen and read-only.
   `benchmark_fit.py` is **pure verdict machinery** (no SUT import, no I/O): an exact
   two-sided McNemar from scratch (`math.comb`, no scipy; `mcnemar_exact_p` /
   `mcnemar_rejects`, boundary-pinned 6/0 rejects, 5/0 not, 8/0 rejects, 7/1 not); a
   frozen `PREREGISTERED_CONFIG` (`MIN_DISCORDANT_PAIRS=8` from exact-McNemar
   reachability, `DELTA_EMPTY_BAND=0.20`, `min_n=12`, `alpha=0.05`); `PairedRow` +
   `aggregate_paired` (within-case `delta_empty` / `delta_file_accuracy` + discordant
   `(b,c)` FROM retained pairs, never a difference of aggregate rates); total
   `decide_axis1` (Axis 1 = query shape) with a paired uncertainty gate and three named
   non-overlapping `INCONCLUSIVE` triggers (`INSUFFICIENT_POWER` /
   `DISTILLER_ARM_DISAGREEMENT` / `AXIS_SIGNAL_DISAGREEMENT`); `RepresentativenessRecord`
   + `is_representative` (Axis 2); and total `compose_verdict` encoding a pre-registered
   2×2 where Axis 2 can DOWNGRADE Axis 1's routing (`QUERY_SHAPE×¬representative` → build
   a terse-query benchmark first, NOT a finder swap; `CAPABILITY×¬representative` → retire
   SWE-bench) — the cell names the next spec. `distill.py` is a **dual distiller**:
   `mechanical_distill` (PRIMARY, verdict-driving — a single case-agnostic, gold-blind
   rule whose output tokens are a subset of the issue tokens and which STRIPS code
   identifiers so it is structurally incapable of injecting gold vocabulary; every
   stripped token recorded; pre-registered `MECHANICAL_RULE_HASH`) and
   `llm_distill_guarded` (LABELED non-primary SENSITIVITY arm, an injected `Callable`
   gated by a post-hoc token-subset hard reject `DistillRejected`; pre-registered
   `LLM_PROMPT_HASH`; never decides). `locate_probe.py` is **extended, not rewritten**
   (AC7): `ReformulationResult` gained `paired_rows` / `delta_file_accuracy` /
   `discordant_pairs` / `llm_delta_empty` / `usable_n` / `excluded_case_ids` appended
   last-with-defaults (0022 constructor + callers byte-compatible); new
   `run_paired_reformulation_probe` (within-case paired A/B, per-case pairs retained) and
   `is_raw_issue` (AC8 raw-arm provenance precondition — a non-multi-paragraph case is
   excluded from `usable_n`, so a terse-fixture `delta≈0` cannot masquerade as
   `CAPABILITY`). The instrument is unit-verified (+52 unit) and live-smoke green, but the
   operator VERDICT is deliberately NOT yet emitted: the terse legacy fixtures give
   `usable_n=0` by construction, so firing `decide_axis1` for real needs operator
   SWE-bench long-issue cases (≥`min_n=12` usable, ≥8 discordant) — until then 0022's
   `RETRIEVAL_FUNDAMENTAL` stands and `BENCHMARK_UNREPRESENTATIVE` is not-yet-excluded.
   Report schema unchanged. See history.md 2026-07-05 (spec 0023).

Tiers are adapters behind stable interfaces (`Locator` protocol) and stay stateless/swappable — the Scout engine, Deep engine, judge, and model backend can each be replaced independently.

## Key decisions

- Cheapest-tier-that-works escalation (Tier 0 → 1 → 2), gated by a read-back
  Verification Gate — LIVE as of Wave 5 (spec 0008): `mode=auto` classifies the query,
  plans a tier ladder from the matrix, and the gate decides whether the Tier-1 answer
  is good enough to stop or must escalate to Deep. See ARCHITECTURE.md §2.2 / §2.7 and
  history.md 2026-06-27 (Wave 5).
- Fresh `dspy.RLM` instance per request (RLM is not thread-safe with a custom interpreter) — ARCHITECTURE.md §4.
- Air-gap enforced in one helper, `gateway.assert_local` (loopback = `127.0.0.0/8`
  / `::1` / `localhost`), reused for both the outbound model endpoint and the
  inbound HTTP bind; all other layers are filesystem-only — ARCHITECTURE.md §4.
- Tier 0 (deterministic, model-free) is the floor every later tier is additive on:
  index → (ripgrep + symbols) → citation formatter behind `harpyja_locate`. As of
  Wave 2 it is symbol-aware: a query naming a symbol surfaces its **definition** above
  its call sites via a formatter definition boost, composed from the ripgrep and
  symbol `Locator`s without branching; a no-symbol-match query degrades byte-identically
  to the Wave-1 ripgrep-only result. `rg` on `PATH` is a hard precondition for
  search/locate only (not `index`); a missing/erroring parser, by contrast, degrades
  gracefully (`grammar-missing` / `parse-error`) — symbols are an enhancement, not a
  precondition. See history.md 2026-06-26.
- Tier 1 (Scout) is live and additive on the Tier-0 floor. **As of spec 0024 the
  production Tier-1 backend is the native `ExplorerBackend` (a general tool-calling
  model over three read-only tools to a `submit_citations` terminal action), which
  RETIRED and replaced the FastContext adapter described below; the FastContext code
  remains in-tree but off the production path — see history.md 2026-07-06 (spec 0024).**
  **As of Wave 5 (spec 0008)
  `mode=auto` climbs** (the Wave-3 "auto byte-identical / zero Gateway calls" statement
  is **superseded**): a point query runs seed → Scout → gate → maybe Deep, and the gate
  decides whether Tier-2 is spent (gated-pass `[0,1]`/`[1]`, escalated
  `[0,1,2]`/`[1,2]`); a broad query routes straight to Deep (`[0,2]`/`[2]`, Scout
  skipped, no gate). `mode=fast` → Scout with the gate run **informationally** (never
  climbs — a would-fail gate tags `gate-low-confidence`); `mode=deep` → Tier 2 (Deep),
  unchanged from Wave 4. The empty-case three-way split keeps the typed-vs-honest rule:
  a Scout typed-unavailable degrades to the Tier-0 floor (`confidence="degraded"`, no
  climb), an honest-empty Scout returns the seed tagged `gate-skipped:scout-empty` (no
  climb), only a malformed/un-scoreable result escalates. A Scout call resolves to a
  four-state degradation floor that never
  collapses model-down into a phantom "nothing found"; seed-before-backend ordering makes
  the loud precondition case win by construction. FastContext is an implementation detail
  *inside* a `Locator`, not a parallel citation path. As of Wave 4 (spec 0007) the real
  default client ships: Scout drives Microsoft's FastContext agent
  (`make_fastcontext_agent`, its own Read/Glob/Grep loop — **not** `dspy.RLM`, the
  invariant keeping Tier 1 structurally distinct from Tier 2) end-to-end, so the Wave-3
  live AC flips skip → genuine pass. The factory is env-only, so `FC_*` are injected from
  `Settings` under a module-level `threading.Lock` (not `asyncio.Lock` — the run is
  bridged onto a loop-free worker thread) held across the whole run; the air-gap is
  enforced at the endpoint (FastContext owns its own model client), and read-only /
  no-egress are assumptions verified by integration test with residual risk recorded.
  See history.md 2026-06-27 (spec 0007).
- Tier 2 (Deep) is live and additive on the Tier-0 floor — reached via `mode=deep`
  **and, as of Wave 5 (spec 0008), via an `auto` escalation** (a gate-fail /
  gate-scoring-failed / malformed Scout result on a point query, or a broad
  classification routing straight to Deep): a `dspy.RLM` explorer in a Deno/Pyodide
  sandbox
  whose entire world is the four confined read-only host tools. A successful run is
  `tiers_run=[0,2]`, `source_tier=2`. The explorer loop is bounded **in layers** —
  externally-enforced tool-calls/tokens/wall-clock (the load-bearing trio; wall-clock
  by an out-of-band host-terminable subprocess hard-kill) plus host-mediated
  depth/subqueries with recorded residual risk, transitively contained by the trio. A
  budget truncation surfaces as a stable non-degrade `deep-truncated:<bound>` note;
  Deep degrades to Scout best-effort **only** on a typed `DeepUnavailable` (weak/zero
  citations stay an honest Tier-2 result — no ungated escalation; the gated escalation
  it referred to now ships as the Wave-5 Verification Gate). Because the RLM writes and runs code, it is untrusted *code*, not just
  an untrusted caller: sandbox isolation (ambient FS + non-loopback egress denied) is
  an **assumption verified by test** with residual risk recorded, and the air-gap is
  enforced at the endpoint via `gateway.assert_local` (the RLM owns its own LM) and
  proven by a network-deny integration test. Deep is **not cached**. See history.md
  2026-06-27 (Wave 4).

## Boundaries

- Inbound: MCP only (`locate` / `read` / `index`) over stdio or streamable HTTP.
  The HTTP listener binds loopback only by default (`DEFAULT_HTTP_HOST =
  127.0.0.1`); a non-loopback bind requires an explicit `--allow-remote-bind`
  opt-out and is gated by the same `gateway.assert_local` check as the outbound
  endpoint. As of Wave 1, `harpyja_locate` (Tier-0, real retrieval),
  `harpyja_index`, and `harpyja_read` are registered; the Wave 0 `locate_stub` is removed.
- Outbound: local model endpoint via the Model Gateway (llama.cpp / Ollama), localhost only.
- Filesystem: read-only access to the target repo's **source**; manifest + symbol
  index are derived artifacts written to `<repo>/.harpyja/` (self-ignoring) or, when
  the repo is unwritable, `${XDG_CACHE_HOME:-~/.cache}/harpyja/<repo-hash>/`.
