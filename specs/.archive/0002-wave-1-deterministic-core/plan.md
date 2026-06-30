---
id: "0002"
title: "Wave 1 — Deterministic core (indexer + ripgrep)"
spec: specs/0002-wave-1-deterministic-core/spec.md
created: 2026-06-26
---

# Plan 0002 — Wave 1 — Deterministic core (indexer + ripgrep)

Test-first (RED→GREEN→REFACTOR). Every GREEN step is preceded by a failing RED.
**Not greenfield** — Wave 0 shipped; several steps EXTEND existing modules/tests.

Conventions: Python 3.12, pytest, ruff; co-located `test_*.py`; `asyncio.run` for
async tests; inject collaborators (`which`/`rg_runner`/`hash_fn`/`writable`/
`environ`) to keep tests network- and process-free; `@pytest.mark.integration`
only where a real subprocess/loop is genuinely exercised. Guardrail: read-only on
**source** files — the manifest under `.harpyja/` is a sanctioned derived
artifact. `rg` is a hard precondition for **search/locate only**, never `index`.

Reuse verbatim (do not redefine): `harpyja/server/types.py`
(`CodeSpan`/`Citation`/`LocateRequest`/`LocateResult`/`Mode`).
Exact contract string to reproduce: `"Wave 1: deterministic tier only; mode has no effect"`.

## Group A — Packaging + Settings

1. **GREEN — Add `pathspec` dependency.** EXTEND `pyproject.toml`
   `[project].dependencies` → `"pathspec>=0.12"`; `uv sync`/`uv lock`. AC4 enabler. _codex._
2. **RED — Settings has Wave-1 defaults.** EXTEND `harpyja/config/test_settings.py`:
   `test_settings_has_wave1_default_fields` (ignore_globs `()`, follow_symlinks `False`,
   search_max_files `4000`, search_max_matches `400`, rg_chunk_size `512`,
   tool_max_lines `400`, tool_max_chars `20000`, manifest_page `200`, cache_dir `None`). AC1,8,15.
3. **GREEN — Add nine fields.** EXTEND `harpyja/config/settings.py` (frozen, typed defaults). AC1,8,15.
4. **RED — `ignore_globs` coercion.** EXTEND `test_settings.py`:
   `test_coerce_ignore_globs_from_toml_list`, `test_coerce_ignore_globs_from_env_csv`. AC1,4.
5. **GREEN — tuple coercion in `_coerce`.** EXTEND `settings.py`: tuple field → list/tuple→str each;
   str→split on `,`. AC1,4.

## Group B — `prior` heuristic

6. **RED — factors + ordering invariant.** CREATE `harpyja/index/test_prior.py`:
   `test_prior_is_pure_same_input_same_output`,
   `test_prior_vendored_ranks_below_equivalent_source`,
   `test_prior_test_file_ranks_below_source`,
   `test_prior_generated_ranks_below_source`,
   `test_prior_source_dir_bonus_applies`,
   `test_prior_deeper_path_penalized_all_else_equal`. AC7.
7. **GREEN — `prior(path)`.** CREATE `harpyja/index/prior.py`: pure float; depth + test/vendor/
   generated penalties + source-dir bonus; placeholder weights preserve asserted orderings (P5). AC7.

## Group C — Indexer

8. **RED — classify by extension.** CREATE `harpyja/index/test_classify.py`:
   `test_classify_python_extension`, `test_classify_go_extension`,
   `test_classify_unknown_extension_is_none`, `test_classify_extensionless_is_none`. AC5.
9. **GREEN — `classify_language`.** CREATE `harpyja/index/classify.py`. AC5.
10. **RED — ignore matcher.** CREATE `harpyja/index/test_ignore.py`:
    `test_ignore_anchored_vs_floating_globs`, `test_ignore_directory_only_rule`,
    `test_ignore_double_star_glob`, `test_ignore_negation_reinclude`,
    `test_ignore_nested_per_directory_gitignore`, `test_ignore_globs_apply_in_addition`,
    `test_ignore_no_git_invocation` (inject git-runner sentinel that raises). AC4.
