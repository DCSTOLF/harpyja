"""Spec 0041 — the exclusive-endpoint gate contract + check (AC1).

A run that starts against a contended endpoint produces invalid cells that are
INDISTINGUISHABLE from honest empties and real typed timeouts (the 0040 run-1
contamination). The gate REFUSES — a typed stop, never a warning, no bypass
parameter — and every check is RECORDED so a past run's validity is auditable
from its artifact (the 0031–0038 posture: a run must PROVE its conditions).

The record's claim never exceeds the mechanism (the 0039/0040 epistemic-labeling
discipline): ``/api/ps`` exposes RESIDENT MODELS (tag + expires_at), not queued
or in-flight requests, so ``exclusivity_check_kind`` names the actual strength
(``start-plus-per-block``) and the record carries the TWO residuals the check
structurally cannot see — the intra-block window (a foreign tag that loads and
fully unloads between two checks) and same-tag contention (a concurrent client
on a tag inside the frozen model set; carried by the opt-in test default and
the single-operator context, never implied covered).
"""

from __future__ import annotations

import datetime as _dt
import json
import urllib.request
from collections.abc import Callable, Iterable, Sequence
from typing import Any

from harpyja.gateway.gateway import assert_local

__all__ = [
    "EXCLUSIVITY_CHECK_KIND",
    "EXCLUSIVITY_SCHEMA_VERSION",
    "EXCLUSIVITY_UNSEEABLE_RESIDUALS",
    "ExclusiveEndpointContended",
    "ExclusivityError",
    "build_exclusivity_record",
    "check_exclusive_endpoint",
    "foreign_residents",
    "validate_exclusivity_record",
]

EXCLUSIVITY_SCHEMA_VERSION = "0041/exclusivity/1"

_KNOWN_SCHEMA_VERSIONS = frozenset({EXCLUSIVITY_SCHEMA_VERSION})

# The actual strength of the check — a start gate plus a re-check before each
# model block. NOT continuous run-duration proof; never label it as such.
EXCLUSIVITY_CHECK_KIND = "start-plus-per-block"

# What /api/ps structurally cannot see. Named in every record so the claim
# and the mechanism can never silently diverge.
EXCLUSIVITY_UNSEEABLE_RESIDUALS = ("intra-block-window", "same-tag-contention")

_REQUIRED_CHECK_KEYS = frozenset({"timestamp", "clean"})


class ExclusivityError(ValueError):
    """An exclusivity record that does not conform — loud, never defaulted."""


class ExclusiveEndpointContended(RuntimeError):
    """Typed stop: the endpoint is not exclusively available. Refuse, don't warn."""

    stop_id = "exclusive-endpoint-contended"

    def __init__(
        self,
        foreign: Sequence[str],
        *,
        label: str,
        residents: Sequence[str] = (),
        timestamp: str | None = None,
    ):
        self.foreign = list(foreign)
        self.label = label
        self.residents = list(residents)
        self.timestamp = timestamp
        super().__init__(
            f"[{self.stop_id}] endpoint not exclusive at check {label!r}: "
            f"foreign resident(s) {self.foreign} — STOP; no cells may run. "
            "Clear the endpoint and re-invoke (there is no bypass). Note the "
            f"check cannot see {list(EXCLUSIVITY_UNSEEABLE_RESIDUALS)}."
        )

    def as_failed_check(self) -> dict[str, Any]:
        """The failed check as a recordable entry — the refusal itself is
        auditable from the artifact (the contamination boundary)."""
        return {
            "label": self.label,
            "timestamp": self.timestamp,
            "clean": False,
            "residents": self.residents,
            "foreign": self.foreign,
        }


def foreign_residents(
    residents: Iterable[str], model_set: Iterable[str]
) -> list[str]:
    """Resident tags NOT in the frozen run config's model set — the pinned
    predicate. The run's own configured models are never foreign (the driver's
    block-by-block loads must not self-trigger the gate)."""
    allowed = set(model_set)
    return [tag for tag in residents if tag not in allowed]


