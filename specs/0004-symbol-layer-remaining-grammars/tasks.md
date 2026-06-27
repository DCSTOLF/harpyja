---
id: "0004"
title: "Wave 2 follow-up — Symbol layer: remaining grammars (Rust, JS/TS, C#, Java, C/C++)"
plan: specs/0004-symbol-layer-remaining-grammars/plan.md
created: 2026-06-26
---

# Tasks 0004 — Wave 2 follow-up — remaining symbol grammars

Execution order. Every RED precedes its GREEN. See `plan.md` for detail.

- [x] 1.  GREEN: Pin tree-sitter-rust/java/c-sharp/javascript/typescript/c/cpp in pyproject  (codex)
- [x] 2.  RED:   engine_identity enumerates all 10 grammar slots + tsx/typescript coupling + new-grammar sentinels
- [x] 3.  GREEN: expand _GRAMMARS + coupled tsx slot from single tree-sitter-typescript probe
- [x] 4.  RED:   no-silent-coverage invariant (KNOWN_LANGUAGES==SYMBOL_LANGUAGES) + routing reconciliation
- [x] 5.  GREEN: shrink classify _EXT_TO_LANG to shipped langs (remove Wave-1 over-reach + buggy .tsx)
- [x] 6.  RED:   Rust kind vocabulary + impl/generic + impl-Trait-for-Foo + UPPER_SNAKE const filter
- [x] 7.  GREEN: Rust extractor + _RUST_NESTED + parser branch
- [x] 8.  RED:   Java class/interface/enum/method + class-in-class nesting + body-local dropped
- [x] 9.  GREEN: Java extractor + _JAVA_NESTED + parser branch
- [x] 10. RED:   C# class/struct/interface/enum/method + nesting + namespace/field/property excluded
- [x] 11. GREEN: C# extractor + _CSHARP_NESTED + parser branch
- [x] 12. RED:   Tier A parse-error own-region scoping (rust/java/csharp)
- [x] 13. GREEN: Tier A degradation scoping via _own_region_errored
- [x] 14. RED:   Ship Tier A routing + SYMBOL_LANGUAGES; FLIP silent-.rs grammarless test
- [x] 15. GREEN: classify .rs/.java/.cs + SYMBOL_LANGUAGES |= {rust,java,csharp} in lockstep
- [x] 16. RED:   JS/TS/TSX function/method/class/constant + export const + TS interface/type/enum + JSX-no-records
- [x] 17. GREEN: JS/TS/TSX extractors + _JS_NESTED + parser branches (tsx+typescript share package)
- [x] 18. RED:   Tier B parse-error scoping
- [x] 19. GREEN: Tier B degradation scoping
- [x] 20. RED:   Ship Tier B routing incl. .tsx→tsx correction + SYMBOL_LANGUAGES
- [x] 21. GREEN: classify .js/.mjs/.cjs/.jsx→js, .ts→typescript, .tsx→tsx + SYMBOL_LANGUAGES lockstep
- [x] 22. RED:   C/C++ vocabulary + typedef idiom + out-of-line method + nesting + prototypes excluded
- [x] 23. GREEN: C/C++ extractors + _C_NESTED/_CPP_NESTED + parser branches
- [x] 24. RED:   .h→C scoped guarantee (class Foo{}; ERROR) + preprocessor-mangled parse-error
- [x] 25. GREEN: C/C++ degradation scoping, never raise
- [x] 26. RED:   Ship Tier C full extension routing (.cxx/.c++/.hxx/.h++, .h→c) + .mts/.cts null + SYMBOL_LANGUAGES
- [x] 27. GREEN: classify C/C++ extensions + SYMBOL_LANGUAGES |= {c,cpp} (all 10 in lockstep)
- [x] 28. RED:   Absent/load-error per new grammar via seam + tsx/typescript coupled absence
- [x] 29. GREEN: generic grammar-missing across new languages (parser_for branches)
- [x] 30. RED:   engine_identity rebuild: new-grammar bump + absent→present clears stale grammar-missing (regression)
- [x] 31. RED:   Method addressing (./::), arrow-not-address, cross-ns collision, definition promotion, exact case (regression)
- [x] 32. RED:   No-match parity + byte-identical determinism on mixed-language tree (regression)
- [x] 33. RED:   symbols_indexed total + no-reparse persistence + prune across all languages (regression)
- [x] 34. RED:   Orchestrator/formatter unchanged + language_hint + mode + max_results + honest notes (regression)
- [x] 35. RED:   Air-gap audit extended to new grammars (EXTEND test_air_gap.py)
- [x] 36. REFACTOR: ruff fix/format + full pytest incl -m integration + cross-language de-dup gate  (codex)
