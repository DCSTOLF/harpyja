---
spec: "0032"
closed: 2026-07-08
---

# Changelog — 0032 trajectory-parser

## What shipped vs spec

The single-source-of-truth tool-name parser dedup shipped complete — all 6 tasks
`[x]`, 1111 units pass, ruff zero NEW errors (36 pre-existing from 0031-era files,
untouched per cutover-not-redesign). The 0031 T20 blocker is closed: there is now
exactly ONE tool-name parser and the strict behavior wins, surfaced as DATA on the
live path.

**AC-by-AC:**

- **AC1 (one parser) — MET.** `build_trajectory_record` (live_verifier.py) no longer
  carries the inline silent-skip tool-name parse; it delegates to the canonical strict
  `extract_tool_names`. Proven by `inspect.getsource` symbol audit (AC8 test), not a
  prose grep — the builder source contains `extract_tool_names(` and no inline
  `seen = set()` loop.
- **AC2 (divergence closed, non-raising) — MET.** A nameless tool_call now yields the
  SAME typed outcome through both paths. On the live builder the strict failure surfaces
  as a NEW additive key `tool_names_failure: str | None` on the returned record (`None`
  on success, `"tool-names-unextractable"` on a nameless tool_call), with
  `tool_names_invoked=[]` and NO partial list. NON-RAISING by design — the key lives only
  on the internal record dict, never on the persisted VerifierResult artifact.
- **AC3 (behavior-preserving on valid input) — MET.** Characterization pin: a well-formed
  ls/grep/symbols/submit_citations history parses to the same ordered-unique list through
  both paths; `tool_names_failure is None`.
- **AC4 (strict-wins, both call sites) — MET.** Both paths return a typed failure, never
  a silent skip, on a nameless tool_call; no partial list that drops a nameless call.
- **AC5 (unchanged contract) — MET.** `VERIFIER_SCHEMA_VERSION == "0031/1"`, the six
  FAILURE_CODES, and FAILURE_PRECEDENCE are frozen by a regression pin. The sentinel key
  never reaches `to_dict()`.
- **AC6 (real trajectories, field-by-field) — MET, LIVE.** See below (Ollama qwen3:14b).
  The hermetic field-by-field VerifierResult golden carries the deterministic
  same-input→same-output guarantee offline; the live run carries same-verified-facts on
  the real cases.
- **AC7 (ExplorerBackend control flow byte-identical) — MET.** The backend calls the
  builder live mid-loop (explorer_backend.py:291) and only STORES the result — it never
  branches on its contents — so a nameless-tool_call run takes the same terminal path,
  same citations/turns, with the sentinel carried as data. Proven by regression test.
- **AC8 (consumer audit + convention) — MET.** Symbol-audit test + the "one parser,
  strict-wins" rule codified in conventions.md (written in-spec as part of AC8).

**Open questions resolved:**

- **OQ1: no move.** The canonical parser stays in `live_verifier.py` —
  `explorer_backend.py` already imports the builder from it; hoisting is churn without
  invariant value.
- **OQ2: tool-names was the ONLY duplicated parse** (verified twice — planner audit +
  in-session grep). `extract_model_identity`, `tiers_run` (propagated as data, set by
  callers as literals), and terminal bucket (`extract_terminal_bucket`) are each
  single-sourced. No parallel blocker spec was needed. The AC8 audit test locks this so a
  fourth copy cannot creep back.

## AC6 live re-verification (Ollama qwen3:14b, loopback, air-gap-first)

- **astropy-12907: EXACT field-by-field match to the 0031 reference** — PASSED /
  terminal_bucket "empty" / tools [ls, grep, submit_citations] / symbols NOT invoked /
  schema 0031/1 / tiers [0,1] / served=requested=qwen3:14b. The instrument's prior
  verified finding survives the refactor.
- **django-12774: PASSED / "correct"** / tools [grep, read_span, submit_citations] /
  symbols NOT invoked. The cited line 693 falls strictly inside gold span 689–695 —
  genuine ground-truth overlap via `classify_case`, NOT a presence proxy. (0031 never
  durably recorded django's bucket — only the astropy artifact was pasted into
  ac6-proof.md; artifacts went to a tempdir.) Also first live confirmation of the 0029
  answer-all-N fix (3 parallel read_span answered in one turn).
