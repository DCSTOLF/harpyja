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
from harpyja.orchestrator.classify import Classifier, classify_query
from harpyja.orchestrator.format import format_citations
from harpyja.orchestrator.gate import VerificationGate
from harpyja.orchestrator.matrix import plan_ladder
from harpyja.scout.errors import NO_ENDPOINT_CONFIGURED, ScoutUnavailable
from harpyja.server.types import CodeSpan, LocateRequest, LocateResult, Mode
from harpyja.symbols.engine_identity import engine_identity
from harpyja.symbols.symbol_locator import SymbolEngine
from harpyja.symbols.symbols_io import load_symbols_or_none

_VALID_MODES = set(get_args(Mode))

# Spec 0008 — stable, caller-visible gate flags (machine-readable identifiers, not
# prose; callers/tests branch on the id).
GATE_SKIPPED_SCOUT_EMPTY = "gate-skipped:scout-empty"
GATE_LOW_CONFIDENCE = "gate-low-confidence"
GATE_SCORING_FAILED = "gate-scoring-failed"


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
    gate: VerificationGate | None = None,
    classifier: Classifier = classify_query,
    index_ready: bool | None = None,
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

    # index_ready gates the Tier-0 seed. Derived from the just-built manifest;
    # overridable for tests. A not-ready index is a routing variant (query-only),
    # not a floor failure.
    if index_ready is None:
        index_ready = bool(manifest)

    def prior_of(path: str) -> float:
        entry = manifest.get(path)
        return entry.prior if entry else 0.0

    if req.mode == "deep":
        return _locate_deep(
            req, settings, manifest, prior_of, engine, symbol_engine, scout_engine, deep_engine
        )
    if req.mode == "fast":
        return _locate_scout(
            req, settings, manifest, prior_of, engine, symbol_engine, scout_engine, gate
        )

    return _locate_auto(
        req,
        settings,
        manifest,
        prior_of,
        engine,
        symbol_engine,
        scout_engine,
        deep_engine,
        gate=gate,
        classifier=classifier,
        index_ready=index_ready,
    )


