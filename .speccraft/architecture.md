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
5. `harpyja/scout/` — Tier 1 finder. **As of spec 0025 the native `ExplorerBackend`
   (below) is the SOLE Scout backend and FastContext is FULLY REMOVED from the tree and
   the lockfile — `fastcontext.py`/`client.py`/`tools.py` deleted, `build_scout_engine` is
   the single canonical factory over `ExplorerBackend` (the parallel
   `build_explorer_scout_engine` is gone), and the explorer runs on `lm_model` via the
   wiring-pinned gateway. The FastContext description below (Wave 3/4, specs 0007/0011/0012)
   is retained as HISTORY, not current code.** Live as of
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
   `explorer_tools.build_explorer_tools` returns (as of spec 0030) EXACTLY FIVE `confine_path`-guarded,
   Settings-bounded, read-only navigation closures `{grep, glob, read_span, ls, symbols}` (`ls` added spec 0027, `symbols` added spec 0030) mirroring
   `deep/host_tools.build_host_tools` — `grep`/`glob` share the SAME `symbols.ripgrep.RipgrepEngine`
   the Deep `search` tool wraps (one bounded rg source of truth), `read_span` reuses
   `server.tools.read_snippet`, `glob` normalizes to file-level `CodeSpan`s bounded by
   `scout_glob_max_paths`; `explorer_loop.run_explorer_loop` answers ALL N parallel
   tool_calls the model emits per turn (spec 0029, answer-all-N): iterates each `tool_call` in
   emitted order, answering with its `tool_call_id` — a terminal `submit_citations` at any
   position [0:N] returns immediately and a non-floor per-call tool error is recorded as
   'tool-call-degraded:execution-error' (in-conversation, model-visible, NON-terminal) and
   the batch continues; N calls = one model turn (turns_used increments per model_call),
   capped by `scout_max_turns` (a model-TURN cap, not per-tool) AND a distinct whole-loop
   `scout_wall_clock_s` ceiling, with deterministic self-recovery (loop-detection on an exact
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

   **As of spec 0025 the parallel-factory deviation is CLOSED and FastContext is fully
   removed.** `build_scout_engine` is now the SINGLE production Scout factory and constructs
   `ExplorerBackend` (`build_explorer_scout_engine` deleted, body folded in); its default
   gateway pins `settings.lm_model` (not `ModelGateway.model`'s `"local"`, which 404s on
   Ollama's tag-routed API), so the explorer runs on `lm_model` (default Qwen3-8B — the SAME
   model as Deep). Deleted: `fastcontext.py`, `client.py` (the 0007 env-injection apparatus
   `_SCOUT_ENV_LOCK`/`_managed_fc_env`/`_run_coro_on_worker_thread`, the 0011 `citation=False`
   `<final_answer>` grammar + `parse_final_answer`), `tools.py` (a SECOND-ORDER orphan — its
   `build_tool_whitelist` was FC's whitelist), the FC error causes
   `FASTCONTEXT_MISSING`/`CLI_MISSING`, the FC-only Settings fields
   `scout_max_tokens`/`scout_temperature`/`scout_reasoning_effort`, and the `fastcontext` git
   dependency (pyproject + uv.lock). The turns-used measurement was MIGRATED off the
   FastContext trajectory scrape onto a native per-run seam:
   `LoopResult.turns_used` → `ExplorerBackend.last_turns_used` (set on submit AND both
   exhaustion-degrade paths, reset per run) → `ScoutEngine.last_turns_used` (getattr-guarded),
   and the 0022 diagnostic repointed BEFORE the `agent_factory=` seam was cut. `normalize.py`
   was DISENTANGLED: only the FC-era suffix-recovery (`_recover_suffix` / `MIN_TAIL_SEGMENTS`,
   spec 0012) is removed; the shared `normalize_spans` / `normalize_spans_with_tally` /
   `ScoutTally` / `last_tally` core is KEPT (still feeds `runner`, `locate_probe`, and the
   0022 `locate_accuracy` diagnostic), recovered counts now structurally zero. `scout_model`
   is KEPT as the served Verification-Gate A/B baseline (`verify_method="scout_model"`, 0018),
   scoped OUT of the FC-removal. Report schema bumped `0014/1 → 0025/1`
   (`fc_citation_recovered_*` retired-to-zero; the `fc_citation_{spanned,filelevel,dropped}`
   shape-tally fields kept, now populated by the EXPLORER — a `fc_`-prefix naming debt recorded
   as backend-neutral). Executable absence guards `test_fastcontext_absent.py` +
   `test_packaging.py` rot-false on reintroduction. Suite 985 pass / 23 skip, ruff clean; the
   AC8 cutover proof passed LIVE end-to-end through the explorer (Qwen3-8B on loopback Ollama,
   zero non-loopback egress). See history.md 2026-07-06 (spec 0025).

   **As of spec 0027 the explorer's EAGER whole-repo context map is REMOVED from the live
   path (push → pull), the navigation suite is EXACTLY FOUR tools, and `turns_used` is
   retired as a diagnostic.** `context_map.build_context_map` is RETIRED-from-live (kept for
   reference, no longer called by the backend); `ExplorerBackend._run_loop` now passes
   `context_map.build_initial_prompt(query)` — a minimal OpenCode-style initial prompt
   (system framing + query, NO repo listing) that is a small constant independent of repo
   size (the turn-1 payload drops ~10,181 → ~60 tokens, ~170×; asserted at the BACKEND level
   over a small AND large synthetic manifest, byte-identical because no manifest term
   survives). `explorer_tools.build_explorer_tools` now returns EXACTLY
   `{grep, glob, read_span, ls}` — the fourth tool `ls(path=".")` is a `confine_path`-guarded
   SINGLE-DIRECTORY listing (immediate children, files AND dirs, the layout-discovery
   affordance `glob` lacks) clamped by a NEW `Settings.scout_ls_max_entries` (default 200) —
   a DELIBERATE, reconciled tool-suite change (exact-count convention amended 3 → 4 + both
   hard-count tests, same commit). The SUT boundary held (cutover, not redesign): the
   `ScoutBackend`/`ScoutEngine`/`Locator` seam, gate, matrix, orchestrator, and
   `submit_citations` are byte-untouched. **Live status: the harness is PROVEN cheap-prompt
   (map removed), but model-drive-to-citation is UNPROVEN** — the AC5 live localization is a
   recorded HOLD: both astropy-12907 and django-12774 degraded `model-unreachable` @~300s on
   a DOWNSTREAM generation-runaway (Qwen3 thinking + unbounded generation), NOT the map
   defect and NOT a capability finding (`model-unreachable ≠ can't-localize`). Generation
   control (thinking-off + a tuned `max_tokens` cap + a directive prompt) is a BLOCKING
   PREREQUISITE for the 0026 re-run + the bake-off + any localization measurement; the AC5
   test (`test_harness_live.py`) ships `xfail` until it lands. See history.md 2026-07-07
   (spec 0027).
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

   **As of spec 0026** the package carries a **terse-query eval set + its
   authoring/measurement harness** — still measurement, not a runtime tier; the SUT
   (`harpyja/scout/`, `harpyja/orchestrator/`, `Settings`) is **byte-frozen** (this is a
   dataset + authoring/measurement harness only, no Scout/gate/orchestrator change).
   `dataset.py` gained a NEW `DATASET_SCHEMA_VERSION = "0026/1"` (introduced, not bumped;
   distinct from `report.SCHEMA_VERSION`) and six additive last-with-defaults `EvalCase`
   guard fields (`schema_version`, `label_provenance`, `query_provenance`,
   `gold_withheld`, `leaked_tokens`, `classification_provenance`); `_parse_case`
   version-gates the guard (`_parse_terse_guard`) so a terse-schema row MAY omit
   `expected_spans` but MUST carry the leakage-guard provenance, while a legacy/seed row
   (no tag) loads unchanged with defaults. `terse_dataset.py::load_terse_dataset` is the
   **JOIN loader (AC1)**: it asserts `sha256(raw.jsonl) == provenance.raw_fixture_sha256`
   BEFORE joining (`assert_raw_pin`, refusing an unverified source), then joins
   `expected_spans` / `base_commit` / source-issue text by `case_id` from the pinned
   `swebench_verified.raw.jsonl` (the sole authority — no span second-transcribed;
   `base_commit` stays a raw-record key via `JoinMeta`, per review B2), stamps
   `label_provenance = "patch-derived-at-convert"`, recomputes the near-vacuous
   `compute_leaked_tokens` tripwire against the JOINED issue, and excludes
   known-correct-span-only cases with a labeled `excluded_count` / `excluded_case_ids`;
   `validate_terse_set_floor` cites the committed `benchmark_fit.PREREGISTERED_CONFIG`
   (`min_n=12`, `MIN_DISCORDANT_PAIRS=8`) and a multi-repo requirement.
   `authoring_provenance.py` is the **loud-validated audit sidecar** (`AuthoringRecord` /
   `AuthoringArtifact`, `AUTHORING_SCHEMA_VERSION = "0026/1"`, validated verdict/outcome
   enums + hash-consistency + aggregate leaky/dropped counts) with pin-(2) blindness as
   the operational `assert_author_input_blind`. `terse_authoring.py` is the **OFFLINE
   two-model blind-authoring tool** (out-of-air-gap operator/dev activity like
   `convert`/`provision`): injected `author_invoke` / `verifier_invoke` callables — NOT
   the product `ModelGateway`, ast-guarded as non-product — author the query with the
   gold span withheld and route a `leaky` verdict to drop. `ac8_pilot.py` is the
   **frozen/hashed pilot power-gate** (`PREREGISTERED_AC8_CONFIG` + `AC8_CONFIG_HASH`,
   two reference models, `pilot_n=10`/`full_n_target=30`, `min_discordant_pairs` reusing
   the committed floor; signal-bearing flip excludes empty↔wrong-file noise; total pure
   `decide_ac8` → `Ac8Outcome ∈ {PROCEED, UNDER_POWERED_STOP}`). `terse_probe.py`
   (`run_terse_locate_probe` / `run_ac8_pilot`) drives the terse set through the REAL
   explorer via the UNCHANGED `run_locate_probe` / `score_distribution` (no forked
   scoring; per-arm `dataclasses.replace(settings, lm_model=…)`; provisioning injected).
   Report schema bumped `0025/1 → 0026/1` (additive `run_metadata.representativeness_caveat`,
   pinned `REPRESENTATIVENESS_CAVEAT` naming the query-shape-only scope + the Python
   language monoculture). **State: the INSTRUMENT is unit-complete but NOT yet usable —
   the committed `swebench_verified.terse.jsonl` is PLACEHOLDERS; the offline
   blind-authoring pilot (real queries) + the live AC8 go/no-go run are a delegated
   operator deliverable, and a likely AC8 `UNDER_POWERED_STOP` is a scoped finding naming
   the finder-capability next step.** See history.md 2026-07-06 (spec 0026).

   **As of spec 0027 the report surfaces PER-CAUSE Scout-degrade counts** (still
   measurement; the SUT change is the sibling spec-0027 explorer edit, not this layer).
   `runner.py` gains `_scout_degrade_cause` (parses `scout-degraded:<cause>`, tolerant of
   the `+no-matches` suffix) and emits four additive per-cause counts —
   `scout_degrade_model_unreachable_count`, `scout_degrade_backend_error_count`,
   `scout_degrade_loop_turns_exhausted_count`, `scout_degrade_loop_wallclock_exhausted_count`
   — alongside the RETAINED collapsed `scout_degrade_count` (the discriminant is the typed
   cause / `LoopResult.outcome`, NEVER `turns_used`, which is `None` on any degrade and a
   sub-cap int on wall-clock exhaustion). `report.SCHEMA_VERSION` bumped `0026/1 → 0027/1`,
   the fields appended last-with-defaults in `_AGGREGATE_DEFAULTS` (legacy 0026 blocks still
   validate); `loop-wallclock-exhausted` is the PRE-EXISTING spec-0024 between-turns ceiling
   merely surfaced per-cause, not new scope. See history.md 2026-07-07 (spec 0027).

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
  model over five read-only tools — `{grep,glob,read_span,ls,symbols}` as of spec 0030 — to a `submit_citations` terminal action), which
  RETIRED and replaced the FastContext adapter described below; as of spec 0025
  FastContext is FULLY REMOVED (single canonical `build_scout_engine` factory over
  `ExplorerBackend`, running on `lm_model`) and the FastContext description below is
  history only — see history.md 2026-07-06 (spec 0025).**
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

## Spec 0030 architecture updates — Tier-0 `symbols` as the fifth explorer tool

**As of spec 0030 `explorer_tools.build_explorer_tools` returns EXACTLY FIVE tools** —
`{grep, glob, read_span, ls, symbols}` — the exact-tool-count convention amended 4 → 5
IN LOCKSTEP (convention text + both hard-count tests, same commit). The fifth tool
`symbols(path)` is a Tier-0 FILE-LOCAL wrapper over the existing symbol index (NO new
parser): it returns kind+span `CodeSpan`s for one file, path-normalized and
confined-after-resolution, clamped by the new `Settings.scout_symbols_max_entries`
(default 400). When the manifest marks the file's symbols `degraded`, the tool falls back
to a ripgrep def-scan with a VISIBLE `degraded: true` marker (never a silent downgrade).
Wiring threads `symbol_records` + `manifest` into the tool builder via
`load_symbols_or_none`; a shared `record_to_codespan` projection was extracted for the
symbols tool and its consumers. A version-stamped lift-report schema shipped
(`symbols_lift_report.py`, `"0030/1"`). Honest close status: the TOOL is PROVEN (20+
unit tests, clean live run to terminal with the 5-tool suite, no degrade) but the LIFT
HYPOTHESIS IS NOT MEASURED — recorded inconclusive-and-inconsistent (the live bucket
oracle was a `has_citations→CORRECT` proxy, the astropy control moved via a mechanism a
file-local tool cannot produce, symbols invocation unconfirmed, N=2); the real lift run
with a ground-truth oracle was the follow-up that became specs 0031–0033. First
proof-of-mechanism (a live `symbols` invocation on astropy) landed in the 0033 adjacent
think-experiment, causal claim withheld. See history.md 2026-07-08 (spec 0030).

## Spec 0031 architecture updates — trajectory-verified live measurement

**As of spec 0031 the `harpyja/eval/` package carries the trajectory-verified live-measurement
VERIFIER** — still measurement, not a runtime tier; the explorer/loop/gateway decision
behavior is byte-unchanged (only two read-only capture seams were added, see below).
`live_verifier.py` is a PURE read-only postflight verifier: `verify_trajectory(traj)`
proves the FOUR FACTS (model identity / model invoked / tool names / terminal bucket)
or returns a `VerifierResult(status="FAILED", failure_reason=…)` carrying exactly one of
SIX enumerated codes in a FIXED precedence (`artifact-incomplete > model-unknown >
model-mismatch > model-not-invoked > tool-names-unextractable > terminal-bucket-missing`,
artifact-integrity first, first-failing-check wins). `VERIFIER_SCHEMA_VERSION="0031/1"`;
`write_verifier_artifact` delegates to `report.atomic_write_json` (the outside-repo
guard, single-sourced). `extract_model_identity` carries OQ1's three branches with a
`configured_endpoint_models` fallback (Ollama/llama.cpp may omit `response['model']`).
`verifier_preflight` gates the live run on `assert_local` FIRST then a `/api/tags`
model-presence check (the 0019 preflight discipline). `build_trajectory_record` is the
shared capture assembler (also used by `ExplorerBackend.last_trajectory`).
**State: verifier + seams unit-complete (AC1–AC5/AC7); `run_verified_case` shipped a STUB
and the AC6 proof-of-instrument live run (0030 astropy+django re-run) is a HELD operator
deliverable, gated by `verifier_preflight`, skip-clean on an absent stack.** The
"trajectory-verified measurement" convention binds all future live specs to a verifier
artifact. See history.md 2026-07-08 (spec 0031).

**As of spec 0031 `ExplorerBackend` exposes a read-only `last_trajectory` capture
seam** (mirroring the `last_turns_used` side-channel): after `run_explorer_loop`
returns, the backend records `self.last_trajectory = build_trajectory_record(...)`
(model turns, ordered-unique tool names, the served model threaded from the model call,
endpoint), reset per run. `run()` still returns `list[CodeSpan]` and decision behavior
is byte-unchanged — this is measurement plumbing for the spec-0031 postflight verifier.
See history.md 2026-07-08 (spec 0031).

**As of spec 0031 `ModelGateway.complete_with_tools` additionally surfaces the served model
additively as `response.get("model")` in its returned dict** (existing keys unchanged; `None`
when the endpoint omits it) — read-only metadata capture for postflight model-identity
verification, request/response semantics untouched.

## Spec 0032 architecture updates — one tool-name parser, strict-wins-as-data

**As of spec 0032 there is exactly ONE tool-call-name parser.** `build_trajectory_record`
(live_verifier.py) no longer carries its own inline silent-skip parse (the 0031 T20
divergence); it now routes through the canonical strict `extract_tool_names`, the same
implementation the verify path calls. The strict `tool-names-unextractable` failure
surfaces on the live builder as DATA — an additive `tool_names_failure: str | None` key on
the returned record dict (`None` on success, `"tool-names-unextractable"` on a nameless
tool_call, with `tool_names_invoked=[]` and NO partial list). This key lives ONLY on the
internal record dict; it never reaches the persisted VerifierResult
(`VERIFIER_SCHEMA_VERSION`, the six codes + precedence, `to_dict()` unchanged — a cutover,
not a redesign). `ExplorerBackend` is byte-unchanged: it calls the builder live mid-loop and
only STORES the result (`self.last_trajectory`), never branching on its contents, so control
flow, citations, and turn accounting are identical whether or not a tool_call is nameless.
The single-parser invariant is enforced by an `inspect.getsource` symbol-audit test (rots
false if a second inline `seen = set()` loop reappears). OQ2 audit confirmed tool-names was
the sole duplicated parse — identity (`extract_model_identity`), tiers_run, and terminal
bucket (`extract_terminal_bucket`) are each single-sourced. See history.md 2026-07-08
(spec 0032).

## Spec 0033 architecture updates — repo-relative scoped grep + found-then-dropped counts

**As of spec 0033 `RipgrepEngine.search` emits REPO-RELATIVE paths for scoped searches**,
fixed at the ONE bounded rg seam. `search(pattern, scope=None, *, repo_root: str | None =
None)` gained an optional per-CALL `repo_root` keyword (deliberately NOT a constructor
field — the engine is built once and shared across repos at `server/app.py` and `cli.py`,
so the repo root is a per-call fact). Mechanism (b), parse-side re-prefix: with `repo_root`
supplied, the `rg` invocation is byte-identical for DIRECTORY scopes (still `cwd=scope`,
same flags) and only the parsed paths are re-prefixed in `_parse(stdout, rel_prefix=...)`
via `os.path.normpath(os.path.join(rel_prefix, path))` (collapsing `.`/`./` artifacts);
`rel_prefix == "."` (scope == repo_root) leaves paths unchanged. A FILE scope (the
`symbols` degraded fallback shape) runs `rg` from the file's PARENT with the filename as an
rg path argument and re-prefixes by the parent's repo-relative prefix — supported, never
the pre-0033 `NotADirectoryError` crash. The legacy no-`repo_root` path is verbatim
(cwd-relative parse), so Tier-0 locate (`scope=req.repo_path`) is byte-identical. See
history.md 2026-07-09 (spec 0033).

**As of spec 0033 the fix is INHERITED by every engine consumer, not re-implemented per
caller.** Explorer `grep`, the `explorer_tools.symbols` degraded fallback, and Deep
`host_tools.search` all SUPPLY `repo_root=repo_path` as data to the shared engine; the
re-prefix logic lives solely in `RipgrepEngine` (the one-bounded-rg-source-of-truth
invariant — supplying data is not a per-caller re-prefix). The tool-contract is: every
path-DISCOVERING explorer tool (grep scoped + unscoped, glob, ls, symbols) emits
repo-relative paths; `read_span` is excluded (it echoes the caller-supplied path and
discovers nothing); `ls` directory entries carry the trailing-`/` shape as repo-relative
non-citable listings.

**As of spec 0033 the submit seam carries a found-then-dropped citation count.**
`submit_citations` returns a frozen `SubmitResult(spans, submitted, surviving)`
(`submitted = len(raw)`, `surviving = len(normalized)`), counted at the ONE normalize pass
where an explorer citation can drop — distinct from the engine re-normalize pass that feeds
`fc_citation_dropped_count` (whose engine-pass-only scope is now documented). The counts
thread as DATA `LoopResult.citations_submitted/citations_surviving` (defaulted) →
`ExplorerBackend` → `build_trajectory_record` → the persisted verifier artifact, mirroring
the `last_turns_used`/`last_trajectory` side-channel discipline. So found-then-dropped
`(1, 0)` is structurally distinguishable from honest-empty `(0, 0)` and can never again hide
inside an `empty` terminal bucket.

**As of spec 0033 `VERIFIER_SCHEMA_VERSION` is `"0033/1"` behind a version GATE.**
`validate_verifier_artifact` no longer uses strict equality; it accepts
`_KNOWN_VERIFIER_SCHEMA_VERSIONS = frozenset({"0031/1", "0033/1"})` (the 0026
`DATASET_SCHEMA_VERSION` pattern), and the two count fields are OPTIONAL, so a legacy
`0031/1` artifact still validates. The eval-report schema and `fc_citation_dropped_count`
are byte-untouched. `run_verified_case` now captures its typed `ScoutUnavailable` cause
into a variable that outlives the except block, names `.cause` in the "did not capture
trajectory" raise, and chains `from` — the dead shadowed `last_trajectory` assignment was
deleted (net-removing a pre-existing ruff F841).

**Measurement-integrity note (not code — a known instrument gap, spec 0034 target):**
`qwen3:14b` on the served Ollama THINKS BY DEFAULT — a `/v1/chat/completions` response
carries a `reasoning` field even with no `think` request param. `ModelGateway.complete_with_tools`
currently DROPS `reasoning` (returns only content/tool_calls/finish_reason/model), so this
reasoning has been generated invisibly and has consumed the `explorer_max_tokens=2048` cap
unseen since 0028 → the 0031–0033 live baselines were measured under invisible-truncation-risk.
Spec 0034 will surface `reasoning` additively and record per-turn reasoning lengths in the
trajectory artifact. See history.md 2026-07-09 (spec 0033). **(RESOLVED by spec 0034 — see
below.)**

## Spec 0034 architecture updates — reasoning observability (the gateway return contract, the backend accumulator seam, think_mode, schema 0034/1)

**As of spec 0034 `ModelGateway.complete_with_tools` surfaces `reasoning` and
`completion_tokens` ADDITIVELY** (AC1, the 0028 `finish_reason` / 0031 `model`
additive-return pattern). The return dict gains `"reasoning": message.get("reasoning")`
(absent field → `None`, present-but-empty → `""` — the honest 0-vs-None SOURCE) and
`"completion_tokens": (response.get("usage") or {}).get("completion_tokens")` (absent
`usage` → `None`) — the cap's actual TOKEN currency, alongside chars. The two 0028/0031
keys are unchanged; no transport change, no second outbound path. See history.md
2026-07-09 (spec 0034).

**As of spec 0034 the per-turn reasoning data rides a NEW backend-side accumulator — the
DECIDED capture seam.** `ExplorerBackend.wrapped_model_call` grew from the
`_last_served_model` last-write scalar into `self._per_turn`, a list appending
`{reasoning_chars, completion_tokens, finish_reason}` per model response (`reasoning_chars
= len(reasoning) if reasoning is not None else None`), reset per run in `run()` alongside
`last_turns_used`/`_last_served_model`. This is the ONLY seam that observes every response
INCLUDING a `finish="length"` FINAL turn — the history-ride route was eliminated because
`LoopResult.history` IS `session.messages()` (double-duty as the outbound wire messages —
annotating it would mutate the request body) and on `finish_reason="length"` the loop
returns BEFORE the assistant message is added to the session, so the truncated turn never
enters `model_turns`. Consequence: **`per_turn` and `model_turns` carry an intrinsic length
SKEW** (a truncated final turn has a `per_turn` entry but no `model_turns` entry) —
documented at the `build_trajectory_record` `per_turn` key; consumers must NOT zip the two
positionally. A truncated-by-reasoning turn (`finish_reason="length"` + `reasoning_chars > 0`
+ empty content) is structurally distinguishable in the record from content-truncated and
from clean. The list threads `build_trajectory_record(..., per_turn=, think_mode=)` → the
in-memory record AND `run_verified_case`'s hand-assembled written artifact (both wired;
guarded by a written-JSON test before any live run — the 0033 drop-at-assembly lesson).

