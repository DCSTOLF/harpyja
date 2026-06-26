"""Tests for the tree-sitter symbol extractor (AC1, AC2, AC4, AC15).

Defs-only, classified by syntactic form. Parsing uses the real (in-process)
grammars; the grammar-missing / load-error paths are exercised by injecting a
`parser_for` seam, never by uninstalling a package.
"""

from __future__ import annotations

from harpyja.symbols.engine_identity import GrammarLoadError, GrammarMissing
from harpyja.symbols.extract import ExtractResult, SymbolRecord, extract_symbols


def _py(src: str, path: str = "m.py") -> ExtractResult:
    return extract_symbols(path, "python", src.encode())


def _go(src: str, path: str = "m.go") -> ExtractResult:
    return extract_symbols(path, "go", src.encode())


def _triples(res: ExtractResult) -> set[tuple[str, str, str | None]]:
    return {(r.name, r.kind, r.parent) for r in res.records}


# --- Python kind vocabulary (AC1, AC2) ---


def test_extract_python_function_method_class_and_module_constant():
    res = _py("X = 1\ndef foo():\n    pass\nclass Bar:\n    def meth(self):\n        pass\n")
    k = _triples(res)
    assert ("foo", "function", None) in k
    assert ("Bar", "class", None) in k
    assert ("meth", "method", "Bar") in k
    assert ("X", "constant", None) in k


def test_extract_python_async_def_same_kind_as_def():
    res = _py("async def baz():\n    pass\n")
    assert ("baz", "function", None) in _triples(res)


def test_extract_python_constant_only_upper_snake_plain_or_annotated():
    res = _py("X = 1\nY: int = 2\nlower = 3\n")
    consts = {r.name for r in res.records if r.kind == "constant"}
    assert consts == {"X", "Y"}


def test_extract_python_constant_excludes_tuple_unpack_and_augmented():
    res = _py("A, B = 1, 2\nC = 5\nC += 1\n")
    consts = {r.name for r in res.records if r.kind == "constant"}
    assert consts == {"C"}


def test_extract_python_call_valued_constant_still_constant_by_syntax():
    res = _py("COLOR = make_thing('x')\n")
    assert ("COLOR", "constant", None) in _triples(res)


def test_extract_python_method_parent_is_immediate_enclosing_class():
    res = _py("class Outer:\n    def m(self):\n        pass\n")
    assert ("m", "method", "Outer") in _triples(res)


def test_extract_python_toplevel_parent_is_null():
    res = _py("def top():\n    pass\n")
    rec = next(r for r in res.records if r.name == "top")
    assert rec.parent is None


def test_extract_python_skips_imports_call_sites_and_function_local_defs():
    res = _py(
        "import os\nfrom sys import path\n"
        "def outer():\n    def inner():\n        pass\n    helper()\n"
    )
    names = {r.name for r in res.records}
    assert names == {"outer"}


def test_extract_python_record_range_is_one_indexed_inclusive():
    res = _py("def foo():\n    pass\n")
    rec = next(r for r in res.records if r.name == "foo")
    assert rec.start_line == 1 and rec.end_line == 2
    assert isinstance(rec, SymbolRecord)
    assert rec.language == "python"


# --- Go kind vocabulary + receiver normalization (AC2) ---


def test_extract_go_function_method_struct_interface_and_named_type():
    src = (
        "package m\n"
        "type Foo struct{}\n"
        "type Sh interface{}\n"
        "type Defined int\n"
        "type Alias = int\n"
        "func Free() {}\n"
        "func (f *Foo) M() {}\n"
    )
    k = _triples(_go(src))
    assert ("Foo", "struct", None) in k
    assert ("Sh", "interface", None) in k
    assert ("Defined", "type", None) in k
    assert ("Alias", "type", None) in k
    assert ("Free", "function", None) in k
    assert ("M", "method", "Foo") in k


def test_extract_go_package_level_const_and_var():
    k = _triples(_go("package m\nconst C = 1\nvar V, W = 1, 2\n"))
    assert ("C", "const", None) in k
    assert ("V", "var", None) in k
    assert ("W", "var", None) in k


def test_extract_go_pointer_and_value_receiver_both_parent_foo():
    src = "package m\nfunc (f *Foo) P() {}\nfunc (b Foo) Q() {}\n"
    k = _triples(_go(src))
    assert ("P", "method", "Foo") in k
    assert ("Q", "method", "Foo") in k


def test_extract_go_generic_receiver_strips_pointer_and_type_params():
    k = _triples(_go("package m\nfunc (s *Stack[T]) Push() {}\n"))
    assert ("Push", "method", "Stack") in k


def test_extract_go_toplevel_parent_is_null():
    rec = next(r for r in _go("package m\nfunc Free() {}\n").records if r.name == "Free")
    assert rec.parent is None


# --- Parse-error own-region scoping + grammar unavailability (AC4, AC15) ---


def test_extract_skips_error_spanned_def_keeps_clean_sibling():
    res = _py("def good():\n    pass\ndef bad(:\n    pass\n")
    names = {r.name for r in res.records}
    assert "good" in names
    assert "bad" not in names
    assert res.degraded == "parse-error"


def test_extract_flags_parse_error_for_error_outside_every_def():
    res = _py("x = (\ndef ok():\n    pass\n")
    names = {r.name for r in res.records}
    assert "ok" in names
    assert res.degraded == "parse-error"


def test_extract_class_with_clean_method_a_and_broken_method_b_emits_class_and_a():
    res = _py("class C:\n    def a(self):\n        pass\n    def b(self,:\n        pass\n")
    k = _triples(res)
    assert ("C", "class", None) in k
    assert ("a", "method", "C") in k
    assert "b" not in {r.name for r in res.records}
    assert res.degraded == "parse-error"


def test_extract_method_with_broken_local_def_still_emitted_full_range():
    res = _py(
        "class C:\n    def m(self):\n        def local(:\n            pass\n        return 1\n"
    )
    names = {r.name for r in res.records}
    assert "m" in names  # nested error excluded from m's own region
    assert "local" not in names  # function-local def not extracted
    assert "C" in names
    assert res.degraded == "parse-error"


def test_extract_grammar_missing_yields_zero_records_flagged_grammar_missing():
    def parser_for(_language):
        raise GrammarMissing("tree-sitter-python")

    res = extract_symbols("m.py", "python", b"def x(): pass", parser_for=parser_for)
    assert res.records == []
    assert res.degraded == "grammar-missing"


def test_extract_grammar_load_error_yields_zero_records_flagged_grammar_missing():
    def parser_for(_language):
        raise GrammarLoadError("tree-sitter-go", "abi15")

    res = extract_symbols("m.go", "go", b"package m", parser_for=parser_for)
    assert res.records == []
    assert res.degraded == "grammar-missing"


def test_extract_clean_file_degraded_is_none():
    assert _py("def x():\n    pass\n").degraded is None
