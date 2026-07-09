"""RED (T3, AC2): the three read-only navigation tools of the explorer loop.

The model driving the loop is an untrusted caller (same posture as the Deep-tier
RLM host tools). Exactly three navigation tools — `grep` / `glob` / `read_span` —
each repo-path-confined, output-bounded from the existing `Settings`, and
read-only. `grep` wraps the SAME `RipgrepEngine` the Deep `search` host tool
wraps (spec invariant B — one bounded ripgrep source of truth), never a second rg
surface. `glob` returns file-level `CodeSpan` records, not raw path strings.
"""

import pytest

from harpyja.config.settings import Settings
from harpyja.index.manifest import ManifestEntry
from harpyja.scout.explorer_tools import build_explorer_tools
from harpyja.server.tools import PathConfinementError
from harpyja.server.types import CodeSpan
from harpyja.symbols.extract import SymbolRecord


class _FakeSearch:
    """Stands in for RipgrepEngine (no `rg` needed) — records its calls."""

    def __init__(self, spans):
        self.spans = spans
        self.calls = []

    def search(self, pattern, scope=None, *, repo_root=None):
        self.calls.append((pattern, scope))
        return list(self.spans)


def _file(tmp_path, rel, n=50):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(f"line {i}" for i in range(1, n + 1)) + "\n", encoding="utf-8")
    return p


def _tools(tmp_path, *, settings=None, search=None, symbol_records=None, manifest=None):
    settings = settings or Settings()
    return build_explorer_tools(
        str(tmp_path),
        settings,
        search_engine=search or _FakeSearch([]),
        symbol_records=symbol_records or [],
        manifest=manifest or [],
    )


def test_build_explorer_tools_returns_exactly_five_navigation_tools(tmp_path):
    tools = _tools(tmp_path)
    # spec 0030: EXACTLY five navigation tools — `symbols` added as the file-local
    # symbol index tool (spec 0027 added `ls` → 4; spec 0030 adds `symbols` → 5).
    # This is a DELIBERATE, reconciled tool-suite change. No terminal submit action.
    assert set(tools) == {"grep", "glob", "read_span", "ls", "symbols"}
    assert "submit_citations" not in tools


def test_explorer_tools_surface_is_read_only(tmp_path):
    tools = _tools(tmp_path)
    assert not (set(tools) & {"write", "edit", "delete", "create", "open", "exec"})


def test_grep_wraps_shared_ripgrep_engine(tmp_path):
    # `grep` delegates to the injected engine (the same one Deep's `search` wraps),
    # not a second/independent rg surface.
    fake = _FakeSearch([CodeSpan(path="a.py", start_line=3, end_line=3)])
    tools = _tools(tmp_path, search=fake)
    out = tools["grep"]("needle")
    assert fake.calls  # the injected engine was actually called
    assert out[0].path == "a.py"


def test_grep_clamps_to_search_max_matches(tmp_path):
    spans = [CodeSpan(path=f"f{i}.py", start_line=1, end_line=1) for i in range(10)]
    tools = _tools(tmp_path, settings=Settings(search_max_matches=3), search=_FakeSearch(spans))
    out = tools["grep"]("x")
    assert len(out) == 3  # defensive clamp on untrusted-loop output


def test_grep_scope_outside_repo_rejected(tmp_path):
    tools = _tools(tmp_path)
    with pytest.raises(PathConfinementError):
        tools["grep"]("x", scope="../../etc")


def test_glob_normalizes_paths_to_file_level_codespans(tmp_path):
    _file(tmp_path, "pkg/a.py")
    _file(tmp_path, "pkg/b.py")
    tools = _tools(tmp_path)
    out = tools["glob"]("pkg/*.py")
    assert out and all(isinstance(s, CodeSpan) for s in out)
    # File-level: a path record, no fabricated line range.
    assert all(s.is_file_level for s in out)
    assert {s.path for s in out} == {"pkg/a.py", "pkg/b.py"}


def test_glob_clamps_to_scout_glob_max_paths(tmp_path):
    for i in range(10):
        _file(tmp_path, f"pkg/f{i}.py")
    tools = _tools(tmp_path, settings=Settings(scout_glob_max_paths=4))
    out = tools["glob"]("pkg/*.py")
    assert len(out) == 4


def test_glob_pattern_escaping_repo_yields_no_out_of_repo_paths(tmp_path):
    _file(tmp_path, "inside.py")
    tools = _tools(tmp_path)
    # A traversal pattern must never surface a path outside the repo root.
    out = tools["glob"]("../*.py")
    assert out == []


def test_read_span_reuses_read_snippet_and_bounds_lines(tmp_path):
    _file(tmp_path, "a.py", n=50)
    tools = _tools(tmp_path, settings=Settings(tool_max_lines=5))
    snippet = tools["read_span"]("a.py", 1, 50)
    assert snippet["truncated"] is True
    assert snippet["end"] == 5  # clamped by tool_max_lines


