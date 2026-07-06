"""RED (T7, AC6): the tool-call-native `submit_citations` terminal action.

The model ends the loop by calling `submit_citations` with STRUCTURED args (not by
emitting free text to be regexed — the FastContext-era `<final_answer>` grammar is
retired). Its args validate under a STRICT schema: unknown/extra fields — including
any diagnosis-shaped field — fail schema (the enforceable form of the
locator-not-diagnoser guard). Semantically bad refs (out-of-repo / nonexistent /
over-budget / malformed range) are DROPPED by the existing `normalize_spans`, never
propagated. An empty well-formed submission is honest-empty, not an error.
"""

import inspect

import pytest

from harpyja.config.settings import Settings
from harpyja.orchestrator.format import format_citations
from harpyja.scout.submit import SubmitCitationsSchemaError, submit_citations
from harpyja.server.types import CodeSpan


def _file(tmp_path, rel, n=50):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(f"line {i}" for i in range(1, n + 1)) + "\n", encoding="utf-8")
    return p


def test_submit_citations_returns_normalized_codespans(tmp_path):
    _file(tmp_path, "a.py", n=50)
    out = submit_citations(
        [{"path": "a.py", "start_line": 3, "end_line": 5}], str(tmp_path), Settings()
    )
    assert out == [CodeSpan(path="a.py", start_line=3, end_line=5)]


def test_submit_citations_keeps_file_level_ref(tmp_path):
    _file(tmp_path, "a.py")
    out = submit_citations([{"path": "a.py"}], str(tmp_path), Settings())
    assert out == [CodeSpan(path="a.py", start_line=None, end_line=None)]


def test_submit_citations_drops_out_of_repo_nonexistent_over_budget_malformed(tmp_path):
    _file(tmp_path, "real.py", n=10)
    out = submit_citations(
        [
            {"path": "../../etc/passwd", "start_line": 1, "end_line": 1},  # out-of-repo
            {"path": "ghost.py", "start_line": 1, "end_line": 1},          # nonexistent
            {"path": "real.py", "start_line": 9, "end_line": 2},           # inverted range
            {"path": "real.py", "start_line": 999, "end_line": 1000},      # out-of-range
        ],
        str(tmp_path),
        Settings(),
    )
    assert out == []  # every bad ref dropped, never propagated


def test_submit_citations_strict_schema_rejects_unknown_field(tmp_path):
    with pytest.raises(SubmitCitationsSchemaError):
        submit_citations(
            [{"path": "a.py", "start_line": 1, "end_line": 1, "confidence": 0.9}],
            str(tmp_path),
            Settings(),
        )


def test_submit_citations_diagnosis_shaped_field_fails_schema(tmp_path):
    # A locator does not diagnose: a root_cause/fix/explanation-style field is not a
    # sanctioned citation field, so the strict schema rejects it.
    for bad in ("root_cause", "fix", "explanation", "rationale", "diagnosis"):
        with pytest.raises(SubmitCitationsSchemaError):
            submit_citations(
                [{"path": "a.py", "start_line": 1, "end_line": 1, bad: "text"}],
                str(tmp_path),
                Settings(),
            )


def test_submit_citations_has_no_repo_read_capability():
    # The terminal action is a pure validator: it takes citations + repo_root +
    # settings and NOTHING that reads the repo (no tool bundle, no grep/glob/read).
    params = set(inspect.signature(submit_citations).parameters)
    assert params == {"citations", "repo_root", "settings"}


def test_submit_citations_empty_is_honest_empty_not_error(tmp_path):
    assert submit_citations([], str(tmp_path), Settings()) == []


def test_submit_citations_spans_reach_source_tier_1_via_engine_path(tmp_path):
    # The action returns plain CodeSpans (unstamped); the =1 stamp happens downstream
    # in the UNCHANGED orchestrator path via format_citations(..., source_tier=1).
    _file(tmp_path, "a.py", n=50)
    spans = submit_citations(
        [{"path": "a.py", "start_line": 1, "end_line": 2}], str(tmp_path), Settings()
    )
    cits = format_citations(spans, lambda p: 1.0, 8, source_tier=1)
    assert cits and all(c.source_tier == 1 for c in cits)
