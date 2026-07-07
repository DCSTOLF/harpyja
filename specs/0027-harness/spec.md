---
id: "0027"
title: "harness"
status: draft
created: 2026-07-07
authors: [claude]
packages: [harpyja/scout, harpyja/eval]
related-specs: [0011, 0014, 0017, 0020, 0021, 0022, 0023, 0024, 0026]
---

# Spec 0027 — harness (remove eager context-map; on-demand structure discovery)

## Why

An RCA on the astropy case found the explorer's per-turn prompt is dominated by
spec-0024's `build_context_map` — a flat whole-repo listing (**~1,221 lines /
~10,181 tokens for astropy**) re-sent every turn and growing as tool outputs
accumulate. On local hardware a capable model (Qwen3-16B-A3B) spends **~48–68s per
turn just prefilling that map** before navigating — and the full explorer prompt
(map + verbose system frame + 3 tool schemas) pushes the model into a generation
that did not even complete turn 1 within a 300s timeout. So turns exceed the HTTP
timeout → the gateway raises → `ScoutUnavailable` → floored to `empty` with
`turns_used: None` (a degrade, not an honest "not found"). **The same model + server
localizes the astropy file+block in seconds under OpenCode**, which starts near-empty
and discovers structure on demand via `grep`/`glob`/`ls`. The eager whole-repo *push*
is the defect; the fix is *pull*.

**CRITICAL downstream:** this defect confounds prior findings. The 0026 pilot's
`UNDER_POWERED_STOP` and the 0020–0023 `RETRIEVAL_FUNDAMENTAL` characterization both
ran through this harness and are **timeout-confounded** — a degrade misread as
non-localization. No capability conclusion is valid until the harness is fixed and
those are re-run.

Ref: 0024 (`build_context_map` — the component being removed), 0017 (gateway per-op
timeout), 0011/0014 (degrade visibility + typed floors), 0020–0023 + 0026 (the
confounded findings).

### Load-bearing invariants

- **INVARIANT (push → pull; FULL removal, not shrinkage):** eager whole-repo context
  injection is REMOVED entirely, not reduced to a smaller tree. Shrinkage leaves a
  confound (*how much did I leave in?*) inside the very fix meant to remove one — full
  removal makes the astropy validation unambiguous. Structure is discovered on demand
  through tools the model chooses to call.
- **INVARIANT (blind-start guard — the opposite failure):** removing the map must not
  swing the model into aimless `grep`/`glob` that exhausts its turn budget — which
  ALSO degrades to empty and would look like the bug just fixed. Add a cheap on-demand
  `ls`/tree TOOL (not an eager dump) so the model can fetch layout when it decides to.
  This is the minimal pull affordance; it is NOT the Tier-0 AST symbol tool (that is
  the named follow-up).
- **INVARIANT (cutover, not redesign):** no change to the `ScoutBackend`/`Locator`
  boundary, the gate, matrix, orchestrator, `submit_citations` contract, or the
  existing `grep`/`glob`/`read_span` tools. This removes ONE component (eager map),
  adds ONE cheap tool (`ls`/tree), and re-validates. Air-gap + per-op timeout (0017)
  unchanged.
- **INVARIANT (distinguish the two empties — the measurement that makes this
  provable):** the failure modes MUST be distinguishable in the result:
  **timeout/backend degrade** (the OLD bug — `turns_used: None`, loop raised before
  submission) vs. **honest turn-exhaustion** from blind search (the NEW risk —
  `turns_used == cap`, loop ran but never localized) vs. **honest-empty** (model
  submitted no citation). Use the existing `turns_used` signature; assert all three are
  separable so a re-emptied astropy is diagnosable, not ambiguous.

## What

- **Remove `build_context_map`'s eager whole-repo injection** from the explorer loop
  entirely (delete, or reduce to nothing injected pre-model). The initial prompt is
  OpenCode-style minimal: system prompt + task/query, **no repo listing**.
- **Add a bounded, read-only `ls`/tree tool** (on-demand directory listing,
  repo-confined, output-clamped from existing `Settings`) to the tool suite alongside
  `grep`/`glob`/`read_span` — same untrusted-caller boundary as the others.
- **Ensure the per-turn prompt no longer carries a re-sent, growing map**; verify the
  turn-1 payload drops from ~10K tokens to a small constant.
- **Keep degradation typed + visible** (the standing convention): timeout/unreachable
  → typed `ScoutUnavailable` → Tier-0 floor; turn-exhausted-no-citation →
  honest-empty; both reported.

## Acceptance criteria

([unit]=fakes/injected; [integration]=live, `@pytest.mark.integration`, skip-not-fail)

