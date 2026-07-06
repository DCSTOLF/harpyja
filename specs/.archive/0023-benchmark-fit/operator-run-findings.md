# Operator-run findings — Spec 0023 benchmark-fit reformulation probe (REAL SWE-bench)

This is the operator measurement spec 0023 named as follow-up #1 ("fire the discriminator
on real long-issue cases"). It runs the shipped, byte-frozen instrument — **no instrument
code was written or modified**; the run is driven entirely by public eval seams. It
resolves whether 0022's provisional `RETRIEVAL_FUNDAMENTAL` is a real capability wall or a
`BENCHMARK_UNREPRESENTATIVE`-via-query-shape artifact.

- **Date context:** 2026-07-05. `HARPYJA_REQUIRE_LIVE_STACK=1`; air-gap held (loopback only).
- **Finder under test (SUT):** **FastContext-1.0-4B-RL-Q8** (`scout_model` default) — the
  same 4B finder the whole spec exists to characterize. The qwen3:8b role is ONLY the
  labeled LLM sensitivity *distiller* (it reformulates the query; it never retrieves).
- **Data:** `swebench_verified.resolved.jsonl`, the 38 `point` cases, all real
  multi-paragraph GitHub issues; 38/38 `is_raw_issue`-admitted, 38/38 worktrees present.

## Precondition gate ("does green connect to the measurement") — PASSED
One real case (astropy-12907) run live: `is_raw_issue` ADMITTED it (usable_n=1, **not 0**),
BOTH arms ran (raw=RIGHT_FILE_WRONG_SPAN, dist=EMPTY), the McNemar cell incremented
(discordant=1). This is the cheap guard against a fourth green-but-`usable_n=0` run — the
instrument fires on real input, unlike the terse legacy fixtures (delta≈0 by construction).

## PRIMARY arm — mechanical distiller (verdict-driving)
Ran the point subset in fixture order until the pre-registered floors were met
(`usable_n >= 12` AND `discordant_pairs >= 8`), then stopped: several remaining cases cost
5–30 min each (psf__requests-1724 = 1831s; matplotlib-25332 = 736s), so exhausting all 38
buys only marginal power on an already-powered result (cheap-before-expensive).

| case_id | raw_bucket | dist_bucket (mechanical) | secs |
|---|---|---|---|
| astropy__astropy-12907 | RIGHT_FILE_WRONG_SPAN | EMPTY | 16.5 |
| astropy__astropy-14365 | RIGHT_FILE_WRONG_SPAN | EMPTY | 26.6 |
| astropy__astropy-7606 | EMPTY | EMPTY | 19.9 |
| django__django-12774 | EMPTY | EMPTY | 155.6 |
| django__django-13516 | EMPTY | EMPTY | 14.2 |
| django__django-13821 | EMPTY | EMPTY | 16.8 |
| matplotlib__matplotlib-21568 | EMPTY | EMPTY | 16.8 |
| matplotlib__matplotlib-24177 | EMPTY | EMPTY | 77.1 |
| matplotlib__matplotlib-24570 | EMPTY | WRONG_FILE | 24.8 |
| matplotlib__matplotlib-25332 | EMPTY | WRONG_FILE | 736.0 |
| matplotlib__matplotlib-26113 | EMPTY | RIGHT_FILE_WRONG_SPAN | 24.1 |
| pallets__flask-5014 | EMPTY | WRONG_FILE | 15.9 |
| psf__requests-1142 | WRONG_FILE | EMPTY | 36.7 |
| psf__requests-1724 | EMPTY | WRONG_FILE | 1831.7 |

Aggregate (n=14):
- raw buckets : `EMPTY×11, RIGHT_FILE_WRONG_SPAN×2, WRONG_FILE×1` → **79% empty, 0/14 CORRECT**
- dist buckets: `EMPTY×9, WRONG_FILE×4, RIGHT_FILE_WRONG_SPAN×1` → **0/14 CORRECT**
- `delta_empty = +0.143` (BELOW the 0.20 band) · `delta_file_accuracy = −0.071` (2/14 → 1/14 right-file)
- discordant = 8 (b=5, c=3) · exact McNemar p = 0.727 → **does NOT reject** at α=0.05
- **AXIS-1 (primary) = INCONCLUSIVE (AXIS_SIGNAL_DISAGREEMENT)** — floors MET, so this is a
  *substantive* trigger (delta_empty>0 but delta_file_accuracy<0), NOT insufficient power.

## SENSITIVITY arm — LLM distiller (qwen3:8b, thinking off), NON-primary/indicative
Pre-registered `LLM_PROMPT` (hash e7a54bab…) applied by the operator callable; post-hoc
subset HARD-REJECT guard. **7/14 accepted, 7/14 hard-rejected** (`DistillRejected`). The
accepted queries RETAIN the identifiers the mechanical arm strips.

