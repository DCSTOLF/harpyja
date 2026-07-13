---
spec: "0044"
round: 2
date: 2026-07-12
reviewers: [codex, claude-p]
verdicts:
  round1:
    codex: changes-requested
    claude-p: changes-requested
  round2:
    codex: approve-with-comments
    claude-p: changes-requested
quorum: 1
quorum-met: true
outcome: reviewed
generated: 2026-07-12T00:00:00Z
---

# Cross-model review — 0044-submission

Quorum rule: 1 `approve` or `approve-with-comments` required. Both reviewers returned
`changes-requested` — quorum is **not met**. The spec stays at `status: draft`.

## codex

**Verdict:** changes-requested

Concerns:
- The core confidence gate is not actually specified yet. The spec lists candidate signals and says "pick before the run," but should name the exact pre-registered definition, precedence, thresholds, and hashable config shape before implementation/live spend.
- The nudge mechanism is underspecified. 0043's nudge was an initial-prompt message; a conditioned nudge requires a runtime injection seam or a different prompt contract. Calling the mechanism "unchanged" is not precise enough to preserve the SUT boundary.
- The self-assessment arm (signal d) is dangerous as written: listed as a candidate but also forbidden as the sole gate. If it is a measured arm, the spec must define whether it can affect behavior, how arms are separated, and how post-hoc arm selection is prevented.
- The live acceptance criteria need a committed operator-driver posture: STOP-AND-WARN/resumable for deliverable runs, not merely skip-not-fail integration behavior.

Suggestions:
- Promote the chosen confidence predicate into a frozen `PREREGISTERED_SUBMISSION_CONFIG_0044` with config hash, SUT hash, detector version, signal precedence, and a total pure verdict function.
- Define the injection point explicitly: loop observes tool results, confidence predicate fires once, then appends a bounded model-visible nudge message; no turn/time fallback; artifact records fired/ignored/wrong-span.
- Make `symbols-derived exact span` the primary shipped gate and treat grep-inside-symbol/convergent evidence as separately named arms only if the pilot is powered and pre-allocated for them.
- Add ACs for dual-seam verifier/schema threading if confidence fields enter trajectory artifacts.

Convention violations:
- Frontmatter uses non-canonical keys (`authors`, `packages`, `related-specs`) and omits `started_at_sha`. Canonical schema is `id, title, status, started_at_sha, created`.
- A pre-registered decision config must be a frozen object with the verdict as a total pure function over it before the run — not deferred to "pick before the run."
- Live/operator drivers should be STOP-AND-WARN on infra; skip-not-fail is for integration tests, not deliverable-producing runs.

## claude-p

**Verdict:** changes-requested

