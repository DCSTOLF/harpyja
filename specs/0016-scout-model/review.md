# Review — Spec 0016 "scout_model"

Reviewers: `codex` (codex-cli, `codex exec --full-auto`), `claude-p` (local `claude -p`)
Synthesis: cross-reviewer + orchestrator source-verification

## Round 1 (2026-07-01)

| Reviewer | Verdict |
|----------|---------|
| claude-p | **approve-with-comments** |
| codex | **changes-requested** → folded (see below) |

**Quorum (≥1 approve / approve-with-comments): MET** (claude-p). Status → `reviewed`.

Both reviewers confirmed the core B1 fix is correct and every concrete source claim in
the spec was verified true against the tree (`settings.py:77` scout default,
`settings.py:43` `lm_model="local"`, `_add_model_flags` at `swebench_eval.py:881` lacking
`--scout-model`, `_settings_from_args` at `:793`, the paired `_FC_GGUF` constant at
`test_settings.py:127`). No guardrail violations — the change touches model *tags*, not
endpoints, so the air-gap is untouched. The two reviewers converged on five load-bearing
precision/coverage items; **all five were folded into the spec before marking reviewed**,
which resolves codex's `changes-requested`.

### Folded — the five convergent load-bearing items

1. **Gate coupling (claude-p's #1 — the strongest).** The draft's flat "no change to the
   gate" INVARIANT overclaimed. `scout_model` does double duty: it is also the gate's
   scoring backend (`verify_method="scout_model"`, the only shipped backend —
   `settings.py:83-94`, `_VERIFY_METHODS`). Source-verified: flipping `scout_model`
   changes the model the gate scores with. **Fold:** added a "Gate-coupling caveat" —
   the flip changes *which served model the gate calls* (broken→served plumbing),
   explicitly **distinct** from B2, which changes the gate's *judging logic*; the next
   OQ2 run must not conflate the two.

2. **Deferred decisions pulled into the spec (codex).** A reviewed spec should not defer
   user-facing CLI semantics and a production-default change to "the plan." **Fold:**
   the two open questions are now **Decisions D1/D2**:
   - **D1** — `--deep-model` canonical, `--lm-model` deprecated alias; `--deep-model`
     wins *regardless of CLI order* via **distinct dests reconciled in
     `_settings_from_args`** (not argparse positional last-wins). AC4 now pins both
     orders.
   - **D2** — the `lm_model` flip is intentional and **global** (hits MCP `mode=auto`,
     not only eval). Blast radius enumerated; the **llama.cpp regression** both reviewers
     raised (`"local"` is benign there, the Ollama Qwen tag won't resolve) is named and
     accepted, mitigated by unchanged override precedence.

3. **"Served" is instance-relative, not universal (codex).** **Fold:** added a "served"
   clarification — the claim is narrow (tags in the documented required local Ollama set,
   replacing a nowhere-served tag), and AC7 was tightened to a **positive `/api/tags`
   membership check** that distinguishes missing-Ollama / missing-tag / old-tag.

4. **AC6 drift guard testability (both).** A text grep over `harpyja/` false-positives on
   the `:796` docstring and the tests. **Fold:** AC6 now specifies **field-default
   introspection** (`Settings()` / `dataclasses.fields`), never a source scan.

5. **Doc blast radius (claude-p; convention: enumerate every consumer).** The
   `_settings_from_args` docstring at `swebench_eval.py:796` asserts `lm_model="local"` —
   factually wrong after the flip. **Fold:** AC9 (was AC8) now names all three doc
   consumers (settings comment, README, the `:796` docstring). A new **AC8** requires
   `run`/`sweep --help` to list both new flags + the deprecated alias (codex suggestion).

### Air-gap assumption made explicit

codex flagged (and claude-p concurred) that the strict runtime air-gap guardrail requires
the `hf.co/...` strings to be understood as **local Ollama tags, not runtime network
fetch**. **Fold:** an "Air-gap note" states this — tags, never endpoints; Model Gateway
stays localhost-only.

## Plan-level items (carry to `/speccraft:spec:plan`, not spec blockers)

- Implement D1's distinct-dest reconciliation in `_settings_from_args` (canonical beats
  alias) and pin AC4's both-orders test.
- AC7's live smoke queries Ollama `/api/tags`; keep it env-gated skip-not-fail.
- Confirm the new scout Q8 tag and Qwen3-8B tag are both in the eval host's served set at
  implementation time (repo memory records them served).

## Action recommendation

**Reviewed — proceed to `/speccraft:spec:plan`.** The core B1 fix (served scout default +
`--scout-model` escape hatch) is unambiguously correct and source-verified; the five
convergent review comments — most importantly the gate-coupling correction and the
in-spec resolution of D1/D2 — are folded, so the spec is now precise and review-hookable.
