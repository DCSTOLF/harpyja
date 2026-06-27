---
spec: "0004"
closed: 2026-06-26
---

# Changelog — 0004 Wave 2 follow-up — Symbol layer: remaining grammars

## What shipped vs spec

- All 36 tasks done; 320 tests pass; ruff clean. **Zero deviations from the
  acceptance criteria** — every AC (1–16) shipped as written.
- Purely additive grammar work behind the existing `SymbolEngine` / `Locator`. The
  locate / orchestrator / formatter path was not touched, so AC15
  (locate/orchestrator/contract unchanged) holds by construction.
- Added the remaining tree-sitter grammars + per-language defs-only extraction,
  delivered in the spec's three tiers:
  - **Tier A (single clean grammar each):** Rust (`function`/`method`/`struct`/
    `enum`/`trait`/`type`/`constant`; `impl` + generic + `impl Trait for Foo`
    parent normalization via the reused Go `_strip_go_type`; `const`/`static` →
    `constant`, `UPPER_SNAKE`-filtered), Java, C# (`class`/`struct`/`interface`/
    `enum`/`method`; class-in-class nesting with immediate parent; method-body-local
    defs dropped; `namespace` containers descended-not-emitted).
  - **Tier B (JS/TS family):** JavaScript, TypeScript, TSX (`function`/`method`/
    `class`/module-`constant` incl. `export const`; TS adds `interface`/`type`/
    `enum`; JSX elements yield no records). `tree-sitter-typescript` provides BOTH
    the `typescript` and `tsx` grammars (`language_typescript()` / `language_tsx()`,
    not `language()`).
  - **Tier C (C/C++):** C, C++ (function-definition-only, prototypes excluded;
    `struct`/`union`/`enum`/`typedef`; `typedef struct {…} Foo;` → one `type`,
    `typedef struct Foo {…} Foo;` → `struct` + `type`; C++ adds `method` incl.
    out-of-line `void Foo::bar(){}` → parent `Foo`, `class`, `using`/typedef `type`,
    nested types; namespaces descended-not-emitted).
- `engine_identity` now enumerates all 10 grammar slots (Python, Go, Rust, Java, C#,
  JavaScript, TypeScript, TSX, C, C++), with `typescript` and `tsx` coupled (two
  identity keys, one `tree-sitter-typescript` package version). A new
  `_GRAMMAR_SLOTS` map (slot → dist, module, language-fn) replaced the flat
  `_GRAMMARS` tuple and handles the typescript dual-grammar load.

## Notable implementation findings

- **Pre-existing P1 no-silent-coverage violation (the biggest finding).** The tree
  already violated the no-false-capability rule before this spec: Wave-1's
  `classify._EXT_TO_LANG` over-routed all 9 languages while
  `indexer.SYMBOL_LANGUAGES` was only `{python, go}`, so `_extract_file` returned
  `([], None)` — a silent clean-zero indistinguishable from a genuinely symbol-less
  file — for `.rs`/`.ts`/etc. Fixed with a permanent lockstep invariant
  `classify.KNOWN_LANGUAGES == indexer.SYMBOL_LANGUAGES`, asserted by the new
  `harpyja/index/test_routing.py` and re-checked at every tier boundary.
- **`.h`→C tolerance discovery (AC8 scoped guarantee vindicated).** Both reviewers
  flagged the original "never a wrong-range record" overclaim. During impl,
  tree-sitter-c was found to **tolerate** a bare `class Foo {}` (parses it with no
  ERROR node — would yield a wrong-meaning record), so the AC8 test uses
  `template<…>`, which reliably triggers an ERROR. The shipped guarantee is exactly
  the narrowed one: degrade only when an `ERROR`/`MISSING` node is present; a C-legal
  subset of a C++ header parsing cleanly as `c` is the documented cost of the `.h`→C
  default, not claimed as rejected.
- **`.tsx`→typescript was a latent Wave-1 routing bug**, corrected to `.tsx`→tsx
  during routing reconciliation. Also added previously-missing `.cxx`/`.c++`/
  `.hxx`/`.h++`.

## Files touched

Production:
- `harpyja/index/classify.py` (routing reconciliation; `KNOWN_LANGUAGES`)
- `harpyja/index/indexer.py` (`SYMBOL_LANGUAGES` lockstep)
- `harpyja/symbols/engine_identity.py` (`_GRAMMAR_SLOTS`, 10 slots, ts/tsx coupling)
- `harpyja/symbols/extract.py` (per-language extraction for 8 new grammars)
- `pyproject.toml` (7 pinned grammar packages), `uv.lock`

Tests:
- `harpyja/index/test_routing.py` (new — lockstep invariant)
- `harpyja/index/test_classify.py`, `harpyja/index/test_indexer.py`,
  `harpyja/orchestrator/test_locate.py`, `harpyja/symbols/test_extract.py`,
  `harpyja/symbols/test_engine_identity.py`, `harpyja/symbols/test_symbol_locator.py`,
  `harpyja/symbols/test_air_gap.py`

## ADR proposed for history.md

See proposal returned to the developer (dated 2026-06-26 — "Wave 2 symbol layer
completed (all 10 grammars) + no-silent-coverage lockstep invariant").

## Conventions proposed

- New: no-silent-coverage lockstep — routing, identity slot, and extraction rules
  for a language ship in the same change; never route a capability ahead of its
  implementation.
- New: per-grammar identity-slot pattern (one slot per grammar entry point;
  same-package grammars share one version and move together).
