---
id: "0003"
title: "Wave 2 — Symbol layer (tree-sitter, Python + Go)"
spec: specs/0003-wave-2-symbol-layer/spec.md
created: 2026-06-26
---

# Plan 0003 — Wave 2 — Symbol layer (tree-sitter, Python + Go)

Test-first (RED→GREEN→REFACTOR). Every GREEN step is preceded by a failing RED.
**Not greenfield** — Wave 0 + Wave 1 shipped; many steps EXTEND existing
modules/tests (`indexer`, `manifest`, `format`, `locate`, `app`, `cli`) and a few
existing assertions that hard-code Wave-1 values must be flipped under a RED first.

Conventions: Python 3.12, pytest, ruff; co-located `test_*.py` (no top-level
`tests/`); `asyncio.run` for async tests (no pytest-asyncio); inject collaborators
(parser/engine/symbol-source/`engine_identity`/`hash_fn`) to keep tests
network- and process-free; `@pytest.mark.integration` **only** where a real
tree-sitter grammar is genuinely spawned or a real loop/socket runs. Frozen
`Settings` (`dataclasses.replace`, never mutate). The only sanctioned writes are
derived artifacts under `<repo>/.harpyja/` (Wave-1 external-cache fallback
unchanged). Byte-reproducible artifacts use fixed key order + stable sort +
same-dir `tempfile.mkstemp` + `os.replace` (literal, not `rename`). Wrap foreign
exceptions with `raise ... from`.

Reuse verbatim (do not redefine): `harpyja/server/types.py`
(`CodeSpan`/`Citation`/`LocateRequest`/`LocateResult`/`Mode`) — a symbol-definition
span is marked by populating the existing optional `CodeSpan.symbol`; any extra
ranking metadata (`kind`, `parent`) rides as **additive optional** `CodeSpan`
attributes, never a redefinition of the Wave-1 fields. Reuse the Wave-1 atomic
same-dir-temp + `os.replace` commit and the `"sha256:…"` digest family.

Exact Wave-2 strings/keys to reproduce:
- locate mode note → `"Wave 2: deterministic + symbol-aware Tier 0; mode has no effect"`
- records total order / formatter tie-break → `(path, start_line, end_line, kind, name)`
- `symbols.jsonl` record key order → `path, language, name, kind, parent, start_line, end_line`
- `engine_identity` sentinels → `"missing"`, `"load-error:<abi>"`

## Group A — Packaging + grammar deps

1. **GREEN — Pin individual tree-sitter grammars.** EXTEND `pyproject.toml`
   `[project].dependencies` → pin `tree-sitter`, `tree-sitter-python`,
   `tree-sitter-go` at explicit versions (NOT the aggregate `tree-sitter-languages`
   wheel); `uv sync`/`uv lock`. AC15, AC17. _codex._

## Group B — Engine identity (cache key)

2. **RED — engine_identity shape + sentinels.** CREATE
   `harpyja/symbols/test_engine_identity.py`:
   `test_engine_identity_includes_runtime_and_each_grammar_version`,
   `test_engine_identity_absent_grammar_records_missing_sentinel`,
   `test_engine_identity_load_failure_records_load_error_abi_sentinel`,
   `test_engine_identity_is_deterministic_across_calls`,
   `test_engine_identity_carries_schema_version_for_record_format`.
   Inject an importer/loader seam (no real grammar required). AC8d, AC15.
3. **GREEN — `engine_identity()`.** CREATE `harpyja/symbols/engine_identity.py`:
   returns the tree-sitter runtime version **plus** each pinned grammar version
   (`tree-sitter-python`, `tree-sitter-go`) and a `schema_version`; absent →
   `"missing"`, ABI/version-skew load failure → `"load-error:<abi-code>"`
   (`raise ... from`); never an empty/undefined slot. AC8d, AC15.

## Group C — Symbol extraction (`extract.py`)

