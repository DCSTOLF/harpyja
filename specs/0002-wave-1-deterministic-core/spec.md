---
id: "0002"
title: "Wave 1 — Deterministic core (indexer + ripgrep)"
status: closed
created: 2026-06-26
authors: [claude]
packages: ["harpyja"]
related-specs: ["0001-wave-0-foundations"]
---

# Spec 0002 — Wave 1 — Deterministic core (indexer + ripgrep)

## Why

Wave 1 turns the Wave 0 skeleton into a genuinely useful, **model-free** locator:
index a repo and answer point lookups via ripgrep, returning real `file:line`
citations with zero model cost and zero network egress. This is the deterministic
floor Harpyja degrades to forever after — every later tier (Scout, Deep, the
verification gate) is additive on top of it. Shipping it proves the
indexer → search → formatter → citation path end-to-end, and replaces the Wave 0
`harpyja_locate` stub with something that actually finds code.

## What

The deterministic core: an indexer, a bounded ripgrep engine, bounded reads, a
citation formatter, and a Tier-0-only orchestrator behind the existing
`harpyja_locate` contract.

- **Indexer** (`index/`): a walker that respects `.gitignore` **and** the
  configured `ignore_globs`, classifies each file's language **by extension**
  (unknown/extensionless → `null`), and writes a ranked manifest
  `manifest.jsonl` — one object per line: `path` (repo-relative), `language`,
  `size`, `hash` (`"sha256:…"`), `mtime`, `prior`. `follow_symlinks=false`.
  Exposed as the `harpyja_index` tool + CLI.
  - **`.gitignore` via `pathspec`** (B3): matched **without invoking `git`** using
    the `pathspec` library's `gitwildmatch` — supporting negation (`!`), anchored
    and floating globs, `**`, directory-only rules, and **nested per-directory**
    `.gitignore` files. Configured `ignore_globs` are applied in addition to (and
    after) `.gitignore`. Non-git directories index correctly.
  - **Incremental change detection** (B1): a two-level scheme — a file whose
    `(mtime, size)` match the prior manifest entry is **not re-hashed** and its
    entry is reused; a file whose `mtime` *or* `size` changed is re-hashed and
    re-indexed. The hash is the change-of-record; `(mtime, size)` is only the
    cheap gate that avoids re-hashing. **Known approximation** (R5): a
    same-second, same-size content edit (coarse `mtime` granularity) can be missed
    by the gate; `harpyja_index --rehash` (full reindex, ignore the gate) is the
    escape hatch and is documented as such.
  - **Pruning** (B2): on refresh, manifest entries for files no longer present on
    disk (deleted or renamed) are **removed**, so the manifest never cites a path
    that no longer exists. (A rename is a delete + add.)
  - **Symlinks** (R11): with `follow_symlinks=false`, symbolic links are **skipped
    during the walk** and never appear in the manifest.
  - **Deterministic order** (R8): the manifest is written in a stable order —
    descending `prior`, tie-broken by `path` — so repeated indexes of an unchanged
    tree produce byte-identical files and stable diffs.
  - **Atomic write** (P4 / R4): the manifest is written to a temp file **in the
    same directory** as the final `manifest.jsonl` and `rename`d into place (so
    the rename is atomic on one filesystem — important for the external-cache
    fallback); a crash mid-refresh can't leave a truncated file.
- **`prior` heuristic:** the full factor set — path depth, test/vendor/generated
  penalties, source-dir bonus (SPEC §4.1) — as a pure, deterministic, documented
  function. The factor *structure* ships now; the weight *numbers* are placeholder
  and tuned later. **Invariant** (P5): placeholder weights MUST preserve the
  ordering the ACs assert (e.g. vendored/test < equivalent source), so a future
  re-tune can't silently break ranking.
- **RipgrepEngine** (`symbols/`): bounded search returning `CodeSpan`s, honoring
  `search_max_files`, `search_max_matches`, `rg_chunk_size`. Confined to
  `repo_path`. The query is treated as a **literal string by default** (regex
  metacharacters matched literally); a validated regex mode is deferred (P1). A
  single-line match yields `start_line == end_line` with no surrounding context
  lines (P3). **`rg` precondition** (B4 / R1): `rg` on `PATH` is required for
  **search/locate only** — `harpyja_locate` fails with a clear, typed, actionable
  error naming ripgrep (not a silent empty result) when `rg` is missing, and
  `doctor` reports its absence. `harpyja_index` does **not** require `rg` (walking
  + hashing + manifest are pure Python) and succeeds without it. This hard-fail
  (rather than a degraded answer) is deliberate: ripgrep is the Wave-1 floor, so
  when it is absent there is no honest degraded result to return — failing loudly
  beats a silent empty list that reads as "nothing found" (R10).
