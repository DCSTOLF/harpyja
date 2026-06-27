"""Tree-sitter symbol extraction for Python and Go (AC1-4, AC15).

**Definitions only**, classified by **syntactic form** (no type inference). The
extractor returns per-file `SymbolRecord`s plus a degradation outcome:

- **grammar unavailable** (absent / fails to load) → zero records, `grammar-missing`;
- **parse error** (tree carries `ERROR`/`MISSING`) → a definition is skipped only
  when an error falls in its **own region** (its span excluding the subtrees of any
  nested-definition syntactic form, extracted or not); cleanly-parsed siblings are
  still emitted, and the file is flagged `parse-error` on *any* error node — even
  one outside every definition.

The parser is injectable (`parser_for`) so the grammar-missing / load-error paths
are unit-testable without uninstalling a package. Real parsing is in-process
(no subprocess, no network).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from harpyja.symbols.engine_identity import GrammarLoadError, GrammarMissing

ParserFor = Callable[[str], object]

# Syntactic forms that introduce a nested scope; excluded from an enclosing
# definition's "own region" when scoping parse errors (D4), and never descended
# into for further top-level/member extraction.
_PY_NESTED = frozenset({"function_definition", "class_definition", "decorated_definition"})
_GO_NESTED = frozenset(
    {
        "function_declaration",
        "method_declaration",
        "func_literal",
        "type_declaration",
        "const_declaration",
        "var_declaration",
    }
)
_RUST_NESTED = frozenset(
    {
        "function_item",
        "function_signature_item",
        "impl_item",
        "struct_item",
        "enum_item",
        "trait_item",
        "type_item",
        "const_item",
        "static_item",
        "closure_expression",
    }
)

DEGRADED_PARSE_ERROR = "parse-error"
DEGRADED_GRAMMAR_MISSING = "grammar-missing"


@dataclass
class SymbolRecord:
    path: str  # repo-relative
    language: str
    name: str
    kind: str
    parent: str | None
    start_line: int  # 1-indexed, inclusive
    end_line: int


@dataclass
class ExtractResult:
    records: list[SymbolRecord]
    degraded: str | None  # DEGRADED_* or None (clean)


def _default_parser_for(language: str) -> object:
    import tree_sitter

    language_fn = "language"
    if language == "python":
        import tree_sitter_python as grammar
    elif language == "go":
        import tree_sitter_go as grammar
    elif language == "rust":
        import tree_sitter_rust as grammar
    elif language == "java":
        import tree_sitter_java as grammar
    elif language == "csharp":
        import tree_sitter_c_sharp as grammar
    elif language == "javascript":
        import tree_sitter_javascript as grammar
    elif language == "typescript":
        import tree_sitter_typescript as grammar

        language_fn = "language_typescript"
    elif language == "tsx":
        import tree_sitter_typescript as grammar

        language_fn = "language_tsx"
    elif language == "c":
        import tree_sitter_c as grammar
    elif language == "cpp":
        import tree_sitter_cpp as grammar
    else:  # pragma: no cover - guarded by caller
        raise GrammarMissing(language)

    try:
        ts_language = tree_sitter.Language(getattr(grammar, language_fn)())
    except Exception as err:  # ABI / version-skew
        raise GrammarLoadError(language, type(err).__name__) from err
    return tree_sitter.Parser(ts_language)


def extract_symbols(
    path: str,
    language: str,
    source: bytes,
    *,
    parser_for: ParserFor = _default_parser_for,
) -> ExtractResult:
    """Extract definitions from ``source``; never raises on a parser problem."""
    try:
        parser = parser_for(language)
    except (GrammarMissing, GrammarLoadError):
        return ExtractResult(records=[], degraded=DEGRADED_GRAMMAR_MISSING)

    tree = parser.parse(source)
    root = tree.root_node

    records: list[SymbolRecord] = []
    if language == "python":
        _extract_python(root, path, records, parent=None)
    elif language == "go":
        _extract_go(root, path, records)
    elif language == "rust":
        _extract_rust(root, path, records)
    elif language == "java":
        _extract_java(root, path, records, parent=None)
    elif language == "csharp":
        _extract_csharp(root, path, records, parent=None)
    elif language in ("javascript", "typescript", "tsx"):
        _extract_js(root, path, records, language, parent=None)
    elif language in ("c", "cpp"):
        _extract_c_family(root, path, records, language, parent=None)

    degraded = DEGRADED_PARSE_ERROR if root.has_error else None
    return ExtractResult(records=records, degraded=degraded)


def _own_region_errored(node, nested_types: frozenset[str]) -> bool:
    """Does ``node``'s own region (excluding nested-definition subtrees) error?"""
    for child in node.children:
        if child.type == "ERROR" or child.is_missing:
            return True
        if child.type in nested_types:
            continue
        if child.has_error and _own_region_errored(child, nested_types):
            return True
    return False