4. **RED — Python kind vocabulary + parent + exclusions.** CREATE
   `harpyja/symbols/test_extract.py`:
   `test_extract_python_function_method_class_and_module_constant`,
   `test_extract_python_async_def_same_kind_as_def`,
   `test_extract_python_constant_only_upper_snake_plain_or_annotated`,
   `test_extract_python_constant_excludes_tuple_unpack_and_augmented`,
   `test_extract_python_call_valued_constant_still_constant_by_syntax`,
   `test_extract_python_method_parent_is_immediate_enclosing_class`,
   `test_extract_python_toplevel_parent_is_null`,
   `test_extract_python_skips_imports_call_sites_and_function_local_defs`.
   Inject a parsed tree / parser seam so no grammar spawns. AC1, AC2.
5. **GREEN — Python extractor + `SymbolRecord`.** CREATE
   `harpyja/symbols/extract.py`: `SymbolRecord(path, language, name, kind, parent,
   start_line, end_line)` (1-indexed inclusive, `CodeSpan`-compatible); Python
   walk classifying by **syntactic form** only; parser injected. AC1, AC2.
6. **RED — Go kind vocabulary + receiver normalization.** EXTEND
   `test_extract.py`:
   `test_extract_go_function_method_struct_interface_and_named_type`,
   `test_extract_go_package_level_const_and_var`,
   `test_extract_go_pointer_and_value_receiver_both_parent_foo`,
   `test_extract_go_generic_receiver_strips_pointer_and_type_params`,
   `test_extract_go_toplevel_parent_is_null`. AC2.
7. **GREEN — Go extractor.** EXTEND `extract.py`: Go walk + receiver
   normalization (strip pointer `*` and generic `[T]` type-param list → bare type
   name). AC2.
8. **RED — Parse-error own-region scoping + grammar-unavailable.** EXTEND
   `test_extract.py`:
   `test_extract_skips_error_spanned_def_keeps_clean_sibling` (AC4-i),
   `test_extract_flags_parse_error_for_error_outside_every_def` (AC4-ii),
   `test_extract_class_with_clean_method_a_and_broken_method_b_emits_class_and_a` (AC4-iv),
   `test_extract_method_with_broken_local_def_still_emitted_full_range` (D4 nested-form
   exclusion: a function-local `def` is an excluded region even though it is not
   itself extracted),
   `test_extract_grammar_missing_yields_zero_records_flagged_grammar_missing` (AC4-iii),
   `test_extract_grammar_load_error_yields_zero_records_flagged_grammar_missing` (AC15).
   AC4, AC15.
9. **GREEN — degradation scoping + `ExtractResult`.** EXTEND `extract.py`: a def is
   **skipped** when an `ERROR`/`MISSING` node falls in its **own region (its span
   excluding the subtrees of any nested-definition syntactic form, extracted or
   not)**; the file is flagged `parse-error` on **any** `ERROR`/`MISSING` node,
   including one outside every def; grammar import/load failure → zero records +
   `grammar-missing`. Return `ExtractResult(records, degraded)` where `degraded` is
   one of `parse-error` / `grammar-missing` / clean. AC4, AC15.

## Group D — `symbols.jsonl` + `symbols.meta.json` I/O + integrity (`symbols_io.py`)

10. **RED — deterministic write/read + sidecar.** CREATE
    `harpyja/symbols/test_symbols_io.py`:
    `test_write_symbols_jsonl_fixed_key_order`,
    `test_symbols_ordered_by_full_total_key_path_start_end_kind_name`,
    `test_two_writes_byte_identical_with_colliding_constants_a1_b2` (AC7: `A = 1;
    B = 2`, two `constant` records sharing both lines),
    `test_write_atomic_same_dir_temp_then_os_replace` (spy `os.replace`, assert
    same dir),
    `test_meta_sidecar_fixed_key_order_and_stable_sorted_languages`,
    `test_meta_languages_is_distinct_langs_with_at_least_one_record`,
    `test_read_symbols_roundtrip`. AC1, AC7.
