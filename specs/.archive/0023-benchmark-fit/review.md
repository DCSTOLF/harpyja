# Cross-model review — Spec 0023 (benchmark-fit)

**Final status: REVIEWED** (quorum met on re-review — `claude-p` **approve-with-comments**,
all six concerns resolved; `codex` improved with P2/P5 resolved). Round 1 was
changes-requested; the spec was revised (two operator decisions + all six concerns), and
the three convergent residuals from round 2 were folded in before marking reviewed.

| Agent | Round 1 | Round 2 (revised spec) |
|---|---|---|
| `codex` (gpt-5.5, `codex exec`) | changes-requested | changes-requested (P2, P5 resolved) |
| `claude-p` (`claude -p`) | changes-requested | **approve-with-comments** (all six resolved) |

## Round 1 — the six concerns (all addressed in the revision)

Both reviewers affirm the spec's **placement and posture**: the cheap discriminator
sits correctly upstream of the N=38 run and the finder swap; the SUT-frozen / additive
posture is honored (no guardrail violations from either agent); the paired-A/B framing
is the right design; the out-of-scope list is disciplined. The changes-requested verdict
is about *trustworthiness of the verdict machinery*, not the skeleton.

The concerns converge on **six** points. One (C4) was independently **verified against
the actual code** and is confirmed.

---

## C1 — AC2 does not *structurally* prevent the biased distiller (both agents; load-bearing)

This is the single failure mode that can manufacture a false `QUERY_SHAPE` and wrongly
exonerate the finder. AC2 as written mostly restates a guarantee the code already
provides for free (the `distill: Callable[[str], str]` signature receives only
`c.query`, so it *cannot* read `expected_spans` at runtime — verified). But that is the
easy half. The real attack is **authorship bias**: a distiller whose output vocabulary
was chosen — by a human or an LLM shown the gold file — to overlap the gold span's
identifiers. A per-case pure function that hardcodes exactly those tokens is still "a
pure function of issue text." AC2 "merely asks for" blindness; it does not enforce it.

