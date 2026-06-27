"""Tests for the tree-sitter symbol extractor (AC1, AC2, AC4, AC15).

Defs-only, classified by syntactic form. Parsing uses the real (in-process)
grammars; the grammar-missing / load-error paths are exercised by injecting a
`parser_for` seam, never by uninstalling a package.
"""

from __future__ import annotations

import pytest

from harpyja.symbols.engine_identity import GrammarLoadError, GrammarMissing
from harpyja.symbols.extract import ExtractResult, SymbolRecord, extract_symbols


def _py(src: str, path: str = "m.py") -> ExtractResult:
    return extract_symbols(path, "python", src.encode())


def _go(src: str, path: str = "m.go") -> ExtractResult:
    return extract_symbols(path, "go", src.encode())


def _rust(src: str, path: str = "m.rs") -> ExtractResult:
    return extract_symbols(path, "rust", src.encode())


def _java(src: str, path: str = "M.java") -> ExtractResult:
    return extract_symbols(path, "java", src.encode())


def _csharp(src: str, path: str = "M.cs") -> ExtractResult:
    return extract_symbols(path, "csharp", src.encode())


def _js(src: str, path: str = "m.js") -> ExtractResult:
    return extract_symbols(path, "javascript", src.encode())


def _ts(src: str, path: str = "m.ts") -> ExtractResult:
    return extract_symbols(path, "typescript", src.encode())


def _tsx(src: str, path: str = "m.tsx") -> ExtractResult:
    return extract_symbols(path, "tsx", src.encode())


def _c(src: str, path: str = "m.c") -> ExtractResult:
    return extract_symbols(path, "c", src.encode())


def _cpp(src: str, path: str = "m.cpp") -> ExtractResult:
    return extract_symbols(path, "cpp", src.encode())


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


# --- Rust kind vocabulary (0004 AC1) ---


def test_extract_rust_function_method_struct_enum_trait_type():
    res = _rust(
        "fn top() {}\n"
        "struct Foo { x: i32 }\n"
        "enum E { A, B }\n"
        "trait T { fn sig(&self); }\n"
        "type Alias = i32;\n"
        "impl Foo { fn meth(&self) {} }\n"
    )
    k = _triples(res)
    assert ("top", "function", None) in k
    assert ("Foo", "struct", None) in k
    assert ("E", "enum", None) in k
    assert ("T", "trait", None) in k
    assert ("Alias", "type", None) in k
    assert ("meth", "method", "Foo") in k


def test_extract_rust_const_and_static_emit_constant_kind_upper_snake_only():
    res = _rust("const MAX: i32 = 1;\nstatic GLOBAL: i32 = 2;\n")
    k = _triples(res)
    assert ("MAX", "constant", None) in k
    assert ("GLOBAL", "constant", None) in k


def test_extract_rust_lowercase_or_function_local_const_yields_no_record():
    res = _rust("const lower: i32 = 1;\nfn f() { const INNER: i32 = 2; }\n")
    consts = {r.name for r in res.records if r.kind == "constant"}
    assert consts == set()


def test_extract_rust_impl_and_generic_impl_both_parent_foo():
    res = _rust("impl Foo { fn a(&self) {} }\nimpl<T> Foo<T> { fn b(&self) {} }\n")
    methods = {(r.name, r.parent) for r in res.records if r.kind == "method"}
    assert ("a", "Foo") in methods
    assert ("b", "Foo") in methods


def test_extract_rust_impl_trait_for_foo_method_parent_foo():
    res = _rust("impl MyTrait for Foo { fn m(&self) {} }\n")
    assert ("m", "method", "Foo") in _triples(res)


def test_extract_rust_skips_use_call_sites_and_function_local_fn():
    res = _rust("use std::io;\nfn outer() {\n    fn inner() {}\n    do_call();\n}\n")
    names = {r.name for r in res.records}
    assert "outer" in names
    assert "inner" not in names
    assert "io" not in names
    assert "do_call" not in names


def test_extract_rust_record_range_one_indexed_inclusive():
    res = _rust("fn top() {\n}\n")
    rec = next(r for r in res.records if r.name == "top")
    assert rec.start_line == 1
    assert rec.end_line == 2


