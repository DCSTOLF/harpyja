---
spec: "0034"
closed: 2026-07-09
---

# Changelog — 0034 reasoning-observability

## What shipped vs spec

The measurement-integrity fix that closes the 0031–0033 blind spot: the reasoning
`qwen3:14b` on this Ollama generates by default was invisibly consuming the
`explorer_max_tokens=2048` cap and was DROPPED by the gateway. It is now surfaced
additively and recorded per-turn in the durable trajectory artifact. All 23 tasks
`[x]`, all 6 ACs MET, 1175 units pass, ruff 34 (= the 0031-era baseline, zero-new).

- **AC1 — gateway surfaces the hidden variable additively.**
  `ModelGateway.complete_with_tools` now returns `reasoning` and
  `usage.completion_tokens` alongside the existing keys (unchanged and pinned):
  `reasoning` absent → `None`, present-empty → `""` (the honest 0-vs-None source);
  `completion_tokens` from `usage` (absent → `None`). The cap's actual token currency
  is now visible next to chars. No transport change, no second outbound path.

- **AC2 — the backend accumulator (the DECIDED seam).** `wrapped_model_call` in
  `ExplorerBackend` grew from the `_last_served_model` last-write scalar into a
  per-turn accumulator appending `{reasoning_chars, completion_tokens, finish_reason}`
  per model response, reset per run, threaded via `build_trajectory_record` into BOTH
  the in-memory record AND `run_verified_case`'s hand-assembled written artifact. This
  seam is the ONLY place that observes a `finish="length"` FINAL turn — that turn never
  enters `model_turns` (the loop returns before the assistant message is added), so
  `per_turn` and `model_turns` carry an intrinsic length SKEW, pinned by test and
  documented at the record key (consumers must NOT zip positionally). A
  truncated-by-reasoning turn (`finish="length"` + `reasoning_chars > 0` + empty
  content) is distinguishable in the record from a content-truncated turn AND a clean
  turn — cap-pressure attribution possible for the first time.

- **think_mode — one canonical enum.** `derive_think_mode(think, enable_thinking)`
  returns `{default-omitted, native-think-true, native-think-false,
  chat-template-disabled, unknown}`; native (`think` explicitly set) WINS over the
  chat-template mechanism on double-set (the review's totality fix). One recorded field
  so the two mechanisms can never produce an ambiguous record.

- **Schema — `0033/1 → 0034/1`.** `VERIFIER_SCHEMA_VERSION` bumped;
  `_KNOWN_VERIFIER_SCHEMA_VERSIONS` extended to `{0031/1, 0033/1, 0034/1}` behind the
  0033 version gate; reasoning fields OPTIONAL everywhere (a non-reasoning model
  legitimately produces none), legacy 0031/1 + 0033/1 fixtures still validate.

- **AC3 — the knob, default-inert, pinned on the REQUEST BODY.**
  `Settings.explorer_think: bool | None = None` (tri-state; `None` ⇒ OMIT the param ⇒
  request byte-identical to pre-0034, captured params == `{"max_tokens": 2048}` under
  defaults; `True/False` send `think=that`). `bool | None` env coercion added to
  `_coerce`. Two-site ctor wiring — `wiring.py` AND `live_verifier.py`
  (`run_verified_case`); missing the second silently kills the live path. Deep outbound
  guard extended (`test_rlm.py` rots false on leak — Deep carries neither the knob nor a
  `think` param). Coexists with `explorer_enable_thinking` (the llama.cpp chat-template
  era) per OQ1's coexist resolution.

- **AC4 — outcome-equality regression.** `verify_trajectory` outcome-equality
  (status / failure_reason / four facts) over the valid-fixture set, with artifact-byte
  identity EXPLICITLY disclaimed (`to_dict()` stamps the current schema version).

- **AC5 — EXERCISED LIVE** (qwen3:14b / Ollama, precondition-probed via the new
  `probe_reasoning_default` helper — one sanctioned gateway call, instance-relative by
  design). Recorded `think_mode=default-omitted`, per-turn
  `reasoning_chars=[2086, 794, 1325, 2676, 1260, 1328, 1795]` — **~11K chars/run of
  previously invisible reasoning now durable in the artifact.** A later observation run
  caught the instrument earning its keep: a 6554-char reasoning turn produced a
  hallucinated grep scope (`"repo"`) whose bare-`[]` return read as no-matches — a
  coupling completely invisible pre-0034.

- **AC6 — the convention.** conventions.md gained the "invisible generation is a
  measurement-integrity defect" rule + the 0031–0033 baseline asterisk (written in T22;
  not touched at close).

## Review round — 10 findings, all applied

Two reviewers (codex + claude-p) returned `changes-requested` with ~10 targeted edits;
applied without a full re-round per the 0032/0033 flow. As landed:

1. **Evidence-provenance gap (the notable one).** The `max_tokens=20` reasoning-first
   probe cited in Why/AC2 was NOT in the committed findings — now committed as durable,
   re-runnable machine evidence under `probes/` (`probe_a_v1_max_tokens_20.json` shows
   `completion_tokens: 20` / `finish_reason: "length"` / all 20 tokens to `reasoning`,
   51 chars, zero content; probe B confirms the identical native `num_predict`
   mechanism; probe C the default-thinking finding; `run_probes.sh` re-runs them).
