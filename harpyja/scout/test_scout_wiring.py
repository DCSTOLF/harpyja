"""Spec 0025 (T1/T2): the canonical Scout factory constructs the EXPLORER.

FastContext is retired; `build_scout_engine` is now the single production
`scout_factory` and wires `ExplorerBackend` behind the unchanged `ScoutEngine`/DI
seam. The parallel `build_explorer_scout_engine` (spec 0024's transitional factory)
is deleted — exactly one clearly-named Scout factory, no lingering parallel path.
"""

from __future__ import annotations

from harpyja.config.settings import Settings
from harpyja.scout.engine import ScoutEngine


def test_build_scout_engine_constructs_explorer_backend(tmp_path):
    # AC1: the canonical factory builds the native explorer backend, not FastContext.
    (tmp_path / "auth.py").write_text("def handler():\n    return 1\n", encoding="utf-8")
    from harpyja.gateway.gateway import ModelGateway
    from harpyja.scout.explorer_backend import ExplorerBackend
    from harpyja.scout.wiring import build_scout_engine
    from harpyja.symbols.ripgrep import RipgrepEngine

    engine = build_scout_engine(Settings(), str(tmp_path))
    assert isinstance(engine, ScoutEngine)
    assert isinstance(engine._backend, ExplorerBackend)
    # The backend's search tool is the SHARED RipgrepEngine (spec invariant B), and
    # its gateway is the loopback ModelGateway — no model touched at build time.
    assert isinstance(engine._backend._search_engine, RipgrepEngine)
    assert isinstance(engine._backend._gateway, ModelGateway)


def test_wiring_constructs_no_fastcontext_backend(tmp_path):
    # AC1: no code path constructs a FastContext backend anymore.
    (tmp_path / "auth.py").write_text("def handler():\n    return 1\n", encoding="utf-8")
    from harpyja.scout.wiring import build_scout_engine

    engine = build_scout_engine(Settings(), str(tmp_path))
    assert type(engine._backend).__name__ != "FastContextBackend"


def test_build_explorer_scout_engine_removed():
    # AC1: no lingering parallel factory — the transitional name is gone.
    import harpyja.scout.wiring as wiring

    assert not hasattr(wiring, "build_explorer_scout_engine")


def test_build_scout_engine_has_no_agent_factory_kwarg():
    # AC2: the transitional FastContext `agent_factory=` seam is gone once the eval
    # turns diagnostic reads the explorer's native count.
    import inspect

    from harpyja.scout.wiring import build_scout_engine

    assert "agent_factory" not in inspect.signature(build_scout_engine).parameters


def test_build_scout_engine_threads_loop_budgets_and_manifest(tmp_path):
    # AC1: loop budgets reach the backend and the manifest feeds the context map.
    (tmp_path / "auth.py").write_text("def handler():\n    return 1\n", encoding="utf-8")
    from harpyja.scout.wiring import build_scout_engine

    engine = build_scout_engine(Settings(scout_max_turns=17), str(tmp_path))
    assert engine._backend._settings.scout_max_turns == 17
    assert any(e.path == "auth.py" for e in engine._backend._manifest)
    assert engine._file_set is not None and "auth.py" in engine._file_set


def test_build_scout_engine_accepts_injected_gateway(tmp_path):
    # AC1/AC8: an injected loopback gateway (used by the live cutover test to pin a
    # served model tag) reaches the backend.
    (tmp_path / "auth.py").write_text("def handler():\n    return 1\n", encoding="utf-8")
    from harpyja.gateway.gateway import ModelGateway
    from harpyja.scout.wiring import build_scout_engine

    gw = ModelGateway(api_base="http://127.0.0.1:11434/v1", allow_remote=False)
    engine = build_scout_engine(Settings(), str(tmp_path), gateway=gw)
    assert engine._backend._gateway is gw


def test_build_scout_engine_default_gateway_pins_configured_model(tmp_path):
    # AC8: the production default gateway selects the configured `lm_model` (not the
    # "local" placeholder, which 404s on Ollama's tag-routed API), so the live cutover
    # hits a served tag. This threads the model through the wiring (AC8's chosen option).
    (tmp_path / "auth.py").write_text("def handler():\n    return 1\n", encoding="utf-8")
    from harpyja.scout.wiring import build_scout_engine

    engine = build_scout_engine(Settings(lm_model="served-scout-tag:latest"), str(tmp_path))
    assert engine._backend._gateway.model == "served-scout-tag:latest"


def test_build_scout_engine_threads_http_timeout(tmp_path, monkeypatch):
    # Spec 0017 (B3): the scout gateway carries timeout_s from Settings (defense in
    # depth). A non-default 7.5 proves real threading, not the field default.
    (tmp_path / "auth.py").write_text("def handler():\n    return 1\n", encoding="utf-8")
    import harpyja.scout.wiring as wiring
    from harpyja.gateway.gateway import ModelGateway as _RealGateway

    captured: dict = {}

    def _spy(**kwargs):
        captured.update(kwargs)
        return _RealGateway(**kwargs)

    monkeypatch.setattr(wiring, "ModelGateway", _spy)
    wiring.build_scout_engine(Settings(lm_http_timeout_s=7.5), str(tmp_path))
    assert captured.get("timeout_s") == 7.5


def test_build_scout_engine_empty_file_set_when_manifest_absent(tmp_path, monkeypatch):
    # Degrade: no manifest entries -> empty file set threaded to the engine.
    (tmp_path / "auth.py").write_text("def handler():\n    return 1\n", encoding="utf-8")
    import harpyja.scout.wiring as wiring

    monkeypatch.setattr(wiring, "read_manifest", lambda _art: [])
    engine = wiring.build_scout_engine(Settings(), str(tmp_path))
    assert engine._file_set == frozenset()