def _name_text(node) -> str | None:
    field = node.child_by_field_name("name")
    return field.text.decode() if field is not None else None


# --- Python ---


_PY_CONST_RE = None


def _is_upper_snake(name: str) -> bool:
    import re

    global _PY_CONST_RE
    if _PY_CONST_RE is None:
        _PY_CONST_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
    return bool(_PY_CONST_RE.match(name))


def _extract_python(node, path: str, records: list[SymbolRecord], parent: str | None) -> None:
    for child in node.children:
        t = child.type
        if t == "decorated_definition":
            inner = child.child_by_field_name("definition")
            if inner is None:
                _defs = ("function_definition", "class_definition")
                inner = next((c for c in child.children if c.type in _defs), None)
            if inner is not None:
                _emit_python_def(inner, path, records, parent, span=child)
        elif t in ("function_definition", "class_definition"):
            _emit_python_def(child, path, records, parent, span=child)
        elif t == "expression_statement" and parent is None:
            _maybe_python_constant(child, path, records)
        elif t == "block":
            # Class body block — descend keeping the current parent.
            _extract_python(child, path, records, parent)


def _emit_python_def(def_node, path, records, parent, *, span) -> None:
    if _own_region_errored(def_node, _PY_NESTED):
        return
    name = _name_text(def_node)
    if name is None:
        return
    if def_node.type == "class_definition":
        kind = "class"
    else:
        kind = "method" if parent is not None else "function"
    records.append(
        SymbolRecord(
            path=path,
            language="python",
            name=name,
            kind=kind,
            parent=parent,
            start_line=span.start_point[0] + 1,
            end_line=span.end_point[0] + 1,
        )
    )
    if def_node.type == "class_definition":
        body = def_node.child_by_field_name("body")
        if body is not None:
            _extract_python(body, path, records, parent=name)


def _maybe_python_constant(expr_stmt, path, records) -> None:
    assign = next((c for c in expr_stmt.children if c.type == "assignment"), None)
    if assign is None:
        return
    left = assign.child_by_field_name("left")
    right = assign.child_by_field_name("right")
    if left is None or right is None:  # annotation-only `X: int` has no value
        return
    if left.type != "identifier":  # tuple/pattern target excluded
        return
    name = left.text.decode()
    if not _is_upper_snake(name):
        return
    records.append(
        SymbolRecord(
            path=path,
            language="python",
            name=name,
            kind="constant",
            parent=None,
            start_line=expr_stmt.start_point[0] + 1,
            end_line=expr_stmt.end_point[0] + 1,
        )
    )


# --- Go ---


def _extract_go(root, path: str, records: list[SymbolRecord]) -> None:
    for child in root.children:
        t = child.type
        if t == "function_declaration":
            _emit_go(child, path, records, kind="function", parent=None)
        elif t == "method_declaration":
            _emit_go(child, path, records, kind="method", parent=_go_receiver_parent(child))
        elif t == "type_declaration":
            _extract_go_types(child, path, records)
        elif t == "const_declaration":
            _extract_go_value_specs(child, path, records, kind="const", spec="const_spec")
        elif t == "var_declaration":
            _extract_go_value_specs(child, path, records, kind="var", spec="var_spec")


def _emit_go(node, path, records, *, kind, parent) -> None:
    if _own_region_errored(node, _GO_NESTED):
        return
    name = _name_text(node)
    if name is None:
        return
    records.append(
        SymbolRecord(
            path=path,
            language="go",
            name=name,
            kind=kind,
            parent=parent,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
        )
    )


def _extract_go_types(type_decl, path, records) -> None:
    for spec in type_decl.children:
        if spec.type not in ("type_spec", "type_alias"):
            continue
        if _own_region_errored(spec, _GO_NESTED):
            continue
        name = _name_text(spec)
        if name is None:
            continue
        type_node = spec.child_by_field_name("type")
        kind = "type"
        if type_node is not None:
            if type_node.type == "struct_type":
                kind = "struct"
            elif type_node.type == "interface_type":
                kind = "interface"
        records.append(
            SymbolRecord(
                path=path,
                language="go",
                name=name,
                kind=kind,
                parent=None,
                start_line=spec.start_point[0] + 1,
                end_line=spec.end_point[0] + 1,
            )
        )


