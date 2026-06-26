"""Result dataclass shapes (SPEC §2.1).

The Wave-0 `locate_stub` is retired in Wave 1 (the MCP `harpyja_locate` tool is
now backed by the Tier-0 orchestrator — see `test_app.py` and
`orchestrator/test_locate.py`). These checks pin the contract data shapes that
every tier produces.
"""

from dataclasses import fields

from harpyja.server.types import Citation, CodeSpan, LocateRequest, LocateResult


def test_locateresult_shape_matches_spec_fields():
    assert [f.name for f in fields(LocateResult)] == [
        "citations",
        "confidence",
        "tiers_run",
        "notes",
    ]


def test_codespan_and_citation_fields_match_spec():
    assert [f.name for f in fields(CodeSpan)] == [
        "path",
        "start_line",
        "end_line",
        "symbol",
        "language",
    ]
    citation_names = [f.name for f in fields(Citation)]
    assert citation_names[:5] == [f.name for f in fields(CodeSpan)]
    assert citation_names[5:] == ["rationale", "source_tier", "score"]


def test_locaterequest_fields_match_spec():
    assert [f.name for f in fields(LocateRequest)] == [
        "query",
        "repo_path",
        "mode",
        "max_results",
        "language_hint",
    ]
