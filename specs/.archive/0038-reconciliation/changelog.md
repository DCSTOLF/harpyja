---
spec: "0038"
closed: 2026-07-10
---

# Changelog — 0038 reconciliation

## What shipped vs spec

- **Probe-first, one typed outcome: `v1-variant`.** The committed 9-arm live probe
  (`probes/run_probes.sh`, Ollama 0.31.1 / `qwen3:14b`) answered OQ1 decisively and NOT
  with the spec's leading candidate: the OpenAI-compat `reasoning_effort` param on the
  EXISTING `/v1/chat/completions` path genuinely toggles GENERATION-level thinking
  (two-factor verdict — off arm `reasoning_effort:"none"`: content `"391"`, finish `stop`,
  4 tokens, 0 reasoning; on `"high"`: 231 chars, cap-exhausted; omitted: 186 chars,
  default-on). `probes/probe_result.json` (schema `0038/1`, split shape
  chosen_path/outcome/usage_mapping/migration_cost/per-arm) is drift-pinned by
  `harpyja/eval/test_reconcile_probe_result.py` via
  `load_committed_reconcile_probe_result` (archive-first path resolution per the
  evidence-path convention).
- **The wiring is ONE mechanism line, not an endpoint migration.**
  `ExplorerBackend._default_model_call` now maps `explorer_think {True→reasoning_effort:"high",
  False→"none", None→omit}` on the same `/v1` transport; the dead top-level `think` field
  (0034 wiring, proven dropped by 0037) is REMOVED. All three arms run through the SAME
  `complete_with_tools` method — no per-value transport split.
- **AC2 pins reconciled in-change.** The 0034 `None ⇒ outbound byte-identical (params ==
  {max_tokens: 2048})` pin SURVIVES intact (no endpoint switch);
  `test_default_outbound_carries_no_think_param` strengthened (asserts no `reasoning_effort`
  either); the 0034 True/False `think` pins superseded same-change with rationale by
  `test_explorer_think_true_sends_reasoning_effort_high` / `_false_sends_reasoning_effort_none`;
  new loud-FAIL tripwire `test_explorer_think_wiring_matches_committed_probe_outcome` fails
  (not skips) if the committed probe outcome ever stops matching the wired `v1-variant`
  mechanism.
- **AC3 live, observed-not-config-derived.** `test_live_reconciled_think_knob_effectiveness`
  PASSED 3× via strict `run_effectiveness.sh` (skip→hard-fail). Durable artifacts
  (schema `0038/1`, `serving_transport: "v1-chat-completions"`) under
  `eval_work/live_artifacts/reconciled_think_{on,off,default}/`: off arm `[None×5]` reasoning,
  18–49 tokens/turn; on 982–3980 chars/turn; default 852–3457 chars/turn. Off/on separation
  replicated across all 3 runs. N=1 per arm per run, stated.
- **AC5 Deep isolation:** new rot-false guard `test_deep_outbound_carries_no_reasoning_effort`
  (both knob directions).
- **AC6 verifier survives:** additive `serving_transport` field threaded from
  `ExplorerBackend` AND through `run_verified_case`'s hand-assembled artifact;
  `VERIFIER_SCHEMA_VERSION 0034/1 → 0038/1`, version-gated (legacy `0031/1`/`0033/1`/`0034/1`
  still validate). `derive_think_mode` audit: labels still disambiguate operator intent
  (transport recorded separately) — no enum change, pinned by
  `test_derive_think_mode_disambiguates_post_switch`.
- **AC7 supersede-with-record:** the two 0037 conditional tripwires
  (`test_explorer_think_pin_gated_on_native_probe_outcome`,
  `test_live_think_knob_three_factor_effectiveness`) KEPT, docstrings marked
  SUPERSEDED-BY-0038, skipping forever with the archived recorded reason; archived 0037
  evidence + its drift pin untouched. No default flip (None = default-on remains).

## Deviations

