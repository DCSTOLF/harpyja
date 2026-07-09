---
id: "0028"
title: "generation-control"
status: closed
created: 2026-07-07
authors: [claude]
packages: []
related-specs: []
---

# Spec 0028 — generation-control

## Why

Spec 0027 PROVED the explorer harness is cheap-prompt — removing the eager whole-repo
context map cut turn-1 payload ~10,181 → ~60 tokens (~170×), repo-size-independent, units green.
But AC5 (does the model actually localize?) is a recorded HOLD: on the served 16B stack, BOTH
`astropy__astropy-12907` and `django__django-12774` degraded `cause=model-unreachable` at ~300s with
`turns_used=None` — the model NEVER FINISHED GENERATING, so it never localized. `model-unreachable`
≠ "can't localize" (the degrade-masks-outcome trap the 0026 RCA corrected); capability is
UNMEASURED. This blocks the 0026 pilot re-run, the model bake-off, and ANY localization
re-validation.

Measured diagnosis (0027 close + AC1 mechanism probe): the 0027 runaway was
UNBOUNDED generation (no `max_tokens` cap). With a `max_tokens` cap present, the model completes a
first tool call in SECONDS: `enable_thinking:false` (request param) + cap2048 = 7.7s clean
(`finish=tool_calls`, valid JSON, no think trace); thinking-ON + cap4096 = 2.5s clean; the
`/no_think` TOKEN is inferior (43s, ran to the cap — it perturbs the jinja template). So the
`max_tokens` cap is the DOMINANT anti-runaway lever and `enable_thinking:false` is the clean
complement. See `specs/0027-harness/operator-run-findings.md` + `rca-explorer-context-bloat.md`.

## What

Bound the explorer loop's per-call model generation so a first response (a well-formed
`tool_call`) completes in seconds, then re-prove AC5/AC6 on the live 16B stack. Three
changes, in dependency order:

**0. FOUNDATION (do this first — AC3/AC4/AC5 are untestable without it).** Extend the Model
Gateway's tool-calling *return contract* to surface the generation `finish_reason`.
`harpyja/gateway/gateway.py` `complete_with_tools` today returns only `{content, tool_calls}` —
it drops `choices[0].finish_reason`. AC3 (detect `finish=length` truncation) and AC4 (assert a
non-truncated `finish=tool_calls`) both need that field. Add it as an **additive** key
(`{content, tool_calls, finish_reason}`), pinned by a unit test; the return-shape change is
backward-additive (existing keys unchanged). This is the load-bearing fix — lead with it.

**1. PRIMARY LEVER — a tuned `max_tokens` cap** on the explorer's per-call generation (the
dominant anti-runaway lever; the 0027 hang was uncapped). Settings-controlled, threaded into
`complete_with_tools` (reached via `harpyja/scout/explorer_backend.py` `_default_model_call`).

**2. TUNABLE COMPLEMENT — a thinking knob** that can disable model thinking via the request param
`chat_template_kwargs` `{enable_thinking: false}` (MEASURED to work on llama.cpp `--jinja`: 7.7s
clean) — NOT the `/no_think` token (measured inferior, 43s). This is the *experiment*, not the
mandate: the measured evidence shows thinking-ON + a generous cap ALSO completes clean (2.5s), so
thinking-off may be OPTIONAL. AC1 provides the knob; AC6 picks empirically against AC5
localization quality.

**Explorer-scoped by construction (AC8).** The new Settings fields are named `explorer_max_tokens`
and `explorer_enable_thinking` (explorer_-prefixed) so the scope boundary is enforced by the field
names and their call sites, NOT by a prose promise. Only the explorer's `_default_model_call`
passes them; the Deep-tier RLM generation path is UNTOUCHED (out of scope — see AC8). If Deep ever
needs capping, that is its own spec.

MEASURE, don't assume: on success, remove the xfail from `harpyja/eval/test_harness_live.py`
(xfail → xpass → pass).

This is a Model-Gateway/Settings change; the ScoutBackend/ScoutEngine/Locator seam, the four-tool
suite `{grep,glob,read_span,ls}`, orchestrator, gate, matrix, and `submit_citations` stay
byte-untouched (cutover, per the push→pull + exact-tool-count conventions). Do NOT re-introduce
eager repo context to "help" the model — the fix is generation control, not more prompt.

## Acceptance criteria

1. **AC0 — `finish_reason` return contract (FOUNDATION — build first):** `ModelGateway.complete_with_tools`
   returns `finish_reason` as an **additive** key alongside the existing `{content, tool_calls}`
   (surfaced from `choices[0].finish_reason`, normalized to a string — `str()`-cast if the API ever
   returns a non-string; when the field is **absent** from the response it defaults to the exact
   sentinel string **`"unknown"`**). A unit test pins the
   new key (both a present value AND the `"unknown"` absent-default) AND asserts the two existing
   keys are unchanged (backward-additive). Rationale: AC3 and AC4 both branch on `finish=length` vs
   `finish=tool_calls`; without this field they are untestable and an implementer would be forced
   into brittle log/transport scraping.
