"""The tool-call-native `submit_citations` terminal action (spec 0024, AC6).

The model ends the explorer loop by calling this action with STRUCTURED citation
args, replacing the retired FastContext-era `<final_answer>` text grammar
(0011/0012) — structured args over regexing prose.

Two distinct rejection paths, deliberately not the same:

- **Strict schema (raises).** Each citation dict may carry ONLY the sanctioned
  fields `{path, start_line, end_line}`. Any unknown/extra key — including a
  diagnosis-shaped one (`root_cause`, `fix`, `explanation`, …) — raises
  :class:`SubmitCitationsSchemaError`. This is the enforceable form of the
  locator-not-diagnoser guard: a diagnosis field fails schema, not a soft check.
- **Content validation (drops).** A structurally-valid ref whose content is bad
  (out-of-repo path, nonexistent file, malformed/over-budget range) is DROPPED by
  the existing `normalize_spans`, never propagated. An empty submission is
  honest-empty.

The action has NO repo-read capability — it only validates and normalizes refs.
The returned spans are plain (unstamped) `CodeSpan`s; the `source_tier=1` stamp
happens downstream in the unchanged orchestrator path.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from harpyja.config.settings import Settings
from harpyja.scout.normalize import normalize_spans
from harpyja.server.types import CodeSpan

# The ONLY fields a citation arg may carry (strict — anything else is a schema error).
ALLOWED_CITATION_FIELDS = frozenset({"path", "start_line", "end_line"})


class SubmitCitationsSchemaError(ValueError):
    """A `submit_citations` arg violated the strict citation schema."""


def _to_span(ref: Mapping[str, Any]) -> CodeSpan:
    extra = set(ref) - ALLOWED_CITATION_FIELDS
    if extra:
        raise SubmitCitationsSchemaError(
            f"unknown citation field(s) {sorted(extra)!r}; "
            f"allowed: {sorted(ALLOWED_CITATION_FIELDS)!r}"
        )
    path = ref.get("path")
    if not isinstance(path, str) or not path:
        raise SubmitCitationsSchemaError(f"citation missing a string 'path': {ref!r}")
    start = ref.get("start_line")
    end = ref.get("end_line")
    if start is not None and not isinstance(start, int):
        raise SubmitCitationsSchemaError(f"start_line must be an int or absent: {ref!r}")
    if end is not None and not isinstance(end, int):
        raise SubmitCitationsSchemaError(f"end_line must be an int or absent: {ref!r}")
    return CodeSpan(path=path, start_line=start, end_line=end)


def submit_citations(
    citations: Sequence[Mapping[str, Any]],
    repo_root: str,
    settings: Settings,
) -> list[CodeSpan]:
    """Validate + normalize the model's terminal citation args into safe spans."""
    raw = [_to_span(ref) for ref in citations]
    return normalize_spans(
        raw,
        repo_root,
        max_citations=settings.scout_max_citations,
        max_span_lines=settings.scout_max_span_lines,
    )
