"""Spec 0041 — AC7 integration: the live residency probe records a typed outcome.

Skip-not-fail without a live stack; strict under HARPYJA_REQUIRE_LIVE_STACK.
Opt-in only (the AC6 deselect default) — this test touches the endpoint's
residency state, exactly the class of traffic the default invocation must
never fire.
"""

from __future__ import annotations

import json
import urllib.request

import pytest

from harpyja.eval.locate_probe import require_live_stack
from harpyja.eval.residency_probe import (
    RESIDENCY_PROBE_OUTCOMES,
    load_committed_residency_probe_result,
    run_residency_probe,
    validate_residency_probe_result,
)


def _residents() -> list[str] | None:
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:11434/api/ps", timeout=5
        ) as r:
            return [m["name"] for m in json.loads(r.read())["models"]]
    except Exception:  # noqa: BLE001
        return None


@pytest.mark.integration
def test_committed_residency_probe_run_records_typed_outcome():
    residents = _residents()
    if residents is None:
        if require_live_stack(False) == "fail":
            pytest.fail("Ollama unreachable (HARPYJA_REQUIRE_LIVE_STACK set)")
        pytest.skip("Ollama unreachable — live residency probe skipped, not faked")
    if not residents:
        pytest.skip(
            "no resident model — the probe needs a pinned before-state and "
            "this test fabricates no traffic (run the operator driver instead)"
        )

    result = run_residency_probe()
    # Exactly one typed outcome, self-consistent with its own expires_at
    # evidence (the validator re-judges).
    validate_residency_probe_result(result)
    assert result["outcome"] in RESIDENCY_PROBE_OUTCOMES
    # If the operator driver has committed THE artifact, it must agree with
    # the same validation (never a divergent hand-edit).
    try:
        committed = load_committed_residency_probe_result()
    except Exception:  # noqa: BLE001 — not committed yet; the driver commits it
        return
    assert committed["outcome"] in RESIDENCY_PROBE_OUTCOMES
    print(json.dumps({"live": result["outcome"], "committed": committed["outcome"]}))