---
spec: "0003-wave-2-symbol-layer"
title: "Wave 2 — Symbol layer (tree-sitter, Python + Go)"
date: 2026-06-26
reviewers: [codex, claude-p]
verdicts: [changes-requested, approve-with-comments]
quorum: 1 approve-or-approve-with-comments
quorum-met: true
status: reviewed
generated: 2026-06-26T00:00:00Z
---

# Cross-model review — 0003-wave-2-symbol-layer

## codex

**Verdict:** changes-requested

Concerns:

- Parse failure semantics underspecified: tree-sitter returns partial trees with ERROR/MISSING nodes rather than throwing; D4/AC4 do not define the threshold at which a file is "parse-error degraded" vs. successfully indexed with partial symbols extracted.
- Incremental symbol reuse (D7) assumes prior symbol records are available and trustworthy; spec does not define behavior when `symbols.jsonl` is missing, truncated, stale, or version-incompatible while the `(mtime, size)` gate would skip re-parsing.
- Locate integration risks bypassing the shared Locator/CodeSpan abstraction by having the orchestrator consult `symbols.jsonl`/SymbolEngine directly — conflicts with the Tier-engine protocol unless symbol search is explicitly adapted behind it.
- Grammar packaging is left as an open question even though it affects reproducibility, air-gapped installs, CI fixtures, and degradation behavior; should be resolved before implementation acceptance.

Suggestions:

- Define "parse-error" precisely: either any tree with ERROR/MISSING at or above definition-bearing nodes is degraded for that file, or partial extraction is allowed but must emit a distinct `degraded` note — pick one.
- Add an artifact version/schema field to `symbols.jsonl`; specify that a missing, unreadable, or schema-incompatible symbol artifact forces a full symbol rebuild without requiring `--rehash`.
- State that symbol search is exposed through the shared Locator protocol returning common CodeSpan/Citation; keep SymbolEngine internal.
- Resolve grammar packaging in this spec, including pinned deps and behavior when the package is absent in tests.

Convention violations:

- **Tier engines implement the shared Locator protocol and return common CodeSpan/Citation; callers never branch on engine.** Location: "What / Symbol-aware locate" narrative and AC8. The spec describes the orchestrator consulting SymbolEngine directly rather than through the shared protocol, which would make locate branch on whether a symbol engine is present.

---

## claude-p

**Verdict:** approve-with-comments

Concerns:

- Query-to-symbol-name matching mechanism is undefined, yet definition promotion (D10) depends on it. Wave-1 locate runs the query as a literal ripgrep term; how a free-text query yields candidate symbol names (whole-string equality? token split? prefix?) is never pinned. AC9 exercises only a single bare token, leaving the core value path under-tested.
- Case sensitivity of symbol-name matching is unspecified. This matters for Go (exported vs. unexported by case) and Python. Must be pinned.
- Python `constant` rule ("upper-case top-level assignment") is a heuristic treated as a closed vocabulary member (D3). Edge cases unaddressed: annotated assignments (`X: int = 5`), tuple unpacking (`A, B = 1, 2`), augmented assignments, `Foo = namedtuple(...)`. Narrow the rule or add boundary fixtures.
- Python kind vocabulary omits nested functions/closures, `async def`, and nested classes. Go omits whether pointer-receiver (`s *Foo`) and value-receiver (`s Foo`) both normalize `parent` to `Foo`. AC2 is ambiguous without these.
- `symbols_indexed` semantics under incremental indexing (D6): "number of `symbols.jsonl` records" implies total-in-index, but file counters usually mean "this run." State explicitly it is the total-in-index count, or AC3 is ambiguous on incremental refresh.
- `(path, start_line)` tie-break (D9/AC10) can collide (decorator line, one-line def, co-located symbols sharing `start_line`). Without a documented secondary key (e.g. `end_line`, then `kind`, then `name`), byte-identical output (AC7) is not guaranteed.
- Corrupt or partially-written `symbols.jsonl` recovery is uncovered. AC11 handles a missing prior file (build from scratch), but D7's incremental merge reads prior records — an unreadable or truncated file needs a defined fallback.

Suggestions:

- Resolve Open Question 1 (grammar packaging) before `/spec:plan` — it is closer to a guardrail dependency than a free implementation choice.
- AC5 needs a stated testability seam: inject the parser/engine so a spy can assert zero parse calls on a cache hit; name that collaborator in the spec.
- Add a `Foo.bar` method-addressing case to AC9 — D10 promises parent-addressability but no AC exercises it.
- State the no-match behavior explicitly: when a query matches no symbol, locate degrades to the exact Wave-1 ripgrep path; assert it as an invariant.

---

## Synthesis

### Status

Quorum is met (claude-p: approve-with-comments). Verdict: **reviewed**. The concerns below are pre-plan refinements, not blockers to the spec existing — but the P0 items must be resolved in the spec before `/spec:plan` is issued.

### Clustered concerns by severity

#### P0 — Must resolve before /spec:plan

