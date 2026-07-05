"""Spec 0022 — Scout locate-accuracy taxonomy, two-granularity scoring, decision rule.

A PURE, additive eval-side projection above the FROZEN oracle
(`harpyja.eval.metrics.span_hit_kind` / `span_hit_secondary`). Nothing under
`harpyja/scout/` or `harpyja/orchestrator/` changes; this module only READS the
oracle's overlap verdict and the SUT's `ScoutTally` (spec 0012 suffix-recovery
side-channel) — it never re-derives routing or re-implements suffix recovery.

The single deliberate departure from the oracle lives ONLY here: a path-only
right-file citation (`span_hit_kind == "file"`) is scored ``RIGHT_FILE_WRONG_SPAN``,
NOT ``CORRECT`` — because the whole diagnostic axis is "found the file" vs "found the
span." `metrics.py` is untouched and its `span_hit_primary` (which counts a path-only
hit as a localization) keeps its meaning for every other consumer.
"""

from __future__ import annotations

import enum
from collections.abc import Sequence
from dataclasses import dataclass

from harpyja.eval.metrics import span_hit_kind, span_hit_secondary
from harpyja.scout.engine import ScoutTally
from harpyja.server.types import CodeSpan

# AC10 — the EXACT frozen SUT surface this additive projection is allowed to consume.
# Read-only: the module reads the oracle's verdict (`span_hit_kind` /
# `span_hit_secondary`) and the SUT's `ScoutTally`, and constructs `CodeSpan`. It
# NEVER imports Scout/orchestrator internals and never edits `metrics.py`. The one
# deliberate re-map (path-only right-file `"file"` → RIGHT_FILE_WRONG_SPAN) lives only
# in `_classify_one`. Widening this set is a reviewed decision, not an accident.
SUT_SURFACE: frozenset[str] = frozenset(
    {
        "harpyja.eval.metrics.span_hit_kind",
        "harpyja.eval.metrics.span_hit_secondary",
        "harpyja.scout.engine.ScoutTally",
        "harpyja.server.types.CodeSpan",
    }
)


@dataclass(frozen=True)
class NormalizedCitations:
    """The effective citations for a case plus the SUT's normalization tally counts.

    ``effective`` are the citations Scout actually returned (the SUT's
    ``ScoutEngine.search`` already applied suffix recovery and dropped malformed refs
    — this layer does NOT re-run that). ``normalization_dropped`` surfaces the tally's
    ``dropped`` so an EMPTY-after-drop case stays distinct from a returned-nothing one.
    """

    effective: tuple[CodeSpan, ...]
    normalization_dropped: int
    recovered_spanned: int
    recovered_filelevel: int


def normalize_citations(
    citations: Sequence[CodeSpan], tally: ScoutTally | None
) -> NormalizedCitations:
    """Assemble the effective-citations view + the SUT tally counts (pure, read-only).

    ``citations`` is the post-normalization output of ``ScoutEngine.search`` (suffix
    recovery already applied, malformed already dropped). The recovery/drop *counts*
    are read off ``tally`` — never re-derived. A ``None`` tally (tier not run /
    uncaptured) yields honest zeros.
    """
    return NormalizedCitations(
        effective=tuple(citations),
        normalization_dropped=tally.dropped if tally else 0,
        recovered_spanned=tally.recovered_spanned if tally else 0,
        recovered_filelevel=tally.recovered_filelevel if tally else 0,
    )


# ---- AC1: the 4-way locate taxonomy ----------------------------------------

class LocateBucket(enum.Enum):
    """The mutually-exclusive locate outcome for one case (best over its citations).

    Precedence (best → worst): ``CORRECT > RIGHT_FILE_WRONG_SPAN > WRONG_FILE >
    EMPTY``. A case takes its single best bucket so the taxonomy is MECE even when
    Scout returns multiple citations of mixed quality.
    """

    CORRECT = "correct"
    RIGHT_FILE_WRONG_SPAN = "right-file-wrong-span"
    WRONG_FILE = "wrong-file"
    EMPTY = "empty"


