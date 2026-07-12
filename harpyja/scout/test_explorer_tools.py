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


# --- Spec 0030: symbols tool (AC1) — result shape re-pinned by spec 0042 (AC2):
# bare list[CodeSpan] like every other nav tool; the 0/28-era nested dict
# {"symbols": [...], "degraded": bool} registered ZERO spans in _spans_of and
# structurally penalized every call.


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
    assert isinstance(out, list)
    assert len(out) == 2
    assert out[0].symbol == "MyClass"
    assert out[0].kind == "class"
    assert out[0].start_line == 1
    assert out[0].end_line == 10
    assert out[1].symbol == "my_func"
    assert out[1].kind == "function"


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
    assert isinstance(out, list)
    assert len(out) == 1
    assert out[0].symbol == "SomeType"
    assert out[0].kind == "type"


def test_symbols_clean_returns_bare_codespan_list(tmp_path):
    # Spec 0042 (AC2): the CLEAN result is a bare list[CodeSpan] — shape parity
    # with grep/glob/ls, so _spans_of unwraps it and its locations enter
    # seen-span/loop-detection accounting.
    records = [
        SymbolRecord(
            path="app.py", language="python", name="f", kind="function",
            parent=None, start_line=1, end_line=2,
        )
    ]
    out = _tools(tmp_path, symbol_records=records)["symbols"]("app.py")
    assert isinstance(out, list)
    assert all(isinstance(s, CodeSpan) for s in out)


def test_symbols_result_shape_no_longer_nested_dict(tmp_path):
    # Spec 0042 (AC2): regression pin against the 0/28-era shape — the result is
    # NEVER a mapping ({"symbols": ..., "degraded": ...}), on any branch:
    # clean, degraded, and no-records.
    from collections.abc import Mapping

    records = [
        SymbolRecord(
            path="app.py", language="python", name="f", kind="function",
            parent=None, start_line=1, end_line=2,
        )
    ]
    manifest = [
        ManifestEntry(
            path="broken.py", language="python", size=1, hash="h", mtime=0.0,
            prior=0.0, degraded="PARSE_ERROR",
        )
    ]
    tools = _tools(
        tmp_path, search=_FakeSearch([CodeSpan(path="broken.py", start_line=1, end_line=1)]),
        symbol_records=records, manifest=manifest,
    )
    for path in ("app.py", "broken.py", "unknown.py"):
        assert not isinstance(tools["symbols"](path), Mapping)


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
    assert len(out1) == 1
    assert len(out2) == 1
    assert out1[0].symbol == out2[0].symbol


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
    assert len(out) == 1
    assert out[0].symbol == "phantom"


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
    assert len(out) == 3  # defensive clamp on untrusted-loop output


# --- Spec 0030: graceful degradation with visible provenance (AC3) —
# Spec 0042 (AC2): the degraded result is [marker, *CodeSpans] — a stable
# ANNOTATION marker string PREPENDED to the real ripgrep-fallback spans (the
# 0035 convention's second case: successful-but-degraded, spans real). The
# marker never counts as a span; 0030's never-a-silent-downgrade contract is
# preserved via loop stringification.


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
    # The ripgrep fallback spans ride BEHIND the marker (not zero records).
    assert isinstance(out, list)
    spans = [s for s in out if isinstance(s, CodeSpan)]
    assert len(spans) == 2
    assert spans[0].start_line == 5


def test_symbols_degraded_prepends_marker_then_codespans(tmp_path):
    # Spec 0042 (AC2): degraded shape is [marker, *CodeSpans] — marker FIRST, a
    # stable identifier (cause-taxonomy shape), then the real fallback spans.
    ripgrep_results = [CodeSpan(path="broken.py", start_line=1, end_line=1)]
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
    tools = _tools(tmp_path, search=_FakeSearch(ripgrep_results), manifest=manifest)
    out = tools["symbols"]("broken.py")
    assert isinstance(out, list)
    assert isinstance(out[0], str)
    assert out[0] == "symbols-degraded: 'broken.py'"
    assert [s for s in out[1:]] == ripgrep_results


def test_symbols_tool_clean_file_not_marked_degraded(tmp_path):
    # AC3: a clean file (no manifest degraded flag) carries NO marker — a bare
    # CodeSpan list with no string element.
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
    assert isinstance(out, list)
    assert not any(isinstance(item, str) for item in out)
    assert len(out) == 1


def test_symbols_tool_degraded_never_raises(tmp_path):
    # AC3: degraded files return a normal tool result, never an exception
    # (untrusted-caller boundary). An empty fallback still carries the marker —
    # the degrade is never silent.
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
    out = tools["symbols"]("broken.py")
    assert out == ["symbols-degraded: 'broken.py'"]


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
    assert [s.path for s in symres] == ["astropy/modeling/core.py"]


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
    assert out[0] == "symbols-degraded: 'astropy/modeling/core.py'"
    assert [s.path for s in out[1:]] == ["astropy/modeling/core.py"]


