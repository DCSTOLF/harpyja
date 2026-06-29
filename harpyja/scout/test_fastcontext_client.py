"""Unit ACs for the default FastContext client (spec 0007).

Everything here is driven by injected fakes — no real `fastcontext` package, no
real model, no real subprocess. Covers AC2 (air-gap before construct/spawn),
AC3 (FC_* mapping + env set-then-restore under the lock), AC4 (concurrency / no
cross-contamination), AC5 (parse `<final_answer>`), AC6 (Path B runner), AC7
(trajectory outside repo), and AC10 (four distinct degrade causes + floor).
"""

from __future__ import annotations

import asyncio
import os
import threading
from dataclasses import replace
from pathlib import Path

import pytest

from harpyja.config.settings import Settings
from harpyja.gateway.gateway import AirGapError
from harpyja.scout import errors
from harpyja.scout.errors import ScoutUnavailable
from harpyja.symbols.ripgrep import RipgrepMissingError

_NONLOOPBACK = "http://10.1.2.3:11434/v1"


# --- Step 4 (T4): the two new degrade causes are distinct, stable identifiers ---


def test_scout_error_causes_are_distinct_identifiers():
    assert errors.FASTCONTEXT_MISSING == "fastcontext-missing"
    assert errors.CLI_MISSING == "cli-missing"
    # All five Scout causes are distinct (no collapse — AC10).
    causes = {
        errors.FASTCONTEXT_MISSING,
        errors.CLI_MISSING,
        errors.CONNECTION_REFUSED,
        errors.NO_ENDPOINT_CONFIGURED,
        errors.BACKEND_ERROR,
    }
    assert len(causes) == 5


# --- Fakes -----------------------------------------------------------------


class _FakeAgent:
    """An agent whose async `run` returns a canned answer and can record state."""

    def __init__(
        self, answer="", *, sleep=0.0, lock_sink=None, model_sink=None, key=None, raise_in_run=None
    ):
        self._answer = answer
        self._sleep = sleep
        self._lock_sink = lock_sink
        self._model_sink = model_sink
        self._key = key
        self._raise_in_run = raise_in_run

    async def run(self, prompt, max_turns=4, verbose=False, citation=False):
        if self._sleep:
            await asyncio.sleep(self._sleep)
        # Lazy per-call reads (the FC_REASONING_EFFORT/llm.py:77 analog).
        if self._lock_sink is not None:
            from harpyja.scout.client import _SCOUT_ENV_LOCK

            self._lock_sink["at_run"] = _SCOUT_ENV_LOCK.locked()
        if self._model_sink is not None:
            self._model_sink[self._key] = os.environ.get("FC_MODEL")
        if self._raise_in_run is not None:
            raise self._raise_in_run
        return self._answer


def _factory_returning(agent, captured=None):
    def factory(*, work_dir, trajectory_file):
        if captured is not None:
            captured["work_dir"] = work_dir
            captured["trajectory_file"] = trajectory_file
            captured["fc_model"] = os.environ.get("FC_MODEL")
        return agent

    return factory


def _factory_raising(exc):
    def factory(*, work_dir, trajectory_file):
        raise exc

    return factory


def _client(settings, repo, **kw):
    from harpyja.scout.client import DefaultFastContextClient

    return DefaultFastContextClient(settings, str(repo), **kw)


# --- Step 6 (T6): FC_* mapping + set-then-restore env guard -----------------


def test_fc_env_maps_from_settings():
    from harpyja.scout.client import _fc_env_from_settings

    s = replace(Settings(), scout_model="m", lm_api_base="http://127.0.0.1:11434/v1")
    env = _fc_env_from_settings(s)
    assert env["FC_MODEL"] == "m"
    assert env["FC_BASE_URL"] == "http://127.0.0.1:11434/v1"
    assert env["FC_API_KEY"] == "ollama"
    assert env["FC_MAX_TOKENS"] == str(s.scout_max_tokens)
    assert env["FC_TEMPERATURE"] == str(s.scout_temperature)
    assert env["FC_REASONING_EFFORT"] == str(s.scout_reasoning_effort)


def test_fc_env_set_then_restore_preserves_unset(monkeypatch):
    from harpyja.scout.client import _managed_fc_env

    monkeypatch.delenv("FC_MODEL", raising=False)
    with _managed_fc_env({"FC_MODEL": "x"}):
        assert os.environ["FC_MODEL"] == "x"
    assert "FC_MODEL" not in os.environ  # absent before → absent after


def test_fc_env_set_then_restore_preserves_empty(monkeypatch):
    from harpyja.scout.client import _managed_fc_env

    monkeypatch.setenv("FC_MODEL", "")  # empty (set) before
    with _managed_fc_env({"FC_MODEL": "x"}):
        assert os.environ["FC_MODEL"] == "x"
    assert os.environ["FC_MODEL"] == ""  # restored to empty, not deleted


