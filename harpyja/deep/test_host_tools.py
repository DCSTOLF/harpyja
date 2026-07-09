"""RED (task 11): bounded read-only host tools for the untrusted RLM (AC7/8/8a).

The RLM is an untrusted caller: every host tool enforces repo-path confinement and
the existing Settings clamps, the surface is read-only, and the exposed set is
*exactly* the four whitelisted tools.
"""

import pytest

from harpyja.config.settings import Settings
from harpyja.deep.budget import DeepBudget
from harpyja.deep.host_tools import build_host_tools
from harpyja.index.manifest import ManifestEntry
from harpyja.server.tools import PathConfinementError
from harpyja.server.types import CodeSpan
from harpyja.symbols.extract import SymbolRecord


class _FakeSearch:
    """Stands in for RipgrepEngine (no `rg` needed)."""

    def __init__(self, spans):
        self.spans = spans
        self.calls = []

    def search(self, pattern, scope=None, *, repo_root=None):
        self.calls.append((pattern, scope))
        return list(self.spans)


def _tools(tmp_path, *, settings=None, search_spans=None, records=None, manifest=None):
    settings = settings or Settings()
    return build_host_tools(
        str(tmp_path),
        settings,
        search_engine=_FakeSearch(search_spans or []),
        symbol_records=records or [],
        manifest=manifest or [],
        budget=DeepBudget(settings),
    )


def _file(tmp_path, rel, n=50):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(f"line {i}" for i in range(1, n + 1)) + "\n", encoding="utf-8")
    return p


def test_host_tools_whitelist_exact_equality(tmp_path):
    tools = _tools(tmp_path)
    assert set(tools) == {"list_manifest", "search", "symbols", "read_span"}


def test_host_tools_surface_is_read_only(tmp_path):
    tools = _tools(tmp_path)
    # No mutating capability is exposed under any name.
    assert not (set(tools) & {"write", "edit", "delete", "create", "open", "exec"})


def test_read_span_rejects_path_outside_repo(tmp_path):
    _file(tmp_path, "a.py")
    tools = _tools(tmp_path)
    with pytest.raises(PathConfinementError):
        tools["read_span"]("../../etc/passwd", 1, 1)


def test_read_span_clamps_over_budget_lines(tmp_path):
    _file(tmp_path, "a.py", n=50)
    tools = _tools(tmp_path, settings=Settings(tool_max_lines=5))
    out = tools["read_span"]("a.py", 1, 40)
    assert out["truncated"] is True
    assert out["end"] == 5  # clamped to the line bound


def test_search_confines_scope_to_repo_root(tmp_path):
    tools = _tools(tmp_path, search_spans=[CodeSpan("a.py", 1, 1)])
    with pytest.raises(PathConfinementError):
        tools["search"]("needle", scope="../outside")


def test_search_clamps_max_matches(tmp_path):
    spans = [CodeSpan(f"f{i}.py", 1, 1) for i in range(10)]
    tools = _tools(tmp_path, settings=Settings(search_max_matches=2), search_spans=spans)
    out = tools["search"]("needle")
    assert len(out) == 2


def test_symbols_rejects_path_outside_repo(tmp_path):
    tools = _tools(tmp_path)
    with pytest.raises(PathConfinementError):
        tools["symbols"]("../escape.py")


def test_symbols_returns_file_definitions(tmp_path):
    _file(tmp_path, "pkg/mod.py")
    recs = [
        SymbolRecord("pkg/mod.py", "python", "foo", "function", None, 1, 2),
        SymbolRecord("other.py", "python", "bar", "function", None, 1, 2),
    ]
    tools = _tools(tmp_path, records=recs)
    out = tools["symbols"]("pkg/mod.py")
    assert [s.symbol for s in out] == ["foo"]  # only this file's defs


def test_list_manifest_bounded_by_manifest_page(tmp_path):
    entries = [
        ManifestEntry(path=f"f{i}.py", language="python", size=1, hash="h", mtime=0.0, prior=0.0)
        for i in range(10)
    ]
    tools = _tools(tmp_path, settings=Settings(manifest_page=3), manifest=entries)
    out = tools["list_manifest"](None)
    assert len(out) == 3


# --- Spec 0033: Deep search inherits the repo-relative fix (AC4) ---

from harpyja.symbols.ripgrep import RipgrepEngine  # noqa: E402
from harpyja.symbols.test_ripgrep import _match_line, _runner_returning  # noqa: E402


def _engine_tools(tmp_path, runner, *, settings=None):
    settings = settings or Settings()
    engine = RipgrepEngine(settings, rg_runner=runner, which=lambda _n: "/usr/bin/rg")
    return build_host_tools(
        str(tmp_path),
        settings,
        search_engine=engine,
        symbol_records=[],
        manifest=[],
        budget=DeepBudget(settings),
    )


def test_deep_search_scoped_returns_repo_relative(tmp_path):
    """AC4: Deep's scoped search POSITIVELY changes to repo-relative — the
    inherited engine-seam fix, not just unscoped non-regression."""
    (tmp_path / "astropy").mkdir()
    runner, _ = _runner_returning(_match_line("modeling/core.py", 812))
    tools = _engine_tools(tmp_path, runner)
    out = tools["search"]("needle", scope="astropy")
    assert [s.path for s in out] == ["astropy/modeling/core.py"]


def test_deep_search_unscoped_byte_identical(tmp_path):
    """AC4: Deep's unscoped search output is byte-identical (repo-root prefix
    collapses to '.')."""
    runner, _ = _runner_returning(_match_line("django/db/models/query.py", 693))
    tools = _engine_tools(tmp_path, runner)
    out = tools["search"]("in_bulk")
    assert [s.path for s in out] == ["django/db/models/query.py"]
