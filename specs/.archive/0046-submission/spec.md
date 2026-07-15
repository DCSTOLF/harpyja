---
id: "0046"
title: "submission"
status: closed
created: 2026-07-13
authors: [claude]
packages: []
related-specs: ["0045", "0044", "0043", "0042", "0041"]
---

# Spec 0046 — submission

## Why

0043→0045 tried three PREDICTIVE confidence gates — guess ex ante whether a span
is good enough to submit — and every one traded directions: fire more →
silence→wrong-confidence (8b submits spans it had stayed silent on); fire less →
found-but-unsubmitted (0045: firing collapsed 3/33, fu 1→8, net −1). The trade is
structural because a single gate is answering two different questions at once: "is
this span worth submitting?" (evidence quality) and "should I stop exploring?"
(budget). Two mechanism changes, both inside the explorer loop, dissolve it rather
than relocating it:

1. **REACTIVE, not predictive.** Default to submitting the best span in hand; keep
   exploring ONLY on a NAMED DISCONFIRMING trigger. Predicting span quality up
   front is the hard problem; noticing that something contradicts your candidate is
   the easy one.
2. **CONFIRM-BEFORE-SUBMIT, not corroborate-to-fire.** 0045 put corroboration in
   the FIRING condition and the gate stopped firing. The same evidence belongs in
   the SUBMIT PATH — keep firing, but require one cheap confirmation before the
   citation goes out. Gate the OUTPUT, not the ACTION.

**Placement decision (was OQ2/OQ3, now pinned).** Confirm-before-submit is a
**host-side interception of `submit_citations` arguments** (verify-then-emit),
NOT an in-loop step the model is coached to take. Rationale: (a) it consumes **no
model turn** — so it cannot reopen 0043's dawdle-after-locate clock-death, and 4b's
token/prefill budget is untouched by the CONFIRM lever (the reactive lever is a
separate cost, see AC7); (b) a small tool-calling model cannot ignore it (it is host
code on the terminal-action path, not a prompt the model may skip); (c) it is the
natural home for the graceful-degradation guardrail's "never return a confident
citation that wasn't verified when verification was available." **Confirm-fail emits
the citation WITH a confidence flag (a degraded honest answer), never silence** —
silence-into-block would manufacture found-but-unsubmitted and trip the
graceful-degradation guardrail, which is 0045's exact failure relocated one level
down.

**The counted cost of the flag (review round 2).** A confidence flag is honesty, not
a refund: a flagged-but-WRONG citation still misdirects the downstream agent. So
emit-with-flag introduces a NEW error direction, and this spec **counts it as a fifth
predicate side (`flagged-wrong-emitted`)** rather than leaving it to a side-observable.
Its conservation partner is s→wc: on a fired cell that submits a wrong span,
confirmation-PASS leaves it confident (→ s→wc) and confirmation-FAIL flags it
(→ flagged-wrong-emitted); the two **partition the fired-wrong-submitted mass, whose
SUM is conserved and reported**. This closes the de-attribution channel by counting
(the mass cannot leave s→wc for an uncounted bucket — it reappears in a watched side),
so `DISSOLVES_TRADE` stays refutable and "flag everything" is scored as the failure it
is, not caught only by a diagnostic.

**Scope note.** This is Tier-1 Scout policy only (`explorer_loop.py`, the
reactive-policy/gate module, and the `submit_citations` interceptor; plus the eval
harness under `harpyja/eval/`). Not modes (auto/deep), not Tier-2 Deep (`dspy.RLM`),
not a new tier. The eval drives ExplorerBackend directly (`tiers_run=[0,1]`) — no
escalation confound.

Ref: 0044 (conditioned gate, net +2 — the operating point being restored), 0045
(TRADES_DIRECTIONS; the four-sided predicate, s→wc as a counted class, the
gold-blind signal defs, the unfired cross-check — ALL KEPT), 0042 (symbols
adoption — symbols-derived spans are the strongest signal), 0041 (gated endpoint).

### Invariants

