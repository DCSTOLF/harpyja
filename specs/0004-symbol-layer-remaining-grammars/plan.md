---
id: "0004"
title: "Wave 2 follow-up — Symbol layer: remaining grammars (Rust, JS/TS, C#, Java, C/C++)"
spec: specs/0004-symbol-layer-remaining-grammars/spec.md
created: 2026-06-26
---

# Plan 0004 — Wave 2 follow-up — remaining symbol grammars

Test-first (RED→GREEN→REFACTOR). Every GREEN is preceded by a failing RED.
**Purely additive grammar work, NOT greenfield.** The `SymbolEngine`, the `Locator`
protocol, the degradation model (D4), the `symbols.jsonl` + `symbols.meta.json`
integrity sidecar (D15), per-file `degraded` persistence (D18), exact matching +
method addressing (D10a/c), and definition promotion are all SHIPPED in 0003 and are
**reused unchanged** — the locate / orchestrator / formatter path needs **no code
change** (AC15). New languages are new grammar+rule entries that produce more records
flowing through the existing pipeline. This plan touches only: grammar pins,
`engine_identity` enumeration, extension routing reconciliation, `SYMBOL_LANGUAGES`,
the per-language extractors, the no-silent-coverage invariant, and tests/fixtures.

Conventions: Python 3.12, pytest, ruff; co-located `test_*.py`; inject collaborators
(`parser_for` / `probe` / `extractor` / `engine_identity`) so absent-package and
load-error paths are exercised by **injected seams, never by uninstalling a package**.
Following 0003's **shipped** choice, extraction/locate tests parse real grammars
**in-process** and stay **unit-level (no marker)**; `@pytest.mark.integration` is
reserved for real subprocess / event-loop tests (none new here). Frozen `Settings`
(`dataclasses.replace`). Sanctioned writes only under `<repo>/.harpyja/`. Wrap foreign
exceptions with `raise ... from`.

Reuse verbatim (do not redefine): `SymbolRecord(path, language, name, kind, parent,
start_line, end_line)` (1-indexed inclusive), `ExtractResult(records, degraded)`,
`_own_region_errored(node, nested_types)` for D4 own-region scoping, the
`^[A-Z][A-Z0-9_]*$` UPPER_SNAKE constant filter, the `"missing"` / `"load-error:<abi>"`
sentinels, the `.` / `::` method-address separators, and the records-first/meta-last
`os.replace` commit.

**No-silent-coverage invariant (P1, the most important correctness item).** A
language's **extension routing + `engine_identity` slot + extraction rules ship in the
SAME tier**. The invariant is enforced as a lockstep equality:
`classify.KNOWN_LANGUAGES == indexer.SYMBOL_LANGUAGES` at every tier boundary. The tree
currently **violates** this (classify routes 9 languages; only python/go extract; a
`.rs` file parses to zero records with `degraded=None` — indistinguishable from a
genuinely symbol-less file). Group 0 reconciles classify back to lockstep by **removing
the premature Wave-1 over-reach routing** (which includes the buggy `.tsx`→typescript
line); each tier then re-adds its extensions **in lockstep** with `SYMBOL_LANGUAGES` and
its extractors, so an unshipped tier is honestly `null`-language/ripgrep-only and never
silent zero-symbol coverage.

## Group 0 — Packaging, engine identity, routing reconciliation, no-silent-coverage invariant

1. **GREEN — Pin the 7 new grammars.** EXTEND `pyproject.toml`
   `[project].dependencies`: add `tree-sitter-rust`, `tree-sitter-java`,
   `tree-sitter-c-sharp`, `tree-sitter-javascript`, `tree-sitter-typescript` (provides
   both `typescript` and `tsx`), `tree-sitter-c`, `tree-sitter-cpp` at explicit
   versions (individual pins, D17 — not the aggregate wheel); `uv sync` / `uv lock`.
   AC9, AC10, AC16. _codex._
