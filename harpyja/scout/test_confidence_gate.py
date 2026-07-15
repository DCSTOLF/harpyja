"""RED (0044 T1, AC1): the gold-blind confidence gate.

The gate is signal (a) SOLELY — a symbols-derived exact span — with the
qualifying projection frozen EXACTLY (spec 0044 §Confidence gate): a `symbols`
tool result qualifies iff it is CLEAN (no 0035 marker of either shape),
BOUNDED (1..CONFIDENCE_MAX_QUALIFYING_SPANS spans — an exact-definition lookup
is confidence, a multi-hundred-entry repo-wide substring batch is a candidate
list), and EXACT-SPAN-SHAPED (every span has non-None start/end lines).

Gold-blind by construction: the module lives in scout/, sees only a tool
result, and imports nothing from eval/ (asserted below) — gold exists only on
the eval side.
"""

from harpyja.scout.confidence_gate import (
    CONFIDENCE_MAX_QUALIFYING_SPANS,
    CONFIDENCE_NUDGE_TEMPLATE,
    CONFIDENCE_SIGNAL,
    build_confidence_nudge,
    qualifying_symbols_spans,
)
from harpyja.server.types import CodeSpan


def _span(path="a.py", start=10, end=20):
    return CodeSpan(path=path, start_line=start, end_line=end)


def test_qualifying_symbols_result_single_exact_span_fires():
    # A clean single-span symbols result IS the confidence signal.
    result = [_span()]
    assert qualifying_symbols_spans(result) == result


def test_qualifying_symbols_result_multi_exact_span_fires_and_names_all_spans():
    # A clean multi-span result (<= the bound) qualifies, and the built nudge
    # names ALL spans — the message must not imply a single certain target
    # (round-2 codex: no arbitrary first-span steering).
    spans = [_span("a.py", 1, 5), _span("b.py", 7, 9), _span("c.py", 30, 42)]
    assert qualifying_symbols_spans(spans) == spans
    nudge = build_confidence_nudge(spans)
    for s in spans:
        assert f"{s.path}:{s.start_line}-{s.end_line}" in nudge["content"]


def test_over_bound_repo_wide_batch_does_not_qualify():
    # A repo-wide name-lookup batch past the frozen bound is a CANDIDATE LIST,
    # not confidence — firing on it would reintroduce submit-before-verify
    # through the gate itself (up to scout_symbols_repo_max_entries=200).
    batch = [_span(f"f{i}.py", i + 1, i + 2) for i in range(CONFIDENCE_MAX_QUALIFYING_SPANS + 1)]
    assert qualifying_symbols_spans(batch) == []


def test_degraded_annotation_result_does_not_qualify():
    # The 0035/0042 ANNOTATION shape — a marker string riding ahead of real
    # spans — is a DEGRADED result and never qualifies (clean-only gate).
    result = ["symbols-degraded: 'x.py' (no parser; ripgrep def-scan)", _span()]
    assert qualifying_symbols_spans(result) == []


def test_replacement_marker_string_does_not_qualify():
    # The 0035 REPLACEMENT shape — a bare marker string IS the result.
    assert qualifying_symbols_spans("symbols-args-missing: pass path and/or name") == []


def test_non_exact_span_shape_does_not_qualify():
    # A file-level (line-less) span is not "exact" — the gate requires explicit
    # start/end lines on EVERY carried span (citation-shaped by construction).
    result = [_span(), CodeSpan(path="b.py", start_line=None, end_line=None)]
    assert qualifying_symbols_spans(result) == []


def test_zero_span_result_does_not_qualify():
    assert qualifying_symbols_spans([]) == []


def test_file_local_and_repo_wide_qualify_under_same_three_conditions():
    # The projection is call-shape-agnostic: a file-local result and a repo-wide
    # by-name result are both judged clean/bounded/exact — the span-count bound
    # is what excludes the repo-wide blast radius, not the call route.
    file_local = [_span("pkg/mod.py", 5, 40)]  # symbols(path=...)
    repo_wide = [_span("pkg/a.py", 1, 3), _span("pkg/b.py", 9, 12)]  # symbols(name=...)
    assert qualifying_symbols_spans(file_local) == file_local
    assert qualifying_symbols_spans(repo_wide) == repo_wide


