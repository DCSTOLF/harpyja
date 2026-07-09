"""Persistent live-test artifact locations (spec 0035 AC7 — harness, non-SUT).

Live integration tests historically wrote verifier artifacts into a
``TemporaryDirectory`` — three bucket-unanswerable re-runs were forced by
artifacts discarded that way (0032 astropy, 0033-T14, 0034-AC5). This module
gives them a persistent, gitignored home under ``eval_work/live_artifacts/``,
reusing the SAME outside-repo atomic writer (`report.atomic_write_json`) so the
inside-repo refusal and atomic same-dir-temp semantics are inherited, never
re-implemented. The base path is deliberately NOT a `Settings` field
(eval-knobs-disjoint): it is a harness location, not a knob the SUT reads.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harpyja.eval.report import atomic_write_json

# The harpyja repo root (this file is harpyja/eval/live_artifacts.py).
_HARPYJA_ROOT = Path(__file__).resolve().parents[2]


def live_artifact_dir(
    test_name: str,
    *,
    now: datetime | None = None,
    pid: int | None = None,
) -> Path:
    """A persistent per-run artifact dir: basic-UTC timestamp + pid (collision rule)."""
    now = now or datetime.now(timezone.utc)
    pid = pid if pid is not None else os.getpid()
    stamp = f"{now:%Y%m%dT%H%M%SZ}-{pid}"
    return _HARPYJA_ROOT / "eval_work" / "live_artifacts" / test_name / stamp


def write_live_artifact(
    payload: dict[str, Any],
    *,
    test_name: str,
    repo_path: str | Path,
    filename: str,
    now: datetime | None = None,
    pid: int | None = None,
) -> Path:
    """Write a live-test artifact durably, outside the TARGET repo.

    ``repo_path`` is the measurement TARGET (worktree) — it must be a separate
    tree from the artifact location or the writer's inside-repo refusal fires
    (the exact conflation the tests pin).
    """
    out_dir = live_artifact_dir(test_name, now=now, pid=pid)
    return atomic_write_json(
        payload, out_dir=out_dir, repo_path=repo_path, filename=filename
    )
