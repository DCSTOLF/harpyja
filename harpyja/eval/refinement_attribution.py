"""Spec 0045 — per-cell attribution over 0044's committed firing data (AC1, T7).

Applied AFTER the stage-1 table freeze (T3). Reads 0044's committed per-cell
submission artifacts (pinned by a manifest sha256) and attributes:

- each FIRED-ON-WRONG-SPAN cell's triggering signal and its weakness — all six
  fired on ``symbols-exact-span`` with grep-inside-symbol containment 0 and
  convergent evidence False, i.e. a WEAK SINGLETON (an uncorroborated bounded
  symbols span);
- the NEVER-FIRED found-unsubmitted cell (``pytest-10081::14b``): the 0044 gate
  never credited its gold span (it sat inside an over-bound symbols batch),
  and it too was uncorroborated — recorded as DATA (``had_corroboration`` False),
  which is why the require-corroboration rule fixes direction (a) but does not
  rescue this cell live (the recorded residual).

The attribution builds the shape consumed by the FROZEN table's
``select_ranking_rule``. The (b)/(c) recompute path delegates to the moved
scout helpers BY IDENTITY (one definition) — the primary diagnosis reads the
committed fields (AC1: no new compute first).
"""

from __future__ import annotations

import glob
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from harpyja.eval.discriminator_table import SelectionRow, select_ranking_rule
from harpyja.scout.confidence_signals import (
    convergent_evidence,
    grep_hits_inside_symbol_spans,
)

# The pinned committed 0044 firing artifacts (32 per-cell files).
ATTRIBUTION_SOURCE_DIR = "specs/.archive/0044-submission/submission_run/artifacts"
ATTRIBUTION_SOURCE_SHA256 = (
    "a09881af455b346af098ceabb8309a4db486ffe6000678d4f4a2441ab4fed0bc"
)

_NEVER_FIRED_CELL = "pytest-dev__pytest-10081::qwen3:14b"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _source_files() -> list[str]:
    root = _repo_root()
    return sorted(glob.glob(str(root / ATTRIBUTION_SOURCE_DIR / "*.submission.json")))


def attribution_source_sha256() -> str:
    """Manifest sha256 over the pinned committed artifacts (rel-name + bytes)."""
    h = hashlib.sha256()
    for f in _source_files():
        rel = ATTRIBUTION_SOURCE_DIR + "/" + Path(f).name
        h.update(rel.encode("utf-8"))
        h.update(Path(f).read_bytes())
    return h.hexdigest()


def load_0044_firing_cells() -> dict[str, dict[str, Any]]:
    """Committed per-cell records keyed ``case_id::model``."""
    cells: dict[str, dict[str, Any]] = {}
    for f in _source_files():
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        cells[f"{d['case_id']}::{d['model']}"] = d
    return cells


def _is_weak_singleton(cell: Mapping[str, Any]) -> bool:
    """Uncorroborated: no grep-inside-symbol containment, no convergence."""
    return (
        (cell.get("grep_hits_inside_symbol_spans") or 0) == 0
        and not cell.get("convergent_evidence")
    )


def diagnose_fired_on_wrong_span(
    cells: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, cell in sorted(cells.items()):
        if cell.get("confidence_null") != "fired-on-wrong-span":
            continue
        rows.append({
            "cell": key,
            "model": cell.get("model"),
            "terminal_bucket": cell.get("terminal_bucket"),
            "triggering_signal": cell.get("confidence_triggering_signal"),
            "grep_hits_inside_symbol_spans": cell.get("grep_hits_inside_symbol_spans"),
            "convergent_evidence": cell.get("convergent_evidence"),
            "is_weak_singleton": _is_weak_singleton(cell),
        })
    return rows


def diagnose_never_fired(cells: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    cell = cells[_NEVER_FIRED_CELL]
    had_corroboration = not _is_weak_singleton(cell)
    return {
        "cell": _NEVER_FIRED_CELL,
        "confidence_fired": cell.get("confidence_fired"),
        "submission_outcome": cell.get("submission_outcome"),
        "had_corroboration": had_corroboration,
        "unrecognised_evidence": (
            "the gold span sat inside an OVER-BOUND symbols batch (>5 spans) the "
            "0044 gate rejected as a candidate list; here it was uncorroborated "
            "(containment 0, convergence False), so require-corroboration fixes "
            "direction (a) but does not rescue this cell live — the residual"
        ),
    }


def build_attribution_shape(cells: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    """The shape consumed by the FROZEN table's ``select_ranking_rule``."""
    wrong = diagnose_fired_on_wrong_span(cells)
    never = diagnose_never_fired(cells)
    return {
        "wrong_span_all_weak_singleton": bool(wrong)
        and all(r["is_weak_singleton"] for r in wrong),
        "wrong_span_fired_on_non_symbols": any(
            r["triggering_signal"] != "symbols-exact-span" for r in wrong
        ),
        "never_fired_cell_had_corroboration": never["had_corroboration"],
    }


def select_refined_rule() -> SelectionRow:
    """Apply the FROZEN stage-1 table over the committed attribution shape."""
    return select_ranking_rule(build_attribution_shape(load_0044_firing_cells()))


def recompute_signals(trajectory: Mapping[str, Any]) -> dict[str, Any]:
    """Recompute (b)/(c) fresh over a trajectory via the moved scout helpers.

    Provenance path — the primary diagnosis reads committed fields; this proves
    the same one-definition helpers back the committed values.
    """
    return {
        "grep_hits_inside_symbol_spans": grep_hits_inside_symbol_spans(trajectory),
        "convergent_evidence": convergent_evidence(trajectory),
    }


# One-definition provenance handles (asserted by identity in the test).
recompute_signals.__wrapped_containment__ = grep_hits_inside_symbol_spans
recompute_signals.__wrapped_convergence__ = convergent_evidence
