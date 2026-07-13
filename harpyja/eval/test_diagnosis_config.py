"""Spec 0043 T10 — PREREGISTERED_DIAGNOSIS_CONFIG_0043 (AC5, stage 2).

Stage 2 of the two-stage freeze: the config — cells, SUT pin, gate proof
version, counted buckets, detector version, the SELECTED lever, and the power
floors — is frozen + hashed + committed AFTER the frozen lever table has
mechanically selected the lever from the committed T9 attribution, BEFORE any
live compute is spent.
"""

import json
from pathlib import Path

from harpyja.eval import submission_gap
from harpyja.eval.adoption_precheck import PREREGISTERED_ADOPTION_CONFIG_0042
from harpyja.eval.diagnosis_config import (
    DIAGNOSIS_CONFIG_HASH_0043,
    PREREGISTERED_DIAGNOSIS_CONFIG_0043,
    compute_sut_hash,
    diagnosis_config_hash,
)
from harpyja.eval.lever_table import (
    LEVER_TABLE_HASH_0043,
    LeverSignals,
    select_lever,
)

_REPO = Path(__file__).resolve().parents[2]
# Evidence-path convention: specs/.archive first, live specs/ fallback.
_ATTRIBUTION_ARCHIVED = (
    _REPO / "specs/.archive/0043-diagnosis/attribution/attribution_table.json"
)
_ATTRIBUTION_LIVE = _REPO / "specs/0043-diagnosis/attribution/attribution_table.json"
_ATTRIBUTION = (
    _ATTRIBUTION_ARCHIVED if _ATTRIBUTION_ARCHIVED.is_file() else _ATTRIBUTION_LIVE
)


def test_diagnosis_config_hash_is_stable():
    cfg = PREREGISTERED_DIAGNOSIS_CONFIG_0043
    assert DIAGNOSIS_CONFIG_HASH_0043 == diagnosis_config_hash(cfg)
    assert len(DIAGNOSIS_CONFIG_HASH_0043) == 64


def test_config_pins_0042_pilot_cells():
    """Cells are CONSUMED from the frozen 0042 adoption config — never
    re-selected — and model coverage likewise."""
    cfg = PREREGISTERED_DIAGNOSIS_CONFIG_0043
    assert cfg.pilot_case_ids == PREREGISTERED_ADOPTION_CONFIG_0042.pilot_case_ids
    assert cfg.required_models == PREREGISTERED_ADOPTION_CONFIG_0042.required_models
    assert cfg.optional_models == PREREGISTERED_ADOPTION_CONFIG_0042.optional_models


def test_config_pins_sut_hash_gate_proof_and_counted_buckets():
    cfg = PREREGISTERED_DIAGNOSIS_CONFIG_0043
    # The SUT pin: a hash over the frozen explorer-surface file list, so the
    # AFTER cells provably ran on the named (post-lever) SUT.
    assert cfg.sut_files  # frozen, non-empty
    assert cfg.sut_hash == compute_sut_hash()
    assert len(cfg.sut_hash) == 64
    # Re-measurement runs behind the 0041 gate; the proof rides the ledger.
    assert cfg.gate_proof_version == "0041/exclusivity/1"
    assert cfg.ledger_schema_version == "0041/pilot/2"
    # The exact counted buckets for movement (bidirectional, net surfaced).
    assert cfg.counted_buckets == (
        "correct",
        "right-file-wrong-span",
        "wrong-file",
        "empty",
    )


def test_config_detector_version_matches_submission_gap():
    """Identical detector on BOTH sides of the BEFORE/AFTER comparison."""
    cfg = PREREGISTERED_DIAGNOSIS_CONFIG_0043
    assert cfg.detector_version == submission_gap.DETECTOR_VERSION


def test_config_has_min_covered_before_cells_floor():
    """The 0042 MIN_RFWS_DENOMINATOR pattern: the power qualification is a
    frozen config value, so under-powered is a mechanical branch. Two floors:
    the covered BEFORE subset (trajectories that survived in eval_work) and
    the BEFORE found-unsubmitted denominator (the class whose drop types the
    outcome — a floor on coverage alone would leave 'drops' vacuous at 0)."""
    cfg = PREREGISTERED_DIAGNOSIS_CONFIG_0043
    assert cfg.min_covered_before_cells == 8
    assert cfg.min_before_found_unsubmitted == 3


def test_config_names_selected_lever_from_frozen_table():
    """The lever-under-test is MECHANICAL: exactly what the frozen (stage-1)
    table selects over the committed T9 attribution — not chosen by hand."""
    cfg = PREREGISTERED_DIAGNOSIS_CONFIG_0043
    table = json.loads(_ATTRIBUTION.read_text())
    assert table["lever_table_hash"] == LEVER_TABLE_HASH_0043
    committed = select_lever(LeverSignals(**table["lever_signals"]))
    assert cfg.levers_under_test == (committed.lever,)
    assert cfg.lever_table_hash == LEVER_TABLE_HASH_0043
