"""spec 0027 (AC5/AC6) — live OpenCode-parity proof on the served 16B stack.

The eager context map is removed (units T1–T11 prove the payload drops ~170×). This
live check asserts the explorer LOCALIZES the gold file WITHOUT a timeout/backend
degrade in <= N turns, on the validation stack (llama.cpp --jinja, 16B @ 8131).

STATE: AC5 is currently a recorded HOLD (`specs/0027-harness/operator-run-findings.md`)
— blocked NOT by the map defect (fixed) but by a DOWNSTREAM generation-runaway (Qwen3
thinking + unbounded generation) that a follow-up spec must control. Hence `xfail`
(non-strict): it SKIPS with no stack (CI-safe), and is expected to fail on the live
stack until generation control lands — at which point it flips to xpass, the signal to
un-mark it.
"""

from __future__ import annotations

import dataclasses
import json
import urllib.request
from pathlib import Path

import pytest

from harpyja.config.settings import Settings
from harpyja.eval.locate_accuracy import LocateBucket, classify_case, normalize_citations
from harpyja.eval.locate_probe import build_scout_only_stack
from harpyja.scout.errors import BACKEND_ERROR, MODEL_UNREACHABLE, ScoutUnavailable
from harpyja.server.types import CodeSpan

_API = "http://127.0.0.1:8131/v1"
_MODEL = "unsloth/Qwen3-16B-A3B-GGUF:Q4_K_M"
_N = 10
_FIX = Path("harpyja/eval/fixtures/swebench_verified.resolved.jsonl")

_CASES = {
    "astropy__astropy-12907": (
        ("astropy/modeling/separable.py", 242, 248),
        "where is the separability matrix computed for nested compound models",
    ),
    "django__django-12774": (
        ("django/db/models/query.py", 689, 695),
        "where does QuerySet.in_bulk resolve and validate the field_name argument",
    ),
}


def _stack_up() -> bool:
    try:
        urllib.request.urlopen(f"{_API}/models", timeout=3).read()
        return True
    except Exception:
        return False


def _worktree(case_id: str) -> str | None:
    if not _FIX.exists():
        return None
    for line in _FIX.read_text().splitlines():
        if line.strip() and json.loads(line)["case_id"] == case_id:
            wt = json.loads(line)["repo"]
            return wt if Path(wt).exists() else None
    return None


@pytest.mark.integration
@pytest.mark.xfail(
    reason="AC5 HOLD: blocked by downstream generation-runaway (Qwen3 thinking + "
    "unbounded generation); generation-control follow-up spec, then un-mark",
    strict=False,
)
@pytest.mark.parametrize("case_id", list(_CASES))
def test_explorer_localizes_without_degrade_within_n_turns(case_id):
    if not _stack_up():
        pytest.skip("16B llama.cpp stack not reachable at 127.0.0.1:8131")
    wt = _worktree(case_id)
    if wt is None:
        pytest.skip(f"no provisioned worktree for {case_id}")

    (gp, gs, ge), query = _CASES[case_id]
    gold = CodeSpan(path=gp, start_line=gs, end_line=ge)
    settings = dataclasses.replace(
        Settings(), lm_api_base=_API, lm_model=_MODEL,
        scout_max_turns=_N, scout_wall_clock_s=600.0, lm_http_timeout_s=300.0,
    )
    engine = build_scout_only_stack(settings, wt).scout_engine

    cause = None
    try:
        spans = engine.search(query, scope=wt)
    except ScoutUnavailable as e:
        spans, cause = [], e.cause

    bucket, _ = classify_case(normalize_citations(list(spans), None).effective, (gold,), window=50)
    # AC5: localized the gold file, and NOT via a timeout/backend degrade.
    assert cause not in (MODEL_UNREACHABLE, BACKEND_ERROR), f"degraded: {cause}"
    assert bucket in (LocateBucket.CORRECT, LocateBucket.RIGHT_FILE_WRONG_SPAN)
