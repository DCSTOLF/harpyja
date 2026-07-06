---
spec: "0025"
title: "removal — FastContext removal + Scout cutover to the explorer backend"
reviewers: [codex, claude-p]
quorum: 1
verdict: reviewed
generated: 2026-07-06
rounds: 2
---

# Cross-model review — 0025 (removal)

Two rounds. Round 1 ran against the initial draft; both reviewers returned
`changes-requested` with convergent, fixable asks. The spec was amended
(revision 2). Round 2 ran against revision 2; **codex → approve-with-comments**,
**claude-p → changes-requested** with three *code-grounded* defects. Those three
were fixed (revision 3). Quorum (1 approve/approve-with-comments) is met by
codex, and claude-p's blocking items are resolved in revision 3.

---

## Round 1 (initial draft)

Both `changes-requested`. Convergent asks (both agents):

1. **Eval report-schema orphaning** — `fc_citation_*` / `fc_citation_recovered_*`
   + the `ScoutTally` recovery side-channel measure a vanishing backend; decide
   their fate per the additive-last-with-defaults / `SCHEMA_VERSION` convention.
2. **`agent_factory=` carries a live measurement** — the 0022 turns-used
   diagnostic; frame removal as *migration*, not dead-seam delete.
3. **OQ2 factory-naming** — resolve in-spec; both recommended keeping
   `build_scout_engine` canonical and deleting `build_explorer_scout_engine`.
4. **AC3 needs executable teeth** — an import-absence assertion, not prose grep.

Single-agent asks:

- **codex** — audit `scout_model` before sweeping it into `FC_*` removal
  (`verify_method='scout_model'` is the 0018 gate baseline, a possibly non-FC
  consumer).
- **claude-p** — enumerate the full FC deletion surface (the 0007 env-injection
  apparatus: `_SCOUT_ENV_LOCK` / `_managed_fc_env` / `_run_coro_on_worker_thread`
  / Path-A→B state machine) and the `normalize.py` split (FC-era
  `normalize_spans_with_tally` / `_recover_suffix` / tally-tuple vs. the kept
  `normalize_spans` — OQ3's hazard in a second module); reuse the existing
  field-default introspection pattern for AC4; name the live model/quant in AC5.

No guardrail violations. codex flagged two convention-coupling findings
(`scout_model` cross-subsystem coupling; measurement-seam removal) — the codified
form of convergent asks #1/#2.

### Amendments (revision 2)

All four convergent findings + all single-agent asks accepted. Added the
"migrate before you delete" invariant naming the two highest-risk edits (the
turns diagnostic and the `normalize.py` split); resolved OQ2 to canonical
`build_scout_engine`; added ACs for the report-schema fate (AC7), the
turns-migration (AC3), the `normalize.py` split proof (AC5), the `scout_model`
audit (AC6); gave the consumer guard executable teeth (AC4); enumerated the full
FC deletion surface in "What."

---

## Round 2 (revision 2)

### codex — approve-with-comments

Direction resolved; comments are test-precision, not blockers:
- AC3 should define turns-used as a concrete counter contract and compare against
  a frozen/golden trajectory, not imply cross-backend semantic identity.
- AC5's post-delete absence guard doesn't by itself prove the *pre-delete*
  consumer graph — capture that as an inventory artifact/fixture too.
- AC8 should state the runnable model tag/profile in one canonical form.

No guardrail or convention violations.

### claude-p — changes-requested (code-grounded)

Verified against the code; three defects in load-bearing ACs:

1. **AC6 self-contradiction.** `scout_model`'s Settings default IS a FastContext
   tag (`settings.py:91` → `hf.co/dstolf/FastContext-1.0-4B-RL-Q8_0-GGUF:latest`),
   and that tag is *served* (pulled into local Ollama). AC6 asked the guard to
   "confirm no Scout default points at an FC tag" while "preserving the FC-tagged
   `scout_model` baseline" — impossible together. And the named guard
   (`test_settings_defaults_drop_unserved_tags`) checks *unserved* tags, so it
   passes the served FC default and never verifies AC6's claimed property.
2. **AC8 mis-identifies the live model.** The explorer does not read `scout_model`
   (`build_explorer_scout_engine` builds the gateway with no `model=` → default
   `"local"`); 0024 ran the explorer live on **Qwen3-8B**, a general tool-calling
   model — NOT FastContext-4B. Pinning AC8's live stack to the FC Q4/Q8 footprint
   note (about the *removed* model) is a category error.
3. **AC3 conflates cap vs. used.** `scout_max_turns` is a Settings *budget* (the
   cap), not the turns-*consumed* count the 0022 diagnostic measures; the
   migration needs a public turns-used seam (like `last_tally`) to assert
   equivalence against `count_turns`.

Also confirmed the prior asks were well-resolved: the deletion surface matches
the code (`fastcontext.py`, `client.py`, `parse_final_answer`, the env apparatus,
the `agent_factory=` seam, the `citation=False` grammar); the report-schema fate
is correct (nothing reads `fc_citation_*` expecting non-zero — `validate_report`
checks key presence only, fields default 0 in `_AGGREGATE_DEFAULTS`); OQ2 and
AC4's teeth are right.

No guardrail violations. One convention finding: AC6 blurred the
plumbing-vs-behavior line (codified form of defect #1).

### Fixes (revision 3)

All three claude-p defects + codex's two refinements resolved:

- **AC3 / invariant (a):** distinguished the `scout_max_turns` *cap* from a
  public per-run turns-*used* seam (mirroring `last_tally`, created if absent),
  asserted equivalent to `count_turns`; diagnostic repointed and green BEFORE the
  seam is deleted.
- **AC6 / invariant:** resolved the contradiction — keep the served `scout_model`
  gate baseline, scope it OUT of the FC-removal drift guard, and assert the
  property the guard actually enforces (no default names an *unserved/unobtainable*
  tag). Dropped the false "no default is FC-branded" claim.
- **AC8:** named **Qwen3-8B on loopback Ollama** as the live explorer model,
  removed the FC Q4/Q8 footprint framing as a category error, and required the
  gateway to select the served tag explicitly (thread it through wiring or pin it
  in the test — `model="local"` 404s on Ollama).
- **AC5:** added the pre-delete consumer-inventory proof alongside the post-delete
  import-absence guard (codex's two-sided ask).
- **AC2:** noted the `agent_factory=` kwarg removal is staged AFTER AC3's
  migration lands, so repointing the factory doesn't break the diagnostic.

---

## Determination

**Quorum met** (codex: approve-with-comments), and claude-p's three code-grounded
blocking defects are resolved in revision 3. Status → **reviewed**. The remaining
codex comments were absorbed into AC3/AC5/AC8. Ready for `/speccraft:spec:plan`.
