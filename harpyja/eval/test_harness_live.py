"""spec 0028 (AC4/AC5) — live generation-control proof on the served 16B stack.

Spec 0028 bounds the explorer's per-call generation (a tuned `max_tokens` cap + a
thinking knob) and surfaces `finish_reason`, so a first tool call completes in seconds
instead of the 0027 unbounded hang.

STATE:
- AC4 (first-call latency) PASSES live — a first explorer call returns a well-formed
  `finish_reason=="tool_calls"` in ~2s (see `test_first_explorer_call_returns_toolcall_under_30s`).
- AC5 (localization) is a recorded HOLD, RE-POINTED. The 0027 blocker (unbounded
  generation) is FIXED — the cap now bounds it and AC3 types it as `generation-truncated`.
  But the live run surfaced a NEW, DISTINCT downstream blocker: the explorer loop echoes
  the N parallel `tool_calls` the model emits on turn 1 but answers only the first,
  leaving N-1 unanswered → a malformed conversation → the model runs away on turn 2 and
  truncates. That is a loop message-handling bug (a different subsystem, out of 0028's
  generation-control scope), so the AC5 case stays `xfail` naming that follow-up and
  flips to xpass when the loop echo is made well-formed. See
  `specs/0028-generation-control/operator-run-findings.md`.
"""

from __future__ import annotations

import dataclasses
import json
import time
import urllib.request
from pathlib import Path

import pytest

from harpyja.config.settings import Settings
from harpyja.eval.locate_accuracy import LocateBucket, classify_case, normalize_citations
from harpyja.eval.locate_probe import build_scout_only_stack
from harpyja.gateway.gateway import ModelGateway
from harpyja.scout.context_map import build_initial_prompt
from harpyja.scout.errors import (
    BACKEND_ERROR,
    GENERATION_TRUNCATED,
    MODEL_UNREACHABLE,
    ScoutUnavailable,
)
from harpyja.scout.explorer_backend import _tool_schemas
from harpyja.server.types import CodeSpan

_API = "http://127.0.0.1:8131/v1"
_MODEL = "unsloth/Qwen3-16B-A3B-GGUF:Q4_K_M"
_MODEL_OVERRIDE_REASON = (
    "Spec 0029 live measurement: uses a specific 16B tuned model (Qwen3-16B-A3B) "
    "pulled into llama.cpp at port 8131 for trajectory-verified live proof-of-concept. "
    "Differs from Settings default (8B Qwen3) for AC4/AC5 generation-control measurement "
    "(spec 0028); see specs/0029-live-measurement/findings.md and spec 0031 (trajectory verification)."
)
_N = 10
_CAP = 2048  # spec 0028 AC2/AC7 — pinned; a well-formed turn completes well under it
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

# The live degrade causes that mean the harness FAILED to drive the model (AC5's
# fail set) — as opposed to an honest capability result (wrong-file/empty).
_HARNESS_DEGRADES = (MODEL_UNREACHABLE, BACKEND_ERROR, GENERATION_TRUNCATED)


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


def _live_settings(**overrides) -> Settings:
    return dataclasses.replace(
        Settings(),
        lm_api_base=_API,
        lm_model=_MODEL,
        scout_max_turns=_N,
        scout_wall_clock_s=600.0,
        lm_http_timeout_s=300.0,
        explorer_max_tokens=_CAP,
        **overrides,
    )


@pytest.mark.integration
def test_first_explorer_call_returns_toolcall_under_30s():
    # spec 0028 AC4: a first explorer model call returns a well-formed, non-truncated
    # tool_call fast — the 0027 unbounded-hang symptom is gone once the cap is present.
    if not _stack_up():
        pytest.skip("16B llama.cpp stack not reachable at 127.0.0.1:8131")

    _, query = _CASES["astropy__astropy-12907"]
    gw = ModelGateway(api_base=_API, model=_MODEL, timeout_s=300.0)
    messages = [{"role": "user", "content": build_initial_prompt(query)}]
    t0 = time.monotonic()
    out = gw.complete_with_tools(messages, _tool_schemas(), max_tokens=_CAP)
    elapsed = time.monotonic() - t0

    assert elapsed <= 30.0, f"first call took {elapsed:.1f}s (> 30s)"
    assert out["finish_reason"] == "tool_calls", f"finish_reason={out['finish_reason']!r}"
    assert out["finish_reason"] != "length"  # not truncated
    assert out["tool_calls"], "no tool_call emitted"


@pytest.mark.integration
@pytest.mark.xfail(
    reason="AC5 HOLD (RE-POINTED): the 0027 unbounded-generation blocker is FIXED (the "
    "cap bounds it; AC3 types it as generation-truncated). A NEW downstream blocker "
    "remains — the explorer loop echoes the N parallel tool_calls the model emits but "
    "answers only the first, so the malformed conversation derails the model into a "
    "turn-2 runaway. That is a loop message-handling fix (different subsystem, out of "
    "0028 scope); flips to xpass when the loop echo is made well-formed.",
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
    settings = _live_settings()
    engine = build_scout_only_stack(settings, wt).scout_engine

    cause = None
    try:
        spans = engine.search(query, scope=wt)
    except ScoutUnavailable as e:
        spans, cause = [], e.cause

    # Reject placeholder / semantically-empty citations (e.g. path="string") — a
    # well-formed-but-empty call AC4 cannot catch. A real localization cites a real path.
    real = [s for s in spans if s.path and s.path not in ("string", "path", "")]
    bucket, _ = classify_case(
        normalize_citations(real, None).effective, (gold,), window=50
    )

    # AC5 gates on the HARNESS working: the model was driven to a terminal answer
    # WITHOUT a degrade masking the outcome. A genuine degrade = FAIL (not a hold);
    # an honest right-file-wrong-span / empty capability result = PASS (localization
    # QUALITY is reported, not gated).
    assert cause not in _HARNESS_DEGRADES, f"harness degrade: {cause}"
    # With the harness healthy, localization is measurable; a gold-file hit is the win.
    assert bucket in (LocateBucket.CORRECT, LocateBucket.RIGHT_FILE_WRONG_SPAN)


def test_recorded_model_matches_settings_or_documents_override():
    """Recorded model/endpoint either match Settings defaults or document override reason.

    Spec 0029 committed-test reconciliation (AC7): the harness's _MODEL/_API must either:
    1. Equal Settings().lm_model and the default endpoint, OR
    2. Have a committed _MODEL_OVERRIDE_REASON explaining why a different model/endpoint is used,
       with a linked spec/issue rationale.

    This prevents silent divergence between committed test data and Settings defaults.
    """
    default_settings = Settings()
    default_endpoint = default_settings.lm_api_base

    # Check if model/endpoint match defaults
    model_matches = _MODEL == default_settings.lm_model
    endpoint_matches = _API == default_endpoint

    if not (model_matches and endpoint_matches):
        # Both must diverge together; at least one does, so check for override reason
        assert (
            _MODEL_OVERRIDE_REASON is not None
        ), (
            f"Recorded model {_MODEL!r} or endpoint {_API!r} diverges from Settings "
            f"defaults ({default_settings.lm_model!r}, {default_endpoint!r}), "
            f"but _MODEL_OVERRIDE_REASON is not defined. "
            f"Add a constant with the spec/issue rationale."
        )
        # Override reason must be non-empty
        assert len(_MODEL_OVERRIDE_REASON.strip()) > 0, "Override reason must not be empty"
