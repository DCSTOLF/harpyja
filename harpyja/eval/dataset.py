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

# spec 0026: a NEW dataset schema-version tag (there was none before). It GATES the
# leakage-guard validation: a row tagged with this version is a "terse" case (0026)
# whose spans are JOINED by case_id from the pinned raw fixture and which MUST carry
# the leakage-guard provenance; an untagged row is a legacy/seed case that loads with
# today's contract (non-empty expected_spans) and the guard fields defaulted. This is
# introduced, not bumped — it is distinct from report.SCHEMA_VERSION.
DATASET_SCHEMA_VERSION = "0026/1"

# Terse-schema (0026) cases MUST carry these leakage-guard provenance fields, so AC2's
# guard is enforced by the loud loader and never rides as an unvalidated passenger.
# (`label_provenance` and `leaked_tokens` are populated at JOIN time, not required here.)
_TERSE_GUARD_REQUIRED = ("gold_withheld", "query_provenance")


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
    # spec 0026: additive last-with-defaults. Populated for terse-schema (0026) cases;
    # legacy/seed rows default them so older on-disk fixtures still read. `label_provenance`
    # and `leaked_tokens` are set at JOIN time (over the pinned raw fixture).
    schema_version: str | None = None
    label_provenance: str | None = None
    query_provenance: str | None = None
    gold_withheld: bool = False
    leaked_tokens: tuple[str, ...] = ()
    classification_provenance: str | None = None


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
    classification = _require(row, "classification", line_no)

    for name, val in (("case_id", case_id), ("query", query), ("repo", repo)):
        if not isinstance(val, str) or not val:
            raise DatasetError(f"line {line_no}: {name!r} must be a non-empty string")
    if classification not in CLASSIFICATIONS:
        raise DatasetError(
            f"line {line_no}: classification={classification!r} not in {sorted(CLASSIFICATIONS)}"
        )

    schema_version = row.get("schema_version")
    is_terse = schema_version == DATASET_SCHEMA_VERSION

    # Version gate (AC3/AC5): a terse (0026) row MAY omit expected_spans (they are
    # joined by case_id from the pinned raw fixture) but MUST carry the leakage-guard
    # provenance; a legacy row keeps the original contract (non-empty expected_spans)
    # and the guard fields defaulted, so seed/legacy fixtures still load.
    if is_terse:
        spans: tuple[ExpectedSpan, ...] = ()
        if "expected_spans" in row:
            spans_raw = row["expected_spans"]
            if not isinstance(spans_raw, list):
                raise DatasetError(f"line {line_no}: 'expected_spans' must be a list")
            spans = tuple(_parse_span(s, line_no) for s in spans_raw)
        guard = _parse_terse_guard(row, line_no)
    else:
        spans_raw = _require(row, "expected_spans", line_no)
        if not isinstance(spans_raw, list) or not spans_raw:
            raise DatasetError(f"line {line_no}: 'expected_spans' must be a non-empty list")
        spans = tuple(_parse_span(s, line_no) for s in spans_raw)
        guard = {}

    return EvalCase(
        case_id=case_id,
        query=query,
        repo=repo,
        expected_spans=spans,
        classification=classification,
        schema_version=schema_version if is_terse else None,
        **guard,
    )


def _parse_terse_guard(row: dict[str, Any], line_no: int) -> dict[str, Any]:
    """Validate + extract the spec-0026 terse leakage-guard provenance fields.

    Terse-schema cases MUST carry the guard provenance so AC2's guard is enforced by
    the loud loader, never an unvalidated passenger. Returns the kwargs for `EvalCase`.
    """
    for key in _TERSE_GUARD_REQUIRED:
        if key not in row:
            raise DatasetError(
                f"line {line_no}: terse case missing required guard field {key!r}"
            )
    gold_withheld = row["gold_withheld"]
    if not isinstance(gold_withheld, bool):
        raise DatasetError(f"line {line_no}: 'gold_withheld' must be a boolean")
    query_provenance = row["query_provenance"]
    if not isinstance(query_provenance, str) or not query_provenance:
        raise DatasetError(f"line {line_no}: 'query_provenance' must be a non-empty string")
    guard: dict[str, Any] = {
        "gold_withheld": gold_withheld,
        "query_provenance": query_provenance,
    }
    cp = row.get("classification_provenance")
    if cp is not None:
        if not isinstance(cp, str) or not cp:
            raise DatasetError(
                f"line {line_no}: 'classification_provenance' must be a non-empty string"
            )
        guard["classification_provenance"] = cp
    return guard


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
