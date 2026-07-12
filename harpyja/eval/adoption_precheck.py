"""Spec 0042 — adoption: frozen pre-registered measurement config + the total
pure typed-outcome decider for the symbols-adoption re-measurement.

The 0040 pilot measured 0/28 clean-cell ``symbols`` invocations against an
UNUSABLE tool (four stacked defects — stale prompt, when-less description,
result-shape penalty, positioning gap). This module freezes every
outcome-shaping choice of the re-measurement BEFORE any live call fires (the
0023/0026/0039/0040 discipline):

- **Adoption boundary**: STILL_NOT_ADOPTED iff clean-cell ``symbols``
  invocations == 0 across the cells actually run — the baseline is exactly
  0/28, so ANY nonzero clean-cell use disproves "structurally unreachable".
  The adoption RATE is reported alongside, never re-thresholded post-hoc.
- **Per-model denominators**: a 14b-only run is typed against 14b's OWN
  clean-cell universe, never the pooled 0/28 baseline it never had.
- **Conversion predicate**: computed from RETAINED per-case pairs
  (0040-ledger bucket vs re-run bucket, per ``case::model``) — BIDIRECTIONAL:
  rfws→exact conversions AND exact→rfws regressions both retained, the net
  surfaced. NEVER marginal counts (the signature makes marginals structurally
  impossible: it takes per-case records only).
- **Power floor**: ``min_rfws_denominator = 3``. Below it a no-conversion
  result types ADOPTED_UNDER_POWERED, never ADOPTED_NO_CONVERSION (a 14b-only
  run has RFWS denominator 2 → under-powered by construction; all-three
  coverage has 4).
- **Pinned model coverage**: the closure run MUST cover ``required_models``;
  ``optional_models`` are recorded-if-run — "wall-clock allows" can never
  shrink the measurement below required.

COMMITTED PRECEDENCE (evaluation order — an input satisfying multiple
predicates types the EARLIEST):

1. STILL_NOT_ADOPTED — zero clean-cell adoption; nothing else is evaluable.
2. ADOPTED_AND_CONVERTS — >= 1 rfws→exact flip in a case where ``symbols``
   was invoked in the re-run. Fires EVEN UNDER the power floor: it is a
   SIGNAL, not an inferential claim (AC7), and the decision record carries
   the ``under_powered`` caveat so the label strength stays honest.
3. ADOPTED_UNDER_POWERED — no conversion signal, RFWS denominator below the
   frozen floor: no refutation claim available.
4. ADOPTED_NO_CONVERSION — no flip at or above the floor: the honest null —
   value refuted by a FAIR test.
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

# One-oracle reuse (identity-asserted by test): the bucket taxonomy is THE
# committed LocateBucket — never re-typed literals. The baseline ledger path
# helper and the 0040 freeze are consumed by import, not mirrored.
from harpyja.eval.locate_accuracy import LocateBucket
from harpyja.eval.pool_fork import _committed_pilot_ledger_path
from harpyja.eval.pool_precheck import (
    POOL_CONFIG_HASH_0040,
    PREREGISTERED_POOL_CONFIG_0040,
)


class AdoptionOutcome(enum.Enum):
    """The total typed answer space, in the FROZEN precedence order (member
    order = evaluation order = ``cfg.outcome_precedence``)."""

    STILL_NOT_ADOPTED = "still-not-adopted"
    ADOPTED_AND_CONVERTS = "adopted-and-converts"
    ADOPTED_UNDER_POWERED = "adopted-under-powered"
    ADOPTED_NO_CONVERSION = "adopted-no-conversion"


@dataclasses.dataclass(frozen=True)
class AdoptionConfig:
    """Pre-registered 0042 adoption re-measurement config (frozen; hashed and
    committed before any live call)."""

    # The baseline: THE committed 0040 pilot ledger — pinned by spec id,
    # schema version, and the 0040 frozen-config hash the ledger cites.
    baseline_spec: str = "0040"
    baseline_ledger_schema_version: str = "0040/pilot/1"
    baseline_config_hash: str = POOL_CONFIG_HASH_0040

    # The pilot case set is CONSUMED from the 0040 freeze, never re-selected.
    pilot_case_ids: tuple[str, ...] = PREREGISTERED_POOL_CONFIG_0040.pilot_case_ids

    # Model coverage pinned PRE-RUN: the closure run MUST cover required;
    # optional models are recorded-if-run. "Wall-clock allows" can never
    # shrink the measurement below required — that is the point of pinning.
    required_models: tuple[str, ...] = ("qwen3:14b",)
    optional_models: tuple[str, ...] = ("qwen3:8b", "qwen3.5:4b")

    # Bucket constants by IDENTITY from the committed LocateBucket taxonomy
    # (one-oracle rule): "exact" IS the "correct" bucket.
    rfws_bucket: str = LocateBucket.RIGHT_FILE_WRONG_SPAN.value
    exact_bucket: str = LocateBucket.CORRECT.value

    # The adoption boundary and denominators (see module docstring).
    adoption_boundary: str = (
        "still-not-adopted-iff-zero-clean-cell-symbols-invocations"
    )
    adoption_denominator: str = "per-model-clean-cells-of-models-actually-run"

    # The conversion predicate: bidirectional, per-case paired buckets only.
    conversion_predicate: str = (
        "bidirectional-per-case-paired-buckets-never-marginals"
    )

    # The power floor: below it, no-conversion types under-powered.
    min_rfws_denominator: int = 3

    # The committed precedence (evaluation order) — matches AdoptionOutcome
    # member order, asserted by test.
    outcome_precedence: tuple[str, ...] = (
        "still-not-adopted",
        "adopted-and-converts",
        "adopted-under-powered",
        "adopted-no-conversion",
    )


PREREGISTERED_ADOPTION_CONFIG_0042 = AdoptionConfig()


def adoption_config_hash(cfg: AdoptionConfig) -> str:
    """dataclasses.asdict → canonical json → sha256 (the 0039/0040 shape)."""
    payload = json.dumps(
        dataclasses.asdict(cfg), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


ADOPTION_CONFIG_HASH_0042 = adoption_config_hash(PREREGISTERED_ADOPTION_CONFIG_0042)


# ---- per-case records + the total pure decider (AC5) ---------------------------


@dataclasses.dataclass(frozen=True)
class AdoptionCell:
    """One ``case::model`` re-measurement record — the retained per-case row
    the decider consumes. A ``None`` bucket means that arm was degraded (a
    typed degrade is not a capability observation — the 0036 posture): a
    ``None`` ``rerun_bucket`` is a non-clean cell (excluded from the adoption
    denominator); a pair is retained for the conversion predicate only when
    BOTH buckets are present."""

    case_id: str
    model: str
    baseline_bucket: LocateBucket | None
    rerun_bucket: LocateBucket | None
    symbols_invocations: int


@dataclasses.dataclass(frozen=True)
class AdoptionDecision:
    """The typed outcome plus every input a reader needs to audit it. The
    ``under_powered`` flag rides EVERY decision so an ADOPTED_AND_CONVERTS
    under the floor carries its caveat in the record (a signal, not an
    inferential claim — AC7)."""

    outcome: AdoptionOutcome
    adoption_count: int
    adoption_denominator: int
    adoption_by_model: tuple[tuple[str, int, int], ...]
    rfws_denominator: int
    conversions: int
    regressions: int
    net: int
    under_powered: bool
    missing_required: tuple[str, ...]
    config_hash: str


def decide_adoption_outcome(
    config: AdoptionConfig, cells: Sequence[AdoptionCell]
) -> AdoptionDecision:
    """TOTAL PURE typed-outcome decider over per-case records (NEVER marginal
    counts — the signature admits only per-case rows). Every boundary is
    decided ONLY from ``config`` fields, in the committed precedence order
    (see module docstring)."""
    rfws = LocateBucket(config.rfws_bucket)
    exact = LocateBucket(config.exact_bucket)

    # Adoption: per-model clean-cell universes of the models actually run.
    models_run = sorted({c.model for c in cells})
    adoption_by_model: list[tuple[str, int, int]] = []
    for model in models_run:
        clean = [c for c in cells if c.model == model and c.rerun_bucket is not None]
        adopted = sum(1 for c in clean if c.symbols_invocations > 0)
        adoption_by_model.append((model, adopted, len(clean)))
    adoption_count = sum(adopted for _, adopted, _ in adoption_by_model)
    adoption_denominator = sum(denom for _, _, denom in adoption_by_model)

    # RFWS denominator: the committed 0040 clean RFWS cells belonging to the
    # models actually run (carried on the cells as baseline buckets).
    rfws_denominator = sum(1 for c in cells if c.baseline_bucket is rfws)

    # Conversion predicate: BIDIRECTIONAL, from retained per-case pairs only.
    retained = [
        c for c in cells if c.baseline_bucket is not None and c.rerun_bucket is not None
    ]
    conversions = sum(
        1 for c in retained if c.baseline_bucket is rfws and c.rerun_bucket is exact
    )
    regressions = sum(
        1 for c in retained if c.baseline_bucket is exact and c.rerun_bucket is rfws
    )
    net = conversions - regressions
    converts_signal = any(
        c.baseline_bucket is rfws
        and c.rerun_bucket is exact
        and c.symbols_invocations > 0
        for c in retained
    )

    under_powered = rfws_denominator < config.min_rfws_denominator

    if adoption_count == 0:
        outcome = AdoptionOutcome.STILL_NOT_ADOPTED
    elif converts_signal:
        outcome = AdoptionOutcome.ADOPTED_AND_CONVERTS
    elif under_powered:
        outcome = AdoptionOutcome.ADOPTED_UNDER_POWERED
    else:
        outcome = AdoptionOutcome.ADOPTED_NO_CONVERSION

    missing_required = tuple(
        m for m in config.required_models if m not in set(models_run)
    )
    return AdoptionDecision(
        outcome=outcome,
        adoption_count=adoption_count,
        adoption_denominator=adoption_denominator,
        adoption_by_model=tuple(adoption_by_model),
        rfws_denominator=rfws_denominator,
        conversions=conversions,
        regressions=regressions,
        net=net,
        under_powered=under_powered,
        missing_required=missing_required,
        config_hash=adoption_config_hash(config),
    )


# ---- baseline ledger + cell builder --------------------------------------------


class AdoptionPrecheckError(RuntimeError):
    pass


def load_committed_0040_pilot_ledger() -> dict[str, Any]:
    """THE committed 0040 pilot ledger — archive-first path REUSED from
    ``pool_fork`` (one path oracle), validated against the frozen 0040 hash
    the pre-registered config pins."""
    path = _committed_pilot_ledger_path()
    if not path.is_file():
        raise AdoptionPrecheckError(f"committed 0040 pilot ledger not found: {path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    cfg = PREREGISTERED_ADOPTION_CONFIG_0042
    if obj.get("schema_version") != cfg.baseline_ledger_schema_version:
        raise AdoptionPrecheckError(
            f"unknown pilot-ledger schema_version: {obj.get('schema_version')!r}"
        )
    if obj.get("config_hash") != cfg.baseline_config_hash:
        raise AdoptionPrecheckError(
            "pilot ledger cites a different frozen 0040 config hash"
        )
    return obj


def build_adoption_cells(
    baseline_entries: Mapping[str, Mapping[str, Any]],
    rerun_entries: Mapping[str, Mapping[str, Any]],
    models: Sequence[str],
) -> list[AdoptionCell]:
    """Join the committed 0040 ledger with re-run records into per-case cells
    (both keyed ``case::model``). The cells actually run are the re-run keys —
    a 14b-only re-run yields 14b cells only, so every denominator downstream
    is per-model by construction. A degraded arm carries a ``None`` bucket."""

    def _bucket(cell: Mapping[str, Any] | None) -> LocateBucket | None:
        if not cell or cell.get("degrade") or not cell.get("bucket"):
            return None
        return LocateBucket(cell["bucket"])

    cells: list[AdoptionCell] = []
    for key, rerun in rerun_entries.items():
        case_id, _, model = key.partition("::")
        if model not in models:
            continue
        cells.append(
            AdoptionCell(
                case_id=case_id,
                model=model,
                baseline_bucket=_bucket(baseline_entries.get(key)),
                rerun_bucket=_bucket(rerun),
                symbols_invocations=int(rerun.get("symbols_invocations") or 0),
            )
        )
    return cells


# ---- committed frozen-config artifact + archive-first loader (AC5) -------------

ADOPTION_CONFIG_SCHEMA_VERSION = "0042/adoption-config/1"


def build_adoption_config_artifact() -> dict[str, Any]:
    """The committed frozen-config artifact — values + hash, single-sourced
    from the in-code freeze (no timestamp, per the 0040 artifact shape)."""
    return {
        "schema_version": ADOPTION_CONFIG_SCHEMA_VERSION,
        "config_hash": ADOPTION_CONFIG_HASH_0042,
        "config": dataclasses.asdict(PREREGISTERED_ADOPTION_CONFIG_0042),
    }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def committed_adoption_config_path(root: Path | None = None) -> Path:
    """THE committed 0042 frozen config — archive-first (the evidence-path
    convention: pin ``specs/.archive/...`` from authoring, live fallback)."""
    base = root if root is not None else _repo_root()
    archived = (
        base / "specs" / ".archive" / "0042-adoption" / "precheck"
        / "adoption_config.json"
    )
    live = base / "specs" / "0042-adoption" / "precheck" / "adoption_config.json"
    return archived if archived.is_file() else live


def load_committed_adoption_config(root: Path | None = None) -> dict[str, Any]:
    path = committed_adoption_config_path(root)
    if not path.is_file():
        raise AdoptionPrecheckError(f"committed 0042 adoption config not found: {path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if obj.get("schema_version") != ADOPTION_CONFIG_SCHEMA_VERSION:
        raise AdoptionPrecheckError(
            f"unknown adoption-config schema_version: {obj.get('schema_version')!r}"
        )
    return obj
