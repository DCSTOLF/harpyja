---
id: "0024"
title: "v2"
status: closed
created: 2026-07-05
authors: [claude]
packages: [scout]
related-specs: ["0005", "0006", "0007", "0011", "0012", "0014", "0017", "0020", "0021", "0022", "0023"]
---

# Spec 0024 — v2

Scout v2 — native explorer-loop finder (grep/glob/read, no symbol tool yet).

## Why

The FastContext-backed Scout is being retired. The upstream 4B model was
retracted and is unobtainable; its only surviving artifacts are lossy/broken
quantizations — an unmaintainable, unshippable dependency, and this is
independent of the localization-quality finding from specs 0020–0023.

This spec replaces the Scout backend with a self-contained explorer loop
Harpyja owns end-to-end: a general tool-calling model driven over a small
read-only tool suite to a citation list, behind the **UNCHANGED** ScoutBackend
seam. It also removes the confound that made prior model tests uninterpretable
(a buggy third-party harness), producing a clean, model-agnostic rig for the
later model bake-off.

Ref: spec 0005 (ScoutBackend protocol + DI seam), 0007/0011 (FastContext
adapter + `citation=False` final-answer parsing we already own), 0006/0014
(untrusted-caller tool boundary + typed degrade), `index/` (manifest + repo
map), `symbols/` (Tier-0 — **NOT** wired here; see out-of-scope).

### Load-bearing invariants

- **Scout stays a locator, not a diagnoser.** The loop's terminal output is
  Harpyja's existing citation contract — repo-confined, clamped `file:line`
  CodeSpans via the existing `normalize_spans`, `source_tier=1`. It does NOT
  emit root-cause analysis, fix suggestions, or prose diagnosis. The finder
  finds; downstream agents reason and edit.
- **Untrusted-caller boundary.** The model driving the loop is an untrusted
  caller of the tools (same posture as the RLM host tools). Every tool is
  READ-ONLY, repo-path-confined, and output-bounded; no terminal/shell/write
  access; nothing reaches outside the repo.
- **Behind the unchanged seam.** This is a new ScoutBackend impl injected via
  the existing DI seam; unit tests keep driving fakes. The orchestrator, gate,
  matrix, formatter, and Locator boundary are untouched. Air-gap via the
  existing `gateway.assert_local` on the resolved endpoint before any model I/O.
- **Minimal tools by design.** The tool suite here is deliberately
  grep/glob/read ONLY. This is the minimal-tools baseline for the later model
  bake-off — it isolates raw finder capability so results are attributable.
  Richer tools (AST symbol search) are a separate, staged spec. Do NOT expand
  the tool suite to "help" a weak model; a weak-model result is a finding, not
  a bug.

## What

The explorer loop:

- **Context map (pre-model).** Build a compact, high-level repo map from the
  EXISTING manifest — filtered tree (respect `.gitignore` + vendor/test/
  generated exclusions already in the indexer), no raw file contents. Injected
  with the query so the model sees layout without loading files. **The
  vendor/test/generated exclusion applies to the CONTEXT MAP ONLY, not to tool
  scope**: `grep`/`glob`/`read_span` must still reach excluded files (a test
  can be the actual localization target) — map-filtering is a display concern,
  never a search-confinement one.
- **Tool suite — three read-only repo tools + one terminal action.** The three
  navigation tools are: `read_span(path, start, end)` bounded;
  `glob(pattern)`; `grep(pattern, scope)` ripgrep-backed. All three are
  repo-confined, clamped, and output-bounded from existing Settings —
  symmetric contracts: `read_span` (max lines), `grep` (`max_files`/
  `max_matches`), `glob` (`max_paths`). Each returns the shared CodeSpan/text
  shape — `glob`'s path list is normalized to that shape (file-level records),
  not raw strings. Distinct from these is the single **terminal action**
  `submit_citations` (below), which ends the loop and has NO repo-read
  capability; "three tools" means three navigation tools, not "three total
  model-facing calls." The `grep`/`glob` ripgrep surface **shares one bounded
  ripgrep implementation with the Deep-tier `search` host tool** (single source
  of truth for bounds and repo-confinement) — no second, subtly-different grep
  surface.