@dataclass(frozen=True)
class SubFlags:
    """Recorded sub-signals on a ``RIGHT_FILE_WRONG_SPAN`` case (else both False).

    - ``path_only_right_file``: the right-file evidence was a line-less (path-only)
      citation — the oracle's ``"file"`` kind, re-mapped here out of ``CORRECT``.
    - ``within_window``: a lined right-file miss fell within the proximity window
      (the secondary-metric zone) rather than beyond it.
    """

    within_window: bool = False
    path_only_right_file: bool = False


# Numeric rank so "best over citations" is a plain max(); higher = better.
_RANK = {
    LocateBucket.EMPTY: 0,
    LocateBucket.WRONG_FILE: 1,
    LocateBucket.RIGHT_FILE_WRONG_SPAN: 2,
    LocateBucket.CORRECT: 3,
}


def classify_case(
    citations: Sequence[CodeSpan],
    expected_spans: Sequence[CodeSpan],
    *,
    window: int,
) -> tuple[LocateBucket, SubFlags]:
    """Classify one case into the best `LocateBucket` over all its citations (pure).

    Routes every overlap judgment through the FROZEN oracle
    (`metrics.span_hit_kind` / `span_hit_secondary`). The one re-map: a right-file
    path-only citation (oracle ``"file"``) is ``RIGHT_FILE_WRONG_SPAN``, not
    ``CORRECT``. Empty citation set → ``EMPTY``.
    """
    best = LocateBucket.EMPTY
    flags = SubFlags()
    for cited in citations:
        bucket, cited_flags = _classify_one(cited, expected_spans, window=window)
        if _RANK[bucket] > _RANK[best]:
            best, flags = bucket, cited_flags
    return best, flags


def _classify_one(
    cited: CodeSpan, expected_spans: Sequence[CodeSpan], *, window: int
) -> tuple[LocateBucket, SubFlags]:
    """The per-citation verdict against the best gold span it touches."""
    in_gold_file = False
    path_only = False
    within = False
    for gold in expected_spans:
        kind = span_hit_kind(cited, gold)
        if kind == "line":
            return LocateBucket.CORRECT, SubFlags()
        if kind == "file":
            # right file, path-only (line-less) → found the file, not the span.
            in_gold_file = True
            path_only = True
            continue
        if cited.path == gold.path:
            # right file, lined, but no line overlap → wrong span; is it within window?
            in_gold_file = True
            if span_hit_secondary(cited, gold, window):
                within = True
    if in_gold_file:
        return LocateBucket.RIGHT_FILE_WRONG_SPAN, SubFlags(
            within_window=within, path_only_right_file=path_only
        )
    return LocateBucket.WRONG_FILE, SubFlags()


# ---- AC2: two-granularity scoring ------------------------------------------

# A per-case classification row the scorer consumes: (bucket, sub-flags, dropped).
ClassifiedCase = tuple[LocateBucket, SubFlags, int]


@dataclass(frozen=True)
class LocateDistribution:
    """The regenerated locate-accuracy distribution (AC2/AC4).

    ``file_level_accuracy`` credits both ``CORRECT`` and ``RIGHT_FILE_WRONG_SPAN``
    (Scout put a citation in a gold file); ``span_level_accuracy`` credits only
    ``CORRECT`` (line overlap). ``gap = file − span`` is the first-class
    precision-vs-retrieval signal.
    """

    n: int
    counts: dict[LocateBucket, int]
    file_level_accuracy: float
    span_level_accuracy: float
    gap: float
    empty_rate: float
    normalization_dropped_total: int


def score_distribution(classified: Sequence[ClassifiedCase]) -> LocateDistribution:
    """Aggregate per-case buckets into the two-granularity distribution (pure).

    An empty population is honestly zeroed (no division by zero).
    """
    n = len(classified)
    counts = {bucket: 0 for bucket in LocateBucket}
    dropped_total = 0
    for bucket, _flags, dropped in classified:
        counts[bucket] += 1
        dropped_total += dropped
    if n == 0:
        return LocateDistribution(
            n=0,
            counts=counts,
            file_level_accuracy=0.0,
            span_level_accuracy=0.0,
            gap=0.0,
            empty_rate=0.0,
            normalization_dropped_total=0,
        )
    file_hits = counts[LocateBucket.CORRECT] + counts[LocateBucket.RIGHT_FILE_WRONG_SPAN]
    span_hits = counts[LocateBucket.CORRECT]
    file_level = file_hits / n
    span_level = span_hits / n
    return LocateDistribution(
        n=n,
        counts=counts,
        file_level_accuracy=file_level,
        span_level_accuracy=span_level,
        gap=file_level - span_level,
        empty_rate=counts[LocateBucket.EMPTY] / n,
        normalization_dropped_total=dropped_total,
    )


