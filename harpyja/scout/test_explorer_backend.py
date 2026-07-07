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

    def search(self, pattern, scope=None):
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

    def search(self, pattern, scope=None):
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
