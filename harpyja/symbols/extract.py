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

    if language == "python":
        import tree_sitter_python as grammar
    elif language == "go":
        import tree_sitter_go as grammar
    else:  # pragma: no cover - guarded by caller (only py/go reach here)
        raise GrammarMissing(language)

    try:
        ts_language = tree_sitter.Language(grammar.language())
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
