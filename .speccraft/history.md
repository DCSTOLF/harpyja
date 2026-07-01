# History

Append-only. Newest first.

## 2026-07-01 — Spec 0017 (gateway_http_timeout) shipped — the B3 fix from 0015: a finite `urlopen(timeout=)` makes the un-raisable raisable so the existing gate degrade can fire

**Spec:** specs/0017-gateway-http-timeout/
**Decision:** Close **B3** from spec 0015 (`live-run-findings.md`) — the Model Gateway's
outbound HTTP call had **no timeout** (`_default_transport` did `urlopen(req)`, default
`None` → block forever), so a stalled/torn-down local Ollama connection wedged the whole
`mode=auto` run indefinitely (observed 2.5 h at 0% CPU with `caffeinate` on) — as a pure
**reliability/plumbing** fix: no tier logic, no gate algorithm, no classifier, no citation
format touched. Six durable points. (1) **A call that can hang forever can never degrade —
so the fix is to make the un-raisable raisable, NOT to add a new degrade path.** The
Verification Gate *already* wraps the judge call in `except Exception → GateOutcome(failed=True)`,
but that safety net never fired because an un-timed-out `urlopen` raises **nothing**; it just
hangs. A finite `urlopen(req, timeout=timeout_s)` converts the silent infinite wedge into a
raised `TimeoutError`/`URLError` that the *existing* catch turns into a graceful degrade —
the "always degrade gracefully" guardrail applied to the one place it structurally could not.
(2) **The finite floor lives on the constructed object's own field default, not only on
Settings.** `ModelGateway.timeout_s: float = 120.0` is finite at the **dataclass default
itself** (AC2), so *any* `ModelGateway(...)` — the two wired sites AND a bare/test/unwired
construction — is hang-bounded out of the box; a default living only on `Settings.lm_http_timeout_s`
(AC1) would leave direct constructions falling back to unbounded `None`. (3) **Seam-preserving
threading (D3).** The timeout rides the gateway and is bound onto the default transport via
`functools.partial(_default_transport, timeout_s=self.timeout_s)` **only when `transport is None`**;
the injectable `Transport` signature `(url, payload) -> dict` is untouched, so every existing
injected fake keeps working. (4) **Timeout-degrade visibility (D4) extends the 0014 convention
to the gate as a LOG signal, not a schema field.** The timeout still degrades through the gate's
existing generic catch, but the path is branched to emit a **distinct timeout-naming WARNING**
(`isinstance(err, (TimeoutError, socket.timeout, URLError))`) so "judge timed out" is separable
from a parse/other failure in operator diagnostics — no `GateOutcome` schema change (a structured
gate-degrade-cause taxonomy stays deferred as a gate-quality concern). (5) **Per-socket-op, not
total-deadline honesty (no-false-capability).** `urlopen(timeout=)` bounds connect and each
blocking read — exactly the observed pathology (accept-then-go-silent trips the read timeout) —
and the spec claims only that; a dribble-slow endpoint could still outlast it, an acknowledged
stdlib-transport limit, out of scope. The default `120.0 s` is deliberately **decoupled** from
`deep_wall_clock_ms` (60 s) — they bound different things (D1), no per-request layer (D2). The
air-gap floor is preserved: `assert_local` still runs **before** egress on the default-transport
path (AC9). Both production sites construct with `timeout_s=settings.lm_http_timeout_s` —
`orchestrator/wiring.py` (the observed B3 hang path) and `scout/wiring.py` (defense-in-depth on
Scout's largely-vestigial Path-A gateway).
**Why:** Spec 0015's OQ2 measurement never completed a single full sweep because this call could
hang forever; the sibling B1 serving fix (0016) is not enough on its own. This is the narrow
robustness prerequisite for re-attempting OQ2 — make a stalled endpoint fail fast and degrade
visibly instead of wedging the run — without touching any tier or gate behavior. It makes no
model faster or better; it makes a hung model *fail fast and visibly*.
**Consequence — B3 closed; the 0015 blocker sequence is now B1(0016)+B3(0017) fixed, B2 and the
OQ2 re-run still open.** Shipped TDD-complete: **+14 unit (725 total, was 711)**, ruff clean; +1
integration. Load-bearing proof is **AC7** — a deterministic loopback server that accepts the
connection then withholds all bytes, driven through `complete()` with a tiny `timeout_s`, raises
in **<1 s** rather than hanging (the real socket-stall pathology bounded, not merely a fake that
can raise) — plus AC5 (a raised timeout yields `GateOutcome(passed=False, failed=True)`, degrade
not crash) and AC3 (the timeout is really threaded to the blocking op, proven by monkeypatching
`urlopen`). AC11 optional live-Ollama happy-path smoke passed (6.15 s, skip-not-fail, explicitly
**not** the stall proof). Docs made consistent in the same change (blast-radius convention):
`settings.py` field comment + module-docstring toml example, the `_default_transport` docstring
(now states the bound), ARCHITECTURE §2.8, and the README config-knob list. **Out of scope /
follow-ups carried forward:** **B2** — the gate-as-judge false-escalation (the FastContext finder
reused as a relevance judge rejecting correct citations — a separate gate-quality spec, orthogonal:
B3 is *when the call hangs*, B2 is *how the reply is judged*); **re-attempting the OQ2 measurement**
(a fresh spec now that B1+B3 land); a **total-request deadline / dribble-slow defense** (per-op
`urlopen(timeout=)` is by design); **Deep's `dspy.RLM`/litellm timeout** (a separate outbound
socket, dspy-managed); **retry/backoff on timeout** (this spec fails fast and degrades); and, still
open from Wave 2, **Wave-2.1 substring/fuzzy matching**.

## 2026-07-01 — Spec 0016 (scout_model) shipped — the B1 serving/plumbing fix from 0015: two Settings defaults flipped to SERVED tags + a CLI override escape hatch

**Spec:** specs/0016-scout-model/
**Decision:** Close **B1** from spec 0015 (`live-run-findings.md` D1) — the out-of-box eval
could not reach a served model — as a pure **serving/plumbing** fix: two `Settings` default
VALUES flip to served Ollama tags and two CLI override flags are added, with **no** change to
tier logic, the classifier, the citation format, or the gate's algorithm. Four durable points.
(1) **A `Settings` default must name a SERVED model.** `scout_model` flips from the UNSERVED
`hf.co/mitkox/FastContext-1.0-4B-RL-Q4_K_M-GGUF:latest` (HTTP 404 on every Scout call → a
fully-degraded run for a non-model reason) to the served `hf.co/dstolf/FastContext-1.0-4B-RL-Q8_0-GGUF:latest`;
`lm_model` flips from the llama.cpp placeholder `"local"` to the served
`hf.co/Qwen/Qwen3-8B-GGUF:latest`. An unserved default is an infrastructure defect, not a
config preference — the same no-false-capability discipline applied to model *tags*. (2) **The
scout flip is stated cross-subsystem coupling, not a hidden gate change (D-body caveat).**
Because `verify_method="scout_model"` is the only shipped gate backend, `scout_model` does
double duty — Scout-tier retrieval AND the model the Verification Gate scores citations with —
so the flip changes *which served model the gate calls* (broken→served plumbing), which is
deliberately DISTINCT from the still-open **B2** gate-*judging-logic* problem; the next OQ2 run
must not conflate the two. (3) **The `lm_model` flip is intentionally GLOBAL, blast radius named
and accepted (D2).** It is a bare `Settings` default, so it hits **every** `Settings()` caller —
the eval `run`/`sweep` drivers AND the MCP server's `mode=auto` Deep tier — not only the eval
CLI. Against Ollama (the primary supported backend for this arc) the old `"local"` was already
unserved; against a llama.cpp `llama-server` endpoint `"local"` was a benign don't-care and the
Ollama-style Qwen tag will not resolve, so a llama.cpp operator relying on the default regresses
— mitigated by the unchanged override precedence (toml/env/`--deep-model`). The Qwen default is
provisional ("for now"), not a long-term Deep choice. (4) **A canonical flag with a deprecated
alias reconciles order-independently at the app layer, not via argparse positional last-wins
(D1).** `run`/`sweep` gain `--scout-model` (the missing escape hatch — an operator can now name
any served model without a source edit or the Python workaround the 0015 run needed) and the
canonical `--deep-model`; `--lm-model` is kept as a **deprecated** back-compat alias on a
**distinct argparse dest**, and `_settings_from_args` reconciles `deep = args.deep_model or
args.lm_model` so the canonical flag wins regardless of CLI order. Every override is built via
`dataclasses.replace` on a fresh `Settings()` — the frozen base-not-mutated contract preserved.
**Why:** Spec 0015's OQ2 measurement degraded on every case for an infra reason — the default
Scout model 404'd — and the CLI had no way to override it, so the out-of-box eval could not even
reach a served model. This spec is the narrow prerequisite for re-attempting OQ2: make the
default *served* and give the operator a source-edit-free escape hatch, without touching any tier
or gate behavior. It does NOT claim any model is *good*, only that the default is *served*
("served" is instance-relative — the claim is narrow: the new tags are in the documented required
local Ollama set, replacing a tag served nowhere in it). (Repo memory: the dev host is now 32 GB
and the dstolf Q8 SFT/RL tags are pulled locally, so the served-set claim is live-validated.)
**Consequence — B1 closed; B2/B3 and the OQ2 re-run remain separate specs.** Shipped
TDD-complete: **711 unit pass**, ruff clean; +11 new unit (2 config incl. an AC6 field-default
**introspection** drift guard asserting `dataclasses.fields(Settings)` no longer carries the old
unserved scout tag nor `"local"` — never a source grep; 9 CLI incl. the both-orders D1 test and
`--help` introspection) plus the flipped `_FC_GGUF` constant driving the existing default test,
and +1 integration `test_scout_model_default_present_in_ollama_served_set` — a **positive**
`/api/tags` membership check with a three-way branch (Ollama unreachable → skip; tag absent →
skip-with-diagnostic; the old unserved tag as default → FAIL), so it cannot pass trivially with
the endpoint down; validated live (the Q8 default IS served). Docs made consistent in the same
change (blast-radius convention): the `settings.py` `scout_model`/`lm_model` comments + the
module-docstring toml example, the `_settings_from_args` docstring (no longer claims the Deep
default is `"local"`), and the README model-guidance callout. **Out of scope / open follow-ups
carried forward:** **B2** — the gate-as-judge false-escalation (the FastContext finder reused as a
relevance judge rejecting correct citations, requests-1766/astropy-12907 — a separate gate-quality
spec); **B3** — the model-gateway `urlopen` with no HTTP timeout (wedges a run indefinitely — a
separate reliability spec); **re-attempting the OQ2 measurement** (a fresh spec after B1/B2/B3);
choosing the **permanent** Deep model (the Qwen3-8B default is provisional); validating the Q8
memory footprint / 8 GB-Q4 hardware floor; and, still open from Wave 2, **Wave-2.1 substring/fuzzy
matching**.

