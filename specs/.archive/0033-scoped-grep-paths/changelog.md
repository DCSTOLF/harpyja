---
spec: "0033"
closed: 2026-07-09
---

# Changelog — 0033 scoped-grep-paths

The 0032 blocker cleared: scoped grep now returns repo-relative paths (fixed at the
ONE `RipgrepEngine` seam), and a found-then-dropped citation is a first-class recorded
fact (submitted-vs-surviving counts on the trajectory/verifier artifact) rather than
something that hides inside the `empty` terminal bucket. All 15 tasks `[x]`, all 8 ACs
MET, 1140 units pass, ruff 34 vs 36 baseline (net **-2** — the cause-swallowing fix
deleted a pre-existing F841). The scoped-grep drop was closed LIVE on the real astropy
case: a cited hit survived normalization (`citations_submitted=1`, `surviving=1`).

## What shipped vs spec

### AC1 — engine emits repo-relative paths (OQ1 → mechanism b, OQ2 → per-call param)
`RipgrepEngine.search` gained an optional `repo_root=` keyword. The `rg` invocation is
byte-identical for directory scopes (still `cwd=scope`, no new path arg, same flags);
only the PARSED paths are re-prefixed with the scope's repo-relative prefix
(`_parse(stdout, rel_prefix=...)` via `os.path.normpath(os.path.join(rel_prefix, path))`,
collapsing `.`/`./` artifacts). Because the real `rg` command never changes on the
directory path, AC1's repo-root ordering + ignore-file pin holds trivially. The legacy
no-`repo_root` path is verbatim (Tier-0 untouched). `repo_root` is a per-CALL param, not
a constructor field — the engine is built once and shared across repos
(`server/app.py`, `cli.py`). A real-`rg` integration case pins ordering + `.ignore`
resolution.

### AC4 edge — the `symbols` degraded-fallback FILE scope (a pre-existing crash, net-fixed)
When `repo_root` is supplied and the scope resolves to a FILE, the engine runs `rg` from
the file's PARENT with the filename as an rg path argument and re-prefixes by the
parent's repo-relative prefix. This KILLS the pre-existing `NotADirectoryError` crash
(that fallback was broken outside injected-runner tests — `subprocess.run(cwd=<file>)`),
preserving its only content path rather than rejecting loudly.

### AC2/AC3/AC4 — wrappers supply repo_root as DATA; blast radius pinned both directions
Explorer `grep`, the `symbols` degraded fallback, and Deep `search` all supply
`repo_root=repo_path` — the re-prefix LOGIC lives solely in the engine (the
one-rg-seam invariant honored; supplying data is not the per-caller fix the invariant
forbids). One tool-contract test asserts grep (scoped + unscoped), glob, ls, and the
`symbols` clean branch all emit repo-relative paths; `read_span` is EXCLUDED (echoes
its input, discovers nothing); `ls` trailing-`/` directory-entry semantics pinned as
repo-relative non-citable listings. The astropy end-to-end RED reproduced the exact
0032 drop (`[] == [astropy/modeling/core.py:812]`) before the fix made the cited hit
SURVIVE; the django control is byte-unchanged. Deep's scoped output is POSITIVELY
pinned as changing to repo-relative (the inherited fix), not just an unscoped no-op.

### AC5 — counts at the drop seam (submit-seam, not the engine re-normalize pass)
`submit_citations` now returns `SubmitResult(spans, submitted, surviving)` (frozen
dataclass; `submitted = len(raw)`, `surviving = len(normalized)`). Single production
caller — the loop's terminal handling — updated in the same change; an AST/no-other-caller
test guards it. The counts thread as DATA `LoopResult.citations_submitted/surviving`
(defaulted) → `ExplorerBackend` → `build_trajectory_record` → the PERSISTED artifact.
`VERIFIER_SCHEMA_VERSION "0031/1" → "0033/1"` with a version GATE
(`_KNOWN_VERIFIER_SCHEMA_VERSIONS = {"0031/1", "0033/1"}`, the 0026 `DATASET_SCHEMA_VERSION`
pattern) and the two count fields OPTIONAL — a legacy `0031/1` artifact fixture still
validates. Found-then-dropped `(1, 0)` is structurally distinguishable from honest-empty
`(0, 0)`. `fc_citation_dropped_count` and the eval-report schema are asserted
byte-untouched (its engine-pass-only scope documented — the two 0032-era pins, the schema
constant and the field-by-field golden, reconciled to `0033/1` in the same change).

### AC6 — run_verified_case carries the typed cause (folded in; net-fixed a ruff F841)
The caught `ScoutUnavailable` is now captured into a `degrade` variable that OUTLIVES
the except block; the no-trajectory raise NAMES `degrade.cause` and chains `from
degrade`. The dead shadowed `last_trajectory = backend.last_trajectory` inside the
except was deleted — that unused binding WAS the bug (the pre-existing ruff F841), so
this net-removes a lint error rather than just holding the line.

### AC7 — live re-run of the 0032 astropy case (T14)
Exercised on the served Ollama `qwen3:14b` stack. The scoped-grep citation SURVIVED
normalization — `citations_submitted=1`, `citations_surviving=1` — closing the 0032
found-then-dropped shape live. The AC7 test also now prints `terminal_bucket` (the T14
observability gap noted below).

### AC8 — conventions.md (written in T15; NOT re-touched at close)
The tool-contract rule (every path-DISCOVERING tool emits repo-relative paths; fix
path-shape defects at the engine seam, never per-caller, never by downstream repair) +
the two-normalize-passes scope note for `fc_citation_dropped_count` + the
0012→0025→0033 history were written in T15.