def _locate_auto(
    req: LocateRequest,
    settings: Settings,
    manifest: dict,
    prior_of: Callable[[str], float],
    engine: _Engine,
    symbol_engine: _Engine,
    scout_engine: _Engine | None,
    deep_engine: object | None,
    *,
    gate: VerificationGate | None,
    classifier: Classifier,
    index_ready: bool,
) -> LocateResult:
    """mode=auto — the full ladder: classifier → matrix → seed → Scout → gate → Deep.

    Realized `tiers_run` is a prefix of the planned ladder: the gate decides
    whether the trailing Tier-2 step runs. Replaces the Wave-0 zero-call lock.
    """
    # The planning matrix is the single source of truth: it returns the planned
    # ladder, and the routing below is derived from it (never a second authority).
    classification = classifier(req.query)
    ladder = plan_ladder("auto", classification, index_ready)
    seed_prefix = [0] if 0 in ladder else []

    if 1 not in ladder:
        # broad routes straight to Deep — Scout skipped, no gate (matrix rows 3/4).
        return _run_deep(
            req, manifest, prior_of, engine, symbol_engine, scout_engine, deep_engine,
            base_tiers=seed_prefix,
        )

    # point ladder: seed → Scout → gate → maybe Deep.
    if scout_engine is None:
        # Scout not wired → auto is the clean Tier-0 floor (no degrade note).
        return _tier0_floor(req, manifest, prior_of, engine, symbol_engine)

    try:
        scout_spans = scout_engine.search(req.query, scope=req.repo_path)
    except ScoutUnavailable as err:
        # typed-unavailable → degrade to Tier-0 (UNCHANGED). RipgrepMissingError /
        # AirGapError propagate as the floor.
        return _degrade(req, manifest, prior_of, engine, symbol_engine, err.cause)

    scout_spans, hint_note = _apply_language_hint(scout_spans, manifest, req.language_hint)
    tier1_tiers = seed_prefix + [1]

    if not scout_spans:
        # honest-empty: gate skipped (nothing to score), return the Tier-0 seed.
        return _honest_empty(
            req, manifest, prior_of, engine, symbol_engine, tier1_tiers, index_ready
        )

    citations = format_citations(scout_spans, prior_of, req.max_results, source_tier=1)

    if gate is None:
        # No gate wired → cannot vouch and cannot escalate; return Scout best-effort.
        return LocateResult(citations, "medium", tier1_tiers, hint_note)

    outcome = gate.verify(req.query, citations, repo_path=req.repo_path, settings=settings)
    if outcome.passed:
        return LocateResult(citations, "high", tier1_tiers, _join(hint_note))

    # gate fail OR gate-scoring-failed (the malformed/un-scoreable case): escalate
    # to Deep if a tier remains, else best-effort Tier-1 + flag.
    flag = GATE_SCORING_FAILED if outcome.failed else None
    if deep_engine is None:
        conf = "low" if flag else ("medium" if citations else "low")
        return LocateResult(citations, conf, tier1_tiers, _join(flag, hint_note))
    return _run_deep(
        req, manifest, prior_of, engine, symbol_engine, scout_engine, deep_engine,
        base_tiers=tier1_tiers, extra_note=flag, hint_note=hint_note,
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
    settings: Settings,
    manifest: dict,
    prior_of: Callable[[str], float],
    engine: _Engine,
    symbol_engine: _Engine,
    scout_engine: _Engine | None,
    gate: VerificationGate | None = None,
) -> LocateResult:
    """Tier 1 (Scout). Explicit `fast` mode; degrades to Tier 0 on model failure.

    `RipgrepMissingError` (from Scout's self-seed) and `AirGapError` (a
    non-loopback endpoint) propagate loudly — they are the degradation floor,
    not a degrade state. Only `ScoutUnavailable` falls back to Tier 0.

    `fast` is an explicit cost **ceiling**: the gate (when wired) runs
    **informationally** and never escalates. A would-fail gate attaches
    `gate-low-confidence`; a gate-scoring failure attaches `gate-scoring-failed`
    (best-effort Tier-1). A clean-empty Scout result is `gate-skipped:scout-empty`
    (the gate has nothing to score — not a low-confidence signal).
    """
    if scout_engine is None:
        # Scout not wired → honest degrade, never a silent no-op.
        return _degrade(req, manifest, prior_of, engine, symbol_engine, NO_ENDPOINT_CONFIGURED)

    try:
        spans = scout_engine.search(req.query, scope=req.repo_path)
    except ScoutUnavailable as err:
        return _degrade(req, manifest, prior_of, engine, symbol_engine, err.cause)

    spans, hint_note = _apply_language_hint(spans, manifest, req.language_hint)

    if not spans:
        # honest-empty: gate skipped (nothing to score), not a low-confidence signal.
        return LocateResult([], "low", [0, 1], _join(GATE_SKIPPED_SCOUT_EMPTY, hint_note))

    citations = format_citations(spans, prior_of, req.max_results, source_tier=1)

    confidence = "medium" if citations else "low"
    flag: str | None = None
    if gate is not None:
        outcome = gate.verify(req.query, citations, repo_path=req.repo_path, settings=settings)
        if outcome.failed:
            flag, confidence = GATE_SCORING_FAILED, "low"
        elif not outcome.passed:
            flag, confidence = GATE_LOW_CONFIDENCE, "low"
        else:
            confidence = "high"

    return LocateResult(
        citations=citations,
        confidence=confidence,
        tiers_run=[0, 1],
        notes=_join(flag, hint_note),
    )


def _locate_deep(
    req: LocateRequest,
    settings: Settings,
    manifest: dict,
    prior_of: Callable[[str], float],
    engine: _Engine,
    symbol_engine: _Engine,
    scout_engine: _Engine | None,
    deep_engine: object | None,
) -> LocateResult:
    """Tier 2 (Deep). Explicit `deep` mode; degrades to Scout best-effort on a typed
    `DeepUnavailable` (NOT on weak/zero output — that would be an ungated
    escalation). `RipgrepMissingError` (Deep's self-seed) and `AirGapError`
    propagate loudly as the floor; a budget truncation is an honest bounded
    Tier-2 result carrying a `deep-truncated:<bound>` note, never a degrade.
    """
    if deep_engine is None:
        # Deep not wired → degrade to Scout best-effort, honestly flagged.
        fallback = _locate_scout(
            req, settings, manifest, prior_of, engine, symbol_engine, scout_engine
        )
        return _with_deep_note(fallback, f"deep-degraded:{NO_ENDPOINT_CONFIGURED}")

    try:
        spans, truncated = deep_engine.run(req.query)
    except DeepUnavailable as err:
        fallback = _locate_scout(
            req, settings, manifest, prior_of, engine, symbol_engine, scout_engine
        )
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


