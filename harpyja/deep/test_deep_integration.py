"""Integration tests for Tier 2 (Deep) — real subprocess / sandbox / RLM.

All `@pytest.mark.integration` (spawn a real process) and skip-not-fail when the
heavy deps (`dspy`/`deno`/endpoint) are absent. The wall-clock mechanism here
needs only a real subprocess, so it runs without those deps.
"""

import shutil

import pytest

from harpyja.config.settings import Settings
from harpyja.deep.runner import DeepRunner

_OLLAMA = "http://localhost:11434/v1"


def _deep_stack_available() -> bool:
    """True when the dspy + Deno sandbox are installed (no Tier-0 seed needed)."""
    if shutil.which("deno") is None:
        return False
    try:
        import dspy  # noqa: F401
    except ImportError:
        return False
    return True


def _endpoint_reachable(api_base: str = _OLLAMA, timeout: float = 0.5) -> bool:
    import socket as _s

    host, _, port = api_base.split("://", 1)[-1].split("/", 1)[0].partition(":")
    try:
        with _s.create_connection((host, int(port or 80)), timeout=timeout):
            return True
    except OSError:
        return False


def _full_stack_available() -> bool:
    """End-to-end also needs a real `rg` BINARY (the Tier-0 seed) + a live endpoint."""
    return _deep_stack_available() and shutil.which("rg") is not None and _endpoint_reachable()


_NEEDS_STACK = "requires dspy + Deno sandbox (provisioning is the Wave-4 open question)"
_NEEDS_FULL = "requires dspy + Deno + a real `rg` binary (Tier-0 seed) + a live endpoint"


# Module-level so the spawn-based subprocess can import (pickle by reference).
def _busy_loop() -> None:
    while True:  # touches no tool/token counter — only the wall clock can stop it
        pass


def _quick_worker(x: int) -> int:
    return x * 2


@pytest.mark.integration
def test_runner_hard_kills_nonyielding_busy_loop_on_wall_clock():
    result, bound = DeepRunner(Settings()).run_isolated(_busy_loop, timeout_ms=300)
    assert result is None
    assert bound == "wall-clock"  # hard-terminated, never a DeepUnavailable


@pytest.mark.integration
def test_runner_isolated_returns_worker_result_within_deadline():
    result, bound = DeepRunner(Settings()).run_isolated(_quick_worker, args=(21,), timeout_ms=5000)
    assert result == 42
    assert bound is None


# --- task 24: live sandbox / runaway / network-deny / end-to-end (skip-not-fail) ---


@pytest.mark.integration
def test_deep_sandbox_denies_ambient_fs_and_network(tmp_path):
    """AC8b: in the real Deno/Pyodide sandbox, RLM-authored code cannot reach
    ambient host FS or network — an open() outside the repo, an open() *inside*
    the repo (which would bypass read_span's clamps), and a socket connect to a
    non-loopback address all fail. Only the bridged host tools are reachable.

    Residual risk (recorded, not asserted): the WASM FS is empty-by-default and
    network is denied by the runtime; a future Pyodide/Deno change could widen the
    surface, which is why this is verified by test rather than assumed.
    """
    if not _deep_stack_available():
        pytest.skip(_NEEDS_STACK)
    from dspy.primitives.python_interpreter import CodeInterpreterError, PythonInterpreter

    repo_file = tmp_path / "secret.py"
    repo_file.write_text("TOKEN = 'sensitive'\n", encoding="utf-8")

    pi = PythonInterpreter()
    try:
        with pytest.raises(CodeInterpreterError):
            pi.execute("open('/etc/passwd').read()")  # ambient FS, outside repo
        with pytest.raises(CodeInterpreterError):
            pi.execute(f"open({str(repo_file)!r}).read()")  # ambient FS, inside repo
        with pytest.raises(CodeInterpreterError):
            pi.execute("import socket; socket.socket().connect(('8.8.8.8', 53))")  # network
    finally:
        pi.shutdown()


