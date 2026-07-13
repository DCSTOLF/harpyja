"""Spec 0045 — AC5/AC6 integration smoke: the committed refinement driver
STOPS-AND-WARNS on missing live infra rather than silently passing, and the
named cells (the 0044 residual + the never-fired fu cell + the rescued flask
cells) are IN the pinned re-measurement coverage.

Skip-not-fail under the 0041 opt-in default (``-m "not integration"``
deselects this file); strict under HARPYJA_REQUIRE_LIVE_STACK. The smoke NEVER
fires live cells: it only exercises the driver's refusal path when the stack is
absent, and skips when a live stack is present (the closure run is T24 — an
operator action, not a test; the 0043/0044 precedent).

Lives in ``harpyja/eval/`` so the suite collects it (specs/ is not on the
pytest collection path — the 0041/0042/0043/0044 precedent).
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

from harpyja.eval.locate_probe import require_live_stack
from harpyja.eval.refinement_config import PREREGISTERED_REFINEMENT_CONFIG_0045

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DRIVER_ARCHIVED = (
    _REPO_ROOT / "specs" / ".archive" / "0045-refinement" / "refinement_run"
    / "run_refinement.py"
)
_DRIVER_LIVE = (
    _REPO_ROOT / "specs" / "0045-refinement" / "refinement_run" / "run_refinement.py"
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
def test_named_cells_enumerated_in_coverage():
    """AC6: the residual (django-14315::8b), the never-fired fu cell
    (pytest-10081::14b), and the rescued flask-5014 cells are inside the pinned
    coverage, so the gated re-run re-checks them by construction."""
    cfg = PREREGISTERED_REFINEMENT_CONFIG_0045
    assert "django__django-14315" in cfg.pilot_case_ids
    assert "pytest-dev__pytest-10081" in cfg.pilot_case_ids
    assert "pallets__flask-5014" in cfg.pilot_case_ids
    assert "qwen3:14b" in cfg.required_models
    assert "qwen3:8b" in cfg.optional_models
    # The named-cell fields point at real coverage cells.
    assert cfg.residual_cell.split("::")[0] in cfg.pilot_case_ids
    assert cfg.never_fired_cell.split("::")[0] in cfg.pilot_case_ids


@pytest.mark.integration
def test_refinement_driver_stops_and_warns_without_live_infra():
    residents = _residents()
    if residents is not None:
        pytest.skip(
            "live stack reachable — the closure run is T24 (an operator "
            "action); this smoke only proves the STOP-AND-WARN refusal path"
        )
    if require_live_stack(False) == "fail":
        pytest.fail("Ollama unreachable (HARPYJA_REQUIRE_LIVE_STACK set)")

    ledger = _DRIVER.parent / "refinement_results.json"
    existed_before = ledger.exists()
    proc = subprocess.run(
        [sys.executable, str(_DRIVER)],
        cwd=str(_REPO_ROOT), capture_output=True, text=True, timeout=120,
        check=False,
    )
    # Missing live infra is a TYPED stop (exit 2) — loud, never a silent pass.
    assert proc.returncode == 2, (proc.stdout, proc.stderr)
    assert "STOP-AND-WARN" in proc.stderr
    assert ledger.exists() == existed_before
