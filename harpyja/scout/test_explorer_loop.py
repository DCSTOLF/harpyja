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
    GENERATION_TRUNCATED,
    SUBMITTED,
    TURNS_EXHAUSTED,
    WALLCLOCK_EXHAUSTED,
    run_explorer_loop,
)
from harpyja.scout.submit import SubmitResult
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
    spans = [CodeSpan(path="a.py", start_line=1, end_line=1)]
    return SubmitResult(spans=spans, submitted=len(citations), surviving=len(spans))


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
    return SubmitResult(spans=out, submitted=len(citations), surviving=len(out))


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


def test_finish_length_yields_generation_truncated_outcome():
    # spec 0028 AC3: a capped generation that ends finish=length with no valid call
    # is a truncation, NOT an empty turn — a distinct terminal outcome.
    tools, _ = _recording_tools()
    model = _scripted({"content": "", "tool_calls": [], "finish_reason": "length"})
    result = run_explorer_loop(
        model_call=model, tools=tools, submit=_submit_ok,
        context_map="map", settings=Settings(),
    )
    assert result.outcome == GENERATION_TRUNCATED
    assert result.spans is None


def test_finish_length_truncates_even_with_valid_tool_call():
    # spec 0028 AC3 (edge case decided): finish=length NEVER takes the success path
    # even if a syntactically valid submit_citations rode along — a length-truncated
    # response was cut off mid-generation and its args may be silently incomplete.
    tools, _ = _recording_tools()
    model = _scripted({
        "content": "",
        "tool_calls": [_tc("submit_citations", citations=[{"path": "a.py"}])],
        "finish_reason": "length",
    })
    result = run_explorer_loop(
        model_call=model, tools=tools, submit=_submit_ok,
        context_map="map", settings=Settings(),
    )
    assert result.outcome == GENERATION_TRUNCATED
    assert result.spans is None


# --- spec 0029 (loop: parallel tool_call handling) ---

def test_parallel_echo_both_calls_answered():
    """T1.1: Two parallel echo calls must BOTH be answered (not just [0])."""
    tools, calls = _recording_tools()
    model = _scripted(
        _msg(
            _tc("grep", call_id="c0", pattern="alpha"),
            _tc("grep", call_id="c1", pattern="beta"),
        ),
        _msg(_tc("submit_citations", citations=[{"path": "a.py"}])),
    )
    result = run_explorer_loop(
        model_call=model, tools=tools, submit=_submit_ok,
        context_map="map", settings=Settings(),
    )
    # Both parallel calls should dispatch, not just [0].
    assert result.outcome == SUBMITTED
    assert len(calls) == 2, f"Expected 2 tool dispatches, got {len(calls)}: {calls}"
    assert calls[0] == ("grep", "alpha")
    assert calls[1] == ("grep", "beta")


def test_parallel_terminal_in_batch_submit_at_position():
    """T1.2: Terminal submit_citations at position [1] in a batch returns immediately."""
    tools, calls = _recording_tools()
    model = _scripted(
        _msg(
            _tc("grep", call_id="c0", pattern="alpha"),
            _tc("submit_citations", call_id="c1", citations=[{"path": "result.py"}]),
        ),
    )
    result = run_explorer_loop(
        model_call=model, tools=tools, submit=_submit_ok,
        context_map="map", settings=Settings(),
    )
    # submit_citations at [1] should return immediately; call [0] may or may not dispatch.
    assert result.outcome == SUBMITTED
    # The key: we do NOT see a turn 2. If calls were [0] only, then call [1] would be
    # invisible and the loop would continue (fail the test).
    assert result.turns_used == 1, "Submit terminal should stop at turn 1"


def test_parallel_bounds_all_calls_answered_not_just_first():
    """T1.3: All N calls in a batch are answered, verifying we iterate, not just [0]."""
    tools, calls = _recording_tools()
    model = _scripted(
        _msg(
            _tc("grep", call_id="c0", pattern="q0"),
            _tc("grep", call_id="c1", pattern="q1"),
            _tc("grep", call_id="c2", pattern="q2"),
            _tc("grep", call_id="c3", pattern="q3"),
        ),
        _msg(_tc("submit_citations", citations=[{"path": "a.py"}])),
    )
    result = run_explorer_loop(
        model_call=model, tools=tools, submit=_submit_ok,
        context_map="map", settings=Settings(),
    )
    assert result.outcome == SUBMITTED
    assert len(calls) == 4, f"Expected 4 tool dispatches, got {len(calls)}"


