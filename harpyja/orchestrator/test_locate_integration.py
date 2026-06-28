"""Integration AC for Wave 5 auto-escalation (spec 0008, AC12).

`@pytest.mark.integration`, skip-not-fail: drives `mode=auto` over the REAL stack
(Scout + Verification Gate + Deep) on a loopback endpoint. A point query must
resolve cheap (no Tier-2); a broad query must climb to Tier-2. Citation *content*
is model-dependent, so this asserts the routing shape and confinement, not spans.

The deterministic shape of every routing decision is pinned by the unit ACs
(`test_locate.py`, `test_matrix.py`, `test_gate.py`); a flaky/absent model
degrades this to a skip, never a false failure.
"""

import shutil
import socket
from dataclasses import replace
from pathlib import Path

import pytest

from harpyja.config.settings import Settings
from harpyja.orchestrator.locate import locate
from harpyja.server.types import LocateRequest

_LOOPBACK = "http://127.0.0.1:11434/v1"
# Deep's `dspy.RLM` driver is distinct from Scout's `scout_model` (FastContext);
# it needs a real chat model pulled in Ollama (mirrors the Wave-4 Deep live test).
_DEEP_MODEL = "qwen2.5-coder:3b"
_NEEDS_STACK = (
    "requires FastContext + dspy + Deno + rg + a live endpoint with the Deep driver model"
)


def _endpoint_reachable(api_base: str, timeout: float = 0.25) -> bool:
    hostport = api_base.split("://", 1)[-1].split("/", 1)[0]
    host, _, port = hostport.partition(":")
    try:
        with socket.create_connection((host, int(port or 80)), timeout=timeout):
            return True
    except OSError:
        return False


def _live_stack_available() -> bool:
    try:
        import dspy  # noqa: F401
        import fastcontext  # noqa: F401
    except ImportError:
        return False
    if shutil.which("deno") is None or shutil.which("rg") is None:
        return False
    return _endpoint_reachable(_LOOPBACK)


def _settings_live() -> Settings:
    # scout_model keeps its FastContext default; lm_model drives Deep's RLM.
    return replace(
        Settings(), lm_api_base=_LOOPBACK, lm_model=_DEEP_MODEL, deep_max_subqueries=1
    )


def _confined(citations, repo: Path) -> bool:
    """Every citation resolves to a real file inside the repo."""
    for c in citations:
        target = repo / c.path
        if not target.is_file():
            return False
    return True


def _build(repo: str):
    from harpyja.deep.wiring import build_deep_engine
    from harpyja.orchestrator.wiring import build_verification_gate
    from harpyja.scout.wiring import build_scout_engine
    from harpyja.symbols.ripgrep import RipgrepEngine

    settings = _settings_live()
    return dict(
        settings=settings,
        engine=RipgrepEngine(settings),
        scout_engine=build_scout_engine(settings, repo),
        deep_engine=build_deep_engine(settings, repo),
        gate=build_verification_gate(settings, repo),
    )


@pytest.mark.integration
def test_locate_auto_point_resolves_cheap_live(tmp_path):
    if not _live_stack_available():
        pytest.skip(_NEEDS_STACK)
    (tmp_path / "auth.py").write_text(
        "def authenticate(token):\n    return token == 'ok'\n", encoding="utf-8"
    )
    wired = _build(str(tmp_path))
    result = locate(
        LocateRequest(query="authenticate", repo_path=str(tmp_path), mode="auto"),
        wired["settings"],
        engine=wired["engine"],
        scout_engine=wired["scout_engine"],
        deep_engine=wired["deep_engine"],
        gate=wired["gate"],
    )
    # A point query that the gate accepts must NOT spend Tier-2 (cost lever held).
    assert 2 not in result.tiers_run
    assert _confined(result.citations, tmp_path)


@pytest.mark.integration
def test_locate_auto_broad_climbs_to_deep_live(tmp_path):
    if not _live_stack_available():
        pytest.skip(_NEEDS_STACK)
    (tmp_path / "auth.py").write_text(
        "def authenticate(token):\n    return token == 'ok'\n", encoding="utf-8"
    )
    wired = _build(str(tmp_path))
    result = locate(
        LocateRequest(
            query="trace how authentication flows across the whole system",
            repo_path=str(tmp_path),
            mode="auto",
        ),
        wired["settings"],
        engine=wired["engine"],
        scout_engine=wired["scout_engine"],
        deep_engine=wired["deep_engine"],
        gate=wired["gate"],
    )
    # A broad query routes straight to Tier-2.
    assert 2 in result.tiers_run
    assert _confined(result.citations, tmp_path)
