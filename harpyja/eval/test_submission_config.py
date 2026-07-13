"""RED (0044 T12, AC5): PREREGISTERED_SUBMISSION_CONFIG_0044 — stage 2 of the
two-stage freeze.

The config carries LITERALS (never references to the SUT constants) and the
drift pins below bind them to the SUT truth — a config that silently diverges
from the shipped gate/template fails loudly here, and the committed JSON
artifact (T21) is pinned against this object by
``test_committed_submission_config_matches_computed_truth`` (in
test_submission_run_integration).
"""

import dataclasses
import hashlib
import json
from pathlib import Path

import pytest

from harpyja.eval.submission_config import (
    PREREGISTERED_SUBMISSION_CONFIG_0044,
    SUBMISSION_CONFIG_HASH_0044,
    compute_sut_hash,
    submission_config_hash,
)
from harpyja.eval.submission_gap import DETECTOR_VERSION
from harpyja.scout.confidence_gate import (
    CONFIDENCE_MAX_QUALIFYING_SPANS,
    CONFIDENCE_NUDGE_TEMPLATE,
    CONFIDENCE_SIGNAL,
)

_CFG = PREREGISTERED_SUBMISSION_CONFIG_0044
_ROOT = Path(__file__).resolve().parents[2]


def test_config_is_frozen_dataclass():
    assert dataclasses.is_dataclass(_CFG)
    assert _CFG.config_id == "0044/submission-config/1"
    with pytest.raises(dataclasses.FrozenInstanceError):
        _CFG.min_covered_before_cells = 0


def test_config_hash_is_stable():
    assert submission_config_hash(_CFG) == SUBMISSION_CONFIG_HASH_0044
    # Deterministic: recomputation over the same object is identical.
    assert submission_config_hash(_CFG) == submission_config_hash(_CFG)


def test_gate_projection_max_spans_matches_sut_constant():
    # The config carries the LITERAL; this pin binds it to the SUT truth.
    assert _CFG.max_qualifying_spans == CONFIDENCE_MAX_QUALIFYING_SPANS
    assert _CFG.confidence_signal == CONFIDENCE_SIGNAL


def test_config_nudge_template_matches_sut_surface():
    # The 0042 prompt↔surface drift-guard pattern applied to the nudge: the
    # frozen config's template is byte-identical to the shipped SUT surface.
    assert _CFG.nudge_template == CONFIDENCE_NUDGE_TEMPLATE
    assert _CFG.nudge_role == "user"


def test_never_fires_threshold_is_numeric_field():
    # Round-2 codex: the NEVER_FIRES threshold is DATA, not prose — keyed to
    # the pre-registered beneficiary model only.
    assert isinstance(_CFG.never_fires_max_beneficiary_firings, int)
    assert _CFG.never_fires_max_beneficiary_firings == 0
    assert _CFG.beneficiary_model == "qwen3:14b"
    assert _CFG.beneficiary_model in _CFG.required_models


def test_power_floors_present():
    # Reused verbatim from the frozen 0043 config.
    assert _CFG.min_covered_before_cells == 8
    assert _CFG.min_before_found_unsubmitted == 3


def test_baseline_ledger_identity_pins_path_and_hash():
    # BEFORE = the committed 0040/0042 pre-nudge ledger (the 0043 attribution
    # table), pinned by path + sha256 — a baseline-identity error is loud, and
    # fu_before re-derives to 6 (14b 2 / 8b 1 / 4b 3), clearing the floor.
    path = _ROOT / _CFG.baseline_table_path
    assert path.is_file()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == _CFG.baseline_table_sha256
    table = json.loads(path.read_text(encoding="utf-8"))
    assert table["detector_version"] == _CFG.detector_version == DETECTOR_VERSION
    rows = [r for r in table["cases"] if r.get("run") == _CFG.baseline_run]
    fu = [r for r in rows if r.get("submission_outcome") == "found-unsubmitted"]
    assert len(fu) == 6
    per_model = {m: sum(1 for r in fu if r["model"] == m)
                 for m in {r["model"] for r in fu}}
    assert per_model == {"qwen3:14b": 2, "qwen3:8b": 1, "qwen3.5:4b": 3}
    assert len(fu) >= _CFG.min_before_found_unsubmitted


def test_sut_hash_covers_confidence_gate_file():
    # The gate is NEW SUT surface — omitting it from the hash would let the
    # predicate drift after the freeze.
    assert "harpyja/scout/confidence_gate.py" in _CFG.sut_files
    assert "harpyja/scout/context_map.py" in _CFG.sut_files
    assert "harpyja/scout/explorer_loop.py" in _CFG.sut_files
    assert _CFG.sut_hash == compute_sut_hash()


def test_per_model_readings_present():
    # OQ2/OQ3 pre-registered as DATA in the config, not close-time prose.
    readings = dict(_CFG.expected_model_readings)
    assert set(readings) == {"qwen3:14b", "qwen3:8b", "qwen3.5:4b"}
    assert "regressions" in readings["qwen3:8b"]  # regressions=0 at ANY firing rate
    assert "inert" in readings["qwen3.5:4b"]
    assert "beneficiary" in readings["qwen3:14b"]


def test_run_knobs_byte_identical_to_0043_run():
    # The AFTER run repeats the 0042/0043 knobs verbatim — the lever is the
    # ONLY deliberate SUT delta.
    assert _CFG.scout_max_turns == 10
    assert _CFG.scout_wall_clock_s == 240.0
    assert _CFG.lm_http_timeout_s == 300.0
    assert _CFG.explorer_think is None


def test_coverage_consumed_from_frozen_0042_config():
    from harpyja.eval.adoption_precheck import PREREGISTERED_ADOPTION_CONFIG_0042

    assert _CFG.pilot_case_ids == PREREGISTERED_ADOPTION_CONFIG_0042.pilot_case_ids
    assert _CFG.required_models == PREREGISTERED_ADOPTION_CONFIG_0042.required_models
    assert _CFG.optional_models == PREREGISTERED_ADOPTION_CONFIG_0042.optional_models


def test_sut_delta_names_removal_and_addition():
    # One delta, two named parts — the comparison is two-armed, never silently
    # three-armed (the shipped 0043 sentence's removal is explicit).
    assert _CFG.sut_delta == (
        "remove-0043-unconditional-nudge",
        "add-confidence-conditioned-mid-loop-nudge",
    )
    assert _CFG.levers_under_test == ("confidence-conditioned-submit-nudge",)
