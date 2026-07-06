"""spec 0026 AC6/AC8 — the terse set drives the REAL explorer backend end-to-end
(integration, skip-not-fail). AC6: file-level + span-level scores come from the
existing oracle via the UNCHANGED run_locate_probe. AC8: the pre-registered pilot
power-gate emits its typed outcome from two reference models.

`@pytest.mark.integration`, gated through `require_live_stack`: SKIP on a host without
a served Scout stack + provisioned worktrees (CI-safe); the deliverable run fails LOUD
under `HARPYJA_REQUIRE_LIVE_STACK=1`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harpyja.eval.ac8_pilot import PREREGISTERED_AC8_CONFIG, Ac8Outcome
from harpyja.eval.locate_probe import require_live_stack, scout_stack_available
from harpyja.eval.terse_probe import run_ac8_pilot, run_terse_locate_probe
from harpyja.eval.test_eval_integration import _NEEDS_STACK, _settings_live

_FIX = Path(__file__).parent / "fixtures"
_TERSE = _FIX / "swebench_verified.terse.jsonl"
_RAW = _FIX / "swebench_verified.raw.jsonl"
_PROV = _FIX / "swebench_verified.provenance.json"
_RESOLVED = _FIX / "swebench_verified.resolved.jsonl"


def _resolved_worktrees() -> dict[str, str]:
    """Machine-local provisioned worktree paths, keyed by case_id (empty if absent)."""
    if not _RESOLVED.exists():
        return {}
    out: dict[str, str] = {}
    for line in _RESOLVED.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            wt = row.get("worktree") or row.get("repo")
            if wt and Path(wt).exists():
                out[row["case_id"]] = wt
    return out


def _gate():
    action = require_live_stack(scout_stack_available(_settings_live()))
    if action == "skip":
        pytest.skip(_NEEDS_STACK + " (Scout-only terse probe)")
    worktrees = _resolved_worktrees()
    if not worktrees:
        pytest.skip("no provisioned SWE-bench worktrees (run `provision`)")
    return worktrees


@pytest.mark.integration
def test_terse_set_scores_through_explorer_offline():
    worktrees = _gate()
    settings = _settings_live()

    def provision(case_id: str, base_commit: str) -> str | None:
        return worktrees.get(case_id)

    result = run_terse_locate_probe(
        _TERSE, _RAW, _PROV, settings=settings, provision=provision
    )
    # Both scoring granularities come from the existing oracle.
    assert result.distribution.file_level_accuracy is not None
    assert result.distribution.span_level_accuracy is not None
    assert result.n_scored >= 1


@pytest.mark.integration
def test_ac8_pilot_gate_emits_typed_outcome():
    _gate()
    result = run_ac8_pilot(
        _TERSE,
        _RAW,
        _PROV,
        settings=_settings_live(),
        provision=lambda cid, bc: _resolved_worktrees().get(cid),
    )
    assert isinstance(result.outcome, Ac8Outcome)
    # the frozen pre-registration hash travels with the verdict (reproducible).
    assert result.config_hash == run_ac8_pilot.__globals__["AC8_CONFIG_HASH"]
    assert result.reference_models == (
        PREREGISTERED_AC8_CONFIG.reference_model_a,
        PREREGISTERED_AC8_CONFIG.reference_model_b,
    )
