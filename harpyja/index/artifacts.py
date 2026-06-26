"""Where index artifacts live, and how they self-ignore (AC17 / B6 / R7).

Default: ``<repo>/.harpyja/`` (a sanctioned *derived*-artifact write — source
files are never touched), with a one-line ``.harpyja/.gitignore`` of ``*`` so the
dir ignores itself and the repo's root ``.gitignore`` is left alone. When the repo
dir is not writable (read-only / air-gapped mounts), fall back to an external
cache dir ``${XDG_CACHE_HOME:-~/.cache}/harpyja/<repo-hash>/`` where ``<repo-hash>``
is a SHA-256 prefix of the repo's absolute realpath. If neither is writable, raise.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from pathlib import Path

from harpyja.config.settings import Settings

Writable = Callable[[Path], bool]


class ArtifactLocationError(RuntimeError):
    """Raised when no writable location for index artifacts could be found."""


def _default_writable(path: Path) -> bool:
    return os.access(path, os.W_OK)


def repo_cache_key(repo_path: str | Path) -> str:
    """Stable cache key for a repo: SHA-256 prefix of its absolute realpath."""
    real = str(Path(repo_path).resolve())
    return hashlib.sha256(real.encode()).hexdigest()[:16]


def _cache_base(settings: Settings, environ: dict[str, str]) -> Path:
    if settings.cache_dir:
        return Path(settings.cache_dir)
    xdg = environ.get("XDG_CACHE_HOME")
    return Path(xdg) if xdg else Path.home() / ".cache"


def resolve_artifact_dir(
    repo_path: str | Path,
    settings: Settings,
    environ: dict[str, str] | None = None,
    writable: Writable = _default_writable,
) -> Path:
    """Resolve (and create) the directory for this repo's index artifacts."""
    environ = os.environ if environ is None else environ
    repo = Path(repo_path)

    if writable(repo):
        in_repo = repo / ".harpyja"
        in_repo.mkdir(parents=True, exist_ok=True)
        (in_repo / ".gitignore").write_text("*\n", encoding="utf-8")
        return in_repo

    cache_root = _cache_base(settings, environ) / "harpyja"
    if writable(cache_root) or writable(cache_root.parent):
        cache_dir = cache_root / repo_cache_key(repo)
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    raise ArtifactLocationError(
        f"no writable artifact location: repo {repo} and cache {cache_root} are both unwritable"
    )
