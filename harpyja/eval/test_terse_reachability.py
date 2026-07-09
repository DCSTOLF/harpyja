"""spec 0036 — mechanical lexical-reachability classifier (AC2, OQ2).

Operator-side, post-authoring: classifies whether the gold span is findable by
the query's own code-like vocabulary (`lexical`) or only by structural/conceptual
navigation (`conceptual`). Computes over gold-span text, so it must stay
structurally outside the product runtime (no `ModelGateway`) — pinned by the same
ast import-absence guard as `terse_authoring`.
"""

from __future__ import annotations

import ast

from harpyja.eval import terse_reachability
from harpyja.eval.terse_reachability import (
    HAND_LABELED,
    MECHANICAL,
    classify_reachability,
)


def _imported_modules_of(module) -> set[str]:
    with open(module.__file__, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
    return names


def test_classify_reachability_lexical_when_span_contains_query_token():
    # The query's code-like identifier ("separability_matrix") appears in the gold
    # span text — grep on the query's own vocabulary can reach the gold.
    query = "separability_matrix returns wrong result for nested models"
    span_text = "def separability_matrix(transform):\n    return _separable(transform)\n"
    assert classify_reachability(query, span_text) == "lexical"


def test_classify_reachability_conceptual_when_no_shared_code_token():
    # No code-like query token appears in the gold span: plain-English overlap
    # ("models", "wrong") must NOT count — that is the RETRIEVAL_FUNDAMENTAL trap.
    query = "nested compound models report wrong separability"
    span_text = "def _cstack(left, right):\n    noutp = _compute_n_outputs(left, right)\n"
    assert classify_reachability(query, span_text) == "conceptual"


def test_classify_reachability_conceptual_when_query_has_no_code_tokens():
    # A purely prose query has no code-like vocabulary at all — nothing for a
    # lexical tool to anchor on, regardless of span content.
    query = "why does the matrix come out wrong for nested models"
    span_text = "def separability_matrix(transform):\n    ...\n"
    assert classify_reachability(query, span_text) == "conceptual"


def test_reachability_provenance_constants():
    # The per-case tag provenance enums match the dataset loader's validation.
    from harpyja.eval.dataset import REACHABILITY_PROVENANCES

    assert MECHANICAL == "mechanical"
    assert HAND_LABELED == "hand-labeled"
    assert {MECHANICAL, HAND_LABELED} == set(REACHABILITY_PROVENANCES)


def test_reachability_module_is_not_product_runtime():
    # Non-product posture (0026): the classifier computes over gold spans and must
    # be structurally unreachable from the SUT — no gateway import, pure stdlib +
    # eval-internal imports only.
    imported = _imported_modules_of(terse_reachability)
    assert not any("gateway" in m for m in imported)
    assert not any(m.startswith("harpyja.scout") for m in imported)
    assert not any(m.startswith("harpyja.deep") for m in imported)
