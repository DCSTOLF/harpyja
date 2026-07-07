"""Spec 0028 (AC8) — Deep-tier scope guard: the explorer generation-control knobs
are `explorer_`-prefixed and threaded ONLY by the explorer's `_default_model_call`.
The Deep-tier RLM path is out of scope and byte-untouched.

These are drift-guards, NOT RED→GREEN pairs: they PASS on introduction precisely
because Deep never carries the explorer knobs, and ROT FALSE if a future change
leaks `explorer_max_tokens` (the cap) or `chat_template_kwargs.enable_thinking`
into the Deep outbound call. They assert on the ACTUAL outbound request kwargs,
not merely the absence of the `explorer_*` Settings names.
"""

import dataclasses

from harpyja.config.settings import Settings
from harpyja.deep.rlm import RlmBackend


class _RecordingRlm:
    """A fake dspy RLM that records the kwargs of its forward call."""

    def __init__(self):
        self.call_kwargs = None

    def __call__(self, **kwargs):
        self.call_kwargs = kwargs
        return type("Pred", (), {"answer": ""})()


def _run_deep_and_capture(settings):
    rlm = _RecordingRlm()
    backend = RlmBackend(
        settings,
        rlm_factory=lambda s, tools: rlm,
        assert_local=lambda *a, **k: None,  # loopback stub — air-gap is tested elsewhere
    )
    backend.run("where is X resolved", [], {})
    return rlm.call_kwargs


def test_deep_outbound_carries_no_explorer_max_tokens_cap():
    # explorer_max_tokens set to a distinctive sentinel; the Deep forward call must
    # NOT carry it (Deep's own bound is deep_token_ceiling, set in its frozen factory).
    settings = dataclasses.replace(Settings(), explorer_max_tokens=99999)
    kwargs = _run_deep_and_capture(settings)
    assert "max_tokens" not in kwargs
    assert 99999 not in kwargs.values()


def test_deep_outbound_carries_no_enable_thinking():
    # explorer_enable_thinking flipped off; the Deep forward call must NOT carry
    # chat_template_kwargs / enable_thinking — the thinking knob is explorer-only.
    settings = dataclasses.replace(Settings(), explorer_enable_thinking=False)
    kwargs = _run_deep_and_capture(settings)
    assert "chat_template_kwargs" not in kwargs
    assert "enable_thinking" not in kwargs