def test_read_span_path_outside_repo_rejected(tmp_path):
    _file(tmp_path, "a.py")
    tools = _tools(tmp_path)
    with pytest.raises(PathConfinementError):
        tools["read_span"]("../../etc/passwd", 1, 1)


# --- spec 0027: the `ls`/tree tool (single-dir, read-only, confined, clamped) ------


def test_ls_lists_a_single_directory_only(tmp_path):
    # ls returns the IMMEDIATE children of one directory (files AND dirs, so layout is
    # discoverable — the affordance glob lacks); it does NOT recurse (Decision 1).
    _file(tmp_path, "pkg/a.py")
    _file(tmp_path, "pkg/sub/b.py")
    tools = _tools(tmp_path)
    names = {s.path for s in tools["ls"]("pkg")}
    assert "pkg/a.py" in names          # immediate file
    assert "pkg/sub/" in names          # immediate dir, marked with a trailing slash
    assert "pkg/sub/b.py" not in names  # NOT recursed into


def test_ls_default_lists_repo_root(tmp_path):
    _file(tmp_path, "top.py")
    _file(tmp_path, "pkg/a.py")
    tools = _tools(tmp_path)
    names = {s.path for s in tools["ls"]()}  # default path="." → repo root
    assert "top.py" in names and "pkg/" in names


def test_ls_returns_file_level_codespans(tmp_path):
    _file(tmp_path, "pkg/a.py")
    tools = _tools(tmp_path)
    out = tools["ls"]("pkg")
    assert out and all(isinstance(s, CodeSpan) and s.is_file_level for s in out)


def test_ls_path_outside_repo_rejected(tmp_path):
    tools = _tools(tmp_path)
    with pytest.raises(PathConfinementError):
        tools["ls"]("../../etc")


def test_ls_clamps_to_scout_ls_max_entries(tmp_path):
    for i in range(10):
        _file(tmp_path, f"many/f{i}.py")
    tools = _tools(tmp_path, settings=Settings(scout_ls_max_entries=3))
    out = tools["ls"]("many")
    assert len(out) == 3  # defensive clamp on untrusted-loop output


# --- Spec 0030: symbols tool (AC1) —


def test_symbols_tool_wraps_tier0_records_python(tmp_path):
    # AC1: symbols tool wraps Tier-0 records, returns CodeSpans with kind+span
    # for Python fixtures (the ≥2-of-9 languages requirement).
    records = [
        SymbolRecord(
            path="app.py",
            language="python",
            name="MyClass",
            kind="class",
            parent=None,
            start_line=1,
            end_line=10,
        ),
        SymbolRecord(
            path="app.py",
            language="python",
            name="my_func",
            kind="function",
            parent=None,
            start_line=12,
            end_line=20,
        ),
    ]
    tools = _tools(tmp_path, symbol_records=records)
    out = tools["symbols"]("app.py")
    assert out["degraded"] is False
    assert len(out["symbols"]) == 2
    assert out["symbols"][0].symbol == "MyClass"
    assert out["symbols"][0].kind == "class"
    assert out["symbols"][0].start_line == 1
    assert out["symbols"][0].end_line == 10
    assert out["symbols"][1].symbol == "my_func"
    assert out["symbols"][1].kind == "function"


def test_symbols_tool_wraps_tier0_records_go(tmp_path):
    # AC1: same over Go (≥2-of-9 languages).
    records = [
        SymbolRecord(
            path="main.go",
            language="go",
            name="SomeType",
            kind="type",
            parent=None,
            start_line=5,
            end_line=15,
        ),
    ]
    tools = _tools(tmp_path, symbol_records=records)
    out = tools["symbols"]("main.go")
    assert out["degraded"] is False
    assert len(out["symbols"]) == 1
    assert out["symbols"][0].symbol == "SomeType"
    assert out["symbols"][0].kind == "type"


def test_symbols_tool_normalized_path(tmp_path):
    # AC1: path normalized (resolved) before lookup. `pkg/../pkg/file.py` →
    # same records as `pkg/file.py`.
    records = [
        SymbolRecord(
            path="pkg/file.py",
            language="python",
            name="func",
            kind="function",
            parent=None,
            start_line=1,
            end_line=5,
        ),
    ]
    tools = _tools(tmp_path, symbol_records=records)
    # Both paths should resolve to the same canonical form.
    out1 = tools["symbols"]("pkg/file.py")
    out2 = tools["symbols"]("pkg/../pkg/file.py")
    assert len(out1["symbols"]) == 1
    assert len(out2["symbols"]) == 1
    assert out1["symbols"][0].symbol == out2["symbols"][0].symbol


