"""Spec 0039 — AC7: committed claim artifact contract (typed, archive-first).

The claim is the spec's durable deliverable: on the gated branch the AC5
pre-check's typed ``UNDER_POWERED_STOP`` (the honest arithmetic: projected
conceptual upper bound 6 < floor 8), on a completed run the split report. It is
test-pinned to COMPUTED truth — the claim cannot exist saying something the
committed evidence does not back."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

from harpyja.eval.think_ab import (
    AB_CONFIG_HASH_0039,
    AB_REPORT_OUTCOMES,
    PREREGISTERED_AB_CONFIG_0039,
    AbConfig,
)

AB_CLAIM_SCHEMA_VERSION = "0039/1"

_KNOWN_CLAIM_SCHEMA_VERSIONS = frozenset({AB_CLAIM_SCHEMA_VERSION})

_CLAIM_STATUSES = frozenset({"gated-under-powered-stop", "completed"})


class AbClaimError(ValueError):
    """A claim.json that does not conform to the 0039/1 contract."""


def validate_ab_claim(obj: dict[str, Any]) -> None:
    version = obj.get("schema_version")
    if version not in _KNOWN_CLAIM_SCHEMA_VERSIONS:
        raise AbClaimError(f"unknown ab-claim schema_version: {version!r}")
    if obj.get("config_hash") != AB_CONFIG_HASH_0039:
        raise AbClaimError(
            "claim cites a different frozen config hash than "
            "PREREGISTERED_AB_CONFIG_0039"
        )
    status = obj.get("status")
    if status not in _CLAIM_STATUSES:
        raise AbClaimError(f"claim status {status!r} not in {sorted(_CLAIM_STATUSES)}")
    headline = obj.get("headline")
    if not (headline in AB_REPORT_OUTCOMES or str(headline).startswith("conceptual:")):
        raise AbClaimError(f"claim headline {headline!r} is not a typed outcome")
    if status == "gated-under-powered-stop" and "precheck" not in obj:
        raise AbClaimError("a gated claim must carry the pre-check outcome")
    if status == "completed" and "report" not in obj:
        raise AbClaimError("a completed claim must carry the split report")


def _spec_evidence_path(filename: str) -> Path:
    """specs/.archive first (the 79f7bf2 evidence-path convention), live fallback."""
    root = Path(__file__).resolve().parents[2]
    archived = root / "specs" / ".archive" / "0039-thinking-ab" / filename
    live = root / "specs" / "0039-thinking-ab" / filename
    return archived if archived.is_file() else live


def committed_ab_claim_path() -> Path:
    return _spec_evidence_path("claim.json")


def committed_findings_path() -> Path:
    return _spec_evidence_path("findings.md")


def load_committed_ab_claim() -> dict[str, Any]:
    path = committed_ab_claim_path()
    if not path.is_file():
        raise AbClaimError(f"committed ab claim not found: {path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise AbClaimError(f"claim must be a JSON object, got {type(obj).__name__}")
    validate_ab_claim(obj)
    return obj


def build_gated_claim(cfg: AbConfig = PREREGISTERED_AB_CONFIG_0039) -> dict[str, Any]:
    """Assemble the gated-branch claim FROM the computed pre-check — the claim
    is derived from evidence, never hand-authored."""
    from harpyja.eval.think_ab_precheck import run_precheck

    outcome = run_precheck(cfg)
    if outcome.outcome != "under-powered-stop":
        raise AbClaimError(
            "build_gated_claim called but the pre-check PROCEEDS — emit the "
            "completed-run claim from the driver result instead"
        )
    return {
        "schema_version": AB_CLAIM_SCHEMA_VERSION,
        "config_hash": AB_CONFIG_HASH_0039,
        "status": "gated-under-powered-stop",
        "headline": "under-powered-stop",
        "precheck": dataclasses.asdict(outcome),
    }