- **Honest run log:** the first django attempt degraded typed `model-unreachable`
  (environment — per-call transport timeout), surfaced via a diagnostic shim, retried
  once, clean. Never skipped past (operator directive: no silent skip on infra error).
- Artifacts: `specs/0032-trajectory-parser/ac6-artifacts/`; analysis in `ac6-findings.md`.

## MAJOR NEW FINDING — scoped-grep path-shape defect (SUT finding, out of 0032 scope)

Surfaced by the instrument doing its job. Astropy's "empty" bucket matches 0031 at the
verifier-fact level, but the MECHANISM differs: this run the model FOUND a hit
(`grep("separability matrix", scope="astropy/")` → one CodeSpan) and SUBMITTED
`modeling/core.py:812` — which normalization DROPPED, because `RipgrepEngine.search` runs
`rg` with cwd=scope and parses the reported paths verbatim, so a scoped grep returns
SCOPE-relative paths that fail repo-confine / `is_file` at `normalize_spans`.
Found-then-dropped, not found-nothing (0031's run genuinely submitted `{"citations":[]}`
after 5 empty greps).

The django case is the within-run A/B CONTROL that isolates the variable: same grep tool,
`scope="."` → repo-relative paths → citation KEPT (correct); `scope="astropy/"` →
scope-relative → citation DROPPED (empty). A tool-contract inconsistency (glob/ls return
repo-relative; scoped grep does not) that FLIPS the measured bucket — not model capability
variance. It systematically converts would-be wrong-file/right-file into EMPTY for any
model that greps scoped (penalizing models that grep MORE precisely), distorting the 0022
file-vs-span axis for the bake-off. Historical note: spec 0012 built suffix recovery for
EXACTLY this path shape and spec 0025 removed it as FC-era code — the explorer re-created
the input shape that machinery existed to fix. Capability reading unchanged either way:
astropy's cite was the wrong file vs gold (separable.py:242-248) regardless.

**Named BLOCKING follow-ups (spec 0033 being filed — both must clear before the bake-off
trusts bucket distributions):**

- **(a) scoped-grep fix:** make scoped-grep output repo-relative AT THE TOOL SEAM
  (`RipgrepEngine`/wrapper — one bounded rg source of truth shared with the Deep `search`
  host tool; fix once, never per-caller).
- **(b) verifier extension:** add a submitted-vs-surviving citation count to the
  verifier/trajectory record so a found-then-dropped case is DISTINGUISHABLE from
  found-nothing — this class must not be able to hide inside "empty" again.

## Deviations / debt (recorded honestly)

- `run_verified_case` (0031 stub-completion code) swallows the typed `ScoutUnavailable`
  cause when the explorer degrades pre-`LoopResult` and raises a cause-less
  `ValueError("Explorer did not capture trajectory")` — a diagnosability gap, out of 0032
  scope, noted in ac6-findings.md (carry the typed cause into the raise; candidate
  line-item for 0033 or a harness spec).
- AC6's "byte-identical" claim is split honestly: live trajectories are nondeterministic
  across runs (0031 astropy ~10 assistant turns vs 3 this run), so same-input→same-output
  is carried by the HERMETIC field-by-field golden (deterministic) and the live run
  carries same-VERIFIED-FACTS on the real cases. Both halves recorded.
- Ruff: 36 pre-existing errors in 0031-era files (`typing.Mapping`, unsorted
  function-local imports in live_verifier.py) — zero introduced by this diff; untouched
  per cutover-not-redesign.

## Files touched

- `harpyja/eval/live_verifier.py` (the cutover: inline parse → `extract_tool_names` +
  `tool_names_failure` sentinel)
- `harpyja/eval/test_live_verifier.py` (+159: 3 characterization pins + 4
  divergence/identity/both-paths tests + AC8 symbol audit)
- `harpyja/scout/test_explorer_backend.py` (+25: AC7 live-run regression)
- `.speccraft/conventions.md` (+1 rule: "one parser, strict-wins" — written in-spec)
- `.speccraft/index.md` (active-spec pointer)

## ADR proposed for history.md

See `.speccraft/history.md` top entry — 2026-07-08, spec 0032 tool-name parser dedup,
strict-wins-as-data, AC6 live match, and the scoped-grep path-shape finding as the named
0033 blocker.

## Conventions proposed

None new here — the "one parser, strict-wins" rule was authored in-spec as part of AC8
(already in conventions.md, "Trajectory-verified measurement" section). No duplication.