def test_symbols_tool_no_new_parser(tmp_path):
    # AC1: tool reads only the injected records (no tree-sitter/parse call).
    # Asserted by passing records for a path whose file does not exist on disk
    # and still getting them back (proves it filters rows, not re-parses).
    records = [
        SymbolRecord(
            path="nonexistent.py",
            language="python",
            name="phantom",
            kind="function",
            parent=None,
            start_line=1,
            end_line=5,
        ),
    ]
    tools = _tools(tmp_path, symbol_records=records)
    out = tools["symbols"]("nonexistent.py")
    assert len(out["symbols"]) == 1
    assert out["symbols"][0].symbol == "phantom"


def test_symbols_tool_out_of_repo_path_rejected(tmp_path):
    # AC2: repo-confinement enforced after path resolution. A resolved path
    # escaping the repo root (e.g., `pkg/../../etc/passwd`) raises PathConfinementError.
    tools = _tools(tmp_path)
    with pytest.raises(PathConfinementError):
        tools["symbols"]("../../etc/passwd")


def test_symbols_tool_clamps_to_scout_symbols_max_entries(tmp_path):
    # AC2: output clamped per scout_symbols_max_entries. A symbol list larger
    # than the clamp is truncated.
    records = [
        SymbolRecord(
            path="big.py",
            language="python",
            name=f"func{i}",
            kind="function",
            parent=None,
            start_line=i,
            end_line=i + 1,
        )
        for i in range(10)
    ]
    tools = _tools(tmp_path, settings=Settings(scout_symbols_max_entries=3), symbol_records=records)
    out = tools["symbols"]("big.py")
    assert len(out["symbols"]) == 3  # defensive clamp on untrusted-loop output


# --- Spec 0030: graceful degradation with visible provenance (AC3) —


def test_symbols_tool_degraded_file_falls_back_to_ripgrep(tmp_path):
    # AC3: a file marked as degraded (failed parsing at index build) falls back
    # to ripgrep (Tier-0's existing fallback) for that file.
    _file(tmp_path, "broken.py")
    ripgrep_results = [
        CodeSpan(path="broken.py", start_line=5, end_line=5),
        CodeSpan(path="broken.py", start_line=10, end_line=10),
    ]
    fake_search = _FakeSearch(ripgrep_results)
    manifest = [
        ManifestEntry(
            path="broken.py",
            language="python",
            size=100,
            hash="abc123",
            mtime=0.0,
            prior=0.0,
            degraded="PARSE_ERROR",
        )
    ]
    tools = _tools(tmp_path, search=fake_search, manifest=manifest)
    out = tools["symbols"]("broken.py")
    # Should return the ripgrep results (not zero records for a degraded file).
    assert isinstance(out, dict)
    assert len(out["symbols"]) == 2
    assert out["symbols"][0].start_line == 5


def test_symbols_tool_degraded_file_marks_output_degraded(tmp_path):
    # AC3: when returning degraded results, the tool surfaces a visible
    # `degraded: true` marker in the output (not a silent swap).
    ripgrep_results = [CodeSpan(path="broken.py", start_line=1, end_line=1)]
    fake_search = _FakeSearch(ripgrep_results)
    manifest = [
        ManifestEntry(
            path="broken.py",
            language="python",
            size=100,
            hash="abc123",
            mtime=0.0,
            prior=0.0,
            degraded="PARSE_ERROR",
        )
    ]
    tools = _tools(tmp_path, search=fake_search, manifest=manifest)
    out = tools["symbols"]("broken.py")
    # The tool returns a dict with symbols + degraded marker.
    assert isinstance(out, dict)
    assert "symbols" in out
    assert "degraded" in out
    assert out["degraded"] is True
    assert len(out["symbols"]) == 1


def test_symbols_tool_clean_file_not_marked_degraded(tmp_path):
    # AC3: a clean file (no manifest degraded flag) carries `degraded: false`.
    records = [
        SymbolRecord(
            path="clean.py",
            language="python",
            name="func",
            kind="function",
            parent=None,
            start_line=1,
            end_line=5,
        )
    ]
    manifest = [
        ManifestEntry(
            path="clean.py",
            language="python",
            size=100,
            hash="abc123",
            mtime=0.0,
            prior=0.0,
            degraded=None,  # clean
        )
    ]
    tools = _tools(tmp_path, symbol_records=records, manifest=manifest)
    out = tools["symbols"]("clean.py")
    # Clean file should be a dict with degraded=False.
    assert isinstance(out, dict)
    assert "degraded" in out
    assert out["degraded"] is False
    assert len(out["symbols"]) == 1