def test_parallel_turn2_reach_multiple_calls_on_turn2():
    """T1.4: Parallel calls on turn 2 (after a turn 1 tool) are all answered."""
    tools, calls = _recording_tools()
    model = _scripted(
        _msg(_tc("grep", call_id="t1c0", pattern="turn1")),
        _msg(
            _tc("grep", call_id="t2c0", pattern="turn2a"),
            _tc("grep", call_id="t2c1", pattern="turn2b"),
        ),
        _msg(_tc("submit_citations", citations=[{"path": "a.py"}])),
    )
    result = run_explorer_loop(
        model_call=model, tools=tools, submit=_submit_ok,
        context_map="map", settings=Settings(),
    )
    assert result.outcome == SUBMITTED
    # All three grep calls should fire: one on turn 1, two on turn 2.
    assert len(calls) == 3, f"Expected 3 tool dispatches, got {len(calls)}"
    assert calls == [("grep", "turn1"), ("grep", "turn2a"), ("grep", "turn2b")]


def test_parallel_mixed_tools_multiple_types_in_batch():
    """T1.5: Parallel calls with mixed tool types (grep, glob) all execute."""
    def glob(pattern):
        return [CodeSpan(path="globbed.py", start_line=1, end_line=1)]

    tools = {
        "grep": lambda pattern, scope=None: [CodeSpan(path="grepped.py", start_line=1, end_line=1)],
        "glob": glob,
        "read_span": lambda p, s, e: {},
    }
    calls = []

    def grep_track(pattern, scope=None):
        calls.append(("grep", pattern))
        return [CodeSpan(path="grepped.py", start_line=1, end_line=1)]

    def glob_track(pattern):
        calls.append(("glob", pattern))
        return [CodeSpan(path="globbed.py", start_line=1, end_line=1)]

    tools["grep"] = grep_track
    tools["glob"] = glob_track

    model = _scripted(
        _msg(
            _tc("grep", call_id="c0", pattern="findme"),
            _tc("glob", call_id="c1", pattern="*.py"),
        ),
        _msg(_tc("submit_citations", citations=[{"path": "a.py"}])),
    )
    result = run_explorer_loop(
        model_call=model, tools=tools, submit=_submit_ok,
        context_map="map", settings=Settings(),
    )
    assert result.outcome == SUBMITTED
    assert len(calls) == 2, f"Expected 2 tool dispatches, got {len(calls)}"
    assert calls[0] == ("grep", "findme")
    assert calls[1] == ("glob", "*.py")


def test_parallel_order_preservation_calls_answered_in_order():
    """T1.6: Parallel calls are answered in positional order, IDs preserved in history."""
    tools, calls = _recording_tools()
    model = _scripted(
        _msg(
            _tc("grep", call_id="id_first", pattern="a"),
            _tc("grep", call_id="id_second", pattern="b"),
            _tc("grep", call_id="id_third", pattern="c"),
        ),
        _msg(_tc("submit_citations", citations=[{"path": "a.py"}])),
    )
    result = run_explorer_loop(
        model_call=model, tools=tools, submit=_submit_ok,
        context_map="map", settings=Settings(),
    )
    assert result.outcome == SUBMITTED
    # Verify calls executed in order.
    assert calls == [("grep", "a"), ("grep", "b"), ("grep", "c")]
    # Verify history preserves the tool_call_ids in order.
    tool_messages = [m for m in result.history if m.get("role") == "tool"]
    assert len(tool_messages) == 3, f"Expected 3 tool messages, got {len(tool_messages)}"
    assert tool_messages[0]["tool_call_id"] == "id_first"
    assert tool_messages[1]["tool_call_id"] == "id_second"
    assert tool_messages[2]["tool_call_id"] == "id_third"


# --- T3: Per-call error handling (spec 0029, AC2) ---

