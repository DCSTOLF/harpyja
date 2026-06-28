"""Eval dataset format + loader (AC1, D1).

A fixture is JSONL, one case per line. Each case is::

    {"case_id": str, "query": str, "repo": str,
     "expected_spans": [{"path": str, "start_line": int, "end_line": int}, ...],
     "classification": "point" | "broad"}

The loader is **loud**: any malformed/missing field raises `DatasetError` and no
row is ever silently dropped (a silent skip would read as "the case passed"). To
add a case, append a well-formed line to the fixture; see `harpyja/eval/fixtures/`.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# The only two classification labels the harness recognizes; mirrors the
# orchestrator classifier's point/broad split (spec 0008).
CLASSIFICATIONS = frozenset({"point", "broad"})


class DatasetError(Exception):
    """A fixture row was malformed or a field was missing/invalid.

    Raised loudly so a bad case is never silently dropped (no-false-capability:
    "we never loaded it" must not read as "it passed").
    """


@dataclass(frozen=True)
class ExpectedSpan:
    """A hand-labeled expected location (repo-relative file + inclusive lines)."""

    path: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class EvalCase:
    """One eval case: a query, its repo, the labeled expected span(s), and label."""

    case_id: str
    query: str
    repo: str
    expected_spans: tuple[ExpectedSpan, ...]
    classification: str


def _require(row: dict[str, Any], key: str, line_no: int) -> Any:
    if key not in row:
        raise DatasetError(f"case on line {line_no}: missing required field {key!r}")
    return row[key]


def _parse_span(raw: Any, line_no: int) -> ExpectedSpan:
    if not isinstance(raw, dict):
        raise DatasetError(
            f"line {line_no}: each expected span must be an object, got {type(raw).__name__}"
        )
    path = _require(raw, "path", line_no)
    start = _require(raw, "start_line", line_no)
    end = _require(raw, "end_line", line_no)
    if not isinstance(path, str) or not path:
        raise DatasetError(f"line {line_no}: span 'path' must be a non-empty string")
    bad_int = (
        not isinstance(start, int)
        or isinstance(start, bool)
        or not isinstance(end, int)
        or isinstance(end, bool)
    )
    if bad_int:
        raise DatasetError(f"line {line_no}: span 'start_line'/'end_line' must be integers")
    if start < 1 or end < start:
        raise DatasetError(f"line {line_no}: span line range invalid (start={start}, end={end})")
    return ExpectedSpan(path=path, start_line=start, end_line=end)


def _parse_case(row: Any, line_no: int) -> EvalCase:
    if not isinstance(row, dict):
        raise DatasetError(f"line {line_no}: case must be a JSON object, got {type(row).__name__}")
    case_id = _require(row, "case_id", line_no)
    query = _require(row, "query", line_no)
    repo = _require(row, "repo", line_no)
    spans_raw = _require(row, "expected_spans", line_no)
    classification = _require(row, "classification", line_no)

    for name, val in (("case_id", case_id), ("query", query), ("repo", repo)):
        if not isinstance(val, str) or not val:
            raise DatasetError(f"line {line_no}: {name!r} must be a non-empty string")
    if classification not in CLASSIFICATIONS:
        raise DatasetError(
            f"line {line_no}: classification={classification!r} not in {sorted(CLASSIFICATIONS)}"
        )
    if not isinstance(spans_raw, list) or not spans_raw:
        raise DatasetError(f"line {line_no}: 'expected_spans' must be a non-empty list")

    spans = tuple(_parse_span(s, line_no) for s in spans_raw)
    return EvalCase(
        case_id=case_id,
        query=query,
        repo=repo,
        expected_spans=spans,
        classification=classification,
    )


def load_dataset(path: str | Path) -> list[EvalCase]:
    """Parse a JSONL eval fixture into `EvalCase`s; raise `DatasetError` on any
    malformed row (never silently skips)."""
    text = Path(path).read_text(encoding="utf-8")
    cases: list[EvalCase] = []
    for line_no, line in enumerate(_nonblank(text.splitlines()), start=1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as err:
            raise DatasetError(f"line {line_no}: invalid JSON ({err.msg})") from err
        cases.append(_parse_case(row, line_no))
    if not cases:
        raise DatasetError(f"dataset {path} contains no cases")
    return cases


def _nonblank(lines: Iterable[str]) -> Iterable[str]:
    for line in lines:
        if line.strip():
            yield line
