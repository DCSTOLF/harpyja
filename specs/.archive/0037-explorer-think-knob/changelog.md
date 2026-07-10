---
spec: "0037"
closed: 2026-07-10
---

# Changelog — 0037 explorer-think-knob

## What shipped vs spec

This spec asked ONE question — does the 0034 `explorer_think` knob actually
toggle thinking on the Ollama `/v1` path? — and answered it with committed,
test-pinned live evidence: **NO.** The typed probe outcome is `no-op`. The spec
closed on its named **NO_OP_BLOCKED** terminal path, one of the two legitimate
terminal outcomes the spec pre-authored. No SUT code changed; the deliverable is
the probe result, the durable finding, and the two conditional tripwire pins.

Per-AC terminal disposition:

- **AC1 [probe] — EXERCISED, outcome `no-op`.** `probes/run_probes.sh`
  (curl-on-loopback, `qwen3:14b`, `http://localhost:11434/v1/chat/completions`)
  ran the three-factor generation-level discriminator. Under the tiny-cap
  (`max_tokens=60`) all three `/v1` arms — `think:true` / `think:false` /
  omitted — are behaviorally IDENTICAL: reasoning generated (205–256 chars),
  empty content, `finish_reason="length"`, all 60 tokens consumed
  reasoning-first. The supplementary `chat_template_kwargs{enable_thinking:false}`
  arm is EQUALLY ineffective (197 reasoning chars) — so the outcome is `no-op`,
  not `chat-template-effective`. The result is committed as
  `probes/probe_result.json` (schema `0037/1`) and pinned by
  `harpyja/eval/test_think_probe_result.py` (8 tests, including the
  committed-file drift-pin) so the claim cannot drift from the evidence. New
  module `harpyja/eval/think_probe.py` carries the typed outcome enum
  (`PROBE_OUTCOMES`), the `0037/1` schema version, the loud `validate_probe_result`
  / `load_probe_result`, and `ProbeResultError`.
- **AC2 [unit — conditional] — CONDITIONAL-SKIP (the legitimate close).**
  `test_explorer_backend.py::test_explorer_think_pin_gated_on_native_probe_outcome`
  is authored, loads the committed probe outcome, and skips with the
  machine-recorded `no-op` reason. Per the branch invariant this is a valid
  terminal disposition — the underlying 0034 tri-state threading remains green
  (AC4). If a future reconciliation spec re-runs the probe and flips the outcome
  to `native-think-effective`, this pin AUTO-ACTIVATES and enforces the tri-state
  request-body assertion (with the `chat_template_kwargs` hedge dropped) — zero
  test edits.
- **AC3 [integration — conditional] — CONDITIONAL-SKIP (the legitimate close).**
  `test_live_verifier_integration.py::test_live_think_knob_three_factor_effectiveness`
  is authored with the THREE separate, non-collapsible assertions ((a) per-turn
  `reasoning_chars`, (b) tiny-cap generation-level discriminator, (c)
  `completion_tokens` cross-check + `<think>`-in-content leak scan), the
  `probe_reasoning_default` gate, the `qwen3:14b` `/api/tags` preflight, and the
  N=1 off-arm strength stated in the docstring. It skips at the outcome gate with
  the recorded `no-op` reason and AUTO-ACTIVATES on a future outcome flip.
- **AC4 [regression] — GREEN.** All four 0034 pin files pass in full — 147
  passed, 1 skip (the new conditional AC2 pin). The shipped knob is
  assert-still-works, not re-built: tri-state request-body pin, `bool|None` env
  coercion + field-default drift-guard, `think_mode` in trajectory record AND
  written artifact, and the Deep-scope leak guard (rots-false on `explorer_`-scope
  leak).
- **AC5 [doc] — DONE.** `findings.md` records the NO_OP_BLOCKED close: the
  `/api/chat` control that localizes the defect, the A/B-blocking consequence, the
  no-default-flip statement, and the N=2 think-experiment cited as
  motivation-for-the-A/B, explicitly NOT as evidence thinking helps.

## Key finding

The `/api/chat` control (`probes/probe_arm_native_api_think_false.json`)
`think:false` → content `"391"` (correct answer), zero thinking chars,
`done_reason="stop"`, `eval_count=4` — proves the param name and the model-side
mechanism are RIGHT. Ollama's OpenAI-compat `/v1` layer silently DROPS the
top-level `think` field. The 0034 knob as wired sets a field the endpoint ignores;
thinking is effectively ALWAYS ON through the gateway. The thinking A/B is BLOCKED
(no thinking-off arm is constructible), and reconciliation — routing `think` via a
path that honors it — is a named follow-up spec, never a silent re-point of
`explorer_think` at a different mechanism.

