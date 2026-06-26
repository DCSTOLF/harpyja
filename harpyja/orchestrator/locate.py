"""Tier-0 orchestrator for `harpyja_locate` (AC10-13).

Wave 1 has a single tier (deterministic ripgrep over the indexed repo). Before
searching, `locate` runs an incremental index refresh so the result reflects the
current tree (adds, edits, deletes) with no explicit re-index call. The three
request fields are honored distinctly:
- `max_results` is a mandatory clamp (via the formatter),
- `mode` is validated and accepted but flagged inert (no routing in Wave 1),
- `language_hint` filters best-effort by the manifest's extension-derived
  language, with distinct notes for an unrecognized hint vs null-language
  exclusion.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, get_args

from harpyja.config.settings import Settings
from harpyja.index.artifacts import resolve_artifact_dir
from harpyja.index.classify import KNOWN_LANGUAGES
from harpyja.index.indexer import index_repo
from harpyja.index.manifest import read_manifest
from harpyja.orchestrator.format import format_citations
from harpyja.server.types import CodeSpan, LocateRequest, LocateResult, Mode

_MODE_NO_EFFECT = "Wave 1: deterministic tier only; mode has no effect"
_VALID_MODES = set(get_args(Mode))


class _Engine(Protocol):
    def search(self, pattern: str, scope: str | None = None) -> list[CodeSpan]: ...


def locate(
    req: LocateRequest,
    settings: Settings,
    *,
    engine: _Engine,
    indexer: Callable[..., object] = index_repo,
    resolve_dir: Callable[..., object] = resolve_artifact_dir,
) -> LocateResult:
    if req.mode not in _VALID_MODES:
        raise ValueError(f"invalid mode: {req.mode!r}; expected one of {_VALID_MODES}")

    # Ensure-index: incremental refresh so the result reflects the current tree.
    art_dir = resolve_dir(req.repo_path, settings)
    indexer(req.repo_path, settings, artifact_dir=art_dir)
    manifest = {e.path: e for e in read_manifest(art_dir)}

    spans = engine.search(req.query, scope=req.repo_path)

    notes: list[str] = [_MODE_NO_EFFECT]
    spans, hint_note = _apply_language_hint(spans, manifest, req.language_hint)
    if hint_note:
        notes.append(hint_note)

    def prior_of(path: str) -> float:
        entry = manifest.get(path)
        return entry.prior if entry else 0.0

    citations = format_citations(spans, prior_of, req.max_results)

    return LocateResult(
        citations=citations,
        confidence="medium" if citations else "low",
        tiers_run=[0],
        notes="; ".join(notes),
    )


def _apply_language_hint(
    spans: list[CodeSpan],
    manifest: dict,
    language_hint: str | None,
) -> tuple[list[CodeSpan], str | None]:
    """Filter spans by language hint; return (spans, note)."""
    if not language_hint:
        return spans, None

    if language_hint not in KNOWN_LANGUAGES:
        # Unrecognized hint: nothing can match; say so explicitly (never silent).
        return [], f"language_hint {language_hint!r} is not a recognized language"

    kept: list[CodeSpan] = []
    skipped_null: set[str] = set()
    for s in spans:
        entry = manifest.get(s.path)
        lang = entry.language if entry else None
        if lang == language_hint:
            kept.append(s)
        elif lang is None:
            skipped_null.add(s.path)

    note = None
    if skipped_null:
        note = f"{len(skipped_null)} files skipped: language undetermined"
    return kept, note
