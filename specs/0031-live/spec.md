---
id: "0031"
title: "live"
status: ready-for-operator
started_at_sha: 78e7d07
created: 2026-07-08
authors: [claude]
packages: []
related-specs: []
---

# Spec 0031 — live

## Why

Three consecutive specs produced capability numbers that cannot be verified from machine evidence, each failing a DIFFERENT integrity check: 0029 couldn't prove which model/endpoint served it (committed test hardcodes 16B/llama.cpp:8131 while the changelog claims 14B/Ollama, override un-git'd); 0030's early "live" runs silently stopped at Tier-0 with the model never invoked, and one ran the wrong (unavailable) model — both nearly reported done; 0030's final run had a JSON artifact (tiers_run=[0,1]) but could NOT confirm the `symbols` tool was actually called, so its lift claim rests on "tool available + good outcome," not causation. The agent repeatedly tried to close green on unrun/unverifiable measurements. The model bake-off AND the representative eval set are nothing but capability measurement across models × cases — they cannot run on a harness whose results the agent can fabricate or fail to verify.

**INVARIANT (machine evidence over agent summary):** validity is asserted from the run's trajectory/log, NOT from the agent's prose. A run that cannot prove the four facts below FAILS — it does not "probably pass." No capability number is trusted without its verification record.

**INVARIANT (instrument, not capability):** this builds the measurement harness; it does NOT run the eval set or rank models. Its own acceptance is met by proving the four assertions fire correctly on constructed pass/fail runs — not by any localization result.

**INVARIANT (machine enforcement):** the verifier's guard does not silently pass or defer judgment to prose. When the four facts cannot be proven, the run is FAILED with a distinct, stable, machine-readable code (one of six enumerated reasons, see AC1 below). The guard's failure surfaces as: (a) a non-zero exit in CLI usage, (b) a raised exception in API usage, or (c) an artifact-resident `verifier_status="FAILED"` field (with `failure_reason` enumerated) for integration workflows. Silent pass is not an option.

## What

**THE FOUR FACTS a valid live run must prove** (each failed by a prior spec):