2. **AC1 — Thinking knob exists and is threaded (the KNOB, not a mandate):** a Settings field
   `explorer_enable_thinking` controls whether the explorer's tool-calling gateway call carries the
   request param `chat_template_kwargs` `{enable_thinking: false}`; a unit test asserts that when the
   knob selects thinking-off the outbound request carries that param, and when it selects thinking-on
   it does not. The knob is the mechanism; AC6 chooses its shipped value empirically. The `/no_think`
   query-token path is explicitly REJECTED (measured 43s / hit-cap / template-perturbing), NEVER a
   fallback. (The measured evidence — thinking-ON + cap = 2.5s clean — is why this is a knob, not a
   forced `enable_thinking:false`.)
3. **AC2 — Bounded generation (PRIMARY lever), pinned + object-level drift-guard on the EXPLORER
   object:** a Settings field `explorer_max_tokens` caps the explorer's per-call max output tokens
   (additive-last, env-coerced), fed at the build site into the explorer's own model-call path so it
   is applied to the `complete_with_tools` request; a unit test asserts it reaches the request as
   `max_tokens`. The default is **pinned at 2048** (512 truncated in probe; 2048 completed clean) —
   a specific value, not a `>512` floor. Per the DRIFT-GUARD convention, the finite cap that guards
   the runaway invariant lives on the **explorer-owned constructed object's own field default** —
   concretely `ExplorerBackend`'s own `max_tokens` constructor-field default `= 2048` (fed by
   `Settings.explorer_max_tokens` at the build site), so a direct `ExplorerBackend(...)` construction
   that bypasses `Settings` is still bounded — pinned by a field-default introspection test on
   `ExplorerBackend`, never a source grep. **`ModelGateway` stays purely param-driven and does NOT
   acquire a `max_tokens` default of its own** — the cap is passed as a per-call param only, so the
   Deep-tier path (which calls the gateway WITHOUT `explorer_max_tokens`) is never capped (see AC8).
4. **AC3 — Truncation is a typed degrade with a STABLE cause id (fifth explorer cause):** a capped
   generation that ends **`finish_reason == "length"`** is handled as a degrade emitting the stable
   machine-readable cause **`scout-degraded:generation-truncated`** (per the cause-taxonomy
   convention — an identifier, never prose), never silently swallowed as an empty turn. **Edge case
   decided: `finish=length` is generation-truncated REGARDLESS of whether a syntactically valid
   `tool_call` is present** — a length-truncated response was cut off mid-generation (its tool-call
   args may be silently incomplete, and per AC7 accepting it would mask cap pressure), so
   `finish=length` never takes the success path even if a parseable tool_call rode along. This is a
   NEW fifth cause on the explorer path: the per-cause count plumbing from 0027 (`_scout_degrade_cause`
   / the `scout_degrade_*_count` report fields) counts it DISTINCTLY (its own additive
   `scout_degrade_generation_truncated_count`), report `SCHEMA_VERSION` bumped additively. Unit/guard
   test asserts the cause id fires (including the length+valid-tool_call case) and is counted
   separately from `model_unreachable` etc.
5. **AC4 — LIVE first-call latency:** on the served 16B stack (llama.cpp `--jinja`,
   `unsloth/Qwen3-16B-A3B-GGUF:Q4_K_M` @ `127.0.0.1:8131/v1`), a first explorer model call returns a
   well-formed (`finish_reason == "tool_calls"`, NOT `"length"`) `tool_call` in ≤ 30s (floor
   evidence: 2.5–7.7s).