Concerns:
- **Unstated comparison BASELINE (top concern).** Three SUTs now exist: pre-nudge 0042, shipped unconditional-nudge 0043, conditioned-nudge 0044. AC4's "before/after" does not say which pairing defines "before." If BEFORE = shipped 0043 SUT, `fu_before` = 2, below the 0043 power floor of 3, making the drop conjunct structurally vacuous; if BEFORE = the committed 0040/0042 ledger, that must be stated and the shipped nudge's removal becomes part of the delta. Must be frozen in config before any number.
- **"0043's mechanism, unchanged" is internally contradictory.** 0043's mechanism is a static sentence in `build_initial_prompt`; evidence-conditioned firing cannot ride the initial prompt because evidence doesn't exist at turn 0. The real mechanism is mid-loop message injection — a larger, unaddressed SUT delta touching truncation (does the nudge survive `scout_history_char_cap`?), loop detection (does injection perturb the no-new-span counter?), and turn accounting (is the injected message a turn?). Also silent on whether the shipped unconditional sentence is actually removed.
- **AC6's outcome enum has overlapping predicates, no total order.** A run where the nudge never fires trivially satisfies `CONDITIONED_NUDGE_SHIPS` (net = 0 ≥ 0, no net-negative model) while also being `NEVER_FIRES`. OQ2 pre-registers "never fires on 8b" as success while AC6 types `NEVER_FIRES` as failure-ish — needs per-model firing rates as inputs, a frozen precedence, and a totality test (the 0020/0023 discipline).
- **Signals (b) and (c) are not mechanically definable as written.** "matched line contains query terms" and "point at the same file/span" each admit several implementations; the freeze convention requires hashable code before the spend, not prose.
- **Signal (d) as "measured arm" is ambiguous** between a second SUT arm (doubling spend/splitting the run) and record-only observability. Under SUT-frozen-per-run only one gating definition can run; (d) should be recorded as data, never gated on, or dropped from this pilot.
- Gold-blindness + one-oracle-reuse: the runtime confidence predicate is SUT code and must be gold-blind by construction (scout/ vs eval/), while AC3's "fired-on-wrong-span" attribution needs gold and must reuse `metrics.span_hit_kind` by identity. The spec never draws this line.
- AC3's "additive schema bump" doesn't name dual-seam threading (`build_trajectory_record` AND `run_verified_case`'s hand-assembled artifact, pinned by a written-JSON test) — a third recurrence of a known miss (0033/0034/0038).

Suggestions:
- Freeze the baseline explicitly: recommend BEFORE = committed 0040/0042 pre-nudge ledger (fu_before = 6, clears the power floor), with the shipped sentence's removal named as part of one SUT delta and the post-lever SUT hash committed before spend.
- State the full SUT delta and surviving pins: remove the 0043 sentence, add conditioned mid-loop injection riding messages only; assert params-pin and prompt↔surface drift guard stay green; add pins for nudge-survives-truncation and nudge-does-not-trip-loop-detection.
- Pre-register per-model readings (OQ2/OQ3) as data in the frozen config; make `decide_*` a total pure function over (per-model net × per-model firing rate) with grid-totality tests.
- Gate on (a) symbols-derived span as primary; (b) only with exact code definition; record (c)/(d) as observability fields, never gates.
- Add `started_at_sha` to frontmatter (or land the deferred 0041-OQ2 scaffold decision first).

Convention violations:
- Frontmatter carries `authors/packages/related-specs` and omits `started_at_sha` — the known 0041-OQ2 scaffold drift, re-committed here.
- Precedence over overlapping (non-partition) outcome conditions must be a frozen total order with all true conditions recorded (0020/0023 projection discipline) — AC6's three labels overlap with no stated precedence or totality requirement.

## Synthesis

Both reviewers agree the spec's direction is right — conditioning the submit-early nudge on
observed evidence is the correct next lever after 0043's bidirectional predicate caught a
net-negative unconditional nudge — but both independently converge on the same structural gap:
**the spec defers exactly the design decisions its own "freeze before any number" invariant
demands be frozen.**

### CONVERGENT findings (both reviewers — strongest signal)

1. **The confidence gate/predicate is not concretely frozen.** Both reviewers flag that listing
   candidate signals (a)-(d) and saying "pick before the run" is not a freeze. codex wants a named
   `PREREGISTERED_SUBMISSION_CONFIG_0044` with hash, precedence, and a total pure verdict function;
   claude-p wants exact code-level definitions for signals (b)/(c) specifically, since prose
   ("query terms," "same span") admits multiple divergent implementations chosen only after
   trajectories are seen.
2. **"0043's mechanism, unchanged" is contradictory.** Both reviewers independently identify that
   0043's nudge was a static initial-prompt sentence, and an evidence-conditioned nudge cannot fire
   at turn 0 — it necessarily requires mid-loop injection. This is a materially larger SUT delta
   than the spec acknowledges, and it needs its own pins (codex: injection point / bounded
   model-visible message / no turn-time fallback; claude-p: survives truncation, doesn't perturb
   loop detection, doesn't corrupt turn accounting; plus whether the old sentence is actually
   removed).
3. **Frontmatter convention violation.** Both flag the same defect: non-canonical keys
   (`authors`, `packages`, `related-specs`) in place of the canonical schema, and a missing
   `started_at_sha` — claude-p notes this is a recurrence of the known, still-unresolved 0041-OQ2
   scaffold drift.
4. **Signal (d) (self-assessment) as a "measured arm" is ambiguous/dangerous.** Both reviewers
   flag that it's unclear whether (d) is a second gating arm (doubling spend / splitting the run)
   or pure observability, and both recommend it be recorded as data only, never used to gate,
   for this pilot.

### DIVERGENT / unique findings

**claude-p only:**
- **The unstated comparison BASELINE — claude-p's top concern, not raised by codex.** Three SUTs
  now exist (pre-nudge 0042, shipped 0043, conditioned 0044) and AC4/AC5 don't say which pairing
  is "before." Depending on the choice, `fu_before` is either 2 (under the 0043 power floor of 3,
  making the drop conjunct vacuous) or 6 (from the 0040/0042 ledger, which clears the floor).
  claude-p recommends freezing BEFORE = the 0040/0042 ledger.
- AC6's outcome enum (`CONDITIONED_NUDGE_SHIPS` / `STILL_TRADES_OFF` / `NEVER_FIRES`) overlaps
  with no total order — a zero-firing run trivially satisfies SHIPS while also being NEVER_FIRES,
  and this collides with OQ2's pre-registration that "8b never fires" is a success reading.
- Signals (b)/(c) are not mechanically definable as written — flagged with specific textual
  ambiguities codex did not call out.
- Gold-blindness + one-oracle-reuse: the runtime predicate must be gold-blind by construction
  (lives in scout/), while AC3's "fired-on-wrong-span" attribution needs gold and must reuse
  `metrics.span_hit_kind` by identity — the spec never draws this line.
- Dual-seam artifact schema threading (`build_trajectory_record` and `run_verified_case`'s
  hand-assembled artifact) not named in AC3's "additive schema bump" — a third recurrence of a
  known miss (0033/0034/0038).

**codex only:**
- Live acceptance criteria need a committed **STOP-AND-WARN / resumable operator-driver posture**
  for deliverable-producing runs, distinct from and in addition to the "skip-not-fail" posture
  that's appropriate for CI integration tests. The spec's Test-tier convention conflates these.

## ACTION ITEMS (ordered by importance)

1. **Freeze the comparison baseline.** State explicitly which SUT pairing defines "before" in
   AC4/AC5 (claude-p recommends the committed 0040/0042 pre-nudge ledger, which keeps 0043 and
   0044 on one comparison axis and clears the `fu_before` power floor). Put this in the frozen
   config, not the plan.
2. **Concretely freeze the confidence predicate before implementation.** Name the exact
   pre-registered signal(s), give (b)/(c) exact code-level definitions (or drop them), fix
   precedence, and package it as a hashable/frozen config object (e.g.
   `PREREGISTERED_SUBMISSION_CONFIG_0044`) with a total pure verdict function — not "pick before
   the run."
3. **Name the mid-loop injection seam explicitly as its own SUT delta.** State that the mechanism
   is mid-loop message injection (not "0043's mechanism, unchanged"), define the injection point,
   state whether the shipped 0043 sentence is removed, and add pins for: survives
   `scout_history_char_cap` truncation, does not perturb loop detection, and does not corrupt turn
   accounting.
4. **Fix AC6's outcome typing.** Make the three outcome labels a genuine partition (or a frozen
   total order over overlapping conditions per 0020/0023 discipline) driven by per-model
   (net, firing-rate) tuples, with OQ2/OQ3's expected per-model readings folded in as data so a
   silent 8b or inert 4b is typed mechanically rather than argued at close.
