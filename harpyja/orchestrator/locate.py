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
from dataclasses import replace
from typing import Protocol, get_args

from harpyja.config.settings import Settings
from harpyja.deep.errors import DeepUnavailable
from harpyja.index.artifacts import resolve_artifact_dir
from harpyja.index.classify import KNOWN_LANGUAGES
from harpyja.index.indexer import index_repo
from harpyja.index.manifest import read_manifest
from harpyja.orchestrator.format import format_citations
from harpyja.scout.errors import NO_ENDPOINT_CONFIGURED, ScoutUnavailable
from harpyja.server.types import CodeSpan, LocateRequest, LocateResult, Mode
from harpyja.symbols.engine_identity import engine_identity
from harpyja.symbols.symbol_locator import SymbolEngine
from harpyja.symbols.symbols_io import load_symbols_or_none

_MODE_NO_EFFECT = "Wave 2: deterministic + symbol-aware Tier 0; mode has no effect"
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
    symbol_engine: _Engine | None = None,
    scout_engine: _Engine | None = None,
    deep_engine: object | None = None,
) -> LocateResult:
    if req.mode not in _VALID_MODES:
        raise ValueError(f"invalid mode: {req.mode!r}; expected one of {_VALID_MODES}")

    # Ensure-index: incremental refresh so the result reflects the current tree
    # (manifest *and* symbols.jsonl).
    art_dir = resolve_dir(req.repo_path, settings)
    indexer(req.repo_path, settings, artifact_dir=art_dir)
    manifest = {e.path: e for e in read_manifest(art_dir)}

    if symbol_engine is None:
        records = load_symbols_or_none(art_dir, engine_identity()) or []
        symbol_engine = SymbolEngine(records, settings)

    def prior_of(path: str) -> float:
        entry = manifest.get(path)
        return entry.prior if entry else 0.0

    if req.mode == "deep":
        return _locate_deep(
            req, manifest, prior_of, engine, symbol_engine, scout_engine, deep_engine
        )
    if req.mode == "fast":
        return _locate_scout(req, manifest, prior_of, engine, symbol_engine, scout_engine)

    # mode=auto — deterministic, symbol-aware Tier 0 (unchanged since Wave 2).
    spans = _tier0_seed(req, engine, symbol_engine)
    notes: list[str] = [_MODE_NO_EFFECT]
    spans, hint_note = _apply_language_hint(spans, manifest, req.language_hint)
    if hint_note:
        notes.append(hint_note)

    citations = format_citations(spans, prior_of, req.max_results)
    return LocateResult(
        citations=citations,
        confidence="medium" if citations else "low",
        tiers_run=[0],
        notes="; ".join(notes),
    )


def _tier0_seed(
    req: LocateRequest,
    engine: _Engine,
    symbol_engine: _Engine,
) -> list[CodeSpan]:
    """Compose the symbol + ripgrep Locators into one Tier-0 CodeSpan stream.

    Shared by the `auto` branch and the Scout degradation fallback. The
    orchestrator never branches on which engine produced a span; the formatter
    promotes definitions via the boost.
    """
    sym_spans = symbol_engine.search(req.query, scope=req.repo_path)
    text_spans = engine.search(req.query, scope=req.repo_path)
    return sym_spans + text_spans


def _locate_scout(
    req: LocateRequest,
    manifest: dict,
    prior_of: Callable[[str], float],
    engine: _Engine,
    symbol_engine: _Engine,
    scout_engine: _Engine | None,
) -> LocateResult:
    """Tier 1 (Scout). Explicit-mode only; degrades to Tier 0 on model failure.

    `RipgrepMissingError` (from Scout's self-seed) and `AirGapError` (a
    non-loopback endpoint) propagate loudly — they are the degradation floor,
    not a degrade state. Only `ScoutUnavailable` falls back to Tier 0.
    """
    if scout_engine is None:
        # Scout not wired → honest degrade, never a silent no-op.
        return _degrade(req, manifest, prior_of, engine, symbol_engine, NO_ENDPOINT_CONFIGURED)

    try:
        spans = scout_engine.search(req.query, scope=req.repo_path)
    except ScoutUnavailable as err:
        return _degrade(req, manifest, prior_of, engine, symbol_engine, err.cause)

    spans, hint_note = _apply_language_hint(spans, manifest, req.language_hint)
    citations = format_citations(spans, prior_of, req.max_results, source_tier=1)

    return LocateResult(
        citations=citations,
        confidence="medium" if citations else "low",
        tiers_run=[0, 1],
        notes=hint_note,
    )


def _locate_deep(
    req: LocateRequest,
    manifest: dict,
    prior_of: Callable[[str], float],
    engine: _Engine,
    symbol_engine: _Engine,
    scout_engine: _Engine | None,
    deep_engine: object | None,
) -> LocateResult:
    """Tier 2 (Deep). Explicit-mode only; degrades to Scout best-effort on a typed
    `DeepUnavailable` (NOT on weak/zero output — that would be an ungated
    escalation). `RipgrepMissingError` (Deep's self-seed) and `AirGapError`
    propagate loudly as the floor; a budget truncation is an honest bounded
    Tier-2 result carrying a `deep-truncated:<bound>` note, never a degrade.
    """
    if deep_engine is None:
        # Deep not wired → degrade to Scout best-effort, honestly flagged.
        fallback = _locate_scout(req, manifest, prior_of, engine, symbol_engine, scout_engine)
        return _with_deep_note(fallback, f"deep-degraded:{NO_ENDPOINT_CONFIGURED}")

    try:
        spans, truncated = deep_engine.run(req.query)
    except DeepUnavailable as err:
        fallback = _locate_scout(req, manifest, prior_of, engine, symbol_engine, scout_engine)
        return _with_deep_note(fallback, f"deep-degraded:{err.cause}")

    spans, hint_note = _apply_language_hint(spans, manifest, req.language_hint)
    citations = format_citations(spans, prior_of, req.max_results, source_tier=2)

    notes: list[str] = []
    if truncated:
        notes.append(f"deep-truncated:{truncated}")
    if hint_note:
        notes.append(hint_note)

    return LocateResult(
        citations=citations,
        confidence="medium" if citations else "low",
        tiers_run=[0, 2],
        notes="; ".join(notes) if notes else None,
    )


def _with_deep_note(result: LocateResult, note: str) -> LocateResult:
    """Prepend a `deep-degraded:<cause>` note to a Scout-fallback result."""
    combined = note if not result.notes else f"{note}; {result.notes}"
    return replace(result, notes=combined)


def _degrade(
    req: LocateRequest,
    manifest: dict,
    prior_of: Callable[[str], float],
    engine: _Engine,
    symbol_engine: _Engine,
    cause: str,
) -> LocateResult:
    """Fall back to the deterministic Tier-0 result with a `degraded` flag.

    Reached only via `ScoutUnavailable` (or an unwired Scout) — i.e. the model
    boundary failed but Tier 0's own preconditions held (`rg`-missing would have
    propagated from Scout's self-seed first). A distinct `+no-matches` suffix
    keeps "Tier-0 honestly empty" distinguishable from "Tier-0 had results".
    """
    spans = _tier0_seed(req, engine, symbol_engine)
    spans, _hint_note = _apply_language_hint(spans, manifest, req.language_hint)
    citations = format_citations(spans, prior_of, req.max_results)

    note = f"scout-degraded:{cause}"
    if not citations:
        note += "+no-matches"

    return LocateResult(
        citations=citations,
        confidence="degraded",
        tiers_run=[0],
        notes=note,
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
