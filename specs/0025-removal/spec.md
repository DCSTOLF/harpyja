---
id: "0025"
title: "removal"
status: closed
created: 2026-07-06
authors: [claude]
packages: [scout, eval, config]
related-specs: ["0005", "0007", "0011", "0012", "0020", "0021", "0022", "0023", "0024"]
---

# Spec 0025 — removal

FastContext removal + Scout cutover to the explorer backend.

## Why

Spec 0024 shipped `ExplorerBackend` (native grep/glob/read + `submit_citations`
loop), live-verified on Qwen3-8B, behind the unchanged `ScoutBackend` seam — but
as a **PARALLEL** factory (`build_explorer_scout_engine`) alongside the retired
FastContext factory, which was kept alive only because the eval harness still
drives the retired SUT via `agent_factory=`. That transitional two-backend state
should not persist: FastContext's upstream model was retracted and is
unobtainable (an unmaintainable dependency, independent of the localization
findings in 0020–0023), and two Scout paths is two things to keep honest. This
spec makes the explorer the sole Scout backend and removes FastContext entirely.

It must land **BEFORE** the representative-eval + model bake-off work, because
the bake-off measures models THROUGH the explorer loop — the explorer must be the
only Scout path first, or the bake-off benchmarks through a backend that isn't
the real one.

Ref: 0024 (`ExplorerBackend` + parallel factory + the deferred-cleanup note in
`tasks.md`), 0005 (`ScoutBackend` seam), 0007/0011/0012 (FastContext adapter,
`citation=False` final-answer grammar, suffix-recovery — all now dead), 0020–0023
(the finding arc justifying retirement).

### Load-bearing invariants

- **Cutover, not redesign.** No change to the explorer loop's behavior, the
  `ScoutBackend`/`Locator` boundary, the gate, matrix, or the orchestrator. This
  spec repoints callers and DELETES dead code; it does not add capability.
- **Suite stays green through cutover.** The eval instrument must still run
  end-to-end at every step — now driving the explorer instead of FastContext.
  Removal is staged so a RED never means "the harness is broken," only "a caller
  still points at the deleted path."
- **Nothing silently orphaned.** Before deleting the text-based final-answer
  grammar (0011/0012), prove the explorer's `submit_citations` path is its ONLY
  replacement and NOTHING else parses it. Same for suffix-recovery and the
  `agent_factory=` seam — grep the consumers, don't assume. The proof must be
  **executable** (an import-absence / public-name assertion that rots-false when
  a deleted symbol reappears), not a point-in-time grep pinned in prose.