def test_fc_env_restored_on_exception(monkeypatch):
    from harpyja.scout.client import _managed_fc_env

    monkeypatch.setenv("FC_MODEL", "orig")
    with pytest.raises(ValueError):
        with _managed_fc_env({"FC_MODEL": "x"}):
            raise ValueError("boom")
    assert os.environ["FC_MODEL"] == "orig"


# --- Step 8 (T8): Path A — air-gap, trajectory, parse, worker-thread bridge --


def test_client_asserts_local_before_agent_constructed(tmp_path):
    constructed = {"called": False}

    def factory(*, work_dir, trajectory_file):
        constructed["called"] = True
        return _FakeAgent("")

    s = replace(Settings(), lm_api_base=_NONLOOPBACK)
    with pytest.raises(AirGapError):
        _client(s, tmp_path, agent_factory=factory)("q", [], {})
    assert constructed["called"] is False  # agent never built


def test_client_trajectory_file_outside_repo(tmp_path):
    (tmp_path / "a.py").write_text("x\n", encoding="utf-8")
    captured = {}
    agent = _FakeAgent("<final_answer>a.py:1</final_answer>")
    _client(Settings(), tmp_path, agent_factory=_factory_returning(agent, captured))("q", [], {})
    assert captured["work_dir"] == str(tmp_path)
    traj = Path(captured["trajectory_file"]).resolve()
    assert tmp_path.resolve() not in traj.parents and traj != tmp_path.resolve()


def test_client_runs_agent_and_parses_final_answer(tmp_path):
    agent = _FakeAgent("noise\n<final_answer>\npkg/a.py:10-12\npkg/b.py:3\n</final_answer>")
    out = _client(Settings(), tmp_path, agent_factory=_factory_returning(agent))("q", [], {})
    assert [(c.path, c.start_line, c.end_line) for c in out] == [
        ("pkg/a.py", 10, 12),
        ("pkg/b.py", 3, 3),
    ]


def test_client_bridges_awaitable_from_running_loop(tmp_path):
    agent = _FakeAgent("<final_answer>a.py:1</final_answer>")
    client = _client(Settings(), tmp_path, agent_factory=_factory_returning(agent))

    async def driver():
        # A naive asyncio.run inside the client would raise here; the worker
        # thread makes it safe (D1).
        return client("q", [], {})

    out = asyncio.run(driver())
    assert [(c.path, c.start_line) for c in out] == [("a.py", 1)]


# --- Step 10 (T10): single-flight lock span + concurrency -------------------


def test_client_holds_lock_across_full_agent_run(tmp_path):
    marks = {}
    agent = _FakeAgent("<final_answer>a.py:1</final_answer>", lock_sink=marks)

    def factory(*, work_dir, trajectory_file):
        from harpyja.scout.client import _SCOUT_ENV_LOCK

        marks["at_construct"] = _SCOUT_ENV_LOCK.locked()
        return agent

    _client(Settings(), tmp_path, agent_factory=factory)("q", [], {})
    assert marks["at_construct"] is True
    assert marks["at_run"] is True  # held across the full run, not just construct