def build_exclusivity_record(
    *, checks: Sequence[dict[str, Any]], model_set: Iterable[str]
) -> dict[str, Any]:
    """Assemble the run-level exclusivity record carried by the ledger."""
    record = {
        "schema_version": EXCLUSIVITY_SCHEMA_VERSION,
        "exclusivity_check_kind": EXCLUSIVITY_CHECK_KIND,
        "unseeable_residuals": list(EXCLUSIVITY_UNSEEABLE_RESIDUALS),
        "model_set": list(model_set),
        "checks": [dict(c) for c in checks],
    }
    validate_exclusivity_record(record)
    return record


def validate_exclusivity_record(obj: dict[str, Any]) -> None:
    """Loudly reject any non-conforming exclusivity record."""
    version = obj.get("schema_version")
    if version not in _KNOWN_SCHEMA_VERSIONS:
        raise ExclusivityError(f"unknown exclusivity schema_version: {version!r}")
    if obj.get("exclusivity_check_kind") != EXCLUSIVITY_CHECK_KIND:
        raise ExclusivityError(
            "exclusivity_check_kind must record the actual strength "
            f"{EXCLUSIVITY_CHECK_KIND!r}, got {obj.get('exclusivity_check_kind')!r}"
        )
    if tuple(obj.get("unseeable_residuals") or ()) != EXCLUSIVITY_UNSEEABLE_RESIDUALS:
        raise ExclusivityError(
            "record must name exactly the unseeable residuals "
            f"{list(EXCLUSIVITY_UNSEEABLE_RESIDUALS)}, "
            f"got {obj.get('unseeable_residuals')!r}"
        )
    model_set = obj.get("model_set")
    if not isinstance(model_set, list) or not model_set:
        raise ExclusivityError(
            "record must carry the frozen model_set the predicate ran against"
        )
    checks = obj.get("checks")
    if not isinstance(checks, list) or not checks:
        raise ExclusivityError("record must carry at least one recorded check")
    for i, check in enumerate(checks):
        if not isinstance(check, dict) or not _REQUIRED_CHECK_KEYS <= set(check):
            missing = _REQUIRED_CHECK_KEYS - set(
                check if isinstance(check, dict) else ()
            )
            raise ExclusivityError(f"check[{i}] missing keys: {sorted(missing)}")


def _default_ps_reader(api_base: str) -> list[str]:
    """Read the resident model tags from ``/api/ps``. Only ever reached after
    ``assert_local`` has passed, so the URL is loopback."""
    with urllib.request.urlopen(f"{api_base}/api/ps", timeout=10) as r:  # noqa: S310
        return [m["name"] for m in json.loads(r.read())["models"]]


def check_exclusive_endpoint(
    api_base: str,
    model_set: Iterable[str],
    *,
    label: str = "start",
    ps_reader: Callable[[str], list[str]] | None = None,
    resolver: Callable[[str], list[str]] | None = None,
    now: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """One exclusivity check: assert_local FIRST (the 0019 rule — ``/api/ps``
    is the same loopback-gated egress class as ``/api/tags``), then read the
    residents and apply the pinned foreign predicate. Foreign resident →
    :class:`ExclusiveEndpointContended` (typed stop, no bypass); exclusive →
    a clean check record (result + timestamp) for the run artifact."""
    assert_local(api_base, resolver=resolver)
    residents = (ps_reader or _default_ps_reader)(api_base)
    foreign = foreign_residents(residents, model_set)
    timestamp = (
        now() if now is not None else _dt.datetime.now(_dt.UTC).isoformat()
    )
    if foreign:
        raise ExclusiveEndpointContended(
            foreign, label=label, residents=residents, timestamp=timestamp
        )
    return {
        "label": label,
        "timestamp": timestamp,
        "clean": True,
        "residents": list(residents),
        "foreign": [],
    }
