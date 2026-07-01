"""Assemble a real `VerificationGate` for a repo (the production `gate_factory`).

Mirrors `scout/wiring.py` and `deep/wiring.py`: the orchestrator stays
seam-injected (`gate=...`), and this builder supplies the live default. Spec 0018
(B2 fix / D1, D3): the judge is selected by `settings.verify_method` — the default
`instruct_model` scores via the served `lm_model` (an in-distribution 0–1 scorer),
replacing the OOD `scout_model` finder that false-rejected correct citations. Either
judge routes through the single outbound caller (`ModelGateway.complete`) with the
air-gap asserted before egress; the judge sets the model per call.
"""

from __future__ import annotations

from harpyja.config.settings import Settings
from harpyja.gateway.gateway import ModelGateway
from harpyja.orchestrator.gate import VerificationGate, select_judge


def build_verification_gate(settings: Settings, repo_path: str) -> VerificationGate:
    """Construct a live `VerificationGate` (used as a `gate_factory`).

    `repo_path` is accepted for factory-signature symmetry with the Scout/Deep
    builders; the gate is repo-agnostic (the repo is passed per `verify` call).
    """
    gateway = ModelGateway(
        api_base=settings.lm_api_base,
        allow_remote=settings.allow_remote,
        timeout_s=settings.lm_http_timeout_s,  # spec 0017 (B3): the observed hang path
    )
    # Spec 0018 (D3): dispatch on `verify_method`; the judge passes its own model
    # (`lm_model` or `scout_model`) to `complete`, so the gateway's default model is
    # unused on the judge path.
    return VerificationGate(gateway, judge=select_judge(gateway, settings))