2. **Observability-only vs the request-body knob** — separated: Invariant reworded to a
   default-omit/no-op pin, backed by the AC3 request-body byte-identity test.
3. **OQ2 (capture route) resolved in-spec toward the backend accumulator** — the
   `LoopResult.history`/`session.messages()` route was code-verified unworkable
   (double-duty as the outbound wire messages; the truncated turn never enters history).
4. **Per-turn `finish_reason` named as a recorded field** (it was checked then discarded)
   so AC2's shape is expressible in the record.
5. **AC4 restated as outcome-equality**, byte-identity disclaimed.
6. **AC5 given a 0023-style not-exercised fallback** with a positive precondition probe.
7. **Reasoning unit named (chars)** + `completion_tokens` (tokens) surfaced additively;
   0-vs-None semantics pinned.
8. **Schema target `0034/1` named**, version-gate + legacy-default/missing-field
   behavior specified.
9. **OQ1 resolved toward coexist** with one recorded effective-mode enum (llama.cpp
   still a documented gateway target). OQ3 (full-text side-channel) dropped.
10. **Epistemic language tightened** — instance-relative ("qwen3:14b on this Ollama")
    and "invisible-truncation-RISK" rather than "cap pressure"; stale 0033 ref path
    fixed (0033 now under `specs/.archive/`).

## Deviations

- No major deviations; all 6 ACs MET as specified after the review edits.
- **T23 (optional REFACTOR) recorded no-op** — the per-turn tuple / none-vs-zero shape
  was already minimal; ruff stayed at the 34 baseline (zero-new), no dedup extracted.
- The 0033 drop-at-assembly lesson was PRE-EMPTED this time: the written-JSON artifact
  path (`run_verified_case`) was guarded by a written-JSON test (T12/T13) BEFORE any
  live run, so the persistence gap that the 0033 live run caught did not recur here.

## Files touched

- harpyja/gateway/gateway.py — AC1 additive `reasoning` + `completion_tokens`
- harpyja/config/settings.py — `explorer_think: bool | None`, `bool | None` env coerce
- harpyja/scout/explorer_backend.py — `derive_think_mode`, `_think` ctor arg + outbound
  wiring, the per-turn accumulator, thread into `build_trajectory_record`
- harpyja/scout/wiring.py — first ctor wiring site (`think=settings.explorer_think`)
- harpyja/eval/live_verifier.py — schema `0034/1` + gate, `build_trajectory_record`
  `per_turn`/`think_mode` params, `probe_reasoning_default`, `run_verified_case` second
  wiring site + artifact copy
- harpyja/deep/test_rlm.py — Deep outbound guard extended (AC3)
- harpyja/gateway/test_gateway.py, harpyja/config/test_settings.py,
  harpyja/scout/test_explorer_backend.py, harpyja/eval/test_live_verifier.py,
  harpyja/eval/test_live_verifier_integration.py — the RED/regression/drift/live pins
- .speccraft/conventions.md — AC6 invisible-generation rule + 0031–0033 asterisk (T22)
- specs/0034-reasoning-observability/probes/ — committed cap-mechanics evidence
  (probe A/B/C + `run_probes.sh`), the review's evidence-provenance fix

## User-agreed close items (from close-notes.md)

1. **Persistent live-test artifacts (named follow-up).** Three
   bucket-unanswerable re-runs were forced by `TemporaryDirectory` artifacts (0033-T14,
   the 0034 AC5 run, the original 0032 astropy loss). The per-field print fixes are
   reactive patches; the structural fix is live tests writing to gitignored
   `eval_work/live_artifacts/<test>/<timestamp>/` via the same outside-repo atomic
   writer. Being folded into spec 0035's harness work (its own live AC needs persistent
   artifacts).

2. **Silent-`[]` grep affordance gap (named input to the NEXT work — spec 0035).** A
   FILE-scope grep AND a nonexistent-scope grep both return bare `[]`, indistinguishable
   from no-matches; two attributable live observations (the 0033 astropy
   `scope="astropy/modeling/separable.py"` reads; the 0034-era `grep(scope="repo")`
   hallucinated directory off a 6554-char reasoning turn). Fix = typed model-visible
   in-conversation markers at the grep wrapper — a SUT change, so it goes in its OWN
   spec (0035, filed at this close, BEFORE the eval set, per the 0033 precedent: never
   baseline on a known tool-contract defect), with the capability-improvement claim
   WITHHELD (the eval set measures it).

## Astropy running tally (close context — the instrument stack is now COMPLETE)

`empty` ×4 (two honest, one found-then-dropped pre-0033, one honest with the
bogus-scope detour), `wrong-file` ×2, `right-file-wrong-span` ×1 (the first-ever
right-file + first `symbols` use, thinking-experiment run 2); `symbols` invoked in 2
runs. Every failure mode is now visible and attributable in the artifacts. The
instrument stack — 0031 verifier → 0032 parser dedup → 0033 path fix + counts → 0034
reasoning observability — is COMPLETE for the eval set to consume.

## ADR proposed for history.md

See the 2026-07-09 entry prepended to `.speccraft/history.md`.

## Conventions proposed

None new at close — AC6's "invisible generation is a measurement-integrity defect" rule
and the 0031–0033 baseline asterisk were written into conventions.md in T22 (not
duplicated here).
