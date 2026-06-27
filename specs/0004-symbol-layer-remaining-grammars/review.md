---
spec: "0004"
title: "Wave 2 follow-up — Symbol layer: remaining grammars (Rust, JS/TS, C#, Java, C/C++)"
reviewers:
  - name: codex
    model: gpt-5.5
    verdict: approve-with-comments
  - name: claude-p
    model: claude (default)
    verdict: approve-with-comments
quorum: 1 (met)
verdict: approve-with-comments
guardrail_violations: none
convention_violations: none
generated: 2026-06-26
---

# Cross-model review — 0004

## codex (gpt-5.5)

**Verdict:** approve-with-comments

Concerns:
- AC9's absent-package and ABI/load-failure coverage becomes brittle without explicit dependency-injection seams for grammar loading; simulating missing packages in tests needs a hook or abstraction.
- The `.h` → C degradation claim ("never a wrong-range record") is stronger than the C grammar guarantees; the fixture must choose syntax that tree-sitter-c actually marks ERROR/MISSING, not syntax it silently tolerates or misclassifies.
- The spec alternates between "remaining five languages", "all six grammars", and a package list covering more grammar entry points — imprecise for implementation and acceptance tracking.
- JS/TS `constant` extraction reuses Python's `Name` wording, but JS/TS tree-sitter nodes do not use Python AST terminology; the kind description should be restated in tree-sitter/identifier terms.

Suggestions:
- Define a grammar-loader abstraction or test hook so missing-package and load-skew cases can be simulated without modifying the installed environment.
- Make tier accounting explicit: language slots, file-extension languages, package names, and grammar entry points listed separately.
- Add representative fixtures: Rust trait impls, TS type aliases, TSX components, C++ out-of-line definitions, and `.h` C++ syntax that reliably triggers parser errors.
- Clarify whether top-level JS/TS exported constants (`export const FOO = 1`) are included.

## claude-p (claude default)

**Verdict:** approve-with-comments

Concerns:
- Numeric inconsistency: "all six grammars" matches no actual count. The spec adds 7 grammar packages (rust, java, c-sharp, javascript, typescript, c, cpp) providing 8 grammar entry points (rust, java, csharp, javascript, typescript, tsx, c, cpp) across 5 language-family slots. "Six" is wrong regardless of which axis is counted.
- False-capability risk on partial-tier delivery: the routing map adds `.rs` → rust unconditionally, and the grammar package enters `engine_identity`. If a tier's extraction rules are not yet written but the grammar package is installed, those files parse successfully and emit zero records without any `grammar-missing` or `parse-error` flag — indistinguishable from a genuinely symbol-less file. This is a silent no-op and violates the no-false-capability-claims guardrail. The tiered-delivery section needs an explicit invariant: a grammar enters routing and `engine_identity` only when its extraction rules ship, OR an unshipped language must degrade visibly.
- Nested-definition semantics are underspecified for class-nesting languages. The inherited 0003 rule ("function-local/nested defs not extracted") was written for Python/Go. Java, C#, and C++ have meaningful class-in-class nesting. AC2, AC3, and AC7 assert method `parent` == enclosing type but never state whether a class nested inside a class is itself extracted (with its own parent) or skipped, and never state how a method inside a nested class is addressed.
- Rust `const`/`static` is underspecified twice: (a) no `kind` string is given — is the kind `"const"`, `"static"`, or `"constant"`? — and (b) unlike JS/Python's `^[A-Z][A-Z0-9_]*$` name filter, no equivalent filter is stated, so it is unclear whether every module-level const/static is extracted or only UPPER_SNAKE-named ones.
- The `.h` → C "never a wrong-range record" claim is stronger than the C grammar guarantees. Some C++ constructs in a `.h` produce a clean ERROR node (e.g. `class Foo {`), but others parse as valid C with a different meaning (e.g. a typedef or struct body) without any ERROR/MISSING node, yielding a plausible but semantically incorrect record. The guarantee should be scoped to "when an ERROR/MISSING node is present."
- "Open questions: none" is incorrect. Rust const kind/filter and nested-class semantics are genuine open items that should be pinned before /plan.

