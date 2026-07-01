---
id: "0018"
title: "judge"
status: closed
created: 2026-07-01
authors: [claude]
packages: [harpyja/orchestrator, harpyja/config]
related-specs: ["0008", "0015", "0016", "0017"]
---

# Spec 0018 — judge

Fixes **B2** from spec 0015 (`live-run-findings.md`, D2): the Verification Gate's
relevance judge is category-wrong and its score parse is noise, so the gate
false-rejects **correct** citations (the AC4 "gate false-escalation" phenomenon).

## Why

The Verification Gate exists to catch a *bad* Scout answer and escalate. In the
0015 live run it did the opposite — it **rejected a correct answer**. Two distinct,
source-verified defects in the gate's judging logic:

1. **Out-of-distribution judge model.** `make_scout_model_judge`
   (`harpyja/orchestrator/gate.py:68`) reuses `scout_model` — a FastContext
   citation-*finder* fine-tune — as a relevance *scorer*, via a plain chat prompt
   ("reply with a single number 0–1"). Scoring is out-of-distribution for a finder
   model, so its numeric replies are essentially noise, biased toward rejecting
   correct answers. Evidence (0015): **astropy-12907 cited the correct file**
   (`separable.py`, the real bug location, 3 valid spans) and the gate returned
   **`gate-low-confidence`**.

2. **Fragile score parse.** `_parse_score` (`harpyja/orchestrator/gate.py:93`) does
   `re.search(r"[0-9]*\.?[0-9]+", reply)` — it grabs the **first number anywhere in
   the reply** and clamps to `[0,1]`. A reasoning reply that mentions a line number
   ("…at line 219…") scores `219 → clamp 1.0` (a fabricated *pass*); "0, because…"
   scores `0` (a reject). The signal a citation's fate rides on is arbitrary.

This is a **gate-quality** fix — a change to the judging *mechanism*. It is the
third and last of the three 0015 blockers (B1 shipped in 0016, B3 in 0017), and a
prerequisite for a trustworthy OQ2 re-run: calibrating `verify_threshold`/
`verify_top_n` over a gate whose relevance signal is noise would be measuring gate
dysfunction, not gate tuning (0015 AC5 `gate_quality_confounded`).

Enabler: spec 0016 flipped `lm_model` from the llama.cpp placeholder `"local"` to a
**served** instruction-following model (`hf.co/Qwen/Qwen3-8B-GGUF:latest`). A real
instruct model — in-distribution for "rate 0.0–1.0" — is now available to be the
judge. That is the chosen fix direction.

