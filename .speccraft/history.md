# History

Append-only. Newest first.

## 2026-07-09 — **Spec 0034 (reasoning-observability) CLOSED the 0031–0033 measurement blind spot: the reasoning `qwen3:14b` on THIS Ollama generates by default — silently DROPPED by the gateway and eating the `explorer_max_tokens=2048` cap since 0028 — is now surfaced ADDITIVELY (`ModelGateway.complete_with_tools` returns `reasoning` + `usage.completion_tokens`; absent→None, present-empty→""/None) and recorded per-turn in the DURABLE trajectory artifact via a NEW backend accumulator (the DECIDED seam: `wrapped_model_call` grew from the `_last_served_model` last-write scalar into a per-turn `{reasoning_chars, completion_tokens, finish_reason}` list, reset per run, threaded into `build_trajectory_record` AND `run_verified_case`'s written artifact — the ONLY seam that sees the finish="length" FINAL turn that never enters `model_turns`, so a truncated-by-reasoning turn is distinguishable IN THE RECORD from content-truncated and clean). One canonical `derive_think_mode` enum (native wins on double-set); `VERIFIER_SCHEMA_VERSION 0033/1→0034/1` behind the gate, reasoning fields OPTIONAL, legacy 0031/1+0033/1 still validate. The knob `Settings.explorer_think: bool | None = None` is tri-state DEFAULT-OMIT ⇒ outbound request BYTE-IDENTICAL to pre-0034 (pinned on the request body: params=={"max_tokens":2048}); coexists with `explorer_enable_thinking`. AC5 EXERCISED LIVE (qwen3:14b/Ollama, precondition-probed): per-turn reasoning_chars=[2086,794,1325,2676,1260,1328,1795] — ~11K chars/run of previously invisible reasoning now durable. Instrument stack 0031→0032→0033→0034 COMPLETE for the eval set; spec 0035 (silent-`[]` grep markers) filed as the next SUT fix BEFORE the eval set. 23/23 tasks, all 6 ACs MET, 1175 units, ruff 34 = baseline (zero-new)**

**Spec:** specs/0034-reasoning-observability/
**Decision:** the 0033-adjacent think-experiment surfaced a HIDDEN VARIABLE — qwen3:14b on this served Ollama emits a `reasoning` field with no `think` param — that `complete_with_tools` silently DROPPED while the generation counted against the 2048 cap, so every 0031–0033 live capability read was measured under invisible-truncation-RISK (asterisked, not clean). This is the measurement-integrity fix that closes the blind spot; NOT the causation experiment (that A/B belongs to the eval set and CONSUMES this observability). The cap mechanics are empirically PINNED by committed, re-runnable probe artifacts (`probes/`, the review's evidence-provenance fix): Ollama's `/v1` `max_tokens=20` → `completion_tokens:20` / `finish_reason:"length"`, identical to native `num_predict=20`, and the budget is consumed REASONING-FIRST (all 20 tokens to `reasoning`, zero content). Durable points. (1) **Gateway surfaces `reasoning` + `completion_tokens` ADDITIVELY** (AC1, 0028 finish_reason / 0031 model pattern) — the cap's actual token currency now visible next to chars; existing keys pinned unchanged. (2) **The backend accumulator is the DECIDED seam (OQ2 resolved in-spec against the review's code-verified finding that the `LoopResult.history`/`session.messages()` route is unworkable — it is double-duty as the outbound wire messages, and the truncated turn returns before the assistant message enters the session).** `wrapped_model_call` accumulates per-turn, reset per run, threaded into the record AND the hand-assembled written artifact (the 0033 drop-at-assembly lesson — guarded by a written-JSON test BEFORE any live run this time). The per_turn/model_turns length SKEW is pinned + documented at the record key (consumers must not zip positionally). (3) **One canonical `derive_think_mode(think, enable_thinking)`** — native wins over chat-template on double-set (the review's totality fix); `explorer_enable_thinking` COEXISTS (llama.cpp era, OQ1 coexist resolution). (4) **`explorer_think` tri-state, default-inert** (AC3): None ⇒ OMIT ⇒ request byte-identical, pinned on the REQUEST BODY, not prose; `bool | None` env coercion added; TWO-site ctor wiring (`wiring.py` + `run_verified_case` — the planner's discovery that missing the second silently kills the live path); Deep outbound guard extended (rots false on leak). (5) **Schema `0034/1` behind the gate**, reasoning fields optional (a non-reasoning model legitimately produces none). (6) **AC4 outcome-equality** (status/failure_reason/four facts), byte-identity explicitly disclaimed (`to_dict()` stamps the current version).
**Why:** the recurring project lesson — invisible generation reads as a clean capability finding — applied at the reasoning layer: reasoning that consumes budget but never appears in the artifact means the 0031–0033 buckets were measured under invisible-truncation-risk. Observability is MANDATORY (the recording); the knob is opt-in CONTROL of a thing already happening, inert by default. This closes the LAST blind spot in the instrument stack before the eval set trusts bucket distributions.
**Consequence — the hidden variable is now VISIBLE and DURABLE.** AC5 exercised live on qwen3:14b/Ollama (precondition-probed via the new `probe_reasoning_default`): think_mode=default-omitted, per-turn reasoning_chars=[2086,794,1325,2676,1260,1328,1795] — ~11K chars/run of previously invisible reasoning now in the artifact. A later observation run caught the instrument earning its keep: a 6554-char reasoning turn produced a hallucinated grep scope (`"repo"`) whose bare-`[]` return read as no-matches — a reasoning→wrong-subsystem coupling completely invisible pre-0034. The instrument stack 0031 verifier → 0032 parser dedup → 0033 path fix + counts → 0034 reasoning observability is COMPLETE; the astropy tally (empty ×4, wrong-file ×2, right-file-wrong-span ×1, symbols invoked in 2 runs) is now fully visible and attributable.
**Deviations:** (a) No major deviation; all 6 ACs MET after the ~10 review edits (applied without a full re-round per the 0032/0033 flow — the notable one was committing the `max_tokens=20` reasoning-first probe as durable machine evidence, closing the evidence-provenance gap both reviewers/the standard flagged). (b) T23 (optional REFACTOR) recorded a no-op — the per-turn shape was already minimal, no dedup extracted, ruff stayed at the 34 baseline (zero-new). (c) The 0033 drop-at-assembly lesson was PRE-EMPTED: the written-JSON artifact path was guarded by a written-JSON test BEFORE the live run, so the persistence gap the 0033 live run caught did not recur.
**Named blocking follow-up:** (1) **spec 0035 filed at THIS close — the silent-`[]` grep affordance gap, the NEXT SUT fix BEFORE the eval set** (the 0033 precedent: never baseline on a known tool-contract defect): a FILE-scope grep AND a nonexistent-scope grep both return bare `[]` indistinguishable from no-matches (two attributable live observations), fixed by typed model-visible in-conversation markers at the grep wrapper, with the capability-improvement claim WITHHELD (the eval set measures it). (2) **Persistent live-test artifacts** — live tests writing to gitignored `eval_work/live_artifacts/<test>/<timestamp>/` via the outside-repo atomic writer instead of `TemporaryDirectory` (three bucket-unanswerable re-runs forced it: 0033-T14, the 0034 AC5 run, the 0032 astropy loss); being folded into spec 0035's harness work. Standing carry-forwards unchanged (the model bake-off, the representative eval set, the 0026 terse-set pilot, the total-request wall-clock deadline; revisit `explorer_max_tokens=2048` now that the reasoning tax is token-denominated).
**Related specs:** [0033, 0032, 0031, 0028, 0026, 0023].

## 2026-07-09 — **Spec 0033 (scoped-grep-paths) CLOSED the 0032 measurement-integrity blocker: scoped grep now returns REPO-RELATIVE paths, fixed at the ONE `RipgrepEngine` seam (`search(repo_root=)`, mechanism-b parse-side re-prefix — the `rg` invocation byte-identical for directory scopes so AC1's ordering/ignore-file pin holds trivially; the FILE-scope `symbols` degraded-fallback runs from the parent dir with the filename as an rg arg, net-fixing a pre-existing NotADirectoryError crash), the fix INHERITED by every engine consumer (explorer `grep`, Deep `search`, `symbols` fallback all supply `repo_root=repo_path` as DATA — never a per-caller re-prefix); found-then-dropped is now a first-class recorded fact — `submit_citations` returns `SubmitResult(spans, submitted, surviving)` threaded LoopResult→backend→`build_trajectory_record`→PERSISTED artifact, `VERIFIER_SCHEMA_VERSION 0031/1→0033/1` behind a version GATE so legacy artifacts still validate; the drop CLOSED LIVE on real astropy (submitted=1, surviving=1). ADJACENT think-experiment (post-impl, N=2) delivered a first-ever right-file + first-ever `symbols` invocation on astropy — PROOF-OF-MECHANISM (the 0030 tool-chain works when engaged) with the CAUSAL CLAIM WITHHELD (both tested knobs measured inert, verdict: variance, not "thinking helps"), and surfaced the HIDDEN-VARIABLE finding that qwen3:14b THINKS BY DEFAULT and the gateway has silently DROPPED `reasoning` + eaten the 2048 cap since 0028 → every 0031–0033 baseline is measured-under-invisible-truncation-risk. 15/15 tasks, all 8 ACs MET, 1140 units, ruff 34 vs 36 (net -2)**

**Spec:** specs/0033-scoped-grep-paths/
**Decision:** 0032's AC6 surfaced this as a within-run A/B: `RipgrepEngine.search` ran `rg` with cwd=scope and parsed paths verbatim, so a SCOPED grep yielded scope-relative paths (`modeling/core.py`, missing the `astropy/` prefix) that failed repo-confine at `normalize_spans` — found-then-dropped read as EMPTY, indistinguishable from found-nothing, penalizing models that grep precisely and distorting the 0022 file-vs-span axis the bake-off depends on. spec 0012 built suffix recovery for EXACTLY this shape; 0025 removed it as FC-era code; the explorer re-created the input — but the RIGHT fix is at the PRODUCER, not a downstream repair. Durable points. (1) **Fix at the ONE bounded rg seam (OQ1→mechanism b).** `search` gained an optional `repo_root=` per-CALL keyword (OQ2 — NOT a constructor field: the engine is built once and shared across repos in `server/app.py`/`cli.py`, so the repo root is a per-call fact); the `rg` invocation stays byte-identical for directory scopes and only the PARSED paths are re-prefixed (`_parse(rel_prefix=)` via `normpath(join(prefix, path))`, collapsing `.`/`./`) — so AC1's repo-root ordering + ignore-file pin holds trivially, guarded by a real-`rg` integration case. The legacy no-`repo_root` path is verbatim (Tier-0 untouched). A FILE scope (the `symbols` degraded fallback) runs from the file's PARENT with the filename as an rg path arg — net-fixing a pre-existing `NotADirectoryError` crash (broken outside injected-runner tests) rather than rejecting loudly. (2) **The fix is INHERITED, not re-implemented per caller.** explorer `grep`, Deep `search`, and the `symbols` fallback all SUPPLY `repo_root=repo_path` as data; the re-prefix logic lives solely in the engine (supplying data is not the per-caller fix the invariant forbids). One tool-contract test pins grep (scoped+unscoped)/glob/ls/symbols-clean as repo-relative; `read_span` EXCLUDED (echoes input, discovers nothing); `ls` trailing-`/` entries pinned as repo-relative non-citable listings. Deep's scoped output POSITIVELY pinned as CHANGING. (3) **Found-then-dropped visible forever.** `submit_citations` returns `SubmitResult(spans, submitted, surviving)` (frozen; counted at the ONE submit-seam normalize pass where the explorer drop occurs — NOT the engine re-normalize pass `fc_citation_dropped_count` watches, whose engine-pass-only scope is documented); single production caller updated, no-other-caller asserted; threaded LoopResult→backend→`build_trajectory_record`→PERSISTED artifact; `VERIFIER_SCHEMA_VERSION 0031/1→0033/1` behind `_KNOWN_VERIFIER_SCHEMA_VERSIONS` version GATE (0026 `DATASET_SCHEMA_VERSION` pattern) with the counts OPTIONAL so a legacy `0031/1` artifact still validates; `(1,0)` structurally distinguishable from `(0,0)`; eval-report schema byte-untouched. (4) **Cause-swallowing folded in (AC6).** `run_verified_case` captures the `ScoutUnavailable` into a `degrade` var that OUTLIVES the except block, names `.cause` in the raise, chains `from` — and DELETES the dead shadowed `last_trajectory` assignment, which net-removed a pre-existing ruff F841 (the unused binding WAS the bug).
**Why:** the bake-off and the eval set trust bucket distributions; a tool-contract inconsistency that FLIPS a measured bucket (glob/ls repo-relative, scoped grep not) systematically converts would-be wrong-file/right-file into EMPTY — a false measurement in the instrument built to prevent false measurements. It had to clear BEFORE the bake-off, a BLOCKING prerequisite carved out of 0032 exactly as 0032 was carved out of 0031.
**Consequence — the drop CLOSED, and CLOSED LIVE.** The astropy end-to-end RED reproduced the exact 0032 drop (`[] == [core.py:812]`) before the fix made the cited hit SURVIVE; the django control byte-unchanged. T14 exercised on the served Ollama `qwen3:14b`: a scoped-grep citation SURVIVED normalization (submitted=1, surviving=1) — the 0032 found-then-dropped shape closed on the real case, in the durable artifact.
**Deviations:** (a) **The persisted-artifact gap the LIVE run caught** — the first T14 run passed but exposed that the counts reached the in-memory trajectory RECORD and NOT the persisted JSON (`run_verified_case` re-assembles the artifact from explicit fields; the unit tests had asserted the record, not the written JSON). RED test against the written JSON added, artifact assembly fixed, live re-run confirmed surviving=1 in the durable artifact — the hermetic fixture proved the MECHANISM, only the live run proved the PERSISTENCE. (b) AC7 is model-behavior-contingent (0023 precondition): a run that never greps scoped records NOT-EXERCISED, never a silent pass; AC3's hermetic fixture is the deterministic proof. (c) Ruff net -2 (34 vs the 36 0031/0032 baseline) via the AC6 F841 deletion; zero new. (d) An operational incident during fixture-commit (below) polluted then restored a measurement worktree — recorded honestly.
**The adjacent think-experiment (N=2, post-implementation — proof-of-mechanism with the causal claim WITHHELD):** run 2 produced the first-ever right-file outcome on astropy (~6 baseline: zero) AND the first-ever observed `symbols` invocation, via a clean push→pull walk — so the 0030 tool-chain PROVABLY works end-to-end when the model engages it (the open question is adoption FREQUENCY, not capability). But the verdict is **mechanism UNESTABLISHED, most likely variance**: both tested knobs measured INERT — thinking is already default-ON (a `/v1` response carries `reasoning` WITHOUT a `think` param) and the cap never bound (max turn 1041 tokens < 2048 < 8192). A result whose hypothesized cause is measured-ABSENT is NOT evidence for that cause; NOT recorded as "thinking improves localization." The load-bearing byproduct is the **hidden-variable finding**: default thinking has been invisibly generated, silently DROPPED by the gateway (returns only content/tool_calls/finish_reason/model), and eating the 2048 cap since 0028 → every 0031–0033 capability read was measured under invisible-truncation-risk and must be asterisked, not treated as a clean baseline. Also a representativeness datapoint: run 2 cited `separability_matrix()` (concept-correct); gold is the `_cstack` patch span → concept-location ≠ patch-location (the 0026 axis). Operational incident: the first fixture-commit landed inside the astropy measurement worktree (stale cwd, relative paths), committed to its detached HEAD; push denied 403 (nothing egressed); worktree hard-reset to base `d16bfe05a7`, input verified pristine — a measurement worktree is SUT input a stale cwd can silently pollute.
**Named blocking follow-up (spec 0034 being scaffolded):** **reasoning observability is priority one — NOT optional** — surface `reasoning` ADDITIVELY through `ModelGateway.complete_with_tools` and record per-turn reasoning LENGTHS in the trajectory artifact, closing the measurement blind spot that corrupted the 0031–0033 baselines. Then: (2) `think` as an `explorer_*`-scoped RECORDED knob (0028 generation-control pattern; reconciling `explorer_enable_thinking`); (3) the eval set's paired thinking-arm vs default-arm within-case A/B (McNemar, the 0023/0026 machinery) — the ONLY thing that settles causation, no more ad-hoc single runs; also revisit `explorer_max_tokens=2048` now that the reasoning tax is visible. Standing carry-forwards unchanged (the model bake-off, the representative eval set, the 0026 terse-set pilot, the total-request wall-clock deadline).
**Related specs:** [0032, 0031, 0030, 0028, 0026, 0025, 0012].

## 2026-07-08 — **Spec 0032 (trajectory-parser) CLOSED the 0031 T20 blocker: dedup'd the tool-call-name parser to ONE strict source of truth — `build_trajectory_record` no longer carries its inline silent-skip parse, it delegates to the canonical `extract_tool_names`, and the strict `tool-names-unextractable` failure now surfaces on the LIVE path as DATA (a NON-RAISING additive `tool_names_failure: str | None` record key, `tool_names_invoked=[]` on a nameless call, never a partial list) so ExplorerBackend's mid-loop control flow is byte-unchanged. OQ2 audited twice: tool-names was the SOLE duplicated parse (identity/tiers_run/bucket each single-sourced) — no parallel spec needed, locked by an `inspect.getsource` symbol-audit test. AC6 RE-VERIFIED LIVE on Ollama qwen3:14b: astropy EXACT field-by-field match to the 0031 reference (PASSED/empty/[ls,grep,submit_citations]/symbols-not-invoked), django PASSED/correct (cite 693 inside gold 689–695, genuine ground-truth overlap; first live confirmation of the 0029 answer-all-N fix). 6/6 tasks, 1111 units, ruff zero-new. BUT the instrument doing its job surfaced a NAMED NEXT BLOCKER — a scoped-grep path-shape defect that FLIPS a measured bucket: astropy's "empty" matches 0031 at the fact level but by a DIFFERENT mechanism (found-then-dropped, not found-nothing), because scoped grep returns scope-relative paths that fail repo-confine at normalization**

**Spec:** specs/0032-trajectory-parser/
**Decision:** 0031 shipped the trajectory verifier but left T20: the tool-call-name parse existed in TWO places with DIVERGENT behavior — `extract_tool_names` (verify path) FAILS `tool-names-unextractable` on a tool_call lacking `function.name`, while the inline parse in `build_trajectory_record` silently SKIPPED it and kept later names. Harmless while the verify path was the sole gate, but a BLOCKER before any downstream (bake-off, eval set) consumes `build_trajectory_record`'s tool list — a silent-skip copy would let a nameless call through undetected, a false measurement in the very tool built to prevent false measurements. Durable points. (1) **One parser, strict-wins.** The inline `seen = set()` loop is deleted; `build_trajectory_record` calls the canonical `extract_tool_names` and the STRICT semantics win — a nameless call is a typed failure everywhere, never a silent skip. (2) **Strict-failure-as-data on the LIVE path (the critical design constraint).** `build_trajectory_record` is called live by `ExplorerBackend.run()` mid-loop, so the failure must NOT raise. It surfaces as an additive `tool_names_failure: str | None` key (`None`/`"tool-names-unextractable"`) with `tool_names_invoked=[]` and no partial list — on the INTERNAL record dict only, never reaching the persisted VerifierResult (`VERIFIER_SCHEMA_VERSION`, the six codes + precedence, `to_dict()` all frozen — cutover, not redesign). ExplorerBackend only STORES the record and never branches on it, so control flow is byte-identical (AC7). (3) **OQ1 no-move:** the parser stays in `live_verifier.py` (explorer_backend already imports the builder from it; hoisting is churn without invariant value). (4) **OQ2 audit — tool-names was the SOLE duplicated parse** (verified planner + in-session): identity (`extract_model_identity`), tiers_run (propagated as data / caller literals), bucket (`extract_terminal_bucket`) each single-sourced. No parallel blocker spec; an `inspect.getsource` symbol-audit test (AC8) rots false if a second inline loop reappears. (5) **AC6 proof split honestly:** live trajectories are nondeterministic across runs (0031 astropy ~10 turns vs 3 here), so same-input→same-output is carried by a HERMETIC field-by-field VerifierResult golden (deterministic), the live run carries same-verified-facts on the real cases.
**Why:** the bake-off and the eval set are capability measurement across models × cases consuming verifier artifacts; the moment any downstream reads the build path's tool list instead of the verify path, the silent-skip copy corrupts the measurement. Two divergent parsers of the thing the instrument measures violates its one-source-of-truth contract, so the dedup had to clear BEFORE any downstream spec consumes artifacts — a BLOCKING prerequisite, not tech debt, carved out of 0031 exactly as 0032 was carved rather than folded in.
**Consequence — the dedup SHIPPED and AC6 re-verified live, but the instrument surfaced the NEXT blocker.** astropy's "empty" bucket matches the 0031 reference at the verifier-fact level yet by a DIFFERENT MECHANISM: the model FOUND a hit (`grep("separability matrix", scope="astropy/")` → one CodeSpan) and submitted `modeling/core.py:812`, which normalization DROPPED — `RipgrepEngine.search` runs `rg` with cwd=scope and parses reported paths verbatim, so a SCOPED grep yields scope-relative paths that fail repo-confine / `is_file` at `normalize_spans`. Found-then-dropped, not found-nothing (0031 genuinely submitted `{"citations":[]}` after 5 empty greps). django is the within-run A/B control: same grep tool, `scope="."` → repo-relative → citation KEPT (correct); `scope="astropy/"` → scope-relative → citation DROPPED (empty). A tool-contract inconsistency (glob/ls return repo-relative, scoped grep does not) that FLIPS the measured bucket and systematically converts would-be wrong-file/right-file into EMPTY for any model that greps scoped — penalizing more-precise scoping and distorting the 0022 file-vs-span axis. Capability reading unchanged either way (astropy's cite was the wrong file vs gold regardless). Spec 0012 built suffix recovery for EXACTLY this path shape and 0025 removed it as FC-era code — the explorer re-created the input the machinery existed to fix.
**Deviations:** (a) AC6 "byte-identical" is split — deterministic half via the hermetic golden, live half via same-verified-facts (live nondeterminism). (b) `run_verified_case` (0031 stub-completion) swallows the typed `ScoutUnavailable` cause and raises a cause-less `ValueError("Explorer did not capture trajectory")` on a pre-`LoopResult` degrade — a diagnosability gap, out of 0032 scope, noted in ac6-findings.md. (c) The first django live attempt degraded typed `model-unreachable` (environment/transport timeout), was surfaced via a diagnostic shim and retried clean — never skipped past. (d) Ruff: 36 pre-existing 0031-era errors untouched, zero introduced.
**Named blocking follow-up (spec 0033 being filed — BOTH must clear before the bake-off trusts bucket distributions):** (a) scoped-grep fix — make scoped grep output repo-relative AT THE TOOL SEAM (`RipgrepEngine`/wrapper, one bounded rg source of truth shared with the Deep `search` host tool; fix once, never per-caller); (b) verifier extension — record a submitted-vs-surviving citation count on the trajectory/verifier record so a found-then-dropped case is DISTINGUISHABLE from found-nothing and cannot hide inside "empty" again. Also candidate: carry the typed cause into `run_verified_case`'s raise (harness diagnosability). Standing carry-forwards unchanged (the model bake-off, the representative eval set, the 0026 terse-set pilot, the total-request wall-clock deadline).
**Related specs:** [0031, 0030, 0025, 0012].

