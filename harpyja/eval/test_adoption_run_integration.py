"""Spec 0042 — AC6 integration smoke: the committed adoption driver
STOPS-AND-WARNS on missing live infra rather than silently passing.

Skip-not-fail under the 0041 opt-in default (``-m "not integration"``
deselects this file); strict under HARPYJA_REQUIRE_LIVE_STACK. The smoke
NEVER fires live cells: it only exercises the driver's refusal path when the
stack is absent, and skips when a live stack is present (the closure run is
T12 — an operator action, not a test).

Deviation from plan.md recorded: the plan placed this file under
``specs/0042-adoption/adoption_run/``; it lives in ``harpyja/eval/`` instead
so it is collected with the suite (the ``test_gate_run_integration.py``
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

_REPO_ROOT = Path(__file__).resolve().parents[2]
# Evidence-path convention: specs/.archive first, live specs/ fallback.
_DRIVER_ARCHIVED = (
    _REPO_ROOT / "specs" / ".archive" / "0042-adoption" / "adoption_run" / "run_adoption.py"
)
_DRIVER_LIVE = _REPO_ROOT / "specs" / "0042-adoption" / "adoption_run" / "run_adoption.py"
_DRIVER = _DRIVER_ARCHIVED if _DRIVER_ARCHIVED.is_file() else _DRIVER_LIVE
_API = "http://127.0.0.1:11434"


def _residents() -> list[str] | None:
    try:
        with urllib.request.urlopen(f"{_API}/api/ps", timeout=5) as r:
            return [m["name"] for m in json.loads(r.read())["models"]]
    except Exception:  # noqa: BLE001
        return None


@pytest.mark.integration
def test_adoption_driver_stops_and_warns_without_live_infra():
    residents = _residents()
    if residents is not None:
        pytest.skip(
            "live stack reachable — the closure run is T12 (an operator "
            "action); this smoke only proves the STOP-AND-WARN refusal path"
        )
    if require_live_stack(False) == "fail":
        pytest.fail("Ollama unreachable (HARPYJA_REQUIRE_LIVE_STACK set)")

    ledger = _DRIVER.parent / "adoption_results.json"
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
    # The refusal fired before any cell: no ledger materializes from it.
    assert ledger.exists() == existed_before