def test_parallel_per_call_error_failed_tool_execution():
    """T3.1: Tool execution failure on one call does NOT stop batch; batch continues."""
    call_log = []

    def failing_grep(pattern, scope=None):
        call_log.append(("grep", pattern))
        raise ValueError("Simulated grep failure")

    def working_glob(pattern):
        call_log.append(("glob", pattern))
        return [CodeSpan(path="globbed.py", start_line=1, end_line=1)]

    tools = {
        "grep": failing_grep,
        "glob": working_glob,
        "read_span": lambda p, s, e: {},
    }
    model = _scripted(
        _msg(
            _tc("grep", call_id="c0", pattern="fail"),
            _tc("glob", call_id="c1", pattern="*.py"),
        ),
        _msg(_tc("submit_citations", citations=[{"path": "a.py"}])),
    )
    result = run_explorer_loop(
        model_call=model, tools=tools, submit=_submit_ok,
        context_map="map", settings=Settings(),
    )
    assert result.outcome == SUBMITTED
    # Both tools should have been called despite the first failing.
    assert len(call_log) == 2, f"Expected 2 calls despite failure, got {len(call_log)}: {call_log}"
    assert call_log[0] == ("grep", "fail")
    assert call_log[1] == ("glob", "*.py")


def test_parallel_per_call_error_degraded_marker_recorded():
    """T3.2: Tool execution failure records a degraded marker in history."""
    def failing_grep(pattern, scope=None):
        raise RuntimeError("grep crashed")

    tools = {"grep": failing_grep, "glob": lambda p: [], "read_span": lambda p, s, e: {}}
    model = _scripted(
        _msg(
            _tc("grep", call_id="c0", pattern="crash"),
            _tc("submit_citations", citations=[{"path": "a.py"}]),
        ),
    )
    result = run_explorer_loop(
        model_call=model, tools=tools, submit=_submit_ok,
        context_map="map", settings=Settings(),
    )
    assert result.outcome == SUBMITTED
    # History should contain a tool response capturing the error.
    tool_messages = [m for m in result.history if m.get("role") == "tool"]
    assert len(tool_messages) >= 1
    # The response should mention the error or have a degraded note.
    assert any("error" in m.get("content", "").lower() or "crash" in m.get("content", "").lower()
               for m in tool_messages)


def test_parallel_terminal_after_failed_tool():
    """T3.3: submit_citations after a failed tool call in the same batch succeeds."""
    def failing_grep(pattern, scope=None):
        raise RuntimeError("grep crashed")

    tools = {"grep": failing_grep, "glob": lambda p: [], "read_span": lambda p, s, e: {}}
    model = _scripted(
        _msg(
            _tc("grep", call_id="c0", pattern="crash"),
            _tc("submit_citations", call_id="c1", citations=[{"path": "result.py"}]),
        ),
    )
    result = run_explorer_loop(
        model_call=model, tools=tools, submit=_submit_echo,
        context_map="map", settings=Settings(),
    )
    # Terminal should succeed even though a prior call failed.
    assert result.outcome == SUBMITTED
    assert result.spans == [CodeSpan(path="result.py", start_line=None, end_line=None)]


# --- T5: Determinism test ---

def test_parallel_determinism_n4_astropy_shape_identical_trace():
    """T5: N=4 parallel calls executed twice yield identical trace (determinism)."""
    tools, _ = _recording_tools()

    # Simulates an astropy-like shape: 4 parallel navigational calls in one turn,
    # then immediate submit on turn 2.
    responses_1 = [
        _msg(
            _tc("grep", call_id="c0", pattern="search1"),
            _tc("grep", call_id="c1", pattern="search2"),
            _tc("glob", call_id="c2", pattern="*.py"),
            _tc("grep", call_id="c3", pattern="search3"),
        ),
        _msg(_tc("submit_citations", citations=[{"path": "found.py"}])),
    ]

    model_1 = _scripted(*responses_1)
    result_1 = run_explorer_loop(
        model_call=model_1, tools=tools, submit=_submit_echo,
        context_map="map", settings=Settings(),
    )
    trace_1 = _rendered(result_1.history)

    # Run it again with identical model responses.
    tools_2, _ = _recording_tools()
    responses_2 = [
        _msg(
            _tc("grep", call_id="c0", pattern="search1"),
            _tc("grep", call_id="c1", pattern="search2"),
            _tc("glob", call_id="c2", pattern="*.py"),
            _tc("grep", call_id="c3", pattern="search3"),
        ),
        _msg(_tc("submit_citations", citations=[{"path": "found.py"}])),
    ]

    model_2 = _scripted(*responses_2)
    result_2 = run_explorer_loop(
        model_call=model_2, tools=tools_2, submit=_submit_echo,
        context_map="map", settings=Settings(),
    )
    trace_2 = _rendered(result_2.history)

    # Identical traces confirm determinism.
    assert trace_1 == trace_2, f"Traces diverged:\n{trace_1}\n---vs---\n{trace_2}"
    assert result_1.turns_used == result_2.turns_used
    assert result_1.outcome == result_2.outcome == SUBMITTED