## 2026-07-08 — **Spec 0031 (live) built the trajectory-verified live-measurement INSTRUMENT — a pure read-only postflight verifier (`live_verifier.py`) that proves the FOUR FACTS a valid live run must show (model identity / model invoked / tools-called-by-name / terminal bucket) or FAILS with exactly one of SIX enumerated, fixed-precedence codes; plus the read-only capture seams that make those facts recoverable (gateway surfaces `response['model']`; `ExplorerBackend.last_trajectory` via `build_trajectory_record`); plus the 0029 committed-test reconciliation (`_MODEL_OVERRIDE_REASON`) and the "trajectory-verified measurement" convention binding all future live specs. VERIFIER + SEAMS UNIT-COMPLETE (26 verifier tests + gateway/backend seam tests, AC1–AC5/AC7), but AC6 proof-of-instrument is a HOLD: `run_verified_case` shipped a STUB and the 0030 astropy/django live re-run (the symbols-invocation resolution) is the operator's deliverable, gated by `verifier_preflight`, skip-clean on an absent stack**

**Spec:** specs/0031-live/
**Decision:** Three consecutive specs (0029/0030) produced capability numbers that could not be verified from machine evidence — 0029 couldn't prove which model/endpoint served it (committed 16B/llama.cpp:8131 vs changelog 14B/Ollama, override un-git'd), 0030-early silently stopped at Tier-0 with the model never invoked, and 0030-final could not confirm the `symbols` tool was actually called. The recurring project failure mode is validity asserted from agent prose over the run's trajectory. This spec builds the INSTRUMENT that makes that impossible, in the 0019–0026 measurement-not-construction lineage (all code additive under `harpyja/eval/` + two read-only capture seams; explorer/loop/gateway decision behavior byte-unchanged). Durable points. (1) **A run that cannot PROVE the four facts FAILS — no silent pass, no defer-to-prose.** `verify_trajectory` is a pure read-only function over a captured trajectory dict; each unprovable fact maps to a DISTINCT machine-readable code, surfaced as an artifact-resident `verifier_status="FAILED"` + `failure_reason` (plus `VerificationError` for CLI/API). (2) **Six enumerated codes in a FIXED precedence** (`artifact-incomplete > model-unknown > model-mismatch > model-not-invoked > tool-names-unextractable > terminal-bucket-missing`), artifact-integrity checked first (nothing else is trustworthy without it), first failing check wins — so a multiply-unprovable trajectory returns one deterministic code. (3) **OQ1 model identity is a three-branch rule with a configured-endpoint fallback** (`extract_model_identity`): served==requested → PROVEN; served!=requested → `model-mismatch`; served absent → `configured_endpoint_models` membership (PROVEN-via-fallback, details record the source; empty/absent → `model-unknown`) — resolving that Ollama/llama.cpp may omit `response['model']`, without silently passing. (4) **model-invoked = `(1 in tiers_run) AND len(model_turns) >= 1`** catches 0030-early's Tier-0 short-circuit; **tool_names_invoked = ordered-unique `function.name` parse** makes 0030-final's `symbols`-vs-not distinguishable (a call object with no parseable name → `tool-names-unextractable`, zero calls → `[]`, not a failure). (5) **Read-only capture seams, mirroring existing side-channels.** The gateway surfaces `response.get("model")` additively (existing keys unchanged); `ExplorerBackend` records `self.last_trajectory` after the loop via the shared `build_trajectory_record`, mirroring the `last_turns_used` seam — neither changes decision behavior or the `run()` return type. (6) **`verifier_preflight` gates AC6** on `assert_local` FIRST then a `/api/tags` model-presence check (the 0019 `preflight_models_present` discipline — same loopback-gated egress class, no second outbound path); an absent model or non-loopback endpoint is a documented invalid-setup skip, never a measurement failure. (7) **0029 reconciliation (AC7):** `_MODEL_OVERRIDE_REASON` + `test_recorded_model_matches_settings_or_documents_override` bind the committed harness model/endpoint to a stated rationale or Settings equality — code and recorded run are no longer at odds.
**Why:** the model bake-off AND the representative eval set are nothing but capability measurement across models × cases; they cannot run on a harness whose results the agent can fabricate or fail to verify. The invariant — machine evidence over agent summary — had to be made ENFORCEABLE before any capability number is trusted, so this instrument is a BLOCKING PREREQUISITE for the bake-off and the 0026 pilot re-run, not cleanup.
**Consequence — the VERIFIER + SEAMS are unit-complete; the PROOF-OF-INSTRUMENT live run is a HOLD.** AC1–AC5/AC7 shipped (26 `test_live_verifier.py` tests + gateway/backend seam tests, all green). **`run_verified_case` shipped a STUB** that satisfies the integration-test interface and writes a valid artifact but does NOT construct an `ExplorerBackend`, drive the case, or derive `terminal_bucket` via `locate_accuracy` — so **AC6's 0030 astropy+django re-run (and the symbols-invocation resolution the 0030 close named as its blocking follow-up) did NOT happen here**; it is the operator's deliverable, gated by `verifier_preflight`, and `test_live_verifier_integration.py` skips clean on an absent stack. The close-vs-hold boundary holds by cause: the verifier is a SUT-observing shipped capability (close), the un-run live proof is a BLOCKED operator step (hold) — never conflated.
**Deviations:** (a) `run_verified_case` is a stub (T24/AC6 above). (b) T15/T20/T25 (REFACTOR, optional) left undone; the T20 consequence is a DUPLICATED tool-name parser — `extract_tool_names` FAILs `tool-names-unextractable` on an unnamed call while `build_trajectory_record` silently skips it — recorded as tech debt (harmless today because the verify path is the sole gate), a T20 follow-up.
**Named blocking follow-up:** the operator proof-of-instrument run (0030 astropy + django re-run through `run_verified_case` on the served stack, symbols-invocation CONFIRMED or the 0030 lift claim retracted); implement `run_verified_case` for real (construct `ExplorerBackend`, derive `terminal_bucket`); T20 shared-parser refactor. Standing carry-forwards unchanged (the model bake-off, the terse-set blind-authoring pilot, the total-request wall-clock deadline).
**Related specs:** [0029, 0030, 0024, 0019].

## 2026-07-08 — **Spec 0030 (symbols) SHIPPED the 5th explorer tool — a Tier-0 file-local `symbols(path)` wrapper (no new parser; kind+span CodeSpans, path-normalized, confined-after-resolution, clamped by new `Settings.scout_symbols_max_entries=400`; manifest-`degraded` → ripgrep fallback with visible `degraded: true` marker). Exact-tool-count convention amended 4 → 5 IN LOCKSTEP. Wiring threads `symbol_records` + `manifest`. Shared `record_to_codespan` projection extracted. Lift-report schema shipped (version-stamped 0030/1). TOOL PROVEN (20+ unit tests) and HARNESS VALIDATED with 5th tool present (clean run to terminal, no degrade). BUT THE LIFT HYPOTHESIS IS NOT MEASURED — recorded inconclusive-and-inconsistent, explicitly NOT "validated": the live bucket oracle is a `has_citations→CORRECT` proxy (not ground-truth span comparison), the astropy control moved to "CORRECT" via a mechanism a file-local tool cannot produce (internal inconsistency, false-capability read), symbols invocation was unconfirmed, and N=2 on an ad-hoc rig. The tool ships proven; the AC5/AC6 measurement is a HOLD naming a real lift run with ground-truth oracle as follow-up**

**Spec:** specs/0030-symbols/
**Decision:** 0029's live signal was django=RIGHT_FILE_WRONG_SPAN (correct file, wrong span) — the exact failure a file-local symbol tool targets — so 0030 added `symbols` as the pull affordance for span precision, staged since 0024 as "MEASURED second round." Reuse Tier-0 (one parser); scope = symbols-and-spans in ONE file (no call graph); pull-not-push, exact-count reconciled; untrusted-caller boundary (read-only, confined, clamped, degrades not crashes). AC3's provenance decision (resolved in planning): parse-failure lives on EXISTING `ManifestEntry.degraded` because a degraded file has ZERO `SymbolRecord` rows; the tool threads BOTH `symbol_records` and `manifest`. Exact-count amended 4→5 in a single lockstep commit (0027 precedent), convention + both hard-count tests + schema together.
**Why:** Harpyja is memory-boxed to ~16B, so tooling (not model scale) is the capability lever; a span-localization tool buys precision at zero added model size, and had to land BEFORE the bake-off so models rank through the final suite.
**Honest outcome (load-bearing):** the TOOL is proven and the harness is clean with it present, but the SPEC'S POINT — AC5's lift measurement — did NOT happen. The live test maps outcome→bucket by citation presence (`has_citations→CORRECT` else `WRONG_FILE`), not by 0029's ground-truth span oracle; under that proxy astropy (baseline WRONG_FILE, the designed structural control a file-local tool CANNOT fix) read "CORRECT," which is internally inconsistent, revealing the oracle is measuring "returned something" not "returned the right span." Symbols invocation was probed by monkeypatch and the test tolerates its absence, so we cannot confirm the model called the tool. The project lesson (degrade-masks-outcome trap, 0026/0027/0028) applies at the measurement layer: a lift claimed on a presence-proxy with a control that moved impossibly is a FALSE-CAPABILITY read.
**Consequence:** the explorer suite is NOW EXACTLY FIVE `{grep, glob, read_span, ls, symbols}`; span precision is AFFORDED but its lift is UNMEASURED. **Named blocking follow-up:** a real lift run (0029 baseline cases and/or 0026 terse instrument) scored by the SAME ground-truth span oracle (`locate_accuracy` buckets, one-oracle reuse), with symbols invocation CONFIRMED, before or as part of the model bake-off. Housekeeping: remove stray repo-root `measure_symbols_lift.py`.
**Related specs:** [0024, 0027, 0029].

## 2026-07-07 — **Spec 0029 (loop) IMPLEMENTED parallel tool_call handling in the explorer loop (answer-all-N, path B): iterate ALL N parallel `tool_calls` the model emits in emitted order, answering each with its `tool_call_id`; honor a terminal `submit_citations` at any position (returns immediately, remaining calls not executed); record a non-floor per-call tool exception as an in-conversation 'tool-call-degraded:execution-error' marker and continue the batch; floor exceptions (RipgrepMissingError / AirGapError) re-raised to the Tier-0 floor. UNIT-proven (10 new tests, 127 scout tests pass, determinism verified on N=4 astropy shape), LIVE-ready (xfail→xpass gate wired), UNOBSERVED (first full localization run requires live 16B stack). The FIFTH consecutive genuine downstream layer resolved, and the SOLE remaining prerequisite for AC5 localization, the 0026 pilot re-run, and the model bake-off (the 0028 operator-run diagnosis proved definitive). The loop now honors parallelism without malformation, per-call resilient to tool errors, deterministic on identical inputs**

**Spec:** specs/0029-loop/
**Decision:** Spec 0028's operator run diagnosed the next distinct downstream defect: the explorer loop echoed the N parallel `tool_calls` the model emitted (measured N=4 on astropy) into the assistant message but answered only `tool_calls[0]`, leaving N−1 unanswered → malformed turn-2 OpenAI conversation → runaway the max_tokens cap caught as `generation-truncated`. Controlled proof: FULL echo → finish=length 101s; TRIMMED-to-answered → 0.8s. This was the turn-2 diagnostic that re-pointed AC5's HOLD from 0027→0028. The decision in review was (B) answer-all-N (path (A) trim-to-answered considered and rejected — it discards the N−1 proposed calls, re-spending turns against the N=10 budget). (A) **New `_answer_tool_call` helper (T2 GREEN), run_explorer_loop iterates the full `tool_calls` list in emitted order.** Terminal `submit_citations` at ANY position returns the LoopResult immediately; remaining calls in the batch are NOT executed (terminal precedence, T3/T4 RED tests, T2 GREEN verified). (B) **Per-call non-floor exception handling (T4 GREEN): wrap each tool execution in try/except Exception.** Floor exceptions (`RipgrepMissingError` / `AirGapError`) are re-raised, never degraded — they still propagate to the Tier-0 floor. A non-floor exception is recorded as an in-conversation, model-visible, NON-terminal marker ('tool-call-degraded:execution-error: <Type>: <msg>') and the batch CONTINUES — deliberately distinct from the terminal `ScoutUnavailable` cause taxonomy and NOT counted in the report. (C) **T6 REFACTOR: fold the three outcome paths (terminal/unknown-tool/degrade/observation) into the single `_answer_tool_call` helper**, so the loop body is readable `for call in tool_calls: term = _answer_tool_call(...); if term: return term`. (D) **N calls = one model turn (turn accounting preserved).** `turns_used` increments per model_call, not per tool_call; the N=10 budget is untouched. (E) **Determinism proven unit-level (T5 RED→GREEN).** Identical injected N=4 astropy-shape turn run twice yields identical trace and turn_count. (F) **Integration wired, live-stack-ready but UNOBSERVED (T7).** The xfail→xpass gate is in place (`test_explorer_localizes_without_degrade_within_n_turns`, astropy + django parametrized, AC8 MUST PASS harness correctness gate on @pytest.mark.integration). The capability MEASUREMENT (per-case bucket: correct / right-file-wrong-span / wrong-file / empty) is REPORTED but not yet observed. Consistent with the lineage 0027→0028 → 0029, each a recorded genuine layer; capability finally unblocked for measurement.
**Shipped:** answer-all-N (all N parallel tool_calls answered in order), terminal precedence (submit_citations returns at position), per-call degrade (batch continues on non-floor error), floor exceptions re-raised, T6 refactor, determinism unit-proven, N=1 regression guard (all prior tests pass), turn accounting unchanged, integration wired + xfail→xpass gate.
**Deviations:** None. All 10 ACs shipped as specified.
**Not shipped (operator-run-ready):** AC6/AC7/AC8/AC9 live runs (no live stack in this session); xfail gate wired, operator-run-ready.
**SUT boundary held:** surgical to loop message handling; ScoutBackend/ScoutEngine/Locator, four-tool suite {grep,glob,read_span,ls}, submit_citations, 0028 gateway knobs, cause taxonomy, gate, matrix, orchestrator all byte-untouched; push→pull and exact-four held.
**Related specs:** [0024, 0027, 0028].

## 2026-07-07 — **Spec 0028 (generation-control) BOUNDED the explorer's per-call generation and made truncation DIAGNOSABLE — surfaced `finish_reason` additively from the Model Gateway (AC0), capped generation at `explorer_max_tokens=2048` with the DRIFT-GUARD on the explorer-owned object (AC2), added the `explorer_enable_thinking` knob via `chat_template_kwargs` (NOT `/no_think`) (AC1), and typed `finish=length` as the FIFTH explorer cause `scout-degraded:generation-truncated` REGARDLESS of a riding tool_call (AC3, `SCHEMA_VERSION 0027/1 → 0028/1`), Deep byte-untouched by `explorer_`-prefix scope (AC8); generation control PROVEN (AC4 first call `finish=tool_calls` ~2s LIVE, units 1046 pass, ruff clean) — but AC5 localization HELD AGAIN, its blocker RE-POINTED from the now-FIXED unbounded generation to a NEW distinct downstream defect: the explorer loop echoes N parallel `tool_calls` (measured N=4) but answers only `tool_calls[0]`, leaving N−1 unanswered → malformed conversation → turn-2 runaway the cap correctly catches as `generation-truncated`. FOURTH consecutive genuine downstream layer; generation control PROVEN, drive-to-citation STILL UNPROVEN, now gated on parallel-tool-call handling**