Suggestions:
- State `typedef struct {...} Foo;` vs `typedef struct Foo {...} Foo;` behavior in a fixture: one `type` record, a struct+type pair, or a dedup rule.
- Map `.mts`/`.cts` (TypeScript module variants) explicitly or list them as out-of-scope; currently they silently fall to null-language/ripgrep-only behavior, unmentioned.
- Note that `tsx` cannot be independently absent or version-bumped from `typescript` (same package). AC9's per-grammar absent-package test and AC10's grammar-only bump test are coupled for these two and should call that out.
- Soften "Open questions: none" — pin Rust const kind/filter and nested-class semantics before /plan.
- Add an AC asserting that cross-namespace `parent` collisions (two `Foo` types in different namespaces both producing `parent == "Foo"`) are accepted as a known addressing ambiguity.

---

## Synthesis

### Consensus — concerns flagged by both reviewers

Both reviewers independently flagged the same two issues:

1. **Numeric inconsistency ("six grammars").** The spec uses "all six grammars" in the What section and "remaining five languages" in Why, but neither count is accurate. There are 7 grammar packages, 8 grammar entry points, and 5 language-family slots. The word "six" matches none of these and should be removed or replaced with language-specific precision (e.g. "the five remaining language families" in prose, and an explicit table or list in the grammar-packaging section that separately names language slots, packages, and grammar entry points).

2. **`.h` overclaim.** The claim "never a wrong-range record" when a `.h` is parsed as C is stronger than tree-sitter-c actually guarantees. Some C++ constructs produce a clean ERROR node and properly degrade; others parse as structurally valid C (different semantics) without ERROR/MISSING, producing a record that is positionally correct but semantically wrong. The guarantee should be narrowed to: "when tree-sitter emits an ERROR/MISSING node, the file degrades via D4; otherwise, records emitted by the C grammar for C++ constructs that parse without error are not guaranteed to be semantically meaningful." The fixture must use C++ syntax that reliably produces an ERROR node in the C grammar, not syntax the C grammar tolerates.

### Prioritized concerns to address before /plan

**P1 — False-capability partial-tier invariant (no-false-capability-claims guardrail).**
This is the highest-priority item. The tiered delivery section does not state what happens between tiers during implementation: specifically, if `tree-sitter-rust` is installed and `.rs` → rust routing is registered but Rust extraction rules have not shipped yet, files produce zero records with no warning flag — indistinguishable from a genuinely symbol-less file. The spec must add an explicit invariant, for example: "A language's extension routing and `engine_identity` entry are added in the same commit as its extraction rules. Until extraction rules ship, the grammar package is not added to routing, `engine_identity`, or AC9/AC10 coverage. A partially-implemented language that is routing-registered but rule-empty must emit a `grammar-missing`-equivalent degradation flag per file rather than silent zero records." This is not about the finished product; it is about what honest partial delivery looks like during implementation of each tier.

**P2 — Nested-class semantics for Java, C#, C++ (design gap).**
AC2, AC3, and AC7 define `parent` as the immediately-enclosing type for methods, but never state the rule for types-nested-inside-types. The inherited "no nested/local defs" rule from 0003 was written for Python/Go where meaningful nesting is rare. Java, C#, and C++ have idiomatic nested classes (Java inner classes, C++ nested structs, C# nested types). The spec must state one of: (a) nested types are extracted with `parent` = enclosing type name (and methods inside them chain through the inner type); (b) nested types and their members are not extracted (consistent with the minimal-extraction philosophy, but must be stated explicitly). Either answer closes the gap; the gap is that currently the answer is unspecified.

