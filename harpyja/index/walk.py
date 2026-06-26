"""Walk a repo, yielding repo-relative file paths to index (AC4, AC6a).

Prunes ignored directories (so they are never descended), skips symlinks when
`follow_symlinks=False`, and always skips `.git/`.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from harpyja.index.ignore import IgnoreMatcher

_ALWAYS_SKIP_DIRS = {".git"}


def walk(
    repo_root: str | Path,
    ignore: IgnoreMatcher,
    follow_symlinks: bool = False,
) -> Iterator[str]:
    root = Path(repo_root)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=follow_symlinks):
        base = Path(dirpath)
        rel_base = base.relative_to(root)

        kept_dirs = []
        for d in dirnames:
            if d in _ALWAYS_SKIP_DIRS:
                continue
            full = base / d
            if not follow_symlinks and full.is_symlink():
                continue
            rel = d if rel_base == Path(".") else (rel_base / d).as_posix()
            if ignore.is_ignored(rel, is_dir=True):
                continue
            kept_dirs.append(d)
        dirnames[:] = kept_dirs

        for f in filenames:
            full = base / f
            if not follow_symlinks and full.is_symlink():
                continue
            rel = f if rel_base == Path(".") else (rel_base / f).as_posix()
            if ignore.is_ignored(rel, is_dir=False):
                continue
            yield rel