def _extract_go_value_specs(decl, path, records, *, kind, spec) -> None:
    for s in decl.children:
        if s.type != spec:
            continue
        if _own_region_errored(s, _GO_NESTED):
            continue
        for name_node in s.children_by_field_name("name"):
            records.append(
                SymbolRecord(
                    path=path,
                    language="go",
                    name=name_node.text.decode(),
                    kind=kind,
                    parent=None,
                    start_line=s.start_point[0] + 1,
                    end_line=s.end_point[0] + 1,
                )
            )


def _go_receiver_parent(method_node) -> str | None:
    recv = method_node.child_by_field_name("receiver")
    if recv is None:
        return None
    param = next((c for c in recv.children if c.type == "parameter_declaration"), None)
    if param is None:
        return None
    type_node = param.child_by_field_name("type")
    if type_node is None:
        type_node = next((c for c in param.children if c.type != "identifier" and c.is_named), None)
    return _strip_go_type(type_node) if type_node is not None else None


def _strip_go_type(node) -> str | None:
    cur = node
    while cur is not None:
        if cur.type == "pointer_type":
            cur = next((c for c in cur.children if c.is_named), None)
        elif cur.type == "generic_type":
            base = cur.child_by_field_name("type")
            cur = base or next((c for c in cur.children if c.is_named), None)
        else:
            break
    return cur.text.decode() if cur is not None else None


# --- Rust ---


_RUST_TYPE_KINDS = {
    "struct_item": "struct",
    "enum_item": "enum",
    "trait_item": "trait",
    "type_item": "type",
}


def _emit_rust(node, path, records, *, kind, parent, name=None) -> None:
    if _own_region_errored(node, _RUST_NESTED):
        return
    name = name if name is not None else _name_text(node)
    if name is None:
        return
    records.append(
        SymbolRecord(
            path=path,
            language="rust",
            name=name,
            kind=kind,
            parent=parent,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
        )
    )


def _extract_rust(root, path: str, records: list[SymbolRecord]) -> None:
    for child in root.children:
        t = child.type
        if t == "function_item":
            _emit_rust(child, path, records, kind="function", parent=None)
        elif t in _RUST_TYPE_KINDS:
            _emit_rust(child, path, records, kind=_RUST_TYPE_KINDS[t], parent=None)
        elif t in ("const_item", "static_item"):
            name = _name_text(child)
            if name is not None and _is_upper_snake(name):
                _emit_rust(child, path, records, kind="constant", parent=None, name=name)
        elif t == "impl_item":
            _extract_rust_impl(child, path, records)


def _extract_rust_impl(impl_node, path, records) -> None:
    parent = _strip_go_type(impl_node.child_by_field_name("type"))
    body = impl_node.child_by_field_name("body")
    if parent is None or body is None:
        return
    for member in body.children:
        if member.type == "function_item":
            _emit_rust(member, path, records, kind="method", parent=parent)


# --- Shared emit (Java / C# / C-family: descend type bodies, never method bodies) ---


def _emit_named(node, path, records, *, language, kind, parent, nested, name=None) -> str | None:
    """Emit one record; skip if the node's own region (excl. nested defs) errored."""
    if _own_region_errored(node, nested):
        return None
    name = name if name is not None else _name_text(node)
    if name is None:
        return None
    records.append(
        SymbolRecord(
            path=path,
            language=language,
            name=name,
            kind=kind,
            parent=parent,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
        )
    )
    return name


# --- Java ---


_JAVA_NESTED = frozenset(
    {
        "class_declaration",
        "interface_declaration",
        "enum_declaration",
        "record_declaration",
        "method_declaration",
        "constructor_declaration",
        "lambda_expression",
    }
)
_JAVA_TYPE_KINDS = {
    "class_declaration": "class",
    "interface_declaration": "interface",
    "enum_declaration": "enum",
}


def _extract_java(node, path: str, records: list[SymbolRecord], parent: str | None) -> None:
    for child in node.children:
        t = child.type
        if t in _JAVA_TYPE_KINDS:
            name = _emit_named(
                child,
                path,
                records,
                language="java",
                kind=_JAVA_TYPE_KINDS[t],
                parent=parent,
                nested=_JAVA_NESTED,
            )
            body = child.child_by_field_name("body")
            if name is not None and body is not None:
                _extract_java(body, path, records, parent=name)
        elif t == "method_declaration":
            _emit_named(
                child,
                path,
                records,
                language="java",
                kind="method",
                parent=parent,
                nested=_JAVA_NESTED,
            )


# --- C# ---