5. **Resolve signal (d)'s role.** Record self-assessment as observability data only, never as a
   gating arm, for this pilot — do not let it silently double the live spend or split the run
   across SUTs.
6. **Fix frontmatter to the canonical schema** (`id, title, status, started_at_sha, created`) and
   add `started_at_sha` — resolving the recurring 0041-OQ2 drift rather than re-committing it.
7. **State the gold-blindness / one-oracle-reuse line for the predicate and AC3's attribution**
   (predicate lives gold-blind in scout/; "fired-on-wrong-span" reuses `metrics.span_hit_kind` by
   identity, not a second oracle).
8. **Name the dual-seam schema threading** in AC3 (`build_trajectory_record` and
   `run_verified_case`'s hand-assembled artifact, pinned by a written-JSON test).
9. **Separate live operator-driver posture from CI integration posture.** Commit to
   STOP-AND-WARN/resumable behavior for deliverable-producing live runs; keep skip-not-fail scoped
   to integration tests only.

## Final action

Quorum is **not met** (0 of 2 reviewers returned approve or approve-with-comments; both returned
changes-requested). Spec 0044 remains `status: draft`.

**Action:** Revise `spec.md` to address the action items above — most urgently the baseline
freeze, the confidence-predicate freeze, and the mid-loop injection seam — then re-run
`/speccraft:spec:review`.

---

# ROUND 2

The round-1 action items were addressed in the spec.md revision: the baseline is frozen
(BEFORE = the committed 0040/0042 ledger), the confidence gate is pinned to signal (a) solely
with (b)/(c)/(d) demoted to fixture-pinned record-only fields, the mid-loop injection seam is
named explicitly (with truncation/loop-detection/turn-accounting pins), `decide_submission_outcome`
is specified as a total pure function with a frozen precedence, and the dual-seam schema
threading, gold-blindness line, and STOP-AND-WARN operator-driver posture are all stated. Round 2
reviewed this revision.

## codex (round 2)

**Verdict:** approve-with-comments

Concerns:
- The symbols-only gate is crisp and preregistered, but it may be too narrow to rescue the
  intended 14b class if those located-but-unsubmitted spans came from grep/read_span rather than
  symbols — a firing-rate risk worth watching, not a blocking defect (resolved by the NEVER_FIRES
  branch plus the attributable-null artifact rather than a spec change).
- The confidence predicate needs a sharper firing definition for multi-span symbols results:
  whether one exact span, many exact spans, degraded annotation results, or repo-wide by-name
  batches (up to `scout_symbols_repo_max_entries=200`) all qualify as the gate.
- The nudge text says "submit it now" but the trigger may identify multiple candidate spans;
  without deterministic message wording for that case, implementation could accidentally steer
  toward arbitrary first-span behavior.
- The config says it carries a NEVER_FIRES threshold, but the spec body effectively defines that
  threshold as exactly zero 14b firings in prose. This should be explicit as data, not only prose.

Suggestions:
- Define the confidence gate projection as a precise function over a tool result: qualifying tool
  name, success/degraded marker handling, exact-span shape, and one-vs-many span behavior.
- Make the injected message template part of the frozen config or pin it in tests, including the
  multi-span case.
- Pre-register the 14b NEVER_FIRES threshold as a concrete numeric field, e.g.
  `never_fires_min_14b_firings = 1` or `never_fires_14b_firing_rate == 0`.
- Add a unit fixture where `symbols(name=...)` returns multiple exact spans and assert both
  whether the gate fires and what message is injected.

Guardrail/convention violations: none.

## claude-p (round 2)

**Verdict:** changes-requested

Concerns:
- **The inert-lever hole.** `CONDITIONED_NUDGE_SHIPS` is reachable at net = 0 with zero
  conversions — the verdict machinery has no benefit conjunct (no `conversions ≥ 1` or
  `fu_after < fu_before` requirement), unlike 0043's two-conjunct predicate. A nudge that fires
  and is universally ignored (fired-but-ignored) would type as a ship.
- **No UNDER_POWERED enum member.** `min_covered_before_cells=8` is carried in the frozen config
  but `decide_submission_outcome` has no branch that consumes it — dormant config that violates
  the 0020/0023/0043 "wired into the real run path, not left dormant" discipline. `fu_before=6`
  clears the *other* floor statically, but the coverage floor depends on the live run and can be
  cut by degrades.
- **The pre-registered 8b near-zero-firing reading contradicts the mechanism.** The gate fires on
  ANY symbols-derived exact span, and 8b had the HIGHEST 0042 symbols adoption (10/11) — 8b's
  firing rate should be expected HIGH, not near-zero. The success criterion should be
  regressions = 0 at any firing rate, not near-zero firing specifically.
- **The gate is looser than "a confident span in hand."** "A successful symbols tool result
  carrying an exact span" also covers repo-wide name-lookup batches (up to
  `scout_symbols_repo_max_entries=200` candidates) and the degraded ripgrep-fallback ANNOTATION
  shape — both currently qualify, reintroducing submit-before-verify through the gate itself if
  left undefined.
