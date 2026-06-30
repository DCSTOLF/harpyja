---
id: "0014"
title: "AdapterParseError"
status: closed
created: 2026-06-30
authors: [claude]
packages: []
related-specs: ["0006", "0007", "0011", "0012"]
---

# Spec 0014 — AdapterParseError

## Why

Running spec 0012's AC5 surfaced a Deep crash: a malformed dspy/model response
raises `AdapterParseError` out of the RLM driver and aborts the whole run,
forcing AC5 to be run in `mode=fast` as a workaround.

This is the **same defect class** as the original Scout backend-error bug
(specs 0005/0007): a third-party parse failure that *should* map to a typed
tier-floor but instead crashes. It is a **known crash path** on the very tier
the upcoming full 12-repo OQ2 sweep will exercise heavily — an unhandled
exception at hour three loses the entire long run. Harden it **before** the
sweep, mirroring Scout's established `backend-error → ScoutUnavailable →
Tier-0 floor` pattern.

This spec **unblocks** a crash-free sweep; it does not run it.

Ref: spec 0006 (Deep/RLM, `DeepUnavailable`, typed-failure-only degrade),
0007 (Scout backend-error pattern), 0011 (degrade-rate as a first-class
metric), 0012 (AC5 `mode=fast` workaround); session RCA next-step #3.

### Invariant — typed-failure-only

`AdapterParseError` maps to `DeepUnavailable(parse-error)` → the **existing**
Deep-unavailable degrade path (skip Tier-2, fall to best Tier-1/0 with a flag).
This **widens what counts as a typed infra failure**; it does **NOT** degrade on
weak/empty/low-confidence Deep output — those stay honest Tier-2 results (the
0006 boundary both reviewers called the single most important thing that tier
gets right). Do **NOT** broaden the catch to a bare `except`.

**Why a new `parse-error` cause and not the existing `backend-error` (reconciled
against the Scout precedent):** the Scout convention maps **any *unexpected***
third-party exception to `...Unavailable(backend-error)` — a catch-all for the
*unforeseen*. `AdapterParseError` is the opposite: a **recognized, named, typed
seam** in the dspy adapter that we are deliberately pinning against source (Open
Q#1). A failure we can name and narrow-catch earns its **own** stable cause so a
plan author and an operator can tell "the dspy adapter could not parse the model
output" apart from "something unforeseen blew up in the backend." So:
`AdapterParseError` (and its pinned siblings) → `deep-degraded:parse-error`;
**truly unexpected** Deep exceptions still fold to the existing
`backend-error` catch-all (unchanged). The two are siblings under
`DeepUnavailable`, not a replacement — the narrow catch is exactly what keeps
them distinct (AC4 guards that an unrelated exception is not laundered into
`parse-error`).

### Invariant — degrade must be visible, not just safe

This is the **third** time a graceful floor could hide a defect (Scout's floor
hid the `format_citations` crash; now Deep's). Adding the Deep typed-degrade
**without** surfacing it just relocates the invisibility. So Deep degradation
gets the same first-class treatment 0011 gave Scout:
`deep-degraded:<cause>` rate reported, `degraded_dominated` aware of it. A run
where Deep silently floors on every escalation must be **impossible to miss**
at report top.

**This is the second typed-degrade floor, so the rule is promoted from a
per-spec fix to a standing project convention:** _every typed-degrade floor
surfaces its rate in aggregate, or it can go dark exactly the way Scout did._
The Deep schema fields here are one instance of that rule, not the rule itself.
This convention is a **deliverable of this spec's close**: `memory-keeper`
records it in `.speccraft/conventions.md` (every new tier/backend floor must
report a `<tier>-degraded:<cause>` rate and feed `degraded_dominated`), so the
next floor inherits visibility by default instead of re-litigating it. Baking it
only into this report schema would leave the *next* floor free to go dark.

## What

- Catch **`dspy.utils.exceptions.AdapterParseError`** (pinned against dspy 3.2.1
  source — Open Q#1, resolved below; that exact class, **alone**) at the **Deep
  driver boundary** → `DeepUnavailable(errors.PARSE_ERROR)`; a distinct stable
  cause id, not reusing an existing one. The seam is the **`rlm(query=...)` call
  in `harpyja/deep/rlm.py` `RlmBackend.run`** (currently `rlm.py:94`) — wrap
  **only** that call. Do **not** wrap `_assert_local` (an `AirGapError` floor must
  propagate loudly) or the `_rlm_factory(...)` construction, and note
  `parse_citations` (Harpyja's own regex over `prediction.answer`) never raises,
  so it is not the seam. Narrow catch at the known seam, **not** a blanket
  wrapper. Preserve the foreign cause when wrapping:
  `raise DeepUnavailable(...) from err` (the cause-preservation convention).
  Import lazily (`from dspy.utils.exceptions import AdapterParseError`) to match
  the module's existing no-top-level-`import dspy` rule.
- Preserve the typed-failure-only boundary: a malformed response → degrade;
  a well-formed but weak/empty-citation response → honest Tier-2 result, no
  degrade (regression-guarded on both sides).
- Reuse `gateway.assert_local` / the existing `DeepUnavailable` degrade routing —
  no parallel path.
- **`tiers_run` on a Deep degrade reflects the floor actually reached** (e.g.
  `[0,1]` when Deep degrades to Scout best-effort), consistent with the existing
  degrade semantics — it is **not** widened to imply Deep produced a result. The
  Deep attempt-and-degrade is made visible **not** through `tiers_run` but through
  the stable `deep-degraded:parse-error` note **and** the first-class
  `deep_degrade_rate` (below); that is the load-bearing visibility channel, so a
  floored run cannot read as "Deep never ran" at report top.
- Degrade visibility: extend the 0011 `ScoutTally` / degrade-rate machinery to
  Deep. Mirror the existing Scout fields with a Deep twin —
  `deep_degrade_count` (int) and `deep_degrade_rate` (the rate, **explicit `null`
  paired with the zero count** on a zero denominator, never an omitted key and
  never a false `0.0`; `indicative_only` self-flag on too-few-samples) — plus the
  per-cause `deep-degraded:<cause>` note surfaced at report top. New report fields
  are appended **last-with-defaults** and declared in the **one** centralized
  `_*_DEFAULTS` anti-drift map so both old-shape and new-shape blocks pass the
  **single loud validator**; schema bump `0012/1 → 0013/1`. Full
  producer → runner → swebench-driver blast radius (grep the consumers).
- **`degraded_dominated` accounts for Deep degrades without double-counting:** a
  case is "degraded" if **any** tier floored (Scout **or** Deep — union, counted
  once per case even when both degrade in the same case); `degraded_dominated`
  fires when that combined per-case degraded rate crosses
  `degraded_dominated_threshold`. The per-tier `scout_degrade_rate` /
  `deep_degrade_rate` stay separate first-class fields for attribution.
- Restore AC5-style runs to `mode=auto` where the `mode=fast` workaround was
  used (Deep no longer crashes the run).

## Acceptance criteria

Legend: `[unit]` = fakes/injected; `[integration]` = `@pytest.mark.integration`,
skip-not-fail; `[close-deliverable]` = a process gate verified at spec close, not
a pytest target.

1. **[unit]** `AdapterParseError` from the Deep driver → `DeepUnavailable(parse-error)`;
   the run does **NOT** crash; it degrades to best Tier-1/0 with a flag.
2. **[unit]** Distinct stable cause id `deep-degraded:parse-error` (not folded
   into an existing cause).
3. **[unit]** Typed-failure-only preserved: a well-formed Deep response with
   weak/empty citations → honest Tier-2 result, **NOT** a degrade (the 0006
   boundary). **Load-bearing — this is the reason Deep gets a typed floor rather
   than a blanket `try/except`:** collapsing "malformed" and "weak" into one
   degrade would silently convert real escalations into floors, which is exactly
   the 0006 boundary both reviewers flagged as the thing this tier must get
   right. Regression-guarded on both sides (AC1 = malformed degrades; AC3 =
   weak-but-real does not).
4. **[unit]** Catch is narrow — an unrelated exception is **NOT** swallowed as
   parse-error (no bare-`except` regression).
5. **[unit]** Deep degrade routes through the existing `DeepUnavailable` path (no
   parallel degrade logic); `tiers_run` reflects the **floor actually reached**
   (e.g. `[0,1]`), **not** a Tier-2 result. The Deep attempt-and-degrade is
   asserted visible through the `deep-degraded:parse-error` note **and** the
   first-class `deep_degrade_rate` — not through `tiers_run` — so a floored run
   does not read as "Deep never ran."
6. **[unit]** `deep-degraded` rate is a first-class reported field;
   `degraded_dominated` accounts for Deep degrades.
7. **[unit]** Report schema `0012/1 → 0013/1` additive; runner **and** swebench
   drivers both populate the new fields (full sink coverage — grep the
   consumers, per the recurring missed-consumer lesson).
8. **[integration]** A run whose Deep driver is made to raise the pinned parse
   exception via a **deterministic injected fault** (a fixtured/canned malformed
   response at the seam, **not** a real nondeterministic model crash) completes in
   `mode=auto` — no crash — with the Deep degrade recorded. The previously-needed
   AC5 `mode=fast` workaround is removed. (Skip-not-fail per the integration
   convention.)
9. **[unit]** The wrapped degrade preserves the foreign cause:
   `DeepUnavailable(parse-error)` is raised `from` the original
   `AdapterParseError` (`__cause__` is the source exception).
10. **[unit]** Old-shape (`0012/1`) report blocks **and** new-shape (`0013/1`)
    blocks both pass the single loud validator via the centralized
    `_*_DEFAULTS` map; `deep_degrade_rate` is explicit `null` (paired with a zero
    `deep_degrade_count`) on a zero denominator — never an omitted key, never a
    false `0.0`.
11. **[unit]** `degraded_dominated` counts a case **once** when any tier floored:
    a case where **both** Scout and Deep degrade is a single degraded case (no
    double-count); the combined per-case degraded rate drives
    `degraded_dominated`, while `scout_degrade_rate` / `deep_degrade_rate` remain
    separate for attribution.
12. **[close-deliverable]** The "every typed-degrade floor reports its rate +
    feeds `degraded_dominated`" convention is recorded in
    `.speccraft/conventions.md` via `memory-keeper` at spec close — tracked as a
    required close deliverable so the visibility rule is not skipped during
    closeout (process gate, not a pytest target).

## Out of scope

- The full 12-repo sweep + OQ2 calibration (this **unblocks** a crash-free
  sweep, it does not run it).
- Gate false-escalation (requests-1766, separate gate-quality lead).
- Q8 `scout_model` default-flip.
- Wave-2.1 substring/fuzzy.
- **`dspy.utils.exceptions.ContextWindowExceededError`** — the only sibling dspy
  exception class; a *distinct* typed failure (prompt exceeds the model's context
  window), **not** a parse failure. It currently also escapes the RLM and would
  crash a run, so it is a candidate for its **own** future
  `deep-degraded:context-window` cause — but folding it into `parse-error` here
  would violate the narrow-catch invariant. Out of scope; flagged as a follow-up.

## Open questions

1. **(RESOLVED — pinned against dspy 3.2.1 source.)** Exact exception class to
   catch: **`dspy.utils.exceptions.AdapterParseError`, that class alone.**
   Findings from the installed source (`.venv/.../dspy/`, dspy `3.2.1`, the
   pinned `>=3.2.1`):
   - `AdapterParseError`'s MRO is `[AdapterParseError, Exception, ...]` — a
     **direct `Exception` subclass**. There is **no broader "adapter parse
     family" base class**, so the "alone vs broader family" question dissolves:
     the single class *is* the family. It is the **one** class raised by **all
     four** adapters (`ChatAdapter`, `JSONAdapter`, `XMLAdapter`, base `Adapter`)
     on a parse failure, and `JSONAdapter` **wraps** raw `json.JSONDecodeError`
     into it (`json_repair` → raise `AdapterParseError`) — so nothing rawer
     escapes. Catching it is neither over-narrow (no sibling parse subclasses to
     miss) nor over-broad (it subsumes no unrelated error).
   - **Not** top-level re-exported (`hasattr(dspy, "AdapterParseError")` is
     `False`) ⇒ import path `from dspy.utils.exceptions import AdapterParseError`.
   - **Propagation confirmed:** the escaping exception is specifically
     `AdapterParseError` from a sub-LLM adapter parse inside the RLM explorer
     loop; RLM's *own* final-output parser catches `(ValueError,
     pydantic.ValidationError)` and `CodeInterpreterError`/`SyntaxError` and
     returns them as error strings (they do **not** escape). RLM **config**
     errors (`RuntimeError` no-LM, `ValueError` empty-prompt, `TypeError`
     bad-tool) are programming/config faults that must surface and are **not**
     folded (AC4 guards this). The one sibling, `ContextWindowExceededError`, is
     out of scope (see Out of scope).
   - This is exactly the Scout "read the source, don't guess the shape" lesson
     honored: the failure crashes one layer down (inside `rlm(query=...)`, not in
     Harpyja's `parse_citations`), which is why the seam is the `rlm()` call.
2. **(RESOLVED — treat-as-failed; structurally the only option.)** Does a
   partial/streaming Deep response ever yield SOME valid citations before the
   parse failure? **No salvage is possible.** Source confirms: on
   `AdapterParseError` the `rlm(query=...)` call **never returns**, so there is no
   `prediction.answer` and Harpyja's `parse_citations` never runs — there is
   literally no partial prefix in hand to salvage. Treat-as-failed is therefore
   not merely the safer choice but the only structural one; it also independently
   satisfies the "never a confident citation that wasn't verified" guardrail. (A
   *successful* `rlm()` returning few/zero citations remains an honest Tier-2
   result, never a salvage and never a degrade — the AC3 boundary.)
3. `deep-degraded:parse-error` as a single cause vs a finer split (adapter vs
   model-output malformation) — **provisional single cause**. (The separate
   question of `parse-error` vs folding into the existing `backend-error` is
   **resolved** in the typed-failure-only invariant above: a named/typed seam
   earns its own cause; truly-unexpected exceptions still fold to `backend-error`.)
