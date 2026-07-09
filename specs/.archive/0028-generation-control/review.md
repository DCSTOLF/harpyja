---
spec: "0028"
title: generation-control
date: 2026-07-07
agents: [codex, claude-p]
rounds: 3
verdicts:
  round-1: { codex: changes-requested, claude-p: changes-requested }
  round-2: { codex: changes-requested, claude-p: changes-requested }
  round-3: { codex: approve, claude-p: approve }
quorum: 1 approve/approve-with-comments
quorum_met: true
recommendation: reviewed → proceed to /speccraft:spec:plan
---

# Cross-model review — spec 0028 (generation-control)

Three rounds. Both aux agents (codex / gpt-5.5, claude-p) converged to **approve** in round 3;
quorum (1 approve) is met and the spec is marked **reviewed**. Round-1 synthesis is preserved in
`review-round1.md`; raw agent outputs for all rounds are in the job transcript.

## Final verdict (round 3)

| Agent | Round 1 | Round 2 | Round 3 |
|-------|---------|---------|---------|
| codex (gpt-5.5) | changes-requested | changes-requested | **approve** |
| claude-p | changes-requested | changes-requested | **approve** |

No guardrail or convention violations remain. Both agents confirmed the spec respects: additive
Settings, object-level DRIFT-GUARD, stable CAUSE-TAXONOMY, EXACT-TOOL-COUNT (four tools untouched),
gateway-centered AIR-GAP, and a deliberate, well-justified refinement of HOLD-BY-CAUSE in AC5.

## What changed across rounds

### Round 1 → Round 2 (7 fixes)
1. **(BLOCKING, both agents) `finish_reason` return contract.** `complete_with_tools` returned only
   `{content, tool_calls}`, making AC3/AC4 untestable. → New **AC0** adds `finish_reason` as an
   additive return key, pinned by a unit test that also asserts the two existing keys are unchanged.
   Built first, as the load-bearing foundation.
2. **AC1/What/AC6 mandate-vs-knob inconsistency.** → Reframed to a **knob** (`explorer_enable_thinking`)
   chosen empirically by AC6; the `max_tokens` cap is the mandate, thinking-off the tunable complement
   (the measured thinking-ON + cap = 2.5s clean is why it is a knob, not a forced default).
3. **AC2 default unpinned + drift-guard location.** → Pinned at **2048**; drift-guard moved to the
   constructed object's own field default.
4. **AC3 needed a stable cause id.** → **`scout-degraded:generation-truncated`**, a distinct fifth
   explorer cause with its own additive count and a `SCHEMA_VERSION` bump.
5. **AC7 Deep-tier scope left open (author's call requested).** → Decided **OUT**: Deep byte-untouched,
   enforced structurally by `explorer_`-prefixed field names (now **AC8**).
6. **cap×turn-budget confound.** → New **AC7**: the cap is tuned for turn-budget headroom (complete
   `submit_citations` args, no forced turn inflation), not latency alone; N=10 inherited unchanged.
7. **AC5 asymmetric-outcome handling.** → AC5 gates on the harness working (no degrade masking the
   outcome), not localization perfection: a genuine degrade = **FAIL**; an honest capability result
   (right-file-wrong-span or honest-empty) = **PASS**.

### Round 2 → Round 3 (4 narrow fixes — both agents pre-approved contingent on these)
- **R2-1 (both): AC2 drift-guard target unnamed + gateway-wide leak risk.** → AC2 now names
  **`ExplorerBackend.max_tokens = 2048`** (own field default, fed by `Settings.explorer_max_tokens`),
  and explicitly states **`ModelGateway` stays param-driven with no `max_tokens` default of its own**
  so the Deep path is never capped. Introspection test is on `ExplorerBackend`. This closes codex's
  tension (a callee-level default would have silently capped Deep too).
- **R2-2 (both): AC3 undefined for `finish=length` WITH a valid tool_call.** → Decided:
  `finish=length` is generation-truncated **regardless** of a parseable tool_call (args may be
  silently incomplete; accepting it would mask cap pressure per AC7); test includes that case.
- **R2-3 (both): AC0 absent-`finish_reason` sentinel unpinned.** → Pinned to the exact string
  **`"unknown"`**; test asserts both present-value and absent-default.
- **R2-4 (claude-p): AC5 bucket overlap** (`right-file-wrong-span` in both (a) and (c)). → Buckets
  are now mutually exclusive: `right-file-wrong-span` lives ONLY in (a) localized; (c) is honest-empty
  (no gold-file hit). Explicit non-overlap statement added.

## Round-3 residual notes (optional polish — non-blocking, folded or deferred)

- **[FOLDED] AC8** — assert on the actual outbound request fields (`max_tokens`,
  `chat_template_kwargs.enable_thinking`), not just the absence of the `explorer_*` Settings names.
  Applied.
- **[FOLDED] AC0** — `str()`-cast if the API ever returns a non-string `finish_reason`. Applied.
- **[DEFERRED] AC3** — a one-line note confirming `generation-truncated` is intentionally
  non-suffixed (no `+no-matches`-style suffix). Author's judgment: the cause is inherently
  non-suffixed; not worth spec churn.
- **[DEFERRED] AC4** — the 30s ceiling is generous vs the 2.5–7.7s floor; a tighter bound (e.g. 15s)
  would catch latency drift earlier. Left at 30s deliberately — AC4 proves sub-runaway operation on a
  loaded local box; a tighter regression bound is a live-tuning call, not a spec commitment.

## Recommendation

**Reviewed.** Quorum met with two independent approvals. Proceed to `/speccraft:spec:plan` — the
implementer should build in AC order (AC0 `finish_reason` first, then AC1–AC3 knobs/degrade, then the
live AC4–AC8 validation).
