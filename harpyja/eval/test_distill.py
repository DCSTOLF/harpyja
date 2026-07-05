"""Spec 0023 (AC2) — the dual distiller: unit layer (the honesty guard).

The mechanical distiller is the PRIMARY, verdict-driving arm and must be
*structurally* incapable of manufacturing a false QUERY_SHAPE: its output tokens are a
subset of the issue tokens (extraction, never generation), it strips code-identifier
tokens (so it measures query-shape, not a symbol-lookup shortcut), it is case-agnostic,
and it never sees the gold span. The LLM arm is a labeled sensitivity check guarded by a
post-hoc token-subset hard reject.
"""

from __future__ import annotations

import inspect

import pytest


def _word_tokens(text: str) -> set[str]:
    import re

    return set(re.findall(r"[a-z]+", text.lower()))


# ---- AC2: mechanical distiller is structurally blind -----------------------


def test_mechanical_distill_output_tokens_subset_of_input():
    from harpyja.eval.distill import mechanical_distill

    issue = "The retry backoff handler fails on the second attempt when the queue drains"
    res = mechanical_distill(issue)
    assert _word_tokens(res.query) <= _word_tokens(issue)
    assert res.query  # non-empty NL query


def test_mechanical_distill_strips_file_paths():
    from harpyja.eval.distill import mechanical_distill

    res = mechanical_distill("The path/to/foo.py handler crashes on startup")
    assert "foo.py" not in res.query
    assert "path/to/foo.py" not in res.query
    assert "path/to/foo.py" in res.stripped_tokens


def test_mechanical_distill_strips_dotted_and_camelcase_symbols():
    from harpyja.eval.distill import mechanical_distill

    res = mechanical_distill("The mod.Thing and CamelCase break during teardown")
    assert "mod.Thing" not in res.query
    assert "CamelCase" not in res.query
    assert "mod.Thing" in res.stripped_tokens
    assert "CamelCase" in res.stripped_tokens


def test_mechanical_distill_strips_stack_trace_frames():
    from harpyja.eval.distill import mechanical_distill

    # The trace frame is the first line; if it were NOT removed, the query would carry
    # "file"/"line". Removal leaves the NL summary line as the query source.
    issue = 'File "foo.py", line 10\nWidget fails to render on resize'
    res = mechanical_distill(issue)
    words = res.query.split()
    assert "file" not in words
    assert "line" not in words
    assert "10" not in words


def test_mechanical_distill_strips_exact_error_strings():
    from harpyja.eval.distill import mechanical_distill

    res = mechanical_distill('Crash with message "widget not found" during boot')
    assert "widget" not in res.query
    assert "found" not in res.query


def test_mechanical_distill_records_stripped_tokens():
    from harpyja.eval.distill import mechanical_distill

    res = mechanical_distill("The mod.Thing at path/to/foo.py fails")
    assert len(res.stripped_tokens) >= 2


def test_mechanical_distill_is_case_agnostic():
    from harpyja.eval.distill import mechanical_distill

    text = "The retry backoff handler fails on the second attempt"
    # No case-id parameter exists, and the output is a pure function of the text.
    assert mechanical_distill(text).query == mechanical_distill(text).query
    params = list(inspect.signature(mechanical_distill).parameters)
    assert params == ["issue_text"]


def test_mechanical_distill_ignores_gold_spans():
    from harpyja.eval.distill import mechanical_distill

    params = list(inspect.signature(mechanical_distill).parameters)
    assert params == ["issue_text"]
    for forbidden in ("expected", "gold", "span", "case"):
        assert not any(forbidden in p for p in params)


def test_mechanical_distill_rule_is_prehashed():
    from harpyja.eval.distill import MECHANICAL_RULE_HASH

    assert isinstance(MECHANICAL_RULE_HASH, str)
    assert len(MECHANICAL_RULE_HASH) == 64
    assert all(ch in "0123456789abcdef" for ch in MECHANICAL_RULE_HASH)


# ---- AC2: LLM sensitivity arm subset-reject filter -------------------------


def test_llm_distill_guarded_rejects_foreign_token():
    from harpyja.eval.distill import DistillRejected, llm_distill_guarded

    issue = "the retry backoff fails on attempt two"

    def _fake(_text: str) -> str:
        return "retry backoff notaword"  # 'notaword' is absent from the issue

    with pytest.raises(DistillRejected):
        llm_distill_guarded(issue, llm=_fake)


def test_llm_distill_guarded_accepts_subset_output():
    from harpyja.eval.distill import llm_distill_guarded

    issue = "the retry backoff fails on attempt two"

    def _fake(_text: str) -> str:
        return "retry backoff"

    res = llm_distill_guarded(issue, llm=_fake)
    assert res.query == "retry backoff"


def test_llm_distill_prompt_is_prehashed():
    from harpyja.eval.distill import LLM_PROMPT, LLM_PROMPT_HASH

    assert isinstance(LLM_PROMPT, str) and LLM_PROMPT
    assert len(LLM_PROMPT_HASH) == 64
    assert all(ch in "0123456789abcdef" for ch in LLM_PROMPT_HASH)