11. **GREEN — `ignore.py` via pathspec.** CREATE: layered per-dir `PathSpec` (gitwildmatch) +
    `ignore_globs`; `is_ignored(rel, is_dir)`; no `git` calls. AC4.
12. **RED — walker.** CREATE `harpyja/index/test_walk.py`:
    `test_walk_yields_non_ignored_files`, `test_walk_skips_symlinks_when_follow_false`,
    `test_walk_descends_unignored_dirs_only`. AC4,6a.
13. **GREEN — `walk()`.** CREATE `harpyja/index/walk.py`: generator; prune ignored dirs; skip symlinks. AC4,6a.
14. **RED — hashing.** CREATE `harpyja/index/test_hash.py`:
    `test_hash_file_sha256_prefixed`, `test_hash_file_stable_for_same_content`. AC1.
15. **GREEN — `hash_file()`.** CREATE `harpyja/index/hash.py`: streaming sha256, `"sha256:…"`. AC1.
16. **RED — artifact location.** CREATE `harpyja/index/test_artifacts.py`:
    `test_artifact_dir_defaults_to_repo_dot_harpyja`,
    `test_artifact_dir_writes_self_ignore_star`,
    `test_artifact_dir_does_not_touch_root_gitignore`,
    `test_artifact_dir_falls_back_to_xdg_cache_when_repo_unwritable` (inject `writable`),
    `test_artifact_dir_repo_hash_is_realpath_sha256_prefix`,
    `test_artifact_dir_fails_when_neither_writable`. AC17.
17. **GREEN — `resolve_artifact_dir`.** CREATE `harpyja/index/artifacts.py`:
    `<repo>/.harpyja/` default; writes `.harpyja/.gitignore`=`*`; XDG fallback
    `${XDG_CACHE_HOME:-~/.cache}/harpyja/<realpath-sha256-prefix>/`; `ArtifactLocationError`. AC17.
18. **RED — manifest write.** CREATE `harpyja/index/test_manifest.py`:
    `test_manifest_line_has_spec_fields`, `test_manifest_ordered_by_prior_desc_then_path`,
    `test_manifest_two_writes_byte_identical`,
    `test_manifest_atomic_temp_in_same_dir_then_rename` (spy `os.replace`, assert same dir). AC18,1.
19. **GREEN — `manifest.py`.** CREATE: `ManifestEntry`; `write_manifest` (sort desc prior/path,
    temp-in-same-dir + `os.replace`); `read_manifest`. AC18,1.
20. **RED — incremental/prune/rehash.** CREATE `harpyja/index/test_indexer.py`:
    `test_index_unchanged_file_not_rehashed` (counting `hash_fn`),
    `test_index_changed_size_triggers_rehash`, `test_index_changed_mtime_triggers_rehash`,
    `test_index_prunes_deleted_file_entry`, `test_index_rehash_ignores_mtime_size_gate`,
    `test_index_null_language_file_still_indexed`. AC2,3,5,6b.
21. **GREEN — `index_repo()`.** CREATE `harpyja/index/indexer.py`: walk → `(mtime,size)` gate vs prior
    manifest (skip unless rehash) → entries (`prior`,`classify`,`hash_file`) → prune → `write_manifest`. AC2,3,5,6b.
22. **RED — IndexResult shape.** EXTEND `test_indexer.py`:
    `test_index_result_shape_matches_spec`, `test_index_languages_sum_le_files_indexed`. AC6.
23. **GREEN — IndexResult.** EXTEND `indexer.py`: `{files_indexed, symbols_indexed:0, languages,
    elapsed_ms, degraded:[]}`; languages counts non-null; timed. AC6.

## Group D — RipgrepEngine

