"""RED (0046 T6/T7, AC3): the confirm-before-submit interceptor.

The SECOND mechanism change: gate the OUTPUT, not the ACTION. Before a citation
is emitted, a host-side interceptor reads the candidate span and applies a
CONCRETE, DETERMINISTIC lexical/symbolic predicate — never a model judgment,
never gold. Confirmation PASSES iff the query's mechanically-extracted key
identifier(s) appear in the span text OR match the span's symbol name. An
undecidable case (no extractable identifier / unreadable span) is CONFIRM_ERROR
(could-not-vouch), never a guessed PASS/FAIL.

Emit routing (in the backend seam, T9): PASS -> clean; FAIL / CONFIRM_ERROR ->
emit WITH a confidence flag (degraded honest citation), never silence.
"""

from __future__ import annotations

import ast
import inspect

from harpyja.scout.confirm import (
    ConfirmationOutcome,
    confirm_before_submit,
    derive_submit_disposition,
    extract_query_key_identifiers,
)
from harpyja.server.types import CodeSpan


def _reader(content):
    def read_span(path, start, end):
        return {"content": content}

    return read_span


def _span(path="m.py", start=10, end=20, symbol=None):
    return CodeSpan(path=path, start_line=start, end_line=end, symbol=symbol)


# --- query key-identifier extraction (mechanical, query-only) ------------------


def test_key_identifier_extraction_matches_token_floor():
    ids = extract_query_key_identifiers("locate separability_matrix in mod.sub")
    assert "separability_matrix" in ids
    assert "mod.sub" in ids  # dotted path kept whole
    assert "in" not in ids  # below the length floor


def test_key_identifier_extraction_prefers_backtick_quoted():
    ids = extract_query_key_identifiers("where is `separability_matrix` defined?")
    assert ids == ["separability_matrix"]


def test_key_identifier_extraction_empty_when_no_identifier():
    assert extract_query_key_identifiers("?? — !!") == []


# --- confirmation outcomes -----------------------------------------------------


def test_confirm_pass_on_lexical_containment():
    out = confirm_before_submit(
        "find separability_matrix",
        _span(),
        _reader("def separability_matrix(model):\n    return ..."),
    )
    assert out is ConfirmationOutcome.PASS


def test_confirm_pass_on_symbol_name_match():
    # The span text does not contain the token, but the span's symbol name does.
    out = confirm_before_submit(
        "find separability_matrix",
        _span(symbol="separability_matrix"),
        _reader("    return _impl(model)  # body without the name"),
    )
    assert out is ConfirmationOutcome.PASS


def test_confirm_fail_when_key_id_extractable_but_absent():
    out = confirm_before_submit(
        "find separability_matrix",
        _span(),
        _reader("def something_else(x):\n    return x + 1"),
    )
    assert out is ConfirmationOutcome.FAIL


def test_confirm_error_when_no_key_id_extractable():
    out = confirm_before_submit("?? !!", _span(), _reader("def foo(): ..."))
    assert out is ConfirmationOutcome.CONFIRM_ERROR


def test_confirm_error_when_read_span_raises():
    def boom(path, start, end):
        raise RuntimeError("unreadable")

    out = confirm_before_submit("find separability_matrix", _span(), boom)
    assert out is ConfirmationOutcome.CONFIRM_ERROR


def test_confirm_error_when_read_span_empty():
    out = confirm_before_submit("find separability_matrix", _span(), _reader(""))
    assert out is ConfirmationOutcome.CONFIRM_ERROR


def test_confirm_error_when_candidate_is_file_level():
    # A line-less (file-level) citation cannot be span-confirmed deterministically.
    out = confirm_before_submit(
        "find separability_matrix",
        CodeSpan(path="m.py", start_line=None, end_line=None),
        _reader("def separability_matrix(): ..."),
    )
    assert out is ConfirmationOutcome.CONFIRM_ERROR


def test_confirm_no_candidate_when_nothing_submitted():
    out = confirm_before_submit("find separability_matrix", None, _reader("x"))
    assert out is ConfirmationOutcome.NO_CANDIDATE


# --- submit_disposition derivation (five attributable shapes) ------------------


def test_submit_disposition_derivation_five_shapes():
    P = ConfirmationOutcome.PASS
    F = ConfirmationOutcome.FAIL
    E = ConfirmationOutcome.CONFIRM_ERROR
    N = ConfirmationOutcome.NO_CANDIDATE

    assert derive_submit_disposition([], N, has_candidate=False) == "no-candidate"
    assert derive_submit_disposition([], F, has_candidate=True) == "confirm-failed-flagged"
    assert derive_submit_disposition([], E, has_candidate=True) == "confirm-failed-flagged"
    assert (
        derive_submit_disposition(["symbols-empty"], P, has_candidate=True)
        == "triggered-and-explored"
    )
    assert (
        derive_submit_disposition([], P, has_candidate=True) == "confirmed-then-submitted"
    )
    assert derive_submit_disposition([], None, has_candidate=True) == "never-triggered"


def test_confirm_module_reads_query_only_never_gold():
    # Structural: the interceptor imports no eval/ code and takes no gold param.
    import harpyja.scout.confirm as confirm_mod

    tree = ast.parse(inspect.getsource(confirm_mod))
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        for name in names:
            assert not name.startswith("harpyja.eval"), (
                f"confirm imports {name} — the interceptor must be gold-blind"
            )
