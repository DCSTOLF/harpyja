"""Spec 0044 — AC6/AC7 integration smoke: the committed submission driver
STOPS-AND-WARNS on missing live infra rather than silently passing, and the
0043 casualty cells are IN the pinned re-measurement coverage.

Skip-not-fail under the 0041 opt-in default (``-m "not integration"``
deselects this file); strict under HARPYJA_REQUIRE_LIVE_STACK. The smoke
NEVER fires live cells: it only exercises the driver's refusal path when the
stack is absent, and skips when a live stack is present (the closure run is
T22 — an operator action, not a test; the 0043 precedent).

Lives in ``harpyja/eval/`` so the suite collects it (the 0041/0042/0043
precedent — specs/ is not on the pytest collection path).
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

from harpyja.eval.locate_probe import require_live_stack
from harpyja.eval.submission_config import PREREGISTERED_SUBMISSION_CONFIG_0044

_REPO_ROOT = Path(__file__).resolve().parents[2]
# Evidence-path convention: specs/.archive first, live specs/ fallback.
_DRIVER_ARCHIVED = (
    _REPO_ROOT
    / "specs" / ".archive" / "0044-submission" / "submission_run"
    / "run_submission.py"
)
_DRIVER_LIVE = (
    _REPO_ROOT / "specs" / "0044-submission" / "submission_run" / "run_submission.py"
)
_DRIVER = _DRIVER_ARCHIVED if _DRIVER_ARCHIVED.is_file() else _DRIVER_LIVE
_API = "http://127.0.0.1:11434"


def _residents() -> list[str] | None:
    try:
        with urllib.request.urlopen(f"{_API}/api/ps", timeout=5) as r:
            return [m["name"] for m in json.loads(r.read())["models"]]
    except Exception:  # noqa: BLE001
        return None


@pytest.mark.integration
def test_0043_casualty_cells_enumerated():
    """AC7: flask-5014 (14b + 8b) and django-14315::8b — the cells the
    UNCONDITIONAL nudge regressed correct→worse — are inside the pinned
    coverage, so the gated re-run re-checks them by construction (the
    conditioned nudge must hold them correct)."""
    cfg = PREREGISTERED_SUBMISSION_CONFIG_0044
    assert "pallets__flask-5014" in cfg.pilot_case_ids
    assert "django__django-14315" in cfg.pilot_case_ids
    # 14b runs always (required); 8b is a frozen optional the closure run
    # enables — both casualty models are named in the frozen coverage.
    assert "qwen3:14b" in cfg.required_models
    assert "qwen3:8b" in cfg.optional_models


@pytest.mark.integration
def test_submission_driver_stops_and_warns_without_live_infra():
    residents = _residents()
    if residents is not None:
        pytest.skip(
            "live stack reachable — the closure run is T22 (an operator "
            "action); this smoke only proves the STOP-AND-WARN refusal path"
        )
    if require_live_stack(False) == "fail":
        pytest.fail("Ollama unreachable (HARPYJA_REQUIRE_LIVE_STACK set)")

    ledger = _DRIVER.parent / "submission_results.json"
    existed_before = ledger.exists()
    proc = subprocess.run(
        [sys.executable, str(_DRIVER)],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    # Missing live infra is a TYPED stop (exit 2) — loud, never a silent
    # pass, never a traceback-shaped exit 1.
    assert proc.returncode == 2, (proc.stdout, proc.stderr)
    assert "STOP-AND-WARN" in proc.stderr
    assert ledger.exists() == existed_before