2. **RED — `engine_identity` enumerates all 10 grammar slots + tsx/typescript
   coupling + per-new-grammar sentinels.** EXTEND
   `harpyja/symbols/test_engine_identity.py`:
   `test_engine_identity_enumerates_all_ten_grammar_slots` (tree-sitter + python, go,
   rust, java, csharp, javascript, typescript, tsx, c, cpp),
   `test_engine_identity_typescript_and_tsx_share_one_package_version` (one
   `tree-sitter-typescript` probe drives both `typescript` and `tsx`; they move
   together — AC9/AC10 coupling note),
   `test_engine_identity_new_grammar_absent_records_missing_sentinel` (parametrized over
   the 7 new packages, injected `probe`),
   `test_engine_identity_new_grammar_load_failure_records_load_error_abi_sentinel`.
   Fails: `_GRAMMARS` lists only python/go, so the new slots are absent. AC9, AC10.
3. **GREEN — expand `_GRAMMARS` + coupled tsx slot.** EXTEND
   `harpyja/symbols/engine_identity.py`: add the 7 packages; map grammar slots →
   distribution so `typescript` and `tsx` are two identity keys both populated from the
   single `tree-sitter-typescript` version (probed once); existing missing/load-error
   sentinel logic reused as-is. AC9, AC10.
4. **RED — no-silent-coverage invariant + routing reconciliation.** CREATE
   `harpyja/index/test_routing.py`:
   `test_symbol_languages_cover_every_routed_symbol_language`
   (`classify.KNOWN_LANGUAGES == indexer.SYMBOL_LANGUAGES`),
   `test_routed_symbol_language_never_falls_through_to_clean_zero` (any language
   `classify` routes is in `SYMBOL_LANGUAGES`, so `_extract_file` never returns
   `([], None)` for a routed language — a routed-but-unsupported language would surface
   `grammar-missing`, never clean-zero),
   `test_unshipped_tier_extension_is_null_language` (`.rs`/`.ts`/`.cpp` → `None` until
   their tier ships). Fails now: classify routes 9 languages but `SYMBOL_LANGUAGES` has
   2. AC8 (invariant).
5. **GREEN — reconcile classify to lockstep.** EDIT
   `harpyja/index/classify.py`: shrink `_EXT_TO_LANG` to only the **shipped** symbol
   extensions (`.py`, `.pyi`, `.go`), removing the premature rust/js/ts/tsx/cs/java/c/cpp
   over-reach (incl. the buggy `.tsx`→typescript). The corrected per-extension mappings
   are re-introduced per tier (steps 15/21/27). Invariant test now green. AC8.

## Group A — Tier A: Rust, Java, C#

6. **RED — Rust kind vocabulary + impl/constant normalization.** EXTEND
   `harpyja/symbols/test_extract.py`:
   `test_extract_rust_function_method_struct_enum_trait_type`,
   `test_extract_rust_const_and_static_emit_constant_kind_upper_snake_only`,
   `test_extract_rust_lowercase_or_function_local_const_yields_no_record`,
   `test_extract_rust_impl_and_generic_impl_both_parent_foo` (`impl Foo` and
   `impl<T> Foo<T>` → `parent == "Foo"`),
   `test_extract_rust_impl_trait_for_foo_method_parent_foo`,
   `test_extract_rust_skips_use_call_sites_and_function_local_fn`,
   `test_extract_rust_record_range_one_indexed_inclusive`. Real grammar; fails — no Rust
   branch. AC1.
7. **GREEN — Rust extractor.** EXTEND `harpyja/symbols/extract.py`: add `_RUST_NESTED`
   frozenset, a `rust` branch in `_default_parser_for` + `extract_symbols`, and
   `_extract_rust()` — `fn`→function (top) / method (in `impl`, parent = impl type name
   with generics + `impl Trait for Foo` normalized to `Foo`), `struct`/`enum`/`trait`,
   `type` alias, `const`/`static`→`constant` filtered to module-level UPPER_SNAKE (reuse
   `_is_upper_snake`). Separator `::`. AC1.
8. **RED — Java kind vocabulary + class-in-class nesting.** EXTEND `test_extract.py`:
   `test_extract_java_class_interface_enum_and_method_parent`,
   `test_extract_java_toplevel_type_parent_null_and_method_never_null`,
   `test_extract_java_nested_inner_class_extracted_with_parent`,
   `test_extract_java_inner_class_method_parent_is_inner_type`,
   `test_extract_java_method_body_local_class_not_extracted`,
   `test_extract_java_skips_fields_imports_and_call_sites`. Fails — no Java branch. AC2.
