---
spec: "0024-v2"
title: "Scout v2 — native explorer-loop finder"
reviewers: [codex, claude-p]
quorum: 1
verdict: approve-with-comments
generated: 2026-07-05T00:00:00Z
---

# Cross-model review — 0024-v2 (Scout v2 — native explorer-loop finder)

## codex

**Verdict:** changes-requested

Concerns:
- "exactly three tools" conflicts with defining `submit_citations` as a terminal tool — wording contradictory; distinguish repo-access tools from the terminal protocol action (`submit_citations` has no repo read capability).
- Context truncation is load-bearing but unresolved: AC5 requires asserting truncation behavior while OQ3 says the policy is undecided and could discard evidence.
- `glob(pattern)` bounds not specified as concretely as `grep` — implementation escape hatch for large path floods.
- Shared return shape unclear: `read_span`/`grep` return CodeSpan/text but `glob` likely returns paths; define whether `glob` returns file-level CodeSpans, path records, or another typed observation.

Suggestions:
- Clarify tool taxonomy: three read-only repo tools PLUS one terminal `submit_citations` action (no repo read).
- Resolve context-truncation policy before plan, or narrow AC5 to verifying a configured truncation hook is invoked once policy is specified.
- Specify glob limits explicitly (`max_files`, pattern restrictions, ignored dirs, deterministic ordering).
- Define exact observation schema per tool and exact `submit_citations` arg schema before plan approval.
- State whether test files are excluded from the pre-model context map only, or also from tool search scope (excluding tests globally could hide valid localization targets).

Discussion: Direction strong, preserves ScoutBackend seam, keeps Scout a locator, enforces local gateway before I/O, typed degrade, avoids symbol-search/diagnosis scope creep. Two blocking issues are precision problems, not architectural: (1) "exactly three tools" vs. terminal `submit_citations` tool; (2) context truncation both AC-required and open-question. Approvable once contracts around the model-facing protocol, tool outputs, and bounded history are sharpened.

## claude-p

**Verdict:** approve-with-comments

Concerns:
- Self-recovery under-guarded: AC5 asserts truncation FIRES, not that it preserves the span the model ultimately cites; a truncated key observation could silently degrade a real find into honest-empty. Add an AC that truncation never drops an observation a subsequent citation depends on.
- Loop-detection specified by intent, not definition: no equality rule for "same unproductive tool call" (identical tool+args? normalized?), "unproductive" undefined, "bloat threshold" undefined. AC5 only deterministically writable once "same" and threshold are pinned — define before plan.
- New grep/glob surface diverges from existing Deep-tier host tools (`list_manifest`/`search`/`symbols`/`read_span`). Introducing grep+glob as a second ripgrep wrapper instead of reusing/adapting the existing bounded `search` risks two divergent ripgrep bounds and confused provenance. Justify or reconcile with `search`.

Suggestions:
- Title is literally "v2" — uninformative; use e.g. "Scout v2 — native explorer-loop finder".
- AC10 asserts "zero non-loopback egress" but names no observation mechanism; needs a concrete check (socket monkeypatch / netns / deny-by-default) or scope claim to `assert_local` coverage.
- `glob`'s bound unstated in What; name it (max results from Settings) so AC2 is writable.
- AC6 "any diagnosis-shaped arg rejected/ignored" is fuzzy; if schema rejects unknown fields, say "strict schema / extra fields rejected" explicitly.
- No wall-clock/latency budget; `scout_max_turns` bounds turns not time; a general model is materially slower; consider a time budget (at least flag for the bake-off).
- Add 0012 to related-specs; consider referencing 0020-0023.

Discussion: Well-constructed; replaces the backend behind an unchanged seam, restates and strengthens the three guardrails, draws an honest-empty vs. degrade line cleanly (empty `submit_citations` = honest-empty; turn-exhaustion-without-submit = `ScoutUnavailable`). Disciplined out-of-scope. OQ2 resolution (tool-call-native `submit_citations`) correct. Would block a plan only on the two self-recovery pieces (truncation safety + loop-detection definition), because that's where correctness quietly leaks; the rest is polish.

## Synthesis

**Quorum status: MET.** claude-p returned `approve-with-comments`, satisfying the default 1-approve quorum, so this spec can advance to `reviewed`. However, the two agents — reviewing independently — converged on the same two substantive gaps, and codex weighted them heavily enough to withhold approval outright. Convergent, independently-derived concerns are a strong signal and are surfaced here as **must-fix-before-plan** items rather than being absorbed into general polish, even though quorum permits advancing without them.

### Must-fix-before-plan (both reviewers converged)

