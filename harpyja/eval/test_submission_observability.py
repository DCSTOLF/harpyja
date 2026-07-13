"""RED (0044 T10, AC4): eval-side postflight observability + the attributable null.

The demoted confidence signals (b)/(c) are RECORD-ONLY fields computed
POSTFLIGHT over the persisted trajectory — never in the loop (the SUT delta
stays predicate + injection only) and never gating. The attributable-null
classification names why a fired/unfired nudge produced no correct submission:
never-fired / fired-but-ignored / fired-on-wrong-span — with the wrong-span
judgment routed through ``metrics.span_hit_kind`` BY IDENTITY (one-oracle-reuse,
never a second overlap definition).
"""

from harpyja.eval import metrics
from harpyja.eval import submission_observability as so
from harpyja.eval.submission_observability import (
    classify_confidence_null,
    convergent_evidence,
    grep_hits_inside_symbol_spans,
)
from harpyja.server.types import CodeSpan


def test_observability_containment_is_scout_function_by_identity():
    # Spec 0045: (b)/(c) moved to scout (gold-blind); eval re-exports BY IDENTITY
    # so ONE definition survives — no drift between the live gate and postflight.
    from harpyja.scout import confidence_signals as sig

    assert grep_hits_inside_symbol_spans is sig.grep_hits_inside_symbol_spans
    assert convergent_evidence is sig.convergent_evidence
    assert so.tool_spans_in_order is sig.tool_spans_in_order


def test_classify_confidence_null_stays_eval_side_uses_gold():
    # The gold-NEEDING classifier is NOT moved to scout — it takes `expected`.
    import inspect

    from harpyja.scout import confidence_signals as sig

    assert "expected" in inspect.signature(classify_confidence_null).parameters
    assert not hasattr(sig, "classify_confidence_null")


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
            "role": "assistant", "content": "",
            "tool_calls": [{"id": call_id, "function": {"name": name, "arguments": "{}"}}],
        })
        turns.append({"role": "tool", "tool_call_id": call_id, "content": content})
    return turns


def test_grep_hit_inside_symbol_span_detected():
    # (b): a grep span lying WITHIN a previously-returned symbols span (same
    # file, line-interval containment) — the exact pre-registered projection.
    turns = _turns(
        ("symbols", "s1", f"[{_span_repr('a.py', 10, 30)}]"),
        ("grep", "g1", f"[{_span_repr('a.py', 15, 15)}]"),
    )
    assert grep_hits_inside_symbol_spans({"model_turns": turns}) == 1


def test_grep_hit_outside_symbol_span_absent():
    turns = _turns(
        ("symbols", "s1", f"[{_span_repr('a.py', 10, 30)}]"),
        ("grep", "g1", f"[{_span_repr('a.py', 50, 50)}]"),  # outside the span
        ("grep", "g2", f"[{_span_repr('b.py', 15, 15)}]"),  # other file
    )
    assert grep_hits_inside_symbol_spans({"model_turns": turns}) == 0


def test_grep_hit_before_symbols_result_does_not_count():
    # "PREVIOUSLY-returned" is ordered: a grep hit that precedes the symbols
    # span is not contained-in-prior-evidence.
    turns = _turns(
        ("grep", "g1", f"[{_span_repr('a.py', 15, 15)}]"),
        ("symbols", "s1", f"[{_span_repr('a.py', 10, 30)}]"),
    )
    assert grep_hits_inside_symbol_spans({"model_turns": turns}) == 0


def test_convergent_evidence_two_tools_overlap_same_file():
    # (c): >=2 DISTINCT tools returned spans on one file whose line intervals
    # overlap (non-empty intersection).
    turns = _turns(
        ("symbols", "s1", f"[{_span_repr('a.py', 10, 30)}]"),
        ("grep", "g1", f"[{_span_repr('a.py', 25, 40)}]"),
    )
    assert convergent_evidence({"model_turns": turns}) is True


def test_convergent_evidence_none():
    # Same tool twice is not convergence; different files are not convergence;
    # non-overlapping intervals are not convergence.
    turns = _turns(
        ("grep", "g1", f"[{_span_repr('a.py', 10, 20)}]"),
        ("grep", "g2", f"[{_span_repr('a.py', 15, 25)}]"),  # same tool
        ("symbols", "s1", f"[{_span_repr('b.py', 10, 20)}]"),  # other file
        ("read_span", "r1", f"[{_span_repr('a.py', 100, 120)}]"),  # no overlap
    )
    assert convergent_evidence({"model_turns": turns}) is False


_GOLD = (CodeSpan(path="pkg/mod.py", start_line=10, end_line=20),)


def test_attributable_null_never_fired():
    traj = {"confidence_fired": False, "confidence_firing_spans": None,
            "terminal_bucket": "empty"}
    assert classify_confidence_null(traj, _GOLD) == "never-fired"


def test_attributable_null_fired_but_ignored():
    # Fired on a gold-hitting span, but the case still ended not-correct: the
    # model ignored the nudge (or submitted something else).
    traj = {
        "confidence_fired": True,
        "confidence_firing_spans": [
            {"path": "pkg/mod.py", "start_line": 10, "end_line": 20}
        ],
        "terminal_bucket": "empty",
    }
    assert classify_confidence_null(traj, _GOLD) == "fired-but-ignored"


def test_attributable_null_fired_on_wrong_span():
    # Fired, but the triggering spans do NOT line-hit gold — the gate passed on
    # the wrong evidence (the measured cost of the pre-registered looseness).
    traj = {
        "confidence_fired": True,
        "confidence_firing_spans": [
            {"path": "other.py", "start_line": 1, "end_line": 2}
        ],
        "terminal_bucket": "wrong-file",
    }
    assert classify_confidence_null(traj, _GOLD) == "fired-on-wrong-span"


def test_no_null_on_correct_case():
    # A correct case has no null to attribute — fired or not.
    fired = {
        "confidence_fired": True,
        "confidence_firing_spans": [
            {"path": "pkg/mod.py", "start_line": 10, "end_line": 20}
        ],
        "terminal_bucket": "correct",
    }
    unfired = {"confidence_fired": False, "confidence_firing_spans": None,
               "terminal_bucket": "correct"}
    assert classify_confidence_null(fired, _GOLD) is None
    assert classify_confidence_null(unfired, _GOLD) is None


def test_file_level_firing_span_is_not_a_gold_hit():
    # The one oracle's "line" grade is required — a path-only overlap ("file")
    # is NOT a gold hit for wrong-span purposes (the 0043 detector posture).
    traj = {
        "confidence_fired": True,
        "confidence_firing_spans": [
            {"path": "pkg/mod.py", "start_line": None, "end_line": None}
        ],
        "terminal_bucket": "empty",
    }
    assert classify_confidence_null(traj, _GOLD) == "fired-on-wrong-span"


def test_wrong_span_attribution_uses_span_hit_kind_by_identity():
    # One-oracle-reuse: the module binds metrics.span_hit_kind BY IDENTITY —
    # never a second overlap definition that could drift.
    assert so.span_hit_kind is metrics.span_hit_kind
