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
   top-N via an injected `Judge` (default `make_scout_model_judge`, routed through
   `ModelGateway.complete`), and decides whether the trailing Tier-2 step runs — so the
   realized `tiers_run` is a prefix of the planned ladder. `wiring.build_verification_gate`
   is the production `gate_factory`. Stable gate flags: `gate-low-confidence` /
   `gate-scoring-failed` / `gate-skipped:scout-empty` / `gate-skipped:no-line-range`
   (spec 0011 — a **file-level**, line-less citation reached the gate: detected
   **before** read-back via `GateOutcome.skipped_reason="no-line-range"`, not scored and
   not a verified pass; `locate.py` escalates if a tier remains in `auto` else carries it
   tagged, never at high confidence — distinct from low-confidence / scoring-failed). The
   Citation Formatter survives a line-less span un-merged (sorted after lined spans on a
   None-safe rank key, no fabricated range).
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
5. `harpyja/scout/` — FastContext adapter (Tier 1). Live as of Wave 3: `ScoutBackend`
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
   `DeepUnavailable.cause` (`sandbox-absent`/`rlm-down`/`backend-error`); a budget
   truncation is a non-degrade `deep-truncated:<bound>` note; `RipgrepMissingError`
   (seed) / `AirGapError` propagate as the floor.
7. `harpyja/gateway/` — Model Gateway over the local OpenAI-compatible endpoint. Only
   outbound caller. Live as of Wave 3: `ModelGateway.complete()` asserts the air-gap at
   name-resolution time (injected resolver + `ipaddress` loopback predicate) **before** an
   injected transport — no request leaves the process until loopback is proven.
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
   `runner.py::aggregate_outcomes` and the `swebench_eval.py` per-case driver.

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
- Tier 1 (Scout) is live and additive on the Tier-0 floor. **As of Wave 5 (spec 0008)
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