**A. Self-recovery under-specification (correctness-leak risk).**
- Context-truncation policy (OQ3) is explicitly load-bearing (AC5 requires asserting it fires) yet the spec's own open questions list it as undecided. Both reviewers flag the same failure mode: truncation could silently discard the evidence the model was about to cite, turning a real find into a false honest-empty. Before plan: either resolve the truncation policy (what counts as "resolved" vs. still load-bearing) and add an AC asserting truncation never drops an observation a subsequent citation depends on, or narrow AC5 to only verify a configured truncation hook is invoked (deferring policy correctness explicitly and visibly, not implicitly).
- Loop-detection is specified by intent, not by a checkable definition. "Same unproductive tool call" needs an equality rule (exact tool+args match? normalized/canonicalized?), "unproductive" needs a definition, and the "bloat threshold" needs a concrete value or Settings knob. AC5 is not deterministically testable until these are pinned.

**B. Tool-contract precision.**
- "Exactly three tools" (What, restricted read-only tool suite) directly contradicts the spec's own definition of `submit_citations` as a fourth, terminal tool call. Resolve by explicitly separating the taxonomy: three read-only repo-access tools (`read_span`, `glob`, `grep`) plus one terminal protocol action (`submit_citations`, no repo-read capability) — and make this distinction visible everywhere the "three tools" claim appears (Why/What/AC2/AC6).
- `glob`'s output bound is unstated (contrast with `grep`'s explicit `max_files`/`max_matches`); name a concrete limit (e.g., `max_files` from Settings) so AC2 is actually writable and hostile-input coverage is testable.
- `glob`'s return shape is undefined relative to the "shared CodeSpan/text shape" claimed for all three tools — `glob` likely returns file paths, not spans/text. Define the exact per-tool observation schema (and the `submit_citations` arg schema) before plan.
- codex additionally raises, and claude-p independently raises from a different angle (existing `search` host tool), the same underlying tension: introducing `grep`/`glob` as a new ripgrep-backed surface risks diverging from the existing Deep-tier `search` tool's bounds and provenance. The spec should either justify why a separate grep/glob pair is warranted here (vs. adapting/reusing `search`) or reconcile the two so there is one bounded ripgrep contract, not two drifting ones.

### Polish (non-blocking, worth folding into plan or a quick spec edit)

- Title is literally "v2" in the frontmatter/heading — replace with something informative, e.g. "Scout v2 — native explorer-loop finder" (the tagline already exists one line down; promote it).
- AC10's "zero non-loopback egress" needs a concrete observation mechanism named (socket monkeypatch, netns, deny-by-default) or an explicit scoping to `assert_local` coverage — as written it's an assertion with no test strategy.
- AC6's "any diagnosis-shaped arg is rejected/ignored" should state the actual mechanism plainly (e.g., "strict schema; unknown/extra fields rejected") rather than leaving it fuzzy.
- No wall-clock/latency budget is defined; `scout_max_turns` bounds turn count, not time, and a general (non-fine-tuned) model will likely be materially slower per turn. At minimum flag this for the bake-off spec.
- Related-specs list should include 0012 (text-grammar predecessor explicitly referenced in the What) and consider 0020-0023 (the localization-quality findings this spec explicitly disclaims dependence on).
- Test-file exclusion scope is ambiguous: is it applied only to the pre-model context map, or also to tool search scope? Excluding tests from live `grep`/`glob` search could hide legitimate localization targets — worth one clarifying sentence.

### Disagreement note

The two reviewers reached different overall verdicts (codex: `changes-requested`; claude-p: `approve-with-comments`) despite substantial concern overlap. The difference is one of threshold, not substance: codex treats the tool-taxonomy contradiction and truncation gap as blocking precision problems in an otherwise-approvable spec, while claude-p treats the self-recovery gaps as the only plan-blocking items and everything else as polish. Both agree the core architecture (unchanged ScoutBackend seam, locator-not-diagnoser boundary, typed degrade, minimal-tools discipline, tool-call-native `submit_citations`) is sound and correctly scoped. Neither agent raised a guardrail or convention violation.

**Action:** Advance spec 0024-v2 to `reviewed` (quorum met via claude-p's approve-with-comments). Before writing the plan, the spec author must resolve the two convergent must-fix items above: (A) pin the context-truncation policy and loop-detection equality rule/threshold with a corresponding testable AC, and (B) fix the "exactly three tools" vs. `submit_citations` taxonomy contradiction, specify `glob`'s bound and return shape, and reconcile the new grep/glob surface against the existing `search` host tool. These are correctness-leak and testability risks, not architectural objections, so they should be resolved as a spec amendment (or explicitly deferred with a named follow-up in Open Questions) rather than blocking the `reviewed` status itself. The polish list can be folded into the same pass or picked up during planning.
