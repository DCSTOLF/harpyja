---
spec: "0003-wave-2-symbol-layer"
title: "Wave 2 — Symbol layer (tree-sitter, Python + Go)"
revision: 2
round: 3
date: 2026-06-26
reviewers: [codex, claude-p]
verdicts: [changes-requested, changes-requested]
quorum: 1 approve-or-approve-with-comments
quorum-met: false
status: draft
generated: 2026-06-26T14:00:00Z
---

# Cross-model review — 0003-wave-2-symbol-layer (revision 2, round 3)

## codex

**Verdict:** changes-requested

**Guardrail violation:** Rule "Graceful degradation / never return an unverified confident citation" — Location: D15 / AC8.

**Convention violation:** Rule "Derived artifacts must be byte-reproducible and correct under atomic recovery assumptions" — Location: D15.

Concerns:

- D15 still has a silent partial-cache hole. A `symbols.jsonl` that is truncated cleanly AT a newline boundary remains valid JSONL and passes every stated read-path check (missing/unreadable, per-line JSON parse, engine-identity). Yet AC8 claims the result is "always correct and complete." External corruption, manual truncation, or a non-atomic mutation outside the write path can produce this state; the spec treats the artifact as untrusted on read, so these are in scope.

Suggestions:

- Add a completeness check to `symbols.meta.json`: record `record_count` PLUS a stable content digest of `symbols.jsonl`, and require a full rebuild when either mismatches. This makes AC8's "always correct and complete" claim actually true. (Alternatively, narrow AC8 to exclude the valid-line-truncation case, but that weakens the design.)

---

## claude-p

**Verdict:** changes-requested

Concerns:

- **Logical contradiction in D15/AC8 crash detection.** With records-first / meta-last write ordering, a crash after `symbols.jsonl` is renamed but before `symbols.meta.json` is written leaves FRESH records + OLD meta. None of the three enumerated rebuild triggers fire: records parse fine (not trigger a), meta is present (not trigger b), and engine_identity matches because the engine did not change (not trigger c). A faithful implementation will NOT rebuild, directly contradicting AC8's claim that this state is "treated as inconsistent → rebuild (never read as valid)." The meta carries no record-derived fingerprint to bind it to a specific records generation.

- **AC8 mischaracterizes the records-first crash residue.** Because records are renamed FIRST, the post-crash records are the fresh/correct ones; a stale-but-engine-matching meta is benign — its only record-derived field (`languages`) is re-derivable. Reading those records as valid is the CORRECT outcome. The genuinely dangerous ordering (meta first over stale records) is correctly forbidden. The spec over-claims that a records-first crash requires a rebuild it has no trigger for and does not actually need — the real fix is a fingerprint that makes stale meta detectable.

- **Nested-definition error-spanning under-specified for the in-scope class+method case.** D4 states "a definition node whose subtree contains an ERROR/MISSING node is skipped." For a class with method A (clean) + method B (broken), the `class_definition` subtree contains B's ERROR, so by the literal rule the CLASS is also skipped — yielding an orphan method-A record (`parent='ClassName'`) with no class record, even though the class header parsed cleanly. AC4 tests only flat function siblings, so this case is untested. The rule should evaluate error-spanning per definition over its OWN region, excluding nested-definition subtrees.

- **Incremental `degraded` staleness — same hole D6 fixed for `symbols_indexed`.** On an incremental refresh a parse-error or grammar-missing file that passes the `(mtime, size)` gate reuses records WITHOUT re-parsing (D7). Its `degraded` status is never re-derived. Nothing in the spec says `degraded` is persisted with the cached records or recomputed for unchanged files, so an incremental run could return `degraded:[]` for a still-partially-parsed file. This violates "partialness never silent" and the project's no-false-capability rule.

Suggestions:

- Pick ONE crash-detection mechanism and state it: (a) record a count/hash of `symbols.jsonl` inside the meta so fresh-records/stale-meta is detectable; (b) delete the old meta BEFORE renaming records so any crash leaves a missing meta (trigger b fires); or (c) accept that records-first crash residue is benign and SOFTEN AC8 to test only engine-change and first-write crash paths. Option (a) is the most robust and is compatible with the codex completeness fix.

- Specify the source of meta's `languages` array — distinct languages with at least one record vs all languages encountered (including grammar-missing zero-symbol files). This affects AC7 byte-reproducibility and the AC8 inconsistency check.

- Spell out how D10a's identifier tokenizer (splits on `./:`) coexists with D10c's adjacent-`.`/`::`-pair detection — whether this requires a separator-preserving tokenizer or a separate pre-split pass. Define "query segment" precisely.

---

## Synthesis

### Quorum and overall verdict

Both agents returned changes-requested. Quorum (1 approve or approve-with-comments) is NOT met. Status remains **draft**.

### Confirmed sound in revision 2

The following items were verified by both reviewers as genuinely closed; they should not be re-opened in the next revision.

- **Exact-only matching + Wave-2.1 deferral (D10a / Out of scope):** substring/partial matching correctly deferred; no-match invariant is now a clean binary. Round-1 guardrail violation closed.
- **Engine_identity cache keying (D15):** rebuild now keys on runtime + each grammar version; schema_version-only staleness hole from round 1 closed.
- **Byte-reproducible sidecar (D15 / AC7):** fixed key order + stable-sorted `languages` array specified; round-1 convention violation closed.
- **Grammar-missing vs parse-error split (D4 / AC4 i–iii):** two causes are now distinguishable; D4 wording corrected; any ERROR/MISSING node flags the file. Round-1 wording concern closed.
- **Generic-receiver stripping (D3):** pointer AND type-parameter list stripped for `(s *Stack[T])`. Round-1 gap closed.
- **ABI / load-skew routing (D17 / AC15):** grammar load failure routes through D4 grammar-unavailable rather than raising. Round-1 gap closed.
- **Locator-protocol composition (D16 / AC9):** SymbolEngine behind shared protocol; orchestrator never branches. Round-0 convention violation closed.
- **Records-first, meta-last write order:** the ordering is correctly stated. The issue is not the ordering itself but that the stated recovery trigger does not match the ordering — see P0 below.