def test_symbols_tool_degraded_never_raises(tmp_path):
    # AC3: degraded files return a normal tool result, never an exception
    # (untrusted-caller boundary).
    fake_search = _FakeSearch([])
    manifest = [
        ManifestEntry(
            path="broken.py",
            language="python",
            size=100,
            hash="abc123",
            mtime=0.0,
            prior=0.0,
            degraded="PARSE_ERROR",
        )
    ]
    tools = _tools(tmp_path, search=fake_search, manifest=manifest)
    # Should not raise, should return a dict with empty symbols list.
    out = tools["symbols"]("broken.py")
    assert isinstance(out, dict)
    assert out["degraded"] is True
    assert out["symbols"] == []


# --- Spec 0033: repo-relative tool contract (AC2/AC3/AC4) ---

from harpyja.symbols.ripgrep import RipgrepEngine  # noqa: E402
from harpyja.symbols.test_ripgrep import _match_line, _runner_returning  # noqa: E402

_RG_PRESENT = lambda _name: "/usr/bin/rg"  # noqa: E731 - test stub


def _real_engine(runner):
    return RipgrepEngine(Settings(), rg_runner=runner, which=_RG_PRESENT)


def test_all_path_discovering_tools_emit_repo_relative_paths(tmp_path):
    """AC2 contract: every path-DISCOVERING tool emits repo-relative paths.

    Covers grep (scoped + unscoped), glob, ls, and the symbols clean branch.
    `read_span` is EXCLUDED from this producer contract with rationale: it echoes
    the caller-supplied path and discovers nothing, so it has no path-shape
    authority of its own.
    """
    _file(tmp_path, "astropy/modeling/core.py")
    # rg (cwd-relative) reports the path relative to its scope dir.
    runner, _ = _runner_returning(_match_line("modeling/core.py", 812))
    tools = _tools(tmp_path, search=_real_engine(runner))

    scoped = tools["grep"]("needle", scope="astropy/")
    assert [s.path for s in scoped] == ["astropy/modeling/core.py"]

    # Unscoped grep: rg runs from the repo root, so its cwd-relative path IS
    # repo-relative already ("modeling/core.py" would be a root-level dir here).
    unscoped_runner, _ = _runner_returning(_match_line("astropy/modeling/core.py", 812))
    tools2 = _tools(tmp_path, search=_real_engine(unscoped_runner))
    unscoped = tools2["grep"]("needle")
    assert [s.path for s in unscoped] == ["astropy/modeling/core.py"]

    globbed = tools["glob"]("astropy/**/*.py")
    assert [s.path for s in globbed] == ["astropy/modeling/core.py"]

    listed = tools["ls"]("astropy")
    assert [s.path for s in listed] == ["astropy/modeling/"]

    record = SymbolRecord(
        path="astropy/modeling/core.py", name="f", kind="function",
        start_line=1, end_line=2, language="python", parent=None,
    )
    symres = _tools(tmp_path, symbol_records=[record])["symbols"]("astropy/modeling/core.py")
    assert [s.path for s in symres["symbols"]] == ["astropy/modeling/core.py"]


def test_ls_directory_entries_are_repo_relative_noncitable(tmp_path):
    """AC2: ls dir entries are repo-relative trailing-'/' LISTINGS (non-citable)."""
    _file(tmp_path, "astropy/modeling/core.py")
    listed = _tools(tmp_path)["ls"]("astropy")
    assert listed == [CodeSpan(path="astropy/modeling/", start_line=None, end_line=None)]
    assert listed[0].is_file_level  # no fabricated line range on a listing


def test_grep_scoped_hit_is_repo_relative(tmp_path):
    """AC3 (the astropy shape at the tool seam): a scoped grep hit carries the
    repo-relative path, not the scope-relative one that normalization drops."""
    _file(tmp_path, "astropy/modeling/core.py")
    runner, _ = _runner_returning(_match_line("modeling/core.py", 812))
    tools = _tools(tmp_path, search=_real_engine(runner))
    out = tools["grep"]("separability matrix", scope="astropy/")
    assert [s.path for s in out] == ["astropy/modeling/core.py"]


def test_symbols_degraded_fallback_file_scope_repo_relative_no_crash(tmp_path):
    """AC4: the symbols degraded fallback (a FILE scope through the shared engine)
    returns repo-relative spans and never NotADirectoryError."""
    _file(tmp_path, "astropy/modeling/core.py")
    manifest = [
        ManifestEntry(
            path="astropy/modeling/core.py",
            language="python",
            size=100,
            hash="abc123",
            mtime=0.0,
            prior=0.0,
            degraded="PARSE_ERROR",
        )
    ]
    runner, captured = _runner_returning(_match_line("core.py", 5))
    tools = _tools(tmp_path, search=_real_engine(runner), manifest=manifest)
    out = tools["symbols"]("astropy/modeling/core.py")
    assert out["degraded"] is True
    assert [s.path for s in out["symbols"]] == ["astropy/modeling/core.py"]