**P3 — Rust const/static kind string and name filter.**
AC1 refers to "module-level `const`/`static`" extraction but does not state the `kind` value emitted in the record. Every other language's vocabulary gives an explicit kind string (`"function"`, `"method"`, `"type"`, etc.). For Rust constants, the spec must state: is the kind `"const"`, `"static"`, or `"constant"` (matching JS/TS)? Are both `const` and `static` extracted under a single kind, or do they emit different kinds? Additionally, the JS/TS constant rule carries an explicit name filter (`^[A-Z][A-Z0-9_]*$`); Rust's entry has no filter stated. Clarify whether every module-level `const`/`static` is extracted or only UPPER_SNAKE-named ones (and if so, state the filter explicitly in the vocabulary table).

**P4 — "Open questions: none" should be corrected.**
P2 and P3 above are genuine open items. The section should be updated to list them as pinned-before-/plan items rather than claiming no open questions exist.

### Clarifications and nice-to-have

These are lower-priority refinements that improve implementation clarity but are not design gaps:

- **tsx/typescript package coupling:** Note explicitly that `tsx` and `typescript` grammars ship in the same `tree-sitter-typescript` package. AC9's per-grammar absent-package test and AC10's grammar-only version-bump test are physically coupled for these two; a test note should acknowledge this rather than implying they can be independently varied.
- **Grammar-loader test seam:** AC9 requires per-grammar absent-package and ABI-failure tests. Document the test mechanism (mock/stub, environment variable, fake-package path injection) so the AC is implementable without modifying the installed environment.
- **`.mts`/`.cts` extensions:** These TypeScript module-variant extensions are unmentioned. Either add them to the `.ts` → typescript routing row or call them out explicitly in Out of Scope so they are not a silent gap.
- **`export const FOO = 1` in JS/TS:** Clarify whether a top-level exported constant (`export const FOO = ...`) passes the same name filter as a non-exported one. The current rule does not mention the `export` modifier.
- **`typedef struct` in C:** Clarify the record output for `typedef struct { ... } Foo;` vs `typedef struct Foo { ... } Foo;` — one `type` record, a `struct`+`type` pair, or a dedup rule. A fixture example resolves this unambiguously.
- **JS/TS constant wording:** The vocabulary entry for JS/TS `constant` borrows Python's `Name` node terminology, which does not exist in tree-sitter-javascript/typescript. Restate as "a single identifier target" or in tree-sitter node-type terms.
- **Cross-namespace parent collisions:** Consider adding an AC or a note asserting that two types named `Foo` in different namespaces both producing `parent == "Foo"` is a known, accepted addressing ambiguity — consistent with the exact-only, no-namespace-awareness design choice already in 0003.

---

## Action

**Verdict: approve-with-comments. Proceed to /plan after folding the following into spec.md. This is a one-pass clarification, not a re-review trigger.**

Required before /plan (non-blocking to the overall design, but must be pinned to avoid implementation ambiguity):

1. Fix the numeric inconsistency: replace "all six grammars" with precise language throughout, and optionally add a small table in the grammar-packaging section that lists language slots, packages, and grammar entry points separately.
2. Add an explicit partial-tier delivery invariant covering the false-capability / silent-zero-records risk (P1 above).
3. State the nested-type extraction rule for Java, C#, and C++ — extracted with parent, or out of scope — in the per-language kind vocabulary section (P2 above).
4. Pin Rust `const`/`static` kind string(s) and name filter in the kind vocabulary table, and update "Open questions: none" accordingly (P3/P4 above).
5. Narrow the `.h` correctness guarantee from "never a wrong-range record" to "degrades via D4 when ERROR/MISSING nodes are present; the fixture uses C++ syntax that reliably triggers an ERROR node in the C grammar."

Recommended (no /plan blocker, fold in while editing):
- Note tsx/typescript package coupling in AC9/AC10.
- Clarify `export const` handling in the JS/TS constant rule.
- Note `.mts`/`.cts` as explicitly out-of-scope extensions.
- Add a test-seam note to AC9 so the absent-package/load-failure test strategy is not left to the implementer to invent.
