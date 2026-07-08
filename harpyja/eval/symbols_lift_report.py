"""Spec 0030 (AC5): Symbols lift-report schema — durable JSON artifact.

Version-stamped, provenance-complete lift report for measuring the symbols tool's
impact on the 0029 baseline cases (astropy-12907, django-12774).

Per-case buckets use the 0029 outcome labels: WRONG_FILE / RIGHT_FILE_WRONG_SPAN / CORRECT.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, TypedDict

SCHEMA_VERSION = "0030/1"


class CaseResult(TypedDict):
    """Per-case lift result: before and after buckets."""

    case_id: str
    before_bucket: str  # 0029 label: WRONG_FILE, RIGHT_FILE_WRONG_SPAN, CORRECT
    after_bucket: str  # 0029 label


class LiftReport(TypedDict):
    """Complete lift-report schema."""

    schema_version: str
    model_tag: str
    endpoint: str
    settings_overrides: dict[str, Any]
    cases: list[CaseResult]
    harness_degrade_status: str  # "clean" or degrade reason


def validate_lift_report(report: LiftReport) -> bool:
    """Validate that a lift report conforms to the schema."""
    required_keys = {
        "schema_version",
        "model_tag",
        "endpoint",
        "settings_overrides",
        "cases",
        "harness_degrade_status",
    }
    if not all(k in report for k in required_keys):
        return False
    # Schema version must match pinned version.
    if report["schema_version"] != SCHEMA_VERSION:
        return False
    # Cases must have the required fields.
    for case in report["cases"]:
        if not all(k in case for k in ("case_id", "before_bucket", "after_bucket")):
            return False
    return True


def write_lift_report(report: dict[str, Any], output_path: str) -> None:
    """Write lift report atomically, outside the repo.

    Raises ValueError if output_path is inside the repo (repo_path must be detected).
    Uses atomic temp + os.replace pattern (same as eval/report.py).
    """
    output_path_obj = Path(output_path)

    # Atomic write: temp file in the same directory, then replace.
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=output_path_obj.parent,
        prefix=f".{output_path_obj.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)
        os.replace(tmp_name, output_path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
