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
        out, dropped, _rs, _rf = normalize_spans_with_tally(
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
    out, dropped, _rs, _rf = normalize_spans_with_tally(
        raw, str(repo), max_citations=8, max_span_lines=200
    )
    assert out == []
    assert dropped == 1


def test_normalize_lined_spans_unchanged_with_tally(tmp_path):
    # AC7: the lined path is byte-identical; the file-level branch is never reached
    # for int-lined (e.g. Deep-budget) spans.
    repo = _repo(tmp_path)
    from harpyja.scout.normalize import normalize_spans_with_tally

    raw = [CodeSpan(path="pkg/mod.py", start_line=1, end_line=40)]
    out, dropped, _rs, _rf = normalize_spans_with_tally(
        raw, str(repo), max_citations=3, max_span_lines=4
    )
    assert [(c.path, c.start_line, c.end_line) for c in out] == [("pkg/mod.py", 1, 4)]
    assert dropped == 0


# --- Spec 0012 (path-prefix): bounded suffix recovery ---


def _recoverable_repo(tmp_path):
    """A repo with real on-disk files; returns (repo_root, file_set frozenset).

    Recovery re-validates with `is_file`, so the file must exist on disk AND be
    listed in `file_set` (the strings the manifest would yield).
    """
    (tmp_path / "src" / "flask").mkdir(parents=True)
    bp = tmp_path / "src" / "flask" / "blueprints.py"
    bp.write_text("\n".join(f"line {i}" for i in range(1, 30)) + "\n", encoding="utf-8")
    (tmp_path / "src" / "flask" / "__init__.py").write_text("x = 1\n", encoding="utf-8")
    file_set = frozenset({"src/flask/blueprints.py", "src/flask/__init__.py"})
    return tmp_path, file_set


def _norm(raw, repo, *, file_set=None, max_citations=8, max_span_lines=200):
    from harpyja.scout.normalize import normalize_spans_with_tally

    return normalize_spans_with_tally(
        raw, str(repo), max_citations=max_citations, max_span_lines=max_span_lines,
        file_set=file_set,
    )


def test_recover_unique_suffix_keeps_filelevel(tmp_path):
    # AC1: an out-of-repo file-level cite whose tail uniquely matches a real,
    # top-level-anchored file recovers to the repo-relative path, stays file-level.
    repo, fs = _recoverable_repo(tmp_path)
    raw = [CodeSpan(path="/pallets/flask/src/flask/blueprints.py", start_line=None, end_line=None)]
    out, dropped, rec_s, rec_f = _norm(raw, repo, file_set=fs)
    assert [(c.path, c.start_line, c.end_line) for c in out] == [
        ("src/flask/blueprints.py", None, None)
    ]
    assert out[0].is_file_level
    assert (rec_f, rec_s, dropped) == (1, 0, 0)


def test_recover_unique_suffix_keeps_spanned_shape(tmp_path):
    # AC1: a recovered cite with a real line range stays spanned; bucket unchanged.
    repo, fs = _recoverable_repo(tmp_path)
    raw = [CodeSpan(path="/pallets/flask/src/flask/blueprints.py", start_line=3, end_line=8)]
    out, dropped, rec_s, rec_f = _norm(raw, repo, file_set=fs)
    assert [(c.path, c.start_line, c.end_line) for c in out] == [
        ("src/flask/blueprints.py", 3, 8)
    ]
    assert not out[0].is_file_level
    assert (rec_s, rec_f, dropped) == (1, 0, 0)


def test_recover_drops_when_no_unique_suffix(tmp_path):
    # AC2: suffix `src/__init__.py` is NOT a real flask file (real: src/flask/__init__.py)
    # — no recovery, honest drop.
    repo, fs = _recoverable_repo(tmp_path)
    raw = [CodeSpan(path="/pallets/flask/src/__init__.py", start_line=None, end_line=None)]
    out, dropped, rec_s, rec_f = _norm(raw, repo, file_set=fs)
    assert out == [] and (dropped, rec_s, rec_f) == (1, 0, 0)


def test_recover_skipped_when_file_set_absent(tmp_path):
    # AC2 degrade: no file set (index not ready) -> no recovery -> spec-0011 drop.
    repo, fs = _recoverable_repo(tmp_path)
    raw = [CodeSpan(path="/pallets/flask/src/flask/blueprints.py", start_line=None, end_line=None)]
    out, dropped, rec_s, rec_f = _norm(raw, repo, file_set=None)
    assert out == [] and (dropped, rec_f) == (1, 0)


def test_recover_skipped_when_file_set_empty(tmp_path):
    # AC2 degrade: empty file set -> no recovery -> spec-0011 drop.
    repo, fs = _recoverable_repo(tmp_path)
    raw = [CodeSpan(path="/pallets/flask/src/flask/blueprints.py", start_line=None, end_line=None)]
    out, dropped, rec_s, rec_f = _norm(raw, repo, file_set=frozenset())
    assert out == [] and (dropped, rec_f) == (1, 0)


def test_recover_interior_overlap_not_rewritten(tmp_path):
    # AC3a: only a trailing suffix matches; an interior segment overlap never rewrites.
    repo, fs = _recoverable_repo(tmp_path)
    raw = [CodeSpan(path="/x/flask/other.py", start_line=None, end_line=None)]
    out, dropped, rec_s, rec_f = _norm(raw, repo, file_set=fs)
    assert out == [] and (dropped, rec_f) == (1, 0)


def test_recover_ambiguous_suffix_dropped(tmp_path):
    # AC3b: a top-level-anchored tail (`pkg/util.py`) matching >1 file is dropped,
    # not silently picked, and does not fall back to a shorter tail.
    (tmp_path / "pkg").mkdir()
    (tmp_path / "other" / "pkg").mkdir(parents=True)
    (tmp_path / "pkg" / "util.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "other" / "pkg" / "util.py").write_text("x = 1\n", encoding="utf-8")
    fs = frozenset({"pkg/util.py", "other/pkg/util.py"})
    raw = [CodeSpan(path="/hall/pkg/util.py", start_line=None, end_line=None)]
    out, dropped, rec_s, rec_f = _norm(raw, tmp_path, file_set=fs)
    assert out == [] and (dropped, rec_f) == (1, 0)


def test_recover_below_min_tail_segments_dropped(tmp_path):
    # AC3c: a bare basename (1 segment < MIN_TAIL_SEGMENTS) never recovers.
    repo, fs = _recoverable_repo(tmp_path)
    raw = [CodeSpan(path="blueprints.py", start_line=None, end_line=None)]
    out, dropped, rec_s, rec_f = _norm(raw, repo, file_set=fs)
    assert out == [] and (dropped, rec_f) == (1, 0)


def test_recover_leading_segment_guard_dropped(tmp_path):
    # AC3d: the only match is via tail `flask/blueprints.py` whose head `flask` is
    # NOT a top-level manifest entry -> dropped; the `src`-anchored tail recovers.
    repo, fs = _recoverable_repo(tmp_path)  # top-level entries: {src}
    raw = [CodeSpan(path="/x/flask/blueprints.py", start_line=None, end_line=None)]
    out, dropped, rec_s, rec_f = _norm(raw, repo, file_set=fs)
    assert out == [] and dropped == 1

    raw2 = [CodeSpan(path="/x/src/flask/blueprints.py", start_line=None, end_line=None)]
    out2, d2, rs2, rf2 = _norm(raw2, repo, file_set=fs)
    assert [c.path for c in out2] == ["src/flask/blueprints.py"] and rf2 == 1


def test_recovered_span_revalidated_and_clamped(tmp_path):
    # AC3e: a recovered spanned cite is re-validated + clamped exactly like a
    # non-recovered span (recovery composes with, never bypasses, 0011 validation).
    repo, fs = _recoverable_repo(tmp_path)  # blueprints.py has 29 lines
    raw = [CodeSpan(path="/pallets/flask/src/flask/blueprints.py", start_line=1, end_line=999)]
    out, dropped, rec_s, rec_f = _norm(raw, repo, file_set=fs, max_span_lines=5)
    assert len(out) == 1
    assert (out[0].path, out[0].start_line, out[0].end_line) == ("src/flask/blueprints.py", 1, 5)
    assert rec_s == 1


def test_recovered_filelevel_keeps_none_lines(tmp_path):
    # AC3f: a recovered file-level span carries None lines (no fabricated range), so
    # it can never read as line-verified downstream.
    repo, fs = _recoverable_repo(tmp_path)
    raw = [CodeSpan(path="/pallets/flask/src/flask/blueprints.py", start_line=None, end_line=None)]
    out, dropped, rec_s, rec_f = _norm(raw, repo, file_set=fs)
    assert out[0].start_line is None and out[0].end_line is None and out[0].is_file_level


def test_recovered_filelevel_paths_collected_via_out_param(tmp_path):
    # AC5 support: an optional `recovered_paths_out` accumulator records the actual
    # recovered FILE-LEVEL paths (the un-gated set an operator must be able to
    # eyeball for wrong-but-unique recoveries) — without changing the return arity.
    from harpyja.scout.normalize import normalize_spans_with_tally

    repo, fs = _recoverable_repo(tmp_path)
    raw = [CodeSpan(path="/pallets/flask/src/flask/blueprints.py", start_line=None, end_line=None)]
    paths: list[str] = []
    out, dropped, rec_s, rec_f = normalize_spans_with_tally(
        raw, str(repo), max_citations=8, max_span_lines=200, file_set=fs,
        recovered_paths_out=paths,
    )
    assert paths == ["src/flask/blueprints.py"] and rec_f == 1
