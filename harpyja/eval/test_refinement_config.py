"""RED (0045 T13, AC4): PREREGISTERED_REFINEMENT_CONFIG_0045 — stage 2 freeze.

The config carries LITERALS drift-pinned to the SUT constants, BOTH comparison
axes pinned by path + sha256, and the comparison literals RE-DERIVED from the
pinned 0044 artifacts in the pin test (the anti-tautology discipline). It is
hashed + committed AFTER the refined gate lands and BEFORE any live call (T23).
"""

import dataclasses
import hashlib
from pathlib import Path

import pytest

from harpyja.eval.refinement_config import (
    PREREGISTERED_REFINEMENT_CONFIG_0045,
    REFINEMENT_CONFIG_HASH_0045,
    RefinementConfig,
    compute_sut_hash,
    derive_0044_comparator,
    refinement_config_hash,
)
from harpyja.eval.refinement_outcome import RefinementVerdict
from harpyja.scout.confidence_gate import CONFIDENCE_MAX_QUALIFYING_SPANS

_CFG = PREREGISTERED_REFINEMENT_CONFIG_0045
_ROOT = Path(__file__).resolve().parents[2]


def test_config_is_frozen_dataclass():
    assert dataclasses.is_dataclass(_CFG)
    assert isinstance(_CFG, RefinementConfig)
    assert _CFG.config_id == "0045/refinement-config/1"
    with pytest.raises(dataclasses.FrozenInstanceError):
        _CFG.min_covered_joined_cells = 0


def test_config_hash_is_stable():
    assert refinement_config_hash(_CFG) == REFINEMENT_CONFIG_HASH_0045
    assert refinement_config_hash(_CFG) == refinement_config_hash(_CFG)


def test_baseline_axis_pinned_by_path_and_sha256():
    path = _ROOT / _CFG.baseline_table_path
    assert path.is_file()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == _CFG.baseline_table_sha256


def test_0044_comparator_results_pinned_by_path_and_sha256():
    path = _ROOT / _CFG.comparator_results_path
    assert path.is_file()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == _CFG.comparator_results_sha256


def test_0044_comparator_config_pinned_by_path_and_sha256():
    path = _ROOT / _CFG.comparator_config_path
    assert path.is_file()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == _CFG.comparator_config_sha256


def test_0044_per_cell_artifacts_dir_pinned_32_files():
    d = _ROOT / _CFG.comparator_artifacts_dir
    assert d.is_dir()
    assert len(sorted(d.glob("*.submission.json"))) == _CFG.comparator_artifacts_count == 32


def test_comparison_literals_rederived_from_pinned_artifacts():
    derived = derive_0044_comparator()
    # net per model — re-derived from the BEFORE(adoption_0042) x AFTER join.
    assert derived["net_by_model"] == dict(_CFG.comparator_net_by_model)
    assert _CFG.comparator_net_by_model == (
        ("qwen3:14b", 1), ("qwen3:8b", 0), ("qwen3.5:4b", 1)
    )
    # fu_after and s->wc re-derived from the committed per-cell artifacts.
    assert derived["fu_after"] == _CFG.comparator_fu_after == 1
    assert derived["swc_by_model"] == dict(_CFG.comparator_swc_by_model)
    assert derived["swc_total"] == _CFG.comparator_swc_total == 5


def test_swc_by_model_rederived_5_from_artifacts():
    derived = derive_0044_comparator()
    assert derived["swc_by_model"] == {"qwen3:8b": 5}
    assert _CFG.comparator_swc_total == 5


def test_power_floor_min_covered_joined_cells_is_8():
    # A LIVE-run power check — a degrade-thinned join trips it.
    assert _CFG.min_covered_joined_cells == 8


def test_power_floor_min_comparator_swc_is_3_documented_as_rederivation_guard():
    # Checked against the freeze-time re-derived comparator (5), so it can only
    # pass at runtime — a RE-DERIVATION GUARD, not a live power check.
    assert _CFG.min_comparator_swc == 3
    assert _CFG.comparator_swc_total >= _CFG.min_comparator_swc
    assert "re-derivation guard" in _CFG.min_comparator_swc_role.lower()