**As of spec 0034 the trajectory carries ONE canonical `think_mode`.**
`derive_think_mode(think: bool | None, enable_thinking: bool)` in `explorer_backend.py`
returns one of `{"native-think-true", "native-think-false", "chat-template-disabled",
"default-omitted", "unknown"}` — native (`think` explicitly set) WINS over the
chat-template mechanism on a double-set config, so the two thinking mechanisms
(`explorer_enable_thinking`'s `chat_template_kwargs`, the llama.cpp template-era knob that
COEXISTS, and the new native `think` param) can never produce an ambiguous record.

**As of spec 0034 `VERIFIER_SCHEMA_VERSION` is `"0034/1"`.**
`_KNOWN_VERIFIER_SCHEMA_VERSIONS = frozenset({"0031/1", "0033/1", "0034/1"})` behind the
same version GATE; the new `per_turn`/`think_mode` (and the reasoning fields generally) are
OPTIONAL, so legacy `0031/1` and `0033/1` artifacts still validate and a non-reasoning
model legitimately producing none is not rejected. `probe_reasoning_default(gateway)` (AC5
precondition helper) makes one sanctioned `complete_with_tools` call through the air-gapped
seam and returns whether THIS served model emits `reasoning` by default — instance-relative
by design (the default-thinking finding is about this endpoint + model, not a universal),
gating the live recording proof skip-clean per the 0023 input-validity-precondition rule.

**As of spec 0034 `explorer_think` is the native think knob — tri-state, default-inert.**
`Settings.explorer_think: bool | None = None`: `None` ⇒ OMIT the `think` request param ⇒
the outbound request body is BYTE-IDENTICAL to pre-0034 (params == `{"max_tokens": 2048}`
under defaults — the observability-only default, pinned on the request body, not prose);
`True/False` ride as `params["think"]` and are operator opt-in generation control. `_coerce`
gained `bool | None` handling (`target_str in ("bool", "bool | None")`). The knob is
`explorer_`-scoped and threaded from TWO ctor sites — `wiring.py` (`build_scout_engine`)
AND `live_verifier.run_verified_case` (missing the second silently kills the live path); the
shared `ModelGateway` stays param-driven with no default, and the Deep-tier outbound guard
(`deep/test_rlm.py`) is extended so Deep carries neither the knob nor a `think` param (rots
false on leak). Coexists with `explorer_enable_thinking` (0028, the llama.cpp era) — the one
`think_mode` field disambiguates. See history.md 2026-07-09 (spec 0034).
