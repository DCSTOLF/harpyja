# Spec 0039 — thinking A/B: findings

## Outcome: `UNDER_POWERED_STOP` at the AC5 gate — the typed stop is the deliverable

The pre-registered upper-bound feasibility pre-check (`ab_power_precheck`, committed
0036 evidence, frozen config `PREREGISTERED_AB_CONFIG_0039`) fired
**UNDER_POWERED_STOP** before any live arm fired:

- The committed 0036 pilot covered only the **first 10 of 19** cases; **7** are
  conceptual — the projectable subset is smaller than the stratum (15).
- The pinned arm (`qwen3:14b`) located **3 of 7** piloted conceptual cases
  (astropy-12907, requests-1766, scikit-learn-10844 — right-file-or-better per the
  committed 0026 oracle).
- Projected signal-bearing discordant **upper bound** over the full conceptual
  stratum: round(15 × 3/7) = **6 < 8** (the frozen floor, fixed-not-re-derivable).
- The projection is an **upper-bound feasibility check, not a power estimate**: the
  pilot measured cross-MODEL discordance (14b vs 4b-instruct), which BOUNDS but
  cannot estimate within-model think-flip rates — every located case was generously
  assumed to flip, and a same-model contrast flips far fewer. Even the ceiling
  cannot reach the floor.

Consequence (the 0026 gate-before-spending discipline): the ~4h paired live run was
**correctly NOT spent**. The live paired-run path (AC6's PROCEED branch) is
**N/A-on-branch**; the committed driver (`run_thinking_ab.sh`) exits with the typed
stop (exit 2, distinct from infra STOPs), and the committed claim
(`claim.json`, schema `0039/1`, pinned to computed truth by
`test_committed_ab_claim_matches_computed_verdict`) records it.

**Named next step:** the 0036 pool-enlargement audited convert step — enlarge the
blind-clean pool past 19 (the 50-case raw pool is exhausted), THEN re-run this
spec's pre-check; the PROCEED branch (runner, ledger, driver, split report) is
built and auto-activates when the committed evidence flips the gate.

## Causation stance (AC8)

- The think-experiment (N=2; run 2's first-ever right-file + first-ever `symbols`
  use) is cited as **motivation only** — it established no causation, and nothing
  in this spec's outcome upgrades it.
- This spec's verdict machinery is the first POWERED read design — and its honest
  answer is that the current data CANNOT power the conceptual-stratum question:
  N=15 conceptual, floor 8, projected ceiling 6. UNDER_POWERED is a typed outcome,
  not a null: **no claim that thinking does or does not help is made**.
- **No default flip is decided here.** `explorer_think=None` (default-on) remains
  shipped; the flip decision follows a future powered verdict, as its own spec.
- The observational True(`high`) arm was **not run** (no live run occurred on the
  gated branch); when the A/B becomes constructible it remains observational-only,
  never part of the paired verdict.

## Instrument notes (durable for the re-run)

- **Arms**: the paired contrast is **None(default-on) vs False(off)** — the
  decision-relevant pair (the follow-up decision is literally None → False), both
  behaviorally proven distinct by 0038 (852–3457 reasoning chars/turn vs 0).
- **Arm distinctness** is guarded per pair, two-factor, from the artifact
  (`classify_pair_validity`): off-arm reasoning present → instrument defect →
  excluded-and-recorded (rate above the frozen ceiling → CONFOUNDED); an on arm
  showing no reasoning is KEPT — legitimate shipped-None behavior (deliberate
  asymmetry; do not "fix" into symmetry). Factor (b) (budget indistinctness) bites
  only when the on arm reasoned substantially (≥256 chars) yet the off arm burned
  an indistinguishable completion budget — the hidden-thinking signature.
- **Seed**: the config records a fixed per-repeat seed schedule with
  `seed_honoring="unverified"`. The driver carries a two-call probe
  (`seed_honoring_probe`) for the endpoint; additionally the explorer's request
  path does not currently carry `seed` at all (only `max_tokens` /
  `reasoning_effort`), so even an endpoint-honored seed is NOT requested by the
  production path — the paired-per-repeat seed property remains a recorded
  aspiration, never asserted provenance (the 0037 lesson). Wiring `seed` into
  `ExplorerBackend` would be a SUT change for the re-run spec to consider.
- **Degrade asymmetry**: the on-arm reasoning tax against `explorer_max_tokens=2048`
  is a predictable CONFOUNDED input; the pre-check surfaces it as a warning
  (per-turn artifacts durable-but-not-committed were unavailable to project a
  fraction — recorded honestly, not silently) and the verdict machinery trips
  CONFOUNDED on per-arm typed-degrade asymmetry above the frozen threshold.
- The lexical stratum (N=4) is typed `STRATUM_UNDER_POPULATED` in the split
  report — described, never verdicted, never implied comparable.