# --- Java kind vocabulary + nesting (0004 AC2) ---


def test_extract_java_class_interface_enum_and_method_parent():
    res = _java("class C { void m() {} }\ninterface I { void f(); }\nenum E { A, B }\n")
    k = _triples(res)
    assert ("C", "class", None) in k
    assert ("I", "interface", None) in k
    assert ("E", "enum", None) in k
    assert ("m", "method", "C") in k
    assert ("f", "method", "I") in k


def test_extract_java_toplevel_type_parent_null_and_method_never_null():
    res = _java("class C { void m() {} }\n")
    for r in res.records:
        if r.kind == "method":
            assert r.parent is not None
        if r.kind == "class":
            assert r.parent is None


def test_extract_java_nested_inner_class_extracted_with_parent():
    res = _java("class Outer { class Inner { } }\n")
    assert ("Inner", "class", "Outer") in _triples(res)


def test_extract_java_inner_class_method_parent_is_inner_type():
    res = _java("class Outer { class Inner { void im() {} } }\n")
    assert ("im", "method", "Inner") in _triples(res)


def test_extract_java_method_body_local_class_not_extracted():
    res = _java("class C { void withLocal() { class L {} } }\n")
    names = {r.name for r in res.records}
    assert "L" not in names
    assert "withLocal" in names


def test_extract_java_skips_fields_imports_and_call_sites():
    res = _java("import a.b.C;\nclass C { int field; void m() { other(); } }\n")
    names = {r.name for r in res.records}
    assert "field" not in names
    assert "other" not in names
    assert names == {"C", "m"}


# --- C# kind vocabulary + nesting (0004 AC3) ---


def test_extract_csharp_class_struct_interface_enum_and_method_parent():
    res = _csharp("class C { void M() {} }\nstruct S {}\ninterface I {}\nenum E { A }\n")
    k = _triples(res)
    assert ("C", "class", None) in k
    assert ("S", "struct", None) in k
    assert ("I", "interface", None) in k
    assert ("E", "enum", None) in k
    assert ("M", "method", "C") in k


def test_extract_csharp_nested_type_extracted_with_parent():
    res = _csharp("class Outer { struct Nested {} void M() {} }\n")
    k = _triples(res)
    assert ("Nested", "struct", "Outer") in k
    assert ("M", "method", "Outer") in k


def test_extract_csharp_skips_properties_fields_using_and_namespace_containers():
    res = _csharp(
        "using System;\nnamespace N {\n  class C { int P { get; set; } int f; void M() {} }\n}\n"
    )
    k = _triples(res)
    names = {r.name for r in res.records}
    assert "N" not in names  # namespace container not emitted
    assert "P" not in names  # property excluded
    assert "f" not in names  # field excluded
    assert ("C", "class", None) in k  # parent is null despite the namespace
    assert ("M", "method", "C") in k


# --- Tier A parse-error own-region scoping (0004 AC9c) ---


def test_extract_rust_skips_error_spanned_def_keeps_clean_sibling():
    res = _rust("fn good() {}\nfn bad() { let x = ; }\n")
    names = {r.name for r in res.records}
    assert "good" in names
    assert "bad" not in names
    assert res.degraded == "parse-error"


def test_extract_java_flags_parse_error_on_any_error_node_clean_sibling_kept():
    # Garbage outside every def still flags the file (partialness never silent).
    res = _java("class C { void m() {} }\n@ @ @\n")
    assert ("C", "class", None) in _triples(res)
    assert ("m", "method", "C") in _triples(res)
    assert res.degraded == "parse-error"


def test_extract_java_nested_broken_method_keeps_enclosing_class_and_sibling():
    res = _java("class C { void ok() {} void bad( { } }\n")
    names = {r.name for r in res.records}
    assert "C" in names  # enclosing class kept
    assert "ok" in names  # clean sibling kept
    assert "bad" not in names  # broken method skipped
    assert res.degraded == "parse-error"


def test_extract_csharp_parse_error_scoped_to_own_region_excluding_nested():
    # Error inside bad()'s body (a nested method subtree): C and ok survive, bad
    # is skipped, file flagged. The error must sit within a parsed method body so
    # it is excluded from the class's own region.
    res = _csharp("class C { void ok() {} void bad() { int x = ; } }\n")
    names = {r.name for r in res.records}
    assert "C" in names
    assert "ok" in names
    assert "bad" not in names
    assert res.degraded == "parse-error"


