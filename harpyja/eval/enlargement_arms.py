"""Spec 0047 — operator arm resolution for the two-model blind protocol.

The blind protocol needs the author and the verifier to be DIFFERENT models invoked in
SEPARATE contexts. This module resolves the two arms to concrete CLI backends
(``claude`` | ``codex``), enforces author ≠ verifier STRUCTURALLY (a same-model
"blind" check is not blind), builds each backend's invocation, and preflights each arm
with one trivial call so a broken/misconfigured CLI fails FAST — before the ~130-case
run, not deep inside it. Pure of subprocess itself: the CLI runner is injected."""

from __future__ import annotations

from collections.abc import Callable

CLAUDE = "claude"
CODEX = "codex"
_BACKENDS = frozenset({CLAUDE, CODEX})
_ALIASES = {"anthropic": CLAUDE, "openai": CODEX}

# run_cli(cmd, *, stdin_text) -> str  (raises on failure)
RunCli = Callable[..., str]


class ArmError(ValueError):
    """Arm misconfiguration (unknown backend, or author == verifier) — loud."""


def normalize_backend(name: str) -> str:
    n = (name or "").lower().strip()
    n = _ALIASES.get(n, n)
    if n not in _BACKENDS:
        raise ArmError(f"unknown arm backend {name!r}; use 'claude' or 'codex'")
    return n


def resolve_backends(author: str, verifier: str | None = None) -> tuple[str, str]:
    """Resolve the (author, verifier) backends. The verifier defaults to the COMPLEMENT
    of the author so the default is always a genuine cross-model pair; an explicit
    verifier equal to the author is rejected (blindness is not optional)."""
    a = normalize_backend(author)
    v = normalize_backend(verifier) if verifier else (CODEX if a == CLAUDE else CLAUDE)
    if a == v:
        raise ArmError(
            f"author and verifier must be DIFFERENT backends for a blind protocol "
            f"(both {a!r}) — set --verifier to the other backend"
        )
    return a, v


def build_cmd(
    backend: str, prompt: str, *, claude_model: str | None = None
) -> tuple[list[str], str | None]:
    """Return ``(argv, stdin_text)`` for a backend. Claude takes the prompt as argv
    (per .speccraft/agents.toml, input=argv); Codex takes it on stdin."""
    b = normalize_backend(backend)
    if b == CLAUDE:
        cmd = ["claude", "-p"]
        if claude_model:
            cmd += ["--model", claude_model]
        return cmd + [prompt], None
    return ["codex", "exec", "--full-auto"], prompt


def make_invoke(
    backend: str, run_cli: RunCli, *, claude_model: str | None = None
) -> Callable[[str], str]:
    """An Invoke callable for a backend, using the injected CLI runner."""
    def _invoke(prompt: str) -> str:
        cmd, stdin = build_cmd(backend, prompt, claude_model=claude_model)
        out = run_cli(cmd, stdin_text=stdin)
        # Claude may emit a multi-line answer; the terse arm wants the first line.
        return out.splitlines()[0].strip() if out and backend == CLAUDE else out.strip()
    return _invoke


def preflight_arm(
    backend: str, run_cli: RunCli, *, claude_model: str | None = None
) -> str:
    """Ping a backend once with a trivial prompt; raises (via run_cli) on failure so the
    driver can STOP-AND-WARN early with the real CLI output."""
    cmd, stdin = build_cmd(
        backend, "Reply with exactly the word: ok", claude_model=claude_model
    )
    return run_cli(cmd, stdin_text=stdin)
