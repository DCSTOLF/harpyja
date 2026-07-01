# OQ2 sweep — operator runbook (spec 0015)

This is the **predeclared** evidence standard for the 12-repo OQ2 measurement. The
grid, K, and refinement/stop rules below are fixed **before** any data is seen, so the
search cannot be tuned after the fact. Do not widen the grid or change K mid-run.

## Air-gap posture

- **Provisioning is staged dev-time** (network clone of the 12 target repos), OUTSIDE
  the runtime air-gap boundary — the same per-case worktree driver the SWE-bench eval
  already uses. Do this first, offline-from-the-model.
- **The measured run/sweep phase is offline**: model traffic stays on the loopback
  Model Gateway; the run asserts no non-loopback egress. The report records
  `egress: loopback-only` and `provisioning_mode: staged-dev-time-clone`.

## 1. Provision the subset (dev-time, network)

```
make swebench-full        # convert full set + provision repos at base_commit (worktrees)
```

Pin the subset: the resolved fixture records each instance's repo + `base_commit`; the
report's `dataset_provenance` + `subset_identity` (repos + revs + per-repo case counts)
are the reproducibility record (AC1).

## 2. Stage-1 — COARSE grid (offline, predeclared)

- **Grid:** `verify_threshold ∈ {0.5, 0.6, 0.7, 0.8}` × `verify_top_n ∈ {1, 3, 5}` = **12 points**.
- **K = 3 runs/point, constant** (constant-K-within-stage so per-point `pstdev` is
  comparable — the `mean(A)−mean(B) > spread(B)` comparator's assumption).

```
make oq2-full LM_MODEL=<served-model>      # writes eval_work/reports/sweep.json
```

This is the model-backed, uncached stack — expect **hours** on the M1 Max. The run
emits the threshold×top_n trade-off table (mean+spread per point) and the typed OQ2
outcome.

## 3. Read the typed outcome (AC5)

`recommendation.outcome` is exactly one of:

| outcome | meaning |
|---|---|
| `recommendation` | a concrete `(verify_threshold, verify_top_n)` (incl. incumbent-validated) |
| `under_n_floor` | `seed_n < n_floor` (30) — sample underpowered, OQ2 withheld |
| `degraded_dominated` | every grid point's scout∪deep degrade rate > 0.5 — a FINDING, not a calibration |
| `gate_quality_confounded` | gate false-escalation rate is reliable (≥ `GATE_RATE_N_FLOOR`=5) AND > `GATE_CONFOUND_THRESHOLD`=0.30 — the gate rejects correct Scout citations at a material rate, so tuning would measure gate dysfunction |
| `not_separable` | no point cleared the catch-rate bar above noise |

Precedence when several co-hold (most-fundamental first):
`under_n_floor → degraded_dominated → gate_quality_confounded → not_separable`.

**If `gate_quality_confounded` fires:** the OQ2 calibration is confounded. Record the
gate false-escalation rate as the finding; do NOT report a clean `(threshold, top_n)`.
A gate-quality fix is a separate spec (out of scope here — this only measures it).

## 4. Stage-2 — REFINE (predeclared rule; only if triggered)

Trigger: a non-incumbent survivor's false-escalation advantage over the incumbent
`(0.6, 3)` is **within** the incumbent's spread BUT **exceeds `0.5 × spread`**
(promising-but-not-yet-significant).

- Refine over a **±1-grid-step neighborhood** around that best survivor.
- **K = 5 runs/point, constant** (a Stage-2 point is never compared against a Stage-1
  point at a different K).

```
make oq2-full LM_MODEL=<served-model> \
  EVAL_EXTRA="--thresholds <best±step> --top-ns <best±step>"   # adjust grid to the neighborhood
```

## 5. STOP conditions (predeclared)

Stop when ANY holds: incumbent validated, OR a (refined) point beats noise, OR a typed
null result fires (`under_n_floor` / `degraded_dominated` / `gate_quality_confounded`).

## 6. Optional — `mode=fast` line (deferrable, OQ3)

For the apples-to-apples vs FastContext Table 2:

```
make swebench-run-fast LM_MODEL=<served-model>
```

Deferrable to keep wall-clock down; not required for the OQ2 recommendation.

## What gets recorded (AC1/AC2/AC6/AC7)

`sweep.json` `run_metadata` carries: `selected_grid`, `k_runs`, `seed_n`, `n_floor`,
`degraded_dominated_threshold`, `gate_confound_threshold`, `gate_rate_n_floor`,
`subset_identity`, `provisioning_mode`, `egress`. Each grid point carries Tier-0-alone
accuracy (`tier01_resolve_rate`) and the `fc_citation_*` shape distribution. Fold the
recommendation + the gate-quality finding into `changelog.md` / `.speccraft/history.md`.