# --- Spec 0033: LoopResult carries the submit-seam counts (AC5) ---


def test_loop_result_carries_submitted_and_surviving_counts(tmp_path):
    """AC5: a found-then-dropped submission threads (1, 0) onto LoopResult."""
    def submit(citations):
        return SubmitResult(spans=[], submitted=1, surviving=0)

    model = _scripted(
        {"content": "", "tool_calls": [_tc("submit_citations",
         citations=[{"path": "modeling/core.py", "start_line": 812, "end_line": 812}])]}
    )
    result = run_explorer_loop(
        model_call=model, tools={}, submit=submit, context_map="", settings=Settings()
    )
    assert result.outcome == SUBMITTED
    assert result.spans == []
    assert result.citations_submitted == 1
    assert result.citations_surviving == 0


def test_loop_honest_empty_counts_zero_zero(tmp_path):
    """AC5: an honest-empty submission threads (0, 0) — distinguishable from
    found-then-dropped."""
    def submit(citations):
        return SubmitResult(spans=[], submitted=0, surviving=0)

    model = _scripted(
        {"content": "", "tool_calls": [_tc("submit_citations", citations=[])]}
    )
    result = run_explorer_loop(
        model_call=model, tools={}, submit=submit, context_map="", settings=Settings()
    )
    assert result.outcome == SUBMITTED
    assert (result.citations_submitted, result.citations_surviving) == (0, 0)


# --- Spec 0035: scope-marker visibility through the loop (zero loop changes) ---


def _marker_grep_tools(calls):
    def grep(pattern, scope=None):
        calls.append((pattern, scope))
        return f"grep-scope-not-found: {scope!r}"

    return {"grep": grep}


def test_grep_scope_marker_visible_and_non_terminal(tmp_path):
    """AC2: the marker string reaches the model-visible history verbatim and the
    loop CONTINUES to a terminal submit — non-terminal by construction."""
    calls = []
    model = _scripted(
        _msg(_tc("grep", pattern="x", scope="repo")),
        _msg(_tc("submit_citations", citations=[])),
    )
    result = run_explorer_loop(
        model_call=model, tools=_marker_grep_tools(calls),
        submit=_submit_ok, context_map="", settings=Settings(),
    )
    assert result.outcome == SUBMITTED
    assert any("grep-scope-not-found: 'repo'" in str(m.get("content", ""))
               for m in result.history)


def test_repeated_bad_scope_trips_loop_detection(tmp_path):
    """AC2: note_navigation still runs on a marker return — repeated identical
    bad-scope calls trip the corrective note (the property the 0029 exception
    route would silently defeat)."""
    calls = []
    model = _scripted(
        _msg(_tc("grep", pattern="x", scope="repo")),
        _msg(_tc("grep", pattern="x", scope="repo")),
        _msg(_tc("submit_citations", citations=[])),
    )
    result = run_explorer_loop(
        model_call=model, tools=_marker_grep_tools(calls),
        submit=_submit_ok, context_map="",
        settings=Settings(scout_loop_repeat_n=2),
    )
    assert result.outcome == SUBMITTED
    corrective = [m for m in result.history
                  if "unproductive" in str(m.get("content", ""))]
    assert corrective  # loop detection armed and fired