9. **GREEN — Java extractor.** EXTEND `extract.py`: `_JAVA_NESTED`, parser branch,
   `_extract_java()` — `class`/`interface`/`enum`/`method` (parent = enclosing type);
   descend into type bodies so nested types are extracted with immediate `parent` and
   inner methods carry the inner type; do **not** descend into method bodies (body-local
   classes dropped). No fields/annotations. Separator `.`. AC2.
10. **RED — C# kind vocabulary + nesting + exclusions.** EXTEND `test_extract.py`:
    `test_extract_csharp_class_struct_interface_enum_and_method_parent`,
    `test_extract_csharp_nested_type_extracted_with_parent`,
    `test_extract_csharp_skips_properties_fields_using_and_namespace_containers`. Fails —
    no C# branch. AC3.
11. **GREEN — C# extractor.** EXTEND `extract.py`: `_CSHARP_NESTED`, parser branch,
    `_extract_csharp()` — `class`/`struct`/`interface`/`enum`/`method`, type-in-type
    nesting like Java, `namespace`/property/field excluded (descend through `namespace`
    containers without emitting them). Separator `.`. AC3.
12. **RED — Tier A parse-error own-region scoping.** EXTEND `test_extract.py`:
    `test_extract_rust_skips_error_spanned_def_keeps_clean_sibling`,
    `test_extract_java_flags_parse_error_on_any_error_node_clean_sibling_kept`,
    `test_extract_csharp_parse_error_scoped_to_own_region_excluding_nested`. Real
    grammars; fails until each language passes its `_<LANG>_NESTED` set to
    `_own_region_errored`. AC9(c).
13. **GREEN — Tier A degradation scoping.** EXTEND `extract.py`: wire each Tier-A
    extractor's emit path through `_own_region_errored(node, _<LANG>_NESTED)`; the file
    flags `parse-error` on any `ERROR`/`MISSING` node (root `has_error`, already
    generic); clean siblings still emitted. AC9(c).
14. **RED — Ship Tier A: routing + `SYMBOL_LANGUAGES` (flip the silent-`.rs` test).**
    EXTEND `harpyja/index/test_classify.py`
    (`test_classify_rust_java_csharp_extensions`), `harpyja/index/test_routing.py`
    (`test_symbol_languages_cover_routed_after_tier_a`), and **FLIP**
    `harpyja/index/test_indexer.py:149`
    `test_index_null_language_and_grammarless_files_contribute_zero_symbols` — its
    `lib.rs`/`fn main` fixture stops being "grammarless"; split into
    `test_index_truly_null_language_file_contributes_zero_symbols` (use a genuinely
    unmapped ext, e.g. `notes.xyz`) and `test_index_rust_file_now_extracts_symbols`
    (`fn main` → one `function` record). Fails — `.rs`/`.java`/`.cs` still `None`. AC1,
    AC2, AC3, AC8.
15. **GREEN — Tier A routing + languages in lockstep.** EDIT `classify.py` (add
    `.rs`→rust, `.java`→java, `.cs`→csharp) and `harpyja/index/indexer.py`
    (`SYMBOL_LANGUAGES |= {rust, java, csharp}`) together so the invariant holds. AC1,
    AC2, AC3, AC8.

## Group B — Tier B: JavaScript, TypeScript, TSX

16. **RED — JS/TS/TSX kind vocabulary + export const + JSX-no-records.** EXTEND
    `test_extract.py`:
    `test_extract_js_function_method_class_and_module_constant`,
    `test_extract_js_export_const_upper_snake_included` (the `export` wrapper does not
    change the kind),
    `test_extract_js_let_var_destructuring_and_lowercase_const_excluded`,
    `test_extract_ts_additionally_yields_interface_type_alias_and_enum`,
    `test_extract_tsx_jsx_elements_yield_no_records_surrounding_defs_extracted`,
    `test_extract_js_skips_imports_call_sites_and_nested_functions`. Fails — no js/ts/tsx
    branch. AC4, AC5.
17. **GREEN — JS/TS/TSX extractors.** EXTEND `extract.py`: `_JS_NESTED`, parser branches
    for `javascript` / `typescript` / `tsx` (tsx + typescript from
    `tree-sitter-typescript`), `_extract_js()` shared core — `function` (top-level
    declaration), `method` (parent = class), `class`, module-level `constant` (single
    `identifier` declarator, UPPER_SNAKE, incl. `export const`; `let`/`var`/destructuring
    excluded, reuse `_is_upper_snake`); TS/TSX additionally `interface`, `type` alias,
    `enum`; JSX/TSX elements emit nothing. Separator `.`. AC4, AC5.