_CSHARP_NESTED = frozenset(
    {
        "class_declaration",
        "struct_declaration",
        "interface_declaration",
        "enum_declaration",
        "record_declaration",
        "namespace_declaration",
        "method_declaration",
        "constructor_declaration",
        "local_function_statement",
        "lambda_expression",
    }
)
_CSHARP_TYPE_KINDS = {
    "class_declaration": "class",
    "struct_declaration": "struct",
    "interface_declaration": "interface",
    "enum_declaration": "enum",
}


def _extract_csharp(node, path: str, records: list[SymbolRecord], parent: str | None) -> None:
    for child in node.children:
        t = child.type
        if t in ("namespace_declaration", "file_scoped_namespace_declaration"):
            # Container: descend without emitting and without changing parent.
            body = child.child_by_field_name("body")
            if body is not None:
                _extract_csharp(body, path, records, parent)
        elif t in _CSHARP_TYPE_KINDS:
            name = _emit_named(
                child,
                path,
                records,
                language="csharp",
                kind=_CSHARP_TYPE_KINDS[t],
                parent=parent,
                nested=_CSHARP_NESTED,
            )
            body = child.child_by_field_name("body")
            if name is not None and body is not None:
                _extract_csharp(body, path, records, parent=name)
        elif t == "method_declaration":
            _emit_named(
                child,
                path,
                records,
                language="csharp",
                kind="method",
                parent=parent,
                nested=_CSHARP_NESTED,
            )


# --- JavaScript / TypeScript / TSX ---


_JS_NESTED = frozenset(
    {
        "function_declaration",
        "generator_function_declaration",
        "function_expression",
        "arrow_function",
        "class_declaration",
        "method_definition",
    }
)
_TS_TYPE_KINDS = {
    "interface_declaration": "interface",
    "type_alias_declaration": "type",
    "enum_declaration": "enum",
}


def _is_const_declaration(node) -> bool:
    return any(c.type == "const" for c in node.children if not c.is_named)


def _extract_js(node, path: str, records: list[SymbolRecord], language: str, parent) -> None:
    for child in node.children:
        _extract_js_node(child, path, records, language, parent)


def _extract_js_node(child, path, records, language, parent) -> None:
    t = child.type
    if t in ("function_declaration", "generator_function_declaration"):
        _emit_named(
            child,
            path,
            records,
            language=language,
            kind="function",
            parent=parent,
            nested=_JS_NESTED,
        )
    elif t == "class_declaration":
        name = _emit_named(
            child,
            path,
            records,
            language=language,
            kind="class",
            parent=parent,
            nested=_JS_NESTED,
        )
        body = child.child_by_field_name("body")
        if name is not None and body is not None:
            _extract_js(body, path, records, language, parent=name)
    elif t == "method_definition" and parent is not None:
        _emit_named(
            child,
            path,
            records,
            language=language,
            kind="method",
            parent=parent,
            nested=_JS_NESTED,
        )
    elif t == "lexical_declaration" and parent is None and _is_const_declaration(child):
        _emit_js_constants(child, path, records, language)
    elif t == "export_statement":
        decl = child.child_by_field_name("declaration")
        if decl is not None:
            _extract_js_node(decl, path, records, language, parent)
    elif language in ("typescript", "tsx") and t in _TS_TYPE_KINDS:
        _emit_named(
            child,
            path,
            records,
            language=language,
            kind=_TS_TYPE_KINDS[t],
            parent=parent,
            nested=_JS_NESTED,
        )


def _emit_js_constants(decl, path, records, language) -> None:
    for d in decl.children:
        if d.type != "variable_declarator":
            continue
        name_node = d.child_by_field_name("name")
        if name_node is None or name_node.type != "identifier":
            continue
        name = name_node.text.decode()
        if not _is_upper_snake(name):
            continue
        records.append(
            SymbolRecord(
                path=path,
                language=language,
                name=name,
                kind="constant",
                parent=None,
                start_line=decl.start_point[0] + 1,
                end_line=decl.end_point[0] + 1,
            )
        )


# --- C / C++ ---


_C_NESTED = frozenset(
    {
        "function_definition",
        "struct_specifier",
        "union_specifier",
        "enum_specifier",
        "type_definition",
    }
)
_CPP_NESTED = _C_NESTED | frozenset(
    {
        "class_specifier",
        "namespace_definition",
        "alias_declaration",
        "lambda_expression",
        "template_declaration",
    }
)
_C_TYPE_SPECIFIERS = {
    "struct_specifier": "struct",
    "union_specifier": "union",
    "enum_specifier": "enum",
    "class_specifier": "class",
}


