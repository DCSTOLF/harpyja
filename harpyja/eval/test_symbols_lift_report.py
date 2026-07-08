"""Spec 0030 (AC5): Symbols lift-report schema — durable JSON artifact.

The lift report is a version-stamped JSON document carrying per-case measurement
results (before/after buckets using 0029 labels) plus provenance (model tag,
endpoint, settings overrides, case IDs, degrade status).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


def test_lift_report_schema_is_version_stamped_and_validated():
    # AC5: the report carries a pinned SCHEMA_VERSION, per-case buckets with 0029
    # labels (WRONG_FILE / RIGHT_FILE_WRONG_SPAN / CORRECT), model tag, endpoint
    # proof, settings overrides, case IDs, and harness degrade status.
    from harpyja.eval.symbols_lift_report import LiftReport, validate_lift_report

    report = LiftReport(
        schema_version="0030/1",
        model_tag="hf.co/Qwen/Qwen3-8B-GGUF:latest",
        endpoint="http://127.0.0.1:11434/v1",
        settings_overrides={"scout_max_turns": 12},
        cases=[
            {
                "case_id": "django-12774",
                "before_bucket": "RIGHT_FILE_WRONG_SPAN",
                "after_bucket": "CORRECT",
            },
            {
                "case_id": "astropy-12907",
                "before_bucket": "WRONG_FILE",
                "after_bucket": "WRONG_FILE",
            },
        ],
        harness_degrade_status="clean",
    )

    # Validate the schema.
    assert validate_lift_report(report)
    assert report["schema_version"] == "0030/1"
    assert len(report["cases"]) == 2
    # Per-case buckets use 0029 labels.
    assert report["cases"][0]["after_bucket"] == "CORRECT"
    assert report["cases"][1]["before_bucket"] == "WRONG_FILE"


def test_lift_report_writes_outside_repo_atomically(tmp_path):
    # AC5: lift report is written outside the repo via atomic write (same pattern
    # as eval/report.py). Atomic write uses temp + os.replace to prevent partial writes.
    from harpyja.eval.symbols_lift_report import write_lift_report

    outside_dir = tmp_path / "output"
    outside_dir.mkdir()

    report = {
        "schema_version": "0030/1",
        "model_tag": "test-model",
        "endpoint": "http://localhost:11434/v1",
        "settings_overrides": {},
        "cases": [],
        "harness_degrade_status": "clean",
    }

    # Write outside repo via atomic operation.
    output_file = outside_dir / "lift_report.json"
    write_lift_report(report, str(output_file))
    assert output_file.exists()
    written = json.loads(output_file.read_text())
    assert written["model_tag"] == "test-model"
    assert written["schema_version"] == "0030/1"
