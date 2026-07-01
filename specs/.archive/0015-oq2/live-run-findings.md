# Spec 0015 — live-run findings & deviations

Recorded during the operator OQ2 run (2026-06-30/07-01). This is a **measurement**
spec; per its invariant, defects surfaced at scale are recorded here as deviations
with a proposed fix + regression-test locus. Some are fixable in-scope (harness/AC8);
one is explicitly the out-of-scope gate-quality problem this spec exists to *measure*.

## Run status

- **AC1 proven:** live `mode=auto` runs to completion with no crash (0014 Deep fix
  holds at scale) — validated on a 3-case smoke.
- **Full N=50 did NOT complete** live: every long run wedged (see Deviation D3). The
  numbers below are from the 3-case smoke + a 6-case Scout probe + captured
  FastContext trajectories, not a full N=50 report.
- Provisioning: 50/50 worktrees across 12 repos (after fixing D0).

## Deviations

### D0 — provision worktree path bug (FIXED + regression test) — AC8
`cmd_provision` ran `git worktree add` with `cwd=<clone>` against a **relative**
`--work-dir`, so git created worktrees *under* the clone while the resolved fixture
recorded `wt.resolve()` (process-cwd-relative) — every recorded repo path 404'd.
- **Fix:** `swebench_eval.py::cmd_provision` — `work = Path(args.work_dir).resolve()`.
- **Test:** `test_swebench_eval.py::test_provision_relative_work_dir_resolves_to_real_worktrees` (network-free, local git repo).
- Status: **shipped in this spec's implementation.**

### D1 — default `scout_model` points at an unserved model (BUG, fixable in-scope) — AC8
`Settings().scout_model = "hf.co/mitkox/FastContext-1.0-4B-RL-Q4_K_M-GGUF:latest"` is
**not served** by the local Ollama (served set: `dstolf/…Q8` RL/SFT, `mitkox/…SFT`
Q4/Q5 — *not* `mitkox RL-Q4`). A live call returns **HTTP 404**. Compounded by the
CLI `run`/`sweep` having **no `--scout-model` flag**, so an operator cannot override
it from the CLI. Net effect: the out-of-the-box eval 404s on every case → Scout
`backend-error` / gate `scoring-failed` → a fully-degraded run for an *infrastructure*
reason, not a model-quality one. (The README already flags recommended-Q4 as
non-functional; this is worse — it isn't even pulled.)
- **Proposed fix (AC8):** (a) add `--scout-model` to the `run`/`sweep` CLI parsers +
  thread through `_settings_from_args`; (b) optionally flip the default to a served
  model. Regression-test locus: `test_swebench_eval.py` (CLI arg → settings override)
  + a wiring test asserting `_settings_from_args` honors `--scout-model`.
- **Impact on this run:** worked around via the Python `run_oq2_sweep` entrypoint with
  an explicit Q8 override; the CLI path remains broken until fixed.

### D2 — gate judge rejects CORRECT citations (the AC4 finding; fix is a SEPARATE spec)
The verification gate scores relevance by reusing **`scout_model` — a FastContext
citation-*finder* fine-tune — as a relevance *judge*** (`gate.py::make_scout_model_judge`)
via a plain chat prompt ("reply with a single number 0–1"). That is out-of-distribution
for that model. Evidence: **astropy-12907 cited the correct file** (`separable.py`, the
actual bug location, 3 valid spans) and the gate returned **`gate-low-confidence`**.
Additionally `_parse_score` (`gate.py:95`) grabs the **first number anywhere in the
reply** — so a reasoning reply that mentions a line number ("…at line 219…") scores
`219 → clamp 1.0`, while "0, because…" scores 0. The relevance signal is essentially
noise, biased toward rejecting correct answers.
- **This is precisely the requests-1766 / AC4 "gate false-escalation of a correct
  Scout answer."** It is the phenomenon spec 0015 is built to MEASURE; per Out-of-Scope,
  *fixing* the gate is a separate gate-quality spec.
- **Consequence for OQ2:** if the full run confirms this rate is material and reliable,
  the honest OQ2 outcome is `gate_quality_confounded` (AC5) — a calibration tuned over
  this gate would be measuring gate dysfunction, not gate tuning.
- **Note:** the AC4 gate-false-escalation metric is computed over the *auto* path
  (escalation must be observed); a Scout-only `mode=fast` run cannot produce it.

### D3 — model gateway has NO HTTP timeout → runs wedge indefinitely (BUG, fixable in-scope) — AC8
`gateway.py::_default_transport` calls `urllib.request.urlopen(req)` with **no
`timeout=`**. `urlopen` blocks forever without one, so a stalled Ollama response
(FastContext Q8 on a ~1,880-file repo can stall the server; a torn-down socket after
sleep/500 also triggers it) **wedges the whole run** — observed as `STAT SN`, 0% CPU,
2.5 h elapsed, no progress, with an httpx `RuntimeError('Event loop is closed')` at
connection teardown. `caffeinate` was active during the wedge, ruling out sleep as the
sole cause. This is why every long live run failed to complete.
- **Proposed fix (AC8):** thread a timeout into `_default_transport`/`ModelGateway.complete`
  (e.g. `urlopen(req, timeout=settings.<gate_timeout_s>)`), default ~60–120 s, so a
  stalled call raises (→ typed degrade) instead of hanging forever. Regression-test
  locus: `test_gateway.py` — inject a transport/socket that never returns and assert
  `complete` raises within the timeout rather than blocking.
- Related: `run_swebench`'s `per_case_timeout` uses `ThreadPoolExecutor(max_workers=1)`;
  `fut.result(timeout=…)` cannot kill the blocked worker thread, so subsequent cases
  deadlock behind it — the timeout must live at the HTTP layer (D3 fix), not only the
  executor.

## What was verified NOT a bug (ruled out)
- **`parse_final_answer`** parses a real Q8-RL final answer correctly (3 citations from
  `path:start-end (explanation)` lines) — the grammar matches the model's output.
- **Suffix recovery is wired** (`scout/wiring.py:46` loads `file_set` from the manifest);
  the model's out-of-repo absolute paths (`/astropy/…`) recover to in-repo paths.

## Observed Scout behavior (indicative, small-N)
- Model emits **out-of-repo absolute paths** (`/astropy/modeling/separable.py`) —
  recovery handles these.
- 6-case probe: 4/6 `scout-empty`, 2/6 produced citations (`gate-low-confidence`),
  0/6 a confident Scout pass. Empty cases finished fast (14–25 s) vs cited cases slow
  (76–291 s). **Dropped-vs-genuinely-empty breakdown: PENDING** a bounded tally run
  (the full N=50 report never completed due to D3).