6. **AC5 (THE PAYOFF — the HARNESS drives the model to a citation; catches placeholder-value calls
   AC4 cannot):** both `astropy__astropy-12907` AND `django__django-12774` RUN TO COMPLETION WITHOUT
   a timeout/backend degrade and WITHOUT generation-truncation — the terminal state of each run is
   classified via the cause taxonomy into exactly one of three MUTUALLY EXCLUSIVE buckets:
   **(a) localized** (correct OR right-file-wrong-span — any hit whose file matches the gold),
   **(b) honest turn-exhaustion** (`loop-turns-exhausted` at N=10 with real tool progress, no
   file-matching hit), or **(c) honest-empty capability result** (a clean terminal submission with
   no gold-file hit — NOT a degrade) — and is NOT `model-unreachable`, `backend-error`, or
   `generation-truncated`. (`right-file-wrong-span` lives ONLY in bucket (a); the buckets do not
   overlap.) AC5 gates on the HARNESS working
   (the model was driven to a terminal answer without a degrade masking the outcome), NOT on
   localization *perfection*: per-case localization **quality is reported, not gated**. Asymmetric
   rule (decided): if one case is a genuine degrade (`model-unreachable`/`backend-error`/
   `generation-truncated`) it is a **FAIL, not a hold**; if the "worse" case is an honest
   right-file-wrong-span or honest-empty *capability* result, AC5 **PASSES** (the harness drove the
   model; the model's localization quality is a separate measurement). Placeholder/semantically-empty
   citations (e.g. `path:"string"`) are rejected as non-localizations — a well-formed-but-empty call
   AC4 cannot catch. On pass, `harpyja/eval/test_harness_live.py` loses its xfail and passes.
7. **AC6 — Empirical lever choice recorded (against AC5 quality):** the close records the measured
   comparison (thinking-off vs thinking-on, each capped) and WHY the shipped `explorer_enable_thinking`
   value was chosen, against AC5 localization quality — not an assumed default. `explorer_max_tokens`
   default is 2048 unless AC6 measures a better value, in which case the doc is updated to the pinned
   measured value. If thinking-off degrades localization, record it, don't hide it.
8. **AC7 — Cap tuned for turn-budget headroom, NOT just latency (the cap×turn-budget confound):** the
   shipped `explorer_max_tokens` is validated against BOTH ends — high enough that a single
   generation can emit COMPLETE tool-call args (including a multi-span `submit_citations`) so the cap
   does NOT force the model into more, smaller turns and blow the N=10 budget (turn-exhaustion
   masking capability as incapability — the exact degrade-masks-outcome trap this spec exists to
   kill), AND low enough to bound runaway. The close records that both bounds were checked (not
   latency alone). N=10 is inherited unchanged from the 0026/0027 harness; the close states so
   explicitly.
9. **AC8 — Explorer scope enforced by construction (Deep OUT):** the generation knobs are
   `explorer_`-prefixed and passed ONLY by the explorer's `_default_model_call`; the Deep-tier RLM
   generation path is **out of scope and byte-untouched**. A test asserts the Deep-tier outbound
   request carries NEITHER the `max_tokens` cap NOR `chat_template_kwargs.enable_thinking` (assert on
   the actual outbound request fields, not just the absence of the `explorer_*` Settings names —
   scope enforced by field naming + call site, not prose).

## Out of scope

- The model bake-off itself (this UNBLOCKS it).
- The 0026 pilot re-run and any re-authoring/execution of the 0026 terse eval set (unblocked, not
  done here).
- The Tier-0 AST symbol tool.
- A total-request wall-clock deadline (0017 caveat — separate).
- Adding/changing explorer tools (suite stays exactly `{grep,glob,read_span,ls}`).
- Re-introducing any eager repo context/map (push→pull holds).
- Substantive localization-prompt changes beyond the minimal directiveness needed for generation
  bounding.
- **Capping / thinking-controlling the Deep-tier RLM generation path** (AC8 decision: Deep is
  OUT — byte-untouched; if it ever needs bounding that is its own spec). The `explorer_`-prefixed
  field names enforce this by construction.
- Changing N (turn budget) — inherited unchanged from 0026/0027 at N=10 (AC7 states so).

## Open questions

_none_

## Grounding addendum (for the implementing session)

- **AC1 mechanism is settled (the KNOB, not a mandate)** — llama.cpp `--jinja` accepts
  `chat_template_kwargs: {"enable_thinking": false}` as a request field and it works (7.7s, no think
  trace). Implementation threads that (gated by `explorer_enable_thinking`) + `explorer_max_tokens`
  through `ModelGateway.complete_with_tools`. Thinking-off is the tunable complement chosen by AC6,
  NOT a forced default — thinking-ON + cap measured 2.5s clean.
- **`finish_reason` is the load-bearing prerequisite (AC0)** — `complete_with_tools` currently drops
  `choices[0].finish_reason`; AC3/AC4 are untestable until it is surfaced additively. Build AC0 first.
- **Probe caveat** — the AC1 probe used a shared over-broad tool schema, so any placeholder-value tool
  call referenced (`path:"string"`) is a probe artifact; the real per-tool schemas are minimal. Watch
  for placeholder-value calls in the live AC5 run — a quality failure AC5 catches, AC4 doesn't.
- **Live stack / worktrees / gold / fixture / conventions** — llama.cpp 16B @ 8131, worktrees under
  `eval_work/worktrees/`, gold `separable.py:242-248` + `query.py:689-695`,
  `swebench_verified.resolved.jsonl`, and the push→pull / cause-taxonomy / additive-Settings /
  exact-tool-count / air-gap conventions.
- **Read first:** `specs/0027-harness/{operator-run-findings.md,changelog.md}`.
