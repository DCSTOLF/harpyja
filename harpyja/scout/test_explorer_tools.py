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
from harpyja.scout.explorer_tools import build_explorer_tools
from harpyja.server.tools import PathConfinementError
from harpyja.server.types import CodeSpan


class _FakeSearch:
    """Stands in for RipgrepEngine (no `rg` needed) — records its calls."""

    def __init__(self, spans):
        self.spans = spans
        self.calls = []

    def search(self, pattern, scope=None):
        self.calls.append((pattern, scope))
        return list(self.spans)


def _file(tmp_path, rel, n=50):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(f"line {i}" for i in range(1, n + 1)) + "\n", encoding="utf-8")
    return p


def _tools(tmp_path, *, settings=None, search=None):
    settings = settings or Settings()
    return build_explorer_tools(
        str(tmp_path),
        settings,
        search_engine=search or _FakeSearch([]),
    )


def test_build_explorer_tools_returns_exactly_four_navigation_tools(tmp_path):
    tools = _tools(tmp_path)
    # spec 0027: EXACTLY four navigation tools — `ls` added as the layout-discovery
    # affordance `glob` lacks (a DELIBERATE, reconciled tool-suite change). No terminal
    # submit action, nothing else.
    assert set(tools) == {"grep", "glob", "read_span", "ls"}
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
