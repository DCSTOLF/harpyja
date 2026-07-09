"""RED (task 24/26): bounded literal ripgrep search → CodeSpans (AC8, AC9)."""

import json

import pytest

from harpyja.config.settings import Settings
from harpyja.server.types import CodeSpan
from harpyja.symbols.ripgrep import RipgrepEngine, RipgrepMissingError

_RG_PRESENT = lambda _name: "/usr/bin/rg"  # noqa: E731 - test stub


def _match_line(path, line):
    return json.dumps(
        {
            "type": "match",
            "data": {
                "path": {"text": path},
                "lines": {"text": "some matching line\n"},
                "line_number": line,
                "submatches": [{"match": {"text": "q"}, "start": 0, "end": 1}],
            },
        }
    )


def _runner_returning(*lines):
    captured = {}

    def runner(args):
        captured["args"] = args
        return "\n".join(lines) + "\n"

    return runner, captured


def test_search_returns_codespans_for_literal_match():
    runner, _ = _runner_returning(_match_line("a.py", 12))
    engine = RipgrepEngine(Settings(), rg_runner=runner, which=_RG_PRESENT)
    spans = engine.search("q", scope=".")
    assert spans == [CodeSpan(path="a.py", start_line=12, end_line=12)]


def test_search_treats_query_as_literal_by_default():
    runner, captured = _runner_returning(_match_line("a.py", 1))
    engine = RipgrepEngine(Settings(), rg_runner=runner, which=_RG_PRESENT)
    engine.search("a.b*c", scope=".")
    assert "--fixed-strings" in captured["args"]


def test_search_caps_at_search_max_matches():
    lines = [_match_line("a.py", n) for n in range(1, 6)]
    runner, _ = _runner_returning(*lines)
    settings = Settings(search_max_matches=2)
    engine = RipgrepEngine(settings, rg_runner=runner, which=_RG_PRESENT)
    assert len(engine.search("q", scope=".")) == 2


def test_search_caps_at_search_max_files():
    lines = [_match_line(f"f{n}.py", 1) for n in range(1, 5)]
    runner, _ = _runner_returning(*lines)
    settings = Settings(search_max_files=2)
    engine = RipgrepEngine(settings, rg_runner=runner, which=_RG_PRESENT)
    spans = engine.search("q", scope=".")
    assert len({s.path for s in spans}) <= 2


def test_search_passes_rg_chunk_size():
    runner, captured = _runner_returning(_match_line("a.py", 1))
    settings = Settings(rg_chunk_size=999)
    engine = RipgrepEngine(settings, rg_runner=runner, which=_RG_PRESENT)
    engine.search("q", scope=".")
    assert any("999" in str(a) for a in captured["args"])


def test_search_missing_rg_raises_typed_actionable_error():
    runner, _ = _runner_returning()
    engine = RipgrepEngine(Settings(), rg_runner=runner, which=lambda _n: None)
    with pytest.raises(RipgrepMissingError) as exc:
        engine.search("q", scope=".")
    assert "ripgrep" in str(exc.value).lower() or "rg" in str(exc.value).lower()


# --- Spec 0033: repo-relative scoped output (engine seam, mechanism b) ---

import shutil as _shutil  # noqa: E402


def test_repo_root_scope_paths_byte_identical_pin(tmp_path):
    """PIN (T1): absolute-repo-root scope WITHOUT repo_root= parses verbatim.

    The Tier-0/django shape — the legacy path the fix must not perturb.
    """
    runner, _ = _runner_returning(_match_line("django/db/models/query.py", 693))
    engine = RipgrepEngine(Settings(), rg_runner=runner, which=_RG_PRESENT)
    spans = engine.search("in_bulk", scope=str(tmp_path))
    assert spans == [CodeSpan(path="django/db/models/query.py", start_line=693, end_line=693)]


def test_tier0_repo_root_scope_legacy_path_unchanged(tmp_path):
    """PIN (T1): the exact Tier-0 call shape (scope=req.repo_path, no repo_root)."""
    runner, captured = _runner_returning(_match_line("a.py", 1))
    engine = RipgrepEngine(Settings(), rg_runner=runner, which=_RG_PRESENT)
    spans = engine.search("q", scope=str(tmp_path))
    assert spans == [CodeSpan(path="a.py", start_line=1, end_line=1)]
    # Legacy invocation shape: no path argument rides the rg args.
    assert captured["args"][-1] == "q"


def test_search_subdir_scope_returns_repo_relative_paths(tmp_path):
    """AC1: subdir scope + repo_root → repo-relative paths (the astropy shape)."""
    (tmp_path / "astropy").mkdir()
    runner, _ = _runner_returning(_match_line("modeling/core.py", 812))
    engine = RipgrepEngine(Settings(), rg_runner=runner, which=_RG_PRESENT)
    spans = engine.search(
        "separability", scope=str(tmp_path / "astropy"), repo_root=str(tmp_path)
    )
    assert spans == [CodeSpan(path="astropy/modeling/core.py", start_line=812, end_line=812)]