1. **Parse-error threshold (both agents, overlapping).** Codex flags that tree-sitter returns partial trees with ERROR/MISSING nodes, not exceptions. Claude-p's corrupt-`symbols.jsonl` concern compounds this: D4/AC4 say "fails to parse" without defining what "fail" means for a partial tree. The spec must pick one of: (a) any tree containing ERROR/MISSING nodes at or above definition-bearing positions is treated as degraded for that file, zero symbols extracted; or (b) partial extraction is permitted but every extracted symbol from a file with ERROR nodes carries a `degraded` flag. This choice also determines whether AC4's forced-failure test is meaningful.

2. **`symbols.jsonl` corruption and schema-incompatibility under incremental merge (both agents, overlapping).** Codex raises the case where `symbols.jsonl` is missing, truncated, stale, or schema-incompatible while the `(mtime, size)` gate would skip re-parsing. Claude-p raises the unreadable/truncated case in the context of D7's merge step. Both gaps are the same root cause: D7 specifies the happy-path reuse but has no defined fallback for an unreadable or incompatible prior artifact. The spec must state: an unreadable, truncated, or schema-mismatched `symbols.jsonl` forces a full symbol rebuild (equivalent to `--rehash` for the symbol layer) and this must not require an explicit `--rehash` from the caller.

3. **Query-to-symbol-name matching mechanism undefined (claude-p; highest-priority unique concern).** D10 and AC9 rely on "the query matches a symbol name," but the spec never defines how a free-text locate query becomes candidate symbol names — whole-string equality? token split on whitespace/punctuation? The case sensitivity rule is also absent (critical for Go's exported/unexported distinction). This is the core value-path of Wave 2 and is completely unspecified.

4. **Grammar packaging (both agents).** Both reviewers flag that leaving this as an open question defers a decision that affects reproducibility, air-gapped installs, CI fixture setup, and degradation semantics. It must be resolved in the spec before plan: either a single `tree-sitter-languages` wheel pinned at a specific version, or individual `tree-sitter-python` / `tree-sitter-go` packages at pinned versions, with documented behavior when the package is absent (test skip vs. degraded mode).

5. **Locator abstraction — convention violation (codex).** The spec describes the orchestrator consulting `SymbolEngine` directly when building locate results. The project convention requires Tier engines to be adapted behind the shared Locator protocol, returning common CodeSpan/Citation, so callers never branch on engine type. The spec must state that `SymbolEngine` is internal; the symbol layer is surfaced to the orchestrator only through the shared Locator protocol.

#### P1 — Should resolve before /spec:plan

6. **`symbols_indexed` total-vs-this-run ambiguity (claude-p).** D6 says "number of `symbols.jsonl` records" but does not clarify whether this is the total record count in the artifact or the count of records parsed in the current run. On incremental refresh where most files are unchanged, these diverge. AC3 is ambiguous without an explicit statement that `symbols_indexed` is the total-in-index count.

7. **`(path, start_line)` tie-break collision (claude-p).** D9/AC7 assert byte-identical output ordered by `(path, start_line)`, but this key is not unique when a decorator and its `def` share a start line, or when two symbols are co-located. A secondary sort key (e.g. `end_line`, then `kind`, then `name`) must be documented to make the determinism claim verifiable.

8. **Kind vocabulary gaps (claude-p).** AC2 is ambiguous without ruling on: Python nested functions and `async def` (same kind as `function`, or excluded?); nested classes (is `parent` the enclosing class?); Go pointer-receiver vs. value-receiver normalization (`parent` = `Foo` regardless of `*Foo` vs `Foo`?). The `constant` heuristic should also enumerate excluded forms (annotated assignments, tuple unpacking, augmented assignments) so test authors do not have to guess.

#### P2 — Can be addressed during implementation planning

9. **AC9 missing `Foo.bar` method-addressing test (claude-p).** D10 promises parent-addressability (a method addressable as `Foo.bar`) but no AC exercises it. Add a fixture case.

10. **AC5 testability seam (claude-p).** The no-reparse-on-cache-hit assertion requires a test seam (injectable parser/engine spy). Name the collaborator in the spec so the implementer does not have to infer it.

11. **No-match locate degradation (claude-p).** When a query matches no symbol, the expected behavior (degrade to the exact Wave-1 ripgrep path) is implicit. Assert it as an explicit invariant either in D10 or AC9.

### Action

**Status: reviewed.** The spec may proceed but the following must be resolved in the spec document before `/spec:plan` is invoked:

1. Define parse-error threshold for partial tree-sitter trees (ERROR/MISSING node semantics).
2. Define `symbols.jsonl` corruption/schema-mismatch fallback for the incremental merge path.
3. Define query-to-symbol-name matching (token split rule + case sensitivity).
4. Close Open Question 1: resolve grammar packaging with pinned versions and test-absent behavior.
5. State that `SymbolEngine` is internal; symbol results reach the orchestrator only through the shared Locator protocol returning CodeSpan/Citation — resolves the convention violation.
6. Clarify `symbols_indexed` as total-in-index count.
7. Add secondary sort key(s) to the `(path, start_line)` ordering to guarantee uniqueness.
8. Document kind-vocabulary boundary cases (constant exclusions, async def, nested functions/classes, receiver normalization).

Items 9–11 (Foo.bar AC, parser spy seam, no-match invariant) may be incorporated during plan or implementation at the spec author's discretion.
