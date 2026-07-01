# Spec 0018 — judge — changelog

Fixes the **B2** finding from spec 0015 (`live-run-findings.md`, D2): the Verification
Gate's relevance judge was category-wrong and its score parse was noise, so the gate
**false-rejected correct citations** (astropy-12907 cited the right file and got
`gate-low-confidence`). This is the last of the three 0015 blockers (B1 → 0016, B3 →
0017).

> **Honest scope (no-false-capability):** this fixes the judging **mechanism**;
> end-to-end accuracy (that astropy-12907 now *passes*) is **deferred to the OQ2 re-run**,
> which needs a calibrated `verify_threshold` over the new score distribution. B2's
> mechanism is fixed — the false-rejection is not yet *demonstrably eliminated*, only made
> possible to eliminate. **Not** "B2 closed."

## What shipped

- **Instruct-model judge (D1).** The gate scores relevance with `settings.lm_model`
  (the served Qwen3-8B instruct model — in-distribution for "rate 0.0–1.0") via the new
  `make_instruct_judge` (`orchestrator/gate.py`), replacing the reuse of the OOD
  `scout_model` finder fine-tune. The judge sends a **constrained bare-number prompt**
  and passes `model=settings.lm_model, temperature=0` to `ModelGateway.complete`.
- **`verify_method` is now a real selector (D3).** `_VERIFY_METHODS =
  {"scout_model", "instruct_model"}`; the default **flips** to `instruct_model`
  (`config/settings.py`). `build_verification_gate` (`orchestrator/wiring.py`) dispatches
  via `select_judge` (`orchestrator/gate.py`, a `_JUDGE_FACTORIES` registry co-located
  with the factories). The finder judge is **retained** (non-default) as the
  finder-vs-instruct A/B baseline (D5).
- **Strict, non-fabricating parse (D2).** `_parse_score` is now `float | None`
  (`orchestrator/gate.py`): a conforming reply is a bare `[0,1]` score (an optional
  `Score:` label and a single trailing period tolerated); an out-of-range number
  (`219`, `1.2`, `-0.1`), a bare line number, prose-after-number (`0, because…`), or no
  number returns `None`. A `None` makes the judge raise the new typed `ScoreParseError`
  and the gate degrades (`failed=True`) — it never fabricates a `1.0` pass from a line
  number or a `0.0` reject from prose (D6, prefer escalate-over-reject). Both judge
  factories share `_score_or_raise`, so they degrade **identically** (AC13).
- **Whole-gate degrade (D7).** A single non-conforming reply degrades the whole
  `verify` call (a model not following the bare-number instruction is suspect for the
  batch); per-span abstain is a deferred refinement.
- **Distinct, single-emit visibility (D4).** `VerificationGate.verify`'s `except`
  branches on `ScoreParseError` **first — because it subclasses `ValueError` and would
  otherwise fall through to the generic branch** — and logs exactly **one** distinct
  WARNING ("verification gate score parse non-conforming: …"): no double-emit of the
  generic "scoring failed" message, and distinct from the 0017 timeout WARNING.
  Log-signal only, no schema change.
- **Stated coupling.** `lm_model` now backs **both** Deep (Tier 2) and the gate judge —
  documented in the `settings.py` comment, `ARCHITECTURE.md` §2.7, and the README so a
  future `lm_model` tune for Deep is known to also retune the gate. `lm_model` remains
  provisional (0016 "for now" Qwen3-8B).
- **Docs.** `settings.py` comment, `gate.py` docstrings (instruct judge + strict-parse /
  `ScoreParseError` contract), `ARCHITECTURE.md` §2.7 Verification-Gate rewrite, and the
  README Configuration note — each stating this is a judging-*mechanism* fix, not a
  calibration change.

## Tests

- `config/test_settings.py`: `instruct_model` accepted, default-flip via field
  **introspection** (not a grep), `_VERIFY_METHODS` membership, `scout_model` still
  accepted, unknown still rejected (AC1, AC2).
- `orchestrator/test_gate.py`: strict `_parse_score` **executable boundary table**
  (conforming + non-conforming incl. `219`/`Score: 219`/`1.2`/`-0.1`/`0, because…`/
  `""`/`n/a`, AC5); instruct judge scores via `lm_model` not `scout_model` at temp 0
  (AC3); bare-number prompt contract (AC4); `assert_local`-before-egress (AC9);
  non-conformance degrades-not-fabricates + whole-gate (AC6); **single** distinct
  non-conformance WARNING with the generic message asserted **absent** and distinct from
  timeout, on the record message not `caplog.text` (AC7); both judges degrade
  identically (AC13); the inverted-harm regression — a correctly-scored correct citation
  now **passes** (AC10, plumbing not accuracy).
- `orchestrator/test_wiring.py`: `build_verification_gate` dispatches `instruct_model`
  by default (calls `lm_model`) and `scout_model` on request (calls `scout_model`) (AC8);
  the 0017 loopback / timeout-threading tests still pass.
- Optional `@pytest.mark.integration` live instruct-judge smoke — parseable `[0,1]`
  score from a served `lm_model`, **skip-not-fail**, explicitly NOT an accuracy claim
  (AC11).

**757 unit pass** (+32 over the 725 baseline), ruff clean.

## Out of scope (unchanged)

Gate **calibration** (`verify_threshold` / `verify_top_n`) is the OQ2 re-run's job;
escalation policy, a deterministic lexical judge, model footprint / co-residency,
constrained-decoding score extraction, and per-span non-conformance abstain are
follow-ups. The **OQ2 re-run** is a fresh spec now that B1 (0016) + B2 (this) + B3
(0017) are all fixed.
