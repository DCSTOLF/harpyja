"""RED (task 10): result dataclasses (SPEC §2.1) + the wave-0 locate stub.

AC5 — harpyja_locate returns a schema-valid EMPTY LocateResult: empty citations,
a confidence flag, no retrieval, no exception, for any arguments.
"""

from dataclasses import fields

from harpyja.server.tools import locate_stub
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
    # Citation extends CodeSpan and adds three fields.
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


def test_locate_stub_returns_empty_citations():
    result = locate_stub(query="anything", repo_path="/tmp/repo")
    assert isinstance(result, LocateResult)
    assert result.citations == []


def test_locate_stub_confidence_is_low():
    result = locate_stub(query="q", repo_path="/tmp/repo")
    assert result.confidence == "low"


def test_locate_stub_tiers_run_empty_and_notes_set():
    result = locate_stub(query="q", repo_path="/tmp/repo")
    assert result.tiers_run == []
    assert result.notes == "wave-0 stub: no retrieval"


def test_locate_stub_accepts_arbitrary_args_no_exception():
    # Every documented input field, plus odd values — never raises, never searches.
    result = locate_stub(
        query="trace the webhook signature check",
        repo_path="/does/not/exist",
        mode="deep",
        max_results=50,
        language_hint="go",
    )
    assert result.citations == []
    assert result.confidence in {"high", "medium", "low"}