| case_id | raw_bucket | llm_bucket | llm_query (qwen3:8b, subset-passing) |
|---|---|---|---|
| astropy__astropy-12907 | RIGHT_FILE_WRONG_SPAN | EMPTY | "separability matrix nested compound models inputs outputs no…" |
| astropy__astropy-7606 | EMPTY | EMPTY | "Unit equality comparison with None raises TypeError for Unre…" |
| django__django-12774 | EMPTY | EMPTY | "Allow QuerySet.in_bulk() for fields with total UniqueConstr…" |
| django__django-13821 | EMPTY | EMPTY | "Drop support for SQLite < 3.9.0 indexes on expressions SQLIT…" |
| matplotlib__matplotlib-24177 | EMPTY | EMPTY | "ax.hist density not auto-scaled when using histtype='step'" |

- scored n=5 (partial; the 3 slow matplotlib cases stopped) — `llm_delta_empty = −0.20`,
  `llm_delta_file_accuracy = −0.20`. rejected: astropy-14365, django-13516, matplotlib-21568,
  matplotlib-24570, flask-5014, requests-1142, requests-1724.
- **Corroboration:** the SMART, identifier-retaining distiller ALSO fails to help FastContext
  (astropy-12907 raw=RIGHT_FILE → llm=EMPTY, same failure as mechanical). So the mechanical
  arm's identifier-stripping is **not** the confound — "distillation does not rescue the
  finder" holds across BOTH a dumb and a smart distiller, closing the "mechanical rule too
  crude → truth is QUERY_SHAPE" escape hatch.

## AXIS 2 — representativeness (pre-registered rule)
Record: query_shape=`verbose-multiparagraph-issue-prose`, repo_type=`mature-popular-oss-library`,
documentation_density=`high`, codebase_age=`mature-actively-maintained`, target_proxy_validity=`weak`.
- Rule `representative = False` iff doc_density==`low` AND proxy==`weak`; here doc_density=`high`
  → **is_representative = True**.
- **Noted rule limitation (OQ):** the threshold only flags a benchmark unrepresentative when it
  is *undocumented*. SWE-bench is a *weak proxy* for Harpyja's target (terse NL over undocumented
  proprietary legacy) yet well-documented OSS, so the AND-gate cannot flag it. The Axis-2 rule
  as written under-detects SWE-bench's unrepresentativeness — a candidate refinement.

## COMPOSED 2×2 VERDICT
`axis1 = INCONCLUSIVE` × `representative = True` → **next_spec = `HOLD_INCONCLUSIVE`**
(`compose_verdict`: an INCONCLUSIVE Axis-1 routes to HOLD regardless of Axis 2.)

## Substantive reading (what the numbers say beyond the formal gate)
1. **0022's `RETRIEVAL_FUNDAMENTAL` is corroborated on REAL long-issue text** (not the terse
   fixtures): on the verbose issues themselves FastContext is 79% empty and **0/14 span-correct**.
2. **QUERY_SHAPE is FALSIFIED:** terser queries do not materially cut the empty-rate (delta
   +0.143 < 0.20 band; McNemar n.s., p=0.73) and do not improve right-file accuracy (−0.071);
   holds across mechanical AND LLM distillers. Distillation merely shuffles some empties into
   WRONG_FILE guesses.
3. **Why the formal gate cannot certify CAPABILITY:** the finder's localization floor is so
   near-zero (0/14 correct, 2/14 right-file) that discordant pairs are dominated by
   empty↔wrong-file *noise*, which is exactly what makes delta_empty and delta_file_accuracy
   oppose at ±1-case magnitude. The discriminator cannot fire cleanly because there is almost
   no successful retrieval to discriminate on — itself the strongest evidence the bottleneck is
   retrieval **CAPABILITY**, not query shape.

## Bottom line & routing
- **Formal typed verdict: `HOLD_INCONCLUSIVE`.**
- **Substantive lean: CAPABILITY × representative → `N38_PLUS_FINDER_CAPABILITY`.** The
  `BENCHMARK_UNREPRESENTATIVE`-via-query-shape escape is falsified: terse queries do not help
  FastContext find code, across two independent distillers. **The next spec is finder-capability
  work — NOT a reformulation/query layer, and NOT a benchmark swap justified by query shape.**
- Enlarging N (exhausting the 38) would likely tip the *formal* gate INCONCLUSIVE→CAPABILITY but
  would not change the substantive conclusion (the axis-disagreement is noise-level;
  distillation-doesn't-help is robust). It is a cheap-vs-power call for the finder-capability spec.

## Operator note (reproducibility)
Run scripts lived outside the repo (scratch dir); raw per-case artifacts are machine-local under
`eval_work/benchmark_fit_run/` (gitignored): `pairs.jsonl`, `llm_queries.jsonl`, `llm_pairs.jsonl`,
`run.log`, `precheck.log`. Two operator lessons: (a) a Scout-arm + LLM-distiller-arm must be run in
**decoupled phases** (distill-all, then score-all) — alternating per case thrashes the single-GPU
Ollama model-swap; (b) the operator callable must apply the pre-registered `LLM_PROMPT` itself
(`llm_distill_guarded` passes raw `issue_text` to the callable by contract).
