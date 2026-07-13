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


# --- Spec 0045 (T8/T9, AC3): the REFINED require-corroboration ranking --------
# The 0044 gate fired on a bare bounded symbols span (a WEAK SINGLETON). The
# attribution (AC1) showed all 6 fired-on-wrong-span cells fired on exactly that
# uncorroborated shape, while the never-fired cell's gold sat inside an
# over-bound symbols batch the gate rejected outright. The refined rule
# (stage-1-selected: require-corroboration) DEMOTES the weak singleton and
# CREDITS convergence / grep-inside-symbol containment as the firing routes.

from harpyja.scout.confidence_gate import qualifying_confidence_spans  # noqa: E402


def test_weak_singleton_symbols_span_no_longer_fires():
    # Direction (a): a clean bounded exact symbols span with NO prior
    # corroboration must NOT fire (it fired under 0044).
    result = [_span("m.py", 10, 20)]
    assert qualifying_confidence_spans(result, prior_spans=[]) == []
    # Same-tool repetition is not corroboration.
    prior_same_tool = [("symbols", _span("m.py", 10, 20))]
    assert qualifying_confidence_spans(result, prior_spans=prior_same_tool) == []


def test_convergence_corroborated_symbols_span_fires():
    # Direction (b), convergence route: a symbols span line-overlapping an
    # earlier DIFFERENT-tool span is corroborated → fires on the overlap.
    result = [_span("m.py", 10, 40)]
    prior = [("grep", _span("m.py", 15, 18))]
    fired = qualifying_confidence_spans(result, prior_spans=prior)
    assert fired == [_span("m.py", 10, 40)]


def test_over_bound_batch_with_one_corroborated_span_fires_on_that_span():
    # The 0044 never-fired shape: an over-bound symbols batch (>5) that the 0044
    # gate rejected wholesale — but ONE span is corroborated by a prior grep hit
    # (containment) → the refined gate fires on the corroborated span only.
    batch = [_span(f"f{i}.py", i + 1, i + 3) for i in range(CONFIDENCE_MAX_QUALIFYING_SPANS + 2)]
    batch.append(_span("hit.py", 100, 140))
    prior = [("grep", _span("hit.py", 110, 112))]
    fired = qualifying_confidence_spans(batch, prior_spans=prior)
    assert fired == [_span("hit.py", 100, 140)]


def test_degraded_or_markered_result_never_fires_even_if_corroborated():
    # A marker in the list (ANNOTATION/degraded) disqualifies — clean-only.
    result = ["symbols-degraded: 'x.py'", _span("m.py", 10, 40)]
    prior = [("grep", _span("m.py", 15, 18))]
    assert qualifying_confidence_spans(result, prior_spans=prior) == []


def test_corroborated_candidates_still_bounded():
    # Corroboration cannot smuggle a candidate LIST back in: if more than the
    # bound of candidates are corroborated, it's a candidate list, not
    # confidence → no fire.
    n = CONFIDENCE_MAX_QUALIFYING_SPANS + 1
    result = [_span(f"m{i}.py", 10, 40) for i in range(n)]
    prior = [("grep", _span(f"m{i}.py", 15, 18)) for i in range(n)]
    assert qualifying_confidence_spans(result, prior_spans=prior) == []


def test_refined_gate_stays_gold_blind_no_eval_import():
    # The refined gate consumes scout.confidence_signals (scout->scout), never
    # eval — the ast pin still holds after the refinement.
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
            assert not name.startswith("harpyja.eval")


def test_refined_ranking_matches_stage1_selected_rule():
    # The implemented rule IS the stage-1-selected row (require-corroboration):
    # demotes weak-singleton, credits convergence + containment.
    from harpyja.eval.refinement_attribution import select_refined_rule

    row = select_refined_rule()
    assert row.rule_key == "require-corroboration"
    assert "weak-singleton" in row.demotes
    assert set(row.credits) == {
        "convergent-evidence",
        "grep-hit-inside-symbol-containment",
    }


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