### Blocking issues (third consecutive round — D15 is the persistent problem area)

This is the third round in which the D15 corruption-recovery area drives a changes-requested verdict. The root cause is the same each time: AC8 makes a correctness claim ("always correct and complete / crash → rebuild") that the enumerated rebuild triggers cannot satisfy. This pass must close it definitively.

#### P0 — D15 completeness and crash-detection gap (BOTH agents; codex: guardrail + convention violation)

Two independently derived concerns from two different angles converge on the same structural fix.

**Codex angle (completeness):** A `symbols.jsonl` truncated at a clean newline boundary passes all three stated read-path checks yet may be missing records. AC8's "always correct and complete" is false.

**claude-p angle (crash detection):** With records-first / meta-last write ordering, a crash between the two renames leaves fresh records + old meta. Engine_identity matches (the engine did not change), so trigger c does not fire, meta is present so trigger b does not fire, and records are valid JSON so trigger a does not fire. AC8's "treated as inconsistent → rebuild" is false for this exact state.

**Recommended fix (both reviewers point at the same mechanism):** Add `record_count` and a deterministic content digest of `symbols.jsonl` to `symbols.meta.json`. Require a full rebuild when either field mismatches. This single addition makes AC8 true as written: a truncated file changes the digest (closes codex's hole) and a stale meta from before the last records rename has a wrong count+digest (closes claude-p's hole). Update AC8 to enumerate a test for this: records renamed, process killed before meta written, next refresh must rebuild.

Alternative paths (noted by claude-p): deleting old meta before renaming records (trigger b always fires on crash) or softening AC8 to acknowledge records-first residue is benign. The fingerprint option is preferred because it also closes the corruption-by-external-edit case that the ordering trick cannot address.

Note: claude-p's secondary observation that reading post-crash records-first residue as valid is technically CORRECT (the records ARE fresh) is accurate but does not remove the need for a fingerprint — the fingerprint is what makes any stale-meta state safely detectable without relying on distinguishing "crash after first rename" from "crash after second rename."

#### P1 — Nested-definition error-spanning rule incomplete (claude-p)

D4's rule "a definition node whose subtree contains an ERROR/MISSING node is skipped" is evaluated on the full subtree, which includes nested definitions. A class with one clean method and one broken method has ERROR in the class subtree, so the class is skipped under the literal rule — producing an orphan method record with no parent class record. AC4 does not cover this case (only flat function siblings are tested).

**Fix:** Scope error-spanning evaluation to a definition's OWN syntactic region, excluding the subtrees of any nested definitions it contains. A class is skipped only when its own header or non-method body is error-spanned; a broken nested method causes only that method's record to be skipped. Add AC4 case (iv): a class with one clean method and one broken method must yield a class record and the clean method's record, with the broken method absent and the file flagged `parse-error`.

#### P1 — Incremental `degraded` staleness (claude-p)

D7 reuses prior symbol records for files that pass the `(mtime, size)` gate. D6 solved the analogous problem for `symbols_indexed` by defining it as total-in-index. But `degraded` has no equivalent fix: if a parse-error file passes the gate, its cached records are reused and its `degraded` status is never re-derived. Nothing in the spec says `degraded` is persisted alongside the cached records or recomputed from persisted state on the no-reparse path. An incremental run can return `degraded:[]` for a still-partially-parsed file — a false capability claim.

**Fix:** Persist per-file `degraded` status (cause + language/path) alongside the cached symbol records in the artifact. On the no-reparse incremental path, read back the persisted per-file status and include it in the reported `degraded` total, the same way `symbols_indexed` reads the total-in-index count from the artifact. Add an AC asserting that an incremental refresh of an unchanged parse-error file still reports that file in `degraded`.

### P2 — Clarifications required (claude-p)

These are not individually blocking but should be resolved in the same revision pass to avoid a fourth round.

- **Meta `languages` source:** specify whether the `languages` array in `symbols.meta.json` contains distinct languages with at least one record, or all languages encountered including grammar-missing zero-symbol files. This affects AC7 byte-reproducibility and the AC8 inconsistency check and currently has no stated answer.

- **Query segment and tokenizer definition for D10a/D10c:** D10a splits on `[^A-Za-z0-9_]` (which includes `.` and `/` and `:`), and D10c matches adjacent `.`/`::` pairs. The interaction is unspecified: does the tokenizer preserve separators for a subsequent adjacency pass, or is there a separate pre-split step? Define "query segment" and state whether the tokenizer is separator-preserving, so D10c's adjacency rule is unambiguously implementable.

## Action

**Status stays `draft`.** Run `/speccraft:spec:revise` to address the P0 fingerprint (record_count + content digest in `symbols.meta.json`, rebuild on mismatch, AC8 updated), both P1s (nested-def error-spanning scoped to own region + AC4 case iv; per-file `degraded` persisted and re-surfaced on no-reparse path + AC), and fold in the P2 clarifications (languages source, query segment + tokenizer spec). Then submit for a fourth review round.

This is the third consecutive round the D15 corruption-recovery area has driven changes. The recommended fix — a content fingerprint in the sidecar — is the same fix both reviewers arrive at independently. It must be resolved completely this pass: the spec cannot advance while AC8's correctness claim is unsatisfiable by the stated triggers.