11. **GREEN — `write_symbols`/`write_meta`/`read_symbols`.** CREATE
    `harpyja/symbols/symbols_io.py`: records sorted by the total key, fixed key
    order; **records committed first, meta last**, each via same-dir
    `mkstemp` + `os.replace`; meta carries `schema_version`, `engine_identity`,
    stable-sorted `languages` (≥1-record langs only), `record_count`,
    `content_digest` (`"sha256:…"` over the exact `symbols.jsonl` bytes). AC1, AC7.
12. **RED — self-verifying integrity → rebuild decision.** EXTEND
    `test_symbols_io.py`:
    `test_needs_rebuild_when_jsonl_missing_or_unreadable`,
    `test_needs_rebuild_when_jsonl_truncated_midline_non_json` (AC8a),
    `test_needs_rebuild_when_clean_newline_truncation_count_mismatch` (AC8b),
    `test_needs_rebuild_when_content_digest_mismatch` (AC8b),
    `test_needs_rebuild_when_meta_missing_but_jsonl_present` (AC8c),
    `test_needs_rebuild_when_engine_identity_mismatch` (AC8d),
    `test_needs_rebuild_on_records_first_meta_last_crash_residue` (fresh records
    under a stale meta whose digest/count no longer bind),
    `test_no_rebuild_when_records_and_meta_intact`. AC8.
13. **GREEN — `load_symbols_or_none` / integrity gate.** EXTEND `symbols_io.py`:
    parse every line (truncation/midline), compare line count to `record_count`
    and recomputed `sha256` to `content_digest`, require a readable meta whose
    `engine_identity` matches the running engine; any failure → signal full
    rebuild (never trust the records). AC8.

## Group E — Manifest per-file `degraded` field (D18)

14. **RED — additive `degraded` field, Wave-1 determinism preserved.** EXTEND
    `harpyja/index/test_manifest.py`:
    `test_manifest_entry_has_degraded_field_default_clean`,
    `test_manifest_degraded_in_key_order_and_serialized_json`,
    `test_manifest_reads_legacy_entry_missing_degraded_with_default`,
    `test_manifest_two_writes_byte_identical_with_degraded_field`. AC16/D18.
15. **GREEN — extend `ManifestEntry`.** EXTEND `harpyja/index/manifest.py`: add a
    `degraded` field (default clean), append it to `_KEY_ORDER` additively, and
    default it on read for back-compat — Wave-1 sort/atomic write unchanged. AC16/D18.

## Group F — Indexer integration

16. **RED — index writes symbols + `symbols_indexed` total-in-index.** EXTEND
    `harpyja/index/test_indexer.py`:
    `test_index_writes_symbols_jsonl_and_meta_alongside_manifest` (AC1),
    `test_index_symbols_indexed_equals_total_records_in_index` (AC3),
    `test_index_null_language_and_grammarless_files_contribute_zero_symbols` (AC3),
    `test_index_languages_map_unchanged_remains_file_count` (AC3).
    Inject an extractor seam (no real grammar). AC1, AC3.
17. **GREEN — wire extraction into `index_repo`.** EXTEND
    `harpyja/index/indexer.py`: parse changed files via the injected extractor,
    write `symbols.jsonl` + `symbols.meta.json`, set `symbols_indexed` = total
    records after refresh, keep `languages` a file count. AC1, AC3.
18. **RED — incremental re-parse / prune / rehash with a spy.** EXTEND
    `test_indexer.py`:
    `test_index_unchanged_file_not_reparsed_zero_parse_calls` (AC5 spy),
    `test_index_changed_hash_file_reparsed_records_replaced` (AC5),
    `test_index_rehash_reparses_every_file` (AC5),
    `test_index_prunes_deleted_file_symbol_records` (AC6),
    `test_index_no_reparse_path_still_reads_jsonl_once_for_digest` (AC5: zero parse
    calls ≠ zero file reads). AC5, AC6.