**Honest scope (no-false-capability).** This fixes the judging *mechanism*; it does
not, by itself, *demonstrate* that astropy-12907 now passes end-to-end — that needs a
calibrated `verify_threshold` over the new instruct-model score distribution, which
is the OQ2 re-run's job. B2 is thereby made *fixable*; the accuracy proof is deferred
(reflected in AC12's changelog wording — "mechanism fixed," never "B2 closed").

## What

Two coordinated changes to the gate's judging logic, plus the config surface that
selects it. **Scope is the two named defects only** — not gate calibration, not
escalation policy.

**Change 1 — the judge is an instruct model, not the finder (D1).** Introduce a new
`verify_method = "instruct_model"` (the new default) backed by a new
`make_instruct_judge(gateway, settings)` that scores via `settings.lm_model` (the
served Qwen3-8B instruct model), with a **constrained prompt** that demands a bare
`[0,1]` number as the entire reply. `verify_method` finally *selects* the judge:
`build_verification_gate` dispatches on it (D3). The existing
`make_scout_model_judge` (over `scout_model`) is **retained** as the still-accepted,
non-default `verify_method = "scout_model"`, so a future OQ2 A/B (finder vs instruct)
needs no resurrected code.

**Change 2 — strict parse, honest degrade (D2).** `_parse_score` becomes strict:
it returns a `[0,1]` float only for a **conforming** reply (a bare score, whitespace
and an optional `Score:` label / trailing punctuation tolerated) and **`None`** for
anything else — including a bare line-number integer (`219`), an out-of-range value
(`1.2`, `-0.1`), and chatty replies. A `None` parse is a **non-vouch**: the judge
raises a typed `ScoreParseError`, the gate's *existing* `except → GateOutcome(
failed=True)` fires (the same "make the un-raisable raisable" move as 0017/B3), and
the gate degrades — it **never fabricates** a score (neither a `1.0` pass nor a `0.0`
reject) from an unparseable reply. On ambiguity the gate prefers to
**degrade-and-escalate over reject** — the 0015 harm was false rejection.

`_parse_score` is **shared plumbing**: both the new instruct judge and the retained
`scout_model` judge call it, so the strict contract changes **both** — the retained
finder judge now also degrades (not fabricates) on a non-conforming reply. That
two-caller blast radius is intended and is asserted for both (AC13). The prompt
(AC4, bare number) and the parse (AC5, tolerant of a `Score:` label / trailing
punctuation) are deliberately **asymmetric** — belt-and-suspenders for model drift,
not a contradiction. In `mode=fast` there is no Deep to escalate to, so a
non-conformance degrade surfaces informationally as `gate-scoring-failed` (inherited
orchestrator behavior, unchanged) rather than escalating — still no false *reject*.

**Visibility (D4).** Extending the 0014/0017 convention, the non-conforming-reply
degrade emits **exactly one** distinct WARNING naming the parse non-conformance,
separable in operator diagnostics from the 0017 timeout WARNING and — critically —
**not** doubled by the generic scoring-failure WARNING. Log-signal only, via a typed
exception; no schema change.

Air-gap, read-only, and graceful-degrade guarantees are untouched: the instruct
judge still routes through `ModelGateway.complete` (which `assert_local`s before any
egress), and a failed/degraded gate still escalates in `auto` exactly as before.

### Decisions

- **D1 — Instruct-model judge.** The gate judges relevance with `settings.lm_model`
  (served Qwen3-8B instruct, an in-distribution 0–1 scorer), **not** `scout_model`
  (a finder fine-tune, OOD). The judge passes `model=settings.lm_model` explicitly to
  `complete()` (parallel to how `make_scout_model_judge` passes `scout_model`).
  **Coupling (stated, per the dual-consumer convention).** `lm_model` already backs
  Deep (Tier 2); this makes it *also* back the Verification Gate — one Settings value,
  two subsystems (mirrors 0016's `scout_model` dual-consumer note). A future tune of
  `lm_model` for Deep would silently retune the gate judge, so callers must treat it as
  shared. `lm_model` is itself provisional (0016 "for now" Qwen3-8B), so the judge
  inherits a provisional default.
- **D2 — Strict parse + non-fabricating degrade.** `_parse_score(reply) -> float |
  None`. Conforming grammar (normative; exact regex finalized at plan): optional
  `Score:` label, then a **single** number, an optional trailing period and
  whitespace, and **nothing else**, with the number in `[0,1]`. Everything else →
  `None`: prose after the number (`0, because…`), an out-of-range value (`1.2`,
  `-0.1`), a bare line-number (`219`, `Score: 219`), or no number. A `None` never
  becomes a fabricated `1.0`/`0.0`; the judge raises `ScoreParseError` and the gate
  degrades (`failed=True`). Prefer escalate-on-ambiguity over reject-on-ambiguity.
- **D3 — `verify_method` becomes a real selector; retain `scout_model`.**
  `_VERIFY_METHODS = {"scout_model", "instruct_model"}`; default flips to
  `"instruct_model"`. `build_verification_gate` dispatches to the matching judge
  factory. Retaining the finder method (non-default) preserves the 0008 pluggable-seam
  intent and enables a future finder-vs-instruct A/B without un-reverting code.
- **D4 — Non-conformance visibility via a typed exception; single warning.** A
  `_parse_score → None` makes the judge raise a typed `ScoreParseError` (a
  `ValueError` subclass). `VerificationGate.verify`'s existing `except` branches on it
  **first** and emits exactly **one** distinct WARNING naming the non-conformance — it
  must **not** also emit the generic `verification gate scoring failed` WARNING (no
  double-emit), and it stays distinct from the 0017 timeout WARNING. Log-signal only;
  no structured degrade-cause schema (as in 0017).
- **D5 — Retain `scout_model` (resolves OQ1).** Both reviewers concur: it costs one
  dispatch branch, honors the 0008 seam, and is the exact finder-vs-instruct A/B
  baseline the OQ2 re-run will want; deleting it would force a resurrection.
- **D6 — Parse boundary is "exactly a bare score, else degrade" (resolves OQ2).**
  `0, because…` → `None` (degrade), **not** a parsed leading `0`. Rationale:
  escalate-over-reject (the 0015 harm was false rejection), and a chatty reply signals
  the model is not following the bare-number instruction, so its number is not
  trustworthy as a score.
- **D7 — Whole-gate degrade on non-conformance (resolves OQ3).** A single
  non-conforming reply raises → the whole gate degrades (`failed=True`) for that
  `verify` call. Rationale: a model not following the bare-number instruction is
  suspect for the entire batch; simpler and honest-safe. Per-span abstain (score the
  conforming spans, drop the non-conforming one) is a deferred future refinement if the
  OQ2 re-run shows whole-gate degrade costs recall.

## Acceptance criteria

1. **New method accepted; old retained; unknown still rejected.** `Settings(
   verify_method="instruct_model")` loads clean; `Settings(verify_method="scout_model")`
   still loads clean; an unsupported value still raises `UnsupportedVerifyMethod`
   loudly at construction. `_VERIFY_METHODS == {"scout_model", "instruct_model"}`.

2. **Default flips to the instruct judge (introspection, not a grep).** The
   `Settings.verify_method` **field default** is `"instruct_model"`, asserted via
   dataclass-field introspection (`fields(Settings)` / a default construction), so the
   test guards drift rather than matching a source string.

3. **The instruct judge scores via `lm_model`, not `scout_model`.**
   `make_instruct_judge(gateway, settings)` returns a judge whose `complete()` call is
   made with `model == settings.lm_model` and `temperature == 0` — asserted by
   capturing the `model` argument (monkeypatched `complete`/transport). It must **not**
   pass `settings.scout_model`.

4. **The judge prompt demands a bare `[0,1]` number.** The messages the instruct judge
   sends constrain the reply to only a number in `[0,1]` (no prose) — asserted on the
   captured prompt text (a stable, greppable instruction contract).

5. **Strict parse — executable boundary table.** `_parse_score(reply) -> float | None`:
   - conforming → the value: `"0.8" → 0.8`, `"0.0" → 0.0`, `"1.0" → 1.0`, `"1" → 1.0`,
     `"0" → 0.0`, `"1." → 1.0`, `"Score: 0.8" → 0.8`, `"Score: 0.8." → 0.8`,
     `"  0.42  " → 0.42`;
   - non-conforming → `None`: `"219"`, `"…at line 219…"`, `"Score: 219"` (line number /
     out of range — the exact B2 regression, must NOT clamp to `1.0`); `"1.2"`, `"-0.1"`
     (out of `[0,1]`); `"0, because the span is unrelated"` (prose after the number, D6);
     `""`, `"n/a"` (no number).

6. **A non-conforming reply degrades, never fabricates.** A `_parse_score → None`
   makes the judge raise `ScoreParseError`; `gate.verify(...)` returns
   `GateOutcome(failed=True, passed=False)`, never raises out of `verify`, and never
   returns a fabricated pass (`1.0`) or a line-number-derived score. Per D7 a single
   non-conforming reply degrades the whole gate for that call.

7. **Exactly one distinct non-conformance WARNING (no double-emit).** The
   non-conformance degrade logs **one** WARNING naming the parse non-conformance,
   asserted on the log **record message** (not `caplog.text`/exc_info — the 0017
   lesson). It is distinct from the 0017 timeout WARNING, and the generic
   `verification gate scoring failed` WARNING is asserted **absent** for a
   `ScoreParseError`.

8. **`build_verification_gate` dispatches on `verify_method`.** With default settings it
   builds the instruct judge over `lm_model`; with `verify_method="scout_model"` it builds
   the retained `make_scout_model_judge` over `scout_model`. Asserted by capturing which
   model the constructed gate's judge would call (or which factory was selected).

9. **Air-gap preserved (parallel to 0017 AC9).** The instruct judge's `complete()` still
   calls `assert_local()` **before** any egress; a non-loopback gateway (`allow_remote=
   False`) raises `AirGapError` and the judge model is never called.

10. **Correct citation with a good score passes (the inverted-harm regression).** A
    lined citation whose (faked) judge reply is a well-formed score `≥
    settings.verify_threshold` (the current `0.6` default) yields `GateOutcome(
    passed=True, failed=False)` — the gate passes a correctly-scored correct citation
    through the new plumbing (fake judge/transport; not a live-model accuracy claim).
    Caveat (no-false-capability): the instruct model's score *distribution* differs from
    the finder's, so `0.6` is now an untested operating point — its calibration is the
    OQ2 re-run's job, not this spec's.

11. **(integration, skip-not-fail) Live instruct-judge smoke.** With a served `lm_model`,
    `make_instruct_judge` returns a **parseable** `[0,1]` score for a trivially relevant
    span. `@pytest.mark.integration`; skips (never fails) when the endpoint/model is
    absent. Explicitly a wiring/parse smoke — **not** an accuracy or calibration claim.

12. **Blast-radius docs + honest changelog (no-false-capability).** `settings.py` comment
    (the `verify_method` default flip + the `lm_model` dual-consumer coupling), `gate.py`
    docstrings (judge is the instruct model; the strict-parse-degrade + typed
    `ScoreParseError` contract), `ARCHITECTURE.md` Verification-Gate note, README if it
    names the gate model, and a spec `changelog.md` B2 entry. The changelog must state
    **"B2 *mechanism* fixed; end-to-end accuracy (astropy-12907 passes) deferred to the
    OQ2 re-run"** — never "B2 closed" / "false-rejection eliminated." State throughout
    that this is a judging-*mechanism* fix, not a calibration/threshold change.

13. **Both judge factories share the strict parse.** `_parse_score` is called by both
    `make_instruct_judge` and the retained `make_scout_model_judge`; a non-conforming
    reply degrades **identically** under both (one grep surfaces both callers; each
    None-degrade path is asserted, so the retained finder judge cannot silently keep the
    old fabricating behavior).

## Out of scope

- **Gate calibration** — tuning `verify_threshold` / `verify_top_n`. That is the OQ2
  re-run's job; this spec fixes the judging *mechanism*, not its operating point.
- **Escalation policy** — how the orchestrator reacts to a failed/low gate (escalate in
  `auto`, flags) is unchanged.
- **Per-span non-conformance abstain** — D7 chose whole-gate degrade; scoring the
  conforming spans and dropping only the non-conforming one is a possible future
  refinement, deferred.
- **A deterministic lexical judge** (`verify_method="lexical"`, no model on the gate) —
  considered and not chosen; a plausible future method behind the same selector.
- **Model footprint / co-residency** — the gate now calls `lm_model` alongside Scout's
  `scout_model`; on a constrained host this can cause Ollama model-swap thrash. Tracked
  with the Q8 / 8 GB footprint work, not addressed here.
- **Constrained-decoding score extraction** (logit-bias / single-token numeric forcing) —
  a future parse-hardening beyond a strict regex.
- **Deep's own judging** and any change to `scout_model` / Scout retrieval.
- **The OQ2 re-run itself** — a fresh spec now that B1+B2+B3 are fixed.

## Open questions

_All three resolved into decisions during review (2026-07-01): OQ1 → **D5** (retain
`scout_model`), OQ2 → **D6** (`0, because…` degrades, not a parsed `0`), OQ3 → **D7**
(whole-gate degrade on a non-conforming reply)._