- Injection point ("after each tool result") is not pinned to the tool-result batch boundary; under
  0029's answer-all-N protocol, interleaving a non-tool message mid-batch (between an assistant
  tool_calls message and its N tool responses) is a malformed conversation.
- Signal (d) is defined as "recorded only if trivially extractable" — prose, not a pinned
  projection like (b)/(c); should be pinned or dropped.
- The injected message's role/text are unspecified but load-bearing; the schema version string
  is never named; whether (b)/(c) are computed SUT-side or eval-side postflight is left open.

Suggestions:
- Add a benefit conjunct (`conversions ≥ 1 OR fu_after < fu_before`) to `CONDITIONED_NUDGE_SHIPS`,
  or add a distinct `NUDGE_INERT`/`FIRED_NO_CONVERSION` label in the frozen precedence.
- Add `UNDER_POWERED` to the enum, triggered when live coverage falls below
  `min_covered_before_cells`; make `decide_submission_outcome` total over it with a grid-totality
  test.
- Tighten or explicitly scope the gate projection (file-local vs repo-wide, clean vs degraded,
  single vs many spans) — a deliberately loose gate is defensible if pre-registered explicitly,
  but the choice must be made now.
- Re-word the 8b reading: regressions = 0 is the success criterion at any firing rate.
- Pin injection to the post-batch boundary per 0029, with a specified message role.
- Pin signal (d)'s extraction rule or cut it; name the schema version string (`0044/1`); state
  that (b)/(c) are computed eval-side postflight.

Convention violations:
- Pre-registered verdict must be a total pure function with every power floor consumed by a typed
  outcome, never dormant config (0020/0023/0043 discipline) — `min_covered_before_cells` has no
  consuming branch.
- Answer-all-N in emitted order — an interleaved/unanswered tool_call batch is a malformed
  conversation (spec 0029) — the injection point is not pinned to the post-batch boundary.

