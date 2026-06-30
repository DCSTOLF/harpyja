---
id: "0010"
title: "SWE-bench Verified eval dataset"
status: closed
created: 2026-06-28
authors: [claude]
packages: []
related-specs: ["0009"]
---

# Spec 0010 — SWE-bench Verified eval dataset

## Why

Spec 0009-6a built the eval **instrument** (loader, single overlap oracle, runner
over the real `mode=auto` path, repeated-run aggregation, OQ2 sweep, pinned D7
report schema) and live-validated it — but shipped only a **5-case seed**. With
N=5 ≪ `N_FLOOR=30`, every run is `indicative_only`, locate accuracy is unproven on
a real legacy tree, and OQ2 (`verify_threshold=0.6` / `verify_top_n=3`, provisional
since 0008) is still **uncalibrated**. The instrument has nothing real to measure.

SWE-bench Verified supplies that dataset: 500 externally-curated, human-validated
GitHub issues across real Python projects, each with a gold patch whose **pre-image
hunk locations are patch-derivable ground-truth spans** — exactly the repo state at
`base_commit` that Harpyja scans. A stratified sample (N≥30) clears the floor, so
this wave produces Harpyja's first **non-indicative** locate-accuracy numbers and a
**sweep-backed** OQ2 recommendation.

**Framing is deliberately modest (contamination, R4).** SWE-bench is public, so the
local model may have seen these repos/issues; the **absolute** accuracy numbers are
not a generalization claim about the air-gapped/legacy trees Harpyja actually
targets. This wave's load-bearing outputs are **relative**: sweep deltas
(`verify_threshold`/`verify_top_n` against each other) and `fast`-vs-`auto` deltas.
Those deltas are far more contamination-robust than any absolute number, and they
are what an OQ2 default-flip would cite.

We use the **standalone localization protocol** (FastContext paper, arXiv
2606.14066): query the pre-fix repo, score predicted citations against patch-derived
target spans. We do **not** run the standard SWE-bench harness — no Docker, no image
builds, no test execution — because Harpyja is a *locator*, not a patcher (this also
sidesteps x86-image-under-emulation pain on Apple Silicon).

Ref: `IMPLEMENTATION_PLAN.md` Wave 6 (accuracy harness); `history.md` 0009-6a
(instrument), 0008 (gate + matrix).

**INVARIANT (measurement only, recommend-only) — inherited from 0009-6a (B1):** no
change to tier internals, orchestrator, gate, matrix, or classifier **code**. This
wave adds a dataset adapter, a per-case-repo driver, and schema/CLI reconciliations,
and **records** an OQ2 trade-off table + a recommended `(verify_threshold,
verify_top_n)`. It **does not flip any `Settings` default** — the flip remains a
separate one-line follow-up spec citing this evidence. The only `Settings`
interaction is the sweep building grid points via `dataclasses.replace` on the real
`verify_threshold` / `verify_top_n` fields, never mutation.

**Recorded deviation (D-route, see below):** to make OQ2 measurable on issue-prose
queries, the driver **overrides query classification** for the run via the existing
`LocateStack.classifier` injection seam. This injects a different *input* into the
unchanged routing/gate/matrix code — it is a measurement choice, not a behavior
change to the system under test — but it means the point-subset runs no longer
*purely observe* the production text classifier. This is surfaced loudly (per-case
agreement + an aggregate agreement rate), never hidden.

**Air-gap scoping (R8):** `convert` and `provision` are **dev-time dataset tools**
that may reach the network (HuggingFace, `git clone`); they are **never** on the MCP
server / `locate()` path and are explicitly **out** of the runtime air-gap
guarantee. The `run` / `sweep` stages are fully offline (local stack only); AC7
asserts zero non-loopback egress for the run stage.

## Resolved decisions (frozen before planning)

- **D-class — query classification by patch shape:** `_to_eval_case` derives
  `case.classification` from **patch shape**: a single file with a small total
  pre-image span → `"point"`; multi-file or large-span → `"broad"`. The single-file
  span-size threshold is a named constant, provisional and re-tuned after the first
  run (Open questions); the *rule* (single-file-small ⇒ point) is frozen.
