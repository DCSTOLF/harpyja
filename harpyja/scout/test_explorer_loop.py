"""RED (T11, AC4): the bounded explorer loop.

One structured tool call per turn; raw tool output appended to history; the loop
terminates at `scout_max_turns` (a non-terminating model is killed by the cap and
never hangs) OR at the `scout_wall_clock_s` whole-loop ceiling (so one slow/hung
turn cannot wedge it). A `submit_citations` call ends the loop with its spans.
The loop is driven here entirely by a fake model-call callable — no gateway, no
network.
"""

from harpyja.config.settings import Settings
from harpyja.scout.explorer_loop import (
    SUBMITTED,
    TURNS_EXHAUSTED,
    WALLCLOCK_EXHAUSTED,
    run_explorer_loop,
)
from harpyja.server.types import CodeSpan


def _tc(name, call_id="c", **args):
    import json

    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }


def _msg(*tool_calls, content=""):
    return {"content": content, "tool_calls": list(tool_calls)}


def _scripted(*responses):
    """A fake model-call: returns each response in turn, repeating the last."""
    seq = list(responses)

    def model_call(messages):
        return seq.pop(0) if len(seq) > 1 else seq[0]

    return model_call


def _recording_tools():
    calls = []

    def grep(pattern, scope=None):
        calls.append(("grep", pattern))
        return [CodeSpan(path="a.py", start_line=1, end_line=1)]

    tools = {"grep": grep, "glob": lambda pattern: [], "read_span": lambda path, start, end: {}}
    return tools, calls


def _submit_ok(citations):
    return [CodeSpan(path="a.py", start_line=1, end_line=1)]


def test_loop_terminates_on_submit_citations():
    tools, _ = _recording_tools()
    model = _scripted(_msg(_tc("submit_citations", citations=[{"path": "a.py"}])))
    result = run_explorer_loop(
        model_call=model, tools=tools, submit=_submit_ok,
        context_map="map", settings=Settings(),
    )
    assert result.outcome == SUBMITTED
    assert result.spans == [CodeSpan(path="a.py", start_line=1, end_line=1)]


def test_loop_executes_one_tool_call_per_turn_and_appends_output():
    tools, calls = _recording_tools()
    model = _scripted(
        _msg(_tc("grep", pattern="needle")),
        _msg(_tc("submit_citations", citations=[{"path": "a.py"}])),
    )
    result = run_explorer_loop(
        model_call=model, tools=tools, submit=_submit_ok,
        context_map="map", settings=Settings(),
    )
    assert result.outcome == SUBMITTED
    assert calls == [("grep", "needle")]  # exactly one navigation dispatch


def test_non_terminating_fake_killed_by_turn_cap():
    tools, calls = _recording_tools()
    model = _scripted(_msg(_tc("grep", pattern="loop")))  # never submits
    settings = Settings(scout_max_turns=4)
    result = run_explorer_loop(
        model_call=model, tools=tools, submit=_submit_ok,
        context_map="map", settings=settings,
    )
    assert result.outcome == TURNS_EXHAUSTED
    assert result.turns_used == 4  # capped, never hangs
    assert len(calls) == 4


def test_wall_clock_ceiling_terminates_when_turns_would_not():
    tools, calls = _recording_tools()
    model = _scripted(_msg(_tc("grep", pattern="slow")))  # never submits
    # A clock that jumps 100s per read: turns are plentiful (100) but the loop
    # ceiling (250s) trips first — a slow turn cannot wedge the loop.
    ticks = iter([0.0, 100.0, 200.0, 300.0, 400.0, 500.0, 600.0])
    settings = Settings(scout_max_turns=100, scout_wall_clock_s=250.0)
    result = run_explorer_loop(
        model_call=model, tools=tools, submit=_submit_ok,
        context_map="map", settings=settings, clock=lambda: next(ticks),
    )
    assert result.outcome == WALLCLOCK_EXHAUSTED
    assert result.turns_used < 100  # stopped by time, not by the turn cap


