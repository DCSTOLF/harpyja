"""Spec 0047 — enlargement: the freeze-before-run machinery for the audited
convert that raises the blind-clean pool past 19.

Everything here is a pure function / frozen dataclass over committed constants; there
is NO I/O, no live model call, and no data acquisition (those are the operator
`[integration]` steps). Four frozen surfaces, all committed BEFORE any raw case is
acquired (the 0036/0040 re-registration rule):

- ``EnlargementConfig`` — the target-N arithmetic. The RAW convert count is PINNED
  upfront (assumption-driven); the blind-clean OUTPUT count FLOATS with measured
  attrition and is reported, never frozen (Decision A). The floor is COPIED from
  ``benchmark_fit.PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS`` and the conceptual
  reportability floor from ``terse_dataset._CONCEPTUAL_FLOOR_FULL`` — never re-derived.
- ``SamplingFrame`` — the candidate manifest: the HF source-snapshot identity + the
  sha256 chain to the committed raw fixture, with the ≤3/repo discipline (0036) and the
  pinned-50 exclusion (no train-on-test re-draw) enforced by ``select_candidates``.
- ``PowerVerdict`` — the five-member typed vocabulary + frozen predicate order,
  committed here BEFORE the enlarged stratum counts exist (Decision B). The AC5/AC6
  re-check uses the THEORETICAL ceiling (max discordance = conceptual N, tag-count-only —
  no located sets); empirical ``DISCORDANCE_STILL_INSUFFICIENT`` is deferred to the
  bake-off spec.
- ``expected_variance_at_n`` / ``single_draw_suffices`` — OQ2→AC: whether the enlarged
  N tames variance enough for a single-draw policy baseline (0046's named follow-up).
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from harpyja.eval.benchmark_fit import PREREGISTERED_CONFIG
from harpyja.eval.pool_precheck import PREREGISTERED_POOL_CONFIG_0040
from harpyja.eval.swebench_eval import is_new_file_only, parse_patch
from harpyja.eval.terse_dataset import _CONCEPTUAL_FLOOR_FULL


class EnlargementError(ValueError):
    """Malformed frozen input (sampling frame / power artifact) — loud, never defaulted."""


# ---- AC4: frozen+hashed enlargement config (raw pinned, output floats) --------


@dataclasses.dataclass(frozen=True)
class EnlargementConfig:
    """Pre-registered 0047 target-N arithmetic (frozen; hashed pre-run).

    ``raw_convert_target`` is the ONE quantity AC4 freezes — the assumption-driven
    upfront count. ``target_conceptual_output_n`` is the design goal the OUTPUT floats
    toward; a measured shortfall types ``INSUFFICIENT_ENLARGED_COVERAGE`` (reported),
    never a silent short pool.
    """

    # The frozen RAW convert count. Derived (see raw_target_derivation), deliberately
    # non-round; credits the existing conceptual stratum (only the SHORTFALL to the
    # target needs new raw). The blind-clean OUTPUT floats with measured attrition.
    raw_convert_target: int = 96

    # The design OUTPUT goal (floats with attrition, reported not frozen): the
    # conceptual stratum sized so expected discordant >= floor WITH headroom for
    # degrades / blind-attrition / the nested-sets risk (0040 had ZERO slack).
    target_conceptual_output_n: int = 40

    # The existing conceptual stratum reused verbatim (0036: 15/19 blind-clean).
    existing_conceptual_n: int = 15

    # Floors COPIED verbatim (never re-derived): the discordance floor from 0023's
    # exact-McNemar reachability, the conceptual reportability floor from 0036.
    conceptual_min_discordant: int = PREREGISTERED_CONFIG.MIN_DISCORDANT_PAIRS
    conceptual_reportability_floor: int = _CONCEPTUAL_FLOOR_FULL

    # The assumptions the RAW count is derived from — the SOLE prior is 0036
    # (19 blind-clean / 50 raw; 15 conceptual / 19 clean).
    assumed_blind_clean_yield: float = 0.38  # 19/50
    assumed_conceptual_fraction: float = 0.79  # 15/19
    realized_discordance_rate: float = 0.35  # 0040 ceilings 6/8/3 on 15
    yield_uncertainty: float = 0.15  # headroom for the yield NOT holding on a new slice

    # The per-repo discipline — RELAXED 0036's ≤3/repo → ≤8/repo (OQ3 resolved by data:
    # ≤3/repo hard-ceilings new raw at 12×3=36 on Verified's 12 repos, below the target).
    max_per_repo: int = 8
    n_benchmark_repos: int = 12

    raw_target_derivation: str = (
        "ceil((target_conceptual_output_n - existing_conceptual_n) / "
        "(assumed_blind_clean_yield × assumed_conceptual_fraction) × (1 + "
        "yield_uncertainty)) = ceil(25/0.30 × 1.15) = 96 — only the SHORTFALL to 40 "
        "needs new raw (the existing 15 are reused verbatim); the OUTPUT floats"
    )
    conceptual_target_derivation: str = (
        "ceil(conceptual_min_discordant / realized_discordance_rate) = ceil(8/0.35) = 23 "
        "floor, headroomed to 40 for degrades + blind-attrition + nested-sets risk "
        "(0040 had ZERO coverage slack: 8 conceptual vs minimum 8)"
    )
    max_per_repo_derivation: str = (
        "RELAXED from 0036's ≤3/repo to ≤8/repo (OQ3, forced by data): on Verified's "
        "12 repos, ≤3/repo caps new raw at 12×3=36 (< the 96 target); ≤8/repo gives "
        "12×8=96 = exactly the derived raw need — the MINIMAL relaxation that makes the "
        "40-conceptual target attainable without leaving the benchmark. Deepens "
        "per-repo coverage (accepted overfit risk) rather than adding repos."
    )
    floor_derivation: str = (
        "fixed-not-re-derivable: copied from benchmark_fit.PREREGISTERED_CONFIG."
        "MIN_DISCORDANT_PAIRS (the 0023 exact-McNemar floor 0039/0040 pinned)"
    )
    coverage_min_derivation: str = (
        "the enlarged conceptual coverage must reach the discordance floor, else a "
        "verdict rests on unobserved mass — the derived minimum reuses the 0040 "
        "coverage discipline (coverage >= conceptual_min_discordant)"
    )


PREREGISTERED_ENLARGEMENT_CONFIG_0047 = EnlargementConfig()


def enlargement_config_hash(cfg: EnlargementConfig) -> str:
    payload = "|".join(f"{k}={v}" for k, v in sorted(dataclasses.asdict(cfg).items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


ENLARGEMENT_CONFIG_HASH_0047 = enlargement_config_hash(PREREGISTERED_ENLARGEMENT_CONFIG_0047)


# ---- AC4: pinned sampling frame + deterministic candidate selection -----------

SAMPLING_FRAME_SCHEMA_VERSION = "0047/frame/1"

_FRAME_REQUIRED = (
    "schema_version",
    "hf_dataset_id",
    "hf_revision",
    "hf_split",
    "prior_raw_fixture_sha256",
)


@dataclasses.dataclass(frozen=True)
class SamplingFrame:
    """The candidate manifest: the source-snapshot identity + the drift-guard root
    (sha256 chain to the committed raw fixture) + the already-pinned ids to exclude."""

    schema_version: str
    hf_dataset_id: str
    hf_revision: str
    hf_split: str
    prior_raw_fixture_sha256: str
    already_pinned_ids: tuple[str, ...] = ()


def validate_sampling_frame(raw: dict[str, Any]) -> SamplingFrame:
    """Loud: a bad/absent schema_version or a missing source-snapshot field raises."""
    for key in _FRAME_REQUIRED:
        if not raw.get(key):
            raise EnlargementError(f"sampling frame missing required field {key!r}")
    if raw["schema_version"] != SAMPLING_FRAME_SCHEMA_VERSION:
        raise EnlargementError(
            f"sampling frame schema_version {raw['schema_version']!r} != "
            f"{SAMPLING_FRAME_SCHEMA_VERSION!r}"
        )
    return SamplingFrame(
        schema_version=raw["schema_version"],
        hf_dataset_id=raw["hf_dataset_id"],
        hf_revision=raw["hf_revision"],
        hf_split=raw["hf_split"],
        prior_raw_fixture_sha256=raw["prior_raw_fixture_sha256"],
        already_pinned_ids=tuple(raw.get("already_pinned_ids", ())),
    )


def _is_malformed(row: dict) -> bool:
    try:
        targets = parse_patch(row.get("patch", ""))
    except Exception:  # noqa: BLE001 — a malformed patch excludes the case, never aborts
        return True
    return not targets


def select_candidates(
    snapshot_rows: Sequence[dict],
    cfg: EnlargementConfig,
    *,
    already_pinned_ids: Sequence[str],
) -> tuple[list[dict], list[tuple[str, str]]]:
    """Pure, deterministic candidate selection over a source-snapshot slice.

    Excludes (each with a RECORDED reason, never a silent drop): the already-pinned
    ids (no train-on-test re-draw), new-file-only, malformed patches, and per-repo
    overflow beyond ``cfg.max_per_repo``. Ordered by ``instance_id`` (stable across
    input order); capped at ``cfg.raw_convert_target``.
    """
    pinned = set(already_pinned_ids)
    rows = sorted(snapshot_rows, key=lambda r: r["instance_id"])
    exclusions: list[tuple[str, str]] = []
    per_repo: dict[str, int] = {}
    selected: list[dict] = []
    for row in rows:
        iid = row["instance_id"]
        if iid in pinned:
            exclusions.append((iid, "already-pinned"))
            continue
        if _is_malformed(row):
            exclusions.append((iid, "malformed"))
            continue
        if is_new_file_only(parse_patch(row["patch"])):
            exclusions.append((iid, "new-file-only"))
            continue
        repo = row["repo"]
        if per_repo.get(repo, 0) >= cfg.max_per_repo:
            exclusions.append((iid, "per-repo-cap"))
            continue
        per_repo[repo] = per_repo.get(repo, 0) + 1
        selected.append(row)
    return selected[: cfg.raw_convert_target], exclusions


# ---- AC5: frozen power vocabulary + theoretical-ceiling re-check ---------------


class PowerVerdict(enum.Enum):
    """The committed answer space for "is a downstream question NOW powered?" — typed
    BEFORE the enlarged counts exist (Decision B). Total, one home, five members."""

    POWERED = "powered"
    STILL_UNDER_POWERED = "still-under-powered"
    DISCORDANCE_STILL_INSUFFICIENT = "discordance-still-insufficient"
    INSUFFICIENT_ENLARGED_COVERAGE = "insufficient-enlarged-coverage"
    VARIANCE_REQUIRES_MULTI_DRAW = "variance-requires-multi-draw"


# The frozen, non-overlapping evaluation order: an input satisfying several predicates
# types the EARLIEST. VARIANCE is layered on top by decide_ab_power only.
POWER_VERDICT_PREDICATE_ORDER: tuple[PowerVerdict, ...] = (
    PowerVerdict.STILL_UNDER_POWERED,
    PowerVerdict.INSUFFICIENT_ENLARGED_COVERAGE,
    PowerVerdict.DISCORDANCE_STILL_INSUFFICIENT,
    PowerVerdict.POWERED,
)


def theoretical_discordance_ceiling(conceptual_n: int) -> int:
    """The AC6 re-check quantity: max POSSIBLE discordance = the conceptual stratum
    size, computable from tag counts ALONE (no located sets, no bake-off compute)."""
    return conceptual_n


def decide_bakeoff_power(
    cfg: EnlargementConfig,
    conceptual_n: int,
    coverage: int,
    *,
    observed_discordance: int | None = None,
) -> PowerVerdict:
    """Total pure per-question verdict in the frozen predicate order:
    STILL_UNDER_POWERED → INSUFFICIENT_ENLARGED_COVERAGE → DISCORDANCE_STILL_INSUFFICIENT
    → POWERED.

    STILL_UNDER_POWERED rests on the THEORETICAL ceiling (< floor even enlarged);
    INSUFFICIENT_ENLARGED_COVERAGE on measured attrition eating the headroom;
    DISCORDANCE_STILL_INSUFFICIENT is the nested-sets finding — typed here so the
    answer space is pre-frozen, but RESOLVABLE only empirically (deferred to the
    bake-off spec; ``observed_discordance`` is None in this spec's tag-count re-check).
    """
    floor = cfg.conceptual_min_discordant
    coverage_min = cfg.conceptual_min_discordant
    if theoretical_discordance_ceiling(conceptual_n) < floor:
        return PowerVerdict.STILL_UNDER_POWERED
    if coverage < coverage_min:
        return PowerVerdict.INSUFFICIENT_ENLARGED_COVERAGE
    if observed_discordance is not None and observed_discordance < floor:
        return PowerVerdict.DISCORDANCE_STILL_INSUFFICIENT
    return PowerVerdict.POWERED


def decide_ab_power(
    cfg: EnlargementConfig,
    conceptual_n: int,
    coverage: int,
    *,
    effect_band: float,
    observed_discordance: int | None = None,
) -> PowerVerdict:
    """The 0039 A/B feasibility twin: the bake-off ceiling check, then the variance
    gate (OQ2→AC). A POWERED base whose expected variance at N still exceeds the
    effect band types VARIANCE_REQUIRES_MULTI_DRAW (single-draw baseline illegitimate)."""
    base = decide_bakeoff_power(
        cfg, conceptual_n, coverage, observed_discordance=observed_discordance
    )
    if base is not PowerVerdict.POWERED:
        return base
    if not single_draw_suffices(conceptual_n, effect_band):
        return PowerVerdict.VARIANCE_REQUIRES_MULTI_DRAW
    return PowerVerdict.POWERED


# ---- OQ2→AC: expected variance at N + single-draw sufficiency ------------------


def expected_variance_at_n(n: int, p: float = 0.5) -> float:
    """Sampling variance of a proportion estimate at N: ``p(1-p)/n`` — monotone
    decreasing in N (the enlarged pool tames the run-to-run variance 0046 named).
    ``p=0.5`` is the max-variance (worst-case) reference proportion."""
    if n <= 0:
        return math.inf
    return p * (1 - p) / n


def single_draw_suffices(n: int, effect_band: float, p: float = 0.5) -> bool:
    """Is a single-draw baseline legitimate at N? True iff the sampling std at N is
    within the effect band being measured; else median-of-2–3 draws are required
    (0046's follow-up) and the verdict is VARIANCE_REQUIRES_MULTI_DRAW."""
    return math.sqrt(expected_variance_at_n(n, p)) <= effect_band


# ---- AC5: the committed power-recheck artifact (compute / validate / load) -----

POWER_RECHECK_SCHEMA_VERSION = "0047/power/1"

# The three named bake-off pairs whose feasibility this spec re-checks (from
# PREREGISTERED_POOL_CONFIG_0040) are used by NAME only — the empirical bake-off is
# out of scope; the ceiling re-checked here is tag-count-only.


@dataclasses.dataclass(frozen=True)
class PowerRecheckResult:
    """The machine-readable AC5 answer: per-question / per-pair power verdict computed
    from the enlarged stratum + attrition counts, pinned to the frozen config hash.

    ``questions`` maps each downstream question ("bakeoff:<pair>", "ab-feasibility",
    "policy-baseline-variance") to a ``PowerVerdict.value``. The bake-off verdicts are
    the THEORETICAL-ceiling re-check (tag-count-only, no located sets); empirical
    discordance is deferred to the bake-off spec."""

    schema_version: str
    config_hash: str
    lexical_n: int
    conceptual_n: int
    coverage: int
    leaky_count: int
    blind_ineligible_count: int
    dropped_count: int
    questions: dict[str, str]


def compute_power_recheck(
    cfg: EnlargementConfig,
    *,
    lexical_n: int,
    conceptual_n: int,
    coverage: int,
    leaky_count: int,
    blind_ineligible_count: int,
    dropped_count: int,
    effect_band: float,
) -> PowerRecheckResult:
    """Compute the per-question verdicts from the enlarged tag/attrition counts.

    Each named bake-off pair gets ``decide_bakeoff_power`` at the enlarged conceptual N
    (the theoretical ceiling is identical across pairs — per-pair empirical discordance
    is the deferred bake-off finding); the A/B feasibility and the policy-baseline
    variance questions get ``decide_ab_power`` (which layers the single-draw gate)."""
    questions: dict[str, str] = {}
    for model_a, model_b in PREREGISTERED_POOL_CONFIG_0040.pairs:
        questions[f"bakeoff:{model_a}-vs-{model_b}"] = decide_bakeoff_power(
            cfg, conceptual_n, coverage
        ).value
    questions["ab-feasibility"] = decide_bakeoff_power(cfg, conceptual_n, coverage).value
    questions["policy-baseline-variance"] = decide_ab_power(
        cfg, conceptual_n=conceptual_n, coverage=coverage, effect_band=effect_band
    ).value
    return PowerRecheckResult(
        schema_version=POWER_RECHECK_SCHEMA_VERSION,
        config_hash=ENLARGEMENT_CONFIG_HASH_0047,
        lexical_n=lexical_n,
        conceptual_n=conceptual_n,
        coverage=coverage,
        leaky_count=leaky_count,
        blind_ineligible_count=blind_ineligible_count,
        dropped_count=dropped_count,
        questions=questions,
    )


def power_recheck_payload(result: PowerRecheckResult) -> dict[str, Any]:
    """Serialize to the committed JSON shape (round-trips through validate)."""
    return {
        "schema_version": result.schema_version,
        "config_hash": result.config_hash,
        "lexical_n": result.lexical_n,
        "conceptual_n": result.conceptual_n,
        "coverage": result.coverage,
        "leaky_count": result.leaky_count,
        "blind_ineligible_count": result.blind_ineligible_count,
        "dropped_count": result.dropped_count,
        "questions": dict(result.questions),
    }


_RECHECK_INT_FIELDS = (
    "lexical_n",
    "conceptual_n",
    "coverage",
    "leaky_count",
    "blind_ineligible_count",
    "dropped_count",
)


def validate_power_recheck(obj: dict[str, Any]) -> PowerRecheckResult:
    """Loud: an off-enum verdict, unknown schema, or non-int count is rejected."""
    if not isinstance(obj, dict):
        raise EnlargementError("power recheck must be an object")
    if obj.get("schema_version") != POWER_RECHECK_SCHEMA_VERSION:
        raise EnlargementError(
            f"power recheck schema_version {obj.get('schema_version')!r} != "
            f"{POWER_RECHECK_SCHEMA_VERSION!r}"
        )
    if not obj.get("config_hash"):
        raise EnlargementError("power recheck missing config_hash")
    for key in _RECHECK_INT_FIELDS:
        if not isinstance(obj.get(key), int) or isinstance(obj.get(key), bool):
            raise EnlargementError(f"power recheck field {key!r} must be an int")
    questions = obj.get("questions")
    if not isinstance(questions, dict) or not questions:
        raise EnlargementError("power recheck 'questions' must be a non-empty object")
    allowed = {v.value for v in PowerVerdict}
    for q, verdict in questions.items():
        if verdict not in allowed:
            raise EnlargementError(
                f"power recheck question {q!r} verdict {verdict!r} not in {sorted(allowed)}"
            )
    return PowerRecheckResult(
        schema_version=obj["schema_version"],
        config_hash=obj["config_hash"],
        lexical_n=obj["lexical_n"],
        conceptual_n=obj["conceptual_n"],
        coverage=obj["coverage"],
        leaky_count=obj["leaky_count"],
        blind_ineligible_count=obj["blind_ineligible_count"],
        dropped_count=obj["dropped_count"],
        questions=dict(questions),
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def committed_power_recheck_path(root: Path | None = None) -> Path:
    """Archive-first (the 79f7bf2 convention), live spec-dir fallback."""
    base = root if root is not None else _repo_root()
    archived = base / "specs" / ".archive" / "0047-enlargement" / "power_recheck.json"
    live = base / "specs" / "0047-enlargement" / "power_recheck.json"
    return archived if archived.is_file() else live


def load_committed_power_recheck(root: Path | None = None) -> PowerRecheckResult:
    path = committed_power_recheck_path(root)
    if not path.is_file():
        raise EnlargementError(f"committed power recheck not found: {path}")
    import json

    return validate_power_recheck(json.loads(path.read_text(encoding="utf-8")))
