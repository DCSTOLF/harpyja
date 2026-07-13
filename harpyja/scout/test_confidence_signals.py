"""RED (0045 T4, AC3): the one-definition move of the trajectory-only
confidence signals into scout/ (gold-blind).

The 0044 record-only observability predicates — grep-hit-inside-symbol
containment (b) and convergent evidence (c) — currently live eval-side. The
refined gate (T9) must CONSUME them, but the gate is gold-blind and cannot
import eval/. So the trajectory-only helpers MOVE to scout/confidence_signals.py
(pure, gold-blind, no eval import, no gold parameter); eval imports them BACK by
identity (T5). ``classify_confidence_null`` (needs gold) STAYS eval-side.

The gold-free span-overlap primitive ``spans_overlap_line`` moves with them; a
test pins that it AGREES with eval's ``metrics.span_hit_kind`` "line" grade on
tool-vs-tool spans — one overlap definition survives WITHOUT a scout->eval edge.
"""

from harpyja.scout.confidence_signals import (
    convergent_evidence,
    grep_hits_inside_symbol_spans,
    spans_overlap_line,
    tool_spans_in_order,
)
from harpyja.server.types import CodeSpan


def _span_repr(path, start, end):
    return (
        f"CodeSpan(path='{path}', start_line={start}, end_line={end}, "
        "symbol=None, language=None, kind=None)"
    )


def _turns(*pairs):
    """Build model_turns from (tool_name, call_id, content) triples."""
    turns = []
    for name, call_id, content in pairs:
        turns.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": call_id, "function": {"name": name, "arguments": "{}"}}
            ],
        })
        turns.append({"role": "tool", "tool_call_id": call_id, "content": content})
    return turns


def test_grep_hit_inside_symbol_span_detected():
    # A grep hit whose lines lie within an EARLIER symbols span (same file).
    traj = {"model_turns": _turns(
        ("symbols", "c1", f"[{_span_repr('m.py', 10, 40)}]"),
        ("grep", "c2", f"[{_span_repr('m.py', 15, 18)}]"),
    )}
    assert grep_hits_inside_symbol_spans(traj) == 1


def test_grep_hit_inside_symbol_span_absent_when_outside_or_before():
    # Outside the symbols span -> no containment.
    outside = {"model_turns": _turns(
        ("symbols", "c1", f"[{_span_repr('m.py', 10, 40)}]"),
        ("grep", "c2", f"[{_span_repr('m.py', 80, 90)}]"),
    )}
    assert grep_hits_inside_symbol_spans(outside) == 0
    # grep BEFORE symbols -> ordering rule: symbols must precede the grep hit.
    before = {"model_turns": _turns(
        ("grep", "c1", f"[{_span_repr('m.py', 15, 18)}]"),
        ("symbols", "c2", f"[{_span_repr('m.py', 10, 40)}]"),
    )}
    assert grep_hits_inside_symbol_spans(before) == 0


def test_convergent_evidence_two_tools_overlap_same_file():
    traj = {"model_turns": _turns(
        ("grep", "c1", f"[{_span_repr('m.py', 10, 20)}]"),
        ("read_span", "c2", f"[{_span_repr('m.py', 18, 30)}]"),
    )}
    assert convergent_evidence(traj) is True


def test_convergent_evidence_none_single_tool_or_no_overlap():
    single = {"model_turns": _turns(
        ("grep", "c1", f"[{_span_repr('m.py', 10, 20)}]"),
        ("grep", "c2", f"[{_span_repr('m.py', 12, 15)}]"),
    )}
    assert convergent_evidence(single) is False
    no_overlap = {"model_turns": _turns(
        ("grep", "c1", f"[{_span_repr('m.py', 10, 20)}]"),
        ("read_span", "c2", f"[{_span_repr('m.py', 80, 90)}]"),
    )}
    assert convergent_evidence(no_overlap) is False


def test_tool_spans_in_order_is_trajectory_only():
    traj = {"model_turns": _turns(
        ("symbols", "c1", f"[{_span_repr('m.py', 10, 40)}]"),
        ("grep", "c2", f"[{_span_repr('m.py', 15, 18)}]"),
    )}
    out = tool_spans_in_order(traj)
    names = [name for _pos, name, _span in out]
    assert names == ["symbols", "grep"]


def test_spans_overlap_line_agrees_with_eval_span_hit_kind_line_grade():
    # The gold-free primitive AGREES with eval's single oracle on tool-vs-tool
    # spans — one overlap definition, no scout->eval import.
    from harpyja.eval.metrics import span_hit_kind

    a = CodeSpan(path="m.py", start_line=10, end_line=20)
    b = CodeSpan(path="m.py", start_line=18, end_line=30)
    c = CodeSpan(path="m.py", start_line=80, end_line=90)
    d = CodeSpan(path="other.py", start_line=15, end_line=19)
    for x, y in ((a, b), (a, c), (a, d), (b, c)):
        assert spans_overlap_line(x, y) == (span_hit_kind(x, y) == "line")


def test_confidence_signals_is_gold_blind_no_eval_import():
    import ast
    import inspect

    import harpyja.scout.confidence_signals as sig

    src = inspect.getsource(sig)
    tree = ast.parse(src)
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        for name in names:
            assert not name.startswith("harpyja.eval"), (
                f"confidence_signals imports {name} — it must be gold-blind"
            )
    # No gold: no function takes an `expected`/`gold` parameter.
    for _n, fn in inspect.getmembers(sig, inspect.isfunction):
        params = set(inspect.signature(fn).parameters)
        assert "expected" not in params and "gold" not in params