- **Migrate before you delete (the sharp edge).** Two deletions would take a
  *still-needed capability* with them if done naïvely — they are migrations, not
  removals, and are the highest-risk edits in this spec:
  - **(a) The `agent_factory=` seam carries a live measurement.** It is the
    injection point the 0022 turns-used diagnostic reads through (`count_turns`
    scraping FastContext's trajectory JSONL). Note `scout_max_turns` is the loop
    *cap* (a budget), NOT the turns-*used* count — the explorer must expose a
    turns-USED reading through a public per-run seam (mirroring the tally
    side-channel's `last_tally`; create it if absent), proven equivalent to what
    the 0022 diagnostic reported, and the diagnostic repointed onto it BEFORE the
    seam is deleted. Migrate the measurement, then remove the seam — not "remove
    the dead seam."
  - **(b) `normalize.py` mixes kept and FC-only code — and the split is subtler
    than it first looked.** The explorer's citation path depends on
    `normalize_spans`, which is implemented in terms of the SHARED
    `normalize_spans_with_tally` / `ScoutTally` core — and that core is NOT
    FastContext-only: `ScoutEngine` (`engine.py`) runs *every* backend's spans
    through it, and its `last_tally` feeds live consumers (`eval/runner.py`,
    `eval/locate_probe.py`, and the spec-0022 locate-accuracy diagnostic
    `eval/locate_accuracy.py`). Only the suffix-recovery (`_recover_suffix` /
    `MIN_TAIL_SEGMENTS`, spec 0012) is genuinely FC-era, and it is embedded inside
    that shared path (gated by `file_set`). The split REMOVES only the
    suffix-recovery and KEEPS the shared tally core, proving the explorer's
    citation path still resolves without it — a disentangle, not a symbol delete.
    (Migrate before you delete, applied to the tally: ripping the whole core would
    strand the 0022 diagnostic.)
- **One canonical Scout factory.** `build_scout_engine` is the single production
  factory and constructs the explorer; `build_explorer_scout_engine` is deleted
  (OQ2 resolved — no lingering parallel path).
- **Delete the FC *model tag/env*, keep the gate config.** `FC_*` env and the
  FastContext-backend model-tag plumbing the explorer doesn't use go. `scout_model`
  is a *separate* consumer — the Verification Gate A/B baseline
  (`verify_method='scout_model'`, 0018). Its default value is itself a
  FastContext-lineage tag, but that tag is a *served* local Ollama model, so the
  baseline still resolves and works. Keep it unless independently retired; it is
  explicitly scoped OUT of the FC-removal drift guard (which targets Scout-backend
  plumbing, not the gate baseline). The removal must not take it along.

## What

- **One canonical factory (OQ2 resolved).** `build_scout_engine` becomes the
  single production Scout factory and constructs `ExplorerBackend`;
  `build_explorer_scout_engine` is deleted (its wiring folded into
  `build_scout_engine`). No lingering parallel factory.
- **Repoint the eval harness** (the one remaining FastContext-factory caller) to
  the canonical `build_scout_engine`. Verify the swebench/runner drivers produce
  citations through the explorer.
- **Migrate the turns-used diagnostic, THEN remove the seam.** Prove the
  explorer's native `scout_max_turns` count reports the same turns-used signal
  the 0022 diagnostic read through `agent_factory=` (`counting_agent_factory` /
  trajectory-JSONL scraping); repoint the diagnostic onto the native count; only
  then delete the `agent_factory=` seam. This is a capability migration, not a
  dead-seam removal.
- **Split `normalize.py` cleanly (highest-risk).** Remove ONLY the FC-era
  suffix-recovery (`_recover_suffix` / `MIN_TAIL_SEGMENTS`, spec 0012) from the
  shared normalize path; KEEP `normalize_spans`, the shared
  `normalize_spans_with_tally` / `ScoutTally` core, and `last_tally` — they are
  the live ScoutEngine shape-tally consumed by `eval/runner.py`,
  `eval/locate_probe.py`, and the spec-0022 locate-accuracy diagnostic, NOT
  FastContext-only. Prove the explorer's citation path still resolves with
  suffix-recovery gone (its submitted paths come from real tool output, so it
  never needed the 0012 prefix hack). The tally's recovered-count outputs become
  structurally zero once recovery is gone.
- **DELETE the full FastContext surface, with executable consumer-absence proof.**
  Named explicitly (no hand-waving "the adapter"):
  - the FastContext adapter/client (`fastcontext.py`, `client.py`);
  - the 0007 **env-injection apparatus**: `_SCOUT_ENV_LOCK`, `_managed_fc_env`
    (set-then-restore, unset-vs-empty preservation), `_run_coro_on_worker_thread`,
    and the Path-A→Path-B `ScoutUnavailable` state machine — all dead once the
    explorer routes through the Gateway;
  - the `citation=False` final-answer text grammar + parser (0011);
  - the FC-era suffix-recovery only (`_recover_suffix` / `MIN_TAIL_SEGMENTS`) —
    the `normalize.py` remainder above; the shared tally core is KEPT;
  - the `agent_factory=` seam (after the migration above).
- **Delete the FC model tag/env, audit-and-keep the gate config.** Remove `FC_*`
  env and FastContext model-tag plumbing the explorer doesn't use. Do NOT sweep
  `scout_model` out with it: `verify_method='scout_model'` is the Verification
  Gate A/B baseline (0018), a separate non-FC consumer — audit it and keep it
  unless independently retired.
- **Decide the eval report-schema fate.** The FC-shaped report fields —
  `fc_citation_{spanned,filelevel,dropped}_count` (0011),
  `fc_citation_recovered_{spanned,filelevel}_count` (0012), and the `ScoutTally`
  recovery side-channel (0011 AC17) — measure a backend that will no longer exist.
  Per the additive-last-with-defaults convention, **retire them to always-zero
  with a `SCHEMA_VERSION` bump** (fields stay for schema stability; the explorer
  never populates them; the bump records that the measured thing changed) — the
  honest default, adopted unless the pre-deletion audit finds a downstream
  consumer that reads them expecting non-zero (in which case remove-with-bump).
- **Drop the retracted dependency** from `pyproject.toml` + lockfile;
  re-bootstrap/verify a clean install.
- **Consolidate:** any Scout fixtures/tests that exercised FastContext output
  shapes are removed or repointed to the explorer's `submit_citations` contract.

## Acceptance criteria

Legend: `[unit]` = fakes/injected; `[integration]` = `@pytest.mark.integration`,
live, skip-not-fail; `[build]` = install/lockfile; `[doc]` = memory record.

1. **[unit]** `build_scout_engine` is the single production Scout factory and
   constructs the `ExplorerBackend`; `build_explorer_scout_engine` no longer
   exists; no code path constructs a FastContext backend; no lingering parallel
   factory.
2. **[unit]** The eval harness/runner/swebench drivers reference the canonical
   `build_scout_engine` only, with no `agent_factory=` kwarg (the `locate_probe.py`
   call site currently passes it; its removal is staged AFTER AC3's turns-migration
   lands, so repointing the factory does not break the diagnostic).
3. **[unit] — turns-diagnostic MIGRATION (load-bearing, highest-risk).**
   Turns-*used* stays measurable AFTER the cutover through a public explorer seam
   — a per-run turns-consumed reading, DISTINCT from the `scout_max_turns` *cap*
   (a budget, not a measurement); created if it does not already exist, mirroring
   the tally side-channel's `last_tally`. It is asserted equivalent to what the
   0022 diagnostic read through `agent_factory=` (`count_turns` over the
   FastContext trajectory JSONL), and the diagnostic is repointed onto the
   explorer seam and green BEFORE the `agent_factory=` seam is removed — the spec
   removes the seam without regressing the measurement.
4. **[unit] — consumer-absence guard with teeth (load-bearing).** An *executable*
   import-absence / public-name assertion (NOT a prose-pinned grep): a test fails
   if the FastContext module is importable or any deleted public name — the
   final-answer grammar/parser, suffix-recovery, FC-era tally normalization, the
   FC env-injection apparatus, `agent_factory=` — still resolves. The test rots
   false when a deleted symbol reappears.
5. **[unit] — `normalize.py` split proof (load-bearing, highest-risk).**
   `normalize_spans` AND the shared `normalize_spans_with_tally` / `ScoutTally` /
   `last_tally` core are RETAINED (they are the live ScoutEngine shape-tally, not
   FastContext-only); the explorer's citation path still resolves through them
   post-change. Only the FC-era suffix-recovery (`_recover_suffix` /
   `MIN_TAIL_SEGMENTS`, spec 0012) is removed. Two-sided proof: a **pre-delete
   consumer inventory** (a captured audit/fixture confirming suffix-recovery was
   reachable only via the FC text-ref path, and that `last_tally`'s live consumers
   — `runner`, `locate_probe`, the 0022 locate-accuracy diagnostic — keep working)
   documents the removal was safe, and a **post-delete import-absence assertion**
   (`_recover_suffix` / `MIN_TAIL_SEGMENTS` no longer resolve) prevents
   reintroduction. The tally's recovered-count outputs become structurally zero.
6. **[unit] — `scout_model` audit / cross-subsystem coupling.** `FC_*` env and the
   FastContext-backend model-tag plumbing are removed. `scout_model` — the
   Verification Gate A/B baseline (`verify_method='scout_model'`, 0018) — is
   preserved: its default is a FastContext-lineage tag, but a *served* local one,
   so the baseline still resolves; retune is a separate, out-of-scope decision.
   The drift guard reuses the existing field-default introspection pattern
   (`test_settings_defaults_drop_unserved_tags` / resolved-`Settings()` over
   `dataclasses.fields`) and asserts the property that pattern actually enforces —
   **no default names an *unserved/unobtainable* tag** — with `scout_model`
   explicitly scoped OUT of FC-removal (it is a gate consumer, not Scout-backend
   plumbing). No claim that "no default is FC-branded"; that would contradict the
   kept, served gate baseline.
7. **[unit] — eval report-schema fate.** Only the recovery-specific fields
   (`fc_citation_recovered_spanned_count`, `fc_citation_recovered_filelevel_count`)
   are retired to always-zero (suffix-recovery is gone), with a `SCHEMA_VERSION`
   bump recording the change; the shape-tally fields
   (`fc_citation_{spanned,filelevel,dropped}_count`) STAY populated — they describe
   the explorer's citation shape too, not just FastContext's. The schema stays
   versioned and NO consumer treats a field's absence/zero as an error (legacy
   blocks keep validating via the `_AGGREGATE_DEFAULTS` anti-drift convention). The
   `ScoutTally` side-channel is retained (its recovered counts read zero).
8. **[integration]** Live cutover proof: the eval instrument runs end-to-end
   driving the EXPLORER (real tool-calling model, loopback), producing citations —
   the harness works post-cutover, zero non-loopback egress. The live model is the
   general tool-calling model 0024 ran the explorer on — **Qwen3-8B on loopback
   Ollama** — NOT the retired FastContext-4B (the Q4/Q8 footprint note describes
   that *removed* model and does not characterize the explorer). The explorer's
   gateway must select that served tag explicitly (thread the model tag through the
   wiring, or the integration test pins it — the gateway's `model="local"` default
   404s on Ollama, which routes by tag); AC8 names which, so the cutover proof is
   reproducible rather than model-ambiguous.
9. **[build]** `pyproject.toml` + lockfile no longer reference the retracted
   FastContext dependency; a clean install (`uv sync` from scratch) succeeds
   without it.
10. **[doc]** Changelog/history record WHY FastContext is removed
    (retracted/unobtainable upstream + the 0020–0023 finding), closing the
    FastContext arc — not merely that it was deleted.

The load-bearing ACs are **3, 4, 5, and 8**, and the two highest-risk are **3 and
5** — both are cases where "delete the FastContext thing" would take a
still-needed capability with it: a live measurement (AC3, the turns diagnostic)
and the shared span-normalizer the explorer depends on (AC5). AC4 is the
"nothing silently orphaned" guard given executable teeth — an import-absence test
that stays true where a point-in-time grep rots. AC8 is the cutover proof — the
whole reason this precedes the bake-off is that the eval instrument must run
through the explorer, so a live end-to-end eval run confirms the cutover actually
works, not just that the old code compiles without FastContext.

## Out of scope

- The representative eval set (next).
- The model bake-off (after that).
- The Tier-0 symbol tool (staged 0024 follow-up).
- Any explorer-loop behavior change.
- OQ2/gate/threshold work.

## Open questions

1. Does removing FastContext strand any eval fixture whose ground truth or query
   format was FastContext-specific? Audit the fixtures before deleting, so the
   eval baseline survives the cutover.
2. **RESOLVED — `build_scout_engine` is canonical.** The single production Scout
   factory keeps the generic name `build_scout_engine` and constructs the
   explorer; `build_explorer_scout_engine` is deleted (its wiring folded in).
   Both reviewers landed here independently: one clearly-named factory, minimal
   caller churn, matching the `wiring.build_*` convention. Reflected in the
   invariants, What, and AC1.
3. **RESOLVED (scope widened, then corrected by recon) — extract-shared-before-
   delete, in TWO modules.** `submit.py` is tool-call-native — confirmed it imports
   only `normalize_spans`, no `citation=False` text-parsing (**checked**). The
   review surfaced the same hazard in `normalize.py`; a code trace then REFINED it:
   the tally core (`normalize_spans_with_tally` / `ScoutTally` / `last_tally`) is
   the SHARED `ScoutEngine` normalize path feeding live consumers (`runner`,
   `locate_probe`, the 0022 locate-accuracy diagnostic), NOT FastContext-only —
   only the suffix-recovery (`_recover_suffix` / `MIN_TAIL_SEGMENTS`) is FC-era.
   The conservative migration keeps the shared core and removes only the
   suffix-recovery; pinned by AC5. This corrected the initial (wrong) premise that
   the whole tally path was dead.