- **Bounded loop.** One structured tool call per turn; append raw tool output
  to history; cap at `scout_max_turns` (existing Settings, provisional; justify
  default). A wall-clock budget bounds the loop alongside the turn cap (turns ≠
  time for a general model): the gateway HTTP timeout (spec 0017) is the
  per-call floor; a whole-loop ceiling stops one slow turn from wedging.
  Model-agnostic — any OpenAI-compatible tool-calling model via the gateway.
- **Self-recovery (lightweight, in-loop).** Two deterministic mechanisms.
  **Loop detection**: an exact `(tool_name, normalized_args)` equality repeated
  for N consecutive turns (N provisional, in Settings) that adds no new spans to
  history → inject a corrective note. **Context management**: when history
  exceeds a concrete token/char cap (Settings), truncate — but truncation MAY
  drop ONLY stale navigational chatter (repeated calls, superseded listings),
  NEVER the raw output of a `read_span`/`grep` hit whose location could still
  appear in a final citation. If recency-capping forces dropping such an
  observation, a compact index of the dropped spans is re-injected so nothing
  citable is unrecoverable. The invariant: **truncation must never convert a
  real find into honest-empty.**
- **Terminal parse (tool-call-native `submit_citations`).** The model ends the
  loop by calling a dedicated `submit_citations` terminal tool with structured
  citation args (not by emitting free text to be regexed). Its args are
  validated and normalized to CodeSpans via the existing `normalize_spans`;
  malformed/out-of-repo/over-budget refs dropped; empty is honest-empty
  (existing four-state degrade unchanged). This replaces the inherited
  text-grammar (`<final_answer>`) parse path from the FastContext era (0011/
  0012) — a decision fixed by OQ2 (see below).