19. **GREEN — gate symbol re-parse by change-of-record.** EXTEND `indexer.py`:
    re-extract only files whose `hash` changed; reuse prior records on a
    `(mtime, size)` gate pass; prune records for vanished paths; `--rehash`
    re-parses all. AC5, AC6.
20. **RED — degraded total-in-index + persistence + integrity rebuild.** EXTEND
    `test_indexer.py`:
    `test_index_degraded_reports_parse_error_file_total_in_index` (AC4),
    `test_index_degraded_persisted_on_manifest_and_reused_on_no_reparse` (AC16),
    `test_index_pruning_drops_persisted_degraded_flag` (AC16),
    `test_index_grammar_missing_distinguishable_from_parse_error_in_degraded` (AC4),
    `test_index_forces_full_symbol_rebuild_on_integrity_failure_independent_of_gate` (AC8),
    `test_index_grammar_version_bump_forces_rebuild_with_mtime_size_unchanged` (AC8d),
    `test_index_absent_to_present_grammar_rebuild_clears_stale_grammar_missing` (AC8e).
    AC4, AC8, AC16.
21. **GREEN — persist + reuse + integrity-driven rebuild.** EXTEND `indexer.py`:
    write each file's degradation outcome onto its `ManifestEntry`, reuse it with
    the gated entry, and surface the full total-in-index `degraded` array; on a
    `symbols_io` integrity/engine-identity failure force a **full** symbol rebuild
    (re-parse every file, independent of the `(mtime, size)` gate and without
    `--rehash`); an `engine_identity` change (incl. absent→present grammar)
    re-parses now-parseable files and clears their stale `grammar-missing` flags.
    AC4, AC8, AC16.

## Group G — SymbolEngine behind the `Locator` protocol (`symbol_locator.py`)

22. **RED — exact-only name + method-address search.** CREATE
    `harpyja/symbols/test_symbol_locator.py`:
    `test_symbol_engine_implements_locator_search_signature` (AC9),
    `test_search_exact_case_sensitive_name_match_parse_ne_lower_parse` (AC9),
    `test_search_no_substring_match_parseconfig_or_reparse` (AC9),
    `test_search_returns_definition_codespans_carrying_symbol_parent_kind` (AC9/AC10),
    `test_search_method_address_dot_pair_matches_parent_then_name` (AC10),
    `test_search_method_address_colon_colon_pair` (AC10),
    `test_search_whitespace_separated_segments_not_method_address` (`Foo bar`) (AC10),
    `test_search_chain_evaluates_every_adjacent_pair` (`Foo.bar.baz`) (AC10),
    `test_search_bounded_by_configured_search_limits` (AC9).
    Inject loaded records (via `symbols_io`). AC9, AC10.
23. **GREEN — `SymbolEngine`.** CREATE `harpyja/symbols/symbol_locator.py`:
    implements `search(pattern, scope=None) -> list[CodeSpan]` (the shared
    `Locator` protocol); split query on whitespace into segments, then per segment
    tokenize names on `[^A-Za-z0-9_]` (exact, case-sensitive `==`) **and** a
    separator-preserving pass for ordered adjacent `.`/`::` `(parent, name)` pairs;
    return definition `CodeSpan`s with `symbol`/`parent`/`kind` populated (additive
    optional fields). AC9, AC10.

## Group H — Citation formatter definition boost

24. **RED — definition boost + widened tie-break + no-match parity.** EXTEND
    `harpyja/orchestrator/test_formatter.py`:
    `test_formatter_ranks_definition_span_above_call_site` (AC10),
    `test_formatter_boost_layers_on_prior_and_density` (AC11/D11),
    `test_formatter_tiebreak_widened_to_path_start_end_kind_name` (AC12),
    `test_formatter_without_definition_spans_identical_to_wave1` (AC11/D10b),
    `test_formatter_same_symbol_in_multiple_files_orders_deterministically` (AC12).
    AC10, AC11, AC12.