24. **RED — bounded literal search.** CREATE `harpyja/symbols/test_ripgrep.py`:
    `test_search_returns_codespans_for_literal_match`,
    `test_search_treats_query_as_literal_by_default` (asserts `--fixed-strings`),
    `test_search_caps_at_search_max_matches`, `test_search_caps_at_search_max_files`,
    `test_search_passes_rg_chunk_size`. Inject `rg_runner`. AC8.
25. **GREEN — `RipgrepEngine.search`.** CREATE `harpyja/symbols/ripgrep.py`: `rg --json
    --fixed-strings`; single-line spans; bounds; scope-confined. AC8.
26. **RED — rg-missing error.** EXTEND `test_ripgrep.py`:
    `test_search_missing_rg_raises_typed_actionable_error` (inject `which`→None). AC9.
27. **GREEN — `RipgrepMissingError`.** EXTEND `ripgrep.py`: raise actionably when `rg` absent. AC9.

## Group E — `harpyja_read`

28. **RED — bounded read.** CREATE `harpyja/server/test_read_tool.py`:
    `test_read_returns_spec_shape`, `test_read_one_indexed_inclusive_range`,
    `test_read_clamps_tool_max_lines_sets_truncated`,
    `test_read_clamps_tool_max_chars_sets_truncated`,
    `test_read_not_truncated_when_within_bounds`. AC15.
29. **GREEN — `read_snippet`.** EXTEND `harpyja/server/tools.py`: 1-indexed inclusive; clamp lines/chars;
    returned start/end = actual; language via `classify_language`. AC15.
30. **RED — path confinement.** EXTEND `test_read_tool.py`:
    `test_read_rejects_parent_traversal`, `test_read_rejects_in_repo_symlink_escaping_repo`. AC16.
31. **GREEN — realpath confinement.** EXTEND `tools.py`: resolve realpath within `repo_path`;
    `PathConfinementError`; shared helper (also for search scope). AC16.

## Group F — Citation Formatter

32. **RED — formatter.** CREATE `harpyja/orchestrator/test_formatter.py`:
    `test_formatter_dedupes_identical_spans`, `test_formatter_merges_overlapping_same_file_spans`,
    `test_formatter_merges_adjacent_same_file_spans`, `test_formatter_does_not_merge_different_files`,
    `test_formatter_ranks_by_prior_then_match_density`,
    `test_formatter_stable_tiebreak_on_path_then_start_line`,
    `test_formatter_clamps_to_max_results`. AC14,11.
33. **GREEN — `format_citations`.** CREATE `harpyja/orchestrator/format.py`. AC14,11.

## Group G — Orchestrator locate + ensure-index

34. **RED — Tier-0 locate + ensure-index.** CREATE `harpyja/orchestrator/test_locate.py`:
    `test_locate_returns_file_line_citations_tier0`, `test_locate_ensures_index_when_no_manifest`,
    `test_locate_reflects_added_file_without_explicit_reindex`,
    `test_locate_reflects_deleted_file_via_prune`. Inject fake engine + real indexer over tmp_path. AC10.
35. **GREEN — `locate()`.** CREATE `harpyja/orchestrator/locate.py`: ensure-index (incremental) →
    engine search → formatter → `tiers_run=[0]`, confidence. AC10.
36. **RED — max_results clamp.** EXTEND `test_locate.py`: `test_locate_never_exceeds_max_results`. AC11.
37. **GREEN — clamp.** EXTEND `locate.py`: pass `max_results` to formatter (mandatory). AC11.
38. **RED — mode accept-validate-flag.** EXTEND `test_locate.py`:
    `test_locate_invalid_mode_rejected`, `test_locate_valid_mode_sets_no_effect_note`. AC12.
39. **GREEN — mode handling.** EXTEND `locate.py`: validate against `Mode`; set fixed note. AC12.
40. **RED — language_hint.** EXTEND `test_locate.py`:
    `test_locate_language_hint_filters_to_matching_language`,
    `test_locate_null_language_excluded_under_hint`,
    `test_locate_null_language_returned_without_hint`,
    `test_locate_unrecognized_hint_note`, `test_locate_null_language_exclusion_note`,
    `test_locate_hint_notes_are_distinct_not_collapsed`. AC13.
