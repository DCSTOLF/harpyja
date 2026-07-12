---
spec: "0040"
reviewers: [codex, claude-p]
quorum: 1
verdict: approve-with-comments
generated: 2026-07-10T00:00:00Z
---

# Cross-model review — 0040 — pool (round 2)

**Date:** 2026-07-10
**Spec:** 0040 — pool (three-model preflight + pilot + per-pair power pre-check)

| Agent | Verdict |
|---|---|
| codex | approve-with-comments |
| claude-p | changes-requested |
| **Overall** | **approve-with-comments — quorum (1 approve / approve-with-comments) MET via codex — status moves to `reviewed`** |

**Flagged caveat:** quorum is met, but claude-p raised one substantive, correctness-grade blocking finding (the ceiling-arithmetic conflation, below). This should be addressed in spec.md **before** running `/speccraft:spec:plan`, even though it does not block the `reviewed` status transition.

## codex

**Verdict:** approve-with-comments

Concerns:
- Preflight exclusions are not threaded into the per-pair verdict space: if `qwen3:8b` or `qwen3.5:4b` is EXCLUDING, the spec says the model is removed, but AC5 still requires ceilings/verdicts for all 3 pairs and the pair enum has no `MODEL_EXCLUDED`/`PREFLIGHT_FAILED` branch.
- The 14b re-confirmation path is under-typed: the spec requires re-confirming 14b on the current harness build, but only the two new models have committed preflight outcomes, leaving unclear what happens if 14b serving/tool-calling regresses.
- The distinction between `PAIR_UNDER_POWERED` and `PAIR_MODELS_TOO_CLOSE` is directionally stated but not fully decision-specified; the frozen pure function should make the predicates non-overlapping, especially for low-discordance-but-covered pilots.

Suggestions:
- Add a pair-level verdict such as `PAIR_MODEL_EXCLUDED`, or explicitly make all per-pair ceiling ACs conditional on all three model preflights/reconfirmations passing.
- Either run the same typed preflight enum for `qwen3:14b`, or define a separate typed 14b reconfirmation outcome that blocks affected pairs on failure.
- Define the exact predicate order for `INSUFFICIENT_PILOT_EVIDENCE`, `PAIR_MODELS_TOO_CLOSE`, `PAIR_UNDER_POWERED`, and `PAIR_FEASIBLE` in the frozen decision function.

Guardrail violations: none.

Convention violations:
- Pre-registered decision config verdicts must be total with non-overlapping predicates — location: Invariants: Upper-bound honesty + typed fork; Acceptance criteria 5-7.

Positive observations: the seven round-1 changes are mostly adequately reflected — the revision now clearly freezes `PREREGISTERED_POOL_CONFIG_0040`, uses per-case pair buckets instead of marginal counts, freezes the coverage threshold and multiplicity stance, distinguishes pytest skip behavior from operator STOP-AND-WARN, commits the asymmetric preflight enum, and pins arm parity at `explorer_think=None`. Codex "would not block" the spec for the multiplicity stance, per-case pairing, pilot parity, or upper-bound labeling — those are materially improved and consistent with repo conventions. The requested changes are narrow: make the failure branches part of the same total typed machinery the spec already values.

## claude-p

**Verdict:** changes-requested

