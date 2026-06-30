---
spec: "0002-wave-1-deterministic-core"
title: "Wave 1 — Deterministic core (indexer + ripgrep)"
closed: 2026-06-26
---

# Changelog — 0002 Wave 1 — Deterministic core (indexer + ripgrep)

## What shipped vs spec

Replaced the Wave 0 `harpyja_locate` stub with a genuinely working, model-free
deterministic locator: index a repo, search it with ripgrep, and return real
`file:line` citations with zero model calls and zero network egress. The full
indexer → search → formatter → citation path is live end-to-end behind the
existing MCP contract. All 20 acceptance criteria are met; implementation was
strictly TDD (RED→GREEN→REFACTOR) across all 51 plan tasks.

### Acceptance-criteria coverage (all 20)

- **AC1** — `harpyja_index` walks honoring `.gitignore` (no `git` invocation) +
  `ignore_globs`, writes `manifest.jsonl` with `path/language/size/hash/mtime/prior`.
  (`index/indexer.py`, `index/manifest.py`)
- **AC2** — Incremental `(mtime, size)` gate reuses unchanged entries without
  re-hashing; changed `mtime` *or* `size` triggers re-hash. (`index/indexer.py`)
- **AC3** — Pruning: deleted/renamed files drop out of the manifest on refresh.
- **AC4** — `.gitignore` via `pathspec` gitwildmatch: negation, dir-only, anchored
  vs floating, `**`, nested per-dir files; `ignore_globs` apply in addition; a
  sentinel test asserts no `git` is invoked. (`index/ignore.py`)
- **AC5** — Language classified by extension; unknown/extensionless → `None`, still
  indexed. (`index/classify.py`)
- **AC6** — `IndexResult` = `{files_indexed, symbols_indexed:0, languages, elapsed_ms,
  degraded:[]}`; `sum(languages.values()) <= files_indexed`. (`index/indexer.py`)
- **AC6a** — Symlinks skipped during the walk under `follow_symlinks=false`. (`index/walk.py`)
- **AC6b** — `--rehash` re-hashes every file, ignoring the gate.
- **AC7** — `prior` = depth + test/vendor/generated penalties + source-dir bonus;
  pure; placeholder weights preserve the ACs' orderings. (`index/prior.py`)
- **AC8** — `RipgrepEngine.search` returns `CodeSpan`s for a literal string
  (`--fixed-strings`), single-line span (`start==end`), bounded by
  `search_max_files`/`search_max_matches`. (`symbols/ripgrep.py`)
- **AC9** — `rg` absent → `RipgrepMissingError` (typed, names ripgrep) on
  search/locate; `harpyja_index` succeeds without `rg`; `doctor` reports absence.
- **AC10** — `harpyja_locate` returns correct `file:line` citations, `tiers_run==[0]`,
  zero model calls; ensure-index runs an incremental refresh first (reflects
  add/modify/delete; builds from scratch when no manifest). (`orchestrator/locate.py`)
- **AC11** — `max_results` is a mandatory clamp (via the formatter).
- **AC12** — Invalid `mode` rejected; valid `mode` accepted but flagged inert with
  the fixed note `"Wave 1: deterministic tier only; mode has no effect"`.
- **AC13** — `language_hint` filters by manifest language; null-language files
  excluded under a hint, returned without one; unrecognized-hint vs
  null-language-exclusion surfaced as *distinct* notes.
- **AC14** — Formatter dedupes, merges overlapping/adjacent same-file spans, ranks
  by `prior` + match density, stable tie-break on `(path, start_line)`. (`orchestrator/format.py`)
- **AC15** — `harpyja_read` returns `{path,start,end,language,content,truncated}`,
  1-indexed inclusive, clamped to `tool_max_lines`/`tool_max_chars`, returned range
  = actual clamped range. (`server/tools.py`)
- **AC16** — Path confinement: `realpath` must lie within `repo_path`; rejects `../`
  and escaping in-repo symlinks via `confine_path`/`PathConfinementError`. (`server/tools.py`)
- **AC17** — Artifacts default to `<repo>/.harpyja/` with self-ignoring
  `.gitignore`=`*` (root `.gitignore` untouched); fall back to
  `${XDG_CACHE_HOME:-~/.cache}/harpyja/<repo-hash>/` (sha256 prefix of abs realpath)
  when the repo is unwritable; `ArtifactLocationError` when neither is. (`index/artifacts.py`)
- **AC18** — Deterministic manifest: byte-identical across two indexes of an
  unchanged tree (sorted desc `prior` then `path`); same-dir temp + `os.replace`. (`index/manifest.py`)

## Deviations from spec

- **Flat toml keys, not §5 table headers.** Config keeps flat keys mirroring
  `Settings` field names (Wave 0 convention), not SPEC §5's `[search]`/`[tools]`/
  `[index]` tables. Flagged as a risk in plan.md; flat kept for consistency. A
  future nested-table need should add a flattening layer behind its own test.
- **Graceful rg-missing CLI handling added beyond the 51 tasks.** Smoke testing
  surfaced a raw traceback when `rg` was absent; `cli.py locate` now catches
  `RipgrepMissingError` → clean stderr message + exit 2 (no traceback). Has its
  own test.
- **`mtime` stored as float `st_mtime`** (finer than SPEC's integer example);
  `--rehash` is the documented escape hatch for the coarse-granularity same-second/
  same-size edge (R5).
- **Repo's own `.harpyja/` is git-invisible** via the self-ignoring `.gitignore`
  (verified); root `.gitignore` untouched.

## Files touched (37 files, ~2000 insertions)

New runtime dependency: `pathspec` (>=0.12).

- `harpyja/index/` — `prior.py`, `classify.py`, `ignore.py`, `walk.py`, `hash.py`,
  `artifacts.py`, `manifest.py`, `indexer.py` (+ co-located `test_*.py`)
- `harpyja/symbols/` — `ripgrep.py` (+ `test_ripgrep.py`)
- `harpyja/orchestrator/` — `format.py`, `locate.py` (+ `test_*.py`)
- `harpyja/server/` — `tools.py` (`read_snippet`, `confine_path`,
  `PathConfinementError`; `locate_stub` removed), `app.py`
  (`build_app(settings, *, which, engine_factory)` registers
  `harpyja_index`/`harpyja_read`/`harpyja_locate`) (+ updated tests)
- `harpyja/config/settings.py` — +9 frozen fields; `_coerce` tuple/CSV handling
- `harpyja/cli.py` — `index` (`--rehash`), `locate`, `read` subcommands
- `pyproject.toml` — `pathspec` dependency

## Test & lint status

- 141 tests pass (including 1 stdio integration test).
- `ruff check` / `ruff format` clean.
- Review: 2 rounds, ended **approve-with-comments** (quorum met). R1–R11 folded
  into the spec before planning; both of codex's flagged guardrail/convention
  violations were adjudicated false positives (derived-artifact exception; rg
  hard-fail is the honest posture).
