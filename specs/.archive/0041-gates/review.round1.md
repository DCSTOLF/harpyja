---
spec: "0041-gates"
reviewers: [codex, claude-p]
quorum: 1 (approve or approve-with-comments)
verdict: changes-requested
generated: 2026-07-11T00:00:00Z
---

# Cross-model review — 0041-gates

**Quorum status: NOT MET.** Both agents returned `changes-requested`. Per the quorum config (1 approve or approve-with-comments required), the spec does NOT clear review and stays at `status: draft`. No mechanical re-review is warranted until the checklist below is addressed.

## codex

**Verdict:** changes-requested

Concerns:
- The exclusivity gate is underspecified: a one-time `/api/ps` check for foreign residents at start does not prove endpoint exclusivity for the run's full duration, nor does it detect a competing process that starts immediately after preflight.
- The artifact proof is too weak as written: recording only the start-check result + timestamp cannot substantiate the invariant that the endpoint was exclusive when the run executed (start-time proof labeled as run-duration proof).
- `keep_alive` is not scoped precisely enough — the spec must name which model-call paths get the bounded value, how it's passed on the Ollama `/v1` transport, and how it avoids leaking an explorer/eval hygiene knob into unrelated Deep/runtime paths.
- The validator/schema target is vague: "run artifact" and "schema bump" don't name the exact artifact(s), accepted legacy versions, or whether this is a verifier artifact, pilot ledger, pool fork, or a new measurement-run schema.
- Default live-test deselection is directionally correct, but the opt-in path needs a CI/operator story so live tests don't become permanently unexercised.

Suggestions:
- Define exclusivity as start-gate plus either an owner lease/lock or repeated per-block `/api/ps` checks; record each check in the artifact.
- Record enough proof to audit the whole run: endpoint URL, allowed resident model set, foreign residents, timestamps, re-check outcomes; reject on any unapproved resident or failed check.
- Make `keep_alive` an explicit eval/live-driver setting or per-call parameter at the caller seam, with a unit guard that Deep outbound requests don't acquire it unless intentionally scoped.
- Replace STOP-AND-WARN with a stable typed stop identifier (e.g. `exclusive-endpoint-contended`), retaining the human-readable message.
- Add acceptance coverage for the race case: endpoint clean at start, foreign resident appears before the next block, driver stops before more cells run and records the contamination boundary.

Guardrail violations: none.

Convention violations:
- Spec frontmatter should use the canonical schema (id, title, status, started_at_sha, created) and nothing else — missing `started_at_sha`; includes non-canonical keys `authors`, `packages`, `related-specs`. (Codex flagged this may be stale/aspirational since specs 0038–0040 also carry these keys.)

## claude-p

**Verdict:** changes-requested

Concerns:
- `keep_alive` honoring is assumed, not probed: AC3 asserts the bounded `keep_alive` "on the outbound request," but 0037 proved this exact Ollama `/v1` compat layer silently DROPS unrecognized request fields (top-level `think`). Sent ≠ honored — an outbound-request assertion can go green while the server still pins the model forever.
- SUT-boundary tension: adding `keep_alive` to model calls changes the production outbound request body, colliding with the pinned 0034/0038 invariant `explorer_think=None ⇒ params == {max_tokens: 2048}` (byte-identical request). The spec declares "no behavior change to the SUT" but doesn't name the seam (ModelGateway default vs explorer param vs driver/eval-side) or reconcile the pin supersession.
- Keep-alive "at the source" doesn't cover all sources: Deep's RlmBackend owns its own LM and never goes through `complete_with_tools`; live integration tests touch other tags — those calls still pin models under the dev host's `keep_alive=-1`. The residual gap should be named.
- AC2 contradicts the version-gated legacy-compat convention as written: an unconditional reject would invalidate every 0031/1–0038/1 artifact. AC2 never names WHICH artifact/schema (per-case verifier vs run-level ledger) — exclusivity is a run-level fact, but the verifier artifact is per-case.
- The exclusivity invariant overclaims: a start-gate `/api/ps` check proves exclusive-at-check-time, not run-duration exclusivity — recording it as the latter is a false-capability label.
- "Foreign resident" is undefined relative to the run's own model set: the driver itself loads models block-by-block, so mid-run `/api/ps` legitimately shows tags the run owns. Pin the predicate (foreign = not in frozen config's model set) or the per-block re-check self-triggers.
- Bounded `keep_alive` trades pinning for reload churn on a stack where per-case timeout sensitivity is already the binding constraint (0040: 240s wall / 300s HTTP, prefill-heavy 4b). Too-short converts memory-squeeze into timeout failure. Deserves an AC-level check (no new timeout degrades attributable to reload).

