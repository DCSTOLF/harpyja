---
spec: "0026"
run: operator-pilot
date: 2026-07-06
verdict: UNDER_POWERED_STOP
ac8_config_hash: b5ffd6451a82cbb22b9cba8cbac2a61fa68ef7f5261c7436195cfa3c3547b30d
---

# Operator run — 0026 AC8 pilot (terse-query ranking instrument)

The delegated deliverable named at close: author real terse queries under the
two-model blind protocol and fire the frozen AC8 pilot over both reference subjects on
the served loopback stack. It **ran end-to-end and returned the pre-registered typed
verdict `UNDER_POWERED_STOP`** — a valid close, not a rerun-until-it-passes loop.

Artifacts (machine-local, gitignored): `eval_work/0026_pilot/{terse.pilot.jsonl,
authoring.json, findings.json}`.

## Verdict

- **`UNDER_POWERED_STOP`** — signal-bearing discordant pairs **0 / 7**, projected **0**
  flips at full size vs floor **8** (`MIN_DISCORDANT_PAIRS`, reused from the committed
  `benchmark_fit.PREREGISTERED_CONFIG`). Frozen config hash
  `b5ffd645…` recorded with the verdict.
- **Reference subjects (frozen):** `hf.co/Qwen/Qwen3-8B-GGUF:latest` (arm A) vs
  `qwen3:4b-instruct` (arm B).
- **Per-case:** all 7 authored cases → **both arms EMPTY** (astropy-12907,
  matplotlib-21568, seaborn-3069, flask-5014, requests-1142, pylint-6528, pytest-10081).
  Zero localizations on either arm → zero flips → the set cannot rank two candidates
  that both flatline.

## The blind protocol worked (layer b did its job)

Author model `hf.co/unsloth/Qwen3-16B-A3B-GGUF:latest`, verifier `qwen3.6:35b-a3b`
(separate invocations, both distinct from the subjects). Of 10 stratified cases (one per
repo):

- **7 authored** blind (gold span withheld; natural terse queries, e.g. requests-1142 →
  *"What code adds 'content-length' header to GET requests?"*).
- **1 dropped** — the **verifier flagged it leaky** (scikit-learn-10844); routed to drop,
  not a silent keep. Layer (b) caught a leak the token tripwire would not have.
- **2 excluded** by **pin (2)** — the issue TEXT itself contained the gold-span path
  (`django-12774` → `django/db/models/query.py`; `xarray-3677` → `xarray/core/dataset.py`),
  so blind authoring was impossible and the operational blindness assertion correctly
  refused to author. (A recorded, honest exclusion — not a silent drop.)

So the executable two-model guard demonstrably fired on real data: one semantic-leak
rejection + two issue-leaks-the-answer exclusions.

## Recorded operator interventions (loud, not buried)

1. **Bounded explorer budgets.** The SUT **default** budgets (12 turns / 300s wall /
   120s per-read) **WEDGED** this local model — a single case ran 60+ min at 0% CPU: a
   **dribble-slow local generation outlasts the per-socket-op timeout**, exactly the
   caveat spec 0017 recorded (`urlopen(timeout=)` is per-socket-op, NOT a total-request
   deadline). The operator run used bounded-but-fair budgets to COMPLETE:
   `lm_http_timeout_s=40, scout_max_turns=6, scout_wall_clock_s=120`. This is a
   conservative intervention (less budget → harder to localize → STOP-ward), recorded so
   the verdict is read in its light.
2. **Model circularity — named, not closed.** Author, verifier, and both subjects are all
   Qwen-family, so only STATE-independence is achieved, not CAPABILITY-independence. The
   model-independent paired-ranking floor is the mitigation (and here it is moot — zero
   flips either way).

## Interpretation (scoped, honest)

- **The pre-registered gate returned `UNDER_POWERED_STOP`:** with these two general
  candidates on this stack, the terse set produces **0 signal-bearing flips** → it cannot
  rank them. That is the deliverable.
- **Corroborates 0022/0023 `RETRIEVAL_FUNDAMENTAL` on REAL terse queries.** 0023's
  operator run saw ~79% empty on verbose SWE-bench issue text; this sees **100% empty on
  short, natural terse queries** — so the near-zero-localization floor is **not a
  query-verbosity artifact**. Rewriting the query shape (0026's whole bet) does not lift
  localization off the floor with these candidates.
- **Budget confound, stated:** the all-EMPTY result is under a 6-turn budget (the default
  wedges), so this does not cleanly isolate capability from budget. But a full-budget
  measurement is **not feasible on this stack** without fixing the total-deadline gap
  (below), and the reduced-budget signal is consistent with the pre-existing 0022/0023
  evidence. The gate's "can't rank" conclusion holds regardless of the capability/budget
  mix: if both candidates localize nothing, the instrument cannot discriminate them.

## Next step (unchanged, corroborated)

**Finder-capability retrieval work (`N38_PLUS_FINDER_CAPABILITY`, the 0022/0023
`RETRIEVAL_FUNDAMENTAL` line)** — improve the finder so Scout localization rises off the
floor, BEFORE authoring the full 20–40 terse set. Building more eval cases cannot help an
instrument whose candidates all score zero. This is NOT a rerun-until-it-passes loop, NOT
a benchmark swap, NOT a query-layer change.

## New follow-up surfaced by this run

**The explorer loop needs a TOTAL-request deadline, not only a per-socket-op timeout.**
A dribble-slow local generation wedged a default-budget run 60+ min (the per-read 120s
timeout never fired because bytes trickled). `ModelGateway.complete_with_tools` DOES bind
the per-op timeout (not a missing-timeout bug), but neither it nor the loop's
`scout_wall_clock_s` preempts an in-flight dribbling read. A total wall-clock deadline
(hard-terminable, like Deep's out-of-band subprocess kill) would let the explorer degrade
instead of wedging. Worth a small robustness spec; independent of 0026.