- **Branch taken was `v1-variant`, not the spec's expected `native-api-chat`.** The plan's
  leading candidate (a full native `/api/chat` endpoint migration inside `ModelGateway`) was
  pre-authored but NOT taken: the probe found a cheaper honoring path on the incumbent
  transport before any endpoint switch was wired (the exact reason the spec required
  probe-before-wire). OQ2 migration cost = zero (v1 tool-calling with
  `reasoning_effort:"none"` returns normal `tool_calls` with ids, finish=`tool_calls`,
  19 tokens, 0 reasoning); OQ3 divergent-transport debt = zero (no endpoint switch).
- **T4/T5 branch-inapplicable** (recorded N/A, not a gap): no native adapter was needed —
  the `/v1` transport is unchanged and `ModelGateway.complete_with_tools` already passes
  params through; branch blast radius covered by the T6 tripwire + amended pins. AC4's
  condition ("IF `/api/chat`") was not triggered.
- **The `run_verified_case` assembly gap re-surfaced and was fixed mid-close** — the first
  live run revealed the hand-assembled written artifact dropped the new `serving_transport`
  field (the 0033 written-JSON lesson recurring); pinned by extending
  `test_written_artifact_carries_per_turn_and_think_mode`.
- **Three strict live runs, not one:** the first proved the mechanism, the second followed the
  schema bump, the third proved the durable `serving_transport` field end-to-end. Off/on
  separation held across all three.

## Files touched

- `harpyja/scout/explorer_backend.py` (mechanism: `reasoning_effort` wiring + `serving_transport` recording)
- `harpyja/scout/test_explorer_backend.py` (superseded/added pins + tripwire)
- `harpyja/eval/reconcile_probe.py` (NEW — typed-outcome contract + loaders)
- `harpyja/eval/test_reconcile_probe_result.py` (NEW — schema/validator/committed-evidence drift pin)
- `harpyja/eval/live_verifier.py` (`serving_transport` field, `VERIFIER_SCHEMA_VERSION 0034/1 → 0038/1`, both seams)
- `harpyja/eval/test_live_verifier.py` (serving_transport + four-facts-survive + enum audit)
- `harpyja/eval/test_live_verifier_integration.py` (`test_live_reconciled_think_knob_effectiveness` + 0037 supersede)
- `harpyja/deep/test_rlm.py` (Deep no-`reasoning_effort` guard)
- `specs/0038-reconciliation/probes/` (`run_probes.sh`, `probe_result.json`, per-arm `probe_arm_*.json`)
- `specs/0038-reconciliation/run_effectiveness.sh`, `findings.md`

## ADR proposed for history.md

2026-07-10 — Spec 0038 (reconciliation) routed `explorer_think` through the probe-proven
honoring mechanism `reasoning_effort` on the EXISTING `/v1` transport (typed outcome
`v1-variant`) — NOT the expected native `/api/chat` migration — unblocking the thinking A/B.
- Decision: probe-first found a cheaper honoring path on the incumbent transport; the wiring
  is one mechanism line and zero endpoint-migration blast radius; the dead `think` field is
  removed; the 0034 None⇒byte-identical pin survives.
- Why: the spec required probe-before-wire precisely so a not-yet-ruled-out variant of the
  incumbent could be found before pricing a costly migration; it was.
- Consequence: explorer and Deep stay on the one `/v1` gateway path (zero divergent-transport
  debt); the thinking A/B now has a constructible off-arm; no default flip.

## Conventions proposed

- Extend the live-probe adjudication discipline: **a probe pricing a costly migration must
  first scope the not-yet-ruled-out VARIANTS of the INCUMBENT transport** — the cheaper
  honoring path may already exist on the endpoint you are about to leave (0038 found
  `reasoning_effort` on `/v1`, avoiding the full `/api/chat` switch).
- Note the recurrence (0033 → 0034 → 0038) of the **dual-seam written-artifact threading**
  lesson at the trajectory-verified measurement conventions: any new trajectory field must be
  threaded into BOTH `build_trajectory_record` AND `run_verified_case`'s hand-assembled
  written artifact.
