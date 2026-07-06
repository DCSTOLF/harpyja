"""spec 0026 AC2 layer (b) — the OFFLINE two-model blind-authoring tool.

Author and verifier are INJECTED callables (separately-invoked model contexts, the
operator cross-model seam) — never the product `ModelGateway`. The tool withholds the
gold span from the author, records loud provenance, and routes a leaky verdict to
re-author/drop (never a silent keep). An ast import-absence guard pins the module as
OFFLINE operator/dev code, not Harpyja runtime.
"""

from __future__ import annotations

import ast

from harpyja.eval.terse_authoring import author_terse_set


def _raw_case(case_id="astropy__astropy-12907") -> dict:
    return {
        "case_id": case_id,
        "query": (
            "nested compound models report the wrong separability matrix when nested; "
            "the outputs stop being independent"
        ),
        "repo": "astropy/astropy",
        "expected_spans": [
            {"path": "astropy/modeling/separable.py", "start_line": 242, "end_line": 248}
        ],
        "base_commit": "d16bfe05a744909de4b27f5875fe0d4ed41ce607",
    }


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


def test_authoring_tool_uses_injected_seam_and_produces_case_and_record():
    author_calls: list[str] = []
    verifier_calls: list[str] = []

    def author_invoke(prompt: str) -> str:
        author_calls.append(prompt)
        return "why do nested compound models lose separability"

    def verifier_invoke(prompt: str) -> str:
        verifier_calls.append(prompt)
        return "clean"

    cases, artifact = author_terse_set(
        [_raw_case()],
        author_invoke=author_invoke,
        verifier_invoke=verifier_invoke,
        author_model="model-A",
        verifier_model="model-B",
    )
    assert len(cases) == 1
    c = cases[0]
    assert c.gold_withheld is True
    assert c.query_provenance == "model-authored-blind"
    assert c.query == "why do nested compound models lose separability"
    # both models were invoked separately (state-level independence)
    assert len(author_calls) == 1 and len(verifier_calls) == 1
    assert artifact.records[0].author_model == "model-A"
    assert artifact.records[0].verifier_model == "model-B"
    assert artifact.records[0].outcome == "kept"
    assert artifact.leaky_count == 0 and artifact.dropped_count == 0


def test_authoring_tool_withholds_gold_span_from_author():
    seen: list[str] = []

    def author_invoke(prompt: str) -> str:
        seen.append(prompt)
        return "terse query about nested models"

    author_terse_set(
        [_raw_case()],
        author_invoke=author_invoke,
        verifier_invoke=lambda p: "clean",
        author_model="A",
        verifier_model="B",
    )
    # The author never saw the gold span path (pin 2, end-to-end).
    assert "astropy/modeling/separable.py" not in seen[0]


def test_leaky_verdict_routes_to_drop_never_silent():
    cases, artifact = author_terse_set(
        [_raw_case()],
        author_invoke=lambda p: "a query that secretly names the gold file",
        verifier_invoke=lambda p: "leaky",
        author_model="A",
        verifier_model="B",
    )
    assert cases == []  # a leaky case is not kept
    assert artifact.leaky_count == 1
    assert artifact.dropped_count == 1
    assert artifact.records[0].outcome == "dropped"
    assert artifact.records[0].verifier_verdict == "leaky"


def test_authoring_module_is_not_product_runtime():
    import harpyja.eval.terse_authoring as ta

    imported = _imported_modules_of(ta)
    # Uses the operator cross-model seam, NOT the product ModelGateway.
    assert not any("gateway" in m.lower() for m in imported)
    assert "harpyja.gateway" not in imported

    # No product runtime module imports the offline authoring tool.
    import harpyja.orchestrator.locate as loc
    import harpyja.scout.wiring as wiring

    for prod in (loc, wiring):
        assert "harpyja.eval.terse_authoring" not in _imported_modules_of(prod)