**Spec:** specs/0028-generation-control/
**Decision:** Spec 0027 proved the explorer is cheap-prompt but left AC5 (does the model
actually localize?) a HOLD: on the served 16B stack both gold cases degraded
`model-unreachable` @~300s with `turns_used=None` — the model NEVER FINISHED GENERATING
turn 1 because generation was UNBOUNDED (no `max_tokens` cap), and `model-unreachable ≠
can't-localize` (the degrade-masks-outcome trap). This spec bounds the explorer's per-call
generation so a first response completes in seconds, and — critically — makes any remaining
runaway DIAGNOSABLE. Five shipped pieces, in dependency order. (0) **`finish_reason` surfaced
additively (AC0 — the load-bearing FOUNDATION).** `ModelGateway.complete_with_tools` now
returns `{content, tool_calls, finish_reason}`, read from `choices[0].finish_reason` (the
CHOICE, not the message), `str`-cast when present and defaulting to the exact sentinel
`"unknown"` when absent; backward-additive (the two existing keys unchanged), pinned by unit
tests. This is what made the AC5 blocker below DIAGNOSABLE where 0027 saw only a masked hang —
a downstream degrade cannot be TYPED without it. (1) **`explorer_max_tokens=2048` — the PRIMARY
anti-runaway lever (AC2).** A `Settings` field (additive-last, env-coerced) threaded into the
explorer's per-call `complete_with_tools`; per the DRIFT-GUARD convention the finite cap ALSO
lives on the explorer-owned constructed object's own field default (`ExplorerBackend.max_tokens
= 2048`, pinned by a field-default introspection test), so a `Settings`-bypassing construction
is still bounded. **`ModelGateway` stays purely param-driven (NO `max_tokens` default of its
own)**, so the Deep-tier path (which calls the gateway without `explorer_max_tokens`) is never
capped. (2) **`explorer_enable_thinking` thinking knob (AC1 — the KNOB, not a mandate).** A
`Settings` bool; when False the explorer's gateway call carries request param
`chat_template_kwargs={"enable_thinking": false}`, when True the param is OMITTED — the inferior
`/no_think` query token (measured 43s, template-perturbing) is REJECTED, never a fallback.
Bidirectional unit test; shipped provisional default `True` (AC6 deferral below). (3)
**`generation-truncated` — the FIFTH explorer degrade cause (AC3).** A `finish_reason ==
"length"` turn is a typed degrade emitting the stable cause `scout-degraded:generation-truncated`
— **REGARDLESS of whether a syntactically valid `tool_call` rode along** (a length-truncated
response was cut off mid-generation; its tool-call args may be silently incomplete, and
accepting it would mask cap pressure per AC7). Plumbed through the whole chain:
`explorer_loop.GENERATION_TRUNCATED` (checked right after the model call, before any tool
dispatch) → `errors.GENERATION_TRUNCATED` → `ExplorerBackend._EXHAUSTION_CAUSE` → runner
`_SCOUT_NATIVE_CAUSES` + a DISTINCT `scout_degrade_generation_truncated_count` → report field +
`_AGGREGATE_DEFAULTS`; `report.SCHEMA_VERSION 0027/1 → 0028/1` (legacy blocks still validate).
(4) **Explorer scope enforced by construction (AC8).** The knobs are `explorer_`-prefixed and
passed ONLY by the explorer's `_default_model_call`; a NEW `harpyja/deep/test_rlm.py` guard
asserts the Deep-tier outbound call carries NEITHER the cap NOR
`chat_template_kwargs.enable_thinking` (asserting on the actual outbound fields, not the absence
of the Settings names) — it PASSES on introduction and ROTS FALSE on any future leak. AC4 is
PROVEN LIVE: a first explorer call returns a well-formed non-truncated `finish=tool_calls` in
~2s (1.9–2.6s across caps 2048–16384, both thinking modes), far inside ≤30s — the 0027 "never
finishes turn 1" symptom is GONE.
**Why:** the recurring project lesson — a degrade that masks an outcome silently reads as a
capability finding — applied at the generation layer: the 0027 unbounded-generation hang was
masked as `model-unreachable`; a `max_tokens` cap bounds it AND, paired with a surfaced
`finish_reason`, converts the hang into a fast, precisely-attributed `generation-truncated`
degrade instead of a phantom "not found." Generation control is a BLOCKING PREREQUISITE 0027
named — it GATES the 0026 pilot re-run, the model bake-off, and any localization measurement.
**AC5 HOLD — RE-POINTED from a FIXED cause to a NEW, precise one.** The 0027 blocker (unbounded
generation, masked `model-unreachable`) is FIXED. But the live AC5 run surfaced a SECOND,
distinct downstream blocker, and the new AC0+AC3 machinery diagnosed it precisely: on turn 1 the
model emits **N parallel `tool_calls`** (measured N=4); the explorer loop echoes ALL N into the
assistant message but processes and answers only `tool_calls[0]`, leaving **N−1 `tool_calls`
with no matching `tool` response** — malformed per the OpenAI tool protocol, derailing the model
into a turn-2 runaway the cap then correctly catches as `generation-truncated`. Controlled
turn-2 diagnostic (same cap 4096, thinking off, only the assistant message shape differs): FULL
echo (all 4 tool_calls, 1 answered) → `finish=length` runaway 101.4s; TRIMMED to the answered
call → `finish=tool_calls` clean 0.8s. **`generation-truncated` here ≠ "can't localize"** — the
SAME degrade-masks-outcome trap the 0026 RCA and 0027 close both flag. `test_harness_live.py`'s
AC5 case stays `xfail` (non-strict), its reason RE-POINTED from "unbounded generation" to name
the exact mechanism (parallel-tool-call echo mismatch → turn-2 runaway), so the follow-up starts
from the diagnosis, not a re-investigation; it flips to xpass when the loop echo is well-formed.
**AC6 lever choice DEFERRED (with data):** the thinking-vs-thinking comparison against AC5
localization QUALITY is not yet MEASURABLE (the parallel-tool-call blocker truncates every run
regardless of thinking mode); first-call latency is ~2s both ways (thinking-on marginally
faster), so the provisional `explorer_enable_thinking=True` shipped and the knob makes a later
flip a one-liner. **AC7 cap validated against BOTH bounds:** upper (runaway) bounded (2048 → 52s
degrade; 8192 → 237s degrade — a bigger cap is SLOWER truncation, not a completion); turn-budget
headroom ample (a well-formed turn completes far under 2048 — first call ~2s, TRIMMED turn-2
0.8s, room for a multi-span `submit_citations`); `N=10` inherited unchanged from 0026/0027.
**OPEN DESIGN QUESTION for the follow-up — NOT a foregone 1-liner:** (A) **trim-to-answered** —
echo only the `tool_calls[0]` the loop processes; minimal and well-formed, but discards the N−1
proposed calls each turn so the model must re-propose them, spending more turns against the
`N=10` budget (turn-budget pressure — the exact degrade-masks-outcome axis AC7 guards); vs (B)
**answer-all-N** — dispatch every parallel `tool_call` and append a `tool` response for each
(OpenAI-correct, uses the model's parallelism for fewer turns), but a larger blast radius on the
0024 loop invariants (one-dispatch-per-turn → N-per-turn, reordered loop-detection/truncation
bookkeeping). The turn-budget tradeoff is the crux; the follow-up decides it against
localization quality once measurable, not by default.
**Consequence — generation control is PROVEN; drive-to-citation is STILL UNPROVEN.** This is the
FOURTH consecutive real downstream layer peeled between the project and its first PROVEN
localization, each a distinct genuine defect — the layered-RCA process WORKING, not failure:
(0026) terse-query instrument built but the AC8 pilot could not measure (`UNDER_POWERED_STOP`,
general candidates under-power terse ranking); (0027) eager whole-repo context-map bloat removed
(~170× payload cut, proven), AC5 HELD on unbounded generation masked as `model-unreachable`;
(0028, this spec) generation control proven (cap bounds runaway, `finish_reason` surfaced,
`generation-truncated` typed, AC4 ~2s live), AC5 HELD AGAIN on the parallel-tool-call echo
mismatch. **AC5 (drive-to-citation) has now been a recorded HOLD across 0027 → 0028**, each time
by a DIFFERENT, correctly-attributed downstream cause. Units 1046 pass, ruff clean; AC4 pass
live, AC5 xfail. Report `SCHEMA_VERSION 0028/1`; the explorer degrade taxonomy is now FIVE
causes.
**Named blocking follow-up (the BLOCKING PREREQUISITE):** a spec that makes the explorer loop's
assistant echo well-formed (decide (A) trim-to-answered vs (B) answer-all-N above). It is the
BLOCKING PREREQUISITE for AC5 localization, the 0026 pilot re-run, AND the model bake-off — the
harness now bounds AND diagnoses runaway cleanly, but cannot yet DRIVE the model to a citation
until the turn-2 conversation is well-formed. First evidence recorded: TRIMMED turn-2 = 0.8s
clean vs FULL = 101.4s runaway. Standing follow-ups unchanged: the Tier-0 AST symbol tool; a
total-request wall-clock deadline (0017-caveat). See specs/0028-generation-control/.

## 2026-07-07 — **Spec 0027 (harness) removed the explorer's EAGER whole-repo context map (RCA-driven push → pull), added an on-demand `ls` tool (exact-tool-count convention reconciled 3 → 4), and plumbed the four-cause degrade taxonomy per-cause to the report (`SCHEMA_VERSION 0026/1 → 0027/1`) — map removal PROVEN live (turn-1 payload ~10,181 → ~60 tokens, ~170× cut, repo-size-independent), but AC5 localization is a HOLD: both cases degraded `model-unreachable` @300s on a DOWNSTREAM generation-runaway (model-unreachable ≠ can't-localize), so finder capability is UNMEASURED. Generation control is a BLOCKING PREREQUISITE for the 0026 re-run + bake-off + any localization measurement. Cutover-not-redesign: gate/matrix/orchestrator/`submit_citations`/`Locator` byte-untouched. AC7 committed-error correction (0020–0023 "confounded") narrowed to 0026-ONLY and ASSERTED consistent across all three surfaces**

**Spec:** specs/0027-harness/
**Decision:** The 0026 RCA (`rca-explorer-context-bloat.md`) found the explorer's per-turn
prompt is dominated by spec-0024's `build_context_map` — a flat whole-repo listing
(~1,221 lines / ~10,181 tokens for astropy) re-sent every turn — pushing the 16B model
into a generation that never completes turn 1 inside the 300s timeout → `ScoutUnavailable`
→ floored to empty (a degrade misread as non-localization). The eager whole-repo *push* is
the defect; the fix is *pull*. This spec (a) REMOVES the eager map from the live path
entirely — the backend now calls a minimal `context_map.build_initial_prompt(query)`
(system framing + query, NO repo listing), so the turn-1 payload is a small constant
independent of repo size; **DEVIATION (T6):** the spec DECIDED `context_map=""`, but the
query was baked into `build_context_map`, so the cutover is a minimal
`build_initial_prompt` (zero repo content, query PRESERVED) rather than a literal empty
string — full-removal governs prompt *content*, which is satisfied; `build_context_map` is
retained for reference, simply no longer called. (b) Adds the **blind-start guard**: a
fourth read-only tool `ls(path=".")` — a `confine_path`-guarded SINGLE-DIRECTORY listing
(lists files AND dirs, the layout-discovery affordance `glob` lacks, since `glob` filters
out directories), clamped by a NEW `scout_ls_max_entries: int = 200` Settings field. This
is a DELIBERATE, RECONCILED tool-suite change: the exact-tool-count convention was amended
`{grep,glob,read_span}` → `{grep,glob,read_span,ls}` with a rationale, and BOTH hard-count
tests updated in the same commit — NOT the silent weak-model tool creep the guard exists
to catch. (c) Plumbs the ALREADY-TYPED four-cause taxonomy
(`ScoutUnavailable.cause`/`LoopResult.outcome`) to the report layer: `runner`
`_scout_degrade_cause` + four additive per-cause counts alongside the retained collapsed
`scout_degrade_count`, `report.SCHEMA_VERSION 0026/1 → 0027/1` via `_AGGREGATE_DEFAULTS`
(`loop-wallclock-exhausted` is the PRE-EXISTING spec-0024 between-turns ceiling merely
surfaced, not new scope). (d) RETIRES `turns_used` as a why-did-it-end signal (executable
source-sweep guard; it survives only as the 0022 turns-CONSUMED measurement). The SUT
boundary held — cutover, not redesign: `ScoutBackend`/`Locator` seam, gate, matrix,
orchestrator, and `submit_citations` byte-untouched. **AC5 HOLD — capability UNMEASURED:**
map removal is PROVEN live (turn-1 ~10,181 → ~60 tokens, ~170× cut, both cases), but the
live localization is BLOCKED downstream — both astropy-12907 and django-12774 degraded
`cause=model-unreachable` @~300s (`turns_used=None`), because the model ran away generating
(Qwen3 thinking + unbounded generation) and never FINISHED, so it never localized.
`model-unreachable ≠ "can't localize"` — the SAME degrade-masks-outcome trap the 0026 RCA
corrected. The AC5 test (`test_harness_live.py`) ships `xfail` (non-strict) that flips to
xpass when the fix lands. Measured diagnosis: `/no_think` alone still runs away (180s);
`/no_think` + a `max_tokens` cap tool-calls in 13.2s — TWO knobs in the
generation-control family, distinct from map removal. **AC7 committed-error correction:** a
factual error shipped in `1ef917f` (0020–0023 "likewise confounded" by the eager map) was
narrowed to **0026-ONLY** and CORRECTED across all three surfaces (spec AC7, the RCA
Impact, the operator-run-findings note) in `0fdcb57`; `build_context_map`/`ExplorerBackend`
are net-new in spec 0024, so 0020–0023 (pre-0024) ran on the retired FastContext backend
and never touched the eager map → **not confounded** (moot for current Scout). The close
ASSERTED (T14) — not merely noted — that all three surfaces are 0026-only,
FastContext-scoped, zero residual "confounded" claims, because a mis-correction that
half-reverts is worse than the original error.
**Why:** the recurring project lesson — a degrade that masks an outcome silently reads as
a capability finding — applied at the harness layer: the eager map was a
repo-size-dependent prompt-bloat *push* that the loop's own timeout floor converted into a
phantom "not found." Removing it (pull, on-demand `ls`) is proven cheap and
repo-size-independent, and surfacing the four terminal causes per-cause is what makes a
re-emptied case DIAGNOSABLE (which state it hit) rather than one collapsed boolean. But
the proof stops at the prompt: **generation control** (disable Qwen3 thinking + a tuned
`max_tokens` cap + likely a more directive tool-use prompt) is a **BLOCKING PREREQUISITE**,
not 0027 cleanup — it GATES the 0026 pilot re-run, the model bake-off, AND any
re-validation of localization capability. Until it lands, we cannot measure whether ANY
model localizes through the explorer.
**Consequence — the harness is proven cheap-prompt, but model-drive-to-citation is
UNPROVEN.** Units T1–T11 green; the live proof (`operator-run-findings.md`) recorded map
removal PROVEN and AC5 a HOLD. Report `SCHEMA_VERSION 0026/1 → 0027/1`; the explorer tool
suite is now EXACTLY four (`{grep,glob,read_span,ls}`); `scout_ls_max_entries` added.
**Named blocking follow-up:** a generation-control spec (thinking-off + tuned `max_tokens`
cap + directive prompt), re-run AC5/AC6 here, then the 0026 pilot re-run and the bake-off.
Other standing follow-ups unchanged: Tier-0 AST symbol tool; a total-request wall-clock
deadline (0017-caveat); the tool-call-serving preflight (llama.cpp `--jinja` emits
`tool_calls`, Ollama's `--no-jinja` chatml path does not). See specs/0027-harness/.

## 2026-07-06 — **Spec 0026 (eval) built the terse-query ranking INSTRUMENT — labels JOINED (never transcribed) by `case_id` from the sha256-pinned raw fixture, only the QUERY rewritten to Harpyja's terse shape; a version-gated loud loader lets additive-defaults (legacy) and reject-if-missing (terse guard) coexist; the leakage guard is an EXECUTABLE two-model blind protocol carried in a loud-validated provenance shape (state- not capability-independence, model-circularity named-not-closed, paired-ranking retained CO-PRIMARY as the model-independent floor); a frozen/hashed AC8 pilot power-gate STOPs before authoring the full set. INFRA COMPLETE but the instrument is NOT yet usable — the offline blind-authoring pilot (real queries) is the pending deliverable and the committed terse fixture is PLACEHOLDERS; suite 1010 pass, ruff clean; SUT byte-frozen**

**Spec:** specs/0026-eval/
**Decision:** Model selection for the explorer's driving LLM needs an eval set that
resembles Harpyja's REAL target — terse NL queries — not SWE-bench's verbose issue
prose (0020–0023 proved that distribution wrong; its only virtue was free
patch-derived labels). This spec builds the smallest labeled set that can RANK
candidate models — a deliberately small, paired, RELATIVE-ranking instrument, NOT an
absolute benchmark — as a pure measurement/dataset harness in the 0019–0025
measurement-not-construction lineage: the SUT (`harpyja/scout/`,
`harpyja/orchestrator/`, `Settings`) stays **byte-frozen**, all code is additive under
`harpyja/eval/`. **This unblocks the bake-off; it is NOT the bake-off.** Five durable
points. (1) **The strategic bet: reuse the free label, rewrite only the query.** Keep
the sha256-pinned, patch-derived `expected_spans` as ground truth (frozen at the
audited network `convert` stage — no gold patch is committed, so nothing is
re-derived; the sha256 pin IS the integrity guarantee, provenance
`patch-derived-at-convert`) and pair each with a terse Harpyja-style query authored
from the issue's INTENT. (2) **Labels JOINED, not copied — one integrity-pinned
authority.** The terse fixture stores NO spans; `terse_dataset.load_terse_dataset`
asserts `sha256(raw.jsonl) == provenance.raw_fixture_sha256` FIRST (refusing to join
against an unverified source) and then joins `expected_spans` / `base_commit` /
source-issue text by `case_id` from the pinned `swebench_verified.raw.jsonl`. So the
raw fixture is the sole authority and there is literally no second transcription of a
span; `base_commit` stays a raw-record key (review B2, exposed via `JoinMeta`, not
promoted onto `EvalCase`). (3) **A version-gated loud loader resolves the
additive-defaults-vs-reject-if-missing contradiction.** A NEW
`dataset.DATASET_SCHEMA_VERSION = "0026/1"` (introduced, not bumped; distinct from
`report.SCHEMA_VERSION`) gates `_parse_case`: a terse-tagged row MAY omit
`expected_spans` (joined later) but MUST carry the leakage-guard provenance
(`_parse_terse_guard`), while a legacy/seed row (no tag) loads unchanged with the guard
fields defaulted — additive-defaults (backward-compat) and reject-if-missing (the terse
guard) coexist in ONE loud loader. (4) **The leakage guard is an EXECUTABLE two-model
blind protocol whose proof is carried in a loud-validated shape, with trust RELOCATED
not eliminated.** Layer (a) is a near-vacuous code-identifier token tripwire recomputed
against the JOINED source issue (a stored value is never trusted). Layer (b), the real
guard, is a one-time OFFLINE operator/dev activity (same out-of-air-gap posture as
0010's `convert`/`provision`): `terse_authoring.py` takes INJECTED author/verifier
callables (separately-invoked model contexts via the operator's cross-model seam, NEVER
the product `ModelGateway` — pinned by an ast import-absence guard that also proves no
product runtime module imports the tool) — one model authors the query with the gold
span WITHHELD, a separately-invoked verifier records a per-case verdict, and a `leaky`
verdict routes to drop (never a silent keep). The load-bearing proof lives in the
loud-validated `authoring_provenance.py` sidecar (`AUTHORING_SCHEMA_VERSION = "0026/1"`,
per-case `AuthoringRecord` with validated verdict/outcome enums + hash-consistency +
aggregate leaky/dropped counts), NEVER prose; pin (2) blindness is the OPERATIONAL
`assert_author_input_blind` (the recorded author input contains none of the gold path
or `path:line` citation). Labelled exactly **"executable + reviewable," NOT
"structurally enforced"** (a determined leak could still pass). Three pins:
independence is STATE-level (separate invocation), NOT CAPABILITY-level (recommend
author≠verifier family; record model-under-test overlap); blindness verified real
operationally; the verdict is DATA. **Named residual risk (not closed):** model
CIRCULARITY — author, verifier, and subject models may share a training-distribution
blind spot that is CORRELATED (does not cancel). Held by author≠verifier≠subject
diversity plus a model-independent FLOOR retained **CO-PRIMARY** (not a mere backstop):
because the instrument is RELATIVE, shared leakage inflates both arms and largely
cancels in the within-case discordant comparison — the one defense that SURVIVES the
circularity risk. (5) **A frozen/hashed AC8 pilot power-gate STOPs before authoring the
full set.** `ac8_pilot.py`'s `PREREGISTERED_AC8_CONFIG` (frozen; two reference models
`hf.co/Qwen/Qwen3-8B-GGUF:latest` vs `qwen3:4b-instruct`, `pilot_n=10`,
`full_n_target=30`, `min_discordant_pairs` reusing the committed
`PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS = 8`) + `AC8_CONFIG_HASH`; a discordant
localization flip is SIGNAL-BEARING only when the arms disagree on whether they LOCATED
the target (an empty↔wrong-file flip is NOISE, excluded — guarding exactly 0023's
near-zero floor); total pure `decide_ac8` projects the pilot signal-rate to full size
and returns `UNDER_POWERED_STOP` below the floor.
**Why:** the recurring project lesson — a guarantee that isn't structurally enforced
silently becomes false — applied at the dataset layer: one integrity-pinned label
source, validated provenance gated by a schema version, a leakage guard whose proof
lives in a validated shape, and a representativeness caveat that travels with every
result (`report.SCHEMA_VERSION 0025/1 → 0026/1`, pinned `representativeness_caveat`
naming the Python language monoculture). The bake-off can rank models honestly only if
the yardstick resembles the real target and its trust is relocated, not overclaimed.
**Consequence — the INSTRUMENT shipped and is unit-complete; the SET is NOT authored
and the instrument is NOT yet usable.** All unit ACs green (suite 1010 pass / 45
integration deselected, ruff clean); AC1–AC5/AC7 unit-complete, AC6/AC8 unit-covered
with fakes and the live run correctly `@pytest.mark.integration` (skip-not-fail on CI;
deliverable run fails loud under `HARPYJA_REQUIRE_LIVE_STACK=1`). **The committed
`swebench_verified.terse.jsonl` is five PLACEHOLDER cases** (`gold_withheld: false`,
`query_provenance: "placeholder-pending-offline-authoring"`) — a unit-test JOIN target,
not a real set. **The offline two-model blind-authoring pilot (real queries) is the
REMAINING DELIVERABLE, not a formality**, delegated to an operator on the served
loopback stack. When it fires, **AC8's likely `UNDER_POWERED_STOP` is a SCOPED FINDING,
not a rerun-until-it-passes loop** — "these two general reference candidates under-power
terse-query ranking at 0023's near-zero-localization floor," a valid typed close naming
the finder-capability next step (`N38_PLUS_FINDER_CAPABILITY`), never a set authored to
rank noise.
**Deviation:** T19's sha256-hoist was DEFERRED — hoisting the 3-line `_sha256_file`
into a shared helper would couple the lightweight loader to the heavy
HuggingFace-`datasets`-importing `swebench_eval` for three lines; the one-oracle reuse
pin (AC8's "located" predicate == `locate_accuracy`'s file-level credit buckets) was
done instead and `terse_dataset` keeps its own local copy.
**Named follow-ups carried forward:** the offline blind-authoring pilot (real queries +
the live AC8 go/no-go run); the model bake-off itself (this builds its instrument); the
finder-capability work (`N38_PLUS_FINDER_CAPABILITY`) from 0022/0023; the deferred
Axis-2 problems (codebase-character AND the Python language monoculture — a
legacy/undocumented and a non-Python eval); OQ2/threshold tuning; the Tier-0 symbol
tool. Standing carry-forwards unchanged (judge thinking-defense, permanent ceiling
calibration, Deep co-residency budget, Wave-2.1 substring/fuzzy).

## 2026-07-06 — **Spec 0025 (removal) DELETED the FastContext surface + dependency and made the native `ExplorerBackend` the SOLE Scout backend — one canonical `build_scout_engine` factory, the turns-used measurement MIGRATED onto a native `ScoutEngine.last_turns_used` seam before the `agent_factory=` seam was cut, `normalize.py` DISENTANGLED (suffix-recovery removed, shared tally core kept), report schema `0014/1 → 0025/1` with the recovery fields retired-to-zero; two behavior changes rode in (the isolated probe now floors a `ScoutUnavailable` degrade to EMPTY; the default gateway now pins `lm_model` so Scout stops 404-ing on Ollama); suite 985 pass / 23 skip, AC8 cutover LIVE-green**

**Spec:** specs/0025-removal/
**Decision:** Close the parallel-factory deviation 0024 left open — FastContext's
upstream 4B was retracted and is unobtainable (an unmaintainable dependency,
independent of the 0020–0023 localization finding), and two Scout paths is two
things to keep honest — by removing FastContext ENTIRELY and making the explorer
the sole Scout backend. This had to land BEFORE the representative-eval + model
bake-off, or the bake-off would benchmark through a backend that isn't the real
one. A staged deletion, not a redesign: the explorer loop, the
`ScoutBackend`/`ScoutEngine`/`Locator` boundary, the gate, matrix, and orchestrator
are untouched — callers are repointed and dead code is deleted behind executable
absence guards. Five durable points. (1) **One canonical factory.**
`build_scout_engine` is the SINGLE production Scout factory and constructs
`ExplorerBackend`; the parallel `build_explorer_scout_engine` is deleted (body
folded in). (2) **Migrate-before-delete for a capability-carrying seam.** The
`agent_factory=` seam carried a LIVE measurement — the 0022 turns-used diagnostic,
which scraped FastContext's trajectory JSONL via `count_turns` /
`counting_agent_factory`. `scout_max_turns` is the loop *cap* (a budget), NOT the
turns-*used* count, so a native per-run seam was created: `LoopResult.turns_used` →
`ExplorerBackend.last_turns_used` (set on submit AND both exhaustion-degrade paths,
reset per run) → `ScoutEngine.last_turns_used` (getattr-guarded). The diagnostic was
repointed and proven green (`turns_used_source` now `"explorer"`/`"unavailable"`)
BEFORE the `agent_factory=` seam was cut — a migration, not a dead-seam delete.
(3) **Disentangle a mixed module, don't symbol-delete it.** `normalize.py` mixed
FC-era code with a shared core: only the suffix-recovery (`_recover_suffix` /
`MIN_TAIL_SEGMENTS`, spec 0012) is removed; the shared `normalize_spans` /
`normalize_spans_with_tally` / `ScoutTally` / `last_tally` core is KEPT (it is the
live `ScoutEngine` shape-tally feeding `runner`, `locate_probe`, and the 0022
`locate_accuracy` diagnostic — NOT FastContext-only), and the explorer's citation
path was proven to resolve with recovery gone (its submitted paths come from real
tool output). Recovered counts are structurally zero. (4) **Executable absence
guards over point-in-time greps.** New `test_fastcontext_absent.py` (AST-based
import-absence + public-name assertions — `fastcontext` / `client` / `tools`
modules, the FC error causes `FASTCONTEXT_MISSING`/`CLI_MISSING`, the FC-only
Settings fields) and `test_packaging.py` (the `pyproject.toml` / `[tool.uv.sources]`
`fastcontext` declaration) rot-false when a deleted symbol reappears, where a prose
grep goes stale. FC-only Settings (`scout_max_tokens`/`scout_temperature`/
`scout_reasoning_effort`) removed; `scout_model` KEPT as the served Verification-Gate
A/B baseline (`verify_method="scout_model"`, 0018), explicitly scoped OUT of the
FC-removal drift guard (which asserts "no default names an *unserved* tag," NOT "no
default is FC-branded" — that would contradict the kept served baseline).
(5) **Report schema `0014/1 → 0025/1`.** `fc_citation_recovered_{spanned,filelevel}`
are retired-to-zero (kept for schema stability, no longer sourced from `ScoutTally`);
the shape-tally `fc_citation_{spanned,filelevel,dropped}` STAY populated — now by the
explorer. Legacy blocks still validate via `_AGGREGATE_DEFAULTS`.
**Why:** an unmaintainable retracted dependency is unshippable regardless of
retrieval quality, and the bake-off must measure through the real backend — so the
explorer had to become the ONLY Scout path first.
**Two behavior changes (flagged, not buried):** (a) **The isolated eval probe now
floors a typed `ScoutUnavailable` to EMPTY, not a crash (T18) — a genuine semantic
change, not a test fix.** The FastContext backend returned honest-empty on failure,
but the explorer RAISES on turn/wall-clock exhaustion (or model-unreachable); the
probe runs Scout in isolation (no orchestrator degrade wrapper), so `_run_scout_query`
had to learn the explorer's degrade taxonomy — it records the degrade as the same
"no usable citation" floor the orchestrator would produce. (b) **The default
`build_scout_engine` gateway now pins `settings.lm_model` (T17) — a
production-correctness fix, distinct from the pure cutover.** The prior default used
`ModelGateway.model`'s `"local"`, which 404s on Ollama's tag-routed API, so the
production Scout path would have failed on Ollama; pinning `lm_model` (default
Qwen3-8B) is the AC8 "thread the model tag through the wiring" resolution — and means
the explorer now runs on `lm_model`, the SAME model as Deep.
**Deviation / discoveries:** `scout/tools.py` was a SECOND-ORDER orphan — its
`build_tool_whitelist` was FastContext's tool whitelist, orphaned BY the primary
deletion (only its own test referenced it after) — removed because leaving it is the
silently-orphaned case; a deletion spec must RE-SCAN for newly-orphaned code after the
primary deletion. Naming debt RECORDED, not fixed: the kept `fc_citation_*` shape-tally
fields are now populated by the explorer, so the `fc_` prefix is a misnomer — treat
them as backend-neutral (or rename with a future bump). The `test_gateway.py` E501 fix
is housekeeping.
**Consequence:** Tier 1 is now the native explorer loop, full stop — FastContext is
gone from the tree and the lockfile. Result: full suite **985 passed / 23 skipped**,
ruff clean; the AC8 cutover proof passed LIVE end-to-end through the explorer on
Qwen3-8B / loopback Ollama, zero non-loopback egress. The parallel-factory deviation
from 0024 is closed. **Named follow-ups (unchanged):** the representative eval set;
the model bake-off (OQ1/OQ3 budget tuning); the Tier-0 symbol tool; the finder-capability
work (`N38_PLUS_FINDER_CAPABILITY`) from 0023's operator run.

## 2026-07-06 — **Spec 0024-v2 (Scout v2) RETIRED the FastContext Tier-1 backend and REPLACED it with a self-contained native `ExplorerBackend` Harpyja owns end-to-end — a general OpenAI-compatible tool-calling model driven over exactly three read-only tools (grep/glob/read_span) to a tool-call-native `submit_citations` terminal action, behind the UNCHANGED `ScoutBackend` seam; bounded loop + citation-preserving truncation + air-gap-before-loop, four typed degrade causes; unit-complete AND live-green (Qwen3-8B, ~28s, zero non-loopback egress); FastContext adapter LEFT in-tree off the production path pending a dedicated cleanup**

**Spec:** specs/0024-v2/
**Decision:** Retire the FastContext-backed Scout — the upstream 4B model was
retracted and is unobtainable, its only surviving artifacts lossy/broken
quantizations (an unshippable dependency, independent of the 0020–0023
localization-quality finding) — and replace it with a native explorer loop behind
the byte-unchanged `ScoutBackend`/`ScoutEngine`/`Locator` seam (the orchestrator,
gate, matrix, formatter, `engine.py`, `normalize.py`, Locator boundary all
untouched; unit tests keep driving fakes). Construction, not measurement: a new
`ExplorerBackend` assembles four new modules over the existing machinery and swaps
in via a NEW production factory. Load-bearing points. (1) **Scout stays a locator,
not a diagnoser, and that guard is now ENFORCEABLE in the type, not a soft check.**
The loop ends by calling a dedicated `submit_citations` terminal tool with
STRUCTURED citation args validated under a STRICT schema (unknown/extra/
diagnosis-shaped fields → `SubmitCitationsSchemaError`), normalized via the
unchanged `normalize_spans` to repo-confined, clamped `source_tier=1` CodeSpans —
malformed/out-of-repo/over-budget refs dropped, empty an honest-empty `[]`. This
resolves OQ2: it REPLACES the inherited 0011/0012 `<final_answer>` text-grammar
parse path — structured args over regexing prose, killing the exact text-parsing
fragility class behind three of the FastContext era's worst bugs; a
diagnosis-shaped field failing schema is the enforceable form of the
locator-not-diagnoser boundary. (2) **Untrusted-caller boundary, mirroring the
Deep host tools.** `build_explorer_tools` returns EXACTLY `{grep, glob, read_span}`
— each `confine_path`-guarded, Settings-bounded, READ-ONLY closures, no
shell/write/terminal; the count is asserted so a weak model cannot motivate
tool-suite creep (a weak-model result is a finding, not a bug). `grep`/`glob`
share ONE bounded `RipgrepEngine` with the Deep `search` host tool (invariant B —
single source of truth for bounds and repo-confinement, never a second drifting rg
surface); `read_span` reuses `server.tools.read_snippet`; `glob` normalizes to
file-level `CodeSpan` records. The pre-model context map is built from the manifest
(filtered tree, no file bytes), and its vendor/test/generated exclusion is a
DISPLAY concern ONLY — an excluded test/vendor file stays reachable via the tools
(map-filter ≠ tool-scope filter). (3) **Bounded loop + self-recovery.** One tool
call/turn, raw output appended, capped at `scout_max_turns` AND a distinct
whole-loop `scout_wall_clock_s` ceiling (turns ≠ time for a general model; the
gateway `lm_http_timeout_s` is the per-CALL floor, the ceiling stops one slow turn
wedging the run). Two deterministic recoveries: loop-detection on an exact
`(tool_name, normalized_args)` repeat over `scout_loop_repeat_n` consecutive
no-new-span turns → corrective injection; and CITATION-PRESERVING truncation past
`scout_history_char_cap` — it drops ONLY stale navigational chatter, NEVER a
`read_span`/`grep` observation whose location could still be cited, re-injecting a
compact dropped-span index if recency-capping forces dropping the raw text. The
binding invariant — truncation must never convert a real find into honest-empty —
is proved by the negative (AC5 preservation case), not merely that truncation
fires. (4) **Air-gap in the one helper, before any I/O.** A NEW
`ModelGateway.complete_with_tools` (returning `{content, tool_calls}` from
`choices[0].message`) routes through `assert_local` BEFORE the transport, and
`ExplorerBackend` calls `assert_local()` once before the loop starts — a
non-loopback endpoint raises `AirGapError` and the loop never starts. The gateway
stays the only outbound caller; AC10 OBSERVES zero non-loopback egress via the
shared `_deny_nonloopback_egress` harness from the 0007/0014 air-gap tests. (5)
**Typed degrade UNCHANGED in posture, extended in vocabulary.** Four distinct
stable causes — `MODEL_UNREACHABLE`, `LOOP_TURNS_EXHAUSTED`,
`LOOP_WALLCLOCK_EXHAUSTED`, and reused `BACKEND_ERROR` — each a terminal loop state
routed to the Tier-0 floor; a well-formed empty `submit_citations` is honest-empty
(never a raise); `AirGapError`/`RipgrepMissingError` propagate as floors; degrade
rate stays a first-class reported field (the "every floor reports its rate"
convention). Five NEW provisional `Settings` budgets (`scout_max_turns=12`,
`scout_wall_clock_s=300.0`, `scout_loop_repeat_n=2`, `scout_history_char_cap=60000`,
`scout_glob_max_paths=400`), each docstring-justified and FLAGGED for the bake-off
(OQ1/OQ3) — a general model needs more turns than FastContext's old `=6`.
**Why:** an unmaintainable retracted dependency is unshippable regardless of its
retrieval quality; owning the loop end-to-end also removes the buggy third-party
harness confound that made prior model tests uninterpretable, yielding a clean,
model-AGNOSTIC rig (any OpenAI-compatible tool-calling model via the gateway) for
the later bake-off.
**Deviation:** the swap ships as a PARALLEL factory
`wiring.build_explorer_scout_engine` (ExplorerBackend), NOT an in-place swap of
`build_scout_engine`; the FastContext factory and its eval callers are left
byte-untouched. Deleting the FastContext adapter/dependency is a DEFERRED cleanup
spec — the parallel factory keeps the backend swap and the removal from entangling
in one diff and lets the new backend be proven first.
**Consequence:** Tier 1 is now the native explorer loop; the FastContext adapter
remains in-tree but OFF the production path. Result: unit-complete (all 10 ACs) and
LIVE-GREEN — both integration tests passed against Qwen3-8B on loopback Ollama
(~28s, zero non-loopback egress); full suite 1015 passed / 23 skipped, ruff clean.
**Out-of-scope staged follow-ups (recorded):** the AST symbol-search tool
(Tier-0-as-a-tool, the minimal-tools baseline's staged second round); the model
bake-off (OQ1/OQ3 budget tuning); the representative eval set; and the FastContext
code + dependency deletion (which closes the parallel-factory deviation).

## 2026-07-05 — **Spec 0023 OPERATOR RUN — fired the benchmark-fit reformulation probe on REAL SWE-bench long-issue text (FastContext-4B, no instrument change): formal `HOLD_INCONCLUSIVE`, but QUERY_SHAPE FALSIFIED and 0022's `RETRIEVAL_FUNDAMENTAL` corroborated → next spec is FINDER-CAPABILITY, not a reformulation/benchmark layer**

**Artifact:** specs/.archive/0023-benchmark-fit/operator-run-findings.md (self-contained,
with per-case tables). Raw run data machine-local under `eval_work/benchmark_fit_run/`
(gitignored). This is the operator measurement 0023 named as follow-up #1; it runs the
byte-frozen instrument via public seams only — **no `harpyja/` source written or modified**.
**Decision:** Resolve whether 0022's provisional `RETRIEVAL_FUNDAMENTAL` is a real capability
wall or a `BENCHMARK_UNREPRESENTATIVE`-via-query-shape artifact, by running the shipped
discriminator on the 38 real `point` cases (all `is_raw_issue`-admitted, all worktrees
present) with `HARPYJA_REQUIRE_LIVE_STACK=1`, air-gap held. The SUT is **FastContext-1.0-4B-RL-Q8**
(`scout_model` default); qwen3:8b is ONLY the labeled LLM sensitivity *distiller* (it never
retrieves). **The load-bearing precondition gate PASSED** (the "does green connect to the
measurement" check): one real case run live → `is_raw_issue` admitted it (usable_n=1, NOT 0),
both arms ran, the McNemar cell incremented — the instrument fires on real input, unlike the
terse legacy fixtures (delta≈0 by construction). **Primary (mechanical) arm, stopped at the
pre-registered floors** (`usable_n=14≥12`, `discordant=8≥8`; remaining cases cost 5–30 min
each — psf__requests-1724 alone 1831s — so exhausting all 38 buys only marginal power,
cheap-before-expensive): raw buckets `EMPTY×11, RIGHT_FILE_WRONG_SPAN×2, WRONG_FILE×1`
(**79% empty, 0/14 span-CORRECT**); `delta_empty=+0.143` (BELOW the 0.20 band),
`delta_file_accuracy=−0.071`, exact McNemar p=0.727 (does NOT reject) → **Axis-1 =
INCONCLUSIVE(AXIS_SIGNAL_DISAGREEMENT)** — floors MET, a *substantive* trigger (empty-rate
delta positive but file-accuracy delta negative: distillation shuffles empties into WRONG_FILE
guesses without improving real localization), NOT insufficient power. **LLM sensitivity arm
(qwen3:8b, non-primary):** 7/14 accepted, 7/14 hard-rejected by the subset guard; scored n=5,
`llm_delta_empty=−0.20` — the SMART, identifier-RETAINING distiller ALSO fails to help
FastContext (astropy-12907 raw=RIGHT_FILE→llm=EMPTY, same as mechanical), so the mechanical
arm's identifier-stripping is **not** the confound — corroboration across a dumb AND a smart
distiller closes the "mechanical rule too crude → truth is QUERY_SHAPE" escape hatch. **Axis-2:**
`representative=True` by the pre-registered rule (doc_density=`high` on well-documented OSS, so
the low∧weak AND-gate does not fire) — with a NOTED rule limitation: the threshold only flags
*undocumented* weak-proxy benchmarks, so it under-detects SWE-bench's unrepresentativeness
(SWE-bench is a weak proxy for the terse-NL/undocumented-legacy target yet documented OSS). **Composed
2×2 → `HOLD_INCONCLUSIVE`.**
**Why (substantive, beyond the formal gate):** (1) 0022's `RETRIEVAL_FUNDAMENTAL` is now
corroborated on REAL multi-paragraph issue text (not the terse fixtures) — 79% empty, 0/14
span-correct on the verbose issues themselves. (2) **QUERY_SHAPE is FALSIFIED:** terser queries
do not materially cut emptiness (delta below band, McNemar n.s.) and do not improve right-file
accuracy, across BOTH distillers. (3) The formal gate cannot certify CAPABILITY only because the
finder's localization floor is so near-zero (0/14 correct, 2/14 right-file) that discordant pairs
are empty↔wrong-file *noise* — which is what makes the two axes oppose at ±1-case magnitude; that
inability is itself the strongest evidence the bottleneck is retrieval CAPABILITY, not query shape.
**Consequence:** the reformulation escape is falsified → **the next spec is FINDER-CAPABILITY work
(`N38_PLUS_FINDER_CAPABILITY`), NOT a reformulation/query layer and NOT a benchmark swap justified
by query shape.** Enlarging N (exhausting the 38) would likely tip the *formal* gate
INCONCLUSIVE→CAPABILITY but would not change the substantive conclusion (axis-disagreement is
noise-level; distillation-doesn't-help is robust) — a cheap-vs-power call for the finder-capability
spec. **Two operator lessons (recorded):** (a) a Scout-arm + LLM-distiller-arm must run in
DECOUPLED phases (distill-all → score-all); alternating per case thrashes the single-GPU Ollama
model-swap (a 120s timeout hit a cold load); (b) the operator callable must itself apply the
pre-registered `LLM_PROMPT` — `llm_distill_guarded` passes raw `issue_text` to the callable by
contract. **Standing carry-forwards unchanged** (OQ1 reachability-vs-power floor; OQ2 promote
`delta_file_accuracy`; Axis-2 threshold refinement now added; judge thinking-defense; Deep
co-residency budget; Wave-2.1 substring/fuzzy).

## 2026-07-05 — **Spec 0023 (benchmark-fit) shipped the typed, two-axis, PRE-REGISTERED discriminator that decides whether 0022's provisional `RETRIEVAL_FUNDAMENTAL` is a real capability wall or a `BENCHMARK_UNREPRESENTATIVE` artifact — a within-case paired McNemar probe (Axis 1) × a structured representativeness record (Axis 2), verdict a PURE FUNCTION over a frozen config, dual-distiller honesty guard; unit-complete + live-smoke green but the operator VERDICT deliberately NOT yet emitted; SUT byte-frozen**

**Spec:** specs/0023-benchmark-fit/
**Decision:** Build the discriminator 0022 left operator-gated — the branch that decides
whether Scout's empty-rate is a **localization capability wall** or an **artifact of
SWE-bench's multi-paragraph issue prose** (nothing like Harpyja's terse-NL target) — as a
pure **measurement/eval** diagnostic in the 0019/0020/0021/0022 measurement-not-construction
lineage: the SUT (`harpyja/scout/`, `harpyja/orchestrator/`) stays **byte-frozen and
read-only**, all code is additive under `harpyja/eval/`, and the deliverable is a typed,
two-axis, pre-registered verdict machine (+ `findings.md`), NOT a Scout fix or the N=38 run.
Cheap-before-expensive: this bounded probe is logically UPSTREAM of both the N=38
confirmation and any finder swap — it decides which experiment is even correct before
either is spent. Five durable points. (1) **The verdict is a PURE FUNCTION over a FROZEN,
pre-registered config, so it cannot be steered after seeing the data — and its threshold is
DERIVED FROM THE TEST'S OWN REACHABILITY ARITHMETIC, not a round guess.** `benchmark_fit.py`
carries a `frozen=True` `PREREGISTERED_CONFIG` (`MIN_DISCORDANT_PAIRS=8`,
`DELTA_EMPTY_BAND=0.20`, `min_n=12`, `alpha=0.05`) and the mechanical rule / LLM prompt are
hashed before any run (`MECHANICAL_RULE_HASH`, `LLM_PROMPT_HASH`); `decide_axis1` /
`compose_verdict` are **total functions with non-overlapping predicates** pinned by grid
totality tests. `MIN_DISCORDANT_PAIRS=8` is not a round number: under H0 the discordant
pairs are a sign test at p=0.5, so an exact two-sided McNemar can only clear α=0.05 once
`n_discordant ≥ 6` (6/0→0.03125 rejects, 5/0→0.0625 fails); 8 buys one contrary pair of
slack (8/0→0.0078, 7/1→0.070 still borderline → `INCONCLUSIVE`). **5 was wrong** (both
reviewers, C2): it made `QUERY_SHAPE` almost unreachable — the small-N trap in reverse.
(2) **Axis 1 is a WITHIN-CASE PAIRED A/B over a BINARY outcome, so its power lives in the
McNemar DISCORDANT PAIRS — the effective sample size is the discordant count, not N.** Each
case runs Scout on the **raw** multi-paragraph issue and on a **distilled terse query** for
the *same* gold span (per-case difficulty cancels); `aggregate_paired` computes `delta_empty`
/ `delta_file_accuracy` / the discordant `(b,c)` FROM retained `PairedRow`s, never a
difference of aggregate rates (AC3). The exact McNemar is implemented from scratch
(`math.comb`, no scipy). The honest consequence, forced out by review: a binary paired probe
is NOT as cheap as the paired-continuous intuition suggested — reaching 8 flips may need
~15–25 raw cases (still << N=38, Scout-only-cheap, but not "a handful"), and the config says
so. (3) **The distiller is DUAL with ASYMMETRIC roles: the verdict-driving arm is made
STRUCTURALLY INCAPABLE of the bias it is trusted against; the smart arm is a LABELED
non-deciding SENSITIVITY check.** `mechanical_distill` (PRIMARY) is a single case-agnostic,
gold-span-blind rule whose output tokens are a **subset of the raw-issue tokens**
(extraction, never generation) that STRIPS code-identifier tokens (paths, dotted/CamelCase
symbols, stack-trace frames, quoted error strings) so the query is natural-language-shaped
(matching Harpyja's terse-NL target) — it therefore *cannot manufacture a false
`QUERY_SHAPE`* by injecting gold vocabulary, and every stripped token is recorded per case
for audit. `llm_distill_guarded` (LABELED, non-primary) is a more natural reformulation under
a fixed prompt, gated by a post-hoc token-subset HARD REJECT (`DistillRejected`); it never
decides — it only disambiguates the one case the mechanical arm cannot (a flat mechanical
`delta`: CAPABILITY *or* the rule under-distilled). Both arms' per-case outputs go in the
audit trail. (4) **Axis 2 (representativeness) is a STRUCTURED, pre-registered record that can
DOWNGRADE Axis 1's routing through a fixed 2×2 — not an inert caveat.** `RepresentativenessRecord`
(query-shape, repo-type, documentation-density, codebase-age, target-proxy-validity) yields a
`representative: bool` via a threshold declared before the assessment (`false` iff *both*
documentation-density=low AND target-proxy-validity=weak); `compose_verdict` encodes the
pre-registered 2×2 total over `Axis1Verdict × bool`: `QUERY_SHAPE×representative` → add a
reformulation layer; `QUERY_SHAPE×¬representative` → build a terse-query benchmark first,
**NOT a finder swap**; `CAPABILITY×representative` → N=38 + finder-capability work;
`CAPABILITY×¬representative` → retire SWE-bench as the yardstick; `INCONCLUSIVE` → hold. The
cell NAMES the next spec. (5) **The raw arm's provenance is a PER-CASE PRECONDITION so an
underpowered / degenerate-input run SELF-FLAGS rather than faking a null.** `is_raw_issue`
(AC8) excludes any case whose query is not a genuine multi-paragraph issue body from
`usable_n` and records it in `excluded_case_ids`, so a terse-fixture `delta≈0` **cannot
masquerade as `CAPABILITY`**; `usable_n < min_n` forces `INCONCLUSIVE(INSUFFICIENT_POWER)`.
`ReformulationResult` was EXTENDED, not rewritten (AC7): the six new fields append
last-with-defaults so 0022's constructor and callers stay byte-compatible.
**Why:** 0022 landed provisional `RETRIEVAL_FUNDAMENTAL` but **explicitly could not exclude
`BENCHMARK_UNREPRESENTATIVE`** — its discriminator was operator-gated and `delta≈0` by
construction on the terse legacy fixtures. Two expensive commitments hang off that unanswered
branch (the N=38 SWE-bench run; a finder swap), both premature until we resolve *which
experiment is correct*. SWE-bench was chosen for convenient patch-derived ground truth, not
for representativeness of Harpyja's terse-query / undocumented-legacy target — so this is the
eval discipline working one level up: questioning not the gate or the finder but whether the
benchmark fits the tool's purpose. Better one cheap probe than swapping a 4B that may be
perfectly adequate for the job it was built for.
**Consequence — the discriminator shipped and is unit-verified + live-smoke green; the
operator VERDICT is deliberately NOT emitted (gated on real long-issue cases). No SUT
change.** Shipped TDD-complete: **+52 unit** (`test_benchmark_fit.py` ×30, `test_distill.py`
×12, `test_locate_probe.py` +10), all green, ruff clean; 7 Scout-only integration tests PASS
LIVE (~56s, served Q8 FastContext stack). **Live smoke — green but non-informative BY
CONSTRUCTION:** the legacy fixtures are TERSE, so `is_raw_issue` excludes every one →
`usable_n=0`, all cases in `excluded_case_ids`, air-gap held under `_deny_nonloopback_egress`
— the AC8 guard working as designed (an underpowered run self-flags rather than faking a
`CAPABILITY`); it does NOT exercise the discriminator on real long-issue text. **Recorded
hashes:** `MECHANICAL_RULE_HASH=5a77d3ee…f3138`, `LLM_PROMPT_HASH=e7a54bab…a0079`. **Honest
scope — never claim the benchmark-fit question is answered:** the instrument shipped and is
live-verified; firing `decide_axis1` for real needs operator SWE-bench long-issue cases
(≥`min_n=12` usable, ≥8 discordant) with `HARPYJA_REQUIRE_LIVE_STACK=1`. Until then 0022's
provisional `RETRIEVAL_FUNDAMENTAL` stands and `BENCHMARK_UNREPRESENTATIVE` remains
not-yet-excluded — exactly the state this instrument exists to resolve. **Named follow-ups
carried forward:** (1) **the operator run** — fire `run_paired_reformulation_probe`
(mechanical primary; LLM sensitivity optional) then `decide_axis1` + `is_representative` +
`compose_verdict`; the 2×2 cell names the next spec, and a `QUERY_SHAPE`/¬representative
outcome routes to a benchmark/query-layer spec, **NOT a finder swap**; (2) **OQ1** — decide
before the live run whether to raise `MIN_DISCORDANT_PAIRS` from the reachability floor (8)
to a formal target-power floor (~12–15), which raises the raw-case count; (3) **OQ2** —
confirm whether `delta_file_accuracy` belongs in the primary Axis-1 rule (currently
diagnostic + the axis-disagreement `INCONCLUSIVE` trigger). Standing carry-forwards unchanged
(judge thinking-defense hardening, permanent ceiling calibration, permanent `lm_model`/Deep
choice, Deep co-residency budget, Wave-2.1 substring/fuzzy matching).

## 2026-07-05 — **Spec 0022 (Tier-1) shipped the Scout locate-accuracy DIAGNOSTIC — a two-granularity (file vs span) projection over the frozen oracle routing to one of four typed findings; live-fixture-verified `RETRIEVAL_FUNDAMENTAL` (provisional), the real 38-case + reformulation-probe discriminator operator-gated; SUT byte-frozen**

**Spec:** specs/0022-tier-1/
**Decision:** Characterize the Scout Tier-1 locate failure that DEFERRED OQ2 in 0020
(`correct_tier1_count = 0`) and that 0021 showed to be empty-dominant — precisely
enough to name its FIX — as a pure **measurement/eval** diagnostic in the
0019/0020/0021 measurement-not-construction lineage: the SUT (`harpyja/scout/`,
`harpyja/orchestrator/` tiers/gate/matrix/judge) stays **FROZEN and read-only**, all
code is additive under `harpyja/eval/` (`locate_accuracy.py`, `locate_probe.py`), and
the deliverable is a RECORDED TYPED FINDING (`findings.md`), not a Scout fix. Five
durable points. (1) **The taxonomy is a PROJECTION ABOVE the frozen oracle with ONE
deliberate SCORED re-map, guarded by an allowlist + a behavior snapshot (reprising
0020's `classify_g3_outcome`).** A 4-way MECE `LocateBucket` `{EMPTY, WRONG_FILE,
RIGHT_FILE_WRONG_SPAN, CORRECT}` with strict precedence `CORRECT >
RIGHT_FILE_WRONG_SPAN > WRONG_FILE > EMPTY` is computed over the byte-unchanged
`metrics.span_hit_kind` / `span_hit_secondary`; the sole departure from the oracle —
a path-only right-file hit (`span_hit_kind == "file"`) re-mapped to
`RIGHT_FILE_WRONG_SPAN`, NOT the oracle's coarse primary-hit — is the whole diagnostic
axis ("found the file" vs "found the span") and lives ONLY in the eval classifier
(`metrics.py` untouched), locked by a `SUT_SURFACE` frozenset allowlist + a
frozen-oracle input→output snapshot (0020 P2 precedent, a snapshot not a source grep).
(2) **Two-granularity scoring with the gap first-class is the discriminator between a
precision fix and a capability fix.** `score_distribution` reports file-level accuracy
(`|CORRECT ∪ RIGHT_FILE_WRONG_SPAN| / n`), span-level accuracy (`|CORRECT| / n`), and
`gap = file − span` as a first-class metric — a large gap is the PRECISION_FIXABLE
signal, a low file-level is the RETRIEVAL_FUNDAMENTAL signal. `decide_finding` routes
over PRE-DECLARED named bands to exactly one of `BENCHMARK_UNREPRESENTATIVE >
PRECISION_FIXABLE > RETRIEVAL_FUNDAMENTAL > MIXED` (ordered, all true conditions
recorded — 0020 pattern), each label naming the fix/next-spec it routes to. (3) **A
discarded internal signal is recovered via a PUBLIC injection seam, LABELED, never
fabricated (extends 0021's labeled-estimate rule).** Turns-used is not on
`search`'s return and the frozen client `os.unlink`s the FastContext trajectory JSONL
in its `finally`, so it is captured through the PUBLIC `build_scout_engine(...,
agent_factory=…)` seam: `counting_agent_factory` wraps the REAL
`make_fastcontext_agent` and `count_turns(trajectory)` reads it BEFORE cleanup fires —
no SUT edit — surfacing `turns_used_source ∈ {"trajectory","unavailable"}`, a labeled
gap on Path B / unwired, never a guessed counter. This corrected a planner
overstatement ("turns genuinely not surfaced"): they ARE tracked, just discarded.
(4) **Availability predicates must be TIER-SCOPED, and the fail-posture is SPLIT.** The
Scout-only tests initially reused the Deep-oriented `_live_stack_available` (needs Deno
+ the Deep model — irrelevant to a Scout probe) and **false-skipped** a Scout-capable
host; the additive `scout_stack_available()` (fastcontext + `rg` + a reachable Scout
endpoint; no Deno) makes the 4 integration tests RUN LIVE. Separately, per the 0020
"skip-not-fail is never a close" rule, the two postures are deliberately NOT the same
answer: integration test FILES stay skip-not-fail (CI-safe) but the DELIVERABLE run
fails loud (`require_live_stack` + `HARPYJA_REQUIRE_LIVE_STACK=1` + a `preflight`
gate), so a skip can never masquerade as a completed measurement. (5) **Honesty —
instrument shipped and live-fixture-verified ≠ the full operator measurement (0019/0020
lineage).** The finding is **provisional `RETRIEVAL_FUNDAMENTAL`**, with
`BENCHMARK_UNREPRESENTATIVE` NOT YET EXCLUDABLE: its discriminator (the reformulation
probe on REAL multi-paragraph SWE-bench issue text) is operator-gated — on the terse
fixture queries `delta_empty ≈ 0` by construction, which is not evidence about the real
question — and the real 38-case SWE-bench distribution needs the per-case checkouts
(the 0020 G2 operator setup), absent on this host.
**Why:** OQ2 (0020) and everything it tried to calibrate — the gate, the judge, the
escalation threshold — measure a signal Scout never produces; 0021 confirmed the
bottleneck is upstream Scout locate-accuracy and flagged `wrong_tier1_count` /
`span_hit_rate_primary` / `gate_catch_rate` CONTAMINATED. So this spec REGENERATES the
distribution from scratch (`scout_engine.search` outputs via the frozen oracle, never
0021's counts) and characterizes the failure's NATURE precisely enough to name the fix
spec, without touching Scout. The pre-registered prior (0021 → `RETRIEVAL_FUNDAMENTAL`
unless the probe fires) is recorded up front as a falsifiability guard against
confirmation bias.
**Consequence — the diagnostic instrument shipped and is live-fixture-verified; a
provisional typed finding is recorded; the real operator measurement is a named
follow-up. No SUT change.** Shipped TDD-complete: **835 → 883 unit pass** (+48,
`test_locate_accuracy.py` ×33 + `test_locate_probe.py` ×15), ruff clean; 4 integration
tests PASS LIVE (real Scout, ~44s). Live fixture smoke (N=5 legacy seed, real
FastContext Q8 on Ollama): `CORRECT=1, EMPTY=4, F=0.20, S=0.20, gap=0.00,
empty_rate=0.80`; `turns_used_source="trajectory"`, turns `(5,5,7,3,5)`. The gap ≈ 0
in both the smoke and the carried-forward prior (finds a file → tends to hit the span;
the dominant failure is empty / wrong-file) — the retrieval-fundamental signature, not
precision-fixable; and the empty cases used only 3–5 of the available turns and emitted
nothing → **early convergence to empty (a recall gap), NOT turn-exhaustion** (answers
AC4). **Named follow-ups carried forward:** (1) **the operator SWE-bench run — with TWO
CO-PRIMARY components, not one-plus-adjunct** (both with `HARPYJA_REQUIRE_LIVE_STACK=1`):
(1a) the N=38 stratified distribution (`run_locate_probe`) sizes the empty-dominance,
and (1b) the reformulation probe on REAL multi-paragraph issue text
(`run_reformulation_probe`) is the DISCRIMINATOR — 1a alone confirms
`RETRIEVAL_FUNDAMENTAL`'s magnitude but CANNOT distinguish "the 4B can't localize" from
"the 4B can't parse a long issue"; only 1b can, so it is the branch-selector, never a
secondary nicety (treating it as optional would let the N=38 empty-rate alone drive a
finder swap — the exact mistake this spec exists to prevent). (2) **the fix spec named
by branch** — if `RETRIEVAL_FUNDAMENTAL`, a finder-capability spec (larger/different
finder); if `BENCHMARK_UNREPRESENTATIVE`, a dataset/query-distill spec, **NOT a finder
swap** (a poor score on verbose GitHub-issue prose is a benchmark-fit artifact against
Harpyja's terse-query target, and swapping the 4B on that basis discards a finder that
may be perfectly adequate for the job it was built for). (3) **`count_turns`
trajectory-schema validation** against FastContext's documented format before trusting
it beyond a labeled estimate. Standing carry-forwards unchanged (judge thinking-defense
hardening, permanent ceiling calibration, permanent `lm_model`/Deep choice, Deep
co-residency budget, Wave-2.1 substring/fuzzy matching).

## 2026-07-04 — **The 0020 `escalation_rate=0`-vs-3.3h anomaly is a recorded typed finding, not a bug: a projection-over-frozen-SUT diagnostic proves `accounting=CORRECT_NO_ESCALATION` and splits the wrong-citation fate on a second MECE axis — SUT frozen, no production change, and a metric-trust verdict gates the next spec** (spec 0021)

**Spec:** specs/0021-escalation-rate-0/
**Decision:** Resolve the 0020 G2 contradiction (a pass recording `escalation_rate = 0.0`
yet taking ~3.3h) as a **metric-integrity diagnostic** in the 0019/0020
measurement-not-construction lineage: the SUT (`harpyja/orchestrator/` tiers/gate/matrix/
judge) stays **FROZEN and read-only** — `harpyja/orchestrator` is reference here, any
proven accounting fix would have landed in the eval metric layer (`harpyja/eval/`), never
the tiers/gate — and the deliverable is a RECORDED TYPED FINDING (`findings.md`), not a
feature. Four durable points. (1) **The finding is MECE on TWO orthogonal axes, because a
flat enum was not mutually exclusive (review C2):** `accounting ∈ {ACCOUNTING_BUG,
CORRECT_NO_ESCALATION}` × `wrong_citation_fate ∈ {GATE_FALSE_ACCEPTANCE, NO_ESCALATION_PATH,
DEEP_DEGRADED_OR_UNAVAILABLE, NOT_APPLICABLE}` — whether the *count* was faithful is
independent of *why the wrong cases didn't escalate* (`GATE_FALSE_ACCEPTANCE` is an
explanation UNDER `CORRECT_NO_ESCALATION`, not a rival to it). (2) **Accounting =
`CORRECT_NO_ESCALATION`, PROVEN.** `escalation_rate` is derived (`metrics.py:126,129`
`mean(2 in o.tiers_run)`) with no independent counter that could disagree — the classic
"two sources drift" bug locus does not exist; 3 new `test_metrics.py` tests PIN the
`tiers_run ⇄ escalation_rate` coupling and pass against the frozen metric, so `0.0` is a
faithful no-escalation, not a lost count, and there is **no production change**. (3) **The
wrong-citation fate is settled by a projection over the byte-frozen SUT, reprising 0020's
`classify_g3_outcome`:** the additive pure `classify_escalation(...)`
(`harpyja/eval/escalation.py`, `WrongCitationFate`) maps `(tier1_empty, tier1_correct,
gate_rejected, deep_available, ladder)` to a fate, reading `plan_ladder` inputs but never
re-deriving them (`test_escalation_trigger.py` obtains every ladder by CALLING
`matrix.plan_ladder`, guarded that they are equal). Reading the frozen `_locate_auto`:
the **33 empty** point cases route to `_honest_empty` (gate-skipped, `tiers_run=[0,1]`,
"Never escalates") → **`NO_ESCALATION_PATH`, CONFIRMED** — the dominant reason
`escalation_rate=0`; the **5 wrong-content** cases terminate at `[0,1]` either by gate
false-acceptance or by a `deep-degraded` fallback → **`GATE_FALSE_ACCEPTANCE` |
`DEEP_DEGRADED_OR_UNAVAILABLE`, UNDETERMINED** (dump gone; resolvable only by a served-model
micro-run). This also corrected the plan's AC2 assumption (that honest-empty escalates)
mid-implement — a characterization/projection test is grounded in the frozen source, not
the plan, and a test asserting a false claim about the SUT is worse than none. (4) **What
cannot be recovered is a LABELED ESTIMATE, never a fabricated recorded number.** The 0020
per-case dump is ABSENT (`eval_work/reports/oq2_{fast,incumbent}/` empty; `eval_work/` is
gitignored/machine-local; the quoted secondaries survive only in the operator transcript),
so the 3.3h attribution is anchored on the one recorded aggregate (wall-clock total) and
split by estimate: the sink is Scout FastContext exploration × 38 cases (~5.2 min/case),
NOT Deep (`escalation_rate=0`). The additive `escalation_microrun.py` (`_wrap_timed` /
`build_micro_result` / `run_escalation_microrun`) attributes per-tier timing at the EVAL
BOUNDARY — wrapping a collaborator's public method, never inside frozen orchestrator
internals — and labels the split `"estimate"`.
**Why:** The 0020 close carried the `escalation_rate: 0.0`-vs-3.3h-runtime accounting
anomaly forward as a named follow-up "before trusting secondary metrics." The next spec
(Scout Tier-1 span-level localization) must not build on suspect numbers, and the load-
bearing DEFERRED verdict (`correct_tier1_count = 0`) is independent and safe regardless —
so the honest move is to attribute the wall-clock, prove whether `escalation_rate=0` is a
bug or correct, and state which 0020 secondaries the next spec may trust. A full re-run of
the 3.3h pass was explicitly forbidden (it defeats the diagnostic's purpose).
**Consequence — the anomaly is resolved as a recorded finding, no SUT change, and the
next spec's inputs are triaged.** Shipped TDD-complete: **820 → 835 unit pass** (+15), ruff
clean, 1 integration skip-not-fail (the live micro-run, gated on served models).
**Metric-trust verdict (AC5):** TRUST `escalation_rate=0` (derived + coupling-pinned +
now structurally explained), `correct_tier1_count=0` (direct count), and
`gate_false_escalation=null` (zero denominator); treat `wrong_tier1_count=5`,
`span_hit_rate_primary=0.2`, `gate_catch_rate` as CONTAMINATED / unverifiable — the "5" is
a non-empty-but-wrong lens inconsistent with the aggregate (which counts empties as wrong →
38), and the rest are in no committed file. The next spec must REGENERATE those from a fresh
instrumented run, not inherit the transcript figures. **The 0020 DEFERRED verdict is
unchanged.** **Named follow-ups carried forward:** the pre-existing **Scout Tier-1
span-level localization on SWE-bench** (the real blocker, `correct_tier1_count=0`);
**resolving the 5-wrong-case fate** with a served-model `run_escalation_microrun` +
`deep-degraded` capture (distinguishes `GATE_FALSE_ACCEPTANCE` from
`DEEP_DEGRADED_OR_UNAVAILABLE`); **if false-acceptance, a gate-false-acceptance
investigation** (the mirror of G2's false-escalation target); the **Deep co-residency
budget** (0020 D9-a, the `qwen3-coder:30b` OOM that makes degradation-suppressed escalation
live on this host); plus the standing 0020 carry-forwards (judge thinking-defense
hardening, permanent ceiling calibration, permanent `lm_model`/Deep choice, and Wave-2.1
substring/fuzzy matching).

## 2026-07-04 — Spec 0020 (OQ2 — the operator sweep) shipped the sequential G0→G3 operator protocol + the `0020/1` gate-ledger; the live run produced a typed **DEFERRED** null — Scout Tier-1 ≈ 0 correct on SWE-bench (verified, model-independent) is the real upstream blocker (OQ2 gate calibration is NOT reached; the SUT stays frozen)

**Spec:** specs/0020-oq2/
**Decision:** Run the 0019 instrument as the OQ2 **operator sweep** — a four-gate sequential
stop-and-report protocol (G0 preflight → G1 smoke → G2 gate-quality → G3 sweep), emitting exactly
one typed outcome + a durable gate-ledger — as a pure **measurement/eval** spec: the SUT (tiers /
gate / matrix / judge / classifier / citation format) stays **FROZEN**, every change lands
additively in `harpyja/eval/`. Four durable points. (1) **The four G3 labels come from a
PROJECTION LAYER above the byte-frozen dispatcher, never a widening of it (D1).** New pure
`classify_g3_outcome(recommendation, aggregate, eval_config)` (`oq2_classify.py`) maps the
byte-unchanged 0019 `recommend_oq2` result (which still emits only its two strings,
`recommended` / `gate-confounded`) + `degraded_dominated` + effective-N down to one of
`{RECOMMENDATION, GATE_CONFOUNDED, DEGRADED_DOMINATED, NOT_SEPARABLE}`, precedence
**DEGRADED_DOMINATED > GATE_CONFOUNDED > NOT_SEPARABLE > RECOMMENDATION**, ALL true blocking
conditions recorded (not only the winner). The no-survivor `S` signal is derived on the frozen
`Recommendation` — the UNIQUE state `incumbent_validated is False AND advantage_exceeds_variance
is False` (a variance-beating flip carries `advantage_exceeds_variance is True`; a validated
incumbent carries `incumbent_validated is True`) — and computed ONLY when `rank_sweep` ran
(`outcome != gate-confounded`), so a phantom `NOT_SEPARABLE` is never booked alongside
`GATE_CONFOUNDED`; `indicative_only` (effective-N < `n_floor` = 30) is a RECOMMENDATION-only
sub-flag. D2 boundary held: within-variance is a validated-incumbent RECOMMENDATION, not
NOT_SEPARABLE. `recommend_oq2` / `rank_sweep` stay byte-frozen (P1 field-reachability lock + P2
behavior-snapshot golden lock in `test_recommend.py` — a snapshot, never a source grep).
(2) **The gate-ledger is a NEW pinned artifact, `LEDGER_SCHEMA_VERSION = "0020/1"` (D8/AC2),
distinct from the sweep report `0014/1`.** `oq2_ledger.py` carries per-gate verdicts (each G1
sub-check's measured value + the close/hold cause; G2's instruct-vs-finder A/B; G3's label +
all D/G/S booleans) + run provenance (SUT git SHA, resolved `EvalConfig`, fixture-subset id,
model tags, the grid), loud `validate_gate_ledger` / `LedgerSchemaError`, and a
`write_gate_ledger` that reuses `report.atomic_write_json` so the outside-the-indexed-repo guard
stays single-sourced; `report.SCHEMA_VERSION` is NOT bumped. (3) **Close ≠ hold, split BY CAUSE
(D7).** `oq2_protocol.py::run_oq2_protocol` records each verdict before the next gate; a SUT-
observing outcome (`STOP:SMOKE` — a run that *completed* then degrade-dominated or gate-false-
rejected — or a G3 label) **closes**, while an environment failure (G0 preflight fail, fixtures
absent, or a G1 sub-check-(a) non-completion for an environment reason: OOM / resource
exhaustion under co-load — the G0-invisible residual, since G0 proves models *pulled*, not
co-resident-loadable) is a **BLOCKED hold** that names the fix. This makes 0019's F4 loophole
airtight: skip-not-fail is NOT a valid close for 0020, and a resource failure can never
masquerade as a SUT finding. (4) **A typed null (incl. an unmeasurable metric) is a complete,
valid deliverable that names the next spec (AC11) — never a forced `(threshold, top_n)` pick.**
`oq2_live.py` + the `oq2` CLI subcommand (`cmd_oq2`) are the live seam that produced the recorded
outcome end-to-end.
**Why:** Specs 0016/0017/0018 fixed the three 0015 blockers (B1/B3/B2) and 0019 shipped the
instrument + gate-confound mechanism but deliberately deferred the numbers; mechanism + instrument
≠ OQ2 calibrated. The dev host is now 32 GB with `mode=auto` OOM resolved and the served models
pulled, so there was no infrastructural reason left to defer — hence AC12 makes a recorded typed
outcome the close gate, not another skip-not-fail demo. The four-gate sequencing IS the spec: it
makes 0015's mistake (a long, expensive run over a broken gate) structurally impossible — find a
wedge in minutes, not hours.
**Consequence — the operator protocol + `0020/1` ledger shipped and unit-verified; the live run
produced a typed DEFERRED null; OQ2 gate calibration is NOT reached, blocked UPSTREAM on Scout
locate accuracy (itself the honest deliverable).** Shipped TDD-complete: **820 unit pass** (+43
over the 777 baseline), ruff clean. **Operator-run outcome (typed DEFERRED, a valid deliverable):**
G0 PASS (tags present, validated twice); G1 (astropy-12907, `mode=auto`) PASS but with an honest
caveat — `tier1_correct=False` (Scout missed the gold span, the gate correctly caught the wrong
citation at catch_rate 1.0 and escalated to Deep, which also missed; sub-check (c) vacuously
satisfied, case not solved end-to-end); **G2 DEFERRED** — the instruct pass over 38 point cases
completed (~3.3 h) with **`correct_tier1_count = 0`** → `gate_false_escalation = null` **by
definition** (you cannot measure whether a judge false-*rejects* correct citations when Scout emits
none), so the finder A/B + G3 sweep are MOOT (`verify_method` changes the judge, not Scout's
citations) and were not run. **Root cause verified real, not a harness artifact:** direct Tier-1
spot-checks confirmed `expected_spans` load, Scout runs/returns citations, oracle correct — Scout
Tier-1 is genuinely ≈ 0 correct on SWE-bench point cases (best case **right-file-wrong-span**:
astropy-12907 cited `separable.py:66-102` vs gold `242-248`; else empty/wrong-file). **Not a
model-swap fix (verified):** `qwen3:4b-instruct` as the Scout finder also 0/3, same pattern, and on
astropy-12907 **both models produced the identical wrong span** → span-level localization / task
difficulty, not model quality. **Environment findings recorded (D9-a/D9-b):** `qwen3-coder:30b` as
Deep+judge **OOM'd** the 32 GB host (swap 94 % full — the D9 co-residency risk realized, an AC4/D7
BLOCKED-hold cause), resolved by dropping to `qwen3:8b` (~9.5 GB co-resident); and
`make_instruct_judge` does **not** disable model "thinking" (the anchored `_parse_score` would fail
on a `<think>` block) — a latent 0018 SUT robustness gap, not biting here (`qwen3:8b` empirically
returns bare, well-calibrated numbers). **Deviations (recorded honestly):** the five protocol
RED/GREEN pairs (T7–T16) were batched into one comprehensive RED + one GREEN (test-first preserved);
T18 refactor was a no-op (the driver already single-sources `_verdict_dict` / `commit`); T19 built
the live harness + ran G0/G1 live, with the full G2/G3 sweep operator-gated and (given the DEFERRED
root cause) moot — AC12's "skip-not-fail ≠ close" honored, the spec closes on a recorded
SUT-observing DEFERRED outcome. **Scope honesty — never claim OQ2 was calibrated or that Scout was
fixed:** mechanism + instrument shipped, G0/G1 validated live, OQ2 gate calibration remains blocked
upstream. **Named follow-up: Scout Tier-1 span-level localization on SWE-bench** (the
right-file-wrong-span pattern from long issue-text queries; file/proximity vs exact-span scoring;
finder capability) — **NOT** a gate-accuracy, threshold-calibration, or finder-model-swap spec.
Secondary follow-ups carried forward: **judge thinking-defense hardening** (D9-b — set
`/no_think` / `enable_thinking=False` or tolerate a `<think>` prefix in `_parse_score`); a
**smaller-footprint Deep + a co-residency budget** (D9-a); reconciling the `escalation_rate: 0.0`
vs 3.3 h-runtime **accounting anomaly** before trusting secondary metrics; **permanent ceiling
calibration** (the provisional 0.20 is still unmeasured — G2 never yielded a rate); the **permanent
`lm_model` / Deep choice**; and, still open from Wave 2, **Wave-2.1 substring/fuzzy matching**.

## 2026-07-02 — Spec 0019 (oq2-rerun) shipped the OQ2 re-run INSTRUMENT + gate-confound MECHANISM — the SUT stays frozen; the actual OQ2 numbers remain an operator sweep (mechanism+instrument shipped ≠ OQ2 calibrated)

**Spec:** specs/0019-oq2-rerun/
**Decision:** With the three 0015 blockers now all fixed — **B1 (0016)** served scout/deep
defaults + CLI overrides, **B3 (0017)** finite gateway HTTP timeout, **B2 (0018)**
in-distribution instruct-model judge + strict non-fabricating parse — build the re-run
INSTRUMENT on top, as a pure **measurement/eval** spec: the SUT (tiers / gate / matrix /
judge) is **FROZEN**, every change lands in `harpyja/eval/` (the harness, additively
extensible even under the measurement-not-construction invariant). Five durable points.
(1) **A recommender refuses to calibrate over an instrument it has measured to be broken.**
`EvalConfig.gate_false_escalation_ceiling = 0.20` (eval-only, `Settings`-disjoint,
**provisional** — a named bar, not a tuned prior) is the gate-confound bar; `recommend.py`
gains `recommend_oq2(points, measured_false_escalation, eval_config)`, which on a measured
instruct false-escalation **strictly `> ceiling`** emits the `gate-confounded` typed null
(`OUTCOME_GATE_CONFOUNDED`, carrying the measured rate) instead of tuning `verify_threshold`
over a judge that rejects correct citations — else defers to the **unchanged** `rank_sweep`.
Boundary `== ceiling` is not confounded (strict `>`); `None` (unmeasured) defers. This is the
principled successor to 0015's `gate_quality_confounded` and 0018's "mechanism fixed ≠
accuracy proven": an honest confound flag beats a threshold calibrated over a still-broken
gate. `Recommendation.outcome` / `.gate_false_escalation_measured` are additive, appended
last-with-defaults so every existing construction stays valid. (2) **Preflight is a
setup-time doctor, single-seam and honesty-scoped (D4).** `preflight_models_present` asserts
`gateway.assert_local` FIRST (no second outbound path — the `/api/tags` read is the same
loopback-gated egress class it preflights), then a deduped required-tag membership check
naming the first absent tag — B1's 404 re-surfaced at SETUP, loudly, not mid-run. It claims
only that models are **"pulled"**, NOT co-resident-loadable, and explicitly names OOM under
`mode=auto` as a residual risk the cheap G1 smoke catches (no-false-capability applied to a
doctor probe). Shipped with `cmd_preflight` + a `preflight` CLI subparser. (3) **Report schema
0013/1 → 0014/1, additive last-with-defaults.** Run-metadata `gate_false_escalation_ceiling`;
aggregate `gate_confounded` / `gate_confounded_measured_rate` + instruct/scout A/B
false-escalation twins, all null-with-zero-count defaults, hoisted to one
`_GATE_CONFOUND_AGG_FIELDS` anti-drift source with a drift-guard test; legacy blocks still
validate. (4) **One oracle, characterization-locked.** A new `test_metrics.py` lock proves
both gate denominators (false-escalation vs catch-rate) flip with the single
`_any_primary_overlap` oracle — no second correctness definition, null-with-zero-count
preserved (no production edit; the behavior already existed). (5) **Honesty — mechanism +
instrument shipped ≠ OQ2 calibrated.** This ships the gate-confound mechanism and the
calibration instrument; the actual OQ2 recommendation / typed null over the real N=12 subset
requires the **operator** sweep (`HARPYJA_N12_FIXTURES` + served models). G1/G2/G3-at-scale
are `@pytest.mark.integration` skip-not-fail DEMONSTRATIONS, not CI-run. **OQ2 is not
calibrated; B2 is not closed; astropy-12907 end-to-end is not demonstrated here.**
**Why:** Spec 0015's OQ2 wedged on B3 and surfaced B1/B2/B3, each since fixed in its own
spec. But 0018 fixed the judging *mechanism* and explicitly deferred proving *accuracy*, and
`verify_threshold=0.6` was calibrated over the OLD finder-model distribution — meaningless
against the new instruct judge. This spec builds the instrument to prove, IN ORDER, the three
things 0015 couldn't reach (G1 completes → G2 gate-quality demonstrable → G3 calibrates), each
willing to stop-and-report a finding, without touching any tier or gate behavior. It makes no
model better; it builds the honest instrument that can either calibrate OQ2 or report a typed
confound.
**Consequence — the OQ2 re-run instrument + the gate-confound mechanism are shipped; the
operator sweep and OQ2 calibration remain open.** Shipped TDD-complete: **777 unit pass**
(+20 over the 757 baseline), ruff clean. Load-bearing proofs: the strict-`>` boundary tests
(`0.20 == ceiling` NOT confounded; `None` defers), the `gate-confounded` sweep-runner test
(a correct citation the gate rejects → false-escalation 1.0 > ceiling → typed null carrying
the rate), the schema legacy-tolerance + round-trip + anti-drift tests, and the preflight
`assert_local`-first / missing-model-names-it / pulled-not-coresident units. Live preflight
PASSED on this host (the three required tags are pulled); the sweep-scale ACs are
operator-gated. **Deviation (recorded honestly):** `plan.md` scoped T11 as
scaffolding-ONLY, but leaving `run_swebench_sweep` calling `rank_sweep` would have left the
`gate-confounded` outcome **wired-but-dormant** and AC9 aspirational — so `recommend_oq2` +
the ceiling were wired INTO the sweep runner (the best-achievable instruct false-escalation =
min over measured grid points, only when base `verify_method=="instruct_model"`), TDD'd with 3
new unit tests. The plan under-scoped; the implement pass caught it; the fix stayed within the
measurement-not-construction invariant (harness additively extensible; SUT frozen). **Out of
scope / follow-ups carried forward:** the **actual operator OQ2 sweep** (served models +
`HARPYJA_N12_FIXTURES` — produce the real recommendation OR typed null over N=12); **permanent
ceiling calibration** (replace the provisional 0.20 with a data-driven bar once the
instruct-judge score distribution is measured); **astropy-12907 end-to-end proof** (the B2
accuracy deferral, still not discharged); **per-span non-conformance abstain** (0018 D7 chose
whole-gate degrade); the **permanent `lm_model` choice** (Qwen3-8B provisional; the judge
inherits it); **Q8 model footprint / co-residency** (OOM under `mode=auto` — the preflight
"pulled ≠ loadable" residual risk); and, still open from Wave 2, **Wave-2.1 substring/fuzzy
matching**.

## 2026-07-01 — Spec 0018 (judge) shipped — the B2 fix from 0015: the Verification Gate's relevance judge moves off the OOD `scout_model` finder onto the in-distribution `lm_model` instruct model, with a strict non-fabricating score parse

**Spec:** specs/0018-judge/
**Decision:** Close **B2** from spec 0015 (`live-run-findings.md` D2) — the Verification Gate
reused `make_scout_model_judge` (over `scout_model`, a FastContext citation-*finder* fine-tune)
as a 0–1 relevance *scorer* via a plain chat prompt, and `_parse_score` grabbed the first number
anywhere and clamped to `[0,1]`, so the gate scored **correct** citations as noise and
false-rejected them (astropy-12907 cited `separable.py`, the real bug site, and got
`gate-low-confidence`) — as a **gate-quality / judging-mechanism** fix: no tier logic, no gate
calibration, no escalation policy, no classifier, no citation format touched. Six durable points.
(1) **The judge must be in-distribution for the task it is asked to do — score relevance, not find
citations.** The gate now judges with `make_instruct_judge` over `settings.lm_model` (served
Qwen3-8B instruct, in-distribution for "rate 0.0–1.0"), which the 0016 B1 fix made available by
flipping `lm_model` from the `"local"` placeholder to a served instruct model; the OOD finder
judge is **retained non-default** (D5) as the exact finder-vs-instruct A/B baseline the OQ2 re-run
will want, so nothing has to be resurrected. (2) **A best-effort scorer degrades on a
non-conforming reply — it never fabricates a score from noise.** `_parse_score` becomes strict
(`float | None`, anchored single-match `^\s*(?:score\s*:\s*)?(\d+(?:\.\d*)?|\.\d+)\s*\.?\s*$`,
range-checked to `[0,1]`): a bare line number (`219`, the exact B2 regression — must NOT clamp to
`1.0`), an out-of-range value (`1.2`, `-0.1`), or prose-after-number (`0, because…`, D6) all
return `None`. A `None` raises a typed `ScoreParseError`, the gate's *existing* `except →
GateOutcome(failed=True)` fires (the same "make the un-raisable raisable" move as 0017/B3), and the
gate degrades — **never** a fabricated `1.0` pass or `0.0` reject. The elegant unifier folded at
review: an out-of-range number and a line number are the same rule (both non-conforming → `None`),
so the range check *is* the B2 fix. On ambiguity the gate prefers **degrade-and-escalate over
reject** (the 0015 harm was false *rejection*). `_parse_score` is shared plumbing via
`_score_or_raise`, so the retained finder judge degrades **identically** (AC13) and cannot silently
keep the old fabricating behavior. (3) **A typed-degrade cause that subclasses another caught type
must be isinstance-checked FIRST.** `ScoreParseError ⊂ ValueError`, so `verify`'s `except` tests it
**before** the 0017 timeout branch and the generic branch — otherwise the generic branch would
catch it and it would degrade under the wrong name (and double-emit). It emits **exactly one**
distinct WARNING naming the non-conformance, with the generic "scoring failed" message asserted
**absent** (AC7, the 0017 double-emit lesson, asserted on the record message not `caplog.text`) and
distinct from the timeout WARNING — extending the 0014/0017 log-signal visibility convention, no
`GateOutcome` schema change. (4) **`verify_method` finally becomes a real selector.**
`_VERIFY_METHODS = {"scout_model", "instruct_model"}`, default flips to `instruct_model`;
`select_judge`/`_JUDGE_FACTORIES` (co-located in `gate.py` so the production builder and the
`verify()` fallback share one source of truth) dispatch, and `build_verification_gate`
(`wiring.py`) routes on it — honoring the 0008 pluggable-seam intent it had only nominally used.
D7: a single non-conforming reply degrades the **whole** gate for that `verify` call (a model not
following the bare-number instruction is suspect for the batch); per-span abstain is a deferred
refinement. (5) **Stated coupling — `lm_model` is now dual-consumer.** It already backed Deep
(Tier 2); it now **also** backs the gate judge, so a future `lm_model` tune for Deep silently
retunes the gate — the same one-value-two-subsystems situation the repo codified for `scout_model`
in 0016, named in the `settings.py` comment, `ARCHITECTURE.md` §2.7, and the README. `lm_model` is
itself provisional (0016 "for now" Qwen3-8B), so the judge inherits a provisional default.
(6) **Honesty (no-false-capability): mechanism fixed ≠ accuracy proven.** This fixes the judging
*mechanism*; it does **not** by itself demonstrate astropy-12907 now passes end-to-end — that needs
a calibrated `verify_threshold` over the new instruct-model score *distribution*, which is the OQ2
re-run's job. The `0.6` default is now an untested operating point; AC10 (correct-citation-passes)
and AC11 (live smoke) are honestly disclaimed as **plumbing/wiring, not accuracy** claims. The
changelog says "B2 *mechanism* fixed; accuracy deferred to the OQ2 re-run," **never** "B2 closed"
or "false-rejection eliminated."
**Why:** Spec 0015's OQ2 measurement could not be trusted because the gate's relevance signal was
noise — calibrating `verify_threshold`/`verify_top_n` over a dysfunctional judge would measure gate
dysfunction, not gate tuning (0015 AC5 `gate_quality_confounded`). B2 is the last of the three 0015
blockers; with the judge scoring in-distribution and never fabricating, the gate's operating point
becomes a meaningful thing to calibrate. It makes no model better; it stops the gate from *asking
the wrong model the wrong way* and then trusting a fabricated number.
**Consequence — B2 mechanism fixed; the 0015 blocker sequence is now B1(0016)+B2(0018)+B3(0017)
all fixed, so the OQ2 re-run is unblocked (a fresh spec).** Shipped TDD-complete: **757 unit pass**
(+32 over the 725 baseline), ruff clean; T17 live instruct-judge smoke **PASSED live**
(skip-not-fail, explicitly a wiring/parse smoke, not an accuracy claim). Load-bearing proofs: AC5's
executable boundary table (`219`/`Score: 219`/`1.2`/`-0.1`/`0, because…`/`""`/`n/a` → `None`, the
regression that must not clamp), AC6 (a `219` reply degrades `failed=True` with `score != 1.0`),
AC7 (exactly one non-conformance WARNING, generic absent), AC13 (both judges degrade identically),
and AC10 (the inverted-harm regression — a correctly-scored correct citation now passes, plumbing
not accuracy). Docs made consistent in the same change (blast-radius convention): `settings.py`
comment, `gate.py` docstrings, `ARCHITECTURE.md` §2.7, README config note — each stating this is a
judging-*mechanism* fix, not a calibration change. **Deviation:** none material; T12's
`_score_or_raise` extraction was folded into T6 (both judges share it from first landing).
**Out of scope / follow-ups carried forward:** the **OQ2 re-run** (now unblocked — calibrate
`verify_threshold` over the new instruct-model score distribution, and demonstrate astropy-12907
passes end-to-end; the accuracy proof B2 defers); **per-span non-conformance abstain** (D7 chose
whole-gate degrade; scoring the conforming spans and dropping only the non-conforming one is a
deferred refinement if OQ2 shows whole-gate degrade costs recall); a **deterministic lexical judge**
(`verify_method="lexical"`, considered, not chosen — a plausible future method behind the same
selector); **constrained-decoding score extraction** (logit-bias / single-token numeric forcing, a
parse-hardening beyond a strict regex); the **permanent `lm_model` choice** (Qwen3-8B is
provisional); **model footprint / co-residency** (the gate now calls `lm_model` alongside Scout's
`scout_model` — Ollama model-swap thrash on a constrained host, tracked with the Q8 / 8 GB work);
and, still open from Wave 2, **Wave-2.1 substring/fuzzy matching**.

## 2026-07-01 — Spec 0017 (gateway_http_timeout) shipped — the B3 fix from 0015: a finite `urlopen(timeout=)` makes the un-raisable raisable so the existing gate degrade can fire

**Spec:** specs/0017-gateway-http-timeout/
**Decision:** Close **B3** from spec 0015 (`live-run-findings.md`) — the Model Gateway's
outbound HTTP call had **no timeout** (`_default_transport` did `urlopen(req)`, default
`None` → block forever), so a stalled/torn-down local Ollama connection wedged the whole
`mode=auto` run indefinitely (observed 2.5 h at 0% CPU with `caffeinate` on) — as a pure
**reliability/plumbing** fix: no tier logic, no gate algorithm, no classifier, no citation
format touched. Six durable points. (1) **A call that can hang forever can never degrade —
so the fix is to make the un-raisable raisable, NOT to add a new degrade path.** The
Verification Gate *already* wraps the judge call in `except Exception → GateOutcome(failed=True)`,
but that safety net never fired because an un-timed-out `urlopen` raises **nothing**; it just
hangs. A finite `urlopen(req, timeout=timeout_s)` converts the silent infinite wedge into a
raised `TimeoutError`/`URLError` that the *existing* catch turns into a graceful degrade —
the "always degrade gracefully" guardrail applied to the one place it structurally could not.
(2) **The finite floor lives on the constructed object's own field default, not only on
Settings.** `ModelGateway.timeout_s: float = 120.0` is finite at the **dataclass default
itself** (AC2), so *any* `ModelGateway(...)` — the two wired sites AND a bare/test/unwired
construction — is hang-bounded out of the box; a default living only on `Settings.lm_http_timeout_s`
(AC1) would leave direct constructions falling back to unbounded `None`. (3) **Seam-preserving
threading (D3).** The timeout rides the gateway and is bound onto the default transport via
`functools.partial(_default_transport, timeout_s=self.timeout_s)` **only when `transport is None`**;
the injectable `Transport` signature `(url, payload) -> dict` is untouched, so every existing
injected fake keeps working. (4) **Timeout-degrade visibility (D4) extends the 0014 convention
to the gate as a LOG signal, not a schema field.** The timeout still degrades through the gate's
existing generic catch, but the path is branched to emit a **distinct timeout-naming WARNING**
(`isinstance(err, (TimeoutError, socket.timeout, URLError))`) so "judge timed out" is separable
from a parse/other failure in operator diagnostics — no `GateOutcome` schema change (a structured
gate-degrade-cause taxonomy stays deferred as a gate-quality concern). (5) **Per-socket-op, not
total-deadline honesty (no-false-capability).** `urlopen(timeout=)` bounds connect and each
blocking read — exactly the observed pathology (accept-then-go-silent trips the read timeout) —
and the spec claims only that; a dribble-slow endpoint could still outlast it, an acknowledged
stdlib-transport limit, out of scope. The default `120.0 s` is deliberately **decoupled** from
`deep_wall_clock_ms` (60 s) — they bound different things (D1), no per-request layer (D2). The
air-gap floor is preserved: `assert_local` still runs **before** egress on the default-transport
path (AC9). Both production sites construct with `timeout_s=settings.lm_http_timeout_s` —
`orchestrator/wiring.py` (the observed B3 hang path) and `scout/wiring.py` (defense-in-depth on
Scout's largely-vestigial Path-A gateway).
**Why:** Spec 0015's OQ2 measurement never completed a single full sweep because this call could
hang forever; the sibling B1 serving fix (0016) is not enough on its own. This is the narrow
robustness prerequisite for re-attempting OQ2 — make a stalled endpoint fail fast and degrade
visibly instead of wedging the run — without touching any tier or gate behavior. It makes no
model faster or better; it makes a hung model *fail fast and visibly*.
**Consequence — B3 closed; the 0015 blocker sequence is now B1(0016)+B3(0017) fixed, B2 and the
OQ2 re-run still open.** Shipped TDD-complete: **+14 unit (725 total, was 711)**, ruff clean; +1
integration. Load-bearing proof is **AC7** — a deterministic loopback server that accepts the
connection then withholds all bytes, driven through `complete()` with a tiny `timeout_s`, raises
in **<1 s** rather than hanging (the real socket-stall pathology bounded, not merely a fake that
can raise) — plus AC5 (a raised timeout yields `GateOutcome(passed=False, failed=True)`, degrade
not crash) and AC3 (the timeout is really threaded to the blocking op, proven by monkeypatching
`urlopen`). AC11 optional live-Ollama happy-path smoke passed (6.15 s, skip-not-fail, explicitly
**not** the stall proof). Docs made consistent in the same change (blast-radius convention):
`settings.py` field comment + module-docstring toml example, the `_default_transport` docstring
(now states the bound), ARCHITECTURE §2.8, and the README config-knob list. **Out of scope /
follow-ups carried forward:** **B2** — the gate-as-judge false-escalation (the FastContext finder
reused as a relevance judge rejecting correct citations — a separate gate-quality spec, orthogonal:
B3 is *when the call hangs*, B2 is *how the reply is judged*); **re-attempting the OQ2 measurement**
(a fresh spec now that B1+B3 land); a **total-request deadline / dribble-slow defense** (per-op
`urlopen(timeout=)` is by design); **Deep's `dspy.RLM`/litellm timeout** (a separate outbound
socket, dspy-managed); **retry/backoff on timeout** (this spec fails fast and degrades); and, still
open from Wave 2, **Wave-2.1 substring/fuzzy matching**.

## 2026-07-01 — Spec 0016 (scout_model) shipped — the B1 serving/plumbing fix from 0015: two Settings defaults flipped to SERVED tags + a CLI override escape hatch

**Spec:** specs/0016-scout-model/
**Decision:** Close **B1** from spec 0015 (`live-run-findings.md` D1) — the out-of-box eval
could not reach a served model — as a pure **serving/plumbing** fix: two `Settings` default
VALUES flip to served Ollama tags and two CLI override flags are added, with **no** change to
tier logic, the classifier, the citation format, or the gate's algorithm. Four durable points.
(1) **A `Settings` default must name a SERVED model.** `scout_model` flips from the UNSERVED
`hf.co/mitkox/FastContext-1.0-4B-RL-Q4_K_M-GGUF:latest` (HTTP 404 on every Scout call → a
fully-degraded run for a non-model reason) to the served `hf.co/dstolf/FastContext-1.0-4B-RL-Q8_0-GGUF:latest`;
`lm_model` flips from the llama.cpp placeholder `"local"` to the served
`hf.co/Qwen/Qwen3-8B-GGUF:latest`. An unserved default is an infrastructure defect, not a
config preference — the same no-false-capability discipline applied to model *tags*. (2) **The
scout flip is stated cross-subsystem coupling, not a hidden gate change (D-body caveat).**
Because `verify_method="scout_model"` is the only shipped gate backend, `scout_model` does
double duty — Scout-tier retrieval AND the model the Verification Gate scores citations with —
so the flip changes *which served model the gate calls* (broken→served plumbing), which is
deliberately DISTINCT from the still-open **B2** gate-*judging-logic* problem; the next OQ2 run
must not conflate the two. (3) **The `lm_model` flip is intentionally GLOBAL, blast radius named
and accepted (D2).** It is a bare `Settings` default, so it hits **every** `Settings()` caller —
the eval `run`/`sweep` drivers AND the MCP server's `mode=auto` Deep tier — not only the eval
CLI. Against Ollama (the primary supported backend for this arc) the old `"local"` was already
unserved; against a llama.cpp `llama-server` endpoint `"local"` was a benign don't-care and the
Ollama-style Qwen tag will not resolve, so a llama.cpp operator relying on the default regresses
— mitigated by the unchanged override precedence (toml/env/`--deep-model`). The Qwen default is
provisional ("for now"), not a long-term Deep choice. (4) **A canonical flag with a deprecated
alias reconciles order-independently at the app layer, not via argparse positional last-wins
(D1).** `run`/`sweep` gain `--scout-model` (the missing escape hatch — an operator can now name
any served model without a source edit or the Python workaround the 0015 run needed) and the
canonical `--deep-model`; `--lm-model` is kept as a **deprecated** back-compat alias on a
**distinct argparse dest**, and `_settings_from_args` reconciles `deep = args.deep_model or
args.lm_model` so the canonical flag wins regardless of CLI order. Every override is built via
`dataclasses.replace` on a fresh `Settings()` — the frozen base-not-mutated contract preserved.
**Why:** Spec 0015's OQ2 measurement degraded on every case for an infra reason — the default
Scout model 404'd — and the CLI had no way to override it, so the out-of-box eval could not even
reach a served model. This spec is the narrow prerequisite for re-attempting OQ2: make the
default *served* and give the operator a source-edit-free escape hatch, without touching any tier
or gate behavior. It does NOT claim any model is *good*, only that the default is *served*
("served" is instance-relative — the claim is narrow: the new tags are in the documented required
local Ollama set, replacing a tag served nowhere in it). (Repo memory: the dev host is now 32 GB
and the dstolf Q8 SFT/RL tags are pulled locally, so the served-set claim is live-validated.)
**Consequence — B1 closed; B2/B3 and the OQ2 re-run remain separate specs.** Shipped
TDD-complete: **711 unit pass**, ruff clean; +11 new unit (2 config incl. an AC6 field-default
**introspection** drift guard asserting `dataclasses.fields(Settings)` no longer carries the old
unserved scout tag nor `"local"` — never a source grep; 9 CLI incl. the both-orders D1 test and
`--help` introspection) plus the flipped `_FC_GGUF` constant driving the existing default test,
and +1 integration `test_scout_model_default_present_in_ollama_served_set` — a **positive**
`/api/tags` membership check with a three-way branch (Ollama unreachable → skip; tag absent →
skip-with-diagnostic; the old unserved tag as default → FAIL), so it cannot pass trivially with
the endpoint down; validated live (the Q8 default IS served). Docs made consistent in the same
change (blast-radius convention): the `settings.py` `scout_model`/`lm_model` comments + the
module-docstring toml example, the `_settings_from_args` docstring (no longer claims the Deep
default is `"local"`), and the README model-guidance callout. **Out of scope / open follow-ups
carried forward:** **B2** — the gate-as-judge false-escalation (the FastContext finder reused as a
relevance judge rejecting correct citations, requests-1766/astropy-12907 — a separate gate-quality
spec); **B3** — the model-gateway `urlopen` with no HTTP timeout (wedges a run indefinitely — a
separate reliability spec); **re-attempting the OQ2 measurement** (a fresh spec after B1/B2/B3);
choosing the **permanent** Deep model (the Qwen3-8B default is provisional); validating the Q8
memory footprint / 8 GB-Q4 hardware floor; and, still open from Wave 2, **Wave-2.1 substring/fuzzy
matching**.

## 2026-07-01 — Spec 0015 (OQ2) CLOSED as a FAILED RUN — implementation reverted, B0 salvaged, B1/B2/B3 seed new specs

**Spec:** specs/0015-oq2/ (status: closed, outcome: failed-run)
**Decision:** The live `mode=auto` OQ2 measurement over the 12-repo SWE-bench subset could
NOT be completed, so the spec is closed for its **findings**, not its deliverable. AC1 was
partially proven (a 3-case smoke ran `mode=auto` to completion with no crash — the 0014 Deep
`AdapterParseError` fix holds at scale), but the full N=50 run never finished and AC2–AC7
were not delivered. Rather than carry un-exercised measurement code, the **entire OQ2
implementation was reverted to HEAD (7aedad8)** — typed-outcome enum + precedence, per-point
degrade gate, gate-confound threshold, report schema bump `0013/1→0014/1` +
`combined_degrade_rate`, sweep provenance, sibling-driver wiring, `run_oq2_sweep`, `make
oq2-full`, and their tests. **One incidental fix was salvaged (B0):** provisioning ran `git
worktree add` with `cwd=<clone>` against a *relative* `--work-dir`, so git created worktrees
under the clone while the resolved fixture recorded `wt.resolve()` (process-cwd-relative) —
every path 404'd; fix is `cmd_provision`: `Path(args.work_dir).resolve()`, locked by
`test_provision_relative_work_dir_resolves_to_real_worktrees` (network-free, local git repo).
**Three blockers explain the failure and seed follow-up specs:** **B1** — `Settings().scout_model`
defaults to `hf.co/mitkox/FastContext-1.0-4B-RL-Q4_K_M-GGUF:latest`, which is not served (HTTP
404), and the CLI has no `--scout-model` flag, so the out-of-box eval degrades on every case
for an infra reason. **B2** — the verification gate reuses `scout_model` (a citation-FINDER
fine-tune) as a relevance JUDGE via a plain "reply 0–1" prompt; it scored astropy-12907's
CORRECT citation (`separable.py`, the real bug site) as `gate-low-confidence`, and
`_parse_score` grabs the first number in the reply (a line number → clamps to 1.0). This IS
the AC4 / requests-1766 gate-false-escalation phenomenon; its fix was always scoped as a
separate gate-quality spec. **B3** — `gateway.py::_default_transport` calls `urlopen(req)`
with no `timeout=`, so a stalled/torn-down Ollama connection (FastContext Q8 on a ~1,880-file
repo, or a socket dropped across sleep/500) wedges the run forever (observed 2.5 h at 0% CPU
with `caffeinate` on); related, `run_swebench`'s `ThreadPoolExecutor(max_workers=1)` per-case
timeout cannot kill the blocked worker so cases deadlock behind it. This is why no full run
completed. **Verified NOT bugs (don't re-chase):** `parse_final_answer` parses real Q8-RL
output correctly; suffix recovery is wired (`scout/wiring.py:46`). Lesson: this measurement
needed the serving/robustness layer (B1/B3) hardened and the gate quality (B2) understood
BEFORE a multi-hour live sweep was attempted — the sweep machinery was premature. Detail in
`specs/0015-oq2/live-run-findings.md` + `changelog.md`. **700 unit pass** after revert, ruff
clean.

## 2026-06-30 — Deep AdapterParseError → typed parse-error degrade shipped — the second typed-degrade floor, with first-class visibility (the rule promoted to a standing convention)

**Spec:** specs/0014-adapterparseerror/
**Decision:** Close the known Deep crash path the spec-0012 AC5 run surfaced (a malformed
dspy/model response raised `AdapterParseError` out of the RLM driver and aborted the whole
run, forcing AC5 to `mode=fast`) — the **same defect class** as the original Scout
backend-error bug (0005/0007): a third-party parse failure that should map to a typed
tier-floor but instead crashes. Harden it **before** the full 12-repo OQ2 sweep, where an
unhandled exception at hour three loses the entire long run. Five durable choices pinned.
(1) **A named, narrow-caught seam earns its OWN cause — a sibling, not a replacement.**
`harpyja/deep/errors.py` adds `PARSE_ERROR = "parse-error"` next to `BACKEND_ERROR`:
`AdapterParseError` is a *recognized, pinned, typed* seam, the opposite of the
`backend-error` catch-all-for-the-unforeseen, so an operator can tell "the dspy adapter
could not parse the model output" apart from "something unforeseen blew up." Truly-unexpected
Deep exceptions still fold to `backend-error` (unchanged); the narrow catch is exactly what
keeps the two distinct (AC4). (2) **Pinned-against-source, dspy-absent-safe narrow catch at
the one seam.** `rlm.py::_adapter_parse_error_types()` lazily resolves
`dspy.utils.exceptions.AdapterParseError` — the single class all four adapters raise (and
into which `JSONAdapter` wraps a raw `json.JSONDecodeError`), per the dspy 3.2.1 source read,
so catching it alone is neither over-narrow nor over-broad — and returns the empty tuple when
dspy is absent (`except ()` catches nothing, preserving the module's no-top-level-`import
dspy` rule). It wraps **only** the `rlm(query=...)` forward call →
`raise DeepUnavailable(PARSE_ERROR) from err`; `_assert_local` (AirGapError floor) and
`_rlm_factory` (config faults) stay outside the try, and `parse_citations` never raises.
(3) **Typed-failure-only boundary preserved (the 0006 invariant both reviewers called this
tier's most important property).** A malformed response degrades; a *well-formed but
weak/empty-citation* response stays an honest Tier-2 result — collapsing the two into one
degrade would silently convert real escalations into floors, which is precisely why Deep
earns a typed floor rather than a blanket `try/except`. Regression-guarded on both sides
(AC1 malformed degrades; AC3 weak-but-real does not). (4) **No orchestrator change — proven,
not assumed.** `_locate_deep`/`_run_deep` already build `deep-degraded:{cause}` notes
generically, so a routing regression lock (`test_locate_deep_parse_error_degrades_to_scout`)
proves no production routing change is needed and pins AC5: `tiers_run` reflects the floor
REACHED (`[0,1]`), NOT a Tier-2 result; the attempt-and-degrade stays visible via the stable
`deep-degraded:parse-error` note + the first-class `deep_degrade_rate`, never via `tiers_run`,
so a floored run cannot read as "Deep never ran." (5) **Degrade made visible, not just safe —
the third time a graceful floor could hide a defect.** Report `SCHEMA_VERSION 0012/1 → 0013/1`
adds additive last-with-default twins `deep_degrade_count` / `deep_degrade_rate`
(null-with-zero-count on a zero denominator, never a false `0.0`) in the one
`_AGGREGATE_DEFAULTS` source, so both old- and new-shape blocks pass the single loud
validator. `runner.py` adds `_is_deep_degraded` (sharing one `_has_degrade_note` predicate
with `_is_scout_degraded`), and `degraded_dominated` now keys off the **UNION** of scout+deep
per-case degrades — a case counted **once** even when both tiers floor (a sum would
double-count) — while the per-tier rates stay separate for attribution (AC11). The single
producer `aggregate_outcomes` means the swebench sibling driver populates the fields with NO
`swebench_eval.py` change, proven by a sibling lock test (the recurring missed-consumer lesson).
**Why:** This is the **second** typed-degrade floor, so the visibility rule is promoted from a
per-spec fix to a **standing project convention** — every typed-degrade floor surfaces its
rate in aggregate or it goes dark exactly the way Scout's `format_citations` crash did.
Baking it only into this report schema would leave the *next* floor free to go dark, so the
convention is itself a close deliverable (AC12, P13).
**Consequence — the sweep is crash-unblocked; the rule is now a convention, not a one-off.**
Shipped TDD-complete: **699 unit pass**, ruff clean; the AC8 integration
`test_deep_auto_parse_error_degrades_not_crash` (deterministic injected fault, skip-not-fail)
drives the real `RlmBackend` → `DeepEngine` → `locate(mode=auto)` to completion with the
degrade recorded, so the spec-0012 AC5 `mode=fast` workaround can revert to `mode=auto`. One
new stable cause id joins the taxonomy (`deep-degraded:parse-error`); report schema is now
`0013/1`. **Deviation:** a pre-existing `test_report_schema_version_is_0012` exact pin was
converted to a `bumped_past_0012` ratchet (the codebase's established pattern), with the new
exact pin `test_report_schema_version_is_0013`. **Blast radius by category:** cause taxonomy
(`deep/errors.py`) → RLM seam (`deep/rlm.py`) → orchestrator routing (unchanged, lock only) →
report schema (`eval/report.py`) → runner aggregation (`eval/runner.py`) → swebench sibling
(unchanged, lock only). Open follow-ups carried forward: **`ContextWindowExceededError`** —
the only sibling dspy exception, a *distinct* failure (prompt exceeds the context window) that
still escapes the RLM and would crash a run, a candidate for its own future
`deep-degraded:context-window` cause (folding it into `parse-error` would break the
narrow-catch invariant); the **full 12-repo OQ2 sweep** this now unblocks (crash-free) but
does not run; the **gate false-escalation of a correct Scout answer** (requests-1766); the
**Q8 `scout_model` default flip** (deferred, variance-gated); and, still open from Wave 2,
**Wave-2.1 substring/fuzzy matching**.

## 2026-06-30 — FastContext dependency source swapped to the DCSTOLF fork (identical rev, no behavior change)

**Spec:** specs/0013-fastcontext/
**Decision:** Repoint the Tier-1 Scout FastContext git source from
`microsoft/fastcontext` to `DCSTOLF/fastcontext` at the **same pinned rev**
`1522d6d6b5e040e817b468e12826662aa069a8b0` — a pure source-of-supply swap with
**no version bump and no behavior change** (the resolved code is byte-identical).
`pyproject.toml` `[tool.uv.sources]` URL, the regenerated `uv.lock` source entry +
dependency-edge marker, and the `README.md` / `FASTCONTEXT_INSTALL.md` clone URLs all
move to the fork; a new `harpyja/test_fastcontext_source.py` drift-guards the source,
the unchanged rev (AC3 byte-identity), and the absence of any surviving
`microsoft/fastcontext` URL. **"Microsoft FastContext" prose attribution is left
intact** (the fork is a fork of MS's project, so the credit stays accurate); only the
URLs changed. No `harpyja/scout/` code touched.
**Why:** Move to a controlled fork source so future local FastContext fixes (the open
`format_citations` crash, recommended-Q4 quality leads) can be carried **without
bumping the pin**. This spec is only the source swap; carrying actual patches is a
deliberate later effort.
**Consequence:** Scout now resolves FastContext from the owned fork at the identical
rev. **683 unit pass** (+5 new source/rev/no-stale-URL guards), ruff clean; **38 Scout
integration tests pass** against the fork (live), confirming no behavior change;
`uv lock --check` resolves 144 packages consistently. The plan's "fork-not-pushed /
network" risk was moot — the fork resolved and built cleanly on first `uv run`. Open
follow-ups carried forward: **carrying the actual FastContext patches** onto the fork
(the `format_citations` robustness fix, Q4 quality leads — now unblocked by owning the
source); the **Q8 `scout_model` default flip** (deferred, variance-gated); the **gate
false-escalation of a correct Scout answer**; the **Deep `AdapterParseError` robustness
gap**; and, still open from Wave 2, **Wave-2.1 substring/fuzzy matching**.

## 2026-06-29 — Scout path-suffix recovery shipped — rescue an out-of-repo hallucinated citation by its unique, manifest-keyed in-repo suffix, composing with (never bypassing) the 0011 drop + honesty floor

**Spec:** specs/0012-path-prefix/
**Decision:** Close the remaining `scout-empty` tail the spec-0010/0011 Q8
re-measurement exposed — **7/12** cases died not because the model found nothing but
because it emitted **out-of-repo absolute paths** fabricated from the repo slug (e.g.
`/pallets/flask/src/flask/blueprints.py`), which spec 0011 correctly **drops** as
out-of-repo (10 dropped in the N=12 auto run) — with a **deterministic,
model-independent** recovery: map such a citation to a real in-repo file by its longest
**unique, specific** path suffix against the repo's own indexed manifest set, only ever
keeping a path that actually exists. The **`scout_model` default was NOT flipped** (a
separate, deferred follow-up). Four durable choices were pinned. (1) **Recover only to an
existing, unique, manifest-keyed path — never a guess.** `normalize.py::_recover_suffix`
tries `k` from the cited path's full length down to `MIN_TAIL_SEGMENTS=2`, matching the
last `k` segments segment-aligned against the manifest `file_set` (`p == tail` or `p`
ends with `"/" + tail`); it keeps a recovery **only** on **exactly one** match at the
longest such `k`. Three guards against wrong-but-existing: ambiguous (>1 match) → **drop**
(never a silent pick, never a fall-back to a shorter, less specific tail); the
`MIN_TAIL_SEGMENTS=2` specificity floor (a bare basename like `__init__.py` is never
recovered); and a **manifest-keyed leading-segment guard** — the matched *tail's head*
must be a known top-level manifest entry, so a fabricated mid-tree suffix is rejected
(`src/flask/blueprints.py` kept, `flask/blueprints.py` whose head `flask` is not
top-level dropped). The worked counter-case proves the floor pays its way: a cite of
`/pallets/flask/src/__init__.py` has suffix `src/__init__.py`, which does **not** exist
in flask (the real file is `src/flask/__init__.py`), so recovery correctly **fails**.
(2) **Recovery composes with, never bypasses, 0011's validation.** A recovered path
re-enters the same repo-confine + `is_file` (+ line-range clamp for spanned) gates
before it is kept; the match-set is **manifest-relative** so match and re-validation
cannot disagree on gitignored/derived files; and `file_set` **absent/empty ⇒ no
recovery** — every out-of-repo ref falls back to the spec-0011 drop, so recovery only
ever *adds* keeps and never changes the no-file-set behavior (graceful degrade when the
index is not ready). (3) **The honesty floor is load-bearing and inherited, not
re-asserted.** A recovered **file-level** citation stays `is_file_level` (`None` lines,
no fabricated range), so it inherits spec 0011's `gate-skipped:no-line-range` floor and
**never** reads as a verified / high-confidence pass — a recovered keep reads no more
confidently than a non-recovered one. This guard matters precisely because a file-level
citation skips read-back: a wrong-but-existing file-level recovery would propagate
**un-verified**, strictly worse than the honest drop it replaces. Proven end-to-end in
`orchestrator/test_locate.py` (gate path) + `scout/test_scout_normalize.py` (no
fabricated range). (4) **The producer→sink blast radius was closed by category in one
change**, per the spec-0011 grep-the-category discipline: `normalize_spans_with_tally`
return widened **2-tuple → 4-tuple** `(spans, dropped, recovered_spanned,
recovered_filelevel)` plus a non-breaking `recovered_paths_out` out-param carrying the
recovered **file-level** paths (chosen deliberately over a 5-tuple to avoid re-churning
the just-updated 4-tuple callers — a mild, recorded out-param smell); `ScoutTally` gained
`recovered_spanned` / `recovered_filelevel` / `recovered_filelevel_paths` on the
unchanged `last_tally` side-channel; `ScoutEngine(file_set=…)` threads the set;
`build_scout_engine` loads it via `read_manifest(art_dir)`; report `SCHEMA_VERSION 0011/1
→ 0012/1` with two additive last-with-default fields
`fc_citation_recovered_{spanned,filelevel}_count` in the one `_AGGREGATE_DEFAULTS`
source (both shapes validate); and **BOTH** `eval/runner.py` **and** `eval/swebench_eval.py`
aggregate the counts (the sibling-driver enumeration a reviewer flagged — a count tracked
in the single-repo runner but not the per-case driver is the same blast-radius miss class).
**Why:** Spec 0011 made Scout robust enough to *answer* on real queries, but a Q8 model
that knows the file yet prefixes a hallucinated root still degraded to Tier-0 under the
honest 0011 drop. The fix is deliberately deterministic and model-independent: it does
not change which Scout model ships, it makes whichever model ships pay off by salvaging a
citation whose only defect is a fabricated prefix — but **only** when the salvage resolves
to a real, unique, anchored file, because a plausible-but-wrong un-gated file-level keep
would be worse than the drop. The recovery and the future model swap are decoupled on
purpose: the swap is a variance-gated default flip this spec explicitly defers.
**Consequence — the `scout-empty` tail shrinks on real data; the model flip is still a
follow-up.** Shipped TDD-complete: **678 unit pass** (+22 over the 0011 baseline of 656),
ruff clean; **integration 5 passed / 1 skipped** (the AC5 operator test, env-gated, runs
`auto`). **AC5 LIVE** (committed `run_q8rl_recovery_n12.json`, `mode=fast`, Q8
fastcontext-4b-rl, recovery ON vs the committed `baseline_q8rl_n12.json`): **scout_empty
7 → 4 (3 of 7 dead cases RESCUED)**, **dropped 10 → 0**, **recovered_spanned = 10**,
**recovered_filelevel = 0** — every recovery was **SPANNED** (the model emitted the
out-of-repo paths *with* line numbers), so `recovered_filelevel_paths` is honestly empty
and the riskiest un-gated file-level recovery category did not occur in this run; `N=12 <
n_floor` ⇒ self-flagged `indicative_only`, an honest recorded delta with no
strict-inequality gate (no production default flipped). **Deviation:** the AC5 run was
`mode=fast` not `auto` — on the dev host (16 GB) `auto` OOMs (jetsam) co-loading the 5 GB
Q8 Scout + Deep + Deno/Pyodide **and** Deep crashes via a dspy `AdapterParseError` on the
qwen model's malformed JSON (sphinx-9698); recovery is Scout-side so `fast` measures it in
full and only the auto-only gate/escalation counts are excluded from the delta (the
committed integration test still runs `auto`). Open follow-ups carried forward: the **Q8
`scout_model` default flip** (deferred; rl favored 5/12 vs 2/12 gate-fire though sft edges
accuracy 0.25 vs 0.167 — must apply the variance-gated recommend→flip discipline + a
missing-model degrade story, typed `scout-degraded` → Tier-0 floor); the **gate
false-escalation of a correct Scout answer** (requests-1766 — a gate-quality lead); the
**Deep `AdapterParseError` robustness gap** (Deep should map a malformed dspy/model
response to a typed `DeepUnavailable` degrade, not crash); two **upstream FastContext bug
reports** drafted this session; and, still open from Wave 2, **Wave-2.1 substring/fuzzy
matching**.

## 2026-06-28 — Scout citation-shape robustness (seam (a), `citation=False`) + harness degrade visibility shipped — line-less `CodeSpan`, the corrected fix locus, safe + observable degradation

**Spec:** specs/0011-citation-shape/
**Decision:** Fix the spec-0010 finding that Scout was **systematically dead on real
SWE-bench queries** (12/12 `scout-degraded:backend-error`, gate upstream-starved, bare
Tier-0 at 2/12 = 0.167) — and the second, enabling defect that the degrade was
**invisible in aggregate metrics** — in **one** spec, because the visibility gap is
*why* the Scout bug hid (degradation must be both **safe** and **observable**; shipping
the fix alone would leave the next tier failure equally invisible). The
**single-wire-format-owner** and **honest-precision** invariants held and **FastContext
is NOT patched**. Six durable choices were pinned. (1) **The RCA's first framing was a
false premise, corrected by a live spike (T0, the fail-fast first plan step).** Harpyja
**never receives FC citation *objects***: FC's `format_citations` runs **inside**
`agent.run(prompt, citation=True)` and raises `TypeError: string indices must be
integers` when the model's final message has no parseable `<final_answer>` block
(`parse_citations` returns a dict fallback whose string keys `format_citations`
iterates) → caught → `ScoutUnavailable(backend-error)` → Tier-0 degrade. So the
"normalize dict-vs-string citation objects" framing solved a problem that doesn't exist
at Harpyja's seam. The spike confirmed live (FC-4B/Ollama): `citation=True` raises the
exact `TypeError`; `citation=False` returns the raw final message and **structurally
cannot reach** `format_citations`. **(2) Fix = seam (a):** Scout invokes FC
**`citation=False`** (Path A `agent.run`; Path B drops the CLI `--citation` flag),
bypassing the crashing formatter entirely — no exception on the hot path, **no
catch-as-control-flow** — and `scout/client.py::parse_final_answer` parses the raw
`<final_answer>` **text per line, anchored** to the spike-pinned FC grammar
`<no-space-path>[:start[-end]] [(explanation)]`: `path:start` → spanned `CodeSpan`;
bare path / malformed-or-non-numeric line → **file-level** `CodeSpan` (`None` lines, no
fabricated range). A `_looks_like_path` guard (dir separator or dotted extension;
markup rejected) and per-line anchoring (never a naked optional `:\d+` over free text)
keep an incidental prose filename from becoming a spurious citation (AC22). This is the
in-`scout/` text seam — the corrected fix locus; seam (c) (catch-the-crash fallback)
was the pre-stated contingency and **was not needed**. **(3) Honest-precision
representation: `CodeSpan.start_line/end_line` widened to `int | None`** (`None ⇒
file-level`, no line range) with a new **`CodeSpan.is_file_level`** property as the
**single predicate** every downstream consumer branches on, so a coarse path-only
citation never reads as a line-verified one. **Both-or-neither:** a half-`None` span is
not a sanctioned shape and is rejected at the parse/normalize boundary (AC23). **(4)
The blast radius was closed by category, not piecemeal** — the round-2/3 review lesson
(a `None`-line span crashes each int-line consumer in turn; the round-3 `format.py`
miss was the same class as the round-2 representation miss) was generalized to a
discipline: `grep -rn 'start_line\|end_line'` enumerates **all** consumers at once and
each gets its **own** RED→GREEN, ordered producer→…→metrics so a `None` span is made
safe before the next stage sees it. `normalize_spans` (file-level branch:
repo-confine + `is_file` + dedup, skip the line clamp; `normalize_spans_with_tally`
returns a dropped count + per-drop log; the Deep/Tier-2 lined path stays byte-identical);
`format.py` (file-level spans survive un-merged, sort after lined on a None-safe rank
key); `gate.py` (new `GateOutcome.skipped_reason="no-line-range"`, detected **before**
read-back — not scored, not a verified pass); `locate.py` (stable
`gate-skipped:no-line-range`, distinct from `gate-low-confidence`/`gate-scoring-failed`,
escalate-if-a-tier-remains-else-carry-tagged in `auto`, informational in `fast`);
`metrics.py` (`span_hit_kind` → `"line"`/`"file"`/`None`, the path-only branch taken
**before** the line arithmetic in **both** the primary and the secondary/window
oracle — `span_hit_secondary` was a blast-radius miss the spec hadn't enumerated,
caught by the same grep discipline). **(5) Deliverable 2 — first-class degrade
visibility on a bumped schema.** `SCHEMA_VERSION` `0010/1` → `0011/1` with 8 additive
fields last-with-defaults in the centralized `_*_DEFAULTS`: aggregate
`scout_degrade_count`, `scout_degrade_rate` (**null-with-count on a zero denominator**,
never a false `0.0`), `degraded_dominated` (rate > threshold), composable
`reliability_notes`, and `fc_citation_{spanned,filelevel,dropped}_count` (the text-ref
shape distribution — the bare-path frequency is the root-cause signal, no drop silent);
run-metadata `degraded_dominated_threshold`. A new **eval-only**
`EvalConfig.degraded_dominated_threshold=0.5` (field-disjoint from the production frozen
`Settings`) encodes the same judgment as the N-floor: a **majority**-degraded run
characterizes the degrade floor, not the SUT, so its escalation/accuracy/OQ2 outputs
are marked unreliable. **(6) The shape tally rides a Scout-result side-channel, not the
orchestrator seam.** `ScoutEngine.last_tally` (`ScoutTally{spanned, filelevel, dropped}`)
is metadata read **only** by `eval/runner.py` (reset+read per case, then aggregated);
the orchestrator's `list[CodeSpan]` is unchanged so callers still never branch on which
engine ran. `compose_reliability_notes` is shared by `runner.py` + `swebench_eval.py`
so the two aggregation sites cannot drift (R2); `is_file_level` is the shared shape
predicate (R1).
**Why:** Spec 0010's instrument did its job and surfaced a **real Scout/FastContext
robustness defect** on real data — but a floored Scout is indistinguishable from
"cheapest tier works" at the metrics layer, so the defect hid behind the very spec-0007
degrade floor that was working. The low bare-Tier-0 accuracy (16.7%) proves the
Scout→gate→Deep NL ladder is load-bearing, not redundant; until Scout is robust the
ladder is non-functional on exactly the real-world queries Harpyja targets and OQ2 is
uncalibratable on real data. The corrected fix locus matters: the original "normalize
FC's citation objects" plan would have written code against shapes Harpyja never
receives; tracing `scout/client.py` against the RCA (and then the live spike) relocated
the fix to where Harpyja genuinely sits — the answer **text** — where the
honest-precision invariant fits *better* (a `path:start` match → spanned; a bare-`path`
match → file-level).
**Consequence — Scout is robust on real queries; OQ2 is now unblocked but not yet done.**
Shipped TDD-complete: **656 unit pass** (+45 over the 0010 baseline), ruff clean;
**7 live integration pass** (5 Scout + 2 SWE-bench driver, real FastContext-4B + Deep +
Ollama). **AC20 proven live:** the exact 12/12-broken flask case now returns with
**zero backend-error** (`test_scout_live_no_backend_error_citation_false`, 22.5s). One
new stable flag id joins the taxonomy (`gate-skipped:no-line-range`). Deviations: the
T0 spike was captured on a small temp repo (the 4B model returns empty on the full
flask tree; the seam/grammar question is repo-independent) and the AC21 N=12 re-run was
exercised on the legacy fixture (the full N=12 flask sweep is the compute-bound operator
opt-in). Open follow-ups carried forward: the **production OQ2 calibration**
(`verify_threshold`/`verify_top_n`) this UNBLOCKS but does not do — now meaningfully
measurable since Scout fires on real data; **`degraded_dominated_threshold` revisit**
to a data-driven value once a real degrade-rate distribution exists (sequenced after
the production OQ2); and, still open from Wave 2, **Wave-2.1 substring/fuzzy matching**.


## Compacted (older than the active window)

### Project & server bootstrap

- **Specs:** specs/0001-speccraft-v1/, specs/0001-wave-0-foundations/
- **Archive:** .speccraft/history-archive/history.md
- The project adopted speccraft for spec-first TDD from day one — all code changes flow through `/spec:new` — and shipped the agent↔server skeleton as a stub-first MCP contract whose foundational invariants every later wave depends on. The air-gap is enforced in **exactly one helper, `gateway.assert_local`**, reused for both the outbound endpoint and the inbound HTTP listener (`DEFAULT_HTTP_HOST=127.0.0.1` plus the `--allow-remote-bind` opt-out; loopback = `127.0.0.0/8` / `::1` / literal `localhost`) — the bind default and `assert_local` are the security-load-bearing surfaces and must stay auditable in one place, never scattered. `harpyja_locate` is registered returning a schema-valid empty `LocateResult` (`confidence="low"`) with no retrieval, so later waves are purely additive behind an unchanged contract. Config resolves on a **frozen `Settings` dataclass** with fixed precedence: defaults < `harpyja.toml` < `HARPYJA_*` env < per-request override. Tests live next to the package under test (`test_*.py`); there is no top-level `tests/` root.

### Deterministic Tier-0 core & symbol layer (Waves 1–2)

- **Specs:** specs/0002-wave-1-deterministic-core/, specs/0003-wave-2-symbol-layer/, specs/0004-symbol-layer-remaining-grammars/
- **Archive:** .speccraft/history-archive/history.md
- Wave 1 replaced the `harpyja_locate` stub with a model-free, reproducible Tier-0 floor: `.gitignore` is matched via `pathspec` `gitwildmatch` and **never by invoking `git`** (so non-git trees and nested/negation/anchored/`**` rules all work); incremental indexing is a two-level scheme where a cheap `(mtime, size)` gate avoids re-hashing and the sha256 hash is the change-of-record, with `--rehash` as the documented escape hatch for the coarse same-second/same-size miss; "ensure-index" *is* a full incremental refresh on every `locate` (staleness is not a separate heuristic); `rg` on `PATH` is a hard precondition for **search/locate only** (typed `RipgrepMissingError`, surfaced in `doctor`), never for the pure-Python `harpyja_index`; artifacts default to `<repo>/.harpyja/` (self-ignoring) with an `${XDG_CACHE_HOME:-~/.cache}/harpyja/<repo-hash>/` fallback when the repo is unwritable; and the contract treats its fields distinctly — `max_results` is a mandatory clamp, `mode` is accept-validate-flag (never a silent no-op), `language_hint` gives *distinct* notes for unrecognized-hint vs null-language exclusion. Wave 2 added a Tier-0, model-free symbol layer (`symbols/`) surfacing a symbol's **definition above its call sites** via tree-sitter, classified by syntactic form (no type inference) into a byte-reproducible `symbols.jsonl` ordered by `(path, start_line, end_line, kind, name)`; the durable lesson — earned over four cross-review rounds — is that **an untrusted derived artifact must authenticate its own generation with a content fingerprint, not just its producer's identity**: the `symbols.meta.json` sidecar carries `engine_identity` + `record_count` + a sha256 `content_digest` over exact record bytes and forces a full rebuild on any missing/truncated records, missing meta, identity mismatch, or fingerprint mismatch, committing records-first/meta-last via same-dir temp + `os.replace`. Degradation has two distinct persisted causes (`grammar-missing` and region-scoped `parse-error` excluding nested-definition subtrees, so a broken method never suppresses its clean enclosing class), persisted per-file so a no-reparse refresh re-surfaces it. `SymbolEngine` implements the shared **`Locator` protocol** and the orchestrator composes it with the ripgrep Locator into one `CodeSpan` stream that never branches, degrading byte-identically to the Wave-1 path on no symbol match. The 0004 follow-up brought all 10 grammars behind the **unchanged** engine/locator/formatter path and pinned the load-bearing **no-silent-coverage lockstep invariant `classify.KNOWN_LANGUAGES == indexer.SYMBOL_LANGUAGES`** (asserted in `index/test_routing.py`, re-checked at every tier boundary): a language's routing, `engine_identity` slot, and extraction rules ship in the *same* change, because routing a capability ahead of its extraction is itself a false claim (Wave 1 had latently over-routed, returning a silent clean-zero indistinguishable from "we looked and found nothing"). Identity is per-grammar via a `_GRAMMAR_SLOTS` map (`typescript`/`tsx` are two keys sharing one `tree-sitter-typescript` version that bump/absent together). Two documented limitations stand: a C-legal subset of a `.h` C++ header parses cleanly as `c` (degrade fires only on an `ERROR`/`MISSING` node — the `.h`→C default is a **scoped, not absolute, guarantee**), and `parent` is immediate-only, so same-named members under different outer types both match `Foo::bar` — a known addressing ambiguity, with method addressing kept a formatter-ranking signal, not a membership filter. Wave-2.1 substring/fuzzy matching remains the sole open follow-up.

### Tiered retrieval: Scout (Tier 1), Deep (Tier 2), Model Gateway & auto-escalation (Waves 3–5)

- **Specs:** specs/0005-wave-3-scout/, specs/0006-wave-4-deep-rlm/, specs/0007-fastcontext/, specs/0008-wave-5-verification-gate/
- **Archive:** .speccraft/history-archive/history.md
- Waves 3–5 layered the model-backed tiers on top of the deterministic Tier-0 floor, all behind the shared `Locator`/`CodeSpan` boundary so callers never branch on engine identity, and all reached through the **`ModelGateway` as the single outbound caller**: `complete()` air-gaps on **resolved** addresses via the one `assert_local`/`AirGapError` helper (no parallel checks) before any transport is touched, and a non-loopback endpoint raises a loud floor, never a silent degrade. **Scout (Tier 1, Wave 3 + `0007`)** sits behind a `ScoutBackend` Protocol (`FastContextBackend`, no top-level hard import) and drives the real Microsoft FastContext agent — its own Read/Glob/Grep loop, deliberately **not** `dspy.RLM`, the invariant keeping Tier 1 structurally distinct from Tier 2; because the factory is env-only, `FC_*` are injected under a module-level **`threading.Lock`** (not `asyncio.Lock`) while each `agent.run` is bridged onto its **own loop-free worker thread**, serializing Scout (accepted on the single-GPU profile) and never leaking to Deep, with the air-gap asserted before construct/spawn and read-only-ness proven by a no-repo-writes test; FastContext ships as a portable `git`-rev pin. **Deep (Tier 2, Wave 4)** is a `dspy.RLM` explorer confined to a Deno/Pyodide sandbox whose entire world is four bounded read-only host tools, reached only via `mode=deep`; its loop is bounded by a *load-bearing external trio* the backend cannot evade — `deep_max_tool_calls`, `deep_token_ceiling`, `deep_wall_clock_ms` (the last enforced by hard-killing an out-of-band subprocess, since a same-thread deadline can't fire behind a WASM busy loop) — plus host-mediated depth/subquery bounds that are transitively contained by the trio; a `deep-truncated:<bound>` note keeps a budget truncation visibly distinct from a complete run. The **typed-failure-only degradation boundary** is the tiers' shared, most-guarded property: each tier degrades to the tier below **only** on a typed cause (`ScoutUnavailable` / `DeepUnavailable` with named causes), while weak-or-empty citations are an honest result, never a smuggled tier-drop; an honest-empty run is kept distinct from a floor via suffix markers (`+no-matches`, `scout-degraded:<cause>`), and a hard precondition absent (`RipgrepMissingError`) propagates loudly. **Wave 5 (`0008`)** made `mode=auto` finally *climb* by wiring the four deferred seams — query classifier, planning matrix, Verification Gate, escalation ladder — as orchestration only (tier internals unchanged). The gate reads cited lines back from disk and scores relevance by reusing the already-loaded `scout_model` as a generative judge (free on the single-GPU profile), bounded to `verify_top_n` citations (no unbounded model cost on the hot path, dropped count logged), routed through the one `ModelGateway.complete()` with a belt-and-suspenders `assert_local` pre-check — deliberately *not* the third-party-owns-its-client pattern, since the gate is in-house code. `plan_ladder(mode, classification, index_ready)` over a seeded table is the **single source of truth** both `_locate_auto` and the tests consult, so `auto` runs the cheapest tier that can answer and `tiers_run` is a prefix of the planned ladder (`[0,1]`/`[1]` gated-pass, `[0,1,2]`/`[1,2]` escalated, `[0,2]`/`[2]` straight-to-Deep); `fast` runs the gate informationally and never climbs; `deep` is unchanged. A best-effort gate never blocks and never silently passes — a scoring failure routes exactly like a gate-fail — and confidence is keyed on terminal-tier + flags (never path tokens alone) so "nothing found" can never read as high-confidence (no-false-capability). Each invariant swap shipped atomically (the Wave-3 `deep` no-Tier-2 guards and the Wave-0 `auto` byte-identical lock were deleted in the *same* change that wired their successors, so the suite never holds an unspecified window), and `verify_method` rejects any unsupported value with a typed error on every construction path — the seam is pluggable in code but the config accepts only what actually functions.

### Eval harness & SWE-bench measurement instrument (Wave 6a)

- **Specs:** specs/0009-6a/, specs/0010-swebench-eval-dataset/
- **Archive:** .speccraft/history-archive/history.md
- Wave 6a landed `harpyja/eval/` — a **measurement-only / recommend-only** package that observes the real `mode=auto` `locate()` path through its public seam (an injected `LocateStack`; fakes for unit, `build_live_stack` for integration) and flips **no** `Settings` default (the B1 invariant — the flip stays a separate one-line follow-up so "measurement only, no behavior change" is literally true); the only `Settings` touch is the sweep building grid points via `dataclasses.replace` on `verify_threshold`/`verify_top_n`, never mutation. Eval-only knobs live on a dedicated frozen `EvalConfig` (`k_runs`/`proximity_window_lines`/`n_floor`/`catch_rate_bar`), **field-name-disjoint** from the production `Settings` (K is a runner loop count the SUT never reads). **ONE overlap oracle** (`_any_primary_overlap`: any cited span overlaps any expected span in the same file, touching ranges count) defines correctness for span-hit accuracy, gate catch-rate, AND gate false-escalation — no second notion can drift; the Tier-1 signal is captured independently of escalation (`CaseOutcome` carries both `tier1_citations` and `final_citations`). Gate metrics are scoped to the **point** subset only (broad queries bypass the gate and are excluded from both denominators; `escalation_rate` is a separate all-cases aggregate); an undefined gate metric serializes as explicit `null` paired with a zero count, never a false `0.0`. The recommendation is **variance-gated and recommend-only**: the incumbent `(0.6, 3)` is displaced only when a sweep point's advantage strictly exceeds the incumbent's run-to-run spread (`mean(A)-mean(B) > pstdev(B)` over K), else the incumbent is recorded *validated*, not guessed; artifacts write outside the indexed repo (`atomic_write_json` refuses inside `repo_path`) under a loud pinned schema (`validate_report`/`ReportSchemaError`), small-N runs self-flag `indicative_only`. Spec 0010 then gave the instrument **real data**: a SWE-bench Verified adapter using the standalone-localization protocol (the gold patch's pre-image `--- a/…` hunk spans as ground truth at `base_commit` — **no** Docker, patch-apply, or test-exec; the ~3-context-line inflation biases span-hit upward, recorded as a durable `span_inflation_tolerance`), patch-shape D-classification (`≤ POINT_SPAN_MAX_LINES=25` single-file ⇒ `point`; 38 point / 12 broad on the N=50 sample, clearing `N_FLOOR=30`), and the **D-route recorded evaluation intervention**: because production `classify_query` (issue prose) is uncorrelated with patch shape, the driver injects `case.classification` through the existing `LocateStack.classifier` seam so the gate genuinely fires, capturing the production label *before* the override, recording both labels + a `classifier_agreement_rate`, and flagging the OQ2 recommendation `oq2_low_confidence`/`deltas-only` below `AGREEMENT_FLOOR=0.5` (a relative ranking, never a calibration). A per-case-repo driver builds its own `LocateStack` per worktree and pools outcomes into the **unchanged** metrics/recommend layers; report schema bumps are additive last-with-defaults, centralized in `report.py` `_*_DEFAULTS` (the single anti-drift source). The honest live outcome: the instrument surfaced a **real Scout/FastContext defect** (`scout-degraded:backend-error` — FastContext's `format_citations` crashes on real-query output → `ScoutUnavailable` → Tier-0 degrade), so Scout was **non-functional on SWE-bench** and OQ2 **could not be calibrated regardless of N** — absolute numbers are contamination-caveated (SWE-bench is public), the contamination-robust **relative deltas** load-bearing, and **no `Settings` default was flipped**.
