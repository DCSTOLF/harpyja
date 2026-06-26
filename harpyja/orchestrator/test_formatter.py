"""RED (task 32): citation formatter — dedupe/merge/rank/tiebreak/clamp (AC14, AC11)."""

from harpyja.orchestrator.format import format_citations
from harpyja.server.types import CodeSpan


def _spans(*triples):
    return [CodeSpan(path=p, start_line=s, end_line=e) for p, s, e in triples]


def _flat_prior(_path):
    return 1.0


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
