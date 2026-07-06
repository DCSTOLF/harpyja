"""RED (T16): the production Scout factory wires the real default client.

`build_scout_engine` is the `scout_factory` analogue of `deep/wiring.py`'s
`build_deep_engine`: it assembles a live `ScoutEngine` whose backend delegates to
a `DefaultFastContextClient` and whose `seed_fn` is the Tier-0 (symbol + ripgrep)
composition — all without touching the model (an injected factory stands in for
the real FastContext import).
"""

from __future__ import annotations

from harpyja.config.settings import Settings
from harpyja.scout.client import DefaultFastContextClient
from harpyja.scout.engine import ScoutEngine
from harpyja.scout.fastcontext import FastContextBackend


def test_build_scout_engine_wires_default_client(tmp_path):
    (tmp_path / "auth.py").write_text("def handler():\n    return 1\n", encoding="utf-8")
    from harpyja.scout.wiring import build_scout_engine

    engine = build_scout_engine(
        Settings(),
        str(tmp_path),
        agent_factory=lambda **kw: None,  # avoid the real import / model
    )
    assert isinstance(engine, ScoutEngine)
    assert isinstance(engine._backend, FastContextBackend)
    assert isinstance(engine._backend._client, DefaultFastContextClient)
    # seed_fn is the Tier-0 composition (symbol defs + ripgrep), no model touched.
    seeded = engine._seed_fn("handler")
    assert isinstance(seeded, list)
    assert any(s.path.endswith("auth.py") for s in seeded)


# --- Spec 0012: wiring loads the manifest file set for suffix recovery ---


def test_build_scout_engine_threads_manifest_file_set(tmp_path):
    # AC4: build reads the manifest the indexer wrote and hands the repo-relative
    # file set to the engine for path-suffix recovery.
    (tmp_path / "auth.py").write_text("def handler():\n    return 1\n", encoding="utf-8")
    from harpyja.scout.wiring import build_scout_engine

    engine = build_scout_engine(
        Settings(), str(tmp_path), agent_factory=lambda **kw: None
    )
    assert engine._file_set is not None and len(engine._file_set) >= 1
    assert "auth.py" in engine._file_set


def test_build_scout_engine_empty_file_set_when_manifest_absent(tmp_path, monkeypatch):
    # AC2/AC4 degrade: no manifest entries -> empty file set -> no recovery.
    (tmp_path / "auth.py").write_text("def handler():\n    return 1\n", encoding="utf-8")
    import harpyja.scout.wiring as wiring

    monkeypatch.setattr(wiring, "read_manifest", lambda _art: [])
    engine = wiring.build_scout_engine(
        Settings(), str(tmp_path), agent_factory=lambda **kw: None
    )
    assert engine._file_set == frozenset()


# --- Spec 0017 (B3): the scout-site gateway carries the timeout (defense-in-depth) ---


def test_build_scout_engine_threads_http_timeout(tmp_path, monkeypatch):
    # AC10: the scout gateway is constructed with timeout_s from Settings. A
    # constructor spy is robust to the (private, vestigial) backend tool shape; a
    # non-default 7.5 proves real threading, not the 120.0 field default.
    (tmp_path / "auth.py").write_text("def handler():\n    return 1\n", encoding="utf-8")
    import harpyja.scout.wiring as wiring
    from harpyja.gateway.gateway import ModelGateway as _RealGateway

    captured: dict = {}

    def _spy(**kwargs):
        captured.update(kwargs)
        return _RealGateway(**kwargs)

    monkeypatch.setattr(wiring, "ModelGateway", _spy)
    wiring.build_scout_engine(
        Settings(lm_http_timeout_s=7.5), str(tmp_path), agent_factory=lambda **kw: None
    )
    assert captured.get("timeout_s") == 7.5


# --- Spec 0024 (v2): the native explorer-loop production factory (T19/T20, AC1) ---
#
# Deviation from the plan's "swap in place": `build_scout_engine` (FastContext) is
# LEFT INTACT — its only caller is the eval harness driving the old SUT, and the
# spec defers FastContext removal to a dedicated cleanup so the two aren't
# entangled. `build_explorer_scout_engine` is the NEW production factory that wires
# `ExplorerBackend` behind the unchanged `ScoutEngine`/DI seam.


def test_build_explorer_scout_engine_wires_explorer_backend(tmp_path):
    (tmp_path / "auth.py").write_text("def handler():\n    return 1\n", encoding="utf-8")
    from harpyja.gateway.gateway import ModelGateway
    from harpyja.scout.engine import ScoutEngine
    from harpyja.scout.explorer_backend import ExplorerBackend
    from harpyja.scout.wiring import build_explorer_scout_engine
    from harpyja.symbols.ripgrep import RipgrepEngine

    engine = build_explorer_scout_engine(Settings(), str(tmp_path))
    assert isinstance(engine, ScoutEngine)
    assert isinstance(engine._backend, ExplorerBackend)
    # The backend's search tool is the SHARED RipgrepEngine (spec invariant B), and
    # its gateway is the loopback ModelGateway — no model touched at build time.
    assert isinstance(engine._backend._search_engine, RipgrepEngine)
    assert isinstance(engine._backend._gateway, ModelGateway)


def test_build_explorer_scout_engine_threads_loop_budgets_and_manifest(tmp_path):
    (tmp_path / "auth.py").write_text("def handler():\n    return 1\n", encoding="utf-8")
    from harpyja.scout.wiring import build_explorer_scout_engine

    settings = Settings(scout_max_turns=17)
    engine = build_explorer_scout_engine(settings, str(tmp_path))
    # Loop budgets reach the backend, and the manifest is threaded for the context map.
    assert engine._backend._settings.scout_max_turns == 17
    assert any(e.path == "auth.py" for e in engine._backend._manifest)
    assert engine._file_set is not None and "auth.py" in engine._file_set


def test_build_explorer_scout_engine_threads_http_timeout(tmp_path, monkeypatch):
    (tmp_path / "auth.py").write_text("def handler():\n    return 1\n", encoding="utf-8")
    import harpyja.scout.wiring as wiring
    from harpyja.gateway.gateway import ModelGateway as _RealGateway

    captured: dict = {}

    def _spy(**kwargs):
        captured.update(kwargs)
        return _RealGateway(**kwargs)

    monkeypatch.setattr(wiring, "ModelGateway", _spy)
    wiring.build_explorer_scout_engine(Settings(lm_http_timeout_s=7.5), str(tmp_path))
    assert captured.get("timeout_s") == 7.5
