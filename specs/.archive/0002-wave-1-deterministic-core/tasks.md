---
id: "0002"
title: "Wave 1 — Deterministic core (indexer + ripgrep)"
plan: specs/0002-wave-1-deterministic-core/plan.md
created: 2026-06-26
---

# Tasks 0002 — Wave 1 — Deterministic core (indexer + ripgrep)

Execution order. Every RED precedes its GREEN. See `plan.md` for detail.

- [x] 1.  GREEN: Add pathspec runtime dependency to pyproject  (codex)
- [x] 2.  RED:   Settings has Wave-1 default fields
- [x] 3.  GREEN: Add nine Wave-1 fields to Settings
- [x] 4.  RED:   ignore_globs tuple/list (toml) + csv (env) coercion
- [x] 5.  GREEN: _coerce handles tuple field type
- [x] 6.  RED:   prior factors + ordering invariant
- [x] 7.  GREEN: prior() pure heuristic
- [x] 8.  RED:   language classify by extension
- [x] 9.  GREEN: classify_language()
- [x] 10. RED:   gitignore/ignore_globs matcher (negation, nested, dir-only, no git)
- [x] 11. GREEN: ignore matcher via pathspec
- [x] 12. RED:   walker skips symlinks, respects ignore
- [x] 13. GREEN: walk()
- [x] 14. RED:   sha256 file hashing
- [x] 15. GREEN: hash_file()
- [x] 16. RED:   artifact dir resolution + self-ignore + XDG fallback
- [x] 17. GREEN: resolve_artifact_dir()
- [x] 18. RED:   manifest line shape + deterministic order + atomic rename
- [x] 19. GREEN: write_manifest/read_manifest
- [x] 20. RED:   incremental (no re-hash) + changed re-hash + prune + rehash
- [x] 21. GREEN: index_repo() core
- [x] 22. RED:   IndexResult summary shape + languages sum<=files_indexed
- [x] 23. GREEN: IndexResult summary
- [x] 24. RED:   ripgrep search literal/bounded/single-line CodeSpans
- [x] 25. GREEN: RipgrepEngine.search
- [x] 26. RED:   rg-missing typed actionable error
- [x] 27. GREEN: RipgrepMissingError precondition
- [x] 28. RED:   read snippet shape + 1-indexed inclusive + clamp/truncated
- [x] 29. GREEN: read_snippet()
- [x] 30. RED:   path confinement (../ + escaping symlink)
- [x] 31. GREEN: realpath confinement
- [x] 32. RED:   formatter dedupe/merge/rank/tiebreak/clamp
- [x] 33. GREEN: format_citations()
- [x] 34. RED:   Tier-0 locate citations + ensure-index reflects add/delete
- [x] 35. GREEN: locate() core, tiers_run=[0]
- [x] 36. RED:   locate never exceeds max_results
- [x] 37. GREEN: max_results mandatory clamp
- [x] 38. RED:   mode invalid rejected / valid sets no-effect note
- [x] 39. GREEN: mode accept-validate-flag
- [x] 40. RED:   language_hint filter + distinct unrecognized/null-exclusion notes
- [x] 41. GREEN: language_hint handling
- [x] 42. REFACTOR: extract notes/filter helpers in locate  (codex)
- [x] 43. RED:   app registers index/read; locate runs Tier 0
- [x] 44. GREEN: register tools + repoint locate in build_app
- [x] 45. RED:   locate surfaces rg-missing; index succeeds without rg
- [x] 46. GREEN: thread which/engine factory through build_app
- [x] 47. RED:   CLI index/locate/read parse + dispatch (+ --rehash)
- [x] 48. GREEN: CLI subcommands
- [x] 49. RED:   retire wave-0 stub-note expectations
- [x] 50. GREEN: remove/deprecate locate_stub
- [x] 51. REFACTOR: ruff fix/format + full pytest gate  (codex)