18. **RED — Tier B parse-error scoping.** EXTEND `test_extract.py`:
    `test_extract_ts_skips_error_spanned_def_keeps_clean_sibling`,
    `test_extract_tsx_flags_parse_error_on_any_error_node`. Fails until `_JS_NESTED` is
    wired through `_own_region_errored`. AC9(c).
19. **GREEN — Tier B degradation scoping.** EXTEND `extract.py`: route js/ts/tsx emit
    paths through `_own_region_errored(node, _JS_NESTED)`. AC9(c).
20. **RED — Ship Tier B: routing (incl. the `.tsx`→tsx correction) + languages.** EXTEND
    `test_classify.py`:
    `test_classify_js_mjs_cjs_jsx_route_to_javascript`,
    `test_classify_ts_routes_to_typescript_and_tsx_routes_to_tsx` (the corrected
    `.tsx`→tsx, not typescript), and `test_routing.py`
    `test_symbol_languages_cover_routed_after_tier_b`. Fails — those extensions still
    `None` (and `.tsx` must be `tsx`, not the old buggy `typescript`). AC5, AC8.
21. **GREEN — Tier B routing + languages.** EDIT `classify.py` (`.js`/`.mjs`/`.cjs`/
    `.jsx`→javascript, `.ts`→typescript, `.tsx`→tsx) and `indexer.py`
    (`SYMBOL_LANGUAGES |= {javascript, typescript, tsx}`) in lockstep. AC5, AC8.

## Group C — Tier C: C, C++

22. **RED — C/C++ kind vocabulary + typedef idiom + out-of-line method + nesting.**
    EXTEND `test_extract.py`:
    `test_extract_c_function_definition_struct_enum_union_and_typedef`,
    `test_extract_c_bare_prototype_yields_no_record`,
    `test_extract_c_typedef_anonymous_struct_single_type_record` (`typedef struct {…}
    Foo;` → one `type` `Foo`),
    `test_extract_c_typedef_named_struct_emits_both_struct_and_type_records`
    (`typedef struct Foo {…} Foo;` → a `struct` **and** a `type`),
    `test_extract_cpp_function_method_class_struct_enum_union_and_type`,
    `test_extract_cpp_out_of_line_method_parent_normalized_to_foo`
    (`void Foo::bar(){}` → method, parent `Foo`),
    `test_extract_cpp_nested_type_extracted_with_parent_and_inner_methods`,
    `test_extract_cpp_prototypes_and_namespace_containers_yield_no_records`. Fails — no
    c/cpp branch. AC6, AC7.
23. **GREEN — C/C++ extractors.** EXTEND `extract.py`: `_C_NESTED` / `_CPP_NESTED`,
    parser branches, `_extract_c()` — `function` (definition with a body; prototypes
    excluded), `struct`/`enum`/`union`, `type` (typedef; emit both records for the named
    `typedef struct Foo {…} Foo;` form, one for the anonymous form) — and `_extract_cpp()`
    — adds `method` (member; out-of-line `Foo::bar` normalized to `Foo`), `class`,
    `using`/typedef `type`, type-in-type nesting; `namespace` containers descended but
    not emitted; prototypes excluded. Separators `.`/`::`. AC6, AC7.
24. **RED — C/C++ degradation: `.h`→C scoped guarantee + preprocessor-mangled.** EXTEND
    `test_extract.py`:
    `test_extract_c_header_with_cpp_class_yields_parse_error_not_crash` (a `.h` parsed as
    `c` containing `class Foo { … };` — syntax that **reliably** triggers a C-grammar
    `ERROR` — degrades `parse-error`, the error-spanned def not emitted, never raises),
    `test_extract_c_preprocessor_mangled_region_degrades_parse_error`,
    `test_extract_c_error_spanned_def_skipped_clean_sibling_kept`. Fails until C nested
    scoping is wired. AC8, AC9(c).
25. **GREEN — C/C++ degradation scoping.** EXTEND `extract.py`: route c/cpp emit paths
    through `_own_region_errored(node, _<LANG>_NESTED)`; `parse-error` on any
    `ERROR`/`MISSING`; never raise. AC8, AC9(c).