1. **MODEL IDENTITY** — which model + endpoint actually served the request (0029's miss). Asserted from the response/trajectory, not from Settings or the agent's claim.
2. **MODEL INVOKED** — the model was actually called; the run did NOT silently short-circuit to Tier-0 (0030-early's miss). tiers_run must show Tier-1 engaged, and the trajectory must contain ≥1 model turn.
3. **TOOLS CALLED BY NAME** — which explorer tools were invoked, by name, in the trajectory (0030-final's miss). A lift claim about `symbols` requires `symbols` to appear in the tool-call log.
4. **TERMINAL BUCKET** — the terminal state + bucket (correct/right-file-wrong-span/wrong-file/empty) tied to the gold span, and any degrade cause — the existing cause taxonomy.

**The six enumerated failure reasons** (when any of the four facts cannot be proven):
- `model-unknown` — the served model cannot be extracted from response or configured endpoint
- `model-mismatch` — the served model differs from the requested model
- `model-not-invoked` — Tier-0 short-circuit; tiers_run=[0] and no model turn in trajectory
- `tool-names-unextractable` — tool calls present but tool names cannot be parsed from trajectory
- `terminal-bucket-missing` — no terminal state or bucket can be assigned (no gold-span comparison possible)
- `artifact-incomplete` — run produced no verifier artifact or artifact lacks a required field

**Implementation:**

**Prerequisite instrumentation (minimal, additive, read-only measurement plumbing):**
- Currently, `LoopResult.history` (in scout/explorer_loop.py:65) is in-memory only and discarded by `ExplorerBackend.locate` (explorer_backend.py:269). A NEW capture seam is required: immediately after `explorer_loop` returns, before the history is discarded, capture the per-turn records (model turns, tool calls, model turn count) to a durable JSON structure inside the run artifact (harpyja/eval/runner.py's event dict). This is a new, read-only write path; it does not change explorer decision behavior or tool routing.
- Currently, `ModelGateway.complete_with_tools` (gateway.py) does not extract `response['model']` from the OpenAI-compatible response. A NEW extraction point is required: within the gateway's response-handling block, extract the served `model` field and thread it into the trajectory/artifact structure so model identity is available for postflight verification. This is read-only metadata capture; it does not change request/response semantics.

**Postflight verifier module:**
- A verifier module that reads the captured trajectory artifact (containing per-turn records and served-model identity) and extracts the four facts. The verifier does NOT modify the explorer, loop, or gateway behavior; it reads only.
- A guard that FAILS a "live" measurement if any of the four is unprovable from the trajectory, with a machine-readable exit: (a) CLI raises `VerificationError(reason=<one of the six codes>)`, exit nonzero; (b) API returns `VerifierResult(status="FAILED", failure_reason=<code>, details=...)`; (c) artifact field `verifier_status="FAILED"` with `failure_reason` populated for workflow consumers.
- The verifier records the four facts + the served model/endpoint + the tool-call names + the terminal bucket into a durable JSON artifact (extend the 0026/0030 report schema; additive, versioned `VERIFIER_SCHEMA_VERSION`).
- Reproducibility fix: the model/endpoint under test is recorded IN the verifier artifact. The committed test (specs/0029-loop/test_harness_live.py) MUST be updated to assert: the model used in the test matches the model recorded in the rerun artifact, OR explicitly document the override and the reason (close the 0029 committed-test-vs-changelog mismatch).
- Re-run 0030's two cases through this verifier as the proof-of-instrument: produce a verifier artifact that shows model identity, model invoked, tools-called-by-name (resolving whether `symbols` was used), and bucket. Record whatever it shows, without pre-judgment.

## Acceptance criteria

1. [unit] The verifier extracts all four facts from a constructed trajectory fixture; a trajectory missing any fact is FAILED with one of the six enumerated reasons (model-unknown, model-mismatch, model-not-invoked, tool-names-unextractable, terminal-bucket-missing, artifact-incomplete). No silent pass; each unprovable fact maps to a distinct code.
2. [unit] Model-identity assertion catches a wrong-model run (fixture: response-model ≠ configured/requested model → status=FAILED, failure_reason=model-mismatch).
3. [unit] Model-invoked assertion catches a Tier-0-only run (fixture: tiers_run=[0], no model turn in trajectory → status=FAILED, failure_reason=model-not-invoked).
4. [unit] Tool-call extraction lists invoked tools by name; a run where `symbols` was available but never called is distinguishable from one where it was called (tool_names_invoked field in artifact records exactly which tools appeared in tool-call events).
5. [unit] Durable JSON artifact schema (`VERIFIER_SCHEMA_VERSION`, additive, atomic write) carries: (a) all four facts (model_identity, model_invoked, tool_names_invoked, terminal_bucket), (b) per-run provenance (timestamp, served_model, endpoint, verifier_status, failure_reason if FAILED), (c) exactly one of verifier_status∈{PASSED,FAILED}. A run without a complete artifact is a FAILED measurement (status=FAILED, failure_reason=artifact-incomplete).
6. [integration] Proof-of-instrument: 0030's astropy + django cases re-run with preflight checks (local Model Gateway reachable, configured model present in endpoint, no non-localhost endpoint); if preflight fails, skip with documented reason (not a measurement failure, an invalid setup). For each case that proceeds: verifier produces an artifact with all four facts or distinct failure reason per unprovable fact; status field is PASSED or FAILED. Whether `symbols` tool appears in tool_names_invoked is recorded as-is (not graded; if captured, the prior 0030 lift claim can be re-assessed; if not captured, claim is retracted). Both astropy and django cases must complete with verifier-produced artifacts.
7. [doc] The 0029 committed-test/changelog model mismatch is reconciled: (a) run the test as-is through the verifier, (b) record the model/endpoint mismatch in the artifact and test file comment, (c) commit the correction so the code and the recorded run are no longer at odds. "Annotate" alone is insufficient; the committed test code or a companion override/fixture must explicitly state why the run used a different model than the current Settings default, with a linked issue/rationale. The "trajectory-verified" requirement is codified as a convention binding all future live measurement specs (bake-off, eval set, capability reports): no capability number is trusted without its verifier artifact and trajectory proof.

## AC6 Proof-of-Instrument — Ready for Live Run

**Status:** Fully implemented and ready. All code in place; awaits live stack (Ollama/llama.cpp with the configured model).

**What it will show:**
When the operator runs `test_proof_of_instrument_astropy_django_produce_verifier_artifacts` on a live stack (see `specs/0031-live/plan.md` T23–T24 and `harpyja/eval/test_live_verifier_integration.py`), it will:

1. **Load astropy-12907 and django-12774** from the test fixture (worktrees at `.harpyja_eval_work/...`)
2. **Preflight:** Check that the Model Gateway is reachable (localhost), the configured model is present in `/api/tags`, and skip cleanly if either fails
3. **For each case:** Construct an `ExplorerBackend`, run the explorer loop against the case query, capture `last_trajectory`, derive `terminal_bucket` from the gold span using `locate_accuracy.classify_case`, verify the trajectory, and write a verifier artifact
4. **Artifact output:** Two JSON files (one per case) in the output directory, each carrying:
   - `verifier_status` ∈ {PASSED, FAILED}
   - `model_identity`, `model_invoked`, `tool_names_invoked`, `terminal_bucket`
   - If FAILED, a distinct `failure_reason` (one of the six codes)
   - The `tool_names_invoked` list **will show whether `symbols` appears** (or not)

**This answers the 0030 open question:** After 0030 closed without confirming whether the `symbols` tool was actually invoked (lift measurement was "inconclusive-and-inconsistent"), this re-run will provide the trajectory evidence. If `symbols` appears in `tool_names_invoked`, the lift claim can be re-assessed on that artifact. If it does not, the 0030 lift claim is retracted and `symbols` availability is decoupled from proof-of-use.

**How to run it:**
```bash
# Ensure llama.cpp or Ollama is running on localhost:8131 (or the configured endpoint)
# with the model specified in specs/0031-live/plan.md (currently: Qwen3-16B)
pytest harpyja/eval/test_live_verifier_integration.py::test_proof_of_instrument_astropy_django_produce_verifier_artifacts -v
```

If the live stack is unavailable, the test skips cleanly with a documented reason.

## Out of scope

- The representative eval set (built next, ON this instrument)
- The model bake-off (runs ON this instrument)
- Re-establishing 0029's capability numbers (superseded by the eval set; only the test mismatch is fixed here)
- Changes to explorer decision logic, tool routing, or gateway request/response semantics (the explorer loop itself, tier selection, degrade taxonomy)
- Tier-0 semantic/call-graph tier

**In-scope measurement plumbing (explicitly carved out):** Adding read-only capture seams to persist the already-computed trajectory and served-model metadata into the run artifact (new write paths in explorer_backend.py and gateway.py that do not change any decision behavior) is in-scope instrumentation necessary to enable postflight verification.

## Open questions

1. **Model-identity capture and fallback:** The gateway's new extraction seam (see Implementation) must decide: (a) does `response['model']` exist in the actual served responses (Ollama/llama.cpp)? If not, is the configured endpoint's served-model list a valid fallback? (b) If captured model ≠ configured/requested model, is this a `model-mismatch` FAIL (AC2) or a recoverable degradation? (c) If the served model cannot be captured at all, does the verifier emit `model-unknown` and proceed to check other facts, or FAIL the measurement immediately? Design this extraction path during planning, with AC2 fixture coverage for all three branches.
2. **Preflight model-presence check:** For AC6's integration test, should the preflight probe verify model presence via the OpenAI-compatible endpoint's `/api/tags` (Ollama) or equivalent, or is the first actual request sufficient to discover unavailability? Early probe preferred; scope in plan phase.