def _c_declarator_name(declarator):
    """Walk a (possibly pointer/reference-wrapped) declarator to its name node."""
    cur = declarator
    while cur is not None:
        t = cur.type
        if t == "function_declarator":
            cur = cur.child_by_field_name("declarator")
        elif t in ("pointer_declarator", "reference_declarator", "parenthesized_declarator"):
            cur = cur.child_by_field_name("declarator") or next(
                (c for c in cur.children if c.is_named), None
            )
        else:
            return cur
    return None


def _extract_c_family(node, path: str, records: list[SymbolRecord], language: str, parent) -> None:
    nested = _CPP_NESTED if language == "cpp" else _C_NESTED
    for child in node.children:
        t = child.type
        if t == "function_definition":
            _emit_c_function(child, path, records, language, parent, nested)
        elif t in _C_TYPE_SPECIFIERS and (language == "cpp" or t != "class_specifier"):
            _emit_c_type(child, path, records, language, parent, nested)
        elif t == "type_definition":
            _emit_c_typedef(child, path, records, language, parent, nested)
        elif t in ("field_declaration", "declaration"):
            # A nested/embedded type definition (`struct Inner {...};`) is carried
            # as the `type` of a field/declaration; emit it when it is a real
            # named+bodied definition (not a forward decl or a variable of that type).
            _emit_c_embedded_type(child, path, records, language, parent, nested)
        elif language == "cpp" and t == "alias_declaration":
            _emit_named(
                child,
                path,
                records,
                language="cpp",
                kind="type",
                parent=parent,
                nested=nested,
            )
        elif language == "cpp" and t == "namespace_definition":
            body = child.child_by_field_name("body")
            if body is not None:
                _extract_c_family(body, path, records, language, parent)


def _emit_c_function(func_def, path, records, language, parent, nested) -> None:
    if _own_region_errored(func_def, nested):
        return
    name_node = _c_declarator_name(func_def.child_by_field_name("declarator"))
    if name_node is None:
        return
    if name_node.type == "qualified_identifier":
        # Out-of-line member definition `Ret Scope::name(...)`.
        scope = name_node.child_by_field_name("scope")
        name_inner = name_node.child_by_field_name("name")
        method_parent = scope.text.decode() if scope is not None else parent
        name = name_inner.text.decode() if name_inner is not None else None
        kind = "method"
    else:
        name = name_node.text.decode()
        kind = "method" if parent is not None else "function"
        method_parent = parent
    if name is None:
        return
    records.append(
        SymbolRecord(
            path=path,
            language=language,
            name=name,
            kind=kind,
            parent=method_parent,
            start_line=func_def.start_point[0] + 1,
            end_line=func_def.end_point[0] + 1,
        )
    )


def _emit_c_embedded_type(decl, path, records, language, parent, nested) -> None:
    spec = decl.child_by_field_name("type")
    if spec is None or spec.type not in _C_TYPE_SPECIFIERS:
        return
    if spec.type == "class_specifier" and language != "cpp":
        return
    if spec.child_by_field_name("name") is None or spec.child_by_field_name("body") is None:
        return
    _emit_c_type(spec, path, records, language, parent, nested)


def _emit_c_type(spec, path, records, language, parent, nested) -> None:
    name_node = spec.child_by_field_name("name")
    body = spec.child_by_field_name("body")
    if name_node is None or body is None:  # anonymous or forward declaration
        return
    name = _emit_named(
        spec,
        path,
        records,
        language=language,
        kind=_C_TYPE_SPECIFIERS[spec.type],
        parent=parent,
        nested=nested,
        name=name_node.text.decode(),
    )
    if name is not None:
        _extract_c_family(body, path, records, language, parent=name)


def _emit_c_typedef(type_def, path, records, language, parent, nested) -> None:
    if _own_region_errored(type_def, nested):
        return
    # A named struct/union/enum carried by the typedef is itself a definition.
    type_spec = type_def.child_by_field_name("type")
    if (
        type_spec is not None
        and type_spec.type in _C_TYPE_SPECIFIERS
        and type_spec.child_by_field_name("name") is not None
        and type_spec.child_by_field_name("body") is not None
    ):
        _emit_c_type(type_spec, path, records, language, parent, nested)
    # The alias itself (one record per declarator name).
    for d in type_def.children_by_field_name("declarator"):
        name_node = d if d.type == "type_identifier" else _c_declarator_name(d)
        if name_node is None:
            continue
        records.append(
            SymbolRecord(
                path=path,
                language=language,
                name=name_node.text.decode(),
                kind="type",
                parent=parent,
                start_line=type_def.start_point[0] + 1,
                end_line=type_def.end_point[0] + 1,
            )
        )