- **D-route — routing is overridden to the patch-shape label, with agreement
  reported (resolves review B1):** the production gate only fires when
  `classify_query(query)` returns `point`, and that keys on lexical triggers in the
  **query prose**, uncorrelated with patch shape. If the driver did not intervene,
  patch-shape-`point` cases would frequently route `broad` → straight to Deep → the
  gate never runs, and `gate_catch_rate` / `gate_false_escalation` (the whole OQ2
  signal) would be computed over cases production never gated. Therefore the driver
  **injects a classifier returning `case.classification`** through the existing
  `LocateStack.classifier` seam, so the gate actually fires on the point subset and
  `verify_threshold`/`verify_top_n` sweeps have effect. To keep this honest: each
  per-case event records **both** the patch-shape label **and** the production
  `classify_query(query)` label, and the aggregate reports their **agreement rate**.
  The override is a recorded evaluation **intervention** (see INVARIANT note), not a
  pure observation, and touches no SUT code.
- **D-newfile — unlocatable new files excluded, not zeroed:** an instance whose gold
  patch targets are **all** new files (`--- /dev/null`) has no pre-image location
  for a pre-fix locator. Such cases are flagged `new_file_only` at convert and
  **excluded** from span/file scoring (the excluded count is a durable report
  field), never scored as a silent zero (no-false-capability).
- **D-protocol — pre-image hunks are the oracle, with a stated upward bias (R5/R6):**
  ground truth is the pre-image (`--- a/…`) hunk line ranges from the gold patch.
  Context lines (~3 per hunk side) **inflate** the target range, which biases
  span-hit **upward** (overlap is easier to achieve) — this tolerance is recorded in
  the report, not framed as neutral. A pure-insertion hunk *in an existing file*
  (pre-image length 0) is anchored to a concrete one-line span at the insertion
  point and **is** scored (the surrounding file is real and locatable); this is
  distinct from an all-new-**file** case (D-newfile), which has no pre-image file at
  all and is excluded. The boundary is "is there a pre-image *file* to locate," and
  the report states it.

## What

- **`harpyja/eval/swebench_eval.py`** — pipeline, stages separated by network
  posture: `convert` (network: HuggingFace) → portable `swebench_verified.raw.jsonl`
  (committed); `provision` (may `git clone`) → machine-local
  `swebench_verified.resolved.jsonl` (`repo` rewritten to a worktree at
  `base_commit`; gitignored); `prune`; and **NEW `run` / `sweep` subcommands** — the
  real offline entrypoints that load the resolved fixture and drive the per-case-repo
  driver. The uploaded `Makefile.swebench` placeholder `python -m
  harpyja.eval.runner --fixture …` does **not** exist (`runner.py`/`sweep.py` have no
  CLI; their callables take a single `repo_path`); targets are reconciled to the new
  subcommands.
- **Schema reconciliation (load-bearing seam).** `_to_eval_case` emits the **real
  `EvalCase` shape** so `load_dataset` accepts it: `case_id` (not `id`),
  `expected_spans` as a **list of `{path, start_line, end_line}`** (not a dict),
  `classification` ∈ `{point, broad}`. `base_commit` lives in the **raw JSONL** and
  is read by `provision` **directly** (`_read_jsonl`, never via `load_dataset`);
  `load_dataset` ignores the extra key without error (it is *not* an `EvalCase`
  field — review B2).
- **Per-case-repo driver (architectural gap).** The 0009-6a harness is
  **single-repo** (`run_dataset(cases, …, repo_path, stack)`). SWE-bench is **one
  worktree per case**. The new driver, per case, uses that case's `repo` as
  `repo_path`, builds its **own** `LocateStack` (real `build_live_stack`, or fakes in
  unit tests) **with the D-route classifier injected**, then **pools** outcomes into
  the D7 aggregate via the **unchanged** `metrics` oracle and `recommend` scorer; the
  `report` schema is **additively extended** (new fields appended-last-with-defaults
  per the conventions' additive-field rule, `SCHEMA_VERSION` bumped, so **both** the
  0009-6a single-run shape and this multi-repo shape validate). Artifacts are written
  via the existing `atomic_write_json` (atomic + outside-repo guard), pooled
  out-of-tree.
