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
