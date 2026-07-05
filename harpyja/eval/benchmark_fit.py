"""Spec 0023 — benchmark-fit verdict machinery (pure, additive; SUT frozen).

The typed, two-axis, pre-registered discriminator that decides the NEXT spec:

- **Axis 1 (query shape)** — a within-case paired A/B over a BINARY outcome, so the
  paired test is exact two-sided McNemar and power lives in the DISCORDANT pairs, not
  raw N. `decide_axis1` is a total function over a frozen config with an uncertainty
  gate; its three `INCONCLUSIVE` triggers are named separately so no path silently
  defaults.
- **Axis 2 (representativeness)** — a structured record → `representative: bool`.
- **Composition** — the pre-registered 2×2 (`compose_verdict`); Axis 2 can downgrade
  Axis 1's routing. Fixed BEFORE the run so the verdict cannot be steered post-hoc.

Everything here is a pure function over `PREREGISTERED_CONFIG`; there is no I/O and no
SUT import beyond the frozen taxonomy enum (`LocateBucket`).
"""

from __future__ import annotations

import enum
import math
from collections.abc import Sequence
from dataclasses import dataclass

from harpyja.eval.locate_accuracy import LocateBucket

# ---- AC4: exact two-sided McNemar ------------------------------------------


def mcnemar_exact_p(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value for discordant counts (b, c).

    Under H0 the discordant pairs are a sign test at p=0.5 over `n = b + c` trials;
    the two-sided exact p doubles the lower tail at `k = min(b, c)`. Clamped to 1.0
    (so `n = 0` → 1.0, i.e. no discordant evidence can never reject). Symmetric in
    `(b, c)`. Boundary pins: 6/0→0.03125, 5/0→0.0625, 8/0→0.0078125, 7/1→0.0703125.
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1))
    return min(1.0, 2.0 * tail / (2**n))


def mcnemar_rejects(b: int, c: int, *, alpha: float = 0.05) -> bool:
    """Whether the exact two-sided McNemar test rejects H0 at ``alpha``."""
    return mcnemar_exact_p(b, c) < alpha


# ---- AC4/AC6: frozen pre-registered config ---------------------------------


@dataclass(frozen=True)
class BenchmarkFitConfig:
    """The pre-registered decision config — a pure verdict input, frozen so the
    thresholds cannot be tuned after seeing the data.

    `MIN_DISCORDANT_PAIRS = 8` is derived from exact-McNemar reachability (6 is the
    bare floor where a unanimous split first clears α=0.05; 8 buys one contrary pair
    of slack), NOT a round guess — see spec OQ1.
    """

    MIN_DISCORDANT_PAIRS: int = 8
    DELTA_EMPTY_BAND: float = 0.20
    min_n: int = 12
    alpha: float = 0.05
    # REPRESENTATIVE_THRESHOLD inputs (Axis 2 → representative:bool).
    low_documentation_density: str = "low"
    weak_target_proxy: str = "weak"


PREREGISTERED_CONFIG = BenchmarkFitConfig()


# ---- AC3: paired aggregator (from retained per-case pairs) ------------------


@dataclass(frozen=True)
class PairedRow:
    """One within-case pair: the same gold span scored on the raw vs distilled arm."""

    case_id: str
    raw_bucket: LocateBucket
    distilled_bucket: LocateBucket


@dataclass(frozen=True)
class PairedAggregate:
    """Paired deltas + discordant counts computed FROM the retained pairs (AC3).

    `delta_empty` is the within-case mean of (raw_empty − distilled_empty): positive
    means distillation CUT the empty-rate (the QUERY_SHAPE direction). `delta_file_
    accuracy` is the within-case mean of (distilled_found − raw_found): positive means
    distillation found the file MORE often. Both agree in sign when distillation helps.
    """

    n: int
    delta_empty: float
    delta_file_accuracy: float
    discordant_b: int  # raw EMPTY, distilled not-empty (distillation improved)
    discordant_c: int  # raw not-empty, distilled EMPTY (distillation worsened)
    discordant_pairs: int


def _is_empty(bucket: LocateBucket) -> bool:
    return bucket is LocateBucket.EMPTY


def _found_file(bucket: LocateBucket) -> bool:
    return bucket in (LocateBucket.CORRECT, LocateBucket.RIGHT_FILE_WRONG_SPAN)


def aggregate_paired(rows: Sequence[PairedRow]) -> PairedAggregate:
    """Reduce retained per-case pairs to paired deltas + discordant counts (pure)."""
    n = len(rows)
    if n == 0:
        return PairedAggregate(0, 0.0, 0.0, 0, 0, 0)
    raw_empty = sum(_is_empty(r.raw_bucket) for r in rows)
    dist_empty = sum(_is_empty(r.distilled_bucket) for r in rows)
    raw_file = sum(_found_file(r.raw_bucket) for r in rows)
    dist_file = sum(_found_file(r.distilled_bucket) for r in rows)
    b = sum(_is_empty(r.raw_bucket) and not _is_empty(r.distilled_bucket) for r in rows)
    c = sum((not _is_empty(r.raw_bucket)) and _is_empty(r.distilled_bucket) for r in rows)
    return PairedAggregate(
        n=n,
        delta_empty=(raw_empty - dist_empty) / n,
        delta_file_accuracy=(dist_file - raw_file) / n,
        discordant_b=b,
        discordant_c=c,
        discordant_pairs=b + c,
    )


# ---- AC4: total Axis-1 verdict ---------------------------------------------