def test_grep_scope_marker_not_flagged_execution_error(tmp_path):
    """AC2: the marker is NOT routed through the 0029 execution-error degrade —
    no 'tool-call-degraded:execution-error:' prefix anywhere in the history."""
    calls = []
    model = _scripted(
        _msg(_tc("grep", pattern="x", scope="repo")),
        _msg(_tc("submit_citations", citations=[])),
    )
    result = run_explorer_loop(
        model_call=model, tools=_marker_grep_tools(calls),
        submit=_submit_ok, context_map="", settings=Settings(),
    )
    assert not any("tool-call-degraded:execution-error" in str(m.get("content", ""))
                   for m in result.history)


# --- Spec 0042 (AC2): symbols list-shape results register in span accounting ---
#
# The 0/28-era nested dict {"symbols": [...], "degraded": bool} yielded ZERO
# spans from _spans_of (a Mapping with no top-level "path" key), so a repeated
# symbols call read as an unproductive repeat and its locations never entered
# seen-span accounting — the tool was structurally PENALIZED for being called.
# The bare-list shape rides the existing list branch: CodeSpans count, the
# degraded ANNOTATION marker string (no .path) is skipped but stays
# model-visible via stringification.


def _symbols_tools(result):
    def symbols(path):
        return result

    return {"symbols": symbols}


def test_spans_of_counts_symbols_codespans_into_seen_accounting():
    """A [marker, CodeSpan] symbols result yields its CodeSpan into new-span
    accounting: an identical second call that ADDS a new span is NOT a repeat,
    so no corrective note fires (the property the nested dict defeated)."""
    span_a = CodeSpan(path="pkg/mod.py", start_line=3, end_line=9)
    span_b = CodeSpan(path="pkg/other.py", start_line=1, end_line=4)
    results = iter([
        ["symbols-degraded: 'pkg/mod.py'", span_a],
        ["symbols-degraded: 'pkg/mod.py'", span_b],  # same call, NEW span
    ])

    def symbols(path):
        return next(results)

    model = _scripted(
        _msg(_tc("symbols", path="pkg/mod.py")),
        _msg(_tc("symbols", path="pkg/mod.py")),
        _msg(_tc("submit_citations", citations=[])),
    )
    result = run_explorer_loop(
        model_call=model, tools={"symbols": symbols}, submit=_submit_ok,
        context_map="", settings=Settings(scout_loop_repeat_n=2),
    )
    assert result.outcome == SUBMITTED
    # New spans on the repeat call → NOT an unproductive repeat → no corrective.
    assert not any("unproductive" in str(m.get("content", "")) for m in result.history)


def test_spans_of_ignores_symbols_marker_string():
    """Only CodeSpan entries count as spans: a symbols result that is ALL marker
    (empty degraded fallback) yields no new span, so an exact repeat trips loop
    detection — the marker element never pollutes span accounting."""
    model = _scripted(
        _msg(_tc("symbols", path="broken.py")),
        _msg(_tc("symbols", path="broken.py")),
        _msg(_tc("submit_citations", citations=[])),
    )
    result = run_explorer_loop(
        model_call=model,
        tools=_symbols_tools(["symbols-degraded: 'broken.py'"]),
        submit=_submit_ok, context_map="",
        settings=Settings(scout_loop_repeat_n=2),
    )
    assert result.outcome == SUBMITTED
    assert any("unproductive" in str(m.get("content", "")) for m in result.history)


def test_symbols_degraded_marker_stays_model_visible():
    """0030's never-a-silent-downgrade contract survives the shape change: the
    ANNOTATION marker reaches the model-visible history verbatim (stringified
    alongside its spans), and is never routed through the execution-error degrade."""
    model = _scripted(
        _msg(_tc("symbols", path="broken.py")),
        _msg(_tc("submit_citations", citations=[])),
    )
    result = run_explorer_loop(
        model_call=model,
        tools=_symbols_tools(
            ["symbols-degraded: 'broken.py'", CodeSpan(path="broken.py", start_line=5, end_line=5)]
        ),
        submit=_submit_ok, context_map="", settings=Settings(),
    )
    assert result.outcome == SUBMITTED
    assert any("symbols-degraded: 'broken.py'" in str(m.get("content", ""))
               for m in result.history)
    assert not any("tool-call-degraded:execution-error" in str(m.get("content", ""))
                   for m in result.history)