def test_nudge_template_is_frozen_constant():
    # The nudge text is SUT surface exactly as the 0043 sentence was — the
    # message is built from the frozen template verbatim, role `user`
    # (the frozen-config drift pin lives in test_submission_config).
    spans = [_span()]
    nudge = build_confidence_nudge(spans)
    assert nudge["role"] == "user"
    assert nudge["content"] == CONFIDENCE_NUDGE_TEMPLATE.format(spans="a.py:10-20")
    assert "submit_citations" in nudge["content"]


def test_confidence_signal_label_is_frozen():
    # The triggering-signal label recorded in artifacts (AC3/AC4).
    assert CONFIDENCE_SIGNAL == "symbols-exact-span"


def test_gate_module_is_gold_blind_no_eval_import():
    # Structural gold-blindness: the SUT-side gate must not import eval code
    # (gold lives in eval/; the fired-on-wrong-span attribution is postflight).
    import ast
    import inspect

    import harpyja.scout.confidence_gate as gate

    tree = ast.parse(inspect.getsource(gate))
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        for name in names:
            assert not name.startswith("harpyja.eval"), (
                f"confidence_gate imports {name} — the gate must be gold-blind"
            )


# --- Spec 0046 (T1/T2, AC1): retire the 0045 require-corroboration LEVER -------
# 0045's require-corroboration-to-fire was measured TRADES_DIRECTIONS (firing
# collapsed 3/33, fu 1->8, net -1): it gated the ACTION when the evidence
# belonged in the OUTPUT path. The LEVER is already reverted in the loop (which
# wires `qualifying_symbols_spans`); this formally RETIRES the unwired refined-gate
# symbols with a recorded rationale, pinned by an import-absence guard (the
# deletion convention). The 0045 APPARATUS is retained and regression-pinned
# elsewhere (the four-sided predicate, s->wc counting, the gold-blind
# `confidence_signals`, the record-only unfired cross-check).


def test_qualifying_confidence_spans_public_name_absent():
    # The 0045 refined gate is retired: its public name no longer resolves.
    import harpyja.scout.confidence_gate as gate

    assert not hasattr(gate, "qualifying_confidence_spans")


def test_is_corroborated_private_symbol_absent():
    # The corroboration helper is gone with the lever it served.
    import harpyja.scout.confidence_gate as gate

    assert not hasattr(gate, "_is_corroborated")


def test_corroboration_retirement_rationale_recorded():
    # A retirement is a MEASURED REGRESSION, not a silent deletion: the reason
    # is preserved as a module-level constant.
    from harpyja.scout.confidence_gate import CORROBORATION_RETIRED_RATIONALE

    assert isinstance(CORROBORATION_RETIRED_RATIONALE, str)
    assert "regression" in CORROBORATION_RETIRED_RATIONALE.lower()
    assert "3/33" in CORROBORATION_RETIRED_RATIONALE  # firing collapse
    assert "1 -> 8" in CORROBORATION_RETIRED_RATIONALE  # found-but-unsubmitted 1 -> 8


def test_spans_overlap_line_retained_and_gold_blind():
    # The gold-blind overlap primitive is RETAINED in confidence_signals (the
    # reactive triggers / confirm interceptor may reuse it) — the apparatus
    # survives the lever's retirement.
    from harpyja.scout.confidence_signals import spans_overlap_line

    a = CodeSpan(path="m.py", start_line=10, end_line=40)
    b = CodeSpan(path="m.py", start_line=15, end_line=18)
    assert spans_overlap_line(a, b) is True


def test_qualifying_symbols_spans_is_the_live_firing_condition():
    # The 0044 firing condition is unchanged and remains the wired gate.
    span = _span("m.py", 10, 20)
    assert qualifying_symbols_spans([span]) == [span]


# --- Spec 0046 (T8, AC3a): the gate does not read the confirmation result -----
def test_confidence_gate_does_not_import_confirm_module():
    import ast
    import inspect

    import harpyja.scout.confidence_gate as gate

    tree = ast.parse(inspect.getsource(gate))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            mods.add(node.module or "")
    assert "harpyja.scout.confirm" not in mods


def test_confidence_gate_does_not_reference_confirmation_symbols():
    import ast
    import inspect

    import harpyja.scout.confidence_gate as gate

    tree = ast.parse(inspect.getsource(gate))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
    }
    leaked = names & {
        "ConfirmationOutcome",
        "confirm_before_submit",
        "derive_submit_disposition",
        "confirmation_outcome",
        "submit_disposition",
    }
    assert leaked == set(), f"confidence_gate references confirmation symbols: {leaked}"