**Structural fix (do all three):**
- **(a) Token-subset property** — distilled tokens MUST be a subset of the raw-issue
  tokens (extraction, never generation). This converts an unbounded attack ("inject the
  gold file's function name") into a bounded, far weaker selection bias, and is a
  genuinely testable property.
- **(b) Case-agnostic mechanical rule** — a single rule (e.g. title / first sentence /
  first-N salient tokens), NO per-case or case-id branching.
- **(c) Pre-register / hash the distill source** before the live run.
- **codex adds:** decide explicitly whether issue-text **stack traces, file paths,
  symbols, exact error messages** are allowed / normalized / removed. Otherwise the probe
  may measure *"symbol leakage in issue prose"* rather than terse-query representativeness
  — and that leakage is a legitimate form of the same contamination.

## C2 — No uncertainty gate on the routing → the small-N trap in a paired costume (claude-p; load-bearing)

AC4/AC6 route on a **point-estimate band crossing** with no CI. But empty is a binary
outcome, so the correct paired test is **McNemar's**, whose power depends on the number
of **discordant pairs**, not on N. With a bounded small N and few discordant pairs, a
single case flipping can cross a band — `delta_empty = 0.2` with a CI spanning zero would
still trip "positive delta_empty → QUERY_SHAPE." That is exactly the 0020/0022 provisional
trap wearing a paired-design costume.

**Fix:** fire `QUERY_SHAPE`/`CAPABILITY` only when a paired CI on `delta_empty` (or an
exact McNemar p) clears/excludes the band; otherwise `INCONCLUSIVE`. Pre-register the
minimum detectable delta and the minimum discordant-pair count. Record the actual
discordant-pair count in the result so a small-N verdict is auditable.

## C3 — The decision boundary lives in Open Questions, not the ACs (codex)

The deliverable *is* a typed verdict, but the minimum N and materiality bands are still
open questions — so the most important part of the spec is non-falsifiable at review
time. Also AC4 ("materially exceed a pre-registered band") and AC6 ("positive
delta_empty → QUERY_SHAPE") state **two different thresholds**.

**Fix:** move the provisional minimum N, materiality bands, and the "mixed" rule OUT of
Open Questions and INTO the ACs or a named config object (mirrors 0022's pre-declared
`LOW_FILE_BAND` etc.). Reconcile AC4/AC6 to one concrete materiality rule
(`delta_empty >= threshold AND usable_n >= min_n AND discordant_pairs >= min_dp`). Define
"mixed" concretely (e.g. `delta_empty` and `delta_file_accuracy` disagree in sign).

## C4 — "Reusing run_reformulation_probe" understates net-new work and conflicts with AC3 (claude-p — VERIFIED against code)

Confirmed by reading `harpyja/eval/locate_probe.py:257–294`: `run_reformulation_probe`
computes `_empty_rate(raw) − _empty_rate(distilled)` — a **difference of two aggregate
rates** over two separate loops (`last_tally` is reset per case; no pairing retained).
`ReformulationResult(n, raw_empty_rate, distilled_empty_rate, delta_empty)` carries **no
per-case pairs and no `delta_file_accuracy`**. This is *exactly* what AC3 forbids, and
AC1 needs per-case rows. The point estimates coincide, but the paired **variance** (the
input to the C2 CI gate) is unrecoverable from the aggregate form.

**Fix:** the spec must say **EXTEND**, not reuse. `ReformulationResult` gains per-case
`(case_id, raw_bucket, distilled_bucket)` rows (mirror `CaseRow`) and a
`delta_file_accuracy`. Not large, but the "just reuse it" framing hides required work.

## C5 — Raw-arm provenance is unverified → a null result is uninterpretable (claude-p)

AC1 says "REAL long-issue cases" but nothing asserts `case.query` for the raw arm is
genuinely full multi-paragraph issue text rather than an already-terse/preprocessed
query. If the raw arm is already terse, `delta_empty ≈ 0` **by construction** — the
identical 0022 failure — and the null is uninterpretable (`CAPABILITY` vs "raw was never
actually raw" are indistinguishable).

**Fix:** add a per-case precondition asserting the raw arm carries the full issue body
(length / paragraph-structure check), recorded per case.

## C6 — AC4 (query-shape) and AC5 (representativeness) have no composition rule (claude-p)

`QUERY_SHAPE` is necessary-not-sufficient: even if query-shape explains the empty rate,
the undocumented-legacy vs documented-OSS **codebase-character** mismatch can
*independently* cap generalizability. AC4 currently says `QUERY_SHAPE ⇒ NOT finder swap,
next = query-layer` with no path for AC5 to qualify or downgrade that routing.

**Fix:** state the composition rule — AC5's representativeness verdict can qualify /
downgrade AC4's routing, and `codex` adds: make AC5 a **structured record**
(query-shape, repo-type, documentation-density, codebase-age, target-proxy-validity),
not a prose appendix, so it is as auditable as the delta verdict.

---

## Secondary / minor

- **`delta_file_accuracy` load-bearing?** — AC1/AC3 record it but AC4/AC6 route only on
  `delta_empty`. State explicitly whether it is in the rule or diagnostic-only (feeds the
  "mixed" definition in C3).
- **Frontmatter title** (both, convention) — `title: "benchmark-fit:"` has a trailing
  colon / no descriptive text. Cosmetic; the H1 carries the full title. Fix if desired.
- **Tooling note** — `codex exec --full-auto` is deprecated (use `--sandbox
  workspace-write`); consider updating `.speccraft/agents.toml`.

## Round 2 — re-review of the revised spec

`claude-p` confirmed **all six** resolved and returned **approve-with-comments**; `codex`
confirmed P2 (thresholds now key off the Axis-1 verdict) and P5 (structured
representativeness record) resolved. Three **convergent, non-blocking** residuals were
raised and then **folded in before marking reviewed**:

- **R1 — `MIN_DISCORDANT_PAIRS=5` hollows the verdict** (both). At 5 discordant pairs an
  exact two-sided McNemar clears α=0.05 only at a perfect 5/0 split, so `QUERY_SHAPE` is
  nearly unreachable → everything defaults to `INCONCLUSIVE` (the small-N trap in reverse).
  **Fix:** raised to **8** from exact-McNemar reachability (6 is the bare floor; 8 gives one
  contrary pair of slack); OQ1 keeps open a formal target-power floor.
- **R2 — symbol-leakage policy declared but not stated** (codex). AC2 *required* declaring
  whether stack traces/paths/symbols/error strings are retained/normalized/stripped; the
  revision now **states** it — mechanical arm strips code-identifier tokens (NL-shaped
  distilled query), raw arm retains all, stripped tokens recorded per case.
- **R3 — `min_n` value + overlapping `INCONCLUSIVE` labels** (codex + claude-p). `min_n`
  set to **12** (distinct from the discordant floor); AC4's single `INCONCLUSIVE` split
  into three **named, non-overlapping** triggers (`insufficient_power`,
  `distiller_arm_disagreement`, `axis_signal_disagreement`) so the branch table is a total
  function.

## Bottom line

Neither agent challenged the *experiment's design intent* — the probe is the right
instrument in the right place. Round 1 made the verdict **honest under small N and
adversarial distillation** (C1–C6); round 2 tightened the **statistical realism** of the
binary paired test (R1–R3). The honest cost surfaced by the reviews — a binary paired
probe may need ~15–25 raw cases, not "a handful" — is now written into the config rather
than glossed. Spec is `reviewed` and ready for `/speccraft:spec:plan`.
