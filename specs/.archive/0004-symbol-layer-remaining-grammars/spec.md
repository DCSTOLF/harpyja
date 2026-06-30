---
id: "0004"
title: "Wave 2 follow-up — Symbol layer: remaining grammars (Rust, JS/TS, C#, Java, C/C++)"
status: closed
created: 2026-06-26
authors: [claude]
packages: ["harpyja"]
related-specs: ["0003-wave-2-symbol-layer", "0002-wave-1-deterministic-core"]
---

# Spec 0004 — Wave 2 follow-up — Symbol layer: remaining grammars (Rust, JS/TS, C#, Java, C/C++)

## Why

Spec 0003 shipped the symbol layer end-to-end for **Python and Go only** — a
deliberate two-language proof of the adapter pattern (parse → `symbols.jsonl` →
symbol-aware ranking). It closed with an explicit follow-up on record: the
**remaining five languages** Harpyja claims to support in its own stack
description (Rust, JS/TS, C#, Java, C/C++) are still **unparsed** — a query for a
Rust `fn` or a Java method falls all the way back to ripgrep line hits, the exact
context-flooding Wave 2 exists to prevent. Until they ship, the index advertises a
symbol tier it only delivers for two of seven languages.

This spec closes that gap. It is **purely additive grammar work**: it adds the
remaining tree-sitter grammars and their kind-extraction rules behind the **same
`SymbolEngine`** and the **same `Locator` protocol** 0003 built, reusing —
unchanged — the degradation model (`grammar-missing` / `parse-error`), the
self-verifying `symbols.meta.json` integrity sidecar, per-file `degraded`
persistence, deterministic/atomic artifact writes, exact-only matching, method
addressing, and definition promotion. The adapter was built so adding a grammar is
additive; this spec is the cash-in. No orchestrator, formatter, or contract
behavior changes — only more languages produce records.

Per the user's scope decisions, this spec ships the remaining symbol coverage in
**one spec, tiered by grammar simplicity** so partial delivery stays honest. The
exact accounting (kept precise here because the loose "five languages / six
grammars" shorthand miscounts on every axis): **5 language-family slots** (Rust,
JS/TS, C#, Java, C/C++) → **7 pinned grammar packages** (`tree-sitter-rust`,
`tree-sitter-java`, `tree-sitter-c-sharp`, `tree-sitter-javascript`,
`tree-sitter-typescript`, `tree-sitter-c`, `tree-sitter-cpp`) → **8 grammar entry
points / file-languages** (`rust`, `java`, `csharp`, `javascript`, `typescript`,
`tsx`, `c`, `cpp`; the `tree-sitter-typescript` package alone provides both the
`typescript` and `tsx` grammars). It keeps each language's kind vocabulary **as
minimal and syntactic-form-only as 0003's** and **reuses 0003's `.` / `::`
addressing** rather than adding language-specific separators.

## What

New tree-sitter grammars, their per-language kind-extraction rules, and the
file-extension → language → grammar routing that selects them — all behind the
existing `harpyja_index` / `harpyja_locate` contracts, the existing manifest, and
the existing `symbols.jsonl` + `symbols.meta.json` artifact pair. The symbol record
shape (`path`, `language`, `name`, `kind`, `parent`, `start_line`, `end_line`;
1-indexed inclusive lines) is **unchanged**.

### Tiered delivery (by grammar simplicity)

ACs are grouped into three tiers so partial delivery is honest. A tier is "done"
only when every language in it passes its extraction + degradation ACs.

- **Tier A — single clean grammar each: Rust, Java, C#.** One grammar package per
  language, no JSX/preprocessor complications.
- **Tier B — JS/TS family: JavaScript, TypeScript, TSX.** Multiple grammars and
  JSX node handling under one logical "JS/TS" slot.
- **Tier C — C/C++: C, C++.** Two grammars, preprocessor-driven parse errors, and
  the header-extension ambiguity.

**No-silent-coverage invariant** (▶ **chosen for robustness**, resolves the
no-false-capability concern both reviewers' synthesis ranked P1): a language's
**extension routing, its `engine_identity` slot, and its extraction rules ship in
the same change** — a grammar is never wired into routing/identity ahead of the
rules that give it records. This closes the dangerous middle state where a grammar
package is installed (so routing sends `.rs` to it and `engine_identity` lists it)
but its kind-extraction is unwritten: such a file would parse cleanly, emit **zero
records, and carry no degradation flag** — indistinguishable at the contract from a
genuinely symbol-less file, i.e. a silent "we looked and found nothing" that is
actually "we never looked." That is exactly the false-capability claim the project
forbids. The tiering is therefore a **delivery** ordering, not a routing one: until
a tier ships, its extensions stay **unmapped** (Wave-1 `null`-language /
ripgrep-only, as today) and its grammars are **absent from `engine_identity`** — so
partial delivery degrades **visibly and honestly**, never as silent zero-symbol
coverage.

### Grammar packaging (D17 reused)

Each grammar is pinned as an **individual** package at an explicit version (the
0003 D17 convention — **not** the aggregate `tree-sitter-languages` wheel), added
to `engine_identity`:

- Tier A: `tree-sitter-rust`, `tree-sitter-java`, `tree-sitter-c-sharp`.
- Tier B: `tree-sitter-javascript`, `tree-sitter-typescript` (which provides both
  the `typescript` and `tsx` grammars).
- Tier C: `tree-sitter-c`, `tree-sitter-cpp`.

Each remains air-gap-safe (bundled, no runtime egress). Absent or ABI/load-skewed
grammars degrade via **D4 grammar-unavailable** (`grammar-missing` /
`load-error:<abi-code>` sentinel), never raise — identical to 0003.

### Extension → language → grammar routing (new, load-bearing)

A file's language is selected by extension; each language maps to exactly one
grammar:

- `.rs` → **rust**
- `.java` → **java**
- `.cs` → **csharp**
- `.js`, `.mjs`, `.cjs`, `.jsx` → **javascript** (the JavaScript grammar parses
  JSX)
- `.ts` → **typescript**
- `.tsx` → **tsx**
- `.c` → **c**; `.cc`, `.cpp`, `.cxx`, `.c++` → **cpp**
- Header files: `.hpp`, `.hh`, `.hxx`, `.h++` → **cpp**; **`.h` → c** (▶ **chosen
  for robustness**: `.h` is genuinely ambiguous between C and C++; it is assigned
  to the **C grammar by default** and this limitation is **documented**, not
  hidden). **Scoped guarantee** (resolves the consensus `.h` overclaim, flagged by
  both reviewers): a C++-only construct that the C grammar cannot parse yields an
  `ERROR`/`MISSING` node and degrades via D4 `parse-error` for that file — never a
  crash. We do **not** claim "never a wrong-range record" unconditionally: a C++
  header whose constructs happen to be a **structurally valid subset of C** (e.g. a
  plain `struct` body or a `typedef`) may parse cleanly under the C grammar **with
  no ERROR node** and yield a positionally-correct record under the `c` language.
  The honesty guarantee is therefore: **whenever an `ERROR`/`MISSING` node is
  present the file degrades rather than emitting the affected (possibly-wrong)
  record** (D4); a clean parse of a C-legal subset is accepted as the documented
  cost of the `.h`→C default, not a silent failure.

Extensions with no mapping keep their Wave-1 behavior: `null` language, zero symbol
records, ripgrep-only — exactly as today. **`.mts` / `.cts`** (TypeScript module
variants) are **explicitly out of scope** in this spec — they fall to
`null`-language/ripgrep until a follow-up maps them — called out so the omission is
deliberate, not an oversight.

### Per-language kind vocabulary (minimal, syntactic-form only)

Each language mirrors 0003's philosophy: a **closed, documented** set, classified
**by syntactic form** (no type inference / value resolution), **definitions only**
(imports, references/call sites, prototypes/forward declarations, and
function-local/nested defs are **not** extracted), `parent` = the **immediately
enclosing** type/class name (or `null` for top-level).

- **Rust:** `function` (`fn`, module/top level), `method` (a `fn` inside an `impl`
  block — `parent` = the impl's type name), `struct`, `enum`, `trait`, `type`
  (alias `type X = …`), and module-level `const` / `static`. **Constant kind +
  filter** (▶ resolves review P3): both `const` and `static` items emit the **same
  `kind == "constant"`** (matching the Python/JS `constant` label — one closed
  kind, classified by syntactic form), and — like the Python/JS rule — only a
  **module-level** item whose single declared name matches `^[A-Z][A-Z0-9_]*$` is
  emitted; lower-case `const`/`static` and any inside a `fn` body are excluded.
  **Receiver/impl normalization** (mirrors Go, D3): `impl Foo` and `impl<T> Foo<T>`
  both normalize `parent` to `Foo` (generic parameter list stripped). `impl Trait
  for Foo` methods record `parent == "Foo"` (the implementing type, not the trait).
- **Java:** `class`, `interface`, `enum`, and `method` (`parent` = enclosing
  class/interface/enum). Java has no top-level functions, so every method carries a
  non-null `parent`. Fields and annotation types are **out of scope** (minimal).
- **C#:** `class`, `struct`, `interface`, `enum`, and `method` (`parent` =
  enclosing type). Properties, fields, and `namespace` containers are **out of
  scope** (minimal).
- **JavaScript / TypeScript / TSX:** `function` (function declaration, top level),
  `method` (`parent` = enclosing `class`), `class`, and module-level `constant`
  (▶ same syntactic-form rule as 0003, restated in tree-sitter/JS terms, not Python
  AST terms: a top-level `const` declaration with a **single** `identifier`
  declarator whose name matches `^[A-Z][A-Z0-9_]*$`; array/object destructuring and
  `let`/`var` excluded). A top-level **`export const FOO = …`** is included — the
  `export` modifier wraps the same declaration and does not change the kind.
  **TypeScript/TSX additionally** emit `interface`, `type` (type alias), and `enum`.
  JSX/TSX elements produce **no** records (they are expressions, not definitions).
- **C:** `function` (definition with a body — **prototypes/forward declarations
  excluded**), `struct`, `enum`, `union`, and `type` (`typedef`). File-scope
  variables are **out of scope** (minimal).
- **C++:** `function`, `method` (a member function — `parent` = enclosing/defining
  class; an out-of-line definition `void Foo::bar() {…}` normalizes `parent` to
  `Foo`, mirroring Go/Rust), `class`, `struct`, `enum`, `union`, and `type`
  (`typedef` / `using` alias). `namespace` containers and file-scope variables are
  **out of scope** (minimal); prototypes/forward declarations are **excluded**
  (definitions only).

**Nesting rule — class-in-class** (▶ **chosen for robustness**, resolves review
P2; 0003's "no nested/local defs" was written for Python/Go where class-in-class is
rare, but Java inner classes, C# nested types, and C++ nested records are
idiomatic): a **type defined directly inside another type body** (a nested
`class`/`struct`/`interface`/`enum`) **IS extracted**, with `parent` = the
**immediately enclosing type name** (immediate-only, per D3 — no fully-qualified
dotted path). Its **methods** record `parent` = that **inner** type's name. What
"not extracted" means is held to its 0003 sense: **function-local defs** — anything
nested inside a **function/method body** (a local class, a closure, a local `fn`) —
is **not** extracted. So "method `parent` = enclosing type" and "no nested defs"
are consistent: the enclosing type is always a real, extracted type record because
type-in-type nesting is in scope, while only body-local defs are dropped. Because
`parent` is immediate-only and `namespace`/outer-qualification is out of scope, two
same-named inner types in different outer types (or namespaces) both record the
same `parent` — an accepted, documented addressing ambiguity, not a bug.

**`typedef struct` idiom (C/C++)**: `typedef struct {…} Foo;` (anonymous struct)
emits a **single `type` record** named `Foo`; `typedef struct Foo {…} Foo;` (named
struct + alias of the same name) emits **both** a `struct` record and a `type`
record for `Foo` (one per syntactic definition — we classify by form, not by
de-duplicating names). Pinned by fixtures.

### Reused unchanged from 0003 (asserted, not re-designed)

- **`SymbolEngine` behind the `Locator` protocol** (D16) — new languages are new
  grammar+rule entries inside the engine; the orchestrator still never branches on
  "is there a symbol engine?" and the Citation Formatter applies the same
  definition boost over the unified `CodeSpan` stream.
- **Degradation** (D4) — `grammar-missing` (zero records, ripgrep unaffected) vs
  `parse-error` (skip only the error-spanned definition's **own region excluding
  nested-definition subtrees**; flag the file on **any** `ERROR`/`MISSING` node),
  the two causes distinguishable per language/file.
- **Integrity + rebuild** (D15) — the `symbols.jsonl` + `symbols.meta.json` pair,
  `record_count` + `sha256` `content_digest`, records-first/meta-last commit via
  `os.replace`, and **rebuild keyed on full `engine_identity`** (now enumerating
  every shipped grammar, each with a `"missing"` / `"load-error:<abi>"` sentinel
  when absent/unloadable). Bumping or installing any new grammar invalidates the
  cache and triggers the rebuild that also clears stale `grammar-missing` flags
  (D15/AC8e).
- **Per-file `degraded` persisted on the manifest** (D18), **incremental re-parse**
  gated by `(mtime, size)` + `hash` with `--rehash` override (D7), **symbol
  pruning** (D8), **deterministic + atomic** writes ordered by
  `(path, start_line, end_line, kind, name)` (D9), `symbols_indexed` and `degraded`
  **total-in-index** (D6/D18).
- **Matching + locate** — exact, case-sensitive identifier-token matching (D10a);
  **method addressing reusing only `.` and `::`** (D10c) — applied uniformly to all
  new languages (Rust `Foo::bar`, C++ `Foo::bar`, Java/C#/JS/TS `Foo.bar`); no
  `->` or other separators; definition promotion (D10); **no-match degrades to the
  Wave-1 ripgrep-only path exactly** (D10b); determinism and placeholder boost
  weights (D11/D12). `mode` / `language_hint` / `max_results` contract unchanged
  (D14).
- **Air-gap** — parsing stays fully local; `gateway.assert_local` and the Wave-0
  inbound-bind defaults are untouched.

## Acceptance criteria

**Tier A — Rust, Java, C#**

1. **Rust extraction:** a Rust fixture yields `function`, `method`, `struct`,
   `enum`, `trait`, `type`, and module-level `const`/`static`. A `const`/`static`
   emits `kind == "constant"` and is recorded **only** for an `UPPER_SNAKE`
   (`^[A-Z][A-Z0-9_]*$`) module-level name — a lower-case or function-local
   `const`/`static` yields **no** record. An `impl Foo` and an `impl<T> Foo<T>` both
   record method `parent == "Foo"` (generic params stripped); an `impl Trait for
   Foo` method records `parent == "Foo"`. Imports (`use`), call sites, and
   function-local `fn`s yield **no** records. Ranges are 1-indexed inclusive and fed
   to `harpyja_read` return the definition.
2. **Java extraction + nesting:** a Java fixture yields `class`, `interface`,
   `enum`, and `method`, with each method's `parent` set to its enclosing type.
   Top-level types have `parent == null`; methods never do. A **nested (inner)
   class** is itself extracted with `parent` = its immediately enclosing type, and a
   method of that inner class records `parent` = the **inner** type's name (nesting
   rule). A class defined inside a **method body** (function-local) is **not**
   extracted. Fields, import statements, and call sites yield **no** records.
3. **C# extraction:** a C# fixture yields `class`, `struct`, `interface`, `enum`,
   and `method` (`parent` = enclosing type). Properties, fields, `using`
   directives, and `namespace` containers yield **no** records.

**Tier B — JavaScript, TypeScript, TSX**

4. **JS/TS extraction:** a `.js` fixture yields `function`, `method` (`parent` =
   class), `class`, and module-level `constant` (single `UPPER_SNAKE` `const`
   declarator only — `let`/`var`, destructuring, and reassignment excluded), and a
   top-level `export const FOO = …` **is** included (the `export` wrapper does not
   change the kind); a `.ts` fixture additionally yields `interface`, `type`, and
   `enum`. Imports, call sites, and nested/inner functions yield **no** records.
5. **TSX/JSX handled:** a `.tsx` fixture parses via the `tsx` grammar and a `.jsx`
   file via the `javascript` grammar; JSX elements produce **no** records while the
   surrounding `function`/`class`/`const` definitions are extracted normally. The
   `.js`/`.mjs`/`.cjs`/`.jsx` → javascript, `.ts` → typescript, `.tsx` → tsx
   routing is asserted.

**Tier C — C, C++**

6. **C extraction:** a `.c` fixture yields `function` (definition with a body —
   **a bare prototype/forward declaration yields no record**), `struct`, `enum`,
   `union`, and `type` (`typedef`). The `typedef struct` idiom is pinned:
   `typedef struct {…} Foo;` → a single `type` record `Foo`; `typedef struct Foo
   {…} Foo;` → **both** a `struct` and a `type` record for `Foo`. A `.h` file is
   parsed with the **C** grammar.
7. **C++ extraction + nesting:** a `.cpp` fixture yields `function`, `method`,
   `class`, `struct`, `enum`, `union`, and `type` (`typedef`/`using`); an
   out-of-line member definition `void Foo::bar() {…}` records `method` with
   `parent == "Foo"`. A **nested type** (struct/class inside a class) is extracted
   with `parent` = the enclosing type, and its methods record the inner type as
   `parent` (nesting rule). `.cc`/`.cpp`/`.cxx` → cpp and `.hpp`/`.hh`/`.hxx` → cpp
   routing is asserted; prototypes/forward declarations and `namespace` containers
   yield **no** records.

**Cross-cutting (all tiers)**

8. **Extension routing + `.h` ambiguity (scoped guarantee):** every extension above
   maps to the stated grammar; unmapped extensions (including `.mts`/`.cts`) keep
   Wave-1 `null`-language/ripgrep-only behavior. A `.h` file containing a C++
   construct the C grammar **cannot parse** yields an `ERROR`/`MISSING` node and
   degrades to `parse-error` (D4) — **never a crash**, and the error-spanned
   definition is not emitted (no wrong-range record for *that* def). The test uses
   syntax that **reliably** triggers a C-grammar `ERROR` (e.g. `class Foo { … };`),
   not syntax the C grammar tolerates. The spec does **not** claim a C-legal subset
   of a C++ header (a plain `struct`/`typedef`) is rejected — that parses cleanly as
   `c` and is the documented cost of the default (see What §routing).
9. **Degradation per new grammar (D4/D17 reused):** for **each** new grammar, (a)
   an absent package → every file of that language gets **zero** records and is
   flagged `grammar-missing` (ripgrep unaffected); (b) an ABI/load-skew failure →
   same grammar-unavailable path with a `load-error:<abi-code>` `engine_identity`
   sentinel; (c) a file with `ERROR`/`MISSING` nodes → only the error-spanned
   definition's own region is skipped (nested-def subtrees excluded), clean
   siblings still emitted, file flagged `parse-error`. Tests cover absent-package
   and load-failure for the new grammars and at least one parse-error fixture per
   tier (including a C/C++ preprocessor-mangled file). **Coupling note:** the
   `typescript` and `tsx` grammars ship in the **same** package
   (`tree-sitter-typescript`), so they cannot be independently absent or
   version-bumped — the absent-package case for that slot necessarily degrades
   **both** `typescript` and `tsx` together; the tests assert the coupled behavior
   rather than an unsatisfiable independent-absence expectation. The
   **grammar-loader is an injectable seam** (per conventions) so absent-package and
   `load-error:<abi>` states are simulated by injecting a stub loader, never by
   mutating the installed environment.
10. **`engine_identity` enumerates all shipped grammars:** the
    `symbols.meta.json` `engine_identity` includes the tree-sitter runtime plus a
    version (or `"missing"` / `"load-error:<abi>"` sentinel) for **every** grammar
    shipped through Wave 2 — Python, Go, Rust, Java, C#, JavaScript, TypeScript,
    TSX, C, C++. A **grammar-only version bump** of any one of them (with
    `schema_version` and `(mtime, size)` unchanged) forces the D15 full rebuild;
    installing a previously-absent new grammar flips its sentinel to a real version,
    fires the rebuild, re-parses the now-parseable files, and **clears their stale
    `grammar-missing` flags** (D18). Both are tested. (Per the AC9 coupling note,
    `typescript` and `tsx` share a package version, so a bump of one is a bump of
    both — the identity carries two slots but they move together.)
11. **Method addressing reuses `.` and `::` only (D10c):** `harpyja_locate` for
    `Foo::bar` (Rust/C++) and `Foo.bar` (Java/C#/JS/TS) promotes method `bar` with
    `parent == "Foo"` above raw line hits; `Foo bar` (whitespace) and any other
    separator (e.g. C++ `->`) do **not** form a method address. Still Tier 0,
    `tiers_run == [0]`, **zero model calls**. Because `parent` is immediate-only and
    namespaces/outer types are out of scope, two same-named members under different
    outer types (e.g. two `Foo` in different namespaces) **both** match `Foo::bar` —
    asserted as an accepted, documented addressing ambiguity, not a regression.
12. **Definition promotion across new languages (D10/D10a):** a name query for a
    symbol in any new language returns its **definition** citation, exact and
    case-sensitive (`Parse` ≠ `parse`, ≠ `ParseConfig`, ≠ `reParse`), ranked above
    raw ripgrep line hits for the same token; results bounded by the configured
    limits.
13. **No-match + determinism preserved (D10b/D9/D11):** a query matching no symbol
    name and no method address returns the **identical** Wave-1 ripgrep-only
    citations and ordering; two indexes of an unchanged mixed-language tree produce
    **byte-identical** `symbols.jsonl` and `symbols.meta.json` (records ordered by
    `(path, start_line, end_line, kind, name)`, sidecar with fixed key order +
    stable-sorted `languages`).
14. **Totals + persistence still hold (D6/D18):** `symbols_indexed` is the total
    record count across **all** indexed languages after a refresh (not parsed-this-
    run); an incremental refresh that re-parses nothing still returns the full
    `symbols_indexed` and the full, accurate `degraded` array for the new languages;
    pruning a deleted file removes its records and its persisted `degraded` flag.
15. **Locate/orchestrator/contract unchanged:** no new branching on language in the
    orchestrator or formatter; `language_hint` filters new languages by manifest
    language; `mode` stays accept-validate-flag; `max_results` stays a mandatory
    clamp; the `notes` string remains honest about the Tier-0 symbol-aware tier.
16. **Air-gap preserved:** all new grammars parse fully locally; no runtime network
    egress is introduced; `gateway.assert_local` and the Wave-0 inbound-bind
    defaults are untouched (test/audit confirms no new outbound calls in the
    index/locate path).

## Out of scope

- **Richer per-language kinds** — fields/properties (Java/C#), Rust enum variants,
  C# `namespace`/C++ `namespace` containers, Java annotation types, file-scope
  variables (C/C++), and any member kind beyond the minimal sets above. Mirrors
  0003's defs-only philosophy; deferred if ever wanted.
- **Language-specific addressing separators** — C++ `->`, Rust turbofish, or any
  separator beyond `.` / `::`. Reuses 0003 addressing exactly (user decision).
- **Substring / fuzzy symbol matching** — still the Wave-2.1 follow-up; matching
  remains exact, case-sensitive (D10a), language-agnostic.
- **C/C++ preprocessor evaluation** — macros are **not** expanded; a macro-mangled
  region that fails to parse degrades via `parse-error` (D4). No `#include`
  resolution, no conditional-compilation evaluation.
- **Declaration/definition reconciliation (C/C++)** — a function declared in a `.h`
  and defined in a `.c`/`.cpp` produces a record only for the **definition**; the
  two are not linked, and prototypes are not indexed.
- **Imports, references, call graphs, signatures/docstrings, nested/local defs** —
  unchanged from 0003 out-of-scope; this spec adds grammars only.
- **Higher tiers / real `mode` routing / regex search** — Scout, Deep, the
  verification gate/classifier, and validated regex remain deferred.

## Open questions

_none open._ Scoping decisions (tiered-by-simplicity rollout, minimal kind
vocabularies, `.`/`::` addressing reuse, all three JS/TS grammars) were resolved
with the user at spec creation, and the architecture is inherited intact from the
closed spec 0003.

**Resolved in cross-review (round 1 — both reviewers approve-with-comments,
quorum met; see `review.md`):**

- **No-silent-coverage invariant** (P1, no-false-capability guardrail): a language's
  routing + `engine_identity` slot + extraction rules ship in the **same** change;
  an unshipped tier stays unmapped (ripgrep-only), never silently zero-symbol
  (What §tiered delivery).
- **Class-in-class nesting** (P2): nested **types** are extracted with immediate
  `parent`; only **function/method-body-local** defs are dropped — so "method
  `parent` = enclosing type" and "no nested defs" are consistent for Java/C#/C++
  (What §nesting rule; AC2/AC7).
- **Rust `const`/`static`** (P3): emit `kind == "constant"`, `UPPER_SNAKE`-filtered
  like Python/JS (What §Rust; AC1).
- **`.h`→C guarantee scoped**: degrade on `ERROR`/`MISSING` only; a C-legal subset
  parsing cleanly as `c` is the documented cost, not a silent failure (consensus
  fix — What §routing; AC8).
- **Numeric precision**: 5 language slots / 7 packages / 8 grammars (consensus fix —
  What).
- Clarifications folded in: `export const` included (AC4); `tsx`/`typescript`
  package coupling for AC9/AC10; injectable grammar-loader seam (AC9); `.mts`/`.cts`
  out of scope (What §routing; AC8); `typedef struct` idiom (AC6); cross-namespace
  `parent` collision accepted as known ambiguity (AC11); JS/TS `constant` reworded
  in tree-sitter terms (What §JS/TS).