def test_parallel_scout_calls_no_fc_model_cross_contamination(tmp_path):
    observed = {}
    start = threading.Barrier(2)

    def call(model):
        s = replace(Settings(), scout_model=model)
        # Capture FC_MODEL *during the run* (after a sleep) — the window the lock
        # must protect; without serialization the other thread would clobber it.
        agent = _FakeAgent(
            "<final_answer>a.py:1</final_answer>", sleep=0.05, model_sink=observed, key=model
        )
        client = _client(s, tmp_path, agent_factory=_factory_returning(agent))
        start.wait()
        client("q", [], {})

    t1 = threading.Thread(target=call, args=("modelA",))
    t2 = threading.Thread(target=call, args=("modelB",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert observed == {"modelA": "modelA", "modelB": "modelB"}


# --- Step 12 (T12): Path B CLI runner fallback ------------------------------


def _import_error_factory():
    return _factory_raising(ImportError("no fastcontext"))


def test_client_path_b_drives_injected_runner(tmp_path):
    seen = {}

    def runner(argv, *, cwd, env, timeout):
        seen["argv"] = argv
        seen["cwd"] = cwd
        seen["env"] = env
        seen["timeout"] = timeout
        return "<final_answer>a.py:7</final_answer>"

    out = _client(
        Settings(),
        tmp_path,
        agent_factory=_import_error_factory(),
        cli_runner=runner,
        which=lambda name: "/usr/local/bin/fastcontext",
    )("q", [], {})
    assert [(c.path, c.start_line) for c in out] == [("a.py", 7)]
    assert seen["cwd"] == str(tmp_path)
    # Spec 0011 seam (a): the CLI runs WITHOUT --citation so FC never calls its
    # crashing format_citations; Harpyja parses the raw answer text itself.
    assert "--citation" not in seen["argv"]
    traj_idx = seen["argv"].index("--traj") + 1
    traj = Path(seen["argv"][traj_idx]).resolve()
    assert tmp_path.resolve() not in traj.parents  # temp trajectory outside repo
    assert seen["timeout"] and seen["timeout"] > 0


def test_client_path_b_asserts_local_before_spawn(tmp_path):
    spawned = {"called": False}

    def runner(argv, *, cwd, env, timeout):
        spawned["called"] = True
        return ""

    s = replace(Settings(), lm_api_base=_NONLOOPBACK)
    with pytest.raises(AirGapError):
        _client(
            s,
            tmp_path,
            agent_factory=_import_error_factory(),
            cli_runner=runner,
            which=lambda name: "/usr/local/bin/fastcontext",
        )("q", [], {})
    assert spawned["called"] is False


def test_client_path_b_env_scoped_to_child(tmp_path, monkeypatch):
    monkeypatch.delenv("FC_MODEL", raising=False)
    seen = {}

    def runner(argv, *, cwd, env, timeout):
        seen["env"] = env
        return "<final_answer>a.py:1</final_answer>"

    s = replace(Settings(), scout_model="child-model")
    _client(
        s,
        tmp_path,
        agent_factory=_import_error_factory(),
        cli_runner=runner,
        which=lambda name: "/usr/local/bin/fastcontext",
    )("q", [], {})
    assert seen["env"]["FC_MODEL"] == "child-model"  # FC_* carried to the child
    assert "FC_MODEL" not in os.environ  # parent env never mutated (D2)


# --- Step 14 (T14): deterministic fallback state machine + four causes -------


def test_client_fastcontext_missing_when_runner_unwired(tmp_path):
    with pytest.raises(ScoutUnavailable) as ei:
        _client(Settings(), tmp_path, agent_factory=_import_error_factory(), cli_runner=None)(
            "q", [], {}
        )
    assert ei.value.cause == errors.FASTCONTEXT_MISSING


def test_client_cli_missing_when_binary_absent(tmp_path):
    with pytest.raises(ScoutUnavailable) as ei:
        _client(
            Settings(),
            tmp_path,
            agent_factory=_import_error_factory(),
            cli_runner=lambda *a, **k: "",
            which=lambda name: None,
        )("q", [], {})
    assert ei.value.cause == errors.CLI_MISSING


def test_client_connection_refused_maps_cause(tmp_path):
    agent = _FakeAgent("", raise_in_run=ConnectionRefusedError("refused"))
    with pytest.raises(ScoutUnavailable) as ei:
        _client(Settings(), tmp_path, agent_factory=_factory_returning(agent))("q", [], {})
    assert ei.value.cause == errors.CONNECTION_REFUSED


def test_client_missing_fc_base_url_maps_no_endpoint(tmp_path):
    factory = _factory_raising(
        RuntimeError("Missing required environment variable FC_BASE_URL or BASE_URL.")
    )
    with pytest.raises(ScoutUnavailable) as ei:
        _client(Settings(), tmp_path, agent_factory=factory)("q", [], {})
    assert ei.value.cause == errors.NO_ENDPOINT_CONFIGURED


def test_client_backend_error_wraps_runtimeerror(tmp_path):
    boom = RuntimeError("boom")
    with pytest.raises(ScoutUnavailable) as ei:
        _client(Settings(), tmp_path, agent_factory=_factory_raising(boom))("q", [], {})
    assert ei.value.cause == errors.BACKEND_ERROR
    assert ei.value.__cause__ is boom  # foreign exception preserved


def test_client_unexpected_backend_exception_maps_backend_error(tmp_path):
    # A third-party crash (e.g. FastContext's own citation formatter raising
    # TypeError on malformed model output) is infra failure → degrade, never a
    # raw exception escaping Scout.
    agent = _FakeAgent("", raise_in_run=TypeError("string indices must be integers"))
    with pytest.raises(ScoutUnavailable) as ei:
        _client(Settings(), tmp_path, agent_factory=_factory_returning(agent))("q", [], {})
    assert ei.value.cause == errors.BACKEND_ERROR


def test_client_missing_rg_propagates_floor(tmp_path):
    factory = _factory_raising(RipgrepMissingError("rg not found"))
    with pytest.raises(RipgrepMissingError):  # floor, NOT ScoutUnavailable
        _client(Settings(), tmp_path, agent_factory=factory)("q", [], {})


def test_client_weak_citations_stay_honest_empty(tmp_path):
    agent = _FakeAgent("I could not find anything relevant.")
    out = _client(Settings(), tmp_path, agent_factory=_factory_returning(agent))("q", [], {})
    assert out == []  # honest empty Tier-1 result, never a raise


# --- Spec 0011 (citation-shape): seam (a) — citation=False + bare-path parsing ---

_FIXTURE = (
    Path(__file__).parent / "fixtures" / "fc_citation_false_final_answer.txt"
).read_text(encoding="utf-8")


class _RecordingAgent:
    """Records the `citation` kwarg agent.run was invoked with."""

    def __init__(self, answer="", sink=None):
        self._answer = answer
        self._sink = sink if sink is not None else {}

    async def run(self, prompt, max_turns=4, verbose=False, citation=False):
        self._sink["citation"] = citation
        return self._answer


def _parse(text):
    from harpyja.scout.client import parse_final_answer

    return parse_final_answer(text)


def _shape(spans):
    return [(c.path, c.start_line, c.end_line) for c in spans]


def test_parse_final_answer_bare_path_emits_file_level_span():
    # AC1: a bare path (no :line) inside <final_answer> → a file-level CodeSpan.
    spans = _parse("<final_answer>\npkg/migrations.py (no line)\n</final_answer>")
    assert _shape(spans) == [("pkg/migrations.py", None, None)]
    assert spans[0].is_file_level


def test_parse_final_answer_bare_path_has_both_lines_none():
    # AC4 (honest precision): no line range invented — BOTH fields None.
    (span,) = _parse("<final_answer>\nsrc/app.py\n</final_answer>")
    assert span.start_line is None and span.end_line is None


def test_parse_final_answer_path_start_stays_spanned():
    # AC2 (regression): path:start and path:start-end keep int lines.
    assert _shape(_parse("<final_answer>\na.py:10-12\nb.py:3\n</final_answer>")) == [
        ("a.py", 10, 12),
        ("b.py", 3, 3),
    ]


def test_parse_final_answer_mixes_bare_and_spanned_refs():
    # AC3: each ref normalized per its own shape in one answer.
    assert _shape(_parse("<final_answer>\na.py:1-2\nb.py\n</final_answer>")) == [
        ("a.py", 1, 2),
        ("b.py", None, None),
    ]


def test_parse_final_answer_malformed_line_degrades_to_file_level():
    # AC5: a usable path with a non-numeric line → file-level (don't drop the
    # path over a bad line, don't fabricate a range).
    assert _shape(_parse("<final_answer>\nparser.py:abc (bad line)\n</final_answer>")) == [
        ("parser.py", None, None)
    ]


def test_parse_final_answer_prose_filename_not_spurious_file_level():
    # AC22: an incidental filename inside a prose line is NOT promoted to a
    # file-level span; the whole prose line is not a citation.
    line = "the change is similar to test_app.py, see app.py:42 for context"
    assert _parse(f"<final_answer>\n{line}\n</final_answer>") == []


def test_parse_final_answer_fixture_covers_all_shapes():
    # AC11: driven by the committed real-FC-grammar fixture. The two spanned and
    # two file-level refs survive; the prose negative-control line is dropped.
    assert _shape(_parse(_FIXTURE)) == [
        ("auth.py", 1, 2),
        ("validate.py", 20, 20),
        ("db.py", None, None),
        ("parser.py", None, None),
    ]


def test_parse_final_answer_output_has_no_half_none_span():
    # AC23 (parse boundary): every emitted span is both-int or both-None.
    for span in _parse(_FIXTURE):
        both_int = span.start_line is not None and span.end_line is not None
        assert span.is_file_level or both_int


def test_parse_final_answer_no_ref_is_honest_empty():
    # AC8 (honest-empty half): prose with no citation line → [], not a raise.
    assert _parse("I looked around but found nothing of note here.") == []


def test_parse_final_answer_reports_shape_tally():
    # AC17 (producer side): the parser reports the per-shape text-ref tally.
    from harpyja.scout.client import parse_final_answer_with_tally

    spans, tally = parse_final_answer_with_tally(_FIXTURE)
    assert tally.spanned == 2
    assert tally.filelevel == 2


def test_client_invokes_fastcontext_with_citation_false(tmp_path):
    # Seam (a): the agent is driven with citation=False, bypassing FC's crashing
    # format_citations entirely (supports AC20 — zero backend-error live).
    sink = {}
    agent = _RecordingAgent("<final_answer>a.py:1</final_answer>", sink)
    _client(Settings(), tmp_path, agent_factory=_factory_returning(agent))("q", [], {})
    assert sink["citation"] is False
