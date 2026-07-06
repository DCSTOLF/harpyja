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
from harpyja.index.manifest import read_manifest
from harpyja.scout.client import AgentFactory, CliRunner, DefaultFastContextClient
from harpyja.scout.engine import ScoutEngine
from harpyja.scout.explorer_backend import ExplorerBackend
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
    # Spec 0012: the repo-relative manifest file set, for Scout path-suffix recovery.
    # Manifest absent/empty ⇒ empty set ⇒ recovery is skipped (graceful degrade).
    file_set = frozenset(e.path for e in read_manifest(art_dir))

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
    gateway = ModelGateway(
        api_base=settings.lm_api_base,
        allow_remote=settings.allow_remote,
        timeout_s=settings.lm_http_timeout_s,  # spec 0017 (B3): defense-in-depth
    )
    # The whitelist is vestigial for Path A (FastContext owns its tools); the seam
    # stays unchanged. read/glob/grep are unused by the real client.
    backend = FastContextBackend(
        client=client,
        model_client=gateway,
        read=None,
        glob=None,
        grep=None,
    )
    return ScoutEngine(backend, seed_fn, settings, repo_path, file_set=file_set)


def build_explorer_scout_engine(
    settings: Settings,
    repo_path: str,
    *,
    model_call: object | None = None,
    gateway: ModelGateway | None = None,
) -> ScoutEngine:
    """Assemble a live `ScoutEngine` backed by the native explorer loop (spec 0024).

    The NEW production `scout_factory`: it wires `ExplorerBackend` behind the same
    unchanged `ScoutEngine`/DI seam the FastContext factory uses. Deliberately does
    NOT touch `build_scout_engine` (whose only remaining caller is the eval harness
    driving the retired SUT) — FastContext deletion is a separate, later cleanup so
    the two changes are not entangled in one diff.

    - `gateway` is the single outbound abstraction, loopback-enforced and carrying
      the spec-0017 HTTP timeout; the air-gap is asserted inside `ExplorerBackend`
      before any model I/O.
    - `search_engine` is the SHARED `RipgrepEngine` (spec invariant B — one bounded
      ripgrep source of truth, the same engine Tier-0 and Deep's `search` use).
    - the manifest entries feed the pre-model context map (no file bytes); the
      repo-relative file set is threaded for `ScoutEngine`'s suffix recovery.
    - `model_call` is an optional injected fake for tests; production leaves it
      `None` so the loop drives the gateway's tool-calling completion.
    """
    art_dir = resolve_artifact_dir(repo_path, settings)
    index_repo(repo_path, settings, artifact_dir=art_dir)  # ensure the index exists
    manifest = read_manifest(art_dir)
    file_set = frozenset(e.path for e in manifest)

    gw = gateway or ModelGateway(
        api_base=settings.lm_api_base,
        allow_remote=settings.allow_remote,
        timeout_s=settings.lm_http_timeout_s,
    )
    ripgrep = RipgrepEngine(settings)
    backend = ExplorerBackend(
        gateway=gw,
        repo_path=repo_path,
        settings=settings,
        manifest=manifest,
        search_engine=ripgrep,
        model_call=model_call,
    )
    # The explorer loop self-explores from the context map + tools, so no Tier-0
    # warm seed is threaded (a no-op seed_fn keeps the ScoutEngine contract).
    return ScoutEngine(backend, lambda _q: [], settings, repo_path, file_set=file_set)