# --- JS / TS / TSX kind vocabulary (0004 AC4, AC5) ---


def test_extract_js_function_method_class_and_module_constant():
    res = _js("const MAX = 1;\nfunction top(){}\nclass C { method(){} }\n")
    k = _triples(res)
    assert ("top", "function", None) in k
    assert ("C", "class", None) in k
    assert ("method", "method", "C") in k
    assert ("MAX", "constant", None) in k


def test_extract_js_export_const_upper_snake_included():
    res = _js("export const LIMIT = 2;\n")
    assert ("LIMIT", "constant", None) in _triples(res)


def test_extract_js_export_function_and_class_included():
    res = _js("export function f(){}\nexport class K {}\n")
    k = _triples(res)
    assert ("f", "function", None) in k
    assert ("K", "class", None) in k


def test_extract_js_let_var_destructuring_and_lowercase_const_excluded():
    res = _js("let x = 1;\nvar y = 2;\nconst lower = 3;\nconst [a, b] = arr;\n")
    consts = {r.name for r in res.records if r.kind == "constant"}
    assert consts == set()


def test_extract_ts_additionally_yields_interface_type_alias_and_enum():
    res = _ts("interface I { x: number }\ntype Alias = number;\nenum E { A, B }\n")
    k = _triples(res)
    assert ("I", "interface", None) in k
    assert ("Alias", "type", None) in k
    assert ("E", "enum", None) in k


def test_extract_tsx_jsx_elements_yield_no_records_surrounding_defs_extracted():
    res = _tsx("function App(){ return <div className='x'/>; }\nconst TITLE = 'hi';\n")
    k = _triples(res)
    assert ("App", "function", None) in k
    assert ("TITLE", "constant", None) in k
    # JSX elements are expressions, not definitions.
    assert all(r.kind in ("function", "constant") for r in res.records)


def test_extract_jsx_file_parses_via_javascript_grammar():
    res = extract_symbols("c.jsx", "javascript", b"function C(){ return <a/>; }\n")
    assert ("C", "function", None) in _triples(res)


def test_extract_js_skips_imports_call_sites_and_nested_functions():
    res = _js("import x from 'm';\nfunction outer(){ function inner(){} call(); }\n")
    names = {r.name for r in res.records}
    assert "outer" in names
    assert "inner" not in names
    assert "x" not in names
    assert "call" not in names


def test_extract_ts_skips_error_spanned_def_keeps_clean_sibling():
    res = _ts("function ok(){}\nfunction bad(){ let x = ; }\n")
    names = {r.name for r in res.records}
    assert "ok" in names
    assert "bad" not in names
    assert res.degraded == "parse-error"


def test_extract_tsx_flags_parse_error_on_any_error_node():
    res = _tsx("function App(){ return <div/>; }\n@ @ @\n")
    assert ("App", "function", None) in _triples(res)
    assert res.degraded == "parse-error"


# --- C kind vocabulary + typedef idiom (0004 AC6) ---


def test_extract_c_function_definition_struct_enum_union_and_typedef():
    res = _c(
        "int f(int x){ return x; }\n"
        "struct S { int a; };\n"
        "enum E { A };\n"
        "union U { int a; };\n"
        "typedef int MyInt;\n"
    )
    k = _triples(res)
    assert ("f", "function", None) in k
    assert ("S", "struct", None) in k
    assert ("E", "enum", None) in k
    assert ("U", "union", None) in k
    assert ("MyInt", "type", None) in k


def test_extract_c_bare_prototype_yields_no_record():
    res = _c("int proto(int);\n")
    assert res.records == []


def test_extract_c_typedef_anonymous_struct_single_type_record():
    res = _c("typedef struct { int a; } Foo;\n")
    k = _triples(res)
    assert ("Foo", "type", None) in k
    assert all(r.kind != "struct" for r in res.records)


def test_extract_c_typedef_named_struct_emits_both_struct_and_type_records():
    res = _c("typedef struct Named { int a; } Named;\n")
    k = _triples(res)
    assert ("Named", "struct", None) in k
    assert ("Named", "type", None) in k


