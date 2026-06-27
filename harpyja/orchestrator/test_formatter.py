"""RED (task 32): citation formatter — dedupe/merge/rank/tiebreak/clamp (AC14, AC11)."""

from harpyja.orchestrator.format import format_citations
from harpyja.server.types import CodeSpan


def _spans(*triples):
    return [CodeSpan(path=p, start_line=s, end_line=e) for p, s, e in triples]


def _flat_prior(_path):
    return 1.0


def test_format_citations_defaults_source_tier_zero():
    out = format_citations(_spans(("a.py", 1, 2)), _flat_prior, 8)
    assert out[0].source_tier == 0


def test_format_citations_threads_source_tier_one():
    out = format_citations(_spans(("a.py", 1, 2)), _flat_prior, 8, source_tier=1)
    assert all(c.source_tier == 1 for c in out)


def test_formatter_dedupes_identical_spans():
    out = format_citations(_spans(("a.py", 1, 2), ("a.py", 1, 2)), _flat_prior, 8)
    assert len(out) == 1
    assert (out[0].path, out[0].start_line, out[0].end_line) == ("a.py", 1, 2)


def test_formatter_merges_overlapping_same_file_spans():
    out = format_citations(_spans(("a.py", 1, 5), ("a.py", 3, 8)), _flat_prior, 8)
    assert len(out) == 1
    assert (out[0].start_line, out[0].end_line) == (1, 8)


def test_formatter_merges_adjacent_same_file_spans():
    out = format_citations(_spans(("a.py", 1, 2), ("a.py", 3, 4)), _flat_prior, 8)
    assert len(out) == 1
    assert (out[0].start_line, out[0].end_line) == (1, 4)


def test_formatter_does_not_merge_different_files():
    out = format_citations(_spans(("a.py", 1, 2), ("b.py", 1, 2)), _flat_prior, 8)
    assert len(out) == 2


def test_formatter_ranks_by_prior_then_match_density():
    priors = {"hi.py": 1.0, "lo.py": 0.1}
    out = format_citations(_spans(("lo.py", 1, 1), ("hi.py", 1, 1)), lambda p: priors[p], 8)
    assert out[0].path == "hi.py"  # higher prior ranks first


def test_formatter_stable_tiebreak_on_path_then_start_line():
    # Equal prior + density → deterministic order by (path, start_line).
    out = format_citations(_spans(("b.py", 5, 5), ("a.py", 9, 9), ("a.py", 1, 1)), _flat_prior, 8)
    keys = [(c.path, c.start_line) for c in out]
    assert keys == [("a.py", 1), ("a.py", 9), ("b.py", 5)]


def test_formatter_clamps_to_max_results():
    spans = _spans(*[(f"f{i}.py", 1, 1) for i in range(10)])
    out = format_citations(spans, _flat_prior, 3)
    assert len(out) == 3


# --- Wave 2: definition boost + widened tie-break (AC10, AC11, AC12) ---


def _def(path, start, end, name, kind="function"):
    return CodeSpan(path=path, start_line=start, end_line=end, symbol=name, kind=kind)


def test_formatter_ranks_definition_span_above_call_site():
    # Same file (same prior); call sites at 1,2 (merge, density 2) vs def at 10-11.
    spans = [CodeSpan("a.py", 1, 1), CodeSpan("a.py", 2, 2), _def("a.py", 10, 11, "foo")]
    out = format_citations(spans, _flat_prior, 8)
    assert out[0].symbol == "foo"  # definition promoted above the call-site cluster


def test_formatter_boost_layers_on_prior_and_density():
    priors = {"hi.py": 1.0, "lo.py": 0.1}
    spans = [_def("lo.py", 5, 5, "foo"), CodeSpan("hi.py", 1, 1)]
    out = format_citations(spans, lambda p: priors[p], 8)
    assert out[0].path == "hi.py"  # prior still dominates the boost


def test_formatter_without_definition_spans_identical_to_wave1():
    priors = {"a.py": 0.5, "b.py": 0.9}
    spans = [CodeSpan("a.py", 1, 1), CodeSpan("b.py", 3, 3)]
    out = format_citations(spans, lambda p: priors[p], 8)
    assert [c.path for c in out] == ["b.py", "a.py"]  # prior desc, exactly Wave-1
    assert all(c.symbol is None for c in out)


def test_formatter_tiebreak_total_order_deterministic_under_shuffle():
    spans = [_def("z.py", 1, 1, "a"), _def("a.py", 2, 2, "b"), _def("a.py", 5, 5, "c")]
    o1 = [(c.path, c.start_line) for c in format_citations(spans, _flat_prior, 8)]
    o2 = [(c.path, c.start_line) for c in format_citations(list(reversed(spans)), _flat_prior, 8)]
    assert o1 == o2 == [("a.py", 2), ("a.py", 5), ("z.py", 1)]


def test_formatter_same_symbol_in_multiple_files_orders_deterministically():
    spans = [_def("b.py", 1, 1, "foo"), _def("a.py", 1, 1, "foo")]
    out = format_citations(spans, _flat_prior, 8)
    assert [c.path for c in out] == ["a.py", "b.py"]


def test_formatter_preserves_symbol_and_kind_on_citation():
    out = format_citations([_def("a.py", 1, 2, "foo", kind="function")], _flat_prior, 8)
    assert out[0].symbol == "foo"
    assert out[0].kind == "function"
