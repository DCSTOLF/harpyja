"""Spec 0040 — pool: frozen 3-model/3-pair power pre-check config + machinery.

The bake-off expands from 2 models to 3 (``qwen3:14b`` / ``qwen3:8b`` /
``qwen3.5:4b`` — three sizes, two generations), giving THREE pairwise
contrasts. This module freezes every verdict-shaping choice BEFORE any live
preflight/pilot call fires (the 0036 re-registration rule: the 0039 freeze
pins one model and two think-arms and cannot govern a 3-model pre-check).

MULTIPLICITY (decided outcome-blind, frozen here): per-pair alpha,
UNCORRECTED. Each pair answers a distinct standalone decision question ("does
A beat B for the ~16B box") — not a family-wise "does any pair differ"; the
8b-vs-4b cut is independently decision-relevant regardless of the other two
pairs. Deciding this after seeing which pairs clear the floor would be the
post-hoc steering the freeze forbids.

TWO per-pair quantities, each labeled by its EPISTEMIC KIND (the
bound-is-not-an-estimate discipline, both directions):

1. the CEILING — the extrapolated per-case UNION-located count
   (``projection_kind="upper-bound-feasibility"``). A TRUE bound: signal
   discordance requires >= 1 located arm by ``is_signal_discordant``'s own
   definition (one-oracle reuse justifying the bound). Gates
   ``PAIR_UNDER_POWERED`` — the stop-quality claim rests ONLY on this bound.
2. the OBSERVED signal-discordance (``estimate_kind="point-estimate"``) —
   pilot pairs through ``is_signal_discordant``, extrapolated. Drives the
   ``PAIR_MODELS_TOO_CLOSE`` vs ``PAIR_FEASIBLE`` split — a REPORTABLE
   closeness finding, never the unimpeachable stop.

Extrapolating observed discordance and calling it a bound would be an
epistemic mislabel (a false UNDER_POWERED from sampling noise); a literal
max-possible bound over unpiloted cases is vacuous (unobserved mass alone
clears the floor). NEVER compute either quantity from marginal locate-counts:
6/7 vs 5/7 is identical whether the located sets fully overlap (TOO_CLOSE) or
are nearly disjoint; union-located and discordance are per-case properties
marginals cannot recover.

PREFLIGHT-ENUM ASYMMETRY (deliberate, load-bearing — do not "fix" into
symmetry): ``UNSERVABLE`` / ``COHERENCE_FAIL`` / ``TOOL_CALL_MALFORMED`` are
EXCLUDING (the model produces no capability number — the 16B-gibberish
lesson); ``THINK_CONTROL_NOOP`` is RECORDED-NON-EXCLUDING (the model still
bakes off default-on; it is only barred from a future thinking-arm). An
INDETERMINATE think-control probe maps to ``THINK_CONTROL_NOOP`` —
conservative, inside the committed answer space.

STAGING (OQ3, pre-declared): preflight all 3, then pilot the widest-gap pair
first — never chosen after early results are visible.
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

# One-oracle reuse (identity-asserted by test): the located predicate and the
# discordance predicate are THE committed ones — never re-derived locally.
from harpyja.eval.ac8_pilot import PilotPair, is_signal_discordant
from harpyja.eval.benchmark_fit import PREREGISTERED_CONFIG
from harpyja.eval.locate_accuracy import LocateBucket
from harpyja.eval.think_ab import located_via_oracle

# The pinned pilot set: the 0036 first-10 subset (7 conceptual / 3 lexical)
# extended by the NEXT conceptual case in committed fixture order
# (django__django-14315) to reach the derived coverage minimum of 8 —
# selection by fixture order, no cherry-picking after 0039's per-case results.
_PILOT_CASE_IDS = (
    "astropy__astropy-12907",
    "django__django-13516",
    "matplotlib__matplotlib-21568",
    "pallets__flask-5014",
    "pydata__xarray-3993",
    "pytest-dev__pytest-10081",
    "scikit-learn__scikit-learn-10844",
    "psf__requests-1766",
    "pylint-dev__pylint-7080",
    "sympy__sympy-16792",
    "django__django-14315",
)


@dataclasses.dataclass(frozen=True)
class PoolConfig:
    """Pre-registered 0040 pool pre-check config (frozen; hashed pre-run)."""

    # The three model tags (three sizes, two generations) and the three named
    # pairwise contrasts.
    model_tags: tuple[str, ...] = ("qwen3:14b", "qwen3:8b", "qwen3.5:4b")
    pairs: tuple[tuple[str, str], ...] = (
        ("qwen3:14b", "qwen3:8b"),
        ("qwen3:14b", "qwen3.5:4b"),
        ("qwen3:8b", "qwen3.5:4b"),
    )

    # Statistics. Floor FIXED at the committed 0023 exact-McNemar floor —
    # copied verbatim from the same source 0039 pinned, never re-derivable.
    alpha: float = 0.05
    conceptual_min_discordant: int = PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS
    floor_derivation: str = "fixed-not-re-derivable"

    # Multiplicity — frozen outcome-blind (see module docstring).
    multiplicity_stance: str = "per-pair-alpha-uncorrected"
    multiplicity_rationale: str = (
        "each pair answers a distinct standalone decision question; the "
        "8b-vs-4b cut is independently decision-relevant for the ~16B box — "
        "not a family-wise 'any pair differs' claim"
    )

    # The pinned pilot set + the DERIVED coverage minimum: the unpiloted
    # conceptual remainder must be strictly smaller than the floor
    # (15 - c < 8 => c >= 8), else a verdict rests on majority-unobserved mass.
    pilot_case_ids: tuple[str, ...] = _PILOT_CASE_IDS
    full_conceptual_n: int = 15
    min_pilot_conceptual_coverage: int = 8
    coverage_derivation: str = (
        "unpiloted remainder < floor: 15 - c < 8 => c >= 8 (the vacuity "
        "boundary — 0 observed + 8 unpiloted >= floor)"
    )

    # The two per-pair quantities' epistemic-kind labels (see module docstring).
    projection_kind: str = "upper-bound-feasibility"
    estimate_kind: str = "point-estimate"

    # Preflight enum precedence (cheapest/most-fundamental failure first) and
    # the per-pair verdict predicate order — both frozen, non-overlapping.
    preflight_precedence: tuple[str, ...] = (
        "unservable",
        "coherence-fail",
        "tool-call-malformed",
        "think-control-noop",
        "preflight-pass",
    )
    pair_verdict_order: tuple[str, ...] = (
        "pair-not-evaluated-model-excluded",
        "insufficient-pilot-evidence",
        "pair-under-powered",
        "pair-models-too-close",
        "pair-feasible",
    )

    # Arm parity: all pilot arms run the shipped default (thinking on).
    explorer_think: bool | None = None

    # OQ3 staging fallback — pre-declared, never chosen after early results.
    staging_order: str = "preflight-all-3-then-pilot-widest-gap-pair-first"


PREREGISTERED_POOL_CONFIG_0040 = PoolConfig()


def pool_config_hash(cfg: PoolConfig) -> str:
    payload = "|".join(f"{k}={v}" for k, v in sorted(dataclasses.asdict(cfg).items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


POOL_CONFIG_HASH_0040 = pool_config_hash(PREREGISTERED_POOL_CONFIG_0040)


# ---- preflight enum + precedence + adjudicator (AC2) --------------------------


class PreflightOutcome(enum.Enum):
    """The committed per-model preflight answer space — total, typed BEFORE the
    probe fires (the 0023/0037 discipline). DELIBERATELY ASYMMETRIC: the first
    three failures EXCLUDE (no capability number — the 16B-gibberish lesson);
    THINK_CONTROL_NOOP is RECORDED-NON-EXCLUDING (bakes off default-on, barred
    only from a future thinking-arm). Do not "fix" this into symmetry."""

    PREFLIGHT_PASS = "preflight-pass"
    UNSERVABLE = "unservable"
    COHERENCE_FAIL = "coherence-fail"
    TOOL_CALL_MALFORMED = "tool-call-malformed"
    THINK_CONTROL_NOOP = "think-control-noop"


# Committed tie-break: checks evaluate in this order and the FIRST failure is
# the outcome (cheapest / most-fundamental first) — a gibberish model that also
# emits malformed tool_calls types COHERENCE_FAIL, not implementer choice.
PREFLIGHT_PRECEDENCE: tuple[PreflightOutcome, ...] = (
    PreflightOutcome.UNSERVABLE,
    PreflightOutcome.COHERENCE_FAIL,
    PreflightOutcome.TOOL_CALL_MALFORMED,
    PreflightOutcome.THINK_CONTROL_NOOP,
    PreflightOutcome.PREFLIGHT_PASS,
)

_EXCLUDING = frozenset(
    {
        PreflightOutcome.UNSERVABLE,
        PreflightOutcome.COHERENCE_FAIL,
        PreflightOutcome.TOOL_CALL_MALFORMED,
    }
)


@dataclasses.dataclass(frozen=True)
class PreflightObservations:
    """The raw per-model probe facts the adjudicator types.

    ``think_control`` is "effective" | "noop" | "indeterminate" — an
    indeterminate probe (effect unadjudicable under the tiny-cap discriminator)
    maps to THINK_CONTROL_NOOP, conservative and inside the answer space."""

    served: bool
    coherent: bool
    tool_calls_clean: bool
    think_control: str


def adjudicate_preflight(obs: PreflightObservations) -> PreflightOutcome:
    """Exactly one value of the committed enum, in the frozen precedence order."""
    if not obs.served:
        return PreflightOutcome.UNSERVABLE
    if not obs.coherent:
        return PreflightOutcome.COHERENCE_FAIL
    if not obs.tool_calls_clean:
        return PreflightOutcome.TOOL_CALL_MALFORMED
    if obs.think_control in ("noop", "indeterminate"):
        return PreflightOutcome.THINK_CONTROL_NOOP
    return PreflightOutcome.PREFLIGHT_PASS


def is_excluding(outcome: PreflightOutcome) -> bool:
    """The load-bearing asymmetry: NOOP still bakes off; the rest exclude."""
    return outcome in _EXCLUDING


# ---- the TWO per-pair quantities from per-case pairs (AC5) --------------------


@dataclasses.dataclass(frozen=True)
class PairCase:
    """One conceptual case's cross-model bucket pair — the retained per-case
    row (case_id, a_bucket, b_bucket) both quantities are computed from.
    Marginal locate-counts cannot recover union-located or discordance."""

    case_id: str
    bucket_a: LocateBucket
    bucket_b: LocateBucket


def build_pair_cases(
    entries: Mapping[str, Mapping[str, Any]],
    model_a: str,
    model_b: str,
    reachability: Mapping[str, str],
) -> list[PairCase]:
    """Join a per model+case pilot ledger into conceptual-stratum pairs.

    A pair exists only where BOTH models carry a CLEAN bucket (a typed degrade
    is not a capability observation — the 0036 posture; the case drops from
    this pair rather than faking an EMPTY)."""
    pairs: list[PairCase] = []
    for case_id, tag in reachability.items():
        if tag != "conceptual":
            continue
        cell_a = entries.get(f"{case_id}::{model_a}")
        cell_b = entries.get(f"{case_id}::{model_b}")
        if not cell_a or not cell_b:
            continue
        if cell_a.get("degrade") or cell_b.get("degrade"):
            continue
        if not cell_a.get("bucket") or not cell_b.get("bucket"):
            continue
        pairs.append(
            PairCase(
                case_id=case_id,
                bucket_a=LocateBucket(cell_a["bucket"]),
                bucket_b=LocateBucket(cell_b["bucket"]),
            )
        )
    return pairs


def _extrapolate(count: int, piloted_n: int, full_n: int) -> int:
    """round(rate * full_n) — the 0039 projection arithmetic, reused."""
    if piloted_n <= 0:
        return 0
    return round((count / piloted_n) * full_n)


def union_located_ceiling(
    pair_cases: Sequence[PairCase], *, full_conceptual_n: int
) -> int:
    """The per-pair CEILING (projection_kind="upper-bound-feasibility"): the
    extrapolated per-case UNION-located count — every case either model
    locates, assumed discordant. A TRUE bound: signal discordance requires
    >= 1 located arm by ``is_signal_discordant``'s own definition. Gates
    PAIR_UNDER_POWERED; the stop-quality claim rests ONLY on this bound."""
    union = sum(
        1
        for p in pair_cases
        if located_via_oracle(p.bucket_a) or located_via_oracle(p.bucket_b)
    )
    return _extrapolate(union, len(pair_cases), full_conceptual_n)


def observed_discordance(
    pair_cases: Sequence[PairCase], *, full_conceptual_n: int
) -> int:
    """The OBSERVED signal-discordance (estimate_kind="point-estimate"),
    extrapolated. Drives the TOO_CLOSE vs FEASIBLE split — a REPORTABLE
    closeness finding, never the unimpeachable stop."""
    discordant = sum(
        1
        for p in pair_cases
        if is_signal_discordant(
            PilotPair(case_id=p.case_id, bucket_a=p.bucket_a, bucket_b=p.bucket_b)
        )
    )
    return _extrapolate(discordant, len(pair_cases), full_conceptual_n)


# ---- derived coverage minimum (AC7) -------------------------------------------


def pilot_conceptual_coverage(pair_cases: Sequence[PairCase]) -> int:
    """The pair's conceptual coverage c: retained per-case pairs (both models
    clean-bucketed) on the conceptual stratum."""
    return len(pair_cases)


def coverage_below_minimum(
    pair_cases: Sequence[PairCase], cfg: PoolConfig = PREREGISTERED_POOL_CONFIG_0040
) -> bool:
    """The frozen, DERIVED coverage predicate (15 - c < 8 => c >= 8): below the
    minimum, the unpiloted remainder alone could clear the floor and any
    verdict would rest on majority-unobserved mass — INSUFFICIENT_PILOT_
    EVIDENCE, never a read-time judgment."""
    return pilot_conceptual_coverage(pair_cases) < cfg.min_pilot_conceptual_coverage


# ---- total per-pair verdict + frozen predicate order + fork (AC6) --------------


class PairVerdict(enum.Enum):
    """The total per-pair answer space, in the FROZEN predicate order (member
    order = evaluation order = ``cfg.pair_verdict_order``). Non-overlapping:
    an input satisfying multiple predicates types the EARLIEST. A pair whose
    member failed preflight gets a TYPED disposition — absence is never a
    disposition (the silent-carry the spec forbids)."""

    PAIR_NOT_EVALUATED_MODEL_EXCLUDED = "pair-not-evaluated-model-excluded"
    INSUFFICIENT_PILOT_EVIDENCE = "insufficient-pilot-evidence"
    PAIR_UNDER_POWERED = "pair-under-powered"
    PAIR_MODELS_TOO_CLOSE = "pair-models-too-close"
    PAIR_FEASIBLE = "pair-feasible"


PAIR_VERDICT_ORDER: tuple[PairVerdict, ...] = tuple(PairVerdict)


@dataclasses.dataclass(frozen=True)
class PairVerdictResult:
    """The verdict plus every input a reader needs to audit it, with both
    quantities carrying their epistemic-kind labels."""

    verdict: PairVerdict
    coverage: int
    ceiling: int
    observed: int
    floor: int
    projection_kind: str
    estimate_kind: str
    preflight_a: PreflightOutcome
    preflight_b: PreflightOutcome


def decide_pair_verdict(
    cfg: PoolConfig,
    pair_cases: Sequence[PairCase],
    *,
    preflight_a: PreflightOutcome,
    preflight_b: PreflightOutcome,
) -> PairVerdictResult:
    """Total pure per-pair verdict in the frozen predicate order:
    MODEL_EXCLUDED → INSUFFICIENT → UNDER_POWERED → TOO_CLOSE → FEASIBLE.

    UNDER_POWERED rests ONLY on the ceiling (the true bound — unimpeachable
    stop quality); the TOO_CLOSE/FEASIBLE split rests on the labeled point
    estimate (a reportable closeness finding). FEASIBLE means "possible to
    clear the floor" — proven only by the bake-off's own run."""
    floor = cfg.conceptual_min_discordant
    coverage = pilot_conceptual_coverage(pair_cases)
    ceiling = union_located_ceiling(pair_cases, full_conceptual_n=cfg.full_conceptual_n)
    observed = observed_discordance(pair_cases, full_conceptual_n=cfg.full_conceptual_n)

    if is_excluding(preflight_a) or is_excluding(preflight_b):
        verdict = PairVerdict.PAIR_NOT_EVALUATED_MODEL_EXCLUDED
    elif coverage_below_minimum(pair_cases, cfg):
        verdict = PairVerdict.INSUFFICIENT_PILOT_EVIDENCE
    elif ceiling < floor:
        verdict = PairVerdict.PAIR_UNDER_POWERED
    elif observed < floor:
        verdict = PairVerdict.PAIR_MODELS_TOO_CLOSE
    else:
        verdict = PairVerdict.PAIR_FEASIBLE

    return PairVerdictResult(
        verdict=verdict,
        coverage=coverage,
        ceiling=ceiling,
        observed=observed,
        floor=floor,
        projection_kind=cfg.projection_kind,
        estimate_kind=cfg.estimate_kind,
        preflight_a=preflight_a,
        preflight_b=preflight_b,
    )