- **`harpyja_read`:** bounded snippet reads returning
  `{path, start, end, language, content, truncated}`, clamped to `tool_max_lines`
  (400) and `tool_max_chars` (20000); `truncated` flags clamping. **Line
  semantics** (R6): `start`/`end` are **1-indexed and inclusive**; the returned
  `start`/`end` reflect the **actual (clamped)** range read, with `truncated=true`
  when the requested range was narrowed. **Path confinement** (B5): the resolved
  real path (`realpath`, following symlinks) must lie within `repo_path`; `../`
  traversal and in-repo symlinks that escape the repo are rejected.
- **Citation Formatter** (`orchestrator/`): dedupe, merge **overlapping** spans —
  defined as same-file line-range intersection or adjacency (P2) — rank by
  `prior` + match density, then a stable tie-break on `(path, start_line)`, and
  clamp to `max_results`.
- **Orchestrator v0 / `harpyja_locate`:** Tier-0 only (no model, `tiers_run=[0]`).
  **Ensure-index** (R2): before searching, `locate` runs a full incremental
  refresh (the cheap `(mtime, size)` gate means an up-to-date tree costs only a
  walk, not re-hashing) — "stale" is not a separate heuristic; the incremental
  pass *is* the staleness reconciliation, and it builds the manifest from scratch
  when none exists. The three request fields are treated **distinctly**:
  - **`max_results` — mandatory clamp.** Never return more than requested
    (upholds the SPEC guarantee; this is the core anti-context-flooding promise,
    not an optimization).
  - **`mode` — accept, validate, flag (never silent no-op).** Invalid enum values
    are rejected; valid values are accepted but have no routing effect in Wave 1,
    surfaced via `notes: "Wave 1: deterministic tier only; mode has no effect"`
    so `mode=deep` can't masquerade as an escalation that didn't happen.
  - **`language_hint` — honor, best-effort.** Filter candidates by the manifest's
    (approximate, extension-derived) `language`; `null`-language files are
    excluded from a hinted query but available when no hint is given. Two distinct
    cases are surfaced separately in `notes` (R3): an **unrecognized** hint value
    (no manifest language could ever match) → e.g. `language_hint 'X' is not a
    recognized language`; vs. **null-language exclusion** of indexed files →
    `N files skipped: language undetermined` (P6). They are never collapsed into a
    single silent empty result.
- **Artifact location & ignoring** (B6): index artifacts default to
  `<repo>/.harpyja/`; the dir self-ignores via a one-line `.harpyja/.gitignore`
  containing `*`, and the repo's **root `.gitignore` is never modified**. Writing
  `<repo>/.harpyja/` is a **sanctioned exception** to the read-only-locator rule:
  `architecture.md` classifies the manifest/symbol index as *derived* artifacts
  (R10) — Harpyja still never mutates source files. If the repo directory is
  **not writable** (read-only / air-gapped mounts), the indexer falls back to an
  external cache dir resolved as `${XDG_CACHE_HOME:-~/.cache}/harpyja/<repo-hash>/`,
  where `<repo-hash>` is a SHA-256 prefix of the repo's **absolute realpath** (R7);
  only if neither location is writable does it fail with a clear error.

## Acceptance criteria

1. `harpyja_index --repo R` walks `R` honoring `.gitignore` (no `git` invocation)
   and the configured `ignore_globs`, writing `manifest.jsonl`; each line has
   `path` (repo-relative), `language`, `size`, `hash` (`"sha256:…"`), `mtime`,
   `prior`.
2. **Incremental detection** (B1): a file whose `(mtime, size)` match the prior
   manifest entry is reused **without re-hashing**; a file whose `mtime` *or*
   `size` changed is re-hashed and re-indexed (its `hash`/`mtime` update). A test
   asserts no re-hash occurs on the unchanged path.
3. **Pruning** (B2): after a tracked file is deleted (or renamed) on disk, a
   refresh **removes** its manifest entry — no manifest line cites a path that no
   longer exists.
4. **`.gitignore` semantics via `pathspec`** (B3): negation (`!`), directory-only
   rules, anchored vs floating globs, `**`, and a **nested** per-directory
   `.gitignore` are all honored; `ignore_globs` apply in addition. A negated
   re-include and a nested-dir ignore are each covered by a test.
5. Language is classified by extension (`.py`→`python`, `.go`→`go`, …); an
   unknown/extensionless file gets `language = null` and is still indexed and
   (when not binary) searchable.
6. `harpyja_index` returns
   `{files_indexed, symbols_indexed: 0, languages: {<lang>: <count>}, elapsed_ms, degraded: []}`
   — `symbols_indexed` is `0` and `degraded` is empty in Wave 1 (no symbol layer).
   `null`-language files count toward `files_indexed` but not the `languages` map,
   so `sum(languages.values()) <= files_indexed` (R9).
