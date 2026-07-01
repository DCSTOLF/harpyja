"""RED (spec 0008, T18): production gate wiring.

`build_verification_gate` is the production `gate_factory` (mirrors
`scout/wiring.py` and `deep/wiring.py`): it builds a `VerificationGate` over a
ModelGateway pointed at the local endpoint with the `scout_model` as judge.
"""

import pytest

from harpyja.config.settings import Settings
from harpyja.gateway.gateway import AirGapError
from harpyja.orchestrator.gate import VerificationGate
from harpyja.orchestrator.wiring import build_verification_gate


def test_build_verification_gate_returns_gate():
    gate = build_verification_gate(Settings(), "/some/repo")
    assert isinstance(gate, VerificationGate)


def test_build_verification_gate_is_loopback_air_gapped():
    # The gate's gateway asserts loopback; a non-loopback endpoint is a floor error.
    gate = build_verification_gate(Settings(), "/some/repo")
    gate.gateway.assert_local()  # default loopback endpoint passes

    remote = Settings(lm_api_base="http://10.0.0.5:11434/v1")
    remote_gate = build_verification_gate(remote, "/some/repo")
    with pytest.raises(AirGapError):
        remote_gate.gateway.assert_local()


def test_build_verification_gate_threads_http_timeout():
    # Spec 0017 AC10: the observed B3 hang path — the gate gateway carries the
    # configured timeout. A non-default value proves it's drawn from Settings, not
    # the shared 120.0 field default or a literal.
    gate = build_verification_gate(Settings(lm_http_timeout_s=7.5), "/some/repo")
    assert gate.gateway.timeout_s == 7.5


def _judge_model(gate, monkeypatch) -> str:
    """Capture which model the built gate's judge passes to `complete`."""
    captured: dict = {}

    def spy_complete(messages, **params):
        captured["model"] = params.get("model")
        return "0.5"

    monkeypatch.setattr(gate.gateway, "complete", spy_complete)
    gate._judge("q", "span")
    return captured["model"]


def test_build_verification_gate_dispatches_instruct_by_default(monkeypatch):
    # Spec 0018 AC8: `verify_method` selects the judge; the default `instruct_model`
    # scores via `lm_model`, NOT the finder `scout_model`.
    settings = Settings()
    gate = build_verification_gate(settings, "/some/repo")
    assert _judge_model(gate, monkeypatch) == settings.lm_model


def test_build_verification_gate_dispatches_scout_model(monkeypatch):
    # Spec 0018 AC8 / D5: the retained `scout_model` method still dispatches to the
    # finder judge over `scout_model` (the A/B baseline).
    settings = Settings(verify_method="scout_model")
    gate = build_verification_gate(settings, "/some/repo")
    assert _judge_model(gate, monkeypatch) == settings.scout_model
