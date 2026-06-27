"""RED (task 8): language classification by extension (AC5)."""

from harpyja.index.classify import classify_language


def test_classify_python_extension():
    assert classify_language("src/a.py") == "python"


def test_classify_go_extension():
    assert classify_language("cmd/main.go") == "go"


def test_classify_unknown_extension_is_none():
    assert classify_language("data/blob.xyz") is None


def test_classify_extensionless_is_none():
    assert classify_language("bin/run") is None


# --- Tier A: Rust, Java, C# (0004 AC1-3, AC8) ---


def test_classify_rust_extension():
    assert classify_language("src/lib.rs") == "rust"


def test_classify_java_extension():
    assert classify_language("src/Main.java") == "java"


def test_classify_csharp_extension():
    assert classify_language("src/Program.cs") == "csharp"


# --- Tier B: JavaScript, TypeScript, TSX (0004 AC4, AC5, AC8) ---


def test_classify_js_mjs_cjs_jsx_route_to_javascript():
    for ext in (".js", ".mjs", ".cjs", ".jsx"):
        assert classify_language("src/a" + ext) == "javascript"


def test_classify_ts_routes_to_typescript():
    assert classify_language("src/a.ts") == "typescript"


def test_classify_tsx_routes_to_tsx_not_typescript():
    # The corrected mapping: .tsx → the tsx grammar, not the typescript grammar.
    assert classify_language("src/App.tsx") == "tsx"


# --- Tier C: C, C++ (0004 AC6, AC7, AC8) ---


def test_classify_c_and_h_route_to_c():
    assert classify_language("src/a.c") == "c"
    assert classify_language("src/a.h") == "c"  # documented .h→C default


def test_classify_cpp_sources_and_headers_route_to_cpp():
    for ext in (".cc", ".cpp", ".cxx", ".c++"):
        assert classify_language("src/a" + ext) == "cpp"
    for ext in (".hpp", ".hh", ".hxx", ".h++"):
        assert classify_language("src/a" + ext) == "cpp"


def test_classify_unmapped_mts_cts_remain_null_language():
    assert classify_language("src/a.mts") is None
    assert classify_language("src/a.cts") is None