- **Revert the LEVER, keep the APPARATUS.** 0045's require-corroboration-to-fire is
  RETIRED — recorded as a measured regression (firing 3/33, fu 1→8), with the reason
  preserved: it gated ACTION when the evidence belonged in the OUTPUT path. Retained
  from 0045 (regression-pinned): the four-sided predicate, s→wc as a first-class
  counted class (schema, dual-seam), the gold-blind (b)/(c) signal definitions shared
  by gate and postflight, and the record-only `unfired_silence_to_wrong_confidence`
  cross-check (it caught that part of 0045's s→wc drop was DE-ATTRIBUTION, not
  elimination — keep it).
- **Re-measure the baseline on the CURRENT SUT — do not compare to history.** 0045
  evolved `confidence_gate.py`, so "0044's gate" on today's code is not
  byte-identical to 0044's run. Run a fresh 0044-equivalent arm on the pinned
  current SUT. The new lever is measured against THAT arm, not against 0044's
  historical numbers (see AC5's band + `BASELINE_DRIFT_STOP` branch).
- **Confirmation is host-side, deterministic, and adds no model turn.** Confirm-before-
  submit reuses the EXISTING `read_span` implementation from host code — it adds NO
  tool to the model's registered suite (still exactly `{grep,glob,read_span,ls,symbols}`,
  the exact-count guard untouched), makes NO model call, uses NO gold, and changes NO
  generation params (the 0034/0038 `explorer_think=None ⇒ params == {max_tokens: 2048}`
  byte-pin SURVIVES VERBATIM). Both new levers ride `messages`/record fields + the
  submit-path interceptor only.
- **FIVE-sided predicate, FROZEN before any number.** The 0045 four sides
  (conversions, regressions, silence→wrong-confidence, found-but-unsubmitted) are
  retained unchanged; 0046 EXTENDS them with a FIFTH counted side
  (`flagged-wrong-emitted`) for the confirm-before-submit lever's new error direction,
  per the per-direction-conjunct convention (a new lever with a new error direction
  gets its own counted side, never a side-observable that only documents the hole).
  Plus the retained unfired-s→wc cross-check AND a NEW record-only confirm-conditioned
  fu cross-check (AC4c) AND a record-only per-model FLAG-RATE diagnostic (AC4d). Per
  model. Three specs running, a frozen predicate has caught what a narrower one would
  have sold as a win; this spec's risk is identical.
- **Per-model sign is expected.** 14b benefits from submit-discipline (fired 5/11,
  zero regressions in 0044); 8b is where miscalibration concentrates (its dawdle IS
  verification — a LOW trigger rate for 8b is a SUCCESS, not a failure); 4b is inert
  to submission levers (its constraint is tool-output bytes/prefill — the parked
  compression spec). The CONFIRM lever adds no turn so it cannot cost 4b; the REACTIVE
  lever DOES spend explore turns/bytes, so a 4b cost is attributed to the reactive lever
  (AC7). Pre-register these readings.
- **Measure on the 0041-gated endpoint.** exclusivity proof per artifact, SUT hash
  pinned, params byte-identical, evict-before / re-pin-after. Two-stage freeze:
  the five-sided predicate freezes before the numbers; the config (with SUT hash)
  freezes after the SUT lever lands, before any live spend; the driver re-verifies
  both hashes at every invocation (typed STOP on drift).

## What

- **REVERT.** Restore 0044's firing condition; retire require-corroboration-to-fire
  with its recorded rationale (a measured regression, not a deletion).