# --- Spec 0035: scope markers + file-scope delegation ---


def test_grep_real_dir_zero_matches_returns_plain_empty(tmp_path):
    """PIN (0035 AC3): a searchable dir scope with zero matches stays plain [] —
    honest-empty is never blurred by the marker split."""
    _file(tmp_path, "astropy/modeling/core.py")
    empty_runner, _ = _runner_returning()  # no match lines
    out = _tools(tmp_path, search=_real_engine(empty_runner))["grep"]("needle", scope="astropy/")
    assert out == []


def test_ls_existing_file_returns_plain_empty(tmp_path):
    """PIN (0035 OQ1): ls on an existing FILE keeps [] — 'list children' of a file
    is honestly empty, categorically distinct from path-absent (which markers)."""
    _file(tmp_path, "a.py")
    assert _tools(tmp_path)["ls"]("a.py") == []


def test_grep_file_scope_delegates_returns_engine_matches(tmp_path):
    """AC1 (the positive astropy fixture): a FILE scope DELEGATES to the engine
    (0033 parent-dir mechanism) and returns real repo-relative matches — the
    0033-observed right-file greps would have returned these, not []."""
    _file(tmp_path, "astropy/modeling/separable.py")
    runner, _ = _runner_returning(_match_line("separable.py", 66))
    out = _tools(tmp_path, search=_real_engine(runner))["grep"](
        "separability_matrix", scope="astropy/modeling/separable.py"
    )
    assert [s.path for s in out] == ["astropy/modeling/separable.py"]


def test_grep_nonexistent_scope_returns_marker(tmp_path):
    """AC2: a nonexistent scope returns the stable marker — and the guard fires
    BEFORE delegation (the injected engine raises on any call)."""
    class _RaisingEngine:
        def search(self, pattern, scope=None, *, repo_root=None):
            raise AssertionError("engine must not be called for a nonexistent scope")

    out = _tools(tmp_path, search=_RaisingEngine())["grep"]("x", scope="repo")
    assert out == "grep-scope-not-found: 'repo'"


def test_grep_real_file_zero_matches_delegates_returns_empty(tmp_path):
    """AC3 (file-scope honest-empty via delegation): the engine IS called and its
    empty result passes through as plain []."""
    _file(tmp_path, "a.py")
    fake = _FakeSearch([])
    out = _tools(tmp_path, search=fake)["grep"]("needle", scope="a.py")
    assert out == []
    assert fake.calls  # delegation happened — the engine was consulted


def test_ls_nonexistent_path_returns_marker(tmp_path):
    """AC4: ls on a NONEXISTENT path returns the stable marker — same fix class
    as grep (confine_path non-strict + silent-[] mechanics)."""
    out = _tools(tmp_path)["ls"]("does/not/exist")
    assert out == "ls-path-not-found: 'does/not/exist'"


# --- Spec 0042 (AC3): repo-wide symbol lookup — `path` optional, by-name -------
#
# The adoption driver: with `path` REQUIRED, symbols was only reachable AFTER a
# candidate file was found (by which point grep had line numbers already — no
# perceived marginal value). Repo-wide by-name lookup is the partial answer to
# lexical unreachability (astropy: "separability matrix" is ungreppable, but
# separability_matrix is findable BY NAME). Read-only, repo-confined (it only
# filters injected Tier-0 records), output-clamped by the DISTINCT
# scout_symbols_repo_max_entries knob, ranking PINNED exact > prefix > substring.


def _rec(name, path="a.py", start=1, end=2):
    return SymbolRecord(
        path=path, language="python", name=name, kind="function",
        parent=None, start_line=start, end_line=end,
    )


def test_symbols_repo_wide_lookup_by_name_no_path(tmp_path):
    # No path → repo-wide lookup over the Tier-0 records, exact spans returned.
    records = [
        _rec("separability_matrix", path="astropy/modeling/separable.py", start=66, end=120),
        _rec("unrelated", path="astropy/io/fits.py"),
    ]
    out = _tools(tmp_path, symbol_records=records)["symbols"](name="separability_matrix")
    assert [s.path for s in out] == ["astropy/modeling/separable.py"]
    assert out[0].start_line == 66
    assert out[0].end_line == 120


def test_symbols_repo_wide_ranking_exact_prefix_substring(tmp_path):
    # PINNED ranking (spec 0042 OQ2): exact-name > prefix > substring, ties
    # broken deterministically by path lexicographic then start_line — never
    # arbitrary truncation order.
    records = [
        _rec("myfoo", path="sub.py"),               # substring tier
        _rec("foobar", path="prefix.py"),            # prefix tier
        _rec("foo", path="z.py"),                    # exact tier, tie-broken second
        _rec("foo", path="a.py"),                    # exact tier, tie-broken first
    ]
    out = _tools(tmp_path, symbol_records=records)["symbols"](name="foo")
    assert [(s.symbol, s.path) for s in out] == [
        ("foo", "a.py"), ("foo", "z.py"), ("foobar", "prefix.py"), ("myfoo", "sub.py"),
    ]


