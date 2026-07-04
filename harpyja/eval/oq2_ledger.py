"""Spec 0020 (D8/AC2) — the gate-ledger: a new pinned artifact (`0020/1`).

Distinct from the sweep report (`report.py`, `0014/1`): the ledger records the
sequential protocol's per-gate verdicts (with each gate's measured sub-values and the
close/hold cause), the terminal G3 label with all D/G/S booleans, and run provenance
(SUT git SHA, resolved `EvalConfig`, fixture-subset id, model tags, the sweep grid) so
a STOP/BLOCKED verdict is reproducible.

The validator is loud (a missing field raises `LedgerSchemaError`), mirroring
`report.validate_report`. Writing reuses `report.atomic_write_json`, so the
outside-the-indexed-repo guard + atomicity live in exactly one place.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path

from harpyja.eval.oq2_classify import G3Classification
from harpyja.eval.report import atomic_write_json

# Own version id, deliberately distinct from report.SCHEMA_VERSION ("0014/1").
LEDGER_SCHEMA_VERSION = "0020/1"

_LEDGER_TOP_FIELDS = ("ledger_version", "disposition", "outcome", "gates", "g3", "provenance")
_PROVENANCE_FIELDS = ("sut_git_sha", "eval_config", "fixture_subset_id", "model_tags", "grid")
# Every per-gate verdict carries at minimum which gate it is and its status; the
# measured sub-values are gate-specific and travel as extra keys (not re-enumerated
# here, so a new measured field never needs a validator bump).
_GATE_FIELDS = ("gate", "status")


class LedgerSchemaError(Exception):
    """A gate-ledger was missing a required field or had the wrong shape."""


def build_gate_ledger(
    *,
    disposition: str,
    outcome: str,
    gates: Sequence[Mapping[str, object]],
    g3: G3Classification | None,
    provenance: Mapping[str, object],
) -> dict:
    """Assemble a gate-ledger from the accumulated verdicts (no validation here).

    `disposition` is `"close"` or `"hold"`; `outcome` is the terminal protocol label
    (`STOP:SMOKE` / `BLOCKED` / a G3 label). `g3` is `None` for any run that stopped
    before G3. Assembly does not validate — `validate_gate_ledger` is the explicit gate
    (called by `write_gate_ledger` before bytes hit disk, and directly in tests).
    """
    return {
        "ledger_version": LEDGER_SCHEMA_VERSION,
        "disposition": disposition,
        "outcome": outcome,
        "gates": [dict(g) for g in gates],
        "g3": asdict(g3) if g3 is not None else None,
        "provenance": dict(provenance),
    }


def _require_keys(obj: object, fields: Sequence[str], where: str) -> None:
    if not isinstance(obj, Mapping):
        raise LedgerSchemaError(f"{where} must be an object, got {type(obj).__name__}")
    for f in fields:
        if f not in obj:
            raise LedgerSchemaError(f"{where}: missing required field {f!r}")


def validate_gate_ledger(ledger: object) -> None:
    """Raise `LedgerSchemaError` unless `ledger` conforms to the pinned `0020/1` schema."""
    _require_keys(ledger, _LEDGER_TOP_FIELDS, "ledger")
    assert isinstance(ledger, Mapping)  # narrowed by _require_keys
    if ledger["ledger_version"] != LEDGER_SCHEMA_VERSION:
        raise LedgerSchemaError(
            f"ledger_version {ledger['ledger_version']!r} != {LEDGER_SCHEMA_VERSION!r}"
        )
    gates = ledger["gates"]
    if not isinstance(gates, Sequence):
        raise LedgerSchemaError("gates must be a list")
    for i, gate in enumerate(gates):
        _require_keys(gate, _GATE_FIELDS, f"gates[{i}]")
    # g3 is either null (stopped before G3) or a full classification block.
    g3 = ledger["g3"]
    if g3 is not None:
        _require_keys(
            g3,
            ("label", "degraded_dominated", "gate_confounded", "no_survivor", "indicative_only"),
            "g3",
        )
    _require_keys(ledger["provenance"], _PROVENANCE_FIELDS, "provenance")


def write_gate_ledger(
    ledger: Mapping[str, object],
    *,
    out_dir: str | Path,
    repo_path: str | Path,
) -> Path:
    """Validate `ledger` then write it as `gate_ledger.json` under `out_dir`, atomically."""
    validate_gate_ledger(ledger)
    return atomic_write_json(
        ledger, out_dir=out_dir, repo_path=repo_path, filename="gate_ledger.json"
    )
