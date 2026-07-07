"""The read-only navigation tools handed to the explorer loop (spec 0024, +0027).

The model driving the loop is an untrusted caller (same posture as the Deep-tier
RLM host tools in `deep/host_tools.py`). This module builds EXACTLY four bounded,
repo-path-confined, read-only navigation tools — and nothing mutating:

- ``grep(pattern, scope=None)`` — wraps the SAME ``RipgrepEngine`` the Deep
  ``search`` host tool wraps (spec invariant B: one bounded ripgrep source of
  truth, never a second rg surface), clamped by ``search_max_matches``.
- ``glob(pattern)`` — repo-confined path glob, returning **file-level**
  ``CodeSpan`` records (not raw strings), clamped by ``scout_glob_max_paths``.
- ``read_span(path, start, end)`` — the existing bounded ``read_snippet``.
- ``ls(path=".")`` — **spec 0027** — single-directory listing (immediate children
  only), repo-confined, listing files AND directories (dirs suffixed ``/``) so the
  model can discover repo LAYOUT on demand. This is the affordance ``glob`` lacks
  (glob filters out directories), added as a DELIBERATE, reconciled tool-suite
  change when the eager whole-repo context map was removed (push → pull). Clamped
  by ``scout_ls_max_entries``.

The distinct terminal ``submit_citations`` action lives in ``scout/submit.py`` and
is deliberately NOT part of this navigation suite.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from harpyja.config.settings import Settings
from harpyja.server.tools import confine_path, read_snippet
from harpyja.server.types import CodeSpan


class _Search:  # structural: anything with .search(pattern, scope)
    def search(self, pattern: str, scope: str | None = None) -> list[CodeSpan]: ...


def build_explorer_tools(
    repo_path: str,
    settings: Settings,
    *,
    search_engine: _Search,
) -> dict[str, Callable[..., Any]]:
    """Return exactly the three navigation tools, keyed by name."""
    repo_real = Path(repo_path).resolve()

    def grep(pattern: str, scope: str | None = None) -> list[CodeSpan]:
        # Confine the search scope to the repo (rejects an out-of-repo scope) and
        # delegate to the shared engine; clamp defensively on untrusted-loop output.
        scoped = str(confine_path(repo_path, scope)) if scope else repo_path
        spans = search_engine.search(pattern, scope=scoped)
        return spans[: settings.search_max_matches]

    def glob(pattern: str) -> list[CodeSpan]:
        # Repo-confined glob → file-level CodeSpan records. Any match whose realpath
        # escapes the repo (e.g. a `../` pattern or an escaping symlink) is dropped,
        # never surfaced. Deterministic order; bounded by scout_glob_max_paths.
        out: list[CodeSpan] = []
        for match in sorted(repo_real.glob(pattern)):
            if not match.is_file():
                continue
            try:
                real = match.resolve()
                rel = real.relative_to(repo_real)
            except ValueError:
                continue  # escapes the repo root — drop
            if real != repo_real and repo_real not in real.parents:
                continue
            out.append(CodeSpan(path=str(rel), start_line=None, end_line=None))
            if len(out) >= settings.scout_glob_max_paths:
                break
        return out

    def read_span(path: str, start: int, end: int) -> dict[str, Any]:
        return read_snippet(repo_path, path, start, end, settings)

    def ls(path: str = ".") -> list[CodeSpan]:
        # Single-directory listing (immediate children only — the model walks down;
        # NOT a recursive tree, which would re-create the eager-dump risk removed in
        # spec 0027). Repo-confined via confine_path; lists files AND directories
        # (dirs suffixed "/") as file-level CodeSpan records so layout is
        # discoverable. Deterministic order; bounded by scout_ls_max_entries.
        target = Path(confine_path(repo_path, path))
        if not target.is_dir():
            return []  # ls on a file → empty (use read_span for file contents)
        out: list[CodeSpan] = []
        for child in sorted(target.iterdir()):
            try:
                rel = child.resolve().relative_to(repo_real)
            except ValueError:
                continue  # escapes the repo root — drop
            name = f"{rel}/" if child.is_dir() else str(rel)
            out.append(CodeSpan(path=name, start_line=None, end_line=None))
            if len(out) >= settings.scout_ls_max_entries:
                break
        return out

    return {"grep": grep, "glob": glob, "read_span": read_span, "ls": ls}
