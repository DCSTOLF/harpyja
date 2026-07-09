"""Persistent live-test artifacts (spec 0035 AC7 — harness, non-SUT).

Three bucket-unanswerable re-runs were forced by TemporaryDirectory artifacts
(0032 astropy, 0033-T14, 0034-AC5). Live integration tests write to a
persistent gitignored location instead, via the SAME outside-repo atomic
writer.
"""

import dataclasses
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from harpyja.config.settings import Settings
from harpyja.eval.live_artifacts import live_artifact_dir, write_live_artifact

_HARPYJA_ROOT = Path(__file__).resolve().parents[2]


def test_live_artifact_dir_path_shape():
    """AC7: <root>/eval_work/live_artifacts/<test>/<UTC-basic-timestamp>-<pid>/."""
    now = datetime(2026, 7, 9, 12, 34, 56, tzinfo=timezone.utc)
    out = live_artifact_dir("some_test", now=now, pid=4242)
    assert out == (_HARPYJA_ROOT / "eval_work" / "live_artifacts" / "some_test"
                   / "20260709T123456Z-4242")


def test_live_artifact_dir_defaults_are_now_and_pid():
    out = live_artifact_dir("t")
    assert out.name.endswith(f"-{os.getpid()}")
    assert out.parent.name == "t"


def test_write_live_artifact_reuses_atomic_write_json_outside_target_repo(tmp_path):
    """AC7: with the TARGET repo distinct from the artifact dir, the write lands."""
    fake_repo = tmp_path / "target_repo"
    fake_repo.mkdir()
    path = write_live_artifact(
        {"k": 1}, test_name="unit_probe", repo_path=str(fake_repo),
        filename="artifact.json",
    )
    assert path.exists()
    assert "eval_work/live_artifacts/unit_probe" in str(path)


def test_write_live_artifact_refuses_inside_target_repo():
    """AC7 (the conflation bug pinned): when the target repo CONTAINS the out dir,
    the atomic writer's inside-repo refusal fires."""
    with pytest.raises(ValueError):
        write_live_artifact(
            {"k": 1}, test_name="unit_probe", repo_path=str(_HARPYJA_ROOT),
            filename="artifact.json",
        )


def test_live_artifacts_base_path_is_not_a_settings_field():
    """AC7: eval-knobs-disjoint — no Settings field names the artifact base."""
    names = {f.name for f in dataclasses.fields(Settings)}
    assert not any("live_artifact" in n or "eval_work" in n for n in names)