- **`mode=fast` seam (R3).** `run_case` currently hardcodes `mode="auto"`; this wave
  threads `mode` into `run_case` so the driver can run the set `mode="fast"` for an
  apples-to-apples Tier-1 line vs the paper's Table 2, alongside the `auto` numbers.
  (Per shipped Wave-5 behavior, `fast` is **Scout-terminal**: the gate runs
  **informationally** — tags `gate-low-confidence`, never escalates — so this is a
  no-climb Tier-1 line, *not* a no-gate path. The accurate-SUT-description fix.)
- **Durable report metadata (R2 + provenance).** The report carries, **as fields**
  (not only changelog prose): protocol identity (`standalone-localization`,
  no-harness/no-patch/no-test-exec); the `new_file_only` excluded count; the
  malformed-skipped count; the classifier-agreement rate (D-route); the
  span-inflation tolerance (D-protocol); the contamination caveat; **dataset
  provenance** (HuggingFace dataset id / split / revision, raw-fixture content hash,
  and the selected sample case-ids — so the committed raw JSONL is reproducible); and
  a per-case **`production_gate_ran`** flag (SUT-observed from `result.tiers_run` /
  `result.notes`), kept **distinct** from the harness's Scout-probe `gate_triggered`
  field, which is explicitly labeled harness-observed (round-1 R9).
- **OQ2 sweep at scale.** Run the existing `threshold × top_n` grid (K runs/point)
  over the resolved sample; with N≥`n_floor` the report is **not** flagged
  `indicative_only`, so the recommendation + spread table is evidence-backed.
- **Plumbing:** `uv add datasets`; merge `Makefile.swebench` into the root
  `Makefile`; `.gitignore` `eval_work/` + `swebench_verified.resolved.jsonl`, keep
  `swebench_verified.raw.jsonl` tracked.

## Acceptance criteria

`[unit]` = fakes/hand-built inputs; `[integration]` = `@pytest.mark.integration`,
skip-not-fail (no network / no stack ⇒ skip, never fail).

1. **[unit]** `parse_patch` derives pre-image targets on hand-built diffs:
   single-hunk and multi-hunk ranges; a deletion (`+++ /dev/null`) locatable at its
   pre-image path; an all-new-**file** hunk (`--- /dev/null`) flagged `is_new_file`
   with no spans; a pure-insertion hunk *in an existing file* anchored to a concrete
   one-line span (D-protocol/R6). Malformed patch text is skipped loudly at the
   instance level with a counted reason, never aborting the set.
2. **[unit]** `_to_eval_case` output **round-trips through the real `load_dataset`**
   without `DatasetError` (asserts `case_id` / `expected_spans` list-of-objects /
   `classification` ∈ `{point, broad}`); and `base_commit` is present in the **raw
   record** and **ignored by `load_dataset`** without error — *not* claimed as an
   `EvalCase` field (review B2). A test asserts `provision` reads `base_commit` from
   the raw dict, not from a loaded `EvalCase`.
3. **[unit]** Classification-by-patch-shape (D-class): single-file small-span ⇒
   `"point"`; multi-file ⇒ `"broad"`; single-file over-threshold-span ⇒ `"broad"`.
   The threshold constant is asserted at its boundary.
4. **[unit]** New-file handling (D-newfile): an all-new-file instance is flagged
   `new_file_only`, **excluded** from the span/file score population, and its count
   surfaced as a durable report field — never a silent zero.
5. **[unit]** Routing override + agreement (D-route, B1): with an injected
   `classify_query` fake that returns `"broad"` for a patch-shape-`point` case, the
   driver's injected classifier **overrides** routing to `point` so the gate fires,
   and the per-case event records **both** labels with an aggregate **agreement
   rate**. The production `classify_query(query)` label is captured **before** the
   override classifier is installed (so agreement never accidentally reads the
   injected label), and "gate fired" is asserted from `result.tiers_run` /
   `result.notes` (SUT-observed `production_gate_ran`), not the harness Scout probe. A
   companion test shows that **without** the override the same case routes `broad` and
   the gate is bypassed (documents exactly what the intervention changes).
6. **[unit]** Per-case-repo driver: drives ≥2 cases **each with a distinct
   `repo_path` and its own injected stack** (no live model), pools them into the
   pinned **D7-schema** report (asserted via `validate_report`), every gate metric
   populated (present null-with-count when the point subset is empty), written via
   `atomic_write_json` **outside every case repo** (asserted).
