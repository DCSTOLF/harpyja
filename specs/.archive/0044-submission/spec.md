---
id: "0044"
title: "submission"
status: closed
started_at_sha: 9e971b3289c486bf6fda5b3186845e5e3203fc8c
created: 2026-07-12
---

# Spec 0044 — submission

Confidence-conditioned submission — submit early ONLY on a confident span.

## Why

0043's unconditional submit-early nudge typed `CLOCK_BOUND_PERSISTS` with a precisely-named residual: it fixes dawdle-after-locate but induces submit-before-verify. Net bucket movement was −1 (2 conversions vs 3 regressions) — the frozen bidirectional predicate caught what "found-but-unsubmitted 6→2" alone would have sold as a win.

The lever's sign is MODEL-DEPENDENT: 14b benefits (fu 2→0, marquee astropy finally submits, requests-1766 empty→correct) but reshapes 6/11 cells and loses flask; 8b pays most (two correct→worse regressions, a new wrong-file submit — it was USING that time to verify, and the nudge took it away); 4b is inert (its problem is tool-output-byte/prefill cost, not dawdling — the named inversion).

So the fix is NOT "nudge less" — it is to condition the nudge on EVIDENCE: submit early only when a confident span is already in hand, preserving 8b's verification while rescuing 14b's located-but-dawdling cells.

Ref: 0043 (the lever table, the bidirectional predicate, found-but-unsubmitted as a first-class artifact fact, the 4b larger-tool-outputs inversion), 0042 (symbols adoption — symbols-derived spans are the strongest confidence signal available), 0041 (exclusive-endpoint gate — required for clean re-measurement).

### Invariants

- **Bidirectional predicate, FROZEN BEFORE ANY NUMBER**: conversions AND regressions counted, NET surfaced. 0043 proved this is what stops an overclaim; this spec has the identical risk profile (it WILL show conversions; the regressions decide whether it ships). The predicate, thresholds, baseline identity, and config hash freeze before the live spend (the 0043 two-stage pattern: choosing rules frozen in this spec BEFORE implementation; config hashed and committed after the SUT lands, BEFORE any live call).
- **Condition on evidence, not on the clock**: the nudge fires only when the trajectory contains a span meeting the pre-registered confidence definition (§Confidence gate). A turn-count/time-based trigger is what 0043 already tried and it induced submit-before-verify. If the confidence test is unmet, the model keeps exploring — the pre-0043 behavior.
- **Per-model sign is expected — report it**: the 0043 lever helped 14b, hurt 8b, was inert for 4b. Report per-model net, not just aggregate. An aggregate win that hides an 8b regression is not a ship. The per-model expected readings (§Pre-registered readings) are DATA in the frozen config, not close-time prose.
- **Measure on the 0041-gated endpoint**: exclusivity proof in every artifact; SUT hash pinned (post-0044 surface); params byte-identical (the 0034/0038 `explorer_think=None ⇒ params == {max_tokens: 2048}` pin must survive verbatim); endpoint evicted-before / re-pinned-after.
- **The confidence predicate is GOLD-BLIND by construction**: it is SUT code, lives in `scout/`, and sees only the trajectory — gold exists only in `eval/`. The postflight "fired-on-wrong-span" attribution DOES need gold and must reuse `metrics.span_hit_kind` BY IDENTITY (one-oracle-reuse) — never a second overlap definition.

## What

### Comparison baseline (frozen)

BEFORE = the committed 0040/0042 pre-nudge ledger — the same axis 0043 was read on. This keeps 0043 and 0044 on ONE comparison axis and gives fu_before = 6 (14b 2 / 8b 1 / 4b 3), clearing the 0043 power floor `min_before_found_unsubmitted = 3`. NOT the shipped 0043 SUT (fu_before would be 2, under the floor, making the drop conjunct structurally vacuous). The baseline ledger identity (path + hash) is a field of the frozen config.

Consequence: the ONE SUT delta of this spec, measured against that baseline, is **(i) REMOVE the shipped 0043 unconditional submit-early sentence from `build_initial_prompt`, and (ii) ADD the conditioned mid-loop nudge** (§Nudge mechanism). Both parts are one delta; the comparison is two-armed (pre-nudge baseline vs conditioned-nudge SUT), never silently three-armed.

### Confidence gate (pre-registered — decided NOW, not "before the run")

