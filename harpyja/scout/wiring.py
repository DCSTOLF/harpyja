"""Assemble a real Tier-1 `ScoutEngine` for a repo (the production `scout_factory`).

Mirrors `deep/wiring.py`: it wires the live pieces behind the same `ScoutEngine`
the unit tests drive with fakes — the real `DefaultFastContextClient` (which
drives Microsoft's FastContext agent), a Tier-0 `seed_fn` (symbol + ripgrep), and
the unchanged `FastContextBackend` seam. FastContext is reached only lazily inside
the client, so importing this module stays cheap when the package is absent.

Honest limit: the real FastContext agent owns its **own** Read/Glob/Grep tools
(built from `work_dir`) and its own model client, so the `FastContextBackend` tool
whitelist is vestigial for Path A — the air-gap is enforced in the client via
`gateway.assert_local` before the agent is constructed, not by routing through the
whitelist's Gateway. The whitelist is still assembled to keep the Wave-3 seam
unchanged; the Gateway handed in is the loopback-enforced one.
"""

from __future__ import annotations

from harpyja.config.settings import Settings
from harpyja.gateway.gateway import ModelGateway
from harpyja.index.artifacts import resolve_artifact_dir
from harpyja.index.indexer import index_repo
from harpyja.scout.client import AgentFactory, CliRunner, DefaultFastContextClient
from harpyja.scout.engine import ScoutEngine
from harpyja.scout.fastcontext import FastContextBackend
from harpyja.symbols.engine_identity import engine_identity
from harpyja.symbols.ripgrep import RipgrepEngine
from harpyja.symbols.symbol_locator import SymbolEngine
from harpyja.symbols.symbols_io import load_symbols_or_none


def build_scout_engine(
    settings: Settings,
    repo_path: str,
    *,
    agent_factory: AgentFactory | None = None,
    cli_runner: CliRunner | None = None,
) -> ScoutEngine:
    """Construct a live `ScoutEngine` for ``repo_path`` (used as a `scout_factory`)."""
    art_dir = resolve_artifact_dir(repo_path, settings)
    index_repo(repo_path, settings, artifact_dir=art_dir)  # ensure the index exists
    records = load_symbols_or_none(art_dir, engine_identity()) or []

    ripgrep = RipgrepEngine(settings)
    symbols = SymbolEngine(records, settings)

    def seed_fn(query: str):
        # Tier-0 seed (symbol defs + ripgrep), the same composition `auto` uses.
        return symbols.search(query, scope=repo_path) + ripgrep.search(query, scope=repo_path)

    client = DefaultFastContextClient(
        settings,
        repo_path,
        agent_factory=agent_factory,
        cli_runner=cli_runner,
    )
    gateway = ModelGateway(api_base=settings.lm_api_base, allow_remote=settings.allow_remote)
    # The whitelist is vestigial for Path A (FastContext owns its tools); the seam
    # stays unchanged. read/glob/grep are unused by the real client.
    backend = FastContextBackend(
        client=client,
        model_client=gateway,
        read=None,
        glob=None,
        grep=None,
    )
    return ScoutEngine(backend, seed_fn, settings, repo_path)
