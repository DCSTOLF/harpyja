---
spec: "0049-serving"
reviewers: [codex, claude-p]
quorum: 1
verdict: approve-with-comments
rounds: 2
generated: 2026-07-17T00:00:00Z
---

# Cross-model review — 0049-serving

Two review rounds. Round 1 (both `changes-requested`) drove a substantial
revision; round 2 met quorum. This file records the round-2 outcome; round-1
detail is summarized under History.

## Round 2 (current)

### codex — changes-requested

Concerns (all spec-closure / provenance, none blocking correctness):
- The single measurement-config consumer path and the concrete Settings/config
  fields carrying the tags were named only as intent, not concrete identifiers.
- The hash's fingerprint inputs didn't state committed-vs-live derivation
  (affects offline reproducibility + the known-value unit test).
- Fingerprint grammar underspecified for multiline TEMPLATE/SYSTEM, whitespace,
  duplicate PARAMETER keys, comments, out-of-set directives.
- Chain of custody: reuse of 0048 draws needs an explicit live-tag-vs-committed-file
  assertion; AC4a compares live-greedy vs live-base, not live vs committed.
- `assert_local` governing `ollama show`: if it's a CLI subprocess, the CLI
  picks its own daemon — the resolved host and subprocess env must be bound.

Guardrail violation: provisioning-egress seam for `ollama show` (bind host+env).
Convention violations: name concrete Settings fields + consumer path; drift pins
must identify canonical value + derivation.

### claude-p — approve-with-comments

"The four consensus items are genuinely closed. This is a strong revision, not a
cosmetic one." No new blocking defect. Comments (fold in inline, no re-review
cycle required):
- AC4a's "Resolves OQ1" pointer was stale (OQ1 is now the recreate decision).
- Committed-vs-live fingerprint boundary in the hash unstated (AC2 [unit] needs a
  committed fingerprint).
- Replay proof scope across the three greedy tags underspecified (8b/4b fresh,
  no reproduction evidence).
- `ollama show` framed two ways (CLI subprocess vs assert_local'd HTTP read).
- Suggestions: AC4a FROM-line resolution + base-has-no-explicit-temperature
  handling; a MIXED/partial typed outcome for AC6.

## Synthesis

**Quorum met** (claude-p `approve-with-comments` satisfies the 1-approve quorum).
Both reviewers agree the four round-1 consensus items are genuinely closed and no
new blocking defect was introduced. codex's `changes-requested` and claude-p's
comments **overlap almost entirely** — concrete naming, the committed-vs-live
fingerprint boundary, the `ollama show` egress framing, three-tag scope, the
fingerprint grammar, and the chain-of-custody assertion. These were folded in
inline (below) rather than deferred to a third round.

### Inline fixes applied (this revision)

1. **Named concrete identifiers** — `harpyja/eval/bakeoff_config.py`'s frozen
   `BakeoffConfig` gains `served_variant_tags` (the three greedy tags, distinct
   from `model_tags`) + committed `served_variant_fingerprints`; hash via the
   existing `bakeoff_config_hash` shape; single consumer = the runner's
   model-resolution step, with a guard that deployment/unrelated paths never read
   `served_variant_tags`.
2. **Committed-vs-live fingerprint boundary pinned** — hashed fingerprints derive
   from the COMMITTED Modelfiles (hash is offline-reproducible, AC2 stays a true
   [unit] known-value test); live `ollama show` reads are CONFORMANCE checks only
   (AC1a, AC4a) and never feed the hash.
3. **Deterministic fingerprint grammar** — one parser; normalizes line endings,
   strips comments, canonicalizes multiline TEMPLATE/SYSTEM, PARAMETERs as a
   sorted key→value map, rejects duplicate keys / out-of-set directives (fail
   loud, no lossy coercion).
4. **`ollama show` egress disambiguated** — it and `ollama create` are local CLI
   subprocesses (not HTTP); the driver resolves the Ollama host once,
   `assert_local`s it, and passes it explicitly via `OLLAMA_HOST` in a sanitized
   env. Only `/api/tags` is the HTTP `assert_local`-first read.
5. **Chain of custody** — new **AC1a** (live hand-created 14b-greedy vs committed
   Modelfile fingerprint, records reuse/discard decision for OQ1); AC5's artifact
   records each cell's committed fingerprint; AC4a adds live→committed conformance.
6. **Three-tag scope** — the replay proof covers all three greedy tags per (tag,
   case) cell; 8b/4b are fresh, so the gate is per-tag, not one-tag-qualifies-all.
7. **AC4a well-definedness** — `FROM` must resolve to the identical base blob
   (excluded from the delta); a base with no explicit temperature yields an ADDED
   `temperature=0` (still "exactly temperature"); any other key change fails.
8. **AC6 mixed outcome** — `GREEDY_REPRODUCIBLE` requires every cell to reproduce;
   any single flip forces `RESIDUAL_NONDETERMINISM` globally (no per-tag
   cherry-pick).
9. **AC4a OQ1 pointer fixed** — points at the base-diff/generation-params claim;
   OQ1 (recreate-from-committed-file) is resolved separately.

### Residual (non-blocking, for the planner)

- The exact `served_variant_tags` / `served_variant_fingerprints` field shapes
  and the runner call-site identifier are named at intent level; the TDD plan
  fixes the final symbols. Nothing architectural remains open.

**Action:** quorum met → spec advances to `reviewed`. Suggested next step:
`/speccraft:spec:plan`.

## History — Round 1 (both changes-requested)

Four consensus gaps drove the revision, all now closed: (1) a positive
`/api/tags` served-tag membership guard (now AC3); (2) the "exactly temperature
vs base" claim can't be a pure fake — split into AC4 [unit pin-vs-pin] + AC4a
[gated live introspection]; (3) the replay proof needed a fixed protocol (What
§3: ≥2 cases/≥2 repos, ≥3 draws/cell, pinned artifact schema, mandatory-committed
vs skip-not-fail-live); (4) the probe must key on BUCKET not trajectory. Plus
single-agent items (Model Gateway boundary, Settings/`dataclasses.replace`
traceability, hash construction, draw-provenance) — all addressed in revision 2.