41. **GREEN — language_hint handling.** EXTEND `locate.py`: filter by manifest language;
    distinct notes; recognized-language set. AC13.
42. **REFACTOR — extract helpers.** `locate.py` `_compose_notes` + filter helpers; tests stay green. _codex._

## Group H — MCP tool registration

43. **RED — register index/read; locate Tier 0.** EXTEND `harpyja/server/test_app.py`:
    `test_build_app_registers_harpyja_index`, `test_build_app_registers_harpyja_read`,
    `test_build_app_index_tool_returns_summary_shape`, `test_build_app_read_tool_returns_snippet_shape`,
    `test_build_app_locate_tool_runs_tier0`. AC6,10,15.
44. **GREEN — register tools.** EXTEND `harpyja/server/app.py`: register `harpyja_index`/`harpyja_read`;
    repoint `harpyja_locate` at orchestrator (real `RipgrepEngine` via `shutil.which`/subprocess). AC6,10,15.
45. **RED — rg-missing through locate tool.** EXTEND `test_app.py`:
    `test_build_app_locate_reports_rg_missing_actionably` (inject `which`→None); index still succeeds. AC9.
46. **GREEN — surface rg-missing.** EXTEND `app.py`: injectable `which`/engine factory in `build_app(...)`;
    locate propagates `RipgrepMissingError` as actionable MCP error; index independent of `rg`. AC9.

## Group I — CLI subcommands

47. **RED — CLI index/locate/read.** EXTEND `harpyja/test_cli.py`:
    `test_cli_index_invokes_indexer_with_repo`, `test_cli_index_rehash_flag_passed`,
    `test_cli_locate_passes_query_mode_maxresults_langhint`,
    `test_cli_read_passes_path_start_end`, `test_cli_index_prints_summary`. AC1,6b,10,12,13,15.
48. **GREEN — subcommands.** EXTEND `harpyja/cli.py`: `index` (`--repo`,`--rehash`),
    `locate` (`--query/--repo/--mode/--max-results/--language-hint`),
    `read` (`--repo/--path/--start/--end`) + dispatch; print summary/JSON. AC1,6b,10,12,13,15.

## Group J — Final gate

49. **RED — retire stub-note expectations.** EXTEND `harpyja/server/test_locate_tool.py`:
    `test_locate_no_longer_returns_wave0_stub_note` (update old stub assertions to Tier-0 contract). AC10,12.
50. **GREEN — retire `locate_stub`.** EXTEND `harpyja/server/tools.py`: remove/deprecate the dead stub. AC10.
51. **REFACTOR — full gate.** `ruff check --fix`, `ruff format`, full `uv run pytest` (incl. `-m integration`);
    de-dup `index/` helpers. Regression gate over all ACs. _codex._

## Delegation
- Steps **1, 42, 51** → codex (packaging, lint/format, refactor, test gate).
- All RED/GREEN logic steps require contract judgement — not mechanical.

## Risks & mitigations
- **Toml table-headers vs flat keys.** SPEC §5 shows `[search]/[tools]/[index]` tables; Wave 0 `Settings`
  is flat keys mirroring field names. Plan keeps flat fields (consistent with Wave 0); if nested tables are
  needed later, add a flattening layer in `_from_toml` behind its own RED test — never retrofit silently.
- **Integration-marker creep.** Inject `rg_runner`/`which`/engine so Groups D/G/H stay unit-level; reserve
  `@pytest.mark.integration` for steps 34/45 only if a real subprocess/loop is exercised.
- **`mtime` granularity gate miss (R5).** `--rehash` escape hatch is its own AC (6b)/test (step 20).
- **Atomicity test fragility.** Spy `os.replace`; assert dir equality only, not exact temp filename.
- **Artifact-write guardrail.** Writing `<repo>/.harpyja/` is the sanctioned derived-artifact exception;
  all FS tests use `tmp_path`; confinement tests assert source read-only posture.
