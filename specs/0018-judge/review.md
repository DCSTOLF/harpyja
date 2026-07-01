# Review — Spec 0018 "judge"

Reviewers: `codex` (codex-cli, `codex exec --full-auto`, model gpt-5.5), `claude-p`
(local `claude -p`)
Synthesis: cross-reviewer + orchestrator source-verification

## Round 1 (2026-07-01)

| Reviewer | Verdict |
|----------|---------|
| claude-p | **approve-with-comments** |
| codex | **changes-requested** → folded (see below) |

**Quorum (≥1 approve / approve-with-comments): MET** (claude-p). Status → `reviewed`.

Both reviewers agreed the **direction is correct and source-verified**: moving the
gate judge off the OOD `scout_model` finder onto the served `lm_model` instruct model,
preserving the air-gap through `ModelGateway.complete`, and making a non-conforming
score **degrade rather than fabricate** all align with the repo's no-false-capability
and graceful-degrade rules. No guardrail violations from either reviewer. The reviews
converged on a single tightening theme — *the spec must be internally closed before
implementation*: resolve the open questions into decisions, make the degrade/logging
mechanics exact, pin the parser grammar, and name two couplings. **All convergent
load-bearing items were folded into `spec.md` before marking `reviewed`**, which
resolves codex's `changes-requested`.

### Folded — the convergent load-bearing items

1. **Open questions reopened implementation-affecting decisions (codex #1 + claude-p
   #4).** OQ2 pinned AC5's conform/non-conform boundary and OQ3 pinned what AC6
   asserts, so leaving them open made the spec internally unstable. **Fold:** all three
   promoted to decisions — **D5** retain `scout_model` (OQ1), **D6** `0, because…`
   degrades rather than parsing a leading `0` (OQ2), **D7** whole-gate degrade on a
   non-conforming reply (OQ3). Both reviewers independently recommended these same
   resolutions. The `## Open questions` section now records the resolution, none open.

2. **Logging could double-emit; needs a typed exception (codex #2 + suggestion 2).**
   As written, D2 raised into the *generic* gate `except` while D4/AC7 demanded a
   *distinct* warning — so a parse failure could emit **both** the new non-conformance
   WARNING and the generic `scoring failed` WARNING, weakening the diagnostic contract.
   **Fold:** D4 now specifies a typed **`ScoreParseError`** (`ValueError` subclass);
   `verify`'s `except` branches on it **first** and emits **exactly one** WARNING; AC7
   now asserts the generic message is **absent** for a `ScoreParseError`. This mirrors
   the existing 0017 timeout branch precisely.

3. **Parser grammar was not exact enough to implement (codex #3 + suggestion 3).**
   **Fold:** D2 states a normative conforming grammar (optional `Score:` label → a
   single number → optional trailing period → nothing else, value in `[0,1]`), and AC5
   is now an **executable boundary table** covering every codex case: `1.0`, `0.0`,
   `1.`, `Score: 0.8.`, `0, because…`, `1.2`, `-0.1`, `Score: 219`, `""`, `n/a`. The
   elegant unifier: an out-of-range number (a line-number `219` or `1.2`) is
   non-conforming → `None`, so the B2 regression and the range check are one rule.

4. **`_parse_score` is shared plumbing — enumerate the second caller (claude-p
   convention_violation #1).** The strict parse also feeds the *retained*
   `make_scout_model_judge`, so it changes the finder judge's behavior too (it now also
   degrades on `None`). That is desirable, but the type-shape-change convention requires
   the second caller get its own assertion. **Fold:** Change 2 states the two-caller
   blast radius; new **AC13** asserts both factories degrade identically on `None`.

5. **`lm_model` is now dual-consumer — state the coupling (claude-p
   convention_violation #2).** Before this spec `lm_model` = Deep's model; after it,
   `lm_model` = Deep's model **and** the gate judge — the exact one-value-two-subsystems
   situation the repo codified for `scout_model` in 0016. **Fold:** D1 now names the
   coupling explicitly (a future `lm_model` tune for Deep silently retunes the gate) and
   notes `lm_model` is itself provisional (0016 "for now" Qwen3-8B), so the judge
   inherits a provisional default.

6. **Honesty: "mechanism fixed" ≠ "B2 closed" (claude-p #3).** Every accuracy-bearing
   AC (AC10 fake score, AC11 skip-not-fail smoke) is honestly disclaimed as plumbing, so
   the spec fixes the *mechanism* but cannot itself demonstrate astropy-12907 now passes
   — that needs a calibrated threshold (the OQ2 re-run). **Fold:** a "Honest scope"
   paragraph in Why, an AC10 distribution/operating-point caveat, and AC12 now mandates
   the changelog say **"B2 *mechanism* fixed; end-to-end accuracy deferred to the OQ2
   re-run,"** never "B2 closed."

### Also folded (claude-p suggestions)

- **Prompt-vs-parse asymmetry stated as intentional** — AC4 demands a bare number while
  AC5 tolerates a `Score:` label / trailing punctuation; Change 2 now calls this
  belt-and-suspenders leniency out so it doesn't read as a contradiction.
- **fast-mode degrade behavior noted** — in `mode=fast` there is no Deep to escalate to,
  so a non-conformance degrade surfaces informationally as `gate-scoring-failed`
  (inherited, unchanged) rather than escalating — still no false *reject*.

## Plan-level items (carry to `/speccraft:spec:plan`, not spec blockers)

- Finalize the exact `_parse_score` regex against AC5's table; decide the precise
  tolerance for the `Score:` label and a single trailing period.
- Introduce `ScoreParseError` in `gate.py`; wire the `verify` `except` to branch on it
  first (before the 0017 timeout branch and the generic branch); assert single-emit.
- Add the `_JUDGE_FACTORIES` / dispatch in `build_verification_gate` keyed on
  `settings.verify_method`; keep the two-arg judge signature.
- `make_instruct_judge`: constrained system+user prompt; pass `model=settings.lm_model`,
  `temperature=0`; RED first via a captured-`model` spy.
- Confirm the instruct-judge prompt reads sensibly against a live Qwen3-8B at
  implementation time (AC11 smoke), without asserting accuracy.

## Action recommendation

**Reviewed — proceed to `/speccraft:spec:plan`.** The core B2 fix (instruct-model judge
+ strict non-fabricating parse, letting the *existing* gate catch fire) is correct and
source-verified; the six convergent items — most importantly the OQ→decision closure
(D5/D6/D7), the typed-exception single-warning contract (D4/AC7), the executable parser
table (AC5), and the two named couplings (shared `_parse_score` AC13, dual-consumer
`lm_model` D1) — are folded, so the spec is now internally closed and review-hookable.
Honesty is tightened so nothing claims B2's accuracy is *proven* — only that the
mechanism is fixed and the proof is deferred to the OQ2 re-run.