def test_search_subdir_scope_trailing_slash(tmp_path):
    """AC1: a trailing-slash scope yields the same repo-relative result."""
    (tmp_path / "astropy").mkdir()
    runner, _ = _runner_returning(_match_line("modeling/core.py", 812))
    engine = RipgrepEngine(Settings(), rg_runner=runner, which=_RG_PRESENT)
    spans = engine.search(
        "separability", scope=str(tmp_path / "astropy") + "/", repo_root=str(tmp_path)
    )
    assert spans == [CodeSpan(path="astropy/modeling/core.py", start_line=812, end_line=812)]


def test_search_nested_subdir_scope(tmp_path):
    """AC1: a nested scope prefixes with the full repo-relative chain."""
    (tmp_path / "astropy" / "modeling").mkdir(parents=True)
    runner, _ = _runner_returning(_match_line("core.py", 812))
    engine = RipgrepEngine(Settings(), rg_runner=runner, which=_RG_PRESENT)
    spans = engine.search(
        "separability", scope=str(tmp_path / "astropy" / "modeling"), repo_root=str(tmp_path)
    )
    assert spans == [CodeSpan(path="astropy/modeling/core.py", start_line=812, end_line=812)]


def test_search_strips_rg_dot_slash_prefix(tmp_path):
    """AC1: an rg './'-prefixed path normalizes cleanly (no 'astropy/./' artifact)."""
    (tmp_path / "astropy").mkdir()
    runner, _ = _runner_returning(_match_line("./modeling/core.py", 812))
    engine = RipgrepEngine(Settings(), rg_runner=runner, which=_RG_PRESENT)
    spans = engine.search(
        "separability", scope=str(tmp_path / "astropy"), repo_root=str(tmp_path)
    )
    assert spans == [CodeSpan(path="astropy/modeling/core.py", start_line=812, end_line=812)]


def test_search_repo_root_scope_with_repo_root_is_byte_identical(tmp_path):
    """AC1: scope == repo_root → '.' prefix collapses, paths unchanged."""
    runner, _ = _runner_returning(_match_line("django/db/models/query.py", 693))
    engine = RipgrepEngine(Settings(), rg_runner=runner, which=_RG_PRESENT)
    spans = engine.search("in_bulk", scope=str(tmp_path), repo_root=str(tmp_path))
    assert spans == [CodeSpan(path="django/db/models/query.py", start_line=693, end_line=693)]


def test_search_file_scope_returns_repo_relative_via_parent(tmp_path):
    """AC4 edge: a FILE scope runs from the parent dir with the filename as an rg
    path arg and prefixes by the parent (the symbols degraded-fallback shape —
    no NotADirectoryError)."""
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "b.py").write_text("needle\n", encoding="utf-8")
    runner, captured = _runner_returning(_match_line("b.py", 1))
    engine = RipgrepEngine(Settings(), rg_runner=runner, which=_RG_PRESENT)
    spans = engine.search(
        "needle", scope=str(tmp_path / "a" / "b.py"), repo_root=str(tmp_path)
    )
    assert spans == [CodeSpan(path="a/b.py", start_line=1, end_line=1)]
    # The filename rides the rg args as a path argument (parent dir is the cwd).
    assert captured["args"][-1] == "b.py"


@pytest.mark.integration
def test_search_real_rg_subdir_repo_relative(tmp_path):
    """AC1 (real rg): scoped search is repo-relative; repo-root scope is
    byte-identical to the legacy path (ordering + ignore-file resolution)."""
    if _shutil.which("rg") is None:
        pytest.skip("rg not on PATH")
    (tmp_path / "astropy" / "modeling").mkdir(parents=True)
    (tmp_path / "astropy" / "modeling" / "core.py").write_text("needle\n", encoding="utf-8")
    (tmp_path / "query.py").write_text("needle\n", encoding="utf-8")
    (tmp_path / "ignored.py").write_text("needle\n", encoding="utf-8")
    (tmp_path / ".ignore").write_text("ignored.py\n", encoding="utf-8")

    engine = RipgrepEngine(Settings())

    scoped = engine.search("needle", scope=str(tmp_path / "astropy"), repo_root=str(tmp_path))
    assert [s.path for s in scoped] == ["astropy/modeling/core.py"]

    legacy = engine.search("needle", scope=str(tmp_path))
    rooted = engine.search("needle", scope=str(tmp_path), repo_root=str(tmp_path))
    assert [s.path for s in legacy] == [s.path for s in rooted]  # ordering incl.
    assert "ignored.py" not in {s.path for s in rooted}  # ignore-file resolution