## Deviations (the honest highlight)

- **The persisted-artifact gap the LIVE run caught.** The first T14 live run PASSED —
  but exposed that the counts reached the in-memory trajectory record and NOT the
  persisted JSON artifact: `run_verified_case` re-assembles the artifact from explicit
  fields, and the unit tests had asserted the RECORD, not the WRITTEN JSON. A RED test
  against the written JSON was added, the artifact assembly fixed
  (`last_trajectory.get("citations_submitted"/"surviving")` threaded into the persisted
  dict), and the live case re-run to confirm surviving=1 in the durable artifact. The
  hermetic fixture had proven the mechanism; only the live run proved the PERSISTENCE.
- **AC7 is model-behavior-contingent (0023 precondition rule):** a run where the model
  never greps scoped cannot exercise the drop; such a run records NOT-EXERCISED rather
  than a silent pass, and AC3's hermetic fixture is the deterministic proof.
- **Ruff net -2** (34 vs the 36-error 0031/0032 baseline): the F841 deleted in AC6; no
  new errors introduced.

## Files touched

- `harpyja/symbols/ripgrep.py` — `search(repo_root=)` param, file-scope parent-dir case,
  `_parse(rel_prefix=)` re-prefix
- `harpyja/scout/submit.py` — `SubmitResult` dataclass; `submit_citations` returns it
- `harpyja/scout/explorer_loop.py` — `LoopResult.citations_submitted/surviving`;
  `_answer_tool_call` unpacks `SubmitResult`
- `harpyja/scout/explorer_backend.py` — threads the counts into `build_trajectory_record`
- `harpyja/scout/explorer_tools.py` — `grep` + `symbols` fallback supply `repo_root`
- `harpyja/deep/host_tools.py` — Deep `search` supplies `repo_root`
- `harpyja/eval/live_verifier.py` — schema `0033/1` + version gate, record + persisted
  artifact fields, `run_verified_case` cause chain
- Tests: `test_ripgrep.py`, `test_explorer_tools.py`, `test_submit_citations.py`,
  `test_explorer_loop.py`, `test_explorer_backend.py`, `test_host_tools.py`,
  `test_live_verifier.py`, `test_live_verifier_integration.py`
- `.speccraft/conventions.md` (T15)
- `specs/0033-scoped-grep-paths/thinking-experiment/` (adjacent experiment — see below)

## Adjacent thinking-experiment (post-implementation; fixtures committed)

Run AFTER T1–T15 on the fixed stack. NOT part of 0033's ACs — recorded as reference
evidence for the follow-up spec and the eval set. The user's verdict is reproduced
EXACTLY because this framing is deliberate and epistemically load-bearing.

**Outcome: N=2** (`think:true` + cap 8192). Run 1 wrong-file (phrase-grep trap,
`core.py:812`). Run 2 right-file-wrong-span (`separable.py:66-102`) — the FIRST-EVER
right-file on astropy (~6 baseline runs, zero), the FIRST-EVER observed `symbols`
invocation, a clean push→pull navigation (ls-walk → symbols → survived citation).
Trajectories saved durably.

**Verdict: mechanism UNESTABLISHED, most likely variance.** Both tested knobs measured
inert — thinking is already default-ON (probe: a `/v1` response carries `reasoning` 3949
chars WITHOUT a `think` param), and the cap never bound (max turn 1041 tokens < 8192,
also < 2048). A result whose hypothesized cause is measured-ABSENT is NOT evidence for
that cause. Do NOT record as "thinking improves localization."

**What IS established (cause-independent):**
- **Proof-of-mechanism:** the 0030 tool-chain works end-to-end when the model engages
  it. The open question is adoption FREQUENCY, not capability.
- **Hidden-variable finding:** default thinking has been invisibly generated and
  silently dropped (the gateway returns only content/tool_calls/finish_reason/model) and
  eating the 2048 cap since 0028 → **every 0031–0033 capability read was measured under
  invisible-truncation-risk. Asterisk those; they are not clean baselines.**
- **Representativeness datapoint:** run 2 cited `separability_matrix()` (concept-correct
  for the query); gold is the patch span inside `_cstack` → concept-location ≠
  patch-location (the 0026 axis). Eval-set scoring must account for
  concept-correct-but-patch-wrong.

**Three follow-ups (priority order, filed):**
1. **Reasoning observability** — per-turn reasoning-length in the trajectory artifact.
   NOT optional: the measurement-integrity fix closing the blind spot that corrupted the
   0031–0033 baselines. Priority one (spec 0034 being scaffolded).
2. `think` as an `explorer_*`-scoped, RECORDED knob (exposing/controlling a thing already
   happening, not adding a feature).
3. Eval-set paired thinking-arm vs default-arm A/B — the ONLY thing that settles
   causation. No more ad-hoc single runs.

**Operational incident (recorded honestly):** the first fixture-commit attempt landed
INSIDE the astropy measurement worktree (stale `cd`, relative paths), committed to its
detached HEAD; the push was denied by `astropy/astropy.git` (403, nothing egressed). The
worktree was hard-reset to base `d16bfe05a7` and the stray dir removed — the measurement
input was verified pristine. Lesson: a measurement worktree is SUT input; a stale cwd
can silently pollute it.

## ADR proposed for history.md

Prepended — see `.speccraft/history.md` 2026-07-09 (spec 0033).

## Architecture updates

"Spec 0033 architecture updates" section appended to `.speccraft/architecture.md`.

## Conventions proposed

None new at close — the tool-contract rule, two-normalize-passes scope note, and
0012→0025→0033 history were written in T15 (AC8). No duplication.