def test_unknown_tool_name_is_rejected_not_dispatched():
    tools, calls = _recording_tools()
    model = _scripted(
        _msg(_tc("delete", path="a.py")),  # not in the whitelist
        _msg(_tc("submit_citations", citations=[{"path": "a.py"}])),
    )
    result = run_explorer_loop(
        model_call=model, tools=tools, submit=_submit_ok,
        context_map="map", settings=Settings(),
    )
    # The unknown tool never runs a navigation dispatch; the loop recovers to submit.
    assert calls == []
    assert result.outcome == SUBMITTED


# --- Self-recovery: loop detection + citation-preserving truncation (T13, AC5) ---

_CORRECTIVE = "different"  # substring of the injected corrective note


def _rendered(history):
    return "\n".join(str(m.get("content", "")) for m in history)


def _submit_echo(citations):
    out = []
    for c in citations:
        out.append(
            CodeSpan(path=c["path"], start_line=c.get("start_line"), end_line=c.get("end_line"))
        )
    return out


def test_exact_repeat_no_new_span_triggers_corrective_injection():
    # A fixed-span tool + an identical repeated call = no new spans. After
    # scout_loop_repeat_n (=2) consecutive identical no-new-span turns, a corrective
    # note is injected.
    def grep(pattern, scope=None):
        return [CodeSpan(path="a.py", start_line=1, end_line=1)]  # always the same

    tools = {"grep": grep, "glob": lambda pattern: [], "read_span": lambda p, s, e: {}}
    model = _scripted(
        _msg(_tc("grep", pattern="same")),
        _msg(_tc("grep", pattern="same")),  # identical, no new span → trip detector
        _msg(_tc("submit_citations", citations=[{"path": "a.py"}])),
    )
    result = run_explorer_loop(
        model_call=model, tools=tools, submit=_submit_echo,
        context_map="map", settings=Settings(),
    )
    assert result.outcome == SUBMITTED
    assert any("unproductive" in str(m.get("content", "")).lower()
               or _CORRECTIVE in str(m.get("content", "")).lower()
               for m in result.history)


def test_distinct_args_do_not_trigger_loop_detection():
    def grep(pattern, scope=None):
        return [CodeSpan(path=f"{pattern}.py", start_line=1, end_line=1)]

    tools = {"grep": grep, "glob": lambda pattern: [], "read_span": lambda p, s, e: {}}
    model = _scripted(
        _msg(_tc("grep", pattern="alpha")),
        _msg(_tc("grep", pattern="beta")),  # different args + new span
        _msg(_tc("submit_citations", citations=[{"path": "alpha.py"}])),
    )
    result = run_explorer_loop(
        model_call=model, tools=tools, submit=_submit_echo,
        context_map="map", settings=Settings(),
    )
    assert not any("unproductive" in str(m.get("content", "")).lower()
                   for m in result.history)


def _bulky_grep_factory():
    """A grep returning a bulky, uniquely-marked observation per pattern."""
    def grep(pattern, scope=None):
        # 'pattern' doubles as the marker; the span location encodes it.
        blob = f"OBS[{pattern}]:" + ("x" * 200)
        return [CodeSpan(path=f"{pattern}.py", start_line=5, end_line=5, symbol=blob)]
    return grep


def test_history_past_char_cap_triggers_truncation():
    tools = {"grep": _bulky_grep_factory(), "glob": lambda p: [], "read_span": lambda p, s, e: {}}
    model = _scripted(
        _msg(_tc("grep", pattern="a")),
        _msg(_tc("grep", pattern="b")),
        _msg(_tc("grep", pattern="c")),
        _msg(_tc("grep", pattern="d")),
        _msg(_tc("submit_citations", citations=[{"path": "a.py"}])),
    )
    settings = Settings(scout_history_char_cap=400, scout_max_turns=10)
    result = run_explorer_loop(
        model_call=model, tools=tools, submit=_submit_echo,
        context_map="map", settings=settings,
    )
    # Truncation fired: a re-injected dropped-span index is present.
    assert any("observed locations" in str(m.get("content", "")).lower()
               for m in result.history)


