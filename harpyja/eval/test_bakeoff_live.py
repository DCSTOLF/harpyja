"""Spec 0048 — bake-off: live-seam mapping + preflight-prober logic (T22 glue).

The pure, correctness-bearing pieces exercised without a live stack: the
verifier→bake-off artifact map and the prober's served/coherence/replay gating.
"""

from __future__ import annotations

import pytest

from harpyja.eval.bakeoff_config import PREREGISTERED_BAKEOFF_CONFIG_0048
from harpyja.eval.bakeoff_live import (
    bakeoff_artifact_from_verifier,
    make_live_cell_runner,
    make_live_preflight_prober,
)
from harpyja.eval.bakeoff_run import BakeoffRunError
from harpyja.eval.exclusivity_gate import build_exclusivity_record
from harpyja.eval.locate_accuracy import LocateBucket

pytestmark = pytest.mark.integration

_CFG = PREREGISTERED_BAKEOFF_CONFIG_0048


def _exclusivity():
    check = {"label": "start", "timestamp": "2026-07-17T00:00:00+00:00", "clean": True,
             "residents": [], "foreign": []}
    return build_exclusivity_record(checks=[check], model_set=_CFG.model_tags)


def test_bakeoff_artifact_from_verifier_maps_clean_cell():
    verifier = {
        "terminal_bucket": "correct",
        "tool_names_invoked": ["grep", "symbols", "read_span", "symbols"],
        "citations_submitted": 2, "citations_surviving": 2,
        "submission_outcome": "submitted", "serving_transport": "v1-chat-completions",
        "per_turn": [{"reasoning_tokens": 100}, {"reasoning_tokens": 250}],
        "degrade": None,
    }
    art = bakeoff_artifact_from_verifier(
        _CFG, case_id="django__django-14315", model="qwen3:14b",
        verifier_artifact=verifier, sut_hash="s1", exclusivity_record=_exclusivity(),
    )
    assert art["bucket"] == "correct"
    assert art["symbols_adopted"] is True
    assert art["tools"]["symbols"] == 2  # counted, not just named
    assert art["reasoning_tokens"] == 350
    assert art["submitted"] is True and art["surviving"] is True
    assert art["found_but_unsubmitted"] is False
    assert art["heavy_repo_degrade"] is False
    assert art["decoding"] == {"temperature": 0.0, "top_p": 1.0, "seed": 0}


def test_bakeoff_artifact_derives_tools_from_model_turns_when_field_null():
    # REGRESSION (observed live 2026-07): the verifier writes tools in model_turns
    # but leaves the top-level `tool_names_invoked` null — the mapper must NOT
    # silently zero symbols-adoption (0042/AC6). Shape matches the smoke run.
    verifier = {
        "terminal_bucket": "empty",
        "tool_names_invoked": None,  # null convenience field
        "model_turns": [
            {"role": "assistant", "tool_calls": [
                {"function": {"name": "glob"}}, {"function": {"name": "symbols"}}]},
            {"role": "tool", "content": "..."},
            {"role": "assistant", "tool_calls": [{"function": {"name": "symbols"}}]},
        ],
        "submission_outcome": "found-unsubmitted",
        "citations_submitted": None, "serving_transport": "v1-chat-completions",
    }
    art = bakeoff_artifact_from_verifier(
        _CFG, case_id="astropy__astropy-12907", model="qwen3:14b",
        verifier_artifact=verifier, sut_hash="s", exclusivity_record=_exclusivity(),
    )
    assert art["symbols_adopted"] is True  # NOT silently zeroed
    assert art["tools"] == {"glob": 1, "symbols": 2}  # per-call counts from turns
    assert art["found_but_unsubmitted"] is True
    assert art["submitted"] is False


def test_bakeoff_artifact_from_verifier_maps_found_but_unsubmitted_and_degrade():
    verifier = {
        "terminal_bucket": None,
        "tool_names_invoked": ["grep"],
        "citations_submitted": 0, "citations_surviving": 0,
        "submission_outcome": "found-unsubmitted", "serving_transport": None,
        "degrade": "scout-degraded:wall-clock",
    }
    art = bakeoff_artifact_from_verifier(
        _CFG, case_id="astropy__astropy-12907", model="qwen3.5:4b",
        verifier_artifact=verifier, sut_hash="s1", exclusivity_record=_exclusivity(),
    )
    assert art["bucket"] is None  # a degrade is never a fabricated EMPTY
    assert art["symbols_adopted"] is False
    assert art["found_but_unsubmitted"] is True
    assert art["heavy_repo_degrade"] is True  # wall-clock -> heavy-repo class
    assert art["degrade"] == "scout-degraded:wall-clock"


def test_live_cell_runner_raises_on_withheld_gold(tmp_path):
    # a blind-withheld gold the operator did not supply is a loud missing-input,
    # raised BEFORE any live call (no ModelGateway constructed).
    runner = make_live_cell_runner(
        _CFG, api_base="http://localhost:11434", out_dir=tmp_path,
        cases_by_id={"a__a-1": {"gold": None, "query": "q", "repo": "a__a"}},
        worktrees_root=tmp_path, sut_hash="s", exclusivity_record=_exclusivity(),
    )
    with pytest.raises(BakeoffRunError, match="no gold span"):
        runner("a__a-1", "qwen3:14b")


def test_preflight_prober_short_circuits_unserved():
    calls: list[str] = []
    prober = make_live_preflight_prober(
        _CFG, served_tags=["qwen3:14b"], replay_cases=["a", "b", "c"],
        coherence_probe=lambda tag: (calls.append(tag), (True, True))[1],
        replay_cell=lambda tag, cid, ix: LocateBucket.CORRECT,
    )
    obs = prober("qwen3:8b")  # not served
    assert obs.served is False and obs.replay == "unserved"
    assert calls == []  # no probe calls for an unserved tag


def test_preflight_prober_runs_replay_when_coherent():
    # a flaky replay (bucket differs across the two runs) -> replay-fail
    flaky = {("a", 0): LocateBucket.CORRECT, ("a", 1): LocateBucket.EMPTY}
    prober = make_live_preflight_prober(
        _CFG, served_tags=["qwen3:14b"], replay_cases=["a"],
        coherence_probe=lambda tag: (True, True),
        replay_cell=lambda tag, cid, ix: flaky[(cid, ix)],
    )
    obs = prober("qwen3:14b")
    assert obs.served and obs.coherent and obs.tool_calls_clean
    assert obs.replay == "replay-fail"


def test_preflight_prober_records_coherence_fail_without_replay():
    prober = make_live_preflight_prober(
        _CFG, served_tags=["qwen3:14b"], replay_cases=["a"],
        coherence_probe=lambda tag: (False, True),  # gibberish
        replay_cell=lambda tag, cid, ix: LocateBucket.CORRECT,
    )
    obs = prober("qwen3:14b")
    assert obs.coherent is False and obs.replay == "unrun"
