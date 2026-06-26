"""Build/refresh the manifest (AC1-6, AC6a/6b, AC17, AC18).

Pure-Python — no ripgrep needed (B4/R1). Incremental: a file whose ``(mtime,
size)`` match the prior manifest entry is reused without re-hashing; everything
else is re-hashed. Files gone from disk are pruned. ``rehash=True`` ignores the
gate. Artifacts go to the resolved artifact dir (in-repo or external cache).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from harpyja.config.settings import Settings
from harpyja.index.artifacts import resolve_artifact_dir
from harpyja.index.classify import classify_language
from harpyja.index.hash import hash_file
from harpyja.index.ignore import build_ignore
from harpyja.index.manifest import ManifestEntry, read_manifest, write_manifest
from harpyja.index.prior import prior
from harpyja.index.walk import walk

HashFn = Callable[[Path], str]


@dataclass
class IndexResult:
    files_indexed: int
    symbols_indexed: int = 0
    languages: dict[str, int] = field(default_factory=dict)
    elapsed_ms: int = 0
    degraded: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "files_indexed": self.files_indexed,
            "symbols_indexed": self.symbols_indexed,
            "languages": self.languages,
            "elapsed_ms": self.elapsed_ms,
            "degraded": self.degraded,
        }


def index_repo(
    repo_path: str | Path,
    settings: Settings,
    *,
    rehash: bool = False,
    hash_fn: HashFn = hash_file,
    artifact_dir: Path | None = None,
) -> IndexResult:
    start = time.perf_counter()
    repo = Path(repo_path)

    # Resolve (and create) the artifact dir first so its self-ignore is in place
    # before we walk — the .harpyja/ contents must not index themselves.
    art_dir = artifact_dir or resolve_artifact_dir(repo, settings)
    prior_entries = {e.path: e for e in read_manifest(art_dir)}

    ignore = build_ignore(repo, settings.ignore_globs)

    entries: list[ManifestEntry] = []
    languages: dict[str, int] = {}
    for rel in walk(repo, ignore, follow_symlinks=settings.follow_symlinks):
        full = repo / rel
        try:
            st = full.stat()
        except OSError:
            continue
        size, mtime = st.st_size, st.st_mtime

        cached = prior_entries.get(rel)
        if not rehash and cached and cached.size == size and cached.mtime == mtime:
            entry = cached
        else:
            entry = ManifestEntry(
                path=rel,
                language=classify_language(rel),
                size=size,
                hash=hash_fn(full),
                mtime=mtime,
                prior=prior(rel),
            )
        entries.append(entry)
        if entry.language is not None:
            languages[entry.language] = languages.get(entry.language, 0) + 1

    write_manifest(art_dir, entries)

    return IndexResult(
        files_indexed=len(entries),
        symbols_indexed=0,
        languages=languages,
        elapsed_ms=int((time.perf_counter() - start) * 1000),
        degraded=[],
    )