7. **[unit]** `mode=fast` seam (R3): `run_case` accepts `mode`; a `mode="fast"` run
   emits a schema-conforming report whose cases never escalate (`escalated_to_deep`
   is `false` for all), distinct from the `auto` block.
8. **[unit]** Durable report metadata (R2 + provenance): the report carries protocol
   identity, the `new_file_only` excluded count, the malformed-skipped count, the
   classifier-agreement rate, the span-inflation tolerance, the contamination caveat,
   and **dataset provenance** (HF id / split / revision, raw-fixture hash, sample
   case-ids) as **fields** (asserted present). The extended schema bumps
   `SCHEMA_VERSION` and still validates the 0009-6a single-run shape (additive,
   default-populated fields).
9. **[unit/integration]** CLI + Makefile (R1): `swebench_eval run` / `swebench_eval
   sweep` subcommands parse and, given a **missing** resolved fixture, exit non-zero
   with an actionable message (unit); the merged root `Makefile` targets invoke these
   entrypoints (asserted by target/recipe inspection). A live end-to-end of these
   commands is covered by AC10/AC11.
10. **[integration]** End-to-end on a tiny provisioned sample (≥1 resolved case): the
    live `auto` path emits a schema-conforming report with all metrics populated; the
    run stage performs **zero non-loopback egress** (network-deny assertion). Skips if
    the resolved fixture or live stack is absent.
11. **[integration]** OQ2 sweep on the sample: trade-off table (mean + spread per
    grid point) backing a recommended `(verify_threshold, verify_top_n)`;
    `indicative_only` is `false` when sample N ≥ `n_floor`; the report asserts **no
    `Settings` default was mutated**; and a **runtime budget** is honored — a
    per-case timeout + a sample cap with the expected wall-clock documented (R7;
    0009-6a was 5 live cases = 634s, so N≥30 × grid × K is bounded explicitly). Skips
    without a live stack.

### OQ2 deliverable (recommend-only, B1)

Run AC11 on a stratified sample (N≥30 ⇒ not indicative-only). Hold the provisional
catch-rate bar **≥ 0.90**; among points clearing it pick the `(threshold, top_n)`
minimizing false-escalation + over-escalation, **only where the advantage exceeds
observed run-to-run variance**. Record the chosen values, the spread table, the bar,
the sample N, the classifier-agreement rate (D-route), and the contamination caveat
in the changelog. If `0.6 / 3` clears the bar and nothing beats it past the noise
margin, record them as *validated*, not guessed.

**Agreement-rate guard (round-2):** because routing is overridden (D-route), the
recommendation is **guarded by the classifier-agreement rate**. Below a named
agreement floor the OQ2 result is flagged **low-confidence (deltas-only)** — the
`(threshold, top_n)` is reported as a relative ranking, **not** a calibration to flip
a default on — and every place OQ2 results are surfaced cites the override
intervention + the agreement rate. This keeps a low-agreement run (where the gate
fired on a synthetic routing distribution production never produces) from reading as
a confident calibration.

**Do not edit `Settings` defaults** — the flip is a separate one-line follow-up spec.

## Out of scope

- **Flipping any `Settings` default** (recommended `(threshold, top_n)` emitted as
  data; the flip is a follow-up spec). (B1, inherited)
- Running the **standard SWE-bench harness** — Docker images, patch application,
  test execution, resolved/unresolved scoring. Localization only.
- **Non-Python** languages — SWE-bench Verified is Python-only; `language` records
  this. Cross-language accuracy is a separate dataset.
- A **gating full-500 run** — the sample run + both reconciliation seams gate this
  spec; the full set is opt-in via a `make` target, run only after the sample passes.
- Changing tier/gate/matrix/classifier **code**; Wave-2.1 substring/fuzzy.

## Open questions

- **Point/broad threshold value (D-class tuning):** the exact "small span" line
  count is seeded conservatively (single-file ∧ total pre-image span ≤ a named
  constant) and re-tuned after the first sample run; rule shape frozen, constant
  provisional.
- **Held-out decontamination check (R4, deferred):** whether to add a small
  non-public mini-set to sanity-check that sweep deltas generalize beyond
  possibly-memorized SWE-bench repos — noted as a future follow-up, not built here.