def test_truncation_drops_only_stale_navigational_chatter():
    tools = {"grep": _bulky_grep_factory(), "glob": lambda p: [], "read_span": lambda p, s, e: {}}
    model = _scripted(
        _msg(_tc("grep", pattern="oldest")),
        _msg(_tc("grep", pattern="mid1")),
        _msg(_tc("grep", pattern="mid2")),
        _msg(_tc("grep", pattern="newest")),
        _msg(_tc("submit_citations", citations=[{"path": "oldest.py"}])),
    )
    settings = Settings(scout_history_char_cap=400, scout_max_turns=10)
    result = run_explorer_loop(
        model_call=model, tools=tools, submit=_submit_echo,
        context_map="map", settings=settings,
    )
    text = _rendered(result.history)
    # The oldest bulky observation's RAW blob is dropped; the newest is retained.
    assert "OBS[oldest]" not in text
    assert "OBS[newest]" in text


def test_truncation_preserves_citable_observation_dropped_span_index_reinjected():
    # THE correctness guard (prove the negative): a citation depends on an
    # observation OLDER than the bloat threshold. Truncation drops its bulky raw
    # blob but re-injects the location in a compact index — so the find is NOT lost
    # to honest-empty.
    tools = {"grep": _bulky_grep_factory(), "glob": lambda p: [], "read_span": lambda p, s, e: {}}
    model = _scripted(
        _msg(_tc("grep", pattern="old")),   # yields old.py:5 with a bulky blob
        _msg(_tc("grep", pattern="f1")),
        _msg(_tc("grep", pattern="f2")),
        _msg(_tc("grep", pattern="f3")),
        _msg(_tc("submit_citations",
                 citations=[{"path": "old.py", "start_line": 5, "end_line": 5}])),
    )
    settings = Settings(scout_history_char_cap=400, scout_max_turns=10)
    result = run_explorer_loop(
        model_call=model, tools=tools, submit=_submit_echo,
        context_map="map", settings=settings,
    )
    text = _rendered(result.history)
    # The bulky raw observation is gone...
    assert "OBS[old]" not in text
    # ...but its location survives in the re-injected dropped-span index.
    assert "old.py:5" in text
    # ...and the find resolves (never converted to honest-empty).
    assert CodeSpan(path="old.py", start_line=5, end_line=5) in result.spans


# --- spec 0027 (AC9): truncation still fires + citation-preserving with map ABSENT ---


def test_truncation_still_fires_past_cap_with_empty_context_map():
    # spec 0027: with the eager map removed (context_map=""), the citation-preserving
    # truncation MECHANISM is unchanged — only its onset shifts later (lighter baseline).
    tools = {"grep": _bulky_grep_factory(), "glob": lambda p: [], "read_span": lambda p, s, e: {}}
    model = _scripted(
        _msg(_tc("grep", pattern="a")),
        _msg(_tc("grep", pattern="b")),
        _msg(_tc("grep", pattern="c")),
        _msg(_tc("grep", pattern="d")),
        _msg(_tc("submit_citations", citations=[{"path": "a.py"}])),
    )
    settings = Settings(scout_history_char_cap=400, scout_max_turns=10)
    result = run_explorer_loop(
        model_call=model, tools=tools, submit=_submit_echo,
        context_map="", settings=settings,
    )
    assert any("observed locations" in str(m.get("content", "")).lower()
               for m in result.history)


def test_empty_map_truncation_preserves_older_citable_observation():
    # The 0024 correctness negative, re-proven with context_map="": a citation on an
    # observation OLDER than the bloat threshold STILL resolves after truncation runs.
    tools = {"grep": _bulky_grep_factory(), "glob": lambda p: [], "read_span": lambda p, s, e: {}}
    model = _scripted(
        _msg(_tc("grep", pattern="old")),
        _msg(_tc("grep", pattern="f1")),
        _msg(_tc("grep", pattern="f2")),
        _msg(_tc("grep", pattern="f3")),
        _msg(_tc("submit_citations",
                 citations=[{"path": "old.py", "start_line": 5, "end_line": 5}])),
    )
    settings = Settings(scout_history_char_cap=400, scout_max_turns=10)
    result = run_explorer_loop(
        model_call=model, tools=tools, submit=_submit_echo,
        context_map="", settings=settings,
    )
    text = _rendered(result.history)
    assert "OBS[old]" not in text          # bulky raw blob dropped
    assert "old.py:5" in text              # location survives in the re-injected index
    assert CodeSpan(path="old.py", start_line=5, end_line=5) in result.spans
