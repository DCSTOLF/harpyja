"""Spec 0047 — arm resolution + preflight (unit; injected fake CLI runner)."""

from __future__ import annotations

import pytest

from harpyja.eval import enlargement_arms as arms


def test_normalize_backend_accepts_names_and_aliases():
    assert arms.normalize_backend("Claude") == arms.CLAUDE
    assert arms.normalize_backend("anthropic") == arms.CLAUDE
    assert arms.normalize_backend("openai") == arms.CODEX
    with pytest.raises(arms.ArmError):
        arms.normalize_backend("gpt-9")


def test_resolve_backends_defaults_verifier_to_complement():
    assert arms.resolve_backends("claude") == (arms.CLAUDE, arms.CODEX)
    assert arms.resolve_backends("codex") == (arms.CODEX, arms.CLAUDE)


def test_resolve_backends_rejects_same_author_and_verifier():
    with pytest.raises(arms.ArmError, match="DIFFERENT"):
        arms.resolve_backends("codex", "codex")


def test_build_cmd_claude_is_argv_codex_is_stdin():
    cmd, stdin = arms.build_cmd("claude", "hello", claude_model="a-tag")
    assert cmd == ["claude", "-p", "--model", "a-tag", "hello"]
    assert stdin is None
    cmd, stdin = arms.build_cmd("codex", "hello")
    assert cmd == ["codex", "exec", "--full-auto"]
    assert stdin == "hello"


def test_make_invoke_claude_takes_first_line():
    def fake_run(cmd, *, stdin_text=None):
        return "the terse query\nextra chatter\n"
    inv = arms.make_invoke("claude", fake_run)
    assert inv("prompt") == "the terse query"


def test_preflight_arm_raises_through_run_cli():
    def broken(cmd, *, stdin_text=None):
        raise RuntimeError(f"{cmd[0]} not authenticated")
    with pytest.raises(RuntimeError, match="not authenticated"):
        arms.preflight_arm("claude", broken)
