"""RED (0046 T3/T4, AC2): the reactive submission policy.

Two mechanism changes dissolve the 0043->0045 confidence-gate trade. This is
the FIRST: default to submitting the best span in hand, and keep exploring ONLY
on a NAMED DISCONFIRMING trigger. The three triggers are pre-registered,
gold-blind (they read tool results / source text, never the gold answer), and
mechanically fixturable:

- ``symbols-empty``     — a ``symbols`` call returned zero spans (or the
  honest-empty marker) — no structural support for a candidate here.
- ``hit-in-comment``    — the grep top-hit's matched line is a comment/docstring
  line (whole-line comment token, or a triple-quote docstring boundary), read
  host-side via an injected line reader (source text, not gold).
- ``tool-disagreement`` — the grep top-hit's file differs, after path
  normalization, from the file the ``symbols`` result owns.

Triggers are a SET: zero, one, or several may fire; all firing identifiers are
recorded. A run that keeps exploring WITHOUT a named trigger is a visible policy
violation (surfaced by ``should_keep_exploring`` returning False on no-trigger).
"""

from __future__ import annotations

import ast
import inspect

from harpyja.scout.reactive_policy import (
    REACTIVE_TRIGGERS,
    REACTIVE_TRIGGERS_ORDER,
    fired_triggers,
    should_keep_exploring,
)


def _tool_call(call_id, name):
    return {
        "role": "assistant",
        "tool_calls": [{"id": call_id, "function": {"name": name}}],
    }


def _tool_result(call_id, content):
    return {"role": "tool", "tool_call_id": call_id, "content": content}


def _traj(*turns):
    return {"model_turns": list(turns)}


def _symbols_content(*spans):
    # The trajectory stringifies tool results; confidence_signals._parse_tool_content
    # parses the `[CodeSpan(...), ...]` repr shape back.
    inner = ", ".join(
        f"CodeSpan(path={p!r}, start_line={s}, end_line={e})" for p, s, e in spans
    )
    return f"[{inner}]"


# --- symbols-empty ------------------------------------------------------------


def test_symbols_empty_trigger_fires_on_zero_span_result():
    traj = _traj(
        _tool_call("c1", "symbols"),
        _tool_result("c1", "[]"),
    )
    assert "symbols-empty" in fired_triggers(traj)


def test_symbols_empty_trigger_fires_on_marker_result():
    traj = _traj(
        _tool_call("c1", "symbols"),
        _tool_result("c1", "symbols-args-missing: pass path and/or name"),
    )
    assert "symbols-empty" in fired_triggers(traj)


def test_symbols_empty_does_not_fire_on_nonempty_symbols():
    traj = _traj(
        _tool_call("c1", "symbols"),
        _tool_result("c1", _symbols_content(("m.py", 10, 20))),
    )
    assert "symbols-empty" not in fired_triggers(traj)


# --- hit-in-comment (injected line reader = source text, never gold) ----------


def _reader(mapping):
    def read(path, line):
        return mapping.get((path, line))

    return read


def test_hit_in_comment_trigger_fires_on_whole_line_comment():
    traj = _traj(
        _tool_call("c1", "grep"),
        _tool_result("c1", _symbols_content(("m.py", 12, 12))),
    )
    reader = _reader({("m.py", 12): "    # TODO: the pattern lives here"})
    assert "hit-in-comment" in fired_triggers(traj, line_reader=reader)


def test_hit_in_comment_trigger_fires_on_docstring_boundary():
    traj = _traj(
        _tool_call("c1", "grep"),
        _tool_result("c1", _symbols_content(("m.py", 3, 3))),
    )
    reader = _reader({("m.py", 3): '    """the query term appears in this docstring."""'})
    assert "hit-in-comment" in fired_triggers(traj, line_reader=reader)


def test_hit_in_comment_does_not_fire_on_code_token():
    traj = _traj(
        _tool_call("c1", "grep"),
        _tool_result("c1", _symbols_content(("m.py", 20, 20))),
    )
    reader = _reader({("m.py", 20): "    result = compute(pattern)  # trailing"})
    assert "hit-in-comment" not in fired_triggers(traj, line_reader=reader)


def test_hit_in_comment_does_not_fire_without_a_reader():
    # No source-text reader available -> cannot confirm a comment -> do not fire
    # (honest: absence of evidence is not a disconfirming trigger).
    traj = _traj(
        _tool_call("c1", "grep"),
        _tool_result("c1", _symbols_content(("m.py", 12, 12))),
    )
    assert "hit-in-comment" not in fired_triggers(traj)


