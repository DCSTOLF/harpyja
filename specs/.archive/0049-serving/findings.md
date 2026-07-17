# Findings — 0049 serving (greedy serving, path A)

## Typed outcome (AC6)

**`RESIDUAL_NONDETERMINISM`** — greedy does NOT give bucket-level reproduction. On
the ≥3-draw × 3-tag × 2-case/2-repo replay (live, 0041-gated, exclusivity-clean),
**all three greedy tags flip a bucket** within a cell:

| Tag | astropy-12907 | django-12774 | Per-tag |
|---|---|---|---|
| `qwen3-14b-greedy` | RFWS, RFWS, RFWS ✓ | correct, correct, **empty** ✗ | `RESIDUAL_NONDETERMINISM` |
| `qwen3-8b-greedy` | empty, empty, **RFWS** ✗ | correct, correct, correct ✓ | `RESIDUAL_NONDETERMINISM` |
| `qwen3.5-4b-greedy` | empty, empty, empty ✓ | correct, correct, **empty** ✗ | `RESIDUAL_NONDETERMINISM` |

Global outcome per AC6 (any single cell flip → global): **`RESIDUAL_NONDETERMINISM`,
per-tag reported — all three blocked from the bake-off.** No degrades on the flip
draws (`degrade=None`) — these are clean runs producing different buckets, not
timeout/wall-clock artifacts. Committed proof artifact: `replay_proof.json`
(drift-pinned `sha256 4bfe8679…`, config hash `82885d1b…`).

### Named source (AC6 requires it) — NOT sampling, NOT the dropped seed/top_p

The flips are a **serving-stack decoding numerical nondeterminism**, not sampling.
Mechanism (visible in `submission_outcome`): at temperature 0 the same (model, case)
flips its **terminal submit-vs-find** decision across draws — 14b/django
`submitted → found-unsubmitted`, 8b/astropy `never-found → submitted`, 4b/django
`submitted → never-found`.

**Seed-pin refutation (confirmatory, the load-bearing test).** Hypothesis: the
temperature-only Modelfile dropped 0048's `seed 0` + `top_p 1`, and those are
load-bearing for determinism. REFUTED: a diagnostic tag rebuilt with 0048's exact
config (`temperature 0 + top_p 1 + seed 0`) re-run on the flipping cell
(14b/django, 3 draws) produced **`correct, correct, empty` — the SAME flip**. So
seed/top_p pinning does NOT restore reproduction; the source is deeper than the
sampler (Ollama/llama.cpp batch/KV-cache numerical nondeterminism that, at a
decision boundary, cascades a flipped logit into a different terminal action).

**Consequence for 0048.** 0048's "greedy reproduces" (2 cases: astropy, pytest)
was a **stable-cell coincidence**, not a general property — those cases sit off the
submit/find decision boundary. The ≥3-draw × per-tag discipline (the 0049 tightening
over 0048's 2-draw) caught what 2 draws by construction could not: a 2-draw proof
would have FALSELY passed 14b/django (correct==correct) and 8b/astropy (empty==empty);
the third draw flipped both.

**The bake-off stays BLOCKED.** Greedy serving is not sufficient for the single-draw
bucket reproducibility the bake-off's discordance comparison requires, and it is not
fixable by a serving-config tweak. Paths forward (own spec): a genuinely
deterministic backend (batch-invariant kernels / single-request serialization / a
different runtime), OR abandon single-draw and adopt multi-draw majority-bucket
(the deployment-realistic direction the control-not-deployment caveat already flags).

## AC1a — chain-of-custody finding (VERIFIED LIVE, then RESOLVED)

The 0048 hand-created `qwen3-14b-greedy` **diverged from the committed
temperature-only Modelfile** — live `ollama show` vs base `qwen3:14b` (tolerant
extractor): `delta = {seed, temperature, top_p}` (it kept 0048's top_p 1 + seed 0).
Per AC1a STOP-AND-WARN → DISCARD 0048's draws. **Resolved in this run:** deleted the
divergent tag, rebuilt all three from `serving/Modelfile.*` via the build driver,
and verified each rebuilt tag is **exactly-temperature** vs its base
(`delta = {temperature}` for 14b/8b/4b). The replay ran on the rebuilt,
correct-definition tags — fresh draws, not 0048's.

## Operator decision — temperature-only Modelfiles

The committed greedy Modelfiles are **`temperature 0` only** (reduced from 0048's
`temperature 0 / top_p 1 / seed 0`). At temperature 0 the decoder is argmax so
top_p/seed are inert; keeping them made the greedy-vs-base delta three keys wide and
failed AC4a ("exactly temperature"). NB: the seed-pin refutation above confirms this
reduction did NOT cause the residual nondeterminism — 0048's full config flips too.

## Caveats (routed to memory)

- **bucket-not-bit-perfect** — greedy gives at most BUCKET-level reproducibility,
  not bit-identical trajectories (14b/astropy reproduced RFWS×3 with tool times
  212/292/167s). This run shows even the bucket is not guaranteed on
  decision-boundary cells.
- **control-not-deployment** — greedy is a CONTROL for a RELATIVE ranking, never the
  deployment config; a greedy ranking must never be cited as a real-world
  localization RATE. (Given RESIDUAL_NONDETERMINISM, greedy isn't even a usable
  single-draw control here.)

## Greedy found-but-unsubmitted (OQ3) — baseline for the later knob spec

Observed **live under greedy** on the rebuilt tags: `qwen3-14b-greedy` on
`django-12774` drew `found-unsubmitted` (draw 2) while drawing `submitted` (correct)
on draws 0–1. So found-but-unsubmitted persists under greedy AND is itself
non-reproducible here (it IS one of the flips). The later reactive/confirm-knob spec
should treat greedy fu as a variable outcome, not a fixed baseline, until the
underlying nondeterminism is resolved.