## Synthesis (round 2)

Quorum is **met**: codex returned `approve-with-comments`, satisfying the 1-approve-or-better
quorum rule, despite claude-p returning `changes-requested`. Per this repo's 0041/0042/0043
precedent, remaining residuals from both round-2 reviewers are folded into `spec.md`
post-quorum (the main session is doing this now) rather than blocking on a third review round.

### CONVERGENT findings (both round-2 reviewers)

Both reviewers converge on the same underlying defect: **the gate projection is underspecified
at the edges.** "A successful symbols tool result carrying an exact span" is looser than
"a confident span in hand" — it currently also covers:
- multi-span symbols results (one exact span vs many),
- the degraded ripgrep-fallback ANNOTATION shape (success/degraded marker handling), and
- repo-wide by-name lookup batches (up to `scout_symbols_repo_max_entries=200` candidate spans).

Both reviewers also independently flag that the injected nudge message's text/template is
unpinned SUT surface — codex because "submit it now" is ambiguous when multiple candidate spans
are in play (risk of arbitrary first-span steering), claude-p because the message's role and
exact wording are unspecified but load-bearing for small models. Both want the template (including
multi-span wording) frozen in config, not left to implementation discretion.

Both reviewers also independently flag that the `NEVER_FIRES` threshold is prose, not data: codex
wants it as a concrete numeric config field (e.g. `never_fires_14b_firing_rate == 0`); claude-p's
UNDER_POWERED concern is a sibling instance of the same "threshold must be config data, not prose"
discipline.

### claude-p unique (its changes-requested substance)

1. **The inert-lever hole** — `CONDITIONED_NUDGE_SHIPS` is reachable at net = 0 with zero
   conversions (a fired-but-ignored run types as a ship); needs a benefit conjunct or a
   NUDGE_INERT label.
2. **No UNDER_POWERED enum member** — `min_covered_before_cells=8` is dormant config with no
   consuming branch (violates 0020/0023/0043 discipline).
3. **The pre-registered 8b near-zero-firing reading contradicts the mechanism** — 8b had the
   HIGHEST 0042 symbols adoption (10/11); expect HIGH firing, not near-zero; the success
   criterion should be regressions = 0 at any firing rate.
4. **Injection must be pinned to the tool-result batch boundary** (0029 answer-all-N —
   interleaving mid-batch is a malformed conversation), with a specified message role.
5. **Signal (d) is unpinned** ("trivially extractable" is prose) — pin or drop.
6. **Name the schema version string** (0044/1) and state that (b)/(c) are computed eval-side
   postflight.

### codex unique

The symbols-only gate may be too NARROW to rescue the 14b class if its located-but-unsubmitted
spans came from grep/read_span rather than symbols — a firing-rate risk worth watching, resolved
by the NEVER_FIRES branch plus the attributable-null artifact rather than requiring a spec change.

### POST-QUORUM RESIDUALS (fold list)

Quorum is met, so these are folded into `spec.md` directly rather than gating a third review
round:

1. Add a benefit conjunct (or a distinct `NUDGE_INERT` label) so a fired-but-ignored nudge cannot
   type as `CONDITIONED_NUDGE_SHIPS`.
2. Add an `UNDER_POWERED` enum member consuming the `min_covered_before_cells` coverage floor,
   with a grid-totality test.
3. Freeze the exact gate projection as config data: clean vs degraded, span-count bound (one vs
   many), file-local vs repo-wide.
4. Pin the nudge message template (role + text, including multi-span wording) in the frozen
   config.
5. Pin the `NEVER_FIRES` threshold as a numeric config field (not prose).
6. Re-word the 8b reading: regressions = 0 is the success criterion at any firing rate (not
   near-zero firing specifically).
7. Pin the injection point to the post-batch boundary per 0029, with a specified message role.
8. Drop or pin signal (d)'s extraction rule.
9. Name `VERIFIER_SCHEMA_VERSION` (0044/1) and state that (b)/(c) are computed eval-side
   postflight.
10. Add a multi-span fixture AC (symbols returning multiple exact spans — assert both whether the
    gate fires and what message is injected).

## Final action (round 2)

Quorum is **met** (codex: approve-with-comments). Spec 0044 moves to `status: reviewed`.
Residuals 1-10 above are folded into `spec.md` post-quorum by the main session per the
0041/0042/0043 precedent (fold remaining reviewer residuals into the spec rather than blocking on
a further review round once quorum is met).

**Action:** Fold the 10 post-quorum residuals into `spec.md`, set `status: reviewed`, then proceed
to `/speccraft:spec:plan`.
