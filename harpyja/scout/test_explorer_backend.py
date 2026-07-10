"""RED (T15, AC1/AC7): the ExplorerBackend — a new ScoutBackend impl.

The backend satisfies the UNCHANGED `ScoutBackend` seam, is injected into
`ScoutEngine` via the existing DI slot, is driven deterministically by fakes (no
live model), and calls `gateway.assert_local()` ONCE before the loop starts — a
non-loopback endpoint raises `AirGapError` and the loop never begins.
"""

import json

import pytest

from harpyja.config.settings import Settings
from harpyja.gateway.gateway import AirGapError, ModelGateway
from harpyja.scout.engine import ScoutEngine
from harpyja.scout.explorer_backend import ExplorerBackend
from harpyja.server.types import CodeSpan


def _file(tmp_path, rel, n=50):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(f"line {i}" for i in range(1, n + 1)) + "\n", encoding="utf-8")
    return p


class _FakeSearch:
    def __init__(self, spans=None):
        self.spans = spans or []

    def search(self, pattern, scope=None, *, repo_root=None):
        return list(self.spans)


def _tc(name, **args):
    return {"id": "c", "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}


def _scripted(*responses):
    seq = list(responses)

    def model_call(messages):
        return seq.pop(0) if len(seq) > 1 else seq[0]

    return model_call


def _backend(tmp_path, *, gateway=None, model_call=None, search=None):
    return ExplorerBackend(
        gateway=gateway or ModelGateway(api_base="http://127.0.0.1:11434/v1"),
        repo_path=str(tmp_path),
        settings=Settings(),
        manifest=[],
        search_engine=search or _FakeSearch(),
        model_call=model_call,
    )


def test_explorer_backend_satisfies_scoutbackend_run(tmp_path):
    _file(tmp_path, "a.py")
    model = _scripted(
        {"content": "", "tool_calls": [_tc("submit_citations", citations=[{"path": "a.py"}])]}
    )
    backend = _backend(tmp_path, model_call=model)
    out = backend.run("find it", [])
    assert isinstance(out, list)
    assert callable(backend.run)


def test_fakes_drive_loop_deterministically_to_citations(tmp_path):
    _file(tmp_path, "real.py", n=50)
    model = _scripted(
        {"content": "", "tool_calls": [_tc("grep", pattern="needle")]},
        {"content": "", "tool_calls": [_tc(
            "submit_citations",
            citations=[{"path": "real.py", "start_line": 1, "end_line": 2}])]},
    )
    backend = _backend(tmp_path, model_call=model, search=_FakeSearch([CodeSpan("real.py", 1, 1)]))
    out = backend.run("q", [])
    assert out == [CodeSpan(path="real.py", start_line=1, end_line=2)]


def test_explorer_backend_injected_into_scout_engine(tmp_path):
    _file(tmp_path, "real.py", n=50)
    model = _scripted({"content": "", "tool_calls": [_tc("submit_citations",
                       citations=[{"path": "real.py", "start_line": 3, "end_line": 4}])]})
    backend = _backend(tmp_path, model_call=model)
    engine = ScoutEngine(backend, lambda q: [], Settings(), str(tmp_path), file_set=None)
    out = engine.search("q", scope=str(tmp_path))
    assert out == [CodeSpan(path="real.py", start_line=3, end_line=4)]


def test_assert_local_called_once_before_loop_starts(tmp_path):
    calls = []

    def model_call(messages):  # must never run for a non-loopback endpoint
        calls.append(1)
        return {"content": "", "tool_calls": []}

    backend = _backend(
        tmp_path,
        gateway=ModelGateway(api_base="http://8.8.8.8:11434/v1"),  # non-loopback
        model_call=model_call,
    )
    with pytest.raises(AirGapError):
        backend.run("q", [])
    assert calls == []  # the loop never started


# --- Typed degradation + degrade-rate (T17, AC8/AC9) ---

from harpyja.scout import errors  # noqa: E402
from harpyja.scout.errors import ScoutUnavailable  # noqa: E402
from harpyja.symbols.ripgrep import RipgrepMissingError  # noqa: E402


class _RaisingSearch:
    def __init__(self, exc):
        self._exc = exc

    def search(self, pattern, scope=None, *, repo_root=None):
        raise self._exc


def test_model_unreachable_raises_distinct_cause(tmp_path):
    def model_call(messages):
        raise ConnectionError("connection refused")

    backend = _backend(tmp_path, model_call=model_call)
    with pytest.raises(ScoutUnavailable) as ei:
        backend.run("q", [])
    assert ei.value.cause == errors.MODEL_UNREACHABLE


def test_turn_exhausted_empty_raises_distinct_cause(tmp_path):
    model = _scripted({"content": "", "tool_calls": [_tc("grep", pattern="x")]})  # never submits
    backend = ExplorerBackend(
        gateway=ModelGateway(api_base="http://127.0.0.1:11434/v1"),
        repo_path=str(tmp_path), settings=Settings(scout_max_turns=3),
        manifest=[], search_engine=_FakeSearch([CodeSpan("a.py", 1, 1)]), model_call=model,
    )
    with pytest.raises(ScoutUnavailable) as ei:
        backend.run("q", [])
    assert ei.value.cause == errors.LOOP_TURNS_EXHAUSTED


def test_wall_clock_exhausted_empty_raises_distinct_cause(tmp_path):
    model = _scripted({"content": "", "tool_calls": [_tc("grep", pattern="x")]})  # never submits
    ticks = iter([0.0, 100.0, 200.0, 300.0, 400.0])
    backend = ExplorerBackend(
        gateway=ModelGateway(api_base="http://127.0.0.1:11434/v1"),
        repo_path=str(tmp_path),
        settings=Settings(scout_max_turns=100, scout_wall_clock_s=150.0),
        manifest=[], search_engine=_FakeSearch([CodeSpan("a.py", 1, 1)]),
        model_call=model, clock=lambda: next(ticks),
    )
    with pytest.raises(ScoutUnavailable) as ei:
        backend.run("q", [])
    assert ei.value.cause == errors.LOOP_WALLCLOCK_EXHAUSTED


def test_backend_raise_maps_to_backend_error_cause(tmp_path):
    def model_call(messages):
        raise RuntimeError("internal explosion")

    backend = _backend(tmp_path, model_call=model_call)
    with pytest.raises(ScoutUnavailable) as ei:
        backend.run("q", [])
    assert ei.value.cause == errors.BACKEND_ERROR


def test_all_four_causes_are_distinct_stable_ids():
    causes = {
        errors.MODEL_UNREACHABLE,
        errors.LOOP_TURNS_EXHAUSTED,
        errors.LOOP_WALLCLOCK_EXHAUSTED,
        errors.BACKEND_ERROR,
    }
    assert len(causes) == 4


def test_well_formed_empty_submit_is_honest_empty_not_unavailable(tmp_path):
    model = _scripted({"content": "", "tool_calls": [_tc("submit_citations", citations=[])]})
    backend = _backend(tmp_path, model_call=model)
    assert backend.run("q", []) == []  # honest-empty, no raise


def test_airgap_error_never_mapped_to_scout_unavailable(tmp_path):
    backend = _backend(tmp_path, gateway=ModelGateway(api_base="http://8.8.8.8:11434/v1"))
    with pytest.raises(AirGapError):
        backend.run("q", [])  # a floor, never ScoutUnavailable


def test_ripgrep_missing_propagates_as_floor(tmp_path):
    model = _scripted({"content": "", "tool_calls": [_tc("grep", pattern="x")]})
    backend = _backend(
        tmp_path, model_call=model,
        search=_RaisingSearch(RipgrepMissingError("no rg")),
    )
    with pytest.raises(RipgrepMissingError):
        backend.run("q", [])  # a floor, never ScoutUnavailable


def test_tool_schemas_match_the_built_tool_surface_single_source(tmp_path):
    # T21 (refactor guard): the model-facing tool SCHEMAS the backend advertises must
    # name EXACTLY the built navigation tools plus the terminal action — no drift
    # between the schema list and the dispatch surface.
    from harpyja.scout.explorer_backend import _tool_schemas
    from harpyja.scout.explorer_loop import SUBMIT_TOOL
    from harpyja.scout.explorer_tools import build_explorer_tools

    schema_names = {s["function"]["name"] for s in _tool_schemas()}
    tool_names = set(build_explorer_tools(str(tmp_path), Settings(), search_engine=_FakeSearch()))
    assert schema_names == tool_names | {SUBMIT_TOOL}


# --- Turns-used native seam (T3/T4, AC3) ---
#
# Spec 0025 migrates the 0022 turns-used diagnostic OFF the FastContext trajectory
# scrape (`count_turns`) and ONTO the explorer's native per-run count. The loop
# already computes `LoopResult.turns_used`; the backend surfaces it as a public
# per-run seam `last_turns_used`, mirroring `ScoutEngine.last_tally`. `turns_used`
# is the count of model iterations CONSUMED (not the `scout_max_turns` cap).


def test_backend_exposes_last_turns_used(tmp_path):
    # grep then submit == 2 model iterations consumed.
    _file(tmp_path, "real.py", n=50)
    model = _scripted(
        {"content": "", "tool_calls": [_tc("grep", pattern="needle")]},
        {"content": "", "tool_calls": [_tc(
            "submit_citations",
            citations=[{"path": "real.py", "start_line": 1, "end_line": 2}])]},
    )
    backend = _backend(tmp_path, model_call=model, search=_FakeSearch([CodeSpan("real.py", 1, 1)]))
    backend.run("q", [])
    assert backend.last_turns_used == 2


def test_last_turns_used_counts_consumed_iterations_not_the_cap(tmp_path):
    # A submit on the first iteration consumes exactly one turn — NOT scout_max_turns.
    _file(tmp_path, "a.py")
    model = _scripted({"content": "", "tool_calls": [_tc("submit_citations",
                       citations=[{"path": "a.py"}])]})
    backend = ExplorerBackend(
        gateway=ModelGateway(api_base="http://127.0.0.1:11434/v1"),
        repo_path=str(tmp_path), settings=Settings(scout_max_turns=12),
        manifest=[], search_engine=_FakeSearch(), model_call=model,
    )
    backend.run("q", [])
    assert backend.last_turns_used == 1  # consumed, not the cap of 12


def test_last_turns_used_reset_per_run(tmp_path):
    _file(tmp_path, "real.py", n=50)
    span = _FakeSearch([CodeSpan("real.py", 1, 1)])
    two_turn = _scripted(
        {"content": "", "tool_calls": [_tc("grep", pattern="n")]},
        {"content": "", "tool_calls": [_tc("submit_citations",
                       citations=[{"path": "real.py", "start_line": 1, "end_line": 2}])]},
    )
    backend = _backend(tmp_path, model_call=two_turn, search=span)
    backend.run("q", [])
    assert backend.last_turns_used == 2
    # A fresh single-turn run resets to 1, not accumulate to 3.
    backend._model_call = _scripted({"content": "", "tool_calls": [_tc(
        "submit_citations", citations=[{"path": "real.py", "start_line": 1, "end_line": 2}])]})
    backend.run("q", [])
    assert backend.last_turns_used == 1


def test_last_turns_used_set_on_turn_exhaustion_degrade(tmp_path):
    # The seam must be populated even on the degrade path it exists to preserve —
    # else the migrated 0022 measurement regresses on exhausted runs.
    model = _scripted({"content": "", "tool_calls": [_tc("grep", pattern="x")]})  # never submits
    backend = ExplorerBackend(
        gateway=ModelGateway(api_base="http://127.0.0.1:11434/v1"),
        repo_path=str(tmp_path), settings=Settings(scout_max_turns=3),
        manifest=[], search_engine=_FakeSearch([CodeSpan("a.py", 1, 1)]), model_call=model,
    )
    with pytest.raises(ScoutUnavailable):
        backend.run("q", [])
    assert backend.last_turns_used == 3  # the exhausted turn count is recorded


def test_degrade_rate_is_first_class_reported_field(tmp_path):
    _file(tmp_path, "a.py")
    empty = _scripted({"content": "", "tool_calls": [_tc("submit_citations", citations=[])]})
    backend = _backend(tmp_path, model_call=empty)
    assert backend.degrade_rate == 0.0  # no runs yet

    backend.run("q", [])  # a clean honest-empty run — NOT a degrade
    assert backend.run_count == 1
    assert backend.degrade_count == 0
    assert backend.degrade_rate == 0.0

    # A degrade (model unreachable) moves the reported rate.
    backend._model_call = lambda messages: (_ for _ in ()).throw(ConnectionError("x"))
    with pytest.raises(ScoutUnavailable):
        backend.run("q", [])
    assert backend.run_count == 2
    assert backend.degrade_count == 1
    assert backend.degrade_rate == 0.5


# --- spec 0027 (AC1/AC2): no eager whole-repo map; bounded, repo-size-independent ---

from harpyja.index.manifest import ManifestEntry  # noqa: E402


def _manifest(n):
    return [
        ManifestEntry(path=f"pkg/mod{i}/file{i}.py", language="python", size=100,
                      hash="h", mtime=0.0, prior=0.5)
        for i in range(n)
    ]


def _capture(box):
    def model_call(messages):
        box.setdefault("first", messages)
        return {"content": "", "tool_calls": [_tc("submit_citations", citations=[])]}
    return model_call


def _turn1_payload(messages):
    return "".join(str(m.get("content", "")) for m in messages)


def _run_with_manifest(tmp_path, n, query, box):
    ExplorerBackend(
        gateway=ModelGateway(api_base="http://127.0.0.1:11434/v1"),
        repo_path=str(tmp_path), settings=Settings(), manifest=_manifest(n),
        search_engine=_FakeSearch(), model_call=_capture(box),
    ).run(query, [])


def test_run_loop_injects_no_whole_repo_listing(tmp_path):
    box = {}
    _run_with_manifest(tmp_path, 500, "where is the retry backoff", box)
    payload = _turn1_payload(box["first"])
    # NO whole-repo listing: no manifest path appears in the turn-1 prompt.
    assert "pkg/mod0/file0.py" not in payload
    assert "pkg/mod499/file499.py" not in payload
    # the QUERY is preserved (a minimal prompt, not an empty one).
    assert "retry backoff" in payload


def test_turn1_payload_bounded_and_repo_size_independent(tmp_path):
    small_box, large_box = {}, {}
    _run_with_manifest(tmp_path, 3, "find the thing", small_box)
    _run_with_manifest(tmp_path, 3000, "find the thing", large_box)
    small = _turn1_payload(small_box["first"])
    large = _turn1_payload(large_box["first"])
    for p in (small, large):
        assert len(p) // 4 <= 2000  # <= ~2000 tokens (AC1 bound)
    # Repo-size independence: no manifest term → the two payloads are IDENTICAL.
    assert small == large


# --- spec 0027 (AC8): turns_used RETIRED as a why-did-it-end signal; cause is truth ---

import re as _re  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

import harpyja.scout.errors as _scout_errors  # noqa: E402
from harpyja.scout.errors import ScoutUnavailable as _ScoutUnavailable  # noqa: E402


def test_wallclock_exhaustion_cause_derives_from_outcome_not_turns(tmp_path):
    # A clock that trips the wall-clock ceiling on the first turn → WALLCLOCK_EXHAUSTED
    # at a SUB-CAP turns_used. The degrade CAUSE derives from LoopResult.outcome, so it
    # is loop-wallclock-exhausted regardless of the (sub-cap) turns_used — which alone
    # could not distinguish this from a low-turn honest-empty.
    clock_vals = iter([0.0, 10**9, 10**9, 10**9])
    backend = ExplorerBackend(
        gateway=ModelGateway(api_base="http://127.0.0.1:11434/v1"),
        repo_path=str(tmp_path), settings=Settings(), manifest=[],
        search_engine=_FakeSearch(),
        model_call=_scripted({"content": "", "tool_calls": [_tc("grep", pattern="x")]}),
        clock=lambda: next(clock_vals),
    )
    with pytest.raises(_ScoutUnavailable) as ei:
        backend.run("q", [])
    assert ei.value.cause == _scout_errors.LOOP_WALLCLOCK_EXHAUSTED
    # turns_used is recorded (the 0022 measurement) but is SUB-CAP — not the discriminant.
    assert backend.last_turns_used is not None
    assert backend.last_turns_used < Settings().scout_max_turns


def test_explorer_outcome_logic_does_not_branch_on_turns_used():
    # spec 0027 AC8 (executable guard): the two outcome-deciding modules must NOT infer
    # run outcome / degrade-kind from turns_used (None on any degrade; sub-cap on
    # wall-clock). turns_used survives ONLY as the 0022 turns-CONSUMED measurement
    # (assignments + the LoopResult carrier), never a comparison feeding a decision.
    for mod in ("explorer_backend.py", "explorer_loop.py"):
        text = (_Path("harpyja/scout") / mod).read_text()
        assert not _re.search(r"(turns_used|last_turns_used)\s*(==|!=|<=|>=|<|>)", text), mod
        assert not _re.search(r"(turns_used|last_turns_used)\s+is(\s+not)?\s+None", text), mod


class _RecordingGateway:
    """A fake gateway that records the kwargs passed to complete_with_tools.

    spec 0028 (AC1/AC2): lets a unit assert the explorer's generation-control
    params (max_tokens, chat_template_kwargs) reach the outbound request without a
    live model or network.
    """

    def __init__(self):
        self.calls = []
        self.messages = []

    def assert_local(self, resolver=None):
        return None

    def complete_with_tools(self, messages, tools, **params):
        self.calls.append(params)
        self.messages.append(list(messages))
        return {"content": "", "tool_calls": [], "finish_reason": "stop"}


def test_explorer_backend_max_tokens_field_default_is_2048():
    # spec 0028 AC2 (DRIFT-GUARD): the finite runaway cap lives on the explorer
    # object's OWN field default (field-default introspection, NOT a source grep),
    # so a Settings-bypassing construction is still bounded.
    import inspect

    param = inspect.signature(ExplorerBackend.__init__).parameters["max_tokens"]
    assert param.default == 2048


def test_default_model_call_passes_max_tokens_to_gateway(tmp_path):
    # spec 0028 AC2: the cap reaches the request as `max_tokens`.
    gw = _RecordingGateway()
    backend = _backend(tmp_path, gateway=gw)
    call = backend._default_model_call()
    call([{"role": "user", "content": "hi"}])
    assert gw.calls[0]["max_tokens"] == 2048


def _thinking_backend(tmp_path, gw, enable_thinking):
    return ExplorerBackend(
        gateway=gw,
        repo_path=str(tmp_path),
        settings=Settings(),
        manifest=[],
        search_engine=_FakeSearch(),
        enable_thinking=enable_thinking,
    )


def test_thinking_off_sends_enable_thinking_false(tmp_path):
    # spec 0028 AC1: thinking-off ⇒ the request carries chat_template_kwargs.
    gw = _RecordingGateway()
    call = _thinking_backend(tmp_path, gw, enable_thinking=False)._default_model_call()
    call([{"role": "user", "content": "hi"}])
    assert gw.calls[0]["chat_template_kwargs"] == {"enable_thinking": False}


def test_thinking_on_omits_chat_template_kwargs(tmp_path):
    # spec 0028 AC1: thinking-on ⇒ the param is OMITTED (not sent as True).
    gw = _RecordingGateway()
    call = _thinking_backend(tmp_path, gw, enable_thinking=True)._default_model_call()
    call([{"role": "user", "content": "hi"}])
    assert "chat_template_kwargs" not in gw.calls[0]


def test_explorer_rejects_no_think_query_token(tmp_path):
    # spec 0028 AC1: the knob is chat_template_kwargs, NEVER the inferior /no_think
    # query token (measured 43s, template-perturbing). No message carries it.
    gw = _RecordingGateway()
    call = _thinking_backend(tmp_path, gw, enable_thinking=False)._default_model_call()
    call([{"role": "user", "content": "find the thing"}])
    assert all("/no_think" not in str(m.get("content", "")) for m in gw.messages[0])


def test_generation_truncated_outcome_raises_scout_unavailable_generation_truncated(tmp_path):
    # spec 0028 AC3: a finish=length truncation degrades with the distinct fifth
    # cause `generation-truncated`, NOT model-unreachable and NOT honest-empty.
    model = _scripted({"content": "", "tool_calls": [], "finish_reason": "length"})
    backend = _backend(tmp_path, model_call=model)
    with pytest.raises(ScoutUnavailable) as ei:
        backend.run("q", [])
    assert ei.value.cause == errors.GENERATION_TRUNCATED
    assert ei.value.cause != errors.MODEL_UNREACHABLE


# --- Spec 0031 (live): Explorer backend trajectory capture (T18/T19) ---


def test_run_captures_last_trajectory_after_loop(tmp_path):
    """ExplorerBackend captures last_trajectory with model_turns, tools, and served_model."""
    _file(tmp_path, "real.py", n=50)

    def model_call(messages):
        # Return a response with served_model to verify it's threaded through
        return {
            "content": "",
            "tool_calls": [_tc("grep", pattern="needle")],
            "model": "served-model-test",
        }

    # Inject a multi-turn model call that uses grep then submits
    model = _scripted(
        {"content": "", "tool_calls": [_tc("grep", pattern="needle")], "model": "served-model-test"},
        {"content": "", "tool_calls": [_tc("submit_citations",
         citations=[{"path": "real.py", "start_line": 1, "end_line": 2}])], "model": "served-model-test"},
    )
    backend = _backend(tmp_path, model_call=model, search=_FakeSearch([CodeSpan("real.py", 1, 1)]))
    backend.run("q", [])

    # Verify last_trajectory is captured
    assert backend.last_trajectory is not None
    assert "model_turns" in backend.last_trajectory
    assert len(backend.last_trajectory["model_turns"]) >= 1  # At least one turn captured
    # Verify tool names are captured
    assert "tool_names_invoked" in backend.last_trajectory or any(
        "grep" in str(t.get("tool_calls", []))
        for t in backend.last_trajectory.get("model_turns", [])
    )
    # Verify served_model is in trajectory
    assert backend.last_trajectory.get("served_model") is not None


def test_run_nameless_tool_call_carries_typed_failure_as_data_not_raise(tmp_path):
    """Spec 0032 AC7: a nameless tool_call in the history never changes run()'s
    control flow — the strict tool-name failure is carried as DATA on
    last_trajectory, not raised.
    """
    _file(tmp_path, "real.py", n=50)
    nameless_call = {"id": "c0", "type": "function", "function": {}}  # no name
    model = _scripted(
        {"content": "", "tool_calls": [nameless_call]},
        {"content": "", "tool_calls": [_tc(
            "submit_citations",
            citations=[{"path": "real.py", "start_line": 1, "end_line": 2}])]},
    )
    backend = _backend(tmp_path, model_call=model)

    out = backend.run("q", [])  # same terminal path as a fully-named run: no raise

    assert out == [CodeSpan(path="real.py", start_line=1, end_line=2)]
    assert backend.last_turns_used == 2
    # The strict failure is data on the captured trajectory, never an exception.
    assert backend.last_trajectory is not None
    assert backend.last_trajectory["tool_names_failure"] == "tool-names-unextractable"
    assert backend.last_trajectory["tool_names_invoked"] == []


def test_last_trajectory_is_reset_per_run(tmp_path):
    """last_trajectory is None before first run and replaced (not accumulated) on next run."""
    _file(tmp_path, "real.py", n=50)

    model1 = _scripted(
        {"content": "", "tool_calls": [_tc("grep", pattern="n")]},
        {"content": "", "tool_calls": [_tc("submit_citations",
         citations=[{"path": "real.py", "start_line": 1, "end_line": 2}])]},
    )
    backend = _backend(tmp_path, model_call=model1, search=_FakeSearch([CodeSpan("real.py", 1, 1)]))

    # Initially None
    assert backend.last_trajectory is None

    # After first run
    backend.run("q", [])
    traj1 = backend.last_trajectory
    assert traj1 is not None
    initial_turn_count = len(traj1.get("model_turns", []))

    # After second run (fresh model call)
    model2 = _scripted(
        {"content": "", "tool_calls": [_tc("submit_citations",
         citations=[{"path": "real.py", "start_line": 1, "end_line": 2}])]},
    )
    backend._model_call = model2
    backend.run("q", [])
    traj2 = backend.last_trajectory

    # Verify it's replaced, not accumulated
    assert traj2 is not traj1  # Different object
    assert len(traj2.get("model_turns", [])) != 2 * initial_turn_count  # Not accumulated


def test_backend_threads_citation_counts_into_trajectory(tmp_path):
    """Spec 0033 AC5: the loop's submit-seam counts land on last_trajectory."""
    _file(tmp_path, "real.py", n=50)
    model = _scripted(
        # Submits one ref that will NOT resolve in-repo → found-then-dropped (1, 0).
        {"content": "", "tool_calls": [_tc(
            "submit_citations",
            citations=[{"path": "modeling/core.py", "start_line": 812, "end_line": 812}])]},
    )
    backend = _backend(tmp_path, model_call=model)
    out = backend.run("q", [])
    assert out == []  # the drop still yields honest-empty spans
    assert backend.last_trajectory is not None
    assert backend.last_trajectory["citations_submitted"] == 1
    assert backend.last_trajectory["citations_surviving"] == 0


# --- Spec 0034: reasoning observability — pins, think_mode, accumulator ---

from harpyja.scout.explorer_backend import derive_think_mode  # noqa: E402


def test_default_outbound_request_body_pinned(tmp_path):
    """PIN (0034 T1) + AC3 baseline: default Settings send EXACTLY max_tokens=2048 —
    no think param, no chat_template_kwargs. The byte-identity floor."""
    captured = {}

    class _Gw:
        api_base = "http://127.0.0.1:11434/v1"

        def assert_local(self, resolver=None):
            pass

        def complete_with_tools(self, messages, tools, **params):
            captured.update(params)
            return {"content": "", "tool_calls": [_tc(
                "submit_citations", citations=[])], "finish_reason": "tool_calls",
                "model": "m", "reasoning": None, "completion_tokens": 7}

    backend = ExplorerBackend(
        gateway=_Gw(), repo_path=str(tmp_path), settings=Settings(),
        manifest=[], search_engine=_FakeSearch(),
    )
    backend.run("q", [])
    assert captured == {"max_tokens": 2048}


def test_think_mode_default_omitted():
    assert derive_think_mode(None, True) == "default-omitted"


def test_think_mode_native_think_true():
    assert derive_think_mode(True, True) == "native-think-true"


def test_think_mode_native_think_false():
    assert derive_think_mode(False, True) == "native-think-false"


def test_think_mode_chat_template_disabled():
    assert derive_think_mode(None, False) == "chat-template-disabled"


def test_think_mode_native_wins_over_chat_template():
    """Double-set (think=False + enable_thinking=False): native precedence — the
    record is never ambiguous."""
    assert derive_think_mode(False, False) == "native-think-false"
    assert derive_think_mode(True, False) == "native-think-true"


def test_run_accumulates_per_turn_reasoning_and_finish(tmp_path):
    """AC2: a two-turn run lands two per_turn entries on last_trajectory."""
    _file(tmp_path, "real.py", n=50)
    model = _scripted(
        {"content": "", "tool_calls": [_tc("grep", pattern="n")],
         "finish_reason": "tool_calls", "reasoning": "let me look", "completion_tokens": 300},
        {"content": "", "tool_calls": [_tc("submit_citations", citations=[])],
         "finish_reason": "tool_calls", "reasoning": "submitting now", "completion_tokens": 120},
    )
    backend = _backend(tmp_path, model_call=model)
    backend.run("q", [])
    pt = backend.last_trajectory["per_turn"]
    assert [t["reasoning_chars"] for t in pt] == [len("let me look"), len("submitting now")]
    assert [t["completion_tokens"] for t in pt] == [300, 120]
    assert [t["finish_reason"] for t in pt] == ["tool_calls", "tool_calls"]


def test_accumulator_captures_final_length_truncated_turn(tmp_path):
    """AC2 (the turn the history route can't reach): a finish="length" final
    response gets a per_turn entry even though it never enters model_turns."""
    model = _scripted(
        {"content": "", "tool_calls": [], "finish_reason": "length",
         "reasoning": "x" * 51, "completion_tokens": 20},
    )
    backend = _backend(tmp_path, model_call=model)
    with pytest.raises(ScoutUnavailable):
        backend.run("q", [])
    pt = backend.last_trajectory["per_turn"]
    assert pt == [{"reasoning_chars": 51, "completion_tokens": 20,
                   "finish_reason": "length"}]
    # The intrinsic skew: the truncated turn is NOT in model_turns.
    assert all("length" != t.get("finish_reason") for t in
               backend.last_trajectory["model_turns"] if isinstance(t, dict))


def test_accumulator_reset_per_run(tmp_path):
    """AC2: per_turn from run 1 does not leak into run 2."""
    _file(tmp_path, "real.py", n=50)
    model1 = _scripted(
        {"content": "", "tool_calls": [_tc("grep", pattern="n")],
         "finish_reason": "tool_calls", "reasoning": "a", "completion_tokens": 1},
        {"content": "", "tool_calls": [_tc("submit_citations", citations=[])],
         "finish_reason": "tool_calls", "reasoning": "b", "completion_tokens": 2},
    )
    backend = _backend(tmp_path, model_call=model1)
    backend.run("q", [])
    assert len(backend.last_trajectory["per_turn"]) == 2
    backend._model_call = _scripted(
        {"content": "", "tool_calls": [_tc("submit_citations", citations=[])],
         "finish_reason": "tool_calls", "reasoning": "c", "completion_tokens": 3},
    )
    backend.run("q", [])
    assert len(backend.last_trajectory["per_turn"]) == 1  # replaced, not accumulated


def test_per_turn_reasoning_chars_none_when_absent_zero_when_empty(tmp_path):
    """AC2: no reasoning key → None; reasoning="" → 0 — never fabricated."""
    _file(tmp_path, "real.py", n=50)
    model = _scripted(
        {"content": "", "tool_calls": [_tc("grep", pattern="n")],
         "finish_reason": "tool_calls"},  # no reasoning key at all
        {"content": "", "tool_calls": [_tc("submit_citations", citations=[])],
         "finish_reason": "tool_calls", "reasoning": ""},  # present-but-empty
    )
    backend = _backend(tmp_path, model_call=model)
    backend.run("q", [])
    pt = backend.last_trajectory["per_turn"]
    assert pt[0]["reasoning_chars"] is None
    assert pt[1]["reasoning_chars"] == 0


def test_last_trajectory_carries_think_mode(tmp_path):
    """AC2: last_trajectory records the derived effective thinking mode."""
    _file(tmp_path, "real.py", n=50)
    model = _scripted(
        {"content": "", "tool_calls": [_tc("submit_citations", citations=[])],
         "finish_reason": "tool_calls"},
    )
    backend = _backend(tmp_path, model_call=model)
    backend.run("q", [])
    assert backend.last_trajectory["think_mode"] == "default-omitted"


def _capturing_gateway(captured):
    class _Gw:
        api_base = "http://127.0.0.1:11434/v1"

        def assert_local(self, resolver=None):
            pass

        def complete_with_tools(self, messages, tools, **params):
            captured.update(params)
            return {"content": "", "tool_calls": [_tc(
                "submit_citations", citations=[])], "finish_reason": "tool_calls",
                "model": "m", "reasoning": None, "completion_tokens": 7}

    return _Gw()


def test_default_outbound_carries_no_think_param(tmp_path):
    """AC3 (0034) + spec 0038 AC2: default Settings → NO thinking-control key at
    all — no dead `think`, no `reasoning_effort`. None preserves the endpoint
    default on the SAME transport (the 0034 byte-identity pin survives the 0038
    reconciliation: this branch is v1-variant, not an endpoint switch)."""
    captured = {}
    backend = ExplorerBackend(
        gateway=_capturing_gateway(captured), repo_path=str(tmp_path),
        settings=Settings(), manifest=[], search_engine=_FakeSearch(),
    )
    backend.run("q", [])
    assert "think" not in captured
    assert "reasoning_effort" not in captured


# Spec 0038 (exact-pin reconciliation, recorded): the 0034 pins below asserted
# `think=True/False` rode the outbound request — a field the /v1 layer silently
# DROPS (0037's committed no-op finding). The knob now routes through the
# probe-proven honoring mechanism, `reasoning_effort` ("high"/"none") on the
# SAME /v1 transport (specs/0038-reconciliation/probes/probe_result.json,
# outcome=v1-variant). The dead `think` field is no longer sent: a serialized
# no-op field pretending to be a knob is the exact hole 0037 caught.


def test_explorer_think_true_sends_reasoning_effort_high(tmp_path):
    """Spec 0038 AC2: explorer_think=True rides as reasoning_effort="high"
    (probe-observed thinking-ON arm); the dropped `think` field is gone."""
    captured = {}
    backend = ExplorerBackend(
        gateway=_capturing_gateway(captured), repo_path=str(tmp_path),
        settings=Settings(), manifest=[], search_engine=_FakeSearch(),
        think=True,
    )
    backend.run("q", [])
    assert captured.get("reasoning_effort") == "high"
    assert "think" not in captured


def test_explorer_think_false_sends_reasoning_effort_none(tmp_path):
    """Spec 0038 AC2: explorer_think=False rides as reasoning_effort="none"
    (probe-observed genuinely-off arm: content, stop, zero reasoning)."""
    captured = {}
    backend = ExplorerBackend(
        gateway=_capturing_gateway(captured), repo_path=str(tmp_path),
        settings=Settings(), manifest=[], search_engine=_FakeSearch(),
        think=False,
    )
    backend.run("q", [])
    assert captured.get("reasoning_effort") == "none"
    assert "think" not in captured


def test_explorer_think_wiring_matches_committed_probe_outcome(tmp_path):
    """Spec 0038 AC2 tripwire: the WIRED mechanism must match the COMMITTED
    probe outcome — a loud FAIL (not a skip) on mismatch.

    The wiring below implements the `v1-variant` outcome (reasoning_effort on
    the existing /v1 transport, all three arms on the SAME method — no
    per-value transport split). If a future re-probe flips the committed
    outcome, this pin fails loudly: wiring and evidence must be reconciled
    explicitly, never allowed to drift apart (the 0037 lesson, mechanized).
    """
    from harpyja.eval.reconcile_probe import load_committed_reconcile_probe_result

    result = load_committed_reconcile_probe_result()
    assert result["outcome"] == "v1-variant", (
        f"committed probe outcome {result['outcome']!r} no longer matches the "
        "wired v1-variant mechanism — reconcile wiring and evidence explicitly"
    )
    # The tri-state translation, asserted on the outbound request of the ONE
    # transport (complete_with_tools — the /v1 path the probe validated).
    for think, expect in ((True, "high"), (False, "none")):
        captured = {}
        backend = ExplorerBackend(
            gateway=_capturing_gateway(captured), repo_path=str(tmp_path),
            settings=Settings(), manifest=[], search_engine=_FakeSearch(),
            think=think,
        )
        backend.run("q", [])
        assert captured.get("reasoning_effort") == expect
        assert "think" not in captured
        assert "chat_template_kwargs" not in captured
    captured = {}
    backend = ExplorerBackend(
        gateway=_capturing_gateway(captured), repo_path=str(tmp_path),
        settings=Settings(), manifest=[], search_engine=_FakeSearch(),
    )
    backend.run("q", [])
    assert captured == {"max_tokens": 2048}  # None: the 0034 byte-identity floor holds


def test_explorer_think_pin_gated_on_native_probe_outcome(tmp_path):
    """Spec 0037 AC2 — tri-state pin CONDITIONAL on the probe's typed outcome.

    SUPERSEDED-BY-0038 (recorded, not auto-armed): this pin is keyed to the
    /v1 top-level `think` mechanism's machine-recorded `no-op` outcome, which
    never legitimately flips — Ollama's /v1 layer keeps dropping the field
    (re-confirmed live by the 0038 probe, arm probe_arm_v1_think_false.json),
    and the knob now routes through the probe-proven `reasoning_effort`
    mechanism instead (specs/0038-reconciliation/probes/probe_result.json,
    outcome=v1-variant). The successor pins are
    test_explorer_think_true_sends_reasoning_effort_high / _false_sends_
    reasoning_effort_none / test_explorer_think_wiring_matches_committed_probe_
    outcome (above). This test is KEPT, skipping forever with the archived
    recorded reason: the archived 0037 evidence and its drift pin are never
    edited (evidence-untouched supersede).

    Original 0037 rationale: loads the committed probes/probe_result.json
    (spec 0037). If the recorded outcome is not `native-think-effective`, this
    pin skips WITH the recorded outcome as the reason — the conditionality is
    machine-recorded, not assumed.
    """
    from pathlib import Path

    from harpyja.eval.think_probe import load_probe_result

    probe_path = (
        Path(__file__).resolve().parents[2]
        / "specs" / ".archive" / "0037-explorer-think-knob"
        / "probes" / "probe_result.json"
    )
    result = load_probe_result(probe_path)
    if result["outcome"] != "native-think-effective":
        pytest.skip(
            f"probe outcome is {result['outcome']!r} (not native-think-effective): "
            "AC2 pin conditional per spec 0037 — see findings.md (A/B blocked)"
        )
    for think, expect in ((True, True), (False, False)):
        captured = {}
        backend = ExplorerBackend(
            gateway=_capturing_gateway(captured), repo_path=str(tmp_path),
            settings=Settings(), manifest=[], search_engine=_FakeSearch(),
            think=think,
        )
        backend.run("q", [])
        assert captured.get("think") is expect
        assert "chat_template_kwargs" not in captured  # native arm, hedge dropped
    captured = {}
    backend = ExplorerBackend(
        gateway=_capturing_gateway(captured), repo_path=str(tmp_path),
        settings=Settings(), manifest=[], search_engine=_FakeSearch(),
    )
    backend.run("q", [])
    assert "think" not in captured  # None ⇒ omitted, byte-identical floor