The gate is **signal (a) SOLELY: a symbols-derived exact span**, with the qualifying projection frozen EXACTLY (not "any successful symbols result" — post-0042, `symbols` can return a degraded ANNOTATION shape or a repo-wide name-lookup batch of up to `scout_symbols_repo_max_entries=200` candidates, and "a span exists in the trajectory" is much weaker than "a confident span is in hand"). A `symbols` tool result QUALIFIES iff ALL of:

- **clean** — no 0035 marker of either shape (a degraded ANNOTATION `[marker, *CodeSpans]` or REPLACEMENT result never qualifies);
- **bounded** — it carries between 1 and `max_qualifying_spans = 5` spans (frozen config field): an exact-definition lookup is confidence, a multi-hundred-entry substring batch is a candidate list and firing on it would reintroduce submit-before-verify through the gate itself;
- **exact-span-shaped** — every carried span has explicit start/end lines (citation-shaped by construction; 0042 showed this precise and adopted, 24/31).

File-local (`path`-scoped) and repo-wide (`name`-only) calls both qualify under the same three conditions — the span-count bound is what excludes the repo-wide blast radius. This scoping is DELIBERATE and pre-registered; the fired-on-wrong-span attribution is the measured cost of any remaining looseness. The gate fires on the FIRST qualifying result. This is the only signal that is mechanically crisp today, and a single gating definition is all that SUT-frozen-per-run admits.

Known, accepted risk (codex round 2): the symbols-only gate may be too NARROW if 14b's located-but-unsubmitted spans came from grep/read_span rather than symbols — this is not a spec change; it is exactly what the `NEVER_FIRES` branch and the attributable-null artifact exist to surface, and the record-only fields feed the next spec's gate choice.

The other candidate signals are demoted to RECORD-ONLY observability fields — computed EVAL-SIDE POSTFLIGHT over the persisted trajectory (never in the loop: this keeps the SUT delta to predicate + injection only, strengthening the byte-pin story), NEVER gating, exact projections defined in code and fixture-pinned:

- (b) grep-hit-inside-symbol-span: a grep result line lying within some previously-returned symbols span (span containment by line interval, same file — exact code definition pinned by fixture);
- (c) convergent evidence: ≥2 distinct tools returned spans on the same file whose line intervals overlap (overlap = non-empty intersection — exact code definition pinned by fixture).