def pair_name(model_a: str, model_b: str) -> str:
    return f"{model_a} vs {model_b}"


def decide_pool_fork(
    cfg: PoolConfig,
    entries: Mapping[str, Mapping[str, Any]],
    reachability: Mapping[str, str],
    *,
    preflight_by_model: Mapping[str, PreflightOutcome],
) -> dict[str, PairVerdictResult]:
    """The overall fork: a typed verdict for EACH of the three named pairs.

    The ANCHOR model (``model_tags[0]``, the re-confirmed ``qwen3:14b``)
    failing preflight voids ALL pairs — the 0039-proven model regressing under
    this harness build is a harness-integrity signal, not a membership fact;
    evaluating the remaining pair against a suspect harness would launder a
    defect into a capability number."""
    anchor = cfg.model_tags[0]
    anchor_excluded = is_excluding(preflight_by_model[anchor])
    fork: dict[str, PairVerdictResult] = {}
    for model_a, model_b in cfg.pairs:
        pf_a = preflight_by_model[model_a]
        pf_b = preflight_by_model[model_b]
        pairs = build_pair_cases(entries, model_a, model_b, reachability)
        result = decide_pair_verdict(cfg, pairs, preflight_a=pf_a, preflight_b=pf_b)
        if anchor_excluded:
            # The pair keeps its own preflight facts; only the verdict is
            # voided by the harness-integrity signal.
            result = dataclasses.replace(
                result, verdict=PairVerdict.PAIR_NOT_EVALUATED_MODEL_EXCLUDED
            )
        fork[pair_name(model_a, model_b)] = result
    return fork