25. **GREEN — boost as a ranking signal.** EXTEND
    `harpyja/orchestrator/format.py`: apply a **placeholder** definition boost
    (keyed on a populated `symbol`) on top of Wave-1 `prior` + density; widen the
    stable tie-break to `(path, start_line, end_line, kind, name)`; the placeholder
    weight MUST preserve "definition above call site" (D12). AC10, AC11, AC12.

## Group I — Orchestrator locate composition

26. **RED — compose Locators, promote, degrade, Wave-2 note.** EXTEND
    `harpyja/orchestrator/test_locate.py` (UPDATE the existing
    `result.notes` assertion at line 98):
    `test_locate_mode_note_is_wave2_symbol_aware_string` (AC14),
    `test_locate_composes_symbol_and_ripgrep_locators_into_one_stream` (AC9),
    `test_locate_promotes_definition_above_call_site_for_same_token` (AC10),
    `test_locate_no_symbol_match_degrades_to_wave1_exact_citations_and_order` (AC11),
    `test_locate_method_address_foo_dot_bar_promotes_method` (AC10),
    `test_locate_foo_space_bar_is_not_a_method_address` (AC10),
    `test_locate_never_branches_on_symbol_engine_presence` (AC9),
    `test_locate_stays_tier0_zero_model_calls` (AC10),
    `test_locate_language_hint_filters_symbol_records_by_file_language` (AC14).
    AC9, AC10, AC11, AC14.
27. **GREEN — compose + Wave-2 note.** EXTEND
    `harpyja/orchestrator/locate.py`: replace `_MODE_NO_EFFECT` with
    `"Wave 2: deterministic + symbol-aware Tier 0; mode has no effect"`; compose
    the `SymbolEngine` and `RipgrepEngine` Locators into one `CodeSpan` stream
    handed to `format_citations` (no branching on engine presence); `mode` stays
    accept-validate-flag, `max_results` mandatory clamp, `language_hint` filters by
    manifest language (symbol records inherit the file language). AC9, AC10, AC11,
    AC14.
28. **RED — ensure-index refreshes symbols.** EXTEND `test_locate.py`:
    `test_locate_after_edit_reflects_new_symbols_without_explicit_reindex` (AC13),
    `test_locate_builds_symbols_from_scratch_when_none_present` (AC13). AC13.
29. **GREEN — ensure-index over symbols.** EXTEND `locate.py`: the Wave-1
    incremental refresh `locate` already runs now also refreshes `symbols.jsonl`
    and feeds the loaded records to the `SymbolEngine`. AC13.

## Group J — MCP + CLI surfacing

30. **RED — surface real symbols/degraded + Wave-2 note through tools.** EXTEND
    `harpyja/server/test_app.py` (UPDATE the `symbols_indexed == 0` assertion at
    line 73) and `harpyja/server/test_locate_tool.py`:
    `test_build_app_index_surfaces_real_symbols_indexed` (AC3),
    `test_build_app_index_surfaces_degraded_array` (AC16),
    `test_build_app_locate_promotes_definition_above_call_site` (AC10),
    `test_build_app_wires_symbol_engine_into_locate` (AC9),
    `test_locate_tool_note_reflects_wave2_symbol_tier` (AC14). AC3, AC9, AC10,
    AC14, AC16.
31. **GREEN — wire SymbolEngine + surface counts.** EXTEND
    `harpyja/server/app.py` (+ `harpyja/server/tools.py` if a compose helper is
    extracted): thread the `SymbolEngine` into the locate engine composition via
    the `engine_factory`; surface populated `symbols_indexed`/`degraded` from
    `index_repo`. AC3, AC9, AC10, AC14, AC16.