Suggestions:
- Probe-first (0038 discipline): before wiring, commit a typed-outcome keep-alive probe — one call with bounded `keep_alive`, then read `/api/ps` `expires_at` — as a spec-local schema-versioned artifact; make AC3 conditional on the recorded outcome. If `/v1` drops the param, enumerate the branches now (native `/api/chat` or post-run explicit eviction).
- Resolve AC2 with the existing 0026/0036 version-gated strict pattern: bump the schema, REQUIRE the exclusivity field on the new version only, legacy versions keep validating; name the target artifact explicitly. If it rides the per-case verifier artifact, apply the dual-seam checklist (`build_trajectory_record` AND `run_verified_case`'s hand-assembled written JSON, pinned by a written-JSON test).
- Label the exclusivity record by epistemic kind (the 0039/0040 two-quantity discipline): `exclusivity_check_kind: start-gate` vs `start-plus-per-block`, so OQ1's strengthening lands as a recorded upgrade, not a silent relabel.
- Route the `/api/ps` check behind `gateway.assert_local` FIRST (the 0019 preflight rule — same loopback-gated egress class as `/api/tags`); state it in the What.
- For OQ3, don't stop at documentation: make the operator drivers' preflight assert the opt-in flag was passed (or run the live tests through `require_live_stack`), so the live suite has a named executable consumer and cannot rot silently.
- AC1's "no bypass parameter (asserted)" has precedent — pin it the way 0039 pinned `run_ab_paired` (signature introspection); state the only sanctioned unblock is changing the environment.

Guardrail violations: none.

Convention violations:
- Spec frontmatter canonical schema — missing `started_at_sha`; includes non-canonical `authors`/`packages`/`related-specs`.
- "Proving a control knob works is a behavior-level claim — never assert only on the request/response FIELD (sent ≠ honored; the 0037 lesson)." Location: AC3.
- "Version-gated schema validation — new required field enforced on the NEW version only." Location: AC2.

## Synthesis

**Both agents converge on the same core diagnosis**, arriving independently at nearly identical findings — a strong signal:

1. **The exclusivity proof overclaims.** Both agents flag that a one-time start-gate `/api/ps` check cannot prove run-duration exclusivity, yet the spec's invariant language ("Exclusivity is RECORDED... proof the endpoint was exclusive when the run executed") implies the stronger, unproven claim. Both independently propose the same fix direction: start-gate plus per-block re-check (or lease/lock), with the check's strength recorded explicitly rather than silently upgraded or overstated (claude-p frames this as an "epistemic labeling" requirement; codex frames it as a race-condition gap in AC coverage).

2. **"Foreign resident" / artifact target are underspecified.** Both flag that the spec doesn't pin down which artifact schema is being bumped (codex: "vague... doesn't name the exact artifact(s)"; claude-p: "AC2 never names WHICH artifact/schema — per-case verifier vs run-level ledger"), and claude-p additionally notes the driver's own block-by-block model loading means "foreign" needs a precise predicate (not in the frozen config's model set) or the re-check self-triggers false positives.

3. **`keep_alive` scoping/seam is unresolved.** Both agents independently insist the spec name the exact call-site seam where `keep_alive` is applied (codex: driver/eval-side param, guard against Deep/runtime leakage; claude-p: same concern, plus the sharper point that this seam collides with the pinned 0034/0038 byte-identical-request invariant for `explorer_think=None`, and that Deep's RlmBackend and live-test call sites are structurally outside "at the source" as scoped).

4. **Deselect-default needs an enforced opt-in consumer**, not just documentation (both agents, independently — codex: "CI/operator story"; claude-p: concrete mechanism via `require_live_stack` or preflight assertion), so OQ3's stated risk doesn't quietly materialize.

5. **Frontmatter convention violation** — both agents flag the same missing `started_at_sha` / non-canonical keys, though codex notes this may be a repo-wide drift already present in 0038–0040 rather than specific to this spec.

**Unique/divergent findings, not raised by the other agent:**

- claude-p's headline finding — **sent ≠ honored** for `keep_alive` — is the sharpest and most load-bearing addition: the spec's own AC3 asserts only on the outbound request field, which is exactly the failure pattern the repo already learned from 0037 (dropped `think` field on the same `/v1` compat layer). Codex did not raise this specific risk. This deserves priority treatment since it could let AC3 go green while the underlying defect (pinned models) persists unfixed.
- claude-p's SUT-boundary collision with the pinned 0034/0038 byte-identical-request invariant is a concrete, named conflict with existing pinned behavior — not raised by codex, and probably the single most concrete blocking issue since it implicates a previously-frozen invariant.
- claude-p's reload-churn / timeout-sensitivity concern (too-short `keep_alive` converts a memory-squeeze failure into a timeout failure on an already timeout-sensitive stack) is a novel risk not raised by codex, tied to 0040's specific timeout constants.
- claude-p's `gateway.assert_local` routing requirement for the `/api/ps` check (tying it to the existing 0019 preflight/loopback-egress convention) is a specific implementation-conformance point codex did not raise.
- codex's suggestion for a stable typed stop identifier (vs. the spec's "STOP-AND-WARN" phrasing, which claude-p separately flagged as awkward under the "refuse, don't warn" invariant) is a smaller, complementary naming/precision point unique to codex, though both agents converge on discomfort with the current phrasing from different angles.

No disagreements were found between the two agents on substance — where their concerns overlap, they reinforce rather than contradict.

## Merged and deduplicated suggestions

1. **Probe before wiring `keep_alive`.** Commit a typed-outcome probe (one call with bounded `keep_alive`, then read `/api/ps expires_at`) as a spec-local schema-versioned artifact; make AC3 conditional on the recorded outcome. If the `/v1` compat layer drops the field (as it did for `think` in 0037), enumerate fallback branches now (native `/api/chat`, or explicit post-run eviction).
2. **Name and pin the `keep_alive` seam explicitly.** State whether it's a ModelGateway default, an explorer/live-driver param, or a driver/eval-side wrapper. Reconcile explicitly with the pinned `explorer_think=None ⇒ params == {max_tokens: 2048}` byte-identical-request invariant from 0034/0038 — either scope `keep_alive` outside that pinned path or supersede the pin with a stated rationale. Add a unit guard that Deep/RlmBackend and unrelated runtime paths do not silently acquire the bounded value. Name the residual gap (Deep's own LM, live-test call sites) rather than leaving it implicit.
3. **Strengthen and label the exclusivity check.** Define exclusivity as start-gate plus either an owner lease/lock or per-block `/api/ps` re-checks; record each check (not just the first) with timestamps and outcomes. Add an explicit `exclusivity_check_kind` (or equivalent) field so the check's actual strength is recorded rather than overclaimed. Pin the "foreign resident" predicate as "not in the frozen run config's model set" to avoid the driver's own block-loaded models self-triggering false positives. Add acceptance coverage for the race case (clean at start, contended before next block → mid-run stop with recorded contamination boundary).
4. **Name the target artifact/schema precisely and apply version-gating.** State exactly which artifact is being schema-bumped (per-case verifier artifact vs. run-level ledger vs. new measurement-run schema) and apply the existing version-gated pattern (0026/0036): new field REQUIRED only on the new version, legacy artifacts still validate under their prior version. If it's the per-case verifier artifact, apply the dual-seam checklist (`build_trajectory_record` and `run_verified_case`'s hand-assembled JSON), pinned by a written-JSON test.
5. **Route the `/api/ps` preflight check through `gateway.assert_local`** (per the 0019 loopback-gated-egress convention), and state this explicitly in the What section.
6. **Give the deselect-default an enforced consumer.** Beyond documenting the opt-in flag, make operator/CI drivers assert the flag was passed (or route live tests through `require_live_stack`) so the live suite has a named, executable consumer and cannot silently rot.
7. **Add an AC-level check for reload-churn regressions**: bounded `keep_alive` must not introduce new timeout degrades attributable to model reload, given 0040's tight timeout budget (240s wall / 300s HTTP) on prefill-heavy cells.
8. **Replace "STOP-AND-WARN" with precise, stable phrasing** consistent with the "refuse, don't warn" invariant — e.g. a typed stop identifier (`exclusive-endpoint-contended`) plus a human-readable message, dropping "WARN" from the label.
9. **Pin AC1's "no bypass parameter" claim mechanically** (signature introspection, per the 0039 `run_ab_paired` precedent) and state the only sanctioned unblock is changing the environment.
10. **Fix or confirm frontmatter canonical schema** — add `started_at_sha`; either drop `authors`/`packages`/`related-specs` or confirm (and document) that these are now an accepted extension of the canonical schema, since 0038–0040 carry the same fields.