- **Degradation UNCHANGED.** Model/gateway unreachable, loop exhausts turns
  with no citation, loop exceeds the wall-clock ceiling with no citation, or
  backend raises → typed `ScoutUnavailable(<cause>)` → existing Tier-0 floor.
  Distinct stable cause ids; degrade rate reported (the "every floor reports its
  rate" convention).

## Acceptance criteria

Legend: `[unit]` = fakes/injected, no model; `[integration]` =
`@pytest.mark.integration`, live, skip-not-fail.

1. **[unit]** New ScoutBackend impl satisfies the existing Locator/CodeSpan/
   Citation boundary; injected via the DI seam; fakes drive the loop
   deterministically.
2. **[unit]** Each of the three navigation tools (`grep`/`glob`/`read_span`) is
   read-only, repo-confined, and output-bounded (`max_matches`/`max_files` /
   `max_paths` / max-lines from Settings); a path outside the repo and an
   over-budget request are both rejected/clamped (hostile-input coverage).
   `glob`'s path results are normalized to the shared CodeSpan/text shape, not
   returned as raw strings.
3. **[unit]** The context map is built from the manifest (filtered tree, no raw
   contents) and injected with the query; no file bytes loaded pre-loop. The
   vendor/test/generated exclusion is asserted to apply to the map ONLY — a
   test/vendor file remains reachable via `grep`/`glob`/`read_span` (map-filter
   ≠ tool-scope filter).
4. **[unit]** Bounded loop: one tool call/turn, output appended, terminates at
   `scout_max_turns`; a non-terminating fake is killed by the turn cap (never
   hangs). The whole-loop wall-clock ceiling also terminates the loop when
   turns alone would not (a single slow/hung call cannot wedge it).
5. **[unit]** Self-recovery, asserted against explicit rules (not just plumbed):
   (a) an exact `(tool_name, normalized_args)` repeat for N consecutive turns
   adding no new spans triggers the corrective injection; (b) history past the
   Settings token/char cap triggers truncation. **Preservation (the correctness
   guard, proving the negative):** a case where a final citation depends on a
   `read_span`/`grep` observation OLDER than the bloat threshold still resolves
   correctly after truncation runs — truncation MUST NOT convert that real find
   into honest-empty (dropped-span index re-injected if the raw observation is
   capped).
6. **[unit]** A `submit_citations` terminal action with structured args →
   confined, clamped, `source_tier=1` CodeSpans via `normalize_spans`;
   out-of-repo/nonexistent/over-budget/malformed refs dropped. Its args validate
   under a **strict schema — unknown/extra fields rejected**; a diagnosis-shaped
   field fails schema (the enforceable form of the locator-not-diagnoser guard,
   not a soft check). `submit_citations` has no repo-read capability.
7. **[unit]** `assert_local(resolved endpoint)` called before any model I/O;
   non-loopback → `AirGapError`, loop never starts.
8. **[unit]** Degradation: model down / turn-exhausted-empty / wall-clock-
   exhausted-empty / backend-raise → distinct typed `ScoutUnavailable` causes →
   existing Tier-0 floor; NOT raised for a well-formed empty `submit_citations`
   result (honest-empty).
9. **[unit]** Degrade-rate is a first-class reported field (per the standing
   convention).
10. **[integration]** Live: the loop runs a real tool-calling model over a real
    repo to a parsed citation list, completes within the turn cap, and asserts
    zero non-loopback connections via the same network-deny harness used in the
    0007/0014 air-gap tests (egress is observed, not merely asserted).

## Out of scope

Named, staged follow-ups — do NOT pull in:

- **AST symbol-search tool (Tier-0-as-a-tool)** — the STAGED second round; this
  spec is the minimal-tools baseline for clean model attribution. Do not wire
  Tier-0 into the loop here.
- **The model bake-off / choosing the driving model** — a later spec; this
  ships a model-AGNOSTIC loop driven by whatever the gateway serves.
- **The representative eval set** — separate spec; not built here.
- **Deleting the FastContext adapter code / dependency removal** — do that in a
  dedicated cleanup once this backend is proven, so the two aren't entangled in
  one diff.
- **OQ2 / gate / threshold work** — all downstream and untouched.

## Open questions

1. **`scout_max_turns` default** for a general (non-fine-tuned) model over three
   tools — the prior value was tuned to a specialized finder; a general model
   may need more turns to localize. Provisional, justify, flag for tuning in the
   bake-off.
2. **RESOLVED — tool-call-native `submit_citations`.** The model ends the loop
   by calling a dedicated `submit_citations` tool with structured citation args,
   NOT by emitting free text parsed by the 0011/0012 `<final_answer>` grammar.
   Rationale: the text grammar is inherited baggage from a FastContext-era
   constraint we no longer have; reusing it would carry forward the exact
   text-parsing fragility behind three of the era's worst bugs. This is fixed
   before plan and reflected in the What (Terminal parse) and AC6. Remaining
   sub-question for plan: the precise `submit_citations` arg schema (per-span
   fields, file-level vs. spanned representation) — a schema-design detail, not
   a fork of the parse path.
3. **RESOLVED — truncation is citation-preserving by rule.** Truncation may drop
   ONLY stale navigational chatter (repeated calls, superseded listings), never
   the raw output of a `read_span`/`grep` hit whose location could still appear
   in a final citation; if recency-capping forces dropping such an observation,
   a compact index of the dropped spans is re-injected so nothing citable is
   unrecoverable. The binding invariant — truncation must never convert a real
   find into honest-empty — is asserted by AC5's preservation case (proving the
   negative), not just that truncation fires. Loop-detection is likewise pinned:
   exact `(tool_name, normalized_args)` equality over N consecutive no-new-span
   turns, with a concrete Settings token/char bloat cap. Remaining for tuning
   (not a fork): the value of N and the bloat cap — provisional, flagged for the
   bake-off alongside `scout_max_turns` (OQ1).
