"""Discover the harpyja.toml to load (AC7).

Order, highest priority first:
1. an explicit path (``--config <path>``),
2. ``harpyja.toml`` in the current working directory,
3. ``harpyja.toml`` at the repo root.

Returns ``None`` when no config file is found. An explicit path is returned
as-is (the caller decides whether a missing explicit file is an error).
"""

from __future__ import annotations

from pathlib import Path

_CONFIG_NAME = "harpyja.toml"


def discover_config_path(
    explicit: str | Path | None = None,
    cwd: str | Path | None = None,
    repo_root: str | Path | None = None,
) -> Path | None:
    if explicit is not None:
        return Path(explicit)

    for base in (cwd, repo_root):
        if base is None:
            continue
        candidate = Path(base) / _CONFIG_NAME
        if candidate.is_file():
            return candidate

    return None