def _slow_real_rlm_worker(model: str, api_base: str) -> str:  # pragma: no cover
    """A genuine dspy.RLM forward (seconds-long) — used to prove host preemption."""
    import dspy

    lm = dspy.LM(f"openai/{model}", api_base=api_base, api_key="ollama", max_tokens=512)
    rlm = dspy.RLM(
        "question -> answer", max_iterations=20, max_llm_calls=50, sub_lm=lm, verbose=False
    )
    rlm.set_lm(lm)
    return getattr(rlm(question="Analyze this in exhaustive detail, step by step."), "answer", "")


@pytest.mark.integration
def test_deep_real_runaway_terminates_with_truncated_note():
    """AC10a: a REAL dspy.RLM forward (~tens of seconds) is hard-killed by the host
    wall-clock deadline and surfaces `deep-truncated:wall-clock` — proving the
    backstop against a real, non-cooperative RLM, not just a fake busy loop."""
    if not _deep_stack_available() or not _endpoint_reachable():
        pytest.skip(_NEEDS_STACK + " + a live endpoint")
    result, bound = DeepRunner(Settings()).run_isolated(
        _slow_real_rlm_worker, args=("qwen2.5-coder:3b", _OLLAMA), timeout_ms=4000
    )
    assert bound == "wall-clock"  # host hard-killed the real RLM
    assert result is None


@pytest.mark.integration
def test_deep_runs_under_network_deny_loopback_only(tmp_path, monkeypatch):
    """AC12: Deep runs to completion under a network-deny guard with a loopback-only
    endpoint — the model path makes no non-loopback egress; sandbox runs offline."""
    if not _full_stack_available():
        pytest.skip(_NEEDS_FULL)
    import socket as _socket
    from dataclasses import replace

    from harpyja.config.settings import Settings as _Settings
    from harpyja.deep.wiring import build_deep_engine

    real_connect = _socket.socket.connect
    tripped: list[str] = []

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        try:
            import ipaddress

            if not ipaddress.ip_address(host).is_loopback:
                tripped.append(str(host))
                raise OSError("network-deny: non-loopback blocked")
        except ValueError:
            pass  # hostnames resolved elsewhere; loopback IPs pass
        return real_connect(self, address)

    monkeypatch.setattr(_socket.socket, "connect", guarded_connect)
    (tmp_path / "auth.py").write_text("def f(t):\n    return t == 'ok'\n", encoding="utf-8")
    settings = replace(_Settings(), lm_model="qwen2.5-coder:3b", deep_max_subqueries=1)
    citations, bound = build_deep_engine(settings, str(tmp_path)).run("where are tokens validated?")
    assert isinstance(citations, list)  # completed; honest Tier-2 result (may be empty)
    assert tripped == []  # no non-loopback egress on the model path


@pytest.mark.integration
def test_deep_end_to_end_live(tmp_path):
    """AC11: mode=deep end-to-end against a live RLM + sandbox + endpoint returns a
    valid Tier-2 LocateResult (citation quality is model-dependent, so this asserts
    the pipeline shape, not specific citations)."""
    if not _full_stack_available():
        pytest.skip(_NEEDS_FULL)
    from dataclasses import replace

    from harpyja.config.settings import Settings as _Settings
    from harpyja.deep.wiring import build_deep_engine
    from harpyja.server.types import CodeSpan

    (tmp_path / "auth.py").write_text("def f(t):\n    return t == 'ok'\n", encoding="utf-8")
    settings = replace(_Settings(), lm_model="qwen2.5-coder:3b", deep_max_subqueries=1)
    citations, bound = build_deep_engine(settings, str(tmp_path)).run("how are tokens validated?")
    # Pipeline completed end-to-end and produced valid (possibly empty) CodeSpans;
    # `source_tier=2` is stamped at the orchestrator boundary (covered by AC1).
    assert isinstance(citations, list)
    assert all(isinstance(c, CodeSpan) for c in citations)
