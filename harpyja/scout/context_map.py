"""The pre-model context map (spec 0024, AC3).

A compact, high-level repo map built from the EXISTING manifest — a filtered tree
with NO raw file contents — injected with the query so the model sees the repo
layout without loading any file bytes. The function takes ONLY the manifest and
the query, so it structurally cannot read the repo.

The vendor/test/generated exclusion is a DISPLAY concern that reuses the indexer's
own canonical classification (`index.prior`) — the single source of truth for what
counts as test/vendor/generated. It applies to the rendered map ONLY: the
navigation tools (`grep`/`glob`/`read_span`) are unaffected and still reach those
files, because a test/vendor file can be the localization target.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import PurePosixPath

from harpyja.config.settings import Settings
from harpyja.index.manifest import ManifestEntry
from harpyja.index.prior import (
    _GENERATED_DIRS,
    _GENERATED_SUFFIXES,
    _TEST_DIRS,
    _VENDOR_DIRS,
    _is_test_file,
)


def _is_map_excluded(path: str) -> bool:
    """True iff ``path`` is a test/vendor/generated file (dropped from the map).

    Reuses the exact dir-name sets + file heuristics `index.prior` uses to
    deprioritize these layers — one source of truth, no divergent second list.
    """
    p = PurePosixPath(path)
    dirs = {part.lower() for part in p.parts[:-1]}
    name = p.name.lower()
    if dirs & _TEST_DIRS or _is_test_file(name):
        return True
    if dirs & _VENDOR_DIRS:
        return True
    if dirs & _GENERATED_DIRS or name.endswith(_GENERATED_SUFFIXES):
        return True
    return False


def build_context_map(
    manifest: Sequence[ManifestEntry],
    query: str,
    settings: Settings,
) -> str:
    """Render the query-injected, filtered repo map (no file bytes)."""
    paths = [e.path for e in manifest if not _is_map_excluded(e.path)]
    paths.sort()
    tree = "\n".join(paths)
    return (
        "You are localizing a query in a repository. Repo layout "
        "(vendor/test/generated omitted; still reachable via tools):\n"
        f"{tree}\n\n"
        f"Query: {query}"
    )
