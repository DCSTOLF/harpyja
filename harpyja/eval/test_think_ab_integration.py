"""Spec 0039 — AC6/AC7 integration: the precheck-GATED live paired run.

The AC5 pre-check gates the live run on committed evidence. On the
UNDER_POWERED_STOP branch (the committed 0036 pilot's honest arithmetic:
projected upper bound 6 < floor 8) the paired run is N/A-on-branch and the
typed stop IS the deliverable — asserted here without a live stack. If a future
pool-enlargement flips the pre-check to PROCEED, the live branch below
auto-activates (skip-not-fail without a served stack; strict under
HARPYJA_REQUIRE_LIVE_STACK — the 0037 conditional-tripwire pattern).
"""

from __future__ import annotations

import pytest

from harpyja.eval.think_ab import PRECHECK_STOP, PREREGISTERED_AB_CONFIG_0039
from harpyja.eval.think_ab_precheck import run_precheck
from harpyja.eval.think_ab_run import run_ab_paired

_CFG = PREREGISTERED_AB_CONFIG_0039


@pytest.mark.integration
def test_ab_live_paired_run_emits_verifier_clean_artifacts(tmp_path):
    precheck = run_precheck(_CFG)
    if precheck.outcome == PRECHECK_STOP:
        # THE GATED BRANCH (branch-correct on the committed evidence): the
        # runner refuses to fire any arm; the typed stop is the deliverable.
        result = run_ab_paired(
            _CFG,
            out_dir=tmp_path / "artifacts",
            ledger_path=tmp_path / "ab_ledger.json",
        )
        assert result["status"] == "gated-under-powered-stop"
        assert result["precheck"]["projected_upper_bound"] < result["precheck"]["floor"]
        assert "pool" in result["precheck"]["next_step"]
        # No arm fired: the ledger was never created.
        assert not (tmp_path / "ab_ledger.json").exists()
        return

    # THE PROCEED BRANCH (auto-activates when the pre-check clears): the live
    # paired run over the 0036 set via the committed driver's machinery.
    pytest.importorskip("requests")
    import json as _json

    import requests

    from harpyja.eval.locate_probe import require_live_stack

    try:
        resp = requests.get("http://127.0.0.1:11434/api/tags", timeout=5)
        served = {m.get("name") for m in resp.json().get("models", [])}
        available = _CFG.lm_model in served
    except Exception:
        available = False
    if not available:
        if require_live_stack(False) == "fail":
            pytest.fail(
                f"{_CFG.lm_model} stack unavailable (HARPYJA_REQUIRE_LIVE_STACK set)"
            )
        pytest.skip(f"{_CFG.lm_model} not served; live paired run skipped")

    result = run_ab_paired(
        _CFG,
        out_dir=tmp_path / "artifacts",
        ledger_path=tmp_path / "ab_ledger.json",
        live=True,
    )
    assert result["status"] == "completed"
    report = result["report"]
    assert report["headline"].startswith("conceptual:")
    assert "symbols_adoption" in result and "reasoning_cost_delta" in result
    ledger = _json.loads((tmp_path / "ab_ledger.json").read_text(encoding="utf-8"))
    assert ledger["entries"], "per-cell ledger must carry the run"
