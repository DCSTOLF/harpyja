"""Shape/type contract tests for server.types (Wave 3: AC5).

Wave 3 adds a `degraded` confidence value for the Scout fallback states; the
existing high/medium/low values keep their meaning.

Spec 0011 (citation-shape): `CodeSpan` line fields become `int | None` so a
bare-path (file-level) citation can carry *no* line range without fabricating
one. `None` lines ⇒ file-level; both-or-neither (a half-`None` is not a sanctioned
shape — enforced at the parse/normalize boundary, AC23). The `is_file_level`
predicate is the one place downstream consumers branch on coarse precision.
"""

from typing import get_args

from harpyja.server.types import CodeSpan, Confidence


def test_confidence_includes_degraded():
    # Wave 3 degrade states 2/3 set confidence="degraded".
    assert "degraded" in get_args(Confidence)


def test_confidence_keeps_wave2_values():
    # Additive change: the prior values must survive.
    assert {"high", "medium", "low"} <= set(get_args(Confidence))


# --- Spec 0011: line-less (file-level) CodeSpan representation ---


def test_codespan_is_file_level_when_both_lines_none():
    # A bare-path citation: path but no line range (AC1/AC4 representation).
    span = CodeSpan(path="auth.py", start_line=None, end_line=None)
    assert span.is_file_level is True
    assert span.start_line is None and span.end_line is None


def test_codespan_is_file_level_false_for_lined_span():
    # A spanned citation keeps both ints and is NOT file-level (regression).
    span = CodeSpan(path="auth.py", start_line=10, end_line=15)
    assert span.is_file_level is False


def test_codespan_is_file_level_false_for_half_none_span():
    # Half-`None` is not file-level: file-level means BOTH lines absent. The
    # shape is rejected upstream (AC23); the predicate must not mistake it for
    # a clean file-level span.
    assert CodeSpan(path="a.py", start_line=10, end_line=None).is_file_level is False
    assert CodeSpan(path="a.py", start_line=None, end_line=15).is_file_level is False