- **BASELINE ARM.** Re-run the 33 cells with the reverted gate on the pinned current
  SUT — the honest comparison point. The aggregate NET is expected in the **frozen
  sanity band `[1, 3]`**; a baseline outside the band emits the typed outcome
  `BASELINE_DRIFT_STOP` (artifacts retained) rather than silently proceeding. Note
  this band is a **sanity check, not a pass/fail gate on the new lever**: AC6 measures
  NEW-vs-baseline head-to-head (not vs 0044's history), so a baseline of +1 is
  survivable and the head-to-head still holds — the band exists only to catch a SUT
  that no longer reproduces the 0044 operating point at all. (In the baseline arm no
  confirmation runs, so `flagged-wrong-emitted = 0` by construction — the fifth side is
  a pure delta of the NEW arm.)

- **REACTIVE POLICY.** Submit the best available span by default; continue exploring
  ONLY on a PRE-REGISTERED disconfirming trigger, and RECORD WHICH trigger(s) fired.
  **The trigger enum is pinned here to a mechanical, fixturable, gold-blind definition
  for each member** (no model judgment, no reference to the gold answer):
  - `symbols-empty` — a `symbols` call for the candidate file returned zero spans
    (or the honest-empty marker). Directly readable from the tool result.
  - `hit-in-comment` — the grep top-hit's matched line is contained in a **comment
    node or a docstring node** (a string literal in statement position — the leading
    statement of a module/class/function body) as reported by the symbol layer
    (tree-sitter); a hit inside executable code (an identifier/call/operator token) is
    NOT a hit-in-comment even if a comment shares the line. Ripgrep-fallback (no parse)
    rule: the matched line is a whole-line comment or the match offset lies after the
    language's line-comment token on that line (a trailing comment); a match inside a
    code token is NOT a hit-in-comment.
  - `tool-disagreement` — the candidate file implied by the grep top-hit differs, after
    canonical path normalization, from the file that OWNS the symbol returned by
    `symbols` for the query's key identifier (`grep-candidate-file != symbols-owning-file`).

  Triggers are a **set**: zero, one, or several may fire on a case; all firing
  identifiers are recorded (multi-trigger is a first-class shape, not a
  precedence problem — the ACTION is "keep exploring" regardless of which/how many
  fired). **Termination bound:** trigger-driven exploration does NOT extend the
  budget — the existing `scout_max_turns` / `scout_wall_clock_s` ceilings (byte-pinned,
  unchanged) remain the hard cap, so a triggered explore cannot dawdle past the clock
  (0043's failure is bounded, not reopened). A run that keeps exploring WITHOUT a
  named trigger is a visible policy violation, countable in the artifact.

- **CONFIRM-BEFORE-SUBMIT.** A **host-side interceptor on the `submit_citations`
  terminal action** (see Placement decision), living in a module SEPARATE from the
  reactive-policy/gate logic (so the AC3(a) import guard is expressible). Before a
  citation is emitted, the interceptor performs one cheap host-side `read_span` of the
  candidate and applies a **concrete, deterministic lexical/symbolic predicate — never
  a model judgment, never gold**: confirmation PASSES iff the query's key identifier(s)
  appear in the returned span text (lexical containment) OR match the span's symbol name
  from the symbol layer. **Query key-identifier extraction (pinned mechanically, like the
  triggers):** the identifier-shaped tokens in the query (matching
  `[A-Za-z_][A-Za-z0-9_]*`, length ≥ a pinned floor, dotted paths kept whole), preferring
  backtick/quote-delimited tokens when the query contains them; the extraction reads the
  QUERY only, never the gold. Outcomes:
  - `PASS` → emit the citation clean.
  - `FAIL` (key identifier extractable but absent from the span) → emit the citation
    **with a confidence flag** (degraded honest citation reusing the existing
    confidence-flag surface), never silence, never re-explore.
  - `CONFIRM_ERROR` (no key identifier can be extracted from the query, OR `read_span`
    errored / returned nothing — the predicate cannot decide) → treat as could-not-vouch
    per graceful degradation → emit **with a confidence flag** (same emit route as
    `FAIL`, distinct recorded cause), NEVER a guessed PASS/FAIL.
  - `NO_CANDIDATE` (the model submitted nothing / no span to confirm) → honest-empty,
    nothing to intercept.

  This targets 8b's s→wc by moving a would-be confident-wrong submission into the
  honestly-flagged `flagged-wrong-emitted` side (not into an uncounted bucket) —
  WITHOUT throttling firing. A flagged-but-CORRECT citation (a confirmation
  false-negative) still counts as located (the citation is right), so confirmation
  false-negatives cannot manufacture regressions; their volume is surfaced by the
  FLAG-RATE diagnostic (AC4d).

- **ARTIFACT (concrete, additive, dual-seam).** Bump `VERIFIER_SCHEMA_VERSION
  0045/1 → 0046/1` (additive, legacy artifacts validate unchanged). Append-last, with
  defaults, threaded through BOTH seams (`build_trajectory_record` params AND the
  `run_verified_case` written artifact):
  - `reactive_triggers_fired: list[str]` — the set of fired trigger identifiers
    (subset of `{symbols-empty, hit-in-comment, tool-disagreement}`); default `[]`.
  - `confirmation_ran: bool` — whether the submit-path interceptor executed;
    default `False`.
  - `confirmation_outcome: str | None` — one of
    `{PASS, FAIL, CONFIRM_ERROR, NO_CANDIDATE}`; default `None`.
  - `submit_disposition: str | None` — the derived attributable shape, one of
    `{never-triggered, triggered-and-explored, confirmed-then-submitted,
    confirm-failed-flagged, no-candidate}`; default `None`.
  From these fields, plus gold (eval-side), every emitted result maps to exactly one
  counted side (truth table below).

### Outcome accounting — five-sided predicate + truth table

Every per-cell outcome in the NEW arm lands in exactly one COUNTED side; no error
direction is left without a side. The counted side is set by **CORRECTNESS ×
s→wc-eligibility**; the confirmation flag is an ORTHOGONAL recorded axis that changes
the counted side ONLY inside the s→wc-eligible-wrong partition (splitting s→wc from
flagged-wrong-emitted) and is otherwise surfaced only by the FLAG-RATE diagnostic
(AC4d). **`s→wc-eligible`** is the retained 0045 condition: the cell was SILENT in the
baseline arm (empty→) AND the 0044 confidence gate fired on it. The interceptor runs on
EVERY submit, so a flag may attach to a not-eligible citation too — that does NOT create
a new correctness side, only a diagnostic mark. `s→wc` and `flagged-wrong-emitted`
PARTITION the s→wc-eligible-wrong mass by confirmation outcome, so their sum is conserved
and reported (the de-attribution guard). Conversions/regressions are the head-to-head
DELTAS of `located` vs the baseline arm.

| correct? | s→wc-eligible? | confirmation | emitted | counted side |
|---|---|---|---|---|
| correct | any | PASS | clean | **located** (→ conversion if baseline-miss); no flag |
| correct | any | FAIL / CONFIRM_ERROR | flagged | **located** (flagged-but-correct still located; flag-rate++) |
| wrong | yes | PASS | clean (confident) | **s→wc** (confirmation false-positive: passed a wrong span) |
| wrong | yes | FAIL / CONFIRM_ERROR | flagged | **flagged-wrong-emitted** (NEW fifth side) |
| wrong | no | PASS | clean | **regression** if baseline-correct, else plain wrong-miss |
| wrong | no | FAIL / CONFIRM_ERROR | flagged | **regression** if baseline-correct, else plain wrong-miss (flag → diagnostic only, NOT flagged-wrong-emitted) |
| none | — | NO_CANDIDATE | — | **fu** if gold was in a tool result, else **honest-empty** (the attributable null) |

The two `wrong | no` rows make the boundary explicit: a not-eligible wrong span that
FAILs confirmation is emitted flagged but counts as `regression`/miss BY CORRECTNESS —
its flag rides the diagnostic axis only, NEVER the `flagged-wrong-emitted` side (which is
s→wc-eligible-wrong by definition). AC4b pins this boundary in test.

`flagged-wrong-emitted` is a first-class COST side in the verdict: it can rise, so
confirm-before-submit CAN worsen the typed outcome (`DISSOLVES_TRADE` is refutable).
The degenerate "flag everything" operating point pushes s→wc-eligible-wrong cells into
`flagged-wrong-emitted` (caught by its pre-registered ceiling, which sits BELOW baseline
s→wc so relabeling the whole mass into flags breaches it) and correct cells into
flagged-but-located (caught by the FLAG-RATE diagnostic) — both are visible, neither
scores as a win.

## Acceptance criteria

1. **[unit]** 0045's corroboration-to-fire is removed; 0044's firing condition
   restored; the 0045 apparatus (four-sided predicate, s→wc counting, gold-blind
   signals, unfired s→wc cross-check) is retained and regression-pinned (existing
   0045 tests stay green unchanged).

2. **[unit]** Reactive policy, fixture-pinned; each trigger has a deterministic,
   gold-blind fixture:
   - no trigger fires → the policy default submits the best span in hand;
   - `symbols-empty`, `hit-in-comment`, `tool-disagreement` each fire on a crafted
     tool-result fixture and are recorded in `reactive_triggers_fired`; a
     non-triggering near-miss fixture for each (a hit in a code token; agreeing
     tools; a non-empty symbols result) does NOT fire it;
   - **multi-trigger:** two triggers firing on one case record BOTH identifiers
     (the field is a set, order-stable);
   - exploration-after-trigger is bounded by the existing `scout_max_turns` /
     `scout_wall_clock_s` ceilings (a fixture proves a triggered explore terminates
     at the cap, not unbounded).

3. **[unit]** Confirm-before-submit is in the SUBMIT PATH, not the firing condition —
   split into the two things that are actually testable:
   - **(a) code-structure assertion** (the real guard that makes the 0045 collapse
     structurally impossible): the reactive-policy/gate module contains NO reference to
     the confirmation result — asserted structurally (ast/import) BOTH by symbol
     (it does not read `ConfirmationOutcome`, the confirmation fields, or the
     submit-disposition derivation) AND by module boundary (it does not import the
     `submit_citations` interceptor module). Requires the gate logic and the interceptor
     to live in SEPARABLE modules (pinned).
   - **(b) fixture:** a confirm-`FAIL` case emits a **flagged** citation (not silence,
     not re-explore) WITHOUT changing the firing count vs the same case with confirm-
     `PASS` — the gate fires at the 0044 rate in both.

4. **[unit]** Artifact + accounting:
   - **(a)** the four additive fields are appended-last with defaults; a legacy
     `0045/1` artifact still validates; the `0046/1` bump is threaded through BOTH
     seams (dual-seam pin);
   - **(b)** a null is attributable across all five `submit_disposition` shapes,
     fixture-pinned; every truth-table row maps to exactly one counted side
     (grid-totality tested, including `flagged-wrong-emitted`) — the partition boundary
     is pinned directly in test: a **not-eligible** wrong span that FAILs confirmation
     counts as `regression`/miss (flag → diagnostic only), while an **s→wc-eligible**
     wrong span that FAILs counts as `flagged-wrong-emitted`;
   - **(c)** the retained record-only, UNCONDITIONED cross-check
     `unfired_silence_to_wrong_confidence` (0045) plus a NEW record-only
     `unfired_confirm_found_but_unsubmitted` counting fu on cells where confirmation
     did NOT fire — reported BESIDE the conditioned counts, NOT in the verdict predicate;
     the s→wc / `flagged-wrong-emitted` SUM (fired-wrong-submitted mass) is reported so a
     drop in one that merely relocates to the other is visible (the de-attribution guard);
   - **(d)** a record-only per-model FLAG-RATE diagnostic (recoverable from
     `confirmation_outcome`: fraction of emitted citations flagged) with a pre-registered
     expected range, reported beside — not in place of — the counted
     `flagged-wrong-emitted` side. The range is a frozen-config literal committed at the
     two-stage freeze point (see AC7 Frozen thresholds), not a free parameter.

5. **[integration]** BASELINE arm (reverted 0044 gate, current SUT): aggregate NET in
   the frozen band `[1, 3]` types the run as reproducing the 0044 operating point;
   outside the band emits `BASELINE_DRIFT_STOP` (artifacts retained). Skip-not-fail
   when the live stack is unavailable.

6. **[integration]** NEW arm on the same 33 cells: report per model conversions /
   regressions / s→wc / **flagged-wrong-emitted** / fu / NET (all five sides + the
   s→wc+flagged-wrong-emitted sum + the flag-rate diagnostic), head-to-head vs the
   BASELINE arm (not vs 0044's history). Named cells: flask-5014 (0044-rescued — stays
   correct?), django-14315::8b (2-spec residual — does confirm-before-submit finally
   catch it?), pytest-10081::14b (0045 never-fired — does reactive submit rescue it?).
   Skip-not-fail when the live stack is unavailable.

7. **[doc]** Typed outcome over the FIVE-sided ledger, frozen before the numbers:
   - `DISSOLVES_TRADE` — fu falls AND s→wc does not rise AND `flagged-wrong-emitted`
     stays at/below its pre-registered ceiling AND the (s→wc + flagged-wrong-emitted)
     sum does not rise AND no model net-negative. The ceiling and the sum conjunct do
     DIFFERENT work: the SUM conjunct blocks NEW s→wc-eligible-wrong mass; the CEILING
     (pinned BELOW baseline s→wc) blocks a pure s→wc→flagged relabel that keeps the sum
     flat — so neither CREATING wrong mass nor merely RELABELING it as flagged reads as a
     dissolve.
   - `TRADES_AGAIN` — name which direction reopened (fu, s→wc, or the new
     `flagged-wrong-emitted`).
   - `NO_EFFECT` — otherwise.

   **Frozen thresholds (two-stage freeze).** The `flagged-wrong-emitted` ceiling and the
   AC4d flag-rate range are BASELINE-RELATIVE: they are committed as config literals
   AFTER the baseline arm yields per-model s→wc (and fixes baseline
   `flagged-wrong-emitted = 0`) and BEFORE any new-arm spend. The ceiling is a
   pre-registered relabel-tolerance FRACTION (< 1) of baseline s→wc, so relabeling the
   whole baseline s→wc mass into flags breaches it; the flag-rate range is a
   pre-registered upper bound on the fraction of emitted citations flagged. The
   derivation RULE is frozen here; the derived literals are the config commit at the
   freeze point (the driver re-verifies the config hash at every invocation).
   Pilot-N signal, not an inferential claim; record the train-on-test confound (three
   specs tuned on the same 33 cells). **4b reconciliation, pre-registered, per lever:**
   the CONFIRM lever adds no model turn, so it cannot cost 4b; the REACTIVE lever spends
   explore turns/bytes, and 4b's binding constraint IS tool-output bytes/prefill. So a
   4b net-negative on a `triggered-and-explored` cell is an **inert-with-cost null**
   (reactive-explore bytes), NOT `TRADES_AGAIN`; only a 4b net-negative on a cell where
   NO trigger fired counts as `TRADES_AGAIN`. `submit_disposition` records the
   distinction — the classification is wired to it, not asserted in prose.

## Out of scope

- Tool-result COMPRESSION for 4b prefill (parked — compression NOT truncation).
- A new tier before Deep (parked — a CAPABILITY question for the conceptual stratum,
  not a policy home).
- Modes / auto / deep routing.
- Tier-2 Deep.
- Pool enlargement.
- The bake-off.
- The 0039 thinking A/B.

## Open questions

_Resolved into the spec across review rounds 1–2:_

- OQ1 (which triggers) → pinned enum with a mechanical, fixturable, gold-blind
  definition per member (What/REACTIVE POLICY; AC2).
- OQ2 (what/where the confirmation call is) → host-side `read_span` interceptor on
  `submit_citations`, deterministic lexical/symbolic containment predicate with an
  explicit `CONFIRM_ERROR` could-not-decide branch, no model turn, no gold
  (Placement decision + What/CONFIRM-BEFORE-SUBMIT).
- OQ3 (does confirm-before-submit induce/hide a cost?) → the flag's cost is COUNTED as
  the fifth predicate side `flagged-wrong-emitted` (partition-partner of s→wc, sum
  conserved), with the confirm-conditioned fu cross-check (AC4c) and the flag-rate
  diagnostic (AC4d) beside it — the lever can worsen the verdict and `DISSOLVES_TRADE`
  is refutable.
