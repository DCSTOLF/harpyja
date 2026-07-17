---
id: "0049"
title: "serving"
status: closed
created: 2026-07-17
authors: [claude]
packages: []
related-specs: [0048, 0046, 0041, 0038, 0034, 0019]
---

# Spec 0049 — serving

## Why

0048 halted the bake-off on a determinism blocker: served models are non-greedy
(temp>0), so the same case flips buckets across runs (astropy empty↔RFWS) →
REPLAY-FAIL → all three models excluded. Root cause validated: the flip is
SAMPLING-DRIVEN submit-discipline variance (both runs found the right file; they
diverged only at the terminal submit-vs-dawdle action, a temp>0 coin-flip), not
batching/KV-cache. Greedy (temp=0) was validated on 2 cases/2 repos — buckets
reproduce.

This spec makes greedy the standing served config for downstream
capability/policy measurement, via PATH A: new variant tags (`qwen3-*-greedy`),
base tags untouched, config re-frozen with a new hash. It unblocks the
bake-off's determinism half AND collapses the sampling noise that produced
0046's BASELINE_DRIFT_STOP — so the reactive/confirm knob and the thinking A/B
become measurable too.

Ref: 0048 (determinism validation, the greedy Modelfiles staged in `serving/`,
`qwen3-14b-greedy:latest` already created, the bucket-not-bit-perfect caveat),
0046 (BASELINE_DRIFT_STOP — single-draw noise), 0038 (v1 reasoning_effort
serving mechanism), 0041 (exclusivity gate), 0034 (byte-pinned generation
params), 0019 (`preflight_models_present`: the `assert_local`-then-`/api/tags`
egress precedent this spec's membership check reuses).

### Invariants

- **PATH A — variant tags, base tags UNTOUCHED:** create `qwen3-14b-greedy` /
  `qwen3-8b-greedy` / `qwen3.5-4b-greedy` (temp=0) via committed Modelfiles. The
  shared base tags (`qwen3:14b` etc.) are NOT recreated or mutated — path B was
  rejected because mutating shared registry tags is irreversible and silently
  changes behavior for everything else using them. The served config is
  re-frozen with a NEW hash recording the greedy variant tags; the bake-off's
  provenance then reads "ran on greedy variants," not silently on mutated bases.
- **Bucket-reproducible, NOT bit-perfect (the honest scope):** greedy gives
  BUCKET-level reproducibility, not bit-identical trajectories (0048: pytest
  greedy runs took 9 vs 6 tool paths, both empty — residual Ollama numerical
  nondeterminism). The acceptance test is bucket-reproduction under the replay
  probe (exclude-on-flip), keyed on the **bucket**, NOT the trajectory / tool-path
  sequence. Do not claim bit-perfect determinism.
- **Greedy is a CONTROL, not the deployment config:** greedy isolates
  model-vs-model from sampling noise — correct for a RELATIVE ranking. It is NOT
  the config users deploy (they run non-greedy). A deployment-realistic RATE
  would need non-greedy multi-draw. Record this so a greedy ranking is never
  later cited as a real-world localization rate.
- **Generation params otherwise semantically identical:** temp=0 is the ONLY
  change. max_tokens=2048, reasoning_effort/explorer_think=None, the tool suite,
  and the v1 transport are unchanged and re-pinned. The 0034/0038 pins survive
  except for the single temperature field; assert the diff is exactly that. The
  in-repo half of this claim (greedy generation pins vs the 0034/0038 pinned
  values) is a unit test; the live half (greedy variant Modelfile vs the base
  tag's actually-served definition) is only honestly verifiable via live
  introspection and is a gated integration check, never a fake (see AC4a).
- **Served-tag membership is a POSITIVE, non-trivially-passing guard:** a
  re-frozen config that NAMES three brand-new external tags must be backed by a
  positive `/api/tags` membership check that the three greedy tags are actually
  served — a down/skipped endpoint must SKIP, never pass. This is the
  served-resource guardrail (an unserved named tag is an infrastructure defect,
  not a config preference); it is a distinct guard from the replay proof and
  does not depend on the replay proof running.
- **Provisioning egress rides the single sanctioned seam:** the **HTTP** read
  `/api/tags` routes `gateway.assert_local` FIRST (same loopback-gated egress
  class as 0019's `preflight_models_present`), introducing NO parallel air-gap
  check and NO new outbound path. Both `ollama create` (tag creation) and
  `ollama show --modelfile` (fingerprint read) are **local CLI subprocesses**,
  NOT HTTP — they inherit the subprocess treatment, not the `assert_local` HTTP
  seam; to keep the subprocess bound to the same local daemon, the driver
  resolves the effective Ollama host once, `assert_local`s that exact value, and
  passes it explicitly to the subprocess (`OLLAMA_HOST`) in a sanitized env
  (never letting the CLI silently pick a different daemon). No completions-Gateway
  change is implied — this is provisioning, not inference.
- **Config is the frozen `BakeoffConfig`, overrides via `dataclasses.replace`:**
  the re-frozen served config is `harpyja/eval/bakeoff_config.py`'s frozen
  `BakeoffConfig`, carrying the greedy tags on a **named** field
  (`served_variant_tags`) distinct from the logical `model_tags`; overrides are
  produced with `dataclasses.replace`, never mutation. The greedy tag set is
  drift-pinned by field-default introspection over the resolved config, never a
  source grep.
- **Hashed fingerprints are COMMITTED, live reads are CONFORMANCE:** every
  semantic fingerprint that enters the config hash is derived from the
  **committed** Modelfiles (so the hash is a pure function of in-repo data and
  the known-value drift test is a true unit test). Live `ollama show` fingerprints
  are only ever CONFORMANCE checks against those committed values (AC1's
  STOP-AND-WARN, AC4a) — a live read never feeds the hash.
- **Validated on the gated endpoint:** every live check (membership, base-diff
  introspection, replay proof) runs behind 0041's exclusivity gate; exclusivity
  is recorded in each live artifact.

## What

### 1. Modelfiles + build driver

- Commit the three greedy Modelfiles (from 0048's `serving/` staging).
- A build driver creates the three variant tags via `ollama create` (local CLI
  subprocess). **Idempotent** and **STOP-AND-WARN** if a tag already exists with
  a *different* definition, compared by a **canonical semantic fingerprint**, NOT
  raw registry bytes — a registry may expose a normalized definition, so byte
  comparison is undefined. On a fingerprint match the driver is a no-op; on a
  mismatch it warns and stops without overwriting.
- **Fingerprint grammar (deterministic, one parser):** the fingerprint reduces a
  Modelfile to `FROM` base + the `PARAMETER` set + `TEMPLATE` + `SYSTEM`, with a
  fixed canonicalization: normalize line endings, strip comments, collapse
  incidental whitespace, canonically quote/represent multiline `TEMPLATE`/`SYSTEM`
  bodies, and represent `PARAMETER`s as a **sorted key→value map** that rejects a
  Modelfile with duplicate/conflicting `PARAMETER` keys or any directive outside
  the selected set (fail loud rather than silently drop) — so any definition that
  cannot be represented losslessly by the grammar is rejected, not coerced. The
  same one parser computes both the committed fingerprint (for the hash) and the
  live fingerprint (for conformance), so they are comparable by construction.

### 2. Re-frozen served config

- Re-freeze `BakeoffConfig` (`harpyja/eval/bakeoff_config.py`) with the three
  greedy variant tags on a named frozen field `served_variant_tags`
  (`("qwen3-14b-greedy", "qwen3-8b-greedy", "qwen3.5-4b-greedy")`), distinct from
  the logical `model_tags`; overrides via `dataclasses.replace`. Add a frozen
  `served_variant_fingerprints` field holding each tag's **committed** semantic
  fingerprint (computed from the committed Modelfiles at freeze time). Recompute
  the hash via the existing `bakeoff_config_hash` shape. The hash's canonical
  inputs are pinned and enumerated: the sorted `served_variant_tags`, the
  `served_variant_fingerprints` (COMMITTED, per the invariant), the generation
  pins (`{temperature: 0, max_tokens: 2048, reasoning_effort: None}`), the
  transport id (`v1`), and the tool-suite id — all in-repo values, so the digest
  is offline-reproducible. Base tags are ABSENT from `served_variant_tags` (path
  A, not B). The **single** measurement-config consumer is the bake-off / knob /
  A-B runner's model-resolution step (the one call site that reads
  `served_variant_tags` to select what gets served); a guard asserts
  deployment/unrelated paths do not read `served_variant_tags`.

### 3. Replay-reproduction proof (fixed protocol, not narrative)

- **Tags:** all THREE greedy tags (14b/8b/4b) — 0048 only validated 14b-greedy;
  8b/4b are created fresh here and carry zero prior reproduction evidence, so the
  gate is **per-tag**, not one-tag-qualifies-all.
- **Cases:** ≥2, across ≥2 repos — the two 0048 cases (astropy, pytest) are the
  named anchors; may add more.
- **Draws:** **≥3 draws per (tag, case)** on the greedy tag (the premise is
  single-draw stochastic noise, so a 2-draw comparison is too weak). A (tag, case)
  cell **reproduces** iff all draws for that cell classify into the **identical
  bucket** under the reused 0048 replay probe's **bucket taxonomy** (probe
  IDENTITY-REUSED, not modified — no oracle change). Any within-cell bucket flip →
  `RESIDUAL_NONDETERMINISM` (naming the tag+case).
- **Probe key:** the probe keys on the **bucket**, not the trajectory / tool-path
  sequence (0048 saw 9-vs-6 tool paths in the *same* bucket — a trajectory-keyed
  probe would fail for the wrong reason).
- **Artifact:** commit a proof artifact with a pinned schema — per (tag, case):
  repo, case id, greedy tag, **the tag's committed fingerprint** (chain of
  custody: the draws are traceable to the committed Modelfile, not a stray
  registry artifact), the K bucket classifications, the reproduce/flip verdict,
  and the exclusivity-evidence fields (0041). Drift-pinned. This committed
  artifact is the **mandatory qualification record**; the live integration test
  that regenerates it is skip-not-fail (skips when the endpoint is absent, and
  the committed artifact carries acceptance).

### 4. Caveats + memory

- Record the caveat set (bucket-not-bit-perfect; control-not-deployment) in
  `findings.md` and route to memory.
- Record the greedy found-but-unsubmitted (fu) observations so the later knob
  spec has a clean greedy baseline (see OQ3).

## Acceptance criteria

Legend: [unit]=fakes; [integration]=live on the 0041-gated endpoint,
skip-not-fail (skips when the endpoint is absent — **never passes trivially**);
[doc]=recorded finding.

1. **[unit]** The greedy Modelfiles set temp=0. The build driver is idempotent
   (re-run on a fingerprint-matching tag is a no-op) and **STOP-AND-WARN** on a
   canonical-semantic-fingerprint mismatch (never overwrites), using the
   deterministic one-parser fingerprint grammar (What §1), not raw registry
   bytes.
1a. **[integration]** Live-vs-committed anchor: the existing hand-created
   `qwen3-14b-greedy:latest` (from 0048) is compared by live `ollama show`
   fingerprint against the committed Modelfile fingerprint; STOP-AND-WARN on
   divergence, and the match/mismatch is RECORDED — this is the chain-of-custody
   check that decides whether 0048's draws may anchor the proof or must be
   discarded for fresh draws (OQ1). `assert_local` on the resolved host first;
   SKIP when absent; exclusivity recorded.
2. **[unit]** Re-frozen `BakeoffConfig` carries the three greedy variant tags on
   the named `served_variant_tags` field + committed `served_variant_fingerprints`
   (overrides via `dataclasses.replace`) + a new hash whose canonical
   inputs/serialization/algorithm are the pinned set in What §2 (all in-repo, so
   the digest is offline-reproducible); base tags absent from `served_variant_tags`
   (path A, not B). Field-default introspection drift guard + a **known-value**
   hash drift test. The single measurement-config consumer (the runner's
   model-resolution step) is named and a guard asserts deployment/unrelated paths
   do not read `served_variant_tags`.
3. **[integration]** POSITIVE `/api/tags` membership check that all three greedy
   variant tags are served: `gateway.assert_local` runs FIRST, then a positive
   membership assertion per tag. Endpoint down/absent → SKIP (never a passing
   assertion). Exclusivity (0041) recorded. This guard is independent of AC5 (the
   replay proof) and does not require it to run.
4. **[unit]** The greedy generation pins diff vs the 0034/0038 pinned values is
   EXACTLY temperature (2048 cap, reasoning_effort=None, tool suite, v1 transport
   all unchanged); regression-pinned against the committed pin values.
4a. **[integration]** Live base-diff introspection: diff
   `ollama show --modelfile <greedy>` against `ollama show --modelfile <base>`
   for each of the three pairs and assert the semantic-fingerprint delta is
   EXACTLY the temperature parameter. Well-definedness: the `FROM` base must
   resolve to the identical base blob on both sides (so `FROM` is NOT part of the
   delta); the "delta" is computed over the canonical `PARAMETER` map, so a base
   that carries no explicit temperature yields an ADDED `temperature=0` entry
   (still "exactly temperature") — any OTHER added/removed/changed key fails.
   This is the only honest home for the "exactly temperature vs the served base"
   claim (a fake cannot prove a committed base snapshot equals the live base).
   Also asserts each live greedy tag conforms to its committed
   `served_variant_fingerprints` entry (live→committed conformance).
   `assert_local` on the resolved host first; SKIP when absent; exclusivity
   recorded. This is the base-diff verification the generation-params invariant
   promises (OQ1 — the recreate-from-committed-file question — is resolved
   separately in Open Questions).
5. **[integration]** Replay-reproduction proof per What §3: all three greedy tags
   × ≥2 cases / ≥2 repos, ≥3 draws per (tag, case), buckets reproduce per-cell
   under the bucket-keyed replay probe (exclude-on-flip); committed artifact with
   the pinned schema (incl. each tag's committed fingerprint) + exclusivity
   evidence; drift-pinned. The committed artifact is the mandatory record; the
   regenerating live test is skip-not-fail.
6. **[doc]** Typed outcome: `GREEDY_REPRODUCIBLE` requires **every** (tag, case)
   cell to reproduce — greedy is then the standing measurement config. **Any**
   single cell flip (any tag, any case) forces `RESIDUAL_NONDETERMINISM` globally
   (naming the offending tag+case; no per-tag cherry-pick of a
   `GREEDY_REPRODUCIBLE` subset), meaning a source beyond sampling exists and the
   bake-off stays blocked. Caveats (bucket-not-bit-perfect,
   control-not-deployment) and the greedy fu observations (OQ3) recorded in
   `findings.md` and routed to memory.

## Out of scope

- The bake-off (unblocked by this + provisioning); its own relaunch.
- Provisioning the 34 cases (the OTHER blocker, its own spec).
- The reactive/confirm knob and the thinking A/B (both become measurable on
  greedy, run later).
- Recreating/mutating base tags (path B, rejected).
- Non-greedy multi-draw (the deployment-rate variant, if ever needed).
- Any change to the completions Model Gateway, the replay probe / bucket oracle
  (IDENTITY-REUSED), the explorer, the verifier, or the tool suite.

## Open questions

1. **RESOLVED — recreate from committed file.** The build driver recreates each
   variant tag from the committed Modelfile so the registry tag's definition is
   reproducible from the repo, not a hand-created artifact; it STOP-AND-WARNs if
   the existing `qwen3-14b-greedy:latest` (hand-created in 0048) diverges by
   canonical fingerprint. Consequence for the proof (AC5): the reproduction
   anchor runs **fresh draws on the newly-created committed tag** — 0048's draws
   ran on the hand-created tag and are reused as an anchor ONLY if that tag's
   fingerprint is proven identical to the committed one; otherwise they are
   discarded in favor of fresh both-sides draws. (**AC1a** owns the live-vs-committed
   fingerprint verification and records the reuse/discard decision; AC5's artifact
   records the committed fingerprint per cell.)
2. How many cases/repos beyond the 2/2 anchor? The proof is a **GATE**, not a
   guarantee the full grid is flip-free — the replay probe carries per-run flip
   detection into the bake-off itself. 2 cases × ≥3 draws is the gate; the
   bake-off is the at-scale reproduction test.
3. Does greedy change the found-but-unsubmitted RATE (0048 saw 14b still
   found-unsubmitted on pytest even greedy — real behavior, not sampling)? Not
   this spec's question, but AC6 records the greedy fu observations so the later
   knob spec has a clean greedy baseline to compare against.