1. **[unit]** The explorer's INITIAL prompt contains NO whole-repo listing; the turn-1
   payload is a small constant (assert an upper bound well below the ~10K-token
   regression), independent of repo size.
2. **[unit]** The per-turn prompt does not re-inject a repo map; prompt growth across
   turns is bounded by tool outputs + truncation policy only (no map term).
3. **[unit]** The new `ls`/tree tool is read-only, repo-confined, output-clamped;
   hostile input (out-of-repo path, over-budget listing) is rejected/clamped — the
   same boundary as `grep`/`glob`/`read_span`.
4. **[unit]** The result taxonomy separates the three empties: timeout-degrade
   (`turns_used: None`) vs. turn-exhaustion (`turns_used == cap`) vs. honest-empty
   (submitted, no citation) — asserted distinct. **(Makes AC5 interpretable.)**
5. **[integration]** astropy case: the explorer (Qwen3-16B-A3B or the served model)
   **localizes the file+block WITHOUT degrade**, in a small number of turns — the
   OpenCode-parity proof. If it still empties, AC4's taxonomy names WHICH failure
   (must NOT be timeout-degrade). **(This AC is the whole spec.)**
6. **[integration]** The turn-1 payload measured LIVE drops from the ~10,181-token
   regression to the small constant; per-turn latency is no longer dominated by map
   prefill.
7. **[doc]** A correction note is appended to `operator-run-findings.md` AND a recorded
   scope is added to 0020–0023: prior localization findings ran through the eager-map
   harness and are timeout-confounded; they require re-run post-fix before any
   capability conclusion stands. **(The FastContext dependency removal stands
   independently — retracted/unobtainable, sourcing grounds; this corrects the
   CAPABILITY characterization, not the sourcing decision.)**

**Two load-bearing items for review.** **AC5 is the whole spec** — astropy localizing
without degrade is the OpenCode-parity proof, and it is binary: either the eager-map
removal fixed it or it didn't. **AC4 is what makes AC5 interpretable** — if astropy
still empties, the three-way taxonomy tells you whether you fixed the timeout bug and
hit the blind-start risk instead (a different, expected-possible outcome) versus
didn't fix anything; without AC4 a re-emptied astropy is as ambiguous as the bug you
started with. **AC7 is the uncomfortable one and must stay in** — the RCA's real damage
is retroactive: 0020–0023's "FastContext can't localize" and 0026's
`UNDER_POWERED_STOP` are capability-**mute**, not capability-findings; the correction
must say that plainly and scope it precisely (FastContext removal stands; the
"can't localize" characterization is unproven until re-run). Don't let the fix quietly
repair the harness while leaving the false conclusions standing in the record.

## Out of scope

- **Tier-0 AST-as-a-callable-symbol-tool** (the named follow-up — this ships only the
  cheap `ls`/tree affordance).
- **Re-running the 0026 pilot** (separate, AFTER this fix, with the timeout above real
  per-turn cost + a tool-call serving preflight).
- **The model bake-off.**
- **The tool-call-serving preflight itself** (name it as a required pre-bake-off item;
  don't build it here). — Context: the explorer needs an endpoint that emits OpenAI
  `tool_calls`; llama.cpp `--jinja` does, Ollama's `--no-jinja --chat-template chatml`
  path does NOT for a raw HF GGUF.
- **OQ2/gate/threshold tuning.**

## Open questions

1. **`ls`/tree tool granularity:** single-directory listing per call (model walks
   down) vs. bounded depth-N subtree per call. Single-dir is the purest pull and
   cheapest; depth-N saves turns but re-creates a mini-eager-dump risk. **Lean
   single-dir; decide before plan.**
2. **Does ANY minimal orientation help the local model without re-introducing the
   defect** — e.g. a one-line "repo root has N top-level dirs: [names]" (cheap,
   constant) vs. truly nothing? **Lean truly nothing first** (cleanest astropy proof);
   add minimal orientation only if AC5 shows blind-start turn-exhaustion. Pilot the
   empty-start; don't pre-scaffold against a risk that may not materialize. **(Settle
   in review.)**
3. **Truncation-policy interaction (0024):** with the map gone, does the
   citation-preserving truncation still behave, or was it tuned assuming the map term
   dominated history? Verify.

## Validation environment (RCA reference)

The astropy proof (AC5/AC6) runs against the served model that reproduced the RCA:
Qwen3-16B-A3B on **llama.cpp** (`--jinja`, tool-calls confirmed), model id
`unsloth/Qwen3-16B-A3B-GGUF:Q4_K_M`, `127.0.0.1:8131/v1`, 65536 context — the same
model+server that localizes astropy in seconds under OpenCode.
