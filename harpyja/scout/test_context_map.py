"""RED (T5, AC3): the pre-model context map.

A compact, high-level repo map built from the EXISTING manifest — a filtered tree
with NO raw file contents — injected with the query so the model sees layout
without loading files. The vendor/test/generated exclusion applies to the MAP
(a display concern) ONLY: the navigation tools (`grep`/`glob`/`read_span`) must
still reach those files, because a test/vendor file can be the localization
target.
"""

from harpyja.config.settings import Settings
from harpyja.index.manifest import ManifestEntry
from harpyja.scout.context_map import build_context_map
from harpyja.scout.explorer_tools import build_explorer_tools
from harpyja.server.types import CodeSpan


def _entry(path):
    return ManifestEntry(
        path=path, language=None, size=1, hash="h", mtime=0.0, prior=1.0
    )


def _file(tmp_path, rel, n=10):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(f"line {i}" for i in range(1, n + 1)) + "\n", encoding="utf-8")
    return p


def test_context_map_built_from_manifest_no_file_bytes():
    # The signature takes ONLY the manifest — it structurally cannot read file
    # bytes. The rendered map names the source paths from the manifest.
    manifest = [_entry("pkg/a.py"), _entry("pkg/sub/b.py")]
    text = build_context_map(manifest, "where is the bug", Settings())
    assert "pkg/a.py" in text
    assert "pkg/sub/b.py" in text


def test_context_map_injected_with_query():
    text = build_context_map([_entry("pkg/a.py")], "locate the parser", Settings())
    assert "locate the parser" in text


def test_context_map_excludes_vendor_test_generated_from_display():
    manifest = [
        _entry("pkg/core.py"),
        _entry("tests/test_core.py"),
        _entry("vendor/dep/lib.py"),
        _entry("dist/bundle.min.js"),
    ]
    text = build_context_map(manifest, "q", Settings())
    assert "pkg/core.py" in text
    # Deprioritized layers are dropped from the DISPLAY.
    assert "tests/test_core.py" not in text
    assert "vendor/dep/lib.py" not in text
    assert "dist/bundle.min.js" not in text


def test_excluded_file_still_reachable_via_tools(tmp_path):
    # A test file dropped from the MAP is still reachable through the tools —
    # map-filtering is a display concern, never a search-confinement one.
    _file(tmp_path, "tests/test_core.py")
    manifest = [_entry("tests/test_core.py")]
    text = build_context_map(manifest, "q", Settings())
    assert "tests/test_core.py" not in text  # excluded from map

    tools = build_explorer_tools(str(tmp_path), Settings(), search_engine=_FakeSearch())
    hits = tools["glob"]("tests/*.py")
    assert [s.path for s in hits] == ["tests/test_core.py"]  # still reachable
    snippet = tools["read_span"]("tests/test_core.py", 1, 1)
    assert snippet["path"] == "tests/test_core.py"


class _FakeSearch:
    def search(self, pattern, scope=None, *, repo_root=None):
        return [CodeSpan(path="tests/test_core.py", start_line=1, end_line=1)]
