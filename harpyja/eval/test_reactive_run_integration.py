"""Spec 0046 — AC5/AC6 integration smoke: the two-arm re-measurement STOPS-AND-
WARNS on missing live infra rather than silently passing, and the named cells
(flask-5014 / django-14315::8b / pytest-10081::14b) are IN the pinned coverage.

Skip-not-fail under the 0041 opt-in default (``-m "not integration"`` deselects
this file); strict under HARPYJA_REQUIRE_LIVE_STACK. The smoke NEVER fires live
cells — it only exercises the driver's refusal path when the stack is absent and
skips when a live stack is present (the closure runs T26/T28 are operator
actions, not tests; the 0043/0044 precedent).

Lives in ``harpyja/eval/`` so the suite collects it.
"""

from __future__ import annotations

import pytest

from harpyja.eval.locate_probe import require_live_stack
from harpyja.eval.pool_pilot import PoolRunError
from harpyja.eval.reactive_config import PREREGISTERED_REACTIVE_CONFIG_0046 as CFG
from harpyja.eval.reactive_run import reactive_arm_flag, run_reactive_cells


@pytest.mark.integration
def test_named_cells_in_pinned_coverage():
    """The three AC6 named cells are inside the frozen coverage, so the gated
    re-run re-checks them by construction: flask-5014 (0044-rescued — stays
    correct?), django-14315::8b (2-spec residual), pytest-10081::14b."""
    assert "pallets__flask-5014" in CFG.pilot_case_ids
    assert "django__django-14315" in CFG.pilot_case_ids
    assert "pytest-dev__pytest-10081" in CFG.pilot_case_ids
    for cell in (
        "pallets__flask-5014::qwen3:14b",
        "django__django-14315::qwen3:8b",
        "pytest-dev__pytest-10081::qwen3:14b",
    ):
        assert cell in CFG.named_cells


@pytest.mark.integration
def test_both_arms_share_one_sut_distinguished_by_flag():
    """Option A: the ONLY delta between the arms is explorer_reactive_confirm."""
    assert reactive_arm_flag("baseline") is False
    assert reactive_arm_flag("new") is True


@pytest.mark.integration
def test_reactive_run_stop_and_warn_refusal_path():
    """The re-measurement REFUSES without live (STOP-AND-WARN), never a silent
    pass — exercised whether or not a live stack is present."""
    with pytest.raises(PoolRunError):
        run_reactive_cells(arm="new", ledger_path="x", artifact_dir="y", live=False)


def _stack_up() -> bool:
    import json
    import urllib.request

    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5) as r:
            return bool(json.loads(r.read()).get("models") is not None)
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.integration
def test_live_stack_smoke_skips_when_absent():
    """When the live stack is unavailable, skip (never fail) unless
    HARPYJA_REQUIRE_LIVE_STACK forces it; when present, still fire no cells here —
    the arms are operator-run (T26 baseline / T28 new)."""
    decision = require_live_stack(_stack_up())
    if decision == "fail":
        pytest.fail("HARPYJA_REQUIRE_LIVE_STACK set but live stack unavailable")
    if decision == "skip":
        pytest.skip("live stack absent — arms are operator-run (T26/T28)")
    pytest.skip("live stack up, but the smoke fires no cells (operator runs T26/T28)")
