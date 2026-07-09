"""Bounded ripgrep search engine (AC8, AC9).

Returns `CodeSpan`s for literal matches. The query is treated as a **literal
string** (`--fixed-strings`) by default. Results are bounded by
`search_max_matches` and `search_max_files`. `rg` is a hard precondition: if it
is absent from `PATH`, `search` raises :class:`RipgrepMissingError` (an honest,
actionable failure — never a silent empty result).

The `rg_runner` is injectable (`(args) -> stdout`) so the engine is unit-testable
without spawning a process.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from harpyja.config.settings import Settings
from harpyja.server.types import CodeSpan

RgRunner = Callable[[list[str]], str]
Which = Callable[[str], str | None]


class RipgrepMissingError(RuntimeError):
    """Raised when the `rg` binary is not available for search/locate."""


def _default_runner_factory(scope: str) -> RgRunner:
    def runner(args: list[str]) -> str:
        proc = subprocess.run(
            ["rg", *args],
            cwd=scope,
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.stdout

    return runner


class RipgrepEngine:
    def __init__(
        self,
        settings: Settings,
        rg_runner: RgRunner | None = None,
        which: Which = shutil.which,
    ) -> None:
        self._settings = settings
        self._rg_runner = rg_runner
        self._which = which

    def search(
        self,
        pattern: str,
        scope: str | None = None,
        *,
        repo_root: str | None = None,
    ) -> list[CodeSpan]:
        """Bounded literal search.

        Without ``repo_root`` (the legacy path) the invocation and the parse are
        byte-identical to the pre-0033 engine: rg runs with cwd=scope and paths
        are returned verbatim (cwd-relative).

        With ``repo_root`` (spec 0033) the output contract is REPO-RELATIVE
        paths regardless of the scope passed: rg still runs with cwd=scope (the
        invocation is unchanged for directory scopes — mechanism (b), parse-side
        re-prefix), and parsed paths are re-prefixed with the scope's
        repo-relative prefix. A FILE scope (the `symbols` degraded-fallback
        shape) runs from the file's parent with the filename as an rg path
        argument — supported, never a NotADirectoryError crash.
        """
        if self._which("rg") is None:
            raise RipgrepMissingError(
                "ripgrep (rg) is required for search but was not found on PATH; "
                "install ripgrep or run `harpyja doctor` to diagnose"
            )

        rel_prefix: str | None = None
        path_arg: str | None = None
        if repo_root is not None:
            root = Path(repo_root).resolve()
            scoped = Path(scope).resolve() if scope else root
            if scoped.is_file():
                cwd = scoped.parent
                path_arg = scoped.name
            else:
                cwd = scoped
            try:
                rel_prefix = str(cwd.relative_to(root))
            except ValueError:
                rel_prefix = None  # scope outside repo_root — verbatim parse
            scope = str(cwd)

        scope = scope or "."
        runner = self._rg_runner or _default_runner_factory(scope)
        args = [
            "--json",
            "--fixed-strings",
            f"--max-columns={self._settings.rg_chunk_size}",
            pattern,
        ]
        if path_arg is not None:
            args.append(path_arg)
        stdout = runner(args)
        return self._parse(stdout, rel_prefix=rel_prefix)

    def _parse(self, stdout: str, rel_prefix: str | None = None) -> list[CodeSpan]:
        spans: list[CodeSpan] = []
        files: set[str] = set()
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("type") != "match":
                continue
            data = obj["data"]
            path = data["path"]["text"]
            line_no = data["line_number"]
            if rel_prefix is not None:
                # Spec 0033: re-prefix the cwd-relative rg path to repo-relative
                # (normpath collapses '.' and './' artifacts). The legacy
                # (rel_prefix=None) parse stays verbatim.
                path = os.path.normpath(os.path.join(rel_prefix, path))

            if path not in files and len(files) >= self._settings.search_max_files:
                continue  # new file beyond the file cap — skip
            files.add(path)

            spans.append(CodeSpan(path=path, start_line=line_no, end_line=line_no))
            if len(spans) >= self._settings.search_max_matches:
                break
        return spans
