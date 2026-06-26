"""Tool helpers: bounded, path-confined reads (`harpyja_read`).

`harpyja_locate` is implemented by the Tier-0 orchestrator (`orchestrator.locate`);
`harpyja_index` by `index.indexer`. This module holds the read helper and the
path-confinement guard shared by reads and search.
"""

from __future__ import annotations

from pathlib import Path

from harpyja.config.settings import Settings
from harpyja.index.classify import classify_language


class PathConfinementError(ValueError):
    """Raised when a path resolves outside the repo (traversal or escaping symlink)."""


def confine_path(repo_path: str | Path, path: str | Path) -> Path:
    """Resolve ``path`` and assert its realpath is within ``repo_path`` (AC16).

    Follows symlinks before the containment check, so an in-repo symlink that
    points outside the repo is rejected just like a ``../`` traversal.
    """
    repo_real = Path(repo_path).resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = repo_real / candidate
    real = candidate.resolve()
    if real != repo_real and repo_real not in real.parents:
        raise PathConfinementError(f"path escapes repo: {path!r}")
    return real


def read_snippet(
    repo_path: str | Path,
    path: str,
    start: int,
    end: int,
    settings: Settings,
) -> dict:
    """Return a bounded, path-confined code snippet (AC15, AC16).

    Lines are 1-indexed and ``end`` is inclusive. The returned ``start``/``end``
    reflect the actual (clamped) range; ``truncated`` is set when the requested
    range was narrowed by ``tool_max_lines`` or ``tool_max_chars`` (clamping to
    end-of-file is not truncation).
    """
    real = confine_path(repo_path, path)
    lines = real.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    total = len(lines)

    start = max(1, start)
    bound_end = start + settings.tool_max_lines - 1
    actual_end = min(end, bound_end, total)
    truncated = end > bound_end  # clamped by the line bound (not by EOF)

    content = "".join(lines[start - 1 : actual_end])
    if len(content) > settings.tool_max_chars:
        content = content[: settings.tool_max_chars]
        truncated = True

    return {
        "path": path,
        "start": start,
        "end": actual_end,
        "language": classify_language(path),
        "content": content,
        "truncated": truncated,
    }