# --- C++ kind vocabulary + out-of-line method + nesting (0004 AC7) ---


def test_extract_cpp_function_method_class_struct_enum_union_and_type():
    res = _cpp(
        "int func(){ return 0; }\n"
        "class Foo { void mm(){} };\n"
        "struct S { int a; };\n"
        "enum E { A };\n"
        "union U { int a; };\n"
        "typedef int MyInt;\n"
        "using Alias = int;\n"
    )
    k = _triples(res)
    assert ("func", "function", None) in k
    assert ("Foo", "class", None) in k
    assert ("mm", "method", "Foo") in k
    assert ("S", "struct", None) in k
    assert ("E", "enum", None) in k
    assert ("U", "union", None) in k
    assert ("MyInt", "type", None) in k
    assert ("Alias", "type", None) in k


def test_extract_cpp_out_of_line_method_parent_normalized_to_foo():
    res = _cpp("void Foo::bar(){}\n")
    assert ("bar", "method", "Foo") in _triples(res)


def test_extract_cpp_nested_type_extracted_with_parent_and_inner_methods():
    res = _cpp("class Outer { struct Inner { void im(){} }; };\n")
    k = _triples(res)
    assert ("Outer", "class", None) in k
    assert ("Inner", "struct", "Outer") in k
    assert ("im", "method", "Inner") in k


def test_extract_cpp_prototypes_and_namespace_containers_yield_no_records():
    res = _cpp("namespace N { void proto(); }\n")
    assert res.records == []


# --- C/C++ degradation: .h→C scoped guarantee + preprocessor-mangled (0004 AC8, AC9c) ---


def test_extract_c_header_with_cpp_construct_yields_parse_error_not_crash():
    # A .h parsed under the C grammar with a C++-only construct that the C grammar
    # CANNOT parse reliably errors (a bare `class {}` is, by contrast, tolerated and
    # misparsed by tree-sitter-c — which is exactly why the spec scopes this
    # guarantee to "when an ERROR/MISSING node is present" and the fixture must use
    # syntax that reliably triggers one, here a `template`).
    res = extract_symbols(
        "widget.h", "c", b"template<typename T> struct Tmpl { T x; };\nint ok(){ return 0; }\n"
    )
    assert res.degraded == "parse-error"  # degrades, never crashes
    names = {r.name for r in res.records}
    assert "Tmpl" not in names  # error-spanned def not emitted
    assert "ok" in names  # clean sibling still emitted


def test_extract_c_preprocessor_mangled_region_degrades_parse_error():
    res = _c("int ok(){ return 0; }\nint bad() { M( ; }\n")
    assert res.degraded == "parse-error"
    assert ("ok", "function", None) in _triples(res)


def test_extract_c_error_spanned_def_skipped_clean_sibling_kept():
    res = _c("int ok(){ return 0; }\nint bad(){ int x = ; }\n")
    names = {r.name for r in res.records}
    assert "ok" in names
    assert "bad" not in names
    assert res.degraded == "parse-error"


# --- Absent / load-error per new grammar via the injected seam (0004 AC9a, AC9b) ---


@pytest.mark.parametrize(
    "language,path",
    [
        ("rust", "m.rs"),
        ("java", "M.java"),
        ("csharp", "M.cs"),
        ("javascript", "m.js"),
        ("typescript", "m.ts"),
        ("tsx", "m.tsx"),
        ("c", "m.c"),
        ("cpp", "m.cpp"),
    ],
)
def test_extract_absent_grammar_yields_zero_records_grammar_missing(language, path):
    def parser_for(_language):
        raise GrammarMissing("tree-sitter-" + language)

    res = extract_symbols(path, language, b"// src", parser_for=parser_for)
    assert res.records == []
    assert res.degraded == "grammar-missing"


def test_extract_load_error_new_grammar_yields_grammar_missing():
    def parser_for(_language):
        raise GrammarLoadError("tree-sitter-rust", "abi15")

    res = extract_symbols("m.rs", "rust", b"fn f(){}", parser_for=parser_for)
    assert res.records == []
    assert res.degraded == "grammar-missing"
