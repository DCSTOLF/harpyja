"""RED (tasks 34-40): Tier-0 orchestrator locate (AC10, 11, 12, 13)."""

import pytest

from harpyja.config.settings import Settings
from harpyja.index.artifacts import resolve_artifact_dir
from harpyja.index.manifest import read_manifest
from harpyja.orchestrator.locate import locate
from harpyja.server.types import CodeSpan, LocateRequest, LocateResult


def _write(root, rel, content="x\n"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


class FakeEngine:
    """Returns preset spans; records the query/scope it was called with."""

    def __init__(self, spans):
        self.spans = spans
        self.calls = []

    def search(self, pattern, scope=None):
        self.calls.append((pattern, scope))
        return list(self.spans)


def _req(repo, query="q", mode="auto", max_results=8, language_hint=None):
    return LocateRequest(
        query=query,
        repo_path=str(repo),
        mode=mode,
        max_results=max_results,
        language_hint=language_hint,
    )


def test_locate_returns_file_line_citations_tier0(tmp_path):
    _write(tmp_path, "a.py", "needle here\n")
    engine = FakeEngine([CodeSpan(path="a.py", start_line=1, end_line=1)])
    result = locate(_req(tmp_path), Settings(), engine=engine)
    assert isinstance(result, LocateResult)
    assert result.tiers_run == [0]
    assert (result.citations[0].path, result.citations[0].start_line) == ("a.py", 1)


def test_locate_ensures_index_when_no_manifest(tmp_path):
    _write(tmp_path, "a.py", "x\n")
    engine = FakeEngine([])
    locate(_req(tmp_path), Settings(), engine=engine)
    art = resolve_artifact_dir(tmp_path, Settings())
    assert {e.path for e in read_manifest(art)} >= {"a.py"}


def test_locate_reflects_added_file_without_explicit_reindex(tmp_path):
    _write(tmp_path, "a.py")
    engine = FakeEngine([])
    locate(_req(tmp_path), Settings(), engine=engine)
    _write(tmp_path, "b.py")
    locate(_req(tmp_path), Settings(), engine=engine)
    art = resolve_artifact_dir(tmp_path, Settings())
    assert "b.py" in {e.path for e in read_manifest(art)}


def test_locate_reflects_deleted_file_via_prune(tmp_path):
    a = _write(tmp_path, "a.py")
    _write(tmp_path, "b.py")
    engine = FakeEngine([])
    locate(_req(tmp_path), Settings(), engine=engine)
    a.unlink()
    locate(_req(tmp_path), Settings(), engine=engine)
    art = resolve_artifact_dir(tmp_path, Settings())
    assert "a.py" not in {e.path for e in read_manifest(art)}


def test_locate_never_exceeds_max_results(tmp_path):
    _write(tmp_path, "a.py")
    spans = [CodeSpan(path=f"f{i}.py", start_line=1, end_line=1) for i in range(10)]
    engine = FakeEngine(spans)
    result = locate(_req(tmp_path, max_results=3), Settings(), engine=engine)
    assert len(result.citations) <= 3


def test_locate_invalid_mode_rejected(tmp_path):
    _write(tmp_path, "a.py")
    engine = FakeEngine([])
    with pytest.raises(ValueError):
        locate(_req(tmp_path, mode="bogus"), Settings(), engine=engine)


def test_locate_valid_mode_sets_no_effect_note(tmp_path):
    _write(tmp_path, "a.py")
    engine = FakeEngine([CodeSpan(path="a.py", start_line=1, end_line=1)])
    result = locate(_req(tmp_path, mode="deep"), Settings(), engine=engine)
    assert result.notes == "Wave 2: deterministic + symbol-aware Tier 0; mode has no effect"


def test_locate_language_hint_filters_to_matching_language(tmp_path):
    _write(tmp_path, "a.py")
    _write(tmp_path, "b.go")
    spans = [
        CodeSpan(path="a.py", start_line=1, end_line=1),
        CodeSpan(path="b.go", start_line=1, end_line=1),
    ]
    engine = FakeEngine(spans)
    result = locate(_req(tmp_path, language_hint="go"), Settings(), engine=engine)
    assert {c.path for c in result.citations} == {"b.go"}


def test_locate_null_language_returned_without_hint(tmp_path):
    _write(tmp_path, "run", "x\n")  # extensionless → null language
    engine = FakeEngine([CodeSpan(path="run", start_line=1, end_line=1)])
    result = locate(_req(tmp_path), Settings(), engine=engine)
    assert "run" in {c.path for c in result.citations}


def test_locate_null_language_excluded_under_hint(tmp_path):
    _write(tmp_path, "run", "x\n")
    engine = FakeEngine([CodeSpan(path="run", start_line=1, end_line=1)])
    result = locate(_req(tmp_path, language_hint="python"), Settings(), engine=engine)
    assert "run" not in {c.path for c in result.citations}
    assert "undetermined" in (result.notes or "")


def test_locate_unrecognized_hint_note(tmp_path):
    _write(tmp_path, "a.py")
    engine = FakeEngine([CodeSpan(path="a.py", start_line=1, end_line=1)])
    result = locate(_req(tmp_path, language_hint="klingon"), Settings(), engine=engine)
    assert "not a recognized language" in (result.notes or "")


# --- Wave 2: symbol-aware composition (AC9, AC10, AC11, AC13, AC14) ---

import os  # noqa: E402


def test_locate_mode_note_is_wave2_symbol_aware_string(tmp_path):
    _write(tmp_path, "a.py", "x = 1\n")
    result = locate(_req(tmp_path), Settings(), engine=FakeEngine([]))
    assert result.notes.startswith("Wave 2: deterministic + symbol-aware Tier 0")


def test_locate_promotes_definition_above_call_site_for_same_token(tmp_path):
    _write(tmp_path, "a.py", "def foo():\n    pass\nfoo()\nfoo()\n")
    # Fake ripgrep returns the call-site lines for the token `foo`.
    engine = FakeEngine([CodeSpan("a.py", 3, 3), CodeSpan("a.py", 4, 4)])
    result = locate(_req(tmp_path, query="foo"), Settings(), engine=engine)
    top = result.citations[0]
    assert top.symbol == "foo"  # the definition
    assert (top.start_line, top.end_line) == (1, 2)
    assert result.tiers_run == [0]  # still Tier 0, zero model calls


def test_locate_no_symbol_match_degrades_to_wave1_exact_citations_and_order(tmp_path):
    _write(tmp_path, "a.py", "x = 1\n")  # no symbol named 'zzz'
    engine = FakeEngine([CodeSpan(path="a.py", start_line=1, end_line=1)])
    result = locate(_req(tmp_path, query="zzz"), Settings(), engine=engine)
    assert [(c.path, c.start_line) for c in result.citations] == [("a.py", 1)]
    assert result.citations[0].symbol is None  # pure text hit, exactly Wave-1


def test_locate_method_address_foo_dot_bar_promotes_method(tmp_path):
    _write(tmp_path, "a.py", "class Foo:\n    def bar(self):\n        pass\n")
    result = locate(_req(tmp_path, query="Foo.bar"), Settings(), engine=FakeEngine([]))
    assert any(c.symbol == "bar" and c.kind == "method" for c in result.citations)


def test_locate_builds_symbols_from_scratch_when_none_present(tmp_path):
    _write(tmp_path, "a.py", "def foo():\n    pass\n")
    result = locate(_req(tmp_path, query="foo"), Settings(), engine=FakeEngine([]))
    assert any(c.symbol == "foo" for c in result.citations)


def test_locate_after_edit_reflects_new_symbols_without_explicit_reindex(tmp_path):
    f = _write(tmp_path, "a.py", "def foo():\n    pass\n")
    locate(_req(tmp_path, query="foo"), Settings(), engine=FakeEngine([]))
    f.write_text("def bar():\n    pass\n", encoding="utf-8")
    os.utime(f, (2_000_000_000, 2_000_000_000))
    result = locate(_req(tmp_path, query="bar"), Settings(), engine=FakeEngine([]))
    assert any(c.symbol == "bar" for c in result.citations)
