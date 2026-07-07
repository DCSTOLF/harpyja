"""Layered settings: defaults < harpyja.toml < HARPYJA_* env < per-request.

Wave 0 keeps the surface small and the precedence explicit (AC6). The toml file
mirrors `Settings` field names at the top level, e.g.::

    lm_api_base = "http://localhost:11434/v1"
    lm_model = "hf.co/Qwen/Qwen3-8B-GGUF:latest"
    lm_http_timeout_s = 120.0
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

# Spec 0008 — gate scoring backends that actually ship; the seam is pluggable in
# code, but the config surface rejects anything else loudly (no silent fall-through;
# no-false-capability). Spec 0018 (B2 fix / D3): `verify_method` finally *selects* the
# judge, so a second value ships — `instruct_model` (the new default) scores via the
# served `lm_model`; `scout_model` (the OOD finder) is retained non-default for a
# future finder-vs-instruct A/B.
_VERIFY_METHODS = frozenset({"scout_model", "instruct_model"})


class UnsupportedVerifyMethod(ValueError):
    """`verify_method` was set to a value Harpyja does not implement.

    Raised loudly at construction so an accepted-but-inert backend can never
    silently degrade to `scout_model` or no-op (spec 0008 AC13).
    """


@dataclass(frozen=True)
class Settings:
    """Resolved configuration. Frozen so overrides return new instances."""

    lm_api_base: str = "http://localhost:11434/v1"
    # Spec 0016 (B1 fix / D2): flipped from the llama.cpp placeholder "local" to a
    # served Ollama tag. This is a GLOBAL default — every bare `Settings()` caller
    # (incl. the MCP server's `mode=auto` Deep tier) gets it. A llama.cpp operator
    # (where "local" was a benign don't-care) must now set `lm_model` explicitly via
    # toml/env/`--deep-model`. Provisional ("for now"), not a long-term Deep choice.
    lm_model: str = "hf.co/Qwen/Qwen3-8B-GGUF:latest"
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

    # `scout_model` is Scout-specific and distinct from Deep's `lm_model`. Spec 0025
    # RETIRED the FastContext backend, but `scout_model` is KEPT: it is a SEPARATE
    # consumer — the Verification Gate A/B baseline (`verify_method="scout_model"`,
    # spec 0018). Its default is a FastContext-lineage tag, but a SERVED local Ollama
    # model (spec 0016 flipped it off the unserved mitkox RL-Q4 tag onto the served
    # dstolf Q8 RL tag), so the gate baseline still resolves. The FC-only knobs
    # (`scout_max_tokens`/`scout_temperature`/`scout_reasoning_effort`, which mapped to
    # FC_MAX_TOKENS / FC_TEMPERATURE / FC_REASONING_EFFORT) were removed with the FC
    # adapter — the explorer does not use them.
    scout_model: str = "hf.co/dstolf/FastContext-1.0-4B-RL-Q8_0-GGUF:latest"

    # Spec 0024 (v2 explorer loop) — the native explorer-loop budgets. ALL are
    # PROVISIONAL and flagged for tuning in the later model bake-off (OQ1/OQ3);
    # they are one-line tunes, never a code fork.
    # `scout_max_turns` — the loop's turn cap. A general (non-fine-tuned) tool-
    # calling model needs more turns to localize than the retired FastContext
    # finder's `_DEFAULT_MAX_TURNS=6`, so this starts higher (OQ1).
    scout_max_turns: int = 12
    # `scout_wall_clock_s` — the WHOLE-LOOP wall-clock ceiling (AC4). Distinct from
    # and strictly above `lm_http_timeout_s` (the per-CALL floor): one slow turn is
    # bounded by the HTTP timeout, and this ceiling stops a sequence of slow turns
    # (or a wedged model) from running unbounded. Turns ≠ time for a general model.
    scout_wall_clock_s: float = 300.0
    # `scout_loop_repeat_n` — loop-detection sensitivity (AC5): an exact
    # (tool_name, normalized_args) call repeated for this many consecutive turns
    # WITHOUT adding new spans to history triggers a corrective injection (OQ3).
    scout_loop_repeat_n: int = 2
    # `scout_history_char_cap` — the context-management bloat threshold (AC5):
    # history exceeding this character budget triggers citation-preserving
    # truncation (stale navigational chatter only; citable observations survive
    # via a re-injected dropped-span index) (OQ3).
    scout_history_char_cap: int = 60000
    # `scout_glob_max_paths` — the `glob` navigation tool's output bound (AC2),
    # parallel to `search_max_matches` for `grep`; glob returns file records so it
    # is bounded independently.
    scout_glob_max_paths: int = 400
    # Spec 0027 — `scout_ls_max_entries` — the `ls`/tree navigation tool's output
    # clamp (AC3): a single-directory listing is bounded to this many entries (the
    # layout-discovery affordance `glob` lacks, since glob filters out directories).
    # Parallel to scout_glob_max_paths; additive-last on the scout budgets.
    scout_ls_max_entries: int = 200

    # Spec 0008 (Wave 5) — Verification Gate (additive, appended last).
    # `verify_method` selects the scoring backend; `verify_threshold` is the pass
    # cutoff on a normalized [0,1] score and `verify_top_n` bounds how many ranked
    # citations the gate scores (provisional defaults, tuned against the eval repo).
    # Spec 0018 (B2 fix / D1): default flips from the OOD finder `scout_model` (which
    # false-rejected correct citations — 0015 D2) to `instruct_model`, which scores via
    # the served `lm_model`. NB the coupling: this makes `lm_model` a SECOND consumer —
    # it already backs Deep (Tier 2), and now also backs the gate judge, so a future
    # `lm_model` tune for Deep silently retunes the gate. `lm_model` is itself
    # provisional (0016 "for now" Qwen3-8B), so the judge inherits a provisional default.
    verify_method: str = "instruct_model"
    verify_threshold: float = 0.6
    verify_top_n: int = 3

    # Spec 0017 (B3 fix / D1): the outbound Model Gateway HTTP timeout, in seconds.
    # Finite (never None) so a stalled/torn-down local endpoint raises instead of
    # wedging the run forever. This is a per-socket-op bound (urlopen(timeout=)),
    # NOT a total-request deadline. Deliberately decoupled from `deep_wall_clock_ms`
    # (they bound different things); no per-request layer (D2) — fixed at gateway
    # construction from resolved Settings.
    lm_http_timeout_s: float = 120.0

    def __post_init__(self) -> None:
        # Fires on every construction path — defaults, toml/env merge, and
        # per-request `replace` — so an unsupported backend is rejected uniformly
        # (AC13). The default `scout_model` passes, so existing callers are
        # unaffected.
        if self.verify_method not in _VERIFY_METHODS:
            accepted = ", ".join(sorted(_VERIFY_METHODS))
            raise UnsupportedVerifyMethod(
                f"verify_method={self.verify_method!r} is not implemented; "
                f"accepted: {{{accepted}}}"
            )


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
    if target is float or target_str == "float":
        return float(raw)
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