26. **RED — Ship Tier C: full extension routing + `.h`→C + `.mts`/`.cts` stay null.**
    EXTEND `test_classify.py`:
    `test_classify_c_and_h_route_to_c`,
    `test_classify_cpp_sources_and_headers_route_to_cpp` (`.cc`/`.cpp`/`.cxx`/`.c++`→cpp;
    `.hpp`/`.hh`/`.hxx`/`.h++`→cpp),
    `test_classify_unmapped_mts_cts_remain_null_language`, and `test_routing.py`
    `test_symbol_languages_cover_routed_after_tier_c` (all 10 symbol languages). Fails —
    c/cpp extensions still `None`, and `.cxx`/`.c++`/`.hxx`/`.h++` were never mapped. AC6,
    AC7, AC8.
27. **GREEN — Tier C routing + languages.** EDIT `classify.py` (full C/C++ extension set,
    `.h`→c default — documented) and `indexer.py`
    (`SYMBOL_LANGUAGES |= {c, cpp}`) in lockstep — `SYMBOL_LANGUAGES` now equals
    `KNOWN_LANGUAGES` over all 10. AC6, AC7, AC8.

## Group D — Cross-cutting end-state (reused 0003 machinery; mostly regression)

These lock the new languages flowing through the **unchanged** pipeline (AC15). Except
step 35 (test-only EXTEND) they require **no production change** — they pass against the
0003 machinery once Groups 0–C ship; they guard against regression / interim gaps.

28. **RED — Absent / load-error per new grammar at extract level + tsx coupling.** EXTEND
    `test_extract.py` (injected `parser_for` seam — never uninstall):
    `test_extract_absent_grammar_yields_zero_records_grammar_missing_each_new_language`
    (parametrized over rust/java/csharp/javascript/typescript/tsx/c/cpp),
    `test_extract_load_error_grammar_yields_grammar_missing`,
    `test_extract_typescript_and_tsx_absent_together_coupled` (one package → both
    degrade). AC9(a)(b).
29. **GREEN — generic grammar-missing across new languages.** EXTEND `extract.py`: confirm
    each new language has a real `_default_parser_for` branch and that the absent /
    load-error paths return `([], grammar-missing)` (reusing `extract_symbols`' existing
    try/except before dispatch). AC9(a)(b).
30. **RED — engine_identity rebuild over new grammars (indexer, regression).** EXTEND
    `harpyja/index/test_indexer.py`:
    `test_index_new_grammar_version_bump_forces_rebuild_mtime_size_unchanged`
    (inject `engine_ident`),
    `test_index_absent_to_present_new_grammar_clears_stale_grammar_missing`. Passes via
    the existing D15 identity-keyed rebuild; no GREEN. AC10.
31. **RED — Method addressing + definition promotion across new languages (locate,
    regression).** EXTEND `harpyja/symbols/test_symbol_locator.py` /
    `harpyja/orchestrator/test_locate.py`:
    `test_search_rust_colon_colon_method_address_promotes_method`,
    `test_search_cpp_colon_colon_method_address_promotes_method`,
    `test_search_java_dot_method_address_promotes_method`,
    `test_search_cpp_arrow_separator_is_not_a_method_address`,
    `test_search_cross_namespace_same_name_parent_both_match` (accepted documented
    ambiguity),
    `test_locate_promotes_new_language_definition_above_ripgrep_line_hits`,
    `test_locate_exact_case_sensitive_for_new_language` (`Parse` ≠ `parse` ≠
    `ParseConfig` ≠ `reParse`),
    `test_locate_stays_tier0_zero_model_calls_for_new_languages`. Reuses D10/D10a/D10c; no
    GREEN. AC11, AC12.
32. **RED — No-match parity + determinism on a mixed-language tree (regression).** EXTEND
    `test_locate.py` / `test_indexer.py`:
    `test_locate_no_symbol_match_identical_to_wave1_on_mixed_tree`,
    `test_index_two_runs_byte_identical_symbols_jsonl_and_meta_mixed_languages` (records
    ordered `(path, start_line, end_line, kind, name)`; sidecar fixed key order +
    stable-sorted `languages`). No GREEN. AC13.