## Convention violations (surfaced regardless of quorum)

- **Frontmatter canonical schema** (both agents): missing `started_at_sha`; non-canonical keys `authors`, `packages`, `related-specs` present. Possibly a repo-wide drift rather than spec-specific — worth a one-time decision (fix this spec, or update the canonical-schema convention to reflect actual practice across 0038–0041).
- **Sent ≠ honored** (claude-p): AC3 asserts a behavior-level claim (`keep_alive` bounded) only on the outbound request field, not on server-observed honoring — the exact 0037 lesson applied to this spec's own control knob.
- **Version-gated schema validation** (claude-p): AC2's "validator rejects" language is written as an unconditional reject, which would invalidate all pre-existing 0031–0038 artifacts; the version-gated pattern (new field required on new version only) is not applied as written.

No guardrail violations were reported by either agent.

**Action:** Revise the spec before any re-review. Priority order: (1) resolve the `keep_alive` seam and reconcile it with the pinned 0034/0038 byte-identical-request invariant, since this is a genuine collision with existing pinned behavior; (2) commit to a probe-first plan for `keep_alive` honoring (sent vs. honored) rather than asserting only on the outbound request; (3) precisely define and name the exclusivity check's strength, predicate, and target artifact/schema with version-gating; (4) give the deselect-default an enforced, named consumer; (5) fix the frontmatter and STOP-AND-WARN phrasing as lower-priority precision items. Because quorum is not met, the spec stays at `status: draft` — do not proceed to implementation until a revised spec clears at least one approve/approve-with-comments verdict.