## 2026-07-01 — Spec 0015 (OQ2) CLOSED as a FAILED RUN — implementation reverted, B0 salvaged, B1/B2/B3 seed new specs

**Spec:** specs/0015-oq2/ (status: closed, outcome: failed-run)
**Decision:** The live `mode=auto` OQ2 measurement over the 12-repo SWE-bench subset could
NOT be completed, so the spec is closed for its **findings**, not its deliverable. AC1 was
partially proven (a 3-case smoke ran `mode=auto` to completion with no crash — the 0014 Deep
`AdapterParseError` fix holds at scale), but the full N=50 run never finished and AC2–AC7
were not delivered. Rather than carry un-exercised measurement code, the **entire OQ2
implementation was reverted to HEAD (7aedad8)** — typed-outcome enum + precedence, per-point
degrade gate, gate-confound threshold, report schema bump `0013/1→0014/1` +
`combined_degrade_rate`, sweep provenance, sibling-driver wiring, `run_oq2_sweep`, `make
oq2-full`, and their tests. **One incidental fix was salvaged (B0):** provisioning ran `git
worktree add` with `cwd=<clone>` against a *relative* `--work-dir`, so git created worktrees
under the clone while the resolved fixture recorded `wt.resolve()` (process-cwd-relative) —
every path 404'd; fix is `cmd_provision`: `Path(args.work_dir).resolve()`, locked by
`test_provision_relative_work_dir_resolves_to_real_worktrees` (network-free, local git repo).
**Three blockers explain the failure and seed follow-up specs:** **B1** — `Settings().scout_model`
defaults to `hf.co/mitkox/FastContext-1.0-4B-RL-Q4_K_M-GGUF:latest`, which is not served (HTTP
404), and the CLI has no `--scout-model` flag, so the out-of-box eval degrades on every case
for an infra reason. **B2** — the verification gate reuses `scout_model` (a citation-FINDER
fine-tune) as a relevance JUDGE via a plain "reply 0–1" prompt; it scored astropy-12907's
CORRECT citation (`separable.py`, the real bug site) as `gate-low-confidence`, and
`_parse_score` grabs the first number in the reply (a line number → clamps to 1.0). This IS
the AC4 / requests-1766 gate-false-escalation phenomenon; its fix was always scoped as a
separate gate-quality spec. **B3** — `gateway.py::_default_transport` calls `urlopen(req)`
with no `timeout=`, so a stalled/torn-down Ollama connection (FastContext Q8 on a ~1,880-file
repo, or a socket dropped across sleep/500) wedges the run forever (observed 2.5 h at 0% CPU
with `caffeinate` on); related, `run_swebench`'s `ThreadPoolExecutor(max_workers=1)` per-case
timeout cannot kill the blocked worker so cases deadlock behind it. This is why no full run
completed. **Verified NOT bugs (don't re-chase):** `parse_final_answer` parses real Q8-RL
output correctly; suffix recovery is wired (`scout/wiring.py:46`). Lesson: this measurement
needed the serving/robustness layer (B1/B3) hardened and the gate quality (B2) understood
BEFORE a multi-hour live sweep was attempted — the sweep machinery was premature. Detail in
`specs/0015-oq2/live-run-findings.md` + `changelog.md`. **700 unit pass** after revert, ruff
clean.

## 2026-06-30 — Deep AdapterParseError → typed parse-error degrade shipped — the second typed-degrade floor, with first-class visibility (the rule promoted to a standing convention)

**Spec:** specs/0014-adapterparseerror/
**Decision:** Close the known Deep crash path the spec-0012 AC5 run surfaced (a malformed
dspy/model response raised `AdapterParseError` out of the RLM driver and aborted the whole
run, forcing AC5 to `mode=fast`) — the **same defect class** as the original Scout
backend-error bug (0005/0007): a third-party parse failure that should map to a typed
tier-floor but instead crashes. Harden it **before** the full 12-repo OQ2 sweep, where an
unhandled exception at hour three loses the entire long run. Five durable choices pinned.
(1) **A named, narrow-caught seam earns its OWN cause — a sibling, not a replacement.**
`harpyja/deep/errors.py` adds `PARSE_ERROR = "parse-error"` next to `BACKEND_ERROR`:
`AdapterParseError` is a *recognized, pinned, typed* seam, the opposite of the
`backend-error` catch-all-for-the-unforeseen, so an operator can tell "the dspy adapter
could not parse the model output" apart from "something unforeseen blew up." Truly-unexpected
Deep exceptions still fold to `backend-error` (unchanged); the narrow catch is exactly what
keeps the two distinct (AC4). (2) **Pinned-against-source, dspy-absent-safe narrow catch at
the one seam.** `rlm.py::_adapter_parse_error_types()` lazily resolves
`dspy.utils.exceptions.AdapterParseError` — the single class all four adapters raise (and
into which `JSONAdapter` wraps a raw `json.JSONDecodeError`), per the dspy 3.2.1 source read,
so catching it alone is neither over-narrow nor over-broad — and returns the empty tuple when
dspy is absent (`except ()` catches nothing, preserving the module's no-top-level-`import
dspy` rule). It wraps **only** the `rlm(query=...)` forward call →
`raise DeepUnavailable(PARSE_ERROR) from err`; `_assert_local` (AirGapError floor) and
`_rlm_factory` (config faults) stay outside the try, and `parse_citations` never raises.
(3) **Typed-failure-only boundary preserved (the 0006 invariant both reviewers called this
tier's most important property).** A malformed response degrades; a *well-formed but
weak/empty-citation* response stays an honest Tier-2 result — collapsing the two into one
degrade would silently convert real escalations into floors, which is precisely why Deep
earns a typed floor rather than a blanket `try/except`. Regression-guarded on both sides
(AC1 malformed degrades; AC3 weak-but-real does not). (4) **No orchestrator change — proven,
not assumed.** `_locate_deep`/`_run_deep` already build `deep-degraded:{cause}` notes
generically, so a routing regression lock (`test_locate_deep_parse_error_degrades_to_scout`)
proves no production routing change is needed and pins AC5: `tiers_run` reflects the floor
REACHED (`[0,1]`), NOT a Tier-2 result; the attempt-and-degrade stays visible via the stable
`deep-degraded:parse-error` note + the first-class `deep_degrade_rate`, never via `tiers_run`,
so a floored run cannot read as "Deep never ran." (5) **Degrade made visible, not just safe —
the third time a graceful floor could hide a defect.** Report `SCHEMA_VERSION 0012/1 → 0013/1`
adds additive last-with-default twins `deep_degrade_count` / `deep_degrade_rate`
(null-with-zero-count on a zero denominator, never a false `0.0`) in the one
`_AGGREGATE_DEFAULTS` source, so both old- and new-shape blocks pass the single loud
validator. `runner.py` adds `_is_deep_degraded` (sharing one `_has_degrade_note` predicate
with `_is_scout_degraded`), and `degraded_dominated` now keys off the **UNION** of scout+deep
per-case degrades — a case counted **once** even when both tiers floor (a sum would
double-count) — while the per-tier rates stay separate for attribution (AC11). The single
producer `aggregate_outcomes` means the swebench sibling driver populates the fields with NO
`swebench_eval.py` change, proven by a sibling lock test (the recurring missed-consumer lesson).
**Why:** This is the **second** typed-degrade floor, so the visibility rule is promoted from a
per-spec fix to a **standing project convention** — every typed-degrade floor surfaces its
rate in aggregate or it goes dark exactly the way Scout's `format_citations` crash did.
Baking it only into this report schema would leave the *next* floor free to go dark, so the
convention is itself a close deliverable (AC12, P13).
**Consequence — the sweep is crash-unblocked; the rule is now a convention, not a one-off.**
Shipped TDD-complete: **699 unit pass**, ruff clean; the AC8 integration
`test_deep_auto_parse_error_degrades_not_crash` (deterministic injected fault, skip-not-fail)
drives the real `RlmBackend` → `DeepEngine` → `locate(mode=auto)` to completion with the
degrade recorded, so the spec-0012 AC5 `mode=fast` workaround can revert to `mode=auto`. One
new stable cause id joins the taxonomy (`deep-degraded:parse-error`); report schema is now
`0013/1`. **Deviation:** a pre-existing `test_report_schema_version_is_0012` exact pin was
converted to a `bumped_past_0012` ratchet (the codebase's established pattern), with the new
exact pin `test_report_schema_version_is_0013`. **Blast radius by category:** cause taxonomy
(`deep/errors.py`) → RLM seam (`deep/rlm.py`) → orchestrator routing (unchanged, lock only) →
report schema (`eval/report.py`) → runner aggregation (`eval/runner.py`) → swebench sibling
(unchanged, lock only). Open follow-ups carried forward: **`ContextWindowExceededError`** —
the only sibling dspy exception, a *distinct* failure (prompt exceeds the context window) that
still escapes the RLM and would crash a run, a candidate for its own future
`deep-degraded:context-window` cause (folding it into `parse-error` would break the
narrow-catch invariant); the **full 12-repo OQ2 sweep** this now unblocks (crash-free) but
does not run; the **gate false-escalation of a correct Scout answer** (requests-1766); the
**Q8 `scout_model` default flip** (deferred, variance-gated); and, still open from Wave 2,
**Wave-2.1 substring/fuzzy matching**.

## 2026-06-30 — FastContext dependency source swapped to the DCSTOLF fork (identical rev, no behavior change)

**Spec:** specs/0013-fastcontext/
**Decision:** Repoint the Tier-1 Scout FastContext git source from
`microsoft/fastcontext` to `DCSTOLF/fastcontext` at the **same pinned rev**
`1522d6d6b5e040e817b468e12826662aa069a8b0` — a pure source-of-supply swap with
**no version bump and no behavior change** (the resolved code is byte-identical).
`pyproject.toml` `[tool.uv.sources]` URL, the regenerated `uv.lock` source entry +
dependency-edge marker, and the `README.md` / `FASTCONTEXT_INSTALL.md` clone URLs all
move to the fork; a new `harpyja/test_fastcontext_source.py` drift-guards the source,
the unchanged rev (AC3 byte-identity), and the absence of any surviving
`microsoft/fastcontext` URL. **"Microsoft FastContext" prose attribution is left
intact** (the fork is a fork of MS's project, so the credit stays accurate); only the
URLs changed. No `harpyja/scout/` code touched.
**Why:** Move to a controlled fork source so future local FastContext fixes (the open
`format_citations` crash, recommended-Q4 quality leads) can be carried **without
bumping the pin**. This spec is only the source swap; carrying actual patches is a
deliberate later effort.
**Consequence:** Scout now resolves FastContext from the owned fork at the identical
rev. **683 unit pass** (+5 new source/rev/no-stale-URL guards), ruff clean; **38 Scout
integration tests pass** against the fork (live), confirming no behavior change;
`uv lock --check` resolves 144 packages consistently. The plan's "fork-not-pushed /
network" risk was moot — the fork resolved and built cleanly on first `uv run`. Open
follow-ups carried forward: **carrying the actual FastContext patches** onto the fork
(the `format_citations` robustness fix, Q4 quality leads — now unblocked by owning the
source); the **Q8 `scout_model` default flip** (deferred, variance-gated); the **gate
false-escalation of a correct Scout answer**; the **Deep `AdapterParseError` robustness
gap**; and, still open from Wave 2, **Wave-2.1 substring/fuzzy matching**.

## 2026-06-29 — Scout path-suffix recovery shipped — rescue an out-of-repo hallucinated citation by its unique, manifest-keyed in-repo suffix, composing with (never bypassing) the 0011 drop + honesty floor

**Spec:** specs/0012-path-prefix/
**Decision:** Close the remaining `scout-empty` tail the spec-0010/0011 Q8
re-measurement exposed — **7/12** cases died not because the model found nothing but
because it emitted **out-of-repo absolute paths** fabricated from the repo slug (e.g.
`/pallets/flask/src/flask/blueprints.py`), which spec 0011 correctly **drops** as
out-of-repo (10 dropped in the N=12 auto run) — with a **deterministic,
model-independent** recovery: map such a citation to a real in-repo file by its longest
**unique, specific** path suffix against the repo's own indexed manifest set, only ever
keeping a path that actually exists. The **`scout_model` default was NOT flipped** (a
separate, deferred follow-up). Four durable choices were pinned. (1) **Recover only to an
existing, unique, manifest-keyed path — never a guess.** `normalize.py::_recover_suffix`
tries `k` from the cited path's full length down to `MIN_TAIL_SEGMENTS=2`, matching the
last `k` segments segment-aligned against the manifest `file_set` (`p == tail` or `p`
ends with `"/" + tail`); it keeps a recovery **only** on **exactly one** match at the
longest such `k`. Three guards against wrong-but-existing: ambiguous (>1 match) → **drop**
(never a silent pick, never a fall-back to a shorter, less specific tail); the
`MIN_TAIL_SEGMENTS=2` specificity floor (a bare basename like `__init__.py` is never
recovered); and a **manifest-keyed leading-segment guard** — the matched *tail's head*
must be a known top-level manifest entry, so a fabricated mid-tree suffix is rejected
(`src/flask/blueprints.py` kept, `flask/blueprints.py` whose head `flask` is not
top-level dropped). The worked counter-case proves the floor pays its way: a cite of
`/pallets/flask/src/__init__.py` has suffix `src/__init__.py`, which does **not** exist
in flask (the real file is `src/flask/__init__.py`), so recovery correctly **fails**.
(2) **Recovery composes with, never bypasses, 0011's validation.** A recovered path
re-enters the same repo-confine + `is_file` (+ line-range clamp for spanned) gates
before it is kept; the match-set is **manifest-relative** so match and re-validation
cannot disagree on gitignored/derived files; and `file_set` **absent/empty ⇒ no
recovery** — every out-of-repo ref falls back to the spec-0011 drop, so recovery only
ever *adds* keeps and never changes the no-file-set behavior (graceful degrade when the
index is not ready). (3) **The honesty floor is load-bearing and inherited, not
re-asserted.** A recovered **file-level** citation stays `is_file_level` (`None` lines,
no fabricated range), so it inherits spec 0011's `gate-skipped:no-line-range` floor and
**never** reads as a verified / high-confidence pass — a recovered keep reads no more
confidently than a non-recovered one. This guard matters precisely because a file-level
citation skips read-back: a wrong-but-existing file-level recovery would propagate
**un-verified**, strictly worse than the honest drop it replaces. Proven end-to-end in
`orchestrator/test_locate.py` (gate path) + `scout/test_scout_normalize.py` (no
fabricated range). (4) **The producer→sink blast radius was closed by category in one
change**, per the spec-0011 grep-the-category discipline: `normalize_spans_with_tally`
return widened **2-tuple → 4-tuple** `(spans, dropped, recovered_spanned,
recovered_filelevel)` plus a non-breaking `recovered_paths_out` out-param carrying the
recovered **file-level** paths (chosen deliberately over a 5-tuple to avoid re-churning
the just-updated 4-tuple callers — a mild, recorded out-param smell); `ScoutTally` gained
`recovered_spanned` / `recovered_filelevel` / `recovered_filelevel_paths` on the
unchanged `last_tally` side-channel; `ScoutEngine(file_set=…)` threads the set;
`build_scout_engine` loads it via `read_manifest(art_dir)`; report `SCHEMA_VERSION 0011/1
→ 0012/1` with two additive last-with-default fields
`fc_citation_recovered_{spanned,filelevel}_count` in the one `_AGGREGATE_DEFAULTS`
source (both shapes validate); and **BOTH** `eval/runner.py` **and** `eval/swebench_eval.py`
aggregate the counts (the sibling-driver enumeration a reviewer flagged — a count tracked
in the single-repo runner but not the per-case driver is the same blast-radius miss class).
**Why:** Spec 0011 made Scout robust enough to *answer* on real queries, but a Q8 model
that knows the file yet prefixes a hallucinated root still degraded to Tier-0 under the
honest 0011 drop. The fix is deliberately deterministic and model-independent: it does
not change which Scout model ships, it makes whichever model ships pay off by salvaging a
citation whose only defect is a fabricated prefix — but **only** when the salvage resolves
to a real, unique, anchored file, because a plausible-but-wrong un-gated file-level keep
would be worse than the drop. The recovery and the future model swap are decoupled on
purpose: the swap is a variance-gated default flip this spec explicitly defers.
**Consequence — the `scout-empty` tail shrinks on real data; the model flip is still a
follow-up.** Shipped TDD-complete: **678 unit pass** (+22 over the 0011 baseline of 656),
ruff clean; **integration 5 passed / 1 skipped** (the AC5 operator test, env-gated, runs
`auto`). **AC5 LIVE** (committed `run_q8rl_recovery_n12.json`, `mode=fast`, Q8
fastcontext-4b-rl, recovery ON vs the committed `baseline_q8rl_n12.json`): **scout_empty
7 → 4 (3 of 7 dead cases RESCUED)**, **dropped 10 → 0**, **recovered_spanned = 10**,
**recovered_filelevel = 0** — every recovery was **SPANNED** (the model emitted the
out-of-repo paths *with* line numbers), so `recovered_filelevel_paths` is honestly empty
and the riskiest un-gated file-level recovery category did not occur in this run; `N=12 <
n_floor` ⇒ self-flagged `indicative_only`, an honest recorded delta with no
strict-inequality gate (no production default flipped). **Deviation:** the AC5 run was
`mode=fast` not `auto` — on the dev host (16 GB) `auto` OOMs (jetsam) co-loading the 5 GB
Q8 Scout + Deep + Deno/Pyodide **and** Deep crashes via a dspy `AdapterParseError` on the
qwen model's malformed JSON (sphinx-9698); recovery is Scout-side so `fast` measures it in
full and only the auto-only gate/escalation counts are excluded from the delta (the
committed integration test still runs `auto`). Open follow-ups carried forward: the **Q8
`scout_model` default flip** (deferred; rl favored 5/12 vs 2/12 gate-fire though sft edges
accuracy 0.25 vs 0.167 — must apply the variance-gated recommend→flip discipline + a
missing-model degrade story, typed `scout-degraded` → Tier-0 floor); the **gate
false-escalation of a correct Scout answer** (requests-1766 — a gate-quality lead); the
**Deep `AdapterParseError` robustness gap** (Deep should map a malformed dspy/model
response to a typed `DeepUnavailable` degrade, not crash); two **upstream FastContext bug
reports** drafted this session; and, still open from Wave 2, **Wave-2.1 substring/fuzzy
matching**.

## 2026-06-28 — Scout citation-shape robustness (seam (a), `citation=False`) + harness degrade visibility shipped — line-less `CodeSpan`, the corrected fix locus, safe + observable degradation

**Spec:** specs/0011-citation-shape/
**Decision:** Fix the spec-0010 finding that Scout was **systematically dead on real
SWE-bench queries** (12/12 `scout-degraded:backend-error`, gate upstream-starved, bare
Tier-0 at 2/12 = 0.167) — and the second, enabling defect that the degrade was
**invisible in aggregate metrics** — in **one** spec, because the visibility gap is
*why* the Scout bug hid (degradation must be both **safe** and **observable**; shipping
the fix alone would leave the next tier failure equally invisible). The
**single-wire-format-owner** and **honest-precision** invariants held and **FastContext
is NOT patched**. Six durable choices were pinned. (1) **The RCA's first framing was a
false premise, corrected by a live spike (T0, the fail-fast first plan step).** Harpyja
**never receives FC citation *objects***: FC's `format_citations` runs **inside**
`agent.run(prompt, citation=True)` and raises `TypeError: string indices must be
integers` when the model's final message has no parseable `<final_answer>` block
(`parse_citations` returns a dict fallback whose string keys `format_citations`
iterates) → caught → `ScoutUnavailable(backend-error)` → Tier-0 degrade. So the
"normalize dict-vs-string citation objects" framing solved a problem that doesn't exist
at Harpyja's seam. The spike confirmed live (FC-4B/Ollama): `citation=True` raises the
exact `TypeError`; `citation=False` returns the raw final message and **structurally
cannot reach** `format_citations`. **(2) Fix = seam (a):** Scout invokes FC
**`citation=False`** (Path A `agent.run`; Path B drops the CLI `--citation` flag),
bypassing the crashing formatter entirely — no exception on the hot path, **no
catch-as-control-flow** — and `scout/client.py::parse_final_answer` parses the raw
`<final_answer>` **text per line, anchored** to the spike-pinned FC grammar
`<no-space-path>[:start[-end]] [(explanation)]`: `path:start` → spanned `CodeSpan`;
bare path / malformed-or-non-numeric line → **file-level** `CodeSpan` (`None` lines, no
fabricated range). A `_looks_like_path` guard (dir separator or dotted extension;
markup rejected) and per-line anchoring (never a naked optional `:\d+` over free text)
keep an incidental prose filename from becoming a spurious citation (AC22). This is the
in-`scout/` text seam — the corrected fix locus; seam (c) (catch-the-crash fallback)
was the pre-stated contingency and **was not needed**. **(3) Honest-precision
representation: `CodeSpan.start_line/end_line` widened to `int | None`** (`None ⇒
file-level`, no line range) with a new **`CodeSpan.is_file_level`** property as the
**single predicate** every downstream consumer branches on, so a coarse path-only
citation never reads as a line-verified one. **Both-or-neither:** a half-`None` span is
not a sanctioned shape and is rejected at the parse/normalize boundary (AC23). **(4)
The blast radius was closed by category, not piecemeal** — the round-2/3 review lesson
(a `None`-line span crashes each int-line consumer in turn; the round-3 `format.py`
miss was the same class as the round-2 representation miss) was generalized to a
discipline: `grep -rn 'start_line\|end_line'` enumerates **all** consumers at once and
each gets its **own** RED→GREEN, ordered producer→…→metrics so a `None` span is made
safe before the next stage sees it. `normalize_spans` (file-level branch:
repo-confine + `is_file` + dedup, skip the line clamp; `normalize_spans_with_tally`
returns a dropped count + per-drop log; the Deep/Tier-2 lined path stays byte-identical);
`format.py` (file-level spans survive un-merged, sort after lined on a None-safe rank
key); `gate.py` (new `GateOutcome.skipped_reason="no-line-range"`, detected **before**
read-back — not scored, not a verified pass); `locate.py` (stable
`gate-skipped:no-line-range`, distinct from `gate-low-confidence`/`gate-scoring-failed`,
escalate-if-a-tier-remains-else-carry-tagged in `auto`, informational in `fast`);
`metrics.py` (`span_hit_kind` → `"line"`/`"file"`/`None`, the path-only branch taken
**before** the line arithmetic in **both** the primary and the secondary/window
oracle — `span_hit_secondary` was a blast-radius miss the spec hadn't enumerated,
caught by the same grep discipline). **(5) Deliverable 2 — first-class degrade
visibility on a bumped schema.** `SCHEMA_VERSION` `0010/1` → `0011/1` with 8 additive
fields last-with-defaults in the centralized `_*_DEFAULTS`: aggregate
`scout_degrade_count`, `scout_degrade_rate` (**null-with-count on a zero denominator**,
never a false `0.0`), `degraded_dominated` (rate > threshold), composable
`reliability_notes`, and `fc_citation_{spanned,filelevel,dropped}_count` (the text-ref
shape distribution — the bare-path frequency is the root-cause signal, no drop silent);
run-metadata `degraded_dominated_threshold`. A new **eval-only**
`EvalConfig.degraded_dominated_threshold=0.5` (field-disjoint from the production frozen
`Settings`) encodes the same judgment as the N-floor: a **majority**-degraded run
characterizes the degrade floor, not the SUT, so its escalation/accuracy/OQ2 outputs
are marked unreliable. **(6) The shape tally rides a Scout-result side-channel, not the
orchestrator seam.** `ScoutEngine.last_tally` (`ScoutTally{spanned, filelevel, dropped}`)
is metadata read **only** by `eval/runner.py` (reset+read per case, then aggregated);
the orchestrator's `list[CodeSpan]` is unchanged so callers still never branch on which
engine ran. `compose_reliability_notes` is shared by `runner.py` + `swebench_eval.py`
so the two aggregation sites cannot drift (R2); `is_file_level` is the shared shape
predicate (R1).
**Why:** Spec 0010's instrument did its job and surfaced a **real Scout/FastContext
robustness defect** on real data — but a floored Scout is indistinguishable from
"cheapest tier works" at the metrics layer, so the defect hid behind the very spec-0007
degrade floor that was working. The low bare-Tier-0 accuracy (16.7%) proves the
Scout→gate→Deep NL ladder is load-bearing, not redundant; until Scout is robust the
ladder is non-functional on exactly the real-world queries Harpyja targets and OQ2 is
uncalibratable on real data. The corrected fix locus matters: the original "normalize
FC's citation objects" plan would have written code against shapes Harpyja never
receives; tracing `scout/client.py` against the RCA (and then the live spike) relocated
the fix to where Harpyja genuinely sits — the answer **text** — where the
honest-precision invariant fits *better* (a `path:start` match → spanned; a bare-`path`
match → file-level).
**Consequence — Scout is robust on real queries; OQ2 is now unblocked but not yet done.**
Shipped TDD-complete: **656 unit pass** (+45 over the 0010 baseline), ruff clean;
**7 live integration pass** (5 Scout + 2 SWE-bench driver, real FastContext-4B + Deep +
Ollama). **AC20 proven live:** the exact 12/12-broken flask case now returns with
**zero backend-error** (`test_scout_live_no_backend_error_citation_false`, 22.5s). One
new stable flag id joins the taxonomy (`gate-skipped:no-line-range`). Deviations: the
T0 spike was captured on a small temp repo (the 4B model returns empty on the full
flask tree; the seam/grammar question is repo-independent) and the AC21 N=12 re-run was
exercised on the legacy fixture (the full N=12 flask sweep is the compute-bound operator
opt-in). Open follow-ups carried forward: the **production OQ2 calibration**
(`verify_threshold`/`verify_top_n`) this UNBLOCKS but does not do — now meaningfully
measurable since Scout fires on real data; **`degraded_dominated_threshold` revisit**
to a data-driven value once a real degrade-rate distribution exists (sequenced after
the production OQ2); and, still open from Wave 2, **Wave-2.1 substring/fuzzy matching**.

## 2026-06-28 — SWE-bench Verified eval dataset + per-case-repo driver shipped — real-data instrument, measurement-only, recommend-only, live-validated

**Spec:** specs/0010-swebench-eval-dataset/
**Decision:** Give the 0009-6a eval **instrument** a real dataset to measure: a
SWE-bench Verified adapter (`harpyja/eval/swebench_eval.py`) plus the **per-case-repo
driver** the single-repo harness structurally lacked, so Harpyja produces its first
**non-indicative** locate-accuracy numbers and a sweep-backed OQ2 picture — while
preserving the **measurement-only / recommend-only INVARIANT inherited from 0009-6a
(B1)**: no tier/gate/matrix/classifier CODE change, no `Settings` default flipped, the
only `Settings` touch a `dataclasses.replace` on `verify_threshold`/`verify_top_n` in
the sweep. Nine durable choices were pinned. (1) **Standalone-localization protocol
(FastContext paper), not the SWE-bench harness.** `parse_patch` derives the gold
patch's pre-image (`--- a/…`) hunk spans as ground truth and scores predicted citations
against them at `base_commit` — **no** Docker, image build, patch apply, or test exec
(Harpyja is a locator, not a patcher; also sidesteps x86-under-emulation pain). The
~3-context-line inflation biases span-hit **upward** and is recorded as a durable
`span_inflation_tolerance`, not framed neutral (R5). (2) **D-class — classification by
patch shape.** `classify_by_patch_shape`: a single file with total pre-image span ≤
`POINT_SPAN_MAX_LINES=25` ⇒ `point`, else `broad`. On the real N=50 sample this gave
**38 point / 12 broad** — a usable point subset, so the all-broad
uncalibratable-risk the review caught is avoided. (3) **D-route — a RECORDED EVALUATION
INTERVENTION (resolves review B1).** Production routing keys on `classify_query(query)`
(issue prose), uncorrelated with patch shape, so a patch-shape-`point` case would
frequently route straight to Deep and the gate would never fire — the whole OQ2 signal
computed over cases production never gated. The driver therefore injects a classifier
returning `case.classification` through the existing **`LocateStack.classifier` seam**,
swapping only the *input* to the unchanged routing/gate/matrix code so the gate
genuinely fires; the production `classify_query` label is captured **before** the
override, both labels are recorded per case + an aggregate `classifier_agreement_rate`,
and a SUT-observed `production_gate_ran` (from `result.tiers_run`/`notes`) is kept
**distinct** from the harness Scout-probe `gate_triggered`. This is **not** pure
observation — surfaced loudly, never hidden — and the single-source-of-truth-routing
flag dissolves because `classify_query`/`plan_ladder` stays the sole routing path.
(4) **OQ2 agreement-rate guard (round-2).** Below `AGREEMENT_FLOOR=0.5` the sweep
recommendation is flagged `oq2_low_confidence` / `oq2_basis=deltas-only` — a relative
ranking, **never** a calibration to flip a default on (keeps a low-agreement run, where
the gate fired on a synthetic routing distribution production never produces, from
reading as a confident calibration). (5) **D-newfile + B2.** All-new-file instances
(`--- /dev/null`, no pre-image) are flagged `new_file_only` and **EXCLUDED** from
scoring with a surfaced count (no silent zero); `base_commit` lives only in the raw
JSONL (`provision` reads it via `_read_jsonl`) and `load_dataset` ignores it — the
round-1 "preserved on `EvalCase`" false-capability is gone. (6) **Per-case-repo
driver.** The 0009-6a harness was single-repo (`run_dataset(..., repo_path, stack)`);
SWE-bench is one worktree per case, so `run_swebench` builds its **own** `LocateStack`
per case (D-route classifier injected) and **pools** outcomes into the UNCHANGED
`metrics`/`recommend` layers + the additively-extended report, artifacts written
outside EVERY case repo. (7) **Additive report schema.** `SCHEMA_VERSION` bumped
`0009-6a/1` → `0010/1`; six run / three case / one aggregate field appended
last-with-defaults, the field set + defaults **centralized in `report.py` `_*_DEFAULTS`**
(the single anti-drift source, fulfilling the T26 refactor by construction) so BOTH the
single-run and multi-repo shapes validate; durable metadata carries protocol id,
new-file-excluded count, malformed-skipped count, agreement rate, span-inflation
tolerance, contamination caveat, and dataset provenance (HF id/split/revision,
raw-fixture sha256, sample case-ids). (8) **`mode=fast` seam (R3).** `run_case` now
threads `mode`; `fast` is **Scout-terminal** (Wave-5 gate informational, never
escalates) — the corrected SUT description, not "no gate". (9) **Network posture /
air-gap scoping (R8).** `convert` (HF) and `provision` (`git clone`) are dev-time
tools explicitly **OUT** of the runtime air-gap guarantee; `run`/`sweep` are offline
(live integration asserts zero non-loopback egress).
**Why:** With N=5 ≪ `N_FLOOR=30` the 0009-6a harness could only emit `indicative_only`
runs — locate accuracy was unproven on a real tree and OQ2 (`0.6`/`3`, provisional
since Wave 5) had nothing real to measure. SWE-bench Verified supplies 500
human-validated issues whose pre-image hunk locations are patch-derivable ground
truth — exactly the repo state at `base_commit` Harpyja scans — so a stratified sample
clears the floor. Framing is deliberately modest (R4): SWE-bench is public, so the
**absolute** numbers are not a generalization claim; the load-bearing outputs are the
contamination-robust **relative** deltas (threshold/top_n against each other,
fast-vs-auto). D-route exists because patch-shape and prose-classification are
uncorrelated, so without the injected input the gate metrics would be partly fiction
and partly flat — the precise "uncalibratable" failure D-class was written to prevent.
**Consequence — instrument built + live-validated on REAL data; the full OQ2
calibration is an operator opt-in.** Reconciliations surfaced in execution: the
uploaded `_to_eval_case` emitted the wrong schema (`id`/expected-dict) → fixed to
`case_id`/`expected_spans`-list; the uploaded `Makefile.swebench` pointed at a
nonexistent `harpyja.eval.runner --fixture` CLI → reconciled to the real `swebench_eval
run|sweep` subcommands; and default `Settings.lm_model="local"` (a llama.cpp
placeholder) forced new `--lm-model`/`--lm-api-base`/`--deep-max-subqueries` flags
(applied via `replace`) + a Makefile `LM_MODEL` so `make swebench-run` drives Ollama.
Shipped TDD-complete: **611 unit pass** (+~54 new eval tests), ruff clean; **4
integration passed LIVE in 185s** — live multi-repo driver e2e, zero non-loopback
egress, live OQ2 sweep + agreement guard, and a **real HuggingFace `convert` smoke**.
Real `convert --sample 50 --per-repo 5` → 50 real cases, 0 malformed, 0 new-file, 12
repos, 38 point / 12 broad, committed as the portable raw fixture (clears `N_FLOOR=30`).
Real `provision + run` (flask + requests, actually cloned + worktreed, 2/2 resolved) gave
`span_hit_primary=0.5` (flask HIT, requests MISS), escalation 0.0 — and the instrument
surfaced a **real Scout/FastContext defect**, NOT a gate finding: both cases carry
`scout-degraded:backend-error` (FastContext's own `format_citations` crashes on real-query
output → `ScoutUnavailable` → Tier-0 degrade, the spec-0007 AC10 case), so Tier-1/gate were
**upstream-starved** and 0.5 is the Tier-0 degrade-floor, not an escalation-skip signal (an
earlier draft mis-read this as "gate did not fire" — corrected per no-false-capability).
**Implication:** Scout is non-functional on real SWE-bench until FastContext `format_citations`
is made robust to string-shaped citations, so OQ2 cannot be calibrated from this dataset
regardless of N — a new lead follow-up. The FULL live OQ2 sweep (all 12 cloned repos × K) is
compute-bound and the documented opt-in (`make swebench-full` → `swebench-sweep`); **no
`Settings` default flipped (B1)**
— the flip remains a separate one-line follow-up spec citing this evidence. Open
follow-ups carried forward: the **OQ2 default flip** (now backed by a real,
N≥30-clearing instrument, guarded by the agreement floor); a **held-out
decontamination mini-set** (R4, deferred); and, still open from Wave 2, **Wave-2.1
substring/fuzzy matching**.

## 2026-06-28 — Wave 6a Eval harness + OQ2 calibration shipped — measurement-only, recommend-only, live-validated

**Spec:** specs/0009-6a/
**Decision:** Land a NEW **measurement-only** package `harpyja/eval/` that observes
the real `mode=auto` `locate()` path and reports locate accuracy, escalation rate,
and gate catch / false-escalation metrics, plus an OQ2 `(verify_threshold,
verify_top_n)` recommendation — and flips **no** `Settings` default (B1; the flip is
a future one-line follow-up spec, so "measurement only, no behavior change" stays
literally true). The harness is the first non-tier layer: it does not answer queries,
it *measures* the system that does. Seven durable choices were pinned. (1) **The
harness observes the SUT through its real public seam and never mutates its config.**
The runner drives the production `harpyja.orchestrator.locate.locate(...)` via an
injected `LocateStack` (fakes for unit, `build_live_stack` real factories for
integration); the only `Settings` interaction is the sweep building grid points via
`dataclasses.replace` on the real `verify_threshold` / `verify_top_n` fields, never
mutation (`test_sweep_does_not_mutate_settings`). (2) **Eval-only knobs live off the
production frozen `Settings` (K-placement deviation).** The spec body's "additive
eval-only `Settings` field carrying K" was reconciled at plan time to a dedicated
frozen `EvalConfig` (k_runs / proximity_window_lines / n_floor / catch_rate_bar),
**field-name-disjoint** from `Settings` (`test_eval_config_is_independent_of_settings`)
— K is a runner loop count the SUT never reads, so putting it in the production config
is a coupling smell with no compensating uniformity benefit. (3) **ONE overlap oracle
defines correctness for every derived metric (D3/D5).** `_any_primary_overlap` (ANY
cited span overlaps ANY expected span in the same file; touching ranges count, D6) is
reused by span-hit accuracy, gate catch-rate, AND gate false-escalation — there is no
second notion of correctness that could drift, asserted by
`test_gate_metrics_use_same_oracle_as_span_hit`. The Tier-1 signal is captured
**independently of escalation**: because the gate replaces citations when it
escalates, `CaseOutcome` carries both `tier1_citations` (gate oracle, an honest extra
Scout call on point cases) and `final_citations` (accuracy). (4) **Gate metrics are
scoped to the point-query subset only (D1).** `gate_catch_rate` /
`gate_false_escalation` range over `classification == "point"` cases; broad queries
bypass the gate (straight to Deep per the 0008 matrix) and are EXCLUDED from both gate
denominators, while `escalation_rate` is a separate aggregate over ALL auto cases —
the two are never conflated. (5) **Null-with-count sentinel on a zero denominator
(D2).** An undefined gate metric serializes as explicit `null` paired with its (zero)
count field, so AC7 "all metrics populated" is honored by a present null-with-count,
never an omitted key or a false `0.0`; the seed must carry ≥1 wrong- and ≥1
correct-Tier-1 point case to keep live denominators non-zero. (6) **Recommendation is
variance-gated and recommend-only (D3/D4, B1).** A sweep point displaces the incumbent
`(0.6, 3)` only when its advantage strictly exceeds the incumbent's run-to-run spread
(`mean(A) - mean(B) > pstdev(B)` over K runs); the D4 lexicographic scorer keeps points
clearing the catch-rate bar, then minimizes false-escalation, tie-breaks lower top_n
then lower threshold. Within noise, the incumbent is recorded **validated**, not
guessed — a `0.55`-over-`0.6` flip on noise is the precise failure this prevents. (7)
**Harness artifacts write outside the indexed repo + a pinned D7 schema.**
`atomic_write_json` refuses (`ValueError`) to write inside or under `repo_path`
(read-only guardrail mirroring the FastContext `trajectory_file`-outside-repo
precedent) via a same-dir temp + `os.replace`; `validate_report` is loud
(`ReportSchemaError`) over the enumerated D7 field set, and small-N runs self-flag
`indicative_only`.
**Why:** All three tiers and `mode=auto` were live and unit-green, but the design's
core claims — escalation stays low, the gate catches wrong Tier-1 citations, the
`scout_model` judge + `top_n=3` hold up — were **unfalsified**: no instrument measured
locate accuracy on a real tree, and OQ2 (`verify_threshold=0.6` / `verify_top_n=3`,
provisional since Wave 5) had no evidence behind it. This wave is that instrument. The
single-oracle and point-scoped denominators exist so two implementers cannot produce
silently incomparable harnesses; the variance gate exists so the recommendation cannot
flap on model non-determinism.
**Consequence — OQ2 partially resolved (the honest outcome).** The harness runs live
and produces a recommendation, BUT the shipped seed is a **5-case starter** over one
small vendored `legacy/` repo (N=5 ≪ the pinned `N_FLOOR=30`), so every run over it is
correctly flagged `indicative_only=true` and the incumbent `(0.6, 3)` is **NOT
displaced**. OQ2 therefore resolves as **"instrument built + live-validated;
calibration deferred to a larger seed"** — NOT a fabricated tuning result. The
provisional `0.6/3` and the `0.90` catch-rate bar remain provisional; a real
calibration (one that could justify a default flip) needs the larger curated D1
dataset (a vendored OSS legacy repo with ≥30 hand-labeled cases), which the plan
explicitly delegates, and the flip itself is a separate one-line follow-up spec.
Shipped TDD-complete: **557 unit tests pass** (+58 new), ruff clean; **5 integration
tests (AC7 ×3 + AC8 ×2) passed LIVE in 634s** — real FastContext Scout + `scout_model`
gate judge + Deep `qwen2.5-coder:3b` over Deno + rg (genuinely verified, not skipped).
`per_tier_model_calls` is honest-`None` (no counter wired through `LocateStack` — a
present null, not a false zero). Open follow-ups carried forward: **the larger D1
dataset → a real OQ2 calibration → a potential default flip in a follow-up spec**; and,
still open from Wave 2, **Wave-2.1 substring/fuzzy matching**.

## 2026-06-27 — Wave 5 Verification Gate + Tier-0→1→2 auto-escalation shipped — `mode=auto` now climbs

**Spec:** specs/0008-wave-5-verification-gate/
**Decision:** Make `mode=auto` trustworthy by wiring the four seams Waves 3/4
deferred — query classifier, planning matrix, Verification Gate, and the escalation
ladder — so `auto` runs the cheapest tier that can answer and climbs only on a real
signal. Tier internals (Tier-0 seed, Scout, Deep) are **unchanged**; this wave is
orchestration only. Seven durable choices were pinned. (1) **The gate is the
`scout_model` reuse judge, routed through the one outbound caller (OQ1 resolved).**
The gate reads the cited lines back from disk and scores their relevance to the query
by reusing the already-loaded Scout fine-tune as a generative judge — no new model to
serve on the single-GPU profile. Because the gate is **in-house orchestrator code**,
its judge call goes through `ModelGateway.complete()` (the only outbound caller, which
already air-gaps at resolution time), **not** a parallel judge client — this is
deliberately *not* the third-party-owns-its-client pattern (Deep/FastContext); it
**additionally** calls `gateway.assert_local()` **before** the judge as a
belt-and-suspenders pre-check (still the one helper, no parallel air-gap type), proven
by a live network-deny integration test. (2) **A generative judge is affordable only
because the scan is bounded top-N (OQ3 resolved) — one causal decision, not two.** The
gate scores at most `verify_top_n` ranked citations (`max` over their scores: one
strongly-relevant span carries the verdict); the dropped count is logged so a bounded
scan is never indistinguishable from a full one (no-silent-truncation). An unbounded
generative judge would put a result-set-sized model cost on the hot path. (3) **The
Wave-0 "auto byte-identical / zero Gateway calls" lock was retired in lockstep** with
the explicit new contract: `_MODE_NO_EFFECT` and its guard tests in **both**
`orchestrator/test_locate.py` and `server/test_app.py` were deleted in the **same**
change that wired the classifier→matrix→ladder, so the suite never holds a state where
`auto` neither emits the old lock nor honors the new AC1 contract — the unspecified
window is closed by construction (the same atomic-invariant-swap discipline as Wave 4's
`deep` guard inversion). (4) **The planning matrix is the genuine single source of
truth — driven by code, not duplicated by it.** `plan_ladder(mode, classification,
index_ready)` over a 6-row `(mode, classification)` seeded table (×`index_ready`
dropping the leading `0` → all 12 rows) is read by both `_locate_auto` and the tests;
a refactor (T17) caught `_locate_auto` re-deriving routing and rewired it to consult
`plan_ladder`, so the escalation branches are *derived from* the table, never a second
authority. (5) **The empty-case three-way split** mirrors the codebase's entrenched
typed-failure-vs-honest-result convention: a Scout **typed-unavailable** degrades to
the Tier-0 floor (`scout-degraded:<cause>`, `confidence="degraded"` UNCHANGED, **no**
climb); an **honest-empty** Scout (clean run, zero citations) skips the gate — nothing
to score — and returns the Tier-0 seed tagged `gate-skipped:scout-empty` (+`no-matches`
on an empty seed), **no** climb; only a **malformed** result escalates. Malformed is
realized as "the gate cannot read back / score the returned citations →
`GateOutcome.failed` → escalate" (Scout's contract is spans-or-`ScoutUnavailable`, so a
malformed result manifests *at the gate*, e.g. a citation whose file is absent fails
read-back — not as a separate Scout signal). (6) **Confidence is keyed on terminal-tier
+ flags, never path tokens alone**, so honest-empty — which shares the `[0,1]`/`[1]`
tokens of a verified gated-pass — gets the distinguishing `gate-skipped:scout-empty`
marker and a distinct `medium`/`low` row, never reading as `high` (no-false-capability:
"nothing found" must never look high-confidence). The typed-unavailable `"degraded"`
literal is preserved; the map's `low` rows are gate-states only, so AC8 and AC9 never
collide. A best-effort gate **never blocks and never silently passes**: a scoring
failure routes exactly like a gate-fail (escalates in `auto` where a tier remains, with
`gate-scoring-failed` retained and `confidence=low`; best-effort un-gated Tier-1 in
`fast`). (7) **`verify_method` honors no-false-capability at the config surface.** Three
additive `Settings` fields are appended last (`verify_method="scout_model"`,
`verify_threshold=0.6`, `verify_top_n=3`); `__post_init__` rejects any unsupported
`verify_method` (`embedding`/`model_judge`/arbitrary) with a typed
`UnsupportedVerifyMethod` naming the field + accepted set — on **every** construction
path (defaults, toml, env, per-request `replace`), never a silent fall-through to
`scout_model`. The seam is pluggable in *code*, but the config accepts only what
actually functions.
**Why:** All three tiers were live and verified end-to-end, but `auto` had nowhere to
climb — it stayed pinned to Tier 0. The honest cost lever ("cheapest tier that works")
only exists once a gate can decide whether the Scout answer is good enough to stop, and
the gate is the precise mechanism the Wave-3/4 entries kept deferring (Deep's "weak
output is NOT a degrade — that is the ungated escalation the Wave-5 gate governs" was a
direct forward reference). Reusing `scout_model` makes the sharper judge free on the
single-GPU profile; bounding it top-N is what keeps that generative call affordable on
the hot path — the two resolutions are one coupled decision, not two.
**Consequence:** `mode=auto` now realizes `tiers_run` as a prefix of the planned ladder
(gated-pass `[0,1]` / `[1]`; escalated `[0,1,2]` / `[1,2]`; broad straight-to-Deep
`[0,2]` / `[2]`); `fast` runs the gate **informationally** and never climbs (a
would-fail gate tags `gate-low-confidence`); `deep` is unchanged. Shipped TDD-complete:
513 tests pass with **all** integration ACs run live (FastContext Scout + scout_model
gate judge + Deep `qwen2.5-coder:3b` over Deno — point resolved cheap, broad climbed to
Tier-2), ruff clean. Three new stable flag ids join the taxonomy
(`gate-low-confidence` / `gate-scoring-failed` / `gate-skipped:scout-empty`). Open
follow-ups carried forward: **OQ2** — the provisional `verify_threshold=0.6` /
`verify_top_n=3` defaults still need tuning against the eval repo (the ACs assert
thresholding *behavior*, not the numbers); and, still open from Wave 2, **Wave-2.1
substring/fuzzy matching**.

## 2026-06-27 — Scout Tier-1 real default client shipped — FastContext agent, env-under-threading-lock, off-loop bridge

**Spec:** specs/0007-fastcontext/
**Decision:** Supply the **real default client** for the already-shipped
`FastContextBackend` seam (Wave 3 left it injected-only), so Scout (Tier 1) drives the
real Microsoft FastContext agent (`make_fastcontext_agent` — its own Read/Glob/Grep
loop, **not** `dspy.RLM`; the load-bearing invariant keeping Tier 1 structurally
distinct from Tier 2) end-to-end and the Wave-3 live AC flips skip → genuine pass. The
`ScoutBackend`/`ScoutEngine`/`Locator`/formatter seams stayed **unchanged**; all new
code lives in `harpyja/scout/` plus four additive `Settings` fields and two new
`errors.py` causes. Six durable choices were pinned. (1) **One client, two paths.**
Path A (primary, in-process): lazy-import the factory, build a fresh agent
(`work_dir=<repo>`, `trajectory_file=<temp OUTSIDE repo>`),
`await agent.run(..., citation=True)`. Path B (fallback): injected CLI runner with
`FC_*` scoped to the child via `env=` (no parent-env mutation). (2) **Off-loop bridge +
`threading.Lock`, verified against FastContext source @ SHA `1522d6d6…`.** The factory
is **env-only** (no `model`/`base_url` params; reads `FC_*` from `os.environ`;
`FC_REASONING_EFFORT` is read **lazily per model call** at `llm.py:77`), so AC3's
absolute ban on `os.environ` mutation relaxed to a conditional one: `FC_*` are injected
via process env, but **only while holding a module-level `threading.Lock`
(`_SCOUT_ENV_LOCK`)** — *not* an `asyncio.Lock`, because each call bridges
`agent.run` onto its **own loop-free worker thread** (`_run_coro_on_worker_thread`, so
`asyncio.run` is legal even when the MCP handler is already on a loop), and only a
thread lock serializes cross-thread `os.environ` writes. The lock is held across the
**entire run** (the lazy reasoning-effort read), set-then-restore with per-key
unset-vs-empty preservation. This **serializes Scout** — accepted for the single-GPU
profile (concurrent Scout calls already contend for the one 4B model); Scout-only,
never leaks to Deep. (3) **Air-gap before construct/spawn, TOCTOU closed.** A single
`gateway.assert_local` on the resolved `FC_BASE_URL` fires before the agent is built
(Path A) and before the subprocess is spawned (Path B); on Path A the lock spans
assert → env-set → construct → run. FastContext owns its own model client (the
`rlm.py` precedent, not the `scout/tools.py` whitelist — the whitelist is **vestigial**
for Path A, recorded as an honest limit), proven by a network-deny integration test.
(4) **Read-only assumption-verified-by-test.** `trajectory_file` resolves outside the
repo; a no-repo-writes integration test (content-hash manifest excluding `.harpyja/`)
proves the scanned repo is byte-unchanged; residual in-process write risk recorded,
symmetric to the network-deny. (5) **Four-way degrade taxonomy + deterministic state
machine.** Added `fastcontext-missing` / `cli-missing` to the existing
`connection-refused` / `no-endpoint-configured` / `backend-error`; the Path-A→Path-B
machine makes `fastcontext-missing` terminal **only** when the CLI runner is unwired,
so AC10's test is unambiguous. (6) **AC10 broadened live (graceful-degradation
guardrail).** A live run surfaced that FastContext's **own** `get_final_answer` /
`format_citations` can raise (e.g. `TypeError`) on malformed model output — confinement
worked, but the third-party post-processing crashed; the client now maps **any**
unexpected backend exception → `ScoutUnavailable(backend-error)` so Scout degrades to
Tier 0 rather than letting a raw exception escape. Floors (`RipgrepMissingError` /
`AirGapError`) and the Path-B `ImportError` signal still propagate; honest-empty (a
clean run, no parseable citation) returns `[]`, never raises.
**Why:** Tier 1 was structurally present since Wave 3 but never ran a model
end-to-end — the live AC only ever skipped. FastContext is real and installable, so
this wave cashes in the seam exactly as Wave 4 did for Deep, turning the suite's last
skip into a genuine pass. The lock rationale is grounded in the actual factory
signature at a pinned SHA, not assumed; the env-under-lock design stops the precise
cross-request race AC3 existed to prevent without overstating the guarantee.
**Consequence:** Scout is **not cached** (model-backed/non-deterministic, no
engine-identity slot — like Deep). Verified live (~42s, suite 442 passed / 0 skipped,
ruff clean); FastContext's confinement blocked the model reading `/harpyja` outside
`work_dir`, and the live ACs accept either Tier-1 success (`[0,1]`) or an honest
`scout-degraded:backend-error` (`[0]`) — both prove the real stack ran. FastContext
ships as a **portable `git`-rev pin** at the SHA — the plan's provisional local-path
editable install (flagged non-portable for CI) was tested and corrected: the
`third_party/mini-swe-agent` submodule is **vestigial** (unreferenced by the package),
so the submodule-skipping `git+https` install resolves and imports cleanly; the
non-portability deviation no longer applies. The **FastContext default client is now
DONE** — no longer an open question. Open follow-ups carried forward: the
**Verification Gate +
Tier-0→1→2 auto-escalation ladder** (Wave 5 — `mode=auto` still does not climb) and,
still open from Wave 2, **Wave-2.1 substring/fuzzy matching**.

## 2026-06-27 — Wave 4 Deep (Tier 2) shipped — dspy.RLM, sandbox, layered explorer-loop bounds

**Spec:** specs/0006-wave-4-deep-rlm/
**Decision:** Land Harpyja's strongest, most expensive tier — Tier 2 Deep, a
`dspy.RLM` explorer running inside a Deno/Pyodide sandbox whose **entire world** is
four bounded, read-only host tools — reached only via `mode=deep`, and make the
Wave-3 provisional `deep` real by shipping routing **and** implementation together.
`mode=auto` stays byte-identical and model-free; `mode=fast` stays Scout. Eight
durable choices were pinned. (1) **Layered explorer-loop enforcement — no single
ignorable counter is load-bearing.** An untrusted code-writing loop is bounded at
different seams: *externally enforced* (the backend cannot evade) `deep_max_tool_calls`
(host-tool wrappers stop dispatching), `deep_token_ceiling` (the Gateway refuses
further completions), and `deep_wall_clock_ms` (a host deadline) are the load-bearing
trio; `deep_max_depth` / `deep_max_subqueries` are *host-mediated* at the spawn seam
with **recorded residual risk** (if the runtime exposes no spawn/recurse hook they
become cooperative) and are **transitively contained** by the external trio — every
sub-query spends tool-calls, tokens, and wall-clock, so a recursion storm terminates
even if the mediation seam is cooperative. A bound the third party can ignore is not
a bound. (2) **Wall-clock requires an out-of-band, host-terminable subprocess.** A
same-thread/same-event-loop deadline can never fire while a synchronous WASM busy
loop blocks it; `DeepRunner` therefore splits an in-process counter facet
(unit-testable, no process) from an out-of-band `run_isolated` worker the host
**hard-kills** — enforcement by termination, never cooperative cancellation; proven
against a genuine `while True: pass` (AC10) and a real RLM runaway (AC10a). (3)
**Typed-failure-only degradation boundary.** Deep degrades to Scout best-effort
**only** on a typed `DeepUnavailable` (`sandbox-absent` / `rlm-down` / `backend-error`);
weak or zero citations are an honest Tier-2 result, **not** a degrade — treating weak
output as a reason to drop a tier would be the ungated escalation the deferred Wave-5
Verification Gate is meant to govern, and must not be smuggled in here. (4)
**`deep-truncated:<bound>` is a stable, caller-visible non-degrade note** (one of
`depth` / `subqueries` / `tool-calls` / `tokens` / `wall-clock`) — a budget
truncation is never silently indistinguishable from a complete run and never a
tier-degrade. (5) **RlmBackend air-gap via `assert_local` on the endpoint.** The real
`dspy.RLM` owns its own `dspy.LM` (litellm) and accepts no model_fn, so it cannot be
routed through `gateway.complete` as the spec assumed; instead `RlmBackend` calls
`gateway.assert_local(settings.lm_api_base)` **before** constructing the LM (single
air-gap helper, no parallel check) and the air-gap is **proven** by the network-deny
integration test (AC12) — assumption-verified-by-test, not asserted. (6) **`DeepEngine`
dual surface.** It self-seeds Tier-0 before the backend and exposes both `.search` for
`Locator` conformance and `run() -> (citations, truncated_bound)` because the
truncation bound is metadata the bare `list[CodeSpan]` contract cannot carry. (7)
**Sandbox isolation verified by test, residual risk recorded.** In the real sandbox an
ambient `open()` (outside *and* inside the repo — the latter would bypass `read_span`'s
clamps) and a non-loopback socket connect all fail (AC8b); the four-tool surface is
also pinned by a deno-less positive-equality `[unit]` whitelist (AC8a). The
runtime-change residual risk is recorded, exactly as the Wave-3 FastContext in-process
egress risk was. (8) **Lockstep guard inversion shipped atomically:** the two Wave-3
guards asserting `deep` emits *no* Tier-2 marker were deleted and replaced by the
inverse invariant in the same change — the suite never holds both sides.
**Why:** The hardest retrieval — trace a request across packages, find every consult
of a budget — needs *iteration* (search, read, partition, spawn sub-queries, pull only
what matters into token space), which a single Scout pass cannot do without blowing the
context window. Because the RLM *writes and runs code* against the host tools, it is an
untrusted **caller** and untrusted **code**: the confinement Wave 3 hardened at the
FastContext boundary now applies one layer deeper, at every host tool, and the bounds
had to be enforced where the backend cannot evade them.
**Consequence:** Deep is **not cached** (model-backed/non-deterministic, no
engine-identity slot — like Scout). Verified live against dspy 3.2.1 + Deno 2.9.0 +
Ollama (loopback) + ripgrep 15.1.0 (cold ~50s, warm ~15s); a weak 4B model means the
live ACs assert pipeline *shape* (valid possibly-empty `CodeSpan`s), not citation
quality. Open follow-ups carried forward: the **Verification Gate + Tier-0→1→2
auto-escalation ladder** (Wave 5 — `mode=auto` still does not climb); the **FastContext
package** for Scout is still absent (Wave-3 live AC1 still skips); and, still open from
Wave 2, **Wave-2.1 substring/fuzzy matching**.

## 2026-06-27 — Wave 3 Scout (Tier 1) + Model Gateway request path shipped

**Spec:** specs/0005-wave-3-scout/
**Decision:** Land Harpyja's first model-backed tier (Scout, Tier 1) and the Model
Gateway **request path** — the single outbound seam every later tier builds on — as an
explicit-opt-in capability that leaves `mode=auto` byte-identical to Wave 2 with **zero**
Gateway calls. Six durable choices were pinned. (1) **A four-state degradation floor.**
A Scout call resolves to exactly one caller-visible state that never collapses into
another: model-down → Tier-0 citations (`confidence="degraded"`, `tiers_run=[0]`,
`scout-degraded:<cause>` note); Tier-0-has-results vs Tier-0-honestly-empty are kept
distinct by a `+no-matches` suffix; and a Tier-0 hard precondition absent
(`RipgrepMissingError`) **propagates loudly**, never swallowed into a degraded-empty.
(2) **Seed-before-backend ordering makes the loud case win by construction.** `ScoutEngine`
runs its own Tier-0 self-seed *before* the backend (under `mode=fast` the caller skipped
`auto`'s pass), with no try/except around `seed_fn`, so `rg`-missing-and-model-down
surfaces state 4 deterministically — the dangerous composition is impossible by ordering,
not luck. (3) **Resolution-time air-gap reused from Wave 0, with a new guarded request
path.** Rather than the spec's named `NonLoopbackEndpointError`, the new
`ModelGateway.complete()` reuses the single air-gap helper (`assert_local` + `AirGapError`)
and asserts loopback on **resolved** addresses **before** an injected transport is touched
— a non-loopback endpoint raises a loud floor error, deliberately *not* one of the four
degrade states. (4) **`ScoutBackend` Protocol + `FastContextBackend` (injected client)
keep the FastContext dependency swappable** — no top-level hard import, so the sole open
question (FastContext package/version) can never break the suite, and Scout sits behind
the shared `Locator`/`CodeSpan` boundary so callers never branch on engine identity. (5)
**`auto` byte-identical / zero-Gateway lock** landed before any routing (T19) and was
re-checked after the `_tier0_seed` refactor (T27); `index`/`read`/`auto` make zero model
calls. (6) **`mode=deep` lockstep guard** (no-false-capability): `deep` provisionally
mirrors `fast`, attaching a `Deep pending` note and asserting **no** Tier-2 marker (no `2`
in `tiers_run`, no Tier-2 identity/cache key) so its later divergence is not a surprise
regression.
**Why:** Tier 0 goes blind on conceptual / natural-language queries that name no symbol
or literal — the honest Tier-0 answer is "nothing found," and a naive Scout fallback would
silently re-create that phantom. The floor and the seed-ordering exist precisely so a
model-down run can never read as a clean zero. Being the first model wave, the air-gap and
the degradation floor — previously cheap — became load-bearing and are now specified at
the Gateway request path and at resolution time, one helper, auditable in one place.
**Consequence:** Scout is **not cached** (model-backed/non-deterministic, no engine-identity
slot — the Wave-2 cache-slot question does not apply). Open follow-ups carried forward:
**FastContext package/version pinning** (the sole genuinely-open item, de-risked behind the
Protocol); a **process/WASM sandbox** for FastContext's in-process egress (tool injection
can't stop third-party in-process code opening its own socket — Scout has no sandbox unlike
Tier 2 Deep; the containment is an assumption verified by the network-deny integration test
AC11, not an asserted guarantee); and, still open from Wave 2, **Wave-2.1 substring/fuzzy
matching**.


## Compacted (older than the active window)

### Project & server bootstrap

- **Specs:** specs/0001-speccraft-v1/, specs/0001-wave-0-foundations/
- **Archive:** .speccraft/history-archive/history.md
- The project adopted speccraft for spec-first TDD from day one — all code changes flow through `/spec:new` — and shipped the agent↔server skeleton as a stub-first MCP contract whose foundational invariants every later wave depends on. The air-gap is enforced in **exactly one helper, `gateway.assert_local`**, reused for both the outbound endpoint and the inbound HTTP listener (`DEFAULT_HTTP_HOST=127.0.0.1` plus the `--allow-remote-bind` opt-out; loopback = `127.0.0.0/8` / `::1` / literal `localhost`) — the bind default and `assert_local` are the security-load-bearing surfaces and must stay auditable in one place, never scattered. `harpyja_locate` is registered returning a schema-valid empty `LocateResult` (`confidence="low"`) with no retrieval, so later waves are purely additive behind an unchanged contract. Config resolves on a **frozen `Settings` dataclass** with fixed precedence: defaults < `harpyja.toml` < `HARPYJA_*` env < per-request override. Tests live next to the package under test (`test_*.py`); there is no top-level `tests/` root.

### Deterministic Tier-0 core & symbol layer (Waves 1–2)

- **Specs:** specs/0002-wave-1-deterministic-core/, specs/0003-wave-2-symbol-layer/, specs/0004-symbol-layer-remaining-grammars/
- **Archive:** .speccraft/history-archive/history.md
- Wave 1 replaced the `harpyja_locate` stub with a model-free, reproducible Tier-0 floor: `.gitignore` is matched via `pathspec` `gitwildmatch` and **never by invoking `git`** (so non-git trees and nested/negation/anchored/`**` rules all work); incremental indexing is a two-level scheme where a cheap `(mtime, size)` gate avoids re-hashing and the sha256 hash is the change-of-record, with `--rehash` as the documented escape hatch for the coarse same-second/same-size miss; "ensure-index" *is* a full incremental refresh on every `locate` (staleness is not a separate heuristic); `rg` on `PATH` is a hard precondition for **search/locate only** (typed `RipgrepMissingError`, surfaced in `doctor`), never for the pure-Python `harpyja_index`; artifacts default to `<repo>/.harpyja/` (self-ignoring) with an `${XDG_CACHE_HOME:-~/.cache}/harpyja/<repo-hash>/` fallback when the repo is unwritable; and the contract treats its fields distinctly — `max_results` is a mandatory clamp, `mode` is accept-validate-flag (never a silent no-op), `language_hint` gives *distinct* notes for unrecognized-hint vs null-language exclusion. Wave 2 added a Tier-0, model-free symbol layer (`symbols/`) surfacing a symbol's **definition above its call sites** via tree-sitter, classified by syntactic form (no type inference) into a byte-reproducible `symbols.jsonl` ordered by `(path, start_line, end_line, kind, name)`; the durable lesson — earned over four cross-review rounds — is that **an untrusted derived artifact must authenticate its own generation with a content fingerprint, not just its producer's identity**: the `symbols.meta.json` sidecar carries `engine_identity` + `record_count` + a sha256 `content_digest` over exact record bytes and forces a full rebuild on any missing/truncated records, missing meta, identity mismatch, or fingerprint mismatch, committing records-first/meta-last via same-dir temp + `os.replace`. Degradation has two distinct persisted causes (`grammar-missing` and region-scoped `parse-error` excluding nested-definition subtrees, so a broken method never suppresses its clean enclosing class), persisted per-file so a no-reparse refresh re-surfaces it. `SymbolEngine` implements the shared **`Locator` protocol** and the orchestrator composes it with the ripgrep Locator into one `CodeSpan` stream that never branches, degrading byte-identically to the Wave-1 path on no symbol match. The 0004 follow-up brought all 10 grammars behind the **unchanged** engine/locator/formatter path and pinned the load-bearing **no-silent-coverage lockstep invariant `classify.KNOWN_LANGUAGES == indexer.SYMBOL_LANGUAGES`** (asserted in `index/test_routing.py`, re-checked at every tier boundary): a language's routing, `engine_identity` slot, and extraction rules ship in the *same* change, because routing a capability ahead of its extraction is itself a false claim (Wave 1 had latently over-routed, returning a silent clean-zero indistinguishable from "we looked and found nothing"). Identity is per-grammar via a `_GRAMMAR_SLOTS` map (`typescript`/`tsx` are two keys sharing one `tree-sitter-typescript` version that bump/absent together). Two documented limitations stand: a C-legal subset of a `.h` C++ header parses cleanly as `c` (degrade fires only on an `ERROR`/`MISSING` node — the `.h`→C default is a **scoped, not absolute, guarantee**), and `parent` is immediate-only, so same-named members under different outer types both match `Foo::bar` — a known addressing ambiguity, with method addressing kept a formatter-ranking signal, not a membership filter. Wave-2.1 substring/fuzzy matching remains the sole open follow-up.
