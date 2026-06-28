"""Pinned eval report schema + writer (AC4, AC7, D7).

The schema is enumerated and version-stamped so callers and tests branch on stable
field names. `validate_report` is loud — a missing field raises `ReportSchemaError`
rather than producing a half-populated report that reads as complete.

Undefined gate metrics are serialized as an explicit `null` paired with their
(zero) count field (D2), so "all metrics populated" (AC7) is honored by a present
null-with-count, never an omitted key.

`write_report` refuses to write inside the indexed/target repo (read-only
guardrail; mirrors the FastContext `trajectory_file`-outside-repo precedent) and
writes atomically via a same-dir temp + `os.replace`.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

SCHEMA_VERSION = "0009-6a/1"

# D7 — enumerated required field names (the pinned contract).
_RUN_METADATA_FIELDS = (
    "repo_revision",
    "seed_n",
    "n_floor",
    "indicative_only",
    "mode",
    "k_runs",
    "settings_snapshot",
    "timestamp",
    "artifact_dir",
)
_SETTINGS_SNAPSHOT_FIELDS = ("verify_method", "verify_threshold", "verify_top_n")
_CASE_FIELDS = (
    "case_id",
    "query",
    "classification",
    "expected_spans",
    "citations",
    "tiers_run",
    "terminal_tier",
    "escalated_to_deep",
    "gate_eligible",
    "gate_triggered",
    "tier1_correct",
    "span_hit_primary",
    "span_hit_secondary",
    "notes",
)
_AGGREGATE_FIELDS = (
    "span_hit_rate_primary",
    "span_hit_rate_secondary",
    "escalation_rate",
    "tier01_resolve_rate",
    "gate_catch_rate",
    "caught_count",
    "wrong_tier1_count",
    "gate_false_escalation",
    "false_escalated_count",
    "correct_tier1_count",
    "per_tier_latency_ms",
    "per_tier_model_calls",
)


class ReportSchemaError(Exception):
    """A report was missing a required field or had the wrong shape."""


def build_report(
    run_metadata: Mapping[str, object],
    cases: Sequence[Mapping[str, object]],
    aggregate: Mapping[str, object],
) -> dict:
    """Assemble a single-run report from its three blocks.

    Assembly does not validate — `validate_report` is the separate, explicit gate
    (called by `write_report` before any bytes hit disk, and directly in tests).
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "run_metadata": dict(run_metadata),
        "cases": [dict(c) for c in cases],
        "aggregate": dict(aggregate),
    }


def _require_keys(obj: object, fields: Sequence[str], where: str) -> None:
    if not isinstance(obj, Mapping):
        raise ReportSchemaError(f"{where} must be an object, got {type(obj).__name__}")
    for f in fields:
        if f not in obj:
            raise ReportSchemaError(f"{where}: missing required field {f!r}")


def validate_report(report: object) -> None:
    """Raise `ReportSchemaError` unless `report` conforms to the pinned schema."""
    _require_keys(report, ("schema_version", "run_metadata", "cases", "aggregate"), "report")
    assert isinstance(report, Mapping)  # narrowed by _require_keys
    if report["schema_version"] != SCHEMA_VERSION:
        raise ReportSchemaError(
            f"schema_version {report['schema_version']!r} != {SCHEMA_VERSION!r}"
        )
    _require_keys(report["run_metadata"], _RUN_METADATA_FIELDS, "run_metadata")
    _require_keys(
        report["run_metadata"]["settings_snapshot"],
        _SETTINGS_SNAPSHOT_FIELDS,
        "run_metadata.settings_snapshot",
    )
    cases = report["cases"]
    if not isinstance(cases, Sequence):
        raise ReportSchemaError("cases must be a list")
    for i, case in enumerate(cases):
        _require_keys(case, _CASE_FIELDS, f"cases[{i}]")
    _require_keys(report["aggregate"], _AGGREGATE_FIELDS, "aggregate")


def _is_within(child: Path, parent: Path) -> bool:
    child = child.resolve()
    parent = parent.resolve()
    return child == parent or parent in child.parents


def atomic_write_json(
    payload: Mapping[str, object],
    *,
    out_dir: str | Path,
    repo_path: str | Path,
    filename: str,
) -> Path:
    """Write `payload` as JSON under `out_dir`, atomically (same-dir temp + replace).

    Refuses (raises `ValueError`) if `out_dir` is the indexed repo or within it —
    the harness is read-only on the target tree (mirrors the FastContext
    `trajectory_file`-outside-repo precedent). Shared by the single-run report
    writer and the sweep writer so the guard + atomicity live in one place.
    """
    out_dir = Path(out_dir)
    if _is_within(out_dir, Path(repo_path)):
        raise ValueError(
            f"refusing to write eval artifacts inside the indexed repo: "
            f"out_dir={out_dir} is within repo_path={repo_path}"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / filename
    data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    fd, tmp_name = tempfile.mkstemp(dir=out_dir, prefix=f".{filename}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp_name, target)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return target


def write_report(
    report: Mapping[str, object],
    *,
    out_dir: str | Path,
    repo_path: str | Path,
) -> Path:
    """Validate `report` then write it as `report.json` under `out_dir`, atomically."""
    validate_report(report)
    return atomic_write_json(report, out_dir=out_dir, repo_path=repo_path, filename="report.json")