def test_symbols_repo_wide_no_match_is_honest_empty(tmp_path):
    # Records PRESENT but nothing matches → plain [] (searchable-but-empty),
    # categorically distinct from the absent-index replacement marker below.
    out = _tools(tmp_path, symbol_records=[_rec("bar")])["symbols"](name="zzz")
    assert out == []


def test_symbols_repo_wide_clamped_by_repo_max_entries(tmp_path):
    # Clamped by the DISTINCT repo-wide knob (a common name's blast radius across
    # a repo differs from one file's symbol list) — not the file-local clamp.
    records = [_rec("common", path=f"pkg/f{i:02d}.py") for i in range(10)]
    settings = Settings(scout_symbols_repo_max_entries=3, scout_symbols_max_entries=400)
    out = _tools(tmp_path, settings=settings, symbol_records=records)["symbols"](name="common")
    assert len(out) == 3


def test_symbols_repo_wide_hostile_input_rejected(tmp_path):
    # Hostile/oversized name input is rejected with a typed marker — bounded,
    # never echoed unclamped, never an unhandled exception.
    tools = _tools(tmp_path, symbol_records=[_rec("foo")])
    oversized = "x" * 10_000
    out = tools["symbols"](name=oversized)
    assert isinstance(out, str)
    assert out.startswith("symbols-name-invalid:")
    assert len(out) < 400  # the hostile input is clipped, not echoed whole
    assert tools["symbols"](name="") == "symbols-name-invalid: ''"


def test_symbols_no_args_returns_typed_marker(tmp_path):
    # Neither path nor name → a typed marker, never a silent [] and never a crash.
    out = _tools(tmp_path, symbol_records=[_rec("foo")])["symbols"]()
    assert out == "symbols-args-missing: 'provide path or name'"


def test_symbols_nonexistent_path_returns_replacement_marker(tmp_path):
    # Post-T12 pin (observed LIVE: symbols({"path": "digest-auth/*"}) returned a
    # silent []): a path with NO records that also does not exist on disk is
    # UNSEARCHABLE — the 0035 replacement marker, same class as ls/grep — never
    # a silent [] that reads as "file has no symbols".
    out = _tools(tmp_path)["symbols"]("digest-auth/*")
    assert out == "symbols-path-not-found: 'digest-auth/*'"


def test_symbols_existing_file_without_records_is_honest_empty(tmp_path):
    # A REAL file with no extracted records (e.g. unsupported language) stays
    # honest-[] — searchable-but-empty, categorically distinct from path-absent.
    _file(tmp_path, "notes.txt")
    assert _tools(tmp_path)["symbols"]("notes.txt") == []


def test_symbols_records_win_over_disk_absence(tmp_path):
    # The records-win contract (test_symbols_tool_no_new_parser) is unchanged:
    # records for a path whose file is NOT on disk are still returned — the
    # marker fires only when BOTH records and the file are absent.
    records = [_rec("phantom", path="gone.py")]
    out = _tools(tmp_path, symbol_records=records)["symbols"]("gone.py")
    assert [s.symbol for s in out] == ["phantom"]


def test_symbols_empty_string_path_routes_repo_wide_not_file_local(tmp_path):
    # Post-T12 pin (observed LIVE in the 0042 measurement, astropy cell): the
    # model sent {"path": "", "name": "..."} and the `path is None` routing sent
    # it down the FILE-LOCAL branch, silently ignoring `name` — a silent
    # degradation of the repo-wide affordance. An empty/absent path with a name
    # MUST route repo-wide.
    records = [_rec("separability_matrix", path="astropy/modeling/separable.py", start=66, end=120)]
    out = _tools(tmp_path, symbol_records=records)["symbols"](path="", name="separability_matrix")
    assert [s.path for s in out] == ["astropy/modeling/separable.py"]


def test_symbols_empty_path_and_no_name_is_args_missing(tmp_path):
    # Empty path with no name is the args-missing marker, same as no args at all.
    out = _tools(tmp_path, symbol_records=[_rec("foo")])["symbols"](path="")
    assert out == "symbols-args-missing: 'provide path or name'"


def test_symbols_repo_wide_absent_tier0_returns_replacement_marker(tmp_path):
    # Absent Tier-0 records (e.g. wiring's load_symbols_or_none(...) or []) →
    # the 0035 REPLACEMENT marker (no spans exist to annotate) — never a silent
    # [] indistinguishable from "no such symbol".
    out = _tools(tmp_path, symbol_records=[])["symbols"](name="separability_matrix")
    assert out == "symbols-index-unavailable: 'separability_matrix'"