class Axis1Verdict(enum.Enum):
    QUERY_SHAPE = "query-shape"
    CAPABILITY = "capability"
    INCONCLUSIVE = "inconclusive"


class InconclusiveReason(enum.Enum):
    INSUFFICIENT_POWER = "insufficient-power"
    DISTILLER_ARM_DISAGREEMENT = "distiller-arm-disagreement"
    AXIS_SIGNAL_DISAGREEMENT = "axis-signal-disagreement"


def _sign(x: float) -> int:
    return (x > 0) - (x < 0)


def decide_axis1(
    agg: PairedAggregate,
    *,
    usable_n: int,
    llm_delta_empty: float | None = None,
    config: BenchmarkFitConfig = PREREGISTERED_CONFIG,
) -> tuple[Axis1Verdict, InconclusiveReason | None]:
    """The Axis-1 verdict: a total function with non-overlapping predicates (AC4).

    Order (each guard returns, so the branch table is total and non-overlapping):
    power gate → axis-signal disagreement → distiller-arm disagreement → QUERY_SHAPE →
    (materially-positive-but-not-significant) → CAPABILITY. Power is checked FIRST —
    under insufficient power the deltas are noise and their signs are not trustworthy.
    """
    powered = (
        agg.discordant_pairs >= config.MIN_DISCORDANT_PAIRS and usable_n >= config.min_n
    )
    if not powered:
        return Axis1Verdict.INCONCLUSIVE, InconclusiveReason.INSUFFICIENT_POWER

    # axis-signal disagreement: empty-rate and file-accuracy deltas point opposite ways.
    se, sf = _sign(agg.delta_empty), _sign(agg.delta_file_accuracy)
    if se and sf and se != sf:
        return Axis1Verdict.INCONCLUSIVE, InconclusiveReason.AXIS_SIGNAL_DISAGREEMENT

    # distiller-arm disagreement: the mechanical (primary) and LLM (sensitivity) arms
    # move delta_empty in opposite directions.
    if llm_delta_empty is not None:
        sl = _sign(llm_delta_empty)
        if se and sl and se != sl:
            return (
                Axis1Verdict.INCONCLUSIVE,
                InconclusiveReason.DISTILLER_ARM_DISAGREEMENT,
            )

    material = agg.delta_empty >= config.DELTA_EMPTY_BAND
    rejects = mcnemar_rejects(agg.discordant_b, agg.discordant_c, alpha=config.alpha)
    if material and rejects:
        return Axis1Verdict.QUERY_SHAPE, None
    if material and not rejects:
        # materially-positive point estimate that the exact test cannot certify.
        return Axis1Verdict.INCONCLUSIVE, InconclusiveReason.INSUFFICIENT_POWER
    # flat with adequate power → distillation genuinely did not help.
    return Axis1Verdict.CAPABILITY, None


# ---- AC5: structured representativeness record ------------------------------


@dataclass(frozen=True)
class RepresentativenessRecord:
    """Axis 2 — a structured (not prose) codebase-character assessment (AC5)."""

    query_shape: str
    repo_type: str
    documentation_density: str
    codebase_age: str
    target_proxy_validity: str


def is_representative(
    record: RepresentativenessRecord, *, config: BenchmarkFitConfig = PREREGISTERED_CONFIG
) -> bool:
    """Apply the pre-registered `REPRESENTATIVE_THRESHOLD`: `False` iff BOTH the
    documentation density is low (undocumented, unlike OSS) AND the target-proxy
    validity is weak. Either one alone does not flip it."""
    return not (
        record.documentation_density == config.low_documentation_density
        and record.target_proxy_validity == config.weak_target_proxy
    )


# ---- AC6: pre-registered 2×2 composition -----------------------------------


class NextSpec(enum.Enum):
    ADD_REFORMULATION_LAYER = "add-reformulation-layer"
    BUILD_TERSE_QUERY_BENCHMARK = "build-terse-query-benchmark"
    N38_PLUS_FINDER_CAPABILITY = "n38-plus-finder-capability"
    RETIRE_SWEBENCH = "retire-swebench"
    HOLD_INCONCLUSIVE = "hold-inconclusive"


@dataclass(frozen=True)
class BenchmarkFitVerdict:
    axis1: Axis1Verdict
    representative: bool
    next_spec: NextSpec


def compose_verdict(axis1: Axis1Verdict, *, representative: bool) -> BenchmarkFitVerdict:
    """The fixed 2×2 (Axis 2 downgrades Axis 1). Total over `Axis1Verdict × bool`.

    - QUERY_SHAPE × representative   → add a reformulation layer
    - QUERY_SHAPE × ¬representative  → build a terse-query benchmark first (NOT a swap)
    - CAPABILITY  × representative   → N=38 confirmation + finder-capability work
    - CAPABILITY  × ¬representative  → retire SWE-bench as the yardstick
    - INCONCLUSIVE (either)          → hold; the discriminator has not resolved
    """
    if axis1 is Axis1Verdict.INCONCLUSIVE:
        next_spec = NextSpec.HOLD_INCONCLUSIVE
    elif axis1 is Axis1Verdict.QUERY_SHAPE:
        next_spec = (
            NextSpec.ADD_REFORMULATION_LAYER
            if representative
            else NextSpec.BUILD_TERSE_QUERY_BENCHMARK
        )
    else:  # CAPABILITY
        next_spec = (
            NextSpec.N38_PLUS_FINDER_CAPABILITY
            if representative
            else NextSpec.RETIRE_SWEBENCH
        )
    return BenchmarkFitVerdict(axis1=axis1, representative=representative, next_spec=next_spec)
