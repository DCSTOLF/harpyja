"""The read-only navigation tools handed to the explorer loop (spec 0024, +0027, +0030).

The model driving the loop is an untrusted caller (same posture as the Deep-tier
RLM host tools in `deep/host_tools.py`). This module builds EXACTLY five bounded,
repo-path-confined, read-only navigation tools — and nothing mutating:

- ``grep(pattern, scope=None)`` — wraps the SAME ``RipgrepEngine`` the Deep
  ``search`` host tool wraps (spec invariant B: one bounded ripgrep source of
  truth, never a second rg surface), clamped by ``search_max_matches``.
- ``glob(pattern)`` — repo-confined path glob, returning **file-level**
  ``CodeSpan`` records (not raw strings), clamped by ``scout_glob_max_paths``.
- ``read_span(path, start, end)`` — the existing bounded ``read_snippet``.
- ``ls(path=".")`` — **spec 0027** — single-directory listing (immediate children
  only), repo-confined, listing files AND directories (dirs suffixed ``/``) so the
  model can discover repo LAYOUT on demand. This is the affordance ``glob`` lacks
  (glob filters out directories), added as a DELIBERATE, reconciled tool-suite
  change when the eager whole-repo context map was removed (push → pull). Clamped
  by ``scout_ls_max_entries``.
- ``symbols(path)`` — **spec 0030** — file-local symbol index (function/class/type
  definitions and their line spans), sourced from Tier-0's pre-extracted symbol
  records. Repo-confined, clamped by ``scout_symbols_max_entries``.

The distinct terminal ``submit_citations`` action lives in ``scout/submit.py`` and
is deliberately NOT part of this navigation suite.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from harpyja.config.settings import Settings
from harpyja.index.manifest import ManifestEntry
from harpyja.server.tools import confine_path, read_snippet
from harpyja.server.types import CodeSpan
from harpyja.symbols.extract import SymbolRecord
from harpyja.symbols.symbols_io import record_to_codespan


class _Search:  # structural: anything with .search(pattern, scope, repo_root=)
    def search(
        self, pattern: str, scope: str | None = None, *, repo_root: str | None = None
    ) -> list[CodeSpan]: ...


def build_explorer_tools(
    repo_path: str,
    settings: Settings,
    *,
    search_engine: _Search,
    symbol_records: Sequence[SymbolRecord] | None = None,
    manifest: Sequence[ManifestEntry] | None = None,
) -> dict[str, Callable[..., Any]]:
    """Return exactly the five navigation tools, keyed by name."""
    symbol_records = symbol_records or []
    manifest = manifest or []
    repo_real = Path(repo_path).resolve()

    # Build a degraded_paths set for AC3 graceful degradation (manifest-based provenance).
    degraded_paths = {m.path for m in manifest if m.degraded}

    def grep(pattern: str, scope: str | None = None) -> list[CodeSpan] | str:
        # Confine the search scope to the repo (rejects an out-of-repo scope) and
        # delegate to the shared engine; clamp defensively on untrusted-loop output.
        scoped_path = confine_path(repo_path, scope) if scope else Path(repo_path)
        # Spec 0035: an UNSEARCHABLE (nonexistent) scope is a typed, model-visible
        # marker — never a silent [] that reads as "searched, nothing found". The
        # guard MUST fire before delegation (a nonexistent cwd crashes the engine's
        # subprocess). An existing FILE scope falls through: the engine searches it
        # for real (0033 parent-dir mechanism) — delegation, not a redirect.
        if scope and not scoped_path.exists():
            return f"grep-scope-not-found: {scope!r}"
        # repo_root threads the repo-relative output contract (spec 0033): the
        # engine re-prefixes scoped results so a cited hit survives normalization.
        spans = search_engine.search(pattern, scope=str(scoped_path), repo_root=repo_path)
        return spans[: settings.search_max_matches]

    def glob(pattern: str) -> list[CodeSpan]:
        # Repo-confined glob → file-level CodeSpan records. Any match whose realpath
        # escapes the repo (e.g. a `../` pattern or an escaping symlink) is dropped,
        # never surfaced. Deterministic order; bounded by scout_glob_max_paths.
        out: list[CodeSpan] = []
        for match in sorted(repo_real.glob(pattern)):
            if not match.is_file():
                continue
            try:
                real = match.resolve()
                rel = real.relative_to(repo_real)
            except ValueError:
                continue  # escapes the repo root — drop
            if real != repo_real and repo_real not in real.parents:
                continue
            out.append(CodeSpan(path=str(rel), start_line=None, end_line=None))
            if len(out) >= settings.scout_glob_max_paths:
                break
        return out

    def read_span(path: str, start: int, end: int) -> dict[str, Any]:
        return read_snippet(repo_path, path, start, end, settings)

    def ls(path: str = ".") -> list[CodeSpan] | str:
        # Single-directory listing (immediate children only — the model walks down;
        # NOT a recursive tree, which would re-create the eager-dump risk removed in
        # spec 0027). Repo-confined via confine_path; lists files AND directories
        # (dirs suffixed "/") as file-level CodeSpan records so layout is
        # discoverable. Deterministic order; bounded by scout_ls_max_entries.
        target = Path(confine_path(repo_path, path))
        # Spec 0035: a NONEXISTENT path is a typed marker (same class as grep's
        # unsearchable-scope rule); an existing FILE keeps honest-[] below —
        # "list children" of a file is genuinely empty, distinct from path-absent.
        if not target.exists():
            return f"ls-path-not-found: {path!r}"
        if not target.is_dir():
            return []  # ls on a file → empty (use read_span for file contents)
        out: list[CodeSpan] = []
        for child in sorted(target.iterdir()):
            try:
                rel = child.resolve().relative_to(repo_real)
            except ValueError:
                continue  # escapes the repo root — drop
            name = f"{rel}/" if child.is_dir() else str(rel)
            out.append(CodeSpan(path=name, start_line=None, end_line=None))
            if len(out) >= settings.scout_ls_max_entries:
                break
        return out

    def _symbols_by_name(name: Any) -> list[CodeSpan] | str:
        # Repo-wide by-name lookup (spec 0042, AC3) — the positioning fix: reachable
        # BEFORE a candidate file is found, and the NAME-based partial answer to
        # lexical unreachability ("separability matrix" is ungreppable;
        # separability_matrix is findable by name). Read-only (filters the injected
        # Tier-0 records — no filesystem walk, no new parser), repo-confined by
        # construction, clamped by the DISTINCT scout_symbols_repo_max_entries knob.
        #
        # Hostile input (non-string / empty / oversized) → typed marker, clipped —
        # never echoed unclamped, never an unhandled exception (0035 marker route:
        # a navigation mistake, not an execution error).
        if not isinstance(name, str) or not name or len(name) > 256:
            return f"symbols-name-invalid: {repr(name)[:128]}"
        # Absent Tier-0 records (index missing/degraded): the 0035 REPLACEMENT
        # marker — no spans exist to annotate, and a silent [] would be
        # indistinguishable from "no such symbol".
        if not symbol_records:
            return f"symbols-index-unavailable: {name!r}"
        # PINNED ranking (OQ2): exact-name > prefix > substring; ties broken
        # deterministically by (path, start_line) — never arbitrary truncation.
        tiers: tuple[list[SymbolRecord], list[SymbolRecord], list[SymbolRecord]] = ([], [], [])
        for record in symbol_records:
            if record.name == name:
                tiers[0].append(record)
            elif record.name.startswith(name):
                tiers[1].append(record)
            elif name in record.name:
                tiers[2].append(record)
        ranked = [
            record
            for tier in tiers
            for record in sorted(tier, key=lambda r: (r.path, r.start_line))
        ]
        clamped = ranked[: settings.scout_symbols_repo_max_entries]
        return [record_to_codespan(r) for r in clamped]

    def symbols(path: str | None = None, name: str | None = None) -> list[CodeSpan | str] | str:
        # Symbol lookup (spec 0030, repositioned by spec 0042): with `path`, the
        # file-local symbol index (functions, classes, types + exact start/end line
        # spans) sourced from Tier-0's pre-extracted records (no new parser); with
        # `name` only, a repo-wide by-name lookup (path is OPTIONAL as of 0042 —
        # the adoption-driver positioning fix). Output clamped per mode.
        #
        # Result shape (spec 0042, AC2): a bare list[CodeSpan] — parity with every
        # other nav tool, so _spans_of unwraps it and its locations enter
        # seen-span/loop-detection accounting (the 0/28-era nested dict registered
        # ZERO spans and structurally penalized every call). A degraded file
        # PREPENDS the stable ANNOTATION marker `symbols-degraded: '<path>'` to the
        # real ripgrep-fallback spans (the 0035 convention's second case:
        # successful-but-degraded — marker model-visible via stringification,
        # never counted as a span; 0030's never-a-silent-downgrade contract).
        # An EMPTY path is absent, not file-local (post-T12 pin: a live 0042 cell
        # sent {"path": "", "name": ...} and the `is None` check silently ignored
        # the name — the repo-wide affordance must not be defeatable by "").
        if not path:
            if name is None:
                return "symbols-args-missing: 'provide path or name'"
            return _symbols_by_name(name)

        # Confine the path first: raises PathConfinementError if out-of-repo.
        # This preserves the untrusted-caller boundary (loud error, not silent drop).
        confine_path(repo_path, path)

        try:
            # Normalize the path: resolve it (handle .. and symlinks), make relative.
            candidate = (repo_real / path).resolve()
            rel_path = candidate.relative_to(repo_real)
        except (ValueError, OSError):
            return []  # escapes or error — empty clean result

        normalized_str = str(rel_path)

        # AC3: Check if this file is degraded (parse failure at index build).
        if normalized_str in degraded_paths:
            # Fallback to ripgrep (Tier-0's existing fallback) for this file.
            ripgrep_results = search_engine.search(
                "", scope=str(candidate), repo_root=repo_path
            )
            clamped = ripgrep_results[: settings.scout_symbols_max_entries]
            return [f"symbols-degraded: {normalized_str!r}", *clamped]

        # Clean file: filter records by the normalized repo-relative path, convert to CodeSpan.
        out: list[CodeSpan] = []
        for record in symbol_records:
            if record.path == normalized_str:
                out.append(record_to_codespan(record))
                if len(out) >= settings.scout_symbols_max_entries:
                    break
        # Post-T12 (0035 replacement marker, the ls/grep class): NO records AND the
        # file absent on disk is UNSEARCHABLE — never a silent [] that reads as
        # "file has no symbols". Records win over disk absence (the no-new-parser
        # contract); a real file with no records keeps honest-[].
        if not out and not candidate.exists():
            return f"symbols-path-not-found: {path!r}"
        return out

    return {"grep": grep, "glob": glob, "read_span": read_span, "ls": ls, "symbols": symbols}
