# Spec 0032 — AC6 live re-verification through the deduped parser

Date: 2026-07-08 · Stack: Ollama `qwen3:14b` @ `http://127.0.0.1:11434/v1` (loopback,
preflight via `verifier_preflight` — air-gap asserted first, model presence confirmed)
· Settings mirror the 0031 AC6 harness (`scout_max_turns=10`, `explorer_max_tokens=2048`,
`scout_wall_clock_s=600`, `lm_http_timeout_s=300`). Artifacts: `ac6-artifacts/`.

## Result vs the 0031 reference

The spec's named reference (0031 ac6-proof.md / index.md): **astropy PASSED /
`terminal_bucket: "empty"` / tools `{ls, grep, submit_citations}` / symbols NOT invoked.**

### astropy__astropy-12907 — EXACT MATCH, field by field

| Field | 0031 reference | 0032 deduped run | Match |
|---|---|---|---|
| schema_version | 0031/1 | 0031/1 | ✓ |
| verifier_status | PASSED | PASSED | ✓ |
| failure_reason | null | null | ✓ |
| requested_model | qwen3:14b | qwen3:14b | ✓ |
| served_model | qwen3:14b | qwen3:14b | ✓ |
| endpoint | http://127.0.0.1:11434/v1 | http://127.0.0.1:11434/v1 | ✓ |
| tiers_run | [0, 1] | [0, 1] | ✓ |
| terminal_bucket | empty | empty | ✓ |
| tools invoked (ordered-unique) | ls, grep, submit_citations | ls, grep, submit_citations | ✓ |
| symbols invoked | NO | NO | ✓ |

The instrument's prior verified finding — astropy empty, symbols-not-invoked — survives
the refactor. (Assistant-turn COUNT differs across live runs, 0031 ~10 vs this run 3:
model stochasticity, not a verifier/parser property; the four verified facts are the
comparison contract.)

### django__django-12774 — PASSED through the deduped parser

| Field | Value |
|---|---|
| verifier_status | PASSED |
| failure_reason | null |
| served_model | qwen3:14b |
| terminal_bucket | correct |
| tools invoked | grep, read_span, submit_citations |
| symbols invoked | NO (consistent with 0031's "neither invoked symbols") |

0031 never durably recorded django's terminal bucket (only the astropy artifact was
pasted into ac6-proof.md; the integration test wrote artifacts to a tempdir), so no
bucket-level reference exists to diff against. Bucket variance across live runs is a
MODEL property; the parser-level same-input→same-output guarantee is carried
deterministically by the hermetic field-by-field golden
(`test_verify_result_field_by_field_stable_on_valid_trajectory`) and the both-paths
tests in `test_live_verifier.py`.

## Honest run log

- Attempt 1 (both cases, default `Settings` loop budgets): astropy PASSED as above;
  django degraded with typed cause `model-unreachable` inside the explorer loop —
  `run_verified_case` masked it as `ValueError("Explorer did not capture trajectory")`;
  a diagnostic shim on `ExplorerBackend.run` recovered the typed cause. Environment
  failure (per-call transport timeout on the local endpoint), NOT a SUT/parser finding.
- Attempt 2 (django only, same settings): PASSED clean as above.
- Per the operator directive (no silent skip on infra error), the degrade was surfaced,
  attributed to its typed cause, and retried — not skipped past.

## Astropy "empty": the bucket matches 0031, but the MECHANISM differs — and it names a SUT finding

The verifier proves the run was CLEAN (tiers [0,1], every tool call named, no degrade
markers, terminal `submit_citations` reached). But "empty" in THIS run does NOT mean
"the model found nothing":

- **0031's run**: 5 greps all returned `[]`; the model submitted a literal
  `{"citations":[]}`. Genuinely found nothing.
- **This run** (trajectory turns [1]–[5]): the model called
  `grep("separability matrix", scope="astropy/")`, got ONE hit —
  `CodeSpan(path='modeling/core.py', start_line=812)` — and faithfully submitted
  `modeling/core.py:812`. That citation was DROPPED at normalization: the path is
  **scope-relative**, not repo-relative (`RipgrepEngine.search` runs `rg` with
  cwd=scope and parses the reported relative paths verbatim), so repo-confine +
  `is_file` against the repo root fails (`<repo>/modeling/core.py` does not exist) →
  honest drop → effective citations `[]` → bucket EMPTY.

Same bucket as 0031, different mechanism: found-then-dropped, not found-nothing. Two
consequences worth recording:

1. **Named SUT finding (out of 0032 scope — any Scout/tool change is excluded):** the
   explorer's `grep(scope=...)` output shape is not submit-compatible — a scoped
   grep's paths systematically fail `normalize_spans` unless the model re-prefixes
   them. The tool suite is internally inconsistent: `glob`/`ls` return repo-relative
   paths, scoped `grep` returns scope-relative. Note spec 0012 built suffix recovery
   for EXACTLY this shape (`modeling/core.py` → unique-suffix →
   `astropy/modeling/core.py`) and spec 0025 removed it as FC-era code — the explorer
   has re-created the input shape that machinery existed to fix. This converts a
   would-be wrong-file (or right-file) citation into EMPTY, distorting the 0022
   file-vs-span diagnostic axis for any bake-off case where the model greps scoped.
   Follow-up: make scoped-grep output repo-relative at the tool seam (one bounded rg
   source of truth — fix in `RipgrepEngine`/tool wrapper, not per-caller).
2. **Capability reading unchanged:** even had the path resolved,
   `astropy/modeling/core.py:812` is the WRONG FILE vs gold
   (`astropy/modeling/separable.py:242-248`) — so this run would grade wrong-file,
   not correct, either way. The 0031-reference bucket match stands at the
   verifier-fact level; this note keeps the mechanism honest.

### django "correct" is genuine — and is the control that proves the grep finding

Django's trajectory: `grep("in_bulk", scope=".")` → scope is the REPO ROOT, so rg's
cwd = repo root and the returned paths are REPO-relative (`django/db/models/query.py`,
prefix intact) → the model verified with 3 parallel `read_span` calls (685/691/693 —
all three answered in one turn, the 0029 answer-all-N fix live) → submitted
`django/db/models/query.py:693`, which resolves in-repo and falls strictly inside the
gold span (689–695). A direct ground-truth span overlap via `classify_case`, not a
presence proxy.

The pair is a within-run A/B on the tool contract: same grep tool, `scope="."` →
repo-relative → citation KEPT (`correct`); `scope="astropy/"` → scope-relative →
citation DROPPED (`empty`). Whether a found citation survives normalization depends on
which scope string the model happened to pass — a tool-contract inconsistency that
flips the measured bucket, not model capability variance. This is the concrete reason
the scoped-grep path-shape fix must land before the bake-off trusts bucket
distributions.

## Residual observation (not a 0032 defect — 0031 harness debt)

`run_verified_case` swallows the `ScoutUnavailable` cause when the explorer degrades
before producing a `LoopResult` and raises a cause-less
`ValueError("Explorer did not capture trajectory")` — a diagnosability gap in the 0031
stub-completion code (out of 0032's "change ONLY the tool-name parsing seam" scope).
Worth a line in a future harness spec: carry the typed cause into the raise.