6a. **Symlinks skipped** (R11): with `follow_symlinks=false`, a symlink in the tree
    is not walked and does not appear in the manifest.
6b. **`--rehash`** (R5): `harpyja_index --rehash` re-hashes and re-indexes every
    file, ignoring the `(mtime, size)` gate (the escape hatch for a same-second,
    same-size edit the gate would otherwise miss).
7. **`prior`** is computed from path depth + test/vendor/generated penalties +
   source-dir bonus; a vendored or test file ranks below an otherwise-equivalent
   source file, the function is pure (same input → same `prior`), and the
   placeholder weights preserve that ordering (P5).
8. `RipgrepEngine.search` returns `CodeSpan`s for a known **literal** string
   (regex metacharacters matched literally, P1) with correct `path` and line
   range; a single-line match has `start_line == end_line` (P3); results never
   exceed `search_max_files` / `search_max_matches`.
9. **`rg` precondition** (B4 / R1): with `rg` absent from `PATH`, `harpyja_locate`
   (and search) fail with a clear, typed, actionable error that names ripgrep (not
   a silent empty result), and `doctor` reports the absence — but `harpyja_index`
   **succeeds without `rg`** (pure-Python walk/hash/manifest).
10. `harpyja_locate` on a known string returns correct `file:line` citations with
    **zero model calls** and `tiers_run == [0]`. Before searching it runs an
    incremental refresh: a query right after a file is added/modified/deleted
    reflects that change with no explicit re-index call (R2), and a query with no
    prior manifest builds one from scratch.
11. `harpyja_locate` never returns more than `max_results` citations (mandatory
    clamp), for any query that would otherwise exceed it.
12. `harpyja_locate` with an invalid `mode` is rejected; with a valid `mode` it
    runs Tier 0 and sets `notes` to
    `"Wave 1: deterministic tier only; mode has no effect"`.
13. `harpyja_locate` with a `language_hint` returns only citations in files whose
    manifest `language` matches; `null`-language files are excluded under a hint
    but returned when no hint is given. The two cases are distinguishable in
    `notes` (R3): an **unrecognized** hint value yields a "not a recognized
    language" note, while excluded `null`-language files yield an "N files skipped:
    language undetermined" note (P6) — never a single silent empty result.
14. The Citation Formatter dedupes and merges **overlapping** spans (same-file
    intersecting or adjacent line ranges, P2), orders by `prior` + match density,
    and breaks ties stably on `(path, start_line)`.
15. `harpyja_read(path, start, end)` returns
    `{path, start, end, language, content, truncated}`, clamped to `tool_max_lines`
    / `tool_max_chars`, with `truncated == true` exactly when clamping occurred.
    Lines are **1-indexed, `end` inclusive**; the returned `start`/`end` are the
    **actual (clamped)** range, not the requested one (R6).
16. **Path confinement** (B5): `harpyja_read` and search reject `../` traversal
    **and** an in-repo symlink whose `realpath` resolves outside `repo_path`.
17. **Artifact location** (B6 / R7): indexing writes `<repo>/.harpyja/` with a
    `.harpyja/.gitignore` containing `*`, and does **not** modify the repo's root
    `.gitignore`. When `<repo>` is unwritable, artifacts go to
    `${XDG_CACHE_HOME:-~/.cache}/harpyja/<repo-hash>/` where `<repo-hash>` is a
    SHA-256 prefix of the repo's absolute realpath; only if neither is writable
    does indexing fail with a clear error.
18. **Deterministic manifest** (R8): two indexes of an unchanged tree produce a
    **byte-identical** `manifest.jsonl` — entries ordered by descending `prior`
    then `path` — and the manifest is written via a same-directory temp file +
    atomic `rename` (R4).

## Out of scope

- AST / tree-sitter symbol extraction and `symbols.jsonl` (Wave 2) — Wave 1 keeps
  `symbols_indexed = 0` and `degraded = []`.
- All model tiers and routing: Scout (Wave 3), Deep (Wave 4), verification
  gate / query classifier / escalation (Wave 5).
- Real `mode` routing — only Tier 0 exists, hence the accept-and-flag treatment.
- Embedding/LLM-based ranking — ranking is `prior` + match density only.
- Tuning the `prior` weights — the factors ship now; the numbers are tuned later
  against real repos.
- Following symlinks (`follow_symlinks=false`).
- A validated **regex** search mode — Wave 1 search is literal-only (P1).
- Binary-file *search results* — binary files are recorded in the manifest but
  excluded from search hits (ripgrep's default binary skipping is kept).

## Open questions

_none — the read-only-target artifact location (B6) and the `.gitignore` matcher
(`pathspec`, B3) were resolved during review._