# --- tool-disagreement --------------------------------------------------------


def test_tool_disagreement_fires_on_divergent_owning_file():
    traj = _traj(
        _tool_call("c1", "grep"),
        _tool_result("c1", _symbols_content(("pkg/a.py", 10, 10))),
        _tool_call("c2", "symbols"),
        _tool_result("c2", _symbols_content(("pkg/b.py", 5, 40))),
    )
    assert "tool-disagreement" in fired_triggers(traj)


def test_tool_disagreement_does_not_fire_on_agreeing_files():
    traj = _traj(
        _tool_call("c1", "grep"),
        _tool_result("c1", _symbols_content(("pkg/a.py", 10, 10))),
        _tool_call("c2", "symbols"),
        _tool_result("c2", _symbols_content(("./pkg/a.py", 5, 40))),
    )
    assert "tool-disagreement" not in fired_triggers(traj)


# --- set semantics / default / gold-blindness ---------------------------------


def test_no_trigger_fires_defaults_to_submit_best_span():
    # A clean converged trajectory (grep + symbols agree on one implementation
    # span) fires nothing -> the policy default is submit-best.
    traj = _traj(
        _tool_call("c1", "grep"),
        _tool_result("c1", _symbols_content(("m.py", 10, 20))),
        _tool_call("c2", "symbols"),
        _tool_result("c2", _symbols_content(("m.py", 8, 40))),
    )
    reader = _reader({("m.py", 10): "    return separability_matrix(x)"})
    assert fired_triggers(traj, line_reader=reader) == []
    assert should_keep_exploring(traj, line_reader=reader) is False


def test_multi_trigger_records_both_identifiers_order_stable():
    # hit-in-comment AND tool-disagreement on one case -> both recorded, in the
    # stable declaration order (hit-in-comment precedes tool-disagreement).
    traj = _traj(
        _tool_call("c1", "grep"),
        _tool_result("c1", _symbols_content(("pkg/a.py", 12, 12))),
        _tool_call("c2", "symbols"),
        _tool_result("c2", _symbols_content(("pkg/b.py", 5, 40))),
    )
    reader = _reader({("pkg/a.py", 12): "# a whole-line comment hit"})
    fired = fired_triggers(traj, line_reader=reader)
    assert "hit-in-comment" in fired and "tool-disagreement" in fired
    # order-stable: matches iteration over the ordered trigger list
    assert fired == sorted(fired, key=list(REACTIVE_TRIGGERS_ORDER).index)


def test_should_keep_exploring_true_iff_any_trigger():
    traj = _traj(_tool_call("c1", "symbols"), _tool_result("c1", "[]"))
    assert should_keep_exploring(traj) is True


def test_reactive_triggers_is_the_closed_frozen_set():
    assert REACTIVE_TRIGGERS == frozenset(
        {"symbols-empty", "hit-in-comment", "tool-disagreement"}
    )


def test_reactive_policy_is_gold_blind_no_eval_import():
    import harpyja.scout.reactive_policy as rp

    tree = ast.parse(inspect.getsource(rp))
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        for name in names:
            assert not name.startswith("harpyja.eval"), (
                f"reactive_policy imports {name} — the policy must be gold-blind"
            )



# --- Spec 0046 (T8, AC3a): separable-modules guard ----------------------------
# Confirmation gates the OUTPUT, not the firing/exploration decision. The
# reactive policy must NOT reference the confirm interceptor (module OR symbols),
# so the 0045 collapse (corroboration throttling firing) is structurally
# impossible — the gate can never read the confirmation result.


def _module_ast(mod):
    import inspect

    return ast.parse(inspect.getsource(mod))


def _imported_modules(tree):
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            mods.add(node.module or "")
    return mods


def _referenced_names(tree):
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
    }


_CONFIRM_SYMBOLS = {
    "ConfirmationOutcome",
    "confirm_before_submit",
    "derive_submit_disposition",
    "confirmation_outcome",
    "confirmation_ran",
    "submit_disposition",
}


def test_reactive_policy_does_not_import_confirm_module():
    import harpyja.scout.reactive_policy as rp

    assert "harpyja.scout.confirm" not in _imported_modules(_module_ast(rp))


def test_reactive_policy_does_not_reference_confirmation_symbols():
    import harpyja.scout.reactive_policy as rp

    leaked = _referenced_names(_module_ast(rp)) & _CONFIRM_SYMBOLS
    assert leaked == set(), f"reactive_policy references confirmation symbols: {leaked}"
