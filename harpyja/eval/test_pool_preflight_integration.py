"""Spec 0040 — AC3 integration: the live three-model preflight.

Preflight BEFORE capability (the 16B-gibberish lesson): every model — the two
NEW tags and the re-confirmed ``qwen3:14b`` anchor — is typed through the
committed enum against THIS Ollama ``/v1`` before it may produce any
capability number. Skip-not-fail without a served stack; strict under
HARPYJA_REQUIRE_LIVE_STACK.
"""

from __future__ import annotations

import json
import urllib.request

import pytest

from harpyja.eval.locate_probe import require_live_stack
from harpyja.eval.pool_pilot import run_model_preflight
from harpyja.eval.pool_precheck import (
    PREREGISTERED_POOL_CONFIG_0040,
    PreflightOutcome,
    is_excluding,
)

_CFG = PREREGISTERED_POOL_CONFIG_0040


def _served_tags() -> set[str] | None:
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:11434/api/tags", timeout=5
        ) as r:
            return {m["name"] for m in json.loads(r.read())["models"]}
    except Exception:  # noqa: BLE001
        return None


@pytest.mark.integration
def test_three_model_preflight_runs_live_and_types_each():
    served = _served_tags()
    if served is None:
        if require_live_stack(False) == "fail":
            pytest.fail("Ollama unreachable (HARPYJA_REQUIRE_LIVE_STACK set)")
        pytest.skip("Ollama unreachable — live preflight skipped, not faked")

    for tag in _CFG.model_tags:
        result = run_model_preflight(tag, served_tags=served)
        # Exactly one value of the committed enum — never a stall outside it.
        assert isinstance(result.outcome, PreflightOutcome)
        # An unserved tag types UNSERVABLE (excluding), never a silent carry.
        if tag not in served:
            assert result.outcome is PreflightOutcome.UNSERVABLE
        # An excluding outcome carries its recorded reason.
        if is_excluding(result.outcome):
            assert result.exclusion_reason
        else:
            assert result.exclusion_reason is None
        # The think-control mechanism is probed per model (0037/0038 lesson),
        # recorded whenever the probe adjudicated it effective.
        if result.observations.think_control == "effective":
            assert result.think_control_mechanism