def _run_deep(
    req: LocateRequest,
    manifest: dict,
    prior_of: Callable[[str], float],
    engine: _Engine,
    symbol_engine: _Engine,
    scout_engine: _Engine | None,
    deep_engine: object | None,
    *,
    base_tiers: list[int],
    extra_note: str | None = None,
    hint_note: str | None = None,
) -> LocateResult:
    """Run Tier 2 from the auto ladder, reporting `tiers_run = base_tiers + [2]`.

    Used by the `broad` route (`base_tiers` = seed prefix) and by a point-query
    escalation (`base_tiers` = `[0,1]` / `[1]`). `extra_note` carries an escalation
    flag (e.g. `gate-scoring-failed`). Degradation mirrors `_locate_deep`: a typed
    `DeepUnavailable` falls back to Scout best-effort with a `deep-degraded` note;
    the floors propagate.
    """
    if deep_engine is None:
        fallback = _locate_scout(
            req, Settings(), manifest, prior_of, engine, symbol_engine, scout_engine
        )
        return _with_deep_note(fallback, f"deep-degraded:{NO_ENDPOINT_CONFIGURED}")

    try:
        spans, truncated = deep_engine.run(req.query)
    except DeepUnavailable as err:
        fallback = _locate_scout(
            req, Settings(), manifest, prior_of, engine, symbol_engine, scout_engine
        )
        return _with_deep_note(fallback, f"deep-degraded:{err.cause}")

    spans, dhint = _apply_language_hint(spans, manifest, req.language_hint)
    citations = format_citations(spans, prior_of, req.max_results, source_tier=2)

    notes: list[str] = []
    if extra_note:
        notes.append(extra_note)
    if truncated:
        notes.append(f"deep-truncated:{truncated}")
    notes.append(dhint or hint_note or "")

    # A retained gate-scoring-failed flag pins confidence to low even on a Deep run.
    confidence = "low" if extra_note == GATE_SCORING_FAILED else ("medium" if citations else "low")
    joined = "; ".join(n for n in notes if n)
    return LocateResult(
        citations=citations,
        confidence=confidence,
        tiers_run=list(base_tiers) + [2],
        notes=joined or None,
    )


def _tier0_floor(
    req: LocateRequest,
    manifest: dict,
    prior_of: Callable[[str], float],
    engine: _Engine,
    symbol_engine: _Engine,
) -> LocateResult:
    """auto with no Scout wired: the clean symbol-aware Tier-0 result (`tiers_run=[0]`).

    This is the honest floor, not a degrade — no `scout-degraded` note, and no
    retired `mode has no effect` lock note.
    """
    spans = _tier0_seed(req, engine, symbol_engine)
    spans, hint_note = _apply_language_hint(spans, manifest, req.language_hint)
    citations = format_citations(spans, prior_of, req.max_results)
    return LocateResult(
        citations=citations,
        confidence="medium" if citations else "low",
        tiers_run=[0],
        notes=hint_note,
    )


def _honest_empty(
    req: LocateRequest,
    manifest: dict,
    prior_of: Callable[[str], float],
    engine: _Engine,
    symbol_engine: _Engine,
    tiers: list[int],
    index_ready: bool,
) -> LocateResult:
    """Scout ran cleanly but returned zero citations: gate skipped, return the seed.

    Tagged `gate-skipped:scout-empty` so this `[0,1]`/`[1]` path is never read as a
    high-confidence gated-pass (it shares those tokens). A `+no-matches` suffix
    marks an empty seed. Never escalates — honest "nothing found".
    """
    if index_ready:
        spans = _tier0_seed(req, engine, symbol_engine)
        spans, _hint = _apply_language_hint(spans, manifest, req.language_hint)
        citations = format_citations(spans, prior_of, req.max_results)
    else:
        # No seed (query-only) and Scout empty → genuinely nothing.
        citations = []

    note = GATE_SKIPPED_SCOUT_EMPTY
    if not citations:
        note += "+no-matches"
    return LocateResult(
        citations=citations,
        confidence="medium" if citations else "low",
        tiers_run=tiers,
        notes=note,
    )


def _join(*parts: str | None) -> str | None:
    """Join non-empty note fragments with `; `; return None if all empty."""
    joined = "; ".join(p for p in parts if p)
    return joined or None


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