def test_six_member_precedence_encoded():
    assert _CFG.verdict_precedence == (
        "UNDER_POWERED",
        "TRADES_DIRECTIONS",
        "RESIDUAL_PERSISTS",
        "GATE_INERT",
        "GATE_CALIBRATED",
        "MISCALIBRATION_REMAINS",
    )
    # Exactly the six enum members, in order.
    assert _CFG.verdict_precedence == tuple(m.name for m in RefinementVerdict)


def test_gate_projection_matches_sut_constants():
    # LITERALS drift-pinned to the SUT truth (anti-tautology).
    assert _CFG.max_qualifying_spans == CONFIDENCE_MAX_QUALIFYING_SPANS
    assert _CFG.refined_rule_key == "require-corroboration"


def test_sut_hash_covers_refined_gate_and_moved_signals():
    assert "harpyja/scout/confidence_gate.py" in _CFG.sut_files
    assert "harpyja/scout/confidence_signals.py" in _CFG.sut_files
    assert "harpyja/scout/explorer_loop.py" in _CFG.sut_files
    assert _CFG.sut_hash == compute_sut_hash()


def test_named_cells_pinned():
    # AC5/AC6 targets carried as data.
    assert _CFG.residual_cell == "django__django-14315::qwen3:8b"
    assert _CFG.never_fired_cell == "pytest-dev__pytest-10081::qwen3:14b"
    assert all("pallets__flask-5014" in c for c in _CFG.rescued_cells_hold_correct)
    assert len(_CFG.rescued_cells_hold_correct) == 2


def test_committed_refinement_config_matches_computed_truth():
    """T23 (stage-2 freeze pin): the COMMITTED config artifact names the in-code
    frozen config, committed AFTER the SUT landed / BEFORE the live call.

    HISTORICAL note (post-close operator revert): after the 0045 measurement, the
    require-corroboration gate was REVERTED to 0044's `qualifying_symbols_spans`
    (verdict TRADES_DIRECTIONS), which evolved `scout/explorer_loop.py` — a hashed
    SUT file. So the live `compute_sut_hash()` no longer equals the `sut_hash`
    0045 froze for its run: the freeze is HISTORICAL (the same reconciliation 0045
    applied to 0044's pin). This test guards the committed artifact's INTERNAL
    CONSISTENCY and that every field EXCEPT the now-evolved `sut_hash` still
    matches the in-code config."""
    import hashlib
    import json

    committed_path = (
        _ROOT / "specs" / "0045-refinement" / "refinement_config"
        / "refinement_config.json"
    )
    archived_path = (
        _ROOT / "specs" / ".archive" / "0045-refinement"
        / "refinement_config" / "refinement_config.json"
    )
    path = archived_path if archived_path.is_file() else committed_path
    assert path.is_file(), (
        "stage-2 freeze artifact missing — commit refinement_config.json "
        "BEFORE any live call (T23)"
    )
    committed = json.loads(path.read_text(encoding="utf-8"))
    assert committed["schema_version"] == "0045/refinement-config/1"
    # Internal consistency: config_hash recomputes from the committed config dict.
    recomputed = hashlib.sha256(
        json.dumps(committed["config"], sort_keys=True).encode("utf-8")
    ).hexdigest()
    assert committed["config_hash"] == recomputed
    # Every field except the reverted-SUT-evolved sut_hash still matches.
    expected = json.loads(json.dumps(dataclasses.asdict(_CFG), default=list))
    got = dict(committed["config"])
    expected.pop("sut_hash")
    got.pop("sut_hash")
    assert got == expected
    # The frozen 0045 sut_hash is a valid digest that now DIFFERS from live
    # (the operator revert evolved the SUT) — the historical freeze made explicit.
    assert len(committed["config"]["sut_hash"]) == 64
    assert committed["config"]["sut_hash"] != compute_sut_hash()
