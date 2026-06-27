"""Tests for SymbolEngine — exact-only symbol search behind the Locator (AC9, AC10).

Matching is exact + case-sensitive (no substring); method addressing is an ordered
adjacent `.`/`::` pair within a single whitespace-delimited segment. The engine
returns definition `CodeSpan`s carrying `symbol`/`kind` so the formatter can promote
them.
"""

from __future__ import annotations

from harpyja.config.settings import Settings
from harpyja.server.types import CodeSpan
from harpyja.symbols.extract import SymbolRecord
from harpyja.symbols.symbol_locator import SymbolEngine


def _rec(name, kind="function", parent=None, path="a.py", start=1, end=2):
    return SymbolRecord(
        path=path,
        language="python",
        name=name,
        kind=kind,
        parent=parent,
        start_line=start,
        end_line=end,
    )


def _engine(records, settings=None):
    return SymbolEngine(records, settings or Settings())


def test_symbol_engine_implements_locator_search_signature():
    eng = _engine([_rec("foo")])
    out = eng.search("foo", scope="/repo")  # (pattern, scope=None) like RipgrepEngine
    assert isinstance(out, list)
    assert all(isinstance(s, CodeSpan) for s in out)


def test_search_exact_case_sensitive_name_match_parse_ne_lower_parse():
    eng = _engine([_rec("Parse")])
    assert len(eng.search("Parse")) == 1
    assert eng.search("parse") == []  # case-sensitive


def test_search_no_substring_match_parseconfig_or_reparse():
    eng = _engine([_rec("Parse")])
    assert eng.search("ParseConfig") == []
    assert eng.search("reParse") == []


def test_search_returns_definition_codespans_carrying_symbol_parent_kind():
    eng = _engine([_rec("foo", kind="function", start=3, end=5, path="m.py")])
    (span,) = eng.search("foo")
    assert span.path == "m.py"
    assert span.start_line == 3 and span.end_line == 5
    assert span.symbol == "foo"
    assert span.kind == "function"


def test_search_method_address_dot_pair_matches_parent_then_name():
    recs = [_rec("bar", kind="method", parent="Foo"), _rec("bar", kind="function", parent=None)]
    out = _engine(recs).search("Foo.bar")
    promoted = {(s.symbol, s.kind) for s in out}
    assert ("bar", "method") in promoted  # the Foo.bar method


def test_search_method_address_colon_colon_pair():
    eng = _engine([_rec("bar", kind="method", parent="Foo")])
    assert any(s.symbol == "bar" for s in eng.search("Foo::bar"))


def test_search_whitespace_separated_segments_not_method_address():
    # `Stack.push` forms the (Stack, push) address; whitespace does NOT glue tokens
    # into an address. The parent token alone is inert (it is not a symbol *name*),
    # so the address is the only thing that ties `Stack` to `push`.
    eng = _engine([_rec("push", kind="method", parent="Stack")])
    assert any(s.symbol == "push" for s in eng.search("Stack.push"))  # dot → address
    assert eng.search("Stack") == []  # parent token alone matches nothing


def test_search_chain_evaluates_every_adjacent_pair():
    recs = [
        _rec("bar", kind="method", parent="Foo"),
        _rec("baz", kind="method", parent="bar"),
    ]
    out = _engine(recs).search("Foo.bar.baz")
    names = {s.symbol for s in out}
    assert "bar" in names  # (Foo, bar)
    assert "baz" in names  # (bar, baz)


def test_search_bounded_by_configured_search_limits():
    from dataclasses import replace

    settings = replace(Settings(), search_max_matches=2)
    recs = [_rec("dup", path=f"f{i}.py", start=i + 1, end=i + 1) for i in range(5)]
    out = _engine(recs, settings).search("dup")
    assert len(out) <= 2


def test_search_orchestrator_never_branches_dedupes_identical():
    rec = _rec("foo")
    eng = _engine([rec])
    # `foo foo` — same name twice across segments — must not duplicate the span.
    assert len(eng.search("foo foo")) == 1


# --- 0004: new-language method addressing reuses `.` / `::` (AC11) ---


def _rec_lang(name, language, kind="function", parent=None, path="a", start=1, end=2):
    return SymbolRecord(
        path=path,
        language=language,
        name=name,
        kind=kind,
        parent=parent,
        start_line=start,
        end_line=end,
    )


def test_search_rust_colon_colon_method_address():
    eng = _engine([_rec_lang("bar", "rust", kind="method", parent="Foo", path="m.rs")])
    assert any(s.symbol == "bar" for s in eng.search("Foo::bar"))


def test_search_cpp_colon_colon_method_address():
    eng = _engine([_rec_lang("bar", "cpp", kind="method", parent="Foo", path="m.cpp")])
    assert any(s.symbol == "bar" for s in eng.search("Foo::bar"))


def test_search_cross_namespace_same_name_parent_both_match():
    # Two `bar` under a `Foo` parent in different files — `parent` is immediate-only
    # and namespaces are out of scope, so `Foo::bar` matches BOTH (documented
    # addressing ambiguity, not a regression).
    recs = [
        _rec_lang("bar", "cpp", kind="method", parent="Foo", path="a.cpp", start=1, end=2),
        _rec_lang("bar", "cpp", kind="method", parent="Foo", path="b.cpp", start=5, end=6),
    ]
    out = _engine(recs).search("Foo::bar")
    assert {s.path for s in out} == {"a.cpp", "b.cpp"}


def test_search_arrow_separator_does_not_glue_into_method_address():
    # Only `.` / `::` glue parent→name. The parent token alone is inert, exactly as
    # for whitespace — `->` is not a method-address separator (AC11).
    eng = _engine([_rec_lang("bar", "cpp", kind="method", parent="Foo", path="m.cpp")])
    assert eng.search("Foo") == []  # parent token alone matches nothing
    # `Foo->bar` finds `bar` only via plain-name tokenization, never an address pair.
    assert eng.search("Foo->bar") == eng.search("bar")
