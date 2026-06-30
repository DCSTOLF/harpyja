---
spec: "0003-wave-2-symbol-layer"
title: "Wave 2 — Symbol layer (tree-sitter, Python + Go)"
revision: 1
date: 2026-06-26
reviewers: [codex, claude-p]
verdicts: [changes-requested, approve-with-comments]
quorum: 1 approve-or-approve-with-comments
quorum-met: nominally (claude-p approve-with-comments) — BLOCKED by open guardrail violation (codex) and claude-p's explicit conditionality; spec must NOT advance to reviewed
status: draft
generated: 2026-06-26T12:00:00Z
---

# Cross-model review — 0003-wave-2-symbol-layer (revision 1)

## codex

**Verdict:** changes-requested

Concerns:

- Partial/substring symbol matching (D10a) conflicts with the no-match degradation invariant (D10b/AC11): a query with no exact symbol match but a partial symbol hit is a third state that AC11 does not account for — "matches no symbol name" is no longer exhaustive. The additive-only guarantee is ambiguous at this boundary.
- Partial-match semantics are completely underspecified: case sensitivity, token boundaries, minimum length, whether a partial match can trigger definition promotion — none are testably defined. AC9 only pins exact case-sensitive behavior, leaving the partial path untestable.
- Method addressing via Parent.name / Parent::name is ambiguous at the implementation boundary: tokenization splits on non-identifier chars and then "the formatter matches a parent+name token pair," but adjacency requirement, order requirement, and which separators count are all undefined — a naive implementation could promote "Foo bar", "bar Foo", or unrelated adjacent tokens.
- D4 grammar-unavailable wording is imprecise: the text says "the affected file's cleanly-parsed definitions are still emitted" — but if the grammar is unavailable, there are NO cleanly-parsed definitions for that language at all. The intended behavior is: emit zero symbol records for files in that language, flag grammar-missing in degraded, index succeeds.
- symbols.meta.json (D15) is not deterministic enough: no fixed key order, no stable language-array ordering, no defined atomicity ordering between meta and jsonl on write, and no stated behavior when the sidecar is missing or unreadable while symbols.jsonl is valid.

Suggestions:

- Either remove partial/substring matching from Wave 2 (exact + Parent.name suffices for the core value path), or make it explicitly non-promoting unless a separate AC proves it cannot violate AC11, and fully define its semantics.
- If partial matching is retained, define precisely: case folding, substring vs identifier-prefix, minimum length, max_results bound, interaction with D10b, and add an AC fixture.
- Define method-address matching as an ordered adjacent token pair from the same query segment, with separators limited to `.` and `::`, and add an AC fixture for `Foo.bar` and `Foo::bar`.
- Rewrite D4 grammar-missing: no grammar available for language L means zero symbol records for all L files; index succeeds; degradation note emitted naming the language; ripgrep remains the fallback.
- Make symbols.meta.json byte-reproducible (fixed key order + stable-sorted languages array), or explicitly exempt it and document that it is not byte-comparable. State that records are renamed first, meta last, on write; inconsistency on read triggers rebuild.

Guardrail violations:

- **Rule: "Graceful degradation: every layer has a fallback; never return an unverified confident citation."** Location: D10a/D10b and AC11. The spec introduces partial/substring matching that can reorder results when an exact match is absent, but AC11 is defined only for the "no match at all" case. A partial match that promotes a wrong definition is an unverified confident citation returned to the caller with no fallback signal. This is a guardrail-class violation until partial matching is either removed or fully specified with an AC proving it cannot promote a definition the caller cannot verify.

Convention violations:

- **Rule: "Byte-reproducible files use fixed key order + stable sort."** Location: D15 symbols.meta.json sidecar. The sidecar's key order and languages-array sort order are unspecified.

---

## claude-p

**Verdict:** approve-with-comments (CONDITIONAL — "resolve the two P0/P1 consistency concerns and this is an approve")

Concerns:

- P0 Grammar-version staleness gap (D7 + D15): the rebuild trigger is keyed on `schema_version`, which is the symbols.jsonl FORMAT version. When a pinned grammar (tree-sitter-python or tree-sitter-go) is bumped, schema_version does not change. A file that passes the (mtime, size) gate will reuse stale symbol records silently — the exact failure mode D15 is designed to prevent. The meta.json `engine` field exists but the rebuild condition in D15/AC8 never checks it. Fix: rebuild must be triggered by any change to full engine identity (runtime version + each grammar version), not schema_version alone.
- P1 Two-file crash-ordering unpinned (D15): splitting metadata into symbols.meta.json introduces a multi-file atomicity hazard that single-file os.replace does not have. If meta.json (with a new schema_version or engine) lands before symbols.jsonl and the process dies, the next run sees a matching meta + stale records — silent staleness. The write-ordering invariant (records renamed first, meta last) and the read-path recovery rule (meta present but inconsistent with records means rebuild) must be stated explicitly.
- P1 Partial/substring matching underspecified + collides with no-match invariant (same concern as codex): AC11's "matches no symbol name" must be "no exact AND no partial match"; a partial-match fixture is absent from the ACs.
- P2 Parse-error file-flag scope ambiguous (D4/AC4): the rule flags a file when a definition subtree is error-spanned, but is silent on ERROR/MISSING nodes that appear OUTSIDE any definition (a broken top-level statement, for example). Such a file could emit all clean definitions and never be flagged, producing silent partialness. Clarify: either any ERROR/MISSING node in the tree flags the file, or only definition-spanning ones do (and document the latter as a known partial-flag gap).
- P2 ABI/version-skew (D17/AC15): individual grammar packages are pinned at explicit versions, but the spec does not address ABI mismatch between the tree-sitter runtime and an individually-pinned grammar at load time. Confirm this is caught at load and routed through D4 grammar-unavailable rather than throwing.

