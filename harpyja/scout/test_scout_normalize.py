"""RED (task 7): normalize hostile/malformed Scout backend output (AC7).

The Scout backend's `<final_answer>` is untrusted: it can name files outside the
repo, nonexistent files, impossible line ranges, duplicates, or more spans than
the budget allows. `normalize_spans` clamps or drops each case rather than
propagating it.
"""

from harpyja.config.settings import Settings
from harpyja.scout.normalize import normalize_spans, normalize_spans_for_scout
from harpyja.server.types import CodeSpan


def _repo(tmp_path):
    (tmp_path / "pkg").mkdir()
    f = tmp_path / "pkg" / "mod.py"
    f.write_text("\n".join(f"line {i}" for i in range(1, 51)) + "\n", encoding="utf-8")
    return tmp_path


def test_normalize_drops_path_outside_repo_root(tmp_path):
    repo = _repo(tmp_path)
    raw = [CodeSpan(path="../../etc/passwd", start_line=1, end_line=1)]
    assert normalize_spans_for_scout(raw, str(repo), Settings()) == []


def test_normalize_drops_nonexistent_file(tmp_path):
    repo = _repo(tmp_path)
    raw = [CodeSpan(path="pkg/missing.py", start_line=1, end_line=1)]
    assert normalize_spans_for_scout(raw, str(repo), Settings()) == []


def test_normalize_drops_inverted_line_range(tmp_path):
    repo = _repo(tmp_path)
    raw = [CodeSpan(path="pkg/mod.py", start_line=10, end_line=3)]
    assert normalize_spans_for_scout(raw, str(repo), Settings()) == []


def test_normalize_drops_out_of_range_line(tmp_path):
    repo = _repo(tmp_path)
    # File has 50 lines; 999 is past EOF, 0 is below line 1.
    raw = [
        CodeSpan(path="pkg/mod.py", start_line=999, end_line=1000),
        CodeSpan(path="pkg/mod.py", start_line=0, end_line=2),
    ]
    assert normalize_spans_for_scout(raw, str(repo), Settings()) == []


def test_normalize_dedupes_duplicate_spans(tmp_path):
    repo = _repo(tmp_path)
    raw = [
        CodeSpan(path="pkg/mod.py", start_line=1, end_line=2),
        CodeSpan(path="pkg/mod.py", start_line=1, end_line=2),
    ]
    out = normalize_spans_for_scout(raw, str(repo), Settings())
    assert len(out) == 1


def test_normalize_clamps_over_max_citations(tmp_path):
    repo = _repo(tmp_path)
    settings = Settings(scout_max_citations=3)
    raw = [CodeSpan(path="pkg/mod.py", start_line=i, end_line=i) for i in range(1, 11)]
    out = normalize_spans_for_scout(raw, str(repo), settings)
    assert len(out) == 3


def test_normalize_clamps_span_over_max_lines(tmp_path):
    repo = _repo(tmp_path)
    settings = Settings(scout_max_span_lines=5)
    raw = [CodeSpan(path="pkg/mod.py", start_line=1, end_line=40)]
    out = normalize_spans_for_scout(raw, str(repo), settings)
    assert len(out) == 1
    assert out[0].start_line == 1
    assert out[0].end_line == 5  # clamped to first scout_max_span_lines lines


# --- Wave 4: generalized explicit-budget core (AC9) ---


def test_normalize_spans_honors_explicit_deep_budgets(tmp_path):
    repo = _repo(tmp_path)
    raw = [CodeSpan(path="pkg/mod.py", start_line=i, end_line=40) for i in range(1, 11)]
    # Explicit (Deep) budgets, distinct from the Scout defaults.
    out = normalize_spans(raw, str(repo), max_citations=3, max_span_lines=4)
    assert len(out) == 3  # clamped to max_citations
    assert out[0].start_line == 1
    assert out[0].end_line == 4  # clamped to first max_span_lines lines


# --- Spec 0011 (citation-shape): file-level (line-less) spans ---


def test_normalize_keeps_file_level_span_for_real_file(tmp_path):
    # AC6 (load-bearing survive-path): a file-level span (None lines) for a real
    # in-repo file survives repo-confine/is_file/dedup and is RETURNED with None
    # lines — not dropped, not given a fabricated range.
    repo = _repo(tmp_path)
    raw = [CodeSpan(path="pkg/mod.py", start_line=None, end_line=None)]
    out = normalize_spans_for_scout(raw, str(repo), Settings())
    assert [(c.path, c.start_line, c.end_line) for c in out] == [("pkg/mod.py", None, None)]
    assert out[0].is_file_level


def test_normalize_drops_file_level_span_for_missing_file(tmp_path):
    # AC9: a bare path that isn't a real file is dropped (honest-empty no-matches),
    # never a fabricated span and never a backend-error.
    repo = _repo(tmp_path)
    raw = [CodeSpan(path="pkg/ghost.py", start_line=None, end_line=None)]
    assert normalize_spans_for_scout(raw, str(repo), Settings()) == []


def test_normalize_dedupes_file_level_span(tmp_path):
    # File-level dedup keys on (path, None, None).
    repo = _repo(tmp_path)
    raw = [
        CodeSpan(path="pkg/mod.py", start_line=None, end_line=None),
        CodeSpan(path="pkg/mod.py", start_line=None, end_line=None),
    ]
    assert len(normalize_spans_for_scout(raw, str(repo), Settings())) == 1


def test_normalize_counts_dropped_refs(tmp_path, caplog):
    # AC10: dropped refs are counted (no silent coverage) and logged per drop.
    import logging

    repo = _repo(tmp_path)
    from harpyja.scout.normalize import normalize_spans_with_tally

    raw = [
        CodeSpan(path="pkg/mod.py", start_line=None, end_line=None),  # kept
        CodeSpan(path="pkg/ghost.py", start_line=None, end_line=None),  # dropped (missing)
        CodeSpan(path="../etc/passwd", start_line=1, end_line=1),  # dropped (out of repo)
    ]
    with caplog.at_level(logging.INFO):
        out, dropped = normalize_spans_with_tally(
            raw, str(repo), max_citations=8, max_span_lines=200
        )
    assert len(out) == 1
    assert dropped == 2
    assert sum("drop" in r.message.lower() for r in caplog.records) >= 2


def test_normalize_rejects_half_none_span(tmp_path):
    # AC23 (normalize boundary): a half-None span (start int, end None) is not a
    # sanctioned shape — dropped, never emitted.
    repo = _repo(tmp_path)
    from harpyja.scout.normalize import normalize_spans_with_tally

    raw = [CodeSpan(path="pkg/mod.py", start_line=10, end_line=None)]
    out, dropped = normalize_spans_with_tally(raw, str(repo), max_citations=8, max_span_lines=200)
    assert out == []
    assert dropped == 1


def test_normalize_lined_spans_unchanged_with_tally(tmp_path):
    # AC7: the lined path is byte-identical; the file-level branch is never reached
    # for int-lined (e.g. Deep-budget) spans.
    repo = _repo(tmp_path)
    from harpyja.scout.normalize import normalize_spans_with_tally

    raw = [CodeSpan(path="pkg/mod.py", start_line=1, end_line=40)]
    out, dropped = normalize_spans_with_tally(raw, str(repo), max_citations=3, max_span_lines=4)
    assert [(c.path, c.start_line, c.end_line) for c in out] == [("pkg/mod.py", 1, 4)]
    assert dropped == 0
