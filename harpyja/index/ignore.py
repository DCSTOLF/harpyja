"""`.gitignore` + `ignore_globs` matching, without invoking `git` (AC4).

Uses `pathspec`'s `gitwildmatch` engine. Nested per-directory `.gitignore` files
are evaluated hierarchically: for a given path, each ancestor directory's spec is
applied shallowest-first, a deeper spec (or a negation) overriding a shallower
decision. Configured `ignore_globs` are applied last, additively, at repo scope.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path, PurePosixPath

import pathspec

_GITIGNORE = ".gitignore"


class IgnoreMatcher:
    """Hierarchical gitignore matcher. ``specs`` are (dir_relposix, spec)."""

    def __init__(
        self,
        specs: list[tuple[str, pathspec.GitIgnoreSpec]],
        extra: pathspec.GitIgnoreSpec | None,
    ) -> None:
        # Shallowest first so deeper specs override.
        self._specs = sorted(specs, key=lambda ds: ds[0].count("/") if ds[0] else -1)
        self._extra = extra

    def is_ignored(self, rel_path: str, is_dir: bool = False) -> bool:
        rel = PurePosixPath(rel_path)
        # gitignore directory-only rules need a trailing slash to match a dir.
        ignored = False

        for spec_dir, spec in self._specs:
            sub = self._relative_to(rel, spec_dir)
            if sub is None:
                continue
            ignored = self._apply(spec, sub, is_dir, ignored)

        if self._extra is not None:
            ignored = self._apply(self._extra, str(rel), is_dir, ignored)

        return ignored

    @staticmethod
    def _relative_to(rel: PurePosixPath, spec_dir: str) -> str | None:
        if not spec_dir:
            return str(rel)
        prefix = spec_dir + "/"
        s = str(rel)
        if s == spec_dir or s.startswith(prefix):
            return s[len(prefix) :] if s.startswith(prefix) else ""
        return None

    @staticmethod
    def _apply(spec: pathspec.GitIgnoreSpec, sub: str, is_dir: bool, current: bool) -> bool:
        if not sub:
            return current
        candidate = sub + "/" if is_dir and not sub.endswith("/") else sub
        result = spec.check_file(candidate)
        if result.include is True:
            return True
        if result.include is False:
            return False
        return current


def build_ignore(repo_root: str | Path, extra_globs: Sequence[str] = ()) -> IgnoreMatcher:
    """Build an :class:`IgnoreMatcher` for ``repo_root``.

    Collects every `.gitignore` under the root (skipping `.git/`) and combines it
    with the configured ``extra_globs``. Never invokes `git`.
    """
    root = Path(repo_root)
    specs: list[tuple[str, pathspec.GitIgnoreSpec]] = []

    for gitignore in root.rglob(_GITIGNORE):
        if ".git" in gitignore.relative_to(root).parts:
            continue
        rel_dir = gitignore.parent.relative_to(root)
        dir_key = "" if rel_dir == Path(".") else rel_dir.as_posix()
        lines = gitignore.read_text(encoding="utf-8", errors="ignore").splitlines()
        specs.append((dir_key, pathspec.GitIgnoreSpec.from_lines(lines)))

    extra = pathspec.GitIgnoreSpec.from_lines(extra_globs) if extra_globs else None
    return IgnoreMatcher(specs, extra)