Concerns:
- The core ceiling arithmetic is internally inconsistent as written: extrapolating OBSERVED pilot discordance proportionally to 15 cases yields a point estimate of the discordance rate, not an upper bound — yet the spec labels it "upper bound (max possible discordance)" and carries `projection_kind="upper-bound-feasibility"`. The true 0039-style generous bound in this setting is the per-case UNION-located count (every case either model locates assumed discordant), extrapolated; observed discordance is the quantity that discriminates `PAIR_MODELS_TOO_CLOSE`. The spec conflates these two quantities in the invariant, the PER-PAIR PRE-CHECK bullet, AC5, and OQ2.
- Consequence of the conflation, both directions: extrapolated observed discordance labeled "upper bound" is an epistemic mislabel (an estimate read as a bound — a false `UNDER_POWERED` stop becomes possible from sampling noise while claiming unimpeachability); conversely, a literal max-possible-discordance bound over the ~8 unobserved conceptual cases is vacuous (0 observed + 8 unobserved ≥ floor 8 always, making `PAIR_UNDER_POWERED` structurally unreachable). The frozen config must pin which formula runs, and the formula must actually have the epistemic kind its label claims.
- The discriminating predicate between `PAIR_UNDER_POWERED` and `PAIR_MODELS_TOO_CLOSE` is asserted to exist (AC6) but never defined — both arise from projected discordance below floor. The boundary (e.g., ceiling clears but observed discordance ≈ 0 among union-located cases → TOO_CLOSE) must be a non-overlapping frozen predicate per the grid-totality discipline, not a read-time judgment.
- The `INSUFFICIENT_PILOT_EVIDENCE` coverage threshold is frozen but its VALUE and DERIVATION are unstated — the conventions require thresholds derived from the consuming test's own arithmetic, not a round guess. What coverage makes a 7-of-15 extrapolation admissible vs not, and why?

Suggestions:
- Split the per-pair arithmetic into two pinned quantities in `PREREGISTERED_POOL_CONFIG_0040`: (1) ceiling = extrapolated per-case UNION-located count (the generous bound, still derived from per-case pairs — consistent with the marginal-counts prohibition since union-located is a per-case property); (2) observed signal-discordance via `is_signal_discordant` (drives TOO_CLOSE). Rename or annotate `projection_kind` if the gate quantity is not literally a bound.
- Pin a precedence order for the preflight enum in the frozen config: a model can simultaneously exhibit `COHERENCE_FAIL` and `TOOL_CALL_MALFORMED`; "exactly one value" requires a committed tie-break, not implementer choice.
- Give pairs involving a preflight-EXCLUDED model a typed disposition in the overall fork (e.g., `PAIR_NOT_EVALUATED_MODEL_EXCLUDED`) rather than absence — including the case where the re-confirmed `qwen3:14b` itself fails, which collapses all three pairs.
- State that an indeterminate think-control probe result (a qwen3.5 param whose effect cannot be adjudicated under the tiny-cap discriminator) maps to `THINK_CONTROL_NOOP`, and note that this is conservative (barred from a thinking-arm) rather than a distinct enum member — or add the distinct member now, before the probe fires.

Guardrail violations: none.

Convention violations:
- A projection that gates an expensive run is labeled by its EPISTEMIC KIND — an upper-bound feasibility check is NOT a power estimate (and vice versa); the label lives in config, code, and claim. Location: Invariant "Per-PAIR power from per-case PAIRS" + "Upper-bound honesty + typed fork"; What → PER-PAIR PRE-CHECK; AC5; Open question 2 ("state as extrapolated-upper-bound").
- Each threshold in a pre-registered decision config is derived from the test's own arithmetic, not a round guess. Location: Invariant "Frozen config before live data" (pilot-coverage threshold named but underived); AC7.

## Round-1 disposition (verified by both agents)

Claude-p confirmed each of the seven round-1 accepted changes explicitly as resolved; codex's discussion independently corroborates the same set:

1. Frozen config first — `PREREGISTERED_POOL_CONFIG_0040` committed-before-evidence, AC1 makes verdicts total pure functions over it, follows the 0036 re-registration precedent.
2. Per-case pairs, not marginal counts — resolved, and called "the strongest part of the revision" (the invariant explains why counts-only fails, and AC5's counts-identical/overlap-different fixture pins the trap shut).
3. Frozen coverage threshold — mechanism resolved (frozen, boundary-tested in AC7); only its value/derivation remains unstated (see headline-adjacent finding below).
4. Skip-not-fail + resumable driver — resolved; AC4 and the What section carry the full 0036/0039 driver posture (STOP-AND-WARN, per model+case ledger, exit 3 while work remains).
5. Multiplicity frozen outcome-blind — resolved; per-pair α with an explicit decision-theoretic rationale, recorded before pilot data.
6. Preflight enum committed, asymmetry load-bearing — resolved; EXCLUDING vs RECORDED-NON-EXCLUDING split stated with rationale, AC2 tests it.
7. Arm parity — resolved; `explorer_think=None` pinned in config, with correct NOOP-vs-exclusion handling.

## The headline finding (claude-p, correctness)

The ceiling arithmetic is conflated between two distinct quantities:

- **Proportional extrapolation of OBSERVED pilot discordance** is a point estimate of the discordance rate, not an upper bound. It is currently labeled "upper bound (max possible discordance)" with `projection_kind="upper-bound-feasibility"` — an epistemic mislabel. Consequence: a false `PAIR_UNDER_POWERED` stop becomes possible purely from sampling noise while the artifact claims the number is unimpeachable.
- **A literal max-possible-discordance bound** over the ~8 unobserved conceptual cases (7-of-15 piloted) is vacuous: 0 observed + 8 unobserved ≥ floor 8 always, so `PAIR_UNDER_POWERED` becomes structurally unreachable — the small-N trap in reverse.

**Clean resolution** (preserves everything the revision got right): pin TWO separate quantities in `PREREGISTERED_POOL_CONFIG_0040`:
1. **ceiling** = the extrapolated per-case **UNION-located** count (every case *either* model locates, assumed discordant) — a true bound, because signal discordance requires ≥1 located arm by `is_signal_discordant`'s own definition (one-oracle reuse justifies the bound). It is still computed from per-case pairs, so it does not reintroduce the marginal-counts trap (union-located is a per-case property marginals cannot recover).
2. **observed signal-discordance** (via `is_signal_discordant`) — drives `PAIR_MODELS_TOO_CLOSE` directly, and incidentally supplies the missing `UNDER_POWERED` vs `TOO_CLOSE` discriminating predicate: a pair whose ceiling clears but whose union-located cases are nearly all concordant successes is `PAIR_MODELS_TOO_CLOSE`.

**Fix spans four locations**: the "Per-PAIR power from per-case PAIRS" invariant, the "Upper-bound honesty + typed fork" invariant, the What → PER-PAIR PRE-CHECK bullet, AC5, and OQ2. Must land in spec text (not a comment) because AC1 freezes the config as the *first* implementation act — a frozen-then-wrong label is durable in committed artifacts, cheaper to fix now than to supersede later.

## Convergent secondary findings (both agents)

(a) **Pairs with a preflight-EXCLUDED model need a typed disposition** — e.g. `PAIR_NOT_EVALUATED_MODEL_EXCLUDED` — rather than absence-as-disposition. This includes the case where the re-confirmed `qwen3:14b` itself fails preflight, which would void all three pairs (codex: "AC5 still requires ceilings/verdicts for all 3 pairs and the pair enum has no MODEL_EXCLUDED/PREFLIGHT_FAILED branch"; claude-p: "absence-as-disposition is the silent-carry the spec elsewhere forbids").

(b) **14b re-confirmation should run the SAME typed preflight enum**, not an untyped check. Codex: "only the two new models have committed preflight outcomes, leaving unclear what happens if 14b serving/tool-calling regresses"; claude-p: treat 14b "with the same typed preflight machinery" as the cleanest fix, including the collapse-all-three-pairs edge case.

(c) **The four pair verdicts need a committed non-overlapping predicate order** in the frozen decision function — `INSUFFICIENT_PILOT_EVIDENCE`, `PAIR_MODELS_TOO_CLOSE`, `PAIR_UNDER_POWERED`, `PAIR_FEASIBLE` — rather than an implicit/read-time boundary (both agents independently flag the missing UNDER_POWERED/TOO_CLOSE discriminant; claude-p's ceiling-split fix above resolves the arithmetic side of this).

## Claude-p minor items (non-blocking)

- **Preflight enum precedence/tie-break**: a gibberish model will often also emit malformed tool_calls; "exactly one value" needs a committed precedence. Suggested order: `UNSERVABLE > COHERENCE_FAIL > TOOL_CALL_MALFORMED > THINK_CONTROL_NOOP > PASS` (cheapest/most-fundamental failure checked first).
- **Indeterminate think-probe result** should map to `THINK_CONTROL_NOOP` (conservative, non-excluding) rather than stalling on an outcome outside the committed answer space — state this explicitly in the enum.

**Claude-p convention violations** (both non-blocking to quorum but should be fixed alongside the headline finding):
- Epistemic-kind labeling of the projection (the headline finding itself, restated as a convention violation: "an upper-bound feasibility check is NOT a power estimate, and vice versa — the label lives in config, code, and claim").
- The coverage threshold's VALUE/DERIVATION is unstated — thresholds must derive from the consuming test's own arithmetic, not a round guess.

## Numbered action list (pre-plan edit)

1. Split the per-pair arithmetic into two pinned quantities in `PREREGISTERED_POOL_CONFIG_0040`: (i) `ceiling` = extrapolated per-case UNION-located count (true bound), (ii) `observed_discordance` via `is_signal_discordant` (drives `PAIR_MODELS_TOO_CLOSE`). Update `projection_kind` annotation accordingly. Apply across the two invariants, the PER-PAIR PRE-CHECK bullet, AC5, and OQ2.
2. Use the ceiling/observed-discordance split from #1 to state the non-overlapping predicate order for the fork: `INSUFFICIENT_PILOT_EVIDENCE` → `PAIR_MODELS_TOO_CLOSE` → `PAIR_UNDER_POWERED` → `PAIR_FEASIBLE` (or equivalent), committed in the frozen decision function.
3. State and derive the `INSUFFICIENT_PILOT_EVIDENCE` coverage threshold's value from the consuming test's own arithmetic (not a round guess) in the frozen config and AC7.
4. Add a typed disposition for pairs with a preflight-EXCLUDED member (e.g. `PAIR_NOT_EVALUATED_MODEL_EXCLUDED`) in the overall fork, explicitly covering the case where re-confirmed `qwen3:14b` fails and voids all three pairs.
5. Run the same typed preflight enum for the `qwen3:14b` re-confirmation (not an untyped check), so a 14b regression produces a typed outcome that blocks affected pairs rather than falling through to infra ambiguity or partial artifacts.
6. Pin a preflight enum precedence/tie-break order: `UNSERVABLE > COHERENCE_FAIL > TOOL_CALL_MALFORMED > THINK_CONTROL_NOOP > PASS`.
7. State that an indeterminate think-control probe result maps to `THINK_CONTROL_NOOP` (conservative, non-excluding), noted explicitly in the enum documentation.

## Action

Apply numbered edits 1–7 above to `specs/0040-pool/spec.md` (edit 1 is the load-bearing correctness fix; edits 2–7 are convergent/secondary but should land in the same pass since they touch the same invariant/AC text). Status is already `reviewed` per quorum (codex approve-with-comments) — no further review round is required to unblock planning. Proceed to `/speccraft:spec:plan` once the edits land; a third full cross-review round is optional, since the required fixes are well-specified by both round-2 reviews.

---

## Round 1 (superseded)

Round 1 verdict was **changes-requested** from both codex and claude-p (quorum not met, status remained `draft`). The round-1 synthesis identified four convergent findings — (1) missing frozen+hashed `PREREGISTERED_POOL_CONFIG_0040`, (2) per-pair ceiling under-specified as marginal counts vs. per-case pairs (claude-p framed this as a correctness/evidence-quality regression, not a style nit), (3) `INSUFFICIENT_PILOT_EVIDENCE` lacking a frozen threshold, (4) skip-not-fail vs. operator STOP-AND-WARN semantics conflated — plus claude-p-only findings on multiplicity, the preflight typed-outcome enum, and pilot arm parity. All seven consolidated round-1 actions were applied in the revision and are confirmed addressed above (with the ceiling-arithmetic fix, item 2, resolving the marginal-counts trap but introducing the new epistemic-kind conflation that is round 2's headline finding). Full round-1 detail is available in git history for this file.
