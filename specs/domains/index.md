# Index domain

Consolidated, current requirements for the file walker, language classification,
manifest format, incremental change detection, and artifact placement. Each line
carries its originating spec(s) as provenance.

- The indexer walks a repo respecting `.gitignore` (matched via `pathspec` `gitwildmatch` without invoking `git`, including negation, anchored/floating globs, `**`, directory-only rules, and nested per-directory files) plus configured `ignore_globs` applied after it; non-git directories index correctly. (spec 0002)
- Each file's language is classified by extension (unknown/extensionless → `null`); `null`-language files are still indexed and (when not binary) searchable. (spec 0002)
- The indexer writes `manifest.jsonl` — one JSON object per line with `path` (repo-relative), `language`, `size`, `hash` (`"sha256:…"`), `mtime`, and `prior`. (spec 0002)
- Incremental change detection: a file whose `(mtime, size)` match the prior manifest entry is reused without re-hashing; a file whose `mtime` or `size` changed is re-hashed and re-indexed (the hash is the change-of-record, `(mtime, size)` only the cheap gate). (spec 0002)
- `harpyja_index --rehash` forces a full reindex ignoring the `(mtime, size)` gate — the escape hatch for a same-second, same-size content edit the gate would otherwise miss. (spec 0002)
- On refresh the indexer prunes manifest entries for files no longer on disk (a rename is delete + add), so the manifest never cites a path that no longer exists. (spec 0002)
- With `follow_symlinks=false`, symbolic links are skipped during the walk and never appear in the manifest. (spec 0002)
- The manifest is written in a stable order (descending `prior`, tie-broken by `path`) so repeated indexes of an unchanged tree produce byte-identical files. (spec 0002)
- The manifest is written via a same-directory temp file + atomic `rename`, so a crash mid-refresh can't leave a truncated file. (spec 0002)
- `prior` is a pure deterministic function of path depth, test/vendor/generated penalties, and source-dir bonus; placeholder weights must preserve the asserted ordering (vendored/test below an equivalent source file). (spec 0002)
- `harpyja_index` returns `{files_indexed, symbols_indexed, languages: {<lang>: <count>}, elapsed_ms, degraded}`; `null`-language files count toward `files_indexed` but not the `languages` map (so `sum(languages.values()) <= files_indexed`). (spec 0002)
- `harpyja_index` requires no `rg` — walking, hashing, and manifest writing are pure Python and succeed without ripgrep on PATH. (spec 0002)
- Index artifacts default to `<repo>/.harpyja/`, which self-ignores via a one-line `.harpyja/.gitignore` containing `*`; the repo's root `.gitignore` is never modified. (spec 0002)
- When `<repo>` is not writable, index artifacts fall back to `${XDG_CACHE_HOME:-~/.cache}/harpyja/<repo-hash>/` where `<repo-hash>` is a SHA-256 prefix of the repo's absolute realpath; only if neither location is writable does indexing fail with a clear error. (spec 0002)
