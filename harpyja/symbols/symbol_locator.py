"""SymbolEngine — exact-only symbol search behind the `Locator` protocol (AC9, AC10).

`SymbolEngine.search(pattern, scope=None)` mirrors `RipgrepEngine.search` so the
orchestrator composes the two without branching on engine type. Matching is:

- **name** — the query is split on whitespace into segments, each segment split into
  identifier tokens on ``[^A-Za-z0-9_]``; a token must **exactly, case-sensitively**
  equal a symbol `name` (no substring matching — that is deferred to Wave 2.1);
- **method address** — a separate pass over each raw segment finds ordered adjacent
  ``<identifier>(.|::)<identifier>`` pairs; the left must equal a symbol's `parent`
  and the right its `name`. A 3+ chain (`Foo.bar.baz`) yields every adjacent pair.

Matches are returned as definition `CodeSpan`s carrying `symbol`/`kind`/`language`
so the Citation Formatter can promote them above raw text hits. Results are bounded
by the configured search limits.
"""

from __future__ import annotations

import re

from harpyja.config.settings import Settings
from harpyja.server.types import CodeSpan
from harpyja.symbols.extract import SymbolRecord

_IDENT_TOKEN = re.compile(r"[A-Za-z0-9_]+")
_SEP = re.compile(r"::|\.")


class SymbolEngine:
    """A Tier-0 `Locator` over extracted symbol definitions."""

    def __init__(self, records: list[SymbolRecord], settings: Settings) -> None:
        self._settings = settings
        self._by_name: dict[str, list[SymbolRecord]] = {}
        self._by_parent_name: dict[tuple[str, str], list[SymbolRecord]] = {}
        for rec in records:
            self._by_name.setdefault(rec.name, []).append(rec)
            if rec.parent is not None:
                self._by_parent_name.setdefault((rec.parent, rec.name), []).append(rec)

    def search(self, pattern: str, scope: str | None = None) -> list[CodeSpan]:
        matched: list[SymbolRecord] = []
        seen: set[tuple[str, int, int, str]] = set()

        def add(rec: SymbolRecord) -> None:
            key = (rec.path, rec.start_line, rec.end_line, rec.name)
            if key not in seen:
                seen.add(key)
                matched.append(rec)

        for segment in pattern.split():
            # Exact name tokens.
            for token in _IDENT_TOKEN.findall(segment):
                for rec in self._by_name.get(token, ()):
                    add(rec)
            # Method address: every adjacent (.|::)-separated identifier pair.
            tokens = _SEP.split(segment)
            for left, right in zip(tokens, tokens[1:], strict=False):
                for rec in self._by_parent_name.get((left, right), ()):
                    add(rec)

        return self._bounded_spans(matched)

    def _bounded_spans(self, records: list[SymbolRecord]) -> list[CodeSpan]:
        spans: list[CodeSpan] = []
        files: set[str] = set()
        for rec in records:
            if rec.path not in files and len(files) >= self._settings.search_max_files:
                continue
            files.add(rec.path)
            spans.append(
                CodeSpan(
                    path=rec.path,
                    start_line=rec.start_line,
                    end_line=rec.end_line,
                    symbol=rec.name,
                    language=rec.language,
                    kind=rec.kind,
                )
            )
            if len(spans) >= self._settings.search_max_matches:
                break
        return spans
