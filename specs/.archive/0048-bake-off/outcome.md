# Spec 0048 — bake-off — Outcome (PRELIMINARY: operator run attempted)

**Typed outcome: `INFRASTRUCTURE_HALTED` (pre-run) — the powered ranking was NOT
produced.** The run was attempted on the dev stack; the preflight discipline (0040/0041
+ this spec's replay gate) caught two independent hard blockers *before* committing the
~9h grid. This is the designed behavior — a preflight that refuses to certify a run whose
preconditions do not hold — not a failure of the machinery, which validated end-to-end on
real model output.

Honest framing: this is NOT the `NO_SEPARATION` / model-homogeneity finding (that requires
a completed, powered run). It is a pre-run infrastructure halt. The ranking remains
unproduced and blocked, with the two blockers named and evidenced below.

## What ran, and what it proved

The full T1–T22 machine executed against the live SUT on a real, provisioned case
(`astropy__astropy-12907`, `qwen3:14b`, gated endpoint, exclusive after evicting the
foreign resident `qwen3-14b-cc:latest`):

- `run_verified_case` drove the explorer loop end-to-end, produced a terminal bucket,
  captured `serving_transport = v1-chat-completions`, and wrote a durable artifact — the
  pipeline (settings → gateway → explorer → verifier → bake-off artifact) is validated on
  real output.
- Wall-clock ≈ **350 s/case** (reasoning-on `qwen3:14b`), ~1.75× the ~200 s planning
  estimate — a full 3×53 grid projects to **~15 h**, not 9 h.

## Blocker 1 — DETERMINISM: the served models are not reproducible (replay-fail)

The spec's reproducibility replay probe double-runs a case and requires identical buckets
(the CHECKED-not-asserted determinism that lets a single draw stand in for a stochastic
one — the 0046 lesson). Observed on `astropy__astropy-12907` / `qwen3:14b`, **both runs
fully validated (no degrade, `verifier_status=PASSED`, 19/16 real turns, 8 tool calls
each — not a silent error, not a bad test case):**

| Run | Tools | Reached right file | Terminal action | Bucket |
|-----|-------|--------------------|-----------------|--------|
| 0   | glob,ls,read_span,**symbols** | ✅ `separable.py` | **prose diagnosis, never submitted** (`found-unsubmitted`) | `empty` |
| 1   | ls,read_span,**symbols** | ✅ `separable.py` | submitted `separable.py:250–287` (gold 242–248) | `right-file-wrong-span` |

→ **REPLAY-FAIL, but the divergence is precise, not chaotic:** BOTH runs navigated to the
right file; they diverged ONLY at the terminal action — run 0 dawdled into a natural-
language diagnosis and never called `submit_citations` (the 0043 found-but-unsubmitted
class), run 1 submitted a slightly-off span. This is temp>0 sampling flipping the
submit-vs-dawdle decision — under greedy decoding the same prompt → same tokens → same
terminal action → same bucket, so greedy serving is expected to make replay pass. The
served models run non-greedy by default, and the explorer's outbound params are byte-pinned
to `{max_tokens: 2048}` (0034/0038), so temperature cannot be injected per-request without
a SUT change the measurement invariant forbids. Under the frozen replay rule (any case
diverging → EXCLUDE), all three models exclude → `INFRASTRUCTURE_HALTED`.

**Defect surfaced by this validation and FIXED (measurement-invariant "any code change is
a surfaced defect with its regression test"):** the verifier writes the invoked tools into
`model_turns` but leaves the top-level `tool_names_invoked` field **null** — both runs used
`symbols`, yet the convenience field was `None`. `bakeoff_live.bakeoff_artifact_from_verifier`
had trusted that field, so it would have recorded `symbols_adopted=False` for every cell and
silently zeroed AC6's symbols-adoption metric (the 0042 uncounted-tool class). The mapper now
derives per-tool call counts from `model_turns` (cross-checked against the committed
`extract_tool_names` oracle); regression test
`test_bakeoff_artifact_derives_tools_from_model_turns_when_field_null` added; verified on the
real artifacts (both runs now `symbols_adopted=True`, exact counts).

**Fix — GREEDY serving, now VALIDATED empirically.** Serving the model greedy
(`temperature 0`, `top_p 1`) makes the explorer's single draw reproducible. Confirmed on a
greedy Modelfile variant of `qwen3:14b`:

| Case | non-greedy | greedy run 0 | greedy run 1 | verdict |
|------|-----------|--------------|--------------|---------|
| astropy-12907 | `empty` vs `RFWS` | `RFWS` (3 subs, 8 tools) | `RFWS` (3 subs, 8 tools) | **REPRODUCIBLE** (identical trajectory) |
| pytest-10081  | — | `empty` (9 tools) | `empty` (6 tools) | **REPRODUCIBLE** (bucket held; trajectory diverged) |

Greedy reproduced the BUCKET on 2/2 cases (the replay probe's criterion), fixing the
non-greedy astropy flip. Honest limit: greedy gives **bucket**-reproducibility, not always
bit-identical trajectories — the pytest greedy runs took different tool paths (9 vs 6) yet
converged to the same `empty`. Ollama retains residual numerical/batching nondeterminism;
greedy collapses it enough that outcomes reproduce, and the replay probe (bucket-level,
exclude-on-flip) is the right guard for the residual (a still-borderline model/case is
excluded, not silently trusted).

The explorer sends only `{max_tokens: 2048}` (0034/0038 byte-pin), so greedy MUST be a
**server-side default** — it cannot be injected per-request. Two adoption paths (greedy
variant tags + config re-freeze, or recreate the base tags greedy) are staged in
`serving/` (Modelfiles + README); adopting is an operator/environment decision, not applied
here. This is a serving precondition (like "the tag must be served"), verified by the replay
probe — NOT a SUT change.

## Blocker 2 — COVERAGE: the enlarged pool is unprovisioned (19 of 53 runnable)

0047 enlarged the pool 19→53 as an **authoring-time convert** — the 34 added cases exist
as terse rows (query + reachability + blind concept authoring) but were **never
materialized** into runnable inputs:

- **Worktrees:** 19 of 53 present (34 missing — the enlarged cases have no checked-out
  repo at their base commit).
- **Gold:** `expected_spans` (audited gold) covers 19 of 53 (`resolved.jsonl`); the 34
  enlarged cases carry no gold (blind-withheld / unresolved).

The 19 runnable cases are 15 conceptual / 4 lexical — eligible conceptual N ≤ 15 < the
coverage floor of 36, so a run on them types `PAIR_UNDER_POWERED` on every pair (the exact
0040 stop the enlargement existed to escape). **A powered run requires provisioning the 34
missing worktrees + gold** (clone + checkout + index each; resolve audited spans) — a
heavy, network/disk operator step.

## Provenance / integrity of the attempt

- Endpoint made exclusive (foreign `qwen3-14b-cc:latest` evicted before the run).
- All three bake-off tags (`qwen3:14b` / `qwen3:8b` / `qwen3.5:4b`) confirmed served on
  the dev Ollama (positive `/api/tags`).
- Frozen config hash `BAKEOFF_CONFIG_HASH_0048` unchanged; SUT untouched (measurement, not
  construction); 61 bake-off tests green, ruff clean.
- Pool sha256 provenance `385107934f61…` intact; the train-on-test confound does not apply.

## To produce the ranking (both required, in order)

1. **Greedy serving** — VALIDATED (`serving/` Modelfiles); adopt one path, re-freeze the
   config if using variant tags, then pass the formal 3-case×2 replay preflight.
2. **Provision the 34 enlarged cases** — worktrees (checkout + index) + audited gold
   (`resolved.jsonl` covers only the 19 pinned; the enlarged 34 need spans resolved).
3. Then launch `harpyja/eval/run_bakeoff.sh` (detached, resumable, ~15 h projected) and
   author the ranking from `outcome.json`.

Until both hold, the bake-off is `INFRASTRUCTURE_HALTED` (pre-run) — powered ranking
pending infrastructure, per the reliability invariant that a run withholds its verdict
rather than report a non-exclusive / non-reproducible / under-covered one.