# ---- AC7: the typed-finding decision rule ----------------------------------

# Pre-declared bands (provisional; the per-case rows in findings.md are the auditable
# ground truth). Named so the decision is reproducible, not eyeballed.
LOW_FILE_BAND: float = 0.25          # file-level accuracy at/below this ⇒ "low F"
EMPTY_DOMINANT_BAND: float = 0.5     # empty-rate at/above this ⇒ "empty-dominant"
LARGE_GAP_BAND: float = 0.30         # (file − span) at/above this ⇒ "F ≫ S"
MATERIAL_DELTA_EMPTY: float = 0.20   # probe empty-rate reduction at/above this ⇒ fired


class FindingLabel(enum.Enum):
    """The branching typed finding (AC7) — exactly one is chosen per run."""

    PRECISION_FIXABLE = "precision-fixable"
    RETRIEVAL_FUNDAMENTAL = "retrieval-fundamental"
    BENCHMARK_UNREPRESENTATIVE = "benchmark-unrepresentative"
    MIXED = "mixed"


# Where each finding routes the next spec (named, not a downstream guess).
_ROUTES = {
    FindingLabel.PRECISION_FIXABLE: (
        "span-refinement fix (e.g. Tier-0 AST re-narrowing in the found file)"
    ),
    FindingLabel.RETRIEVAL_FUNDAMENTAL: "finder-capability spec (different/larger finder)",
    FindingLabel.BENCHMARK_UNREPRESENTATIVE: "dataset/benchmark spec (query-shape, not finder)",
    FindingLabel.MIXED: "both leads, prioritized by count",
}


@dataclass(frozen=True)
class Finding:
    """The recorded typed finding + the observed numbers that produced it."""

    label: FindingLabel
    file_level_accuracy: float
    span_level_accuracy: float
    empty_rate: float
    gap: float
    delta_empty: float
    representative: bool
    conditions: dict[str, bool]
    routes_to: str


def decide_finding(
    dist: LocateDistribution, *, delta_empty: float, representative: bool
) -> Finding:
    """Route the distribution to exactly one `FindingLabel` by the ordered rule.

    Order (first match wins):
      1. BENCHMARK_UNREPRESENTATIVE — (low-F OR empty-dominant) AND (the distilled
         probe materially cut the empty-rate OR the queries are judged
         unrepresentative). The probe is the discriminator vs. rule 3.
      2. PRECISION_FIXABLE — F not low AND a large file-minus-span gap (finds files,
         misses spans).
      3. RETRIEVAL_FUNDAMENTAL — (low-F OR empty-dominant) AND the probe was flat AND
         the queries are representative (a genuine finder-capability gap).
      4. MIXED — no dominant mode.
    """
    low_f = dist.file_level_accuracy <= LOW_FILE_BAND
    empty_dominant = dist.empty_rate >= EMPTY_DOMINANT_BAND
    large_gap = dist.gap >= LARGE_GAP_BAND
    probe_fired = delta_empty >= MATERIAL_DELTA_EMPTY

    conditions = {
        "low_f": low_f,
        "empty_dominant": empty_dominant,
        "large_gap": large_gap,
        "probe_fired": probe_fired,
        "representative": representative,
    }

    weak_retrieval = low_f or empty_dominant
    if weak_retrieval and (probe_fired or not representative):
        label = FindingLabel.BENCHMARK_UNREPRESENTATIVE
    elif large_gap and not low_f:
        label = FindingLabel.PRECISION_FIXABLE
    elif weak_retrieval and not probe_fired and representative:
        label = FindingLabel.RETRIEVAL_FUNDAMENTAL
    else:
        label = FindingLabel.MIXED

    return Finding(
        label=label,
        file_level_accuracy=dist.file_level_accuracy,
        span_level_accuracy=dist.span_level_accuracy,
        empty_rate=dist.empty_rate,
        gap=dist.gap,
        delta_empty=delta_empty,
        representative=representative,
        conditions=conditions,
        routes_to=_ROUTES[label],
    )
