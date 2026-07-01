"""Assemble a real `VerificationGate` for a repo (the production `gate_factory`).

Mirrors `scout/wiring.py` and `deep/wiring.py`: the orchestrator stays
seam-injected (`gate=...`), and this builder supplies the live default. The gate
reuses the loaded `scout_model` as a relevance judge, routed through the single
outbound caller (`ModelGateway.complete`) with the air-gap asserted before egress.
"""

from __future__ import annotations

from harpyja.config.settings import Settings
from harpyja.gateway.gateway import ModelGateway
from harpyja.orchestrator.gate import VerificationGate, make_scout_model_judge


def build_verification_gate(settings: Settings, repo_path: str) -> VerificationGate:
    """Construct a live `VerificationGate` (used as a `gate_factory`).

    `repo_path` is accepted for factory-signature symmetry with the Scout/Deep
    builders; the gate is repo-agnostic (the repo is passed per `verify` call).
    """
    gateway = ModelGateway(
        api_base=settings.lm_api_base,
        model=settings.scout_model,
        allow_remote=settings.allow_remote,
        timeout_s=settings.lm_http_timeout_s,  # spec 0017 (B3): the observed hang path
    )
    return VerificationGate(gateway, judge=make_scout_model_judge(gateway, settings))