Suggestions:

- AC7's collision example (decorator + one-line def) is WRONG: a decorator is not an extracted symbol, so "@decorator + its decorated one-line def" yields exactly ONE symbol record, not two sharing start_line — the collision proof is vacuous. Replace with a genuine collision: semicolon-joined module-level constants `A = 1; B = 2` producing two `constant` records with the same start_line AND end_line.
- Specify Go generic receivers: `func (s *Stack[T]) Push()` should normalize parent to `Stack` (strip pointer AND type parameters); D3 mentions pointer-stripping only.
- State behavior when symbols.meta.json is missing or unreadable while symbols.jsonl is present (presumably treat as schema mismatch and rebuild).
- Note the read-path cost of corruption detection (D15): checking for a corrupt symbols.jsonl requires JSON-parsing every line on every refresh, including the no-reparse incremental path. This is acceptable but should be stated so implementers don't optimize it away.
- Pin partial-match case-sensitivity and add an AC fixture for the substring path, or remove partial matching.

Convention violations:

- **Rule: "Byte-reproducible files use fixed key order + stable sort."** Location: D15 symbols.meta.json sidecar — languages array ordering and JSON key order are unspecified.

---

## Synthesis

### Quorum and overall verdict

Quorum is nominally met: claude-p gave approve-with-comments. However, claude-p's approval is explicitly conditional ("resolve the two P0/P1 consistency concerns and this is an approve"), codex gave changes-requested and raised a guardrail violation, and both reviewers independently flag a convention violation. An open guardrail violation plus convergent P0 correctness holes mean the spec must not advance to `reviewed`. Verdict: **changes-requested**. Status remains `draft`.

### Resolved from round 0 — confirmed sound by both reviewers

The following round-0 items were addressed in revision 1 and are accepted as resolved:

- Parse-error threshold now precisely defined by ERROR/MISSING-spanning definition nodes (D4/AC4). One scope ambiguity remains at P1c below, but the core threshold decision is sound.
- `symbols_indexed` is total-in-index (D6/AC3). Unambiguous.
- Full `(path, start_line, end_line, kind, name)` sort key (D9). Correctly resolves the earlier tie-break gap.
- `Locator` protocol composition — SymbolEngine behind shared protocol, orchestrator never branches (D16/AC9). Convention violation closed.
- D10a exact case-sensitive matching pinned. Core case-sensitivity decision is correct.
- `constant` boundary rules, receiver normalization, nested-def exclusion (D3/AC2). Vocabulary is adequately closed.
- Grammar packaging resolved to pinned individual packages (D17/AC15). Correct choice.
- Grammar unavailability degrades via D4 not error (D17). Pattern is right; wording fix needed (see P1c).

### New issues found in revision 1

#### P0a — Partial-matching vs no-match invariant (BOTH agents; codex: guardrail violation)

D10a introduces partial/substring matching as a fallback when no exact match exists, but:

1. AC11 defines no-match degradation as "query matches no symbol name" — this is now a two-state description of a three-state system (exact match / partial match / no match). The additive-only guarantee is broken at the partial boundary.
2. A partial match that promotes the wrong definition is an unverified confident citation with no fallback — the graceful-degradation guardrail. This is a guardrail-class violation.
3. Partial-match semantics are entirely untested: case sensitivity, substring vs prefix, minimum length, whether partial can trigger promotion, and max_results interaction are all undefined.

Both reviewers agree. Recommended resolution: **defer substring/partial matching to a follow-up spec**. Exact-name matching plus Parent.name/Parent::name addressing is sufficient for Wave 2's core value path. If partial matching is retained, it requires a full semantics specification and a dedicated AC proving it cannot promote an unverified definition, and AC11 must be redefined as "no exact AND no partial match."

#### P0b — Grammar-version staleness in rebuild trigger (claude-p)

The rebuild condition in D15/AC8 is keyed on `schema_version`, which is the record-format version. When a pinned grammar package is upgraded, `schema_version` does not change, so the (mtime, size) gate passes and stale symbol records are reused silently — the exact failure D15 is designed to prevent. The existing `engine` field in symbols.meta.json captures full engine identity but the rebuild check ignores it. Fix: the rebuild condition must compare full engine identity (runtime version + each grammar version as encoded in the `engine` field), not schema_version alone.