## Deviations

- **T7 (per-mode live effectiveness run) NOT run — per the branch gate, not a
  gap.** Against a no-op knob the three modes (on/off/default) are three identical
  thinking-on runs; running them would prove nothing. `run_effectiveness.sh` was
  correctly NOT authored — the plan's Step 7 driver exists only to exercise a knob
  the probe proved inert. Recorded as the honest branch disposition, not a skipped
  deliverable.
- **OQ2 (off-arm vs `max_tokens` budget interaction) NOT EXERCISED** — no genuine
  off arm exists on this endpoint, so the interaction is unmeasurable here.
  Recorded, not papered.
- No schema bump: `probe_result.json` is a spec-local `0037/1` artifact, NOT a
  verifier field; `VERIFIER_SCHEMA_VERSION` is untouched.

## Out-of-scope drift found (for /speccraft:sync or a follow-up)

The full suite is **1251 passed / 30 skipped / 1 failed**. The 1 failure is
**PRE-EXISTING drift on `main`, NOT 0037**:
`harpyja/eval/test_terse_floor.py::test_committed_full_set_report_matches_computed_truth`
hardcodes `specs/0036-terse-query/full_set_report.json`, but 0036's close
archived that dir to `specs/.archive/0036-terse-query/`. The test was written at
`f58c29d` and the dir moved at `5e3b666`; the suite was evidently not re-run after
the move. This is a stale committed-path pin unrelated to the think knob — flagged
here as a drift item to fix in `/speccraft:sync` or a follow-up (re-point the test
at the archived path, or make the locator archive-aware).

## Test / lint numbers

- Full suite: 1251 passed / 30 skipped / 1 failed (the 1 = the pre-existing 0036
  drift above, out of scope).
- 0034 regression set: 147 passed (1 skip = the new conditional AC2 pin).
- Ruff: zero-new vs `main` (41 = 41).

## Files touched

- `harpyja/eval/think_probe.py` (NEW — typed outcome enum + `0037/1` schema + loud validator/loader)
- `harpyja/eval/test_think_probe_result.py` (NEW — 8 tests pinning the outcome space, the validator, and the committed evidence file)
- `harpyja/scout/test_explorer_backend.py` (AC2 conditional tripwire pin added)
- `harpyja/eval/test_live_verifier_integration.py` (AC3 three-factor conditional tripwire test added)
- `specs/0037-explorer-think-knob/probes/run_probes.sh` (NEW — committed curl-on-loopback operator driver)
- `specs/0037-explorer-think-knob/probes/probe_result.json` (NEW — typed outcome `no-op`, schema `0037/1`, test-pinned)
- `specs/0037-explorer-think-knob/probes/probe_arm_*.json` (NEW — five raw arm outputs incl. the `/api/chat` control)
- `specs/0037-explorer-think-knob/findings.md` (NEW — the NO_OP_BLOCKED close record)
- `.speccraft/index.md` (active-spec pointer)

## ADR proposed for history.md

See the appended entry below (2026-07-10 — spec 0037). Headline: the 0034
`explorer_think` knob is a live-verified NO-OP on the Ollama `/v1` path; the
compat layer drops the field; the mechanism works on `/api/chat`; the thinking A/B
is blocked; reconciliation is the named next spec.

## Conventions proposed

- New: "**A capability-adjudicating live probe returns exactly one value of a
  committed TYPED-OUTCOME enum, persisted as a schema-versioned spec-local
  artifact pinned by a unit test, with downstream ACs CONDITIONAL on the recorded
  outcome — a tripwire: the conditional tests skip with the machine-recorded reason
  and AUTO-ACTIVATE with zero edits when a future run flips the outcome.**"
  Rationale: 0037 asked a yes/no capability question whose answer (`no-op`) blocks
  downstream work; pinning the typed outcome to committed evidence and gating the
  ACs on it makes the block auditable and self-healing — a reconciliation spec that
  flips the probe enforces the withheld pins automatically. Extends the 0023
  named-outcome discipline and the committed-driver rule; distinct from both.
- New: "**Proving a GENERATION-CONTROL knob works is a GENERATION-level claim, not
  a REPORTING-level one — never assert only on the response field the knob is
  supposed to suppress.**" Rationale: a `think:false` that merely hides the
  reasoning field while the model still burns thinking tokens would fake a working
  off-arm; the proof needs evidence the MODEL's behavior changed (tiny-cap
  discriminator + token accounting + `<think>`-leak scan), non-collapsible.
  Sibling to the 0030 presence-proxy false-capability rule, one level down.
