"""The real default `FastContextClient` for `FastContextBackend` (spec 0007).

This is the one piece Wave 3 left injected: a concrete client that drives the
**real** Microsoft FastContext agent (its own Read/Glob/Grep loop via
`make_fastcontext_agent`), distinct from Deep's `dspy.RLM`. It is reached only
through the unchanged `ScoutBackend` seam, so unit tests keep driving fakes.

Two paths, one client:

- **Path A (primary, in-process):** lazy-import `make_fastcontext_agent`, build a
  fresh agent (`work_dir=<repo>`, `trajectory_file=<temp outside repo>`), and
  `await agent.run(..., citation=True)`. Because the MCP handler may already be
  on an event loop and FastContext is env-configured, the run is bridged onto a
  **dedicated loop-free worker thread** (D1) and the managed `FC_*` env is set
  **only while holding a module-level `threading.Lock`**, held across the *whole*
  run because `FC_REASONING_EFFORT` is read lazily per model call (D2/D6).
- **Path B (fallback):** when the package can't be imported, drive the
  `fastcontext` CLI through an injected runner with `FC_*` scoped to the child
  via `env=` (no parent-env mutation).

The air-gap (`gateway.assert_local` on the resolved `FC_BASE_URL`) fires before
the agent is constructed (Path A) and before the subprocess is spawned (Path B)
— the single helper, never a parallel check. Backend output is untrusted; the
caller (`ScoutEngine`) normalizes it. Weak/empty citations are an honest empty
result; only typed infra failures raise `ScoutUnavailable`.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import tempfile
import threading
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from typing import Any

from harpyja.config.settings import Settings
from harpyja.gateway.gateway import AirGapError
from harpyja.gateway.gateway import assert_local as _gateway_assert_local
from harpyja.scout import errors
from harpyja.scout.errors import ScoutUnavailable
from harpyja.server.types import CodeSpan
from harpyja.symbols.ripgrep import RipgrepMissingError

# Single-flight serialization for Path A. A *threading* lock (not asyncio) is
# load-bearing: each call bridges `agent.run` onto its own worker thread / loop,
# so concurrent Scout calls land on different OS threads; only a thread lock
# serializes their `os.environ` writes. Module-level + Scout-only — never Deep.
_SCOUT_ENV_LOCK = threading.Lock()

# An agent factory: build a fresh FastContext agent for this repo/trajectory.
AgentFactory = Callable[..., Any]
# A CLI runner: invoke `fastcontext` and return its stdout (the answer text).
CliRunner = Callable[..., str]
Which = Callable[[str], str | None]
AssertLocal = Callable[..., None]

_FINAL_ANSWER = re.compile(r"<final_answer>(.*?)</final_answer>", re.DOTALL)
# Lenient `path:line` / `path:start-end` extraction (mirrors deep/rlm.py).
_CITATION = re.compile(r"([\w./\-]+\.[A-Za-z0-9_]+):(\d+)(?:-(\d+))?")

_DEFAULT_MAX_TURNS = 6
_DEFAULT_CLI_TIMEOUT_S = 120.0


def _fc_env_from_settings(settings: Settings) -> dict[str, str]:
    """Map Scout `Settings` → the FastContext `FC_*` env contract (D3).

    `scout_model` (Scout's fine-tune) is distinct from Deep's `lm_model`.
    `FC_API_KEY` is a constant dummy because the local Ollama endpoint needs none.
    """
    return {
        "FC_MODEL": str(settings.scout_model),
        "FC_BASE_URL": str(settings.lm_api_base),
        "FC_API_KEY": "ollama",
        "FC_MAX_TOKENS": str(settings.scout_max_tokens),
        "FC_TEMPERATURE": str(settings.scout_temperature),
        "FC_REASONING_EFFORT": str(settings.scout_reasoning_effort),
    }


@contextmanager
def _managed_fc_env(env: Mapping[str, str]):
    """Set `env` in `os.environ`, restoring each key's prior state on exit.

    Per-key unset-vs-empty is preserved: a key absent before is `del`-eted after;
    a key set to `""` before is restored to `""`. Restoration runs even when the
    guarded body raises. Callers hold `_SCOUT_ENV_LOCK` across this guard.
    """
    sentinel = object()
    prior: dict[str, Any] = {k: os.environ.get(k, sentinel) for k in env}
    try:
        os.environ.update(env)
        yield
    finally:
        for key, value in prior.items():
            if value is sentinel:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _run_coro_on_worker_thread(make_coro: Callable[[], Any]) -> Any:
    """Run an awaitable (built by `make_coro`) to completion on a fresh thread.

    `asyncio.run` cannot be called from a running event loop, but the MCP tool
    handler may already be on one. Running it on a dedicated loop-free thread
    keeps the synchronous `ScoutBackend` seam intact regardless of caller context
    (D1). The worker's exception is re-raised in the caller thread.
    """
    box: dict[str, Any] = {}

    def worker() -> None:
        try:
            box["value"] = asyncio.run(make_coro())
        except BaseException as err:  # noqa: BLE001 - re-raised below, fidelity preserved
            box["error"] = err

    thread = threading.Thread(target=worker, name="harpyja-scout-fc")
    thread.start()
    thread.join()
    if "error" in box:
        raise box["error"]
    return box["value"]


def parse_final_answer(text: str) -> list[CodeSpan]:
    """Extract `path:line` refs from a `<final_answer>` block (else whole text).

    Output is untrusted (a weak model emits noise) and is confined/clamped by the
    caller's `normalize_spans`; a parse that finds nothing yields an honest empty
    Tier-1 result rather than an error.
    """
    body = text or ""
    match = _FINAL_ANSWER.search(body)
    if match:
        body = match.group(1)
    spans: list[CodeSpan] = []
    for path, start, end in _CITATION.findall(body):
        s = int(start)
        spans.append(CodeSpan(path=path, start_line=s, end_line=int(end) if end else s))
    return spans


def _compose_prompt(query: str, seed: list[CodeSpan]) -> str:
    if not seed:
        return query
    hints = ", ".join(f"{s.path}:{s.start_line}" for s in seed)
    return f"{query}\n\nTier-0 seed hints (starting points): {hints}"


def _map_runtime_error(err: RuntimeError) -> ScoutUnavailable:
    """Map a typed factory/agent `RuntimeError` to a stable degrade cause."""
    msg = str(err).lower()
    if "base_url" in msg or "endpoint" in msg:
        return ScoutUnavailable(errors.NO_ENDPOINT_CONFIGURED)
    if "connection" in msg or "refused" in msg:
        return ScoutUnavailable(errors.CONNECTION_REFUSED)
    return ScoutUnavailable(errors.BACKEND_ERROR)


class DefaultFastContextClient:
    """The production `FastContextClient` — callable as ``(query, seed, tools)``."""

    def __init__(
        self,
        settings: Settings,
        repo_root: str,
        *,
        agent_factory: AgentFactory | None = None,
        cli_runner: CliRunner | None = None,
        which: Which | None = None,
        assert_local: AssertLocal | None = None,
        max_turns: int = _DEFAULT_MAX_TURNS,
        cli_timeout_s: float = _DEFAULT_CLI_TIMEOUT_S,
        trajectory_dir: str | None = None,
    ) -> None:
        self._settings = settings
        self._repo_root = repo_root
        self._agent_factory = agent_factory
        self._cli_runner = cli_runner
        self._which = which or shutil.which
        self._assert_local = assert_local or _gateway_assert_local
        self._max_turns = max_turns
        self._cli_timeout_s = cli_timeout_s
        # Trajectory files live OUTSIDE the scanned repo so the run never pollutes
        # it (read-only guarantee). The system temp dir is outside any repo.
        self._trajectory_dir = trajectory_dir or tempfile.gettempdir()

    # The FastContextClient signature: (query, seed, tools) -> list[CodeSpan].
    def __call__(
        self, query: str, seed: list[CodeSpan], tools: Mapping[str, Any]
    ) -> list[CodeSpan]:
        prompt = _compose_prompt(query, seed)
        try:
            return self._run_path_a(prompt)
        except ImportError:
            pass  # package not importable → fall through to the Path B decision
        # Path B decision (deterministic; makes the terminal cause unambiguous).
        if self._cli_runner is None:
            raise ScoutUnavailable(errors.FASTCONTEXT_MISSING)
        if self._which("fastcontext") is None:
            raise ScoutUnavailable(errors.CLI_MISSING)
        return self._run_path_b(prompt)

    # --- Path A (in-process) ---

    def _build_agent(self, work_dir: str, trajectory_file: str) -> Any:
        if self._agent_factory is not None:
            return self._agent_factory(work_dir=work_dir, trajectory_file=trajectory_file)
        from fastcontext.agent.agent_factory import make_fastcontext_agent

        return make_fastcontext_agent(work_dir=work_dir, trajectory_file=trajectory_file)

    def _run_path_a(self, prompt: str) -> list[CodeSpan]:
        trajectory = self._new_trajectory_file()
        try:
            # Lock spans assert_local → env-set → construct → full run, closing the
            # TOCTOU window and serializing FC_* env writes across worker threads.
            with _SCOUT_ENV_LOCK:
                self._assert_local(
                    self._settings.lm_api_base, allow_remote=self._settings.allow_remote
                )
                with _managed_fc_env(_fc_env_from_settings(self._settings)):
                    try:
                        agent = self._build_agent(self._repo_root, trajectory)
                        answer = _run_coro_on_worker_thread(
                            lambda: agent.run(prompt, max_turns=self._max_turns, citation=True)
                        )
                    except ImportError:
                        raise  # signal the Path B fallback (caught by __call__)
                    except (RipgrepMissingError, AirGapError):
                        raise  # Tier-0 / air-gap floor, never a degrade
                    except ScoutUnavailable:
                        raise  # already typed; do not re-wrap
                    except OSError as err:
                        raise ScoutUnavailable(errors.CONNECTION_REFUSED) from err
                    except RuntimeError as err:
                        raise _map_runtime_error(err) from err
                    except Exception as err:  # noqa: BLE001 - third-party crash → degrade
                        # A buggy backend (e.g. FastContext's own citation formatter
                        # raising on malformed model output) is infra failure: degrade
                        # to Tier 0, never let a raw exception escape Scout.
                        raise ScoutUnavailable(errors.BACKEND_ERROR) from err
            return parse_final_answer(answer)
        finally:
            self._cleanup(trajectory)

    # --- Path B (CLI subprocess) ---

    def _run_path_b(self, prompt: str) -> list[CodeSpan]:
        # Air-gap before the subprocess is spawned (single helper, before egress).
        self._assert_local(self._settings.lm_api_base, allow_remote=self._settings.allow_remote)
        trajectory = self._new_trajectory_file()
        argv = [
            "fastcontext",
            "--query",
            prompt,
            "--max-turns",
            str(self._max_turns),
            "--traj",
            trajectory,
            "--citation",
        ]
        # FC_* scoped to the child only — the parent os.environ is never mutated.
        child_env = {**os.environ, **_fc_env_from_settings(self._settings)}
        try:
            output = self._cli_runner(
                argv, cwd=self._repo_root, env=child_env, timeout=self._cli_timeout_s
            )
        except (RipgrepMissingError, AirGapError):
            raise  # floors
        except ScoutUnavailable:
            raise
        except OSError as err:
            raise ScoutUnavailable(errors.CONNECTION_REFUSED) from err
        except RuntimeError as err:
            raise _map_runtime_error(err) from err
        except Exception as err:  # noqa: BLE001 - third-party crash → degrade
            raise ScoutUnavailable(errors.BACKEND_ERROR) from err
        finally:
            self._cleanup(trajectory)
        return parse_final_answer(output)

    # --- helpers ---

    def _new_trajectory_file(self) -> str:
        fd, path = tempfile.mkstemp(
            suffix=".jsonl", prefix="harpyja-scout-traj-", dir=self._trajectory_dir
        )
        os.close(fd)
        return path

    @staticmethod
    def _cleanup(path: str) -> None:
        try:
            os.unlink(path)
        except OSError:
            pass