#### P1a — Two-file crash-ordering unpinned (claude-p)

Splitting metadata into symbols.meta.json introduces a multi-file write hazard. If the process dies after meta.json lands but before symbols.jsonl is renamed, the next run sees a consistent-looking meta paired with stale or empty records — silent staleness. The spec must state: (1) records file is renamed first, meta file last; (2) the read path treats "meta present but engine/schema inconsistent with records header" as a mismatch requiring full rebuild. Without this invariant, D15's atomicity claim is not sound.

#### P1b — Sidecar byte-reproducibility (BOTH agents; convention violation)

symbols.meta.json has unspecified key order and unspecified languages-array sort order. Two index runs over an identical tree can produce byte-different sidecars, violating the project convention that byte-reproducible files use fixed key order and stable sort. Both reviewers agree this is a convention violation. Fix: specify fixed JSON key order and a stable sort for the languages array (alphabetical), or explicitly document that symbols.meta.json is exempt from byte-reproducibility and is not byte-compared across runs (and add a note explaining why).

Additionally, both reviewers note that the spec does not state the behavior when symbols.meta.json is missing or unreadable while symbols.jsonl is valid. The presumed behavior (treat as mismatch, rebuild) must be stated explicitly.

#### P1c — D4 wording and parse-error flag scope (codex + claude-p)

Two sub-issues in the degradation surface:

1. (codex) D4 grammar-unavailable wording: "the affected file's cleanly-parsed definitions are still emitted" is contradictory — if the grammar is unavailable, there is no parser, so there are no cleanly-parsed definitions. Correct wording: zero symbol records are emitted for files in the grammar-missing language; index succeeds; degradation note is emitted naming the language; ripgrep remains available.

2. (claude-p) Parse-error flag scope: D4/AC4 flags a file only when a definition subtree is error-spanned. ERROR/MISSING nodes outside any definition (e.g. a broken top-level statement) can leave a file that emits all its clean definitions and is never flagged — silent partialness. The spec must state whether any ERROR/MISSING node in the tree triggers the file flag, or only definition-spanning ones do (and if the latter, document it as a known intentional gap with the ripgrep fallback covering it).

#### P2 — Minor correctness and coverage gaps

- **AC7 wrong collision example (claude-p):** A decorator is not an extracted symbol, so "@decorator + its decorated one-line def" yields one record, not two — the collision proof is vacuous. Replace with `A = 1; B = 2` on the same line, producing two `constant` records with identical start_line and end_line.
- **Go generic receiver type-parameter stripping (claude-p):** D3 specifies stripping the pointer from `(s *Foo)` but does not cover generic receivers `(s *Stack[T])`. The normalized parent should be `Stack` (strip pointer AND type parameters). Specify this.
- **Method-addressing adjacency rule (codex):** D10a says the formatter matches a parent+name token pair but does not define ordering, adjacency, or which separators qualify. Define: an ordered adjacent token pair from the same query segment with `.` or `::` as the separator.
- **ABI mismatch routing (claude-p):** D17/AC15 pins runtime and grammar versions but does not confirm that a runtime/grammar ABI mismatch at load time is caught and routed through D4 grammar-unavailable rather than raising an unhandled exception. State this explicitly.
- **Read-path JSON-parse cost (claude-p):** Corruption detection requires JSON-parsing every line of symbols.jsonl on every refresh, including the no-reparse incremental path. This is acceptable but should be documented so implementers do not silently optimize it away by skipping the check on cache hits.

### Action

**Status stays `draft`.** The spec must not advance to `reviewed` with an open guardrail violation (P0a) and two correctness holes that both reviewers independently identified (P0b grammar-version staleness, P1a crash-ordering).

Run `/speccraft:spec:revise` to address P0a, P0b, P1a, and P1b as a minimum set before re-review. P1c and the P2 items should be folded into the same revision pass; they are small but collectively they leave ambiguous behavior on observable paths.

Minimum revision checklist:

1. P0a — Remove partial/substring matching from Wave 2 scope (recommended), OR provide full semantics + AC + redefine AC11 as "no exact AND no partial match" + confirm guardrail is met.
2. P0b — Change rebuild trigger to check full engine identity (runtime + grammar versions via the `engine` field), not schema_version alone.
3. P1a — State write-ordering invariant (records first, meta last) and read-path recovery rule (meta/records mismatch → rebuild).
4. P1b — Fix symbols.meta.json: fixed key order + alphabetically-sorted languages array (convention compliance), plus state missing/unreadable-sidecar behavior.
5. P1c — Rewrite D4 grammar-missing sentence; clarify parse-error flag scope for non-definition ERROR nodes.
6. P2 — Replace AC7 collision example; add Go generic receiver stripping to D3; define method-addressing separator and adjacency rule; state ABI-mismatch routing; add read-path cost note.
