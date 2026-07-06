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


# --- Spec 0025: FastContext-era suffix recovery (0012) REMOVED ---
#
# The explorer submits paths chosen from real tool output (grep/glob/read_span), so
# it never needed the 0012 path-prefix hack that repaired FastContext's hallucinated
# leading roots. The CONSERVATIVE migration removes ONLY the suffix-recovery
# (`_recover_suffix` / `MIN_TAIL_SEGMENTS`) and KEEPS the shared
# `normalize_spans_with_tally` / `ScoutTally` core — the live ScoutEngine shape-tally
# consumed by `runner`, `locate_probe`, and the 0022 locate-accuracy diagnostic. The
# recovered-count outputs become structurally zero; the tally is otherwise intact.


def _recoverable_repo(tmp_path):
    """A repo with real on-disk files; returns (repo_root, file_set frozenset)."""
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


def test_suffix_recovery_symbols_removed():
    # Executable absence guard: the 0012 suffix-recovery internals no longer resolve.
    import harpyja.scout.normalize as normalize

    assert not hasattr(normalize, "_recover_suffix")
    assert not hasattr(normalize, "MIN_TAIL_SEGMENTS")


def test_previously_recoverable_ref_now_drops(tmp_path):
    # The exact 0012 case that USED to recover (a hallucinated leading root onto a
    # real repo path) now honestly DROPS — recovery is gone, recovered counts zero.
    repo, fs = _recoverable_repo(tmp_path)
    raw = [CodeSpan(path="/pallets/flask/src/flask/blueprints.py", start_line=None, end_line=None)]
    out, dropped, rec_s, rec_f = _norm(raw, repo, file_set=fs)
    assert out == [] and (dropped, rec_s, rec_f) == (1, 0, 0)


def test_in_repo_ref_normalizes_with_zero_recovered(tmp_path):
    # The explorer's citation path — a REAL repo-relative path — still resolves
    # cleanly post-removal; recovered counts are structurally zero.
    repo, fs = _recoverable_repo(tmp_path)
    raw = [CodeSpan(path="src/flask/blueprints.py", start_line=3, end_line=8)]
    out, dropped, rec_s, rec_f = _norm(raw, repo, file_set=fs)
    assert [(c.path, c.start_line, c.end_line) for c in out] == [
        ("src/flask/blueprints.py", 3, 8)
    ]
    assert (dropped, rec_s, rec_f) == (0, 0, 0)


def test_recovered_counts_structurally_zero_even_with_file_set(tmp_path):
    # The tally core is KEPT, but recovery is inert: an out-of-repo ref drops and the
    # recovered_* counts never move, even when a file_set is supplied.
    repo, fs = _recoverable_repo(tmp_path)
    raw = [
        CodeSpan(path="/hallucinated/root/src/flask/__init__.py", start_line=None, end_line=None)
    ]
    out, dropped, rec_s, rec_f = _norm(raw, repo, file_set=fs)
    assert out == [] and (rec_s, rec_f) == (0, 0)


def test_recovered_bookkeeping_inert_across_mixed_batch(tmp_path):
    # T18 refactor guard: across a mixed in-repo batch (file-level + spanned) plus an
    # out-of-repo drop, the recovered_* counters stay 0 and recovered_paths_out empty —
    # the recovery bookkeeping is fully inert (no dead branch can move them).
    repo, fs = _recoverable_repo(tmp_path)
    raw = [
        CodeSpan(path="src/flask/__init__.py", start_line=None, end_line=None),  # file-level
        CodeSpan(path="src/flask/blueprints.py", start_line=1, end_line=3),       # spanned
        CodeSpan(path="/out/of/repo/x.py", start_line=None, end_line=None),        # drop
    ]
    paths: list[str] = []
    from harpyja.scout.normalize import normalize_spans_with_tally

    out, dropped, rec_s, rec_f = normalize_spans_with_tally(
        raw, str(repo), max_citations=8, max_span_lines=200, file_set=fs,
        recovered_paths_out=paths,
    )
    assert len(out) == 2 and dropped == 1
    assert (rec_s, rec_f) == (0, 0) and paths == []


def test_recovered_paths_out_retained_but_never_populated(tmp_path):
    # `recovered_paths_out` stays in the signature (schema/side-channel stability) but
    # is never populated now that recovery is removed.
    from harpyja.scout.normalize import normalize_spans_with_tally

    repo, fs = _recoverable_repo(tmp_path)
    raw = [CodeSpan(path="/pallets/flask/src/flask/blueprints.py", start_line=None, end_line=None)]
    paths: list[str] = []
    out, dropped, rec_s, rec_f = normalize_spans_with_tally(
        raw, str(repo), max_citations=8, max_span_lines=200, file_set=fs,
        recovered_paths_out=paths,
    )
    assert paths == [] and (rec_s, rec_f) == (0, 0)
