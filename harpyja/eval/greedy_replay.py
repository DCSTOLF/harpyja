"""Spec 0049 (AC5/AC6) — the greedy replay-reproduction proof + typed outcome.

The bucket taxonomy is REUSED BY IDENTITY from ``locate_accuracy.LocateBucket``
(no oracle change — the 0049 invariant). This module owns only:

- ``greedy_replay_proof`` — the ≥3-draw orchestration: per (tag, case) cell,
  ``reproduce`` iff all draws classify into the IDENTICAL ``LocateBucket``, else
  ``flip``. The proof keys on the BUCKET, not the trajectory / tool-path (0048 saw
  9-vs-6 tool paths in the same bucket). Any single cell flip → the GLOBAL typed
  outcome ``RESIDUAL_NONDETERMINISM`` (no per-tag cherry-pick), naming the offender.
- ``build_greedy_replay_artifact`` — the drift-pinned per-cell artifact schema,
  carrying the tag's COMMITTED fingerprint (chain of custody) + the validated
  0041 exclusivity record.

Pure: draws are pre-classified ``LocateBucket`` members; no model, no I/O.
"""

from __future__ import annotations

import dataclasses
import enum
from collections.abc import Iterable, Sequence

from harpyja.eval.bakeoff_config import BakeoffConfig
from harpyja.eval.exclusivity_gate import validate_exclusivity_record
from harpyja.eval.locate_accuracy import LocateBucket

MIN_DRAWS_PER_CELL = 3


class GreedyServingOutcome(enum.Enum):
    """The global 0049 verdict — mutually exclusive, never a per-tag cherry-pick."""

    GREEDY_REPRODUCIBLE = "greedy-reproducible"
    RESIDUAL_NONDETERMINISM = "residual-nondeterminism"


@dataclasses.dataclass(frozen=True)
class ReplayCell:
    """One (tag, case) reproduction cell: K pre-classified bucket draws."""

    tag: str
    case_id: str
    repo: str
    draws: tuple[LocateBucket, ...]


# The drift-pinned per-cell artifact schema (AC5).
GREEDY_REPLAY_ARTIFACT_KEYS = (
    "repo",
    "case_id",
    "tag",
    "committed_fingerprint",
    "buckets",
    "verdict",
    "exclusivity",
)


def greedy_replay_proof(
    cells: Iterable[ReplayCell], *, min_draws: int = MIN_DRAWS_PER_CELL
) -> dict:
    """Adjudicate per-cell reproduce/flip and the global typed outcome.

    Raises ``ValueError`` if any cell has < ``min_draws`` draws (a 2-draw compare
    is too weak given the single-draw-noise premise) and ``TypeError`` if any draw
    is not a ``LocateBucket`` (the taxonomy is the oracle, reused by identity).
    """

    cell_results: list[dict] = []
    flips: list[tuple[str, str]] = []
    for cell in cells:
        if len(cell.draws) < min_draws:
            raise ValueError(
                f"cell ({cell.tag}, {cell.case_id}) has {len(cell.draws)} draws; "
                f"the replay proof requires ≥{min_draws} per cell"
            )
        if not all(isinstance(d, LocateBucket) for d in cell.draws):
            raise TypeError(
                "replay draws must be LocateBucket members (the reused taxonomy)"
            )
        reproduces = len(set(cell.draws)) == 1
        verdict = "reproduce" if reproduces else "flip"
        if not reproduces:
            flips.append((cell.tag, cell.case_id))
        cell_results.append(
            {
                "tag": cell.tag,
                "case_id": cell.case_id,
                "repo": cell.repo,
                "buckets": [b.value for b in cell.draws],
                "verdict": verdict,
            }
        )

    outcome = (
        GreedyServingOutcome.GREEDY_REPRODUCIBLE
        if not flips
        else GreedyServingOutcome.RESIDUAL_NONDETERMINISM
    )
    return {"outcome": outcome, "cells": cell_results, "flips": flips}


def build_greedy_replay_artifact(
    cfg: BakeoffConfig,
    *,
    tag: str,
    case_id: str,
    repo: str,
    buckets: Sequence[LocateBucket],
    verdict: str,
    exclusivity_record: dict,
) -> dict:
    """The drift-pinned per-cell proof artifact (committed fingerprint + exclusivity)."""

    validate_exclusivity_record(exclusivity_record)
    fingerprints = dict(cfg.served_variant_fingerprints)
    if tag not in fingerprints:
        raise KeyError(f"no committed fingerprint for greedy tag {tag!r}")
    return {
        "repo": repo,
        "case_id": case_id,
        "tag": tag,
        "committed_fingerprint": fingerprints[tag],
        "buckets": [b.value for b in buckets],
        "verdict": verdict,
        "exclusivity": exclusivity_record,
    }


__all__ = [
    "GREEDY_REPLAY_ARTIFACT_KEYS",
    "MIN_DRAWS_PER_CELL",
    "GreedyServingOutcome",
    "ReplayCell",
    "build_greedy_replay_artifact",
    "greedy_replay_proof",
]
