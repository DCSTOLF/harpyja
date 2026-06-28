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
