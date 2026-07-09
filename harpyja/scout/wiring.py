"""Assemble a real Tier-1 `ScoutEngine` for a repo (the production `scout_factory`).

`build_scout_engine` is the SINGLE production Scout factory (spec 0025): it wires
the native `ExplorerBackend` — a general OpenAI-compatible tool-calling model
driven over three read-only tools (grep/glob/read_span) to a `submit_citations`
terminal action — behind the unchanged `ScoutEngine`/`Locator` DI seam. The
retired FastContext adapter and its parallel `build_explorer_scout_engine` factory
are gone; there is exactly one clearly-named Scout factory.

- `gateway` is the single outbound abstraction, loopback-enforced and carrying the
  spec-0017 HTTP timeout; the air-gap is asserted inside `ExplorerBackend` before
  any model I/O.
- `search_engine` is the SHARED `RipgrepEngine` (spec invariant B — one bounded
  ripgrep source of truth, the same engine Tier-0 and Deep's `search` use).
- the manifest entries feed the pre-model context map (no file bytes); the
  repo-relative file set is threaded for `ScoutEngine`'s tally normalization.
- `model_call` is an optional injected fake for tests; production leaves it `None`
  so the loop drives the gateway's tool-calling completion.
"""

from __future__ import annotations

from harpyja.config.settings import Settings
from harpyja.gateway.gateway import ModelGateway
from harpyja.index.artifacts import resolve_artifact_dir
from harpyja.index.indexer import index_repo
from harpyja.index.manifest import read_manifest
from harpyja.scout.engine import ScoutEngine
from harpyja.scout.explorer_backend import ExplorerBackend
from harpyja.symbols.engine_identity import engine_identity
from harpyja.symbols.ripgrep import RipgrepEngine
from harpyja.symbols.symbols_io import load_symbols_or_none


def build_scout_engine(
    settings: Settings,
    repo_path: str,
    *,
    model_call: object | None = None,
    gateway: ModelGateway | None = None,
) -> ScoutEngine:
    """Construct a live explorer-backed `ScoutEngine` for ``repo_path``."""
    art_dir = resolve_artifact_dir(repo_path, settings)
    index_repo(repo_path, settings, artifact_dir=art_dir)  # ensure the index exists
    manifest = read_manifest(art_dir)
    file_set = frozenset(e.path for e in manifest)

    # Spec 0030: load symbol records (Tier-0 file-local symbol index) for the
    # symbols explorer tool (on-demand, not eager injection).
    symbol_records = load_symbols_or_none(art_dir, engine_identity()) or []

    gw = gateway or ModelGateway(
        api_base=settings.lm_api_base,
        model=settings.lm_model,  # spec 0025 (AC8): pin the served tag, not "local"
        allow_remote=settings.allow_remote,
        timeout_s=settings.lm_http_timeout_s,  # spec 0017 (B3): defense-in-depth
    )
    ripgrep = RipgrepEngine(settings)
    backend = ExplorerBackend(
        gateway=gw,
        repo_path=repo_path,
        settings=settings,
        manifest=manifest,
        search_engine=ripgrep,
        symbol_records=symbol_records,
        model_call=model_call,
        max_tokens=settings.explorer_max_tokens,  # spec 0028 (AC2): feed the cap
        enable_thinking=settings.explorer_enable_thinking,  # spec 0028 (AC1)
        think=settings.explorer_think,  # spec 0034 (native knob; None ⇒ omit)
    )
    # The explorer loop self-explores from the context map + tools, so no Tier-0
    # warm seed is threaded (a no-op seed_fn keeps the ScoutEngine contract).
    return ScoutEngine(backend, lambda _q: [], settings, repo_path, file_set=file_set)