## Changes required before re-review (checklist)

- [ ] Name the exact `keep_alive` seam (ModelGateway default / explorer param / driver-eval-side) and reconcile with the pinned `explorer_think=None ⇒ params == {max_tokens: 2048}` invariant (0034/0038)
- [ ] Add a probe step (single call + `/api/ps expires_at` read) establishing whether the Ollama `/v1` transport honors `keep_alive`, with enumerated fallback branches if it does not; make AC3 conditional on this outcome
- [ ] Guard against `keep_alive` leaking into Deep/RlmBackend or other unrelated call paths; explicitly name any residual uncovered sources (Deep's own LM, live-test call sites)
- [ ] Strengthen exclusivity to start-gate + per-block re-check (or lease/lock); record every check, not just the first
- [ ] Add an `exclusivity_check_kind` (or equivalent) field so the check's actual strength is recorded, not overclaimed as run-duration proof
- [ ] Pin the "foreign resident" predicate precisely (not in the frozen run config's model set)
- [ ] Add acceptance coverage for the mid-run contention race case
- [ ] Name the exact target artifact/schema for the exclusivity-proof bump and apply the version-gated (new-version-only-required) validation pattern instead of an unconditional reject
- [ ] Route the `/api/ps` preflight check through `gateway.assert_local`
- [ ] Give the live-test opt-in an enforced, executable consumer in operator/CI drivers (not documentation-only)
- [ ] Add an AC-level check that bounded `keep_alive` does not introduce new timeout degrades via reload churn
- [ ] Replace "STOP-AND-WARN" with a stable typed stop identifier consistent with "refuse, don't warn"
- [ ] Pin AC1's "no bypass parameter" claim via signature introspection (0039 precedent)
- [ ] Resolve frontmatter: add `started_at_sha`; reconcile `authors`/`packages`/`related-specs` against the canonical-schema convention (fix here, or update the convention to match 0038–0041 practice)
