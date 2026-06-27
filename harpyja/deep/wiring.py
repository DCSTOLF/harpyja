"""Assemble a real Tier-2 `DeepEngine` for a repo (the production `deep_factory`).

Wires the live pieces behind the same `DeepEngine` the unit tests drive with
fakes: a `RlmBackend` (dspy.RLM, air-gap asserted on the endpoint), a Tier-0
`seed_fn` (symbol + ripgrep), the bounded host-tool whitelist, and the
host-terminable `DeepRunner`. Heavy deps (`dspy`/Deno) are reached only when this
factory actually runs, so importing the module stays cheap.
"""

from __future__ import annotations

from harpyja.config.settings import Settings
from harpyja.deep.engine import DeepEngine
from harpyja.deep.host_tools import build_host_tools
from harpyja.deep.rlm import RlmBackend
from harpyja.deep.runner import DeepRunner
from harpyja.index.artifacts import resolve_artifact_dir
from harpyja.index.indexer import index_repo
from harpyja.index.manifest import read_manifest
from harpyja.symbols.engine_identity import engine_identity
from harpyja.symbols.ripgrep import RipgrepEngine
from harpyja.symbols.symbol_locator import SymbolEngine
from harpyja.symbols.symbols_io import load_symbols_or_none


def build_deep_engine(settings: Settings, repo_path: str) -> DeepEngine:
    """Construct a live `DeepEngine` for ``repo_path`` (used as a `deep_factory`)."""
    art_dir = resolve_artifact_dir(repo_path, settings)
    index_repo(repo_path, settings, artifact_dir=art_dir)  # ensure the index exists
    manifest = read_manifest(art_dir)
    records = load_symbols_or_none(art_dir, engine_identity()) or []

    ripgrep = RipgrepEngine(settings)
    symbols = SymbolEngine(records, settings)

    def seed_fn(query: str):
        # Tier-0 seed (symbol defs + ripgrep), the same composition `auto` uses.
        return symbols.search(query, scope=repo_path) + ripgrep.search(query, scope=repo_path)

    def make_tools(budget):
        return build_host_tools(
            repo_path,
            settings,
            search_engine=ripgrep,
            symbol_records=records,
            manifest=manifest,
            budget=budget,
        )

    return DeepEngine(
        RlmBackend(settings),
        seed_fn,
        DeepRunner(settings),
        settings,
        repo_path,
        make_tools=make_tools,
    )
