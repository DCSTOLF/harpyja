# Server domain

Consolidated, current requirements for the FastMCP server, its transports, and
tool registration. Each line carries its originating spec(s) as provenance.

- `harpyja serve --stdio` and `harpyja serve --http` both register `harpyja_locate`, returning the `LocateResult` shape per `SPEC.md §2.1`. (spec 0001)
- `--http` binds loopback (`127.0.0.1`) only by default; binding any non-loopback interface requires an explicit opt-out. (spec 0001)
- The stdio transport keeps stdout clean (MCP protocol frames only); all logs go to stderr. (spec 0001)
- `harpyja_read(path, start, end)` returns `{path, start, end, language, content, truncated}` clamped to `tool_max_lines` (400) and `tool_max_chars` (20000); `start`/`end` are 1-indexed and `end`-inclusive, the returned range is the actual (clamped) range, and `truncated` is true exactly when clamping occurred. (spec 0002)
- `harpyja_read` and search enforce path confinement: the resolved real path (`realpath`, following symlinks) must lie within `repo_path`; `../` traversal and in-repo symlinks resolving outside the repo are rejected. (spec 0002)
- `CodeSpan` line fields are `start_line: int | None` / `end_line: int | None` with `None` meaning file-level (no line range); a span is either both-int or both-`None` — a half-`None` span is rejected at the parse/normalize boundary. (spec 0011)
- `confine_path`'s NON-STRICT resolve — a nonexistent in-repo path passes confinement without raising — is pinned by a fixture in `harpyja/server/test_tools.py`, so the contract the scope-marker branches' `exists()` guard depends on cannot silently switch to strict/exists-enforcing (spec 0035)
