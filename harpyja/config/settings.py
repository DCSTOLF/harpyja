"""Layered settings: defaults < harpyja.toml < HARPYJA_* env < per-request.

Wave 0 keeps the surface small and the precedence explicit (AC6). The toml file
mirrors `Settings` field names at the top level, e.g.::

    lm_api_base = "http://localhost:11434/v1"
    lm_model = "local"
    max_results = 8
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

from harpyja.config.discovery import discover_config_path

# Maps a Settings field name to its HARPYJA_* environment variable.
_ENV_PREFIX = "HARPYJA_"


@dataclass(frozen=True)
class Settings:
    """Resolved configuration. Frozen so overrides return new instances."""

    lm_api_base: str = "http://localhost:11434/v1"
    lm_model: str = "local"
    max_results: int = 8
    allow_remote: bool = False

    # Wave 1 — indexer / search / tool bounds (SPEC §5).
    ignore_globs: tuple[str, ...] = ()
    follow_symlinks: bool = False
    search_max_files: int = 4000
    search_max_matches: int = 400
    rg_chunk_size: int = 512
    tool_max_lines: int = 400
    tool_max_chars: int = 20000
    manifest_page: int = 200
    cache_dir: str | None = None

    # Wave 3 — Scout (Tier 1) budgets (spec 0005 §What).
    scout_seed_top_n: int = 5
    scout_max_citations: int = 20
    scout_max_span_lines: int = 200

    # Wave 4 — Deep (Tier 2) budgets (spec 0006 §Concrete budgets).
    deep_seed_top_n: int = 5
    deep_max_citations: int = 20
    deep_max_span_lines: int = 200
    deep_max_depth: int = 3
    deep_max_subqueries: int = 8
    deep_max_tool_calls: int = 200
    deep_token_ceiling: int = 32000
    deep_wall_clock_ms: int = 60000


_FIELD_TYPES = {f.name: f.type for f in fields(Settings)}


def _coerce(name: str, raw: Any) -> Any:
    """Coerce a raw (env-string or toml) value to the field's type."""
    target = _FIELD_TYPES[name]
    target_str = target if isinstance(target, str) else getattr(target, "__name__", "")
    if target_str.startswith("tuple"):
        # toml lists arrive as list/tuple; env values arrive as a CSV string.
        if isinstance(raw, (list, tuple)):
            items = [str(v) for v in raw]
        else:
            items = [part.strip() for part in str(raw).split(",")]
        return tuple(p for p in items if p)
    if target is bool or target_str == "bool":
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}
    if target is int or target_str == "int":
        return int(raw)
    return str(raw)


def _known(overrides: dict[str, Any]) -> dict[str, Any]:
    """Keep only keys that name a real Settings field, coerced to its type."""
    return {k: _coerce(k, v) for k, v in overrides.items() if k in _FIELD_TYPES}


def _from_toml(path: Path | None) -> dict[str, Any]:
    if path is None or not Path(path).is_file():
        return {}
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    return _known(data)


def _from_env(environ: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in _FIELD_TYPES:
        env_key = _ENV_PREFIX + name.upper()
        if env_key in environ:
            out[name] = environ[env_key]
    return _known(out)


def load_settings(
    config_path: str | Path | None = None,
    repo_path: str | Path | None = None,
    environ: dict[str, str] | None = None,
) -> Settings:
    """Build Settings from defaults, then the discovered toml, then env.

    Per-request overrides are applied separately via :func:`resolve_settings`.
    """
    environ = os.environ if environ is None else environ
    toml_path = discover_config_path(
        explicit=config_path,
        cwd=Path.cwd(),
        repo_root=repo_path,
    )
    merged: dict[str, Any] = {}
    merged.update(_from_toml(toml_path))
    merged.update(_from_env(environ))
    return replace(Settings(), **merged)


def resolve_settings(base: Settings, request_override: dict[str, Any] | None = None) -> Settings:
    """Apply the highest-precedence per-request override onto ``base``.

    Returns a new Settings; ``base`` is never mutated.
    """
    if not request_override:
        return base
    return replace(base, **_known(request_override))