33. **RED — Totals + persistence across all languages (regression).** EXTEND
    `test_indexer.py`:
    `test_index_symbols_indexed_total_across_all_languages`,
    `test_index_incremental_no_reparse_keeps_full_symbols_indexed_and_degraded`,
    `test_index_prune_deleted_new_language_file_drops_records_and_degraded`. Reuses
    D6/D18; no GREEN. AC14.
34. **RED — Locate/orchestrator/formatter unchanged (regression).** EXTEND
    `test_locate.py` (+ `harpyja/orchestrator/test_formatter.py` if needed):
    `test_locate_orchestrator_does_not_branch_on_language_for_new_languages`,
    `test_locate_language_hint_filters_new_language_records_by_manifest_language`,
    `test_locate_mode_accept_validate_flag_unchanged`,
    `test_locate_max_results_clamp_unchanged`,
    `test_locate_notes_string_remains_honest_tier0_symbol_aware`. No GREEN. AC15.
35. **RED — Air-gap audit extended to the new grammars.** EXTEND
    `harpyja/symbols/test_air_gap.py`
    `test_index_and_locate_make_no_outbound_network_call`: add rust/java/csharp/
    typescript/tsx/c/cpp fixtures to the parsed tree; assert `socket.connect`/`connect_ex`
    forbidden and `gateway.assert_local` / `DEFAULT_HTTP_HOST == "127.0.0.1"` untouched.
    Fails until all tiers parse (it now indexes the new languages); test-only. AC16.
36. **REFACTOR — full gate.** `ruff check --fix`, `ruff format`, full `uv run pytest`
    (incl. `-m integration`); de-dup the per-language `_extract_*` walkers / nested-set
    declarations where they share structure; regression gate over all 16 ACs. _codex._

## Delegation

- Steps **1, 36** → codex (grammar pin/lock; lint/format + full incl-integration gate +
  cross-language de-dup). Mechanical, no contract judgement.
- All RED/GREEN extraction + routing + invariant steps require contract judgement
  (per-language kind vocabulary, nesting rule, `typedef struct`/out-of-line
  normalization, parse-error scoping, lockstep invariant) — not mechanical.

## Risks & mitigations

- **The P1 silent-coverage state is live in the tree today.** Group 0's invariant test
  (`classify.KNOWN_LANGUAGES == SYMBOL_LANGUAGES`) RED-fails immediately and is re-asserted
  at every tier boundary (steps 14/20/26); the GREEN brings routing + languages + rules in
  lockstep, so partial delivery is honestly `null`-language, never silent zero-symbol.
- **`.tsx`→typescript bug + missing `.cxx`/`.c++`/`.hxx`/`.h++`.** Removed with the
  over-reach in Group 0; re-added correctly per tier (steps 21/27) with classify tests
  pinning each extension before the GREEN.
- **`typescript`/`tsx` share one package** (cannot be independently absent or bumped).
  Steps 2/3 carry two coupled identity slots from one probe; step 28 asserts coupled
  absence rather than an unsatisfiable independent-absence expectation.
- **`.h`→C overclaim.** Step 24 uses syntax that **reliably** triggers a C-grammar `ERROR`
  (`class Foo{};`) to pin the scoped guarantee (degrade on `ERROR`/`MISSING`, never
  crash, error-spanned def not emitted); a C-legal subset parsing cleanly as `c` is the
  documented cost, not claimed as rejected.
- **Nesting rule vs "no nested defs."** Per-language extractors descend **type bodies**
  (nested types extracted, immediate `parent`) but not **method/function bodies**
  (body-local defs dropped) — pinned by AC2/AC3/AC7 fixtures before each GREEN.
- **Integration-marker creep.** Following 0003's shipped choice, in-process real-grammar
  extraction/locate tests stay unit-level; absent/load-error/engine_identity use injected
  seams; only the air-gap socket audit touches real sockets.
- **Reuse claim must be real (AC15).** Group D is mostly regression with no production
  GREEN; if any step fails, the fix is a **localized** extractor/routing bug in Groups
  0–C, never an orchestrator/formatter change — keeping the adapter's "additive only"
  promise honest.
- **Artifact-write guardrail.** All FS tests use `tmp_path`; source files stay read-only;
  `symbols.jsonl`/`symbols.meta.json` remain the only new derived writes.