32. **RED — CLI summary shows real symbols/degraded.** EXTEND
    `harpyja/test_cli.py` (UPDATE the `symbols_indexed`/`degraded` fixtures at
    lines 69/72):
    `test_cli_index_summary_shows_real_symbols_indexed` (AC3),
    `test_cli_index_summary_lists_degraded_files` (AC16). AC3, AC16.
33. **GREEN — CLI summary.** EXTEND `harpyja/cli.py`: index summary prints the real
    `symbols_indexed` and `degraded` from the result. AC3, AC16.

## Group K — Air-gap audit + final gate

34. **RED — index/locate path makes no outbound call.** CREATE
    `harpyja/symbols/test_air_gap.py`:
    `test_index_and_locate_make_no_outbound_network_call` (monkeypatch `socket`
    to forbid connects, run index+locate over a tmp Python/Go fixture),
    `test_assert_local_and_inbound_bind_defaults_untouched`. Genuine-grammar parse
    paths marked `@pytest.mark.integration`. AC17.
35. **GREEN — confirm local-only parsing.** Confirm tree-sitter parsing introduces
    no egress and `gateway.assert_local` / the Wave-0 loopback bind are untouched;
    contain any incidental egress if the audit surfaces one. AC17.
36. **REFACTOR — full gate.** `ruff check --fix`, `ruff format`, full
    `uv run pytest` (incl. `-m integration`); de-dup `symbols/` and indexer
    helpers; regression gate over all 17 ACs. _codex._

## Delegation
- Steps **1, 36** → codex (grammar pin/lock, lint/format, full incl-integration
  test gate, regression de-dup). Mechanical, no contract judgement.
- All RED/GREEN logic steps require contract judgement (kind vocabulary, parse-error
  scoping, integrity/rebuild semantics, exact-match + method addressing, ranking
  invariants) — not mechanical.

## Risks & mitigations
- **Manifest byte-shape change from adding `degraded` (D18).** Add the field
  **last** in `_KEY_ORDER` with a clean default and default-on-read for legacy
  entries; step 14 RED pins back-compat read **and** byte-identical determinism
  before the GREEN — Wave-1 manifests never silently break.
- **tree-sitter as a real dependency.** Keep extraction unit-testable via a parser
  seam (inject a parsed tree / parser factory) and an injected `engine_identity`;
  grammar-missing and load-error paths are exercised by injection (steps 8/9/20),
  not by uninstalling a package. Reserve `@pytest.mark.integration` for the few
  genuine-grammar parse tests and the air-gap audit (step 34).
- **Integration-marker creep.** Inject extractor/engine/symbol-source seams so
  Groups C–J stay unit-level; only real-grammar and socket tests carry the marker.
- **Digest read-path cost (O(records) every refresh, incl. no-reparse).** Accepted
  per spec (correctness > micro-opt); step 18 pins that the no-reparse path still
  reads `symbols.jsonl` once for the digest, so "zero parse calls" stays distinct
  from "zero file reads" and the cost is intentional, not accidental.
- **Two-file commit is not jointly atomic.** Records-first / meta-last with the
  fingerprint (`record_count` + `content_digest`) detecting the only inconsistent
  intermediate; step 12 RED simulates the crash residue (fresh records under a
  stale meta) and asserts rebuild; `os.replace` named literally for cross-platform
  atomicity.
- **Definition metadata on `CodeSpan`.** Mark definitions via the existing optional
  `symbol`; carry `kind`/`parent` as additive optional attributes — Wave-1 fields
  are reused verbatim, the formatter boost keys on a populated `symbol`.
- **Air-gap regression.** Step 34 monkeypatches `socket` across the full
  index+locate path and asserts `assert_local` / inbound-bind defaults untouched.
- **Artifact-write guardrail.** `symbols.jsonl`/`symbols.meta.json` join
  `manifest.jsonl` as sanctioned `.harpyja/` derived artifacts; all FS tests use
  `tmp_path`; source files stay read-only.