Signal (d) model self-assessment is DROPPED entirely (round-2 fold): it had no pinnable extraction rule ("trivially extractable" is prose, and an unpinned field cannot feed the next spec's gate choice, which was its only purpose), and a 4B/8B's confidence is poorly calibrated anyway.

These record-only fields exist so the NEXT spec can choose a better gate from measured data instead of intuition.

### Nudge mechanism (mid-loop injection — a NAMED seam, not "0043's mechanism")

0043's mechanism was a static sentence in `build_initial_prompt`; an evidence-conditioned nudge cannot ride turn 0 because the evidence does not exist yet. The mechanism here is **mid-loop message injection**: after each COMPLETED tool-result batch — never between an assistant `tool_calls` message and its N tool responses, which is the malformed-conversation class 0029 fixed (answer-all-N in emitted order) — the (gold-blind) confidence predicate inspects the trajectory; on its FIRST pass, the loop appends ONE bounded, model-visible nudge message with `role: user`, AFTER the batch's final tool message and BEFORE the next model call. It fires at most once per case; there is NO turn-count or wall-clock fallback.

The nudge text is SUT surface exactly as the 0043 sentence was — its EXACT template is a field of the frozen config and is test-pinned, including the multi-span wording (a qualifying result may carry up to `max_qualifying_spans` spans; the message must name the evidence without implying a single certain target — e.g. "your symbols result contains the exact span(s) {spans}; if one answers the query, submit it now via submit_citations" — so the implementation cannot drift into arbitrary first-span steering).

This is a loop-behavior SUT delta and it interacts with three pieces of load-bearing machinery, each of which gets its own pin:

- **Truncation**: the injected nudge must survive `scout_history_char_cap` truncation (never silently dropped, never displacing citable observations);
- **Loop detection**: the injection must not perturb the no-new-span/repeat accounting (it is not a tool result and registers no spans);
- **Turn accounting**: the injected message is not a model turn and must not distort `per_turn` or turn-cap arithmetic.

The delta rides `messages` ONLY. The 0034/0038 params byte-pin and the 0042 prompt↔surface drift guard must stay green (`test_params_pin_survives_*` successor test named in the plan).

### Verdict machinery (total, pure, frozen)

`PREREGISTERED_SUBMISSION_CONFIG_0044` — a frozen, hashed config committed BEFORE any live call, carrying: baseline ledger identity (path + per-source hash), post-lever SUT hash, detector version, the gate definition (= signal (a) with its exact projection: clean, `max_qualifying_spans = 5`, exact-span-shaped), the nudge message template (exact text + role), the record-only field definitions, the power floors (reused from 0043: `min_covered_before_cells = 8`, `min_before_found_unsubmitted = 3`), the NEVER_FIRES threshold as a NUMERIC field (`never_fires_max_14b_firings = 0` — the label triggers iff 14b firings ≤ this value; data, not prose), and the pre-registered per-model readings (below).

`decide_submission_outcome` — a TOTAL PURE function over per-model (net, firing-rate) tuples, aggregate net, conversions, fu_before/fu_after, and live coverage, with a FROZEN TOTAL ORDER over the (overlapping, non-partition) outcome conditions and a grid-totality test (the 0020/0023 discipline). All true conditions are recorded in the artifact; the precedence picks the label. Every input returns an enum member — power failure is never close-time prose (the 0043 `UNDER_POWERED` discipline), and the floors the config carries are CONSUMED by a branch, never dormant. Precedence (first match wins):

1. `UNDER_POWERED` — live covered BEFORE-subset cells < `min_covered_before_cells` (8). The fu floor (`min_before_found_unsubmitted = 3`) is cleared statically by fu_before = 6 on the frozen baseline, but is re-checked here as a guard against a baseline-identity error.
2. `NEVER_FIRES` — 14b firings ≤ `never_fires_max_14b_firings` (= 0; the model pre-registered as the intended beneficiary). Keyed to 14b ONLY: an 8b zero-firing rate does NOT trigger this label (see readings). Report all per-model firing rates alongside.
3. `STILL_TRADES_OFF` — any model's net is negative, OR aggregate net < 0. Name the residual.
4. `NUDGE_INERT` — the nudge fired but bought nothing: conversions = 0 AND fu_after ≥ fu_before. Fired-but-ignored is one of this spec's own named null shapes and must be distinguishable at the VERDICT level, not only in per-case artifact fields — without this label (or the benefit conjunct below) a do-nothing mechanism would type as a ship at net = 0.
5. `CONDITIONED_NUDGE_SHIPS` — aggregate net ≥ 0 AND no model net-negative AND a BENEFIT conjunct holds (conversions ≥ 1 OR fu_after < fu_before) — the 0043 predicate was two-conjunct (drop AND net) and this spec keeps both sides: the regressions decide the ship, the benefit conjunct proves there is something being shipped.

### Pre-registered readings (DATA in the frozen config, not close-time argument)

- **8b**: its dawdle IS verification, and its SUCCESS CRITERION is regressions = 0 at ANY firing rate. Two success shapes are pre-registered: 8b firing HIGH with regressions = 0 (the conditioned nudge is safe where the unconditional one was not — the EXPECTED shape, since 8b had the highest 0042 symbols adoption, 10/11, so the gate will likely fire often on it), and 8b firing low/zero with regressions = 0 (the gate never disturbs it). Neither is instrument failure; 8b's regressions are the ship/no-ship signal.
- **4b**: expected INERT (its constraint is tool-output-byte/prefill cost, not dawdling — the 0043 named inversion). An unmoved 4b is consistent-with-expectation, not a gate failure; its lever is the future compression spec.
- **14b**: the intended beneficiary (its 0043 failure mode was dawdle-after-locate). NEVER_FIRES is keyed to 14b for exactly this reason.

### Artifact

Per case: confidence-fired (bool), triggering signal, firing turn, the record-only observability fields ((b)/(c), eval-side postflight), and (postflight, eval-side) the fired-on-wrong-span attribution via `metrics.span_hit_kind` BY IDENTITY — so a null result is attributable: never-fired / fired-but-ignored / fired-on-wrong-span. Additive schema bump `VERIFIER_SCHEMA_VERSION 0043/1 → 0044/1`, threaded through BOTH verifier seams — `build_trajectory_record` AND `run_verified_case`'s hand-assembled written artifact — pinned by a written-JSON test; legacy versions validate unchanged (the 0033/0034/0038 dual-seam checklist; this is its fourth application, named here so it is not missed a fourth time).

## Acceptance criteria

Test-tier convention: [unit] = fakes, no endpoint. [integration] = live on the 0041-gated endpoint; integration TESTS are skip-not-fail (opt-in by default per 0041), but the deliverable-producing live RUN goes through a STOP-AND-WARN resumable operator driver (typed non-zero exit on infra failure, resumable ledger — the 0042/0043 driver posture), never a silently-skipping test.

1. [unit] Confidence predicate implemented per the pre-registered projection (gate = symbols-derived exact span SOLELY: clean, 1–`max_qualifying_spans` spans, exact-span-shaped); gold-blind by construction (lives in `scout/`, sees only the trajectory); fixture-pinned on ALL edges: qualifying span present → nudge fires once; grep-only/ambiguous evidence → no nudge; degraded ANNOTATION/REPLACEMENT symbols result → no fire; over-bound repo-wide batch (> `max_qualifying_spans` spans) → no fire; a multi-span qualifying result (`symbols(name=…)` returning several exact spans) → fires, with the injected message's multi-span wording asserted.
2. [unit] The nudge is EVIDENCE-gated, not turn/time-gated — a run with many turns but no confident span receives NO nudge (the 0043 failure mode is structurally impossible); fires at most once per case.
3. [unit] Mid-loop injection seam pinned: the injected message rides `messages` only and the 0043 unconditional sentence is REMOVED (both asserted); injection lands ONLY at a completed tool-result batch boundary — after the batch's final tool message, before the next model call, never interleaved inside an answer-all-N batch (the 0029 protocol pin) — with `role: user` and the EXACT frozen-config template (test-pinned, incl. multi-span wording); the nudge survives `scout_history_char_cap` truncation; injection does not perturb loop-detection/no-new-span accounting; injection is not a model turn (turn accounting unchanged); the 0034/0038 params byte-pin and the 0042 prompt↔surface drift guard stay green.
4. [unit] Artifact records confidence-fired (bool), triggering signal, firing turn, and the record-only observability fields (b)/(c) (computed eval-side postflight; signal (d) dropped); additive schema bump `VERIFIER_SCHEMA_VERSION 0043/1 → 0044/1` threaded through BOTH seams (`build_trajectory_record` + `run_verified_case`), pinned by a written-JSON test; legacy versions validate unchanged; a null is attributable (never-fired / fired-but-ignored / fired-on-wrong-span), with wrong-span attribution reusing `metrics.span_hit_kind` BY IDENTITY.
5. [unit] `PREREGISTERED_SUBMISSION_CONFIG_0044` frozen + hashed, carrying baseline ledger identity, SUT hash, detector version, gate projection (incl. `max_qualifying_spans`), nudge message template (text + role), record-only definitions, power floors, `never_fires_max_14b_firings = 0`, and the pre-registered per-model readings; `decide_submission_outcome` is a total pure function over per-model (net, firing-rate), aggregate net, conversions, fu_before/fu_after, and live coverage, returning one of the FIVE enum members (UNDER_POWERED / NEVER_FIRES / STILL_TRADES_OFF / NUDGE_INERT / CONDITIONED_NUDGE_SHIPS) per the frozen precedence, with a grid-totality test proving every input types — the power floors are CONSUMED by the UNDER_POWERED branch, never dormant config; committed BEFORE any live call.
6. [integration] Re-measure the 0043 pilot cells on the gated endpoint via the STOP-AND-WARN resumable driver (SUT hash verified at startup, exclusivity proof in every artifact): report per-model conversions, regressions, NET, firing rate, and found-but-unsubmitted before/after — BEFORE = the committed 0040/0042 ledger. 8b's regressions are the ship/no-ship signal.
7. [integration] Specifically re-check the 0043 casualties: flask-5014 (14b + 8b) and django-14315::8b (correct→worse under the unconditional nudge) — do they hold correct under the conditioned nudge?
8. [doc] Typed outcome via `decide_submission_outcome`: UNDER_POWERED / NEVER_FIRES / STILL_TRADES_OFF / NUDGE_INERT / CONDITIONED_NUDGE_SHIPS per the frozen precedence, all true conditions recorded, per-model firing rates reported. Pilot-N signal, not an inferential claim.

## Out of scope

- Tool-result COMPRESSION for 4b prefill cost (named future spec — compression, NOT truncation: positional cutoff would discard relevant hits, the found-then-dropped class)
- Choosing a better/composite confidence gate from the record-only fields (that is the NEXT spec's job, fed by this spec's observability data)
- Pool enlargement
- The bake-off
- The 0039 thinking A/B
- Any model swap
- The semantic tier

## Open questions

_none — the round-1 open questions are resolved into the spec body: OQ1 (gate = symbols-derived span solely, others record-only), OQ2 (8b zero-firing pre-registered as a success reading, keyed into the NEVER_FIRES definition), OQ3 (4b inert pre-registered as consistent-with-expectation)._
